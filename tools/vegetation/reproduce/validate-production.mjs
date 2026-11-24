import { readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const root = path.resolve(process.env.VEGETATION_DATA_DIR ?? process.cwd());
const moduleDir = path.resolve(process.env.VEGETATION_MODULE_DIR ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../.."));
const { gameXZ } = await import(pathToFileURL(path.join(moduleDir, "capability-evidence.js")).href);
const modelPath = path.resolve(process.argv[2] ?? path.join(moduleDir, "vegetation-model.js"));
const label = process.argv[3] ?? "production";
const baselineAlpha = Number(process.argv[4] ?? 0);
const baselineRadiusM = Number(process.argv[5] ?? 25000);
const modelBytes = await readFile(modelPath);
const dependencyUrl = pathToFileURL(path.join(moduleDir, "capability-evidence.js")).href;
const modelSource = modelBytes.toString("utf8").replace('from "./capability-evidence.js"', `from "${dependencyUrl}"`);
// Import the measured exact bytes; concurrent writer edits cannot change this run.
const { compositionSampler } = await import(`data:text/javascript;base64,${Buffer.from(modelSource).toString("base64")}`);
const blockM = 1000, bufferM = 250, minTest = 30;
const centers = { boston: { lon: -71.057, lat: 42.36 }, asheville: { lon: -82.555, lat: 35.58 } };
const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
const readJSON = async (filename) => JSON.parse(await readFile(path.join(root, filename), "utf8"));
const mean = (values) => values.reduce((sum, value) => sum + value, 0) / values.length;
function counts(records) {
  const map = new Map();
  for (const record of records) map.set(record.genus, (map.get(record.genus) ?? 0) + 1);
  return map;
}
function metrics(truth, prediction, vocabulary) {
  let tvd = 0, js = 0, crossEntropy = 0, zeroMass = 0;
  for (const name of vocabulary) {
    const q = truth.get(name) ?? 0, p = prediction.get(name) ?? 0, midpoint = (q + p) / 2;
    tvd += Math.abs(q - p) / 2;
    if (q) {
      js += q * Math.log2(q / midpoint) / 2;
      crossEntropy -= q * Math.log(Math.max(p, 1e-9));
      if (!p) zeroMass += q;
    }
    if (p) js += p * Math.log2(p / midpoint) / 2;
  }
  const top = (distribution) => [...distribution].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0]?.[0];
  return { tvd, js_divergence_bits: js, clipped_cross_entropy_nats: crossEntropy, test_mass_with_zero_predicted_share: zeroMass, top_genus_correct: Number(top(truth) === top(prediction)), top_genus: top(prediction) };
}
function summary(folds) {
  const paired = folds.filter((fold) => fold.local !== null);
  const out = { heldout_blocks: folds.length, heldout_records: folds.reduce((sum, f) => sum + f.test_n, 0), local_evaluable_blocks: paired.length, local_unknown_blocks: folds.filter((f) => f.local_unknown).length, local_tvd_wins: paired.filter((f) => f.local.tvd < f.regional.tvd).length, min_train_distance_to_heldout_block_m: Math.min(...folds.map((f) => f.min_train_distance_to_heldout_block_m)) };
  for (const method of ["local", "regional"]) {
    out[method] = {};
    for (const key of ["tvd", "js_divergence_bits", "clipped_cross_entropy_nats", "test_mass_with_zero_predicted_share", "top_genus_correct"]) out[method][key] = mean(paired.map((fold) => fold[method][key]));
  }
  out.mean_tvd_reduction = out.regional.tvd - out.local.tvd;
  out.production_methods = Object.fromEntries([...new Set(folds.map((f) => f.method))].map((method) => [method, folds.filter((f) => f.method === method).length]));
  return out;
}

const result = {
  evaluated_at: new Date().toISOString(),
  model_file: path.relative(path.dirname(root), modelPath), model_sha256: sha256(modelBytes),
  projection_module_sha256: sha256(await readFile(path.join(moduleDir, "capability-evidence.js"))),
  design: { block_width_m: blockM, exclusion_buffer_m: bufferM, min_test_records_per_block: minTest, target: "Entire 1km blocks contained in preset 17.28km square", training: "All same-source inventory records, excluding whole heldout block and rectangular 250m buffer; neither heldout block nor buffer enters model source-pool or baseline", projection: "Production gameXZ exact WGS84 local linearization; scale1 rotation0", query: "Actual exported compositionSampler at heldout block center, {urban:true}; no heldout coordinates or labels supplied", regional_baseline: `Training-only genus frequencies within ${baselineRadiusM}m of square center, symmetric pseudocount alpha=${baselineAlpha}; zero means unsmoothed source-pool proportions`, reporting: "Equal-weight paired block mean over blocks with local estimates; zero-share taxa scored with clipped probability1e-9 only for log-loss, also report their true test mass", unknown: "Unknown predictions excluded from both paired mean scores; coverage and unknown counts reported explicitly, not silently imputed", limitations: ["Within-source spatial transfer is not independent-source or cross-city validation.", "No abundance, individual height/crown, wild-versus-planted, or natural-only validation.", "Taxon vocabulary is source-wide; frequencies are strictly training-only.", "Final source-pool fallback was selected after the local-k24 benchmark failed; final results are not an untouched model-selection holdout."] },
  sources: {},
};
try {
  const committed = execFileSync("git", ["-C", moduleDir, "show", "HEAD:vegetation-model.js"]);
  result.model_commit = sha256(committed) === sha256(modelBytes)
    ? execFileSync("git", ["-C", moduleDir, "rev-parse", "HEAD"], { encoding: "utf8" }).trim()
    : null;
} catch {
  result.model_commit = null;
}

for (const source of ["boston", "asheville"]) {
  const square = { ...centers[source], rotation: 0, scale: 1 };
  const records = await readJSON(`${source}_inventory.json`);
  const points = records.map((record) => {
    const [x, z] = gameXZ(square, record.lon, record.lat);
    return { record, x, z, bx: Math.floor(x / blockM), bz: Math.floor(z / blockM) };
  });
  const vocabulary = [...new Set(records.map((r) => r.genus))].sort();
  const blockCounts = new Map();
  for (const p of points) {
    const key = `${p.bx},${p.bz}`;
    blockCounts.set(key, (blockCounts.get(key) ?? 0) + 1);
  }
  const folds = [];
  for (const [key, count] of [...blockCounts].sort(([a], [b]) => a.localeCompare(b))) {
    if (count < minTest) continue;
    const [bx, bz] = key.split(",").map(Number);
    const x0 = bx * blockM, z0 = bz * blockM, x1 = x0 + blockM, z1 = z0 + blockM;
    if (Math.max(Math.abs(x0), Math.abs(x1), Math.abs(z0), Math.abs(z1)) > 8640) continue;
    const test = points.filter((p) => p.bx === bx && p.bz === bz);
    const train = points.filter((p) => !(p.x >= x0 - bufferM && p.x <= x1 + bufferM && p.z >= z0 - bufferM && p.z <= z1 + bufferM));
    const minGap = Math.min(...train.map((p) => Math.hypot(Math.max(x0 - p.x, p.x - x1, 0), Math.max(z0 - p.z, p.z - z1, 0))));
    if (minGap < bufferM - 1e-7) throw new Error(`Buffer leakage ${source}:${key}`);
    const sampler = compositionSampler(square, train.map((p) => p.record));
    const prediction = sampler((x0 + x1) / 2, (z0 + z1) / 2, { urban: true });
    const truthCounts = counts(test.map((p) => p.record));
    const truth = new Map([...truthCounts].map(([name, n]) => [name, n / test.length]));
    const priorTrain = train.filter((p) => Math.hypot(p.x, p.z) <= baselineRadiusM);
    const regionalCounts = counts(priorTrain.map((p) => p.record));
    const denominator = priorTrain.length + baselineAlpha * vocabulary.length;
    const regional = new Map(vocabulary.map((name) => [name, ((regionalCounts.get(name) ?? 0) + baselineAlpha) / denominator]));
    const local = new Map(prediction.genus.map(({ genus, share }) => [genus, share]));
    folds.push({ source, block_x: bx, block_z: bz, test_n: test.length, train_n: train.length, baseline_train_n: priorTrain.length, buffer_excluded_n: records.length - test.length - train.length, min_train_distance_to_heldout_block_m: minGap, local_unknown: !prediction.genus.length, method: prediction.method ?? "rejected_k24_kernel", evidence: prediction.evidence, truth: [...truth].map(([genus, share]) => ({ genus, share })), local: prediction.genus.length ? metrics(truth, local, vocabulary) : null, regional: metrics(truth, regional, vocabulary), local_prediction: prediction.genus });
  }
  const sourceSummary = summary(folds);
  result.sources[source] = sourceSummary;
  await writeFile(path.join(root, `${source}_${label}_heldout_blocks.json`), JSON.stringify(folds, null, 2));
  console.log(source, JSON.stringify(sourceSummary), { model_sha256: result.model_sha256 });
}
await writeFile(path.join(root, `${label}_benchmark.json`), JSON.stringify(result, null, 2));

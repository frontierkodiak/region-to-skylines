// node tools/vegetation-sheet.mjs TRUTH_DATA_DIR OUTPUT_DIR
// Sources are reacquired independently; composition uses the named Cabinet snapshot.
import { readFile, writeFile, mkdir, copyFile } from "node:fs/promises";
import { resolve, join } from "node:path";
import { gzipSync } from "node:zlib";
import { createHash } from "node:crypto";
import { fromUrl } from "geotiff";
import { vegetationExpectation, growthForm } from "../vegetation-inputs.js";

const [truthArg, outputArg] = process.argv.slice(2);
if (!truthArg || !outputArg) throw new Error("Pass TRUTH_DATA_DIR OUTPUT_DIR");
const truth = resolve(truthArg), out = resolve(outputArg);
await mkdir(out, { recursive: true });
const squares = [
  ["Asheville", "asheville", -82.555, 35.58], ["Boston", "boston", -71.057, 42.36],
  ["Innsbruck", "innsbruck", 11.4, 47.27], ["Rio de Janeiro", "rio", -43.205, -22.94],
  ["Charleston", "charleston", -79.93, 32.78], ["Boreal · Rovaniemi", "rovaniemi", 25.7294, 66.5039],
];
const sheet = { generated_at: new Date().toISOString(), schema: "polli.vegetation-sheet/1", squares: [] };
const manifest = { generated_at: sheet.generated_at, source_files: {}, outputs: {} };
for (const [name, slug, lon, lat] of squares) {
  const files = [`${slug}_treegoer_occurrences.json`, ...(["boston", "asheville"].includes(slug) ? [`${slug}_inventory.json`] : [])];
  const records = [], sources = [];
  for (const file of files) {
    const raw = await readFile(join(truth, file));
    const hash = createHash("sha256").update(raw).digest("hex"); manifest.source_files[file] = hash;
    records.push(...JSON.parse(raw).map((r) => ({ ...r, growth_form: growthForm(r.genus, {}, r.species) })));
    sources.push({ source: file, sha256: hash, dataset: file.includes("occurrences") ? "Cabinet iNaturalist metadata snapshot 20261027; exact TreeGOER species filter" : "Public city inventory retrieved 2026-11-23", status: "available" });
  }
  const report = await vegetationExpectation({ lon, lat, rotation: 0, scale: 1 }, { fromUrl, recordEvidence: { records, sources } });
  if (report.summary.canopy.coverage.fraction < 0.5) throw new Error(`${name}: insufficient height coverage`);
  const bytes = gzipSync(JSON.stringify(report), { mtime: 0 });
  await writeFile(join(out, `${slug}.json.gz`), bytes);
  manifest.outputs[`${slug}.json.gz`] = { sha256: createHash("sha256").update(bytes).digest("hex"), bytes: bytes.length };
  sheet.squares.push({ name, slug, square: report.square, grid: report.grid, summary: report.summary, counts: report.counts,
    canopy: report.cells.map((c) => c.canopy.cover), height: report.cells.map((c) => c.canopy.height_m.p50),
    sources: report.sources, limitations: report.limitations });
  console.log(JSON.stringify({ slug, cover: report.summary.canopy.cover, height: report.summary.canopy.height_m.p50, records: records.length, top: report.summary.composition.genus.slice(0, 3) }));
}
for (const file of ["final_source_pool_benchmark.json", "production_benchmark.json", "treegoer_query_receipt.json", "inat_receipt.json", "boston_receipt.json", "asheville_receipt.json"])
  await copyFile(join(truth, file), join(out, file));
await writeFile(join(out, "sheet-data.json"), JSON.stringify(sheet));
await writeFile(join(out, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
for (const file of ["index.html", "sheet.js", "sheet.css"]) await copyFile(new URL(`./vegetation-sheet/${file}`, import.meta.url), join(out, file));

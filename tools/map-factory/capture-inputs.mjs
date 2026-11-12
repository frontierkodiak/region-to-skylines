// Archive the shared page/CLI input pipeline and its exact Python work files.
// Run on blade: node tools/map-factory/capture-inputs.mjs OUTPUT SLUG...
// Build the unmodified CLI first in OUTPUT/live-pin/SLUG; equality is mandatory.
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { loadPyodide } from "pyodide";
import { fromUrl } from "geotiff";
import { PRESETS, DEFAULTS } from "../../terrain.js";
import { captureInputs } from "../../inputs.js";
import { startFactory, landCover, deposits, buildMap, clearWork, WORLDCOVER_S3, worldCoverFile, FACTORY_FILES } from "../../mapgen.js";

const [output, ...slugs] = process.argv.slice(2);
if (!output || !slugs.length) throw Error("Usage: capture-inputs.mjs OUTPUT SLUG...");
const root = fileURLToPath(new URL("../../", import.meta.url));
const sha = (b) => createHash("sha256").update(b).digest("hex");
const read = async (f) => new Uint8Array(await readFile(join(root, "tools/map-factory", f)));
const source = execFileSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8" }).trim();
const sourceFiles = {};
for (const f of ["inputs.js", "terrain.js", "mapgen.js", ...FACTORY_FILES.map((f) => "tools/map-factory/" + f)])
  sourceFiles[f] = sha(await readFile(join(root, f)));
const factory = await startFactory({ loadPyodide, read });
for (const slug of slugs) {
  const preset = PRESETS.find((p) => p.slug === slug);
  if (!preset) throw Error(`Unknown preset: ${slug}`);
  const sq = { lon: preset.lon, lat: preset.lat, rotation: 0, scale: 1, vscale: "auto", rivers: true, ...DEFAULTS, name: preset.name, slug };
  const status = (s) => console.error(`${slug}: ${s}`);
  clearWork(factory);
  const inputs = await captureInputs(sq, { status, about: { cli: "region-to-skylines" } });
  const cover = await landCover(factory, sq, { fromUrl, tileUrl: (t) => WORLDCOVER_S3 + worldCoverFile(t), status });
  const evidence = await deposits(factory, sq, { status });
  const built = await buildMap(factory, { ...inputs, landcover: cover.path, evidence: evidence?.path ?? null }, { status });
  const cli = await readFile(resolve(output, "live-pin", slug, `${slug}.crp`));
  if (sha(cli) !== sha(built.bytes)) throw Error(`${slug}: recapture differs from CLI: ${sha(built.bytes)} != ${sha(cli)}`);
  const folder = resolve(output, "captures", slug);
  const files = {};
  async function copy(from, to) {
    await mkdir(to, { recursive: true });
    for (const name of factory.py.FS.readdir(from).filter((n) => ![".", ".."].includes(n))) {
      const path = `${from}/${name}`, target = join(to, name);
      if (factory.py.FS.isDir(factory.py.FS.stat(path).mode)) await copy(path, target);
      else {
        const bytes = factory.py.FS.readFile(path);
        await writeFile(target, bytes);
        files[path.slice(6)] = sha(bytes);
      }
    }
  }
  await copy("/work", folder);
  await writeFile(join(folder, "landcover.json"), JSON.stringify({ source: "ESA WorldCover 2021 v200; mapgen.js landCover", sq, tiles: cover.tiles, classes: cover.classes }, null, 2) + "\n");
  await writeFile(join(folder, "capture.json"), JSON.stringify({ source_commit: source, source_files_sha256: sourceFiles, slug, sq, cli_sha256: sha(cli), crp_sha256: sha(built.bytes), evidence_available: evidence !== null, files_sha256: files }, null, 2) + "\n");
  console.log(`${slug}: ${sha(built.bytes)} (equals live-pin CLI)`);
}
process.exit(0);

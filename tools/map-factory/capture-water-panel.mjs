// CPU/network preparation only. Never launches or installs the game.
// node tools/map-factory/capture-water-panel.mjs PANEL FROZEN OUTPUT
import { readFile, writeFile, mkdir, access } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { loadPyodide } from "pyodide";
import { fromUrl } from "geotiff";
import { DEFAULTS } from "../../terrain.js";
import { captureInputs } from "../../inputs.js";
import { startFactory, landCover, deposits, buildMap, clearWork, WORLDCOVER_S3, worldCoverFile, FACTORY_FILES } from "../../mapgen.js";

const [panelPath, frozenPath, outputPath] = process.argv.slice(2);
if (!outputPath) throw Error("Usage: capture-water-panel.mjs PANEL FROZEN OUTPUT");
const root = fileURLToPath(new URL("../../", import.meta.url));
const output = resolve(outputPath);
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const panelBytes = await readFile(panelPath), panel = JSON.parse(panelBytes);
const frozen = JSON.parse(await readFile(join(frozenPath, "freeze.json")));
if (sha(panelBytes) !== frozen.panel_sha256 || sha(await readFile(join(frozenPath, "model.json"))) !== frozen.model_sha256)
  throw Error("Panel or fitted model changed after freeze");
const source = execFileSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8" }).trim();
const sourceFiles = {};
for (const f of ["inputs.js", "terrain.js", "mapgen.js", ...FACTORY_FILES.map((f) => "tools/map-factory/" + f)]) {
  const bytes = await readFile(join(root, f));
  // Capture must not silently load uncommitted product code.
  if (sha(bytes) !== sha(execFileSync("git", ["show", `${source}:${f}`], { cwd: root }))) throw Error(`Dirty writer: ${f}`);
  sourceFiles[f] = sha(bytes);
}
await mkdir(output, { recursive: true });
const factory = await startFactory({ loadPyodide, read: async (f) => new Uint8Array(await readFile(join(root, "tools/map-factory", f))) });
let failed = 0;
for (const item of panel.squares) {
  const sq = { ...DEFAULTS, ...item.sq }, folder = join(output, sq.slug);
  try { await access(join(folder, "capture.json")); console.error(`${sq.slug}: preserved prior capture`); continue; } catch {}
  await mkdir(folder, { recursive: true });
  const status = (s) => console.error(`${sq.slug}: ${s}`);
  try {
    clearWork(factory);
    let inputs;
    try {
      const geometry = JSON.parse(await readFile(join(folder, "input-geometry.json")));
      const png = new Uint8Array(await readFile(join(folder, "input.png")));
      const raw = await readFile(join(folder, "input-banks.f32"));
      inputs = { geometry, png, banks: new Float32Array(raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength)) };
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
      inputs = await captureInputs(sq, { status, about: { cli: "region-to-skylines" } });
      await writeFile(join(folder, "input-geometry.json"), JSON.stringify(inputs.geometry));
      await writeFile(join(folder, "input.png"), inputs.png);
      await writeFile(join(folder, "input-banks.f32"), new Uint8Array(inputs.banks.buffer));
    }
    const cover = await landCover(factory, sq, { fromUrl, tileUrl: (t) => WORLDCOVER_S3 + worldCoverFile(t), status });
    const evidence = await deposits(factory, sq, { status });
    const built = await buildMap(factory, { ...inputs, landcover: cover.path, evidence: evidence?.path ?? null }, { status });
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
    await copy("/work", join(folder, "work"));
    await writeFile(join(folder, "capture.json"), JSON.stringify({
      schema: 1, panel_sha256: frozen.panel_sha256, model_sha256: frozen.model_sha256,
      source_commit: source, source_files_sha256: sourceFiles, sq,
      package_sha256: sha(built.bytes), files_sha256: files,
      landcover_tiles: cover.tiles, evidence_available: evidence !== null,
      runtime_assessment: built.waterRisk,
    }, null, 2) + "\n");
    console.log(`${sq.slug}: prepared ${sha(built.bytes)}`);
  } catch (error) {
    failed++;
    await writeFile(join(folder, "failure.json"), JSON.stringify({ square: sq.slug, error: String(error), retained_in_panel: true }, null, 2) + "\n");
    console.error(`${sq.slug}: failed, retained in panel: ${error}`);
  }
}
console.log(JSON.stringify({ squares: panel.squares.length, failed, game_launched: false }));
process.exit(failed ? 1 : 0);

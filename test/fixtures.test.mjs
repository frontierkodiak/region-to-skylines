// Acceptance: the shipping MRDS path and the richer offline resource reference both
// reproduce their maps from inputs.js captures. Slow (about 40 s a build on an idle
// machine, plus the first Pyodide download): run with `npm run test:fixtures`.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { gunzipSync } from "node:zlib";
import { createHash } from "node:crypto";
import { loadPyodide } from "pyodide";
import { startFactory, buildMap, clearWork } from "../mapgen.js";

const root = new URL("../tools/map-factory/", import.meta.url);
const read = async (f) => new Uint8Array(await readFile(new URL(f, root)));
const manifest = JSON.parse(new TextDecoder().decode(await read("fixtures/manifest.json")));
assert.equal(manifest.capture_module, "inputs.js", "shipping fixtures must use the shared page/CLI capture");
for (const name of ["inputs.js", "terrain.js"])
  assert.equal(createHash("sha256").update(await readFile(new URL("../" + name, import.meta.url))).digest("hex"),
    manifest.capture_sources_sha256[name], `${name} changed; recapture and qualify`);
const nativeCases = Object.fromEntries(JSON.parse(new TextDecoder().decode(await read("fixtures/native-qualification.json"))).cases.map((c) => [c.slug, c]));
const only = process.env.FIXTURES ? process.env.FIXTURES.split(",") : null;
const sha = (b) => createHash("sha256").update(b).digest("hex");
const captureModuleSha = sha(await readFile(new URL("../inputs.js", import.meta.url)));
const shippingSources = Object.fromEntries(await Promise.all(["mapgen.js", "tools/map-factory/web.py"].map(async (f) =>
  [f, sha(await readFile(new URL("../" + f, import.meta.url)))])));

const factory = await startFactory({ loadPyodide, read });
for (const c of manifest.cases.filter((c) => !only || only.includes(c.slug))) {
  for (const [kind, expected, evidence] of [
    ["reference", c, c.files_sha256["evidence.json"] ? "evidence.json" : null],
    ["shipping", c.shipping, c.shipping?.evidence_file],
  ]) test(`${c.slug} ${kind}: exact .crp`, { timeout: 15 * 60 * 1000 }, async () => {
    const dir = `fixtures/${c.slug}/`, has = (f) => c.files_sha256[f] !== undefined;
    assert.ok(expected, `${c.slug}: ${kind} golden is required`);
    assert.ok(c.input_capture, `${c.slug}: inputs.js capture receipt is required`);
    const native = nativeCases[c.slug];
    assert.ok(native, `${c.slug}: native qualification is required`);
    assert.equal(c.input_capture.cli_sha256, native.native_crp_sha256, `${c.slug}: captured map differs from native run`);
    assert.deepEqual(c.input_capture.prepared_sha256, native.prepared_sha256, `${c.slug}: native grids changed`);
    assert.equal(sha(await read("templates/native-corridors.crp")), native.template_sha256, `${c.slug}: native template changed`);
    assert.equal(sha(await read("templates/native-corridors.json")), native.layout_sha256, `${c.slug}: native layout changed`);
    assert.equal(captureModuleSha, c.input_capture.source_files_sha256["inputs.js"], `${c.slug}: inputs.js changed; recapture and qualify`);
    if (kind === "shipping") for (const [name, digest] of Object.entries(shippingSources))
      assert.equal(digest, expected.source_files_sha256[name], `${c.slug}: shipping ${name} changed; recapture`);
    clearWork(factory);
    factory.py.FS.mkdirTree("/work");
    factory.py.FS.writeFile("/work/landcover.u8.gz", await read(dir + "landcover.u8.gz"));
    if (evidence) {
      assert.ok(has(evidence));
      const bytes = await read(dir + evidence);
      assert.equal(sha(bytes), c.files_sha256[evidence]);
      factory.py.FS.writeFile("/work/evidence.json", bytes);
    }
    const banks = gunzipSync(await read(dir + "banks.f32.gz"));
    const png = await read(dir + "input.png");
    const geometry = new Uint8Array(gunzipSync(await read(dir + (kind === "shipping" ? expected.geometry_file : "geometry.json.gz"))));
    const inputHashes = kind === "shipping" ? expected.input_files_sha256 : c.input_capture.files_sha256;
    for (const [name, bytes] of Object.entries({ "input.png": png, "geometry.json": geometry, "banks.f32": banks }))
      assert.equal(sha(bytes), inputHashes[name], `${c.slug} ${kind}: frozen inputs.js ${name}`);
    assert.deepEqual(c.prepared_sha256, c.input_capture.prepared_sha256, `${c.slug}: native-tested live-pin grids`);
    const t = performance.now();
    const { bytes, mapName } = await buildMap(factory, {
      png,
      geometry,
      banks: new Float32Array(banks.buffer, banks.byteOffset, banks.byteLength / 4),
      landcover: "/work/landcover.u8.gz",
      evidence: evidence ? "/work/evidence.json" : null,
    });
    console.log(`  ${c.slug} ${kind}: ${mapName}, ${bytes.length} bytes, ${((performance.now() - t) / 1000).toFixed(1)} s`);
    assert.equal(bytes.length, expected.expected_crp_bytes);
    assert.equal(sha(bytes), expected.expected_crp_sha256);
    for (const name of ["terrain.u16", "water.u16"])
      assert.equal(sha(factory.py.FS.readFile("/work/out/" + name)), c.input_capture.prepared_sha256[name], `${c.slug} ${kind}: native-tested ${name}`);
    const controls = JSON.parse(factory.py.runPython(`
import hashlib, json
from pathlib import Path
hydro = json.loads(Path('/work/out/hydrology.json').read_text())
json.dumps({
    'water_sources_sha256': hashlib.sha256(json.dumps(hydro['sources'], sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
    'node_positions_sha256': hashlib.sha256(json.dumps(hydro['node_positions'], sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
    'start_tile': hydro['start_tile'],
    'sea_level_m': hydro['sea_level_m'],
})
`));
    for (const name of ["water_sources_sha256", "node_positions_sha256", "start_tile", "sea_level_m"])
      assert.deepEqual(controls[name], native[name], `${c.slug} ${kind}: native-tested ${name}`);
  });
}

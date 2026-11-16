// Byte conformance, not full native acceptance: shipping MRDS and the richer
// offline resource reference both
// reproduce their maps from inputs.js captures. Slow (about 40 s a build on an idle
// machine, plus the first Pyodide download): run with `npm run test:fixtures`.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { gunzipSync } from "node:zlib";
import { createHash } from "node:crypto";
import { loadPyodide } from "pyodide";
import { startFactory, buildMap, clearWork } from "../mapgen.js";
import { loadFixtureContract } from "./fixture-contract.mjs";

const root = new URL("../tools/map-factory/", import.meta.url);
const read = async (f) => new Uint8Array(await readFile(new URL(f, root)));
const { manifest, nativeCases, historicalNativeCases } = await loadFixtureContract(read, async (f) => new Uint8Array(await readFile(new URL("../" + f, import.meta.url))));
assert.equal(manifest.capture_module, "inputs.js", "shipping fixtures must use the shared page/CLI capture");
for (const name of ["inputs.js", "terrain.js"])
  assert.equal(createHash("sha256").update(await readFile(new URL("../" + name, import.meta.url))).digest("hex"),
    manifest.capture_sources_sha256[name], `${name} changed; recapture and qualify`);
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
    for (const [name, digest] of Object.entries(c.files_sha256))
      assert.equal(sha(await read("fixtures/" + (c.fixture_files[name] ?? `${c.slug}/${name}`))), digest, `${c.slug}: fixture ${name}`);
    assert.ok(expected, `${c.slug}: ${kind} golden is required`);
    assert.ok(c.input_capture, `${c.slug}: inputs.js capture receipt is required`);
    const native = nativeCases[c.slug];
    assert.ok(native, `${c.slug}: fresh native evaluation is required`);
    assert.equal(c.input_capture.cli_sha256, historicalNativeCases[c.slug].native_crp_sha256, `${c.slug}: historical capture differs from historical native run`);
    assert.deepEqual(c.input_capture.prepared_sha256, historicalNativeCases[c.slug].prepared_sha256, `${c.slug}: historical native grids changed`);
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
    assert.deepEqual(c.prepared_sha256, native.prepared_sha256, `${c.slug}: native-tested live-pin grids`);
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
      assert.equal(sha(factory.py.FS.readFile("/work/out/" + name)), native.prepared_sha256[name], `${c.slug} ${kind}: native-tested ${name}`);
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
    const presentation = kind === "reference" ? c.presentation_delta : expected.presentation_delta;
    if (presentation) {
      // The delta's claim, executed: same resource grids and tree positions,
      // only the map environment and tree species moved.
      factory.py.FS.writeFile("/work/base-plan.npz", await read("fixtures/" + presentation.base_plan));
      factory.py.FS.writeFile("/work/native-water.bin", gunzipSync(await read("fixtures/" + presentation.water_simulation_file)));
      const delta = JSON.parse(factory.py.runPython(`
import hashlib, json, numpy as np
from pathlib import Path
from crp import read_package, patch_payload_environment
from template import manager_tag
old = np.load('/work/base-plan.npz')
new = np.load('/work/out/plan.npz')
hydro = json.loads(Path('/work/out/hydrology.json').read_text())
data = next(a['payload'] for a in read_package(Path('/work/out/' + hydro['map_id'] + '.crp').read_bytes())[1] if a['kind'] == 52)
water = data[data.index(manager_tag('WaterSimulation')):data.index(manager_tag('NetManager'))]
normalized = patch_payload_environment(data, ${JSON.stringify(presentation.previous_environment)})
json.dumps({
    'grids_equal': bool(all(np.array_equal(old[k], new[k]) for k in ('ore', 'oil', 'fertility', 'forest', 'tree'))),
    'positions_equal': bool(np.array_equal(old['px'], new['px']) and np.array_equal(old['pz'], new['pz'])),
    'species_equal': bool(np.array_equal(old['kinds'], new['kinds'])),
    'water_simulation_exact': water == Path('/work/native-water.bin').read_bytes(),
    'water_simulation_sha256': hashlib.sha256(water).hexdigest(),
    'normalized_non_tree_sha256': hashlib.sha256(normalized[:normalized.index(manager_tag('TreeManager'))]).hexdigest(),
})
`));
      assert.ok(delta.grids_equal, `${c.slug}: resources changed in a presentation-only delta`);
      assert.ok(delta.positions_equal, `${c.slug}: tree positions changed in a presentation-only delta`);
      assert.equal(delta.species_equal, !presentation.tree_species_changed, `${c.slug}: tree species flag`);
      assert.ok(delta.water_simulation_exact, `${c.slug}: native water segment changed`);
      assert.equal(delta.water_simulation_sha256, presentation.water_simulation_sha256);
      assert.equal(delta.normalized_non_tree_sha256, presentation.normalized_non_tree_sha256, `${c.slug}: changes outside environment and trees`);
    }
    if (kind === "shipping" && expected.source_order_variant_file) {
      clearWork(factory);
      factory.py.FS.mkdirTree("/work");
      factory.py.FS.writeFile("/work/landcover.u8.gz", await read(dir + "landcover.u8.gz"));
      if (evidence) factory.py.FS.writeFile("/work/evidence.json", await read(dir + evidence));
      const variant = await buildMap(factory, {
        png, banks: new Float32Array(banks.buffer, banks.byteOffset, banks.byteLength / 4),
        geometry: new Uint8Array(gunzipSync(await read("fixtures/" + expected.source_order_variant_file))),
        landcover: "/work/landcover.u8.gz", evidence: evidence ? "/work/evidence.json" : null,
      });
      assert.equal(variant.receipt.native_admission.applied, true, "live source-pin order must not discard the admission");
      assert.equal(sha(variant.bytes), expected.expected_crp_sha256, "source-pin order changed the full package");
      console.log(`  ${c.slug} live source-pin permutation: exact complete shipping package`);
    }
  });
}

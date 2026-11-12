// Acceptance: the site's writer path (mapgen.js on Pyodide) gives PL-857's five fixture map
// files byte for byte, from the fixtures' own inputs. Slow (about 40 s a region on an idle
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
const only = process.env.FIXTURES ? process.env.FIXTURES.split(",") : null;
const sha = (b) => createHash("sha256").update(b).digest("hex");

const factory = await startFactory({ loadPyodide, read });
for (const c of manifest.cases.filter((c) => !only || only.includes(c.slug))) {
  test(`${c.slug}: same .crp as the reference (${c.expected_crp_sha256.slice(0, 12)})`, { timeout: 15 * 60 * 1000 }, async () => {
    const dir = `fixtures/${c.slug}/`, has = (f) => c.files_sha256[f] !== undefined;
    clearWork(factory);
    factory.py.FS.mkdirTree("/work");
    factory.py.FS.writeFile("/work/landcover.u8.gz", await read(dir + "landcover.u8.gz"));
    if (has("evidence.json")) factory.py.FS.writeFile("/work/evidence.json", await read(dir + "evidence.json"));
    const banks = gunzipSync(await read(dir + "banks.f32.gz"));
    const t = performance.now();
    const { bytes, mapName } = await buildMap(factory, {
      png: await read(dir + "input.png"),
      geometry: new Uint8Array(gunzipSync(await read(dir + "geometry.json.gz"))),
      banks: new Float32Array(banks.buffer, banks.byteOffset, banks.byteLength / 4),
      landcover: "/work/landcover.u8.gz",
      evidence: has("evidence.json") ? "/work/evidence.json" : null,
    });
    console.log(`  ${c.slug}: ${mapName}, ${bytes.length} bytes, ${((performance.now() - t) / 1000).toFixed(1)} s`);
    assert.equal(bytes.length, c.expected_crp_bytes);
    assert.equal(sha(bytes), c.expected_crp_sha256);
  });
}

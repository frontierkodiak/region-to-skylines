// CPU parity only. This does not read, replace or grant native qualification.
// node tools/map-factory/verify-candidate.mjs OUTPUT_OF_minor_stream_candidate.py
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { createHash } from "node:crypto";
import { loadPyodide } from "pyodide";
import { startFactory, buildMap, clearWork } from "../../mapgen.js";

const output = resolve(process.argv[2]);
const root = new URL("./", import.meta.url);
const read = async (path) => new Uint8Array(await readFile(new URL(path, root)));
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const manifest = JSON.parse(await readFile(`${output}/fixtures/manifest.json`, "utf8"));
assert.equal(sha(await read("region.py")), manifest.writer_sha256, "candidate writer changed");
const factory = await startFactory({ loadPyodide, read });
for (const c of manifest.cases) {
  clearWork(factory);
  factory.py.FS.mkdirTree("/work");
  factory.py.FS.writeFile("/work/landcover.u8.gz", await read(`fixtures/${c.slug}/landcover.u8.gz`));
  const dir = `${output}/inputs/${c.slug}`;
  let evidence = null;
  // The candidate generator uses exactly the shipping evidence, not the richer offline one.
  try {
    const bytes = await read(`fixtures/${c.slug}/shipping-evidence.json`);
    factory.py.FS.writeFile("/work/evidence.json", bytes);
    evidence = "/work/evidence.json";
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  const banks = await readFile(`${dir}/banks.f32`);
  const { bytes } = await buildMap(factory, {
    png: await read(`fixtures/${c.slug}/input.png`),
    geometry: new Uint8Array(await readFile(`${dir}/source-geometry.json`)),
    banks: new Float32Array(banks.buffer, banks.byteOffset, banks.byteLength / 4),
    landcover: "/work/landcover.u8.gz", evidence,
  });
  assert.equal(bytes.length, c.crp_bytes, c.slug);
  assert.equal(sha(bytes), c.crp_sha256, `${c.slug}: full CRP`);
  for (const name of ["terrain.u16", "water.u16"])
    assert.equal(sha(factory.py.FS.readFile(`/work/out/${name}`)), c.grids[name].after_sha256, `${c.slug}: ${name}`);
  console.log(`${c.slug}: Python / JavaScript-Pyodide full CRP and grids byte-identical`);
}

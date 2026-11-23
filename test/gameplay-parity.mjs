// Replay the fixed eight inputs through the real browser/CLI Python runtime.
import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { loadPyodide } from "pyodide";
import { startFactory, buildMap, clearWork } from "../mapgen.js";

const root = process.argv[2];
if (!root) throw new Error("Usage: node test/gameplay-parity.mjs RUN_ROOT");
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const factory = await startFactory({ loadPyodide,
  read: path => readFile(new URL("../tools/map-factory/" + path, import.meta.url)) });
const cases = ["asheville", "innsbruck", "rio", "pittsburgh", "charleston", "grand-canyon", "hong-kong", "yosemite"];
const proof = [];
for (const slug of cases) {
  clearWork(factory);
  const input = root + "/inputs/" + slug + "/";
  factory.py.FS.mkdirTree("/work");
  for (const name of ["landcover.u8.gz", "evidence.json"])
    factory.py.FS.writeFile("/work/" + name, await readFile(input + name));
  const banks = await readFile(input + "banks.f32");
  const result = await buildMap(factory, {
    png: await readFile(input + "input.png"),
    geometry: new Uint8Array(await readFile(input + "geometry.json")),
    banks: new Float32Array(banks.buffer, banks.byteOffset, banks.byteLength / 4),
    landcover: "/work/landcover.u8.gz", evidence: "/work/evidence.json",
  });
  const expected = JSON.parse(await readFile(root + "/after-v3/" + slug + "/generation.json"));
  assert.equal(sha(result.bytes), expected.package.sha256, slug + ": CPython/Pyodide package equality");
  proof.push({ square: slug, sha256: sha(result.bytes), bytes: result.bytes.length });
  await writeFile(root + "/pyodide-parity.json", JSON.stringify(proof, null, 2) + "\n");
  console.log(slug + " package exact", result.bytes.length);
}

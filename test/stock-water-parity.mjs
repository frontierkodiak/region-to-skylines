// The actual browser/CLI runtime must reproduce the packages tested in-game.
import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { loadPyodide } from "pyodide";
import { startFactory, buildMap, clearWork } from "../mapgen.js";

const [inputs, prepared, output, ...squares] = process.argv.slice(2);
if (!output || !squares.length) throw new Error("Usage: node test/stock-water-parity.mjs INPUTS PREPARED OUTPUT SQUARE...");
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const factory = await startFactory({ loadPyodide,
  read: name => readFile(new URL("../tools/map-factory/" + name, import.meta.url)) });
const proof = [];
for (const square of squares) {
  clearWork(factory);
  factory.py.FS.mkdirTree("/work");
  for (const file of ["landcover.u8.gz", "evidence.json"])
    factory.py.FS.writeFile("/work/" + file, await readFile(`${inputs}/${square}/${file}`));
  const banks = await readFile(`${inputs}/${square}/banks.f32`);
  const result = await buildMap(factory, {
    png: await readFile(`${inputs}/${square}/input.png`),
    geometry: new Uint8Array(await readFile(`${inputs}/${square}/geometry.json`)),
    banks: new Float32Array(banks.buffer, banks.byteOffset, banks.byteLength / 4),
    landcover: "/work/landcover.u8.gz", evidence: "/work/evidence.json",
  });
  const expected = JSON.parse(await readFile(`${prepared}/${square}/generation.json`));
  const actual = sha(result.bytes);
  proof.push({ square, expected: expected.package.sha256, actual, bytes: result.bytes.length });
  await writeFile(output, JSON.stringify(proof, null, 2) + "\n");
  assert.equal(actual, expected.package.sha256, square + ": native Python/Pyodide package equality");
  console.log(square + ": exact package bytes", result.bytes.length);
}

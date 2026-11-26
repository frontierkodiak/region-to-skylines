import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { loadFixtureContract } from "./fixture-contract.mjs";

const PREFIX = "fixtures/contracts/pl1072-sea-neighbours-v1/";
const read = name => readFile(new URL("../tools/map-factory/" + name, import.meta.url));
const source = name => readFile(new URL("../" + name, import.meta.url));
const encode = value => Buffer.from(JSON.stringify(value, null, 2) + "\n");
const sha = bytes => createHash("sha256").update(bytes).digest("hex");

test("sea-neighbour refresh retains the main capture chain and prepared calibration", async () => {
  const result = await loadFixtureContract(read, source);
  const screen = result.historicalScreen ?? result.current;
  assert.equal(screen.version, "pl1072-sea-neighbours-v1");
  assert.equal(result.manifest.cases.length, 5);
  assert.deepEqual(Object.keys(result.historicalCaptureSources), ["inputs.js"]);
  const prepared = JSON.parse(await read(PREFIX + "prepared-screen.json"));
  assert.deepEqual(screen.risk_cases, prepared.risk_cases);
  assert.deepEqual(screen.calibration, prepared.calibration);
});

test("refresh archives, current source and native-case identity fail closed", async () => {
  for (const name of ["prepared-screen.json", "historical-water_risk.py", "previous-active.json"])
    await assert.rejects(loadFixtureContract(async path => {
      const raw = await read(path);
      return path === PREFIX + name ? Buffer.concat([raw, Buffer.from(" ")]) : raw;
    }, source), /screen refresh archive changed/);
  await assert.rejects(loadFixtureContract(read, async path =>
    path === "tools/map-factory/water_risk.py" ? Buffer.from("changed source") : source(path)),
  /current contract source changed/);
  const current = JSON.parse(await read(PREFIX + "current.json"));
  current.cases[0].status = "invented acceptance";
  await assert.rejects(loadFixtureContract(path => path === PREFIX + "current.json" ?
    Promise.resolve(encode(current)) : read(path), source), /Air predecessor contract changed/);
});

test("coherent hash rewrites cannot relabel the old corpus or change unrelated features", async () => {
  for (const mutate of [
    row => { row.labels.flood = !row.labels.flood; },
    row => { row.features[Object.keys(row.features).find(key => key !== "narrow_film_km2")] += 1; },
  ]) {
    const current = JSON.parse(await read(PREFIX + "current.json"));
    const prepared = JSON.parse(await read(PREFIX + "prepared-screen.json"));
    const corpus = JSON.parse(await read(PREFIX + "corpus.json"));
    mutate(corpus[0]);
    const corpusBytes = encode(corpus);
    current.corpus_sha256 = prepared.corpus_sha256 = sha(corpusBytes);
    const preparedBytes = encode(prepared);
    current.screen_refresh.prepared.sha256 = sha(preparedBytes);
    const overrides = new Map([
      [PREFIX + "current.json", encode(current)],
      [PREFIX + "prepared-screen.json", preparedBytes],
      [PREFIX + "corpus.json", corpusBytes],
    ]);
    await assert.rejects(loadFixtureContract(path => overrides.has(path) ?
    Promise.resolve(overrides.get(path)) : read(path), source), /Air predecessor contract changed/);
  }
});

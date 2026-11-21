import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { loadRunwayContract } from "./runway-fixture-contract.mjs";
import { loadWaterRiskContract } from "./water-risk-fixture-contract.mjs";

const PREFIX = "contracts/pl1072-sea-neighbours-v1/";
const VERSION = "pl1072-sea-neighbours-v1";
const SCOPE = "Sea-neighbour measurement correction after optional capture adoption; no new fixture native qualification or physical package";
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const parse = bytes => JSON.parse(new TextDecoder().decode(bytes));

export async function loadSeaNeighbourContract({ read, readSource, current, historical, historicalNativeCases, factoryFiles }) {
  const refresh = current.screen_refresh;
  assert.deepEqual(Object.keys(refresh).sort(), ["historical_measurement", "predecessor", "prepared", "prepared_source_head", "previous_active"]);
  assert.equal(refresh.prepared_source_head, "cc9d541604ef05ddf49d08f73d7819f5cf931075");
  const bound = async (key, name) => {
    const item = refresh[key];
    assert.equal(item.file, name);
    const raw = await read("fixtures/" + name);
    assert.equal(sha(raw), item.sha256, `${key}: screen refresh archive changed`);
    return raw;
  };
  const predecessor = parse(await bound("predecessor", "contracts/pl1066-optional-runways-v1/current.json"));
  const prepared = parse(await bound("prepared", PREFIX + "prepared-screen.json"));
  const oldMeasurement = await bound("historical_measurement", PREFIX + "historical-water_risk.py");
  assert.equal(sha(oldMeasurement), predecessor.source_files_sha256["tools/map-factory/water_risk.py"]);
  assert.deepEqual(parse(await bound("previous_active", PREFIX + "previous-active.json")), {
    format: 2, current: refresh.predecessor.file, historical_current: "current.json",
  });

  // Verify the unchanged prior capture chain against its actual old measurement bytes.
  const prior = await loadRunwayContract({ read,
    readSource: name => name === "tools/map-factory/water_risk.py" ? oldMeasurement : readSource(name),
    current: predecessor, historical, historicalNativeCases, factoryFiles });
  const inputs = await read("fixtures/" + prior.historicalCaptureSources["inputs.js"].file);
  const screen = { ...prepared, corpus_file: PREFIX + "corpus.json" };
  assert.deepEqual(current, { ...screen, version: VERSION, scope: SCOPE,
    source_files_sha256: { ...prepared.source_files_sha256, "inputs.js": sha(await readSource("inputs.js")) },
    screen_refresh: refresh,
  }, "current contract source changed or screen evidence relabelled");
  for (const [name, digest] of Object.entries(current.source_files_sha256))
    if (name !== "tools/map-factory/water_risk.py")
      assert.equal(digest, predecessor.source_files_sha256[name], `${name}: unrelated source change`);
  assert.deepEqual(current.calibration, predecessor.calibration, "deployed model calibration changed");
  assert.deepEqual(current.cases, predecessor.cases, "native cases relabelled");

  const correctedBytes = await read("fixtures/" + screen.corpus_file);
  assert.equal(sha(correctedBytes), screen.corpus_sha256, "corrected corpus changed");
  const corrected = parse(correctedBytes);
  const original = parse(await read("fixtures/" + predecessor.corpus_file));
  const stable = row => ({ ...row, features: { ...row.features, narrow_film_km2: null } });
  assert.deepEqual(corrected.map(stable), original.map(stable), "refresh changed labels, bindings or unrelated features");
  const base = await loadWaterRiskContract({ read,
    readSource: name => name === "inputs.js" ? inputs : readSource(name),
    current: screen, historical, historicalNativeCases, factoryFiles });
  return { ...base, current, historicalCaptureSources: prior.historicalCaptureSources };
}

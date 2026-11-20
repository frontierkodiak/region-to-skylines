// This metadata-only layer preserves every predecessor receipt and CRP identity.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { loadTransientContract } from "./transient-fixture-contract.mjs";
const sha = (b) => createHash("sha256").update(b).digest("hex");
const parse = (b) => JSON.parse(new TextDecoder().decode(b));

export async function loadWaterRiskContract({ read, readSource, current, historical, historicalNativeCases, factoryFiles }) {
  assert.deepEqual(Object.keys(current).sort(), ["format", "version", "status", "scope", "predecessor", "previous_contracts", "native_tested_head", "cases", "source_files_sha256", "export_gate_files_sha256", "archived_sources", "historical_tool_sources", "corpus_file", "corpus_sha256", "coverage_file", "coverage_sha256", "calibration", "risk_cases"].sort());
  assert.equal(current.format, 1);
  assert.equal(current.version, "pl912-water-risk-v1");
  assert.equal(current.status, "partial_not_accepted");
  assert.equal(current.scope, "Input-only screening metadata; no new native qualification or physical package");
  const previousBytes = await read("fixtures/" + current.predecessor.file);
  assert.equal(sha(previousBytes), current.predecessor.sha256, "predecessor contract changed");
  const previous = parse(previousBytes);
  assert.deepEqual(current.cases, previous.cases, "risk screening cannot relabel native cases");
  assert.deepEqual(current.previous_contracts, previous.previous_contracts);
  assert.equal(current.native_tested_head, previous.native_tested_head);
  assert.deepEqual(Object.keys(current.source_files_sha256).sort(), ["inputs.js", "terrain.js", "mapgen.js", ...factoryFiles.map((f) => "tools/map-factory/" + f)].sort());
  for (const [name, digest] of Object.entries(current.source_files_sha256))
    assert.equal(sha(await readSource(name)), digest, `${name}: current contract source changed`);
  for (const [name, digest] of Object.entries(current.export_gate_files_sha256))
    assert.equal(sha(await readSource(name)), digest, `${name}: export gate source changed`);
  const metadataFiles = ["mapgen.js", "tools/map-factory/web.py"];
  assert.deepEqual(Object.keys(current.archived_sources).sort(), metadataFiles.sort());
  const snapshots = {};
  for (const [name, digest] of Object.entries(previous.source_files_sha256)) {
    if (metadataFiles.includes(name)) {
      const bytes = await read("fixtures/" + current.archived_sources[name]);
      assert.equal(sha(bytes), digest, `${name}: archived source changed`);
      snapshots[name] = bytes;
    } else assert.equal(sha(await readSource(name)), digest, `${name}: physical writer changed`);
  }
  // PR49 already changed this nonshipping trace driver after the old native
  // runs. Preserve both identities rather than claiming current-driver native
  // qualification or silently dropping the historical material check.
  assert.deepEqual(Object.keys(current.historical_tool_sources), ["tools/map-factory/native_opening_diagnostic.py"]);
  for (const [name, proof] of Object.entries(current.historical_tool_sources)) {
    assert.equal(sha(await readSource(name)), proof.current_sha256, `${name}: harness tool changed`);
    const bytes = await read("fixtures/" + proof.snapshot);
    assert.equal(sha(bytes), proof.native_tested_sha256, `${name}: historical tool snapshot changed`);
    snapshots[name] = bytes;
  }
  const corpusBytes = await read("fixtures/" + current.corpus_file);
  assert.equal(sha(corpusBytes), current.corpus_sha256, "water-risk corpus changed");
  assert.equal(sha(await read("fixtures/" + current.coverage_file)), current.coverage_sha256, "water-risk coverage changed");
  const model = parse(await readSource("tools/map-factory/water-risk-model.json"));
  assert.deepEqual(model.calibration, current.calibration);
  const originalFactory = Object.keys(previous.source_files_sha256).filter((n) => n.startsWith("tools/map-factory/")).map((n) => n.slice("tools/map-factory/".length));
  const base = await loadTransientContract({ read, readSource: (name) => snapshots[name] ?? readSource(name), current: previous, historical, historicalNativeCases, factoryFiles: originalFactory });
  for (const c of base.manifest.cases) c.shipping.source_files_sha256 = { ...current.source_files_sha256 };
  return { ...base, current };
}

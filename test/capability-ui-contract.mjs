// Explicit UI-only source evolution. The predecessor keeps its original bytes,
// physical writers and native receipts; it is checked against archived UI bytes.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
const sha = (b) => createHash("sha256").update(b).digest("hex");
const parse = (b) => JSON.parse(new TextDecoder().decode(b));
const GATES = ["app.js", "build.mjs", "index.html", "package.json", "style.css"];

export async function capabilityUISources({ read, readSource, activeBytes, currentBytes, current }) {
  const adoption = parse(await read("fixtures/contracts/pl1119-capability-ui-v1/adoption.json"));
  assert.equal(adoption.schema, 1);
  assert.equal(adoption.scope, "Capability UI and standalone checks only; no new native qualification or physical writer");
  assert.equal(adoption.predecessor_active_sha256, sha(activeBytes), "capability predecessor active pointer changed");
  assert.equal(adoption.predecessor_contract_sha256, sha(currentBytes), "capability predecessor contract changed");
  assert.deepEqual(Object.keys(adoption.archived_gates).sort(), GATES.sort());
  const archived = {};
  for (const name of GATES) {
    const binding = adoption.archived_gates[name];
    assert.equal(binding.file, "contracts/pl1119-capability-ui-v1/baseline/" + name);
    const raw = await read("fixtures/" + binding.file);
    assert.equal(sha(raw), current.export_gate_files_sha256[name], `${name}: archived gate changed`);
    assert.equal(sha(await readSource(name)), binding.current_sha256, `${name}: capability UI source changed`);
    archived[name] = raw;
  }
  assert.deepEqual(Object.keys(adoption.added_files_sha256).sort(), ["capabilities.json", "capability-evidence.js", "capability-evidence-worker.js", "capability-inputs.js", "capability-ledger.mjs", "capability-model.js", "capability-ui.js", "tools/map-factory/capabilities.py", "tools/map-factory/integrate_outside_evidence.py", "tools/map-factory/capability-evidence/pl1119-v3-predictions.json"].sort());
  for (const [name, digest] of Object.entries(adoption.added_files_sha256)) assert.equal(sha(await readSource(name)), digest, `${name}: capability source changed`);
  return (name) => archived[name] ?? readSource(name);
}

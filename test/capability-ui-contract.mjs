// Nonphysical capability-source evolution. The predecessor retains its original
// writer/native bytes; exact-context path certificates do not qualify that baseline.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
const sha = (b) => createHash("sha256").update(b).digest("hex");
const parse = (b) => JSON.parse(new TextDecoder().decode(b));
const GATES = ["app.js", "build.mjs", "index.html", "package.json", "style.css"];

export async function capabilityUISources({ read, readSource, activeBytes, currentBytes, current }) {
  const adoption = parse(await read("fixtures/contracts/pl1119-capability-ui-v1/adoption.json"));
  assert.equal(adoption.schema, 1);
  assert.equal(adoption.scope, "Capability checks and four retained exact-context path certificates; physical writers and historical native qualification unchanged");
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
  assert.deepEqual(Object.keys(adoption.added_files_sha256).sort(), ["capabilities.json", "capability-evidence.js", "capability-evidence-worker.js", "capability-inputs.js", "capability-ledger.mjs", "capability-model.js", "capability-ui.js", "tools/map-factory/capabilities.py", "tools/map-factory/integrate_outside_evidence.py", "tools/map-factory/integrate_outside_v2.py", "tools/map-factory/capability-evidence/runtime-identities/25eb5d7018f379e7dbb25fcd4a7e3ab72ef4155f3d54fca077257d6eefb7d8e0.json", "tools/map-factory/capability-evidence/runtime-identities/3499552b48486b2822a80e5ab101af8ad0e1cd70c4512f606c5299d7fe65eb00.json", "tools/map-factory/capability-evidence/runtime-identities/b844c6cd44dd32189294b52f03b40fd2e7eb4e8a0e6b51374d3ad29ea584e4c9.json", "tools/map-factory/capability-evidence/runtime-identities/b8cc86a4540f96db8628d742afc534caa69679f7c29dac5764ee3c46a14a628d.json", "tools/map-factory/capability-evidence/pl1119-v3-predictions.json"].sort());
  for (const [name, digest] of Object.entries(adoption.added_files_sha256)) assert.equal(sha(await readSource(name)), digest, `${name}: capability source changed`);
  return (name) => archived[name] ?? readSource(name);
}

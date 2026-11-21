import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { checkCapabilities } from "../capability-model.js";
import { validateLedger, ledgerPage } from "../capability-ledger.mjs";

const root = new URL("../", import.meta.url);
const ledger = JSON.parse(readFileSync(new URL("capabilities.json", root)));
const staged = ledger.evidence_studies["outside-targeted-v2"].qualification_candidates;

test("targeted v2 stages four bound receipts without activating or pooling v1", () => {
  validateLedger(ledger);
  assert.equal(staged.length, 4);
  assert.equal(ledger.native_path_certificates.length, 0);
  assert.equal(ledger.evidence_studies["outside-v1"].qualification_candidates.length, 9);
  for (const c of staged) {
    assert.deepEqual(c.blocked_by, ["independent_review_pending"]);
    assert.equal(c.capability, "ship");
    assert.equal(c.native_context.opening_runtime_identity.assemblies.length, 23);
    assert.equal(c.native_context.opening_error_count, 3);
    assert.match(c.limitations, /not in-memory code attestation/);
  }
  const html = ledgerPage(ledger);
  assert.match(html, /outside-targeted-v2/);
  assert.match(html, /outside-v1/);
  assert.match(html, /not pooled as independent votes/);
  assert.match(html, /4 awaiting independent review. Active certificates: 0/);
});

test("proposed activation changes only the review block; context mutations stay unqualified", () => {
  // Constructed geometry here; the Python export test separately reads real files.
  const proposal = structuredClone(ledger);
  proposal.native_path_certificates = staged.map((c) => {
    const object = structuredClone(c); delete object.blocked_by; return object;
  });
  validateLedger(proposal);
  for (const certificate of staged) {
    const input = { schema: 1, mode: "export", graph: { nodes: [{outside:"west"}, {outside:"east"}], edges: [{a:0,b:1,kind:"ship"}] },
      export_identity: {artifact_sha256: certificate.artifact_sha256, inputs_sha256: certificate.inputs_sha256, native_context: certificate.native_context} };
    assert.equal(checkCapabilities(input, ledger).capabilities.ship.level, "likely");
    assert.equal(checkCapabilities(input, proposal).capabilities.ship.level, "promised");
    const mutations = [
      (i) => {i.mode = "estimate";},
      (i) => {delete i.export_identity;},
      (i) => {i.export_identity.native_context.opening_plugins[0].enabled = true;},
      (i) => {i.export_identity.native_context.opening_runtime_identity.assemblies[1].sha256 = "0".repeat(64);},
      (i) => {i.export_identity.native_context.opening_runtime_identity.namespace_pid++;},
      (i) => {i.export_identity.native_context.opening_runtime_identity.process_start_ticks = "1";},
      (i) => {i.export_identity.native_context.opening_errors = [];},
      (i) => {i.export_identity.native_context.collector_sources["runtime_identity.py"] = "0".repeat(64);},
    ];
    for (const mutate of mutations) {
      const i = structuredClone(input); mutate(i);
      assert.notEqual(checkCapabilities(i, proposal).capabilities.ship.level, "promised");
    }
  }
});

test("ledger rejects arbitrary projection files and staged receipt/context/control tampering", () => {
  for (const mutate of [
    (l) => {l.evidence_studies["outside-targeted-v2"].projection_tool_file = "../../AGENTS.md";},
    (l) => {l.evidence_studies["outside-v1"].projection_tool_file = "tools/map-factory/integrate_outside_v2.py";},
    (l) => {l.evidence_studies["outside-targeted-v2"].qualification_candidates[0].controls.boundary_1 = false;},
    (l) => {l.evidence_studies["outside-targeted-v2"].qualification_candidates[0].native_context.opening_plugins[0].enabled = true;},
    (l) => {l.evidence_studies["outside-targeted-v2"].qualification_candidates[0].observed_at = "changed";},
    (l) => {l.evidence_studies["outside-targeted-v2"].qualification_candidates[0].observation_sha256 = "0".repeat(64);},
    (l) => {l.evidence_studies["outside-targeted-v2"].qualification_candidates[0].blocked_by = [];},
  ]) {
    const changed = structuredClone(ledger); mutate(changed);
    assert.throws(() => validateLedger(changed));
  }
  const file = new URL(staged[0].runtime_identity_evidence.file, root), bytes = readFileSync(file);
  try {
    writeFileSync(file, Buffer.concat([bytes, Buffer.from(" ")]));
    assert.throws(() => validateLedger(ledger), /receipt binding changed/);
  } finally {writeFileSync(file, bytes);}
});

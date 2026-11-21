// Current byte conformance is distinct from historical or full native acceptance.
import assert from "node:assert/strict";
import { loadWaterRiskContract } from "./water-risk-fixture-contract.mjs";
import { loadRunwayContract } from "./runway-fixture-contract.mjs";
import { capabilityUISources } from "./capability-ui-contract.mjs";
import { loadTransientContract } from "./transient-fixture-contract.mjs";
import { FACTORY_FILES } from "../mapgen.js";
import { createHash } from "node:crypto";
const sha = (b) => createHash("sha256").update(b).digest("hex");
const parse = (b) => JSON.parse(new TextDecoder().decode(b));

export async function loadFixtureContract(read, readSource) {
  const historicalBytes = await read("fixtures/manifest.json");
  const historicalNativeBytes = await read("fixtures/native-qualification.json");
  const historical = parse(historicalBytes);
  const historicalNativeCases = Object.fromEntries(parse(historicalNativeBytes).cases.map((c) => [c.slug, c]));
  const activeBytes = await read("fixtures/active.json"), active = parse(activeBytes);
  assert.equal(active.format, 2);
  assert.match(active.current, /^contracts\/[a-z0-9-]+\/current\.json$/);
  const currentBytes = await read("fixtures/" + active.current), current = parse(currentBytes);
  readSource = await capabilityUISources({ read, readSource, activeBytes, currentBytes, current });
  if (current.version === "pl1066-optional-runways-v1")
    return loadRunwayContract({ read, readSource, current, historical, historicalNativeCases, factoryFiles: FACTORY_FILES });
  if (current.version === "pl912-water-risk-v1")
    return loadWaterRiskContract({ read, readSource, current, historical, historicalNativeCases, factoryFiles: FACTORY_FILES });
  if (current.version === "pl912-transient-storage-v1")
    return loadTransientContract({ read, readSource, current, historical, historicalNativeCases, factoryFiles: FACTORY_FILES });
  assert.equal(current.previous_contracts.accepted_presentation.file, "current.json");
  assert.equal(current.previous_contracts.native_baseline.file, "contracts/pl912-native-dry-subreach-v1/current.json");
  for (const parent of Object.values(current.previous_contracts))
    assert.equal(sha(await read("fixtures/" + parent.file)), parent.sha256, "predecessor contract changed");
  assert.deepEqual(Object.keys(current.source_files_sha256).sort(), ["inputs.js", "terrain.js", "mapgen.js", ...FACTORY_FILES.map((f) => "tools/map-factory/" + f)].sort(), "every shipping runtime dependency must be bound");
  assert.equal(current.format, 1);
  assert.equal(current.status, "partial_not_accepted");
  assert.equal(sha(historicalBytes), current.historical_manifest_sha256, "historical fixture contract changed");
  assert.equal(sha(historicalNativeBytes), current.historical_native_qualification_sha256, "historical native evidence changed");
  assert.deepEqual(current.unverified, ["strict_disableMods_ordinary_menu", "macOS", "populated_long_term"]);
  const evaluationBytes = await read("fixtures/" + current.native_evaluation_file);
  assert.equal(sha(evaluationBytes), current.native_evaluation_sha256, "fresh native evaluation changed");
  const evaluation = parse(evaluationBytes);
  const presentationBytes = await read("fixtures/" + current.presentation_proof_file);
  assert.equal(sha(presentationBytes), current.presentation_proof_sha256, "presentation proof changed");
  const presentationProof = parse(presentationBytes);
  assert.equal(presentationProof.status, "complete");
  assert.equal(presentationProof.cases.length, 10);
  assert.equal(presentationProof.source_head, current.presentation_writer_commit);
  assert.deepEqual(presentationProof.source_files_sha256, current.source_files_sha256);
  assert.equal(evaluation.status, "partial_not_accepted");
  assert.equal(current.native_tested_head, evaluation.native_tested_head);
  const admission = parse(await readSource("tools/map-factory/native-water-admission.json"));
  const originalRegistryBytes = await read("fixtures/" + current.original_native_registry_file);
  assert.equal(sha(originalRegistryBytes), current.native_source_files_sha256["tools/map-factory/native-water-admission.json"]);
  const originalRegistry = parse(originalRegistryBytes);
  const migrationBytes = await read("fixtures/" + current.binding_migration_file);
  assert.equal(sha(migrationBytes), current.binding_migration_sha256);
  const migration = parse(migrationBytes);
  assert.equal(migration.records.length, 5);
  assert.equal(Object.keys(originalRegistry.records).length, 5);
  assert.equal(Object.keys(admission.records).length, 5);
  for (const row of migration.records) {
    const before = originalRegistry.records[row.old_fingerprint], after = admission.records[row.new_fingerprint];
    assert.deepEqual(after.edits, before.edits, "binding migration changed native edits");
    assert.deepEqual(after.target, before.target, "binding migration changed native target grids");
    const a = { ...after.bindings }, b = { ...before.bindings };
    delete a.geometry; delete b.geometry;
    assert.deepEqual(a, b, "binding migration changed physical forcing or baseline grids");
  }
  assert.match(current.native_engine_sha256, /^[a-f0-9]{64}$/);
  assert.equal(current.native_engine_sha256, evaluation.native_engine_sha256);
  assert.equal(current.native_engine_sha256, admission.native_engine_sha256);
  assert.deepEqual(current.native_source_files_sha256, evaluation.source_files_sha256);
  const presentationFiles = ["generate.py", "crp.py", "paint.py", "resources.py", "wet_reach_admission.py", "native-water-admission.json"].map((f) => "tools/map-factory/" + f);
  for (const [name, digest] of Object.entries(current.native_source_files_sha256))
    if (!presentationFiles.includes(name)) assert.equal(current.source_files_sha256[name], digest, `${name}: hydraulic dependency changed`);
  assert.equal(current.source_files_sha256["tools/map-factory/region.py"], evaluation.production_writer_sha256);
  for (const [name, digest] of Object.entries(current.source_files_sha256))
    assert.equal(sha(await readSource(name)), digest, `${name}: current contract source changed`);
  const slugs = historical.cases.map((c) => c.slug);
  assert.deepEqual(current.cases.map((c) => c.slug), slugs, "current contract must retain every region in order");
  assert.deepEqual(evaluation.cases.map((c) => c.slug), slugs);
  const cases = [], nativeCases = {};
  for (const old of historical.cases) {
    const c = current.cases.find((c) => c.slug === old.slug);
    const measured = evaluation.cases.find((c) => c.slug === old.slug);
    const native = c.native;
    for (const [name, digest] of Object.entries(old.files_sha256))
      assert.equal(sha(await read(`fixtures/${old.slug}/${name}`)), digest, `${old.slug}: historical fixture ${name} changed`);
    // Old capture identities remain historical evidence, never current qualification.
    assert.equal(old.input_capture.cli_sha256, historicalNativeCases[old.slug].native_crp_sha256);
    assert.deepEqual(old.input_capture.prepared_sha256, historicalNativeCases[old.slug].prepared_sha256);
    assert.equal(native.harness_commit, evaluation.native_tested_head);
    assert.equal(native.strict_vanilla_verified, false);
    assert.equal(native.game_minutes, measured.game_minutes);
    assert.ok(native.game_minutes >= 60 && measured.clean_source);
    assert.equal(measured.no_regression, true, "a passing-gate regression blocks promotion");
    assert.deepEqual(measured.passing_gate_regressions, []);
    assert.ok(Object.values(measured.new_required_point_losses).every((losses) => losses.length === 0));
    assert.equal(native.frozen_flood_reference_sha256, measured.frozen_flood_reference_sha256);
    assert.equal(native.verdict, measured.native_verdict);
    assert.deepEqual(native.failed_checks, measured.failed);
    assert.deepEqual(native.receipt_sha256, measured.receipt_sha256);
    assert.equal(native.native_crp_sha256, measured.binding.files_sha256[`PL857-${old.slug}.crp`]);
    const delta = c.reference.presentation_delta;
    if (delta) {
      // A presentation-only re-export: the package is new, the simulation data
      // is the native-tested package's, and only these parts may differ.
      assert.deepEqual(delta.changed, ["environment", "trees"], `${old.slug}: presentation delta scope`);
      assert.match(delta.base_crp_sha256, /^[0-9a-f]{64}$/, `${old.slug}: delta must name the package it re-exports`);
      assert.ok(delta.base_plan && typeof delta.environment_changed === "boolean" && typeof delta.tree_species_changed === "boolean", `${old.slug}: delta needs its base plan and change flags`);
      if (delta.environment_changed || delta.tree_species_changed) {
        assert.notEqual(c.shipping.expected_crp_sha256, native.native_crp_sha256, `${old.slug}: a real change must change the package`);
      } else {
        assert.equal(c.shipping.expected_crp_sha256, native.native_crp_sha256, `${old.slug}: an unchanged export must keep the native-tested bytes`);
      }
      assert.equal(c.shipping.presentation_delta.base_crp_sha256, native.native_crp_sha256);
      assert.equal(c.shipping.presentation_delta.water_simulation_sha256, native.water_simulation_sha256);
      assert.equal(delta.water_simulation_sha256, native.water_simulation_sha256);
      for (const kind of ["reference", "shipping"]) {
        const row = presentationProof.cases.find((r) => r.case === old.slug && r.kind === kind);
        const section = c[kind];
        assert.equal(row.package.sha256, section.expected_crp_sha256);
        assert.equal(row.base_crp_sha256, section.presentation_delta.base_crp_sha256);
        assert.equal(row.water_simulation_sha256, section.presentation_delta.water_simulation_sha256);
        assert.equal(row.normalized_non_tree_sha256, section.presentation_delta.normalized_non_tree_sha256);
      }
    } else {
      assert.equal(c.shipping.expected_crp_sha256, native.native_crp_sha256, "only shipping is the native-tested full package");
    }
    assert.deepEqual(c.reference.prepared_sha256, native.prepared_sha256);
    for (const [name, digest] of Object.entries(native.prepared_sha256))
      assert.equal(digest, measured.binding.files_sha256[name], `${old.slug}: actual native grid binding`);
    assert.deepEqual(c.shipping.source_files_sha256, current.source_files_sha256);
    if (delta) {
      assert.equal(c.shipping.writer_source_commit, current.presentation_writer_commit, `${old.slug}: delta writer commit`);
      assert.notEqual(c.shipping.writer_source_commit, evaluation.native_tested_head, "a delta re-export is written by a later writer");
    } else {
      assert.equal(c.shipping.writer_source_commit, evaluation.native_tested_head);
    }
    assert.equal(c.shipping.historical_capture_source_commit, old.shipping.source_commit);
    assert.deepEqual(measured.initial_audits, { terrain_exact: true, initial_water_exact: true, source_controls_match: true });
    assert.ok(Object.values(measured.cleanup).every((v) => v.length === 0));
    cases.push({ ...old, ...c.reference, shipping: c.shipping, files_sha256: c.files_sha256, fixture_files: c.fixture_files });
    nativeCases[old.slug] = native;
  }
  return { manifest: { ...historical, cases }, nativeCases, historicalNativeCases, current };
}

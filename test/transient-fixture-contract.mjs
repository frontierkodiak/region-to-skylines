// Fresh physical packages need their own evidence; never inherit native hashes.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";

const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const parse = (bytes) => JSON.parse(new TextDecoder().decode(bytes));

export async function loadTransientContract({ read, readSource, current, historical, historicalNativeCases, factoryFiles, executionSnapshots = {} }) {
  assert.equal(current.version, "pl912-transient-storage-v1");
  assert.equal(current.format, 1);
  assert.equal(current.status, "partial_not_accepted");
  assert.equal(current.previous_contracts.accepted_presentation.file, "current.json");
  assert.equal(current.previous_contracts.native_baseline.file, "contracts/pl912-native-dry-subreach-v1/current.json");
  assert.equal(current.previous_contracts.partial_landing.file, "contracts/pl912-biome-delta-v2/current.json");
  for (const parent of Object.values(current.previous_contracts))
    assert.equal(sha(await read("fixtures/" + parent.file)), parent.sha256, "predecessor evidence changed");
  const partialLanding = parse(await read("fixtures/" + current.previous_contracts.partial_landing.file));
  assert.equal(current.original_native_registry_sha256, partialLanding.source_files_sha256["tools/map-factory/native-water-admission.json"]);
  assert.equal(sha(await read("fixtures/manifest.json")), current.historical_manifest_sha256);
  assert.equal(sha(await read("fixtures/native-qualification.json")), current.historical_native_qualification_sha256);
  assert.deepEqual(current.unverified, ["strict_disableMods_ordinary_menu", "macOS", "populated_long_term"]);
  assert.deepEqual(Object.keys(current.source_files_sha256).sort(), ["inputs.js", "terrain.js", "mapgen.js", ...factoryFiles.map((f) => "tools/map-factory/" + f)].sort());
  for (const [name, digest] of Object.entries(current.source_files_sha256))
    assert.equal(sha(await readSource(name)), digest, `${name}: current contract source changed`);

  async function bound(fileKey, hashKey) {
    const bytes = await read("fixtures/" + current[fileKey]);
    assert.equal(sha(bytes), current[hashKey], fileKey);
    return parse(bytes);
  }
  const preserved = await bound("preserved_fixtures_file", "preserved_fixtures_sha256");
  assert.equal(preserved.baseline_merge, "896f6ddb318b2d7bbe712ec5fdf4919415d296f1");
  assert.equal(Object.keys(preserved.files_sha256).length, 307);
  for (const [name, digest] of Object.entries(preserved.files_sha256))
    assert.equal(sha(await read("fixtures/" + (name === "active.json" ? preserved.active_snapshot : name))), digest, `${name}: historical fixture ${name.split("/").at(-1)} changed`);

  const python = await bound("byte_build_proof_file", "byte_build_proof_sha256");
  const browser = await bound("browser_build_proof_file", "browser_build_proof_sha256");
  const evaluation = await bound("native_evaluation_file", "native_evaluation_sha256");
  const shorts = await bound("short_proof_file", "short_proof_sha256");
  assert.equal(shorts.status, "complete_shorts_not_sixty_minute_qualification");
  assert.equal(shorts.review_issue, "PL-1002");
  assert.deepEqual(shorts.cases.map((c) => c.case), ["rio", "asheville"]);
  for (const [name, digest] of Object.entries(shorts.material_files_sha256))
    assert.equal(sha(executionSnapshots[name] ?? await readSource(name)), digest, `${name}: short-tested execution material changed`);
  for (const c of shorts.cases) {
    assert.equal(c.audit.numeric_short_pass, true);
    assert.equal(c.pool.pool_stage_pass, true);
    assert.deepEqual(c.audit.new_required_five_misses, []);
    assert.deepEqual(c.audit.intake_violations, []);
    assert.equal(c.audit.package_sha256, evaluation.cases.find((r) => r.slug === c.case).crp_sha256);
  }
  assert.equal(python.status, "complete_byte_builds_not_native_qualification");
  assert.equal(browser.status, "complete");
  assert.equal(evaluation.status, "partial_not_accepted");
  assert.equal(python.cases.length, 10);
  assert.equal(browser.cases.length, 10);
  assert.equal(python.source_head, current.native_tested_head);
  assert.equal(browser.source_head, current.native_tested_head);
  assert.equal(evaluation.native_tested_head, current.native_tested_head);
  for (const proof of [python, browser, evaluation])
    assert.deepEqual(proof.source_files_sha256, current.source_files_sha256);
  assert.equal(evaluation.production_writer_sha256, current.source_files_sha256["tools/map-factory/region.py"]);

  const admission = parse(await readSource("tools/map-factory/native-water-admission.json"));
  const predecessor = await bound("original_native_registry_file", "original_native_registry_sha256");
  assert.equal(Object.keys(admission.records).length, 5);
  assert.deepEqual(Object.keys(admission.records).sort(), Object.keys(predecessor.records).sort(), "physical bindings must not change");
  for (const [fingerprint, after] of Object.entries(admission.records)) {
    const before = predecessor.records[fingerprint];
    assert.deepEqual(after.bindings, before.bindings, "restoration must not relax input or forcing bindings");
    const edits = new Map(after.edits.map((e) => [e[0], e]));
    assert.equal(edits.size, after.edits.length);
    for (const e of after.edits) {
      assert.ok(e[2] >= e[1] && e[4] <= e[3], "no lower floor or added water");
    }
    for (const e of before.edits) {
      const next = edits.get(e[0]);
      assert.ok(next, "prior restoration lost");
      assert.equal(next[1], e[1]);
      assert.equal(next[3], e[3]);
      assert.ok(next[2] >= e[2] && next[4] <= e[4], "prior restored floor or cleared water regressed");
    }
  }
  assert.equal(admission.native_engine_sha256, current.native_engine_sha256);
  assert.equal(evaluation.native_engine_sha256, current.native_engine_sha256);

  const slugs = historical.cases.map((c) => c.slug);
  assert.deepEqual(current.cases.map((c) => c.slug), slugs);
  assert.deepEqual(evaluation.cases.map((c) => c.slug), slugs);
  const cases = [], nativeCases = {};
  let observations = 0, required = 0;
  for (const old of historical.cases) {
    const c = current.cases.find((c) => c.slug === old.slug);
    const measured = evaluation.cases.find((c) => c.slug === old.slug);
    const native = c.native;
    assert.ok(measured.clean_source && measured.no_regression && measured.game_minutes >= 60);
    assert.deepEqual(measured.passing_gate_regressions, []);
    assert.ok(Object.values(measured.new_required_point_losses).every((p) => p.length === 0));
    assert.deepEqual(measured.intake_violations, []);
    assert.equal(measured.source_reading_epochs, 13);
    assert.deepEqual(measured.initial_audits, { terrain_exact: true, initial_water_exact: true, source_controls_match: true });
    assert.equal(measured.pool_stage.five_minute_reviewed_stage_pass, true);
    assert.deepEqual(measured.pool_stage.later_stage_findings, []);
    for (const field of ["encoded_terrain_never_lowered", "startup_water_never_added", "all_native_raw_terrain_epochs_exact", "hydrology_records_byte_exact", "resource_plan_arrays_exact", "native_ground_replay_all_recorded_epochs_exact"])
      assert.equal(measured.static_identity[field], true, `${old.slug}: ${field}`);
    for (const epoch of Object.values(measured.static_identity.hydraulic_floor_epochs))
      for (const field of ["all_offsets_guarded", "floor_equals_target", "never_below_reference_native_floor", "reference_offset_pattern_exact"])
        assert.equal(epoch[field], true, `${old.slug}: ${field}`);
    assert.equal(measured.view_bindings.candidate_crp_sha256, native.native_crp_sha256);
    if (["rio", "asheville"].includes(old.slug)) assert.equal(measured.view_bindings.all_ten_camera_fields_equal, true);
    assert.ok(Object.values(measured.cleanup).every((p) => p.length === 0));
    const observation = measured.observation_contract;
    observations += observation.observations;
    required += observation.required;
    assert.equal(measured.static_identity.native_ground_readings_replayed, observation.observations * 13);
    assert.deepEqual(observation.sample_labels, ["t000", "t005", "t010", "t015", "t020", "t025", "t030", "t035", "t040", "t045", "t050", "t055", "t060"]);
    assert.equal(observation.frozen_flood_reference_sha256, measured.frozen_flood_reference_sha256);
    for (const [name, digest] of Object.entries(old.files_sha256))
      assert.equal(sha(await read(`fixtures/${old.slug}/${name}`)), digest, `${old.slug}: original fixture changed`);
    assert.equal(old.input_capture.cli_sha256, historicalNativeCases[old.slug].native_crp_sha256);
    assert.deepEqual(old.input_capture.prepared_sha256, historicalNativeCases[old.slug].prepared_sha256);
    assert.equal(native.native_crp_sha256, measured.crp_sha256);
    assert.equal(native.native_crp_sha256, measured.binding.files_sha256[`PL857-${old.slug}.crp`]);
    assert.equal(native.template_sha256, current.source_files_sha256["tools/map-factory/templates/native-corridors.crp"]);
    assert.equal(native.layout_sha256, current.source_files_sha256["tools/map-factory/templates/native-corridors.json"]);
    assert.equal(c.shipping.expected_crp_sha256, native.native_crp_sha256);
    assert.equal(c.shipping.writer_source_commit, current.native_tested_head);
    assert.deepEqual(c.shipping.source_files_sha256, current.source_files_sha256);
    assert.equal(native.harness_commit, current.native_tested_head);
    assert.equal(native.game_minutes, measured.game_minutes);
    assert.equal(native.strict_vanilla_verified, false);
    assert.equal(native.verdict, measured.native_verdict);
    assert.deepEqual(native.failed_checks, measured.failed);
    assert.deepEqual(native.receipt_sha256, measured.receipt_sha256);
    assert.equal(native.frozen_flood_reference_sha256, measured.frozen_flood_reference_sha256);
    assert.deepEqual(c.reference.prepared_sha256, native.prepared_sha256);
    for (const [name, digest] of Object.entries(native.prepared_sha256))
      assert.equal(digest, measured.binding.files_sha256[name]);
    for (const kind of ["reference", "shipping"]) {
      const py = python.cases.find((r) => r.case === old.slug && r.kind === kind);
      const js = browser.cases.find((r) => r.case === old.slug && r.kind === kind);
      assert.equal(py.expected_crp_sha256, c[kind].expected_crp_sha256);
      assert.equal(js.package_sha256, c[kind].expected_crp_sha256);
      assert.equal(py.expected_crp_bytes, c[kind].expected_crp_bytes);
      assert.deepEqual(js.grids, native.prepared_sha256);
    }
    cases.push({ ...old, ...c.reference, shipping: c.shipping, files_sha256: c.files_sha256, fixture_files: c.fixture_files });
    nativeCases[old.slug] = native;
  }
  assert.equal(observations, 30982);
  assert.equal(required, 7524);
  return { manifest: { ...historical, cases }, nativeCases, historicalNativeCases, current };
}

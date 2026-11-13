// Current byte conformance is distinct from historical or full native acceptance.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
const sha = (b) => createHash("sha256").update(b).digest("hex");
const parse = (b) => JSON.parse(new TextDecoder().decode(b));

export async function loadFixtureContract(read, readSource) {
  const historicalBytes = await read("fixtures/manifest.json");
  const historicalNativeBytes = await read("fixtures/native-qualification.json");
  const historical = parse(historicalBytes);
  const historicalNativeCases = Object.fromEntries(parse(historicalNativeBytes).cases.map((c) => [c.slug, c]));
  const current = parse(await read("fixtures/current.json"));
  assert.equal(current.format, 1);
  assert.equal(current.status, "partial_not_accepted");
  assert.equal(sha(historicalBytes), current.historical_manifest_sha256, "historical fixture contract changed");
  assert.equal(sha(historicalNativeBytes), current.historical_native_qualification_sha256, "historical native evidence changed");
  assert.deepEqual(current.unverified, ["strict_disableMods_ordinary_menu", "macOS", "populated_long_term"]);
  const evaluationBytes = await read("fixtures/" + current.native_evaluation_file);
  assert.equal(sha(evaluationBytes), current.native_evaluation_sha256, "fresh native evaluation changed");
  const evaluation = parse(evaluationBytes);
  assert.equal(evaluation.status, "partial_not_accepted");
  assert.equal(current.native_tested_head, evaluation.native_tested_head);
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
    assert.equal(native.verdict, measured.native_verdict);
    assert.deepEqual(native.failed_checks, measured.failed);
    assert.deepEqual(native.receipt_sha256, measured.receipt_sha256);
    assert.equal(native.native_crp_sha256, measured.binding.files_sha256[`PL857-${old.slug}.crp`]);
    assert.equal(c.shipping.expected_crp_sha256, native.native_crp_sha256, "only shipping is the native-tested full package");
    assert.deepEqual(c.reference.prepared_sha256, native.prepared_sha256);
    for (const [name, digest] of Object.entries(native.prepared_sha256))
      assert.equal(digest, measured.binding.files_sha256[name], `${old.slug}: actual native grid binding`);
    assert.deepEqual(c.shipping.source_files_sha256, current.source_files_sha256);
    assert.equal(c.shipping.writer_source_commit, evaluation.native_tested_head);
    assert.equal(c.shipping.historical_capture_source_commit, old.shipping.source_commit);
    assert.deepEqual(measured.initial_audits, { terrain_exact: true, initial_water_exact: true, source_controls_match: true });
    assert.ok(Object.values(measured.cleanup).every((v) => v.length === 0));
    cases.push({ ...old, ...c.reference, shipping: c.shipping, files_sha256: c.files_sha256, fixture_files: c.fixture_files });
    nativeCases[old.slug] = native;
  }
  return { manifest: { ...historical, cases }, nativeCases, historicalNativeCases, current };
}

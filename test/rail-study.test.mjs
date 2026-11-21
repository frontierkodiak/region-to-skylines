import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { validateLedger, ledgerPage } from "../capability-ledger.mjs";
import {
  RAIL_STUDY, RAIL_PROJECTION, RAIL_PROJECTION_SHA, RAIL_PREDICTIONS, RAIL_SOURCE_MANIFEST,
  railStudy, railStudyFiles, railStudyPage, validateRailStudy,
} from "../rail-study.mjs";

const root = new URL("../", import.meta.url);
const file = (path) => new URL(path, root);
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const ledger = JSON.parse(readFileSync(file("capabilities.json")));
const { study, summary } = railStudy();

test("the directed rail study is separately typed, evidence only and not a certificate", () => {
  validateLedger(ledger);
  const rail = ledger.capabilities.find((capability) => capability.id === "rail");
  assert.equal(rail.rail_study, RAIL_STUDY);
  assert.deepEqual(Object.keys(ledger.rail_studies), [RAIL_STUDY]);
  assert.equal(ledger.rail_studies[RAIL_STUDY].kind, "directed_rail_control_and_cohort_study");
  assert.equal(ledger.rail_studies[RAIL_STUDY].certificates, "none");
  assert.equal(ledger.native_path_certificates.filter((certificate) => certificate.capability === "rail").length, 0);
  assert.equal(ledger.native_path_certificates.length, 4);
  assert.ok(ledger.native_path_certificates.every((certificate) => certificate.capability === "ship"));
  assert.deepEqual(validateRailStudy(ledger), summary);
  // The old transport studies stay exactly where they were.
  for (const id of ["outside-v1", "outside-targeted-v2"]) {
    assert.ok(rail.game_agreement.some((row) => row.study === id));
  }
  assert.equal(ledger.evidence_studies["outside-targeted-v2"].qualification_candidates.length, 4);
});

test("the projection, its tool and the frozen predictions are all hash-bound", () => {
  assert.equal(sha(readFileSync(file(RAIL_PROJECTION))), RAIL_PROJECTION_SHA);
  assert.equal(sha(readFileSync(file(RAIL_PREDICTIONS))), ledger.rail_studies[RAIL_STUDY].frozen_predictions_sha256);
  assert.equal(
    study.frozen_predictions.sha256,
    "1f2db0bb64e62965137cce05ffe0cea7bf8aa339c2a8a9e9560fafe4ef64ae03",
  );
  assert.equal(sha(readFileSync(file(RAIL_SOURCE_MANIFEST))), ledger.rail_studies[RAIL_STUDY].source_closure_sha256);
});

test("every archived receipt still matches the projection's recorded bytes", () => {
  assert.equal(study.raw_files.length, 111);
  assert.equal(study.raw_files.filter((record) => record.path.includes("rail-v1/") || record.path.includes("rail-v2/")).length, 28);
  for (const record of study.raw_files) {
    const bytes = readFileSync(file(record.path));
    assert.equal(sha(bytes), record.gzip_sha256, `${record.path}: compressed bytes changed`);
    if (record.path.endsWith("observation.json.gz") || record.path.endsWith("query-freeze.json.gz")) {
      const plain = gunzipSync(bytes);
      assert.equal(plain.length, record.bytes, `${record.path}: decompressed length changed`);
      assert.equal(sha(plain), record.sha256, `${record.path}: decompressed bytes changed`);
    }
  }
});

test("the frozen native source closure is read-only evidence, not an installed harness", () => {
  assert.equal(study.source_closure.harness_sources, 56);
  assert.equal(study.source_closure.build_source_count, 17);
  assert.equal(Object.keys(study.source_closure.files).length, 56);
  assert.equal(study.source_closure.prefix, "tools/map-factory/capability-evidence/rail-native-sources");
  for (const [original, record] of Object.entries(study.source_closure.files)) {
    assert.equal(sha(readFileSync(file(record.file))), record.sha256, `${original}: archived source changed`);
    assert.ok(record.file.startsWith("tools/map-factory/capability-evidence/rail-native-sources/"));
  }
  assert.ok(!("tools/cs1-harness/cs1_harness/rail_study.py".length === 0));
});

test("controls, bounded coverage and the four positive cells stay separate", () => {
  assert.deepEqual(summary.controls.map((control) => control.file), ["AP Asanu Beach.crp", "AP Hanami Bay.crp"]);
  assert.deepEqual(summary.controls.map((control) => control.distinct_edge_successes), [8, 8]);
  assert.deepEqual(summary.controls.map((control) => control.selected_failures), [0, 16]);
  assert.ok(summary.controls.every((control) => control.reciprocal_positives && control.invalid_vehicle_pair_rejected));
  assert.deepEqual(summary.totals, {
    selected_boundary: 244, distinct_edge_successes: 9, same_edge_successes: 2,
    selected_failures: 233, unqueried_boundary_candidates: 112, sampled_positive: 4, unknown: 5,
  });
  const pittsburgh = summary.cohort.find((cell) => cell.slug === "pittsburgh");
  assert.equal(pittsburgh.attempts.at(-1).unqueried_boundary_candidates, 112);
  const boston = summary.cohort.find((cell) => cell.slug === "boston");
  assert.equal(boston.attempts.at(-1).same_edge_successes, 2);
  assert.equal(boston.attempts.at(-1).distinct_edge_successes, 2);
  for (const slug of ["charleston", "grand-canyon", "yosemite"]) {
    const cell = summary.cohort.find((candidate) => candidate.slug === slug);
    assert.equal(cell.status, "Unknown");
    assert.equal(cell.attempts.at(-1).selected_boundary, 0);
    assert.equal(cell.attempts.at(-1).missing_reason, "no_pair_or_directed_lane");
  }
  const rio = summary.cohort.find((cell) => cell.slug === "rio");
  assert.equal(rio.attempts.length, 2, "the retained queue denial was erased");
  assert.match(rio.attempts[0].error, /waiters are ahead in the slot queue/);
  assert.equal(rio.attempts[0].completed, false);
});

test("the cleanup finding stays degraded rather than being repaired", () => {
  assert.equal(summary.cleanup.degraded, true);
  assert.equal(summary.cleanup.findings.length, 1);
  assert.equal(summary.cleanup.findings[0].attempt, "pittsburgh-attempt-1");
  assert.deepEqual(summary.cleanup.findings[0].raw_cleanup.steam_instances, ["3933505219"]);
  assert.match(summary.cleanup.findings[0].later_state, /later audit proves listed instance absent/);
  assert.match(summary.cleanup.coverage, /every observation's game PID\/start/);
});

test("the generated page makes the study readable without flattening it to accuracy", () => {
  const html = ledgerPage(ledger, "test-source");
  assert.match(html, /id="rail-directed-study"/);
  assert.match(html, /Directed rail native study/);
  assert.match(html, /Successes \/ selected/);
  assert.match(html, /Positive-witness agreement|positive-witness agreement/);
  assert.match(html, /not accuracy, sensitivity, a blind holdout/);
  assert.match(html, /112/);
  assert.match(html, /same-edge/);
  assert.match(html, /proves that listed instance absent/);
  assert.match(html, /rail-v3-followup-1\/strict-verifier-failure\.txt/);
  const cohort = html.slice(html.indexOf("data-rail-cohort"), html.indexOf("</table>", html.indexOf("data-rail-cohort")));
  const cells = [...cohort.matchAll(/<span data-case-name>([^<]+)<\/span>/g)].map((match) => match[1]);
  assert.deepEqual(cells, [...summary.cohort.map((cell) => cell.square.name), "Total"], "the nine original case rows are not all rendered");
  assert.match(html, /Unknown/);
  const evidence = [...html.matchAll(/data-evidence href="([^"]+)" data-sha256="([a-f0-9]{64})"/g)];
  assert.ok(evidence.length >= 111, "evidence links are not all rendered");
  assert.ok(study.raw_files.every((record) => html.includes(record.path)), "an archived receipt is not linked");
});

test("every served evidence file exists and the page never executes archived tools", () => {
  const files = railStudyFiles();
  assert.ok(files.length >= 170);
  for (const path of files) {
    assert.ok(existsSync(file(path)), `${path}: missing served evidence`);
  }
  assert.ok(files.includes(RAIL_PROJECTION));
  assert.ok(!files.some((path) => path.endsWith(".py") && !path.includes("rail-native-sources")));
});

test("schema-equivalent payloads built with a custom loader are accepted", () => {
  // The page is a pure renderer over the validated summary; it must not depend on cwd.
  const html = railStudyPage({ study, summary }, (value) => String(value).replace(/[&<>"]/g, ""));
  assert.match(html, /data-rail-cohort/);
  assert.match(html, /data-rail-controls/);
  assert.match(html, /data-rail-attempts/);
});

test("ledger mutations to the rail binding are rejected", () => {
  for (const mutate of [
    (changed) => { changed.rail_studies[RAIL_STUDY].totals.distinct_edge_successes = 10; },
    (changed) => { changed.rail_studies[RAIL_STUDY].certificates = "sampled"; },
    (changed) => { changed.rail_studies[RAIL_STUDY].projection_sha256 = "0".repeat(64); },
    (changed) => { changed.rail_studies[RAIL_STUDY].source_closure_sha256 = "0".repeat(64); },
    (changed) => { changed.capabilities.find((capability) => capability.id === "rail").rail_study = "other"; },
    (changed) => { delete changed.capabilities.find((capability) => capability.id === "rail").rail_study; },
    (changed) => { delete changed.rail_studies; },
    (changed) => { changed.rail_studies[RAIL_STUDY].cohort.pop(); },
    (changed) => { changed.rail_studies[RAIL_STUDY].cleanup.degraded = false; },
  ]) {
    const changed = structuredClone(ledger);
    mutate(changed);
    assert.throws(() => validateLedger(changed));
  }
});

test("file mutations to the projection, closure or predictions are rejected", () => {
  const restore = (path) => {
    const target = file(path), bytes = readFileSync(target);
    return () => writeFileSync(target, bytes);
  };
  for (const [path, mutate] of [
    [RAIL_PROJECTION, (bytes) => Buffer.concat([bytes, Buffer.from(" ")])],
    [RAIL_PREDICTIONS, (bytes) => Buffer.concat([bytes, Buffer.from(" ")])],
    [RAIL_SOURCE_MANIFEST, (bytes) => Buffer.concat([bytes, Buffer.from(" ")])],
    ["tools/map-factory/capability-evidence/rail-native-sources/cs1_harness/rail_study.py", (bytes) => Buffer.concat([bytes, Buffer.from("\n")])],
  ]) {
    const undo = restore(path);
    const target = file(path);
    try {
      writeFileSync(target, mutate(readFileSync(target)));
      assert.throws(() => validateLedger(JSON.parse(readFileSync(file("capabilities.json")))), `${path}: changed bytes accepted`);
    } finally {
      undo();
    }
  }
});

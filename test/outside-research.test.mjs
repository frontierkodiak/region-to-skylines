import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { validateLedger, ledgerPage } from "../capability-ledger.mjs";
import {
  OUTSIDE_RESEARCH_PROJECTION, OUTSIDE_RESEARCH_PROJECTION_SHA, OUTSIDE_RESEARCH_SOURCES,
  OUTSIDE_RESEARCH_SOURCES_SHA, OUTSIDE_RESEARCH_STUDY, OUTSIDE_RESEARCH_TOOL,
  OUTSIDE_RESEARCH_TOOL_SHA, outsideResearch, outsideResearchFiles, outsideResearchPage,
  outsideResearchReference, validateOutsideResearch,
} from "../outside-research.mjs";

const root = new URL("../", import.meta.url);
const file = (path) => new URL(path, root);
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const ledger = JSON.parse(readFileSync(file("capabilities.json")));
const { projection, study, summary } = outsideResearch();
const escape = (value) => String(value).replace(/[&<>"']/g, (character) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);

test("one accepted outside-connection study is referenced from Road, Ship and Air", () => {
  validateLedger(ledger);
  for (const id of ["road", "ship", "air"]) {
    const capability = ledger.capabilities.find((entry) => entry.id === id);
    assert.deepEqual(capability.outside_research_studies, [OUTSIDE_RESEARCH_STUDY]);
  }
  for (const id of ["rail", "water", "start", "buildable", "resources", "trees", "water_risk"]) {
    assert.equal(ledger.capabilities.find((entry) => entry.id === id).outside_research_studies, undefined);
  }
  assert.deepEqual(Object.keys(ledger.outside_research_studies), [
    "kind", "study", "source_commit", "source_base", "internal_merge", "source_issue", "pull_request",
    "publication_files", "copied_files", "linked_files", "projection_file", "projection_sha256",
    "projection_tool_file", "projection_tool_sha256", "source_manifest_file", "source_manifest_sha256",
    "freeze", "selected_queries", "primary_queries", "rows", "packages", "modes", "primary_fitted",
    "same_edge_fitted", "evidence_files_sha256", "certificates",
  ]);
  assert.deepEqual(validateOutsideResearch(ledger), summary);
  assert.equal(study.evidence_only, true);
  assert.equal(study.certificates, "none");
  // The study is not a native study and adds no certificate.
  assert.equal(ledger.native_path_certificates.length, 4);
  assert.equal(ledger.evidence_studies[OUTSIDE_RESEARCH_STUDY], undefined);
  assert.equal(ledger.evidence_studies["outside-targeted-v2"].source_commit, "29b095475ba2f93c7e918fefc08c736493670304");
  assert.equal(Object.keys(ledger.evidence_studies).length, 2);
  // The rail research integration is untouched.
  assert.deepEqual(ledger.capabilities.find((entry) => entry.id === "rail").rail_research_studies, [
    "rail-query-model-v1", "rail-junction-fit-v1", "rail-stock-holdout-v1",
  ]);
});

test("the projection, its tool and the strict source manifest are hash-bound", () => {
  assert.equal(sha(readFileSync(file(OUTSIDE_RESEARCH_PROJECTION))), OUTSIDE_RESEARCH_PROJECTION_SHA);
  assert.equal(sha(readFileSync(file(OUTSIDE_RESEARCH_SOURCES))), OUTSIDE_RESEARCH_SOURCES_SHA);
  assert.equal(sha(readFileSync(file(OUTSIDE_RESEARCH_TOOL))), OUTSIDE_RESEARCH_TOOL_SHA);
  assert.equal(projection.source_manifest.file, OUTSIDE_RESEARCH_SOURCES);
  assert.equal(projection.source_manifest.sha256, OUTSIDE_RESEARCH_SOURCES_SHA);
  assert.deepEqual(Object.keys(projection.studies), [OUTSIDE_RESEARCH_STUDY]);
  assert.equal(summary.projection_sha256, OUTSIDE_RESEARCH_PROJECTION_SHA);
  assert.equal(summary.projection_tool_sha256, OUTSIDE_RESEARCH_TOOL_SHA);
  assert.equal(summary.source_manifest_sha256, OUTSIDE_RESEARCH_SOURCES_SHA);
});

test("the publication's whole file scope is pinned and only the compact files are carried", () => {
  const manifest = JSON.parse(readFileSync(file(OUTSIDE_RESEARCH_SOURCES)));
  const publication = manifest.publications[OUTSIDE_RESEARCH_STUDY];
  assert.equal(publication.commit, "030db86ce470b972b6ef3462a2698744dff40ebb");
  assert.equal(Object.keys(publication.files).length, 21);
  assert.equal(publication.copied.length, 18);
  assert.equal(publication.linked.length, 3);
  assert.deepEqual([...publication.linked].sort(), ["inventory.json", "predictions.json", "requests.json"]);
  for (const [relative, record] of Object.entries(publication.files)) {
    assert.match(record.sha256, /^[a-f0-9]{64}$/, `${relative} lacks a content hash`);
    assert.match(record.git_blob, /^[a-f0-9]{40}$/, `${relative} lacks a Git blob id`);
    assert.ok(record.bytes > 0, `${relative} has no size`);
    const path = `${publication.prefix}/${relative}`;
    if (publication.copied.includes(relative)) {
      const raw = readFileSync(file(path));
      assert.equal(sha(raw), record.sha256, `${relative}: carried bytes changed`);
      assert.equal(raw.length, record.bytes, `${relative}: carried size changed`);
      const digest = createHash("sha1").update(Buffer.concat([Buffer.from(`blob ${raw.length}\0`), raw])).digest("hex");
      assert.equal(digest, record.git_blob, `${relative}: Git blob id does not follow its bytes`);
    } else {
      assert.equal(existsSync(file(path)), false, `${relative}: bulk source duplicated in the repository`);
    }
  }
  // Carried and linked partition the publication, and nothing extra sits under the prefix.
  assert.deepEqual([...publication.copied, ...publication.linked].sort(), Object.keys(publication.files).sort());
  for (const record of study.files) assert.ok(record.path.startsWith(publication.prefix + "/"));
  assert.equal(study.files.length, 18);
  assert.equal(study.linked.length, 3);
});

test("every linked source document is corroborated by the publication's own hashes", () => {
  const protocol = JSON.parse(readFileSync(file(`${study.closure.prefix}/protocol.json`)));
  const integrity = JSON.parse(readFileSync(file(`${study.closure.prefix}/integrity.json`)));
  const bindings = JSON.parse(readFileSync(file(`${study.closure.prefix}/bindings.json`)));
  const manifest = JSON.parse(readFileSync(file(`${study.closure.prefix}/manifest.json`)));
  assert.equal(protocol.predictions_sha256, integrity.hashes["predictions.json"]);
  assert.equal(protocol.predictions_sha256, bindings.files["predictions.json"]);
  assert.equal(protocol.predictions_bytes, 845394);
  assert.equal(protocol.sources.requests, manifest.hashes["requests.json"]);
  assert.equal(protocol.sources.inventory, manifest.hashes["inventory.json"]);
  assert.equal(protocol.sources.inventory, integrity.hashes["inventory.json"]);
  for (const record of study.linked) {
    const relative = record.path.slice(study.closure.prefix.length + 1);
    assert.ok(record.declared_by.length >= 2, `${relative} is declared once and could be re-pinned alone`);
    assert.deepEqual(record.declared_by, study.declarations[relative]);
  }
  // The collector source is a real, fixed identity, not a display name.
  assert.equal(protocol.domain.collector_source.sha256, "d644218e8969f40737ce08367a3a3e4c9adb6a550ba145fb3bf220ffa5f23813");
  assert.equal(protocol.domain.collector_source.revision, "29b095475ba2f93c7e918fefc08c736493670304");
  assert.equal(bindings.source_revisions.accepted_base, "49cf49516f4aa8b24a154d9923c1a6fd149bf1a3");
});

test("the protocol is the corrected per-mode one and the freeze claims no observation date", () => {
  const domain = study.protocol.domain;
  assert.deepEqual(domain.mode_vehicle, { road: "Car", ship: "Ship", air: "Plane" });
  assert.deepEqual(domain.category_by_mode, { road: "PassengerCar", ship: "All", air: "All" });
  assert.deepEqual(domain.accepted_lane_types.road, ["Vehicle"]);
  assert.deepEqual(domain.accepted_lane_types.ship, ["CargoVehicle", "TransportVehicle", "Vehicle"]);
  assert.deepEqual(domain.accepted_lane_types.air, ["CargoVehicle", "TransportVehicle", "Vehicle"]);
  assert.equal(domain.max_length, 100000);
  assert.match(study.protocol.protocol_copied_from_source, /seed 857/);
  assert.match(study.protocol.protocol_copied_from_source, /literal \[segment,lane,offset\] endpoints/);
  assert.equal(study.protocol.primary_rule, "lane:any_lane:forbidden");
  assert.equal(study.protocol.rules.length, 12);
  assert.equal(study.protocol.baselines.length, 4);
  assert.equal(study.freeze.retrospective, true);
  assert.equal(study.freeze.frozen_before_observations, false);
  assert.equal(study.freeze.observation_dates, "unknown");
  assert.equal(study.freeze.frozen_at, "2026-11-23T08:53:14.972926+00:00");
  assert.equal(study.freeze.predictions_sha256, "3c38dd19b38fadc90b2e2b0240b2e6a35ad13c2953c591e8cc71270e9a2cfc11");
  // The page must not present the freeze time as an observation date.
  const html = ledgerPage(ledger, "test-source");
  const section = html.slice(html.indexOf('data-outside-research'), html.indexOf('</article>', html.indexOf('data-outside-research')));
  assert.match(section, /not<\/strong> an observation date/);
  assert.match(section, /observation dates: Unknown/);
});

test("all 876 retained rows are preserved with their exclusions and Unknowns", () => {
  assert.equal(study.rows.length, 876);
  assert.equal(study.selection.queries, 876);
  assert.equal(study.selection.eligible, 378);
  assert.equal(study.selection.primary, 342);
  assert.equal(study.selection.same_edge, 36);
  assert.equal(study.selection.literal_request_rows, 820);
  assert.equal(study.selection.excluded_rows, 498);
  assert.equal(study.selection.anomalies ?? study.anomalies.length, 3);
  assert.deepEqual(study.selection.by_stratum, {
    archived_player_run: 28,
    midpoint_diagnostic: 378,
    primary_distinct_edge: 342,
    same_edge: 36,
    unclassified_protocol: 64,
    unrequested: 28,
  });
  assert.deepEqual(study.selection.by_exclusion, {
    midpoint_diagnostic_unscored: 378,
    no_request_recorded: 28,
    player_construction_not_unchanged_map: 28,
    protocol_fields_absent: 64,
  });
  // Unlabelled rows stay Unknown; no exclusion becomes a failure or an invented negative.
  assert.equal(study.rows.filter((row) => row.label === null).length, 92);
  assert.equal(study.rows.filter((row) => row.recorded_outcome !== null).length, 848);
  assert.equal(study.exclusions.length, 498);
  for (const row of study.exclusions) assert.ok(row.exclusion && row.stratum);
  const anomalies = study.anomalies.map((row) => `${row.slug}/${row.attempt_id}`).sort();
  assert.deepEqual(anomalies, ["asheville/attempt-1", "pittsburgh/native-v2-2", "rio/native-v2-1"]);
  assert.deepEqual(study.selection.midpoint_repeats, { agree: 378, pairs: 378 });
  assert.deepEqual(study.selection.cross_opening_repeats, { agree: 8, pairs: 8 });
});

test("the primary rule and the fitted rule are tied, not proven equivalent", () => {
  const primary = study.rules.primary_stratum["lane:any_lane:forbidden"].counts;
  const fitted = study.rules.primary_stratum.directed_segment.counts;
  assert.deepEqual(primary, { tp: 93, fp: 19, tn: 230, fn: 0, abstain: 0, unknown: 0 });
  assert.deepEqual(fitted, primary);
  assert.equal(study.rules.fitted, "directed_segment");
  assert.equal(study.rules.primary, "lane:any_lane:forbidden");
  assert.deepEqual(study.rules.same_edge.directed_segment.counts, { tp: 9, fp: 0, tn: 27, fn: 0, abstain: 0, unknown: 0 });
  // The equivalence classes: lane continuity buys nothing on this evidence.
  const classes = study.rules.identical.road.map((group) => [...group].sort());
  assert.ok(classes.some((group) => JSON.stringify(group) === JSON.stringify(
    ["directed_segment", "lane:any_lane:allowed", "lane:any_lane:forbidden"])));
  assert.ok(classes.some((group) => JSON.stringify(group) === JSON.stringify(
    ["lane:index_mirror:forbidden", "lane:orientation_mirror:forbidden"])));
});

test("per mode keeps road's two classes apart from ship and air's one class", () => {
  const road = study.modes.road;
  assert.equal(road.primary, 316);
  assert.equal(road.successes, 67);
  assert.equal(road.failures, 249);
  assert.equal(road.discrimination_estimable, true);
  assert.deepEqual(road.fitted.directed_segment.counts, { tp: 67, fp: 19, tn: 230, fn: 0, abstain: 0, unknown: 0 });
  for (const [mode, primary, successes] of [["ship", 16, 16], ["air", 10, 10]]) {
    const record = study.modes[mode];
    assert.equal(record.primary, primary);
    assert.equal(record.successes, successes);
    assert.equal(record.failures, 0);
    assert.equal(record.discrimination_estimable, false);
    assert.equal(record.fitted.directed_segment.rates.precision, 1);
    assert.equal(study.one_class[mode].discrimination_estimable, false);
    assert.equal(study.one_class[mode].negatives, 0);
  }
  assert.equal(study.one_class.ship.note, "one class only: the retained evidence for this mode contains successful requests and no observed failures. The arithmetic precision is therefore trivially 1 and no discrimination among the frozen rules is estimable.");
});

test("every group, package and fold preserves the accepted numbers", () => {
  assert.deepEqual(study.selection.groups["PL-1121 first openings"], {
    n: 114, tp: 27, fp: 0, tn: 87, fn: 0, fidelity: "collector-recipe-only",
  });
  assert.deepEqual(study.selection.groups["PL-1142 targeted openings"], {
    n: 264, tp: 75, fp: 19, tn: 170, fn: 0, fidelity: "runtime-bound",
  });
  assert.deepEqual(study.selection.package_groups["hong-kong"], { n: 102, tp: 11, fp: 6, tn: 85, fn: 0 });
  assert.deepEqual(study.selection.package_groups.pittsburgh, { n: 148, tp: 53, fp: 13, tn: 82, fn: 0 });
  assert.equal(study.folds.length, 6);
  for (const fold of study.folds) {
    assert.equal(fold.selected_rule, "directed_segment");
    assert.equal(fold.held_out_rows, study.selection.package_groups[fold.held_out].n);
  }
  assert.equal(study.folds.reduce((total, fold) => total + fold.fp, 0), 19);
  assert.deepEqual(study.folds.filter((fold) => fold.fp > 0).map((fold) => fold.held_out).sort(),
    ["hong-kong", "pittsburgh"]);
});

test("all 19 disagreements stay unexplained false positives, never a length rule", () => {
  assert.equal(study.disagreements.length, 19);
  assert.equal(study.length_check.binds, false);
  assert.equal(study.length_check.max_directed_chord_over_cap, 0.48886885468);
  assert.deepEqual(study.length_check.cap_sensitive_no_path, []);
  for (const row of study.disagreements) {
    assert.equal(row.mode, "road");
    assert.equal(row.relation, "false_positive");
    assert.equal(row.mechanism_status, "unknown");
    assert.deepEqual(
      { complete: row.native.complete, released: row.native.released, success: row.native.success, flags: row.native.flags, length: row.native.length },
      { complete: true, released: true, success: false, flags: 8, length: 100000 },
    );
    assert.ok(row.path_lower_bound_length >= 21735 && row.path_lower_bound_length <= 30917,
      `${row.query_id}: chord lower bound moved outside the reported band`);
  }
  assert.match(study.limits, /19 road false positives/);
  assert.match(study.limits, /not proof that a search budget was exhausted/);
  assert.match(study.limits, /not blind or global accuracy/);
  assert.match(study.limits, /Chord length is not a native cost/);
  assert.match(study.method, /No scorer, predictor or native run is repeated/);
});

test("the bridge re-checks every field the model reads on the nine packages", () => {
  assert.equal(study.bridge.answer, "yes");
  assert.deepEqual(study.bridge.totals, {
    segments_native: 27191,
    nodes_native: 26633,
    segments_built: 27191,
    nodes_built: 26633,
    start_end_equal: 27191,
    prefab_equal: 27191,
    lanes_equal: 27191,
    invert_equal: 27191,
    chords_equal_within_2pct: 27136,
    chords_equal_within_20pct: 27191,
    positions_within_tolerance: 25993,
    outside_nodes_equal: 26633,
    node_flags_differ_count: 1213,
    node_flags_differ_outside_disagreements: 0,
  });
  assert.equal(study.bridge.catalog.prefabs, 12);
  assert.deepEqual(study.bridge.catalog_uncovered,
    { asheville: 1, boston: 0, charleston: 0, "grand-canyon": 0, "hong-kong": 2, innsbruck: 0, pittsburgh: 0, rio: 0, yosemite: 0 });
  assert.ok(Object.values(study.bridge.packages).every((record) => record.mode_inputs_equal === true));
  assert.equal(study.bridge.limitations.length, 3);
  // The catalog hash binds the carried catalogs bytes.
  assert.equal(study.bridge.catalog.sha256_catalogs_json,
    sha(readFileSync(file(`${study.closure.prefix}/catalogs.json`))));
});

test("the package identities and the per-opening collector builds are pinned", () => {
  assert.equal(study.packages.asheville.sha256, "0b92ed3ddd833d48c3af993ca254e4b891bac1d8ac84b99a98b679e47f047870");
  assert.equal(study.packages.pittsburgh.bytes, 7393376);
  assert.equal(Object.keys(study.packages).length, 9);
  assert.equal(study.openings.length, 17);
  const collectors = new Set(study.openings.map((opening) => opening.collector_sha256));
  assert.deepEqual([...collectors].sort(), [
    "818e6a12d15fb0a90bd7c3155a2199d942c01ebb744888a03ebfb5f9d5797df1",
    "a1c774edbe768a9d4168aa1df429f0996538c18d9808daecc837c5755c0e1def",
    "d5a40930097dd7482fc71e9124a632c42a4c82a67a682c981cb05aafcac3d358",
    "e3488f300e8797fd2e92dfb182e7c55988a1831d57d8a97908f74d3a7952a6f6",
  ]);
  for (const opening of study.openings) {
    assert.equal(opening.artifact_sha256, study.packages[opening.slug].sha256,
      `${opening.slug}/${opening.attempt_id}: opening package identity changed`);
  }
  for (const slug of ["asheville", "boston", "charleston", "grand-canyon", "hong-kong", "innsbruck", "pittsburgh", "rio", "yosemite"]) {
    assert.deepEqual(study.runtime.lineage[slug], {
      cpu_evidence: `cpu_evidence_${slug}`,
      reproduction_evidence: `reproduction_evidence_${slug}`,
      package_lineage: `package_lineage_${slug}`,
    });
  }
});

test("the generated page renders mode and stratum groups, complete rows and served evidence", () => {
  const html = ledgerPage(ledger, "test-source");
  assert.match(html, /id="outside-research-study"/);
  assert.match(html, /Outside-connection query evidence/);
  assert.equal((html.match(/Outside-connection query evidence/g) ?? []).length, 3);
  const section = html.slice(html.indexOf('data-outside-research'));
  assert.match(section, /Primary stratum · distinct edges · all modes/);
  assert.match(section, /TP 93 · FP 19 · TN 230 · FN 0/);
  assert.match(section, /pre-registered primary/);
  assert.match(section, /Ship and air are one class/);
  assert.match(section, /Every disagreement/);
  assert.match(section, /mechanism_status|unknown/);
  assert.match(section, /Complete rows · 876 retained requests/);
  assert.match(section, /Exclusions, anomalies and eligibility rules/);
  assert.match(section, /data-outside-rows/);
  assert.match(section, /data-outside-modes/);
  assert.match(section, /data-outside-groups/);
  assert.match(section, /data-outside-packages/);
  assert.match(section, /data-outside-folds/);
  assert.match(section, /data-outside-disagreements/);
  assert.match(section, /data-outside-bridge/);
  // 876 retained rows plus the exclusion, mode and bridge tables.
  const rows = section.slice(section.indexOf("data-outside-rows"), section.indexOf("data-outside-exclusions"));
  assert.equal((rows.match(/<tr>/g) ?? []).length, 877);
  for (const [attribute, expected] of [["primary", 7], ["modes", 3], ["groups", 2], ["packages", 6],
    ["folds", 6], ["disagreements", 19], ["all-rules", 12], ["exclusions", 498], ["anomalies", 3], ["bridge", 9]]) {
    const start = section.indexOf(`data-outside-${attribute}`);
    assert.ok(start > 0, `missing the ${attribute} table`);
    const body = section.slice(start, section.indexOf("</table>", start));
    assert.equal((body.match(/<tr>/g) ?? []).length - 1, expected, `${attribute} table row count`);
  }
  for (const record of study.files) {
    assert.ok(section.includes(record.path), `${record.path}: carried evidence is not linked`);
  }
  for (const record of study.linked) {
    assert.ok(section.includes(`https://github.com/frontierkodiak/region-to-skylines/blob/030db86ce470b972b6ef3462a2698744dff40ebb/${record.path}`),
      `${record.path}: linked source is not an immutable blob link`);
  }
  // The capability references are mode-scoped, not a second copy of the study.
  const road = html.slice(html.indexOf('<article id="road">'), html.indexOf('<article id="rail">'));
  assert.match(road, /Road has 316 primary requests: TP 67 · FP 19 · TN 230 · FN 0/);
  const ship = html.slice(html.indexOf('<article id="ship">'), html.indexOf('<article id="air">'));
  assert.match(ship, /one class only/);
  assert.match(ship, /not a service or a guarantee/);
  // Nothing claims this evidence is the current runtime estimate, accuracy or a promise.
  assert.doesNotMatch(section, /accuracy: \d/);
  assert.doesNotMatch(section, /promised/);
});

test("every served file exists and no research code is imported or executed", () => {
  const files = outsideResearchFiles();
  assert.equal(files.length, 18 + 2);
  for (const path of files) assert.ok(existsSync(file(path)), `${path}: missing served evidence`);
  assert.ok(files.includes(OUTSIDE_RESEARCH_PROJECTION));
  assert.ok(files.includes(OUTSIDE_RESEARCH_SOURCES));
  const module = readFileSync(file("outside-research.mjs"), "utf8");
  for (const forbidden of ["child_process", "execFile", "spawn(", "eval(", "python"]) {
    assert.ok(!module.includes(forbidden), `the renderer must not execute research code: ${forbidden}`);
  }
  // The bulk sources are never served from this repository.
  for (const record of study.linked) assert.ok(!files.includes(record.path));
  // The reference renderer is a pure function of the validated study.
  const html = outsideResearchReference("ship", { study }, escape);
  assert.match(html, /Ship has 16 primary requests/);
  assert.match(html, /href="#outside-research-study"/);
  const page = outsideResearchPage({ study }, escape);
  assert.match(page, /data-outside-research/);
  assert.equal((page.match(/data-outside-rows/g) ?? []).length, 1);
});

test("ledger mutations to the study binding are rejected", () => {
  for (const mutate of [
    (changed) => { changed.outside_research_studies.selected_queries = 377; },
    (changed) => { changed.outside_research_studies.rows = 875; },
    (changed) => { changed.outside_research_studies.primary_fitted.fp = 18; },
    (changed) => { changed.outside_research_studies.modes.ship.discrimination_estimable = true; },
    (changed) => { changed.outside_research_studies.freeze.frozen_before_observations = true; },
    (changed) => { changed.outside_research_studies.certificates = "sampled"; },
    (changed) => { changed.outside_research_studies.projection_sha256 = "0".repeat(64); },
    (changed) => { delete changed.outside_research_studies; },
    (changed) => { changed.capabilities.find((entry) => entry.id === "road").outside_research_studies = []; },
    (changed) => { delete changed.capabilities.find((entry) => entry.id === "ship").outside_research_studies; },
    (changed) => { changed.capabilities.find((entry) => entry.id === "rail").outside_research_studies = [OUTSIDE_RESEARCH_STUDY]; },
    (changed) => { changed.native_path_certificates.push({ capability: "road", study: OUTSIDE_RESEARCH_STUDY }); },
  ]) {
    const changed = structuredClone(ledger);
    mutate(changed);
    assert.throws(() => validateLedger(changed));
  }
});

test("file mutations to the projection, manifest, tool or carried evidence are rejected", () => {
  const restore = (path) => {
    const target = file(path), bytes = readFileSync(target);
    return () => writeFileSync(target, bytes);
  };
  const carried = study.files[0].path;
  for (const [path, mutate] of [
    [OUTSIDE_RESEARCH_PROJECTION, (bytes) => Buffer.concat([bytes, Buffer.from(" ")])],
    [OUTSIDE_RESEARCH_SOURCES, (bytes) => Buffer.concat([bytes, Buffer.from(" ")])],
    [OUTSIDE_RESEARCH_TOOL, (bytes) => Buffer.concat([bytes, Buffer.from("\n")])],
    [carried, (bytes) => Buffer.concat([bytes, Buffer.from("\n")])],
  ]) {
    const undo = restore(path);
    try {
      writeFileSync(file(path), mutate(readFileSync(file(path))));
      assert.throws(() => validateLedger(JSON.parse(readFileSync(file("capabilities.json")))), `${path}: changed bytes accepted`);
    } finally {
      undo();
    }
  }
});

test("re-pinning a changed source file in the manifest cannot defeat the canonical pin", () => {
  // The adversarial case: change a carried evidence file AND the declared manifest
  // together, as if the publication had been re-pinned to the new bytes.
  const manifestPath = OUTSIDE_RESEARCH_SOURCES;
  const carriedPath = `${study.closure.prefix}/evaluation.json`;
  const manifestBytes = readFileSync(file(manifestPath));
  const carriedBytes = readFileSync(file(carriedPath));
  const manifest = JSON.parse(manifestBytes);
  const changed = Buffer.concat([carriedBytes, Buffer.from(" ")]);
  manifest.publications[OUTSIDE_RESEARCH_STUDY].files["evaluation.json"] = {
    ...manifest.publications[OUTSIDE_RESEARCH_STUDY].files["evaluation.json"],
    sha256: sha(changed),
    bytes: changed.length,
  };
  try {
    writeFileSync(file(carriedPath), changed);
    writeFileSync(file(manifestPath), JSON.stringify(manifest, null, 1) + "\n");
    assert.throws(() => validateLedger(JSON.parse(readFileSync(file("capabilities.json")))));
    assert.throws(() => outsideResearch());
  } finally {
    writeFileSync(file(carriedPath), carriedBytes);
    writeFileSync(file(manifestPath), manifestBytes);
  }
  // The restored bytes still validate.
  validateOutsideResearch(JSON.parse(readFileSync(file("capabilities.json"))));
});

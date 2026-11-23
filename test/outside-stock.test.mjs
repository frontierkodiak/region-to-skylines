import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { validateLedger, ledgerPage } from "../capability-ledger.mjs";
import {
  OUTSIDE_STOCK_PROJECTION, OUTSIDE_STOCK_PROJECTION_SHA, OUTSIDE_STOCK_SOURCES,
  OUTSIDE_STOCK_SOURCES_SHA, OUTSIDE_STOCK_STUDY, OUTSIDE_STOCK_TOOL,
  OUTSIDE_STOCK_TOOL_SHA, outsideStock, outsideStockFiles, outsideStockPage,
  outsideStockReference, validateOutsideStock,
} from "../outside-stock.mjs";

const root = new URL("../", import.meta.url);
const file = (path) => new URL(path, root);
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const ledger = JSON.parse(readFileSync(file("capabilities.json")));
const { projection, study, summary } = outsideStock();
const escape = (value) => String(value).replace(/[&<>"']/g, (character) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);

test("one accepted outside-stock study is referenced from Road, Ship and Air", () => {
  validateLedger(ledger);
  for (const id of ["road", "ship", "air"]) {
    const capability = ledger.capabilities.find((entry) => entry.id === id);
    assert.deepEqual(capability.outside_stock_studies, [OUTSIDE_STOCK_STUDY]);
    assert.deepEqual(capability.outside_research_studies, ["outside-query-model-v1"],
      `${id}: the sibling outside-query reference changed`);
  }
  for (const id of ["rail", "water", "start", "buildable", "resources", "trees", "water_risk"]) {
    assert.equal(ledger.capabilities.find((entry) => entry.id === id).outside_stock_studies, undefined);
  }
  assert.deepEqual(validateOutsideStock(ledger), summary);
  assert.equal(study.evidence_only, true);
  assert.equal(study.certificates, "none");
  // The study is not a native study and adds no certificate.
  assert.equal(ledger.native_path_certificates.length, 4);
  assert.equal(ledger.evidence_studies[OUTSIDE_STOCK_STUDY], undefined);
  assert.equal(Object.keys(ledger.evidence_studies).length, 2);
  // The rail and outside-query integrations are untouched.
  assert.deepEqual(ledger.capabilities.find((entry) => entry.id === "rail").rail_research_studies, [
    "rail-query-model-v1", "rail-junction-fit-v1", "rail-stock-holdout-v1",
  ]);
  assert.deepEqual(ledger.outside_research_studies.study, "outside-query-model-v1");
});

test("the projection, its tool and the strict source manifest are hash-bound", () => {
  assert.equal(sha(readFileSync(file(OUTSIDE_STOCK_PROJECTION))), OUTSIDE_STOCK_PROJECTION_SHA);
  assert.equal(sha(readFileSync(file(OUTSIDE_STOCK_SOURCES))), OUTSIDE_STOCK_SOURCES_SHA);
  assert.equal(sha(readFileSync(file(OUTSIDE_STOCK_TOOL))), OUTSIDE_STOCK_TOOL_SHA);
  assert.equal(projection.source_manifest.file, OUTSIDE_STOCK_SOURCES);
  assert.equal(projection.source_manifest.sha256, OUTSIDE_STOCK_SOURCES_SHA);
  assert.deepEqual(Object.keys(projection.studies), [OUTSIDE_STOCK_STUDY]);
  assert.equal(summary.projection_sha256, OUTSIDE_STOCK_PROJECTION_SHA);
  assert.equal(summary.projection_tool_sha256, OUTSIDE_STOCK_TOOL_SHA);
  assert.equal(summary.source_manifest_sha256, OUTSIDE_STOCK_SOURCES_SHA);
  assert.equal(study.source.publication_commit, "d745b14e3e207ee67f91033811958a2934fb38a4");
  assert.equal(study.source.publication_base, "030db86ce470b972b6ef3462a2698744dff40ebb");
  assert.equal(study.source.history.superseded_head, "7b5b4ab4214cd6027844dd7ed7f13cd414ab69e0");
});

test("the publication's whole 142-file scope is pinned; only the compact files are carried", () => {
  const manifest = JSON.parse(readFileSync(file(OUTSIDE_STOCK_SOURCES)));
  const publication = manifest.publications[OUTSIDE_STOCK_STUDY];
  assert.equal(publication.commit, "d745b14e3e207ee67f91033811958a2934fb38a4");
  assert.equal(Object.keys(publication.files).length, 142);
  assert.equal(publication.copied.length, 32);
  assert.equal(publication.linked.length, 110);
  assert.equal(publication.integrity_file, "integrity.json");
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
      assert.equal(existsSync(file(path)), false, `${relative}: bulky member duplicated in the repository`);
    }
  }
  // Carried and linked partition the publication, and nothing extra sits under the prefix.
  assert.deepEqual([...publication.copied, ...publication.linked].sort(), Object.keys(publication.files).sort());
  const carried = readFileSync(file(`${publication.prefix}/integrity.json`));
  const integrity = JSON.parse(carried);
  assert.equal(Object.keys(integrity.files).length, 141);
  assert.equal(publication.files["integrity.json"].sha256, sha(carried));
  for (const [relative, digest] of Object.entries(integrity.files)) {
    assert.equal(digest, publication.files[relative].sha256, `${relative}: integrity hash differs`);
  }
});

test("every linked bulky member is declared by carried bytes, and the four single-declaration members stay explicit", () => {
  const retention = JSON.parse(readFileSync(file(`${study.closure.prefix}/retention.json`)));
  const sourceFix = JSON.parse(readFileSync(file(`${study.closure.prefix}/analysis/source-fix.json`)));
  const integrity = JSON.parse(readFileSync(file(`${study.closure.prefix}/integrity.json`)));
  const raw = study.linked.filter((record) => record.path.includes("/raw/"));
  assert.equal(raw.length, 105);
  for (const record of raw) {
    assert.ok(record.declared_by.includes("integrity.json"), `${record.path}: missing the integrity declaration`);
    assert.ok(record.declared_by.includes("retention.json"), `${record.path}: missing the retention declaration`);
    assert.equal(record.corroborated, true);
  }
  const freeze = study.linked.find((record) => record.path.endsWith("/freeze.json"));
  assert.ok(freeze.declared_by.includes("analysis/source-fix.json"));
  assert.equal(freeze.sha256, sourceFix.frozen_plan_sha256);
  const single = study.linked.filter((record) => !record.corroborated).map((record) => record.path.split("/").pop()).sort();
  assert.deepEqual(single, [
    "features.json.gz", "pre-native-checksum-correction.zip",
    "pre-native-preparation-v0.zip", "pre-native-preparation-v1.zip",
  ]);
  for (const record of study.linked) {
    assert.equal(record.sha256, integrity.files[record.path.slice(study.closure.prefix.length + 1)]);
  }
});

test("the population, exclusions and five fixed selections are preserved", () => {
  assert.deepEqual(study.population.counts, {
    installed: 105, excluded_packages: 13, excluded_hashes: 21, eligible: 92,
    supported: 28, abstaining: 64, decode_errors: 23,
  });
  assert.equal(Object.keys(study.population.excluded_hashes).length, 21);
  const tags = Object.values(study.population.excluded_hashes).map((value) => value.join("+"));
  assert.equal(tags.filter((tag) => tag.includes("PL-1239-selected-including-metadata")).length, 10);
  assert.equal(tags.filter((tag) => tag.includes("PL-1239-controls")).length, 2);
  assert.equal(tags.filter((tag) => tag === "old_geographic_cohort").length, 9);
  assert.equal(study.population.blank_co, "CO.crp");
  assert.equal(study.population.selection.requested_packages, 3);
  assert.equal(study.population.selection.metadata_only_packages, 2);
  assert.deepEqual(
    Object.fromEntries(Object.entries(study.population.selection.cases).map(([key, value]) => [key, value.requests])),
    { "holdout-01": 12, "holdout-02": 18, "holdout-03": 18, "holdout-04": 0, "holdout-05": 0 },
  );
  assert.equal(study.population.packages.length, 105);
  assert.equal(study.stock_exclusion_source.carried_sha256, "20dfb33d863deb4fd13abcbeb952a59e139f93910216771c74fd21c069935a18");
  assert.equal(study.stock_exclusion_source.repository_bytes_equal, true);
});

test("the complete 84-request set is checked, not trusted, and Unknown never becomes a negative", () => {
  assert.equal(study.requests.planned, 84);
  assert.equal(study.requests.observed, 78);
  assert.equal(study.requests.unknown, 6);
  assert.deepEqual(study.requests.by_kind, { holdout: 48, control: 12, intervention: 24 });
  assert.equal(study.requests.records.length, 84);
  assert.equal(new Set(study.requests.records.map((record) => record.id)).size, 84);
  const unknown = study.requests.records.filter((record) => !record.observed);
  assert.equal(unknown.length, 6);
  for (const record of unknown) {
    assert.equal(record.case_id, "stock-1");
    assert.equal(record.kind, "control");
    assert.equal(record.label, "unknown");
    assert.match(record.reason, /unexpected entry protocol/);
  }
});

test("the stock primary and reference tables follow from the saved rows", () => {
  assert.equal(study.stock.rows.length, 48);
  assert.deepEqual(study.stock.primary, {
    road: { tp: 12, fp: 0, tn: 12, fn: 0 },
    ship: { tp: 8, fp: 0, tn: 4, fn: 0 },
    air: { tp: 8, fp: 0, tn: 4, fn: 0 },
  });
  assert.deepEqual(study.stock.reference, {
    road: { tp: 12, fp: 12, tn: 0, fn: 0 },
    ship: { tp: 8, fp: 0, tn: 4, fn: 0 },
    air: { tp: 8, fp: 0, tn: 4, fn: 0 },
  });
  assert.deepEqual(study.stock.total, { tp: 28, fp: 0, tn: 20, fn: 0 });
  const referenceTotal = { tp: 0, fp: 0, tn: 0, fn: 0 };
  for (const mode of ["road", "ship", "air"]) {
    for (const key of Object.keys(referenceTotal)) referenceTotal[key] += study.stock.reference[mode][key];
  }
  // Summing the per-mode reference tables must keep the 12 road false positives
  // and the 8 ship + air true negatives.
  assert.deepEqual(referenceTotal, { tp: 28, fp: 12, tn: 8, fn: 0 });
  assert.deepEqual(study.stock.qualified_modes, { road: false, ship: false, air: false });
  assert.equal(study.stock.modes.road.successes, 12);
  assert.equal(study.stock.modes.road.failures, 12);
  assert.equal(study.stock.modes.ship.discrimination_estimable, true);
  // One-class package-modes stay visible.
  assert.deepEqual(study.stock.one_class.ship.packages, ["holdout-01", "holdout-03"]);
  assert.deepEqual(study.stock.one_class.air.packages, ["holdout-01", "holdout-02"]);
  assert.deepEqual(study.stock.one_class.road.packages, []);
  assert.equal(Object.keys(study.stock.package_mode).length, 9);
  // The published per-package TP/TN counts.
  assert.deepEqual(
    Object.fromEntries(Object.entries(study.stock.package_mode).map(([key, value]) => [key, `${value.TP}/${value.TN}`])),
    {
      "holdout-01/air": "2/0", "holdout-01/road": "4/4", "holdout-01/ship": "2/0",
      "holdout-02/air": "2/0", "holdout-02/road": "4/4", "holdout-02/ship": "4/4",
      "holdout-03/air": "4/4", "holdout-03/road": "4/4", "holdout-03/ship": "2/0",
    },
  );
  assert.equal(study.stock.groups[`${"lane:any_lane:forbidden"}/mode:road`].n, 24);
  assert.equal(Object.keys(study.stock.groups).length, 40);
  assert.deepEqual(study.stock.selection_tags, {
    "road:success:distinct_edge": 12, "road:no_path:distinct_edge": 12,
    "ship:success:distinct_edge": 12, "ship:no_path:distinct_edge": 18,
    "air:success:distinct_edge": 12, "air:no_path:distinct_edge": 18,
  });
  assert.equal(Object.values(study.stock.selection_tags).reduce((total, value) => total + value, 0), 84);
});

test("the strict bridge subset is only the sixteen road requests with exact identity", () => {
  assert.equal(study.bridge.subset.requests, 16);
  assert.equal(study.bridge.subset.not_matched, 32);
  assert.deepEqual(study.bridge.subset.packages, ["holdout-01", "holdout-02"]);
  assert.deepEqual(study.bridge.subset.primary, { tp: 8, fp: 0, tn: 8, fn: 0 });
  assert.deepEqual(study.bridge.subset.reference, { tp: 8, fp: 8, tn: 0, fn: 0 });
  assert.equal(study.stock.snapshot_matched.request_ids.length, 16);
  assert.equal(study.stock.snapshot_matched.request_ids.every((id) => id.startsWith("holdout-0")), true);
  assert.equal(study.stock.snapshot_matched.request_ids.every((id) => id.includes("/road/")), true);
  assert.match(study.bridge.subset.note, /not admitted to this subset/);
});

test("every reference disagreement stays a road false positive with the corrected IDs", () => {
  assert.equal(study.stock.disagreements.length, 12);
  assert.equal(study.stock.disagreements.every((row) => row.mode === "road" && row.rule === "weak_component"), true);
  const ids = study.stock.disagreements.map((row) => row.query_id);
  for (const case_ of ["holdout-01", "holdout-02"]) {
    for (const index of ["001", "006", "007", "008"]) assert.ok(ids.includes(`${case_}/road/${index}`));
  }
  for (const index of ["001", "002", "007", "008"]) assert.ok(ids.includes(`holdout-03/road/${index}`));
  assert.ok(!ids.includes("holdout-03/road/006"), "the rejected holdout-03 ID came back");
  assert.equal(study.stock.disagreements.some((row) => row.rule === "lane:any_lane:forbidden"), false);
});

test("controls keep the first opening Unknown and the second complete, and no mode qualifies", () => {
  assert.equal(study.controls.all_controls_complete, false);
  assert.equal(study.controls.hanami_complete, true);
  assert.equal(study.controls.cases["stock-1"].name, "Asanu");
  assert.equal(study.controls.cases["stock-1"].observed, 0);
  assert.match(study.controls.cases["stock-1"].reason, /MetaBool string "False"/);
  assert.equal(study.controls.cases["stock-2"].name, "Hanami");
  assert.equal(study.controls.cases["stock-2"].observed, 6);
  for (const mode of ["road", "ship", "air"]) assert.equal(study.controls.modes[mode].qualified, false);
  const rows = study.requests.records.filter((record) => record.kind === "control");
  assert.equal(rows.length, 12);
  assert.equal(rows.filter((record) => record.case_id === "stock-1").every((record) => record.label === "unknown"), true);
  assert.equal(rows.filter((record) => record.case_id === "stock-2").every((record) =>
    record.label === (record.request_kind === "positive" ? "success" : "no_path")), true);
});

test("the budget intervention is a separate correlated stratum, never a clean law", () => {
  assert.equal(study.intervention.cohort.old_false_positives, 4);
  assert.equal(study.intervention.cohort.matched_old_successes, 4);
  assert.equal(study.intervention.cohort.not_a_holdout, true);
  assert.equal(study.intervention.cohort.not_a_rejudge, true);
  assert.equal(study.intervention.cohort.clean_single_variable_trials, 7);
  assert.equal(study.intervention.cohort.drifting_groups, 1);
  assert.equal(study.intervention.groups.length, 8);
  for (const group of study.intervention.groups) {
    assert.deepEqual(group.rows.map((row) => row.budget), [100000, 200000, 1000000]);
    assert.equal(group.non_budget_effective_arguments_equal, true);
    assert.equal(group.entry_context_unchanged, true);
    for (const row of group.rows) {
      assert.equal(row.budget, row.effective_max_length);
      if (row.label === "no_path") {
        assert.equal(row.flags, 8);
        assert.equal(row.returned_length, row.budget);
      }
    }
    if (group.old_label === "failure") assert.deepEqual(group.labels, ["no_path", "no_path", "no_path"]);
  }
  const measured = study.intervention.groups.filter((group) => group.sensitive);
  assert.equal(measured.length, 1);
  assert.equal(measured[0].old_query_id, "hong-kong/native-v2-5/road/167");
  assert.deepEqual(measured[0].labels, ["no_path", "success", "success"]);
  const drifted = study.intervention.groups.filter((group) => !group.all_mode_graph_constant);
  assert.equal(drifted.length, 1);
  assert.equal(drifted[0].old_query_id, "pittsburgh/native-v2-6/road/093");
  assert.equal(drifted[0].rows.find((row) => row.budget === 1000000).snapshot_matched, false);
  assert.equal(study.intervention.error_mechanisms, "unknown");
  assert.match(study.intervention.units, /not proof of native exhaustion/);
});

test("bridge and opening drift keep every retained difference and never a clean claim", () => {
  assert.deepEqual(study.bridge.height_drift, {
    "holdout-01": 33.029134, "holdout-02": 161.935462, "holdout-03": 8.026451,
  });
  assert.equal(study.bridge.horizontal_unchanged, true);
  assert.equal(study.bridge.lane_connectivity_invert_outside_mismatches, 0);
  assert.equal(study.bridge.roslyn_prefabs.length, 4);
  assert.deepEqual(study.bridge.roslyn_prefabs.map((change) => change.segment), [428, 8772, 24652, 35418]);
  assert.equal(study.bridge.packages["holdout-01"].modes.road.exact_equal, true);
  assert.equal(study.bridge.packages["holdout-03"].modes.road.mismatches, 4);
  assert.equal(study.bridge.packages["holdout-04"].missing.length, 11);
  assert.equal(study.bridge.packages["holdout-05"].missing.length, 13);
  assert.deepEqual(study.drift.opening_changes["holdout-03"].air.changed_segments, [17396, 20340, 21466, 26056, 29446, 32716, 35098]);
  assert.deepEqual(study.drift.opening_changes["holdout-03"].ship.changed_segments, [9993, 31169]);
  assert.deepEqual(study.drift.opening_changes["budget-01"].air.changed_segments, [5973, 5974]);
  assert.deepEqual(study.drift.pre_post_query_changes, ["holdout-03/air/002", "holdout-03/air/007", "holdout-03/road/006"]);
  assert.equal(study.drift.reported_opening_fingerprint_mismatches, 17);
  assert.equal(study.drift.pre_query_opening_fingerprint_mismatches, 18);
  assert.equal(study.drift.openings["holdout-03"].opening_post_graph_equal, false);
  assert.equal(study.drift.openings["budget-01"].opening_post_graph_equal, false);
  assert.equal(study.drift.openings["stock-1"].completed, false);
});

test("the runtime, its 25 phase inventories and the 45 historical identities are preserved", () => {
  assert.equal(study.runtime.openings, 9);
  assert.equal(study.runtime.phase_inventories, 25);
  assert.equal(study.runtime.process_identities, 45);
  assert.equal(study.runtime.observation_windows.length, 9);
  assert.equal(Object.keys(study.runtime.installed_crp_receipts).length, 9);
  assert.equal(study.runtime.launch_caption_used_as_evidence, false);
  assert.match(study.runtime.cleanup_note, /not a description of blade's current/);
  assert.deepEqual(study.runtime.process_kinds["stock-1"], ["auditor", "collector", "driver", "game", "session_gpu_monitor"]);
  assert.equal(study.runtime.build.dll_sha256, "7cfb994191efd7a7b21eeabee283100e8b45627836bf65b621e04b1a134f7063");
  assert.equal(study.runtime.phase_inventory_names["stock-1"].length, 1);
  for (const window of study.runtime.observation_windows) {
    assert.match(window.started_at, /^2026-11-23T/);
    assert.match(window.finished_at, /^2026-11-23T/);
  }
  // The observation window is not the freeze or publication time.
  assert.equal(study.runtime.observation_windows.some((window) => window.started_at === "2026-11-23T12:25:23.481463+00:00"), false);
});

test("the schema repair is evidenced, not a hidden re-freeze", () => {
  assert.equal(study.schema_repair.retained_failure.sha256, "2d11834d1afdde1f799fb64819eb0658e44cc1109103f216bb3bb79310e7c962");
  assert.equal(study.schema_repair.repair.decompressed_sha256, "c915293ba0d70a99745b21dd763783bf8d34961fc32b8a3681ea5b7c0ddb8a80");
  assert.deepEqual(study.schema_repair.repair.transport_required, { ok: true });
  assert.equal(study.schema_repair.retained_selection.queries, 48);
  assert.deepEqual(study.schema_repair.retained_selection.selected.map((row) => row[0]),
    ["holdout-01", "holdout-02", "holdout-03", "holdout-04", "holdout-05"]);
  assert.deepEqual(study.stock.selection_strata.map((row) => row.available), [27, 27, 15, 4, 27, 13]);
  assert.match(study.schema_repair.scope, /not a hidden re-freeze/);
});

test("the generated page renders the study once, with every table and served evidence", () => {
  const html = ledgerPage(ledger, "test-source");
  assert.match(html, /id="outside-stock-study"/);
  assert.equal((html.match(/data-outside-stock>/g) ?? []).length, 1);
  assert.equal((html.match(/Outside-stock validation and budget limits/g) ?? []).length, 4);
  const section = html.slice(html.indexOf("data-outside-stock>"), html.indexOf("</article>", html.indexOf("data-outside-stock>")));
  assert.match(section, /All three modes remain UNQUALIFIED/);
  assert.match(section, /descriptive intent-to-test/);
  assert.match(section, /TP 28 · FP 0 · TN 20 · FN 0/);
  assert.match(section, /Only these 16 road requests have exact export\/native field identity/);
  assert.match(section, /the other 32 requests fail exact bridge identity/i);
  assert.match(section, /One-class package-modes/);
  assert.match(section, /MetaBool string "False"/);
  assert.match(section, /all four error mechanisms remain Unknown|remain <strong>Unknown<\/strong>/);
  assert.match(section, /not a clean single-variable trial/);
  assert.match(section, /not proof of native exhaustion/);
  assert.match(section, /says nothing about blade's current slot or process state/);
  assert.match(section, /data-outside-stock-package-mode/);
  assert.match(section, /data-outside-stock-population/);
  assert.match(section, /data-outside-stock-intervention/);
  assert.match(section, /data-outside-stock-windows/);
  assert.match(section, /data-outside-stock-controls/);
  // The modes table's total row must report the reference rule's own totals,
  // not the primary total with TN zeroed.
  const modes = section.slice(section.indexOf("data-outside-stock-modes"), section.indexOf("</table>", section.indexOf("data-outside-stock-modes")));
  const totalRow = modes.slice(modes.lastIndexOf("<tr>"));
  assert.match(totalRow, /TP 28 · FP 12 · TN 8 · FN 0/);
  assert.doesNotMatch(totalRow, /TP 28 · FP 0 · TN 0 · FN 0/);
  for (const [attribute, expected] of [
    ["population", 5], ["packages", 5], ["modes", 4], ["package-mode", 9], ["strata", 6],
    ["tags", 6], ["subset", 1], ["bridge", 11], ["drift", 2], ["controls", 12],
    ["intervention", 8], ["windows", 9], ["requests", 84], ["groups", 40], ["disagreements", 12],
  ]) {
    const start = section.indexOf(`data-outside-stock-${attribute}`);
    assert.ok(start > 0, `missing the ${attribute} table`);
    const body = section.slice(start, section.indexOf("</table>", start));
    assert.equal((body.match(/<tr>/g) ?? []).length - 1, expected, `${attribute} table row count`);
  }
  for (const record of study.files) assert.ok(section.includes(record.path), `${record.path}: carried evidence is not linked`);
  for (const record of study.linked) {
    assert.ok(section.includes(`https://github.com/frontierkodiak/region-to-skylines/blob/030db86ce470b972b6ef3462a2698744dff40ebb/`.replace("030db86ce470b972b6ef3462a2698744dff40ebb", "d745b14e3e207ee67f91033811958a2934fb38a4") + record.path),
      `${record.path}: linked source is not an immutable blob link`);
  }
  // The capability references are mode-scoped, not a second copy of the study.
  const road = html.slice(html.indexOf('<article id="road">'), html.indexOf('<article id="rail">'));
  assert.match(road, /Road has 24 new stock requests: primary TP 12 · FP 0 · TN 12 · FN 0/);
  assert.match(road, /All three modes remain unqualified/);
  assert.doesNotMatch(section, /accuracy: \d/);
  assert.doesNotMatch(section, /promised/i);
});

test("every served file exists and no research code is imported or executed", () => {
  const files = outsideStockFiles();
  assert.equal(files.length, 32 + 2);
  for (const path of files) assert.ok(existsSync(file(path)), `${path}: missing served evidence`);
  assert.ok(files.includes(OUTSIDE_STOCK_PROJECTION));
  assert.ok(files.includes(OUTSIDE_STOCK_SOURCES));
  const module = readFileSync(file("outside-stock.mjs"), "utf8");
  for (const forbidden of ["child_process", "execFile", "spawn(", "eval(", "python"]) {
    assert.ok(!module.includes(forbidden), `the renderer must not execute research code: ${forbidden}`);
  }
  for (const record of study.linked) assert.ok(!files.includes(record.path));
  const html = outsideStockReference("ship", { study }, escape);
  assert.match(html, /Ship has 12 new stock requests/);
  assert.match(html, /href="#outside-stock-study"/);
  const page = outsideStockPage({ study }, escape);
  assert.equal((page.match(/data-outside-stock>/g) ?? []).length, 1);
});

test("regeneration is deterministic twice and preserves every sibling study byte", () => {
  const before = readFileSync(file("capabilities.json"));
  const projectionBefore = readFileSync(file(OUTSIDE_STOCK_PROJECTION));
  execFileSync("python3", ["tools/map-factory/integrate_outside_stock.py"], { cwd: root, stdio: "pipe" });
  assert.deepEqual(readFileSync(file("capabilities.json")), before, "regeneration rewrote unowned ledger bytes");
  assert.deepEqual(readFileSync(file(OUTSIDE_STOCK_PROJECTION)), projectionBefore);
  execFileSync("python3", ["tools/map-factory/integrate_outside_stock.py"], { cwd: root, stdio: "pipe" });
  assert.deepEqual(readFileSync(file("capabilities.json")), before, "the second run was not idempotent");
  // All four retained certificates are byte-identical after regeneration.
  const after = JSON.parse(readFileSync(file("capabilities.json")));
  assert.deepEqual(after.native_path_certificates, ledger.native_path_certificates);
  assert.deepEqual(after.outside_research_studies, ledger.outside_research_studies);
  assert.deepEqual(after.rail_studies, ledger.rail_studies);
  assert.deepEqual(after.rail_research_studies, ledger.rail_research_studies);
  assert.deepEqual(after.witness_studies, ledger.witness_studies);
  assert.deepEqual(after.evidence_studies, ledger.evidence_studies);
});

test("exact parent bytes outside every producer's owned fragments are unchanged", () => {
  let text = readFileSync(file("capabilities.json")).toString();
  for (const id of ["start", "water"]) {
    const marker = text.indexOf('"id": "' + id + '"'), begin = text.lastIndexOf("    {", marker);
    const end = text.indexOf("\n    }", marker) + "\n    }".length;
    text = text.slice(0, begin) + text.slice(end);
  }
  text = text.replace('      "rail_study": "directed-rail-v3",\n', "");
  text = text.replace(',\n      "rail_research_studies": [\n        "rail-query-model-v1",\n        "rail-junction-fit-v1",\n        "rail-stock-holdout-v1"\n      ]', "");
  text = text.replaceAll(',\n      "outside_research_studies": [\n        "outside-query-model-v1"\n      ]', "");
  text = text.replaceAll(',\n      "outside_stock_studies": [\n        "outside-stock-budget-v1"\n      ]', "");
  text = text.slice(0, text.indexOf('\n  "witness_studies":') - 1) + "\n}\n";
  assert.equal(sha(Buffer.from(text)), "4f459361a10779d3a0a5ab4886da02307e65ffbf4ad9f5a73a4dea4d4b0e4eff",
    "exact parent bytes outside owned fragments");
});

test("ledger mutations to the study binding are rejected", () => {
  for (const mutate of [
    (changed) => { changed.outside_stock_studies.planned_requests = 83; },
    (changed) => { changed.outside_stock_studies.stock_primary.fp = 1; },
    (changed) => { changed.outside_stock_studies.qualified_modes.road = true; },
    (changed) => { changed.outside_stock_studies.controls.all_controls_complete = true; },
    (changed) => { changed.outside_stock_studies.intervention.error_mechanisms = "exhaustion"; },
    (changed) => { changed.outside_stock_studies.bridge_subset_requests = 17; },
    (changed) => { changed.outside_stock_studies.certificates = "sampled"; },
    (changed) => { changed.outside_stock_studies.projection_sha256 = "0".repeat(64); },
    (changed) => { delete changed.outside_stock_studies; },
    (changed) => { changed.capabilities.find((entry) => entry.id === "road").outside_stock_studies = []; },
    (changed) => { delete changed.capabilities.find((entry) => entry.id === "ship").outside_stock_studies; },
    (changed) => { changed.capabilities.find((entry) => entry.id === "rail").outside_stock_studies = [OUTSIDE_STOCK_STUDY]; },
    (changed) => { changed.native_path_certificates.push({ capability: "road", study: OUTSIDE_STOCK_STUDY }); },
    (changed) => { changed.evidence_studies[OUTSIDE_STOCK_STUDY] = { source_commit: "0".repeat(40) }; },
  ]) {
    const changed = structuredClone(ledger);
    mutate(changed);
    assert.throws(() => validateLedger(changed));
  }
});

test("mutated source, raw, freeze, request, context, control, cleanup and drift facts fail closed", () => {
  for (const mutate of [
    (changed) => { changed.population.counts.installed = 104; },
    (changed) => { changed.population.counts.decode_errors = 0; },
    (changed) => { delete changed.population.excluded_hashes[Object.keys(changed.population.excluded_hashes)[0]]; },
    (changed) => { changed.requests.planned = 83; },
    (changed) => { changed.requests.records.pop(); },
    (changed) => { changed.requests.records.find((record) => !record.observed).observed = true; },
    (changed) => { changed.requests.records.find((record) => record.kind === "control" && record.case_id === "stock-2" && record.request_kind === "positive").label = "no_path"; },
    (changed) => { changed.stock.rows[0].label = "unknown"; },
    (changed) => { changed.stock.rows[0].snapshot_matched = true; },
    (changed) => { changed.stock.rows.find((row) => row.case_id === "holdout-02" && row.mode === "ship").snapshot_matched = true; },
    (changed) => { changed.stock.package_mode["holdout-01/ship"].absent_class_power = false; },
    (changed) => { changed.stock.one_class.ship.packages = []; },
    (changed) => { changed.stock.selection_tags["road:success:distinct_edge"] = 11; },
    (changed) => { changed.bridge.height_drift["holdout-02"] = 1; },
    (changed) => { changed.bridge.roslyn_prefabs.pop(); },
    (changed) => { changed.bridge.packages["holdout-03"].modes.air.horizontal_equal = false; },
    (changed) => { changed.drift.pre_post_query_changes.pop(); },
    (changed) => { changed.drift.reported_opening_fingerprint_mismatches = 18; },
    (changed) => { changed.drift.opening_changes["holdout-03"].air.changed_segments.pop(); },
    (changed) => { changed.controls.cases["stock-1"].observed = 6; },
    (changed) => { changed.controls.modes.ship.qualified = true; },
    (changed) => { changed.intervention.groups[0].rows[1].budget = 300000; },
    (changed) => { changed.intervention.groups[0].rows[0].flags = 4; },
    (changed) => { changed.intervention.groups[0].non_budget_effective_arguments_equal = false; },
    (changed) => { changed.intervention.groups.find((group) => group.old_label === "failure").labels = ["success", "success", "success"]; },
    (changed) => { changed.intervention.measured_response.labels = ["success", "success", "success"]; },
    (changed) => { changed.intervention.drift.per_query_road_snapshot_retained = true; },
    (changed) => { changed.runtime.process_identities = 44; },
    (changed) => { changed.runtime.phase_inventories = 24; },
    (changed) => { changed.runtime.openings = 8; },
    (changed) => { changed.runtime.launch_caption_used_as_evidence = true; },
    (changed) => { changed.runtime.cleanup_note = "nothing is running"; },
    (changed) => { changed.schema_repair.retained_failure.sha256 = "0".repeat(64); },
    (changed) => { changed.schema_repair.repair.transport_required = {}; },
    (changed) => { changed.protocol.mode_vehicle.road = "Bus"; },
    (changed) => { changed.protocol.seed = 858; },
    (changed) => { changed.protocol.budgets = [100000, 200000]; },
    (changed) => { changed.closure.publication_files = 141; },
    (changed) => { changed.linked.pop(); },
    (changed) => { changed.linked.find((record) => record.corroborated).corroborated = false; },
    (changed) => { changed.source.review.parent_acceptance = "0".repeat(36); },
    (changed) => { changed.source.history.superseded_head = "0".repeat(40); },
    (changed) => { changed.limits = "Everything is qualified."; },
  ]) {
    const changed = structuredClone(projection);
    mutate(changed.studies[OUTSIDE_STOCK_STUDY]);
    const target = file(OUTSIDE_STOCK_PROJECTION);
    const before = readFileSync(target);
    try {
      writeFileSync(target, JSON.stringify(changed, null, 1) + "\n");
      assert.throws(() => outsideStock(), "a changed derived fact was accepted");
    } finally {
      writeFileSync(target, before);
    }
  }
});

test("file mutations to the projection, manifest, tool or carried bytes are rejected", () => {
  const restore = (path) => {
    const target = file(path), bytes = readFileSync(target);
    return () => writeFileSync(target, bytes);
  };
  const carried = study.files.find((record) => record.path.endsWith("/RESULTS.md")).path;
  for (const [path, mutate] of [
    [OUTSIDE_STOCK_PROJECTION, (bytes) => Buffer.concat([bytes, Buffer.from(" ")])],
    [OUTSIDE_STOCK_SOURCES, (bytes) => Buffer.concat([bytes, Buffer.from(" ")])],
    [OUTSIDE_STOCK_TOOL, (bytes) => Buffer.concat([bytes, Buffer.from("\n")])],
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

test("re-pinning a changed carried file or a linked member in the manifest cannot defeat the canonical pin", () => {
  const manifestPath = OUTSIDE_STOCK_SOURCES;
  const carriedPath = `${study.closure.prefix}/RESULTS.md`;
  const manifestBytes = readFileSync(file(manifestPath));
  const carriedBytes = readFileSync(file(carriedPath));
  const manifest = JSON.parse(manifestBytes);
  const changed = Buffer.concat([carriedBytes, Buffer.from(" ")]);
  manifest.publications[OUTSIDE_STOCK_STUDY].files["RESULTS.md"] = {
    ...manifest.publications[OUTSIDE_STOCK_STUDY].files["RESULTS.md"],
    sha256: sha(changed),
    bytes: changed.length,
  };
  // Also re-pin a raw member, as if the publication's own integrity record had changed.
  const rawName = "raw/budget-01/game.log.gz";
  manifest.publications[OUTSIDE_STOCK_STUDY].files[rawName] = {
    ...manifest.publications[OUTSIDE_STOCK_STUDY].files[rawName],
    sha256: "0".repeat(64),
  };
  try {
    writeFileSync(file(carriedPath), changed);
    writeFileSync(file(manifestPath), JSON.stringify(manifest, null, 1) + "\n");
    assert.throws(() => validateLedger(JSON.parse(readFileSync(file("capabilities.json")))));
    assert.throws(() => outsideStock());
  } finally {
    writeFileSync(file(carriedPath), carriedBytes);
    writeFileSync(file(manifestPath), manifestBytes);
  }
  validateOutsideStock(JSON.parse(readFileSync(file("capabilities.json"))));
});

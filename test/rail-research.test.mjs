import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { validateLedger, ledgerPage } from "../capability-ledger.mjs";
import {
  RAIL_RESEARCH_PROJECTION, RAIL_RESEARCH_PROJECTION_SHA, RAIL_RESEARCH_SOURCES,
  RAIL_RESEARCH_SOURCES_SHA, RAIL_RESEARCH_STUDIES, RAIL_RESEARCH_TOOL, RAIL_RESEARCH_TOOL_SHA,
  railResearch, railResearchFiles, railResearchPage, validateRailResearch,
} from "../rail-research.mjs";
import { railStudyFiles } from "../rail-study.mjs";

const root = new URL("../", import.meta.url);
const file = (path) => new URL(path, root);
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const ledger = JSON.parse(readFileSync(file("capabilities.json")));
const { projection, studies, summary } = railResearch();

test("the three research publications are separate typed studies referenced from Rail", () => {
  validateLedger(ledger);
  const rail = ledger.capabilities.find((capability) => capability.id === "rail");
  assert.deepEqual(rail.rail_research_studies, RAIL_RESEARCH_STUDIES);
  assert.deepEqual(Object.keys(ledger.rail_research_studies), RAIL_RESEARCH_STUDIES);
  assert.deepEqual(validateRailResearch(ledger), summary);
  assert.deepEqual(Object.values(summary).map((study) => study.kind), [
    "query_scoped_rail_reachability_study",
    "export_tangent_junction_study",
    "frozen_stock_rule_holdout_study",
  ]);
  for (const study of Object.values(studies)) {
    assert.equal(study.evidence_only, true);
    assert.equal(study.certificates, "none");
  }
  // The older directed-rail study stays exactly where it was: one key, unchanged.
  assert.deepEqual(Object.keys(ledger.rail_studies), ["directed-rail-v3"]);
  assert.equal(ledger.native_path_certificates.filter((certificate) => certificate.capability === "rail").length, 0);
  assert.equal(ledger.native_path_certificates.length, 4);
});

test("the projection, its tool and the strict source manifest are hash-bound", () => {
  assert.equal(sha(readFileSync(file(RAIL_RESEARCH_PROJECTION))), RAIL_RESEARCH_PROJECTION_SHA);
  assert.equal(sha(readFileSync(file(RAIL_RESEARCH_SOURCES))), RAIL_RESEARCH_SOURCES_SHA);
  assert.equal(sha(readFileSync(file(RAIL_RESEARCH_TOOL))), RAIL_RESEARCH_TOOL_SHA);
  assert.equal(projection.source_manifest[RAIL_RESEARCH_STUDIES[0]].sha256, RAIL_RESEARCH_SOURCES_SHA);
  assert.deepEqual(projection.source_manifest[RAIL_RESEARCH_STUDIES[2]].copied_files, 16);
});

test("every publication's file scope is complete and every carried byte matches it", () => {
  const expected = {
    "rail-query-model-v1": { total: 29, copied: 19, linked: 10 },
    "rail-junction-fit-v1": { total: 18, copied: 10, linked: 8 },
    "rail-stock-holdout-v1": { total: 159, copied: 16, linked: 143 },
  };
  const manifest = JSON.parse(readFileSync(file(RAIL_RESEARCH_SOURCES)));
  for (const id of RAIL_RESEARCH_STUDIES) {
    const study = studies[id];
    const publication = manifest.publications[id];
    assert.equal(study.closure.publication_files, expected[id].total);
    assert.equal(study.closure.copied_files, expected[id].copied);
    assert.equal(study.closure.linked_files, expected[id].linked);
    assert.equal(Object.keys(publication.files).length, expected[id].total);
    assert.equal(publication.copied.length, expected[id].copied);
    assert.equal(publication.linked.length, expected[id].linked);
    assert.deepEqual([...publication.copied].sort(), study.files.map((record) => record.path.slice(study.closure.prefix.length + 1)).sort());
    const carried = new Set(study.files.map((record) => record.path));
    for (const [relative, record] of Object.entries(publication.files)) {
      assert.ok(/^[a-f0-9]{64}$/.test(record.sha256), `${id}: ${relative} lacks a hash`);
      assert.ok(/^[a-f0-9]{40}$/.test(record.git_blob), `${id}: ${relative} lacks a blob id`);
      assert.ok(record.bytes > 0, `${id}: ${relative} has no size`);
      if (publication.copied.includes(relative)) {
        const path = `${study.closure.prefix}/${relative}`;
        assert.ok(carried.has(path), `${id}: ${relative} is not carried evidence`);
        assert.equal(sha(readFileSync(file(path))), record.sha256, `${id}: carried bytes changed: ${relative}`);
      } else {
        assert.ok(!existsSync(file(`${study.closure.prefix}/${relative}`)), `${id}: linked file duplicated in the repository`);
      }
    }
  }
});

test("the query study keeps the fitted, primary, control and cohort results separate", () => {
  const study = studies["rail-query-model-v1"];
  const fitted = study.rules.all[study.rules.fitted].counts;
  assert.deepEqual(fitted, { tp: 26, fp: 4, tn: 245, fn: 1, abstain: 0, scored: 276 });
  const primary = study.rules.all[study.rules.primary].counts;
  assert.deepEqual(primary, { tp: 11, fp: 198, tn: 51, fn: 16, abstain: 0, scored: 276 });
  assert.deepEqual(study.rules.split_totals[study.rules.fitted].stock_controls, { tp: 16, fp: 0, tn: 16, fn: 0 });
  assert.deepEqual(study.rules.split_totals[study.rules.fitted].cohort, { tp: 10, fp: 4, tn: 229, fn: 1 });
  assert.equal(Object.keys(study.rules.all).length, 28);
  assert.equal(study.rows.length, 276);
  assert.deepEqual(study.selection.labels, { exact_path_success: 27, selected_query_failure: 249 });
  assert.equal(study.counterexamples.length, 5);
  assert.ok(study.counterexamples.every((row) => row.opening === "pittsburgh"));
  assert.deepEqual(study.counterexamples.map((row) => row.kind).sort(), ["false_negative", "false_positive", "false_positive", "false_positive", "false_positive"]);
  assert.equal(study.selection.unqueried.pittsburgh, 112);
  assert.equal(study.runtime.export_bridge.status, "bridge_established");
  assert.equal(study.runtime.export_bridge.totals["segment_present:checked"], 6774);
  assert.equal(study.runtime.export_bridge.prediction_agreement.identical, 244);
});

test("the tangent study reports the perfect fit and the grouped counterweight", () => {
  const study = studies["rail-junction-fit-v1"];
  const tangent = study.rules.all[study.rules.fitted].all.counts;
  assert.deepEqual(tangent, { tp: 27, fp: 0, tn: 249, fn: 0, abstain: 0, unknown: 0 });
  const reference = study.rules.all[study.rules.reference].all.counts;
  assert.deepEqual(reference, { tp: 26, fp: 4, tn: 245, fn: 1, abstain: 0, unknown: 0 });
  assert.deepEqual(study.rules.all[study.rules.chord_reimplementation].all.counts, reference);
  assert.deepEqual(study.rules.pooled_out_of_fold.cohort.selected.counts, { abstain: 0, fn: 1, fp: 4, tn: 229, tp: 10, unknown: 0 });
  assert.deepEqual(study.rules.pooled_out_of_fold.cohort.correspondence.counts, { abstain: 0, fn: 0, fp: 0, tn: 233, tp: 11, unknown: 0 });
  assert.equal(study.rules.paired.all.right_only_correct, 5);
  assert.equal(study.rules.paired.all.both_correct, 271);
  assert.equal(study.counterexamples[study.rules.reference].length, 5);
  assert.equal(study.counterexamples[study.rules.fitted].length, 0);
  assert.equal(study.runtime.export_bridge.tangents.native_attested, false);
  assert.equal(study.runtime.export_bridge.totals.tangent_train_segments, 7216);
  const heldOut = study.selection.folds.find((fold) => fold.held_out.includes("pittsburgh"));
  assert.equal(heldOut.selected, study.rules.chord_reimplementation);
});

test("the stock holdout keeps both rules identical, one failing package and the unsupported cases", () => {
  const study = studies["rail-stock-holdout-v1"];
  assert.equal(study.freeze.sha256, "20dfb33d863deb4fd13abcbeb952a59e139f93910216771c74fd21c069935a18");
  assert.equal(study.freeze.frozen_at, "2026-11-21T21:51:01.430026+00:00");
  assert.equal(study.freeze.discordant_predictions, 0);
  assert.equal(study.rows.length, 48);
  assert.equal(study.selection.supported_packages, 6);
  assert.equal(study.selection.unsupported_packages, 4);
  for (const [name, table] of Object.entries(study.rules.tables)) {
    for (const rule of study.rules.rules) {
      const counts = table.all[rule].counts;
      assert.deepEqual(counts, { tp: 40, fp: 0, tn: 8, fn: 0, abstain: 0, unknown: 0, requests: 48 }, `${name}: ${rule}`);
    }
  }
  for (const row of study.rows) {
    assert.equal(row.predicted["tangent:continuation:any_lane"], row.predicted["chord:continuation:any_lane"]);
    assert.equal(row.snapshot_matched, true);
  }
  const failures = study.rows.filter((row) => row.observed === "no_path");
  assert.equal(failures.length, 8);
  assert.deepEqual([...new Set(failures.map((row) => row.opening))], ["holdout-02"]);
  assert.equal(study.selection.strata.pair_difference.selected, 2);
  assert.equal(study.selection.strata.no_pair_difference.selected, 4);
  assert.equal(study.selection.strata.unsupported_or_no_pair.selected, 4);
  assert.equal(study.runtime.raw_retention.files, 136);
  assert.equal(study.runtime.field_audit.supported_train_segments, 1277);
  assert.match(study.limits, /The three post-load errors/);
  assert.doesNotMatch(study.limits, /four post-load errors/);
  assert.deepEqual(study.runtime.field_audit.unsupported.map((entry) => entry.opening_mismatches).sort((a, b) => a - b), [6, 8, 14, 44]);
  assert.equal(study.runtime.native_verification.openings.length, 12);
  assert.deepEqual(study.controls.map((control) => [control.slug, control.boundary_successes, control.boundary_requests]),
    [["stock-1", 8, 8], ["stock-2", 8, 24]]);
  assert.ok(study.controls.every((control) => control.invalid_pair_rejected));
  assert.equal(study.runtime.metadata_reader.public_fields_only, true);
});

test("the source chain is pinned, not inferred from display names", () => {
  const query = studies["rail-query-model-v1"].source;
  const junction = studies["rail-junction-fit-v1"].source;
  const stock = studies["rail-stock-holdout-v1"].source;
  assert.equal(junction.publication_base, query.publication_commit);
  assert.equal(stock.publication_base, junction.publication_commit);
  assert.equal(query.internal_merge, "d008778fd44cf448b2078738468267e8a7863af0");
  assert.equal(junction.internal_merge, "fef279efb339d26d3cc86eddcf588f3f7611e290");
  assert.equal(stock.internal_merge, null);
  assert.equal(stock.pull_request, 84);
  assert.equal(studies["rail-stock-holdout-v1"].freeze.query_source, query.publication_commit);
  assert.equal(studies["rail-stock-holdout-v1"].freeze.native_source, query.publication_base);
});

test("the generated page makes the three studies readable without pooling them", () => {
  const html = ledgerPage(ledger, "test-source");
  assert.match(html, /id="rail-research-studies"/);
  assert.match(html, /three separate typed studies/);
  assert.match(html, /not pooled with the directed native study/);
  const query = html.slice(html.indexOf('data-rail-research="rail-query-model-v1"'), html.indexOf('data-rail-research="rail-junction-fit-v1"'));
  const junction = html.slice(html.indexOf('data-rail-research="rail-junction-fit-v1"'), html.indexOf('data-rail-research="rail-stock-holdout-v1"'));
  const stock = html.slice(html.indexOf('data-rail-research="rail-stock-holdout-v1"'), html.indexOf('</section>', html.indexOf('data-rail-research="rail-stock-holdout-v1"')));
  assert.match(query, /TP 26 · FP 4 · TN 245 · FN 1/);
  assert.match(query, /pre-registered primary/);
  assert.match(query, /pittsburgh:54/);
  assert.match(junction, /Tangent continuation \(fitted\)/);
  assert.match(junction, /10 · FP|TP 10/);
  assert.match(junction, /5 corrected, 0 broken, 271 both right/);
  assert.match(stock, /40 · FP 0 · TN 8/);
  assert.match(stock, /does not prefer tangent over chord/);
  assert.match(stock, /holdout-02/);
  assert.match(stock, /frozen 2026-11-21T21:51:01\.430026\+00:00/);
  for (const id of RAIL_RESEARCH_STUDIES) {
    const study = studies[id];
    const section = html.slice(html.indexOf(`data-rail-research="${id}"`));
    for (const record of study.files) {
      assert.ok(section.includes(record.path), `${id}: carried evidence is not linked`);
    }
  }
  const rows = [...html.matchAll(/data-rail-research-rows/g)];
  assert.equal(rows.length, 3, "each study must render its complete selected rows");
});

test("every served file exists and no research code is imported or executed", () => {
  const files = railResearchFiles(Object.values(studies));
  assert.ok(files.length >= 45 + 2);
  for (const path of files) assert.ok(existsSync(file(path)), `${path}: missing served evidence`);
  assert.ok(files.includes(RAIL_RESEARCH_PROJECTION));
  assert.ok(files.includes(RAIL_RESEARCH_SOURCES));
  const module = readFileSync(file("rail-research.mjs"), "utf8");
  for (const forbidden of ["child_process", "execFile", "spawn(", "eval(", "python"]) {
    assert.ok(!module.includes(forbidden), `the renderer must not execute research code: ${forbidden}`);
  }
  // The directed native study's own served-file rule is unchanged.
  assert.ok(!railStudyFiles().some((path) => path.endsWith(".py") && !path.includes("rail-native-sources")));
});

test("ledger mutations to the research binding are rejected", () => {
  for (const mutate of [
    (changed) => { changed.rail_research_studies["rail-query-model-v1"].selected_queries = 277; },
    (changed) => { changed.rail_research_studies["rail-junction-fit-v1"].publication_files = 17; },
    (changed) => { changed.rail_research_studies["rail-stock-holdout-v1"].freeze.discordant_predictions = 1; },
    (changed) => { changed.rail_research_studies["rail-stock-holdout-v1"].projection_sha256 = "0".repeat(64); },
    (changed) => { changed.rail_research_studies["rail-query-model-v1"].certificates = "sampled"; },
    (changed) => { delete changed.rail_research_studies["rail-junction-fit-v1"]; },
    (changed) => { changed.capabilities.find((capability) => capability.id === "rail").rail_research_studies.pop(); },
    (changed) => { delete changed.capabilities.find((capability) => capability.id === "rail").rail_research_studies; },
    (changed) => { changed.rail_research_studies["rail-stock-holdout-v1"].internal_merge = "fef279ef"; },
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
  const carried = studies["rail-stock-holdout-v1"].files[0].path;
  for (const [path, mutate] of [
    [RAIL_RESEARCH_PROJECTION, (bytes) => Buffer.concat([bytes, Buffer.from(" ")])],
    [RAIL_RESEARCH_SOURCES, (bytes) => Buffer.concat([bytes, Buffer.from(" ")])],
    [RAIL_RESEARCH_TOOL, (bytes) => Buffer.concat([bytes, Buffer.from("\n")])],
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

test("the renderer is a pure function of the validated projection", () => {
  const html = railResearchPage({ studies }, (value) => String(value).replace(/[&<>"']/g, ""));
  assert.match(html, /data-rail-research-studies/);
  assert.equal((html.match(/data-rail-research-rows/g) ?? []).length, 3);
  assert.match(html, /Frozen stock rail holdout/);
});

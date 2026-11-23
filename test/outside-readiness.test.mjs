import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { validateLedger, ledgerPage } from "../capability-ledger.mjs";
import {
  OUTSIDE_READINESS_FROZEN, OUTSIDE_READINESS_PREFIX, OUTSIDE_READINESS_PROJECTION,
  OUTSIDE_READINESS_PROJECTION_SHA, OUTSIDE_READINESS_PUBLICATION,
  OUTSIDE_READINESS_SOURCES, OUTSIDE_READINESS_SOURCES_SHA, OUTSIDE_READINESS_STUDY,
  OUTSIDE_READINESS_TOOL, OUTSIDE_READINESS_TOOL_SHA, outsideReadiness,
  outsideReadinessFiles, outsideReadinessPage, outsideReadinessReference,
  validateOutsideReadiness,
} from "../outside-readiness.mjs";

const root = new URL("../", import.meta.url);
const file = (path) => new URL(path, root);
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const readUtf8 = (path) => readFileSync(file(path));
const parse = (path) => JSON.parse(readUtf8(path));
const ledger = parse("capabilities.json");
const { study, summary } = outsideReadiness();
const escape = (value) => String(value).replace(/[&<>"']/g, (character) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);

/** A loader that can tamper with one path while leaving every other byte intact. */
const loader = (tamper) => (path) => {
  const raw = readUtf8(path);
  const changed = tamper(path, raw);
  return changed === undefined ? raw : changed;
};

test("one accepted outside-readiness study is referenced from Road, Ship and Air", () => {
  validateLedger(ledger);
  for (const id of ["road", "ship", "air"]) {
    const capability = ledger.capabilities.find((entry) => entry.id === id);
    assert.deepEqual(capability.outside_readiness_studies, [OUTSIDE_READINESS_STUDY]);
    assert.deepEqual(capability.outside_stock_studies, ["outside-stock-budget-v1"],
      `${id}: the sibling outside-stock reference changed`);
    assert.deepEqual(capability.outside_research_studies, ["outside-query-model-v1"],
      `${id}: the sibling outside-query reference changed`);
  }
  for (const id of ["rail", "water", "start", "buildable", "resources", "trees", "water_risk"]) {
    assert.equal(ledger.capabilities.find((entry) => entry.id === id).outside_readiness_studies, undefined);
  }
  assert.deepEqual(validateOutsideReadiness(ledger), summary);
  assert.equal(study.evidence_only, true);
  assert.equal(study.certificates, "none");
  assert.equal(study.result, "unknown");
  // The study is not a native study and adds no certificate.
  assert.equal(ledger.native_path_certificates.length, 4);
  assert.equal(ledger.evidence_studies[OUTSIDE_READINESS_STUDY], undefined);
  assert.equal(Object.keys(ledger.evidence_studies).length, 2);
  // The sibling studies are untouched.
  assert.deepEqual(ledger.capabilities.find((entry) => entry.id === "rail").rail_research_studies, [
    "rail-query-model-v1", "rail-junction-fit-v1", "rail-stock-holdout-v1",
  ]);
  assert.equal(ledger.outside_research_studies.study, "outside-query-model-v1");
  assert.equal(ledger.outside_stock_studies.study, "outside-stock-budget-v1");
});

test("the projection, its tool and the strict source manifest are hash-bound", () => {
  assert.equal(sha(readUtf8(OUTSIDE_READINESS_PROJECTION)), OUTSIDE_READINESS_PROJECTION_SHA);
  assert.equal(sha(readUtf8(OUTSIDE_READINESS_SOURCES)), OUTSIDE_READINESS_SOURCES_SHA);
  assert.equal(sha(readUtf8(OUTSIDE_READINESS_TOOL)), OUTSIDE_READINESS_TOOL_SHA);
  const projection = parse(OUTSIDE_READINESS_PROJECTION);
  assert.equal(projection.source_manifest.file, OUTSIDE_READINESS_SOURCES);
  assert.equal(projection.source_manifest.sha256, OUTSIDE_READINESS_SOURCES_SHA);
  assert.deepEqual(Object.keys(projection.studies), [OUTSIDE_READINESS_STUDY]);
  assert.equal(summary.projection_sha256, OUTSIDE_READINESS_PROJECTION_SHA);
  assert.equal(summary.projection_tool_sha256, OUTSIDE_READINESS_TOOL_SHA);
  assert.equal(summary.source_manifest_sha256, OUTSIDE_READINESS_SOURCES_SHA);
  assert.equal(study.source.publication_commit, OUTSIDE_READINESS_PUBLICATION);
  assert.equal(study.source.publication_base, "86fee78d9517eff3c0e715813202b7b81b7e11d1");
  assert.equal(study.source.frozen_commit, OUTSIDE_READINESS_FROZEN);
  assert.equal(study.source.internal_merge, "10be1b73598d7080afae44010c9de8b99d295316");
  assert.equal(summary.pull_request, 93);
});

test("the publication's exact 26-file scope is pinned; only the compact files are carried", () => {
  const manifest = parse(OUTSIDE_READINESS_SOURCES);
  const publication = manifest.publications[OUTSIDE_READINESS_STUDY];
  assert.equal(Object.keys(publication.files).length, 26);
  assert.equal(publication.copied.length, 25);
  assert.equal(publication.linked.length, 1);
  assert.deepEqual(publication.linked, ["features.json.gz"]);
  assert.equal(publication.frozen_publication_files, 20);
  assert.equal(publication.post_control.length, 6);
  assert.equal(publication.frozen_changed.length, 2);
  for (const [relative, record] of Object.entries(publication.files)) {
    assert.match(record.sha256, /^[a-f0-9]{64}$/, `${relative} lacks a content hash`);
    assert.match(record.git_blob, /^[a-f0-9]{40}$/, `${relative} lacks a Git blob id`);
    assert.ok(record.bytes > 0, `${relative} has no size`);
    assert.equal(record.source, "86fee78d9517eff3c0e715813202b7b81b7e11d1", `${relative}: source pin changed`);
    const path = `${publication.prefix}/${relative}`;
    if (publication.copied.includes(relative)) {
      const raw = readFileSync(file(path));
      assert.equal(sha(raw), record.sha256, `${relative}: carried bytes changed`);
      assert.equal(raw.length, record.bytes, `${relative}: carried size changed`);
      const digest = createHash("sha1").update(Buffer.concat([Buffer.from(`blob ${raw.length}\0`), raw])).digest("hex");
      assert.equal(digest, record.git_blob, `${relative}: Git blob id does not follow its bytes`);
      assert.equal(publication.files[relative].frozen === null,
        publication.post_control.includes(relative),
        `${relative}: frozen-record presence does not follow the post-control set`);
    } else {
      assert.equal(existsSync(file(path)), false, `${relative}: bulk member duplicated in the repository`);
    }
  }
  // Carried and linked partition the publication, and nothing extra sits under the prefix.
  assert.deepEqual([...publication.copied, ...publication.linked].sort(), Object.keys(publication.files).sort());
  // The module's 25 member hashes are the 25 non-module publication files.
  const module = parse(`${publication.prefix}/module.json`);
  assert.equal(Object.keys(module.files).length, 25);
  assert.equal(module.version, 3);
  assert.equal(module.source, publication.base);
  for (const [name, digest] of Object.entries(module.files)) {
    assert.equal(publication.files[name].sha256, digest, `${name}: module hash disagrees`);
  }
  // Exactly two frozen records differ from the published bytes.
  const changed = Object.entries(publication.files)
    .filter(([, record]) => record.frozen && record.frozen.sha256 !== record.sha256)
    .map(([name]) => name).sort();
  assert.deepEqual(changed, ["README.md", "module.json"]);
});

test("all 51 retained raw hashes are recorded and the five carried files decompress to them", () => {
  const manifest = parse(OUTSIDE_READINESS_SOURCES);
  const publication = manifest.publications[OUTSIDE_READINESS_STUDY];
  const evaluation = parse(`${publication.prefix}/evaluation.json`);
  assert.equal(Object.keys(publication.raw.files).length, 51);
  assert.deepEqual(
    Object.fromEntries(Object.entries(publication.raw.files).sort()),
    Object.fromEntries(Object.entries(evaluation.raw_files).sort()));
  assert.equal(publication.raw.carried.length, 5);
  assert.equal(study.raw.length, 5);
  for (const record of publication.raw.carried) {
    const raw = readFileSync(file(record.path));
    assert.equal(sha(raw), record.sha256, `${record.path}: gzip hash changed`);
    const original = execFileSync("python3", ["-c", "import gzip,sys;sys.stdout.buffer.write(gzip.decompress(sys.stdin.buffer.read()))"], { input: raw });
    assert.equal(sha(original), record.raw_sha256, `${record.path}: decompressed hash changed`);
    assert.equal(original.length, record.raw_bytes);
    assert.equal(evaluation.raw_files[record.raw_path], record.raw_sha256, `${record.path}: not a recorded raw file`);
  }
  assert.equal(study.raw_manifest.length, 51);
  assert.equal(sha(JSON.stringify(study.raw_manifest.map((row) => [row.path, row.sha256]))), study.raw_manifest_sha256);
  assert.equal(sha(JSON.stringify(study.raw.map((row) => [row.path, row.sha256, row.raw_sha256]))), study.raw_evidence_sha256);
});

test("the outcome is Unknown: zero of six holdout cells, null metrics never 0%", () => {
  assert.equal(study.result, "unknown");
  assert.equal(study.holdout.planned, 6);
  assert.equal(study.holdout.observed, 0);
  assert.equal(study.holdout.unknown, 6);
  assert.equal(study.holdout.accuracy, null);
  assert.equal(study.holdout.precision, null);
  assert.equal(study.holdout.recall, null);
  assert.equal(study.holdout.records.length, 6);
  assert.ok(study.holdout.records.every((row) => row.status === "unobserved_unknown"));
  assert.ok(study.holdout.records.every((row) => row.prediction === row.class));
  assert.match(study.limits, /not estimable/);
  assert.match(study.limits, /never 0%/);
  assert.match(study.limits, /not a qualification/);
  // No request in the plan is observed; controls are separate from holdout.
  assert.equal(study.requests.controls, 12);
  assert.equal(study.requests.holdout, 6);
  assert.equal(study.requests.planned, 18);
});

test("the corrected controls are complete, released, indexed and cleaned up", () => {
  assert.equal(study.control_rows.length, 12);
  assert.ok(study.control_rows.every((row) => row.complete === true && row.released === true));
  assert.ok(study.control_rows.every((row) => row.pre_build_index === row.effective_build_index));
  assert.equal(study.controls.successes, 6);
  assert.equal(study.controls.failures, 6);
  assert.equal(study.controls.openings, 2);
  assert.equal(study.controls.inventories_per_opening, 3);
  assert.equal(study.controls.inventory.files, 45);
  assert.equal(study.controls.inventory.roots, 11);
  assert.equal(study.controls.inventory.plugins, 7);
  assert.equal(study.controls.inventory.assemblies, 23);
  assert.equal(study.controls.owned_processes, 10);
  assert.equal(study.controls.owned_processes_gone, 10);
  assert.equal(study.controls.graph_opening_equals_post, true);
  // Observation windows are the retained dated context, not freeze/publication times.
  assert.equal(study.observation_windows.length, 2);
  for (const window of study.observation_windows) {
    assert.ok(window.started_at < window.finished_at);
    assert.ok(window.started_at > study.freeze.frozen_at, `${window.case_id}: window precedes the freeze`);
  }
});

test("the 82-file study tree and the 30-file contract closure are both re-derivable", () => {
  const freeze = parse(`${OUTSIDE_READINESS_PREFIX}${OUTSIDE_READINESS_STUDY}/freeze.json`);
  const sources = freeze.source_files;
  assert.equal(Object.keys(sources).length, 82);
  const canonical = (value) => JSON.stringify(Object.fromEntries(Object.entries(value).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))));
  assert.equal(sha(Buffer.from(canonical(sources))),
    "03f7fb7c8eb8e3d6dd94f6444c5cd0cbd2156c325148b1006b564776a34f226d");
  const contract = study.freeze.contract_source_files;
  assert.equal(contract.length, 30);
  assert.deepEqual(contract, [...contract].sort());
  assert.ok(contract.every((name) => sources[name] !== undefined));
  const subset = Object.fromEntries(contract.map((name) => [name, sources[name]]));
  assert.equal(sha(Buffer.from(canonical(subset))),
    "561e4b522bc27fe9c06eb59a0ed875461b47277a2379c18d5998b8e753854860");
  // The runtime policy records the 82-file digest, which cannot equal the 30-file closure.
  assert.equal(study.bundle.policy_source_sha256, study.freeze.source_sha256);
  assert.notEqual(study.bundle.policy_source_sha256, study.freeze.contract_source_sha256);
  assert.equal(study.readiness.ready_for_measurement, false);
  assert.equal(study.readiness.reasons.length, 2);
  assert.ok(study.readiness.reasons.every((reason) => reason.endsWith("runtime policy differs from freeze")));
  // Immutable siblings.
  assert.equal(study.freeze.old_fact_count, 84);
  assert.equal(study.freeze.old_publication_files, 142);
  assert.equal(study.freeze.readiness_files, 24);
});

test("the page renders the one study once and keeps it distinct from qualification", () => {
  const html = outsideReadinessPage({ study }, escape);
  assert.equal(html.split('id="outside-readiness-study"').length - 1, 1);
  for (const phrase of [
    "Unknown",
    "Zero of six planned holdout requests were issued",
    "not estimable",
    "never 0%",
    "82",
    "30",
    "03f7fb7c8eb8e3d6dd94f6444c5cd0cbd2156c325148b1006b564776a34f226d",
    "561e4b522bc27fe9c06eb59a0ed875461b47277a2379c18d5998b8e753854860",
    "not a qualification",
    "post-exit audit",
    "fresh clone cannot reproduce the full verify",
  ]) assert.ok(html.includes(phrase), `missing ${phrase}`);
  assert.ok(!/accuracy:\s*\d/.test(html), "the page flattens the study into an accuracy headline");
  assert.ok(!/promised/i.test(html), "the page promises a capability");
  // Regression: array fields must render counts and names, never NaN or an empty cell.
  assert.ok(!html.includes("NaN"), "the page renders NaN");
  assert.ok(html.includes("6 files were written after the controls"), "the post-control file count is missing");
  assert.ok(html.includes("2 changed after the freeze"), "the frozen-changed count is missing");
  assert.ok(html.includes("other 18 publication files are the frozen bytes"), "the unchanged frozen count is missing");
  const selectionTable = html.match(/data-outside-readiness-selection[\s\S]*?<\/table>/)[0];
  assert.match(selectionTable, /<td>6<\/td><td>0<\/td><\/tr>/, "the selection table lost its covered/missing counts");
  assert.equal((html.match(/The outcome is Unknown and limited/g) ?? []).length, 1, "the limits paragraph is repeated");
  for (const id of ["road", "ship", "air"]) {
    const reference = outsideReadinessReference(id, { study }, escape);
    assert.ok(reference.includes("Unknown"), `${id}: the reference hides the Unknown state`);
    assert.ok(reference.includes("controls are not holdout predictions"), `${id}: the reference turns controls into votes`);
  }
  const page = ledgerPage(ledger, "test-source");
  assert.equal(page.split('id="outside-readiness-study"').length - 1, 1, "the study is rendered more than once");
  assert.equal(page.split("Outside-query controls on a frozen unseen cohort — Unknown").length - 1, 4,
    "the page heading plus Road, Ship and Air references must each be present");
  assert.deepEqual(outsideReadinessFiles(study).sort(), [
    OUTSIDE_READINESS_PROJECTION, OUTSIDE_READINESS_SOURCES,
    ...study.files.map((record) => record.path),
    ...study.raw.map((record) => record.path),
  ].sort());
});

test("a changed holdout outcome, label, cleanup, digest or raw byte fails closed", () => {
  const cases = [
    ["evaluation.json", (value) => { value.result = "success"; }],
    ["evaluation.json", (value) => { value.holdout_observed = 1; value.holdout[0].status = "observed"; }],
    ["evaluation.json", (value) => { value.controls[0].rows[0].label = "no_path"; value.controls[0].rows[0].kind = "positive"; }],
    ["evaluation.json", (value) => { value.controls[0].rows[0].pre_build_index = 1; }],
    ["evaluation.json", (value) => { value.controls[0].cleanup.game.gone = false; }],
    ["evaluation.json", (value) => { value.controls[0].opening_graph_sha256 = "0".repeat(64); }],
    ["freeze.json", (value) => { value.source_sha256 = "0".repeat(64); }],
    ["freeze.json", (value) => { value.source_files["tools/map-factory/crp.py"] = "0".repeat(64); }],
    ["bundle.json", (value) => { value.policy.source_sha256 = "561e4b522bc27fe9c06eb59a0ed875461b47277a2379c18d5998b8e753854860"; }],
    ["requests.json", (value) => { value.holdout[0].prediction = "no_path"; }],
    ["requests.json", (value) => { value.holdout.pop(); }],
    ["selection.json", (value) => { value.covered_cells.pop(); }],
    ["module.json", (value) => { value.files["README.md"] = "0".repeat(64); }],
  ];
  for (const [name, apply] of cases) {
    const load = loader((path, raw) => {
      if (path !== `${OUTSIDE_READINESS_PREFIX}${OUTSIDE_READINESS_STUDY}/${name}`) return undefined;
      const value = JSON.parse(raw.toString("utf8"));
      apply(value);
      return Buffer.from(JSON.stringify(value));
    });
    assert.throws(() => outsideReadiness(load), `${name}: mutation was not refused`);
  }
  // A changed carried byte and a changed raw gzip byte are both refused.
  const readme = `${OUTSIDE_READINESS_PREFIX}${OUTSIDE_READINESS_STUDY}/README.md`;
  assert.throws(() => outsideReadiness(loader((path, raw) => path === readme
    ? Buffer.concat([raw, Buffer.from("x")]) : undefined)), "carried bytes changed without refusal");
  const rawFile = study.raw[0].path;
  assert.throws(() => outsideReadiness(loader((path, raw) => path === rawFile
    ? gzipSync(Buffer.from("not the retained bytes")) : undefined)), "raw gzip changed without refusal");
  // The valid loader still succeeds.
  assert.equal(outsideReadiness(loader(() => undefined)).study.study, OUTSIDE_READINESS_STUDY);
});

test("the importer is deterministic and never rewrites an unowned ledger byte", () => {
  const before = readFileSync(file("capabilities.json"));
  const beforeLedger = JSON.parse(before);
  const owned = JSON.stringify({
    certificates: beforeLedger.native_path_certificates,
    native: beforeLedger.evidence_studies,
    rail: beforeLedger.rail_studies,
    railResearch: beforeLedger.rail_research_studies,
    outsideResearch: beforeLedger.outside_research_studies,
    outsideStock: beforeLedger.outside_stock_studies,
  });
  const run = () => execFileSync("python3", ["tools/map-factory/integrate_outside_readiness.py"], { cwd: file(".").pathname, encoding: "utf8" });
  run();
  run();
  const after = readFileSync(file("capabilities.json"));
  assert.equal(sha(after), sha(before), "regeneration changed the ledger");
  const afterLedger = JSON.parse(after);
  assert.equal(JSON.stringify({
    certificates: afterLedger.native_path_certificates,
    native: afterLedger.evidence_studies,
    rail: afterLedger.rail_studies,
    railResearch: afterLedger.rail_research_studies,
    outsideResearch: afterLedger.outside_research_studies,
    outsideStock: afterLedger.outside_stock_studies,
  }), owned, "an unowned ledger section changed");
  assert.equal(afterLedger.outside_readiness_studies.study, OUTSIDE_READINESS_STUDY);
  // The sibling outside-stock producer's exact text surgery preserves this study.
  const raw = after.toString("utf8");
  const stockHead = '\n  "outside_stock_studies": ';
  const sibling = '\n  "outside_research_studies": ';
  const start = raw.indexOf(stockHead);
  const stop = raw.indexOf(sibling, start);
  assert.ok(start > 0 && stop > start);
  const stockBlock = raw.slice(start, stop).replace(/,$/, "");
  const simulated = raw.slice(0, start) + stockBlock + "," + raw.slice(stop);
  assert.equal(sha(Buffer.from(simulated)), sha(Buffer.from(raw)), "the simulation is not the sibling producer's no-op rewrite");
  const simulatedLedger = JSON.parse(simulated);
  assert.equal(simulatedLedger.outside_readiness_studies.study, OUTSIDE_READINESS_STUDY,
    "the sibling producer's rewrite would drop this study");
  for (const id of ["road", "ship", "air"]) {
    assert.deepEqual(simulatedLedger.capabilities.find((entry) => entry.id === id).outside_readiness_studies,
      [OUTSIDE_READINESS_STUDY], `${id}: the sibling rewrite would drop the reference`);
  }
  // And this producer's rewrite preserves the sibling summary and references.
  for (const id of ["road", "ship", "air"]) {
    assert.deepEqual(afterLedger.capabilities.find((entry) => entry.id === id).outside_stock_studies,
      ["outside-stock-budget-v1"]);
  }
  assert.equal(afterLedger.outside_stock_studies.study, "outside-stock-budget-v1");
  assert.equal(afterLedger.outside_research_studies.study, "outside-query-model-v1");
});
test("only this study's ledger fields differ from the exact source ledger", () => {
  const canonical = (value) => createHash("sha256").update(JSON.stringify(value)).digest("hex");
  const sorted = (value) => {
    if (Array.isArray(value)) return value.map(sorted);
    if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)).map(([k, v]) => [k, sorted(v)]));
    return value;
  };
  const digest = (value) => canonical(sorted(value));
  // Fingerprints of the exact a58356e ledger, excluding only this study's key and references.
  assert.equal(digest(ledger.native_path_certificates), "ce2d91ab67127659a0887bf7496909cdc980d9848243ed99af7ca6ee4002df02");
  assert.equal(digest(ledger.evidence_studies), "db89882050b633a596abffb6144962b5d26dca97ba8a4199a38198839c91c056");
  assert.equal(digest(ledger.outside_stock_studies), "e09523826e11cd679c0da19aa8fbcb4a7d6b35ca3a6bcee388983473c5771da5");
  assert.equal(digest(ledger.outside_research_studies), "d082d9f88de5d679e0b5f141418a115948d254000b04ad3d6208de7d33fbb270");
  assert.equal(digest(ledger.rail_studies), "7d56922c9c7099791b36544376674fd579b1f49b19a92a632eb439aab7a4f498");
  assert.equal(digest(ledger.rail_research_studies), "8acfe9cf7cd6b0c78f16ffb3929b5ca8d410942407f060523515d4185f0adfa2");
  assert.equal(digest(ledger.witness_studies), "5a98de5c788682a90f00ae9b1228d270c09bb92a08590301d92484ab7bee1d88");
  const stripped = ledger.capabilities.map(({ outside_readiness_studies, ...rest }) => rest);
  assert.equal(digest(stripped), "0da579dca5f4697323c9009b43f5235a906e675647d73bca5f3103d397cdb481");
  // Exactly one top-level key was added, and it is this study's.
  assert.deepEqual(Object.keys(ledger).slice(-1), ["outside_readiness_studies"]);
  assert.equal(Object.keys(ledger).filter((key) => key === "outside_readiness_studies").length, 1);
});

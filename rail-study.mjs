// The reviewed directed-rail native study, read from archived bytes only.
//
// This module never runs the archived native tools, the collector, a predictor, a
// scorer or the game. It re-checks the projection's own bindings, the frozen native
// source closure and the ledger summary, then renders the study under the Rail
// capability. A sampled native lane path is not a rail service, an accuracy score or
// a geographic negative.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";

const ROOT = fileURLToPath(new URL(".", import.meta.url));
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const read = (file) => readFileSync(ROOT + file);

export const RAIL_STUDY = "directed-rail-v3";
export const RAIL_PROJECTION = "tools/map-factory/capability-evidence/rail-study.json";
export const RAIL_PROJECTION_SHA = "16fdc0007236477f02ea28fd3b2e677f459b00d9d425ba626ee7701674c67c84";
export const RAIL_PROJECTION_TOOL = "tools/map-factory/integrate_rail_evidence.py";
export const RAIL_PROJECTION_TOOL_SHA = "4f8a0b8483acb11997c1154791f5a6a1095aff3f13e48f3ac7f4de50a2dc0b4c";
export const RAIL_PREDICTIONS = "tools/map-factory/capability-evidence/pl1119-v3-predictions.json";
export const RAIL_PREDICTIONS_SHA = "1f2db0bb64e62965137cce05ffe0cea7bf8aa339c2a8a9e9560fafe4ef64ae03";
export const RAIL_SOURCE_MANIFEST = "tools/map-factory/capability-evidence/rail-native-sources/manifest.json";
export const RAIL_SOURCE_MANIFEST_SHA = "b9ab05084e613605dc1cc5b97368bba864e9e87afc7153e55cf7ab7217ff6134";
export const RAIL_EVIDENCE_PREFIX = "tools/map-factory/capability-evidence/";

const EXPECTED = {
  kind: "directed_rail_control_and_cohort_study",
  study: RAIL_STUDY,
  source_commit: "1a0e45c65745ba5f05cf22f947da2e88fed25277",
  source_base: "29b095475ba2f93c7e918fefc08c736493670304",
  source_issue: "01a1fe64-7010-7533-bf2d-34ed498286c7",
  controls: 2,
  cohort: 9,
  selected_boundary: 244,
  distinct_edge_successes: 9,
  same_edge_successes: 2,
  selected_failures: 233,
  unqueried_boundary_candidates: 112,
  sampled_positive: 4,
  unknown: 5,
  runtime_openings: 11,
  final_protocol_raw_files: 83,
  earlier_revision_raw_files: 28,
  raw_files: 111,
  harness_sources: 56,
  build_sources: 17,
};

const fail = (message) => {
  throw new Error(message);
};

/** Frozen native source closure: 56 harness files and 17 C# build sources. */
export function railSourceClosure(load = read) {
  if (sha(load(RAIL_SOURCE_MANIFEST)) !== RAIL_SOURCE_MANIFEST_SHA) fail("Native rail source manifest changed");
  const manifest = JSON.parse(load(RAIL_SOURCE_MANIFEST).toString("utf8"));
  if (manifest.source_commit !== EXPECTED.source_commit) fail("Native rail source manifest names another publication");
  const files = Object.entries(manifest.files);
  if (files.length !== EXPECTED.harness_sources) fail("Frozen native source count changed");
  for (const [original, record] of files) {
    if (record.file !== `${RAIL_EVIDENCE_PREFIX}rail-native-sources/${
      original.startsWith("tools/cs1-harness/mod/") ? "mod" : "cs1_harness"}/${original.split("/").at(-1)}`)
      fail(`Unexpected archive path for ${original}`);
    if (sha(load(record.file)) !== record.sha256) fail(`Archived native source changed: ${original}`);
  }
  return { manifest, files };
}

/**
 * The projection plus the exact ledger summary. Every byte this reads is pinned by a
 * hash; the summary is derived, never copied, so a mutated projection or ledger fails.
 */
export function railStudy(load = read) {
  const closure = railSourceClosure(load);
  if (sha(load(RAIL_PROJECTION_TOOL)) !== RAIL_PROJECTION_TOOL_SHA) fail("Directed rail projection tool changed");
  const projectionBytes = load(RAIL_PROJECTION);
  const projectionSha = sha(projectionBytes);
  if (projectionSha !== RAIL_PROJECTION_SHA) fail("Directed rail projection changed");
  const study = JSON.parse(projectionBytes.toString("utf8"));
  if (sha(load(RAIL_PREDICTIONS)) !== RAIL_PREDICTIONS_SHA) fail("Frozen v3 rail predictions changed");
  if (study.kind !== EXPECTED.kind || study.study !== EXPECTED.study) fail("Directed rail study kind changed");
  if (study.source.publication_commit !== EXPECTED.source_commit ||
      study.source.publication_base !== EXPECTED.source_base ||
      study.source.source_issue !== EXPECTED.source_issue)
    fail("Directed rail study source identity changed");
  if (study.frozen_predictions.file !== RAIL_PREDICTIONS || study.frozen_predictions.sha256 !== RAIL_PREDICTIONS_SHA)
    fail("Directed rail study does not bind the frozen predictions");
  if (study.source_closure.manifest_file !== RAIL_SOURCE_MANIFEST || study.source_closure.harness_sources !== EXPECTED.harness_sources ||
      study.source_closure.build_source_count !== EXPECTED.build_sources)
    fail("Directed rail source closure changed");
  if (!isDeepStrictEqual(study.source_closure.files, closure.manifest.files) ||
      !isDeepStrictEqual(study.source_closure.build_sources, Object.fromEntries(
        Object.entries(closure.manifest.files)
          .filter(([original]) => original.startsWith("tools/cs1-harness/mod/"))
          .map(([original, record]) => [original.split("/").at(-1), record.sha256]))))
    fail("Directed rail source closure does not match its manifest");
  if (study.controls.length !== EXPECTED.controls || study.cohort.length !== EXPECTED.cohort) fail("Directed rail study lost a cell");
  if (study.totals.selected_boundary !== EXPECTED.selected_boundary ||
      study.totals.distinct_edge_successes !== EXPECTED.distinct_edge_successes ||
      study.totals.same_edge_successes !== EXPECTED.same_edge_successes ||
      study.totals.selected_failures !== EXPECTED.selected_failures ||
      study.totals.unqueried_boundary_candidates !== EXPECTED.unqueried_boundary_candidates ||
      study.totals.sampled_positive !== EXPECTED.sampled_positive || study.totals.unknown !== EXPECTED.unknown)
    fail("Directed rail totals changed");
  const recomputed = {
    selected_boundary: 0, distinct_edge_successes: 0, same_edge_successes: 0,
    selected_failures: 0, unqueried_boundary_candidates: 0, sampled_positive: 0, unknown: 0,
  };
  for (const cell of study.cohort) {
    if (cell.status === "sampled_positive") recomputed.sampled_positive++;
    else if (cell.status === "Unknown") recomputed.unknown++;
    else fail(`${cell.slug}: unknown case status`);
    for (const attempt of cell.attempts) {
      if (!attempt.completed) continue;
      for (const key of Object.keys(recomputed).slice(0, 5)) recomputed[key] += attempt[key] ?? 0;
    }
  }
  for (const [key, value] of Object.entries(recomputed)) if (study.totals[key] !== value) fail(`Directed rail ${key} is not consistent`);
  if (recomputed.selected_boundary !== recomputed.distinct_edge_successes + recomputed.same_edge_successes + recomputed.selected_failures)
    fail("Directed rail selected totals do not add up");
  for (const control of study.controls) {
    if (!control.reciprocal_positives || !control.invalid_vehicle_pair_rejected) fail(`${control.slug}: control gate lost`);
    if (control.selected_boundary !== control.distinct_edge_successes + control.same_edge_successes + control.selected_failures)
      fail(`${control.slug}: control totals do not add up`);
  }
  if (study.controls.reduce((n, c) => n + c.selected_boundary, 0) !== 32 ||
      study.controls.reduce((n, c) => n + c.distinct_edge_successes, 0) !== 16)
    fail("Stock control totals changed");
  const pittsburgh = study.cohort.find((cell) => cell.slug === "pittsburgh");
  if (pittsburgh?.attempts.at(-1)?.unqueried_boundary_candidates !== EXPECTED.unqueried_boundary_candidates)
    fail("Pittsburgh's bounded coverage changed");
  const boston = study.cohort.find((cell) => cell.slug === "boston");
  if (!boston || !boston.attempts.some((attempt) => attempt.completed && attempt.same_edge_successes === 2))
    fail("Boston's same-edge successes are not separate");
  for (const cell of study.cohort) {
    if (cell.attempts.some((attempt) => !attempt.completed && !attempt.error)) fail(`${cell.slug}: unlaunched attempt lost its error`);
  }
  const counts = study.raw_files.length;
  if (counts !== EXPECTED.raw_files || study.raw_file_counts.total !== counts ||
      study.raw_file_counts.final_protocol !== EXPECTED.final_protocol_raw_files ||
      study.raw_file_counts.earlier_revisions !== EXPECTED.earlier_revision_raw_files ||
      study.raw_file_counts.runtime_openings !== EXPECTED.runtime_openings)
    fail("Directed rail raw file accounting changed");
  const attempts = study.cohort.flatMap((cell) => cell.attempts.map((attempt) => attempt.attempt));
  if (study.cleanup.degraded !== true) fail("The retained teardown finding was waived");
  for (const finding of study.cleanup.findings) {
    if (!attempts.includes(finding.attempt)) fail("Cleanup finding names an unknown attempt");
    if (!finding.raw_cleanup.steam_instances.length) fail("Cleanup finding lost its raw remainder");
    if (!/later audit proves listed instance absent/.test(finding.later_state)) fail("Cleanup finding was reclassified");
  }
  const summary = {
    kind: study.kind,
    study: study.study,
    source_commit: study.source.publication_commit,
    source_base: study.source.publication_base,
    source_issue: study.source.source_issue,
    projection_file: RAIL_PROJECTION,
    projection_sha256: projectionSha,
    projection_tool_file: RAIL_PROJECTION_TOOL,
    projection_tool_sha256: RAIL_PROJECTION_TOOL_SHA,
    source_closure_manifest: RAIL_SOURCE_MANIFEST,
    source_closure_sha256: RAIL_SOURCE_MANIFEST_SHA,
    frozen_predictions_file: RAIL_PREDICTIONS,
    frozen_predictions_sha256: RAIL_PREDICTIONS_SHA,
    raw_files: study.raw_file_counts.total,
    final_protocol_raw_files: study.raw_file_counts.final_protocol,
    earlier_revision_raw_files: study.raw_file_counts.earlier_revisions,
    runtime_openings: study.raw_file_counts.runtime_openings,
    controls: study.controls.map((control) => ({
      slug: control.slug, file: control.file, artifact_sha256: control.artifact_sha256,
      selected_boundary: control.selected_boundary, distinct_edge_successes: control.distinct_edge_successes,
      same_edge_successes: control.same_edge_successes, selected_failures: control.selected_failures,
      reciprocal_positives: control.reciprocal_positives,
      invalid_vehicle_pair_rejected: control.invalid_vehicle_pair_rejected, observed_at: control.observed_at,
    })),
    totals: study.totals,
    cohort: study.cohort.map((cell) => ({
      slug: cell.slug, square: cell.square, artifact_sha256: cell.artifact_sha256, status: cell.status,
      frozen_model_level: cell.frozen_model_prediction.level,
      attempts: cell.attempts.map((attempt) => ({
        attempt: attempt.attempt, observed_at: attempt.observed_at, finished_at: attempt.finished_at,
        completed: attempt.completed, error: attempt.error, selected_boundary: attempt.selected_boundary,
        distinct_edge_successes: attempt.distinct_edge_successes,
        same_edge_successes: attempt.same_edge_successes, selected_failures: attempt.selected_failures,
        unqueried_boundary_candidates: attempt.unqueried_boundary_candidates,
        missing_reason: attempt.missing_reason,
      })),
    })),
    documents: study.documents,
    cleanup: {
      audited_at: study.cleanup.audited_at, degraded: study.cleanup.degraded,
      findings: study.cleanup.findings, coverage: study.cleanup.coverage,
    },
    certificates: "none",
    limits: study.limits,
  };
  return { study, summary, closure };
}

/** Every repo-relative file the generated page serves for this study. */
export function railStudyFiles(study = railStudy().study) {
  const extra = [
    RAIL_PROJECTION, RAIL_PREDICTIONS, RAIL_SOURCE_MANIFEST,
    ...study.documents.map((document) => document.path),
  ];
  const sources = Object.values(study.source_closure.files).map((record) => record.file);
  return [...new Set([...study.raw_files.map((record) => record.path), ...extra, ...sources])];
}

/** The archived raw receipts, keyed by attempt, for the page's evidence lists. */
export function railEvidenceIndex(study = railStudy().study) {
  return study.raw_files.map((record) => ({
    path: record.path,
    sha256: record.sha256,
    gzip_sha256: record.gzip_sha256,
    bytes: record.bytes,
    attempt: record.path.slice(RAIL_EVIDENCE_PREFIX.length).split("/").slice(0, 3).join("/"),
  }));
}

export function validateRailStudy(ledger, load = read) {
  const { summary } = railStudy(load);
  if (!isDeepStrictEqual(ledger.rail_studies, { [RAIL_STUDY]: summary }))
    fail("Directed rail projection is stale or unbound in the ledger");
  const rail = ledger.capabilities.find((capability) => capability.id === "rail");
  if (rail?.rail_study !== RAIL_STUDY) fail("Rail does not reference the directed rail study");
  if ((ledger.native_path_certificates ?? []).some((certificate) => certificate.capability === "rail"))
    fail("A rail native certificate exists; this study is evidence only");
  return summary;
}

const table = (escape, heads, rows, attrs = "") =>
  `<div class="ledger-table"><table ${attrs}><thead><tr>${heads.map((head) => `<th scope="col">${escape(head)}</th>`).join("")}</tr></thead><tbody>${rows
    .map((row) => `<tr>${row.map((value, index) => `<${index ? "td" : "th"}${index ? "" : ' scope="row"'}>${escape(value)}</${index ? "td" : "th"}>`).join("")}</tr>`)
    .join("")}</tbody></table></div>`;

const stackedTable = (escape, heads, rows, attrs = "") =>
  `<div class="ledger-table"><table ${attrs}><thead><tr>${heads.map((head) => `<th scope="col">${escape(head)}</th>`).join("")}</tr></thead><tbody>${rows
    .map(([name, note, ...rest]) => `<tr><th scope="row"><span data-case-name>${escape(name)}</span><br><span class="note">${escape(note)}</span></th>${rest
      .map((value) => `<td>${escape(value)}</td>`).join("")}</tr>`)
    .join("")}</tbody></table></div>`;

const detail = (escape, title, value) =>
  `<details><summary>${escape(title)}</summary><pre>${escape(JSON.stringify(value, null, 2))}</pre></details>`;

const evidenceItem = (escape, base, record) =>
  `<li><a data-evidence href="${escape(`${base}${record.path}`)}" data-sha256="${record.gzip_sha256}">${escape(record.path.slice(RAIL_EVIDENCE_PREFIX.length))}</a><br>served <code>${record.gzip_sha256}</code><br>decompressed <code>${record.sha256}</code></li>`;

export function railStudyPage({ study, summary }, escape, base = "") {
  const value = (flag) => (flag === null || flag === undefined ? "Unknown" : flag ? "Yes" : "No");
  const cohortRows = summary.cohort.map((cell) => {
    const attempts = cell.attempts.filter((attempt) => attempt.completed);
    const selected = attempts.reduce((n, attempt) => n + attempt.selected_boundary, 0);
    const distinct = attempts.reduce((n, attempt) => n + attempt.distinct_edge_successes, 0);
    const same = attempts.reduce((n, attempt) => n + attempt.same_edge_successes, 0);
    const failed = attempts.reduce((n, attempt) => n + attempt.selected_failures, 0);
    const unqueried = attempts.reduce((n, attempt) => n + attempt.unqueried_boundary_candidates, 0);
    const state = cell.status === "sampled_positive"
      ? `Sampled positive${same ? ` · ${same} same-edge` : ""}${unqueried ? ` · ${unqueried} unqueried` : ""}`
      : selected === 0 && failed === 0 ? "Unknown · no directed pair"
      : failed ? "Unknown · selected failures" : "Unknown";
    return [cell.square.name, `${selected}`, `${distinct}`, `${failed}`, state];
  });
  const total = summary.totals;
  const attemptRows = summary.cohort.flatMap((cell) => cell.attempts.map((attempt) => [
    cell.square.name,
    attempt.attempt.replace(`${cell.slug}-`, ""),
    attempt.finished_at ? attempt.finished_at.slice(0, 10) : "Unknown",
    attempt.completed ? "Opening completed" : "Stopped before launch",
  ]));
  const controls = summary.controls.map((control) => [
    control.file.replace(/\.crp$/, ""),
    `${control.distinct_edge_successes}/${control.selected_boundary}`,
    `${control.selected_failures}`,
  ]);
  const agreement = summary.cohort.map((cell) => [
    cell.square.name,
    cell.frozen_model_level === "likely" ? "likely" : "not possible",
    `${cell.artifact_sha256.slice(0, 8)}…`,
    cell.status === "sampled_positive" ? "Witness observed" : "Unknown",
  ]);
  const evidence = study.raw_files;
  return `<section id="rail-directed-study" data-rail-study="${escape(summary.study)}">
    <h3>Directed rail native study · ${escape(summary.study)} · evidence only</h3>
    <p>Two fixed stock controls calibrate an exact directed Train path query at opening, between literal native lane positions. The unchanged nine-package cohort then runs. Success is a complete, released native path whose first and last positions are the requested Outside offsets. A failure or an empty candidate list is <strong>Unknown</strong>, never absence. No rail service, train spawn, station, sustained gameplay or editor/gameplay parity is tested or claimed.</p>
    ${table(escape, ["Stock control", "Successes / selected", "Failures"], controls, 'data-rail-controls')}
    <p>Both controls complete in bound contexts, both carry reciprocal exact successes, and both reject an explicit Train query to a Car-but-not-Train lane. That rejection is a protocol diagnostic, never a geographic observation.</p>
    ${stackedTable(escape, ["Original case", "Selected", "Distinct-edge", "Failures"], [
      ...cohortRows.map(([name, selected, distinct, failed, state]) => [name, state, selected, distinct, failed]),
      ["Total", `${total.sampled_positive} positive · ${total.unknown} Unknown · ${total.same_edge_successes} same-edge · ${total.unqueried_boundary_candidates} unqueried`,
        `${total.selected_boundary}`, `${total.distinct_edge_successes}`, `${total.selected_failures}`],
    ], 'data-rail-cohort')}
    <p>Selected requests are a bounded sample. Pittsburgh's fixed 128-request cap left ${escapedNumber(total.unqueried_boundary_candidates)} candidates unqueried; Boston's two same-edge successes are not distinct-edge witnesses. Charleston, Grand Canyon and Yosemite listed no directed pair: Unknown, not "no railway".</p>
    ${stackedTable(escape, ["Case", "Date", "Outcome"],
      attemptRows.map(([name, attempt, date, outcome]) => [name, attempt, date, outcome]), 'data-rail-attempts')}
    <h4>Frozen v3 model comparability</h4>
    <p>Four positive cells match the preserved frozen-v3 rail candidates by exact artifact SHA-256 and CPU receipt lineage, not by place name. That is <strong>positive-witness agreement on an already observed cohort</strong>, not accuracy, sensitivity, a blind holdout or a fitted place-level promise. The five Unknown cells remain unscored.</p>
    ${stackedTable(escape, ["Case", "Frozen v3 rail", "Native observation"],
      agreement.map(([name, level, artifact, observation]) => [name, `artifact ${artifact}`, level, observation]), 'data-rail-agreement')}
    <p>Frozen predictions: <a data-evidence href="${escape(base + summary.frozen_predictions_file)}" data-sha256="${escape(summary.frozen_predictions_sha256)}">${escape(summary.frozen_predictions_file.slice(RAIL_EVIDENCE_PREFIX.length))}</a> · <code>${escape(summary.frozen_predictions_sha256)}</code>. Raw native receipts bind CRP bytes; the three prepared-input hashes are reused frozen lineage, not fresh native rehashes.</p>
    <h4>Cleanup finding · retained, not repaired</h4>
    <p>${summary.cleanup.degraded
      ? `One teardown snapshot lists a Steam instance and the frozen strict verifier rejects it. The later read-only audit at ${escape(summary.cleanup.audited_at)} proves that listed instance absent and every recorded owned game, collector and monitor process gone. The raw receipt and the strict failure are unchanged; this is a degraded finding, not an empty teardown.`
      : "All recorded teardown snapshots were empty."} Coverage checked by this importer: ${escape(summary.cleanup.coverage)}.</p>
    ${detail(escape, "Cleanup finding, raw teardown and later audit", summary.cleanup)}
    ${detail(escape, "Every attempt's raw error, identity and cleanup facts", summary.cohort.map((cell) => ({ slug: cell.slug, attempts: cell.attempts })))}
    <details><summary>Source, protocol, frozen selection and native source closure</summary>
      <p>Publication <a href="https://github.com/frontierkodiak/region-to-skylines/tree/${escape(summary.source_commit)}/${escape(RAIL_EVIDENCE_PREFIX)}rail-v3">${escape(summary.source_commit.slice(0, 12))}…</a> on accepted base ${escape(summary.source_base.slice(0, 12))}…, review pass on issue ${escape(summary.source_issue)}. Publication is not an observation date. Source closure re-checked: ${study.source_closure.harness_sources} frozen harness sources and ${study.source_closure.build_source_count} C# build sources, archived read-only under ${escape(study.source_closure.prefix)}.</p>
      ${detail(escape, "Native protocol and frozen selection", { protocol: study.protocol, selection: study.selection, source: study.source })}
      ${detail(escape, "Earlier selector revisions retained separately", study.earlier_revisions.map((revision) => ({ ...revision, raw_files_sha256: undefined, raw: revision.raw_files })))}
      <ul>${Object.entries(study.source_closure.files).map(([original, record]) =>
        `<li><a data-evidence href="${escape(base + record.file)}" data-sha256="${escape(record.sha256)}">${escape(original)}</a> · <code>${escape(record.sha256)}</code></li>`).join("")}</ul>
    </details>
    <details><summary>Method and limits</summary><p>${escape(study.method)}</p><p>${escape(study.limits)}</p></details>
    <details><summary>All ${escapedNumber(summary.raw_files)} archived evidence files · ${escapedNumber(summary.final_protocol_raw_files)} final protocol + ${escapedNumber(summary.earlier_revision_raw_files)} earlier revisions</summary>
      <p>Each link is served beside this page. The checked hash is the SHA-256 of the exact served (compressed) bytes; the receipt's decompressed SHA-256 and byte length are bound by the same integrity manifest and re-checked by the importer.</p>
      <ul data-rail-evidence>${evidence.map((record) => evidenceItem(escape, base, record)).join("")}</ul>
      <p>Earlier selectors remain separate diagnostics. The published protocol, results and the retained strict failure are served below with their own hashes; earlier revisions and repeated stock openings are not pooled as votes.</p>
      <ul>${summary.documents.map((document) => `<li><a data-evidence href="${escape(base + document.path)}" data-sha256="${escape(document.sha256)}">${escape(document.path.slice(RAIL_EVIDENCE_PREFIX.length))}</a> · <code>${escape(document.sha256)}</code></li>`).join("")}</ul>
    </details>
    <p class=note>${escape(summary.limits)}</p></section>`;
}

const escapedNumber = (value) => Number(value).toLocaleString("en-US");

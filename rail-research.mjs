// Three accepted rail research publications, read from archived bytes only.
//
// This module never runs a research model, the collector, a scorer, the game or
// the browser. It re-checks each publication's carried evidence and file scope,
// re-derives a compact summary of the projection, and renders the three studies
// under the Rail capability. They are distinct typed studies: not pooled with
// directed-rail-v3, not promises, not certificates and not live rules.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";

const ROOT = fileURLToPath(new URL(".", import.meta.url));
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const read = (file) => readFileSync(ROOT + file);

export const RAIL_RESEARCH_STUDIES = ["rail-query-model-v1", "rail-junction-fit-v1", "rail-stock-holdout-v1"];
export const RAIL_RESEARCH_PROJECTION = "tools/map-factory/capability-evidence/rail-research-studies.json";
export const RAIL_RESEARCH_PROJECTION_SHA = "f9ad71df4d1ff436324d02c5c875a06e3c01882e8d7a5090926eb430d0db2b75";
export const RAIL_RESEARCH_TOOL = "tools/map-factory/integrate_rail_research.py";
export const RAIL_RESEARCH_TOOL_SHA = "a49282eeb69b970f5204fa734cf5f46709b61f5c72af32a66dacda7ccde27f26";
export const RAIL_RESEARCH_SOURCES = "tools/map-factory/capability-evidence/rail-research-sources.json";
export const RAIL_RESEARCH_SOURCES_SHA = "00bab93bfa5a6884567f1e46845fa863ba8a2bf1fb2c46c5ee3586f58c77247b";
export const RAIL_EVIDENCE_PREFIX = "tools/map-factory/capability-evidence/";

const EXPECTED = {
  "rail-query-model-v1": {
    kind: "query_scoped_rail_reachability_study",
    commit: "364628b81701c134e3f469f9e175c4fe40f7a311",
    base: "1a0e45c65745ba5f05cf22f947da2e88fed25277",
    publication_files: 29,
    copied_files: 19,
    linked_files: 10,
    rows: 276,
    rules: 28,
    labels: { exact_path_success: 27, selected_query_failure: 249 },
    counterexamples: 5,
  },
  "rail-junction-fit-v1": {
    kind: "export_tangent_junction_study",
    commit: "49cf49516f4aa8b24a154d9923c1a6fd149bf1a3",
    base: "364628b81701c134e3f469f9e175c4fe40f7a311",
    publication_files: 18,
    copied_files: 10,
    linked_files: 8,
    rows: 276,
    rules: 58,
    counterexamples: 5,
  },
  "rail-stock-holdout-v1": {
    kind: "frozen_stock_rule_holdout_study",
    commit: "914c153687106197e5f3a745d3ff7e181181ea8a",
    base: "49cf49516f4aa8b24a154d9923c1a6fd149bf1a3",
    publication_files: 159,
    copied_files: 16,
    linked_files: 143,
    rows: 48,
    raw_files: 136,
    unsupported_packages: 4,
    freeze_sha256: "20dfb33d863deb4fd13abcbeb952a59e139f93910216771c74fd21c069935a18",
  },
};

const fail = (message) => {
  throw new Error(message);
};

const requestText = (request) => `${request.from.join(",")}→${request.to.join(",")}`;

/** Every repo-relative file the page serves for these studies, plus the projection. */
export function railResearchFiles(studies) {
  const files = [RAIL_RESEARCH_PROJECTION, RAIL_RESEARCH_SOURCES];
  for (const study of studies ?? Object.values(railResearch().studies)) files.push(...study.files.map((file) => file.path));
  return [...new Set(files)];
}

/**
 * Re-check the projection, its tool and its source manifest, then every carried
 * evidence file. A changed byte anywhere fails before the page is built.
 */
export function railResearch(load = read) {
  if (sha(load(RAIL_RESEARCH_TOOL)) !== RAIL_RESEARCH_TOOL_SHA) fail("Rail research projection tool changed");
  if (sha(load(RAIL_RESEARCH_SOURCES)) !== RAIL_RESEARCH_SOURCES_SHA) fail("Rail research source manifest changed");
  const bytes = load(RAIL_RESEARCH_PROJECTION);
  const projectionSha = sha(bytes);
  if (projectionSha !== RAIL_RESEARCH_PROJECTION_SHA) fail("Rail research projection changed");
  const projection = JSON.parse(bytes.toString("utf8"));
  if (projection.schema !== 1) fail("Rail research projection header changed");
  if (JSON.stringify(Object.keys(projection.studies)) !== JSON.stringify(RAIL_RESEARCH_STUDIES))
    fail("Rail research studies are not the three accepted publications");
  if (projection.source_manifest[RAIL_RESEARCH_STUDIES[0]].sha256 !== RAIL_RESEARCH_SOURCES_SHA)
    fail("Rail research projection does not bind the carried source manifest");

  const studies = {};
  const summary = {};
  for (const id of RAIL_RESEARCH_STUDIES) {
    const study = projection.studies[id];
    const expected = EXPECTED[id];
    if (study.study !== id || study.kind !== expected.kind) fail(`${id}: study identity changed`);
    if (study.source.publication_commit !== expected.commit || study.source.publication_base !== expected.base)
      fail(`${id}: source identity changed`);
    if (study.closure.publication_files !== expected.publication_files ||
        study.closure.copied_files !== expected.copied_files ||
        study.closure.linked_files !== expected.linked_files ||
        study.closure.commit !== expected.commit ||
        study.closure.prefix !== `${RAIL_EVIDENCE_PREFIX}${id}`)
      fail(`${id}: publication file scope changed`);
    if (!study.evidence_only || study.certificates !== "none") fail(`${id}: study is not evidence only`);
    if (!Array.isArray(study.files) || study.files.length !== expected.copied_files)
      fail(`${id}: carried evidence count changed`);
    for (const file of study.files) {
      if (!file.path.startsWith(`${RAIL_EVIDENCE_PREFIX}${id}/`)) fail(`${id}: carried evidence outside the study prefix`);
      if (!/^[a-f0-9]{64}$/.test(file.sha256 ?? "")) fail(`${id}: carried evidence lacks a hash`);
      const raw = load(file.path);
      if (raw.length !== file.bytes || sha(raw) !== file.sha256) fail(`${id}: carried evidence changed: ${file.path}`);
    }
    const present = new Set(study.files.map((file) => file.path));
    if (!study.documents.every((path) => present.has(path))) fail(`${id}: a document is not carried evidence`);
    if (study.selection.selected_queries !== expected.rows || study.rows.length !== expected.rows)
      fail(`${id}: selected row set changed`);

    if (id === "rail-query-model-v1") {
      if (Object.keys(study.rules.all).length !== expected.rules) fail(`${id}: rule count changed`);
      if (!isDeepStrictEqual(study.selection.labels, expected.labels)) fail(`${id}: label counts changed`);
      const fitted = study.rules.all[study.rules.fitted];
      if (fitted.counts.tp !== 26 || fitted.counts.fp !== 4 || fitted.counts.tn !== 245 || fitted.counts.fn !== 1)
        fail(`${id}: fitted confusion changed`);
      const primary = study.rules.all[study.rules.primary];
      if (primary.counts.tp !== 11 || primary.counts.fp !== 198 || primary.counts.tn !== 51 || primary.counts.fn !== 16)
        fail(`${id}: primary confusion changed`);
      const split = study.rules.split_totals[study.rules.fitted];
      if (split.stock_controls.tp !== 16 || split.stock_controls.fp !== 0 ||
          split.stock_controls.tn !== 16 || split.stock_controls.fn !== 0 ||
          split.cohort.tp !== 10 || split.cohort.fp !== 4 || split.cohort.tn !== 229 || split.cohort.fn !== 1)
        fail(`${id}: control and cohort groups are not separate`);
      if (study.counterexamples.length !== expected.counterexamples) fail(`${id}: fitted counterexamples changed`);
      if (study.runtime.export_bridge.status !== "bridge_established") fail(`${id}: export bridge is not established`);
    }
    if (id === "rail-junction-fit-v1") {
      if (Object.keys(study.rules.all).length !== expected.rules) fail(`${id}: rule count changed`);
      const tangent = study.rules.all[study.rules.fitted].all.counts;
      if (tangent.tp !== 27 || tangent.fp !== 0 || tangent.tn !== 249 || tangent.fn !== 0)
        fail(`${id}: tangent confusion changed`);
      const reference = study.rules.all[study.rules.reference].all.counts;
      if (reference.tp !== 26 || reference.fp !== 4 || reference.tn !== 245 || reference.fn !== 1)
        fail(`${id}: reference confusion changed`);
      if (!isDeepStrictEqual(study.rules.all[study.rules.chord_reimplementation].all.counts, reference))
        fail(`${id}: chord reimplementation diverged from the reference`);
      const selected = study.rules.pooled_out_of_fold.cohort.selected.counts;
      if (selected.tp !== 10 || selected.fp !== 4 || selected.tn !== 229 || selected.fn !== 1)
        fail(`${id}: strict package-held-out selection changed`);
      const correspondence = study.rules.pooled_out_of_fold.cohort.correspondence.counts;
      if (correspondence.tp !== 11 || correspondence.fp !== 0 || correspondence.tn !== 233 || correspondence.fn !== 0)
        fail(`${id}: predeclared counterpart changed`);
      const paired = study.rules.paired.all;
      if (paired.rows !== 276 || paired.both_correct !== 271 || paired.right_only_correct !== 5 ||
          paired.left_only_correct !== 0 || paired.both_wrong !== 0)
        fail(`${id}: paired comparison changed`);
      if (study.rules.selection.rule !== study.rules.fitted) fail(`${id}: descriptive selection changed`);
      if (study.counterexamples[study.rules.reference].length !== expected.counterexamples ||
          study.counterexamples[study.rules.fitted].length !== 0)
        fail(`${id}: retained counterexamples changed`);
      if (study.runtime.export_bridge.tangents.native_attested !== false)
        fail(`${id}: tangents are no longer declared export-derived`);
    }
    if (id === "rail-stock-holdout-v1") {
      if (study.freeze.sha256 !== expected.freeze_sha256) fail(`${id}: freeze changed`);
      if (study.freeze.discordant_predictions !== 0) fail(`${id}: a discordant prediction was recorded`);
      if (study.selection.supported_packages !== 6 ||
          study.selection.unsupported_packages !== expected.unsupported_packages)
        fail(`${id}: package support changed`);
      if (study.selection.inventory !== 105 || study.selection.excluded_hashes.length !== 11)
        fail(`${id}: selection inventory changed`);
      if (study.runtime.raw_retention.files !== expected.raw_files) fail(`${id}: retained raw file count changed`);
      const tables = study.rules.tables;
      for (const name of Object.keys(tables)) {
        for (const rule of study.rules.rules) {
          const counts = tables[name].all[rule].counts;
          if (counts.tp !== 40 || counts.fp !== 0 || counts.tn !== 8 || counts.fn !== 0 || counts.requests !== 48)
            fail(`${id}: ${name} ${rule} confusion changed`);
        }
      }
    }
    const labels = { success: 0, no_path: 0, unknown: 0 };
    const failurePackages = new Set();
    for (const row of study.rows) {
      labels[row.observed] = (labels[row.observed] ?? 0) + 1;
      if (row.observed === "no_path") failurePackages.add(row.opening);
      if (!row.id || !row.request || !row.predicted) fail(`${id}: incomplete selected row`);
      for (const rule of Object.keys(row.predicted)) {
        if (!["success", "no_path", "unknown"].includes(row.predicted[rule])) fail(`${id}: unknown prediction label`);
      }
    }
    if (id === "rail-stock-holdout-v1") {
      if (labels.success !== 40 || labels.no_path !== 8 || labels.unknown !== 0) fail(`${id}: row labels changed`);
      if (failurePackages.size !== 1 || !failurePackages.has("holdout-02")) fail(`${id}: failures are not one package`);
      for (const row of study.rows) {
        if (row.predicted["tangent:continuation:any_lane"] !== row.predicted["chord:continuation:any_lane"])
          fail(`${id}: the two rules disagree on a request`);
        if (row.snapshot_matched !== true) fail(`${id}: lost a snapshot-matched row`);
      }
      for (const control of study.controls) {
        if (!control.invalid_pair_rejected) fail(`${id}: a control lost its invalid-pair diagnostic`);
      }
    } else if (labels.success !== 27 || labels.no_path !== 249 || labels.unknown !== 0) {
      fail(`${id}: joined observation labels changed`);
    }
    if (id === "rail-junction-fit-v1") {
      const queryIds = new Set(projection.studies["rail-query-model-v1"].rows.map((row) => row.id));
      if (!study.rows.every((row) => queryIds.has(row.id))) fail(`${id}: studies select different requests`);
    }
    const freeze = {
      name: study.freeze.name,
      sha256: study.freeze.sha256 ?? null,
      frozen_before_observations: study.freeze.frozen_before_observations === true,
      discordant_predictions: study.freeze.discordant_predictions ?? null,
    };
    studies[id] = study;
    summary[id] = {
      kind: study.kind,
      study: id,
      source_commit: study.source.publication_commit,
      source_base: study.source.publication_base,
      source_issue: study.source.source_issue,
      pull_request: study.source.pull_request,
      internal_merge: study.source.internal_merge,
      publication_files: study.closure.publication_files,
      copied_files: study.closure.copied_files,
      linked_files: study.closure.linked_files,
      projection_file: RAIL_RESEARCH_PROJECTION,
      projection_sha256: projectionSha,
      projection_tool_file: RAIL_RESEARCH_TOOL,
      projection_tool_sha256: RAIL_RESEARCH_TOOL_SHA,
      source_manifest_file: RAIL_RESEARCH_SOURCES,
      source_manifest_sha256: RAIL_RESEARCH_SOURCES_SHA,
      freeze,
      selected_queries: study.selection.selected_queries,
      evidence_files_sha256: sha(JSON.stringify(study.files.map((file) => [file.path, file.sha256]))),
      certificates: "none",
    };
  }
  if (studies["rail-query-model-v1"].source.internal_merge !== "d008778fd44cf448b2078738468267e8a7863af0" ||
      studies["rail-junction-fit-v1"].source.internal_merge !== "fef279efb339d26d3cc86eddcf588f3f7611e290" ||
      studies["rail-stock-holdout-v1"].source.internal_merge !== null)
    fail("Rail research internal merge identity changed");
  if (studies["rail-junction-fit-v1"].source.publication_base !== studies["rail-query-model-v1"].source.publication_commit ||
      studies["rail-stock-holdout-v1"].source.publication_base !== studies["rail-junction-fit-v1"].source.publication_commit)
    fail("Rail research source chain changed");
  if (studies["rail-stock-holdout-v1"].freeze.query_source !== studies["rail-query-model-v1"].source.publication_commit ||
      studies["rail-stock-holdout-v1"].freeze.native_source !== studies["rail-query-model-v1"].source.publication_base)
    fail("Stock holdout does not name the accepted query and native sources");
  return { projection, studies, summary, sha: projectionSha };
}

/** The ledger keeps only this derived summary, never the rows themselves. */
export function validateRailResearch(ledger, load = read) {
  const { summary } = railResearch(load);
  if (!isDeepStrictEqual(ledger.rail_research_studies, summary))
    fail("Rail research projection is stale or unbound in the ledger");
  const rail = ledger.capabilities.find((capability) => capability.id === "rail");
  if (!isDeepStrictEqual(rail?.rail_research_studies, RAIL_RESEARCH_STUDIES))
    fail("Rail does not reference the three research studies");
  if ((ledger.native_path_certificates ?? []).some((certificate) => certificate.capability === "rail"))
    fail("A rail native certificate exists; these studies are evidence only");
  return summary;
}

const table = (escape, heads, rows, attrs = "") =>
  `<div class="ledger-table"><table ${attrs}><thead><tr>${heads.map((head) => `<th scope="col">${escape(head)}</th>`).join("")}</tr></thead><tbody>${rows
    .map((row) => `<tr>${row.map((value, index) => `<${index ? "td" : "th"}${index ? "" : ' scope="row"'}>${escape(value)}</${index ? "td" : "th"}>`).join("")}</tr>`)
    .join("")}</tbody></table></div>`;

const detail = (escape, title, value) =>
  `<details><summary>${escape(title)}</summary><pre>${escape(JSON.stringify(value, null, 2))}</pre></details>`;

const value = (flag) => (flag === null || flag === undefined ? "null" : flag);
const observedText = (label) =>
  label === "success" || label === "exact_path_success" ? "success"
    : label === "no_path" || label === "selected_query_failure" ? "complete failure"
      : "Unknown";
const counts = (confusion) => {
  const c = confusion.counts ?? confusion;
  const parts = [`TP ${value(c.tp)}`, `FP ${value(c.fp)}`, `TN ${value(c.tn)}`, `FN ${value(c.fn)}`];
  if ("abstain" in c) parts.push(`abstain ${value(c.abstain)}`);
  if ("unknown" in c) parts.push(`unknown ${value(c.unknown)}`);
  if ("requests" in c) parts.push(`requests ${value(c.requests)}`);
  return parts.join(" · ");
};
const rates = (confusion) => {
  const r = confusion.rates ?? confusion;
  const parts = [];
  for (const key of ["precision", "recall", "coverage", "specificity", "balanced_accuracy"]) {
    if (key in r) parts.push(`${key.replace("_", " ")} ${value(r[key])}`);
  }
  return parts.join(" · ");
};

function evidenceList(escape, study, base) {
  return `<ul>${study.files.map((file) => {
    const relative = file.path.slice(RAIL_EVIDENCE_PREFIX.length);
    return `<li><a data-evidence href="${escape(base + file.path)}" data-sha256="${escape(file.sha256)}">${escape(relative)}</a> · <code>${escape(file.sha256)}</code> · ${escape(file.role)}</li>`;
  }).join("")}</ul>`;
}

function sourceBlock(escape, study, summary) {
  const merge = study.source.internal_merge ? `internal merge ${study.source.internal_merge}` : "no internal merge; retained as the publication pin";
  return `<dl>
    <dt>Publication</dt><dd><code>${escape(study.source.publication_commit)}</code> on base <code>${escape(study.source.publication_base)}</code>, PR #${escape(study.source.pull_request)}; ${escape(merge)}.</dd>
    <dt>Source issue</dt><dd>${escape(study.source.source_issue)}</dd>
    <dt>Review</dt><dd>${escape(study.review.note)} Review ${escape(study.review.review_comment)}, acceptance ${escape(study.review.acceptance_comment)}${study.review.parent_acceptance_comment ? `, parent acceptance ${escape(study.review.parent_acceptance_comment)}` : ""}.</dd>
    <dt>Freeze</dt><dd>${escape(study.freeze.name)} · written before any observation: ${study.freeze.frozen_before_observations ? "yes" : "no"}${summary.freeze.frozen_at ? ` · frozen ${escape(summary.freeze.frozen_at)}` : ""}${summary.freeze.sha256 ? ` · <code>${escape(summary.freeze.sha256)}</code>` : ""}${summary.freeze.discordant_predictions != null ? ` · ${escape(String(summary.freeze.discordant_predictions))} discordant predictions` : ""}.</dd>
    <dt>File scope</dt><dd>${escape(String(study.closure.publication_files))} publication files: ${escape(String(study.closure.copied_files))} carried here byte for byte, ${escape(String(study.closure.linked_files))} linked as immutable Git blobs with SHA-256 and blob ids in <a href="${escape("./" + summary.source_manifest_file)}">the strict source manifest</a>.</dd>
  </dl>`;
}

function queryModelPage(escape, study) {
  const all = study.rules.all;
  const shown = ["always_fail", "always_candidate", "weak_component", "lane:any_lane:forbidden",
                 study.rules.primary, study.rules.fitted];
  const rows = [...new Set(shown)].map((rule) => [
    rule === study.rules.fitted ? `${rule} · fitted` : rule === study.rules.primary ? `${rule} · pre-registered primary` : rule,
    counts(all[rule]), rates(all[rule]),
  ]);
  const counterexampleRows = study.counterexamples.map((row) => [
    row.query_id, row.kind.replace("_", " "), observedText(row.observed), requestText(row.request),
    row.observed_detail?.length ?? "null",
  ]);
  const rowRows = study.rows.map((row) => [
    row.id, observedText(row.observed), row.predicted[study.rules.fitted], row.predicted[study.rules.primary],
    row.package, requestText(row.request),
  ]);
  return `<section data-rail-research="${escape(study.study)}">
    <h4>Query-scoped reachability fit · research only</h4>
    <p>${escape(study.scope)}</p>
    ${sourceBlock(escape, study, { ...study.closure, freeze: study.freeze, source_manifest_file: RAIL_RESEARCH_SOURCES })}
    <p>${escape(study.method)}</p>
    ${table(escape, ["Rule", "Confusion on 276 selected requests", "Derived rates"], rows, "data-rail-research-rules")}
    <p>Fitted ${escape(study.rules.fitted)}: ${escape(counts(all[study.rules.fitted]))}. Two facts matter more than that fit: every observed success is inside one weak Train component, and all 51 cross-component requests fail. Reachability is necessary, not sufficient. The five fitted errors are all in Pittsburgh; the four false positives are preserved with their exact requests.</p>
    ${table(escape, ["Query", "Kind", "Observed", "Request", "Length"], counterexampleRows, "data-rail-research-counterexamples")}
    <p>Labels over all 276 selected requests: ${escape(String(study.selection.labels.exact_path_success))} exact-path successes and ${escape(String(study.selection.labels.selected_query_failure))} selected failures. Pittsburgh left ${escape(String(study.selection.unqueried.pittsburgh))} candidates unqueried; Charleston, Grand Canyon and Yosemite have no directed pair. Those are Unknown, never "no railway".</p>
    <details><summary>All ${escape(String(Object.keys(all).length))} rule tables, with every null kept</summary>${table(escape, ["Rule", "Confusion", "Rates"],
      Object.keys(all).sort().map((rule) => [rule, counts(all[rule]), rates(all[rule])]))}${detail(escape, "Rule tables as data", all)}</details>
    <details><summary>Complete selected rows · ${escape(String(study.rows.length))} requests, joined to the retained native observation</summary>${table(escape, ["Query", "Observed", "Fitted", "Primary", "Package", "Request"], rowRows, "data-rail-research-rows")}</details>
    ${detail(escape, "Export bridge", study.runtime.export_bridge)}
    <details><summary>Carried evidence · ${escape(String(study.files.length))} files</summary>${evidenceList(escape, study, "")}</details>
    <p class=note>${escape(study.limits)}</p></section>`;
}

function junctionPage(escape, study) {
  const rules = study.rules;
  const rows = [
    ["Reference frozen junction rule", counts(rules.all[rules.reference].all), rates(rules.all[rules.reference].all)],
    ["Chord reimplementation", counts(rules.all[rules.chord_reimplementation].all), rates(rules.all[rules.chord_reimplementation].all)],
    ["Tangent continuation (fitted)", counts(rules.all[rules.fitted].all), rates(rules.all[rules.fitted].all)],
    ["Tangent orientation counterpart", counts(rules.all[rules.predeclared_counterpart].all), rates(rules.all[rules.predeclared_counterpart].all)],
  ];
  const outOfFold = rules.pooled_out_of_fold.cohort;
  const foldRows = rules.all && study.selection.folds.map((fold) => [
    fold.fold, fold.held_rows ?? "null", fold.selected,
  ]);
  const counterexampleRows = study.counterexamples[rules.reference].map((row) => [
    row.query_id, row.kind.replace("_", " "), observedText(row.label), requestText(row.request), row.label_detail?.length ?? "null",
  ]);
  const rowRows = study.rows.map((row) => [
    row.id, observedText(row.observed), row.predicted[rules.reference], row.predicted[rules.fitted],
    row.package, requestText(row.request),
  ]);
  return `<section data-rail-research="${escape(study.study)}">
    <h4>Export-tangent junction fit · research only</h4>
    <p>${escape(study.scope)}</p>
    ${sourceBlock(escape, study, { ...study.closure, freeze: study.freeze, source_manifest_file: RAIL_RESEARCH_SOURCES })}
    <p>${escape(study.method)}</p>
    ${table(escape, ["Rule", "Confusion on 276 selected requests", "Derived rates"], rows, "data-rail-research-rules")}
    <p>Paired on identical requests: ${escape(String(rules.paired.all.right_only_correct))} corrected, ${escape(String(rules.paired.all.left_only_correct))} broken, ${escape(String(rules.paired.all.both_correct))} both right, ${escape(String(rules.paired.all.not_comparable))} not comparable.</p>
    <p><strong>The honest counterweight.</strong> Strict leave-one-package-out selection picks the tangent rule in five of six cohort folds, but Pittsburgh is the only package that discriminates the rules and it is the fold where every remaining-perfect rule ties, so the predeclared tie-break reaches the chord rule. Pooled <em>selected</em> out-of-fold is therefore ${escape(counts(outOfFold.selected))} — identical to the reference — while the fixed tangent counterpart is ${escape(counts(outOfFold.correspondence))}. Neither number is a blind estimate.</p>
    ${table(escape, ["Fold held out", "Rows held", "Selected rule"], foldRows, "data-rail-research-folds")}
    <p>The tangent rule rejects two transitions on a real successful Pittsburgh path; the reference rejects three. Both transfer the retained counterexample, and the false negative's native path is reproduced by neither rule. This is a better fit, not an identified native junction law.</p>
    ${table(escape, ["Query", "Kind", "Observed", "Request", "Length"], counterexampleRows, "data-rail-research-counterexamples")}
    <details><summary>All ${escape(String(Object.keys(rules.all).length))} rules · all, cohort and stock-control confusion</summary>${table(escape, ["Rule", "All", "Cohort", "Stock controls"],
      Object.keys(rules.all).sort().map((rule) => [rule, counts(rules.all[rule].all), counts(rules.all[rule].cohort), counts(rules.all[rule].stock_controls)]), "data-rail-research-all-rules")}
      <p>Per-opening tables and every opening-level null stay in the projection and in the carried <code>evaluation.json</code>.</p></details>
    <details><summary>Complete selected rows · ${escape(String(study.rows.length))} requests</summary>${table(escape, ["Query", "Observed", "Reference", "Tangent", "Package", "Request"], rowRows, "data-rail-research-rows")}</details>
    ${detail(escape, "Export bridge", study.runtime.export_bridge)}
    <details><summary>Carried evidence · ${escape(String(study.files.length))} files</summary>${evidenceList(escape, study, "")}</details>
    <p class=note>${escape(study.limits)}</p></section>`;
}

function stockPage(escape, study) {
  const rules = study.rules;
  const tables = rules.tables;
  const ruleRows = rules.rules.map((rule) => [
    rule === "tangent:continuation:any_lane" ? `${rule} · fitted hypothesis` : `${rule} · reference`,
    counts(tables["all-complete intent-to-test"].all[rule]),
    counts(tables["snapshot-matched"].all[rule]),
  ]);
  const stratumRows = Object.entries(study.selection.strata).map(([name, stratum]) => [
    name, String(stratum.available ?? "null"), String(stratum.selected), String(stratum.requests),
    String(stratum.success), String(stratum.no_path), stratum.packages.join(", "),
  ]);
  const rowRows = study.rows.map((row) => [
    row.id, observedText(row.observed), row.predicted["tangent:continuation:any_lane"],
    row.predicted["chord:continuation:any_lane"], row.snapshot_matched ? "matched" : "not matched",
    row.package, requestText(row.request),
  ]);
  const controlRows = study.controls.map((control) => [
    control.slug, `${control.boundary_successes}/${control.boundary_requests}`,
    control.invalid_pair_rejected ? "rejected" : "not rejected", control.context_bound ? "bound" : "unbound",
    control.cleanup.game.length + control.cleanup.steam_instances.length + control.cleanup.units_active.length === 0 ? "empty" : "retained",
  ]);
  const field = study.runtime.field_audit;
  return `<section data-rail-research="${escape(study.study)}">
    <h4>Frozen stock rail holdout · research only</h4>
    <p>${escape(study.scope)}</p>
    ${sourceBlock(escape, study, { ...study.closure, freeze: study.freeze, source_manifest_file: RAIL_RESEARCH_SOURCES })}
    <p>${escape(study.method)}</p>
    ${table(escape, ["Rule", "All-complete intent-to-test", "Snapshot-matched"], ruleRows, "data-rail-research-rules")}
    <p>Both rules score ${escape(counts(tables["all-complete intent-to-test"].all[rules.rules[0]]))} on ${escape(String(study.selection.selected_queries))} completed requests. <strong>Their pre-query predictions were identical for all ${escape(String(study.selection.selected_queries))}, so this selection does not prefer tangent over chord.</strong> The eight failures all belong to one package (holdout-02) and are not eight independent votes.</p>
    ${table(escape, ["Stratum", "Available", "Selected", "Requests", "Success", "Failure", "Packages"], stratumRows, "data-rail-research-strata")}
    <p>Supported package coverage is ${escape(String(study.selection.supported_packages))}/${escape(String(study.selection.package_count))}. The ${escape(String(study.selection.unsupported_packages))} unsupported packages keep metadata-only captures and selected zero requests; they are not dropped or replaced.</p>
    ${table(escape, ["Control", "Boundary successes / requests", "Invalid pair", "Context", "Cleanup"], controlRows, "data-rail-research-controls")}
    <p>All ${escape(String(study.runtime.native_verification.openings.length))} openings have fresh process identities and empty game, Steam-instance and unit cleanup lists. The supported packages' 1,277 Train segments have no used-field mismatches; the unsupported packages retain ${escape(field.unsupported.map((entry) => `${entry.package}: ${entry.opening_mismatches}`).join(", "))} opening mismatches as coverage gaps, not scored failures.</p>
    <details><summary>All ${escape(String(Object.keys(rules.tables["all-complete intent-to-test"].packages).length))} package and stratum tables, with every null kept</summary>${detail(escape, "Scored tables as data", rules.tables)}</details>
    <details><summary>Complete selected rows · ${escape(String(study.rows.length))} requests</summary>${table(escape, ["Query", "Observed", "Tangent", "Chord", "Snapshot", "Package", "Request"], rowRows, "data-rail-research-rows")}</details>
    ${detail(escape, "Runtime, field audit and raw retention", study.runtime)}
    <details><summary>Carried evidence · ${escape(String(study.files.length))} files</summary>${evidenceList(escape, study, "")}</details>
    <p class=note>${escape(study.limits)}</p></section>`;
}

/** The three studies, rendered in one place under Rail, never pooled into a score. */
export function railResearchPage({ studies }, escape) {
  return `<section id="rail-research-studies" data-rail-research-studies>
    <h3>Accepted rail research · three separate typed studies · evidence only</h3>
    <p class=note>These are retrospective research results, kept apart from the current runtime estimate above. They are not pooled with the directed native study, not votes, not a fitted place-level promise and not rail activation candidates. Null denominators stay null; an unobserved or unsupported request is Unknown, never "no railway".</p>
    ${RAIL_RESEARCH_STUDIES.map((id) => (id === "rail-query-model-v1" ? queryModelPage(escape, studies[id])
      : id === "rail-junction-fit-v1" ? junctionPage(escape, studies[id]) : stockPage(escape, studies[id]))).join("")}
  </section>`;
}

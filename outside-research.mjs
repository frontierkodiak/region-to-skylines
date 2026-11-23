// One accepted outside-connection query-model publication, read from archived bytes only.
//
// This module never runs the study's model, predictor, collector, scorer, the
// game or the browser. It re-checks the projection, its manifest and every
// carried evidence byte, re-derives a compact summary of the projection, and
// renders the one study under Road, Ship and Air. It is a distinct typed study:
// not pooled with the native outside-v1/v2 studies, not a promise, not a
// certificate and not a live rule.
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";

const ROOT = fileURLToPath(new URL(".", import.meta.url));
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const read = (file) => readFileSync(ROOT + file);

export const OUTSIDE_RESEARCH_STUDY = "outside-query-model-v1";
export const OUTSIDE_RESEARCH_PROJECTION = "tools/map-factory/capability-evidence/outside-research-studies.json";
export const OUTSIDE_RESEARCH_PROJECTION_SHA = "8c3e785d26bf864f325d78de8b543008870d2816f8608a940c1b94947cb115e4";
export const OUTSIDE_RESEARCH_TOOL = "tools/map-factory/integrate_outside_research.py";
export const OUTSIDE_RESEARCH_TOOL_SHA = "4ac7e82fe17bd4a04fab4ceb9201bc3e9c219d0cea5f34477fe7ad92e509662b";
export const OUTSIDE_RESEARCH_SOURCES = "tools/map-factory/capability-evidence/outside-research-sources.json";
export const OUTSIDE_RESEARCH_SOURCES_SHA = "bfe001f5a450fb8166ff9131dba92de1a313883694920cf1450ef31c4bf63f7e";
export const OUTSIDE_EVIDENCE_PREFIX = "tools/map-factory/capability-evidence/";
export const OUTSIDE_PUBLICATION = "030db86ce470b972b6ef3462a2698744dff40ebb";
export const OUTSIDE_REPO = "https://github.com/frontierkodiak/region-to-skylines/blob/";

const RULES = [
  "always_fail",
  "always_candidate",
  "weak_component",
  "directed_segment",
  "lane:any_lane:forbidden",
  "lane:any_lane:allowed",
  "lane:index_same:forbidden",
  "lane:index_same:allowed",
  "lane:index_mirror:forbidden",
  "lane:orientation_index:forbidden",
  "lane:orientation_index:allowed",
  "lane:orientation_mirror:forbidden",
];
const MODES = ["road", "ship", "air"];
const FITTED = "directed_segment";
const PRIMARY = "lane:any_lane:forbidden";

const EXPECTED = {
  kind: "outside_connection_query_model_study",
  publication_files: 21,
  copied_files: 18,
  linked_files: 3,
  rows: 876,
  eligible: 378,
  primary: 342,
  same_edge: 36,
  anomalies: 3,
  disagreements: 19,
  packages: 9,
  primary_counts: [93, 19, 230, 0],
  same_edge_counts: [9, 0, 27, 0],
  modes: { road: [316, 67, 19, 230, 0], ship: [16, 16, 0, 0, 0], air: [10, 10, 0, 0, 0] },
  bridge: {
    segments_native: 27191,
    nodes_native: 26633,
    chords_equal_within_2pct: 27136,
    chords_equal_within_20pct: 27191,
    outside_nodes_equal: 26633,
  },
  freeze_sha256: "3c38dd19b38fadc90b2e2b0240b2e6a35ad13c2953c591e8cc71270e9a2cfc11",
  collector_sha256: "d644218e8969f40737ce08367a3a3e4c9adb6a550ba145fb3bf220ffa5f23813",
  candidate_linked: ["inventory.json", "predictions.json", "requests.json"],
};

const fail = (message) => {
  throw new Error(message);
};

const counts = (confusion) => {
  const c = confusion.counts ?? confusion;
  return [`TP ${c.tp}`, `FP ${c.fp}`, `TN ${c.tn}`, `FN ${c.fn}`].join(" · ");
};
const rates = (confusion) => {
  const r = confusion.rates ?? confusion;
  const parts = [];
  for (const key of ["precision", "recall", "f1", "coverage"]) {
    if (key in r) parts.push(`${key} ${r[key] === null ? "null" : r[key]}`);
  }
  return parts.join(" · ");
};

/** Every repo-relative file the page serves for this study, plus its projection. */
export function outsideResearchFiles(study) {
  const files = [OUTSIDE_RESEARCH_PROJECTION, OUTSIDE_RESEARCH_SOURCES];
  for (const record of (study ?? outsideResearch().study).files) files.push(record.path);
  return [...new Set(files)];
}

/**
 * Re-check the projection, its tool and its source manifest, then every carried
 * evidence file and every declaration it publishes. A changed byte anywhere
 * fails before the page is built.
 */
export function outsideResearch(load = read) {
  if (sha(load(OUTSIDE_RESEARCH_TOOL)) !== OUTSIDE_RESEARCH_TOOL_SHA) fail("Outside research projection tool changed");
  if (sha(load(OUTSIDE_RESEARCH_SOURCES)) !== OUTSIDE_RESEARCH_SOURCES_SHA) fail("Outside research source manifest changed");
  const bytes = load(OUTSIDE_RESEARCH_PROJECTION);
  const projectionSha = sha(bytes);
  if (projectionSha !== OUTSIDE_RESEARCH_PROJECTION_SHA) fail("Outside research projection changed");
  const projection = JSON.parse(bytes.toString("utf8"));
  if (projection.schema !== 1) fail("Outside research projection header changed");
  if (JSON.stringify(Object.keys(projection.studies)) !== JSON.stringify([OUTSIDE_RESEARCH_STUDY]))
    fail("Outside research projection is not the one accepted publication");
  const study = projection.studies[OUTSIDE_RESEARCH_STUDY];
  const manifest = JSON.parse(load(OUTSIDE_RESEARCH_SOURCES).toString("utf8"));
  const publication = manifest.publications?.[OUTSIDE_RESEARCH_STUDY];
  if (!publication) fail("Outside research source manifest lost its publication");
  if (projection.source_manifest.file !== OUTSIDE_RESEARCH_SOURCES ||
      projection.source_manifest.sha256 === undefined ||
      projection.source_manifest.commit !== OUTSIDE_PUBLICATION)
    fail("Outside research projection does not bind the carried source manifest");
  if (publication.commit !== OUTSIDE_PUBLICATION) fail("Outside research source manifest names another publication");

  if (study.study !== OUTSIDE_RESEARCH_STUDY || study.kind !== EXPECTED.kind) fail("Outside research study identity changed");
  if (study.evidence_only !== true || study.certificates !== "none") fail("Outside research study is not evidence only");
  const source = study.source;
  if (source.publication_commit !== OUTSIDE_PUBLICATION || source.publication_base !== "49cf49516f4aa8b24a154d9923c1a6fd149bf1a3" ||
      source.accepted_base !== "49cf49516f4aa8b24a154d9923c1a6fd149bf1a3" ||
      source.internal_merge !== "f6c73b17a9b211c6887ede23d313545caac3735b" ||
      source.pull_request !== 87 || source.branch !== "PL-1249-outside-models" ||
      source.source_issue !== "01a2006b-105d-7bc7-af9e-c3e42ea9c944")
    fail("Outside research source identity changed");
  if (!isDeepStrictEqual(source.native_sources,
    { outside_v1: "4cef6fb620f403c603e597a46f3bb7d7e5feadb7", targeted_v2: "29b095475ba2f93c7e918fefc08c736493670304" }))
    fail("Outside research native sources changed");

  const closure = study.closure;
  if (closure.publication_files !== EXPECTED.publication_files ||
      closure.copied_files !== EXPECTED.copied_files ||
      closure.linked_files !== EXPECTED.linked_files ||
      closure.commit !== OUTSIDE_PUBLICATION ||
      closure.prefix !== `${OUTSIDE_EVIDENCE_PREFIX}${OUTSIDE_RESEARCH_STUDY}`)
    fail("Outside research publication file scope changed");
  const carriedRelative = study.files.map((record) => record.path.slice(closure.prefix.length + 1)).sort();
  if (Object.keys(publication.files).length !== EXPECTED.publication_files ||
      publication.copied.length !== EXPECTED.copied_files ||
      publication.linked.length !== EXPECTED.linked_files ||
      JSON.stringify([...publication.copied].sort()) !== JSON.stringify(carriedRelative) ||
      JSON.stringify([...publication.linked].sort()) !== JSON.stringify([...EXPECTED.candidate_linked].sort()))
    fail("Outside research source manifest file split changed");

  // Carried bytes: exactly the publication's non-bulk files.
  if (!Array.isArray(study.files) || study.files.length !== EXPECTED.copied_files)
    fail("Outside research carried evidence count changed");
  for (const record of study.files) {
    if (!record.path.startsWith(`${OUTSIDE_EVIDENCE_PREFIX}${OUTSIDE_RESEARCH_STUDY}/`))
      fail("Outside research carried evidence outside the study prefix");
    if (!/^[a-f0-9]{64}$/.test(record.sha256 ?? "") || !/^[a-f0-9]{40}$/.test(record.git_blob ?? ""))
      fail(`${record.path}: carried evidence lacks a hash`);
    const raw = load(record.path);
    if (raw.length !== record.bytes || sha(raw) !== record.sha256)
      fail(`Outside research carried evidence changed: ${record.path}`);
    const published = publication.files[record.path.slice(closure.prefix.length + 1)];
    if (!published || published.sha256 !== record.sha256 || published.git_blob !== record.git_blob ||
        published.bytes !== record.bytes)
      fail(`${record.path}: carried evidence does not match the source manifest`);
  }
  const present = new Set(study.files.map((record) => record.path));
  for (const path of study.documents) {
    if (!present.has(`${closure.prefix}/${path}`)) fail("Outside research lost a carried document");
  }

  // Linked bulk sources: pinned, corroborated by at least two carried declarations, and not served here.
  if (!Array.isArray(study.linked) || study.linked.length !== EXPECTED.linked_files)
    fail("Outside research linked source count changed");
  for (const record of study.linked) {
    const relative = record.path.slice(closure.prefix.length + 1);
    if (!EXPECTED.candidate_linked.includes(relative)) fail("Outside research linked a file outside the bulk set");
    const published = publication.files[relative];
    if (!published || published.sha256 !== record.sha256 || published.git_blob !== record.git_blob)
      fail(`${record.path}: linked source does not match the source manifest`);
    if (!Array.isArray(record.declared_by) || record.declared_by.length < 2)
      fail(`${record.path}: linked source is not corroborated by two carried documents`);
    if (!isDeepStrictEqual(record.declared_by, study.declarations[relative]))
      fail(`${record.path}: linked source provenance changed`);
    // A linked file must not be duplicated in the repository.
    if (existsSync(ROOT + record.path)) fail(`${record.path}: a linked file is duplicated in the repository`);
  }

  // Protocol and freeze.
  const protocol = study.protocol;
  if (protocol.model_version !== OUTSIDE_RESEARCH_STUDY || protocol.primary_rule !== PRIMARY || protocol.rules_per_mode !== 12)
    fail("Outside research protocol header changed");
  if (!isDeepStrictEqual(protocol.rules, RULES)) fail("Outside research rule family changed");
  if (protocol.predictions_sha256 !== EXPECTED.freeze_sha256) fail("Outside research frozen prediction hash changed");
  if (protocol.predictions_bytes !== 845394 || protocol.prediction_count !== EXPECTED.eligible)
    fail("Outside research frozen prediction size changed");
  if (protocol.domain.collector_source.sha256 !== EXPECTED.collector_sha256)
    fail("Outside research collector identity changed");
  const domain = protocol.domain;
  if (domain.mode_vehicle.road !== "Car" || domain.mode_vehicle.ship !== "Ship" || domain.mode_vehicle.air !== "Plane" ||
      domain.category_by_mode.road !== "PassengerCar" || domain.category_by_mode.ship !== "All" || domain.category_by_mode.air !== "All" ||
      JSON.stringify(domain.accepted_lane_types.road) !== JSON.stringify(["Vehicle"]) ||
      JSON.stringify(domain.accepted_lane_types.ship) !== JSON.stringify(["CargoVehicle", "TransportVehicle", "Vehicle"]) ||
      JSON.stringify(domain.accepted_lane_types.air) !== JSON.stringify(["CargoVehicle", "TransportVehicle", "Vehicle"]))
    fail("Outside research protocol domain is not the corrected per-mode protocol");
  if (!protocol.protocol_copied_from_source.includes("seed 857") ||
      !protocol.protocol_copied_from_source.includes("maxLength 100000"))
    fail("Outside research protocol text changed");
  const freeze = study.freeze;
  if (freeze.retrospective !== true || freeze.frozen_before_observations !== false || freeze.observation_dates !== "unknown")
    fail("Outside research freeze claims more than the evidence");
  if (freeze.predictions_sha256 !== EXPECTED.freeze_sha256) fail("Outside research freeze hash changed");

  // The rows and every table re-derived from them.
  const rows = study.rows;
  if (!Array.isArray(rows) || rows.length !== EXPECTED.rows) fail("Outside research row count changed");
  const ids = new Set();
  let eligible = 0, primary = 0, sameEdge = 0, literal = 0;
  for (const row of rows) {
    if (ids.has(row.id)) fail(`Outside research duplicate row ${row.id}`);
    ids.add(row.id);
    if (!MODES.includes(row.mode)) fail(`${row.id}: unknown mode`);
    if (!["primary_distinct_edge", "same_edge", "midpoint_diagnostic", "unclassified_protocol",
          "archived_player_run", "unrequested"].includes(row.stratum)) fail(`${row.id}: unknown stratum`);
    if (row.request !== null) literal += 1;
    if (!row.eligible) {
      if (!row.exclusion) fail(`${row.id}: excluded row without a reason`);
      continue;
    }
    eligible += 1;
    if (row.stratum === "primary_distinct_edge") primary += 1;
    if (row.stratum === "same_edge") sameEdge += 1;
    if (!["success", "failure"].includes(row.label)) fail(`${row.id}: eligible row without a label`);
    if (JSON.stringify(Object.keys(row.predicted)) !== JSON.stringify(RULES)) fail(`${row.id}: prediction rule set changed`);
    for (const label of Object.values(row.predicted)) {
      if (!["success", "no_path", "unknown", "abstain"].includes(label)) fail(`${row.id}: unknown prediction label`);
    }
  }
  if (eligible !== EXPECTED.eligible || primary !== EXPECTED.primary || sameEdge !== EXPECTED.same_edge || literal !== 820)
    fail("Outside research scored row sets changed");

  const tally = (selection, rule) => {
    const counts = { tp: 0, fp: 0, tn: 0, fn: 0 };
    for (const row of selection) {
      const prediction = row.predicted[rule];
      const label = row.label;
      if (prediction === "success" && label === "success") counts.tp += 1;
      else if (prediction === "success" && label === "failure") counts.fp += 1;
      else if (prediction === "no_path" && label === "failure") counts.tn += 1;
      else if (prediction === "no_path" && label === "success") counts.fn += 1;
    }
    return [counts.tp, counts.fp, counts.tn, counts.fn];
  };
  const primaryRows = rows.filter((row) => row.eligible && row.stratum === "primary_distinct_edge");
  const sameRows = rows.filter((row) => row.eligible && row.stratum === "same_edge");
  const allRows = rows.filter((row) => row.eligible);
  if (JSON.stringify(tally(primaryRows, FITTED)) !== JSON.stringify(EXPECTED.primary_counts))
    fail("Outside research primary confusion changed");
  if (JSON.stringify(tally(primaryRows, PRIMARY)) !== JSON.stringify(EXPECTED.primary_counts))
    fail("Outside research primary rule is no longer tied with the fitted rule");
  if (JSON.stringify(tally(sameRows, FITTED)) !== JSON.stringify(EXPECTED.same_edge_counts))
    fail("Outside research same-edge confusion changed");
  for (const mode of MODES) {
    const expected = EXPECTED.modes[mode];
    const selected = primaryRows.filter((row) => row.mode === mode);
    const got = [selected.length, tally(selected, FITTED)[0], ...tally(selected, FITTED).slice(1)];
    if (JSON.stringify(got) !== JSON.stringify(expected)) fail(`Outside research ${mode} confusion changed`);
    const table = study.rules.primary_stratum[FITTED].counts;
    if (mode === "road" && JSON.stringify([table.tp, table.fp, table.tn, table.fn]) !== JSON.stringify(EXPECTED.primary_counts))
      fail("Outside research projection tables disagree with its rows");
  }
  if (JSON.stringify(tally(allRows, FITTED)) !== JSON.stringify([102, 19, 257, 0]))
    fail("Outside research all-eligible confusion changed");
  for (const rule of RULES) {
    const counts = study.rules.primary_stratum[rule].counts;
    if (JSON.stringify([counts.tp, counts.fp, counts.tn, counts.fn]) !== JSON.stringify(tally(primaryRows, rule)))
      fail(`Outside research ${rule} table disagrees with its rows`);
  }

  if (!Array.isArray(study.folds) || study.folds.length !== 6) fail("Outside research fold set changed");
  if (!study.folds.every((fold) => fold.selected_rule === FITTED)) fail("Outside research selection changed");
  if (!Array.isArray(study.disagreements) || study.disagreements.length !== EXPECTED.disagreements)
    fail("Outside research disagreement count changed");
  if (!study.disagreements.every((row) => row.relation === "false_positive" && row.mechanism_status === "unknown" &&
    row.native.flags === 8 && row.native.length === 100000 && row.native.success === false))
    fail("Outside research disagreements changed");
  if (!Array.isArray(study.exclusions) || study.exclusions.length !== 498) fail("Outside research excluded rows changed");
  if (!Array.isArray(study.anomalies) || study.anomalies.length !== EXPECTED.anomalies)
    fail("Outside research anomaly count changed");
  if (study.selection.queries !== EXPECTED.rows || study.selection.eligible !== EXPECTED.eligible ||
      study.selection.primary !== EXPECTED.primary || study.selection.same_edge !== EXPECTED.same_edge ||
      study.selection.literal_request_rows !== 820 || study.selection.packages !== EXPECTED.packages)
    fail("Outside research selection summary changed");
  if (JSON.stringify(study.bridge.totals.segments_native) !== JSON.stringify(EXPECTED.bridge.segments_native) ||
      study.bridge.totals.nodes_native !== EXPECTED.bridge.nodes_native ||
      study.bridge.totals.chords_equal_within_2pct !== EXPECTED.bridge.chords_equal_within_2pct ||
      study.bridge.totals.chords_equal_within_20pct !== EXPECTED.bridge.chords_equal_within_20pct ||
      study.bridge.totals.outside_nodes_equal !== EXPECTED.bridge.outside_nodes_equal ||
      study.bridge.answer !== "yes" || study.bridge.catalog.prefabs !== 12)
    fail("Outside research bridge summary changed");
  if (!study.limits.includes("19 road false positives") || !study.limits.includes("stays Unknown") ||
      !study.limits.includes("not blind or global accuracy"))
    fail("Outside research limits lost a bound");
  if (!study.method.includes("No scorer, predictor or native run is repeated"))
    fail("Outside research method claims a replay");

  const summary = {
    kind: study.kind,
    study: study.study,
    source_commit: source.publication_commit,
    source_base: source.publication_base,
    internal_merge: source.internal_merge,
    source_issue: source.source_issue,
    pull_request: source.pull_request,
    publication_files: closure.publication_files,
    copied_files: closure.copied_files,
    linked_files: closure.linked_files,
    projection_file: OUTSIDE_RESEARCH_PROJECTION,
    projection_sha256: projectionSha,
    projection_tool_file: OUTSIDE_RESEARCH_TOOL,
    projection_tool_sha256: OUTSIDE_RESEARCH_TOOL_SHA,
    source_manifest_file: OUTSIDE_RESEARCH_SOURCES,
    source_manifest_sha256: OUTSIDE_RESEARCH_SOURCES_SHA,
    freeze: {
      name: freeze.name,
      frozen_at: freeze.frozen_at,
      predictions_sha256: freeze.predictions_sha256,
      retrospective: true,
      frozen_before_observations: false,
      observation_dates: "unknown",
    },
    selected_queries: study.selection.eligible,
    primary_queries: study.selection.primary,
    rows: study.selection.queries,
    packages: study.selection.packages,
    modes: Object.fromEntries(MODES.map((mode) => [mode, {
      primary: study.modes[mode].primary,
      successes: study.modes[mode].successes,
      failures: study.modes[mode].failures,
      discrimination_estimable: study.modes[mode].discrimination_estimable,
      fitted: study.modes[mode].fitted[FITTED].counts,
    }])),
    primary_fitted: study.rules.primary_stratum[FITTED].counts,
    same_edge_fitted: study.rules.same_edge[FITTED].counts,
    evidence_files_sha256: sha(JSON.stringify(study.files.map((record) => [record.path, record.sha256]))),
    certificates: "none",
  };
  return { projection, study, summary, sha: projectionSha };
}

/** The ledger keeps only this derived summary, never the rows themselves. */
export function validateOutsideResearch(ledger, load = read) {
  const { study, summary } = outsideResearch(load);
  if (!isDeepStrictEqual(ledger.outside_research_studies, summary))
    fail("Outside research projection is stale or unbound in the ledger");
  for (const id of MODES) {
    const capability = ledger.capabilities.find((entry) => entry.id === id);
    if (!isDeepStrictEqual(capability?.outside_research_studies, [OUTSIDE_RESEARCH_STUDY]))
      fail(`${id} does not reference the outside research study`);
  }
  for (const other of ledger.capabilities.filter((entry) => !MODES.includes(entry.id))) {
    if (other.outside_research_studies) fail(`${other.id} references outside research it does not own`);
  }
  if ((ledger.native_path_certificates ?? []).some((certificate) => MODES.includes(certificate.capability) && certificate.study === OUTSIDE_RESEARCH_STUDY))
    fail("An outside-query-format native certificate exists; this study is evidence only");
  if (ledger.evidence_studies?.[OUTSIDE_RESEARCH_STUDY]) fail("The research study was registered as a native study");
  if ((ledger.native_path_certificates ?? []).length !== 4) fail("The retained native certificate set changed");
  if (study.evidence_only !== true) fail("The study is not evidence only");
  return summary;
}

const table = (escape, heads, rows, attrs = "") =>
  `<div class="ledger-table"><table ${attrs}><thead><tr>${heads.map((head) => `<th scope="col">${escape(head)}</th>`).join("")}</tr></thead><tbody>${rows
    .map((row) => `<tr>${row.map((value, index) => `<${index ? "td" : "th"}${index ? "" : ' scope="row"'}>${escape(value)}</${index ? "td" : "th"}>`).join("")}</tr>`)
    .join("")}</tbody></table></div>`;

const detail = (escape, title, value) =>
  `<details><summary>${escape(title)}</summary><pre>${escape(JSON.stringify(value, null, 2))}</pre></details>`;

const value = (flag) => (flag === null || flag === undefined ? "null" : flag);
const num = (digits) => Number(digits).toLocaleString("en-US");
const observedText = (label) => (label === "success" ? "success" : label === "failure" ? "failure" : "Unknown");
const requestText = (request) =>
  request ? `${request.from.join(",")}→${request.to.join(",")}` : "no request";

function evidenceList(escape, study) {
  return `<ul>${study.files.map((record) => {
    const relative = record.path.slice(OUTSIDE_EVIDENCE_PREFIX.length);
    return `<li><a data-evidence href="./${escape(record.path)}" data-sha256="${escape(record.sha256)}">${escape(relative)}</a> · <code>${escape(record.sha256)}</code> · ${escape(record.role)}</li>`;
  }).join("")}</ul>`;
}

function linkedList(escape, study) {
  return `<ul>${study.linked.map((record) => {
    const relative = record.path.slice(OUTSIDE_EVIDENCE_PREFIX.length);
    return `<li><a data-linked-evidence href="${escape(OUTSIDE_REPO + OUTSIDE_PUBLICATION + "/" + record.path)}" data-blob="${escape(record.git_blob)}">${escape(relative)}</a> · <code>${escape(record.sha256)}</code> · Git blob <code>${escape(record.git_blob)}</code> · ${escape(record.bytes)} bytes · ${escape(record.role)}<br>Declared by ${record.declared_by.map((where) => `<code>${escape(where)}</code>`).join(", ")}.</li>`;
  }).join("")}</ul>`;
}

function sourceBlock(escape, study) {
  const source = study.source;
  return `<dl>
    <dt>Publication</dt><dd><code>${escape(source.publication_commit)}</code> on base <code>${escape(source.publication_base)}</code>, PR #${escape(String(source.pull_request))}; internal merge <code>${escape(source.internal_merge)}</code>.</dd>
    <dt>Native sources</dt><dd>Outside v1 <code>${escape(source.native_sources.outside_v1)}</code>; targeted repeat <code>${escape(source.native_sources.targeted_v2)}</code>. This publication is a retrospective research result, not a native observation date.</dd>
    <dt>Source issue</dt><dd>${escape(source.source_issue)}</dd>
    <dt>Review</dt><dd>Independent PASS ${escape(source.review.pass)}, engineering note ${escape(source.review.engineering_note)}, parent acceptance ${escape(source.review.parent_acceptance)}.</dd>
    <dt>Freeze</dt><dd>${escape(study.freeze.name)} · protocol written at ${escape(study.freeze.frozen_at)} (the protocol file's timestamp, <strong>not</strong> an observation date) · retrospective: yes · frozen before the observations: no · observation dates: Unknown · carried predictions <code>${escape(study.freeze.predictions_sha256)}</code> · ${escape(String(study.freeze.predictions_bytes))} bytes.</dd>
    <dt>File scope</dt><dd>${escape(String(study.closure.publication_files))} publication files: ${escape(String(study.closure.copied_files))} carried here byte for byte, ${escape(String(study.closure.linked_files))} linked as immutable Git blobs with SHA-256 and blob ids in <a href="./${escape(OUTSIDE_RESEARCH_SOURCES)}">the strict source manifest</a>.</dd>
    <dt>Collector</dt><dd><code>${escape(study.protocol.domain.collector_source.path)}</code> at ${escape(study.protocol.domain.collector_source.revision)}, SHA-256 <code>${escape(study.protocol.domain.collector_source.sha256)}</code>, matching the retained build receipts per opening.</dd>
  </dl>`;
}

function primaryTable(escape, study) {
  const all = study.rules.primary_stratum;
  const shown = ["always_fail", "always_candidate", "weak_component", FITTED, PRIMARY,
                 "lane:index_same:forbidden", "lane:index_mirror:forbidden"];
  return [
    ...new Set(shown),
  ].map((rule) => {
    const name = rule === FITTED ? `${rule} · fitted` : rule === PRIMARY ? `${rule} · pre-registered primary` : rule;
    return [name, counts(all[rule]), rates(all[rule])];
  });
}

function modeRows(escape, study) {
  return MODES.map((mode) => {
    const record = study.modes[mode];
    const conf = record.fitted[FITTED];
    return [
      mode,
      String(record.primary),
      String(record.successes),
      String(record.failures),
      counts(conf),
      conf.rates.precision === null ? "null" : String(conf.rates.precision),
      record.discrimination_estimable ? "two classes" : "one class only",
    ];
  });
}

function groupRows(study) {
  return Object.entries(study.selection.groups).map(([name, group]) => [
    name, String(group.n), String(group.tp), String(group.fp), String(group.tn), String(group.fn), group.fidelity,
  ]);
}

function packageRows(study) {
  return Object.entries(study.selection.package_groups).map(([name, group]) => [
    name, String(group.n), String(group.tp), String(group.fp), String(group.tn), String(group.fn),
  ]);
}

function foldRows(study) {
  return study.folds.map((fold) => [
    fold.held_out, String(fold.held_out_rows), String(fold.successes), String(fold.failures),
    `TP ${fold.tp} · FP ${fold.fp} · TN ${fold.tn} · FN ${fold.fn}`, fold.selected_rule,
  ]);
}

function disagreementRows(escape, study) {
  return study.disagreements.map((row) => [
    row.query_id, observedText(row.native.success ? "success" : "failure"), row.relation,
    row.mechanism_status, String(value(row.native.flags)), String(value(row.native.length)),
    `${(row.path_lower_bound_length / 1000).toFixed(1)} km`,
  ]);
}

function rowTable(study) {
  return study.rows.map((row) => [
    row.id, row.mode, row.stratum, row.eligible ? observedText(row.label) : `excluded: ${row.exclusion}`,
    row.eligible ? row.predicted[FITTED] : "not scored", row.package, requestText(row.request),
  ]);
}

function exclusionRows(study) {
  return study.exclusions.map((row) => [
    row.query_id, row.mode, row.stratum, row.exclusion, row.label ?? "null",
  ]);
}

function bridgeRows(study) {
  return Object.entries(study.bridge.packages).map(([slug, record]) => [
    slug,
    String(record.segments_native),
    String(record.nodes_native),
    String(record.start_end_equal),
    String(record.lanes_equal),
    String(record.invert_equal),
    String(record.chords_equal_within_2pct),
    String(record.chords_equal_within_20pct),
    `${(record.chord_relative_error_max * 100).toFixed(2)}%`,
    record.mode_inputs_equal ? "identical" : "differ",
  ]);
}

/** The one study, rendered in one place, referenced from Road, Ship and Air. */
export function outsideResearchPage({ study }, escape) {
  const b = study.bridge;
  return `<article id="outside-research-study" data-outside-research>
    <div class="ledger-title"><h2>Outside-connection query model</h2><span>research only · evidence</span></div>
    <p class=note>One retrospective, query-scoped study of the accepted outside-v1 native rows, referenced from Road, Ship and Air. It is evidence only: not the current runtime estimate above, not pooled with the native outside-v1/v2 studies, not a vote, not a fitted place-level promise and not activation. A selected failure labels that exact request, never a place. No observation date is recorded, so every observation date is Unknown.</p>
    <p>${escape(study.scope)}</p>
    ${sourceBlock(escape, study)}
    <p>${escape(study.method)}</p>

    <h3>Primary stratum · distinct edges · all modes</h3>
    ${table(escape, ["Rule", "Confusion on 342 primary requests", "Derived rates"], primaryTable(escape, study), "data-outside-primary")}
    <p>The registered primary <code>${escape(PRIMARY)}</code> and the fitted <code>${escape(FITTED)}</code> are tied on this evidence at TP 93 / FP 19 / TN 230 / FN 0; the frozen rule order picks <code>${escape(FITTED)}</code>. That is a tie, not a proven equivalence: these requests do not distinguish lane continuity from segment-level directed reachability. ${escape(String(study.selection.same_edge))} same-edge requests score ${escape(counts(study.rules.same_edge[FITTED]))} under the fitted rule, kept separate from the primary stratum.</p>

    <h3>Per mode</h3>
    ${table(escape, ["Mode", "Primary", "Successes", "Failures", "Fitted confusion", "Precision", "Discrimination"], modeRows(escape, study), "data-outside-modes")}
    <p><strong>Ship and air are one class.</strong> Every complete retained request in those modes succeeded, so their arithmetic precision of 1 carries no information, no rule can be distinguished on them, and only their positive consistency is checked. That is a limit of the retained evidence, not a property of ships or aircraft.</p>

    <h3>Strata and study groups</h3>
    ${table(escape, ["Group", "n", "TP", "FP", "TN", "FN", "Fidelity"], groupRows(study), "data-outside-groups")}
    <p>${escape(String(study.selection.queries))} retained rows in total: ${escape(String(study.selection.primary))} distinct-edge primary, ${escape(String(study.selection.same_edge))} same-edge, ${escape(String(study.selection.by_stratum.midpoint_diagnostic))} correlated offset-128 midpoint repeats, ${escape(String(study.selection.by_stratum.unclassified_protocol))} earliest-collector rows with no <code>position_kind</code> (Unknown, not failures), ${escape(String(study.selection.by_stratum.archived_player_run))} archived player probes and ${escape(String(study.selection.by_stratum.unrequested))} unrequested rows, both excluded. All ${escape(String(study.selection.literal_request_rows))} rows that carry a literal request bind to their raw entries. No exclusion becomes a failure or an invented negative. Midpoints agree with their boundary sibling ${escape(String(study.selection.midpoint_repeats.agree))}/${escape(String(study.selection.midpoint_repeats.pairs))} and the ${escape(String(study.selection.cross_opening_repeats.pairs))} repeated openings of one package agree ${escape(String(study.selection.cross_opening_repeats.agree))}/${escape(String(study.selection.cross_opening_repeats.pairs))}: correlated repeats, never independent votes.</p>

    <h3>Per package · primary stratum</h3>
    ${table(escape, ["Package", "n", "TP", "FP", "TN", "FN"], packageRows(study), "data-outside-packages")}
    <p>Every false positive sits in the two targeted second openings (hong-kong and pittsburgh); the first openings have none.</p>

    <h3>Leave one package out</h3>
    ${table(escape, ["Held out", "n", "Successes", "Failures", "Held-out confusion", "Selected rule"], foldRows(study), "data-outside-folds")}
    <p>Selection is estimable in all six packages that carry a primary request, and every fold selects <code>${escape(FITTED)}</code> on the other five. Because the selected rule is the same in each, the held-out figures coincide with the pooled ones. These are retrospective folds, not a blind holdout.</p>

    <h3>Every disagreement</h3>
    ${table(escape, ["Query", "Native", "Relation", "Mechanism", "flags", "length", "Chord lower bound"], disagreementRows(escape, study), "data-outside-disagreements")}
    <p>All ${escape(String(study.disagreements.length))} are road false positives in two targeted second openings. Each returns <code>complete = true</code>, <code>released = true</code>, <code>success = false</code>, flags 8, length 100000 and no positions. The harness reads those fields from the failed path unit and reports no cause: the retained maximum-length sentinel is <strong>not</strong> proof that a search budget was exhausted, and all ${escape(String(study.disagreements.length))} failure mechanisms remain unknown. Their directed chord paths are 21.7–30.9 km while observed successes reach 35.6 km, so a simple length cutoff does not separate them. No threshold, place exception or post-hoc rule was added.</p>

    <details><summary>All 12 rules · primary, same-edge and every eligible row, with every null kept</summary>
      ${table(escape, ["Rule", "Primary (342)", "Same edge (36)", "All eligible (378)"],
        RULES.map((rule) => [rule, counts(study.rules.primary_stratum[rule]), counts(study.rules.same_edge[rule]), counts(study.rules.all_eligible[rule])]), "data-outside-all-rules")}
      <p>The rules form ${escape(String(Object.keys(study.rules.identical).length))} equivalence classes per mode on this evidence; the full grouped rates and every null stay in the carried <code>evaluation.json</code>.</p>
      ${detail(escape, "Rule tables as data", {
        primary: study.rules.primary_stratum,
        same_edge: study.rules.same_edge,
        all_eligible: study.rules.all_eligible,
        identical: study.rules.identical,
        one_class: study.one_class,
        length_check: study.length_check,
      })}</details>

    <details><summary>Complete rows · ${escape(String(study.rows.length))} retained requests, scored and excluded</summary>
      ${table(escape, ["Query", "Mode", "Stratum", "Observed", "Fitted", "Package", "Request"], rowTable(study), "data-outside-rows")}
      <p>Rows are shown in the retained inventory order. Every row keeps its exclusion, its Unknown label and its package. A row is scored only when it is an eligible literal boundary request on a distinct or same map edge.</p></details>

    <details><summary>Exclusions, anomalies and eligibility rules</summary>
      ${table(escape, ["Query", "Mode", "Stratum", "Exclusion", "Recorded label"], exclusionRows(study), "data-outside-exclusions")}
      <p>${escape(String(study.anomalies.length))} openings failed before a network snapshot existed and are recorded as anomalies, not as failures:</p>
      ${table(escape, ["Package", "Attempt", "Kind"], study.anomalies.map((row) => [row.slug, row.attempt_id, row.kind]), "data-outside-anomalies")}
      ${detail(escape, "Eligibility rules as recorded", study.eligibility_rules)}</details>

    <details><summary>Bridge · every model field recovered from the nine unchanged packages</summary>
      <p>${escape(b.question)} Answer: <strong>${escape(b.answer)}</strong>. Across ${escape(num(b.totals.segments_native))} segments and ${escape(num(b.totals.nodes_native))} nodes the bridge reproduces the native segment id set, start and end nodes, prefab and lane templates, and the per-mode model-input digests are identical. The Outside node flag agrees on all ${escape(num(b.totals.outside_nodes_equal))} nodes. ${escape(num(b.totals.chords_equal_within_2pct))} of ${escape(num(b.totals.segments_native))} segments have a chord length within 2% and all ${escape(num(b.totals.chords_equal_within_20pct))} within 20%: airplane-path and some movable segments record their own endpoints while the save stores node centres.</p>
      ${table(escape, ["Package", "Segments", "Nodes", "Start/end", "Lanes", "Invert", "Chords ≤2%", "Chords ≤20%", "Largest error", "Mode inputs"], bridgeRows(study), "data-outside-bridge")}
      <p>Node OneWayIn/OneWayOut flags are recomputed by the game at load; ${escape(num(b.totals.node_flags_differ_count))} node flag values differ and the Outside bit agrees on every node. The leave-one-package-out catalog leaves one asheville-only and two hong-kong-only node flag values unnamed, which touches no model input. Chord length is used only in the <code>maxLength</code> lower-bound check, which never binds: the longest frozen successful directed path is ${escape(String(study.length_check.max_directed_chord_over_cap))} of the cap, and no negative prediction becomes reachable without a cap. Chord length is <strong>not</strong> a qualified native cost and not an SI conversion.</p>
      ${detail(escape, "Bridge limitations", b.limitations)}</details>

    <details><summary>Carried evidence · ${escape(String(study.files.length))} files</summary>${evidenceList(escape, study)}</details>
    <details><summary>Linked source documents · ${escape(String(study.linked.length))} immutable blobs at the publication commit</summary>${linkedList(escape, study)}</details>
    <details><summary>Protocol, stratum definitions and the freeze</summary>${detail(escape, "Protocol as recorded", study.protocol)}</details>
    <p class=note>${escape(study.limits)}</p></article>`;
}

/** A compact reference from one capability to the single shared study. */
export function outsideResearchReference(capability, { study }, escape) {
  const record = study.modes[capability];
  const conf = record.fitted[FITTED].counts;
  const head = `${capability[0].toUpperCase()}${capability.slice(1)}`;
  const line = record.discrimination_estimable
    ? `${escape(head)} has ${escape(String(record.primary))} primary requests: TP ${conf.tp} · FP ${conf.fp} · TN ${conf.tn} · FN ${conf.fn}, with ${escape(String(record.successes))} observed successes and ${escape(String(record.failures))} observed failures.`
    : `${escape(head)} has ${escape(String(record.primary))} primary requests and every one succeeded. That is one class only: positive consistency, not discrimination, and not a service or a guarantee.`;
  return `<h3>Outside-connection query evidence</h3>
    <p>Retrospective, query-scoped evidence on the accepted outside-v1 rows. ${line}
    <a href="#outside-research-study">The one study, all modes, strata, exclusions and limits</a>.
    It is evidence only: not the current runtime estimate, not a promise and not activation.</p>`;
}

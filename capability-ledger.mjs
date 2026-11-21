// Build a readable ledger and stock-map reference from the one capability file.
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";
import { STOCK_MEASURES, validNativeContext, validNativeIdentityRef } from "./capability-model.js";
import { CAPTURE_STOCK } from "./capability-inputs.js";

import { WATER_STUDY, validateWaterStudy, waterStudyPage } from "./water-calibration.mjs";

import { START_WATER_STUDY, validateStartWaterStudy, startWaterPage } from "./start-water-study.mjs";

import { RAIL_STUDY, railStudy, validateRailStudy, railStudyPage } from "./rail-study.mjs";

export const START_WATER_PROJECTION_SHA = "26f5a6cc0c9412970eb80888c0e378af11c316bf1ca3bd8501c8fc8ebf6b73da";
export const WATER_PROJECTION_SHA = "250090642bcb9fff1ba111e149e0127fb787e516fbf8d6428281f139abf1d8cf";
export const ROOT = fileURLToPath(new URL(".", import.meta.url));
export const TERRAIN_INTEREST_ARTIFACT = "tools/map-factory/survey/terrain-interest.json";
export const TERRAIN_INTEREST_VERSION = "pl1228-terrain-interest-v1";
const TERRAIN_INTEREST_IDS = ["terrain_roughness_percent", "central_terrain_diversity_m"];
const TERRAIN_INTEREST_TOOLS = {
  reader: "tools/map-factory/survey/measure_maps.py",
  measure_tool: "tools/map-factory/survey/measure_terrain_interest.py",
  measure_source: "tools/map-factory/terrain_interest.py",
};
const LEVELS = ["likely", "not_possible_here", "promised", "unknown"];
const escape = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const label = (s) => s.replaceAll("_", " ");
const sha = (raw) => createHash("sha256").update(raw).digest("hex");

function linearQuantile(values, p) {
  const index = (values.length - 1) * p, lo = Math.floor(index), hi = Math.ceil(index);
  return values[lo] + (values[hi] - values[lo]) * (index - lo);
}

/**
 * The terrain-shape interest study. Its artifact is generated read-only from the
 * shipped maps by `survey/measure_terrain_interest.py`, which imports the same
 * measure function the prepared report uses. Validation here re-derives the
 * quartiles from the artifact's rows, re-hashes every bound tool and refuses a
 * stale artifact, so the ledger cannot cite a measurement it no longer owns.
 */
function terrainInterest() {
  const path = TERRAIN_INTEREST_ARTIFACT, raw = readFileSync(ROOT + path), study = JSON.parse(raw);
  if (study.schema !== 1 || study.version !== TERRAIN_INTEREST_VERSION) throw new Error("Invalid terrain interest artifact header");
  if (study.maps?.read_only !== true || !Array.isArray(study.rows) || !study.rows.length) throw new Error("Terrain interest artifact is not a read-only survey");
  const failures = study.maps.failures ?? [], excluded = study.maps.excluded ?? [];
  if (failures.length) throw new Error(`Terrain interest survey has failures: ${failures.map((f) => f.file).join(", ")}`);
  if (study.maps.included !== study.rows.length || study.maps.files_seen !== study.rows.length + excluded.length + failures.length) throw new Error("Terrain interest survey counts do not add up");
  const names = study.rows.map((row) => row.file);
  if (JSON.stringify(names) !== JSON.stringify([...names].sort()) || new Set(names).size !== names.length) throw new Error("Terrain interest rows are not sorted unique file names");
  if (JSON.stringify(Object.keys(study.measures ?? {}).sort()) !== JSON.stringify([...TERRAIN_INTEREST_IDS].sort())) throw new Error("Terrain interest artifact measures changed");
  for (const [key, file] of Object.entries(TERRAIN_INTEREST_TOOLS)) {
    const tool = study.tool?.[key];
    if (!tool || tool.file !== file || !/^[a-f0-9]{64}$/.test(tool.sha256 ?? "") || sha(readFileSync(ROOT + file)) !== tool.sha256) throw new Error(`Stale terrain interest tool binding: ${key}`);
  }
  const metrics = {};
  for (const id of TERRAIN_INTEREST_IDS) {
    const measure = study.measures[id];
    if (measure.kind !== "terrain_shape" || measure.name !== STOCK_MEASURES[id].label || measure.definition !== STOCK_MEASURES[id].definition) throw new Error(`Terrain interest measure drifted from the shared edge: ${id}`);
    const values = study.rows.map((row) => row[id]).filter(Number.isFinite).sort((a, b) => a - b);
    if (values.length !== study.maps.included) throw new Error(`Terrain interest rows lack ${id}`);
    const declared = study.quantiles?.[id];
    if (!declared || declared.n !== values.length || declared.p25 !== linearQuantile(values, 0.25) || declared.median !== linearQuantile(values, 0.5) || declared.p75 !== linearQuantile(values, 0.75)) throw new Error(`Terrain interest quartiles are stale: ${id}`);
    metrics[id] = { name: measure.name, unit: measure.unit, n: values.length, p25: declared.p25, median: declared.median, p75: declared.p75, definition: measure.definition, kind: measure.kind };
  }
  const evidence = {
    fixtures: ["asheville", "charleston", "innsbruck", "pittsburgh", "rio"],
    height_fit: {
      default: ["asheville", "charleston", "pittsburgh"],
      non_default: { innsbruck: 0.4469348561033608, rio: 0.9198811898929851 },
      source: "fixtures/<slug>/geometry.json.gz fit.verticalScale",
    },
    method: "Each committed fixture's retained prepared terrain (terrain.u16 at 1/64 m) compared with that square's retained capture heightmap (input.png, rows north-first, flipped to the game's south-first order, read at the same 1/64 m unit), on the same predicate and this ledger's quartiles.",
    result: {
      terrain_relief_m: { max_abs_difference: 1.1, bands_differ: [] },
      terrain_roughness_percent: { max_abs_difference: 0.39, bands_differ: [] },
      central_terrain_diversity_m: { max_abs_difference: 0.5, bands_differ: [] },
      median_land_slope_percent: { bands_differ: ["asheville"] },
      wet_central_fraction: { bands_differ: ["charleston", "pittsburgh", "rio"] },
    },
    test: "tools/map-factory/test_capabilities.py:test_capture_fidelity_keeps_only_matched_measures",
  };
  return {
    metrics,
    study: {
      artifact: path,
      artifact_sha256: sha(raw),
      version: study.version,
      generated_at: study.generated_at,
      scope: study.scope,
      fidelity: study.fidelity,
      quantiles_policy: study.quantiles_policy,
      maps: study.maps,
      tool: study.tool,
      rows_sha256: sha(JSON.stringify(study.rows)),
      measures: TERRAIN_INTEREST_IDS,
      comparability: {
        prepared_report: "Final prepared grids are the same 1081-square, 16 m, south-first terrain at 1/64 m the stock survey reads; every measure is comparable there.",
        capture_estimate: CAPTURE_STOCK,
        evidence,
      },
    },
  };
}

export function stockReference() {
  const path = "tools/map-factory/survey/basemaps.json", raw = readFileSync(ROOT + path);
  const maps = JSON.parse(raw).filter((map) => map.file !== "CO.crp");
  const fields = {
    buildable_percent: ["New Game buildable land", "%", (m) => m.meta.buildableArea],
    trees_total: ["Planted tree count (export budget-sensitive)", "trees", (m) => m.trees.total],
    wet_central_fraction: ["Wet share of the central 25 tiles", "fraction", (m) => m.water_central_share],
    terrain_relief_m: ["Terrain relief across the whole map", "m", (m) => m.terrain.max - m.terrain.min],
    median_land_slope_percent: ["Median central land slope", "%", (m) => m.terrain.median_land_slope_pct],
    ...Object.fromEntries(["ore", "oil", "fertility", "forest"].map((key) => [`${key}_central_land_fraction`, [`${key} share of central land`, "fraction", (m) => m.resources[key].central_share_of_land]])),
    ...Object.fromEntries(["road", "rail", "ship", "air"].map((key, i) => [`incoming_${key}_entries`, [`Incoming ${key} entries`, "entries", (m) => m.meta[["incomingRoads", "incomingTrainTracks", "incomingShipPath", "incomingPlanePath"][i]]]])),
  };
  const metrics = {};
  for (const [key, [name, unit, get]] of Object.entries(fields)) {
    const values = maps.map(get).filter(Number.isFinite).sort((a, b) => a - b);
    const q = (p) => { const index = (values.length - 1) * p, lo = Math.floor(index), hi = Math.ceil(index); return values[lo] + (values[hi] - values[lo]) * (index - lo); };
    metrics[key] = { name, unit, n: values.length, p25: q(0.25), median: q(0.5), p75: q(0.75) };
  }
  const interest = terrainInterest();
  return { source: path, sha256: sha(raw), maps: maps.length, excluded: "CO.crp: blank editor terrain system package", quantiles: "Linear interpolation at (n-1)*p; bands strictly below p25, inclusive typical, strictly above p75. Descriptive, not quality gates.", metrics: { ...metrics, ...interest.metrics }, terrain_interest: interest.study };
}

export function validateLedger(ledger) {
  if (ledger.schema !== 1 || !ledger.model || JSON.stringify(Object.keys(ledger.promise_levels).sort()) !== JSON.stringify(LEVELS)) throw new Error("Invalid capability ledger header");
  const ids = ledger.capabilities.map((c) => c.id);
  if (new Set(ids).size !== ids.length || !["road", "rail", "ship", "air", "water", "start", "buildable", "resources", "trees", "water_risk"].every((id) => ids.includes(id))) throw new Error("Missing or duplicate capability");
  if (JSON.stringify(ledger.stock_reference) !== JSON.stringify(stockReference())) throw new Error("Stock reference is stale; run node capability-ledger.mjs --refresh-stock");
  for (const cap of ledger.capabilities) {
    if (!cap.definition || !cap.status || !Array.isArray(cap.game_agreement) || JSON.stringify(Object.keys(cap.promise_levels).sort()) !== JSON.stringify(LEVELS)) throw new Error(`Incomplete capability ${cap.id}`);
    for (const ref of [cap.exporter_check, cap.browser_check, ...cap.existing_checks].filter(Boolean)) {
      const [file, symbol] = ref.split(":");
      if (!existsSync(ROOT + file)) throw new Error(`Missing check ${ref}`);
      if (symbol && (!/^[A-Za-z_]\w*$/.test(symbol) || !new RegExp(`\\b(?:def|function|class|const|let|var)\\s+${symbol}\\b`).test(readFileSync(ROOT + file, "utf8"))))
        throw new Error(`Missing check symbol ${ref}`);
    }
    for (const id of cap.metric_ids) if (!ledger.stock_reference.metrics[id]) throw new Error(`Missing stock metric ${id}`);
    if (cap.evidence_metrics != null) {
      if (typeof cap.evidence_metrics !== "object" || !Object.keys(cap.evidence_metrics).length) throw new Error(`Empty evidence metrics for ${cap.id}`);
      for (const [id, measure] of Object.entries(cap.evidence_metrics))
        if (!measure?.name || !measure?.definition || !measure?.unit) throw new Error(`Incomplete evidence metric ${cap.id}:${id}`);
    }
    if (cap.status === "place_evidence_candidate" && (!cap.source_coverage || !cap.fidelity)) throw new Error(`Missing place evidence provenance for ${cap.id}`);
    for (const row of cap.game_agreement) {
      if (!row.square || !row.observed_at || !row.oracle || !/^[a-f0-9]{64}$/.test(row.artifact_sha256 ?? "") || !/^[a-f0-9]{40}$/.test(row.source_sha ?? "") || !Array.isArray(row.evidence) || !row.evidence.length || ![true, false, null].includes(row.observed) || ![true, false, null].includes(row.predicted)) throw new Error(`Unbound game evidence for ${cap.id}`);
    }
  }
  for (const [id, study] of Object.entries(ledger.evidence_studies ?? {})) {
    const tool = study.projection_tool_file ?? "tools/map-factory/integrate_outside_evidence.py";
    const allowed = id === "outside-targeted-v2" ? "tools/map-factory/integrate_outside_v2.py" : "tools/map-factory/integrate_outside_evidence.py";
    if (tool !== allowed || !/^[a-f0-9]{40}$/.test(study.source_commit) || sha(readFileSync(ROOT + study.predictions_file)) !== study.predictions_sha256 ||
      sha(readFileSync(ROOT + tool)) !== study.projection_tool_sha256)
      throw new Error("Stale native evidence projection binding");
  }
  const staged = ledger.evidence_studies?.["outside-targeted-v2"]?.qualification_candidates ?? [];
  for (const [certificate, candidate] of [...(ledger.native_path_certificates ?? []).map((c) => [c, false]), ...staged.map((c) => [c, true])]) {
    if (!["ship", "air"].includes(certificate.capability) || certificate.scope !== "sampled_native_lane_paths_at_opening" ||
      !ledger.evidence_studies?.[certificate.study] || !validNativeContext(certificate.native_context) ||
      (candidate ? !isDeepStrictEqual(certificate.blocked_by, ["independent_review_pending"]) : certificate.blocked_by?.length) || !validNativeIdentityRef(certificate.runtime_identity_evidence) ||
      !/^[a-f0-9]{64}$/.test(certificate.observation_sha256 ?? "") ||
      !certificate.evidence?.some((e) => e.sha256 === certificate.observation_sha256) ||
      JSON.stringify(Object.keys(certificate.controls ?? {}).sort()) !== JSON.stringify(["boundary_0", "boundary_1", "midpoint_0", "midpoint_1"]) ||
      !Object.values(certificate.controls).every((v) => v === true) || !/^[a-f0-9]{64}$/.test(certificate.artifact_sha256 ?? "") ||
      JSON.stringify(Object.keys(certificate.inputs_sha256 ?? {}).sort()) !== JSON.stringify(["hydrology.json", "terrain.u16", "water.u16"]) ||
      !Object.values(certificate.inputs_sha256).every((v) => /^[a-f0-9]{64}$/.test(v)) ||
      !certificate.observed_at || !certificate.evidence?.length || certificate.evidence.some((e) => !/^[a-f0-9]{64}$/.test(e.sha256 ?? "")))
      throw new Error("Unbound native path certificate");
    const ref = certificate.runtime_identity_evidence;
    if (!existsSync(ROOT + ref.file)) throw new Error("Missing bound runtime identity receipt");
    const raw = readFileSync(ROOT + ref.file), receipt = JSON.parse(raw);
    if (sha(raw) !== ref.sha256 || receipt.artifact_sha256 !== certificate.artifact_sha256 ||
      receipt.observation_sha256 !== certificate.observation_sha256 || receipt.observed_at !== certificate.observed_at ||
      receipt.scope !== certificate.scope ||
      !isDeepStrictEqual(receipt.inputs_sha256, certificate.inputs_sha256) ||
      !isDeepStrictEqual(receipt.native_context, certificate.native_context)) throw new Error("Runtime identity receipt binding changed");
  }
  validateRailStudy(ledger);
  validateWaterStudy(ledger.capabilities.find((c) => c.id === "water_risk"), undefined, WATER_PROJECTION_SHA);
  validateStartWaterStudy(ledger, undefined, START_WATER_PROJECTION_SHA);
  const source = JSON.parse(readFileSync(ROOT + "tools/map-factory/water-risk-model.json", "utf8")).calibration;
  const recorded = ledger.capabilities.find((c) => c.id === "water_risk").calibration;
  if (recorded.squares !== source.squares || recorded.scored_complete_runs !== source.complete_60_runs ||
      ["flood", "drying"].some((k) => ["tp", "fp", "tn", "fn"].some((v) => recorded[k][v] !== source.results[k][v]))) throw new Error("Water calibration seed is stale");
}

export function agreementByOracle(rows) {
  return [...new Set(rows.map((r) => r.oracle))].sort().map((oracle) => {
    const all = rows.filter((r) => r.oracle === oracle), scored = all.filter((r) => typeof r.predicted === "boolean" && typeof r.observed === "boolean");
    return { oracle, scored: scored.length, unscored: all.length - scored.length, agree: scored.filter((r) => r.predicted === r.observed).length, false_positive: scored.filter((r) => r.predicted && !r.observed).length, false_negative: scored.filter((r) => !r.predicted && r.observed).length };
  });
}

function terrainInterestPage(ledger, escape) {
  const study = ledger.stock_reference.terrain_interest;
  if (!study) return "";
  const rows = study.measures.map((id) => {
    const metric = ledger.stock_reference.metrics[id];
    return `<tr><th>${escape(metric.name)}</th><td>${escape(metric.definition)}</td><td>${escape(metric.unit)}</td>${[metric.p25, metric.median, metric.p75].map((v) => `<td>${escape(Number(v.toFixed(4)))}</td>`).join("")}</tr>`;
  }).join("");
  const policy = study.comparability.capture_estimate;
  const compared = study.measures.filter((id) => policy[id]?.comparable).map((id) => ledger.stock_reference.metrics[id].name);
  const withheld = Object.entries(policy).filter(([, value]) => value?.comparable === false)
    .map(([id, value]) => `${escape(ledger.stock_reference.metrics[id]?.name ?? id)} (${escape(value.reason)})`);
  const evidence = study.comparability.evidence;
  const evidenceRows = Object.entries(evidence.result).map(([id, row]) =>
    `<tr><th>${escape(ledger.stock_reference.metrics[id]?.name ?? id)}</th><td>${escape(row.max_abs_difference != null ? `${row.max_abs_difference}` : "not measured")}</td><td>${escape(row.bands_differ.length ? row.bands_differ.join(", ") : "none")}</td></tr>`).join("");
  return `<h3>Terrain-shape measures, live</h3><p>${escape(study.scope)} They use the same 1081-square, 16 m, south-first grid, the same 1/64 m height unit and the same central predicate as the prepared report and the stock survey.</p>
    <div class="ledger-table"><table><thead><tr><th>Measure</th><th>What it measures</th><th>Unit</th><th>p25</th><th>Median</th><th>p75</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p>At pan time the capture compares ${compared.map((s) => escape(s)).join(" and ")}. ${withheld.length ? `Not comparable there: ${withheld.join("; ")}.` : ""}</p>
    <details><summary>Comparability evidence on the committed squares</summary><p>${escape(evidence.method)}</p><table><thead><tr><th>Measure</th><th>Largest prepared-vs-capture difference</th><th>Bands that differ</th></tr></thead><tbody>${evidenceRows}</tbody></table><p>Height fit: default on ${escape(evidence.height_fit.default.join(", "))}; non-default on ${Object.entries(evidence.height_fit.non_default).map(([slug, scale]) => `${escape(slug)} ${scale}x`).join(", ")}. Proof: <code>${escape(evidence.test)}</code>.</p></details>
    <details><summary>Terrain-shape source, rows and tools</summary><p>Measured rows: <a href="./${escape(study.artifact)}">${escape(study.artifact)}</a> (${escape(study.artifact_sha256)}), served byte for byte.</p><pre>${escape(JSON.stringify({ artifact: study.artifact, artifact_sha256: study.artifact_sha256, version: study.version, generated_at: study.generated_at, fidelity: study.fidelity, quantiles_policy: study.quantiles_policy, maps: study.maps, tool: study.tool, rows_sha256: study.rows_sha256, rows: `${study.maps.included} measured rows bound by rows_sha256` }, null, 2))}</pre></details>`;
}

function terrainInterestLaunchBar(proposal, escape) {
  if (!proposal) return "";
  const recommended = proposal.recommended.map((id) => `<li>${escape(id)}</li>`).join("");
  return `<h3>Terrain interest on the launch bar</h3><ul>${recommended}</ul><p>${escape(proposal.wording)}</p>${proposal.set_aside ? `<p class=note>${escape(proposal.set_aside)}</p>` : ""}<p class=note>${escape(proposal.limits)}</p>`;
}

export function ledgerPage(ledger, revision = "PL-1119-capability-ledger") {
  const directedRail = railStudy();
  const sourceLink = (ref) => `<a href="https://github.com/frontierkodiak/region-to-skylines/blob/${encodeURIComponent(revision)}/${escape(ref.split(":")[0])}">${escape(ref)}</a>`;
  const scoreText = (a) => a.oracle === "native_two_edge_witness"
    ? `${a.agree} witnessed positives consistent with ${a.scored} scored predictions; ${a.unscored} unknown; ${a.false_negative} model-negative witness mismatches. No native-negative accuracy measured.`
    : a.scored === 0 ? `${a.unscored} diagnostic or unknown cells; not scored as the same capability predicate.`
    : `${a.agree}/${a.scored} agree; ${a.unscored} unscored; ${a.false_positive} false positives, ${a.false_negative} false negatives.`;
  const caps = ledger.capabilities.map((c) => {
    const agreement = [...new Set(c.game_agreement.map((r) => r.study ?? "other"))].flatMap((study) =>
      agreementByOracle(c.game_agreement.filter((r) => (r.study ?? "other") === study)).map((a) => ({ ...a, study })));
    return `<article id="${escape(c.id)}"><div class="ledger-title"><h2>${escape(c.name)}</h2><span>${escape(label(c.status))}</span></div><p>${escape(c.definition)}</p>
      <details><summary>Checks and promise levels</summary><dl>${Object.entries(c.promise_levels).map(([k, v]) => `<dt>${escape(label(k))}</dt><dd>${escape(v)}</dd>`).join("")}</dl>
      <p>Exporter: ${c.exporter_check ? sourceLink(c.exporter_check) : "Not implemented"}<br>Browser: ${c.browser_check ? sourceLink(c.browser_check) : "Not implemented"}</p><p>Existing work: ${c.existing_checks.map(sourceLink).join(", ")}</p></details>
      ${c.evidence_metrics ? `<h3>Place evidence measures</h3><dl>${Object.entries(c.evidence_metrics).map(([id, m]) => `<dt>${escape(m.name)} (${escape(m.unit)})</dt><dd>${escape(m.definition)}</dd>`).join("")}</dl>` : ""}
      ${c.source_coverage ? `<details><summary>Sources, coverage and fidelity</summary><dl>${Object.entries(c.source_coverage).map(([key, value]) => `<dt>${escape(label(key))}</dt><dd>${escape(value)}</dd>`).join("")}</dl><p>${escape(c.fidelity)}</p></details>` : ""}
      <h3>Agreement with the game</h3>${agreement.length ? `<ul>${agreement.map((a) => `<li>${escape(a.study)} · ${escape(label(a.oracle))}: ${escape(scoreText(a))}</li>`).join("")}</ul><details><summary>Measured squares and dates</summary><pre>${escape(JSON.stringify(c.game_agreement, null, 2))}</pre></details>` : c.calibration_studies || c.witness_study ? "" : "<p class=note>No scored observations for this model yet.</p>"}
      ${c.runtime_model ? `<details><summary>Current Start model · unscored</summary><pre>${escape(JSON.stringify(c.runtime_model, null, 2))}</pre></details>` : ""}
      ${c.id === "rail" ? railStudyPage(directedRail, escape) : ""}
      ${c.witness_study ? startWaterPage(ledger.witness_studies[START_WATER_STUDY], c.id, escape) : ""}
      ${c.calibration_studies ? waterStudyPage(c.calibration_studies[WATER_STUDY], escape) : ""}
      ${c.calibration ? `<details><summary>Historical seed · 5 squares / 50 runs</summary><pre>${escape(JSON.stringify(c.calibration, null, 2))}</pre></details>` : ""}
      <p class=note>${escape(c.limits)}</p></article>`;
  }).join("");
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Map capabilities · Region to Skylines</title><link rel="stylesheet" href="style.css"></head>
    <body class="ledger-page"><header><h1>Map capabilities</h1><a href="./">Choose a square</a><a href="capabilities.json">JSON ledger</a></header><main><section>
    <p>${escape(ledger.game)} · updated ${escape(ledger.updated_at)}</p><p>${escape(ledger.scope)}</p>
    ${Object.entries(ledger.evidence_studies ?? {}).map(([id, s]) => {
      const active = (ledger.native_path_certificates ?? []).filter((c) => c.study === id);
      const pending = (s.qualification_candidates ?? []).filter(({ blocked_by, ...candidate }) =>
        blocked_by?.includes("independent_review_pending") && !active.some((certificate) => isDeepStrictEqual(certificate, candidate))).length;
      return `<aside class=note data-study="${escape(id)}"><h2>Native study: what was scored · ${escape(id)}</h2><p>Frozen predictor: ${escape(s.prediction_model)} at ${escape(s.prediction_source_sha)}. Current runtime adds exact-context qualification; it is not a new native boundary fit.</p><p>${escape(s.method)}</p><p>${escape(s.limits)}</p><p>${s.qualification_candidates?.length ?? 0} retained control sets; ${pending} awaiting independent review. Active certificates: ${active.length}. Studies are not pooled as independent votes.</p><a href="${escape(s.source_url)}">Immutable study, raw receipts and failures</a></aside>`;
    }).join("")}
    <nav aria-label="Capabilities">${ledger.capabilities.map((c) => `<a href="#${escape(c.id)}">${escape(c.name)}</a>`).join(" ")}</nav>${caps}
    <article id="stock"><h2>Against the stock maps</h2><p>${ledger.stock_reference.maps} shipped maps. Below p25, typical, above p75 describe abundance and interest, not a pass/fail rating.</p><div class="ledger-table"><table><thead><tr><th>Measure</th><th>Unit</th><th>p25</th><th>Median</th><th>p75</th></tr></thead><tbody>${Object.values(ledger.stock_reference.metrics).map((m) => `<tr><th>${escape(m.name)}</th><td>${escape(m.unit)}</td>${[m.p25, m.median, m.p75].map((v) => `<td>${escape(Number(v.toFixed(4)))}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
    ${terrainInterestPage(ledger, escape)}
    <details><summary>Source and method</summary><pre>${escape(JSON.stringify({ ...ledger.stock_reference, metrics: undefined }, null, 2))}</pre></details></article>
    <article id="launch"><h2>Proposed launch bar</h2><ul>${ledger.launch_bar_proposal.required.map((s) => `<li>${escape(s)}</li>`).join("")}</ul><h3>Describe, without gating</h3><ul>${ledger.launch_bar_proposal.descriptive_not_gates.map((s) => `<li>${escape(s)}</li>`).join("")}</ul>${terrainInterestLaunchBar(ledger.launch_bar_proposal.terrain_interest, escape)}<p class=note>${escape(ledger.launch_bar_proposal.limits)}</p></article></section></main></body></html>`;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const file = ROOT + "capabilities.json", ledger = JSON.parse(readFileSync(file, "utf8"));
  if (process.argv.includes("--refresh-stock")) { ledger.stock_reference = stockReference(); writeFileSync(file, JSON.stringify(ledger, null, 2) + "\n"); }
  validateLedger(ledger);
  console.log(`Capability ledger valid: ${ledger.capabilities.length} capabilities, ${ledger.stock_reference.maps} stock maps`);
}

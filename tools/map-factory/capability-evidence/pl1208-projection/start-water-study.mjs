// Import saved, reviewed evidence only. Never execute the archived predictors or judges.
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";

const ROOT = fileURLToPath(new URL(".", import.meta.url));
export const START_WATER_STUDY = "pl1078-start-water-v2";
export const START_WATER_SOURCE = "9a4aad77101fbdb0190c7ceaa11ec643065bec56";
export const START_WATER_MANIFEST = "tools/map-factory/capability-evidence/pl1078-files.json";
export const START_WATER_MANIFEST_SHA = "7cd7e6b2f2dd0d78e6443b8ff8cddd9d5df4ffbdf29d5d7c51fed0ae66092a58";
export const START_WATER_PREFIX = "tools/map-factory/capability-evidence/PL-1078-start-water-v2/";
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const read = (file) => readFileSync(ROOT + file);

export function startWaterStudy(load = read) {
  const manifestBytes = load(START_WATER_MANIFEST);
  if (sha(manifestBytes) !== START_WATER_MANIFEST_SHA) throw new Error("Changed start/water file manifest");
  const manifest = JSON.parse(manifestBytes);
  for (const {file, sha256} of manifest.files)
    if (sha(load(file)) !== sha256) throw new Error(`Changed original start/water evidence: ${file}`);
  const json = (name) => JSON.parse(load(START_WATER_PREFIX + name));
  const report = json("observations.json"), predictions = json("predictions.json");
  const exports = json("export-identities-and-warnings.json");
  // The nested square records selection, not necessarily the actual exported artifact.
  const artifactBindings = predictions.rows.map(({slug, prediction, prediction_sha256}) => {
    const receipt = exports.cases[slug];
    if (prediction.artifact_sha256 !== receipt.stage.crp_sha256 ||
        report.rows.filter((r) => r.square.slug === slug).length !== 2 ||
        report.rows.some((r) => r.square.slug === slug &&
          (r.artifact_sha256 !== prediction.artifact_sha256 ||
           !isDeepStrictEqual(r.water_risk, receipt.water_risk))))
      throw new Error(`Unbound start/water artifact: ${slug}`);
    return {
      slug, artifact_sha256: prediction.artifact_sha256,
      physical_inputs_sha256: prediction.inputs_sha256,
      prediction_sha256, selection: prediction.square,
      selection_package_matches_artifact: prediction.square.package_sha256 == null
        ? null : prediction.square.package_sha256 === prediction.artifact_sha256,
      export_stage: receipt.stage, baseline_comparison: receipt.baseline_comparison,
    };
  });
  return {
    schema: 1, kind: "saved_start_and_surface_intake_witnesses",
    provenance: {
      publication_commit: START_WATER_SOURCE,
      exporter_commit: predictions.exporter_source_sha,
      assessment_collector_commit: predictions.assessment_source_sha,
      oracle_dll_sha256: "f916bdebb5bcef51a646b202b8db728d35f4e3fe811dedf530257d3cc79f1c2b",
      observations_sha256: sha(load(START_WATER_PREFIX + "observations.json")),
      predictions_sha256: sha(load(START_WATER_PREFIX + "predictions.json")),
      model_sha256: predictions.model_sha256,
      manifest: {file: START_WATER_MANIFEST, sha256: START_WATER_MANIFEST_SHA},
      files: manifest.files,
      components: [
        {capability: "start", symbol: "start_capabilities.start_witness", source_file: "tools/map-factory/start_capabilities.py"},
        {capability: "water", symbol: "surface_intake.assess_surface", source_file: "tools/map-factory/surface_intake.py"},
        {capability: "report", symbol: "report_start_water.report", source_file: "tools/map-factory/report_start_water.py"},
      ].map((c) => ({...c, source_commit: START_WATER_SOURCE,
        archived_file: "tools/map-factory/capability-evidence/pl1078-components/" + c.source_file.split("/").at(-1),
        runtime_adoption: false})),
      source_url: `https://github.com/frontierkodiak/region-to-skylines/tree/${START_WATER_SOURCE}/${START_WATER_PREFIX}`,
    },
    projection: {file: "start-water-study.mjs", sha256: sha(load("start-water-study.mjs"))},
    report, predictions, artifact_bindings: artifactBindings,
    reference_quantity: json("reference-controls/quantity-qualification.json"),
    interrupted_reference: json("history/mixed-api-reference/observation.json"),
    first_hour: {
      comparison: json("first-hour/comparison.json"),
      evidence_index: json("first-hour/evidence-index.json"),
      pre_rule_original_eight: json("first-hour/pre-rule-original-eight.json"),
      post_run_identity: json("first-hour/post-run-identity.json"),
      player_identity: json("player-arm-identity.json"),
    },
  };
}

export function validateStartWaterStudy(ledger, load = read, expectedProjectionHash) {
  if (sha(load("start-water-study.mjs")) !== expectedProjectionHash) throw new Error("Start/water projection tool changed");
  if (!isDeepStrictEqual(ledger.witness_studies, {[START_WATER_STUDY]: startWaterStudy(load)}))
    throw new Error("Start/water projection is stale or unbound");
  for (const id of ["start", "water"]) {
    const cap = ledger.capabilities.find((c) => c.id === id);
    if (cap.witness_study !== START_WATER_STUDY || cap.status !== "saved_witness_study_live_unmodeled" ||
        cap.exporter_check !== null || cap.browser_check !== null || cap.game_agreement.length)
      throw new Error("Start/water saved-study scope changed");
  }
}

export function importStartWater(ledger) {
  ledger.witness_studies = {[START_WATER_STUDY]: startWaterStudy()};
  for (const id of ["start", "water"]) {
    const cap = ledger.capabilities.find((c) => c.id === id);
    cap.witness_study = START_WATER_STUDY;
    cap.status = "saved_witness_study_live_unmodeled";
    cap.limits = id === "start"
      ? "Saved declared-plan construction and sampled passenger-car literal outside paths, not fresh-map road connectivity, freight/spawning or geographic impossibility. Advisory Python component delivered at the pinned source, not adopted in this runtime. Live Start remains unmodeled."
      : "Saved clean surface service at 1000 native water/sewage units per 256 frames, explicit auxiliary power, two loaded settling minutes and sixty scored minutes. No SI/population/indefinite-capacity claim; groundwater-player success is separate. Advisory Python component delivered at the pinned source, not adopted in this runtime. Live Water remains unmodeled.";
  }
  return ledger;
}

export function startWaterPage(study, id, escape) {
  const table = (heads, rows, attrs = "") => `<div class="ledger-table"><table ${attrs}><thead><tr>${heads.map((h) => `<th scope="col">${escape(h)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((v, i) => `<${i ? "td" : "th"}${i ? "" : ' scope="row"'}>${escape(v)}</${i ? "td" : "th"}>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  const detail = (title, value) => `<details><summary>${escape(title)}</summary><pre>${escape(JSON.stringify(value, null, 2))}</pre></details>`;
  const rate = (r) => r.positive_witness_agreement === null ? "NOT ESTIMABLE (n=0)"
    : `${r.agreed}/${r.agreed + r.disagreed}`;
  const value = (v) => v === null ? "Unknown" : v ? "Yes" : "No";
  const rows = study.report.rows.filter((r) => r.capability_id === id);
  const comparison = study.first_hour.comparison;
  const cohort = (v) => `${v.passed}/${v.planned}`;
  return `<section data-witness-study="${START_WATER_STUDY}" data-capability="${id}">
    <h3>Saved ${id === "start" ? "start-plan" : "surface-intake"} witnesses · advisory</h3>
    <p>Live check: unmodeled. Positive-witness agreement, not overall accuracy or global prevalence.</p>
    ${table(["Split", "Registered", "Positive predictions", "Agreed / scored", "Unscored positives", "Other unscored rows"],
      ["fitting", "held_out"].map((split) => {
        const s = study.report.summary[split][id];
        return [split === "held_out" ? "Regional holdout" : "Fitting", s.registered_squares, s.positive_predictions,
          rate(s), s.unscored_positive, rows.filter((r) => r.split === split && (r.predicted !== true || r.observed === null)).length];
      }), 'data-witness-scores')}
    ${id === "start"
      ? "<p>Exact declared grid construction, then sampled passenger-car paths to literal outside endpoints. Innsbruck and Pittsburgh agreed; Charleston’s final hookup collided with its earlier grid road at step 27. This is not fresh-map connectivity or a general negative.</p>"
      : "<p>1000 native water/sewage units per 256 frames · explicit auxiliary power · 2 loaded settling minutes · 60 scored minutes. Hong Kong northeast returned zero water on 130/843 scored requests: a failed fixed witness, not geographic incapability. Grand Canyon northeast is Unknown. Groundwater-player success is not a surface-water positive.</p>"}
    <details><summary>All 11 ${escape(id)} rows and dates</summary>
    ${table(["Square", "Split", "Predicted / observed", "Observation date"], rows.map((r) => [r.square.slug, r.split, `${value(r.predicted)} / ${value(r.observed)}`, r.observed_at ?? "Unknown"]), 'data-witness-rows')}
    ${detail("Exact saved rows, warnings, facets and hashes", rows)}</details>
    ${id === "water" ? `<details><summary>Stock quantity references · separate from model agreement</summary>
      <p>Predictions are NULL; neither reference contributes to model agreement or player qualification. Interrupted mixed-API reference: unscored, not negative.</p>
      ${table(["Reference", "Full quantities / requests", "Polluted deliveries", "Clean service", "Prediction"], study.reference_quantity.rows.map((r) => [r.slug, `${r.cycles - r.short_water_cycles}/${r.cycles}`, r.polluted_delivery_cycles, value(r.observed_surface_service), "NULL"]))}
      ${detail("Reference qualification, protocol limits and raw bindings", study.reference_quantity)}
      ${detail("Interrupted diagnostic", study.interrupted_reference)}</details>` : ""}
    ${id === "start" ? `<details data-first-hour><summary>First-hour oracle context · unchanged player and maps</summary>
      <p>Final 4a4 player passes both stock controls. Original eight were frozen before capability implementation: 3/8 first-hour, 2/8 strict. Historical 1/8 is unqualified.</p>
      ${table(["Cohort / verdict", "Before", "Fresh repeat"], [
        ["Original eight · first-hour", cohort(comparison.first_hour_survival.original_player_baseline), "3/8"],
        ["Frozen eleven · first-hour", cohort(comparison.first_hour_survival.before), cohort(comparison.first_hour_survival.after)],
        ["Frozen eleven · strict whole-map", cohort(comparison.before), cohort(comparison.after)],
      ])}
      <p>Grand Canyon northeast alone changed: growth first seen at 6.038 minutes, after the unchanged 5-minute deadline; peak 540, final 385. Charleston retains its independent DEM failure. No physical exporter improvement: maps, grids, resources, probes, player and judge are unchanged.</p>
      ${table(["Square", "First-hour before / repeat", "Strict before / repeat"], Object.entries(comparison.cases).map(([slug, r]) => [slug, `${r.before.first_hour} / ${r.after.first_hour}`, `${r.before.overall} / ${r.after.overall}`]), 'data-first-hour-pairs')}
      ${detail("Full 11 pairs, controls and metrics", comparison)}
      ${detail("Public proof-bundle manifests and provenance", study.first_hour.evidence_index)}
      <p>All 24 verdicts and public per-file manifests are served below. Large proof ZIPs remain on the <a href="https://github.com/frontierkodiak/region-to-skylines/pull/69">source study</a> and owning issue; selected receipts are not launch-context qualification.</p>
    </details>` : ""}
    <details><summary>Components, actual artifacts and source files</summary>
      <p>Delivered Python components are archived evidence, not active parent-runtime checks. Selection square metadata is not actual package identity: Yosemite’s nested 17020ec… differs from actual bc0d9f4…; regional holdout selection records have no package/input keys. Neither Yosemite capability has a measured native attempt. Physical inputs below come from frozen predictions; actual artifacts bind to export receipts.</p>
      <ul>${study.provenance.components.filter((c) => c.capability === id).map((c) => `<li><a href="https://github.com/frontierkodiak/region-to-skylines/blob/${c.source_commit}/${c.source_file}">${escape(c.symbol)}</a> · not runtime-adopted</li>`).join("")}</ul>
      ${detail("Actual artifact, physical inputs and selection metadata", study.artifact_bindings)}
      ${detail("Exact source roles and independent hashes", {...study.provenance, files: undefined})}
      <ul>${study.provenance.files.map(({file, sha256}) => `<li><a href="${escape(file)}">${escape(file)}</a> · <code>${sha256}</code></li>`).join("")}</ul>
      <p>Archived v1 remains separate. No native path certificate or live promise is derived from this study.</p>
    </details></section>`;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const file = ROOT + "capabilities.json";
  let original = readFileSync(file, "utf8");
  const ledger = importStartWater(JSON.parse(original));
  // Patch only owned capability fragments and the new final top-level study.
  // Preserve original transport numeric spellings, ordering and certificates.
  for (const id of ["start", "water"]) {
    const marker = original.indexOf(`"id": "${id}"`);
    const begin = original.lastIndexOf("    {", marker);
    const end = original.indexOf("\n    }", marker) + "\n    }".length;
    const replacement = JSON.stringify(ledger.capabilities.find((c) => c.id === id), null, 2)
      .split("\n").map((line) => "    " + line).join("\n");
    original = original.slice(0, begin) + replacement + original.slice(end);
  }
  const studyMarker = original.indexOf('\n  "witness_studies":');
  if (studyMarker >= 0) original = original.slice(0, studyMarker - 1) + "\n}\n";
  const addition = JSON.stringify(ledger.witness_studies, null, 2).split("\n")
    .map((line, i) => i ? "  " + line : line).join("\n");
  writeFileSync(file, original.trimEnd().slice(0, -1).trimEnd() + ',\n  "witness_studies": ' + addition + "\n}\n");
}

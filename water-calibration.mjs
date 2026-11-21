// Immutable PL-1072 evidence; none of the archived Python tools are executed.
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";

const ROOT = fileURLToPath(new URL(".", import.meta.url));
export const WATER_STUDY = "pl1072-independent-geography";
export const WATER_SOURCE = "cd1aa8317205053895517bc2ac141a9f0240ee36";
export const WATER_FILES = {
  "tools/map-factory/capability-evidence/pl1072-water/calibration/pl1072-frozen/HOLDOUT_REPORT.md": {
    "source_file": "tools/map-factory/calibration/pl1072-frozen/HOLDOUT_REPORT.md",
    "sha256": "b7bd2e4cd288824e777eea9b51f40ef8e5ccb4babb2111c4aea860b0a3ccae0c"
  },
  "tools/map-factory/capability-evidence/pl1072-water/calibration/pl1072-frozen/final-pre-score-verification.json": {
    "source_file": "tools/map-factory/calibration/pl1072-frozen/final-pre-score-verification.json",
    "sha256": "4ad563b6cb57cd6c4ce649c491d9610561046e70bc7b5183f2756772fe3dfecf"
  },
  "tools/map-factory/capability-evidence/pl1072-water/calibration/pl1072-frozen/freeze.json": {
    "source_file": "tools/map-factory/calibration/pl1072-frozen/freeze.json",
    "sha256": "829b644cec6f04d2eb9a5fe21770eb49a4cc1c4e4becd420eb446ef75dafcd90"
  },
  "tools/map-factory/capability-evidence/pl1072-water/calibration/pl1072-frozen/holdout-disposition.json": {
    "source_file": "tools/map-factory/calibration/pl1072-frozen/holdout-disposition.json",
    "sha256": "41c0a25e803d6373e1f968b8a38039dab9ce5709b0ef4e782ed2f9334f5db0dd"
  },
  "tools/map-factory/capability-evidence/pl1072-water/calibration/pl1072-frozen/holdout-score-audit.json": {
    "source_file": "tools/map-factory/calibration/pl1072-frozen/holdout-score-audit.json",
    "sha256": "f5e8fc5c918284fcc892bce52d65a65abe06f9fba04a2893192327ac3a659115"
  },
  "tools/map-factory/capability-evidence/pl1072-water/calibration/pl1072-frozen/holdout-score.json": {
    "source_file": "tools/map-factory/calibration/pl1072-frozen/holdout-score.json",
    "sha256": "b42412a2e6575a462bc831505a5ed199d3592849964db4b30b5428787fae424b"
  },
  "tools/map-factory/capability-evidence/pl1072-water/calibration/pl1072-frozen/model.json": {
    "source_file": "tools/map-factory/calibration/pl1072-frozen/model.json",
    "sha256": "233534080d1f063fd96d5ca62167c3e3e2292503961184ed70f63a348a89e23d"
  },
  "tools/map-factory/capability-evidence/pl1072-water/score_water_panel.py": {
    "source_file": "tools/map-factory/score_water_panel.py",
    "sha256": "0344c9a6df8a1d793928dd80f35be46c14f7efda9e33f0459994d2b75fa1791e"
  },
  "tools/map-factory/capability-evidence/pl1072-water/fit_water_holdout.py": {
    "source_file": "tools/map-factory/fit_water_holdout.py",
    "sha256": "ed6f30910faf5891962e10ab21f7567cd07833f2fced1de8de5d9818c19a6e3a"
  },
  "tools/map-factory/capability-evidence/pl1072-water/water-calibration-panel.json": {
    "source_file": "tools/map-factory/water-calibration-panel.json",
    "sha256": "37d88f277973a709a61b496925bb911255bbeb201e863f61629377ca172c014e"
  },
  "tools/map-factory/capability-evidence/pl1072-water/water_calibration_panel.py": {
    "source_file": "tools/map-factory/water_calibration_panel.py",
    "sha256": "8499a9047bff93867724c532a325bbb24ba8a7715ee9d42577ce3fbaabff0595"
  },
  "tools/map-factory/capability-evidence/pl1072-water/water_risk_corpus.py": {
    "source_file": "tools/map-factory/water_risk_corpus.py",
    "sha256": "5a892c19c5beb52fb5d3663730750526c72944c6bdb090fbc5e42a2d103f1a90"
  },
  "tools/map-factory/capability-evidence/pl1072-water/water_risk.py": {
    "source_file": "tools/map-factory/water_risk.py",
    "sha256": "5108488a96cfc03330c940c66969ff4c708ba7465b5fe1abf89b56ab4773375b"
  },
  "tools/map-factory/capability-evidence/pl1072-water/water-risk-model.json": {
    "source_file": "tools/map-factory/water-risk-model.json",
    "sha256": "e3bcba51880755724812a665c1d3a5363abf8b888339e4fca417492a0559d5a0"
  },
  "tools/map-factory/capability-evidence/pl1072-water/run_water_panel.py": {
    "source_file": "tools/map-factory/run_water_panel.py",
    "sha256": "b9e49395924cba456faba0fe714519b9589695e969a2f92576d0497c38608ef7"
  },
  "tools/map-factory/capability-evidence/pl1072-water/stage_water_panel.py": {
    "source_file": "tools/map-factory/stage_water_panel.py",
    "sha256": "f2450cddf2eba44440846e658acaff3b4b46ad0bde81ad7b9243921ebbc523e5"
  }
};
const PREFIX = "tools/map-factory/capability-evidence/pl1072-water/";
const FROZEN = "calibration/pl1072-frozen/";
const sha = (raw) => createHash("sha256").update(raw).digest("hex");

export function waterStudy(read = (file) => readFileSync(ROOT + file)) {
  // Constants, not a manifest supplied by the assembler, anchor the original bytes.
  const files = Object.entries(WATER_FILES).map(([file, pin]) => {
    if (sha(read(file)) !== pin.sha256) throw new Error(`Changed original water evidence: ${file}`);
    return { file, ...pin, source_commit: WATER_SOURCE };
  });
  const json = (name) => JSON.parse(read(PREFIX + name));
  const score = json(FROZEN + "holdout-score.json");
  return {
    schema: 1,
    kind: "frozen_independent_geography_holdout",
    provenance: {
      publication_commit: WATER_SOURCE,
      pre_score_source_commit: "cc9d541604ef05ddf49d08f73d7819f5cf931075",
      writer_equivalent_capture_commit: "99702f1f0d37d9d924ba7c147547a82e5cde5765",
      writer_byte_equivalent_files: 21,
      native_runtime_commit: "6949182ccf3f8bf066fd24372e1bcfc31c8512f1",
      observed_at: null,
      observed_at_limits: "Native observation dates are not recorded in the saved score. Pre-score verification and publication dates are not native observation times.",
      source_url: `https://github.com/frontierkodiak/region-to-skylines/tree/${WATER_SOURCE}/tools/map-factory/calibration/pl1072-frozen`,
      files,
    },
    projection: { file: "water-calibration.mjs", sha256: sha(read("water-calibration.mjs")) },
    label_definition: {
      flood: "Original no-flooding gate: more than 0.05 km² deeper than 0.5 m beyond frozen initial/mapped-water references and 128 m exclusions.",
      drying: "Frozen water_risk_corpus.native_outcome: initialized optional-water loss as well as required endpoint/throughout losses. Not solely required-water failure, fresh-water intake or playability.",
      limits: "16 of 27 drying positives arise only from the broad optional-initialized-water criterion (PL-1190 review). The sole drying-negative square floods. All 28 original overall verdicts fail; producer image sidecars are not human acceptance.",
    },
    interpretation: "Failed qualification. Drying flags all 28, identical to always-warn. Flood-only clears show no demonstrated reduction. Candidate 3 m and the frozen study’s deployed-screen comparator at 1.5 m agree on all 28; no threshold promotion. Purposive panel, not global prevalence. Release HOLD; warning guard retained; no safe class. This is not a fresh qualification of the current 8e runtime or hosted product; the post-score sea-neighbour contract layer is not imported. Fresh-water intake and live Water/Start remain outside this study.",
    score,
    freeze: json(FROZEN + "freeze.json"),
    model: json(FROZEN + "model.json"),
    pre_score: json(FROZEN + "final-pre-score-verification.json"),
    audit: json(FROZEN + "holdout-score-audit.json"),
    disposition: json(FROZEN + "holdout-disposition.json"),
  };
}

export function validateWaterStudy(cap, read, expectedProjectionHash) {
  const load = read ?? ((file) => readFileSync(ROOT + file));
  if (sha(load("water-calibration.mjs")) !== expectedProjectionHash)
    throw new Error("Water projection tool changed");
  if (!isDeepStrictEqual(cap.calibration_studies, { [WATER_STUDY]: waterStudy(read) }))
    throw new Error("Water calibration projection is stale or unbound");
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const file = ROOT + "capabilities.json";
  const original = readFileSync(file, "utf8");
  // Replace only the final water capability; preserve every transport byte,
  // including numeric spellings and key order, in the existing ledger.
  const id = original.indexOf('"id": "water_risk"');
  const start = original.lastIndexOf("    {", id);
  const end = original.indexOf("\n    }\n  ],", id) + "\n    }".length;
  if (id < 0 || start < 0 || end < start) throw new Error("Missing final water capability");
  const cap = JSON.parse(original.slice(start, end));
  cap.calibration_studies = { [WATER_STUDY]: waterStudy() };
  const replacement = JSON.stringify(cap, null, 2).split("\n").map((line) => "    " + line).join("\n");
  writeFileSync(file, original.slice(0, start) + replacement + original.slice(end));
}

export function waterStudyPage(study, escape) {
  const s = study.score;
  const percent = (value) => `${(value * 100).toFixed(1)}%`;
  const rate = (r) => r.rate === null ? `NOT ESTIMABLE (n=${r.n})`
    : `${r.events}/${r.n} = ${percent(r.rate)} [${r.ci95.map(percent).join(", ")}]`;
  const table = (heads, rows, attrs = "") => `<div class="ledger-table"><table ${attrs}><thead><tr>${heads.map((h) => `<th scope="col">${escape(h)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((v, i) => `<${i ? "td" : "th"}${i ? "" : ' scope="row"'}>${escape(v)}</${i ? "td" : "th"}>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  const targets = Object.entries(s.metrics);
  const details = (title, value) => `<details><summary>${escape(title)}</summary><pre>${escape(JSON.stringify(value, null, 2))}</pre></details>`;
  const flag = (value) => value == null ? "Unknown" : value ? "Flagged" : "Clear";
  const outcome = (value) => value == null ? "Unknown" : value ? "Fail" : "Pass";
  const groups = (name, collection) => `<details><summary>${escape(name)}</summary>${table(
    ["Group / target", "TP / FP / TN / FN", "Precision · exact 95% CI", "Recall · exact 95% CI", "Unknown squares"],
    Object.entries(collection).flatMap(([group, metrics]) => Object.entries(metrics).map(([target, m]) => [
      `${group} / ${target}`, [m.tp, m.fp, m.tn, m.fn].join(" / "), rate(m.precision), rate(m.recall), m.unknown_squares.join(", ") || "None",
    ]))) }${details("Full group metrics and intervals", collection)}</details>`;
  return `<section data-calibration-study="${WATER_STUDY}"><h3>Independent water study · failed qualification</h3>
    <p>30 squares · 28 complete native observations · 2 capture failures Unknown. Release HOLD · warning guard retained · no safe class.</p>
    <p>Rates: exact two-sided 95% Clopper–Pearson intervals; displayed to one decimal percent. Full saved precision is retained below.</p>
    ${table(["Target", "TP / FP / TN / FN", "Precision · exact 95% CI", "Recall · exact 95% CI", "Specificity · exact 95% CI"], targets.map(([target, m]) => [target, [m.tp, m.fp, m.tn, m.fn].join(" / "), rate(m.precision), rate(m.recall), rate(m.specificity)]), 'data-water-targets')}
    ${table(["Target", "Always-warn precision / base failure", "Always-warn recall", "Target-only cleared risk"], targets.map(([target, m]) => [target, rate(m.always_warn_precision), rate(m.always_warn_recall), rate(m.cleared_risk)]))}
    <p>Drying flags all 28: identical to always-warn, not qualification. Flood-only clears fail 5/23 versus base 6/28: no demonstrated reduction.</p>
    ${table(["Screen", "Base either-target failure · exact 95% CI", "Cleared count", "Cleared risk", "Absolute / relative risk reduction"], [["Combined candidate (3 m)", s.rule_clearance], ["Study deployed-screen comparator (1.5 m)", s.deployed_product_clearance]].map(([name, c]) => [name, rate(c.base_risk), c.cleared_risk.n, rate(c.cleared_risk), "NOT ESTIMABLE / NOT ESTIMABLE"]), 'data-water-clearance')}
    <p>Zero clears is not zero risk. Candidate and study deployed-screen comparator flags match 28/28; no threshold promotion.</p>
    <details><summary>Definitions, scope and provenance</summary><dl>${Object.entries(study.label_definition).map(([k, v]) => `<dt>${escape(k)}</dt><dd>${escape(v)}</dd>`).join("")}</dl><p>${escape(study.interpretation)}</p><p>${escape(study.provenance.observed_at_limits)}</p><p>Native observation date: Unknown.</p>${details("Source roles and exact hashes", study.provenance)}</details>
    <details><summary>30 squares, including both unknowns</summary>${table(["Square", "Stratum / world region", "Flood flag / outcome", "Drying flag / outcome", "Observation date"], s.squares.map((r) => [r.slug, `${r.stratum} / ${r.world_region}`, `${flag(r.flags?.flood)} / ${outcome(r.labels?.flood)}`, `${flag(r.flags?.drying)} / ${outcome(r.labels?.drying)}`, "Unknown"]), 'data-water-squares')}${details("Original rows, package and report/verdict hashes", s.squares)}</details>
    ${groups("By intended water setting", s.per_stratum)}${groups("By world region", s.per_world_region)}
    ${details("Original full metrics and clearance (unrounded)", { metrics: s.metrics, rule_clearance: s.rule_clearance, deployed_product_clearance: s.deployed_product_clearance })}
    <details><summary>Original saved files</summary><ul>${study.provenance.files.map(({ file, sha256, source_file }) => `<li><a href="${escape(file)}">${escape(source_file)}</a> · SHA256 <code>${escape(sha256)}</code></li>`).join("")}</ul><a href="${escape(study.provenance.source_url)}">Immutable publication</a></details>
    </section>`;
}

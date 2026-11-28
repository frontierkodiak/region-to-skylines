import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { isDeepStrictEqual } from "node:util";
import { WATER_FILES, WATER_STUDY, waterStudy, validateWaterStudy } from "../water-calibration.mjs";
import { validateLedger, ledgerPage, WATER_PROJECTION_SHA } from "../capability-ledger.mjs";
import { checkCapabilities } from "../capability-model.js";
import { beforeStockWater } from "./stock-water-ledger.mjs";

const read = (file) => readFileSync(new URL("../" + file, import.meta.url));
const ledger = JSON.parse(read("capabilities.json"));
const cap = ledger.capabilities.find((c) => c.id === "water_risk");
const study = cap.calibration_studies[WATER_STUDY];
const sha = (raw) => createHash("sha256").update(raw).digest("hex");

test("saved study deterministically projects original bytes, distinct from historical seed", () => {
  assert.deepEqual(waterStudy(), waterStudy());
  assert.deepEqual(study, waterStudy());
  validateLedger(ledger);
  assert.equal(cap.calibration.squares, 5);
  assert.equal(cap.calibration.scored_complete_runs, 50);
  assert.deepEqual(study.score.coverage, { planned: 30, complete: 28, unscored: ["lake-shore-south-america", "low-coast-africa"] });
  assert.equal(study.score.squares.length, 30);
  assert.equal(study.provenance.observed_at, null);
  assert.equal(study.provenance.pre_score_source_commit, "cc9d541604ef05ddf49d08f73d7819f5cf931075");
  assert.equal(study.provenance.native_runtime_commit, "6949182ccf3f8bf066fd24372e1bcfc31c8512f1");
  assert.ok(!ledger.evidence_studies[WATER_STUDY]);
  assert.deepEqual(JSON.parse(beforeStockWater(read("capabilities.json").toString())).capabilities.find(c => c.id === "water_risk").game_agreement, []);
  assert.equal(study.audit.score_sha256, "b42412a2e6575a462bc831505a5ed199d3592849964db4b30b5428787fae424b");
});

test("the new failed packages do not invent six observations or a cleared-water prediction", () => {
  const trial = JSON.parse(read("tools/map-factory/capability-evidence/pl1191-continuous-water/verdicts.json"));
  assert.equal(trial.rows.length, 8);
  for (const study of ["pl1191-stock-water", "pl1191-local-budget", "pl1191-continuous-water"]) {
    const observed = cap.game_agreement.filter(row => row.study === study);
    assert.deepEqual(observed.map(row => row.square), ["asheville", "pittsburgh"]);
    for (const row of observed) {
      const raw = read(row.evidence[0]), verdict = JSON.parse(raw);
      assert.equal(row.verdict_json_sha256, sha(raw));
      assert.equal(row.artifact_sha256, verdict.artifact_sha256);
      assert.notEqual(row.artifact_sha256, row.verdict_json_sha256);
      assert.equal(row.observed, verdict.water_verdict === "pass");
      assert.equal(row.predicted, null);
      if (study === "pl1191-continuous-water") {
        const latest = trial.rows.find(r => r.slug === row.square);
        assert.equal(latest.artifact_sha256, verdict.artifact_sha256);
        assert.equal(latest.flood_km2, verdict.flood_km2);
        assert.equal(latest.minimum_original_point_retention, verdict.minimum_original_point_retention);
        const overlay = row.square === "asheville" ? "asheville-construction-overlay.png" : "pittsburgh-overlay.png";
        assert.ok(read(`tools/map-factory/capability-evidence/pl1191-continuous-water/${overlay}`).length > 1000);
      }
    }
  }
  const unrun = trial.rows.filter(row => row.observed_at === null);
  assert.equal(unrun.length, 6);
  const resumed = trial.rows.find(row => row.slug === "pittsburgh");
  assert.ok(resumed.game_minutes >= 60);
  const controls = JSON.parse(read("tools/map-factory/capability-evidence/pl1191-continuous-water/pittsburgh-controls-verified.json"));
  assert.equal(controls.sources, 88);
  assert.equal(controls.captures, 13);
  assert.equal(controls.all_record_id_type_position_target_input_output_match, true);
  assert.ok(unrun.every(row => row.water_verdict === "unknown"));
});

test("all immutable byte mutations, even coherent score/model/projection replacements, are rejected", () => {
  for (const file of Object.keys(WATER_FILES)) {
    const mutatedRead = (path) => path === file ? Buffer.concat([read(path), Buffer.from(" ")]) : read(path);
    assert.throws(() => waterStudy(mutatedRead), /Changed original water evidence/);
  }
  const file = study.provenance.files.find((f) => f.file.endsWith("holdout-score.json")).file;
  const rewritten = structuredClone(study.score); rewritten.metrics.flood.tp++;
  const bytes = Buffer.from(JSON.stringify(rewritten));
  const modified = structuredClone(cap);
  modified.calibration_studies[WATER_STUDY].score = rewritten;
  modified.calibration_studies[WATER_STUDY].provenance.files.find((f) => f.file === file).sha256 = sha(bytes);
  assert.throws(() => validateWaterStudy(modified, (p) => p === file ? bytes : read(p), WATER_PROJECTION_SHA), /Changed original/);
  const toolRead = (p) => p === "water-calibration.mjs" ? Buffer.concat([read(p), Buffer.from("\n// altered\n")]) : read(p);
  const toolRewrite = structuredClone(cap);
  toolRewrite.calibration_studies[WATER_STUDY].projection.sha256 = sha(toolRead("water-calibration.mjs"));
  assert.throws(() => validateWaterStudy(toolRewrite, toolRead, WATER_PROJECTION_SHA), /projection tool changed/);
  assert.throws(() => waterStudy((p) => { if (p === file) throw new Error("missing score"); return read(p); }), /missing score/);
});

test("every projected field is bound, not just an assembler verification boolean", () => {
  const walk = (value, path = []) => {
    if (value !== null && typeof value === "object") return Object.entries(value).flatMap(([k, v]) => walk(v, [...path, k]));
    return [path];
  };
  for (const path of walk(study)) {
    const changed = structuredClone(ledger);
    let target = changed.capabilities.find((c) => c.id === "water_risk").calibration_studies[WATER_STUDY];
    for (const key of path.slice(0, -1)) target = target[key];
    target[path.at(-1)] = "tampered";
    assert.throws(() => validateLedger(changed), /projection is stale or unbound/);
  }
  for (const mutate of [(c) => {delete c.calibration_studies;}, (c) => {c.calibration_studies[WATER_STUDY].score.squares.pop();}]) {
    const changed = structuredClone(ledger); mutate(changed.capabilities.find((c) => c.id === "water_risk"));
    assert.throws(() => validateLedger(changed), /stale or unbound/);
  }
});

test("saved labels/counts reproduce overall and groups without regenerating outcomes or intervals", () => {
  const s = study.score;
  const known = s.squares.filter((r) => r.status === "complete");
  assert.equal(known.length, 28);
  assert.equal(known.filter((r) => r.labels.drying && !r.original_dry_gate_failed && !r.required_water_loss).length, 16);
  assert.equal(known.filter((r) => !r.labels.drying)[0].labels.flood, true);
  const check = (rows, metrics) => {
    for (const target of ["flood", "drying"]) {
      const counts = {tp:0, fp:0, tn:0, fn:0};
      for (const r of rows.filter((r) => r.labels[target] !== null)) counts[r.flags[target] ? r.labels[target] ? "tp" : "fp" : r.labels[target] ? "fn" : "tn"]++;
      assert.deepEqual(counts, Object.fromEntries(Object.keys(counts).map((k) => [k, metrics[target][k]])));
    }
  };
  check(s.squares, s.metrics);
  for (const [key, groups] of [["stratum",s.per_stratum],["world_region",s.per_world_region]])
    for (const [group, metrics] of Object.entries(groups)) check(s.squares.filter((r) => r[key] === group), metrics);
  assert.equal(s.metrics.flood.cleared_risk.events, 5);
  assert.equal(s.metrics.flood.cleared_risk.n, 23);
  assert.equal(s.metrics.drying.identical_to_always_warn, true);
  for (const clearance of [s.rule_clearance, s.deployed_product_clearance]) {
    assert.deepEqual(clearance.cleared_risk, {n:0, events:0, rate:null, ci95:null});
    for (const field of ["absolute_risk_reduction","relative_risk","relative_risk_reduction"]) assert.equal(clearance[field], null);
  }
});

test("page shows failed qualification and unrounded evidence; study cannot promote live water/start", () => {
  const html = ledgerPage(ledger);
  for (const text of ["failed qualification", "Historical seed · 5 squares / 50 runs", "NOT ESTIMABLE (n=0)", "20.0% [0.5%, 71.6%]", "16.7% [0.4%, 64.1%]", "96.4% [81.7%, 99.9%]", "initialized optional-water loss", "Native observation date: Unknown", "By world region", "5/23 versus base 6/28"]) assert.ok(html.includes(text), text);
  assert.ok(!html.includes("independent geography is still incomplete"));
  for (const ref of study.provenance.files) assert.ok(html.includes(`href="${ref.file}"`));
  const without = structuredClone(ledger); delete without.capabilities.find((c) => c.id === "water_risk").calibration_studies;
  for (const mode of ["estimate", "export"]) {
    const input = {schema:1, mode};
    const current = checkCapabilities(input, ledger), original = checkCapabilities(input, without);
    assert.ok(isDeepStrictEqual(current, original));
    for (const id of ["water", "start"]) assert.equal(current.capabilities[id].level, "unknown");
  }
});

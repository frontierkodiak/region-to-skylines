import {test} from "node:test";
import assert from "node:assert/strict";
import {createHash} from "node:crypto";
import {readFileSync} from "node:fs";
import {execFileSync} from "node:child_process";
import {gunzipSync} from "node:zlib";
import {startWaterStudy, validateStartWaterStudy, START_WATER_MANIFEST, START_WATER_PREFIX, START_WATER_STUDY} from "../start-water-study.mjs";
import {validateLedger, ledgerPage, START_WATER_PROJECTION_SHA} from "../capability-ledger.mjs";
import {checkCapabilities} from "../capability-model.js";
const read = (file) => readFileSync(new URL("../" + file, import.meta.url));
const sha = (v) => createHash("sha256").update(v).digest("hex");
const ledger = JSON.parse(read("capabilities.json"));
const study = ledger.witness_studies[START_WATER_STUDY];

test("import is reproducible; every unowned ledger byte and all four certificates stay exact", () => {
  const original = read("capabilities.json");
  execFileSync(process.execPath, ["start-water-study.mjs"], {cwd:new URL("..",import.meta.url)});
  assert.deepEqual(read("capabilities.json"), original);
  assert.deepEqual(startWaterStudy(), study);
  assert.equal(study.projection.sha256, "294e3e3fc301b96311fce546fb2bf6db0951067247f92a6250f758454538f21b");
  let text = original.toString();
  for (const id of ["start","water"]) {
    const marker = text.indexOf('"id": "' + id + '"'), begin = text.lastIndexOf("    {",marker);
    const end = text.indexOf("\n    }",marker) + "\n    }".length;
    text = text.slice(0,begin) + text.slice(end);
  }
  // The directed-rail and rail-research adapters own their Rail references; they are separate producers.
  text = text.replace('      "rail_study": "directed-rail-v3",\n', "");
  text = text.replace(',\n      "rail_research_studies": [\n        "rail-query-model-v1",\n        "rail-junction-fit-v1",\n        "rail-stock-holdout-v1"\n      ]', "");
  // The outside-query adapter owns its Road, Ship and Air references; it is a separate producer.
  text = text.replaceAll(',\n      "outside_research_studies": [\n        "outside-query-model-v1"\n      ]', "");
  // The outside-stock adapter owns its own Road, Ship and Air references; it is a separate producer.
  text = text.replaceAll(',\n      "outside_stock_studies": [\n        "outside-stock-budget-v1"\n      ]', "");
  // The outside-readiness adapter owns its own Road, Ship and Air references; it is a separate producer.
  text = text.replaceAll(',\n      "outside_readiness_studies": [\n        "outside-readiness-stock-v2"\n      ]', "");
  text = text.slice(0,text.indexOf('\n  "witness_studies":') - 1) + "\n}\n";
  assert.equal(sha(text), "4f459361a10779d3a0a5ab4886da02307e65ffbf4ad9f5a73a4dea4d4b0e4eff", "exact parent bytes outside owned fragments");
  assert.equal(ledger.native_path_certificates.length,4);
  assert.equal(study.report.rows.length,22);
  assert.equal(study.predictions.rows.length,11);
  assert.equal(study.provenance.observations_sha256,"85ce024d015ef0b43c801770d49df2d09ffb6274a9029537855396d0631b35a5");
  validateLedger(ledger);
});

test("immutable file, manifest, projection and coherent ledger mutations are rejected", () => {
  const manifest = JSON.parse(read(START_WATER_MANIFEST));
  // Constructed byte mutations of actual saved files, not new native observations.
  for (const {file} of manifest.files) {
    assert.throws(() => startWaterStudy((p) => p === file ? Buffer.concat([read(p),Buffer.from(" ")]) : read(p)), /Changed original/);
  }
  assert.throws(() => startWaterStudy((p) => p === START_WATER_MANIFEST ? Buffer.from("{}") : read(p)), /file manifest/);
  assert.throws(() => validateStartWaterStudy(ledger,(p) => p === "start-water-study.mjs" ? Buffer.from("// changed") : read(p),START_WATER_PROJECTION_SHA), /projection tool changed/);
  for (const mutate of [
    (s) => s.report.rows.pop(),
    (s) => {s.report.rows[0].predicted=false;},
    (s) => {s.report.rows[0].observed=false;},
    (s) => {s.report.rows[0].observed_at="invented";},
    (s) => {s.report.rows[0].water_risk={};},
    (s) => {s.report.summary.held_out.start.positive_witness_agreement=0;},
    (s) => {s.artifact_bindings[7].artifact_sha256=s.artifact_bindings[7].selection.package_sha256;},
    (s) => {s.artifact_bindings[8].selection.package_sha256="invented";},
    (s) => {s.reference_quantity.rows[0].predicted=true;},
    (s) => {s.first_hour.comparison.cases["grand-canyon-northeast"].after.first_hour="pass";},
    (s) => {s.first_hour.comparison.stock_policy_qualified=false;},
    (s) => {s.provenance.components[0].runtime_adoption=true;},
  ]) {
    const changed=structuredClone(ledger);mutate(changed.witness_studies[START_WATER_STUDY]);
    assert.throws(() => validateLedger(changed), /projection is stale or unbound/);
  }
  const promoted=structuredClone(ledger);promoted.capabilities.find((c)=>c.id==="start").exporter_check="tools/map-factory/region.py:start_area";
  assert.throws(()=>validateLedger(promoted),/saved-study scope changed/);
});

test("all saved rows, risks, exact raw evidence and actual package/input bindings survive", () => {
  const report=study.report;
  for (const entry of study.predictions.rows) {
    const binding=study.artifact_bindings.find((r)=>r.slug===entry.slug);
    assert.equal(binding.artifact_sha256,binding.export_stage.crp_sha256);
    assert.deepEqual(binding.physical_inputs_sha256,entry.prediction.inputs_sha256);
    const rows=report.rows.filter((r)=>r.square.slug===entry.slug);
    assert.equal(rows.length,2);
    for(const r of rows) {
      assert.equal(r.artifact_sha256,binding.artifact_sha256);
      assert.equal(r.model_sha256,study.provenance.model_sha256);
      assert.equal(r.predicted,entry.prediction.capabilities[r.capability_id].predicted);
      assert.deepEqual(r.water_risk,rows[0].water_risk);
      assert.deepEqual(r.water_risk.inputs_sha256,binding.physical_inputs_sha256);
      for(const ref of r.evidence) {
        const bytes=read(START_WATER_PREFIX+ref.path);
        assert.equal(sha(bytes),ref.sha256);
        if(ref.encoding==="gzip")assert.equal(sha(gunzipSync(bytes)),ref.decompressed_sha256);
      }
    }
  }
  const yosemite=study.artifact_bindings.find((r)=>r.slug==="yosemite");
  assert.equal(yosemite.selection_package_matches_artifact,false);
  assert.match(yosemite.artifact_sha256,/^bc0d9f4/);
  assert.match(yosemite.selection.package_sha256,/^17020ec/);
  for(const r of report.rows.filter((r)=>r.square.slug==="yosemite"))assert.equal(r.observed,null);
  for(const r of study.artifact_bindings.slice(8)) {
    assert.equal(r.selection_package_matches_artifact,null);
    assert.equal(r.selection.package_sha256,undefined);
    assert.equal(r.selection.input_files_sha256,undefined);
  }
});

test("saved split summaries reproduce without rejudging; unknowns never become negatives", () => {
  for(const split of ["fitting","held_out"])for(const id of ["start","water"]) {
    const rows=study.report.rows.filter((r)=>r.split===split&&r.capability_id===id), saved=study.report.summary[split][id];
    const positives=rows.filter((r)=>r.predicted===true);
    assert.equal(rows.length,saved.registered_squares);
    assert.equal(positives.length,saved.positive_predictions);
    assert.equal(positives.filter((r)=>r.observed===true).length,saved.agreed);
    assert.equal(positives.filter((r)=>r.observed===false).length,saved.disagreed);
    assert.equal(positives.filter((r)=>r.observed===null).length,saved.unscored_positive);
  }
  assert.equal(study.report.summary.fitting.start.agreed,2);
  assert.equal(study.report.summary.fitting.water.agreed,3);
  assert.equal(study.report.summary.held_out.water.positive_witness_agreement,0.5);
  assert.equal(study.report.summary.held_out.start.positive_witness_agreement,null);
  assert.equal(study.report.summary.held_out.start.positive_predictions,0);
  const hk=study.report.rows.find((r)=>r.capability_id==="water"&&r.square.slug==="hong-kong-northeast");
  assert.equal(hk.observed,false);assert.equal(hk.predicted,true);
  const gc=study.report.rows.find((r)=>r.capability_id==="water"&&r.square.slug==="grand-canyon-northeast");
  assert.equal(gc.observed,null);
  for(const r of study.reference_quantity.rows) {
    assert.equal(r.predicted,null);assert.equal(r.model_agreement_scored,false);
    assert.equal(r.cycles,843);assert.equal(r.quantity_supported,true);
  }
  assert.equal(study.reference_quantity.rows[0].polluted_delivery_cycles,733);
  assert.equal(study.reference_quantity.rows[1].polluted_delivery_cycles,0);
});

test("24 unchanged verdicts and all 11 first-hour pairs retain separate player metrics", () => {
  const c=study.first_hour.comparison;
  let count=0;
  for(const arm of ["before","after","stock"]) {
    const rows=arm==="stock"?c.controls:Object.fromEntries(Object.entries(c.cases).map(([k,v])=>[k,v[arm]]));
    for(const [slug,r] of Object.entries(rows)) {
      const bytes=read(START_WATER_PREFIX+`first-hour/verdicts/${arm}/${slug}/verdict.json`);
      assert.equal(sha(bytes),r.verdict_sha256);count++;
    }
  }
  assert.equal(count,24);
  assert.equal(Object.keys(c.cases).length,11);
  for(const [arm,expected] of [["before",4],["after",3]])
    assert.equal(Object.values(c.cases).filter((r)=>r[arm].first_hour==="pass").length,expected);
  assert.equal(c.before.passed,3);assert.equal(c.after.passed,2);
  assert.equal(c.first_hour_survival.original_player_baseline.passed,3);
  assert.equal(c.original_player_baseline.passed,2);
  assert.deepEqual(Object.entries(c.cases).filter(([,r])=>r.before.first_hour!==r.after.first_hour).map(([k])=>k),["grand-canyon-northeast"]);
  assert.equal(c.cases.charleston.before.overall,"fail");
  assert.equal(c.cases.charleston.after.overall,"fail");
});

test("generated page separates oracles and source components cannot promote live capabilities", () => {
  const html=ledgerPage(ledger);
  for(const text of ["NOT ESTIMABLE (n=0)","130/843","6.038","peak 540","733","Regional holdout","2/3","3/3","1/2","All 11 start rows","All 11 water rows","not runtime-adopted","17020ec","bc0d9f4","Historical 1/8"])assert.ok(html.includes(text),text);
  assert.ok(!html.includes("awaiting start oracle"));
  for(const {file} of study.provenance.files)assert.ok(html.includes(`href="${file}"`),file);
  const without=structuredClone(ledger);delete without.witness_studies;
  for(const cap of without.capabilities)delete cap.witness_study;
  for(const mode of ["estimate","export"]) {
    const current=checkCapabilities({schema:1,mode},ledger);
    assert.deepEqual(current,checkCapabilities({schema:1,mode},without));
    for(const id of ["start","water"])assert.equal(current.capabilities[id].level,"unknown");
  }
});

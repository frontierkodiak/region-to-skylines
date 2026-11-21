import { test } from "node:test";
import assert from "node:assert/strict";
import {
  liveFootprint,
  footprintCenters,
  evaluateStart,
} from "../start-model.js";
import { footprintDetail } from "../capability-ui.js";
import { captureEstimate } from "../capability-inputs.js";
const N = 1081;
const flat = () => new Float64Array(N * N).fill(100),
  dry = () => new Float64Array(N * N);

test("constructed footprint extent, threshold equality and missing coverage", () => {
  const g = flat(),
    d = dry();
  const result = liveFootprint(g, d);
  assert.equal(result.candidates, 529);
  assert.equal(result.footprint, "candidate");
  assert.equal(result.hookup, "unknown");
  assert.equal(result.level, "unknown");
  d.fill(0.1);
  assert.equal(liveFootprint(g, d).candidates, 529);
  d.fill(0.100001);
  assert.equal(liveFootprint(g, d).footprint, "unknown");
  for (const input of [
    new Float64Array(100),
    new Float64Array(N * N).fill(NaN),
  ])
    assert.equal(liveFootprint(input, d).footprint, "unknown");
  assert.equal(liveFootprint(g, d, { spacing: 64 }).footprint, "unknown");
  assert.equal(
    liveFootprint(flat(), dry(), { n: 25, half: 192 }).footprint,
    "unknown",
  );
  const missing = evaluateStart({});
  assert.equal(missing.predicted, null);
  assert.match(
    footprintDetail(result),
    /384 × 384 m candidate.*Hookup: Unknown.*Not comparable/,
  );
});

test("constructed north-first witness stays in the dry southern footprint", () => {
  const g = flat(),
    d = new Float64Array(N * N).fill(1);
  for (let r = 540; r < 610; r++)
    for (let c = 500; c < 581; c++) d[r * N + c] = 0;
  const result = liveFootprint(g, d);
  assert.equal(result.footprint, "candidate");
  assert.ok(result.center_xz[1] < 0);
  const slope = flat();
  for (let r = 0; r < N; r++)
    for (let c = 0; c < N; c++) slope[r * N + c] = c * 4;
  assert.equal(liveFootprint(slope, dry()).footprint, "unknown");
  const narrow = new Float64Array(N * N).fill(1);
  for (let r = 530; r < 551; r++)
    for (let c = 0; c < N; c++) narrow[r * N + c] = 0;
  assert.equal(
    liveFootprint(g, narrow).footprint,
    "unknown",
    "dry strip narrower than 384m cannot fit",
  );
});

test("one capture feeds footprint and optional evidence; cancellation stays cancellation", async () => {
  let calls = 0;
  const capture = async () => {
    calls++;
    return {
      game: flat(),
      banks: flat(),
      seaLevel: null,
      geometry: {
        sq: { lon: 0, lat: 0, scale: 1, rotation: 0 },
        roads: [],
        oceans: [],
      },
    };
  };
  const sources = {
    capture,
    landcover: async () => null,
    deposits: async () => null,
  };
  const result = await captureEstimate({}, { sources });
  assert.equal(calls, 1);
  assert.equal(result.input.start_footprint.footprint, "candidate");
  assert.equal(result.input.start_footprint.hookup, "unknown");
  const controller = new AbortController();
  controller.abort(new Error("cancelled"));
  await assert.rejects(
    () => captureEstimate({}, { sources, signal: controller.signal }),
    /cancelled/,
  );
});

test("slope equality and relief equality use inclusive predicates", () => {
  // Exactly representable relief; 8m over 24 grid intervals.
  const g = flat();
  for (let r = 0; r < N; r++)
    for (let c = 0; c < N; c++) g[r * N + c] = Math.min(c, 540) * 0.25;
  assert.ok(footprintCenters(g, dry()).centers.length > 0);
  assert.equal(
    evaluateStart({ planner_enabled: { start: false } }).reason,
    "planner_disabled",
  );
});


test("active source and parameter mutations cannot inherit archived agreement", async () => {
  const {readFileSync}=await import("node:fs");
  const {validateLedger}=await import("../capability-ledger.mjs");
  const ledger=JSON.parse(readFileSync(new URL("../capabilities.json",import.meta.url)));
  for(const mutate of [
    (c)=>{c.runtime_model.parameters.max_slope=0.16;},
    (c)=>{c.runtime_model.source_sha256["start-model.js"]="0".repeat(64);},
    (c)=>{c.runtime_model.agreement="qualified";},
    (c)=>{c.exporter_check="tools/map-factory/region.py:start_area";},
  ]) {
    const changed=structuredClone(ledger);mutate(changed.capabilities.find((c)=>c.id==="start"));
    assert.throws(()=>validateLedger(changed),/saved-study scope changed/);
  }
  assert.equal(ledger.capabilities.find((c)=>c.id==="start").game_agreement.length,0);
  assert.equal(ledger.native_path_certificates.length,4);
});

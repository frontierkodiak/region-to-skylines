import { test } from "node:test";
import assert from "node:assert/strict";
import { CS1 } from "../terrain.js";
import { DRAMA, STOCK_TERRAIN_BAND, fitDrama, dramaFit, terrainShape, blurTrend, gameHeightAt, panelFlatness } from "../terrain-drama.mjs";

const N = CS1.px;
// A smooth field with a given regional relief and a small hill pattern: deterministic, no network.
function field({ relief, hills = 0, period = 40, sea = false }) {
  const grid = new Float32Array(N * N);
  for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
    const u = c / (N - 1), v = r / (N - 1);
    const regional = relief * (0.55 * u + 0.45 * v);
    const local = hills * Math.sin((2 * Math.PI * c) / period) * Math.cos((2 * Math.PI * r) / period);
    grid[r * N + c] = (sea ? -relief * 0.3 : 0) + regional + local;
  }
  return grid;
}

test("a flat square gains relief, a steep one gives it back, and both stay in the stock band", () => {
  const flat = field({ relief: 40, hills: 6 });
  const steep = field({ relief: 1800, hills: 20 });
  const flatFit = fitDrama(flat, { spacing: 16 });
  const steepFit = fitDrama(steep, { spacing: 16 });
  assert.ok(flatFit.low > 1.2, `flat regional gain ${flatFit.low} should stretch`);
  assert.ok(steepFit.high < 1 || steepFit.low < 1, "the steep square should compress somewhere");
  // The flat square can reach the band; the steep one is limited by the game's 1,024 m
  // ceiling, which must be reported rather than hidden.
  assert.equal(flatFit.limitedBy, null);
  assert.equal(steepFit.limitedBy, "headroom");
  const inBand = (fit, metric) => {
    const band = STOCK_TERRAIN_BAND[metric];
    assert.ok(fit.achieved[metric] >= band.p25 - 0.05 - band.median * 0.02, `${metric} ${fit.achieved[metric]} below band`);
    assert.ok(fit.achieved[metric] <= band.p75 + 0.05 + band.median * 0.02, `${metric} ${fit.achieved[metric]} above band`);
  };
  for (const metric of ["roughness_percent", "central_terrain_diversity_m"]) inBand(flatFit, metric);
  inBand(steepFit, "central_terrain_diversity_m");
  assert.ok(steepFit.achieved.roughness_percent <= STOCK_TERRAIN_BAND.roughness_percent.p75,
    "a ceiling-limited square must not overshoot the band it cannot fill");
});

test("gains are positive, deterministic, and the result fits under the ceiling", () => {
  const grid = field({ relief: 2000, hills: 30 });
  const a = fitDrama(grid, { spacing: 16 }), b = fitDrama(grid, { spacing: 16 });
  assert.deepEqual([a.low, a.high], [b.low, b.high]);
  assert.ok(a.low > 0 && a.high > 0);
  const fit = dramaFit(grid, grid, a);
  assert.ok(fit.gameMax <= CS1.maxHeight, `game max ${fit.gameMax}`);
  assert.ok(fit.gameMax <= 1000 + 0.01, `fit targets the 1,000 m ceiling, got ${fit.gameMax}`);
  assert.ok(fit.gameMin >= 0);
  assert.equal(fit.clipped, 0);
});

test("sea squares keep sea level fixed and give land 1 m of freeboard", () => {
  const grid = field({ relief: 200, sea: true });
  const sea = new Uint8Array(N * N);
  for (let i = 0; i < sea.length; i++) sea[i] = grid[i] < 0 ? 1 : 0;
  const spec = fitDrama(grid, { sea, spacing: 16 });
  const fit = dramaFit(grid, grid, spec, { sea });
  assert.ok(fit.seaLevel > 0);
  let deep = 0, free = 0;
  for (let i = 0; i < sea.length; i++) {
    if (sea[i]) { assert.ok(fit.game[i] <= fit.seaLevel - 10 + 1e-6, "sea is at least 10 m deep"); deep++; }
    else assert.ok(fit.game[i] >= fit.seaLevel + 1 - 1e-6, "land keeps 1 m of freeboard");
    if (!sea[i]) free++;
  }
  assert.ok(deep > 0 && free > 0);
});

test("local gain scales a carve: a game-metre river stays that deep", () => {
  const grid = field({ relief: 400, hills: 10 });
  const spec = fitDrama(grid, { spacing: 16 });
  const one = dramaFit(grid, grid, spec);
  const carved = Float32Array.from(grid);
  const depthReal = 10 / spec.high;
  carved[Math.floor(carved.length / 2)] -= depthReal;
  const two = dramaFit(grid, carved, spec);
  const at = Math.floor(carved.length / 2);
  assert.ok(Math.abs((one.game[at] - two.game[at]) - 10) < 0.2, `carve depth ${one.game[at] - two.game[at]} should be 10 game m`);
});

test("a real height can be placed back on the fit's own scale", () => {
  const grid = field({ relief: 700, hills: 25 });
  const spec = fitDrama(grid, { spacing: 16 });
  const fit = dramaFit(grid, grid, spec);
  for (const i of [0, 12345, Math.floor(grid.length / 2), grid.length - 1]) {
    const mapped = gameHeightAt(fit, i, grid[i]);
    assert.ok(Math.abs(mapped - fit.game[i]) < 1e-3, `node ${i}: ${mapped} vs ${fit.game[i]}`);
  }
});

test("blurTrend is a normalised, edge-clamped smoothing", () => {
  const flat = new Float32Array(N * N).fill(7);
  assert.ok(blurTrend(flat, 40).every((v) => Math.abs(v - 7) < 1e-6));
  const step = field({ relief: 0, hills: 0 });
  for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) step[r * N + c] = c < N / 2 ? 0 : 100;
  const out = blurTrend(step, 40);
  assert.ok(out[0] < 5 && out[out.length - 1] > 95);
  assert.ok(Math.abs(out[Math.floor(N / 2) * N + Math.floor(N / 2)] - 50) < 20, "the step is smoothed across its edge");
});
test("the two measures read the whole grid and the central 25 tiles", () => {
  const grid = new Float32Array(N * N).fill(300);
  const flat = terrainShape(grid);
  assert.equal(flat.roughness_percent, 0);
  assert.equal(flat.central_terrain_diversity_m, 0);
  for (let r = 400; r < 700; r++) for (let c = 0; c < N; c++) grid[r * N + c] += 100;
  const shaped = terrainShape(grid);
  assert.ok(shaped.roughness_percent > 0);
  assert.ok(shaped.central_terrain_diversity_m > 0);
});

test("the panel flatness score is the game's own window and orientation", () => {
  const flat = new Float32Array(N * N).fill(300);
  assert.equal(panelFlatness(flat), 1);
  // a one-sided step: the native score's window is not vertically symmetric, so a north/south
  // asymmetry must show up. Put the step only in the south half's rows.
  const grid = new Float32Array(N * N).fill(300);
  for (let r = 0; r < 400; r++) for (let c = 0; c < N; c++) grid[r * N + c] += 120;
  const top = panelFlatness(grid);
  const mirrored = new Float32Array(N * N);
  for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) mirrored[r * N + c] = grid[(N - 1 - r) * N + c];
  assert.notEqual(top, panelFlatness(mirrored));
});

test("the buildable floor caps the gains where the dry share is low", () => {
  // A square whose band fit wants steep local relief, in a marsh: the floor has to bite.
  const grid = field({ relief: 40, hills: 30, period: 20 });
  const open = fitDrama(grid, { spacing: 16 });
  assert.equal(open.buildable.dry_fraction, 1);
  // a marsh: about 40% of the central 25 tiles is water, so the panel's dry term is about 0.6
  const wet = new Uint8Array(N * N);
  for (let r = 240; r <= 840; r++) for (let c = 240; c <= 840; c++) if ((r + c) % 10 < 3) wet[r * N + c] = 1;
  const capped = fitDrama(grid, { spacing: 16, wet });
  assert.ok(capped.buildable.dry_fraction < 0.75 && capped.buildable.dry_fraction > 0.6, `dry ${capped.buildable.dry_fraction}`);
  assert.ok(capped.buildable.estimated_percent >= DRAMA.buildable_margin + STOCK_TERRAIN_BAND.buildable_percent.p25,
    `estimated buildable ${capped.buildable.estimated_percent}`);
  assert.equal(capped.limitedBy, "buildable_floor");
  assert.ok(capped.low < open.low && capped.high < open.high, "the floor pulls both gains down");
});

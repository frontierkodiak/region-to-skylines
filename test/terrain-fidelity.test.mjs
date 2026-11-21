import test from "node:test";
import assert from "node:assert/strict";
import { CS1, squareToLonLat, fitHeights } from "../terrain.js";
import { shoreDistances, sourceFaithfulTerrain } from "../tools/map-factory/terrain_fidelity.mjs";

const sq = { lon: 0, lat: 0, scale: 1, rotation: 0 };
const empty = { rivers: [], riverAreas: [], lakes: [], oceans: [] };
const polygon = (left, bottom, right, top) => ({ rings: [[
  [left, bottom], [right, bottom], [right, top], [left, top], [left, bottom],
].map(([x, z]) => squareToLonLat(sq, x, z))] });

test("shore distance follows land, not artificial map edges", () => {
  const sea = Uint8Array.from({ length: 25 }, (_, i) => i % 5 >= 2 ? 1 : 0);
  const distance = shoreDistances(sea, 5, 4);
  for (let row = 0; row < 5; row++) assert.deepEqual([...distance.slice(row * 5 + 2, row * 5 + 5)], [1, 2, 3]);
  assert.deepEqual([...shoreDistances(new Uint8Array(9).fill(1), 3, 4)], new Array(9).fill(4));
});

test("engineered sea is wet and uncarved land/banks retain source elevations", () => {
  const raw = Float32Array.from({ length: CS1.px ** 2 }, (_, i) => 0.001 * (i % CS1.px) + 0.001 * Math.floor(i / CS1.px));
  const water = { ...empty, oceans: [polygon(0, -9000, 9000, 9000)] };
  const result = sourceFaithfulTerrain(raw, sq, water);
  let largestNeighbourStep = 0;
  for (let i = 0; i < raw.length; i++) {
    const { game, sea, seaLevel, base, verticalScale } = result.fit;
    if (sea[i]) assert.ok(game[i] < seaLevel);
    const expected = (result.ground[i] - base) * verticalScale + 50;
    assert.ok(Math.abs(result.banks[i] - expected) < 1e-4);
    if (!sea[i]) assert.equal(game[i], result.banks[i]);
    if (i % CS1.px > 0) largestNeighbourStep = Math.max(largestNeighbourStep, Math.abs(game[i] - game[i - 1]));
  }
  assert.equal(result.policy.native_verified, false);
  assert.equal(result.policy.dry_land_raised_vertices, 0);
  assert.ok(largestNeighbourStep < 3); // no inherited 11 m binary shoreline step
});

test("inland uncarved elevations reproduce the existing affine fit", () => {
  const raw = Float32Array.from({ length: CS1.px ** 2 }, (_, i) => 100 + (i % CS1.px) * 0.04);
  const result = sourceFaithfulTerrain(raw, sq, empty);
  const expected = fitHeights(result.ground, result.ground);
  assert.deepEqual(result.fit.game, expected.game);
  assert.equal(result.fit.seaLevel, null);
});

test("low-relief carving is bounded and a lake polygon cannot erase a summit", () => {
  const raw = new Float32Array(CS1.px ** 2).fill(10);
  for (let row = 480; row < 600; row++) for (let col = 480; col < 600; col++) raw[row * CS1.px + col] = 100;
  const water = { ...empty, lakes: [polygon(-4000, -4000, 4000, 4000)] };
  const before = structuredClone(water);
  const result = sourceFaithfulTerrain(raw, sq, water);
  assert.equal(result.policy.carving_depth_source_m, 3);
  for (let i = 0; i < raw.length; i++) assert.ok(result.ground[i] - result.carved.heights[i] <= 3.00001);
  assert.ok(result.carved.heights[540 * CS1.px + 540] > 90);
  assert.deepEqual(water, before);
});

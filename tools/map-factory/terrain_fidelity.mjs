// Experimental source-preserving earthworks. Not a water-safety qualification.
import { CS1, smooth, carveWater } from "../../terrain.js";
import { CAPTURE, oceanMask } from "../../inputs.js";

export const TERRAIN_POLICY = Object.freeze({
  version: "source-faithful-v2",
  nominal_shallow_depth_game_m: 3,
  ocean_minimum_depth_game_m: 0.25,
  robust_relief_fraction: 0.1,
  shore_ramp_game_m: 64,
  transition_game_m: 0.25,
});

function smoothMaximum(a, b, width) {
  return Math.max(a, b) + width * Math.log1p(Math.exp(-Math.abs(a - b) / width));
}

/** Truncated four-neighbour distance to actual land, never to the map edge. */
export function shoreDistances(sea, n, steps) {
  const distance = new Uint16Array(sea.length).fill(steps);
  const queue = new Uint32Array(sea.length);
  let head = 0, tail = 0;
  for (let row = 0; row < n; row++) for (let col = 0; col < n; col++) {
    const i = row * n + col;
    if (sea[i] && ((col && !sea[i - 1]) || (col + 1 < n && !sea[i + 1]) ||
        (row && !sea[i - n]) || (row + 1 < n && !sea[i + n]))) {
      distance[i] = 1;
      queue[tail++] = i;
    }
  }
  while (head < tail) {
    const i = queue[head++], row = Math.floor(i / n), col = i % n;
    const next = distance[i] + 1;
    if (next >= steps) continue;
    for (const j of [col ? i - 1 : -1, col + 1 < n ? i + 1 : -1,
      row ? i - n : -1, row + 1 < n ? i + n : -1]) {
      if (j >= 0 && sea[j] && next < distance[j]) {
        distance[j] = next;
        queue[tail++] = j;
      }
    }
  }
  return distance;
}

export function sourceFaithfulTerrain(raw, sq, water) {
  const ground = smooth(raw, CAPTURE.smoothing), sea = oceanMask(water.oceans ?? [], sq);
  const sorted = Float32Array.from(ground).sort();
  const realMin = sorted[0], realMax = sorted.at(-1);
  const robustRelief = sorted[Math.floor((sorted.length - 1) * 0.95)] - sorted[Math.floor((sorted.length - 1) * 0.05)];
  const base = sea ? Math.min(-40, realMin) : realMin;
  const verticalScale = Math.min(1, 950 / Math.max(realMax - base, 1));
  const depth = Math.min(CAPTURE.riverDepth, Math.max(
    TERRAIN_POLICY.nominal_shallow_depth_game_m / verticalScale,
    TERRAIN_POLICY.robust_relief_fraction * robustRelief,
  ));
  const carved = carveWater(ground, sq,
    { ...water, rivers: water.rivers.filter(r => r.brunnel !== "tunnel") },
    { depth, halfWidth: CAPTURE.riverHalfWidth, lakeDepth: Math.min(CAPTURE.lakeDepth, depth) });
  // Lake flattening must not silently remove a mountain inside a water polygon.
  for (let i = 0; i < ground.length; i++) carved.heights[i] = Math.max(carved.heights[i], ground[i] - depth);
  const distance = sea && shoreDistances(sea, CS1.px, Math.ceil(TERRAIN_POLICY.shore_ramp_game_m / 16));
  const game = new Float32Array(ground.length), banks = new Float32Array(ground.length);
  let gameMin = Infinity, gameMax = -Infinity, oceanLowered = 0;
  let maxCoastalLowering = 0, overBudget = 0, clipped = 0;
  const width = TERRAIN_POLICY.transition_game_m / verticalScale;
  const oceanDepth = TERRAIN_POLICY.ocean_minimum_depth_game_m / verticalScale;
  const steps = Math.ceil(TERRAIN_POLICY.shore_ramp_game_m / 16);
  for (let i = 0; i < ground.length; i++) {
    let height = carved.heights[i];
    if (sea?.[i]) {
      const t = distance[i] / steps, ramp = t * t * (3 - 2 * t);
      const target = -(0.125 / verticalScale + (oceanDepth - 0.125 / verticalScale) * ramp);
      height = -smoothMaximum(-height, -target, width);
      const lowering = carved.heights[i] - height;
      if (lowering > 1 / 128) oceanLowered++;
      maxCoastalLowering = Math.max(maxCoastalLowering, lowering);
      if (ground[i] - height > depth + 1 / 128) overBudget++;
    }
    game[i] = (height - base) * verticalScale + 50;
    banks[i] = (ground[i] - base) * verticalScale + 50;
    gameMin = Math.min(gameMin, game[i]); gameMax = Math.max(gameMax, game[i]);
    if (game[i] < 0 || game[i] > CS1.maxHeight) clipped++;
  }
  const policy = { ...TERRAIN_POLICY, native_verified: false,
    robust_relief_source_m: robustRelief, carving_depth_source_m: depth,
    carving_depth_game_m: depth * verticalScale, ocean_lowered_vertices: oceanLowered,
    dry_land_raised_vertices: 0, maximum_coastal_lowering_source_m: maxCoastalLowering,
    maximum_coastal_raising_source_m: 0,
    coast_exceeding_carving_budget_vertices: overBudget,
    bathymetry: "existing below-sea terrain retained; engineered shallow minimum where needed, not measured bathymetry",
    low_land: "source depressions retained; no invented dry-land shelf or flood-safety claim" };
  const fit = { game, sea, base, verticalScale, autoScale: verticalScale, realMin, realMax,
    relief: realMax - realMin, gameMin, gameMax, headroom: CS1.maxHeight - gameMax,
    clipped: clipped / game.length,
    seaLevel: sea ? -base * verticalScale + 50 : null };
  return { ground, carved, fit, banks, policy };
}

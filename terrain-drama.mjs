// Per-square vertical shaping: terrain that plays well by region (PL-1329).
//
// One global height scale is the wrong tool. Flat squares (Boston, Charleston) sit below the
// shipped maps' relief and central height range, so their drumlins and harbour hills never
// read; very steep squares (Innsbruck, the Grand Canyon) have to be squeezed whole, which
// flattens the cliffs that make them worth exporting. This module splits the vertical scale
// into two gains on each square's own ground:
//
//   regional trend  (a blur at DRAMA.trend_metres)  -> the square's overall shape
//   local relief    (what is left)                  -> ridgelines, bluffs, valleys, islands
//
// The gains are fitted, per square, to the 104 shipped maps' terrain band (PL-1151/PL-1228's
// survey): mean 16 m gradient, and the central 25 tiles' 10-90 height range. A square already
// inside the band is left alone; one outside is brought to the nearest band edge. The map
// always still has to fit under the game's 1,024 m ceiling.
//
// This is opt-in (`--terrain drama`, `terrain=drama` in a link). The shipping writer's terrain
// stays `terrain.js`'s `fitHeights`, whose bytes are bound to the frozen native water contract;
// promoting this policy to the default is a separate decision that needs its own native
// evaluation. Figures and before/after evidence: tools/map-factory/TERRAIN_DRAMA.md.

import { CS1, waterSources } from "./terrain.js";

/**
 * What a square's terrain is asked to look like, from the 104 shipped maps' own measurements
 * (frozen in tools/map-factory/survey/terrain-interest.json and capabilities.json).
 * The p25-p75 band is what stock maps look like; the fit clamps to the nearest edge, never
 * targets past it. Bands, not gates.
 */
export const STOCK_TERRAIN_BAND = Object.freeze({
  roughness_percent: Object.freeze({ p25: 11.2625, median: 15.5, p75: 21.185 }),
  central_terrain_diversity_m: Object.freeze({ p25: 114.625, median: 182.2, p75: 300.65 }),
  relief_m: Object.freeze({ p25: 595.875, median: 761.6, p75: 989.925 }),
  buildable_percent: Object.freeze({ p25: 57 }),
  source: "104 shipped CS1 maps, 1081-square 16 m south-first grids at the 1/64 m terrain unit",
});

/** The per-square transform's own constants. */
export const DRAMA = Object.freeze({
  version: "per-square-gain-v1",
  trend_metres: 1200,      // blur scale that separates regional trend from local relief
  low_gain: [0.1, 12],     // regional trend gain
  high_gain: [0.25, 12],   // local relief gain (also the game-metre scale of a carve)
  solve_points: 4,         // subsample step for the gain search; the result is measured whole
});

const CENTRAL_NODE = (() => {
  const RES = 512, CELL = 33.75, HN = CS1.px, node = [];
  for (let i = 0; i < RES; i++) {
    const tile = Math.min(8, Math.floor((i * 9) / RES));
    if (tile < 2 || tile > 6) continue;
    node.push(Math.min(HN - 1, Math.max(0, Math.floor(((i - 256 + 0.5) * CELL + 8640) / 16 + 0.5))));
  }
  return node;
})();

/** Separable box blur, three passes, running sums: a Gaussian of `sigma` pixels at O(pixels). */
export function blurTrend(h, sigma) {
  const N = CS1.px;
  if (!(sigma > 0.5)) return Float32Array.from(h);
  const r = Math.max(1, Math.round((Math.sqrt(4 * sigma * sigma + 1) - 1) / 2));
  let src = Float32Array.from(h), dst = new Float32Array(N * N);
  const pass = (vertical) => {
    const stride = vertical ? N : 1;
    for (let line = 0; line < N; line++) {
      const base = vertical ? line : line * N;
      const at = (k) => src[base + Math.min(N - 1, Math.max(0, k)) * stride];
      let sum = 0;
      for (let k = -r; k <= r; k++) sum += at(k);
      for (let k = 0; k < N; k++) {
        dst[base + k * stride] = sum / (2 * r + 1);
        sum += at(k + r + 1) - at(k - r);
      }
    }
    [src, dst] = [dst, src];
  };
  for (let p = 0; p < 3; p++) { pass(true); pass(false); }
  return src;
}

/** Mean 16 m gradient (percent) and central 10-90 height range (metres) of a game-metre grid. */
export function terrainShape(game, step = 1) {
  const N = CS1.px, q = (v) => Math.floor(v * 64 + 0.5) / 64;
  let gradSum = 0, gradN = 0;
  for (let r = 0; r < N; r += step) for (let c = 0; c < N; c += step) {
    const i = r * N + c;
    const z = r > 0 && r < N - 1 ? (q(game[i + N]) - q(game[i - N])) / 32 : 0;
    const x = c > 0 && c < N - 1 ? (q(game[i + 1]) - q(game[i - 1])) / 32 : 0;
    gradSum += Math.hypot(x, z) * 100; gradN++;
  }
  const node = step === 1 ? CENTRAL_NODE : CENTRAL_NODE.filter((_, k) => k % step === 0);
  const central = [];
  for (const r of node) for (const c of node) central.push(q(game[r * N + c]));
  central.sort((a, b) => a - b);
  const pct = (p) => { const x = (central.length - 1) * p, lo = Math.floor(x), hi = Math.ceil(x); return central[lo] + (central[hi] - central[lo]) * (x - lo); };
  return { roughness_percent: gradSum / Math.max(gradN, 1), central_terrain_diversity_m: pct(0.9) - pct(0.1) };
}

/**
 * Fit the two gains for a square. Local relief is solved first (it sets slope, and so what can
 * be built); the regional trend is then solved until the central 25 tiles' range sits in the
 * band. Each solve is a bisection: roughness rises with local gain at fixed regional gain, and
 * central range rises with regional gain at fixed local gain. Both gains stay positive, so the
 * ground keeps its order and a river still runs downhill along the path it does today.
 */
export function fitDrama(raw, { sea = null, floor = 50, ceiling = 1000, seaDepth = 40, spacing = 16 } = {}) {
  const N = CS1.px, sigma = Math.max(1, DRAMA.trend_metres / spacing);
  const L = blurTrend(raw, sigma);
  let lo = Infinity, lowIndex = 0;
  for (let i = 0; i < raw.length; i++) if (raw[i] < lo) { lo = raw[i]; lowIndex = i; }
  const hasSea = !!sea;
  // Anchor at the lowest ground (or at sea level on a coast) so the floor stays the floor.
  const La = hasSea ? 0 : L[lowIndex], Da = hasSea ? 0 : raw[lowIndex] - L[lowIndex];
  const seaGame = floor + seaDepth, baseGame = hasSea ? seaGame : floor;
  const step = DRAMA.solve_points, rows = [], cols = [];
  for (let r = 0; r < N; r += step) rows.push(r);
  for (let c = 0; c < N; c += step) cols.push(c);
  const center = CENTRAL_NODE.filter((_, k) => k % step === 0);
  const q = (v) => Math.floor(v * 64 + 0.5) / 64;
  // Measure the map the square will actually be: open sea keeps its 10..seaDepth m depth and
  // land keeps 1 m of freeboard, so a shallow or deep seabed cannot drag the fit around.
  const shaped = (i, a, b) => {
    const g = baseGame + a * (L[i] - La) + b * (raw[i] - L[i] - Da);
    if (!hasSea) return g;
    if (sea[i]) return Math.min(seaGame - 10, Math.max(seaGame - seaDepth, g));
    return Math.max(g, seaGame + 1);
  };
  const value = (i, a, b) => q(shaped(i, a, b));
  const shape = (a, b) => {
    let sum = 0, count = 0;
    for (const r of rows) for (const c of cols) {
      const i = r * N + c;
      const z = r > 0 && r < N - 1 ? (value(i + N, a, b) - value(i - N, a, b)) / 32 : 0;
      const x = c > 0 && c < N - 1 ? (value(i + 1, a, b) - value(i - 1, a, b)) / 32 : 0;
      sum += Math.hypot(x, z) * 100; count++;
    }
    const central = [];
    for (const r of center) for (const c of center) central.push(value(r * N + c, a, b));
    central.sort((p, q2) => p - q2);
    const pct = (p) => { const x2 = (central.length - 1) * p, l = Math.floor(x2), h = Math.ceil(x2); return central[l] + (central[h] - central[l]) * (x2 - l); };
    return { roughness_percent: sum / count, central_terrain_diversity_m: pct(0.9) - pct(0.1) };
  };
  // The map still has to fit under the ceiling, so every candidate pair is first squeezed to
  // fit; the search runs on those effective gains, which is what the map will actually get.
  const topAt = (a, b) => {
    let top = -Infinity;
    for (const r of rows) for (const c of cols) {
      const i = r * N + c;
      const g = shaped(i, a, b);
      if (g > top) top = g;
    }
    return top;
  };
  const effective = (a, b) => {
    const room = (ceiling - baseGame) / Math.max(topAt(a, b) - baseGame, 1);
    return room < 1 ? [a * room, b * room] : [a, b];
  };
  // Aim a little inside the band edge: the search measures a subsample, and the finished map
  // must not land a fraction of a metre outside the band it was fitted to.
  const inset = (m) => { const pad = 0.02 * (m.p75 - m.p25); return [m.p25 + pad, m.p75 - pad]; };
  const band = (v, m) => { const [lo, hi] = inset(m); return Math.min(hi, Math.max(lo, v)); };
  const evaluate = (a, b) => { const [ea, eb] = effective(a, b); return shape(ea, eb); };
  const start = evaluate(1, 1);
  const target = {
    roughness_percent: band(start.roughness_percent, STOCK_TERRAIN_BAND.roughness_percent),
    central_terrain_diversity_m: band(start.central_terrain_diversity_m, STOCK_TERRAIN_BAND.central_terrain_diversity_m),
  };
  const solve = (fix, aim, from, values) => {
    const [g0, g1] = values;
    if (aim(g0, fix) >= from) return g0;
    if (aim(g1, fix) <= from) return g1;
    let out = g0, in_ = g1;
    for (let k = 0; k < 26; k++) {
      const mid = (out + in_) / 2;
      if (aim(mid, fix) < from) out = mid; else in_ = mid;
    }
    return (out + in_) / 2;
  };
  let a = 1, b = 1;
  for (let iter = 0; iter < 4; iter++) {
    b = solve(a, (x, fixed) => evaluate(fixed, x).roughness_percent, target.roughness_percent, DRAMA.high_gain);
    a = solve(b, (x, fixed) => evaluate(x, fixed).central_terrain_diversity_m, target.central_terrain_diversity_m, DRAMA.low_gain);
  }
  const capped = a >= DRAMA.low_gain[1] || b >= DRAMA.high_gain[1];
  const pair = effective(a, b);
  const limitedBy = capped ? "gain_cap" : pair[0] < a - 1e-9 || pair[1] < b - 1e-9 ? "headroom" : null;
  [a, b] = pair;
  // The search's subsample can miss the true peak by a few metres: check every node and squeeze
  // once more if the finished map would break the ceiling.
  let peak = -Infinity;
  for (let i = 0; i < raw.length; i++) { const g = shaped(i, a, b); if (g > peak) peak = g; }
  if (peak > ceiling) { const k = 0.9995 * (ceiling - baseGame) / Math.max(peak - baseGame, 1); a *= k; b *= k; }
  const result = shape(a, b);
  return {
    version: DRAMA.version, low: +a.toFixed(6), high: +b.toFixed(6),
    trend_metres: DRAMA.trend_metres, sigma_px: +sigma.toFixed(3),
    La, Da, baseGame, seaGame, floor, ceiling, seaDepth, limitedBy, L,
    target: {
      roughness_percent: +target.roughness_percent.toFixed(2),
      central_terrain_diversity_m: +target.central_terrain_diversity_m.toFixed(1),
    },
    achieved: {
      roughness_percent: +result.roughness_percent.toFixed(2),
      central_terrain_diversity_m: +result.central_terrain_diversity_m.toFixed(1),
    },
  };
}

/**
 * The game heights this transform gives `carved` (real metres): the same shape `fitHeights`
 * returns, so everything downstream reads it the same way. Sea keeps its fixed 10..40 m depth;
 * land keeps 1 m of freeboard; carved water may dip below the sea.
 */
export function dramaFit(raw, carved, spec, { sea = null, floor = 50, ceiling = 1000, seaDepth = 40 } = {}) {
  const N = carved.length, game = new Float32Array(N);
  const hasSea = !!sea;
  let rmin = Infinity, rmax = -Infinity;
  for (const v of raw) { if (v < rmin) rmin = v; if (v > rmax) rmax = v; }
  let gmin = Infinity, gmax = -Infinity, clipped = 0;
  for (let i = 0; i < N; i++) {
    let g = spec.baseGame + spec.low * (spec.L[i] - spec.La) + spec.high * (carved[i] - spec.L[i] - spec.Da);
    if (hasSea) {
      if (sea[i]) g = Math.min(spec.seaGame - 10, Math.max(spec.seaGame - seaDepth, g));
      else if (carved[i] < raw[i]) g = Math.max(g, spec.seaGame - seaDepth);
      else g = Math.max(g, spec.seaGame + 1);
    } else g = Math.max(g, floor);
    game[i] = g;
    if (g < gmin) gmin = g; if (g > gmax) gmax = g;
    if (g > CS1.maxHeight || g < 0) clipped++;
  }
  return {
    game, sea, realMin: rmin, realMax: rmax, relief: rmax - rmin,
    verticalScale: spec.high, autoScale: spec.high, base: hasSea ? -seaDepth : rmin,
    gameMin: gmin, gameMax: gmax, headroom: CS1.maxHeight - gmax, clipped: clipped / N,
    seaLevel: hasSea ? spec.seaGame : null,
    trend: spec.L, trendLow: spec.low, trendAnchor: spec.La, detailAnchor: spec.Da, baseGame: spec.baseGame,
    drama: {
      version: spec.version, low: spec.low, high: spec.high, trend_metres: spec.trend_metres,
      trend_sigma_px: spec.sigma_px, trend_anchor_metres: spec.La, detail_anchor_metres: spec.Da,
      base_game_m: spec.baseGame, sea_level_game_m: hasSea ? spec.seaGame : null,
      target: spec.target, achieved: spec.achieved, limited_by: spec.limitedBy,
    },
  };
}

/** A real height at node `i` in this fit's game metres (the same transform dramaFit applied). */
export function gameHeightAt(fit, i, real) {
  return fit.baseGame + fit.trendLow * (fit.trend[i] - fit.trendAnchor) +
    fit.verticalScale * (real - fit.trend[i] - fit.detailAnchor);
}

/** Water sources, with each lake's surface placed by the transform rather than by a linear scale. */
export function dramaSources(sq, water, carved, fit) {
  const sources = waterSources(sq, water, carved, fit);
  const N = CS1.px, lakes = carved.lakeInfo ?? [];
  for (const s of sources) {
    if (s.kind !== "lake") continue;
    let best = null, bestDistance = Infinity;
    for (const L of lakes) {
      const col = L.i % N, row = Math.floor(L.i / N);
      const distance = Math.hypot(col - s.col, row - s.row);
      if (distance < bestDistance) { bestDistance = distance; best = L; }
    }
    if (best) s.surface_game_m = Math.round(gameHeightAt(fit, best.i, best.shore_real_m) * 10) / 10;
  }
  return sources;
}

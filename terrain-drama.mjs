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

import { CS1, DEFAULTS, smooth, carveWater, fitHeights, waterSources, mapDetails, extentOf, encode16, png16 } from "./terrain.js";
import { captureInputs, CAPTURE } from "./inputs.js";

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
  buildable_margin: 1,     // the panel score is floored, and the carve only ever lowers it
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
 * The game's own New Game flatness score over the "central 25" tiles, 0..1 (map_metadata.py).
 * The native score composes two +2 tile offsets, so its window is not vertically symmetric:
 * it is taken in the game's own south-first row order, which `game` is mirrored into first.
 */
export function panelFlatness(game) {
  const N = CS1.px, h = new Int32Array(N * N);
  for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) h[(N - 1 - r) * N + c] = Math.floor(game[r * N + c] * 64 + 0.5);
  const patches = new Float64Array(81), quads = 120 * 120;
  for (let r = 0; r < N - 1; r++) {
    const band = Math.floor(r / 120) * 9;
    for (let c = 0; c < N - 1; c++) {
      const a = h[r * N + c], b = h[r * N + c + 1], d = h[(r + 1) * N + c], e = h[(r + 1) * N + c + 1];
      const span = Math.min(Math.max(a, b, d, e) - Math.min(a, b, d, e), 32768);
      patches[band + Math.floor(c / 120)] += Math.floor((512 * 4096) / (512 + Math.floor((span * span) / 512)));
    }
  }
  let sum = 0;
  for (let pr = 4; pr < 9; pr++) for (let pc = 4; pc < 9; pc++) sum += patches[pr * 9 + pc] / quads / 4096;
  return sum / 25;
}

/** The water mask the carve will leave, independent of the vertical gains. */
export function wetMaskFor(sq, water) {
  if (!water?.rivers?.length && !water?.lakes?.length && !water?.riverAreas?.length) return null;
  const empty = new Float32Array(CS1.px ** 2);
  return carveWater(empty, sq, water, { depth: 10, halfWidth: 40, lakeDepth: 4 }).wet;
}

/** Dry share of the central 25 tiles, the panel score's second term (1 - water/capacity). */
export function centralDryFraction(wet, sea) {
  if (!wet && !sea) return 1;
  const N = CS1.px;
  let wetCells = 0, cells = 0;
  for (let r = 240; r <= 840; r++) for (let c = 240; c <= 840; c++) {
    const i = r * N + c;
    cells++;
    if (wet?.[i] || sea?.[i]) wetCells++;
  }
  return 1 - wetCells / cells;
}

/** The New Game buildable score this terrain would give, as the writer's panel reports it. */
export function estimatedBuildable(game, dry) {
  return Math.max(0, Math.min(100, Math.floor(panelFlatness(game) * dry * 100)));
}

/**
 * Fit the two gains for a square. Local relief is solved first (it sets slope, and so what can
 * be built); the regional trend is then solved until the central 25 tiles' range sits in the
 * band. Each solve is a bisection: roughness rises with local gain at fixed regional gain, and
 * central range rises with regional gain at fixed local gain. Both gains stay positive, so the
 * ground keeps its order and a river still runs downhill along the path it does today.
 */
export function fitDrama(raw, { sea = null, floor = 50, ceiling = 1000, seaDepth = 40, spacing = 16, wet = null } = {}) {
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
  const build = (a, b) => {
    const out = new Float32Array(N * N);
    for (let i = 0; i < out.length; i++) out[i] = shaped(i, a, b);
    return out;
  };
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
  let limitedBy = capped ? "gain_cap" : pair[0] < a - 1e-9 || pair[1] < b - 1e-9 ? "headroom" : null;
  [a, b] = pair;
  // The search's subsample can miss the true peak by a few metres: check every node and squeeze
  // once more if the finished map would break the ceiling.
  let peak = -Infinity;
  for (let i = 0; i < raw.length; i++) { const g = shaped(i, a, b); if (g > peak) peak = g; }
  if (peak > ceiling) { const k = 0.9995 * (ceiling - baseGame) / Math.max(peak - baseGame, 1); a *= k; b *= k; }
  // Buildable floor: the game's own New Game flatness over the terrain it will contain, times
  // the dry share of the central 25 tiles, may not fall below the shipped maps' p25. Gain
  // compression raises flatness, so this caps both gains together. Bisect one common scale
  // factor: the score rises monotonically as the gains shrink toward zero.
  const dry = centralDryFraction(wet, sea);
  const need = STOCK_TERRAIN_BAND.buildable_percent.p25 + DRAMA.buildable_margin;
  const scoreAt = (k) => Math.floor(panelFlatness(build(a * k, b * k)) * dry * 100);
  let flatness = panelFlatness(build(a, b)), buildable = Math.floor(flatness * dry * 100);
  let buildableApplied = false;
  // A square with so little dry ground that even flat terrain cannot reach the floor is left
  // alone: flattening the whole map to gain zero would not make it more buildable in practice.
  const reachable = dry * 100 >= need + 0.5;
  if (reachable && buildable < need) {
    let lo = 0, hi = 1;
    for (let i = 0; i < 18; i++) {
      const mid = (lo + hi) / 2;
      if (scoreAt(mid) >= need) lo = mid; else hi = mid;
    }
    a *= lo; b *= lo;
    flatness = panelFlatness(build(a, b)); buildable = Math.floor(flatness * dry * 100);
    buildableApplied = true;
  }
  if (buildableApplied) limitedBy = "buildable_floor";
  const result = shape(a, b);
  const buildableReport = {
    floor_percent: STOCK_TERRAIN_BAND.buildable_percent.p25, margin: DRAMA.buildable_margin,
    dry_fraction: +dry.toFixed(4), flatness: +flatness.toFixed(4), estimated_percent: buildable,
    applied: buildableApplied, reachable,
  };
  return {
    version: DRAMA.version, low: +a.toFixed(6), high: +b.toFixed(6),
    trend_metres: DRAMA.trend_metres, sigma_px: +sigma.toFixed(3),
    La, Da, baseGame, seaGame, floor, ceiling, seaDepth, limitedBy, buildable: buildableReport, L,
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
      buildable: spec.buildable,
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

/** The ready-to-play writer's inputs for a square, with the shaped terrain. */
/**
 * The upper quartile of the real ground over dry cells, for the New Game theme rule. Under the
 * transform the recorded fit can no longer invert game height to real elevation, so the real
 * value the rule needs is measured here and recorded in the geometry.
 */
export function dryRealPercentile(ground, sea, wet, p = 0.75) {
  const values = [];
  for (let i = 0; i < ground.length; i++) {
    if (sea?.[i] || wet?.[i]) continue;
    values.push(ground[i]);
  }
  if (values.length < 4096) return null;
  values.sort((a, b) => a - b);
  const x = (values.length - 1) * p, lo = Math.floor(x), hi = Math.ceil(x);
  return values[lo] + (values[hi] - values[lo]) * (x - lo);
}

export async function captureDramaInputs(sq, options = {}) {
  const legacy = await captureInputs(sq, options);
  const { base, verticalScale } = legacy.geometry.fit;
  const N = CS1.px, real = (g) => (g - 50) / verticalScale + base;
  const ground = new Float32Array(N * N), sea = new Uint8Array(N * N);
  let hasSea = false;
  for (let i = 0; i < N * N; i++) {
    ground[i] = real(legacy.banks[i]);
    // The shipping fit keeps open sea 10..40 m below sea level and land at least 1 m above it.
    if (legacy.geometry.seaLevel !== null && ground[i] < -5) { sea[i] = 1; hasSea = true; }
  }
  const water = { ...legacy.geometry, rivers: legacy.geometry.rivers.filter((r) => r.brunnel !== "tunnel") };
  const spacing = extentOf(sq) / (N - 1);
  const wet = wetMaskFor(sq, water);
  const spec = fitDrama(ground, { sea: hasSea ? sea : null, spacing, wet });
  // Re-cut the water in real metres for a game-metre depth: the carve is drawn on the shaped map.
  const carved = carveWater(ground, sq, water, {
    depth: CAPTURE.riverDepth / spec.high, halfWidth: CAPTURE.riverHalfWidth, lakeDepth: CAPTURE.lakeDepth / spec.high,
  });
  const fit = dramaFit(ground, carved.heights, spec, { sea: hasSea ? sea : null });
  const banksFit = dramaFit(ground, ground, spec, { sea: hasSea ? sea : null });
  const sources = dramaSources(sq, legacy.geometry, carved, fit);
  const png = new Uint8Array(await (await png16(encode16(fit.game), N, N)).arrayBuffer());
  return {
    png, banks: banksFit.game, game: fit.game, seaLevel: fit.seaLevel, spec, fit, carved,
    geometry: {
      ...legacy.geometry,
      seaLevel: fit.seaLevel,
      sources,
      fit: {
        base: fit.base, verticalScale: fit.verticalScale, drama: fit.drama,
        // The affine fit lets the resource stage invert game height to real elevation; under the
        // transform that inversion no longer holds, so the real upper quartile is recorded here.
        real_p75_m: dryRealPercentile(ground, hasSea ? sea : null, carved.wet, 0.75),
      },
    },
  };
}

/**
 * Build a square with the per-square transform, for the page and the CLI's heightmap path.
 * Same contract as `buildMap`, plus the fitted spec.
 */
export function buildDramaMap({ sq, elev, w }, opts = {}) {
  const o = { ...DEFAULTS, ...opts };
  const ground = smooth(elev.heights, o.sm);
  const spacing = extentOf(sq) / (CS1.px - 1);
  const wet = w ? wetMaskFor(sq, w) : null;
  const spec = fitDrama(ground, { sea: elev.sea, spacing, wet });
  const carved = w
    ? carveWater(ground, sq, w, { depth: o.rd / spec.high, halfWidth: o.rw, lakeDepth: o.ld / spec.high })
    : { heights: ground, wet: null, riverLine: null, riversCut: false, lakes: 0, lakeInfo: [] };
  const fit = dramaFit(ground, carved.heights, spec, { sea: elev.sea });
  const sources = w ? dramaSources(sq, w, carved, fit) : [];
  const note = w ? `${new Set(w.rivers.map((r) => r.name || "?")).size} rivers (${w.rivers.length} pieces` +
    `${w.riverAreas?.length ? `, ${w.riverAreas.length} wide-river outlines` : ""}), ${carved.lakes} lakes · OSM via OpenFreeMap tiles, zoom ${w.zoom}` : null;
  return { carved, fit, sources, note, spec };
}

/** The sidecar JSON's heights section, with the transform and the buildable floor's result. */
export function dramaDetails({ sq, elev, w, map, opts = {}, file, link, note }) {
  const { fit } = map, r1 = (v) => Math.round(v * 10) / 10;
  const details = mapDetails({ sq, elev, w, map, opts, file, link, note });
  const shape = terrainShape(fit.game);
  const bandOf = (value, metric) => value < metric.p25 ? "below_p25" : value > metric.p75 ? "above_p75" : "inside_p25_p75";
  details.heights = {
    real_min_m: r1(fit.realMin), real_max_m: r1(fit.realMax),
    vertical_scale: +fit.verticalScale.toFixed(4),
    game_m: "base_game_m + regional_gain * (regional trend - its anchor) + local_gain * (local relief - its anchor)",
    base_m: r1(fit.base), game_min_m: r1(fit.gameMin), game_max_m: r1(fit.gameMax),
    sea_level_game_m: fit.seaLevel === null ? null : r1(fit.seaLevel),
    vertical_transform: { ...fit.drama, regional_gain: fit.drama.low, local_gain: fit.drama.high },
  };
  details.water = { ...details.water, river_depth_m: +Number(opts.rd ?? 10).toFixed(1), lake_depth_m: +Number(opts.ld ?? 4).toFixed(1), depth_frame: "game metres (the carve follows the shaped ground)" };
  details.terrain_shape = {
    measured_on: "this map's final 1081-square, 16 m, 1/64 m game-height grid",
    roughness_percent: +shape.roughness_percent.toFixed(2),
    central_terrain_diversity_m: +shape.central_terrain_diversity_m.toFixed(1),
    relief_m: r1(fit.gameMax - fit.gameMin),
    buildable: fit.drama.buildable,
    stock_band: STOCK_TERRAIN_BAND,
    bands: {
      roughness: bandOf(shape.roughness_percent, STOCK_TERRAIN_BAND.roughness_percent),
      central_height_range: bandOf(shape.central_terrain_diversity_m, STOCK_TERRAIN_BAND.central_terrain_diversity_m),
      relief: bandOf(fit.gameMax - fit.gameMin, STOCK_TERRAIN_BAND.relief_m),
    },
  };
  details.terrain = "drama-v1: per-square two-gain vertical transform fitted to the stock terrain band";
  return details;
}

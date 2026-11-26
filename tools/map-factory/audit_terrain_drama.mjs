// Evidence for the per-square vertical transform (PL-1329): the shipping fit and the drama fit
// side by side on the five shipping fixtures, Boston, and one very flat and one very steep
// square chosen by rule, each placed against the 104 shipped maps' terrain band.
//
//   cd tools/map-factory && node audit_terrain_drama.mjs --out DIR
//
// Reads the same sources the exporter does (AWS Terrain Tiles, OpenFreeMap water) and the
// fixtures' frozen water geometry; writes evidence.json plus before/after hillshades. No game,
// no writer and no acceptance claim. The stock quartiles are copied from the frozen
// survey artifact and re-stated, not recomputed.

import { mkdir, writeFile } from "node:fs/promises";
import { gunzipSync } from "node:zlib";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  CS1, DEFAULTS, PRESETS, sampleElevation, fetchBasemapWater, smooth, carveWater, fitHeights,
  extentOf, pngRGB, encode16,
} from "../../terrain.js";
import { fitDrama, dramaFit, terrainShape, wetMaskFor, STOCK_TERRAIN_BAND } from "../../terrain-drama.mjs";
import { captureInputs, oceanMask } from "../../inputs.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const N = CS1.px, SPACING = 16;

/** The five shipping fixtures, plus places the issue names, plus candidates the rule chooses from. */
const SQUARES = [
  ...["asheville", "charleston", "innsbruck", "pittsburgh", "rio"].map((slug) => ({ slug, kind: "fixture" })),
  { slug: "boston", kind: "boston", name: "Boston", lat: 42.355, lon: -71.06 },
];
// Declared before measuring anything: the rule takes the lowest and highest source relief.
const CANDIDATES = [
  { slug: "new-orleans", name: "New Orleans", lat: 29.95, lon: -90.07 },
  { slug: "amsterdam", name: "Amsterdam", lat: 52.37, lon: 4.9 },
  { slug: "chicago", name: "Chicago", lat: 41.88, lon: -87.63 },
  { slug: "yosemite", name: "Yosemite Valley", lat: 37.735, lon: -119.575 },
  { slug: "hong-kong", name: "Hong Kong", lat: 22.29, lon: 114.17 },
  { slug: "grand-canyon", name: "Grand Canyon", lat: 36.08, lon: -112.11 },
];

const q = (v) => Math.floor(v * 64 + 0.5) / 64;

/** The game's own stair-step check (cs1_harness.report.terracing), on the 1/64 m grid. */
export function terracing(game) {
  const h = Int32Array.from(game, (v) => Math.round(q(v) * 64));
  const span = (r, c) => {
    let lo = Infinity, hi = -Infinity;
    for (let y = Math.max(0, r - 2); y <= Math.min(N - 1, r + 2); y++)
      for (let x = Math.max(0, c - 2); x <= Math.min(N - 1, c + 2); x++) {
        const v = h[y * N + x]; if (v < lo) lo = v; if (v > hi) hi = v;
      }
    return hi - lo;
  };
  const sloped = new Uint8Array(N * N);
  for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) sloped[r * N + c] = span(r, c) > 4 * 64 ? 1 : 0;
  let equal = 0, total = 0;
  for (let r = 0; r < N; r++) for (let c = 0; c + 1 < N; c++) {
    const i = r * N + c;
    if (sloped[i] && sloped[i + 1]) { total++; if (h[i] === h[i + 1]) equal++; }
  }
  return total ? equal / total : 0;
}

/** How much the vertical transform reorders the ground: reversed east-west pairs, and rank agreement. */
export function orderMetrics(realGame, shapedGame, step = 8) {
  let pairs = 0, reversed = 0, reversedOverMetre = 0, maxReversal = 0;
  for (let r = 0; r < N; r += step) for (let c = 0; c + 1 < N; c += step) {
    const i = r * N + c;
    const a = realGame[i] - realGame[i + 1], b = shapedGame[i] - shapedGame[i + 1];
    if (Math.abs(a) < 1 / 64 && Math.abs(b) < 1 / 64) continue;
    pairs++;
    if (a * b < 0) {
      reversed++;
      const magnitude = Math.min(Math.abs(a), Math.abs(b));
      if (magnitude > 1) reversedOverMetre++;
      if (magnitude > maxReversal) maxReversal = magnitude;
    }
  }
  const xs = [], ys = [];
  for (let r = 4; r < N; r += 137) for (let c = 4; c < N; c += 137) { xs.push(realGame[r * N + c]); ys.push(shapedGame[r * N + c]); }
  const rank = (v) => { const order = v.map((x, i) => [x, i]).sort((p, q2) => p[0] - q2[0]); const out = new Array(v.length); order.forEach(([, i], k) => { out[i] = k; }); return out; };
  const rx = rank(xs), ry = rank(ys), n = xs.length;
  const mean = (v) => v.reduce((a, b) => a + b, 0) / v.length;
  const mx = mean(rx), my = mean(ry);
  let sxy = 0, sxx = 0, syy = 0;
  for (let i = 0; i < n; i++) { const dx = rx[i] - mx, dy = ry[i] - my; sxy += dx * dy; sxx += dx * dx; syy += dy * dy; }
  return {
    reversed_pair_fraction: +(pairs ? reversed / pairs : 0).toFixed(4),
    reversed_over_1m_fraction: +(pairs ? reversedOverMetre / pairs : 0).toFixed(4),
    max_reversal_m: +maxReversal.toFixed(2),
    rank_agreement: +(sxy / Math.sqrt(sxx * syy)).toFixed(4),
  };
}

function band(value, metric) {
  return value < metric.p25 ? "below_p25" : value > metric.p75 ? "above_p75" : "inside_p25_p75";
}

/** A north-up shaded view of a game-metre grid, same shading as the writer's preview. */
function hillshade(game) {
  const rgb = new Uint8Array(N * N * 3);
  let lo = Infinity, hi = -Infinity;
  for (const v of game) { if (v < lo) lo = v; if (v > hi) hi = v; }
  const span = Math.max(hi - lo, 1);
  for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
    const i = r * N + c;
    const dx = (game[r * N + Math.min(c + 1, N - 1)] - game[r * N + Math.max(c - 1, 0)]) / 32;
    const dz = (game[Math.min(r + 1, N - 1) * N + c] - game[Math.max(r - 1, 0) * N + c]) / 32;
    const shade = Math.max(0.28, Math.min(1.3, 0.92 + (-dx - dz) * 3.2));
    const t = (game[i] - lo) / span;
    rgb[i * 3] = Math.min(255, (110 + 130 * t) * shade);
    rgb[i * 3 + 1] = Math.min(255, (126 + 118 * t) * shade);
    rgb[i * 3 + 2] = Math.min(255, (96 + 120 * t) * shade);
  }
  return rgb;
}

async function writeHillshade(dir, name, game) {
  const bytes = new Uint8Array(await (await pngRGB(hillshade(game), N, N)).arrayBuffer());
  await writeFile(join(dir, `${name}.png`), bytes);
}

function loadFixture(slug) {
  const dir = join(HERE, "fixtures", slug);
  const geometry = JSON.parse(gunzipSync(readFileSync(join(dir, "geometry.json.gz"))).toString());
  return geometry;
}

async function measureSquare(spec, dir) {
  const geometry = spec.kind === "fixture" ? loadFixture(spec.slug) : null;
  const sq = geometry
    ? geometry.sq
    : { lon: spec.lon, lat: spec.lat, rotation: 0, scale: 1, name: spec.name, slug: spec.slug };
  // Only `captureInputs` carries the ocean polygons, so a non-fixture square is captured whole
  // and its uncarved game heights are taken back to real metres through the capture's own fit.
  const capture = geometry ? null : await captureInputs(sq, { about: { tool: "audit_terrain_drama.mjs" } });
  const w = geometry ?? capture.geometry;
  let ground, sea;
  if (geometry) {
    const elev = await sampleElevation(sq);
    ground = smooth(elev.heights, 1);
    sea = oceanMask(w.oceans ?? [], sq);
  } else {
    const { base, verticalScale } = capture.geometry.fit;
    ground = Float32Array.from(capture.banks, (g) => (g - 50) / verticalScale + base);
    sea = capture.geometry.seaLevel === null ? null : Uint8Array.from(ground, (v) => (v < -5 ? 1 : 0));
  }
  const legacyCarved = carveWater(ground, sq, w, { depth: DEFAULTS.rd, halfWidth: DEFAULTS.rw, lakeDepth: DEFAULTS.ld });
  const legacy = fitHeights(ground, legacyCarved.heights, { sea });
  const spacing = extentOf(sq) / (N - 1);
  const tunnelsCut = { ...w, rivers: w.rivers.filter((r) => r.brunnel !== "tunnel") };
  const specDrama = fitDrama(ground, { sea, spacing, wet: wetMaskFor(sq, tunnelsCut) });
  const dramaCarved = carveWater(ground, sq, w, { depth: DEFAULTS.rd / specDrama.high, halfWidth: DEFAULTS.rw, lakeDepth: DEFAULTS.ld / specDrama.high });
  const drama = dramaFit(ground, dramaCarved.heights, specDrama, { sea });
  let sourceMin = Infinity, sourceMax = -Infinity;
  for (const v of ground) { if (v < sourceMin) sourceMin = v; if (v > sourceMax) sourceMax = v; }
  const sourceRelief = sourceMax - sourceMin;
  const legacyShape = terrainShape(legacy.game);
  const dramaShape = terrainShape(drama.game);
  const row = {
    slug: spec.slug, kind: spec.kind, name: sq.name ?? spec.name,
    center: { lon: sq.lon, lat: sq.lat }, scale: sq.scale,
    source_relief_m: +sourceRelief.toFixed(1),
    legacy: {
      gains: { regional: 1, local: legacy.verticalScale },
      relief_m: +(legacy.gameMax - legacy.gameMin).toFixed(1),
      roughness_percent: +legacyShape.roughness_percent.toFixed(2),
      central_height_range_m: +legacyShape.central_terrain_diversity_m.toFixed(1),
      terracing: +terracing(legacy.game).toFixed(4),
      game_max_m: +legacy.gameMax.toFixed(1),
    },
    drama: {
      gains: { regional: specDrama.low, local: specDrama.high },
      limited_by: specDrama.limitedBy,
      target: specDrama.target, achieved: specDrama.achieved,
      relief_m: +(drama.gameMax - drama.gameMin).toFixed(1),
      roughness_percent: +dramaShape.roughness_percent.toFixed(2),
      central_height_range_m: +dramaShape.central_terrain_diversity_m.toFixed(1),
      buildable: specDrama.buildable,
      terracing: +terracing(drama.game).toFixed(4),
      game_max_m: +drama.gameMax.toFixed(1),
      ...orderMetrics(legacy.game, drama.game),
    },
  };
  row.bands = {
    legacy: {
      relief: band(row.legacy.relief_m, STOCK_TERRAIN_BAND.relief_m),
      roughness: band(row.legacy.roughness_percent, STOCK_TERRAIN_BAND.roughness_percent),
      central_height_range: band(row.legacy.central_height_range_m, STOCK_TERRAIN_BAND.central_terrain_diversity_m),
    },
    drama: {
      relief: band(row.drama.relief_m, STOCK_TERRAIN_BAND.relief_m),
      roughness: band(row.drama.roughness_percent, STOCK_TERRAIN_BAND.roughness_percent),
      central_height_range: band(row.drama.central_height_range_m, STOCK_TERRAIN_BAND.central_terrain_diversity_m),
    },
  };
  await writeHillshade(dir, `${spec.slug}-legacy`, legacy.game);
  await writeHillshade(dir, `${spec.slug}-drama`, drama.game);
  return row;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const outIndex = process.argv.indexOf("--out");
  const dir = outIndex > 0 ? process.argv[outIndex + 1] : join(HERE, "terrain-drama-evidence");
  await mkdir(dir, { recursive: true });
  // The rule: lowest and highest source relief among the declared candidates, measured before
  // any transformed number is compared.
  const candidates = [];
  for (const candidate of CANDIDATES) {
    const sq = { ...candidate, rotation: 0, scale: 1 };
    const elev = await sampleElevation(sq);
    const ground = smooth(elev.heights, 1);
    // Relief of the square's dry ground: an offshore seabed (a harbour the vector water layer
    // calls something other than "ocean" included) is not the relief a player builds on.
    let lo = Infinity, hi = -Infinity;
    for (let i = 0; i < ground.length; i++) {
      if (ground[i] <= 0) continue;
      const v = ground[i]; if (v < lo) lo = v; if (v > hi) hi = v;
    }
    candidates.push({ ...candidate, source_relief_m: +(hi - lo).toFixed(1) });
    console.log(`${candidate.slug}: source relief ${candidates.at(-1).source_relief_m} m`);
  }
  const flat = candidates.reduce((a, b) => (b.source_relief_m < a.source_relief_m ? b : a));
  const steep = candidates.reduce((a, b) => (b.source_relief_m > a.source_relief_m ? b : a));
  const squares = [...SQUARES, { ...flat, kind: "rule_flat" }, { ...steep, kind: "rule_steep" }];
  const rows = [];
  for (const square of squares) {
    process.stdout.write(`${square.slug}… `);
    rows.push(await measureSquare(square, dir));
    console.log("done");
  }
  const evidence = {
    schema: 1, version: "pl1329-terrain-drama-evidence-v1",
    generated_by: "tools/map-factory/audit_terrain_drama.mjs",
    scope: "Offline terrain-shape comparison of the shipping fit and the opt-in drama fit. No game, no writer, no water-safety claim.",
    spacing_m: SPACING, grid: "1081 x 1081, south-first", terrain_unit_m: 1 / 64,
    stock_band: STOCK_TERRAIN_BAND,
    stock_band_source: "tools/map-factory/survey/terrain-interest.json and capabilities.json (104 shipped maps, frozen 2026-11-21)",
    rule: {
      declared_before_measuring: true,
      candidates: candidates.map(({ slug, name, source_relief_m }) => ({ slug, name, source_relief_m })),
      flat: flat.slug, steep: steep.slug,
      text: "Among these six squares, the one with the lowest source relief is 'very flat' and the highest is 'very steep'. Source relief is the range of the square's own ground above sea level, before any transform; open sea and seabed are excluded.",
    },
    gradients: "mean terrain gradient magnitude at 16 m spacing, percent; central height range is the 10th-90th percentile over the central 25 tiles' nodes",
    rows,
  };
  await writeFile(join(dir, "evidence.json"), JSON.stringify(evidence, null, 2) + "\n");
  for (const row of rows) {
    console.log(`${row.slug.padEnd(13)} legacy ${String(row.legacy.relief_m).padStart(6)} m ${String(row.legacy.roughness_percent).padStart(6)}% ${String(row.legacy.central_height_range_m).padStart(6)} m | drama x${row.drama.gains.regional}/${row.drama.gains.local} ${String(row.drama.relief_m).padStart(6)} m ${String(row.drama.roughness_percent).padStart(6)}% ${String(row.drama.central_height_range_m).padStart(6)} m ${row.drama.limited_by ?? ""}`);
  }
  console.log(`evidence: ${join(dir, "evidence.json")}`);
}

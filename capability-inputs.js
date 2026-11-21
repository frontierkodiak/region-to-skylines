// The pan-time approximation uses captured initial terrain, not a water simulation.
// Full export reports use final prepared grids through capabilities.py instead.
import { captureInputs, oceanMask } from "./inputs.js";
import { measureStockMetrics } from "./capability-model.js";
import { LANDCOVER_SOURCE, MRDS_SOURCE, PLACE_GRID, requestDeposits, requestLandcover } from "./capability-evidence.js";

/** The 271-node lattice the capability grid uses, sampled from a 1081-square grid. */
const NODES = PLACE_GRID.size;

/**
 * What the stock maps' measures can honestly say at capture fidelity. Measured on
 * the five committed prepared fixtures: whole-map relief kept its stock band on
 * all five, but the capture estimate of central land slope crossed a band on
 * Asheville and central wet share crossed one on Pittsburgh. Those two need the
 * prepared terrain and water, which the pan-time capture does not have, so the
 * reason travels with the value and no caller can quietly compare them anyway.
 */
export const CAPTURE_STOCK = {
  terrain_relief_m: { comparable: true, basis: "capture_heightmap" },
  median_land_slope_percent: {
    comparable: false,
    reason: "capture_terrain_and_water_are_not_prepared",
    detail: "Slope would read the captured terrain through carved-bed water screening, not the prepared terrain and water mask; on a committed fixture that moved the median across a stock band.",
  },
  wet_central_fraction: {
    comparable: false,
    reason: "capture_bed_depth_is_not_prepared_water",
    detail: "The capture estimates carved-bed depth, not the finished map's water level; on a committed fixture that moved the share across a stock band.",
  },
};

/**
 * Bank-minus-bed excavation on every node: it estimates river cutting, not the filled
 * level. Coastal water uses the capture's explicit ocean mask and fitted sea level.
 */
function captureDepth({ game, banks, seaLevel, geometry }) {
  const sea = oceanMask(geometry.oceans ?? [], geometry.sq), depth = new Float64Array(game.length);
  for (let i = 0; i < game.length; i++)
    depth[i] = Math.max(0, sea?.[i] && seaLevel != null ? seaLevel - game[i] : 0, banks[i] - game[i]);
  return depth;
}

export function estimateInputs(capture, depth = captureDepth(capture), evidence = {}) {
  const { game, geometry } = capture;
  const n = 1081, coarse = NODES;
  const ship = new Float64Array(coarse ** 2), terrain = new Array(coarse ** 2);
  let dry = 0, central = 0;
  for (let r = 0; r < coarse; r++) for (let c = 0; c < coarse; c++) {
    let minimum = Infinity;
    for (let y = r * 4; y < Math.min(n, r * 4 + 4); y++) for (let x = c * 4; x < Math.min(n, c * 4 + 4); x++)
      minimum = Math.min(minimum, depth[y * n + x]);
    ship[r * coarse + c] = minimum;
    // The same node the exporter reads from its prepared terrain.
    terrain[r * coarse + c] = game[(r * 4) * n + c * 4];
    const y = r * 4, x = c * 4, i = y * n + x;
    if (x >= 240 && x < 840 && y >= 240 && y < 840) {
      const dx = (game[i + 1] - game[i - 1]) / 32, dy = (game[i + n] - game[i - n]) / 32;
      central++;
      if (minimum < 0.25 && Math.hypot(dx, dy) < 0.15) dry++;
    }
  }
  const roads = geometry.roads ?? [];
  return { schema: 1, mode: "estimate", grid: { size: coarse, spacing_m: 64, depth_m: Array.from(ship) },
    transport: { road: roads.some((r) => ["motorway", "trunk"].includes(r.class)), rail: roads.some((r) => r.class === "rail"), air: !!geometry.airport },
    buildable_fraction: central ? dry / central : null,
    place: {
      terrain_m: terrain,
      landcover: evidence.landcover ?? { status: "unavailable", source: LANDCOVER_SOURCE, fidelity: "unavailable", tiles: [], values: null },
      deposits: evidence.deposits ?? { status: "unavailable", source: MRDS_SOURCE, records: [] },
    } };
}

/** Captures run north-first; the stock measures read the game's south-first order. */
function southFirst(grid, n = 1081) {
  const out = new Float64Array(n * n);
  for (let r = 0; r < n; r++) out.set(grid.subarray((n - 1 - r) * n, (n - r) * n), r * n);
  return out;
}

export function stockEstimate(capture, depth = captureDepth(capture)) {
  return { fidelity: "capture_estimate", measures: measureStockMetrics(southFirst(capture.game), southFirst(depth)), comparability: CAPTURE_STOCK };
}

export async function captureEstimate(sq, { signal } = {}) {
  // One terrain capture feeds the icon row, the stock comparison and the slope
  // screen; land cover and deposits are the only extra reads.
  const capturePromise = captureInputs(sq, { signal, includeRunways: true });
  const coverPromise = requestLandcover(sq, { signal });
  const depositPromise = requestDeposits(sq, { signal }).catch((error) => {
    if (signal?.aborted) throw error;
    return { status: "unavailable", source: MRDS_SOURCE, records: [] };
  });
  const capture = await capturePromise;
  if (signal?.aborted) throw signal.reason;
  const [landcover, deposits] = await Promise.all([coverPromise, depositPromise]);
  if (signal?.aborted) throw signal.reason;
  // One fetch and one depth pass feed both the icon row and the stock comparison.
  const depth = captureDepth(capture);
  return { input: estimateInputs(capture, depth, { landcover, deposits }), stock: stockEstimate(capture, depth), square: capture.geometry.sq };
}

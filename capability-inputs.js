// The pan-time approximation uses captured initial terrain, not a water simulation.
// Full export reports use final prepared grids through capabilities.py instead.
import { captureInputs, oceanMask } from "./inputs.js";

export function estimateInputs(capture) {
  const { game, banks, geometry, seaLevel } = capture;
  const n = 1081, coarse = 271, depth = new Float64Array(coarse ** 2);
  const sea = oceanMask(geometry.oceans ?? [], geometry.sq);
  let dry = 0, central = 0;
  for (let r = 0; r < coarse; r++) for (let c = 0; c < coarse; c++) {
    let minimum = Infinity;
    for (let y = r * 4; y < Math.min(n, r * 4 + 4); y++) for (let x = c * 4; x < Math.min(n, c * 4 + 4); x++) {
      const i = y * n + x;
      // Bank-minus-bed estimates river excavation, not the actual filled level.
      // Coastal water uses the capture's explicit ocean mask/fitted sea level.
      const d = Math.max(0, sea?.[i] && seaLevel != null ? seaLevel - game[i] : 0, banks[i] - game[i]);
      minimum = Math.min(minimum, d);
    }
    depth[r * coarse + c] = minimum;
    const y = r * 4, x = c * 4, i = y * n + x;
    if (x >= 240 && x < 840 && y >= 240 && y < 840) {
      const dx = (game[i + 1] - game[i - 1]) / 32, dy = (game[i + n] - game[i - n]) / 32;
      central++;
      if (minimum < 0.25 && Math.hypot(dx, dy) < 0.15) dry++;
    }
  }
  const roads = geometry.roads ?? [];
  return { schema: 1, mode: "estimate", grid: { size: coarse, spacing_m: 64, depth_m: Array.from(depth) },
    transport: { road: roads.some((r) => ["motorway", "trunk"].includes(r.class)), rail: roads.some((r) => r.class === "rail"), air: !!geometry.airport },
    buildable_fraction: central ? dry / central : null };
}

export async function captureEstimate(sq, { signal } = {}) {
  const capture = await captureInputs(sq, { signal, includeRunways: true });
  if (signal?.aborted) throw signal.reason;
  return { input: estimateInputs(capture), square: capture.geometry.sq };
}

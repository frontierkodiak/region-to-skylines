// Active PL1212 Water-only port; frozen predicates, new unscored runtime.
import { sample, position, tileOf } from "./start-model.js";
export const WATER_MODEL = "pl1212-surface-intake-port-v1";
export const WATER_LOAD = Object.freeze({
  consumer_api: "spatial_water_and_sewage", settling_has_load: true,
  native_units_per_cycle: 1000, cycle_frames: 256, settling_game_minutes: 2,
  horizon_game_minutes: 60, shore_snap_radius_m: 50, auxiliary_power_rate: 1000,
  max_pollution_native: 0,
});
export const WATER_BANK = Object.freeze({
  search_radius_m: 192, radial_step_m: 16, directions: 16,
  lateral_sample_spacing_m: 8, minimum_wet_depth_m: 1,
  minimum_freeboard_m: 0.25, maximum_freeboard_m: 8, maximum_bank_slope: 0.15,
});
const N = 1081;
const xz = (p) => [p[0], p[2]];
const distance = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const mix = (a, b, t) => a.map((v, i) => v * (1 - t) + b[i] * t);
export function bankCandidate(ground, depth, anchor, waterHeight, tile, northFirst = false) {
  const read = (grid, point) => sample(grid, point, northFirst);
  const origin = xz(anchor), candidates = [], b = WATER_BANK;
  for (let radius = b.radial_step_m; radius <= b.search_radius_m; radius += b.radial_step_m)
    for (let direction = 0; direction < b.directions; direction++) {
      const angle = direction * (2 * Math.PI / b.directions);
      const point = [origin[0] + radius * Math.cos(angle), origin[1] + radius * Math.sin(angle)];
      const p = [point[0], read(ground, point), point[1]];
      if (tileOf(p) !== tile || read(depth, point) > 0.1) continue;
      const [x, z] = point;
      const dz = (read(ground, [x, z + 16]) - read(ground, [x, z - 16])) / 32;
      const dx = (read(ground, [x + 16, z]) - read(ground, [x - 16, z])) / 32;
      const slope = Math.hypot(dx, dz), freeboard = p[1] - waterHeight;
      if (freeboard < b.minimum_freeboard_m || freeboard > b.maximum_freeboard_m || slope > b.maximum_bank_slope) continue;
      const count = Math.trunc(radius / b.lateral_sample_spacing_m) + 1;
      let last = count - 1, minimum = Infinity;
      for (let i = 0; i < count; i++) {
        const wetDepth = read(depth, mix(origin, point, i / (count - 1)));
        if (wetDepth < b.minimum_wet_depth_m) { last = i - 1; break; }
        minimum = Math.min(minimum, wetDepth);
      }
      if (last < 0) continue;
      const wet = mix(origin, point, last / (count - 1));
      if (distance(point, wet) > WATER_LOAD.shore_snap_radius_m) continue;
      candidates.push({ radius, slope, angle, result: {
        bank: p, water_anchor: [wet[0], 0, wet[1]],
        lateral_offset_m: distance(wet, origin), lateral_min_depth_m: minimum,
        lateral_sample_count: last + 1,
      } });
    }
  candidates.sort((a, b) => a.radius - b.radius || a.slope - b.slope || a.angle - b.angle);
  return candidates[0]?.result ?? null;
}
export function channelCandidate(ground, depth, routes, tile) {
  const candidates = [];
  for (const name of Object.keys(routes).sort()) {
    const p = routes[name];
    if (!Array.isArray(p) || p.length < 2 || p.some((v) => !Array.isArray(v) || v.length !== 3 || v.some((x) => !Number.isFinite(x)))) continue;
    const depths = p.map((v) => sample(depth, xz(v)));
    const surfaces = p.map((v, i) => sample(ground, xz(v)) + depths[i]);
    const arc = [0];
    for (let i = 1; i < p.length; i++) arc.push(arc[i - 1] + distance(xz(p[i]), xz(p[i - 1])));
    const inside = p.map((_, i) => i).filter((i) => tileOf(p[i]) === tile && depths[i] >= 1);
    for (const i of inside) {
      const j = inside.find((j) => arc[j] - arc[i] >= 320 &&
        depths.slice(i, j + 1).every((d) => d >= 1) && surfaces[i] > surfaces[j] + 1 / 64);
      if (j === undefined) continue;
      candidates.push({ name, i, j, separation: arc[j] - arc[i], p, depths, surfaces }); break;
    }
  }
  candidates.sort((a, b) => a.separation - b.separation || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0) || a.i - b.i || a.j - b.j);
  const c = candidates[0];
  return c ? {
    river: c.name, intake_sample_index: c.i, outlet_sample_index: c.j,
    intake_water_point: c.p[c.i], outlet_water_point: c.p[c.j],
    along_route_separation_m: c.separation, initial_intake_depth_m: c.depths[c.i],
    initial_surface_drop_m: c.surfaces[c.i] - c.surfaces[c.j],
    direction_basis: "Prepared upstream-to-downstream channel route and initial surface drop; not simulated velocity",
    bank_placement: null, demand_native_units: null, horizon_game_minutes: 60,
  } : null;
}
const base = () => ({
  level: "unknown", predicted: null, witness: null, model: WATER_MODEL,
  native_agreement: "unscored_new_runtime", stock_comparison: "not_comparable",
  service: "unknown", flow: "unknown", hookup: "unknown",
});
function complete(g, d) {
  return g?.length === N * N && d?.length === N * N &&
    !g.some((v) => !Number.isFinite(v)) && !d.some((v) => !Number.isFinite(v));
}
export function evaluateWater(data) {
  const water = base(), input = data.start_input;
  if (data.planner_enabled?.water === false) return { ...water, reason: "planner_disabled" };
  if (!input) return { ...water, reason: "missing_complete_water_grids" };
  if (input.fidelity !== "prepared_16m_south_first") return { ...water, reason: "unsupported_water_fidelity" };
  water.fidelity = input.fidelity;
  const { terrain_m: g, depth_m: d, tile } = input;
  if (!complete(g, d)) return { ...water, reason: "missing_complete_water_grids" };
  if (d.some((v) => v < 0)) throw new Error("Negative water depth");
  if (!Number.isInteger(tile) || tile < 0 || tile >= 25) return { ...water, reason: "missing_start_tile" };
  const routes = data.water_plan?.samples;
  if (!routes || Array.isArray(routes) || typeof routes !== "object" || !Object.keys(routes).length)
    return { ...water, reason: "missing_directed_channel_routes" };
  if (Object.values(routes).some((p) => !Array.isArray(p) || p.length < 2 ||
    p.some((v) => !Array.isArray(v) || v.length !== 3 || v.some((x) => !Number.isFinite(x)))))
    return { ...water, reason: "partial_channel_routes" };
  const candidate = channelCandidate(g, d, routes, tile);
  Object.assign(water, { reason: "no_supported_surface_load_witness", channel_candidate: candidate });
  if (!candidate) return water;
  const banks = [];
  for (const [key, prefab] of [["intake_water_point", "Water Intake"], ["outlet_water_point", "Water Outlet"]]) {
    const anchor = candidate[key], surface = sample(g, xz(anchor)) + sample(d, xz(anchor));
    const bank = bankCandidate(g, d, anchor, surface, tile);
    if (!bank) return water;
    banks.push({ prefab, anchor: bank.water_anchor, initial_surface_m: surface,
      model_bank_candidate: bank.bank,
      bank_search: { lateral_offset_m: bank.lateral_offset_m, lateral_min_depth_m: bank.lateral_min_depth_m, lateral_sample_count: bank.lateral_sample_count },
      placement: "one_native_shore_snap", shore_snap_radius_m: WATER_LOAD.shore_snap_radius_m });
  }
  const consumer = position(g, [0, 2].map((i) => (banks[0].model_bank_candidate[i] + banks[1].model_bank_candidate[i]) / 2));
  return { ...water, predicted: true, level: "likely",
    reason: "initial_wet_downstream_route_with_nearby_bank_candidates",
    witness: { schema: 1, start_tile: tile, facilities: banks, consumer_point: consumer,
      load: { ...WATER_LOAD }, channel_route: candidate,
      auxiliary_power: "fixed native ElectricityManager supply, not a claim about map power generation",
      pipe_plan: "intake native pipe node -> consumer -> outlet native pipe node; no reroute",
      scope: "Specified surface intake/outlet anchors, one native shore snap each, controlled power and fixed load/horizon" },
    limits: [
      "Provisional geometric model; native shore snapping/placement may reject the specified anchors",
      "Native demand units per256simulationframes; no m3/s or population conversion",
      "Only a successful fixed-load native run can establish service at that demand/horizon",
      "Power is held available as an explicit auxiliary fixture, not a whole-map gameplay promise",
      "No global or long-horizon guarantee; no promise promotion",
    ],
    initial_quality_basis: "crp.water_payload initializes native water pollution to zero; not a real-world salinity claim",
  };
}

/** Finite central-square shoreline search on one full north-first capture.
 * No directed route, future start tile, service, salinity or native load inference.
 * Row-major 64m wet anchors; same lateral bank geometry, only central-square scope.
 */
export function liveShore(ground, depth, { spacing = 16 } = {}) {
  const result = { ...base(), reason: "incomplete_or_coarse_shore_grid",
    opportunity: "unknown", fidelity: "capture_16m_bank_minus_bed_or_coastal_depth",
    native_agreement: "unscored_capture_approximation" };
  if (spacing !== 16 || !complete(ground, depth) || depth.some((v) => v < 0)) return result;
  for (let z = -832; z <= 832; z += 64) for (let x = -832; x <= 832; x += 64) {
    if (sample(depth, [x, z], true) < WATER_BANK.minimum_wet_depth_m) continue;
    const surface = sample(ground, [x, z], true) + sample(depth, [x, z], true);
    const bank = bankCandidate(ground, depth, [x, 0, z], surface, 12, true);
    if (bank) return { ...result, level: "likely", reason: "captured_shore_bank_candidate",
      opportunity: "candidate", bank, wet_point_xz: [x, z],
      scope: "Central 1920m square, 64m wet-anchor lattice, 16m capture and 8m lateral interpolation" };
  }
  return { ...result, reason: "no_bank_in_finite_capture_search" };
}

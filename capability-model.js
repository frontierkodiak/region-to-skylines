import { evaluateStart } from "./start-model.js";
// Mirrored deterministic core: tools/map-factory/capabilities.py. No DOM or IO.
const KINDS = { road: ["highway", "ramp"], rail: ["rail"], ship: ["ship"], air: ["air"] };
const PATH_SCOPE = "sampled_native_lane_paths_at_opening";
const CONTROLS = ["boundary_0", "boundary_1", "midpoint_0", "midpoint_1"];
const INPUTS = ["hydrology.json", "terrain.u16", "water.u16"];
const digest = (value) => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
const canonical = (value) => JSON.stringify(value, (_, v) => v && typeof v === "object" && !Array.isArray(v)
  ? Object.fromEntries(Object.keys(v).sort().map((key) => [key, v[key]])) : v);

export function validNativeContext(context) {
  const assemblies = context?.game_assemblies, protocol = context?.protocol;
  return !!assemblies && digest(assemblies["Assembly-CSharp.dll"]) && digest(assemblies["UnityEngine.dll"]) &&
    Object.values(assemblies).every(digest) && digest(context.mod_sha256) && digest(context.collector_sha256) &&
    digest(context.runtime_game_sha256) && canonical(context.runtime_game_assemblies) === canonical(assemblies) &&
    protocol?.entry === "NewGameFromMap" && protocol.no_workshop === true &&
    protocol.strict_disable_mods === false && protocol.inverted_traffic === false;
}

export function validNativeIdentityRef(ref) {
  return digest(ref?.sha256) && ref.file === `tools/map-factory/capability-evidence/runtime-identities/${ref.sha256}.json`;
}

export function qualifyExactExport(report, identity, ledger) {
  if (report.mode !== "export" || !validNativeContext(identity?.native_context) || !digest(identity.artifact_sha256) ||
    canonical(Object.keys(identity.inputs_sha256 ?? {}).sort()) !== canonical(INPUTS) || !Object.values(identity.inputs_sha256).every(digest)) return report;
  const capabilities = { ...report.capabilities };
  for (const certificate of ledger.native_path_certificates ?? []) {
    const key = certificate.capability;
    if (!["ship", "air"].includes(key) || capabilities[key]?.level !== "likely" || certificate.scope !== PATH_SCOPE ||
      canonical(Object.keys(certificate.controls ?? {}).sort()) !== canonical([...CONTROLS].sort()) ||
      !CONTROLS.every((control) => certificate.controls[control] === true) || !certificate.evidence?.length || certificate.blocked_by?.length ||
      !validNativeIdentityRef(certificate.runtime_identity_evidence) ||
      !digest(certificate.observation_sha256) || !certificate.evidence.some((e) => e.sha256 === certificate.observation_sha256) ||
      certificate.artifact_sha256 !== identity.artifact_sha256 ||
      canonical(certificate.inputs_sha256) !== canonical(identity.inputs_sha256) ||
      canonical(certificate.native_context) !== canonical(identity.native_context)) continue;
    capabilities[key] = { ...capabilities[key], level: "promised", reason: "exact_export_sampled_native_paths",
      qualification: { scope: PATH_SCOPE, observed_at: certificate.observed_at, artifact_sha256: certificate.artifact_sha256,
        native_context: certificate.native_context, runtime_identity_evidence: certificate.runtime_identity_evidence,
        observation_sha256: certificate.observation_sha256,
        evidence: certificate.evidence, limitations: certificate.limitations } };
  }
  return { ...report, capabilities };
}

export function shipCorridor(depth, size, spacing, rules) {
  const deep = Array.from(depth, (d) => d >= rules.min_initial_depth_m);
  const safe = deep.map((wet, i) => {
    if (!wet) return false;
    const r = Math.floor(i / size), c = i % size, reach = rules.shore_clearance_cells;
    for (let y = Math.max(0, r - reach); y < Math.min(size, r + reach + 1); y++)
      for (let x = Math.max(0, c - reach); x < Math.min(size, c + reach + 1); x++)
        if (!deep[y * size + x]) return false;
    return true;
  });
  const seen = new Set(), half = (size - 1) * spacing / 2;
  for (let seed = 0; seed < safe.length; seed++) {
    if (!safe[seed] || seen.has(seed)) continue;
    const queue = [seed], border = [];
    let central = false;
    seen.add(seed);
    for (let q = 0; q < queue.length; q++) {
      const cell = queue[q], r = Math.floor(cell / size), c = cell % size;
      central ||= Math.abs(c * spacing - half) <= rules.central_half_extent_m && Math.abs(r * spacing - half) <= rules.central_half_extent_m;
      if (r === 0 || r === size - 1 || c === 0 || c === size - 1) border.push(cell);
      for (const [y, x] of [[r - 1, c], [r, c - 1], [r, c + 1], [r + 1, c]]) {
        const i = y * size + x;
        if (y >= 0 && y < size && x >= 0 && x < size && safe[i] && !seen.has(i)) {
          seen.add(i); queue.push(i);
        }
      }
    }
    if (border.length < 2 || !central) continue;
    const byCol = [...border].sort((a, b) => a % size - b % size || a - b);
    const byRow = [...border].sort((a, b) => a - b);
    const extremes = [byCol[0], byCol.at(-1), byRow[0], byRow.at(-1)];
    for (const a of extremes) for (const b of extremes) {
      if (Math.hypot(Math.floor(a / size) - Math.floor(b / size), a % size - b % size) * spacing >= rules.min_endpoint_separation_m)
        return { candidate: true, endpoints: [a, b], clearance_m: spacing * rules.shore_clearance_cells, depth_m: rules.min_initial_depth_m };
    }
  }
  return { candidate: false, endpoints: [], clearance_m: spacing * rules.shore_clearance_cells, depth_m: rules.min_initial_depth_m };
}

export function networkAccess(graph, capability) {
  const nodes = graph.nodes ?? [], forward = nodes.map(() => []), reverse = nodes.map(() => []);
  for (const edge of graph.edges ?? []) {
    if (!KINDS[capability].includes(edge.kind)) continue;
    const { a, b } = edge;
    if (!Number.isInteger(a) || !Number.isInteger(b) || !nodes[a] || !nodes[b]) throw new Error("Invalid capability graph edge");
    forward[a].push(b); reverse[b].push(a);
    if (capability !== "road") { forward[b].push(a); reverse[a].push(b); }
  }
  const outside = new Set(nodes.flatMap((node, i) => node.outside ? [i] : []));
  const incoming = [...outside].filter((i) => forward[i].length), outgoing = [...outside].filter((i) => reverse[i].length);
  for (const seed of incoming) {
    const queue = [seed], seen = new Set([seed]);
    for (let q = 0; q < queue.length; q++) {
      const i = queue[q];
      if (i !== seed && outside.has(i)) return { candidate: true, incoming: incoming.length, outgoing: outgoing.length, endpoints: [seed, i] };
      for (const neighbour of forward[i]) if (!seen.has(neighbour)) { seen.add(neighbour); queue.push(neighbour); }
    }
  }
  return { candidate: false, incoming: incoming.length, outgoing: outgoing.length, endpoints: [] };
}

const round4 = (value) => (Number.isFinite(value) ? round(value, 4) : null);
const round3 = (value) => (Number.isFinite(value) ? round(value, 3) : null);

/** Recorded deposits inside the square, split by kind; a missing record is not absence. */
function depositEvidence(deposits, centralHalf) {
  const status = deposits?.status === "available" ? "available" : "unavailable";
  const records = status === "available" && Array.isArray(deposits.records) ? deposits.records : [];
  const summary = { ore: { records: 0, central: 0, central_weight: 0 }, oil: { records: 0, central: 0, central_weight: 0 }, wells: 0 };
  for (const record of records) {
    if (record?.kind === "well") { summary.wells++; continue; }
    const kind = record?.kind === "oil" ? "oil" : record?.kind === "ore" ? "ore" : null;
    if (!kind || !Number.isFinite(record.x) || !Number.isFinite(record.z)) continue;
    summary[kind].records++;
    if (Math.abs(record.x) <= centralHalf && Math.abs(record.z) <= centralHalf) {
      summary[kind].central++;
      summary[kind].central_weight += Number.isFinite(record.weight) ? record.weight : 1;
    }
  }
  for (const kind of ["ore", "oil"]) summary[kind].central_weight = round3(summary[kind].central_weight);
  const recorded = summary.ore.records + summary.oil.records;
  return { status, source: deposits?.source ?? null, records: recorded, wells: summary.wells, ore: summary.ore, oil: summary.oil };
}

/**
 * Vegetation and resource potential from place evidence, mirrored in
 * tools/map-factory/capabilities.py. Every node is the same lattice as the
 * depth grid. Weights, class sets, slope cuts and thresholds come from the
 * ledger's model_rules.place, so neither core carries a second catalog.
 */
export function placeEvidence(grid, place, rules) {
  const n = grid.size, spacing = grid.spacing_m, total = n * n;
  const values = place?.landcover?.status === "available" ? place.landcover.values : null;
  if (values && (values.length !== total || Array.from(values).some((v) => !Number.isInteger(v) || v < 0 || v > 255)))
    throw new Error("Land-cover evidence must match the capability grid as 0-255 classes");
  const terrain = Array.isArray(place?.terrain_m) ? place.terrain_m : null;
  if (terrain && (terrain.length !== total || terrain.some((h) => !Number.isFinite(h))))
    throw new Error("Terrain evidence must match the capability grid as finite metres");
  const half = ((n - 1) * spacing) / 2, centralHalf = rules.central_half_extent_m;
  // Central differences at the lattice spacing, one-sided at the edges, as
  // numpy.gradient at the same spacing. Magnitudes only; row 0 is north.
  let gx = null, gz = null;
  if (terrain) {
    gx = new Float64Array(total); gz = new Float64Array(total);
    for (let r = 0; r < n; r++) {
      const r0 = Math.max(0, r - 1), r1 = Math.min(n - 1, r + 1), dz = r === 0 || r === n - 1 ? spacing : 2 * spacing;
      for (let c = 0; c < n; c++) {
        const c0 = Math.max(0, c - 1), c1 = Math.min(n - 1, c + 1), dx = c === 0 || c === n - 1 ? spacing : 2 * spacing;
        gz[r * n + c] = (terrain[r1 * n + c] - terrain[r0 * n + c]) / dz;
        gx[r * n + c] = (terrain[r * n + c1] - terrain[r * n + c0]) / dx;
      }
    }
  }
  const forest = new Set(rules.forest_classes), vegetated = new Set(rules.vegetated_classes), crop = new Set(rules.crop_classes);
  const counts = {};
  let centralLand = 0, covered = 0, treeCover = 0, vegetatedNodes = 0, cropNodes = 0, treeSum = 0, fertileSum = 0;
  for (let r = 0; r < n; r++) {
    const z = half - r * spacing;
    if (Math.abs(z) > centralHalf) continue;
    for (let c = 0; c < n; c++) {
      if (Math.abs(c * spacing - half) > centralHalf) continue;
      const i = r * n + c;
      if (!(grid.depth_m[i] < rules.land_depth_m)) continue;
      centralLand++;
      if (!values) continue;
      const cls = values[i], weight = rules.tree_weight[cls] ?? 0, fertile = rules.fertile_weight[cls] ?? 0;
      if (cls !== 0) covered++;
      counts[cls] = (counts[cls] ?? 0) + 1;
      if (forest.has(cls)) treeCover++;
      if (vegetated.has(cls)) vegetatedNodes++;
      if (crop.has(cls)) cropNodes++;
      if (gx) {
        const axis = Math.max(Math.abs(gx[i]), Math.abs(gz[i]));
        treeSum += weight * Math.min(1, Math.max(0, (rules.tree_slope_limit_percent / 100 - axis) / (rules.tree_slope_taper_percent / 100)));
        const slope = Math.sqrt(gx[i] * gx[i] + gz[i] * gz[i]) * 100;
        const flat = Math.min(1, Math.max(0, (rules.fertile_slope_none_percent - slope) / (rules.fertile_slope_none_percent - rules.fertile_slope_full_percent)));
        fertileSum += fertile * flat;
      } else {
        treeSum += weight; fertileSum += fertile;
      }
    }
  }
  return {
    grid: { size: n, spacing_m: spacing, central_half_extent_m: centralHalf, central_land_nodes: centralLand },
    landcover: {
      status: values ? "available" : "unavailable",
      source: values ? (place.landcover.source ?? null) : null,
      fidelity: values ? (place.landcover.fidelity ?? "unspecified") : null,
      cell_m: values ? (place.landcover.cell_m ?? null) : null,
      sample_m: values ? (place.landcover.sample_m ?? null) : null,
      tiles: values && Array.isArray(place.landcover.tiles) ? place.landcover.tiles : [],
      coverage_of_central_land: centralLand ? round4(covered / centralLand) : null,
      class_counts: Object.fromEntries(Object.keys(counts).sort((a, b) => a - b).map((key) => [key, counts[key]])),
    },
    deposits: depositEvidence(place?.deposits, centralHalf),
    vegetation: {
      tree_suitability: centralLand ? round4(treeSum / centralLand) : null,
      tree_cover_share_of_central_land: centralLand ? round4(treeCover / centralLand) : null,
      vegetated_share_of_central_land: centralLand ? round4(vegetatedNodes / centralLand) : null,
      slope_screened: !!gx,
      slope_limit_percent: rules.tree_slope_limit_percent,
      candidate_min: rules.tree_suitability_min,
    },
    fertility: {
      suitability: centralLand ? round4(fertileSum / centralLand) : null,
      crop_share_of_central_land: centralLand ? round4(cropNodes / centralLand) : null,
      slope_full_percent: rules.fertile_slope_full_percent,
      slope_none_percent: rules.fertile_slope_none_percent,
      candidate_min: rules.fertile_suitability_min,
    },
    balanced_top_up: "not_evidence",
  };
}

/**
 * The two candidate levels. Trees describe what the land cover can host, never
 * the export's budgeted tree count. Resources report recorded deposits and
 * fertile cover; a missing deposit record is not geographic absence, so this
 * never yields a negative from place evidence alone.
 */
export function placeCapabilities(grid, place, rules) {
  const evidence = placeEvidence(grid, place, rules);
  const centralLand = evidence.grid.central_land_nodes;
  const coverage = evidence.landcover.coverage_of_central_land ?? 0;
  const landcoverOk = evidence.landcover.status === "available" && centralLand > 0 && coverage >= rules.landcover_min_coverage;
  const suitability = evidence.vegetation.tree_suitability, trees = evidence.landcover.status !== "available"
    ? { level: "unknown", reason: "no_landcover_evidence" }
    : centralLand === 0 ? { level: "unknown", reason: "no_central_land" }
    : !landcoverOk ? { level: "unknown", reason: "landcover_coverage_incomplete" }
    // The candidate threshold is not an impossibility boundary: a coarse
    // overview, a 90 percent covered window or a thin patch can all read low.
    // Only the export plan's own empty tree list can say No.
    : suitability >= rules.tree_suitability_min ? { level: "likely", reason: "vegetation_suitability_candidate" }
    : suitability > 0 ? { level: "unknown", reason: "tree_support_below_candidate_threshold" }
    : { level: "unknown", reason: "no_tree_support_in_sampled_landcover" };
  const deposits = evidence.deposits, fertile = evidence.fertility.suitability;
  const crop = evidence.fertility.crop_share_of_central_land ?? 0;
  const resources = deposits.status === "available" && (deposits.ore.central > 0 || deposits.oil.central > 0)
    ? { level: "likely", reason: "recorded_deposit_in_central_tiles" }
    : landcoverOk && fertile >= rules.fertile_suitability_min ? { level: "likely", reason: "fertile_land_suitability_candidate" }
    : deposits.status === "available" && deposits.records > 0 ? { level: "unknown", reason: "recorded_deposit_outside_central_tiles" }
    : landcoverOk && (fertile > 0 || crop > 0) ? { level: "unknown", reason: "fertile_cover_below_candidate_threshold" }
    : landcoverOk && deposits.status === "available" ? { level: "unknown", reason: "no_recorded_deposit_or_fertile_cover" }
    : landcoverOk ? { level: "unknown", reason: "deposit_evidence_unavailable" }
    : deposits.status === "available" ? { level: "unknown", reason: "landcover_evidence_unavailable" }
    : { level: "unknown", reason: "no_place_evidence" };
  return {
    evidence,
    resources: { ...resources, evidence },
    trees: { ...trees, evidence },
  };
}

export function checkCapabilities(data, ledger) {
  if (data.schema !== 1 || !["export", "estimate"].includes(data.mode)) throw new Error("Expected capability input schema 1 and export/estimate mode");
  const grid = data.grid;
  if (grid && (!Number.isInteger(grid.size) || grid.size < 2 || !Number.isFinite(grid.spacing_m) || grid.spacing_m <= 0 ||
    grid.depth_m.length !== grid.size ** 2 || Array.from(grid.depth_m).some((d) => !Number.isFinite(d) || d < 0))) throw new Error("Invalid capability grid");
  const result = {};
  for (const key of Object.keys(KINDS)) {
    if (data.planner_enabled?.[key] === false) {
      result[key] = { level: "unknown", reason: "planner_disabled" };
      continue;
    }
    const witness = data.graph != null ? networkAccess(data.graph, key) : null;
    if (key === "ship") {
      const corridor = grid ? shipCorridor(grid.depth_m, grid.size, grid.spacing_m, ledger.model_rules.ship) : null;
      const route = witness?.candidate === true, broad = corridor?.candidate === true;
      const absent = data.mode === "export" && witness?.candidate === false && corridor?.candidate === false;
      result[key] = {
        level: route || broad ? "likely" : absent ? "not_possible_here" : "unknown",
        reason: route ? (broad ? "authored_ship_route" : "authored_ship_route_corridor_unconfirmed")
          : broad ? (witness ? "initial_deep_corridor_no_authored_route" : "initial_deep_corridor")
          : absent ? "no_authored_ship_route_or_initial_deep_corridor"
          : data.mode === "estimate" && grid ? "no_corridor_in_estimate" : "ship_feasibility_not_established",
      };
      if (corridor) result[key].witness = corridor;
      if (witness) result[key].authored_route = witness;
    } else if (witness) {
      result[key] = { level: witness.candidate ? "likely" : "not_possible_here", reason: witness.candidate ? "authored_edge_to_edge_route" : "no_authored_edge_to_edge_route", witness };
    } else {
      const observation = data.transport?.[key];
      result[key] = { level: observation ? "likely" : "unknown", reason: observation ? "mapped_candidate_not_routed" : "transport_not_established" };
    }
  }
  for (const key of ["water", "start", "buildable", "resources", "trees", "water_risk"]) result[key] = { level: "unknown", reason: "not_evaluated" };
  if (data.start_input != null || data.planner_enabled?.start === false) result.start = evaluateStart(data);
  const buildable = data.buildable_fraction;
  if (buildable != null && Number.isFinite(buildable) && buildable >= 0 && buildable <= 1)
    result.buildable = { level: buildable > 0 ? "likely" : data.mode === "export" ? "not_possible_here" : "unknown", reason: "dry_low_slope_samples", fraction: buildable };
  if (data.place != null) {
    if (!grid) throw new Error("Place evidence needs a capability grid");
    if (!ledger.model_rules?.place) throw new Error("Ledger lacks place evidence rules");
    const place = placeCapabilities(grid, data.place, ledger.model_rules.place);
    result.resources = place.resources;
    result.trees = place.trees;
  }
  return qualifyExactExport({ schema: 1, model: ledger.model, mode: data.mode, capabilities: result }, data.export_identity, ledger);
}

export function stockBand(value, metric) {
  if (!metric || !Number.isFinite(value)) return "not_comparable";
  return value < metric.p25 ? "below_p25" : value > metric.p75 ? "above_p75" : "typical";
}

// Stock-map measures, mirrored in tools/map-factory/capabilities.py. Same 1081-node
// grids, 16 m gradient, central 25-tile mask and 0.5 m wet threshold as
// survey/measure_maps.py, so a prepared export scores inside the same definitions.
export const STOCK_MEASURES = {
  terrain_relief_m: {
    label: "Terrain relief",
    definition: "highest minus lowest terrain over all 1081 x 1081 nodes, in metres",
  },
  median_land_slope_percent: {
    label: "Central land slope",
    definition: "median terrain gradient at 16 m spacing over the central 25 tiles' dry samples, in percent",
  },
  wet_central_fraction: {
    label: "Central wet share",
    definition: "share of the central 25 tiles whose water depth is above 0.5 m",
  },
};
const STOCK_GRID = 1081, STOCK_RESOURCE = 512, STOCK_CELL_M = 33.75, STOCK_SPACING_M = 16;
const STOCK_CENTRAL = Array.from({ length: STOCK_RESOURCE }, (_, i) => {
  const tile = Math.min(8, Math.floor((i * 9) / STOCK_RESOURCE));
  return tile >= 2 && tile <= 6;
});
const STOCK_NODE = Array.from({ length: STOCK_RESOURCE }, (_, i) =>
  Math.min(STOCK_GRID - 1, Math.max(0, Math.floor(((i - 256 + 0.5) * STOCK_CELL_M + 8640) / STOCK_SPACING_M + 0.5))));
// Python's round() on the exact decimal value of the double, ties to even, so the
// two cores print the same number at a dyadic tie (e.g. 6.25 -> 6.2, not 6.3).
function round(value, places) {
  if (!Number.isFinite(value)) return value;
  const negative = value < 0, digits = Math.abs(value).toFixed(20).replace(".", "").split("");
  const keep = String(Math.floor(Math.abs(value))).length + places;
  let head = Number(digits.slice(0, keep).join("")) || 0;
  const rest = digits.slice(keep), first = Number(rest[0] ?? "0");
  if (first > 5 || (first === 5 && (/[1-9]/.test(rest.slice(1).join("")) || head % 2 === 1))) head++;
  return (negative ? -head : head) / 10 ** places;
}

/** The three stock measures on 1081-square terrain/water metre grids in the game's south-first row order. */
export function measureStockMetrics(ground, depth) {
  if (ground?.length !== STOCK_GRID ** 2 || depth?.length !== STOCK_GRID ** 2)
    throw new Error("Stock measures need 1081-square terrain and water grids");
  let low = Infinity, high = -Infinity;
  for (let i = 0; i < ground.length; i++) { const h = ground[i]; if (h < low) low = h; if (h > high) high = h; }
  const slopes = [];
  let wet = 0, central = 0;
  for (let r = 0; r < STOCK_RESOURCE; r++) {
    if (!STOCK_CENTRAL[r]) continue;
    const row = STOCK_NODE[r] * STOCK_GRID;
    for (let c = 0; c < STOCK_RESOURCE; c++) {
      if (!STOCK_CENTRAL[c]) continue;
      const i = row + STOCK_NODE[c];
      central++;
      if (depth[i] > 0.5) { wet++; continue; }
      const dz = (ground[i + STOCK_GRID] - ground[i - STOCK_GRID]) / (2 * STOCK_SPACING_M);
      const dx = (ground[i + 1] - ground[i - 1]) / (2 * STOCK_SPACING_M);
      slopes.push(Math.hypot(dx, dz) * 100);
    }
  }
  slopes.sort((a, b) => a - b);
  const middle = slopes.length >> 1;
  const median = !slopes.length ? null
    : slopes.length % 2 ? slopes[middle] : (slopes[middle - 1] + slopes[middle]) / 2;
  return {
    terrain_relief_m: Number.isFinite(high - low) ? round(high - low, 1) : null,
    wet_central_fraction: central ? round(wet / central, 4) : null,
    median_land_slope_percent: median == null ? null : round(median, 1),
  };
}

/**
 * Values plus the stock reference they are read against. A measure the caller marks
 * not comparable keeps its definition but carries no value or band: absent at this
 * input fidelity is not silent zero.
 */
export function stockComparison(values, reference, comparability = {}) {
  const metrics = reference?.metrics ?? {};
  return Object.fromEntries(Object.entries(STOCK_MEASURES).map(([id, measure]) => {
    const metric = metrics[id], comparable = comparability[id]?.comparable !== false;
    const value = comparable && Number.isFinite(values?.[id]) ? values[id] : null;
    return [id, {
      value, comparable, definition: measure.definition, label: measure.label,
      unit: metric?.unit ?? null, p25: metric?.p25 ?? null, median: metric?.median ?? null, p75: metric?.p75 ?? null,
      band: stockBand(value, metric),
    }];
  }));
}

/** Rounded like Python's round(), for mirrored values and MRDS coordinates. */
export { round as roundTo };

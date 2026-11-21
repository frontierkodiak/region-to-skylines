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
  const buildable = data.buildable_fraction;
  if (buildable != null && Number.isFinite(buildable) && buildable >= 0 && buildable <= 1)
    result.buildable = { level: buildable > 0 ? "likely" : data.mode === "export" ? "not_possible_here" : "unknown", reason: "dry_low_slope_samples", fraction: buildable };
  return qualifyExactExport({ schema: 1, model: ledger.model, mode: data.mode, capabilities: result }, data.export_identity, ledger);
}

export function stockBand(value, metric) {
  if (!metric || !Number.isFinite(value)) return "not_comparable";
  return value < metric.p25 ? "below_p25" : value > metric.p75 ? "above_p75" : "typical";
}

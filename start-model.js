// Active Start-only port of PL1078 9a4aad7. No native labels or place identity.
export const START_MODEL = "pl1210-start-port-v1";
export const START_PARAMETERS = Object.freeze({
  footprint_half_m: 192,
  center_step_m: 64,
  max_depth_m: 0.1,
  max_slope: 0.15,
  max_relief_m: 8,
  min_segment_m: 40,
  max_hookup_m: 512,
  road_clearance_m: 24,
});
const N = 1081,
  S = 16,
  H = 8640;
const road = (e) => ["highway", "ramp"].includes(e.kind);
const xz = (v) => [v[0], v[2]],
  add = (a, b) => a.map((v, i) => v + b[i]),
  sub = (a, b) => a.map((v, i) => v - b[i]);
const scale = (a, v) => a.map((x) => x * v),
  norm = (a) => Math.sqrt(a.reduce((sum, v) => sum + v * v, 0));
const distance = (a, b) => norm(sub(a, b));
const tileOf = ([x, , z]) => {
  const tx = Math.floor(x / 1920 + 2.5),
    tz = Math.floor(z / 1920 + 2.5);
  return tx >= 0 &&
    tx < 5 &&
    tz >= 0 &&
    tz < 5 &&
    Math.abs(x - (tx - 2) * 1920) < 900 &&
    Math.abs(z - (tz - 2) * 1920) < 900
    ? tz * 5 + tx
    : null;
};
function access(graph) {
  const f = graph.nodes.map(() => []),
    r = graph.nodes.map(() => []);
  for (const e of graph.edges)
    if (road(e)) {
      f[e.a].push(e.b);
      r[e.b].push(e.a);
    }
  const ids = graph.nodes.map((_, i) => i),
    incoming = ids.filter((i) => graph.nodes[i].outside && f[i].length),
    outgoing = ids.filter((i) => graph.nodes[i].outside && r[i].length);
  const reach = (seeds, links) => {
    const seen = new Set(seeds),
      queue = [...seeds];
    for (let i = 0; i < queue.length; i++)
      for (const j of links[queue[i]])
        if (!seen.has(j)) {
          seen.add(j);
          queue.push(j);
        }
    return seen;
  };
  const from = reach(incoming, f),
    to = reach(outgoing, r);
  return {
    incoming,
    outgoing,
    arrive: ids.filter(
      (i) =>
        !graph.nodes[i].outside &&
        r[i].length === 1 &&
        !f[i].length &&
        from.has(i),
    ),
    leave: ids.filter(
      (i) =>
        !graph.nodes[i].outside &&
        f[i].length === 1 &&
        !r[i].length &&
        to.has(i),
    ),
  };
}
function sample(grid, [x, z], northFirst = false) {
  const c = Math.max(0, Math.min(N - 1, (x + H) / S)),
    r = Math.max(0, Math.min(N - 1, ((northFirst ? -z : z) + H) / S));
  const i = Math.floor(r),
    j = Math.floor(c),
    y = r - i,
    t = c - j;
  return (
    grid[i * N + j] * (1 - y) * (1 - t) +
    grid[i * N + Math.min(j + 1, N - 1)] * (1 - y) * t +
    grid[Math.min(i + 1, N - 1) * N + j] * y * (1 - t) +
    grid[Math.min(i + 1, N - 1) * N + Math.min(j + 1, N - 1)] * y * t
  );
}
const position = (g, p) => [p[0], sample(g, p), p[1]];
function curve(graph, e) {
  const a = xz(graph.nodes[e.a].xyz),
    b = xz(graph.nodes[e.b].xyz),
    length = distance(a, b),
    count = Math.max(2, Math.trunc(length / 4) + 1);
  const c =
      e.start_dir && e.end_dir
        ? add(a, scale(xz(e.start_dir), length / 3))
        : null,
    d = c && add(b, scale(xz(e.end_dir), length / 3));
  return Array.from({ length: count }, (_, i) => {
    const t = i / (count - 1),
      u = 1 - t;
    return a.map((v, k) =>
      c
        ? v * u ** 3 +
          3 * c[k] * u ** 2 * t +
          3 * d[k] * u * t ** 2 +
          b[k] * t ** 3
        : v * u + b[k] * t,
    );
  });
}
function heading(graph, hook) {
  const e = graph.edges.find((e) => road(e) && [e.a, e.b].includes(hook)),
    dir = e.a === hook ? e.start_dir : e.end_dir;
  if (dir) return scale(xz(dir), -1);
  const delta = sub(
    xz(graph.nodes[hook].xyz),
    xz(graph.nodes[e.a === hook ? e.b : e.a].xyz),
  );
  return scale(delta, 1 / Math.max(norm(delta), 1e-9));
}
function clearance(a, b, corridor) {
  a = xz(a);
  b = xz(b);
  const count = Math.max(2, Math.trunc(distance(a, b) / 4) + 1);
  let min = Infinity;
  for (let i = 0; i < count; i++) {
    const t = i / (count - 1),
      p = add(scale(a, 1 - t), scale(b, t));
    for (const c of corridor) min = Math.min(min, distance(p, c));
  }
  return min;
}
function segment(g, d, a, b, p) {
  const length = distance(xz(a), xz(b));
  if (
    length < p.min_segment_m ||
    length > p.max_hookup_m ||
    Math.abs(b[1] - a[1]) / length > p.max_slope
  )
    return false;
  const count = Math.max(2, Math.ceil(length / 8) + 1);
  for (let i = 0; i < count; i++)
    if (
      sample(
        d,
        add(scale(xz(a), 1 - i / (count - 1)), scale(xz(b), i / (count - 1))),
      ) > p.max_depth_m
    )
      return false;
  return true;
}
// Separable sliding extrema keep the full 16 m predicate O(n), not O(n*width²).
function extrema(grid, n, radius, maximum) {
  let src = grid;
  for (const vertical of [false, true]) {
    const dst = new Float64Array(n * n);
    for (let line = 0; line < n; line++) {
      const queue = new Int32Array(n);
      let head = 0,
        tail = 0,
        right = -1;
      const at = (i) => (vertical ? i * n + line : line * n + i);
      for (let i = 0; i < n; i++) {
        while (right < Math.min(n - 1, i + radius)) {
          right++;
          const v = src[at(right)];
          while (
            tail > head &&
            (maximum
              ? src[at(queue[tail - 1])] <= v
              : src[at(queue[tail - 1])] >= v)
          )
            tail--;
          queue[tail++] = right;
        }
        while (head < tail && queue[head] < i - radius) head++;
        dst[at(i)] = src[at(queue[head])];
      }
    }
    src = dst;
  }
  return src;
}
// northFirst changes coordinate reporting only; the gradient magnitude is invariant.
export function footprintCenters(
  ground,
  depth,
  {
    n = N,
    spacing = S,
    half = H,
    northFirst = false,
    tile = 12,
    obstacles = null,
    params = START_PARAMETERS,
  } = {},
) {
  const unknown = {
    status: "unknown",
    reason: "incomplete_or_coarse_footprint_grid",
    centers: [],
  };
  if (
    !Number.isInteger(n) ||
    n < 2 ||
    spacing > S ||
    spacing <= 0 ||
    ground?.length !== n * n ||
    depth?.length !== n * n
  )
    return unknown;
  const dry = new Float64Array(n * n);
  for (let r = 0; r < n; r++)
    for (let c = 0; c < n; c++) {
      const i = r * n + c;
      if (
        !Number.isFinite(ground[i]) ||
        !Number.isFinite(depth[i]) ||
        depth[i] < 0
      )
        return unknown;
      const dx =
        (ground[r * n + Math.min(c + 1, n - 1)] -
          ground[r * n + Math.max(0, c - 1)]) /
        (spacing * (c === 0 || c === n - 1 ? 1 : 2));
      const dz =
        (ground[Math.min(r + 1, n - 1) * n + c] -
          ground[Math.max(0, r - 1) * n + c]) /
        (spacing * (r === 0 || r === n - 1 ? 1 : 2));
      dry[i] =
        depth[i] <= params.max_depth_m && Math.hypot(dx, dz) <= params.max_slope
          ? 1
          : 0;
    }
  const radius = Math.ceil(params.footprint_half_m / spacing),
    clear = extrema(dry, n, radius, false),
    low = extrema(ground, n, radius, false),
    high = extrema(ground, n, radius, true);
  const obstruction =
    obstacles &&
    extrema(
      obstacles,
      n,
      radius + Math.ceil(params.road_clearance_m / spacing),
      true,
    );
  const margin = 960 - params.footprint_half_m - 32,
    lo = -Math.floor(margin / params.center_step_m) * params.center_step_m,
    centers = [];
  const tx = (tile % 5) - 2,
    tz = Math.floor(tile / 5) - 2;
  for (let oz = lo; oz <= margin; oz += params.center_step_m)
    for (let ox = lo; ox <= margin; ox += params.center_step_m) {
      const x = ox + tx * 1920,
        z = oz + tz * 1920,
        c = Math.round((x + half) / spacing),
        r = Math.round((half + (northFirst ? -z : z)) / spacing),
        i = r * n + c;
      if (
        r - radius < 0 ||
        r + radius >= n ||
        c - radius < 0 ||
        c + radius >= n
      )
        continue;
      if (
        clear[i] &&
        high[i] - low[i] <= params.max_relief_m &&
        !obstruction?.[i]
      )
        centers.push([x, z]);
    }
  return {
    status: centers.length ? "candidate" : "unknown",
    reason: centers.length
      ? "sampled_dry_flat_footprint"
      : "no_footprint_in_finite_search",
    centers,
  };
}
export function liveFootprint(ground, depth, options = {}) {
  const found = footprintCenters(ground, depth, {
    northFirst: true,
    ...options,
  });
  return {
    level: "unknown",
    predicted: null,
    reason: found.reason,
    footprint: found.status,
    hookup: "unknown",
    center_xz: found.centers[0] ?? null,
    candidates: found.centers.length,
    footprint_m: [384, 384],
    search: "central_1920m_square_64m_centers",
    fidelity: "capture_16m_initial_depth_estimate",
    model: START_MODEL,
    stock_comparison: "not_comparable",
    native_agreement: "unscored_capture_approximation",
  };
}
export function evaluateStart(data) {
  const missing = { level: "unknown", predicted: null, hookup: "unknown" };
  if (data.planner_enabled?.start === false)
    return { ...missing, reason: "planner_disabled" };
  const input = data.start_input;
  if (!input) return { ...missing, reason: "missing_complete_start_grids" };
  if (input.fidelity !== "prepared_16m_south_first")
    return { ...missing, reason: "unsupported_start_fidelity" };
  const { terrain_m: g, depth_m: d, tile } = input;
  if (
    g?.length !== N * N ||
    d?.length !== N * N ||
    Array.from(g).some((v) => !Number.isFinite(v)) ||
    Array.from(d).some((v) => !Number.isFinite(v))
  )
    return { ...missing, reason: "missing_complete_start_grids" };
  if (Array.from(d).some((v) => v < 0)) throw new Error("Negative start depth");
  const meta = {
    hookup: "unknown",
    model: START_MODEL,
    fidelity: input.fidelity,
    native_agreement: "unscored_new_runtime",
    stock_comparison: "not_comparable",
  };
  const finish = (v) => ({
    ...v,
    ...meta,
    hookup: v.predicted ? "declared_plan" : "unknown",
  });
  if (!Number.isInteger(tile) || tile < 0 || tile >= 25)
    return finish({
      level: "unknown",
      reason: "missing_start_tile",
      predicted: null,
    });
  const graph = data.graph;
  if (!graph)
    return finish({
      level: "unknown",
      reason: "missing_authored_graph",
      predicted: null,
    });
  const a = access(graph),
    arrivals = a.arrive.filter((i) => tileOf(graph.nodes[i].xyz) === tile),
    departures = a.leave.filter((i) => tileOf(graph.nodes[i].xyz) === tile);
  const scope =
    "Current authored directed graph and current start tile only; not all possible generators";
  if (!a.incoming.length || !a.outgoing.length)
    return finish({
      level: "not_possible_here",
      reason: "missing_authored_outside_road_direction",
      predicted: false,
      scope,
      witness: null,
    });
  if (!arrivals.length || !departures.length)
    return finish({
      level: "unknown",
      reason: "no_supported_two_stub_witness",
      predicted: null,
      scope,
      witness: null,
    });
  const mask = new Float64Array(N * N);
  for (const e of graph.edges)
    if (!["air", "ship"].includes(e.kind))
      for (const [x, z] of curve(graph, e)) {
        const c = Math.max(0, Math.min(N - 1, Math.floor((x + H) / S + 0.5))),
          r = Math.max(0, Math.min(N - 1, Math.floor((z + H) / S + 0.5)));
        mask[r * N + c] = 1;
      }
  const centers = footprintCenters(g, d, { tile, obstacles: mask }).centers;
  const pairs = arrivals
    .flatMap((i) =>
      departures.map((j) => [
        distance(xz(graph.nodes[i].xyz), xz(graph.nodes[j].xyz)),
        i,
        j,
      ]),
    )
    .sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2]);
  const p = START_PARAMETERS;
  for (const [gap, arrival, departure] of pairs) {
    if (gap > 400) continue;
    let hooks = [arrival, departure],
      xyz = hooks.map((i) => graph.nodes[i].xyz);
    const h = add(heading(graph, arrival), heading(graph, departure));
    if (norm(h) < 0.1) continue;
    const mean = scale(add(...xyz), 0.5);
    let approach = Math.max(12, Math.min(96, gap * 0.75)),
      joinXZ;
    while (true) {
      joinXZ = add(xz(mean), scale(h, approach / norm(h)));
      if (
        Math.min(...xyz.map((v) => distance(xz(v), joinXZ))) >=
          p.min_segment_m ||
        approach >= 160
      )
        break;
      approach += 8;
    }
    const join = position(g, joinXZ),
      elevation = Math.max(0, mean[1] - join[1]);
    join[1] += elevation;
    if (tileOf(join) !== tile || !xyz.every((v) => segment(g, d, v, join, p)))
      continue;
    const corridor = graph.edges
      .filter(
        (e) =>
          !["air", "ship"].includes(e.kind) &&
          !hooks.some((i) => [e.a, e.b].includes(i)),
      )
      .map((e) => curve(graph, e))
      .filter(
        (c) =>
          Math.min(...c.map((v) => distance(v, joinXZ))) < p.max_hookup_m + 400,
      )
      .flat();
    if (
      corridor.length &&
      xyz.some((v) => clearance(v, join, corridor) < p.road_clearance_m)
    )
      continue;
    const first = (hook) => {
      const other = hooks.find((v) => v !== hook),
        e = graph.edges.find((e) => road(e) && [e.a, e.b].includes(other));
      return clearance(graph.nodes[hook].xyz, join, curve(graph, e));
    };
    const ranks = new Map(hooks.map((i) => [i, first(i)]));
    hooks.sort((i, j) => ranks.get(j) - ranks.get(i) || i - j);
    xyz = hooks.map((i) => graph.nodes[i].xyz);
    for (const center of [...centers].sort(
      (a, b) =>
        distance(a, joinXZ) - distance(b, joinXZ) || a[0] - b[0] || a[1] - b[1],
    )) {
      const corner = position(g, [
        center[0] + (join[0] < center[0] ? -144 : 144),
        center[1] + (join[2] < center[1] ? -144 : 144),
      ]);
      if (
        !segment(g, d, join, corner, p) ||
        (corridor.length &&
          clearance(join, corner, corridor) < p.road_clearance_m)
      )
        continue;
      const points = {},
        steps = [],
        bindings = {};
      for (let z = 0; z < 4; z++)
        for (let x = 0; x < 4; x++)
          points[`g${x}${z}`] = position(g, [
            center[0] - 144 + x * 96,
            center[1] - 144 + z * 96,
          ]);
      for (let z = 0; z < 4; z++)
        for (let x = 0; x < 3; x++)
          steps.push({
            from: `g${x}${z}`,
            to: `g${x + 1}${z}`,
            prefab: "Basic Road",
          });
      for (let x = 0; x < 4; x++)
        for (let z = 0; z < 3; z++)
          steps.push({
            from: `g${x}${z}`,
            to: `g${x}${z + 1}`,
            prefab: "Basic Road",
          });
      points.join = join;
      hooks.forEach((hook, i) => {
        const key = `hook${i}`;
        points[key] = xyz[i];
        bindings[key] = {
          graph_node: hook,
          position: points[key],
          segments: 1,
        };
        steps.push({
          from: key,
          to: "join",
          prefab: "Basic Road",
          end_elevation: i === 0 ? elevation : 0,
        });
      });
      steps.push({
        from: "join",
        to: `g${join[0] < center[0] ? 0 : 3}${join[2] < center[1] ? 0 : 3}`,
        prefab: "Basic Road",
      });
      const witness = {
        schema: 1,
        start_tile: tile,
        center_xz: center,
        footprint_half_m: p.footprint_half_m,
        points,
        bindings,
        steps,
        outside_graph_anchors: { incoming: a.incoming, outgoing: a.outgoing },
        scope:
          "Fixed 4x4 road grid, then clearance-ranked two-stub shared junction; no grading or bridge fallback",
        ordering_basis:
          "Maximum sampled clearance from the other authored ramp corridor, then graph index; never native retries",
      };
      return finish({
        level: "likely",
        reason: "dry_footprint_and_directed_hookup_plan",
        predicted: true,
        scope,
        witness,
        subchecks: {
          dry_footprint: true,
          directed_outside_graph: true,
          native_placement: null,
          native_outside_path: null,
        },
        limits: [
          "16m footprint samples and 8m hookup water samples; between-sample terrain/collisions unresolved",
          "Provisional length/slope/clearance limits, not recovered game constants",
          "Cubic corridor uses authored tangents and one-third-chord control length; native curve/width/pillars can disagree",
        ],
      });
    }
  }
  return finish({
    level: "unknown",
    reason: "no_witness_in_finite_plan_search",
    predicted: null,
    scope,
    dry_footprint_candidates: centers.length,
    witness: null,
  });
}

// Shared native-grid sampling and tile geometry; Start behavior is unchanged.
export { sample, position, tileOf };

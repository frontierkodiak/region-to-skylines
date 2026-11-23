// Geometry rules mirrored in tools/map-factory/connection_rules.py.
export const CONNECTION_RULES = { ship_width_m: 256, margin_m: 64, edge_margin_m: 32, edge_separation_m: 512 };

function crosses(a, b, h) {
  let lo = 0, hi = 1;
  for (let axis = 0; axis < 2; axis++) {
    const d = b[axis] - a[axis];
    if (!d) { if (Math.abs(a[axis]) > h) return false; continue; }
    const t0 = (-h - a[axis]) / d, t1 = (h - a[axis]) / d;
    lo = Math.max(lo, Math.min(t0, t1)); hi = Math.min(hi, Math.max(t0, t1));
  }
  if (hi - lo < 1e-10) return false;
  const inside = (p) => Math.max(Math.abs(p[0]), Math.abs(p[1])) < h - 1e-8;
  const t = (lo + hi) / 2;
  if (!inside([a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])])) return false;
  return lo > 0 || hi < 1 || (inside(a) !== inside(b));
}

export function edgeConnection(lines, kind, half, margin) {
  let gap = Infinity, eligible = 0;
  for (const line of lines) {
    const rail = line.class === "rail" && !["subway", "light_rail", "tram", "monorail"].includes(line.subclass) &&
      !["yard", "siding", "spur"].includes(line.service);
    if (!(kind === "road" ? ["motorway", "trunk"].includes(line.class) : rail)) continue;
    eligible++;
    for (let i = 1; i < line.pts.length; i++) if (crosses(line.pts[i - 1], line.pts[i], half))
      return { level: "yes", reason: "mapped_edge_crossing", crossings: 1, edge_gap_m: 0 };
    for (const [x, z] of line.pts) {
      if (Math.abs(x) <= half && Math.abs(z) <= half) gap = Math.min(gap, half - Math.max(Math.abs(x), Math.abs(z)));
    }
  }
  return { level: gap <= margin ? "maybe" : "no", reason: gap <= margin ? "near_map_edge" : "no_mapped_edge_crossing",
    crossings: 0, edge_gap_m: Number.isFinite(gap) ? Math.round(gap * 100) / 100 : null, eligible_lines: eligible };
}

/** Widest connected mapped-water corridor, at the same lattice as stock water. */
export function waterWidth(grid, separation = 512) {
  const { size: n, spacing_m: sp, water, sea = [] } = grid, count = n * n;
  if (!Number.isInteger(n) || n < 2 || !(sp > 0) || water.length !== count) throw new Error("Invalid mapped-water grid");
  const distance = new Int32Array(count).fill(n), queue = new Int32Array(count);
  let tail = 0;
  for (let i = 0; i < count; i++) if (!water[i]) { distance[i] = 0; queue[tail++] = i; }
  for (let q = 0; q < tail; q++) {
    const i = queue[q], r = Math.floor(i / n), c = i % n;
    for (let y = Math.max(0, r - 1); y <= Math.min(n - 1, r + 1); y++) for (let x = Math.max(0, c - 1); x <= Math.min(n - 1, c + 1); x++) {
      const j = y * n + x;
      if (distance[j] > distance[i] + 1) { distance[j] = distance[i] + 1; queue[tail++] = j; }
    }
  }
  const order = Array.from({ length: count }, (_, i) => i).filter((i) => water[i]).sort((a, b) => distance[b] - distance[a] || a - b);
  const parent = new Int32Array(count).fill(-1), minX = new Int32Array(count).fill(n), maxX = new Int32Array(count).fill(-1),
    minY = new Int32Array(count).fill(n), maxY = new Int32Array(count).fill(-1), ocean = new Uint8Array(count);
  const find = (i) => { while (parent[i] !== i) { parent[i] = parent[parent[i]]; i = parent[i]; } return i; };
  for (const i of order) {
    const r = Math.floor(i / n), c = i % n;
    parent[i] = i; ocean[i] = sea[i] ? 1 : 0;
    if (r === 0 || c === 0 || r === n - 1 || c === n - 1) { minX[i] = maxX[i] = c; minY[i] = maxY[i] = r; }
    for (const j of [r ? i - n : -1, r < n - 1 ? i + n : -1, c ? i - 1 : -1, c < n - 1 ? i + 1 : -1]) {
      if (j < 0 || parent[j] < 0) continue;
      const a = find(i), b = find(j); if (a === b) continue;
      parent[b] = a; minX[a] = Math.min(minX[a], minX[b]); maxX[a] = Math.max(maxX[a], maxX[b]);
      minY[a] = Math.min(minY[a], minY[b]); maxY[a] = Math.max(maxY[a], maxY[b]); ocean[a] ||= ocean[b];
    }
    const root = find(i), span = Math.max(maxX[root] - minX[root], maxY[root] - minY[root]) * sp;
    if (span >= separation || (ocean[root] && maxX[root] >= 0)) return Math.max(0, 2 * distance[i] - 1) * sp;
  }
  return 0;
}

export function connectionRules(input, rules = CONNECTION_RULES) {
  const road = edgeConnection(input.roads, "road", input.extent_m / 2, rules.edge_margin_m);
  const rail = edgeConnection(input.roads, "rail", input.extent_m / 2, rules.edge_margin_m);
  const width = waterWidth(input.water_grid, rules.edge_separation_m), delta = width - rules.ship_width_m;
  return { road, rail,
    ship: { level: width === 0 || delta <= -rules.margin_m ? "no" : delta >= rules.margin_m ? "yes" : "maybe",
      reason: width === 0 ? "no_edge_waterway" : "mapped_water_width", width_m: width, threshold_m: rules.ship_width_m, margin_m: rules.margin_m },
    air: { level: "yes", reason: "air_paths_stock_default" } };
}

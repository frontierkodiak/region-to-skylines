// A pure, evidence-only vegetation expectation. Coordinates and areas are real
// metres; no biome, latitude, tree-count or genus-to-evergreen prior is applied.
import { gameXZ } from "./capability-evidence.js";

const SIDE_M = 17280;
const RADIUS_M = 2000;
const NEIGHBORS = 24;
const INVENTORY_POOL_M = 25000;
const FORMS = [
  "needleleaf_evergreen", "broadleaf_deciduous", "broadleaf_evergreen",
  "palm", "shrub", "grass", "unknown",
];
const CLASSES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100];
const HEIGHT_EDGES = [2, 5, 10, 15, 20, 30, 40, 60];
const ratio = (a, b) => b > 0 ? a / b : null;
const sourceKey = (source) => typeof source === "string" ? source : "unknown";
const compareText = (a, b) => a < b ? -1 : a > b ? 1 : 0;

function squareInput(square) {
  const { lon, lat, rotation = 0, scale = 1 } = square ?? {};
  if (![lon, lat, rotation, scale].every(Number.isFinite) ||
      Math.abs(lon) > 180 || Math.abs(lat) >= 90 || scale <= 0) {
    throw new TypeError("A finite WGS84 square with positive scale is required");
  }
  return { lon, lat, rotation, scale };
}

function heightStats(values) {
  const bins = HEIGHT_EDGES.map((min, i) => ({
    min_m: min, max_m: HEIGHT_EDGES[i + 1] ?? null, area_m2: 0,
  }));
  const order = Array.from({ length: values.length / 2 }, (_, i) => i * 2);
  order.sort((a, b) => values[a] - values[b]);
  let area = 0;
  for (const i of order) {
    area += values[i + 1];
    let bin = HEIGHT_EDGES.length - 1;
    while (values[i] < HEIGHT_EDGES[bin]) bin--;
    bins[bin].area_m2 += values[i + 1];
  }
  const quantile = (p) => {
    if (!area) return null;
    let cumulative = 0;
    for (const i of order) {
      cumulative += values[i + 1];
      if (cumulative >= p * area) return values[i];
    }
    return values[order.at(-1)];
  };
  return {
    p10: quantile(0.1), p50: quantile(0.5), p90: quantile(0.9),
    max: order.length ? values[order.at(-1)] : null,
    histogram: bins.map((bin) => ({ ...bin, share: ratio(bin.area_m2, area) })),
  };
}

function structureCell() {
  return {
    samples: 0, valid: 0, canopy: 0, validArea: 0, canopyArea: 0,
    landValid: 0, landArea: 0, classes: new Map(), heights: [],
  };
}

// Raster pixels are equal-area footprints, not points. Intersections preserve
// valid areas even when the source grid and requested cell grid do not align.
function aggregateStructure(structure, width, size, cellM) {
  const cells = Array.from({ length: size * size }, structureCell);
  const sourceSize = structure?.size;
  const summary = structureCell();
  if (!Number.isInteger(sourceSize) || sourceSize <= 0) return { cells, summary };
  const pixel = width / sourceSize;
  for (let r = 0; r < sourceSize; r++) {
    const top = r * pixel, bottom = (r + 1) * pixel;
    const firstRow = Math.min(size - 1, Math.floor(top / cellM));
    const lastRow = Math.min(size - 1, Math.ceil(bottom / cellM) - 1);
    for (let c = 0; c < sourceSize; c++) {
      const left = c * pixel, right = (c + 1) * pixel;
      const firstCol = Math.min(size - 1, Math.floor(left / cellM));
      const lastCol = Math.min(size - 1, Math.ceil(right / cellM) - 1);
      const index = r * sourceSize + c;
      const height = structure.heights?.[index];
      const valid = typeof height === "number" && Number.isFinite(height) && height >= 0;
      const canopy = valid && height >= 2;
      const land = structure.landcover?.[index];
      const landValid = CLASSES.includes(land);
      addStructure(summary, pixel * pixel, height, valid, canopy, land, landValid);
      for (let row = firstRow; row <= lastRow; row++) {
        const dy = Math.min(bottom, (row + 1) * cellM) - Math.max(top, row * cellM);
        for (let col = firstCol; col <= lastCol; col++) {
          const dx = Math.min(right, (col + 1) * cellM) - Math.max(left, col * cellM);
          if (dx > 0 && dy > 0) {
            addStructure(cells[row * size + col], dx * dy, height, valid, canopy, land, landValid);
          }
        }
      }
    }
  }
  return { cells, summary };
}

function addStructure(cell, area, height, valid, canopy, land, landValid) {
  cell.samples++;
  if (valid) { cell.valid++; cell.validArea += area; }
  if (canopy) {
    cell.canopy++; cell.canopyArea += area;
    cell.heights.push(height, area);
  }
  if (landValid) {
    cell.landValid++; cell.landArea += area;
    cell.classes.set(land, (cell.classes.get(land) ?? 0) + area);
  }
}

function canopyReport(cell, area, structure) {
  return {
    status: cell.validArea > 0 ? "available" : "unknown",
    cover: ratio(cell.canopyArea, cell.validArea),
    canopy_area_m2: cell.validArea > 0 ? cell.canopyArea : null,
    height_m: heightStats(cell.heights),
    coverage: {
      valid_samples: cell.valid, total_samples: cell.samples,
      canopy_samples: cell.canopy, valid_area_m2: cell.validArea,
      fraction: cell.samples ? Math.min(1, cell.validArea / area) : 0,
    },
    evidence: { source: structure?.source ?? null, sample_m: structure?.sample_m ?? null },
    estimand: "area fraction with top-of-canopy height >= 2 m among valid height area",
    height_estimand: "canopy-area top-of-canopy heights, not individual-tree heights",
  };
}

function landcoverReport(cell, area, structure) {
  const share = (code) => ratio(cell.classes.get(code) ?? 0, cell.landArea);
  return {
    status: cell.landArea > 0 ? "available" : "unknown",
    tree_share: share(10), shrub_share: share(20), grass_share: share(30),
    herbaceous_wetland_share: share(90), moss_lichen_share: share(100),
    built_share: share(50),
    classes: Object.fromEntries(CLASSES.map((code) => [code, share(code)])),
    coverage: {
      valid_samples: cell.landValid, total_samples: cell.samples,
      valid_area_m2: cell.landArea,
      fraction: cell.samples ? Math.min(1, cell.landArea / area) : 0,
    },
    evidence: { source: structure?.landcover_source ?? structure?.source ?? null },
    estimand: "WorldCover class area shares among valid land-cover area; not tree counts",
  };
}

function normalizedRecords(square, input) {
  const records = [], counts = { input: input.length, invalid: 0, duplicates: 0 };
  for (const record of input) {
    if (!record || !["inventory", "osm", "occurrence"].includes(record.kind) ||
        !Number.isFinite(record.lon) || !Number.isFinite(record.lat) ||
        Math.abs(record.lon) > 180 || Math.abs(record.lat) >= 90) {
      counts.invalid++;
      continue;
    }
    const [gx, gz] = gameXZ(square, record.lon, record.lat);
    const source = sourceKey(record.source);
    const genus = typeof record.genus === "string" && record.genus.trim()
      ? record.genus.trim() : "unknown";
    const form = FORMS.includes(record.growth_form) ? record.growth_form : "unknown";
    const id = record.id ?? `${record.lon},${record.lat},${genus}`;
    const key = `${record.kind}\u0000${source}\u0000${id}`;
    records.push({
      key, source, genus, form, kind: record.kind,
      x: gx * square.scale, z: gz * square.scale,
      lon: record.lon, lat: record.lat,
    });
  }
  records.sort((a, b) => compareText(a.key, b.key) || a.lon - b.lon ||
    a.lat - b.lat || compareText(a.genus, b.genus) || compareText(a.form, b.form));
  const unique = records.filter((record, i) => {
    const duplicate = i > 0 && record.key === records[i - 1].key;
    if (duplicate) counts.duplicates++;
    return !duplicate;
  });
  return { records: unique, counts: { ...counts, unique: unique.length } };
}

function compareAxis(a, b, axis) {
  return a[axis] - b[axis] || a[axis === "x" ? "z" : "x"] - b[axis === "x" ? "z" : "x"] ||
    compareText(a.key, b.key);
}

// In-place median partition keeps the balanced kd-tree in one record array.
function partitionMedian(points, lo, hi, target, axis) {
  while (lo < hi) {
    const pivot = points[(lo + hi) >> 1];
    let i = lo, j = hi;
    while (i <= j) {
      while (compareAxis(points[i], pivot, axis) < 0) i++;
      while (compareAxis(points[j], pivot, axis) > 0) j--;
      if (i <= j) { [points[i], points[j]] = [points[j], points[i]]; i++; j--; }
    }
    if (target <= j) hi = j;
    else if (target >= i) lo = i;
    else return;
  }
}

function tree(points, lo = 0, hi = points.length - 1, depth = 0) {
  if (lo >= hi) return points;
  const mid = (lo + hi) >> 1, axis = depth % 2 ? "z" : "x";
  partitionMedian(points, lo, hi, mid, axis);
  tree(points, lo, mid - 1, depth + 1);
  tree(points, mid + 1, hi, depth + 1);
  return points;
}

function nearest(points, x, z, radius, limit = NEIGHBORS) {
  const found = [];
  const radius2 = (radius + 1e-6) ** 2;
  const compare = (a, b) => a.distance2 - b.distance2 || compareText(a.record.key, b.record.key);
  const visit = (lo, hi, depth) => {
    if (lo > hi) return;
    const mid = (lo + hi) >> 1, record = points[mid];
    const distance2 = (record.x - x) ** 2 + (record.z - z) ** 2;
    if (distance2 <= radius2) {
      const item = { record, distance2 };
      if (found.length < limit || compare(item, found.at(-1)) < 0) {
        found.push(item);
        if (Number.isFinite(limit)) found.sort(compare);
        if (found.length > limit) found.pop();
      }
    }
    const delta = depth % 2 ? z - record.z : x - record.x;
    if (delta < 0) visit(lo, mid - 1, depth + 1);
    else visit(mid + 1, hi, depth + 1);
    const reach = found.length < limit ? radius2 : found.at(-1).distance2;
    if (delta * delta <= reach) {
      if (delta < 0) visit(mid + 1, hi, depth + 1);
      else visit(lo, mid - 1, depth + 1);
    }
  };
  visit(0, points.length - 1, 0);
  if (!Number.isFinite(limit)) found.sort(compare);
  return found;
}

function compositionShares(found, weighted) {
  const genus = new Map(), forms = Object.fromEntries(FORMS.map((form) => [form, 0]));
  let total = 0;
  for (const { record, distance2 } of found) {
    const weight = weighted ? 1 / (1 + distance2 / 10000) : 1;
    total += weight;
    genus.set(record.genus, (genus.get(record.genus) ?? 0) + weight);
    forms[record.form] += weight;
  }
  return {
    genus: [...genus].map(([name, weight]) => ({ genus: name, share: weight / total }))
      .sort((a, b) => b.share - a.share || compareText(a.genus, b.genus)),
    growth_forms: Object.fromEntries(FORMS.map((form) => [form, ratio(forms[form], total)])),
  };
}

function compositionContext(records) {
  const trees = Object.fromEntries(["inventory", "osm", "occurrence"].map((kind) =>
    [kind, tree(records.filter((record) => record.kind === kind))]));
  const poolRecords = records.filter((record) => record.kind === "inventory" &&
    record.x ** 2 + record.z ** 2 <= INVENTORY_POOL_M ** 2);
  const grouped = new Map();
  for (const record of poolRecords) {
    if (!grouped.has(record.source)) grouped.set(record.source, []);
    grouped.get(record.source).push({ record });
  }
  const pools = new Map([...grouped].map(([source, found]) => {
    const shares = compositionShares(found, false);
    return [source, {
      genus: Object.freeze(shares.genus.map(Object.freeze)),
      growth_forms: Object.freeze(shares.growth_forms), count: found.length,
    }];
  }));
  return { trees, pools, poolTree: tree(poolRecords) };
}

function compositionReport(context, x, z, built) {
  const localRadius = built ? 100 : 250;
  const local = nearest(context.trees.inventory, x, z, localRadius, Infinity);
  const localSource = local[0]?.record.source;
  const sourceLocal = local.filter(({ record }) => record.source === localSource);
  if (sourceLocal.length >= (built ? 3 : 1)) {
    return {
      status: "estimated", kind: "inventory", method: "observed_local_inventory",
      ...compositionShares(sourceLocal, false),
      evidence: {
        record_count: sourceLocal.length, sources: [localSource], radius_m: localRadius,
        nearest_k: null, nearest_m: Math.sqrt(sourceLocal[0].distance2),
        farthest_m: Math.sqrt(sourceLocal.at(-1).distance2), minimum_records: built ? 3 : 1,
      },
      estimand: "count shares of observed inventory records in the stated local window; not unsurveyed forest abundance",
    };
  }
  if (built) {
    const closest = nearest(context.poolTree, x, z, INVENTORY_POOL_M, 1)[0];
    if (closest) {
      const pool = context.pools.get(closest.record.source);
      return {
        status: "estimated", kind: "inventory", method: "city_inventory_source_pool",
        genus: pool.genus, growth_forms: pool.growth_forms,
        evidence: {
          record_count: pool.count, sources: [closest.record.source],
          radius_m: INVENTORY_POOL_M, pool_center_x_m: 0, pool_center_z_m: 0,
          query_radius_m: INVENTORY_POOL_M, nearest_k: null,
          nearest_m: Math.sqrt(closest.distance2), farthest_m: null,
        },
        estimand: "inventory source count shares within 25 km of square centre; regional urban prior, not local interpolation or wild-forest abundance",
      };
    }
  }
  let kind = null, found = [];
  for (const candidate of ["osm", "occurrence"]) {
    found = nearest(context.trees[candidate], x, z, RADIUS_M);
    if (found.length) { kind = candidate; break; }
  }
  return {
    status: found.length ? "estimated" : "unknown", kind,
    method: found.length ? "local_record_proxy" : "unknown",
    ...compositionShares(found, true),
    evidence: {
      record_count: found.length, sources: [...new Set(found.map(({ record }) => record.source))].sort(),
      radius_m: kind ? RADIUS_M : null, nearest_k: NEIGHBORS,
      nearest_m: found.length ? Math.sqrt(found[0].distance2) : null,
      farthest_m: found.length ? Math.sqrt(found.at(-1).distance2) : null,
    },
    estimand: "distance-weighted local record composition proxy; not tree abundance or occurrence density",
  };
}

/**
 * Build once for many real-metre local queries; shares expectation's kernel.
 * urban=true selects the city-inventory prior after fewer than three observed
 * inventory records within 100m. Outside urban cells, inventory needs records
 * within 250m. OSM/occurrence fallback is a bounded evidence proxy, not abundance.
 */
export function compositionSampler(square, records = []) {
  const sq = squareInput(square);
  const normalized = normalizedRecords(sq, records);
  const context = compositionContext(normalized.records);
  return (x, z, { urban = false } = {}) => {
    if (!Number.isFinite(x) || !Number.isFinite(z)) throw new TypeError("Finite real-metre query coordinates are required");
    return compositionReport(context, x, z, urban);
  };
}

/** A single-query convenience; compositionSampler avoids rebuilding the tree. */
export function compositionAt(square, records, x, z, options) {
  return compositionSampler(square, records)(x, z, options);
}

function clipPolygon(polygon, axis, boundary, keepGreater) {
  const output = [];
  for (let i = 0; i < polygon.length; i++) {
    const a = polygon[i], b = polygon[(i + 1) % polygon.length];
    const insideA = keepGreater ? a[axis] >= boundary : a[axis] <= boundary;
    const insideB = keepGreater ? b[axis] >= boundary : b[axis] <= boundary;
    if (insideA) output.push(a);
    if (insideA !== insideB) {
      const t = (boundary - a[axis]) / (b[axis] - a[axis]);
      output.push([a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]);
    }
  }
  return output;
}

function intersectionArea(polygon, x0, z0, x1, z1) {
  let clipped = clipPolygon(polygon, 0, x0, true);
  clipped = clipPolygon(clipped, 0, x1, false);
  clipped = clipPolygon(clipped, 1, z0, true);
  clipped = clipPolygon(clipped, 1, z1, false);
  let twice = 0;
  for (let i = 0; i < clipped.length; i++) {
    const a = clipped[i], b = clipped[(i + 1) % clipped.length];
    twice += a[0] * b[1] - b[0] * a[1];
  }
  return Math.abs(twice) / 2;
}

// Union a source's overlapping surveyed WGS84 rectangles into disjoint slabs.
// This prevents overlapping receipt bounds from doubling the surveyed area.
function surveyRegions(square, surveys) {
  const sources = new Map();
  for (const survey of surveys) {
    const b = survey?.bounds;
    if (survey?.kind !== "inventory" || survey.complete !== true ||
        !Array.isArray(b) || b.length !== 4 || !b.every(Number.isFinite) ||
        !(b[0] < b[2] && b[1] < b[3]) || Math.abs(b[0]) >= 90 ||
        Math.abs(b[2]) >= 90 || Math.abs(b[1]) > 180 || Math.abs(b[3]) > 180) continue;
    const source = sourceKey(survey.source);
    if (!sources.has(source)) sources.set(source, []);
    sources.get(source).push([...b]);
  }
  return [...sources].sort(([a], [b]) => compareText(a, b)).map(([source, bounds]) => {
    const cuts = [...new Set(bounds.flatMap((b) => [b[1], b[3]]))].sort((a, b) => a - b);
    const polygons = [];
    for (let i = 0; i < cuts.length - 1; i++) {
      const west = cuts[i], east = cuts[i + 1], mid = (west + east) / 2;
      const intervals = bounds.filter((b) => b[1] <= mid && b[3] >= mid)
        .map((b) => [b[0], b[2]]).sort((a, b) => a[0] - b[0]);
      const union = [];
      for (const interval of intervals) {
        if (union.length && interval[0] <= union.at(-1)[1]) {
          union.at(-1)[1] = Math.max(union.at(-1)[1], interval[1]);
        } else union.push([...interval]);
      }
      for (const [south, north] of union) {
        polygons.push([[west, south], [east, south], [east, north], [west, north]]
          .map(([lon, lat]) => gameXZ(square, lon, lat).map((v) => v * square.scale)));
      }
    }
    return { source, bounds, polygons };
  });
}

function densityCells(square, regions, records, size, cellM, width) {
  const counts = new Map(regions.map(({ source }) => [source, new Uint32Array(size * size)]));
  for (const record of records) {
    if (record.kind !== "inventory" || !counts.has(record.source) ||
        Math.abs(record.x) > width / 2 + 1e-6 || Math.abs(record.z) > width / 2 + 1e-6) continue;
    const region = regions.find((item) => item.source === record.source);
    if (!region.bounds.some(([s, w, n, e]) => record.lon >= w && record.lon <= e && record.lat >= s && record.lat <= n)) continue;
    const col = Math.max(0, Math.min(size - 1, Math.floor((record.x + width / 2) / cellM)));
    const row = Math.max(0, Math.min(size - 1, Math.floor((width / 2 - record.z) / cellM)));
    counts.get(record.source)[row * size + col]++;
  }
  return Array.from({ length: size * size }, (_, i) => {
    const row = Math.floor(i / size), col = i % size;
    const x0 = col * cellM - width / 2, z1 = width / 2 - row * cellM;
    let area = 0, selected = null;
    for (const region of regions) {
      const covered = region.polygons.reduce((sum, polygon) =>
        sum + intersectionArea(polygon, x0, z1 - cellM, x0 + cellM, z1), 0);
      if (covered > area) { area = covered; selected = region; }
    }
    const count = selected ? counts.get(selected.source)[i] : 0;
    return {
      status: selected ? "available" : "unknown",
      trees_per_ha: area > 0 ? count / area * 10000 : null,
      surveyed_area_m2: area, coverage: Math.min(1, area / (cellM * cellM)),
      evidence: { source: selected?.source ?? null, record_count: selected ? count : null },
      estimand: "inventory records per surveyed hectare, only within explicit complete inventory bounds",
    };
  });
}

function compositionSummary(cells, cellArea, totalArea) {
  const genus = new Map(), forms = Object.fromEntries(FORMS.map((form) => [form, 0]));
  const kinds = { inventory: 0, osm: 0, occurrence: 0 };
  const withHeights = cells.some((cell) =>
    cell.composition.status !== "unknown" && cell.canopy.status === "available");
  let area = 0, evidencedArea = 0, count = 0;
  for (const cell of cells) {
    const composition = cell.composition;
    if (composition.status === "unknown") continue;
    const weight = withHeights
      ? cell.canopy.status === "available" ? cell.canopy.cover * cellArea : 0
      : cellArea;
    if (!weight) continue;
    area += weight;
    evidencedArea += cellArea;
    count++;
    kinds[composition.kind]++;
    for (const entry of composition.genus) {
      genus.set(entry.genus, (genus.get(entry.genus) ?? 0) + entry.share * weight);
    }
    for (const form of FORMS) forms[form] += composition.growth_forms[form] * weight;
  }
  return {
    status: area ? "estimated" : "unknown",
    genus: [...genus].map(([name, weight]) => ({ genus: name, share: weight / area }))
      .sort((a, b) => b.share - a.share || compareText(a.genus, b.genus)),
    growth_forms: Object.fromEntries(FORMS.map((form) => [form, ratio(forms[form], area)])),
    coverage: {
      cells: count, area_m2: evidencedArea, fraction: evidencedArea / totalArea,
      weighted_area_m2: area, cells_by_kind: kinds,
    },
    weight_basis: withHeights ? "estimated_canopy_area" : "cell_area_no_height_evidence",
    estimand: "canopy-area-weighted local record composition over height-covered evidenced cells; cell-area fallback only without height evidence; not regional tree abundance",
  };
}

/**
 * Aggregate a square into real-metre cells. structure.size² pixels cover the
 * entire square, north-first in its rotated local frame; null is missing and
 * height zero is observed non-canopy. Heights are top-of-canopy measurements.
 *
 * Optional surveys: [{kind:"inventory", complete:true, source,
 * bounds:[south,west,north,east]}]. Only matching-source inventory records can
 * contribute density. With overlapping sources the largest surveyed footprint
 * per cell wins; inventory records and areas are never pooled across sources.
 *
 * This function does no I/O and does not mutate its inputs.
 */
export function expectation(square, evidence = {}, { cellSize = 160 } = {}) {
  const sq = squareInput(square);
  if (!Number.isFinite(cellSize) || cellSize < 50 || cellSize > 200) {
    throw new RangeError("Vegetation cellSize must be between 50 and 200 real metres");
  }
  const width = SIDE_M * sq.scale, size = Math.ceil(width / cellSize), cellM = width / size;
  const area = width * width, cellArea = cellM * cellM;
  const structure = evidence.structure ?? {};
  const raster = aggregateStructure(structure, width, size, cellM);
  const normalized = normalizedRecords(sq, evidence.records ?? []);
  const context = compositionContext(normalized.records);
  const regions = surveyRegions(sq, evidence.surveys ?? []);
  const densities = densityCells(sq, regions, normalized.records, size, cellM, width);
  const cells = raster.cells.map((sample, i) => {
    const row = Math.floor(i / size), col = i % size;
    const x = (col + 0.5) * cellM - width / 2, z = width / 2 - (row + 0.5) * cellM;
    const landcover = landcoverReport(sample, cellArea, structure);
    return {
      row, col, x_m: x, z_m: z,
      canopy: canopyReport(sample, cellArea, structure), landcover,
      composition: compositionReport(context, x, z, landcover.built_share >= 0.5),
      density: densities[i],
    };
  });
  const surveyedArea = densities.reduce((sum, cell) => sum + cell.surveyed_area_m2, 0);
  const inventoryCount = densities.reduce((sum, cell) => sum + (cell.evidence.record_count ?? 0), 0);
  return {
    schema: "polli.vegetation/1", square: sq,
    grid: { size, cell_m: cellM, side_m: width, frame: "rotated local square; real metres; rows north-first, x east, z north" },
    cells,
    summary: {
      canopy: canopyReport(raster.summary, area, structure),
      landcover: landcoverReport(raster.summary, area, structure),
      composition: compositionSummary(cells, cellArea, area),
      density: {
        status: surveyedArea ? "available" : "unknown",
        trees_per_ha: surveyedArea ? inventoryCount / surveyedArea * 10000 : null,
        surveyed_area_m2: surveyedArea, coverage: Math.min(1, surveyedArea / area),
        evidence: { record_count: surveyedArea ? inventoryCount : null, sources: regions.map(({ source }) => source) },
        estimand: "inventory records per surveyed hectare over selected complete surveyed cell footprints",
      },
    },
    counts: normalized.counts,
    sources: structuredClone(evidence.sources ?? []),
    limitations: [
      "Canopy heights describe canopy area, not individual-tree heights or tree counts.",
      "Genus and growth-form shares describe local evidence composition, not abundance; occurrence absence is not zero trees.",
      "Unknown growth forms remain unknown; genus and latitude do not assign evergreen or deciduous traits.",
      "WorldCover shrub, grass, herbaceous wetland and moss/lichen classes are not converted to tree density.",
    ],
  };
}

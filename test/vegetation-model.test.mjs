import { test } from "node:test";
import assert from "node:assert/strict";
import { expectation, compositionAt, compositionSampler } from "../vegetation-model.js";

const square = (side = 320, extra = {}) => ({
  lon: -82.55, lat: 35.6, rotation: 0, scale: side / 17280, ...extra,
});
const close = (actual, expected, tolerance = 1e-9) =>
  assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} != ${expected}`);

function lonLat(sq, x, z) {
  const rad = Math.PI / 180, a = 6378137, e2 = 0.00669437999014;
  const w = 1 - e2 * Math.sin(sq.lat * rad) ** 2;
  const m = a * (1 - e2) / w ** 1.5;
  const nc = a / Math.sqrt(w) * Math.cos(sq.lat * rad);
  const theta = sq.rotation * rad;
  return {
    lon: sq.lon + (x * Math.cos(theta) + z * Math.sin(theta)) / nc / rad,
    lat: sq.lat + (-x * Math.sin(theta) + z * Math.cos(theta)) / m / rad,
  };
}

function record(sq, id, x, z, genus = "Quercus", extra = {}) {
  return { id, ...lonLat(sq, x, z), genus, source: "city", kind: "inventory", ...extra };
}

function bounds(sq, x0, z0, x1, z1) {
  const corners = [lonLat(sq, x0, z0), lonLat(sq, x0, z1),
    lonLat(sq, x1, z0), lonLat(sq, x1, z1)];
  return [Math.min(...corners.map((p) => p.lat)), Math.min(...corners.map((p) => p.lon)),
    Math.max(...corners.map((p) => p.lat)), Math.max(...corners.map((p) => p.lon))];
}

test("canopy-area heights, valid zero and missing data are distinct", () => {
  const report = expectation(square(), {
    structure: { size: 2, heights: [null, 0, 2, 20], landcover: [20, 30, 90, 100], source: "analytic" },
  });
  assert.equal(report.schema, "polli.vegetation/1");
  assert.equal(report.grid.size, 2);
  assert.equal(report.grid.cell_m, 160);
  assert.equal(report.cells[0].canopy.cover, null);
  assert.equal(report.cells[0].canopy.status, "unknown");
  assert.equal(report.cells[1].canopy.cover, 0);
  assert.equal(report.cells[1].canopy.height_m.p50, null);
  assert.equal(report.cells[2].canopy.cover, 1, "2m is included in canopy");
  close(report.summary.canopy.cover, 2 / 3);
  close(report.summary.canopy.coverage.fraction, 0.75);
  assert.equal(report.summary.canopy.coverage.valid_samples, 3);
  assert.equal(report.summary.canopy.height_m.p50, 2);
  assert.equal(report.summary.canopy.height_m.p90, 20);
  assert.match(report.summary.canopy.height_estimand, /not individual-tree/);
  for (const field of ["shrub_share", "grass_share", "herbaceous_wetland_share", "moss_lichen_share"]) {
    close(report.summary.landcover[field], 0.25);
  }
  assert.equal(report.cells[2].landcover.grass_share, 0, "wetland is not grass");
  assert.equal(report.cells[3].landcover.grass_share, 0, "moss/lichen is not grass");
  assert.equal(report.summary.density.trees_per_ha, null);
});

test("pixel footprint intersections preserve area across nonaligned cell grids", () => {
  const report = expectation(square(300), {
    structure: { size: 2, heights: [10, 0, 10, 0], landcover: [10, 0, 10, 0] },
  }, { cellSize: 100 });
  assert.equal(report.grid.size, 3);
  close(report.cells[1].canopy.cover, 0.5);
  close(report.cells[1].canopy.coverage.fraction, 1);
  close(report.cells[1].landcover.coverage.fraction, 0.5);
  close(report.cells[1].landcover.tree_share, 1);
  close(report.summary.canopy.cover, 0.5);
  close(report.summary.landcover.coverage.fraction, 0.5);
  close(report.cells.reduce((sum, cell) => sum + cell.canopy.canopy_area_m2, 0), 45000);
});

test("negative, nonfinite and absent heights are unavailable, not zero", () => {
  const report = expectation(square(), {
    structure: { size: 2, heights: [-1, NaN, Infinity, undefined], landcover: [0, null, -1, 999] },
    records: [],
  });
  assert.equal(report.summary.canopy.cover, null);
  assert.equal(report.summary.canopy.coverage.fraction, 0);
  assert.equal(report.summary.landcover.grass_share, null);
  assert.equal(report.summary.composition.status, "unknown");
  assert.equal(report.summary.composition.growth_forms.grass, null);
  assert.equal(report.summary.density.trees_per_ha, null);
  assert.doesNotThrow(() => JSON.stringify(report));
});

test("WGS84 rotation and scale place inventory trees in the real-metre cells", () => {
  const sq = square(400, { rotation: 90 });
  const records = [record(sq, "nw", -100, 100), record(sq, "se", 100, -100)];
  const report = expectation(sq, {
    records,
    surveys: [{ kind: "inventory", complete: true, source: "city", bounds: bounds(sq, -200, -200, 200, 200) }],
  }, { cellSize: 200 });
  assert.deepEqual(report.cells.map((cell) => cell.density.evidence.record_count), [1, 0, 0, 1]);
  assert.deepEqual(report.cells.map(({ row, col }) => [row, col]), [[0, 0], [0, 1], [1, 0], [1, 1]]);
  close(report.cells[0].x_m, -100);
  close(report.cells[0].z_m, 100);
  close(report.summary.density.trees_per_ha, 0.125, 1e-8);

  const large = square(8640, { rotation: 37 });
  const nearby = compositionAt(large, [
    record(large, "in", 1500, 0, "Quercus", { kind: "occurrence" }),
    record(large, "out", 2100, 0, "Magnolia", { kind: "occurrence" }),
  ], 0, 0, { urban: true });
  assert.deepEqual(nearby.genus, [{ genus: "Quercus", share: 1 }]);
  close(nearby.evidence.nearest_m, 1500, 1e-5);
});

test("inventory evidence has explicit urban and rural windows; occurrence absence is unknown", () => {
  const sq = square();
  const records = [
    record(sq, "street", 1000, 0, "Quercus"),
    record(sq, "mapped", 10, 0, "Magnolia", { kind: "osm", source: "OSM" }),
    record(sq, "wild", 0, 0, "Ficus", { kind: "occurrence", source: "GBIF" }),
  ];
  const query = compositionSampler(sq, records);
  assert.equal(query(0, 0, { urban: true }).kind, "inventory");
  assert.deepEqual(query(0, 0, { urban: true }).genus, [{ genus: "Quercus", share: 1 }]);
  assert.equal(query(0, 0).kind, "osm");
  assert.equal(query(0, 0).evidence.radius_m, 2000);
  assert.equal(compositionAt(sq, [record(sq, "park", 200, 0)], 0, 0).kind, "inventory");
  assert.equal(compositionAt(sq, [record(sq, "far", 300, 0)], 0, 0).status, "unknown");
  const occurrenceOnly = expectation(sq, { records: [records[2]] });
  assert.equal(occurrenceOnly.cells[0].composition.kind, "occurrence");
  assert.equal(occurrenceOnly.summary.density.trees_per_ha, null);
  assert.equal(expectation(sq, { records: [] }).summary.density.trees_per_ha, null);
});

test("genus alone never supplies an evergreen or deciduous growth form", () => {
  const sq = square();
  const records = ["Quercus", "Magnolia", "Ficus", "Larix", "Taxodium", "Pinus"]
    .map((genus, i) => record(sq, i, 0, 0, genus));
  const composition = compositionAt(sq, records, 0, 0, { urban: true });
  assert.equal(composition.growth_forms.unknown, 1);
  assert.equal(composition.growth_forms.needleleaf_evergreen, 0);
  const explicit = compositionAt(sq, [record(sq, "trait", 0, 0, "Pinus", { growth_form: "needleleaf_evergreen" })], 0, 0);
  assert.equal(explicit.growth_forms.needleleaf_evergreen, 1);
  const unsupported = compositionAt(sq, [record(sq, "trait", 0, 0, "Larix", { growth_form: "needleleaf_deciduous" })], 0, 0);
  assert.equal(unsupported.growth_forms.unknown, 1);
});

test("urban inventory uses observed local counts or an explicit single-source regional pool", () => {
  const sq = square(17280);
  const records = [
    record(sq, "a", 0, 0, "Quercus"),
    record(sq, "b", 20, 0, "Quercus"),
    record(sq, "c", 90, 0, "Magnolia"),
    record(sq, "regional", 4000, 0, "Magnolia"),
    record(sq, "other-city", 10000, 0, "Ficus", { source: "other-city" }),
    record(sq, "out-of-pool", 26000, 0, "Ficus"),
    record(sq, "osm", 1, 0, "Pinus", { kind: "osm" }),
  ];
  const query = compositionSampler(sq, records);
  const direct = query(0, 0, { urban: true });
  assert.equal(direct.method, "observed_local_inventory");
  assert.equal(direct.evidence.record_count, 3);
  close(direct.genus.find((entry) => entry.genus === "Quercus").share, 2 / 3,
    1e-12, "direct observed counts are not distance weighted");
  const gap = query(1500, 0, { urban: true });
  assert.equal(gap.method, "city_inventory_source_pool");
  assert.equal(gap.evidence.record_count, 4);
  assert.deepEqual(gap.evidence.sources, ["city"]);
  assert.deepEqual(gap.genus, [{ genus: "Magnolia", share: 0.5 }, { genus: "Quercus", share: 0.5 }]);
  assert.equal(gap.evidence.radius_m, 25000);
  assert.match(gap.estimand, /regional urban prior/);
  assert.equal(query(10000, 0, { urban: true }).genus[0].genus, "Ficus");
});

test("bounded nearest-k kernel agrees with an analytic brute-force query and is deterministic", () => {
  const sq = square(17280);
  const records = Array.from({ length: 80 }, (_, i) => record(sq, `tree-${i}`, (i * 137 % 3600) - 1800, (i * 359 % 3600) - 1800, `Genus${i}`, { kind: "occurrence" }));
  const x = 137, z = -91;
  const ranked = records.map((item, i) => ({
    item, distance2: ((i * 137 % 3600) - 1800 - x) ** 2 + ((i * 359 % 3600) - 1800 - z) ** 2,
  })).filter((item) => item.distance2 <= 2000 ** 2).sort((a, b) => a.distance2 - b.distance2).slice(0, 24);
  const total = ranked.reduce((sum, item) => sum + 1 / (1 + item.distance2 / 10000), 0);
  const actual = compositionAt(sq, records, x, z, { urban: true });
  assert.equal(actual.evidence.record_count, 24);
  for (const item of ranked) {
    close(actual.genus.find((entry) => entry.genus === item.item.genus).share, 1 / (1 + item.distance2 / 10000) / total, 1e-9);
  }
  assert.deepEqual(actual, compositionAt(sq, [...records].reverse(), x, z, { urban: true }));
});

test("complete surveyed bounds alone permit density and overlapping receipts do not duplicate area", () => {
  const sq = square(200);
  const left = { kind: "inventory", complete: true, source: "city", bounds: bounds(sq, -100, -100, 50, 100) };
  const right = { ...left, bounds: bounds(sq, -50, -100, 100, 100) };
  const tree = record(sq, "same", 0, 0);
  const report = expectation(sq, { records: [tree, { ...tree }], surveys: [left, right] }, { cellSize: 200 });
  assert.equal(report.counts.unique, 1);
  assert.equal(report.counts.duplicates, 1);
  assert.equal(report.summary.density.evidence.record_count, 1);
  close(report.summary.density.surveyed_area_m2, 40000, 1e-5);
  close(report.summary.density.trees_per_ha, 0.25, 1e-8);
  const empty = expectation(sq, { records: [], surveys: [left, right] }, { cellSize: 200 });
  assert.equal(empty.summary.density.trees_per_ha, 0, "complete surveyed absence is an observed zero");
  const incomplete = expectation(sq, { records: [tree], surveys: [{ ...left, complete: false }] });
  assert.equal(incomplete.summary.density.trees_per_ha, null);
  assert.equal(expectation(sq, { records: [tree] }).summary.density.trees_per_ha, null);
});

test("regional genus composition weights observed canopy area, not empty or missing cells", () => {
  const sq = square(800), records = [], heights = [];
  for (let row = 0; row < 4; row++) for (let col = 0; col < 4; col++) {
    records.push(record(sq, `${row}:${col}`, (col + 0.5) * 200 - 400, 400 - (row + 0.5) * 200,
      col < 2 ? "Quercus" : "Magnolia"));
    heights.push(col === 0 ? 10 : 0);
  }
  const report = expectation(sq, { records, structure: { size: 4, heights } }, { cellSize: 200 });
  assert.equal(report.summary.composition.weight_basis, "estimated_canopy_area");
  assert.deepEqual(report.summary.composition.genus, [{ genus: "Quercus", share: 1 }]);
  close(report.summary.composition.coverage.weighted_area_m2, 160000);
  const missing = expectation(sq, { records }, { cellSize: 200 });
  assert.equal(missing.summary.composition.weight_basis, "cell_area_no_height_evidence");
  for (const entry of missing.summary.composition.genus) close(entry.share, 0.5);
});

test("aggregation is pure and boundary validation is explicit", () => {
  const sq = square(), evidence = {
    records: [record(sq, "tree", 0, 0)],
    structure: { size: 2, heights: [0, 2, 10, null], landcover: [10, 20, 30, 90] },
    sources: [{ id: "city", coverage: { available: true } }],
  };
  const saved = structuredClone(evidence), savedSquare = { ...sq };
  const report = expectation(sq, evidence);
  assert.deepEqual(evidence, saved);
  assert.deepEqual(sq, savedSquare);
  report.sources[0].coverage.available = false;
  assert.deepEqual(evidence, saved);
  assert.throws(() => expectation({ ...sq, scale: 0 }), /positive scale/);
  assert.throws(() => expectation(sq, {}, { cellSize: 49 }), /50 and 200/);
  assert.throws(() => compositionAt(sq, [], NaN, 0), /Finite real-metre/);
});

test("forest raster supplies a canopy-area prior without inventing genus or individual traits", () => {
  const report = expectation(square(320, { lat: -22.9, lon: -43.2 }), {
    structure: {
      size: 2, heights: [10, 20, 10, 20], forest_types: [2, 2, 2, 2],
      forest_type_source: "Copernicus analytic Rio forest type", forest_type_sample_m: 100,
    },
  });
  const prior = report.summary.canopy.form_prior;
  assert.equal(prior.growth_forms.broadleaf_evergreen, 1);
  assert.equal(prior.coverage.known_fraction, 1);
  assert.equal(prior.year, 2019);
  assert.equal(prior.nominal_resolution_m, 100);
  assert.match(prior.source, /Copernicus/);
  assert.match(prior.estimand, /not individual-tree/);
  assert.equal(report.summary.tree_forms.growth_forms.broadleaf_evergreen, 1);
  assert.equal(report.summary.tree_forms.prior_filled_share, 1);
  assert.deepEqual(report.summary.composition.genus, [], "leaf-form raster does not invent genera");
  assert.equal(report.summary.density.trees_per_ha, null);
  assert.equal(report.summary.landcover.grass_share, null);
});

test("missing, mixed and deciduous-needleleaf priors retain unknown mass in the six-form vocabulary", () => {
  const observed = expectation(square(), {
    structure: { size: 2, heights: [10, 10, 10, 10], forest_types: [1, 2, 3, 4] },
  });
  const prior = observed.summary.canopy.form_prior;
  close(prior.growth_forms.needleleaf_evergreen, 0.25);
  close(prior.growth_forms.broadleaf_evergreen, 0.25);
  close(prior.growth_forms.broadleaf_deciduous, 0.25);
  close(prior.growth_forms.unknown, 0.25);
  assert.equal(prior.coverage.fraction, 1, "deciduous needleleaf is valid forest-type evidence");
  assert.equal(prior.coverage.known_fraction, 0.75, "but not evergreen needleleaf");
  assert.equal(observed.cells[2].tree_forms.growth_forms.unknown, 1);

  const unclassified = expectation(square(), {
    structure: { size: 2, heights: [10, 10, 10, 10], forest_types: [5, 0, 255, "1"] },
  });
  assert.equal(unclassified.summary.canopy.form_prior.growth_forms.unknown, 1);
  assert.equal(unclassified.summary.canopy.form_prior.coverage.fraction, 0.25);
  assert.equal(unclassified.summary.tree_forms.growth_forms.unknown, 1);
  const missing = expectation(square(), { structure: { size: 2, heights: [10, 10, 10, 10] } });
  assert.equal(missing.summary.tree_forms.growth_forms.unknown, 1);
  assert.equal(missing.summary.tree_forms.status, "unknown");
});

test("explicit palm records are retained and the forest prior fills only unknown record mass", () => {
  const sq = square();
  const palm = record(sq, "palm", 0, 0, "Sabal", { growth_form: "palm" });
  const unknown = record(sq, "unknown", 0, 0, "Magnolia");
  const structure = { size: 2, heights: [10, 10, 10, 10], forest_types: [2, 2, 2, 2] };
  const known = expectation(sq, { records: [palm], structure });
  assert.equal(known.summary.tree_forms.growth_forms.palm, 1);
  assert.equal(known.summary.tree_forms.growth_forms.broadleaf_evergreen, 0);
  assert.equal(known.summary.tree_forms.prior_filled_share, 0);
  const mixed = expectation(sq, { records: [palm, unknown], structure });
  assert.equal(mixed.summary.tree_forms.growth_forms.palm, 0.5);
  assert.equal(mixed.summary.tree_forms.growth_forms.broadleaf_evergreen, 0.5);
  assert.equal(mixed.summary.tree_forms.growth_forms.unknown, 0);
  assert.equal(mixed.summary.tree_forms.record_known_share, 0.5);
  assert.equal(mixed.summary.tree_forms.prior_filled_share, 0.5);
  assert.equal(mixed.summary.composition.growth_forms.unknown, 0.5,
    "raw record composition remains distinct from the estimated forest prior");
});

test("forest form overlap is exact, masked by observed canopy and canopy-area weighted", () => {
  const report = expectation(square(300), {
    structure: { size: 2, heights: [10, 0, 10, 0], forest_types: [1, 2, 4, 2] },
  }, { cellSize: 100 });
  const middle = report.cells[4].canopy.form_prior;
  close(middle.coverage.canopy_area_m2, 5000);
  close(middle.growth_forms.needleleaf_evergreen, 0.5);
  close(middle.growth_forms.broadleaf_deciduous, 0.5);
  assert.equal(middle.growth_forms.broadleaf_evergreen, 0, "forest pixels over height zero are excluded");
  assert.equal(report.summary.tree_forms.weight_basis, "observed_canopy_area");
  close(report.summary.tree_forms.coverage.canopy_area_m2, 45000);
  close(report.summary.tree_forms.growth_forms.needleleaf_evergreen, 0.5);
  close(report.summary.tree_forms.growth_forms.broadleaf_deciduous, 0.5);
  const partial = expectation(square(), {
    structure: { size: 2, heights: [10, 10, 10, null], forest_types: [1, 2, 2, 1] },
  });
  close(partial.summary.tree_forms.growth_forms.needleleaf_evergreen, 1 / 3);
  close(partial.summary.tree_forms.growth_forms.broadleaf_evergreen, 2 / 3);
  const missing = expectation(square(), {
    structure: { size: 2, heights: [null, NaN, 0, -1], forest_types: [2, 2, 2, 2] },
  });
  assert.equal(missing.summary.canopy.canopy_area_m2, 0);
  assert.equal(missing.summary.canopy.form_prior.growth_forms.broadleaf_evergreen, null);
  assert.equal(missing.summary.tree_forms.growth_forms.broadleaf_evergreen, null);
  assert.equal(missing.summary.tree_forms.status, "unknown");
  assert.equal(missing.cells[0].canopy.cover, null, "a forest type cannot create missing canopy heights");
});

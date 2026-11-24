import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { checkCapabilities, measureStockMetrics, networkAccess, shipCorridor, stockBand, stockComparison, STOCK_MEASURES } from "../capability-model.js";
import { validateLedger, ledgerPage, stockReference, agreementByOracle } from "../capability-ledger.mjs";
import { CAPTURE_STOCK, captureEstimate, estimateInputs, stockEstimate } from "../capability-inputs.js";
import { latticeLonLat, parseMrdsXml, PLACE_GRID, requestDeposits, requestLandcover } from "../capability-evidence.js";
import { placeDetail } from "../capability-ui.js";
import { squareToLonLat } from "../terrain.js";
import { loadFixtureContract } from "./fixture-contract.mjs";

const ledger = JSON.parse(readFileSync(new URL("../capabilities.json", import.meta.url)));
const rules = ledger.model_rules.ship;
const node = (outside = null) => ({ outside });
const edge = (a, b, kind) => ({ a, b, kind });

test("water results show one verdict and reason, with captured text escaped", () => {
  const measured = structuredClone(ledger);
  measured.capabilities.find(c => c.id === "water_risk").game_agreement = [{
    study: "pl1191-playable-water", square: "Test <river>", verdict: "Dries",
    reason: "Dry reach & no flood", predicted: null, observed: false,
    oracle: "native_water_60_minutes",
  }];
  const page = ledgerPage(measured);
  assert.match(page, /<td>Test &lt;river&gt;<\/td><td>Dries<\/td><td>Dry reach &amp; no flood<\/td>/);
  assert.match(page, /Before and after openings/);
});

test("eight gameplay-water rows bind the fixed selection and actual failed evidence", () => {
  const prefix = "tools/map-factory/capability-evidence/pl1191-playable-water/";
  const selection = JSON.parse(readFileSync(new URL("../tools/map-factory/calibration/pl1191-construction-v1/gameplay-water/eight-squares.json", import.meta.url)));
  const result = JSON.parse(readFileSync(new URL("../" + prefix + "verdicts.json", import.meta.url)));
  const rows = ledger.capabilities.find(c => c.id === "water_risk").game_agreement.filter(r => r.study === "pl1191-playable-water");
  assert.deepEqual(rows.map(r => r.square), selection.squares.map(s => s.slug));
  assert.deepEqual(result.rows, rows);
  for (const row of rows) {
    const raw = readFileSync(new URL("../" + row.evidence[0], import.meta.url));
    assert.equal(createHash("sha256").update(raw).digest("hex"), row.artifact_sha256);
    assert.equal(row.source_sha, result.source_sha);
    const outcome = JSON.parse(readFileSync(new URL("../" + prefix + row.square + "-maintained-feature-outcome.json", import.meta.url)));
    assert.ok(outcome.contracts.some(c => c.status === "fail"), "all eight observed packages lose required water");
    assert.equal(row.observed, false);
    assert.equal(row.predicted, null);
  }
});

test("ledger references real checks, calibrated seed and all 104 stock maps", () => {
  validateLedger(ledger);
  assert.equal(stockReference().maps, 104);
  const b = ledger.stock_reference.metrics.buildable_percent;
  assert.deepEqual([b.p25, b.median, b.p75], [57, 68, 76.25]);
  const page = ledgerPage(ledger, "test-source");
  assert.match(page, /Native study: what was scored/);
  assert.match(page, /no native negative is validated/i);
  assert.match(page, /104 shipped maps/);
  assert.match(page, /blob\/test-source\/tools\/map-factory\/capabilities.py/);
  assert.match(page, /Terrain-shape measures, live/);
  assert.match(page, /Comparability evidence on the committed squares/);
  assert.match(page, /Terrain interest on the launch bar/);
});

test("the terrain-interest survey is row-, tool- and quartile-bound", () => {
  const bound = ledger.stock_reference.terrain_interest;
  const raw = readFileSync(new URL("../" + bound.artifact, import.meta.url));
  assert.equal(bound.artifact_sha256, createHash("sha256").update(raw).digest("hex"));
  const study = JSON.parse(raw);
  assert.equal(study.version, "pl1228-terrain-interest-v1");
  const names = study.rows.map((row) => row.file);
  assert.deepEqual(names, [...names].sort());
  assert.equal(new Set(names).size, names.length);
  assert.equal(study.maps.read_only, true);
  assert.equal(study.maps.included, study.rows.length);
  assert.equal(study.maps.files_seen, study.rows.length + study.maps.excluded.length + study.maps.failures.length);
  assert.deepEqual(study.maps.failures, []);
  assert.deepEqual(bound.comparability.capture_estimate, CAPTURE_STOCK);
  assert.deepEqual(bound.measures, ["terrain_roughness_percent", "central_terrain_diversity_m"]);
  for (const [key, file] of Object.entries({
    reader: "tools/map-factory/survey/measure_maps.py",
    measure_tool: "tools/map-factory/survey/measure_terrain_interest.py",
    measure_source: "tools/map-factory/terrain_interest.py",
  })) assert.equal(bound.tool[key].sha256, createHash("sha256").update(readFileSync(new URL("../" + file, import.meta.url))).digest("hex"));
  assert.equal(bound.rows_sha256, createHash("sha256").update(JSON.stringify(study.rows)).digest("hex"));
  const q = (values, p) => { const index = (values.length - 1) * p, lo = Math.floor(index), hi = Math.ceil(index); return values[lo] + (values[hi] - values[lo]) * (index - lo); };
  for (const id of bound.measures) {
    const values = study.rows.map((row) => row[id]).sort((a, b) => a - b);
    assert.equal(values.length, study.maps.included);
    for (const [key, p] of [["p25", 0.25], ["median", 0.5], ["p75", 0.75]])
      assert.equal(ledger.stock_reference.metrics[id][key], q(values, p), `${id} ${key}`);
    assert.equal(ledger.stock_reference.metrics[id].definition, STOCK_MEASURES[id].definition);
    assert.equal(ledger.stock_reference.metrics[id].name, STOCK_MEASURES[id].label);
    assert.equal(ledger.stock_reference.metrics[id].kind, "terrain_shape");
    assert.equal(ledger.stock_reference.metrics[id].status, "measured_stock_distribution_capture_comparable");
  }
  // A changed quartile or a rewritten policy makes the stock reference stale.
  for (const mutate of [
    (candidate) => { candidate.stock_reference.metrics.terrain_roughness_percent.p25 = 0; },
    (candidate) => { candidate.stock_reference.terrain_interest.comparability.capture_estimate.terrain_roughness_percent.basis = "changed"; },
    (candidate) => { candidate.stock_reference.terrain_interest.rows_sha256 = "0".repeat(64); },
  ]) {
    const candidate = structuredClone(ledger); mutate(candidate);
    assert.throws(() => validateLedger(candidate), /Stock reference is stale/);
  }
});

test("outside counts do not establish directed road connectivity", () => {
  const nodes = [node("west"), node(), node(), node("east")];
  const graph = { nodes, edges: [edge(0, 1, "highway"), edge(2, 3, "highway")] };
  assert.equal(networkAccess(graph, "road").candidate, false);
  graph.edges.push(edge(1, 2, "rail"));
  assert.equal(networkAccess(graph, "road").candidate, false, "rail cannot fill a road gap");
  graph.edges.push(edge(2, 1, "ramp"));
  assert.equal(networkAccess(graph, "road").candidate, false, "wrong-way ramp cannot fill it");
  graph.edges.push(edge(1, 2, "ramp"));
  assert.equal(networkAccess(graph, "road").candidate, true);
});

test("rail, ship and air routes are bidirectional but need distinct outside nodes", () => {
  for (const kind of ["rail", "ship", "air"]) {
    const graph = { nodes: [node("west"), node(), node("east")], edges: [edge(1, 0, kind), edge(1, 2, kind)] };
    assert.equal(networkAccess(graph, kind).candidate, true);
    graph.nodes[2].outside = null;
    assert.equal(networkAccess(graph, kind).candidate, false);
  }
});

test("ship candidate needs a deep, broad, edge-connected component", () => {
  const size = 33, spacing = 540;
  const grid = new Array(size ** 2).fill(8);
  assert.equal(shipCorridor(grid, size, spacing, rules).candidate, true);
  for (let r = 0; r < size; r++) grid[r * size + 16] = 0;
  // A shore wall splits the water, but each half still has multiple outside entries.
  assert.equal(shipCorridor(grid, size, spacing, rules).candidate, true);
  const lake = grid.map((_, i) => {
    const r = Math.floor(i / size), c = i % size;
    return r > 3 && r < size - 4 && c > 3 && c < size - 4 ? 8 : 0;
  });
  assert.equal(shipCorridor(lake, size, spacing, rules).candidate, false);
  const narrow = grid.map((_, i) => Math.floor(i / size) === 16 ? 8 : 0);
  assert.equal(shipCorridor(narrow, size, spacing, rules).candidate, false);
  assert.equal(shipCorridor(grid.map(() => 5.99), size, spacing, rules).candidate, false);
});

test("estimates and absent data cannot promote promises or false negatives", () => {
  const input = { schema: 1, mode: "estimate", grid: { size: 2, spacing_m: 64, depth_m: [0, 0, 0, 0] }, buildable_fraction: 0 };
  const result = checkCapabilities(input, ledger);
  for (const c of Object.values(result.capabilities)) assert.equal(c.level, "unknown");
  input.mode = "export";
  assert.equal(checkCapabilities(input, ledger).capabilities.ship.level, "unknown", "missing graph does not establish absence");
  input.graph = { nodes: [], edges: [] };
  assert.equal(checkCapabilities(input, ledger).capabilities.ship.level, "not_possible_here");
  assert.throws(() => checkCapabilities({ ...input, grid: { ...input.grid, depth_m: [NaN, 0, 0, 0] } }, ledger));
  assert.throws(() => networkAccess({ nodes: [node()], edges: [edge(-1, 0, "rail")] }, "rail"));
});

test("ship route existence and broad-corridor support are separate evidence", () => {
  const nodes = [node("west"), node("east")], edges = [edge(0, 1, "ship")];
  const input = { schema: 1, mode: "export", grid: { size: 17, spacing_m: 1080, depth_m: new Array(289).fill(0) }, graph: { nodes, edges } };
  const narrow = checkCapabilities(input, ledger).capabilities.ship;
  assert.equal(narrow.level, "likely");
  assert.equal(narrow.reason, "authored_ship_route_corridor_unconfirmed");
  assert.equal(narrow.authored_route.candidate, true);
  assert.equal(narrow.witness.candidate, false);
  input.graph = { nodes: [], edges: [] };
  input.grid.depth_m.fill(8);
  const unrouted = checkCapabilities(input, ledger).capabilities.ship;
  assert.equal(unrouted.level, "likely");
  assert.equal(unrouted.reason, "initial_deep_corridor_no_authored_route");
  assert.equal(unrouted.authored_route.candidate, false);
  assert.equal(unrouted.witness.candidate, true);
});

test("ledger rejects a stale symbol even when its source file exists", () => {
  const stale = structuredClone(ledger);
  stale.capabilities.find((c) => c.id === "air").existing_checks = ["inputs.js:capturedAirport"];
  assert.throws(() => validateLedger(stale), /Missing check symbol/);
  assert.match(ledger.stock_reference.metrics.trees_total.name, /budget-sensitive/);
  for (const key of ["ship", "air"]) {
    const capability = ledger.capabilities.find((c) => c.id === key);
    assert.equal(capability.exporter_check, "tools/map-factory/capabilities.py:check");
    assert.equal(capability.browser_check, "capability-model.js:checkCapabilities");
    assert.match(capability.promise_levels.unknown, /planner was explicitly disabled/);
  }
});

test("explicit planner opt-outs are unknown even with corridor or stale route evidence", () => {
  const input = { schema: 1, mode: "export", planner_enabled: { ship: false, air: false },
    graph: { nodes: [node("west"), node("east")], edges: [edge(0, 1, "ship"), edge(0, 1, "air")] },
    grid: { size: 17, spacing_m: 1080, depth_m: new Array(289).fill(8) } };
  for (const mode of ["export", "estimate"]) {
    input.mode = mode;
    for (const key of ["ship", "air"])
      assert.deepEqual(checkCapabilities(input, ledger).capabilities[key], { level: "unknown", reason: "planner_disabled" });
  }
  input.mode = "export";
  input.planner_enabled = { ship: true, air: true };
  for (const key of ["ship", "air"]) assert.equal(checkCapabilities(input, ledger).capabilities[key].level, "likely");
  input.graph = { nodes: [], edges: [] };
  input.grid.depth_m.fill(0);
  input.planner_enabled = { ship: false, air: false };
  for (const key of ["ship", "air"]) assert.equal(checkCapabilities(input, ledger).capabilities[key].level, "unknown");
  delete input.planner_enabled;
  for (const key of ["ship", "air"]) assert.equal(checkCapabilities(input, ledger).capabilities[key].level, "not_possible_here");
});

test("agreement separates oracle types and excludes missing labels", () => {
  const scores = agreementByOracle([
    { oracle: "native_path", predicted: true, observed: true },
    { oracle: "native_path", predicted: true, observed: false },
    { oracle: "native_path", predicted: true, observed: null },
    { oracle: "native_panel", predicted: true, observed: true },
  ]);
  assert.deepEqual(scores.find((s) => s.oracle === "native_path"), { oracle: "native_path", scored: 2, unscored: 1, agree: 1, false_positive: 1, false_negative: 0 });
  const m = { p25: 1, p75: 3 };
  assert.deepEqual([0, 1, 2, 3, 4].map((v) => stockBand(v, m)), ["below_p25", "typical", "typical", "typical", "above_p75"]);
  assert.equal(stockBand(null, m), "not_comparable");
});

test("stock measures follow the prepared definitions, mask and wet threshold", () => {
  const n = 1081, ground = new Float64Array(n ** 2), depth = new Float64Array(n ** 2);
  // 1 m per 16 m row is exactly 6.25% slope; Python's round() takes the tie to 6.2.
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) ground[r * n + c] = r;
  assert.deepEqual(measureStockMetrics(ground, depth), {
    terrain_relief_m: 1080, terrain_roughness_percent: 6.25, central_terrain_diversity_m: 481,
    wet_central_fraction: 0, median_land_slope_percent: 6.2,
  });
  ground.fill(100);
  depth.fill(0.5); // the threshold is strictly above 0.5 m, as in terrain_fields()
  assert.equal(measureStockMetrics(ground, depth).wet_central_fraction, 0);
  depth.fill(0.6);
  assert.equal(measureStockMetrics(ground, depth).wet_central_fraction, 1);
  depth.fill(0);
  for (let i = 0; i < n * n; i += 1) if (i % n < 100) depth[i] = 1; // water outside the central 25 tiles
  assert.equal(measureStockMetrics(ground, depth).wet_central_fraction, 0);
  assert.throws(() => measureStockMetrics(new Float64Array(4), depth), /1081-square/);
});

test("terrain-shape measures are terrain only and read a constructed step", () => {
  const n = 1081, depth = new Float64Array(n ** 2);
  const flat = new Float64Array(n ** 2).fill(100);
  const flatResult = measureStockMetrics(flat, new Float64Array(n ** 2).fill(500));
  assert.equal(flatResult.terrain_roughness_percent, 0);
  assert.equal(flatResult.central_terrain_diversity_m, 0);
  // A single step down the middle: the central window spans both levels.
  const step = new Float64Array(n ** 2);
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) step[r * n + c] = c < 540 ? 100 : 200;
  const reference = measureStockMetrics(step, depth);
  assert.ok(reference.terrain_roughness_percent > 0, "a step has roughness");
  assert.equal(reference.central_terrain_diversity_m, 100, "the central window sees both levels");
  // The terrain-shape measures never read depth.
  assert.equal(measureStockMetrics(step, new Float64Array(n ** 2).fill(9)).terrain_roughness_percent, reference.terrain_roughness_percent);
  assert.equal(measureStockMetrics(step, new Float64Array(n ** 2).fill(9)).central_terrain_diversity_m, reference.central_terrain_diversity_m);
});

test("a capture grid mismatch is Not comparable with a typed reason", () => {
  const short = stockEstimate({ game: new Float32Array(4) }, new Float64Array(4));
  assert.equal(short.measures, null);
  assert.equal(short.comparability.terrain_roughness_percent.reason, "capture_grid_fidelity_mismatch");
  const rows = stockComparison(short.measures, ledger.stock_reference, short.comparability);
  for (const row of Object.values(rows)) {
    assert.equal(row.comparable, false);
    assert.equal(row.value, null);
    assert.equal(row.band, "not_comparable");
    assert.equal(row.reason, "capture_grid_fidelity_mismatch");
  }
});

test("stock comparison withholds only the measures capture fidelity cannot support", () => {
  const reference = ledger.stock_reference;
  const values = {
    terrain_relief_m: 300, terrain_roughness_percent: 25, central_terrain_diversity_m: 400,
    median_land_slope_percent: 9, wet_central_fraction: 0.2,
  };
  const withheld = {
    median_land_slope_percent: { comparable: false, reason: "capture_terrain_and_water_are_not_prepared" },
    wet_central_fraction: { comparable: false, reason: "capture_bed_depth_is_not_prepared_water" },
  };
  const result = stockComparison(values, reference, withheld);
  assert.equal(result.terrain_relief_m.value, 300);
  assert.equal(result.terrain_relief_m.band, "below_p25");
  assert.equal(result.terrain_relief_m.definition, STOCK_MEASURES.terrain_relief_m.definition);
  assert.deepEqual([result.terrain_relief_m.p25, result.terrain_relief_m.median, result.terrain_relief_m.p75], [reference.metrics.terrain_relief_m.p25, reference.metrics.terrain_relief_m.median, reference.metrics.terrain_relief_m.p75]);
  assert.equal(result.terrain_roughness_percent.value, 25);
  assert.equal(result.terrain_roughness_percent.band, "above_p75");
  assert.equal(result.central_terrain_diversity_m.value, 400);
  assert.equal(result.central_terrain_diversity_m.band, "above_p75");
  for (const id of ["median_land_slope_percent", "wet_central_fraction"]) {
    assert.equal(result[id].comparable, false);
    assert.equal(result[id].value, null, "a withheld measure carries no value to compare");
    assert.equal(result[id].band, "not_comparable");
    assert.equal(result[id].reason, withheld[id].reason, "a withheld measure carries its typed reason");
    assert.ok(result[id].definition, "the definition still travels with the withheld measure");
  }
  assert.equal(result.median_land_slope_percent.label, "Central land slope");
  assert.equal(result.terrain_roughness_percent.label, "Terrain roughness");
  assert.equal(result.central_terrain_diversity_m.label, "Central height range");
  assert.equal(Object.keys(result).length, Object.keys(STOCK_MEASURES).length);
  const missing = stockComparison(null, reference);
  for (const row of Object.values(missing)) { assert.equal(row.value, null); assert.equal(row.band, "not_comparable"); }
  assert.deepEqual(CAPTURE_STOCK.terrain_roughness_percent.comparable, true);
  assert.deepEqual(CAPTURE_STOCK.central_terrain_diversity_m.comparable, true);
});

test("UI adoption cannot hide changed live checks or rewritten historical gates", async () => {
  const root = new URL("../", import.meta.url);
  const read = async (name) => readFileSync(new URL("tools/map-factory/" + name, root));
  const source = async (name) => readFileSync(new URL(name, root));
  await assert.rejects(loadFixtureContract(read, async (name) => name === "capability-model.js" ? Buffer.from("changed") : source(name)), /capability source changed/);
  await assert.rejects(loadFixtureContract(async (name) => name.endsWith("pl1119-capability-ui-v1/baseline/build.mjs") ? Buffer.from("changed") : read(name), source), /archived gate changed/);
});

test("native verification needs exact package, inputs, explicit environment and every matched control", () => {
  // Constructed launch identity tests the gate; it is NOT new game evidence.
  const qualified = structuredClone(ledger);
  const certificate = structuredClone(ledger.evidence_studies["outside-v1"].qualification_candidates.find((c) => c.capability === "ship"));
  delete certificate.blocked_by;
  certificate.native_context.runtime_game_sha256 = "a".repeat(64);
  certificate.native_context.runtime_game_assemblies = structuredClone(certificate.native_context.game_assemblies);
  certificate.native_context.protocol.entry = "NewGameFromMap";
  certificate.native_context.protocol.inverted_traffic = false;
  certificate.runtime_identity_evidence = { file: `tools/map-factory/capability-evidence/runtime-identities/${"a".repeat(64)}.json`, sha256: "a".repeat(64) };
  qualified.native_path_certificates = [certificate];
  const identity = structuredClone({ artifact_sha256: certificate.artifact_sha256, inputs_sha256: certificate.inputs_sha256, native_context: certificate.native_context });
  const input = { schema: 1, mode: "export", graph: { nodes: [node("west"), node("east")], edges: [edge(0, 1, "ship")] }, export_identity: identity };
  assert.notEqual(checkCapabilities(input, ledger).capabilities.ship.level, "promised", "real receipts still lack runtime identity");
  const result = checkCapabilities(input, qualified).capabilities.ship;
  assert.equal(result.level, "promised");
  assert.equal(result.qualification.scope, "sampled_native_lane_paths_at_opening");
  assert.deepEqual(result.qualification.runtime_identity_evidence, certificate.runtime_identity_evidence);
  assert.throws(() => validateLedger(qualified), /Missing bound runtime identity receipt/);
  const mutations = [
    (d) => { d.mode = "estimate"; },
    (d) => { delete d.export_identity; },
    (d) => { d.export_identity = true; },
    (d) => { d.export_identity.artifact_sha256 = "0".repeat(64); },
    (d) => { delete d.export_identity.inputs_sha256; },
    (d) => { d.export_identity.inputs_sha256["water.u16"] = "0".repeat(64); },
    (d) => { delete d.export_identity.native_context; },
    (d) => { d.export_identity.native_context = {}; },
    (d) => { d.export_identity.native_context.mod_sha256 = "0".repeat(64); },
    (d) => { d.export_identity.native_context.collector_sha256 = "0".repeat(64); },
    (d) => { delete d.export_identity.native_context.runtime_game_sha256; },
    (d) => { delete d.export_identity.native_context.runtime_game_assemblies; },
    (d) => { d.export_identity.native_context.game_assemblies["Assembly-CSharp.dll"] = "0".repeat(64); },
    (d) => { d.export_identity.native_context.protocol.no_workshop = false; },
    (d) => { d.planner_enabled = { ship: false }; },
    (d) => { d.graph = null; },
  ];
  for (const mutate of mutations) {
    const candidate = structuredClone(input); mutate(candidate);
    assert.notEqual(checkCapabilities(candidate, qualified).capabilities.ship.level, "promised");
  }
  const incomplete = structuredClone(qualified);
  for (const c of incomplete.native_path_certificates) c.controls.midpoint_1 = false;
  assert.equal(checkCapabilities(input, incomplete).capabilities.ship.level, "likely");
  assert.throws(() => validateLedger(incomplete), /Unbound native path certificate/);
});

test("native scoring retains failures and unknowns without substituting panels or player runs", () => {
  const road = ledger.capabilities.find((c) => c.id === "road").game_agreement.filter((r) => r.study === "outside-v1");
  const ship = ledger.capabilities.find((c) => c.id === "ship").game_agreement.filter((r) => r.study === "outside-v1");
  assert.ok(road.some((r) => r.oracle === "native_probe_boundary_selected_pair" && r.predicted === null && r.observed === false));
  assert.ok(road.some((r) => r.oracle === "native_attempt_error" && r.observed === null));
  assert.ok(road.filter((r) => ["native_panel", "native_path_archived_player", "native_path_fresh_named"].includes(r.oracle)).every((r) => r.predicted === null));
  assert.equal(ship.filter((r) => r.oracle === "native_two_edge_witness" && r.observed === true).length, 4);
  assert.equal(ship.filter((r) => r.oracle === "native_two_edge_witness" && r.observed === null).length, 5);
  assert.equal(ledger.native_path_certificates.filter((c) => c.study === "outside-v1").length, 0, "v1 stays unbound");
  assert.equal(ledger.native_path_certificates.filter((c) => c.study === "outside-targeted-v2").length, 4);
  const primary = ledger.capabilities.flatMap((c) => c.game_agreement.filter((r) => r.study === "outside-v1" && r.oracle === "native_two_edge_witness"));
  assert.equal(primary.filter((r) => r.observed === true).length, 11);
  assert.equal(primary.filter((r) => r.observed === null).length, 25);
  const stale = structuredClone(ledger);
  stale.evidence_studies["outside-v1"].predictions_sha256 = "0".repeat(64);
  assert.throws(() => validateLedger(stale), /Stale native evidence projection/);
});

test("place evidence separates land cover from the export's tree budget", () => {
  const rules = ledger.model_rules.place;
  const grid = { size: 3, spacing_m: 4800, depth_m: new Array(9).fill(0) };
  const landcover = { status: "available", source: "constructed", fidelity: "constructed", cell_m: 10, sample_m: 40, tiles: [], values: new Array(9).fill(10) };
  const result = checkCapabilities({ schema: 1, mode: "estimate", grid, place: { landcover } }, ledger);
  const trees = result.capabilities.trees;
  assert.equal(trees.level, "likely");
  assert.equal(trees.reason, "vegetation_suitability_candidate");
  assert.equal(trees.evidence.balanced_top_up, "not_evidence");
  assert.equal(trees.evidence.vegetation.tree_cover_share_of_central_land, 1);
  assert.equal(trees.evidence.vegetation.tree_suitability, rules.tree_weight[10]);
  assert.ok(!("trees_total" in trees), "the model must not invent the exporter's tree count");
  // Without a slope grid the taper cannot hide the cover, and it says so.
  assert.equal(trees.evidence.vegetation.slope_screened, false);
  const terrain_m = Array.from({ length: 9 }, (_, i) => 100 + Math.floor(i / 3) * 4800);
  const screened = checkCapabilities({ schema: 1, mode: "estimate", grid, place: { landcover, terrain_m } }, ledger).capabilities.trees;
  assert.equal(screened.level, "unknown");
  assert.equal(screened.reason, "no_tree_support_in_sampled_landcover");
  assert.equal(screened.evidence.vegetation.slope_screened, true);
});

test("no place evidence is Unknown, never a No", () => {
  const grid = { size: 3, spacing_m: 4800, depth_m: new Array(9).fill(0) };
  const bare = checkCapabilities({ schema: 1, mode: "estimate", grid }, ledger).capabilities;
  assert.deepEqual([bare.resources.level, bare.resources.reason, bare.trees.level, bare.trees.reason], ["unknown", "not_evaluated", "unknown", "not_evaluated"]);
  const unavailable = checkCapabilities({ schema: 1, mode: "estimate", grid, place: { deposits: { status: "unavailable", records: [] } } }, ledger).capabilities;
  assert.equal(unavailable.trees.reason, "no_landcover_evidence");
  assert.equal(unavailable.resources.reason, "no_place_evidence");
  assert.equal(unavailable.resources.level, "unknown");
  // Built-up land with no deposit is still not a negative: a missing record is
  // not geographic absence.
  const built = { status: "available", source: "constructed", cell_m: 10, sample_m: 40, tiles: [], values: new Array(9).fill(50) };
  const none = checkCapabilities({ schema: 1, mode: "estimate", grid, place: { landcover: built, deposits: { status: "available", records: [] } } }, ledger).capabilities;
  assert.equal(none.trees.level, "unknown");
  assert.equal(none.trees.reason, "no_tree_support_in_sampled_landcover");
  assert.equal(none.resources.level, "unknown");
  assert.equal(none.resources.reason, "no_recorded_deposit_or_fertile_cover");
  // A well record is not a deposit record.
  const wells = checkCapabilities({ schema: 1, mode: "estimate", grid, place: { landcover: built, deposits: { status: "available", records: [{ kind: "well", x: 0, z: 0 }] } } }, ledger).capabilities.resources.evidence.deposits;
  assert.deepEqual([wells.records, wells.wells], [0, 1]);
});

test("place evidence refuses mismatched arrays instead of guessing", () => {
  const grid = { size: 3, spacing_m: 4800, depth_m: new Array(9).fill(0) };
  const short = { status: "available", values: [10, 10], source: "constructed" };
  assert.throws(() => checkCapabilities({ schema: 1, mode: "estimate", grid, place: { landcover: short } }, ledger), /Land-cover evidence/);
  assert.throws(() => checkCapabilities({ schema: 1, mode: "estimate", grid, place: { terrain_m: [1, 2] } }, ledger), /Terrain evidence/);
  assert.throws(() => checkCapabilities({ schema: 1, mode: "estimate", place: { landcover: short } }, ledger), /needs a capability grid/);
});

test("deposits fail closed to unavailable, and an abort propagates", async () => {
  const square = { lon: -82.555, lat: 35.58, rotation: 0, scale: 1 };
  const failed = await requestDeposits(square, { fetchImpl: async () => ({ ok: false, status: 500, text: async () => "" }) });
  assert.deepEqual([failed.status, failed.records.length], ["unavailable", 0]);
  const thrown = await requestDeposits(square, { fetchImpl: async () => { throw new Error("offline"); } });
  assert.equal(thrown.status, "unavailable");
  const controller = new AbortController();
  controller.abort(new Error("panned"));
  await assert.rejects(requestDeposits(square, { signal: controller.signal, fetchImpl: async () => { throw controller.signal.reason; } }), /panned/);
});

test("MRDS parsing keeps the writer's provenance rules", () => {
  const square = { lon: -82.555, lat: 35.58, rotation: 0, scale: 1 };
  // The sample holds four records: an occurrence, a processing plant, a
  // producer and a prospect outside the square. Only the producer counts.
  const records = parseMrdsXml(readFileSync(new URL("./mrds-sample.xml", import.meta.url), "utf8"), square);
  assert.deepEqual(records.map((r) => r.weight), [1], "occurrences, processing plants and out-of-square prospects are not deposits");
  for (const record of records) assert.ok(Math.abs(record.x) <= 8640 && Math.abs(record.z) <= 8640);
  assert.match(records[0].source, /^USGS MRDS \d+ .+ \(Producer, Surface\)$/);
});

test("the pan-time input samples the same lattice as the exporter", () => {
  const capture = { game: new Float32Array(1081 * 1081), geometry: { roads: [], sq: {} } };
  for (let i = 0; i < capture.game.length; i++) capture.game[i] = i % 977;
  const depth = new Float64Array(1081 * 1081);
  const input = estimateInputs(capture, depth);
  assert.equal(input.grid.size, 271);
  assert.equal(input.place.terrain_m.length, 271 * 271);
  for (const [r, c] of [[0, 0], [1, 2], [270, 270]]) {
    assert.equal(input.place.terrain_m[r * 271 + c], capture.game[(r * 4) * 1081 + c * 4]);
  }
  assert.equal(input.place.landcover.status, "unavailable");
  assert.equal(input.place.deposits.status, "unavailable");
});

test("the ledger page carries the place measures, sources and fidelity", () => {
  const page = ledgerPage(ledger, "test-source");
  assert.match(page, /Place evidence measures/);
  assert.match(page, /Tree suitability/);
  assert.match(page, /Sources, coverage and fidelity/);
  assert.match(page, /balanced ore\/oil top-up/i);
  const incomplete = structuredClone(ledger);
  delete incomplete.capabilities.find((c) => c.id === "trees").source_coverage;
  assert.throws(() => validateLedger(incomplete), /place evidence provenance/);
  const empty = structuredClone(ledger);
  empty.capabilities.find((c) => c.id === "resources").evidence_metrics = {};
  assert.throws(() => validateLedger(empty), /Empty evidence metrics/);
});

test("the worker lattice matches the page's square transform", () => {
  // The worker cannot use the page's import map, so capability-evidence.js
  // carries landcover.lonlat itself. This pins it to terrain.squareToLonLat.
  const half = ((PLACE_GRID.size - 1) * PLACE_GRID.spacing_m) / 2;
  for (const sq of [
    { lon: -71.057, lat: 42.36, rotation: 0, scale: 1 },
    { lon: 139.7, lat: 35.68, rotation: 33, scale: 1.5 },
    { lon: -43.17, lat: -22.91, rotation: -90, scale: 0.5 },
  ]) {
    const { lon, lat } = latticeLonLat(sq);
    for (const [r, c] of [[0, 0], [3, 7], [135, 135], [270, 270]]) {
      const [expectedLon, expectedLat] = squareToLonLat(sq, (c * PLACE_GRID.spacing_m - half) * sq.scale, (half - r * PLACE_GRID.spacing_m) * sq.scale);
      assert.ok(Math.abs(lon[r * PLACE_GRID.size + c] - expectedLon) < 1e-12, `lon ${r},${c}`);
      assert.ok(Math.abs(lat[r * PLACE_GRID.size + c] - expectedLat) < 1e-12, `lat ${r},${c}`);
    }
  }
});

test("below-threshold or coarse tree evidence stays Unknown, never a No", () => {
  const grid = { size: 3, spacing_m: 4800, depth_m: new Array(9).fill(0) };
  const run = (values) => checkCapabilities({ schema: 1, mode: "estimate", grid, place: { landcover: { status: "available", source: "constructed", cell_m: 10, sample_m: 74, tiles: [], values } } }, ledger).capabilities.trees;
  // Pure grass: 0.03 weighted suitability, no tree-cover class.
  const grass = run(new Array(9).fill(30));
  assert.deepEqual([grass.level, grass.reason], ["unknown", "tree_support_below_candidate_threshold"]);
  // 4 percent forest in the central 9 nodes is 0.44 here; use the 0.03 case as
  // the below-threshold proof and a mixed one for a positive, non-zero cover.
  const sparse = run(new Array(9).fill(50).map((value, i) => i === 0 ? 10 : value));
  assert.equal(sparse.level, "likely");
  // Built-up only: zero tree support in this sample, still Unknown.
  const built = run(new Array(9).fill(50));
  assert.deepEqual([built.level, built.reason], ["unknown", "no_tree_support_in_sampled_landcover"]);
  // Incomplete coverage is Unknown even when the sampled cover is zero.
  const partial = run([50, 50, 50, 50, 0, 0, 0, 0, 0]);
  assert.deepEqual([partial.level, partial.reason], ["unknown", "landcover_coverage_incomplete"]);
  for (const result of [grass, built, partial]) assert.notEqual(result.level, "not_possible_here");
});

test("fertility copy separates crop share from weighted suitability", () => {
  const evidence = (vegetation, fertility) => ({
    landcover: { sample_m: 74, coverage_of_central_land: 1 },
    vegetation: { tree_cover_share_of_central_land: 0, tree_suitability: 0.03, candidate_min: 0.05, ...vegetation },
    fertility: { suitability: 0.7, crop_share_of_central_land: 0, candidate_min: 0.02, ...fertility },
    deposits: { status: "available", records: [], ore: { central: 0 }, oil: { central: 0 } },
  });
  const grass = placeDetail({ reason: "fertile_land_suitability_candidate", evidence: evidence() });
  assert.match(grass, /suitability 0\.7/);
  assert.match(grass, /cropland 0%/);
  assert.doesNotMatch(grass, /Crop and pasture cover on 0%/);
  const lowCrop = placeDetail({ reason: "fertile_cover_below_candidate_threshold", evidence: evidence({}, { suitability: 0.01, crop_share_of_central_land: 0.003 }) });
  assert.match(lowCrop, /below the 0\.02 candidate level/);
  assert.doesNotMatch(lowCrop, /no crop or pasture cover/i);
  const lowTrees = placeDetail({ reason: "tree_support_below_candidate_threshold", evidence: evidence({ tree_cover_share_of_central_land: 0.04, tree_suitability: 0.04 }) });
  assert.match(lowTrees, /below the 0\.05 candidate level/);
  assert.doesNotMatch(lowTrees, /supports no trees|no supporting cover/i);
});

function fakeCapture() {
  return {
    game: new Float32Array(1081 * 1081),
    banks: new Float32Array(1081 * 1081),
    seaLevel: null,
    geometry: { sq: { lon: 0, lat: 0, rotation: 0, scale: 1 }, oceans: [], roads: [] },
  };
}

test("captureEstimate settles optional evidence on abort, failure and timeout", async () => {
  const square = { lon: 0, lat: 0, rotation: 0, scale: 1 };
  const unhandled = [];
  const onUnhandled = (error) => unhandled.push(error);
  process.on("unhandledRejection", onUnhandled);
  try {
    // Already aborted: one rejection for the caller, nothing extra.
    const aborted = new AbortController();
    aborted.abort(new Error("constructed pan abort"));
    await assert.rejects(captureEstimate(square, { signal: aborted.signal, budgetMs: 50, sources: {
      capture: async () => { throw aborted.signal.reason; },
      landcover: async () => { throw aborted.signal.reason; },
      deposits: async () => { throw aborted.signal.reason; },
    } }), /constructed pan abort/);
    // Terrain failure with untouched pending evidence: no hang, no unhandled.
    await assert.rejects(captureEstimate(square, { budgetMs: 50, sources: {
      capture: async () => { throw new Error("terrain down"); },
      landcover: () => new Promise(() => {}),
      deposits: () => new Promise(() => {}),
    } }), /terrain down/);
    // Stalled optional sources: the budget resolves them as unavailable while
    // the terrain-backed checks still render.
    const started = Date.now();
    const stalled = await captureEstimate(square, { budgetMs: 40, sources: {
      capture: async () => fakeCapture(),
      landcover: () => new Promise(() => {}),
      deposits: () => new Promise(() => {}),
    } });
    assert.ok(Date.now() - started < 2000, "the evidence budget bounds the pan");
    assert.equal(stalled.input.place.landcover.status, "unavailable");
    assert.equal(stalled.input.place.deposits.status, "unavailable");
    assert.equal(stalled.input.place.terrain_m.length, 271 * 271);
    assert.ok(stalled.stock.measures.terrain_relief_m != null);
    // In-flight pan abort: the capture rejects and evidence settles.
    const controller = new AbortController();
    const pending = captureEstimate(square, { signal: controller.signal, budgetMs: 5000, sources: {
      capture: (sq, { signal }) => new Promise((_, reject) => signal.addEventListener("abort", () => reject(signal.reason), { once: true })),
      landcover: () => new Promise(() => {}),
      deposits: () => new Promise(() => {}),
    } });
    setTimeout(() => controller.abort(new Error("panned")), 10);
    await assert.rejects(pending, /panned/);
    // A worker request that is already aborted never starts one.
    assert.equal(await requestLandcover(square, { signal: aborted.signal }), null);
  } finally {
    process.off("unhandledRejection", onUnhandled);
  }
  await new Promise((resolve) => setTimeout(resolve, 30));
  assert.deepEqual(unhandled, []);
});

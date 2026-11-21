import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { checkCapabilities, networkAccess, shipCorridor, stockBand } from "../capability-model.js";
import { validateLedger, ledgerPage, stockReference, agreementByOracle } from "../capability-ledger.mjs";
import { loadFixtureContract } from "./fixture-contract.mjs";

const ledger = JSON.parse(readFileSync(new URL("../capabilities.json", import.meta.url)));
const rules = ledger.model_rules.ship;
const node = (outside = null) => ({ outside });
const edge = (a, b, kind) => ({ a, b, kind });

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
  const road = ledger.capabilities.find((c) => c.id === "road").game_agreement;
  const ship = ledger.capabilities.find((c) => c.id === "ship").game_agreement;
  assert.ok(road.some((r) => r.oracle === "native_probe_boundary_selected_pair" && r.predicted === null && r.observed === false));
  assert.ok(road.some((r) => r.oracle === "native_attempt_error" && r.observed === null));
  assert.ok(road.filter((r) => ["native_panel", "native_path_archived_player", "native_path_fresh_named"].includes(r.oracle)).every((r) => r.predicted === null));
  assert.equal(ship.filter((r) => r.oracle === "native_two_edge_witness" && r.observed === true).length, 4);
  assert.equal(ship.filter((r) => r.oracle === "native_two_edge_witness" && r.observed === null).length, 5);
  assert.equal(ledger.native_path_certificates.length, 0, "runtime launch identity remains unbound");
  const primary = ledger.capabilities.flatMap((c) => c.game_agreement.filter((r) => r.oracle === "native_two_edge_witness"));
  assert.equal(primary.filter((r) => r.observed === true).length, 11);
  assert.equal(primary.filter((r) => r.observed === null).length, 25);
  const stale = structuredClone(ledger);
  stale.evidence_studies["outside-v1"].predictions_sha256 = "0".repeat(64);
  assert.throws(() => validateLedger(stale), /Stale native evidence projection/);
});

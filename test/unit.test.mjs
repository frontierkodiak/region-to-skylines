// Quick checks (no network): what ships, what the rewrite admits, and the ocean fill.
import { test } from "node:test";
import { loadFixtureContract } from "./fixture-contract.mjs";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { FACTORY_FILES, worldCoverFile } from "../mapgen.js";
import { oceanMask, carveSurfaceWater, CAPTURE } from "../inputs.js";
import { CS1, PRESETS, waterwayTags, carveWater } from "../terrain.js";

const root = new URL("../", import.meta.url).pathname;

test("the writer's files exist, ship in the npm package and survive git archive", () => {
  const pkg = JSON.parse(readFileSync(root + "package.json", "utf8"));
  for (const f of FACTORY_FILES) {
    const path = `tools/map-factory/${f}`;
    assert.ok(existsSync(root + path), path);
    assert.ok(pkg.files.includes(path), `package.json files: ${path}`);
    const attr = execFileSync("git", ["check-attr", "export-ignore", "--", path], { cwd: root, encoding: "utf8" });
    assert.match(attr, /export-ignore: unset$/m, path);
  }
  const fixture = execFileSync("git", ["check-attr", "export-ignore", "--", "tools/map-factory/fixtures/manifest.json"], { cwd: root, encoding: "utf8" });
  assert.match(fixture, /export-ignore: set$/m);
});

test("the WorldCover rewrite admits map tiles only", () => {
  const { rewrites } = JSON.parse(readFileSync(root + "vercel.json", "utf8"));
  const pattern = rewrites[0].source.match(/\((.*)\)$/)[1];
  const re = new RegExp(`^${pattern}$`);
  for (const tile of ["N33W084", "S24W045", "N45E009", "S03E141"]) assert.ok(re.test(worldCoverFile(tile)), tile);
  for (const other of ["ESA_WorldCover_10m_2021_v200_N33W084_Map.tif.aux.xml", "../v100/x.tif", "index.html", "ESA_WorldCover_10m_2021_v200_N33W084_InputQuality.tif"])
    assert.ok(!re.test(other), other);
  assert.match(rewrites[0].destination, /^https:\/\/esa-worldcover\.s3\.eu-central-1\.amazonaws\.com\/v200\/2021\/map\/:tile$/);
});

test("ocean polygons fill by pixel centre, with holes", () => {
  const sq = { lon: 0, lat: 0, rotation: 0, scale: 1 };
  const deg = 17280 / 2 / 111320; // half the square, roughly, in degrees
  const outer = [[-deg, -deg], [deg, -deg], [deg, 0], [-deg, 0], [-deg, -deg]];
  const hole = [[-deg / 4, -deg / 2], [deg / 4, -deg / 2], [deg / 4, -deg / 4], [-deg / 4, -deg / 4], [-deg / 4, -deg / 2]];
  const mask = oceanMask([{ rings: [outer, hole] }], sq);
  const n = CS1.px, at = (r, c) => mask[r * n + c];
  assert.equal(at(1000, 540), 1); // south half: sea
  assert.equal(at(100, 540), 0); // north half: land
  assert.equal(at(540 + 200, 540), 0); // inside the hole
  assert.equal(oceanMask([], sq), null);
});

test("waterway tags keep tunnels and intermittent streams, nothing else", () => {
  assert.deepEqual(waterwayTags({ class: "river", brunnel: "tunnel", intermittent: 0, name: "x" }), { brunnel: "tunnel", intermittent: 0 });
  assert.deepEqual(waterwayTags({ class: "river" }), {});
});

test("surface inputs never excavate a buried river, but retain bridges and surface crossings", () => {
  const sq = { lon: 0, lat: 0, rotation: 0, scale: 1 };
  const ground = new Float32Array(CS1.px ** 2).fill(100);
  const tunnel = { name: "buried", brunnel: "tunnel", pts: [[0, -0.02], [0, 0.02]] };
  const visible = { name: "crossing", brunnel: "bridge", intermittent: 1, pts: [[-0.02, 0], [0.02, 0]] };
  const water = { rivers: [tunnel, visible], lakes: [], riverAreas: [] };
  const before = structuredClone(water);
  const actual = carveSurfaceWater(ground, sq, water);
  const expected = carveWater(ground, sq, { ...water, rivers: [visible] },
    { depth: CAPTURE.riverDepth, halfWidth: CAPTURE.riverHalfWidth, lakeDepth: CAPTURE.lakeDepth });
  assert.deepEqual(actual, expected);
  assert.deepEqual(water, before);
  const at = (r, c) => actual.heights[r * CS1.px + c];
  assert.equal(at(470, 540), 100); // buried reach, away from the crossing
  assert.ok(at(540, 540) < 100); // actual surface crossing still carved
  const unfiltered = carveWater(ground, sq, water);
  assert.ok(unfiltered.heights[470 * CS1.px + 540] < 100); // original bug is exercised
});

test("presets with a failed game check say so; the others don't", () => {
  assert.deepEqual(PRESETS.filter((p) => p.check).map((p) => p.slug).sort(), ["charleston", "rio"]);
  for (const slug of ["asheville", "innsbruck", "rio", "pittsburgh", "charleston"]) assert.ok(PRESETS.find((p) => p.slug === slug), slug);
});


const readFixture = async (name) => readFileSync(root + "tools/map-factory/" + name);
const readContractSource = async (name) => readFileSync(root + name);

test("current partial fixture contract binds all five native packages without claiming acceptance", async () => {
  const { manifest, nativeCases, historicalNativeCases, current } = await loadFixtureContract(readFixture, readContractSource);
  assert.equal(manifest.cases.length, 5);
  assert.equal(current.status, "partial_not_accepted");
  assert.equal(nativeCases.asheville.harness_commit, "022d795fb05a4c93ede04f78cce210773f23e58f");
  assert.notEqual(nativeCases.asheville.native_crp_sha256, historicalNativeCases.asheville.native_crp_sha256);
  assert.deepEqual(nativeCases.rio.failed_checks, ["no_flooding"]);
  assert.deepEqual(nativeCases.charleston.failed_checks, ["ground_truth"]);
  assert.notEqual(manifest.cases[0].expected_crp_sha256, manifest.cases[0].shipping.expected_crp_sha256);
});

test("current fixture contract refuses stale writers, missing regions and fabricated qualification", async () => {
  await assert.rejects(loadFixtureContract(readFixture, async (name) => name.endsWith("region.py") ? new Uint8Array([0]) : readContractSource(name)), /current contract source changed/);
  await assert.rejects(loadFixtureContract(async (name) => name === "fixtures/asheville/terrain.u16.gz" ? new Uint8Array([0]) : readFixture(name), readContractSource), /historical fixture terrain.u16.gz changed/);
  const original = JSON.parse(await readFixture("fixtures/current.json"));
  for (const mutate of [
    (c) => c.cases.pop(),
    (c) => { c.cases[0].native.strict_vanilla_verified = true; },
    (c) => { c.cases[2].native.failed_checks = []; },
    (c) => { c.cases[0].native.harness_commit = "later-metadata-head"; },
    (c) => { c.cases[0].shipping.writer_source_commit = c.cases[0].shipping.historical_capture_source_commit; },
    (c) => { c.cases[0].shipping.expected_crp_sha256 = c.cases[0].reference.expected_crp_sha256; },
    (c) => { c.cases[0].reference.prepared_sha256["terrain.u16"] = "stale-grid"; },
  ]) {
    const candidate = structuredClone(original);
    mutate(candidate);
    await assert.rejects(loadFixtureContract(async (name) => name === "fixtures/current.json" ? new TextEncoder().encode(JSON.stringify(candidate)) : readFixture(name), readContractSource));
  }
});

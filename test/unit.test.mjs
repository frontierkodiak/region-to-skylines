// Quick checks (no network): what ships, what the rewrite admits, and the ocean fill.
import { test } from "node:test";
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

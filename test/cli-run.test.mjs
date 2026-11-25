// The shipped CLI, through its default Node entry point, on a committed region: the point
// is that a real run writes the map and its sidecar records, not that a function returns.
// Aimed at the "entry point emits no records" defect (PL-1327): if cli.mjs stops writing
// the heightmap, its water map or the JSON the agent reads, this fails.
//
// The network is the captured asheville square in test/fixtures/cli-region-asheville,
// recorded from AWS Terrain Tiles and OpenFreeMap (see region.json and its README).
import test from "node:test";
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const started = promisify(execFile);
const root = new URL("../", import.meta.url);
const fixture = new URL("fixtures/cli-region-asheville/", import.meta.url);
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const json = async (path) => JSON.parse(await readFile(path, "utf8"));

test("the CLI writes a committed region's heightmap and records through its default Node entry point", { timeout: 180000 }, async () => {
  const out = await mkdtemp(join(tmpdir(), "r2s-cli-region-"));
  const log = join(out, "requests.log");
  try {
    const { stdout } = await started(process.execPath, [
      "--import", fileURLToPath(new URL("support/offline-region.mjs", import.meta.url)),
      fileURLToPath(new URL("cli.mjs", root)),
      "asheville", "--scale", "0.5", "--heightmap", "--out", out, "--json",
    ], { cwd: fileURLToPath(root), env: { ...process.env, CLI_REGION_FIXTURE: fileURLToPath(fixture), CLI_REGION_LOG: log } });

    const region = await json(new URL("region.json", fixture));
    const summary = JSON.parse(stdout);
    assert.equal(summary.name, "asheville");
    assert.equal(summary.kind, "heightmap", "the CLI summary does not name the heightmap it made");
    assert.equal(summary.installed, null);

    // The bytes a person gets, not just exit 0.
    for (const [name, digest] of Object.entries(region.outputs)) {
      assert.equal(sha(await readFile(join(out, name))), digest, `${name}: the CLI wrote different bytes than the captured run`);
    }
    const heights = await readFile(join(out, "asheville.png"));
    assert.equal(heights.readUInt32BE(16), 1081, "heightmap width");
    assert.equal(heights.readUInt32BE(20), 1081, "heightmap height");
    assert.equal(heights[24], 16, "heightmap bit depth");
    assert.equal(heights[25], 0, "heightmap colour type (greyscale)");

    // The records an agent passes on: the square, its relief and every water-source pin.
    const details = await json(join(out, "asheville.json"));
    assert.deepEqual(details.center, { lon: region.square.lon, lat: region.square.lat });
    assert.equal(details.scale, region.square.scale);
    assert.equal(details.heightmap.px, 1081);
    assert.equal(details.heightmap.bit_depth, 16);
    assert.ok(details.heights.real_max_m > details.heights.real_min_m, "the run found no relief");
    assert.equal(details.water.rivers_and_lakes_cut, true, "the run cut no rivers");
    assert.equal(details.elevation.source, "AWS Terrain Tiles (Terrarium)");
    assert.equal(details.water_sources.length, 5, "a pin is missing from the run's water sources");
    details.water_sources.forEach((source, index) => {
      assert.equal(source.pin, index + 1);
      assert.match(source.kind, /^(river entry|river exit|lake)$/, `pin ${source.pin} kind`);
      assert.ok(source.name.trim().length > 0, `pin ${source.pin} has no name`);
      assert.match(source.where, /edge, \d+% from the left|\d+% down from the top|\d+% from the left, \d+% down from the top/, `pin ${source.pin} has no place`);
      assert.ok(Number.isFinite(source.lon) && Number.isFinite(source.lat), `pin ${source.pin} has no coordinates`);
      assert.ok(Number.isFinite(source.ground_game_m), `pin ${source.pin} has no ground height`);
    });
    assert.ok(!JSON.stringify(details).includes("NaN"), "the run wrote NaN");

    // Every captured tile was replayed and nothing else was asked for, so the run proves the
    // whole region path: terrain, the basemap TileJSON and all water tiles.
    const served = (await readFile(log, "utf8")).trim().split("\n");
    assert.equal(new Set(served).size, served.length, "the CLI repeated a request");
    assert.equal(served.length, region.request_count, "the CLI used fewer captured responses than recorded");
    assert.deepEqual([...new Set(served.map((url) => new URL(url).host))].sort(), region.hosts);
  } finally {
    await rm(out, { recursive: true, force: true });
  }
});

import test from "node:test";
import assert from "node:assert/strict";
import { sampleCoordinates, canopyTile, collectRaster, collectRecords, growthForm } from "../vegetation-inputs.js";

test("equal-area sample centres honor rotation and real-ground scale", () => {
  const a = sampleCoordinates({ lon: 0, lat: 0, scale: 1, rotation: 0 }, 2);
  const b = sampleCoordinates({ lon: 0, lat: 0, scale: 2, rotation: 90 }, 2);
  assert.ok(a.lon[0] < 0 && a.lat[0] > 0);
  assert.ok(Math.abs(b.lon[0] + 2 * a.lon[0]) < 1e-10);
  assert.ok(Math.abs(b.lat[0] - 2 * a.lat[0]) < 1e-10);
  assert.equal(canopyTile(-82.555, 35.58), "0320030123");
});

function fakeCog({ mask = 1, maskPresent = true, value = 0 } = {}) {
  const image = { getWidth: () => 2, getHeight: () => 2, getResolution: () => [10000, -10000],
    getBoundingBox: () => [-10000, -10000, 10000, 10000], getGDALNoData: () => null,
    getFileDirectory: () => ({}), readRasters: async () => Uint8Array.from([value]) };
  const validity = { ...image, getFileDirectory: () => ({ NewSubfileType: 4 }), readRasters: async () => Uint8Array.from([mask]) };
  return async () => ({ getImageCount: async () => maskPresent ? 2 : 1, getImage: async (i) => i ? validity : image });
}
const sq = { lon: 0, lat: 0, rotation: 0, scale: 1 };
test("masked zero is missing; unmasked zero is genuinely open", async () => {
  const missing = await collectRaster(sq, "canopy", { fromUrl: fakeCog({ mask: 0 }), size: 1 });
  const open = await collectRaster(sq, "canopy", { fromUrl: fakeCog(), size: 1 });
  assert.deepEqual(missing.values, [null]);
  assert.deepEqual(open.values, [0]);
});
test("missing canopy mask cannot turn clouds into treeless land", async () => {
  const result = await collectRaster(sq, "canopy", { fromUrl: fakeCog({ maskPresent: false }), size: 1 });
  assert.deepEqual(result.values, [null]);
  assert.equal(result.tiles[0].status, "unavailable");
});
test("mixed and deciduous needleleaf genera are not assigned evergreen", () => {
  for (const genus of ["Quercus", "Magnolia", "Acer", "Larix", "Taxodium"]) assert.equal(growthForm(genus), "unknown");
  assert.equal(growthForm("Pinus"), "needleleaf_evergreen");
  assert.equal(growthForm("Quercus", { leaf_type: "broadleaved", leaf_cycle: "evergreen" }), "broadleaf_evergreen");
  assert.equal(growthForm("Acer", {}, "Acer platanoides 'Columnare'"), "broadleaf_deciduous");
  assert.equal(growthForm("Magnolia", {}, "Magnolia grandiflora"), "broadleaf_evergreen");
  assert.equal(growthForm("Magnolia", {}, "Magnolia virginiana"), "unknown");
});

const boston = { lon: -71.057, lat: 42.36, rotation: 0, scale: 1 };
const response = (body) => ({ ok: true, json: async () => body });
const bundledUrl = (name) => new URL(`../vegetation-data/${name}`, import.meta.url).href;

test("Node loads bundled planting and taxonomy data without a custom file fetcher", async () => {
  const requests = [];
  const fetchImpl = async (url, options) => {
    const request = new URL(url);
    assert.equal(request.protocol, "https:", "bundled files must be read by the default Node loader");
    assert.match(options.headers["User-Agent"], /Polli-Region-to-Skylines/);
    requests.push(request);
    if (request.hostname === "api.gbif.org") return response({ count: 1, results: request.searchParams.get("offset") === "0" ? [{
      key: "node-test", species: "Quercus rubra", genus: "Quercus", decimalLongitude: -71.057, decimalLatitude: 42.36,
      coordinateUncertaintyInMeters: 10, datasetKey: "constructed-test-data", license: "http://creativecommons.org/licenses/by/4.0/legalcode",
    }] : [] });
    assert.equal(request.hostname, "overpass-api.de");
    return response({ elements: [{ id: "node-test", lon: -71.057, lat: 42.36, tags: { genus: "Pinus", species: "Pinus strobus" } }] });
  };
  const result = await collectRecords(boston, { fetchImpl });
  assert.ok(result.records.filter((r) => r.kind === "inventory").length > 50000);
  assert.equal(result.records.find((r) => r.id === "boston:1")?.growth_form, "broadleaf_deciduous");
  assert.ok(result.records.some((r) => r.id === "gbif:node-test"), "bundled taxonomy must enable the tree occurrence query");
  assert.ok(result.records.some((r) => r.id === "osm:node/node-test"));
  assert.equal(requests.length, 5);
  assert.equal(result.sources.find((s) => s.source.startsWith("Boston Parks"))?.status, "available");
});

test("a missing inventory catalog is reported without hiding other composition sources", async () => {
  const result = await collectRecords(boston, {
    dataUrl: (name) => name === "inventories.json" ? bundledUrl("missing-inventories-node-test.json") : bundledUrl(name),
    fetchImpl: async (url) => response(new URL(url).hostname === "api.gbif.org" ? { count: 0, results: [] } : { elements: [] }),
  });
  const inventory = result.sources.find((s) => s.source === "Public tree inventory catalog");
  assert.equal(inventory?.status, "unavailable");
  assert.match(inventory.error, /ENOENT/);
  assert.equal(result.sources.find((s) => s.source === "GBIF occurrence API")?.status, "available");
});

test("a missing taxonomy catalog does not suppress the bundled planting inventory", async () => {
  const requests = [];
  const result = await collectRecords(boston, {
    dataUrl: (name) => name === "tree-taxa.json" ? bundledUrl("missing-taxonomy-node-test.json") : bundledUrl(name),
    fetchImpl: async (url) => { requests.push(new URL(url).hostname); return response({ elements: [] }); },
  });
  assert.ok(result.records.filter((r) => r.kind === "inventory").length > 50000);
  assert.deepEqual(requests, ["overpass-api.de"]);
  assert.equal(result.sources.find((s) => s.source === "GBIF occurrence API")?.status, "unavailable");
});

test("a cancelled Node collection stops before making HTTP requests", async () => {
  const controller = new AbortController(); controller.abort(new Error("square changed"));
  let requests = 0;
  await assert.rejects(collectRecords(boston, { signal: controller.signal,
    fetchImpl: async () => { requests++; return response({}); },
  }), /square changed/);
  assert.equal(requests, 0);
});

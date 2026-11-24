import test from "node:test";
import assert from "node:assert/strict";
import { sampleCoordinates, canopyTile, collectRaster, growthForm } from "../vegetation-inputs.js";

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

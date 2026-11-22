// Independent geographic vectors only: no elevation, fitting, carving or map export.
import { readFile, writeFile } from "node:fs/promises";
import { VectorTile } from "@mapbox/vector-tile";
import Pbf from "pbf";
import { basemapTile, basemapTiles } from "../../terrain.js";

const [planPath, outputPath] = process.argv.slice(2);
if (!planPath || !outputPath) throw new Error("Usage: capture_reference_shores.mjs PLAN.json NEW_OUTPUT.json");
const plan = JSON.parse(await readFile(planPath));
const z = 14, features = [], tiles = [];
for (let y = plan.tile_box.y0; y <= plan.tile_box.y1; y++) {
  for (let x = plan.tile_box.x0; x <= plan.tile_box.x1; x++) {
    const bytes = await basemapTile(z, x, y);
    if (!bytes) throw new Error(`Missing independent vector coverage: ${z}/${x}/${y}`);
    const tile = new VectorTile(new Pbf(bytes));
    tiles.push({ z, x, y });
    const layer = tile.layers.water;
    for (let i = 0; layer && i < layer.length; i++) {
      const feature = layer.feature(i).toGeoJSON(x, y, z);
      if (["Polygon", "MultiPolygon"].includes(feature.geometry.type)) features.push(feature);
    }
  }
}
await writeFile(outputPath, JSON.stringify({
  type: "FeatureCollection", features, tiles, source: await basemapTiles(),
  acquisition: "Independent OSM/OpenFreeMap water, projected later with pyproj/rasterio; no exporter mask reused",
}, null, 2) + "\n", { flag: "wx" });

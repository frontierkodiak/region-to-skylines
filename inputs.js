// The ready-to-play writer's inputs for a square: the heightmap, the geographic JSON it routes
// water and roads with, and the uncarved ground. It follows tools/map-factory/capture.js, the
// capture PL-857's reference maps were made from, with two changes so the page, other
// browsers and the CLI all get the same bytes: tiles are read in a fixed order, and ocean
// polygons are filled by pixel centre (fillMask, as the page fills lakes) instead of an
// antialiased canvas. No DOM, no canvas: the page and Node both run it.

import { VectorTile } from "@mapbox/vector-tile";
import Pbf from "pbf";
import { CS1, sampleElevation, smooth, fetchBasemapWater, basemapTile, carveWater, fitHeights, waterSources,
  encode16, png16, corners, lonLatToSquare, extentOf, fillMask, waterwayTags } from "./terrain.js";

/** The capture's own settings, which the reference maps were made with (the page's defaults). */
export const CAPTURE = { smoothing: 1, riverDepth: 10, riverHalfWidth: 40, lakeDepth: 4 };

/** Ocean polygons of one vector tile's water layer (capture-ocean.js oceanPolygons). */
function oceanPolygons(feature, tile) {
  if (feature.properties.class !== "ocean") return [];
  const geometry = feature.toGeoJSON(tile.x, tile.y, tile.z).geometry;
  if (!["Polygon", "MultiPolygon"].includes(geometry.type)) throw new Error(`water/ocean has unsupported geometry ${geometry.type}`);
  return (geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates)
    .map((rings) => ({ rings, properties: { ...feature.properties }, tile, featureId: feature.id ?? null }));
}

/** Open sea: every ocean polygon filled by pixel centre, holes even-odd, pieces unioned; null if none. */
export function oceanMask(polygons, sq) {
  if (!polygons.length) return null;
  const n = CS1.px, half = (n - 1) / 2, sp = extentOf(sq) / (n - 1);
  const toPx = ([lon, lat]) => { const [u, v] = lonLatToSquare(sq, lon, lat); return [u / sp + half + 0.5, half - v / sp + 0.5]; };
  const mask = fillMask(polygons.map((p) => p.rings.map((ring) => ring.map(toPx))), n);
  return mask.includes(1) ? mask : null;
}

const lines = (g) => g.type === "MultiLineString" ? g.coordinates : g.type === "LineString" ? [g.coordinates] : [];

/**
 * Everything the writer reads, for square `sq` ({lon, lat, rotation, scale, name, slug}).
 * Returns {png (16-bit PNG bytes), geometry (object), banks (Float32Array, rows north first),
 * game (Float32Array heights), seaLevel}.
 */
export async function captureInputs(sq, { signal, status = () => {}, about = {} } = {}) {
  status("Fetching terrain");
  const elevation = await sampleElevation(sq, { signal });
  const ground = smooth(elevation.heights, CAPTURE.smoothing);
  status("Fetching rivers, roads and coast");
  const water = await fetchBasemapWater(sq, signal);
  const z = water.zoom;
  const merc = ([lon, lat]) => [(lon + 180) / 360 * 2 ** z, (1 - Math.asinh(Math.tan(lat * Math.PI / 180)) / Math.PI) / 2 * 2 ** z];
  const pts = corners(sq).map(merc), jobs = [];
  for (let y = Math.floor(Math.min(...pts.map((p) => p[1]))); y <= Math.floor(Math.max(...pts.map((p) => p[1]))); y++)
    for (let x = Math.floor(Math.min(...pts.map((p) => p[0]))); x <= Math.floor(Math.max(...pts.map((p) => p[0]))); x++) jobs.push([x, y]);
  // read concurrently, then use the tiles in row order so the result never depends on timing
  const buffers = new Array(jobs.length), queue = jobs.map((_, k) => k);
  await Promise.all(Array.from({ length: 6 }, async () => {
    while (queue.length) { const k = queue.shift(); buffers[k] = await basemapTile(z, jobs[k][0], jobs[k][1], signal); }
  }));
  const roads = [], streams = [], oceans = [];
  jobs.forEach(([x, y], k) => {
    if (!buffers[k]) return; // missing tiles are unknown, never inferred sea
    const vt = new VectorTile(new Pbf(buffers[k])), tile = { x, y, z };
    for (let i = 0, L = vt.layers.water; L && i < L.length; i++) oceans.push(...oceanPolygons(L.feature(i), tile));
    for (let i = 0, L = vt.layers.waterway; L && i < L.length; i++) {
      const f = L.feature(i);
      if (f.properties.class !== "stream") continue;
      for (const p of lines(f.toGeoJSON(x, y, z).geometry)) streams.push({ name: f.properties.name || "", class: "stream", pts: p, ...waterwayTags(f.properties) });
    }
    for (let i = 0, L = vt.layers.transportation; L && i < L.length; i++) {
      const f = L.feature(i);
      if (!["motorway", "trunk", "rail"].includes(f.properties.class)) continue;
      for (const p of lines(f.toGeoJSON(x, y, z).geometry)) roads.push({ ...f.properties, pts: p });
    }
  });
  status("Shaping the terrain");
  const sea = oceanMask(oceans, sq);
  const carved = carveWater(ground, sq, water, { depth: CAPTURE.riverDepth, halfWidth: CAPTURE.riverHalfWidth, lakeDepth: CAPTURE.lakeDepth });
  const fit = fitHeights(ground, carved.heights, { sea });
  const sources = waterSources(sq, water, carved, fit);
  const uncarved = fitHeights(ground, ground, { sea, verticalScale: fit.verticalScale });
  const geometry = {
    sq: { name: sq.name, slug: sq.slug, lon: sq.lon, lat: sq.lat, rotation: sq.rotation, scale: sq.scale },
    ...water, streams, roads, oceans, sources, seaLevel: fit.seaLevel,
    fit: { base: fit.base, verticalScale: fit.verticalScale },
    provenance: {
      ...about, capture: "region-to-skylines inputs.js (tools/map-factory/capture.js order-stable, pixel-centre ocean)",
      elevation: { source: "AWS Terrain Tiles / Terrarium", zoom: elevation.zoom, tiles: elevation.tiles },
      water: "OpenFreeMap / OpenStreetMap", ocean: { polygons: oceans.length, cells: sea ? sea.reduce((a, b) => a + b, 0) : 0 },
    },
  };
  const png = new Uint8Array(await (await png16(encode16(fit.game), CS1.px, CS1.px)).arrayBuffer());
  return { png, geometry, banks: uncarved.game, game: fit.game, seaLevel: fit.seaLevel };
}

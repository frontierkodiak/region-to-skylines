import { tileName, worldCoverFile, LANDCOVER_S3 } from "./capability-evidence.js";
import { speciesGrowthForm, TRAIT_SOURCES } from "./vegetation-traits.js";

export const CANOPY_S3 = "https://dataforgood-fb-data.s3.us-east-1.amazonaws.com/forests/v2/global/dinov3_global_chm_v2_ml3/chm/";
export const FOREST_TYPES_URL = "https://zenodo.org/api/records/3939050/files/PROBAV_LC100_global_v3.0.1_2019-nrt_Forest-Type-layer_EPSG-4326.tif/content";
const RAD = Math.PI / 180;
const IS_NODE = Boolean(globalThis.process?.versions?.node);
const PROJECT_USER_AGENT = "Polli-Region-to-Skylines/vegetation (https://github.com/frontierkodiak/region-to-skylines)";
const timeout = (signal) => signal ? AbortSignal.any([signal, AbortSignal.timeout(45000)]) : AbortSignal.timeout(45000);

/** Equal-area sample centres in the export's rotated frame, in real metres. */
export function sampleCoordinates(sq, size) {
  const side = 17280 * sq.scale, a = 6378137, e2 = 0.00669437999014;
  const w = 1 - e2 * Math.sin(sq.lat * RAD) ** 2;
  const m = a * (1 - e2) / w ** 1.5, nc = a / Math.sqrt(w) * Math.cos(sq.lat * RAD);
  const t = sq.rotation * RAD, lon = new Float64Array(size ** 2), lat = new Float64Array(size ** 2);
  for (let r = 0; r < size; r++) for (let c = 0; c < size; c++) {
    const x = ((c + 0.5) / size - 0.5) * side, z = (0.5 - (r + 0.5) / size) * side, i = r * size + c;
    lon[i] = sq.lon + (x * Math.cos(t) + z * Math.sin(t)) / nc / RAD;
    lat[i] = sq.lat + (-x * Math.sin(t) + z * Math.cos(t)) / m / RAD;
  }
  return { lon, lat };
}

export function canopyTile(lon, lat) {
  const x = Math.max(0, Math.min(1023, Math.floor((lon + 180) / 360 * 1024)));
  const y = Math.max(0, Math.min(1023, Math.floor((1 - Math.asinh(Math.tan(lat * RAD)) / Math.PI) / 2 * 1024)));
  let key = "";
  for (let bit = 9; bit >= 0; bit--) key += ((x >> bit) & 1) + 2 * ((y >> bit) & 1);
  return key;
}

/** Bounded COG reads, retaining the actual overview resolution and missing tiles. */
export async function collectRaster(sq, kind, { fromUrl, size = 432, signal, canopyUrl = (k) => CANOPY_S3 + k + ".tif", coverUrl = (k) => LANDCOVER_S3 + worldCoverFile(k), forestUrl = FOREST_TYPES_URL } = {}) {
  const { lon, lat } = sampleCoordinates(sq, size), canopy = kind === "canopy";
  const groups = new Map(), values = new Array(size ** 2).fill(null), receipts = [];
  for (let i = 0; i < lon.length; i++) {
    const tile = canopy ? canopyTile(lon[i], lat[i]) : kind === "forest" ? "global" : tileName(lat[i], lon[i]);
    if (!groups.has(tile)) groups.set(tile, []);
    groups.get(tile).push(i);
  }
  // Two simultaneous files limit browser memory and upstream range requests.
  const jobs = [...groups];
  async function read() {
    while (jobs.length) {
      const [tile, indices] = jobs.shift(), url = canopy ? canopyUrl(tile) : kind === "forest" ? forestUrl : coverUrl(tile);
      signal?.throwIfAborted();
      try {
        const headers = kind === "forest" && IS_NODE ? { "User-Agent": PROJECT_USER_AGENT } : undefined;
        const tiff = await fromUrl(url, { allowFullFile: false, headers }, signal);
        const base = await tiff.getImage(0), count = await tiff.getImageCount();
        const xs = [], ys = [], bounds = [Infinity, Infinity, -Infinity, -Infinity];
        for (const i of indices) {
          const x = canopy ? 6378137 * lon[i] * RAD : lon[i];
          const y = canopy ? 6378137 * Math.asinh(Math.tan(lat[i] * RAD)) : lat[i];
          xs.push(x); ys.push(y);
          bounds[0] = Math.min(bounds[0], x); bounds[1] = Math.min(bounds[1], y);
          bounds[2] = Math.max(bounds[2], x); bounds[3] = Math.max(bounds[3], y);
        }
        let chosen;
        // Select the finest bounded window. Do not request a full 32768² COG.
        for (let j = 0; j < count; j++) {
          const image = await tiff.getImage(j);
          if ((image.getFileDirectory().NewSubfileType ?? 0) & 4) continue; // internal validity mask
          const [dx, dy] = image.getResolution(base), [left, , , top] = base.getBoundingBox();
          const window = [Math.max(0, Math.floor((bounds[0] - left) / dx)), Math.max(0, Math.floor((bounds[3] - top) / dy)),
            Math.min(image.getWidth(), Math.floor((bounds[2] - left) / dx) + 1), Math.min(image.getHeight(), Math.floor((bounds[1] - top) / dy) + 1)];
          if ((window[2] - window[0]) * (window[3] - window[1]) <= 1048576) { chosen = { image, dx, dy, left, top, window, overview: j }; break; }
        }
        if (!chosen) throw new Error("No bounded overview");
        const { image, dx, dy, left, top, window, overview } = chosen;
        const raster = await image.readRasters({ window, samples: [0], interleave: true, signal });
        let mask = null;
        if (canopy) {
          for (let j = 0; j < count; j++) {
            const candidate = await tiff.getImage(j);
            if (((candidate.getFileDirectory().NewSubfileType ?? 0) & 4) && candidate.getWidth() === image.getWidth() && candidate.getHeight() === image.getHeight()) {
              mask = await candidate.readRasters({ window, samples: [0], interleave: true, signal }); break;
            }
          }
          if (!mask) throw new Error("Canopy validity mask missing");
        }
        const nodata = image.getGDALNoData(), width = window[2] - window[0];
        let valid = 0;
        for (let k = 0; k < indices.length; k++) {
          const col = Math.floor((xs[k] - left) / dx) - window[0], row = Math.floor((ys[k] - top) / dy) - window[1];
          if (col < 0 || row < 0 || col >= width || row >= window[3] - window[1]) continue;
          const offset = row * width + col, v = raster[offset];
          if (!Number.isFinite(v) || v === nodata || (canopy ? v === 255 || !mask[offset] : v === 0)) continue;
          values[indices[k]] = v; valid++;
        }
        receipts.push({ tile, url, status: "available", overview, pixel_m: canopy ? Math.abs(dx) * Math.cos(sq.lat * RAD) : Math.abs(dx) * 111320 * Math.cos(sq.lat * RAD), valid });
      } catch (error) {
        signal?.throwIfAborted();
        receipts.push({ tile, url, status: "unavailable", error: String(error.message) });
      }
    }
  }
  await Promise.all([read(), read()]);
  return { values, tiles: receipts.sort((a, b) => a.tile.localeCompare(b.tile)), sample_m: 17280 * sq.scale / size,
    status: receipts.every((r) => r.status === "available") ? "available" : receipts.some((r) => r.status === "available") ? "partial" : "unavailable",
    source: canopy ? "Meta/WRI CHMv2 2026 · CC BY 4.0" : kind === "forest" ? "Copernicus Global Land Service forest type 2019 v3.0.1 · CC BY 4.0" : "ESA WorldCover 2021 v200 · CC BY 4.0",
    height_basis: canopy ? "Top-of-canopy area samples; COG overview pixels, not individual-tree heights" : undefined };
}

async function json(url, { signal, fetchImpl = fetch } = {}) {
  const requestSignal = signal ? AbortSignal.any([signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000);
  requestSignal.throwIfAborted();
  if (IS_NODE && String(url).startsWith("file:")) {
    const { readFile } = await import("node:fs/promises");
    return JSON.parse(await readFile(new URL(url), { encoding: "utf8", signal: requestSignal }));
  }
  const headers = IS_NODE ? { "User-Agent": PROJECT_USER_AGENT } : undefined;
  const response = await fetchImpl(url, { signal: requestSignal, headers });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function boundsOf(sq, padding = 0) {
  const reach = 8640 * sq.scale * Math.SQRT2 + padding;
  return [sq.lat - reach / 110500, sq.lon - reach / (111320 * Math.cos(sq.lat * RAD)),
    sq.lat + reach / 110500, sq.lon + reach / (111320 * Math.cos(sq.lat * RAD))];
}
const overlaps = (a, b) => a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1];

async function ashevilleInventory(entry, options) {
  const records = [];
  for (let offset = 0; offset < 10000; offset += 1000) {
    const params = new URLSearchParams({ where: "1=1", outFields: "objectid,genus,species,date_removed,lifecyclestatus", outSR: "4326", f: "geojson", resultOffset: offset, resultRecordCount: 1000, orderByFields: "objectid" });
    const page = await json(`${entry.api}/query?${params}`, options);
    if (!Array.isArray(page.features)) throw new Error("Inventory response has no features");
    for (const f of page.features) {
      const p = f.properties, point = f.geometry?.coordinates;
      if (p.date_removed || !["Active", null, undefined].includes(p.lifecyclestatus) || !point) continue;
      const genus = String(p.genus ?? "").trim().split(/\s+/)[0];
      if (!/^[A-Z][a-z]+$/.test(genus) || ["Unknown", "Vacant", "Stump"].includes(genus)) continue;
      const species = String(p.genus).includes(" ") ? String(p.genus).trim() : `${genus} ${p.species ?? ""}`.trim();
      records.push({ id: `asheville:${p.objectid}`, lon: point[0], lat: point[1], genus, species });
    }
    if (page.features.length < 1000) return records;
  }
  throw new Error("Inventory exceeds bounded acquisition; coverage unknown");
}

/** Genus-level leaf habit is deliberately sparse; mixed genera stay unknown. */
export function growthForm(genus, tags = {}, species) {
  if (["Sabal", "Cocos", "Roystonea", "Syagrus", "Phoenix", "Euterpe", "Washingtonia", "Archontophoenix", "Butia"].includes(genus)) return "palm";
  if (tags.leaf_type === "needleleaved" && tags.leaf_cycle === "deciduous") return "unknown";
  if (tags.leaf_type === "needleleaved" && tags.leaf_cycle === "evergreen") return "needleleaf_evergreen";
  if (tags.leaf_type === "broadleaved" && tags.leaf_cycle === "deciduous") return "broadleaf_deciduous";
  if (tags.leaf_type === "broadleaved" && tags.leaf_cycle === "evergreen") return "broadleaf_evergreen";
  const trait = speciesGrowthForm(species);
  if (trait) return trait;
  if (["Pinus", "Picea", "Abies", "Tsuga", "Pseudotsuga", "Cedrus", "Cupressus", "Juniperus", "Thuja", "Araucaria"].includes(genus)) return "needleleaf_evergreen";
  if (["Betula", "Fagus", "Liriodendron", "Populus", "Carya", "Ginkgo"].includes(genus)) return "broadleaf_deciduous";
  return "unknown";
}

/** Local planting inventories take precedence where present, not a native-range prior. */
export async function collectRecords(sq, { signal, fetchImpl = fetch, dataUrl = (f) => new URL(`./vegetation-data/${f}`, import.meta.url).href } = {}) {
  const box = boundsOf(sq, 2000), records = [], sources = [];
  const options = { signal, fetchImpl };
  const catalogUrl = dataUrl("tree-taxa.json"), inventoryUrl = dataUrl("inventories.json");
  const [catalogResult, inventoryResult] = await Promise.allSettled([json(catalogUrl, options), json(inventoryUrl, options)]);
  signal?.throwIfAborted();
  if (inventoryResult.status === "rejected") sources.push({ source: "Public tree inventory catalog", url: inventoryUrl,
    status: "unavailable", error: String(inventoryResult.reason?.message ?? inventoryResult.reason) });
  const catalog = catalogResult.status === "fulfilled" ? catalogResult.value : null;
  const species = new Set(catalog?.species ?? []);
  const inventories = inventoryResult.status === "fulfilled" ? inventoryResult.value : [];
  await Promise.all(inventories.filter((v) => overlaps(box, v.bounds)).map(async (entry) => {
    try {
      const data = entry.api ? await ashevilleInventory(entry, options) : await json(dataUrl(entry.file), options);
      const rows = data.records ?? data;
      for (const raw of rows) {
        const r = Array.isArray(raw) ? { id: raw[0], lon: raw[1], lat: raw[2], genus: raw[3], species: raw[4] } : raw;
        records.push({ ...r, source: entry.source, kind: "inventory", growth_form: r.growth_form ?? growthForm(r.genus, {}, r.species) });
      }
      sources.push({ ...entry, status: "available", records: rows.length });
    } catch (error) { signal?.throwIfAborted(); sources.push({ ...entry, status: "unavailable", error: error.message }); }
  }));
  const polygon = `POLYGON((${box[1]} ${box[0]},${box[3]} ${box[0]},${box[3]} ${box[2]},${box[1]} ${box[2]},${box[1]} ${box[0]}))`;
  // GBIF's paged response is explicitly a capped occurrence sample, not a census.
  if (catalog) {
    const params = new URLSearchParams({ taxonKey: "6", geometry: polygon, hasCoordinate: "true", hasGeospatialIssue: "false", year: "2000,2026", coordinateUncertaintyInMeters: "0,200", limit: "300" });
    params.append("license", "CC0_1_0"); params.append("license", "CC_BY_4_0");
    const urls = [0, 300, 600, 900].map((offset) => `https://api.gbif.org/v1/occurrence/search?${params}&offset=${offset}`);
    const pages = await Promise.allSettled(urls.map((url) => json(url, options)));
    let seen = 0, total = null;
    for (let p = 0; p < pages.length; p++) {
      if (pages[p].status !== "fulfilled") continue;
      const page = pages[p].value; total = page.count; seen += page.results.length;
      for (const r of page.results) {
        if (!species.has(r.species) || !["http://creativecommons.org/licenses/by/4.0/legalcode", "http://creativecommons.org/publicdomain/zero/1.0/legalcode"].includes(r.license)) continue;
        if (r.coordinateUncertaintyInMeters != null && r.coordinateUncertaintyInMeters > 200) continue;
        records.push({ id: `gbif:${r.key}`, lon: r.decimalLongitude, lat: r.decimalLatitude, genus: r.genus,
          species: r.species, growth_form: growthForm(r.genus, {}, r.species), kind: "occurrence", source: `GBIF ${r.datasetKey}`, license: r.license });
      }
    }
    sources.push({ source: "GBIF occurrence API", urls, status: pages.some((p) => p.status === "fulfilled") ? "available" : "unavailable", total_plant_records: total, examined: seen, truncated: total > seen, tree_filter: catalog.source,
      estimand: "Spatially weighted tree-species occurrence records, not stem or canopy abundance" });
  } else sources.push({ source: "GBIF occurrence API", status: "unavailable", error: "Tree taxonomy catalog unavailable" });
  const query = `[out:json][timeout:20];node[natural=tree](${box.join(",")});out tags center;`;
  const osmUrl = `https://overpass-api.de/api/interpreter?data=${encodeURIComponent(query)}`;
  try {
    const osm = await json(osmUrl, options);
    for (const r of osm.elements ?? []) {
      const genus = r.tags?.genus || r.tags?.["genus:en"] || r.tags?.species?.split(" ")[0];
      if (!/^[A-Z][a-z]+$/.test(genus ?? "")) continue;
      records.push({ id: `osm:node/${r.id}`, lon: r.lon, lat: r.lat, genus, species: r.tags.species,
        growth_form: growthForm(genus, r.tags, r.tags.species), kind: "osm", source: "OpenStreetMap contributors · ODbL" });
    }
    sources.push({ source: "OpenStreetMap contributors · ODbL", url: osmUrl, status: "available", mapped_trees: osm.elements?.length ?? 0 });
  } catch (error) { signal?.throwIfAborted(); sources.push({ source: "OpenStreetMap contributors · ODbL", status: "unavailable", error: error.message }); }
  const unique = [...new Map(records.filter((r) => Number.isFinite(r.lon) && Number.isFinite(r.lat)).map((r) => [r.id, r])).values()];
  return { records: unique, sources: [...sources, { source: "NC State Extension leaf-habit profiles", traits: TRAIT_SOURCES }] };
}

/** One entry point, usable in both the browser worker and a Node batch. */
export async function vegetationExpectation(square, { fromUrl, signal, size = 432, cellSize = 160, recordEvidence, ...options } = {}) {
  const sq = { rotation: 0, scale: 1, ...square };
  if (![sq.lon, sq.lat, sq.rotation, sq.scale].every(Number.isFinite) || Math.abs(sq.lat) > 85 || Math.abs(sq.lon) > 180 || sq.scale < 0.5 || sq.scale > 2) throw new Error("Square outside exporter bounds");
  const boundedSignal = timeout(signal);
  const [height, cover, forest, points] = await Promise.all([
    collectRaster(sq, "canopy", { fromUrl, size, signal: boundedSignal, ...options }),
    collectRaster(sq, "landcover", { fromUrl, size, signal: boundedSignal, ...options }),
    collectRaster(sq, "forest", { fromUrl, size, signal: boundedSignal, ...options }),
    recordEvidence ?? collectRecords(sq, { signal: boundedSignal, ...options }),
  ]);
  const { expectation } = await import("./vegetation-model.js");
  return expectation(sq, { structure: { size, heights: height.values, landcover: cover.values, forest_types: forest.values, forest_type_source: forest.source, sample_m: height.sample_m, source: height.source, landcover_source: cover.source },
    records: points.records, sources: [height, cover, forest, ...points.sources].map(({ values, ...receipt }) => receipt) }, { cellSize });
}

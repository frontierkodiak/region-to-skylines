// Pan-time place evidence: land cover from the ESA WorldCover COG and recorded
// deposits from USGS MRDS. Acquisition only; the deterministic model is
// capability-model.js:placeCapabilities. Both cores read the same normalized
// place block, so nothing here decides a level.
//
// This reads the same 271-node (64 m) lattice as the capability grid: node
// (r, c) sits at game metres x = (c - 135) * 64, z = (135 - r) * 64. It is not
// the map writer: no CRP, no preparation, no tree plan.
import { squareToLonLat } from "./terrain.js";
import { roundTo } from "./capability-model.js";

/** The capability grid's lattice, and the WorldCover document the writer uses. */
export const PLACE_GRID = { size: 271, spacing_m: 64 };
export const LANDCOVER_S3 = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/";
export const worldCoverFile = (tile) => `ESA_WorldCover_10m_2021_v200_${tile}_Map.tif`;
export const LANDCOVER_SOURCE = "ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium";
/** One overview read per WorldCover tile; the finest bounded read wins. */
export const LANDCOVER_PIXEL_CAP = 262144;

export const MRDS = "https://mrdata.usgs.gov/mrds/search-bbox.php?xmin={w}&ymin={s}&xmax={e}&ymax={n}&format=xml";
export const MRDS_SOURCE = "USGS MRDS (public domain)";
const DEPOSIT_WEIGHT = { Producer: 1.0, "Past Producer": 0.8, Prospect: 0.35 };
const OIL = new Set(["OIL", "GAS", "PETROLEUM", "NATURAL GAS"]);
const RAD = Math.PI / 180;

/** WorldCover's 3-degree tile name, as landcover.py:tile_name writes it. */
export function tileName(lat, lon) {
  const la = 3 * Math.floor(lat / 3), lo = 3 * Math.floor(lon / 3);
  return `${la >= 0 ? "N" : "S"}${String(Math.abs(la)).padStart(2, "0")}${lo >= 0 ? "E" : "W"}${String(Math.abs(lo)).padStart(3, "0")}`;
}

/** The MSDS bounding box evidence.py uses: the square's circumscribed reach. */
export function depositBounds(sq) {
  const reach = 8640 * Math.SQRT2 * sq.scale;
  const dlat = reach / 111000, dlon = reach / (111320 * Math.cos(sq.lat * RAD));
  return [sq.lat - dlat, sq.lon - dlon, sq.lat + dlat, sq.lon + dlon];
}

export function mrdsUrl(sq) {
  const [s, w, n, e] = depositBounds(sq);
  return MRDS.replace("{s}", s).replace("{w}", w).replace("{n}", n).replace("{e}", e);
}

/** Game metres from WGS84, the inverse of prepare.pixel, as evidence.game_xz. */
export function gameXZ(sq, lon, lat) {
  const a = 6378137, e2 = 0.00669437999014, w = 1 - e2 * Math.sin(sq.lat * RAD) ** 2;
  const m = (a * (1 - e2)) / w ** 1.5, nc = (a / Math.sqrt(w)) * Math.cos(sq.lat * RAD);
  const east = (lon - sq.lon) * RAD * nc, north = (lat - sq.lat) * RAD * m;
  const t = sq.rotation * RAD;
  return [(east * Math.cos(t) - north * Math.sin(t)) / sq.scale, (east * Math.sin(t) + north * Math.cos(t)) / sq.scale];
}

const unescapeXml = (text) => text.replace(/&(amp|lt|gt|quot|apos|#\d+|#x[0-9a-f]+);/gi, (_, code) => {
  const named = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'" }[code.toLowerCase()];
  if (named) return named;
  return String.fromCodePoint(code[1].toLowerCase() === "x" ? parseInt(code.slice(2), 16) : Number(code.slice(1)));
});
const attributes = (text) => Object.fromEntries([...text.matchAll(/([\w:.-]+)\s*=\s*"([^"]*)"/g)].map(([, key, value]) => [key, unescapeXml(value)]));

/**
 * MRDS records as evidence.py:parse writes them, from the search-bbox XML the
 * browser also fetches for a download. Producers count, prospects a little,
 * processing plants not at all, and anything outside the square is dropped.
 */
export function parseMrdsXml(xml, sq) {
  const out = [];
  for (const [, open, body] of xml.matchAll(/<record\b([^>]*)>([\s\S]*?)<\/record>/g)) {
    const record = attributes(open), weight = DEPOSIT_WEIGHT[record.dev_stat];
    if (!weight) continue;
    const deposit = body.match(/<deposits\b([^>]*)/);
    const operation = deposit ? attributes(deposit[1]).oper_tp ?? "" : "";
    if (operation === "Processing Plant") continue;
    const commodities = new Set([...body.matchAll(/<commodity\b([^>]*)/g)].flatMap(([, attrs]) => {
      const value = attributes(attrs).value;
      return value ? [value.toUpperCase()] : [];
    }));
    for (const code of (record.code_list ?? "").split(/\s+/)) if (code) commodities.add(code.toUpperCase());
    const [x, z] = gameXZ(sq, Number(record.x), Number(record.y));
    if (!Number.isFinite(x) || !Number.isFinite(z) || Math.max(Math.abs(x), Math.abs(z)) > 8640) continue;
    out.push({
      kind: [...commodities].some((value) => OIL.has(value)) ? "oil" : "ore",
      x: roundTo(x, 1), z: roundTo(z, 1), weight,
      source: `USGS MRDS ${record.dep_id} ${record.site_name} (${record.dev_stat}, ${operation || "unknown"})`,
    });
  }
  return out;
}

/** One bbox query; a failure is unavailable evidence, never absence. */
export async function requestDeposits(sq, { signal, fetchImpl = fetch } = {}) {
  try {
    const response = await fetchImpl(mrdsUrl(sq), { signal });
    if (!response.ok) return { status: "unavailable", source: MRDS_SOURCE, records: [] };
    return { status: "available", source: MRDS_SOURCE, records: parseMrdsXml(await response.text(), sq) };
  } catch (error) {
    if (signal?.aborted) throw error;
    return { status: "unavailable", source: MRDS_SOURCE, records: [] };
  }
}

/** Every lattice node's longitude and latitude, in the writer's own frame. */
export function latticeLonLat(sq, size = PLACE_GRID.size) {
  const half = ((size - 1) * PLACE_GRID.spacing_m) / 2;
  const lon = new Float64Array(size * size), lat = new Float64Array(size * size);
  for (let r = 0; r < size; r++) for (let c = 0; c < size; c++) {
    const [lo, la] = squareToLonLat(sq, (c * PLACE_GRID.spacing_m - half) * sq.scale, (half - r * PLACE_GRID.spacing_m) * sq.scale);
    lon[r * size + c] = lo; lat[r * size + c] = la;
  }
  return { lon, lat };
}

/**
 * The square's WorldCover classes at the capability lattice.
 *
 * Each intersecting 3-degree tile is read once, from the finest overview whose
 * window stays under LANDCOVER_PIXEL_CAP pixels, then the lattice nodes are
 * indexed into it. The chosen overview's cell size travels with the result, so
 * a coarse read never passes as the 10 m document. A tile that does not exist
 * (open ocean) or fails leaves its nodes at class 0, no data.
 */
export async function collectLandcover(sq, { fromUrl, tileUrl, signal, size = PLACE_GRID.size } = {}) {
  const { lon, lat } = latticeLonLat(sq, size);
  const values = new Uint8Array(size * size);
  const used = [];
  let sample = 0;
  for (const tile of [...new Set(Array.from(lon, (value, i) => tileName(lat[i], value)))].sort()) {
    if (signal?.aborted) throw signal.reason;
    let tiff;
    try { tiff = await fromUrl(tileUrl(tile), { allowFullFile: false }, signal); }
    catch (error) { if (signal?.aborted) throw error; continue; }
    const count = await tiff.getImageCount(), base = await tiff.getImage(0);
    const [resX, resY] = base.getResolution(), [left, , , top] = base.getBoundingBox(), [width, height] = [base.getWidth(), base.getHeight()];
    const [stepLon, stepLat] = [Math.abs(resX), Math.abs(resY)], [right, bottom] = [left + stepLon * width, top - stepLat * height];
    const inside = [];
    for (let i = 0; i < lon.length; i++) {
      const [lo, la] = [lon[i], lat[i]];
      if (lo >= left && lo < right && la > bottom && la <= top) inside.push(i);
    }
    if (!inside.length) continue;
    let [minLon, maxLon, minLat, maxLat] = [Infinity, -Infinity, Infinity, -Infinity];
    for (const i of inside) { minLon = Math.min(minLon, lon[i]); maxLon = Math.max(maxLon, lon[i]); minLat = Math.min(minLat, lat[i]); maxLat = Math.max(maxLat, lat[i]); }
    let chosen = null;
    for (let k = 1; k < count; k++) {
      const image = await tiff.getImage(k), scale = width / image.getWidth();
      const stepX = stepLon * scale, stepY = stepLat * scale;
      const cols = Math.ceil((maxLon - minLon) / stepX) + 3, rows = Math.ceil((maxLat - minLat) / stepY) + 3;
      chosen = { image, stepX, stepY, pixels: Math.max(cols, 0) * Math.max(rows, 0) };
      if (chosen.pixels <= LANDCOVER_PIXEL_CAP) break;
    }
    if (!chosen) continue;
    const { image, stepX, stepY } = chosen;
    const col0 = Math.max(0, Math.floor((minLon - left) / stepX) - 1), row0 = Math.max(0, Math.floor((top - maxLat) / stepY) - 1);
    const col1 = Math.min(image.getWidth(), Math.ceil((maxLon - left) / stepX) + 2), row1 = Math.min(image.getHeight(), Math.ceil((top - minLat) / stepY) + 2);
    const [block] = await image.readRasters({ window: [col0, row0, col1, row1], samples: [0], signal });
    const width2 = Math.max(0, col1 - col0);
    if (width2 <= 0 || !block.length) continue;
    for (const i of inside) {
      const col = Math.floor((lon[i] - left) / stepX) - col0, row = Math.floor((top - lat[i]) / stepY) - row0;
      if (row >= 0 && row < Math.floor(block.length / width2) && col >= 0 && col < width2) values[i] = block[row * width2 + col];
    }
    used.push(tile);
    sample = Math.max(sample, Math.max(stepX * 111320 * Math.cos(sq.lat * RAD), stepY * 110574));
  }
  return {
    status: used.length ? "available" : "unavailable",
    source: LANDCOVER_SOURCE,
    fidelity: "pan_time_worldcover_overview",
    cell_m: 10,
    sample_m: sample ? roundTo(sample, 1) : null,
    tiles: used,
    values: Array.from(values),
  };
}

/** Land cover in a bounded worker; null when it cannot be read or is aborted. */
export function requestLandcover(sq, { signal } = {}) {
  if (typeof Worker === "undefined") return Promise.resolve(null);
  return new Promise((resolve) => {
    const worker = new Worker(new URL("./capability-evidence-worker.js", import.meta.url), { type: "module" });
    const finish = (value) => { signal?.removeEventListener("abort", abort); worker.terminate(); resolve(value); };
    const abort = () => finish(null);
    signal?.addEventListener("abort", abort, { once: true });
    worker.onmessage = ({ data }) => finish(data?.error ? null : { ...data.landcover, values: Array.from(new Uint8Array(data.values)) });
    worker.onerror = () => finish(null);
    worker.postMessage({ square: { lon: sq.lon, lat: sq.lat, rotation: sq.rotation, scale: sq.scale } });
  });
}

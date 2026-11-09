// Real terrain -> Cities: Skylines 1 heightmap, entirely in the browser.
// Sample a 1081 px square, burn OSM rivers in with a (1 - (d/w)^2)^2 profile, shift the
// lowest ground to `floor` metres, and encode 0..65535 = 0..1024 m.

import { VectorTile } from "https://cdn.jsdelivr.net/npm/@mapbox/vector-tile@2.0.3/+esm";
import Pbf from "https://cdn.jsdelivr.net/npm/pbf@4.0.1/+esm";

export const CS1 = { px: 1081, extent: 17280, maxHeight: 1024 };
// WGS84 radii of curvature at the square's centre: metres per radian north (M) and east (N cos lat).
const radii = (latDeg) => {
  const a = 6378137, e2 = 0.00669437999014, s = Math.sin((latDeg * Math.PI) / 180);
  const w = 1 - e2 * s * s;
  return [(a * (1 - e2)) / w ** 1.5, (a / Math.sqrt(w)) * Math.cos((latDeg * Math.PI) / 180)];
};
const TERRARIUM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";
// Public Overpass instances, used only when the user asks to refine the water with live OSM
// data, one at a time. Both say "feel free to use our service in any project". The FOSSGIS main
// instance is left out: it is overloaded, counts all of an app's users together, and asks apps on
// fast-deployment hosting not to use it. (OSM wiki, Overpass API, public instances; read 2026-11-09.)
export const OVERPASS = [
  "https://overpass.private.coffee/api/interpreter",
  "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
];

// ---------------------------------------------------------------- square geometry

/** Square frame: u east, v north (metres) before rotation; rotation is clockwise degrees. */
export function squareToLonLat(sq, u, v) {
  const t = (sq.rotation * Math.PI) / 180;
  const x = u * Math.cos(t) + v * Math.sin(t);
  const y = -u * Math.sin(t) + v * Math.cos(t);
  const [M, Nc] = radii(sq.lat);
  const lat = sq.lat + (y / M) * (180 / Math.PI);
  const lon = sq.lon + (x / Nc) * (180 / Math.PI);
  return [lon, lat];
}

export function lonLatToSquare(sq, lon, lat) {
  const [M, Nc] = radii(sq.lat);
  const x = (((lon - sq.lon) * Math.PI) / 180) * Nc;
  const y = (((lat - sq.lat) * Math.PI) / 180) * M;
  const t = (sq.rotation * Math.PI) / 180;
  return [x * Math.cos(t) - y * Math.sin(t), x * Math.sin(t) + y * Math.cos(t)];
}

export function extentOf(sq) {
  return CS1.extent * sq.scale;
}

/** Corners (lon, lat) of the square, or of a centred sub-square `frac` of its size. */
export function corners(sq, frac = 1) {
  const h = (extentOf(sq) / 2) * frac;
  return [[-h, h], [h, h], [h, -h], [-h, -h], [-h, h]].map(([u, v]) => squareToLonLat(sq, u, v));
}

function bbox(sq, padM = 0) {
  const h = extentOf(sq) / 2 + padM;
  const pts = [[-h, h], [h, h], [h, -h], [-h, -h]].map(([u, v]) => squareToLonLat(sq, u, v));
  const lons = pts.map((p) => p[0]), lats = pts.map((p) => p[1]);
  return [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)];
}

// ---------------------------------------------------------------- elevation

const merc = (lon, lat, z) => {
  const n = 256 * 2 ** z;
  const s = Math.sin((lat * Math.PI) / 180);
  return [((lon + 180) / 360) * n, (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * n];
};

/** Smallest Terrarium zoom whose pixels are no coarser than the map's. */
export function pickZoom(sq) {
  const spacing = extentOf(sq) / (CS1.px - 1);
  const ground = 156543.034 * Math.cos((sq.lat * Math.PI) / 180);
  return Math.max(8, Math.min(14, Math.ceil(Math.log2(ground / spacing))));
}

const tileCache = new Map();

async function fetchTile(z, x, y, signal) {
  const key = `${z}/${x}/${y}`;
  if (tileCache.has(key)) return tileCache.get(key);
  const url = TERRARIUM.replace("{z}", z).replace("{x}", x).replace("{y}", y);
  let lastErr;
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      const r = await fetch(url, { signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(20000)]) : AbortSignal.timeout(20000), mode: "cors" });
      if (!r.ok) throw new Error(`tile ${key}: HTTP ${r.status}`);
      const bmp = await createImageBitmap(await r.blob(), {
        colorSpaceConversion: "none",
        premultiplyAlpha: "none",
      });
      const c = new OffscreenCanvas(256, 256);
      const g = c.getContext("2d", { willReadFrequently: true });
      g.drawImage(bmp, 0, 0);
      const d = g.getImageData(0, 0, 256, 256).data;
      const h = new Float32Array(256 * 256);
      for (let i = 0; i < h.length; i++) h[i] = d[4 * i] * 256 + d[4 * i + 1] + d[4 * i + 2] / 256 - 32768;
      if (tileCache.size > 600) tileCache.delete(tileCache.keys().next().value);
      tileCache.set(key, h);
      return h;
    } catch (e) {
      if (signal?.aborted) throw e;
      lastErr = e;
      await new Promise((res) => setTimeout(res, 400 * 2 ** attempt));
    }
  }
  throw lastErr;
}

/** Fetch the Terrarium tiles under the square and sample a 1081 x 1081 grid (row 0 = top edge). */
export async function sampleElevation(sq, { signal, onProgress } = {}) {
  const z = pickZoom(sq);
  const [w, s, e, n] = bbox(sq, 200);
  const [x0, y0] = merc(w, n, z).map((v) => Math.floor(v / 256));
  const [x1, y1] = merc(e, s, z).map((v) => Math.floor(v / 256));
  const nx = x1 - x0 + 1, ny = y1 - y0 + 1;
  const W = nx * 256, H = ny * 256;
  const mosaic = new Float32Array(W * H);
  const jobs = [];
  for (let ty = y0; ty <= y1; ty++) for (let tx = x0; tx <= x1; tx++) jobs.push([tx, ty]);
  let done = 0;
  const worker = async () => {
    while (jobs.length) {
      const [tx, ty] = jobs.shift();
      const t = await fetchTile(z, tx, ty, signal);
      const ox = (tx - x0) * 256, oy = (ty - y0) * 256;
      for (let r = 0; r < 256; r++) mosaic.set(t.subarray(r * 256, r * 256 + 256), (oy + r) * W + ox);
      onProgress?.(++done, nx * ny);
    }
  };
  await Promise.all(Array.from({ length: 8 }, worker));

  const N = CS1.px, half = (N - 1) / 2, sp = extentOf(sq) / (N - 1);
  const out = new Float32Array(N * N);
  for (let row = 0; row < N; row++) {
    for (let col = 0; col < N; col++) {
      const [lon, lat] = squareToLonLat(sq, (col - half) * sp, (half - row) * sp);
      let [px, py] = merc(lon, lat, z);
      px = px - x0 * 256 - 0.5; py = py - y0 * 256 - 0.5; // pixel centres
      const ix = Math.max(0, Math.min(W - 2, Math.floor(px)));
      const iy = Math.max(0, Math.min(H - 2, Math.floor(py)));
      const fx = Math.min(1, Math.max(0, px - ix)), fy = Math.min(1, Math.max(0, py - iy));
      const i = iy * W + ix;
      out[row * N + col] =
        (mosaic[i] * (1 - fx) + mosaic[i + 1] * fx) * (1 - fy) +
        (mosaic[i + W] * (1 - fx) + mosaic[i + W + 1] * fx) * fy;
    }
  }
  return { heights: out, zoom: z, tiles: nx * ny, metresPerTilePx: 156543.034 * Math.cos((sq.lat * Math.PI) / 180) / 2 ** z };
}

// ---------------------------------------------------------------- water (OSM rivers + lakes)

const waterCache = new Map();
// water areas that flow: carved to their outline but not flattened (they slope downstream)
const RIVER_AREA = new Set(["river", "canal", "rapids"]);
// water areas that are neither lakes nor big rivers; left alone
const NOT_LAKE = new Set(["stream", "ditch", "drain", "stream_pool", "wastewater", "moat", "fish_pass"]);
const CACHE_PREFIX = "regionmap.water.v3:";
const GOOD_SERVER = "regionmap.overpass.good";
const sleep = (ms, signal) => new Promise((res, rej) => {
  const t = setTimeout(res, ms);
  signal?.addEventListener("abort", () => { clearTimeout(t); rej(new Error("cancelled")); }, { once: true });
});

/** Join a relation's member ways into closed rings (OSM splits big lake outlines into pieces). */
function stitch(ways) {
  const left = ways.filter((w) => w.length >= 2).map((w) => w.slice());
  const same = (a, b) => a[0] === b[0] && a[1] === b[1];
  const out = [];
  while (left.length) {
    let ring = left.shift(), grew = true;
    while (!same(ring[0], ring.at(-1)) && grew) {
      grew = false;
      for (let i = 0; i < left.length; i++) {
        const w = left[i];
        if (same(w[0], ring.at(-1))) ring = ring.concat(w.slice(1));
        else if (same(w.at(-1), ring.at(-1))) ring = ring.concat(w.slice().reverse().slice(1));
        else continue;
        left.splice(i, 1); grew = true; break;
      }
    }
    if (ring.length >= 3) out.push(ring);
  }
  return out;
}

// Results are cached per square in localStorage, so reopening a link or nudging back to a
// square asks OpenStreetMap nothing. Storage can be missing or full; the app works without it.
function cacheGet(key) {
  try { const v = localStorage.getItem(CACHE_PREFIX + key); return v ? JSON.parse(v) : null; } catch { return null; }
}
function cachePut(key, water) {
  const body = JSON.stringify(water);
  for (let tries = 0; tries < 8; tries++) {
    try { localStorage.setItem(CACHE_PREFIX + key, body); localStorage.setItem(CACHE_PREFIX + key + ":t", String(Date.now())); return; } catch {
      try { // full: drop the oldest cached square and try again
        const keys = Object.keys(localStorage).filter((k) => k.startsWith(CACHE_PREFIX) && k.endsWith(":t"));
        if (!keys.length) return;
        keys.sort((a, b) => Number(localStorage.getItem(a)) - Number(localStorage.getItem(b)));
        localStorage.removeItem(keys[0]); localStorage.removeItem(keys[0].slice(0, -2));
      } catch { return; }
    }
  }
}

/**
 * OSM waterway=river lines, river-area outlines and natural=water lakes around the square, in
 * one Overpass query, only when the user presses "Refine water with live OSM data". Polite by design (Overpass API usage policies, read 2026-11-09): one query
 * per square, asked of one instance at a time and never twice of the same one; the instance that
 * answered last is asked first; results cached, so a square is asked for at most once per browser. `onTry(host, k, n)` reports which instance is being asked.
 */
const waterKey = (sq) => bbox(sq, 500).map((v) => v.toFixed(3)).join(",");
/** Live OSM water already fetched for this square (memory or localStorage), without asking any server. */
export function cachedWater(sq) {
  const key = waterKey(sq);
  if (waterCache.has(key)) return waterCache.get(key);
  const cached = cacheGet(key);
  if (cached) waterCache.set(key, cached);
  return cached;
}
export async function fetchWater(sq, signal, onTry) {
  const [w, s, e, n] = bbox(sq, 500).map((v) => v.toFixed(3));
  const key = [w, s, e, n].join(",");
  const hit = cachedWater(sq);
  if (hit) return hit;
  const b = `(${s},${w},${n},${e})`;
  const q = `[out:json][timeout:20];(way["waterway"="river"]${b};way["waterway"="riverbank"]${b};` +
    `way["natural"="water"]${b};relation["natural"="water"]${b};);out geom;`;
  let good = null;
  try { good = localStorage.getItem(GOOD_SERVER); } catch {}
  const order = [...OVERPASS].sort((x, y) => (y === good) - (x === good));
  let data, lastErr;
  for (const [k, url] of order.entries()) {
    if (signal?.aborted) throw new Error("cancelled");
    onTry?.(new URL(url).host, k + 1, order.length);
    try {
      // 20 s each: a healthy instance answers a square (about 1 MB) in 5 to 16 s; a stuck one rarely recovers
      const r = await fetch(url, {
        method: "POST", body: new URLSearchParams({ data: q }),
        signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(20000)]) : AbortSignal.timeout(20000),
      });
      if (!r.ok) { lastErr = new Error(`Overpass HTTP ${r.status}`); continue; } // busy: next instance
      data = await r.json();
      try { localStorage.setItem(GOOD_SERVER, url); } catch {}
      break;
    } catch (err) {
      if (signal?.aborted) throw err;
      lastErr = err;
    }
  }
  if (!data) throw lastErr || new Error("Overpass failed");
  const r5 = (v) => Math.round(v * 1e5) / 1e5;
  const pts = (g) => g.filter(Boolean).map((p) => [r5(p.lon), r5(p.lat)]);
  const rivers = [], lakes = [], riverAreas = [];
  for (const el of data.elements) {
    const t = el.tags || {};
    if (el.type === "way" && t.waterway === "river") {
      if (el.geometry?.length >= 2) rivers.push({ name: t.name || "", pts: pts(el.geometry) });
      continue;
    }
    const rings = el.type === "way" ? (el.geometry?.length >= 3 ? [pts(el.geometry)] : [])
      : stitch((el.members || []).filter((m) => m.geometry?.length >= 2).map((m) => pts(m.geometry)));
    if (!rings.length) continue;
    if (t.waterway === "riverbank" || RIVER_AREA.has(t.water)) riverAreas.push({ name: t.name || "", rings });
    else if (!NOT_LAKE.has(t.water)) lakes.push({ name: t.name || "", rings });
  }
  const water = { rivers, lakes, riverAreas, source: "osm" };
  waterCache.set(key, water);
  cachePut(key, water);
  return water;
}

/**
 * The rivers and lakes in the basemap's OpenMapTiles vector tiles (OpenStreetMap data, from
 * OpenFreeMap's CDN), read over the whole square at the most detailed zoom that keeps the
 * request to at most MAX_BASEMAP_TILES tiles (zoom 14, the deepest, for a true-size square), so
 * the result never depends on the screen. This is the app's only automatic water source: at
 * zoom 14 the tiles carry OSM's river areas at full width, lakes and ponds, and named
 * waterway=river lines, so the public Overpass servers are not needed. Lines and outlines are
 * cut at tile edges (each tile also carries a few pixels of its neighbours, so pieces overlap);
 * the water polygons are unnamed and take their names from water_name labels.
 */
const MAX_BASEMAP_TILES = 160;
const vtCache = new Map(); // "z/x/y" -> ArrayBuffer | null, so nudging the square refetches only new tiles
let basemapTileJSON = null;
const tileRange = (box, z) => {
  const [w, s, e, n] = box;
  const [x0, y0] = merc(w, n, z).map((v) => Math.floor(v / 256));
  const [x1, y1] = merc(e, s, z).map((v) => Math.floor(v / 256));
  return { x0, y0, x1, y1, count: (x1 - x0 + 1) * (y1 - y0 + 1) };
};
export async function fetchBasemapWater(sq, signal, { zoom } = {}) {
  basemapTileJSON ??= fetch("https://tiles.openfreemap.org/planet").then((r) => r.json())
    .catch((err) => { basemapTileJSON = null; throw err; });
  const tj = await basemapTileJSON, tmpl = tj.tiles[0];
  const box = bbox(sq, 500);
  let z = zoom ?? Math.min(14, tj.maxzoom ?? 14);
  while (!zoom && z > 10 && tileRange(box, z).count > MAX_BASEMAP_TILES) z--;
  const { x0, y0, x1, y1, count } = tileRange(box, z);
  const jobs = [];
  for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) jobs.push([x, y]);
  const rivers = [], lakes = [], riverAreas = [], labels = [];
  const r5 = (v) => Math.round(v * 1e5) / 1e5;
  const ring = (r) => r.map(([lo, la]) => [r5(lo), r5(la)]);
  const nameOf = (p) => p.name || p["name:latin"] || p.name_en || "";
  const get = async (x, y) => {
    const key = `${tmpl}|${z}/${x}/${y}`;
    if (vtCache.has(key)) return vtCache.get(key);
    for (let attempt = 0; ; attempt++) {
      try {
        const r = await fetch(tmpl.replace("{z}", z).replace("{x}", x).replace("{y}", y),
          { signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000) });
        let buf = null; // 204/404: no data here (open sea)
        if (r.status !== 204 && r.status !== 404) {
          if (!r.ok) throw new Error(`basemap HTTP ${r.status}`);
          buf = await r.arrayBuffer();
        }
        if (vtCache.size > 600) vtCache.delete(vtCache.keys().next().value);
        vtCache.set(key, buf);
        return buf;
      } catch (err) {
        if (signal?.aborted || attempt >= 2) throw err;
        await sleep(500 * 2 ** attempt, signal);
      }
    }
  };
  const one = async ([x, y]) => {
    const buf = await get(x, y);
    if (!buf) return;
    const vt = new VectorTile(new Pbf(buf));
    // river lines are clipped to the tile's own square (tiles also carry a margin of their
    // neighbours), so pieces from neighbouring tiles meet end to end instead of overlapping
    const ww = vt.layers.waterway;
    for (let i = 0; ww && i < ww.length; i++) {
      const f = ww.feature(i);
      if (f.properties.class !== "river") continue;
      const E = ww.extent, toLonLat = ([px, py]) => {
        const zx = (x + px / E) / 2 ** z, zy = (y + py / E) / 2 ** z;
        return [r5(zx * 360 - 180), r5((360 / Math.PI) * Math.atan(Math.exp(Math.PI * (1 - 2 * zy))) - 90)];
      };
      for (const line of f.loadGeometry())
        for (const piece of clipLine(line.map((p) => [p.x, p.y]), E))
          rivers.push({ name: nameOf(f.properties), pts: piece.map(toLonLat) });
    }
    const wn = vt.layers.water_name;
    for (let i = 0; wn && i < wn.length; i++) {
      const f = wn.feature(i), name = nameOf(f.properties);
      if (!name) continue;
      const g = f.toGeoJSON(x, y, z).geometry;
      const pts = g.type === "Point" ? [g.coordinates] : g.type === "LineString" ? g.coordinates
        : g.type === "MultiLineString" ? g.coordinates.flat() : g.type === "MultiPoint" ? g.coordinates : [];
      for (const at of pts) labels.push({ name, at });
    }
    const wa = vt.layers.water;
    for (let i = 0; wa && i < wa.length; i++) {
      const f = wa.feature(i), cls = f.properties.class;
      const into = cls === "river" ? riverAreas : ["lake", "pond", "dock"].includes(cls) ? lakes : null;
      if (!into) continue;
      const g = f.toGeoJSON(x, y, z).geometry;
      for (const rings of g.type === "MultiPolygon" ? g.coordinates : [g.coordinates])
        into.push({ name: "", rings: rings.map(ring) });
    }
  };
  const worker = async () => { while (jobs.length) await one(jobs.shift()); };
  await Promise.all(Array.from({ length: 6 }, worker));
  // the water layer has no names; its labels (water_name points and lines) do
  for (const L of lakes) { const hit = labels.find((p) => inRings(p.at, L.rings)); if (hit) L.name = hit.name; }
  return { rivers, lakes, riverAreas, fragments: true, source: "basemap", zoom: z, tiles: count };
}

/** Clip a polyline to the square [0, E] x [0, E]; returns the pieces inside (Liang-Barsky per segment). */
function clipLine(pts, E) {
  const out = [];
  let cur = null;
  for (let k = 1; k < pts.length; k++) {
    const [x0, y0] = pts[k - 1], [x1, y1] = pts[k], dx = x1 - x0, dy = y1 - y0;
    let t0 = 0, t1 = 1, ok = true;
    for (const [p, q] of [[-dx, x0], [dx, E - x0], [-dy, y0], [dy, E - y0]]) {
      if (p === 0) { if (q < 0) { ok = false; break; } continue; }
      const r = q / p;
      if (p < 0) { if (r > t1) { ok = false; break; } if (r > t0) t0 = r; }
      else { if (r < t0) { ok = false; break; } if (r < t1) t1 = r; }
    }
    if (!ok) { cur = null; continue; }
    const a = [x0 + t0 * dx, y0 + t0 * dy], b = [x0 + t1 * dx, y0 + t1 * dy];
    if (!cur || t0 > 0) { cur = [a]; out.push(cur); }
    cur.push(b);
    if (t1 < 1) cur = null;
  }
  return out.filter((l) => l.length >= 2);
}

/** Even-odd point-in-polygon over all rings (outer and holes). */
function inRings([x, y], rings) {
  let inside = false;
  for (const r of rings) for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
    const [xi, yi] = r[i], [xj, yj] = r[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** 4-connected components of a mask: label per pixel (0 = none) and pixel count per label. */
function components(mask, N) {
  const label = new Int32Array(N * N), sizes = [0], stack = new Int32Array(N * N);
  for (let i0 = 0; i0 < mask.length; i0++) {
    if (!mask[i0] || label[i0]) continue;
    const id = sizes.length;
    let sp = 0, count = 0;
    stack[sp++] = i0; label[i0] = id;
    while (sp) {
      const i = stack[--sp]; count++;
      const r = (i / N) | 0, c = i - r * N;
      if (c > 0 && mask[i - 1] && !label[i - 1]) { label[i - 1] = id; stack[sp++] = i - 1; }
      if (c < N - 1 && mask[i + 1] && !label[i + 1]) { label[i + 1] = id; stack[sp++] = i + 1; }
      if (r > 0 && mask[i - N] && !label[i - N]) { label[i - N] = id; stack[sp++] = i - N; }
      if (r < N - 1 && mask[i + N] && !label[i + N]) { label[i + N] = id; stack[sp++] = i + N; }
    }
    sizes.push(count);
  }
  return { label, sizes };
}

/**
 * Open sea: pixels at or below `level` metres that connect to the map edge. The elevation
 * data stores the sea surface as blocky 0..2 m noise, so "above 0 m" is not land; and
 * low ground or lakes cut off from the edge are not sea. Small low specks left inside the
 * sea are that same noise and become sea too.
 */
export function seaMask(raw, level = 3) {
  const N = CS1.px, low = new Uint8Array(N * N);
  for (let i = 0; i < low.length; i++) low[i] = raw[i] <= level ? 1 : 0;
  const { label, sizes } = components(low, N);
  const edge = new Set();
  for (let k = 0; k < N; k++) for (const i of [k, (N - 1) * N + k, k * N, k * N + N - 1]) if (label[i]) edge.add(label[i]);
  const sea = new Uint8Array(N * N);
  let any = 0;
  for (let i = 0; i < sea.length; i++) if (edge.has(label[i])) { sea[i] = 1; any++; }
  if (!any) return null;
  const land = new Uint8Array(N * N);
  for (let i = 0; i < land.length; i++) land[i] = 1 - sea[i];
  const islands = components(land, N), top = new Float32Array(islands.sizes.length).fill(-Infinity);
  for (let i = 0; i < land.length; i++) if (land[i]) top[islands.label[i]] = Math.max(top[islands.label[i]], raw[i]);
  for (let i = 0; i < land.length; i++) {
    const id = islands.label[i];
    if (id && islands.sizes[id] < 40 && top[id] < 8) sea[i] = 1;
  }
  return sea;
}

/** 1D squared distance transform (Felzenszwalb & Huttenlocher). */
function dt1(f, n, d, v, zz) {
  let k = 0;
  v[0] = 0; zz[0] = -Infinity; zz[1] = Infinity;
  for (let q = 1; q < n; q++) {
    let s;
    while (true) {
      const p = v[k];
      s = (f[q] + q * q - (f[p] + p * p)) / (2 * q - 2 * p);
      if (s <= zz[k] && k > 0) k--; else break;
    }
    if (s <= zz[k]) { v[0] = q; zz[0] = -Infinity; zz[1] = Infinity; k = 0; continue; }
    k++; v[k] = q; zz[k] = s; zz[k + 1] = Infinity;
  }
  k = 0;
  for (let q = 0; q < n; q++) {
    while (zz[k + 1] < q) k++;
    const p = v[k];
    d[q] = (q - p) * (q - p) + f[p];
  }
}

function edt(mask, N) {
  const BIG = 1e12, d2 = new Float64Array(N * N);
  for (let i = 0; i < d2.length; i++) d2[i] = mask[i] ? 0 : BIG;
  const f = new Float64Array(N), d = new Float64Array(N), v = new Int32Array(N), zz = new Float64Array(N + 1);
  for (let c = 0; c < N; c++) {
    for (let r = 0; r < N; r++) f[r] = d2[r * N + c];
    dt1(f, N, d, v, zz);
    for (let r = 0; r < N; r++) d2[r * N + c] = d[r];
  }
  for (let r = 0; r < N; r++) {
    for (let c = 0; c < N; c++) f[c] = d2[r * N + c];
    dt1(f, N, d, v, zz);
    for (let c = 0; c < N; c++) d2[r * N + c] = d[c];
  }
  return d2;
}

/**
 * Lower the heights along river centrelines, then sink each lake flat,
 * `lakeDepth` metres below its lowest real height. Returns the carved copy, a mask of
 * wet pixels for the preview, and what was cut.
 */
export function carveWater(heights, sq, water, { depth = 10, halfWidth = 40, lakeDepth = 4 } = {}) {
  const N = CS1.px, half = (N - 1) / 2, sp = extentOf(sq) / (N - 1);
  const toPx = ([lon, lat]) => {
    const [u, v] = lonLatToSquare(sq, lon, lat);
    return [u / sp + half + 0.5, half - v / sp + 0.5]; // canvas pixel edges
  };
  const c = new OffscreenCanvas(N, N);
  const g = c.getContext("2d", { willReadFrequently: true });
  g.strokeStyle = "#fff"; g.lineWidth = 1; g.lineJoin = "round";
  for (const r of water.rivers) {
    g.beginPath();
    r.pts.forEach((p, i) => { const [x, y] = toPx(p); i ? g.lineTo(x, y) : g.moveTo(x, y); });
    g.stroke();
  }
  let a = g.getImageData(0, 0, N, N).data;
  const mask = new Uint8Array(N * N);
  let anyRiver = false;
  for (let i = 0; i < mask.length; i++) if (a[4 * i + 3] >= 96) { mask[i] = 1; anyRiver = true; }
  const out = Float32Array.from(heights);
  const wet = new Uint8Array(N * N);
  if (anyRiver) {
    const d2 = edt(mask, N);
    const w = Math.max(halfWidth, 2.5 * sp);
    for (let i = 0; i < out.length; i++) {
      const d = Math.sqrt(d2[i]) * sp;
      if (d >= w) continue;
      const p = (1 - (d / w) ** 2) ** 2;
      out[i] -= depth * p;
      if (depth * p > 1) wet[i] = 1;
    }
  }
  // river areas (OSM outlines of wide rivers, e.g. the Tennessee): the bed is cut across the
  // whole outline, with a short ramp at the banks. Rivers slope downstream, so unlike lakes
  // they are not flattened; the centreline cut above stays for rivers mapped only as a line.
  let anyArea = false;
  if (water.riverAreas?.length) {
    g.clearRect(0, 0, N, N);
    g.fillStyle = "#fff";
    for (const ra of water.riverAreas) {
      g.beginPath();
      for (const ring of ra.rings) ring.forEach((p, i) => { const [x, y] = toPx(p); i ? g.lineTo(x, y) : g.moveTo(x, y); });
      g.fill("evenodd");
    }
    a = g.getImageData(0, 0, N, N).data;
    const bank = new Uint8Array(N * N);
    for (let i = 0; i < bank.length; i++) if (a[4 * i + 3] >= 128) anyArea = true; else bank[i] = 1;
    if (anyArea) {
      const d2 = edt(bank, N), ramp = Math.max(2 * sp, 24);
      for (let i = 0; i < out.length; i++) {
        if (bank[i]) continue;
        let p = Math.min(1, (Math.sqrt(d2[i]) * sp) / ramp);
        p = p * p * (3 - 2 * p);
        out[i] = Math.min(out[i], heights[i] - depth * p);
        if (depth * p > 1) wet[i] = 1;
      }
    }
  }
  // lakes: fill every outline (even-odd, so islands stay), then one flat level per lake
  g.clearRect(0, 0, N, N);
  g.fillStyle = "#fff";
  for (const lake of water.lakes) {
    g.beginPath();
    for (const ring of lake.rings) ring.forEach((p, i) => { const [x, y] = toPx(p); i ? g.lineTo(x, y) : g.moveTo(x, y); });
    g.fill("evenodd");
  }
  a = g.getImageData(0, 0, N, N).data;
  const lakeMask = new Uint8Array(N * N);
  for (let i = 0; i < lakeMask.length; i++) lakeMask[i] = a[4 * i + 3] >= 128 ? 1 : 0;
  const { label, sizes } = components(lakeMask, N);
  const low = new Float32Array(sizes.length).fill(Infinity);
  for (let i = 0; i < label.length; i++) if (label[i]) low[label[i]] = Math.min(low[label[i]], heights[i]);
  let lakes = 0;
  for (let id = 1; id < sizes.length; id++) if (sizes[id] >= 12) lakes++;
  for (let i = 0; i < label.length; i++) {
    const id = label[i];
    if (!id || sizes[id] < 12) continue; // ponds smaller than ~3,000 m2 stay as they are
    out[i] = Math.min(out[i], low[id] - lakeDepth);
    wet[i] = 1;
  }
  // soften the cut itself: the river mask is drawn on the 16 m grid and lake beds are flat-walled,
  // which leaves stair-stepped banks; blurring only the cut (not the ground) rounds them off
  const cut = new Float32Array(N * N);
  for (let i = 0; i < cut.length; i++) cut[i] = out[i] - heights[i];
  const soft = smooth(cut, 1.2);
  for (let i = 0; i < out.length; i++) out[i] = heights[i] + Math.min(soft[i], 0);
  // the deepest-inside pixel of each sizeable lake: where its water source goes
  const lakeInfo = [];
  const big = [];
  for (let id = 1; id < sizes.length; id++) if (sizes[id] * sp * sp >= 40000) big.push(id); // >= 4 ha
  if (big.length) {
    const dry = new Uint8Array(N * N);
    for (let i = 0; i < dry.length; i++) dry[i] = label[i] ? 0 : 1;
    const d2 = edt(dry, N), best = new Map();
    for (let i = 0; i < label.length; i++) {
      const id = label[i];
      if (id && sizes[id] * sp * sp >= 40000 && (!best.has(id) || d2[i] > d2[best.get(id)])) best.set(id, i);
    }
    const names = new Map(); // name each lake from the OSM outline that covers its centre
    for (const [id, i] of best) lakeInfo.push({ i, area_m2: sizes[id] * sp * sp, shore_real_m: low[id], name: "" });
    water.lakes.forEach((lake) => {
      if (!lake.name) return;
      g.clearRect(0, 0, N, N); g.beginPath();
      for (const ring of lake.rings) ring.forEach((p, k) => { const [x, y] = toPx(p); k ? g.lineTo(x, y) : g.moveTo(x, y); });
      for (const L of lakeInfo) if (!L.name && g.isPointInPath((L.i % N) + 0.5, Math.floor(L.i / N) + 0.5, "evenodd")) L.name = lake.name;
    });
  }
  return { heights: out, wet, riversCut: anyRiver || anyArea, lakes, lakeInfo };
}

/** Separable Gaussian blur (sigma in pixels) of an N x N height grid; edges clamp. */
export function smooth(h, sigma) {
  if (!sigma) return h;
  const N = CS1.px, R = Math.ceil(sigma * 2.5), k = [];
  let sum = 0;
  for (let j = -R; j <= R; j++) { const v = Math.exp(-(j * j) / (2 * sigma * sigma)); k.push(v); sum += v; }
  for (let j = 0; j < k.length; j++) k[j] /= sum;
  const tmp = new Float32Array(N * N), out = new Float32Array(N * N);
  for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
    let a = 0;
    for (let j = -R; j <= R; j++) a += k[j + R] * h[r * N + Math.min(N - 1, Math.max(0, c + j))];
    tmp[r * N + c] = a;
  }
  for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
    let a = 0;
    for (let j = -R; j <= R; j++) a += k[j + R] * tmp[Math.min(N - 1, Math.max(0, r + j)) * N + c];
    out[r * N + c] = a;
  }
  return out;
}

/**
 * Where to put water sources in the Map Editor: where each sizeable OSM river flows into the
 * square (OSM draws waterways in their flow direction), where one starts inside it, where it
 * leaves (no source there), and the middle of each lake of 4 ha or more. Positions are the editor's: metres from the map centre,
 * x east and z north, plus the ground height there in game metres.
 */
export function waterSources(sq, water, carved, fit) {
  const N = CS1.px, half = (N - 1) / 2, h = extentOf(sq) / 2, sp = extentOf(sq) / (N - 1), gsp = CS1.extent / (N - 1);
  const inside = ([u, v]) => Math.abs(u) < h && Math.abs(v) < h;
  const px = ([u, v]) => {
    const c = Math.round(Math.min(N - 1, Math.max(0, u / sp + half))), r = Math.round(Math.min(N - 1, Math.max(0, half - v / sp)));
    return r * N + c;
  };
  const at = (i, kind, name, extra = {}) => {
    const r = Math.floor(i / N), c = i % N;
    const [lon, lat] = squareToLonLat(sq, (c - half) * sp, (half - r) * sp);
    return { kind, name, x_m: Math.round((c - half) * gsp), z_m: Math.round((half - r) * gsp), col: c, row: r,
      ground_game_m: Math.round(fit.game[i] * 10) / 10, lon: +lon.toFixed(5), lat: +lat.toFixed(5), ...extra };
  };
  // in-map length per river name, so creeks tagged "river" don't each get a source
  const lenByName = new Map(), endKeys = new Set();
  const ways = water.rivers.map((r) => ({ name: r.name || "unnamed river", uv: r.pts.map(([lo, la]) => lonLatToSquare(sq, lo, la)), pts: r.pts }));
  for (const w of ways) {
    endKeys.add(w.pts.at(-1).join(","));
    let L = 0;
    for (let k = 1; k < w.uv.length; k++) if (inside(w.uv[k]) || inside(w.uv[k - 1])) L += Math.hypot(w.uv[k][0] - w.uv[k - 1][0], w.uv[k][1] - w.uv[k - 1][1]);
    lenByName.set(w.name, (lenByName.get(w.name) || 0) + L);
  }
  // every place a sizeable river crosses the edge, nudged 3 px inside, with its direction
  const cand = [];
  for (const w of ways) {
    if ((lenByName.get(w.name) || 0) < 1500) continue;
    if (!water.fragments && inside(w.uv[0]) && !endKeys.has(w.pts[0].join(","))) {
      cand.push(at(px(w.uv[0]), "river start", w.name));
    }
    for (let k = 1; k < w.uv.length; k++) {
      const a = w.uv[k - 1], b = w.uv[k];
      if (inside(a) === inside(b)) continue;
      const [o, i] = inside(b) ? [a, b] : [b, a]; // outside, inside
      let lo = 0, hi = 1;
      for (let it = 0; it < 30; it++) { const m = (lo + hi) / 2; inside([o[0] + (i[0] - o[0]) * m, o[1] + (i[1] - o[1]) * m]) ? (hi = m) : (lo = m); }
      const e = [o[0] + (i[0] - o[0]) * hi, o[1] + (i[1] - o[1]) * hi];
      const toC = Math.hypot(e[0], e[1]) || 1;
      cand.push(at(px([e[0] - (e[0] / toC) * 3 * sp, e[1] - (e[1] / toC) * 3 * sp]), inside(b) ? "river entry" : "river exit", w.name));
    }
  }
  // OSM ways run downstream, so their direction tells entry from exit. Basemap pieces are cut
  // at tile edges and their direction can't be trusted. There, a river's real ends inside the
  // square are the piece ends that touch no other river line (pieces of neighbouring tiles
  // overlap, so a cut end always touches its continuation; a tributary's mouth touches the
  // river it joins). Each river starts at the highest of its edge crossings and real ends: an
  // entry if that is a crossing, a start if it is an end. Every other crossing is an exit.
  if (water.fragments) {
    const CELL = 250, grid = new Map(), cellKey = (x, y) => `${Math.floor(x / CELL)},${Math.floor(y / CELL)}`;
    ways.forEach((w, wi) => {
      for (let k = 1; k < w.uv.length; k++) {
        const [a, b] = [w.uv[k - 1], w.uv[k]];
        const seen = new Set();
        for (let t = 0; t <= 1; t += 0.25) {
          const key = cellKey(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t);
          if (seen.has(key)) continue;
          seen.add(key);
          if (!grid.has(key)) grid.set(key, []);
          grid.get(key).push([a, b, wi]);
        }
      }
    });
    const segDist = ([px, py], [ax, ay], [bx, by]) => {
      const dx = bx - ax, dy = by - ay, L = dx * dx + dy * dy;
      const t = L ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / L)) : 0;
      return Math.hypot(px - ax - t * dx, py - ay - t * dy);
    };
    const touches = (p, wi) => {
      const cx = Math.floor(p[0] / CELL), cy = Math.floor(p[1] / CELL);
      for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++)
        for (const [a, b, o] of grid.get(`${cx + i},${cy + j}`) || []) if (o !== wi && segDist(p, a, b) < 30) return true;
      return false;
    };
    const margin = h - 3 * sp;
    ways.forEach((w, wi) => {
      if ((lenByName.get(w.name) || 0) < 1500) return;
      for (const e of [w.uv[0], w.uv.at(-1)])
        if (Math.abs(e[0]) < margin && Math.abs(e[1]) < margin && !touches(e, wi)) cand.push(at(px(e), "river end", w.name));
    });
    const top = new Map();
    for (const c of cand) if (!top.has(c.name) || c.ground_game_m > top.get(c.name).ground_game_m) top.set(c.name, c);
    for (let k = cand.length - 1; k >= 0; k--) {
      const c = cand[k], first = top.get(c.name) === c;
      if (c.kind === "river end") first ? (c.kind = "river start") : cand.splice(k, 1); // other ends are mouths
      else c.kind = first ? "river entry" : "river exit";
    }
  }
  // one point per river per place (entries win over exits), merged within 400 m; and only the
  // lowest exit of each river, since where it leaves is a note, not something to build
  const rank = { "river entry": 0, "river start": 1, "river exit": 2 };
  cand.sort((a, b) => rank[a.kind] - rank[b.kind] || (a.kind === "river exit" ? a.ground_game_m - b.ground_game_m : 0));
  const rivers = [], exited = new Set();
  for (const c of cand) {
    if (c.kind === "river exit" && exited.has(c.name)) continue;
    if (rivers.some((o) => Math.hypot(o.x_m - c.x_m, o.z_m - c.z_m) < 400)) continue;
    rivers.push(c);
    if (c.kind === "river exit") exited.add(c.name);
  }
  rivers.sort((a, b) => (lenByName.get(b.name) || 0) - (lenByName.get(a.name) || 0) || rank[a.kind] - rank[b.kind]);
  // lakes at or below sea level are lagoons the sea fills by itself
  const above = (L) => fit.seaLevel === null || (L.shore_real_m - fit.base) * fit.verticalScale + 50 > fit.seaLevel + 1;
  // a named lake the carving split in two (a causeway, a dam) is still one lake: one source, at its biggest part
  // (unnamed pieces count as one lake when their shores are level and within 2 km)
  const merged = [];
  const xy = (i) => [(i % N) * sp, Math.floor(i / N) * sp];
  for (const L of (carved.lakeInfo || []).filter(above).sort((a, b) => b.area_m2 - a.area_m2)) {
    const same = merged.find((M) => L.name ? M.name === L.name
      : !M.name && Math.abs(M.shore_real_m - L.shore_real_m) < 1 && Math.hypot(...xy(M.i).map((v, k) => v - xy(L.i)[k])) < 2000);
    if (same) same.area_m2 += L.area_m2; else merged.push({ ...L });
  }
  const lakes = merged.sort((a, b) => b.area_m2 - a.area_m2).slice(0, 8).map((L) =>
    at(L.i, "lake", L.name || "unnamed lake", {
      area_ha: Math.round(L.area_m2 / 1000) / 10,
      // water surface at the lake's real shoreline, in game metres
      surface_game_m: Math.round(((L.shore_real_m - fit.base) * fit.verticalScale + 50) * 10) / 10,
    }));
  return [...rivers.slice(0, 12), ...lakes];
}

// ---------------------------------------------------------------- fit + encode

/**
 * Shift (and if needed squeeze) real heights into CS1's 0..1024 m.
 * The lowest ground sits at `floor` and 1 game metre = 1 real metre.
 * If the relief would not fit under `ceiling`, heights are scaled down to fit.
 * `sea` (from seaMask) is open sea: it goes 10..`seaDepth` m below sea level, and all
 * other ground is kept at least 1 m above it, so the coast neither floods nor sprouts islands.
 */
export function fitHeights(raw, carved, { sea = null, floor = 50, ceiling = 1000, verticalScale = "auto", seaDepth = 40 } = {}) {
  let rmin = Infinity, rmax = -Infinity;
  for (const v of raw) { if (v < rmin) rmin = v; if (v > rmax) rmax = v; }
  const hasSea = !!sea;
  const lo = hasSea ? -seaDepth : rmin;
  const relief = rmax - lo;
  const auto = Math.min(1, (ceiling - floor) / Math.max(relief, 1));
  // a number, "auto", or a function of the fit-to-1024 m factor (the app's Real slopes option)
  const vs = verticalScale === "auto" ? auto : typeof verticalScale === "function" ? verticalScale(auto) : verticalScale;
  const N = carved.length, game = new Float32Array(N);
  let gmin = Infinity, gmax = -Infinity, clipped = 0;
  for (let i = 0; i < N; i++) {
    let r;
    if (!hasSea) r = carved[i];
    else if (sea[i]) r = Math.min(Math.max(carved[i], -seaDepth), -10);
    else r = carved[i] < raw[i] ? Math.max(carved[i], -seaDepth) : Math.max(carved[i], 1); // carved water may dip below
    const g = (r - lo) * vs + floor;
    game[i] = g;
    if (g < gmin) gmin = g; if (g > gmax) gmax = g;
    if (g > CS1.maxHeight || g < 0) clipped++;
  }
  return {
    game, sea, realMin: rmin, realMax: rmax, relief: rmax - rmin, verticalScale: vs, autoScale: auto,
    base: lo, gameMin: gmin, gameMax: gmax, headroom: CS1.maxHeight - gmax,
    clipped: clipped / N, seaLevel: hasSea ? (0 - lo) * vs + floor : null,
  };
}

export function encode16(game) {
  const out = new Uint16Array(game.length);
  for (let i = 0; i < game.length; i++)
    out[i] = Math.round((Math.min(Math.max(game[i], 0), CS1.maxHeight) / CS1.maxHeight) * 65535);
  return out;
}

const CRC = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();
const crc32 = (bytes) => {
  let c = 0xffffffff;
  for (const b of bytes) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
};

/** 16-bit greyscale PNG (colour type 0, depth 16) from a Uint16Array, deflated with CompressionStream. */
export async function png16(data, w, h) {
  const stride = 1 + w * 2, raw = new Uint8Array(stride * h);
  for (let y = 0; y < h; y++) {
    raw[y * stride] = 2; // "Up" filter: neighbouring rows of terrain are similar
    for (let x = 0; x < w; x++) {
      const v = data[y * w + x], u = y ? data[(y - 1) * w + x] : 0;
      const o = y * stride + 1 + 2 * x;
      raw[o] = ((v >> 8) - (u >> 8)) & 0xff;
      raw[o + 1] = ((v & 0xff) - (u & 0xff)) & 0xff;
    }
  }
  const z = new Uint8Array(await new Response(new Blob([raw]).stream().pipeThrough(new CompressionStream("deflate"))).arrayBuffer());
  const chunk = (type, body) => {
    const b = new Uint8Array(12 + body.length), dv = new DataView(b.buffer);
    dv.setUint32(0, body.length);
    b.set([...type].map((ch) => ch.charCodeAt(0)), 4);
    b.set(body, 8);
    dv.setUint32(8 + body.length, crc32(b.subarray(4, 8 + body.length)));
    return b;
  };
  const ihdr = new Uint8Array(13), dv = new DataView(ihdr.buffer);
  dv.setUint32(0, w); dv.setUint32(4, h);
  ihdr.set([16, 0, 0, 0, 0], 8);
  const sig = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]);
  return new Blob([sig, chunk("IHDR", ihdr), chunk("IDAT", z), chunk("IEND", new Uint8Array())], { type: "image/png" });
}

// Real terrain -> Cities: Skylines 1 heightmap. The same module runs in the browser (app.js)
// and in Node (cli.mjs), so a square gives the same PNG either way: no canvas, no DOM.
// Sample a 1081 px square, burn OSM rivers in with a (1 - (d/w)^2)^2 profile, shift the
// lowest ground to `floor` metres, and encode 0..65535 = 0..1024 m.

// Bare specifiers: the page's import map points them at jsDelivr; Node finds them in node_modules.
import { VectorTile } from "@mapbox/vector-tile";
import Pbf from "pbf";

export const CS1 = { px: 1081, extent: 17280, maxHeight: 1024 };
// WGS84 radii of curvature at the square's centre: metres per radian north (M) and east (N cos lat).
const radii = (latDeg) => {
  const a = 6378137, e2 = 0.00669437999014, s = Math.sin((latDeg * Math.PI) / 180);
  const w = 1 - e2 * s * s;
  return [(a * (1 - e2)) / w ** 1.5, (a / Math.sqrt(w)) * Math.cos((latDeg * Math.PI) / 180)];
};
const TERRARIUM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";
export const SITE = "https://region-to-skylines.vercel.app";

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

const inflate = async (blob) =>
  new Uint8Array(await new Response(blob.stream().pipeThrough(new DecompressionStream("deflate"))).arrayBuffer());

/** Decode an 8-bit, non-interlaced PNG (what Terrarium serves) to RGB bytes, exactly, in any JS runtime. */
export async function decodePNG(buf) {
  const b = new Uint8Array(buf), dv = new DataView(b.buffer, b.byteOffset, b.byteLength);
  let w = 0, h = 0, depth = 0, type = -1, interlace = 0, plte = null;
  const idat = [];
  for (let o = 8; o + 8 <= b.length;) {
    const len = dv.getUint32(o), t = String.fromCharCode(...b.subarray(o + 4, o + 8)), body = b.subarray(o + 8, o + 8 + len);
    if (t === "IHDR") { w = dv.getUint32(o + 8); h = dv.getUint32(o + 12); depth = b[o + 16]; type = b[o + 17]; interlace = b[o + 20]; }
    else if (t === "PLTE") plte = body;
    else if (t === "IDAT") idat.push(body);
    else if (t === "IEND") break;
    o += 12 + len;
  }
  const ch = { 0: 1, 2: 3, 3: 1, 4: 2, 6: 4 }[type];
  if (depth !== 8 || interlace || !ch) throw new Error(`unsupported PNG (colour type ${type}, depth ${depth})`);
  const raw = await inflate(new Blob(idat)), stride = w * ch, px = new Uint8Array(stride * h);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)], src = y * (stride + 1) + 1, dst = y * stride;
    for (let x = 0; x < stride; x++) {
      const a = x >= ch ? px[dst + x - ch] : 0, u = y ? px[dst - stride + x] : 0, c = x >= ch && y ? px[dst - stride + x - ch] : 0;
      let v = raw[src + x];
      if (f === 1) v += a;
      else if (f === 2) v += u;
      else if (f === 3) v += (a + u) >> 1;
      else if (f === 4) { const p = a + u - c, pa = Math.abs(p - a), pb = Math.abs(p - u), pc = Math.abs(p - c); v += pa <= pb && pa <= pc ? a : pb <= pc ? u : c; }
      px[dst + x] = v & 255;
    }
  }
  const rgb = new Uint8Array(w * h * 3);
  for (let i = 0; i < w * h; i++) {
    if (type === 2 || type === 6) { rgb[3 * i] = px[ch * i]; rgb[3 * i + 1] = px[ch * i + 1]; rgb[3 * i + 2] = px[ch * i + 2]; }
    else if (type === 3) rgb.set(plte.subarray(3 * px[i], 3 * px[i] + 3), 3 * i);
    else rgb.fill(px[ch * i], 3 * i, 3 * i + 3);
  }
  return { w, h, rgb };
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
      const { rgb } = await decodePNG(await r.arrayBuffer());
      const h = new Float32Array(256 * 256);
      for (let i = 0; i < h.length; i++) h[i] = rgb[3 * i] * 256 + rgb[3 * i + 1] + rgb[3 * i + 2] / 256 - 32768;
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

const sleep = (ms, signal) => new Promise((res, rej) => {
  const t = setTimeout(res, ms);
  signal?.addEventListener("abort", () => { clearTimeout(t); rej(new Error("cancelled")); }, { once: true });
});

/**
 * The rivers and lakes in the basemap's OpenMapTiles vector tiles (OpenStreetMap data, from
 * OpenFreeMap's CDN), read over the whole square at the most detailed zoom that keeps the
 * request to at most MAX_BASEMAP_TILES tiles (zoom 14, the deepest, for a true-size square), so
 * the result never depends on the screen. This is the app's only water source: at zoom 14
 * the tiles carry OSM's river areas at full width, lakes and ponds, and named waterway=river
 * lines (they match a live Overpass query on 99.7% of wet pixels for Asheville). Which way a
 * river flows is read from the ground, in waterSources. Lines and outlines are
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
/** The basemap's TileJSON (OpenFreeMap's current planet build), fetched once. */
export async function basemapTiles() {
  basemapTileJSON ??= fetch("https://tiles.openfreemap.org/planet").then((r) => r.json())
    .catch((err) => { basemapTileJSON = null; throw err; });
  return basemapTileJSON;
}

/** One basemap vector tile as an ArrayBuffer, or null where there is no data (open sea); cached. */
export async function basemapTile(z, x, y, signal) {
  const tmpl = (await basemapTiles()).tiles[0], key = `${tmpl}|${z}/${x}/${y}`;
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
}

export async function fetchBasemapWater(sq, signal, { zoom } = {}) {
  const tj = await basemapTiles();
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
  const one = async ([x, y]) => {
    const buf = await basemapTile(z, x, y, signal);
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
          rivers.push({ name: nameOf(f.properties), pts: piece.map(toLonLat), ...waterwayTags(f.properties) });
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

/** A waterway's tunnel and intermittent tags, which the ready-to-play writer reads (tunnels carry no surface water). */
export const waterwayTags = (p) => Object.fromEntries(["brunnel", "intermittent"].filter((k) => p[k] !== undefined).map((k) => [k, p[k]]));

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
 * Pixels (row-major, N x N) whose centre lies within 0.6 px of a polyline, in pixel-edge
 * coordinates: the thin line the river cut is measured from.
 */
function strokeMask(lines, N, r = 0.6) {
  const mask = new Uint8Array(N * N);
  for (const pts of lines) for (let k = 1; k < pts.length; k++) {
    const [ax, ay] = pts[k - 1], [bx, by] = pts[k], dx = bx - ax, dy = by - ay, L = dx * dx + dy * dy;
    const c0 = Math.max(0, Math.floor(Math.min(ax, bx) - r)), c1 = Math.min(N - 1, Math.floor(Math.max(ax, bx) + r));
    const r0 = Math.max(0, Math.floor(Math.min(ay, by) - r)), r1 = Math.min(N - 1, Math.floor(Math.max(ay, by) + r));
    for (let row = r0; row <= r1; row++) for (let col = c0; col <= c1; col++) {
      const px = col + 0.5, py = row + 0.5;
      const t = L ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / L)) : 0;
      if (Math.hypot(px - ax - t * dx, py - ay - t * dy) <= r) mask[row * N + col] = 1;
    }
  }
  return mask;
}

/** Pixels whose centre is inside a shape (even-odd over its rings, so islands stay out), for a list of shapes. */
export function fillMask(shapes, N) {
  const mask = new Uint8Array(N * N);
  for (const rings of shapes) {
    let y0 = Infinity, y1 = -Infinity;
    for (const ring of rings) for (const [, y] of ring) { if (y < y0) y0 = y; if (y > y1) y1 = y; }
    const xs = [];
    for (let row = Math.max(0, Math.floor(y0)); row <= Math.min(N - 1, Math.ceil(y1)); row++) {
      const y = row + 0.5;
      xs.length = 0;
      for (const ring of rings) for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        const [xi, yi] = ring[i], [xj, yj] = ring[j];
        if ((yi > y) !== (yj > y)) xs.push(xi + ((y - yi) * (xj - xi)) / (yj - yi));
      }
      xs.sort((p, q) => p - q);
      for (let k = 0; k + 1 < xs.length; k += 2) {
        const ca = Math.max(0, Math.ceil(xs[k] - 0.5)), cb = Math.min(N, Math.ceil(xs[k + 1] - 0.5));
        mask.fill(1, row * N + ca, row * N + Math.max(ca, cb));
      }
    }
  }
  return mask;
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
    return [u / sp + half + 0.5, half - v / sp + 0.5]; // pixel-edge coordinates: pixel c spans c..c+1
  };
  const mask = strokeMask(water.rivers.map((r) => r.pts.map(toPx)), N);
  const anyRiver = mask.includes(1);
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
    const area = fillMask(water.riverAreas.map((ra) => ra.rings.map((ring) => ring.map(toPx))), N);
    const bank = new Uint8Array(N * N);
    for (let i = 0; i < bank.length; i++) if (area[i]) anyArea = true; else bank[i] = 1;
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
  const lakeRings = water.lakes.map((lake) => lake.rings.map((ring) => ring.map(toPx)));
  const lakeMask = fillMask(lakeRings, N);
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
    // name each lake from the OSM outline that covers its centre
    for (const [id, i] of best) lakeInfo.push({ i, area_m2: sizes[id] * sp * sp, shore_real_m: low[id], name: "" });
    water.lakes.forEach((lake, k) => {
      if (!lake.name) return;
      for (const L of lakeInfo) if (!L.name && inRings([(L.i % N) + 0.5, Math.floor(L.i / N) + 0.5], lakeRings[k])) L.name = lake.name;
    });
  }
  return { heights: out, wet, riverLine: mask, riversCut: anyRiver || anyArea, lakes, lakeInfo };
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
 * Which way the river line flows at pixel `i`: +1 if the carved line runs downhill away from
 * it (water goes into the map from here), -1 if uphill (water arrives here), 0 if too flat to
 * tell. Walks the river line (all rivers, 8-connected) 0.6 to 2.4 km from the point and compares
 * the ground there, at its 25th percentile, with the ground at the point. At an exit every river
 * inland is upstream, so even a tributary in the walk reads uphill; at an entry the main river
 * downstream pulls the low percentile down.
 */
function flowAway(i, line, game, N) {
  const near = [], r0 = Math.floor(i / N), c0 = i % N;
  for (let r = r0 - 3; r <= r0 + 3; r++) for (let c = c0 - 3; c <= c0 + 3; c++)
    if (r >= 0 && c >= 0 && r < N && c < N && line[r * N + c]) near.push(r * N + c);
  if (!near.length) return 0;
  const dist = new Map(near.map((k) => [k, 0])), ring = [];
  let frontier = near;
  for (let step = 1; step <= 150 && frontier.length; step++) {
    const next = [];
    for (const k of frontier) {
      const r = Math.floor(k / N), c = k % N;
      for (let dr = -1; dr <= 1; dr++) for (let dc = -1; dc <= 1; dc++) {
        const rr = r + dr, cc = c + dc, j = rr * N + cc;
        if ((dr || dc) && rr >= 0 && cc >= 0 && rr < N && cc < N && line[j] && !dist.has(j)) { dist.set(j, step); next.push(j); }
      }
    }
    if (step >= 40) for (const j of next) ring.push(game[j]);
    frontier = next;
  }
  if (ring.length < 10) return 0;
  ring.sort((p, q) => p - q);
  const here = near.reduce((t, k) => t + game[k], 0) / near.length, there = ring[Math.floor(ring.length / 4)];
  return here - there > 1 ? 1 : there - here > 1 ? -1 : 0;
}

/**
 * Where to put water sources in the Map Editor: where each sizeable river flows into the square,
 * where one starts inside it, where it leaves (no source there), and the middle of each lake of
 * 4 ha or more. The basemap's river lines are cut at tile edges and their direction can't be
 * trusted, so which way each flows is read from the ground along the carved line (flowAway).
 * Positions are the editor's: metres from the map centre, x east and z north, plus the ground
 * height there in game metres.
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
  const lenByName = new Map();
  const ways = water.rivers.map((r) => ({ name: r.name || "unnamed river", uv: r.pts.map(([lo, la]) => lonLatToSquare(sq, lo, la)) }));
  for (const w of ways) {
    let L = 0;
    for (let k = 1; k < w.uv.length; k++) if (inside(w.uv[k]) || inside(w.uv[k - 1])) L += Math.hypot(w.uv[k][0] - w.uv[k - 1][0], w.uv[k][1] - w.uv[k - 1][1]);
    lenByName.set(w.name, (lenByName.get(w.name) || 0) + L);
  }
  // every place a sizeable river crosses the edge, nudged 3 px inside
  const cand = [];
  for (const w of ways) {
    if ((lenByName.get(w.name) || 0) < 1500) continue;
    for (let k = 1; k < w.uv.length; k++) {
      const a = w.uv[k - 1], b = w.uv[k];
      if (inside(a) === inside(b)) continue;
      const [o, i] = inside(b) ? [a, b] : [b, a]; // outside, inside
      let lo = 0, hi = 1;
      for (let it = 0; it < 30; it++) { const m = (lo + hi) / 2; inside([o[0] + (i[0] - o[0]) * m, o[1] + (i[1] - o[1]) * m]) ? (hi = m) : (lo = m); }
      const e = [o[0] + (i[0] - o[0]) * hi, o[1] + (i[1] - o[1]) * hi];
      const toC = Math.hypot(e[0], e[1]) || 1;
      cand.push(at(px([e[0] - (e[0] / toC) * 3 * sp, e[1] - (e[1] / toC) * 3 * sp]), "river crossing", w.name));
    }
  }
  // A river's real ends inside the square are the piece ends that touch no other river line
  // (pieces of neighbouring tiles overlap, so a cut end always touches its continuation; a
  // tributary's mouth touches the river it joins).
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
  // Downhill from a crossing into the map: an entry; uphill: an exit. Downhill from an end: the
  // river starts there; uphill: it is a mouth (into a lake or the sea) and needs nothing. Where
  // the ground is too flat to tell, the river's highest crossing or end is where it comes from.
  const line = carved.riverLine, dir = new Map();
  for (const c of cand) dir.set(c, line ? flowAway(c.row * N + c.col, line, fit.game, N) : 0);
  const top = new Map();
  for (const c of cand) if (!top.has(c.name) || c.ground_game_m > top.get(c.name).ground_game_m) top.set(c.name, c);
  for (let k = cand.length - 1; k >= 0; k--) {
    const c = cand[k], d = dir.get(c), up = d ? d > 0 : top.get(c.name) === c;
    if (c.kind === "river end") up ? (c.kind = "river start") : cand.splice(k, 1);
    else c.kind = up ? "river entry" : "river exit";
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

/** PNG from already-filtered scanlines (each row: filter byte + pixels), deflated with CompressionStream. */
async function pngFile(raw, w, h, depth, colourType) {
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
  ihdr.set([depth, colourType, 0, 0, 0], 8);
  const sig = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]);
  return new Blob([sig, chunk("IHDR", ihdr), chunk("IDAT", z), chunk("IEND", new Uint8Array())], { type: "image/png" });
}

/** 16-bit greyscale PNG (colour type 0, depth 16) from a Uint16Array. */
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
  return pngFile(raw, w, h, 16, 0);
}

/** 8-bit RGB PNG from a Uint8Array of w * h * 3 bytes. */
export async function pngRGB(rgb, w, h) {
  const stride = 1 + w * 3, raw = new Uint8Array(stride * h);
  for (let y = 0; y < h; y++) raw.set(rgb.subarray(y * w * 3, (y + 1) * w * 3), y * stride + 1);
  return pngFile(raw, w, h, 8, 2);
}

// ---------------------------------------------------------------- names, checks, and where the water goes

/** A file name from a place name: accents dropped (Zürich -> zurich, Ærø -> aero), anything else not a-z or 0-9 -> "-"; "" for a name in another script. */
const LETTERS = { æ: "ae", ø: "o", œ: "oe", ß: "ss", ł: "l", đ: "d", ð: "d", þ: "th", ı: "i" };
export const slugify = (s) => String(s).normalize("NFKD").replace(/\p{M}+/gu, "").toLowerCase()
  .replace(/[æøœßłđðþı]/g, (ch) => LETTERS[ch]).replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40).replace(/-+$/, "");
/** A file name from a centre point: 35.58n-82.56w. */
export const coordName = (lat, lon) =>
  `${Math.abs(lat).toFixed(2)}${lat < 0 ? "s" : "n"}-${Math.abs(lon).toFixed(2)}${lon < 0 ? "w" : "e"}`;

export const SCALES = [0.5, 0.75, 1, 1.5, 2];
/** What is wrong with a square's settings, or null. The page's controls can't produce a bad one; a hand-made link or command can. */
export function squareProblem(sq) {
  if (!(isFinite(sq.lat) && Math.abs(sq.lat) <= 85)) return "latitude must be within ±85";
  if (!(isFinite(sq.lon) && Math.abs(sq.lon) <= 180)) return "longitude must be within ±180";
  if (!(isFinite(sq.rotation) && Math.abs(sq.rotation) <= 180)) return "rotation takes degrees from -180 to 180";
  if (!SCALES.includes(sq.scale)) return `scale takes ${SCALES.slice(0, -1).join(", ")} or ${SCALES.at(-1)}`;
  if (!["auto", "slopes"].includes(sq.vscale) && !(typeof sq.vscale === "number" && sq.vscale > 0 && sq.vscale <= 4))
    return "height takes auto, slopes or a factor above 0, up to 4";
  const range = { sm: [0, 4], rd: [0, 40], rw: [8, 200], ld: [0, 20] };
  for (const [k, [lo, hi]] of Object.entries(range))
    if (sq[k] !== undefined && !(isFinite(sq[k]) && sq[k] >= lo && sq[k] <= hi)) return `${k} takes ${lo} to ${hi}`;
  return null;
}

/**
 * A water source's spot in words, in the heightmap's own frame (top of the image = top of the
 * map as imported): "top edge, 30% from the left", or "30% from the left, 70% down".
 */
export function describeSpot({ col, row }) {
  const last = CS1.px - 1, pc = (v) => `${Math.round((v / last) * 100)}%`, near = 0.04 * last;
  if (row < near) return `top edge, ${pc(col)} from the left`;
  if (row > last - near) return `bottom edge, ${pc(col)} from the left`;
  if (col < near) return `left edge, ${pc(row)} down from the top`;
  if (col > last - near) return `right edge, ${pc(row)} down from the top`;
  if (Math.hypot(col - last / 2, row - last / 2) < 0.06 * last) return "near the centre";
  return `${pc(col)} from the left, ${pc(row)} down from the top`;
}

// 3 x 5 pixel digits for numbering pins
const DIGITS = ["111101101101111", "010110010010111", "111001111100111", "111001111001111", "101101111001001",
  "111100111001111", "111100111101111", "111001001001001", "111101111101111", "111101111001111"];

/**
 * A picture of the map to place water sources from: shaded terrain, the 9 x 9 tile grid, water in
 * blue, and numbered pins (dark blue: river enters or starts; light blue: lake; grey: river leaves).
 * Returns RGB bytes, CS1.px square, oriented like the heightmap.
 */
export function waterMap({ fit, carved, sources }) {
  const N = CS1.px, g = fit.game, rgb = new Uint8Array(N * N * 3);
  const lo = fit.seaLevel ?? fit.gameMin, span = Math.max(fit.gameMax - lo, 1);
  for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
    const i = r * N + c;
    const dx = g[r * N + Math.min(c + 1, N - 1)] - g[r * N + Math.max(c - 1, 0)];
    const dy = g[Math.min(r + 1, N - 1) * N + c] - g[Math.max(r - 1, 0) * N + c];
    const shade = Math.max(0.35, Math.min(1.25, 0.9 + (-dx + -dy) * 0.04)); // light from the top left
    const t = (g[i] - lo) / span;
    let col = [(150 + 70 * t) * shade, (175 + 40 * t) * shade, (130 + 70 * t) * shade];
    if (carved?.wet?.[i]) col = [70, 125, 200];
    if (fit.sea?.[i]) col = [45, 92, 155];
    if ((c % 120 === 0 || r % 120 === 0)) col = col.map((v) => v * 0.7); // tile lines, every 1,920 m
    rgb.set(col.map((v) => Math.max(0, Math.min(255, Math.round(v)))), 3 * i);
  }
  const dot = (cx, cy, rad, colr) => {
    for (let y = -rad; y <= rad; y++) for (let x = -rad; x <= rad; x++) {
      const X = cx + x, Y = cy + y;
      if (X < 0 || Y < 0 || X >= N || Y >= N || x * x + y * y > rad * rad) continue;
      rgb.set(colr, 3 * (Y * N + X));
    }
  };
  sources.forEach((s, k) => {
    const cx = Math.min(N - 17, Math.max(16, s.col)), cy = Math.min(N - 17, Math.max(16, s.row));
    dot(cx, cy, 16, [255, 255, 255]);
    dot(cx, cy, 13, s.kind === "lake" ? [40, 190, 220] : s.kind === "river exit" ? [130, 130, 130] : [20, 70, 190]);
    const text = String(k + 1), S = 3, w = text.length * 4 * S - S;
    [...text].forEach((d, j) => {
      const bits = DIGITS[+d];
      for (let b = 0; b < 15; b++) if (bits[b] === "1")
        for (let yy = 0; yy < S; yy++) for (let xx = 0; xx < S; xx++) {
          const X = cx - (w >> 1) + j * 4 * S + (b % 3) * S + xx, Y = cy - 7 + Math.floor(b / 3) * S + yy;
          rgb.set([255, 255, 255], 3 * (Y * N + X));
        }
    });
  });
  return rgb;
}

// ---------------------------------------------------------------- the whole map, for the page and the CLI

/** Playability defaults. sm: smoothing sigma in 16 m pixels; rd: river depth m; rw: river half-width m; ld: lake depth m. */
export const DEFAULTS = { sm: 1, rd: 10, rw: 40, ld: 4 };
// `check`: what an hour-long game test of a preset's square found, when it didn't all pass (PL-857).
export const PRESETS = [
  { name: "Asheville", slug: "asheville", lon: -82.555, lat: 35.58 },
  { name: "Yosemite Valley", slug: "yosemite", lon: -119.575, lat: 37.735 },
  { name: "Rio de Janeiro", slug: "rio", lon: -43.205, lat: -22.94,
    check: "In an hour-long game test of this square, a little water pooled past a few shorelines and two small rivers weren't wet all the way." },
  { name: "Hong Kong", slug: "hong-kong", lon: 114.17, lat: 22.29 },
  { name: "Innsbruck", slug: "innsbruck", lon: 11.4, lat: 47.27 },
  { name: "Grand Canyon", slug: "grand-canyon", lon: -112.11, lat: 36.08 },
  { name: "Pittsburgh", slug: "pittsburgh", lon: -80, lat: 40.44 },
  { name: "Charleston", slug: "charleston", lon: -79.93, lat: 32.78,
    check: "In an hour-long game test of this square, the marsh and tidal creeks came out less true to the real ground than our other maps." },
];

/** The height factor an option gives: "auto" and "slopes" (1 / ground scale) are capped so the map fits under 1,024 m. */
export const heightFactor = (vscale, scale, auto) => vscale === "auto" ? auto : vscale === "slopes" ? Math.min(1 / scale, auto) : vscale;

/** A square and its options as the page's link keeps them (the part after #), and back. */
export function parseHash(hash) {
  const p = new URLSearchParams(hash.replace(/^#/, "")), o = {};
  if (p.has("c")) {
    const [lon, lat] = p.get("c").split(",").map(Number);
    if (isFinite(lon) && isFinite(lat)) Object.assign(o, { lon, lat });
  }
  if (p.has("r")) o.rotation = Number(p.get("r")) || 0;
  if (p.has("s")) o.scale = Number(p.get("s")) || 1;
  if (p.has("h")) o.vscale = ["auto", "slopes"].includes(p.get("h")) ? p.get("h") : Number(p.get("h"));
  if (p.has("rivers")) o.rivers = p.get("rivers") !== "0";
  if (p.has("n")) o.name = p.get("n");
  for (const k of Object.keys(DEFAULTS)) if (p.has(k) && isFinite(Number(p.get(k)))) o[k] = Number(p.get(k));
  return o;
}
export function squareHash(o) {
  const p = new URLSearchParams({
    c: `${o.lon.toFixed(5)},${o.lat.toFixed(5)}`, r: o.rotation ?? 0, s: o.scale ?? 1,
    h: o.vscale ?? "auto", rivers: o.rivers === false ? 0 : 1, n: o.name ?? "map",
  });
  for (const k of Object.keys(DEFAULTS)) if (o[k] !== undefined && o[k] !== DEFAULTS[k]) p.set(k, o[k]);
  return "#" + p.toString().replaceAll("%2C", ",");
}

/** Smooth, carve, fit and place water sources: everything after the downloads, cheap enough to rerun on any option change. */
export function buildMap({ sq, elev, w }, opts = {}) {
  const o = { ...DEFAULTS, vscale: "auto", ...opts };
  const ground = smooth(elev.heights, o.sm);
  const carved = w ? carveWater(ground, sq, w, { depth: o.rd, halfWidth: o.rw, lakeDepth: o.ld })
    : { heights: ground, wet: null, riverLine: null, riversCut: false, lakes: 0, lakeInfo: [] };
  const fit = fitHeights(ground, carved.heights, { sea: elev.sea, verticalScale: (auto) => heightFactor(o.vscale, sq.scale, auto) });
  const sources = w ? waterSources(sq, w, carved, fit) : [];
  const note = w ? `${new Set(w.rivers.map((r) => r.name || "?")).size} rivers (${w.rivers.length} pieces` +
    `${w.riverAreas?.length ? `, ${w.riverAreas.length} wide-river outlines` : ""}), ${carved.lakes} lakes · OSM via OpenFreeMap tiles, zoom ${w.zoom}` : null;
  return { carved, fit, sources, note };
}

/** The sidecar JSON: where the square is, how heights map, and where the water goes. */
export function mapDetails({ sq, elev, w, map, opts = {}, file, link, note }) {
  const o = { ...DEFAULTS, ...opts }, { fit, carved, sources } = map;
  const r1 = (v) => Math.round(v * 10) / 10;
  return {
    game: "Cities: Skylines 1",
    heightmap: { file, px: CS1.px, bit_depth: 16, extent_m: extentOf(sq),
      spacing_m: extentOf(sq) / (CS1.px - 1), height_scale_m: CS1.maxHeight },
    center: { lon: +sq.lon.toFixed(6), lat: +sq.lat.toFixed(6) },
    rotation_deg: sq.rotation,
    scale: sq.scale,
    corners_lonlat: corners(sq).slice(0, 4).map(([x, y]) => [+x.toFixed(6), +y.toFixed(6)]),
    heights: {
      real_min_m: r1(fit.realMin), real_max_m: r1(fit.realMax), vertical_scale: +fit.verticalScale.toFixed(4),
      game_m: "(real_m - base_m) * vertical_scale + 50", base_m: r1(fit.base),
      game_min_m: r1(fit.gameMin), game_max_m: r1(fit.gameMax),
      sea_level_game_m: fit.seaLevel === null ? null : r1(fit.seaLevel),
    },
    water: {
      rivers_and_lakes_cut: !!w, rivers_cut: !!carved.riversCut, lakes_lowered: carved.lakes || 0,
      open_sea: !!fit.sea, note: note ?? map.note,
      source: w ? `OpenStreetMap via OpenFreeMap vector tiles (OpenMapTiles schema), zoom ${w.zoom}` : null,
      river_depth_m: o.rd, river_half_width_m: o.rw, lake_depth_m: o.ld,
    },
    terrain_smoothing_m: o.sm * 16,
    // x east and z north, metres from the map centre; heights in game metres
    water_sources: sources.map(({ col, row, ...s }, k) => ({ pin: k + 1, ...s, where: describeSpot({ col, row }) })),
    tiles: { grid: "9 x 9", tile_game_m: 1920, tile_real_m: 1920 * sq.scale, base_game_buildable: "middle 5 x 5",
      middle_25_real_m: 9600 * sq.scale, all_81_real_m: extentOf(sq), start_tile: "centre tile" },
    elevation: { source: "AWS Terrain Tiles (Terrarium)", zoom: elev.zoom },
    link,
  };
}

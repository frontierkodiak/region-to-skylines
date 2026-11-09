import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CS1, corners, extentOf, squareToLonLat, sampleElevation, fetchWater, cachedWater, fetchBasemapWater, carveWater, seaMask, fitHeights, smooth, waterSources, encode16, png16 } from "./terrain.js";

const PRESETS = [
  { name: "Asheville", slug: "asheville", lon: -82.555, lat: 35.58 },
  { name: "Yosemite Valley", slug: "yosemite", lon: -119.575, lat: 37.735 },
  { name: "Rio de Janeiro", slug: "rio", lon: -43.205, lat: -22.94 },
  { name: "Hong Kong", slug: "hong-kong", lon: 114.17, lat: 22.29 },
  { name: "Innsbruck", slug: "innsbruck", lon: 11.4, lat: 47.27 },
  { name: "Grand Canyon", slug: "grand-canyon", lon: -112.11, lat: 36.08 },
];

const $ = (id) => document.getElementById(id);
// Playability defaults. sm: smoothing sigma in 16 m pixels; rd: river depth m; rw: river half-width m; ld: lake depth m.
const DEFAULTS = { sm: 1, rd: 10, rw: 40, ld: 4 };
const state = { lon: -82.555, lat: 35.58, rotation: 0, scale: 1, vscale: "auto", rivers: true, ...DEFAULTS };
let result = null, job = null;

// ---------------------------------------------------------------- URL state

function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  if (p.has("c")) {
    const [lon, lat] = p.get("c").split(",").map(Number);
    if (isFinite(lon) && isFinite(lat)) Object.assign(state, { lon, lat });
  }
  if (p.has("r")) state.rotation = Number(p.get("r")) || 0;
  if (p.has("s")) state.scale = Number(p.get("s")) || 1;
  if (p.has("h")) state.vscale = ["auto", "slopes"].includes(p.get("h")) ? p.get("h") : Number(p.get("h"));
  if (p.has("rivers")) state.rivers = p.get("rivers") !== "0";
  if (p.has("n")) $("name").value = p.get("n");
  for (const k of Object.keys(DEFAULTS)) if (p.has(k) && isFinite(Number(p.get(k)))) state[k] = Number(p.get(k));
}
function writeHash() {
  const p = new URLSearchParams({
    c: `${state.lon.toFixed(5)},${state.lat.toFixed(5)}`, r: state.rotation, s: state.scale,
    h: state.vscale, rivers: state.rivers ? 1 : 0, n: $("name").value,
  });
  for (const k of Object.keys(DEFAULTS)) if (state[k] !== DEFAULTS[k]) p.set(k, state[k]);
  history.replaceState(null, "", "#" + p.toString().replaceAll("%2C", ","));
}
readHash();
$("rot").value = state.rotation; $("rotOut").textContent = `${state.rotation}°`;
$("scale").value = String(state.scale); $("vscale").value = String(state.vscale); $("rivers").checked = state.rivers;
for (const k of Object.keys(DEFAULTS)) $(k).value = String(state[k]);

// ---------------------------------------------------------------- map

const map = new maplibregl.Map({
  container: "map",
  style: "https://tiles.openfreemap.org/styles/liberty",
  center: [state.lon, state.lat],
  zoom: 10,
  bearing: state.rotation, // the map turns with the square, so the square stays upright like in the game
  attributionControl: { compact: true },
});
map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), "top-left");
map.dragRotate.disable(); map.touchZoomRotate.disableRotation(); // rotate with the slider

/** The square, its 9 x 9 grid of in-game tiles, the base game's middle 25 and the starting tile. */
function squareGeoJSON() {
  const h = extentOf(state) / 2, t = (2 * h) / 9, f = [];
  const line = (a, b) => [a, b].map(([u, v]) => squareToLonLat(state, u, v));
  for (let k = 1; k < 9; k++) {
    const x = -h + k * t, inner = k >= 2 && k <= 7; // lines 2..7 bound the middle 5 x 5
    f.push({ type: "Feature", properties: { kind: inner ? "grid25" : "grid" }, geometry: { type: "LineString", coordinates: line([x, -h], [x, h]) } });
    f.push({ type: "Feature", properties: { kind: inner ? "grid25" : "grid" }, geometry: { type: "LineString", coordinates: line([-h, x], [h, x]) } });
  }
  return {
    type: "FeatureCollection",
    features: [
      { type: "Feature", properties: { kind: "map" }, geometry: { type: "Polygon", coordinates: [corners(state)] } },
      ...f,
      { type: "Feature", properties: { kind: "inner" }, geometry: { type: "LineString", coordinates: corners(state, 5 / 9) } },
      { type: "Feature", properties: { kind: "starttile" }, geometry: { type: "Polygon", coordinates: [corners(state, 1 / 9)] } },
    ],
  };
}

map.on("load", () => {
  map.addSource("dem", {
    type: "raster-dem", encoding: "terrarium", tileSize: 256, maxzoom: 13,
    tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
  });
  const firstSymbol = map.getStyle().layers.find((l) => l.type === "symbol")?.id;
  map.addLayer({ id: "hillshade", type: "hillshade", source: "dem",
    paint: { "hillshade-exaggeration": 0.45, "hillshade-shadow-color": "#3d4a40" } }, firstSymbol);
  map.addSource("square", { type: "geojson", data: squareGeoJSON() });
  map.addLayer({ id: "sq-fill", type: "fill", source: "square", filter: ["==", "kind", "map"],
    paint: { "fill-color": "#e8590c", "fill-opacity": 0.08 } });
  map.addLayer({ id: "sq-line", type: "line", source: "square", filter: ["==", "kind", "map"],
    paint: { "line-color": "#e8590c", "line-width": 2.5 } });
  map.addLayer({ id: "sq-grid", type: "line", source: "square", filter: ["in", "kind", "grid", "grid25"],
    paint: { "line-color": "#e8590c", "line-width": 0.8, "line-opacity": ["match", ["get", "kind"], "grid25", 0.45, 0.22] } });
  map.addLayer({ id: "sq-start", type: "line", source: "square", filter: ["==", "kind", "inner"],
    paint: { "line-color": "#e8590c", "line-width": 1.6, "line-dasharray": [3, 2] } });
  map.addLayer({ id: "sq-starttile", type: "fill", source: "square", filter: ["==", "kind", "starttile"],
    paint: { "fill-color": "#e8590c", "fill-opacity": 0.18, "fill-outline-color": "#e8590c" } });
  map.addSource("sources", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  map.addLayer({ id: "sources", type: "circle", source: "sources",
    paint: { "circle-radius": 5, "circle-color": ["match", ["get", "kind"], "lake", "#1fb5d6", "exit", "#9aa3ad", "#1d5fd1"],
      "circle-stroke-color": "#fff", "circle-stroke-width": 1.5 } });
  fitToSquare(false);
  schedule(0);
});

/** Centre the square, turn the map by its rotation and zoom so the whole square shows. */
function fitToSquare(animate = true) {
  const c = map.getContainer(), px = Math.max(120, Math.min(c.clientWidth, c.clientHeight) - 80);
  const zoom = Math.log2((40075016.686 * Math.cos((state.lat * Math.PI) / 180) * px) / (512 * extentOf(state)));
  const cam = { center: [state.lon, state.lat], zoom, bearing: state.rotation };
  animate ? map.easeTo({ ...cam, duration: 900 }) : map.jumpTo(cam);
}

function refreshSquare() {
  map.getSource("square")?.setData(squareGeoJSON());
}
map.on("move", () => {
  const c = map.getCenter();
  state.lon = c.lng; state.lat = c.lat;
  refreshSquare();
});
map.on("moveend", () => { writeHash(); schedule(); });

// ---------------------------------------------------------------- controls

function renderPresets() {
  $("presets").replaceChildren(...PRESETS.map((p) => {
    const b = document.createElement("button");
    b.textContent = p.name;
    const on = Math.abs(p.lon - state.lon) < 0.01 && Math.abs(p.lat - state.lat) < 0.01;
    b.setAttribute("aria-pressed", on);
    b.onclick = () => {
      Object.assign(state, { lon: p.lon, lat: p.lat });
      $("name").value = p.slug;
      refreshSquare();
      fitToSquare();
    };
    return b;
  }));
}
renderPresets();

$("rot").oninput = (e) => {
  state.rotation = Number(e.target.value);
  $("rotOut").textContent = `${state.rotation}°`;
  refreshSquare();
  map.jumpTo({ bearing: state.rotation });
};
$("rot").onchange = () => { fitToSquare(); writeHash(); schedule(); };
$("scale").onchange = (e) => { state.scale = Number(e.target.value); scaleNote(); refreshSquare(); fitToSquare(); };

/** Real ground in km, one way everywhere: 2 decimals at true size (17.28, 9.6, 1.92), else 1 (25.9). */
const km = (metres, s = state.scale) =>
  (metres / 1000).toFixed(s === 1 ? 2 : 1).replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "") + " km";
/** The height factor the current options give: Auto and Real slopes are capped so the map fits. */
const heightFactor = (sq, auto) => state.vscale === "auto" ? auto : state.vscale === "slopes" ? Math.min(1 / sq.scale, auto) : state.vscale;

/**
 * What the scale choice does, in plain words, from the real extent and the height factor in
 * use (once terrain is loaded). Cities: Skylines 1 terrain is 1 game metre = 1 real metre.
 */
function scaleNote(fit = result?.fit) {
  const s = state.scale, E = 17280 * s, el = $("scalenote");
  const vs = fit && result.sq.scale === s ? fit.verticalScale : null;
  const steep = vs === null ? "" : (() => {
    const f = vs * s;
    const how = Math.abs(f - 1) < 0.03 ? "as steep as real" : `${f.toFixed(2)}x as steep as real`;
    return ` With Height at ${vs.toFixed(2)}x, slopes are ${how}` +
      (Math.abs(f - 1) >= 0.03 && state.vscale !== "slopes" && s !== 1 ? "; Height \u201cReal slopes\u201d keeps them true." : ".");
  })();
  el.classList.toggle("warn", s !== 1);
  el.textContent = s === 1
    ? `True size: the game's map is 17.28 km across and 1 game metre is 1 real metre, so a real block is a game block. The 25 tiles you can build on without mods are the middle 9.6 km.${vs !== null && vs < 1 ? steep : ""}`
    : s > 1
      ? `Fits more region: ${km(E)} of real ground squeezed into the 17.28 km map, so everything is ${Math.round(100 / s)}% of real size and real streets won't match the game's road sizes.${steep}`
      : `Zooms in: ${km(E)} of real ground stretched over the 17.28 km map, so everything is ${(1 / s).toFixed(1)}x real size. Good for a single town; the region around it is lost.${steep}`;
  const t = (id, v) => ($(id).textContent = v);
  t("tTile", s === 1 ? "1.92 km" : `1.92 km of game ground (${km(1920 * s)} real)`);
  t("t25", km(9600 * s)); t("t81", km(E));
}
scaleNote();
$("vscale").onchange = (e) => {
  state.vscale = ["auto", "slopes"].includes(e.target.value) ? e.target.value : Number(e.target.value);
  writeHash();
  if (result) finish(result.raw); // no refetch needed
};
$("rivers").onchange = (e) => { state.rivers = e.target.checked; writeHash(); refineButton(); schedule(0); };
for (const k of Object.keys(DEFAULTS)) $(k).onchange = (e) => { state[k] = Number(e.target.value); writeHash(); if (result) finish(result.raw); };
$("resetplay").onclick = () => { Object.assign(state, DEFAULTS); for (const k of Object.keys(DEFAULTS)) $(k).value = String(state[k]); writeHash(); if (result) finish(result.raw); };
$("name").onchange = () => { writeHash(); finishLabel(); };

// Nominatim usage policy (read 2026-11-09): searches only when the user submits, never as they
// type (no autocomplete); at most one request per second; repeated queries answered from a cache.
// The endpoint lives in this one constant so it can be switched without other changes.
const NOMINATIM = "https://nominatim.openstreetmap.org/search";
let lastSearch = 0;
const searchCache = new Map();
$("search").onsubmit = async (e) => {
  e.preventDefault();
  const q = $("q").value.trim();
  if (!q) return;
  setStatus(`Searching “${q}”…`);
  try {
    let hit;
    if (searchCache.has(q.toLowerCase())) hit = searchCache.get(q.toLowerCase());
    else {
      const wait = lastSearch + 1100 - Date.now();
      if (wait > 0) await new Promise((res) => setTimeout(res, wait));
      lastSearch = Date.now();
      const r = await fetch(`${NOMINATIM}?format=jsonv2&limit=1&q=${encodeURIComponent(q)}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      [hit] = await r.json();
      searchCache.set(q.toLowerCase(), hit);
    }
    if (!hit) return setStatus(`No place called “${q}”`);
    Object.assign(state, { lon: Number(hit.lon), lat: Number(hit.lat) });
    $("name").value = q.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || "map";
    refreshSquare();
    fitToSquare();
  } catch {
    setStatus("Search failed; drag the map instead");
  }
};

// ---------------------------------------------------------------- build

let timer;
function schedule(delay = 450) {
  clearTimeout(timer);
  timer = setTimeout(build, delay);
}
const setStatus = (t) => ($("status").textContent = t);

async function build() {
  job?.abort();
  const ctl = (job = new AbortController());
  const sq = { ...state };
  renderPresets();
  setDownload("busy");
  try {
    setStatus("Fetching elevation…");
    const elev = await sampleElevation(sq, {
      signal: ctl.signal,
      onProgress: (d, n) => setStatus(`Fetching elevation ${d}/${n} tiles…`),
    });
    if (ctl.signal.aborted) return;
    elev.sea = seaMask(elev.heights);
    if (!sq.rivers) return finish({ sq, elev, w: null, waterNote: "off", water: "off" });
    // Live OSM water fetched earlier for this square (the user asked for it) is reused without asking again.
    const live = cachedWater(sq);
    if (live) return finish({ sq, elev, w: live, water: "osm" });
    // Bare terrain at once; then the rivers and lakes from the basemap's vector tiles, a second or two.
    finish({ sq, elev, w: null, waterNote: "loading…", water: "loading" }, "Loading rivers and lakes…");
    let w = null;
    try {
      w = await fetchBasemapWater(sq, ctl.signal);
    } catch {
      if (ctl.signal.aborted) return;
    }
    if (ctl.signal.aborted) return;
    finish({ sq, elev, w, water: w ? "basemap" : "failed",
      waterNote: w ? undefined : "The basemap's water tiles didn't load: not cut. Move the map a little to retry." });
  } catch (err) {
    if (!ctl.signal.aborted) setStatus(`Failed: ${err.message}. Move the map to retry.`);
  }
}

/**
 * Opt-in only: ask a public Overpass server, once, for this square's full OSM water. The basemap
 * water is the default because public Overpass instances are not meant as an app's backend.
 */
async function refine() {
  if (!result || !["basemap", "failed"].includes(result.raw.water)) return;
  const ctl = job, { raw } = result, t0 = Date.now();
  let asking = "";
  $("refine").disabled = true;
  const tick = setInterval(() => asking && setStatus(`Asking ${asking} for live OSM water · ${Math.round((Date.now() - t0) / 1000)} s`), 500);
  try {
    const w = await fetchWater(raw.sq, ctl.signal, (host, k, n) => (asking = `${host} (${k} of ${n})`));
    if (ctl.signal.aborted || result.raw !== raw) return;
    finish({ ...raw, w, water: "osm", waterNote: undefined });
  } catch {
    if (ctl.signal.aborted || result.raw !== raw) return;
    setStatus("No Overpass server answered; the basemap water stays. Try again later.");
  } finally {
    clearInterval(tick);
    refineButton();
  }
}
$("refine").onclick = refine;
function refineButton() {
  const b = $("refine"), mode = result?.raw.water;
  $("refinewrap").hidden = !state.rivers;
  b.disabled = !["basemap", "failed"].includes(mode);
  b.textContent = mode === "osm" ? "Using live OSM water" : "Refine water with live OSM data";
}

/** The download button says whether the map it would save has its rivers and lakes. */
function setDownload(mode) {
  const dl = $("dl");
  dl.disabled = $("dljson").disabled = mode === "busy";
  dl.classList.toggle("partial", mode === "loading" || mode === "failed");
  dl.textContent = {
    busy: "Download heightmap", basemap: "Download heightmap", osm: "Download heightmap", off: "Download heightmap",
    loading: "Download now (rivers still loading)", failed: "Download (no rivers or lakes)",
  }[mode];
}

/** Smooth, carve and fit the fetched terrain with the current options; cheap enough to rerun on any change. */
function finish(raw, status = "") {
  const { sq, elev, w } = raw;
  const ground = smooth(elev.heights, state.sm);
  const carved = w ? carveWater(ground, sq, w, { depth: state.rd, halfWidth: state.rw, lakeDepth: state.ld })
    : { heights: ground, wet: null, riversCut: false, lakes: 0, lakeInfo: [] };
  const fit = fitHeights(ground, carved.heights, { sea: elev.sea, verticalScale: (auto) => heightFactor(sq, auto) });
  const sources = w ? waterSources(sq, w, carved, fit) : [];
  if (w) raw.waterNote = `${new Set(w.rivers.map((r) => r.name || "?")).size} rivers (${w.rivers.length} ${w.fragments ? "pieces" : "OSM ways"}` +
    `${w.riverAreas?.length ? `, ${w.riverAreas.length} wide-river outlines` : ""}), ${carved.lakes} lakes · ` +
    (w.fragments ? `OSM via OpenFreeMap tiles, zoom ${w.zoom}` : "live OSM via Overpass");
  raw.carved = carved;
  result = { raw, fit, sq, sources };
  showStats(fit, elev, raw.waterNote, sq);
  scaleNote(fit);
  drawPreview(fit, carved.wet);
  showSources(sources, fit);
  setStatus(status);
  setDownload(raw.water);
  refineButton();
  $("mapname").textContent = `${fileName()}.png · ${km(extentOf(sq), sq.scale)} · ${Math.round(fit.gameMin)}–${Math.round(fit.gameMax)} m`;
}

/** Water source suggestions: dots on the map, pins in the preview, a list in the panel. */
function showSources(sources, fit) {
  map.getSource("sources")?.setData({ type: "FeatureCollection", features: sources.map((s) => ({
    type: "Feature", properties: { kind: s.kind === "lake" ? "lake" : s.kind === "river exit" ? "exit" : "river" }, geometry: { type: "Point", coordinates: [s.lon, s.lat] } })) });
  const list = $("sources");
  if (!sources.length) {
    list.innerHTML = ["basemap", "osm"].includes(result.raw.water) ? "<li>No sizeable river or lake in this square.</li>" : "<li>Waiting for rivers and lakes…</li>";
  } else {
    list.replaceChildren(...sources.map((s) => {
      const li = document.createElement("li");
      li.className = s.kind === "lake" ? "lake" : s.kind === "river exit" ? "exit" : "river";
      const where = `x ${s.x_m.toLocaleString()}, z ${s.z_m.toLocaleString()}`;
      li.innerHTML = `<b></b> <span></span>`;
      li.querySelector("b").textContent = s.kind === "lake" ? `${s.name} (${s.area_ha} ha)` : `${s.name}, ${{ "river entry": "enters", "river start": "starts", "river exit": "leaves" }[s.kind]}`;
      li.querySelector("span").textContent = s.kind === "lake"
        ? `${where} · source height to ${Math.round(s.surface_game_m)} m`
        : s.kind === "river exit" ? `${where} · drains off the edge; no source here`
        : `${where} · ground ${Math.round(s.ground_game_m)} m`;
      return li;
    }));
  }
  drawPins(sources, fit);
}

const m = (v) => `${Math.round(v).toLocaleString()} m`;
function showStats(fit, elev, waterNote, sq) {
  const rows = [
    ["Real ground", fit.seaLevel === null ? `${m(fit.realMin)} to ${m(fit.realMax)}` : `sea to ${m(fit.realMax)} (sea 10–40 m deep)`],
    ["Relief", m(fit.realMax - fit.base)],
    ["In game", `${m(fit.gameMin)} to ${m(fit.gameMax)} of 1,024 m`],
    ["Height", fit.verticalScale === 1 ? "1:1 true height" : `${fit.verticalScale.toFixed(2)}x` +
      (state.vscale === "slopes" ? (fit.verticalScale < 1 / sq.scale - 1e-6 ? " (real slopes, squeezed to fit)" : " (real slopes)") : state.vscale === "auto" ? " (squeezed to fit)" : ""),
      fit.verticalScale < 1 ? "warn" : ""],
    ["Headroom", m(fit.headroom), fit.headroom < 0 ? "warn" : ""],
  ];
  if (fit.seaLevel !== null) rows.push(["Sea level in game", `${m(fit.seaLevel)} (set the editor's sea level here)`, "warn"]);
  if (fit.clipped > 0) rows.push(["Clipped", `${(fit.clipped * 100).toFixed(2)}% of pixels`, "warn"]);
  rows.push(
    ["Size", `${km(extentOf(sq), sq.scale)} · ${(extentOf(sq) / (CS1.px - 1)).toFixed(1)} m/px`],
    ["Elevation data", `zoom ${elev.zoom} · ${elev.metresPerTilePx.toFixed(1)} m/px · ${elev.tiles} tiles`],
    ["Water", waterNote],
  );
  $("stats").replaceChildren(...rows.flatMap(([k, v, cls]) => {
    const dt = document.createElement("dt"), dd = document.createElement("dd");
    dt.textContent = k; dd.textContent = v; if (cls) dd.className = cls;
    return [dt, dd];
  }));
}

// ---------------------------------------------------------------- downloads

const save = (blob, filename) => {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
};
const baseName = () => ($("name").value.trim().replace(/[^\w.-]+/g, "-") || "map");
// a map saved before (or without) the OSM water says so in its name
const fileName = () => baseName() + (result && ["loading", "failed"].includes(result.raw.water) ? "-no-rivers" : "");

$("dl").onclick = async () => {
  if (!result) return;
  $("dl").disabled = true;
  const blob = await png16(encode16(result.fit.game), CS1.px, CS1.px);
  save(blob, `${fileName()}.png`);
  $("dl").disabled = false;
  if (result.raw.water === "loading") setStatus("Saved without rivers; download again once they load");
};
$("dljson").onclick = () => {
  if (!result) return;
  save(new Blob([JSON.stringify(details(), null, 2)], { type: "application/json" }), `${fileName()}.json`);
};

function details() {
  const { sq, fit, raw } = result;
  const r1 = (v) => Math.round(v * 10) / 10;
  return {
    game: "Cities: Skylines 1",
    heightmap: { file: `${fileName()}.png`, px: CS1.px, bit_depth: 16, extent_m: extentOf(sq),
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
      rivers_and_lakes_cut: !!raw.w, rivers_cut: !!raw.carved.riversCut, lakes_lowered: raw.carved.lakes || 0,
      open_sea: !!fit.sea, note: raw.waterNote,
      source: !raw.w ? null : raw.w.fragments ? `OpenStreetMap via OpenFreeMap vector tiles (OpenMapTiles schema), zoom ${raw.w.zoom}` : "OpenStreetMap via Overpass API (live)",
      river_depth_m: state.rd, river_half_width_m: state.rw, lake_depth_m: state.ld,
    },
    terrain_smoothing_m: state.sm * 16,
    // x east and z north, metres from the map centre; heights in game metres
    water_sources: result.sources.map(({ col, row, ...s }) => s),
    tiles: { grid: "9 x 9", tile_game_m: 1920, tile_real_m: 1920 * sq.scale, base_game_buildable: "middle 5 x 5",
      middle_25_real_m: 9600 * sq.scale, all_81_real_m: extentOf(sq), start_tile: "centre tile" },
    elevation: { source: "AWS Terrain Tiles (Terrarium)", zoom: raw.elev.zoom },
    link: location.href,
  };
}

// ---------------------------------------------------------------- 3D preview

const canvas = $("preview3d");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: true, preserveDrawingBuffer: true });
const PIXEL = 0.45; // render below screen resolution, upscale with crisp pixels
const scene = new THREE.Scene();
const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -100, 100);
camera.position.set(10, 10, 10);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = false;
controls.enablePan = false;
controls.minZoom = 0.6; controls.maxZoom = 6;
controls.minPolarAngle = 0.35; controls.maxPolarAngle = 1.2; // never knock the block flat
controls.addEventListener("change", render);
scene.add(new THREE.HemisphereLight(0xe8f0ff, 0x4a4030, 1.1));
const sun = new THREE.DirectionalLight(0xfff3dd, 2.2);
sun.position.set(-6, 9, -4);
scene.add(sun);
let mesh = null, water = null;

function resize() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w || !h) return;
  renderer.setPixelRatio(PIXEL);
  renderer.setSize(w, h, false);
  const a = w / h, s = 1.12;
  Object.assign(camera, { left: -s * a, right: s * a, top: s, bottom: -s });
  camera.updateProjectionMatrix();
  render();
}
new ResizeObserver(resize).observe(canvas);
function render() { renderer.render(scene, camera); }

const TINT = [[70, 120, 60], [120, 150, 80], [170, 160, 110], [150, 120, 90], [235, 230, 225]];
const BANDS = 14;
function tint(t) {
  t = Math.round(Math.min(1, Math.max(0, t)) * BANDS) / BANDS; // terraced colour bands
  const x = t * (TINT.length - 1), i = Math.min(TINT.length - 2, Math.floor(x)), f = x - i;
  return TINT[i].map((c, k) => (c * (1 - f) + TINT[i + 1][k] * f) / 255);
}

// Soil-coloured walls under the terrain's edge, so the square reads as a diorama block.
function skirt(pos, n) {
  const base = -0.06, v = [], idx = [];
  const ring = [];
  for (let c = 0; c < n; c++) ring.push(c);
  for (let r = 1; r < n; r++) ring.push(r * n + n - 1);
  for (let c = n - 2; c >= 0; c--) ring.push((n - 1) * n + c);
  for (let r = n - 2; r >= 0; r--) ring.push(r * n);
  ring.forEach((i, k) => {
    v.push(pos.getX(i), pos.getY(i), pos.getZ(i), pos.getX(i), base, pos.getZ(i));
    if (k) { const a = 2 * (k - 1), b = 2 * k; idx.push(a, a + 1, b, b, a + 1, b + 1); }
  });
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(v, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return new THREE.Mesh(g, new THREE.MeshLambertMaterial({ color: 0x8a6a4a, side: THREE.DoubleSide, flatShading: true }));
}

// a preview vertex stands for a STEP x STEP block of the heightmap: blue if a river crosses it
function anyWet(wet, r0, c0, step) {
  const N = CS1.px, h = step >> 1;
  for (let r = Math.max(0, r0 - h); r <= Math.min(N - 1, r0 + h); r++)
    for (let c = Math.max(0, c0 - h); c <= Math.min(N - 1, c0 + h); c++) if (wet[r * N + c]) return true;
  return false;
}

function drawPreview(fit, wet) {
  const STEP = 4, n = Math.floor((CS1.px - 1) / STEP) + 1, EXAG = 3;
  const size = 2, k = size / 17280; // scene units per game metre at 1x scale
  const geo = new THREE.PlaneGeometry(size, size, n - 1, n - 1);
  geo.rotateX(-Math.PI / 2);
  const pos = geo.attributes.position, col = new Float32Array(pos.count * 3);
  const lo = fit.seaLevel ?? fit.gameMin, span = Math.max(fit.gameMax - lo, 1);
  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      const i = r * n + c, src = r * STEP * CS1.px + c * STEP, g = fit.game[src];
      pos.setY(i, (g - fit.gameMin) * k * EXAG * (17280 / extentOf(result.sq)));
      let rgb = tint((g - lo) / span);
      if (wet && anyWet(wet, r * STEP, c * STEP, STEP)) rgb = [0.24, 0.47, 0.78];
      if (fit.sea?.[src]) rgb = [0.18, 0.36, 0.6];
      col.set(rgb, 3 * i);
    }
  }
  geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
  geo.computeVertexNormals();
  if (mesh) { scene.remove(mesh); mesh.geometry.dispose(); }
  mesh = new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ vertexColors: true, flatShading: true }));
  mesh.position.y = -0.25;
  mesh.add(skirt(pos, n));
  mesh.add(tileGrid(pos, n));
  scene.add(mesh);
  if (water) { scene.remove(water); water = null; }
  if (fit.seaLevel !== null) {
    water = new THREE.Mesh(new THREE.PlaneGeometry(size, size).rotateX(-Math.PI / 2),
      new THREE.MeshLambertMaterial({ color: 0x3f7fc0, transparent: true, opacity: 0.75 }));
    water.position.y = -0.25 + (fit.seaLevel + 1 - fit.gameMin) * k * EXAG * (17280 / extentOf(result.sq));
    scene.add(water);
  }
  placeNorth(result.sq.rotation);
  previewY = (g) => -0.25 + (g - fit.gameMin) * k * EXAG * (17280 / extentOf(result.sq));
  $("legend").textContent = `Height x${EXAG} · lines: in-game tiles, white = start · drag to orbit`;
  resize();
}

// The 9 x 9 in-game tiles as lines draped on the terrain. At STEP 4 the preview has 270 cells a
// side, so tile edges fall exactly on every 30th vertex row and the lines follow the ground.
const gridMats = [
  new THREE.LineBasicMaterial({ color: 0xe8590c, transparent: true, opacity: 0.4 }), // outer 56 tiles
  new THREE.LineBasicMaterial({ color: 0xe8590c, transparent: true, opacity: 0.85 }), // the base game's middle 25
  new THREE.LineBasicMaterial({ color: 0xffffff }), // the starting tile
];
function tileGrid(pos, n) {
  const T = (n - 1) / 9, lift = 0.006, sets = [[], [], []];
  const P = (r, c) => { const i = r * n + c; return [pos.getX(i), pos.getY(i) + lift, pos.getZ(i)]; };
  for (let k = 1; k < 9; k++) {
    const L = k * T;
    for (let j = 0; j < n - 1; j++) {
      const band = Math.floor(j / T); // the tile this short segment borders, counted across the line
      const set = (k === 4 || k === 5) && band === 4 ? 2 : k >= 2 && k <= 7 && band >= 2 && band <= 6 ? 1 : 0;
      sets[set].push(...P(L, j), ...P(L, j + 1)); // along a row
      sets[set].push(...P(j, L), ...P(j + 1, L)); // along a column
    }
  }
  const grp = new THREE.Group();
  sets.forEach((v, i) => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(v, 3));
    const ls = new THREE.LineSegments(g, gridMats[i]); ls.renderOrder = 2 + i;
    grp.add(ls);
  });
  return grp;
}

// Water-source pins: a pixel-style post with a block on top, blue for rivers, cyan for lakes.
let previewY = () => 0;
const pins = new THREE.Group();
scene.add(pins);
const pinMat = { river: new THREE.MeshLambertMaterial({ color: 0x1d5fd1, flatShading: true }),
  lake: new THREE.MeshLambertMaterial({ color: 0x1fb5d6, flatShading: true }),
  exit: new THREE.MeshLambertMaterial({ color: 0x9aa3ad, flatShading: true }),
  post: new THREE.MeshLambertMaterial({ color: 0xffffff }) };
const postGeo = new THREE.BoxGeometry(0.012, 0.16, 0.012), headGeo = new THREE.BoxGeometry(0.05, 0.05, 0.05);
function drawPins(sources, fit) {
  pins.clear();
  const N = CS1.px;
  for (const s of sources) {
    const x = (s.col / (N - 1)) * 2 - 1, z = (s.row / (N - 1)) * 2 - 1, y = previewY(fit.game[s.row * N + s.col]);
    const post = new THREE.Mesh(postGeo, pinMat.post); post.position.set(x, y + 0.08, z);
    const head = new THREE.Mesh(headGeo, s.kind === "lake" ? pinMat.lake : s.kind === "river exit" ? pinMat.exit : pinMat.river); head.position.set(x, y + 0.18, z);
    pins.add(post, head);
  }
  render();
}

// "N" on the block's edge where true north is (the square's top when unrotated)
const north = (() => {
  const c = document.createElement("canvas"); c.width = c.height = 64;
  const g = c.getContext("2d");
  g.fillStyle = "#e8590c"; g.beginPath(); g.arc(32, 32, 28, 0, 2 * Math.PI); g.fill();
  g.fillStyle = "#fff"; g.font = "bold 40px system-ui, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText("N", 32, 35);
  const t = new THREE.CanvasTexture(c); t.magFilter = THREE.NearestFilter;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, depthTest: false }));
  s.scale.set(0.22, 0.22, 1); s.renderOrder = 10;
  scene.add(s);
  return s;
})();
function placeNorth(rotationDeg) {
  const t = (rotationDeg * Math.PI) / 180;
  north.position.set(-Math.sin(t) * 1.13, -0.15, -Math.cos(t) * 1.13); // scene -z is the map's top edge
}
function finishLabel() {
  if (result) $("mapname").textContent = $("mapname").textContent.replace(/^[^ ]+\.png/, `${fileName()}.png`);
}

// for automated checks
window.__regionmap = { state, get result() { return result; }, details: () => details(), png: () => png16(encode16(result.fit.game), CS1.px, CS1.px) };

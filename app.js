import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CS1, SITE, DEFAULTS, PRESETS, corners, extentOf, squareToLonLat, sampleElevation, fetchBasemapWater, seaMask, buildMap, mapDetails, parseHash, squareHash, encode16, png16, pngRGB, waterMap, slugify, coordName, describeSpot } from "./terrain.js";
import { captureInputs } from "./inputs.js";
import { buildDramaMap, captureDramaInputs, dramaDetails } from "./terrain-drama.mjs";
import { waterRiskDecision } from "./water-risk.js";
import { mountCapabilities } from "./capability-ui.js";
import { mountVegetation } from "./vegetation-ui.js";

const $ = (id) => document.getElementById(id);
const state = { lon: -82.555, lat: 35.58, rotation: 0, scale: 1, vscale: "auto", rivers: true, terrain: "auto", ...DEFAULTS };
let result = null, job = null;
const capabilityView = mountCapabilities($("capabilities"), { onFootprint: showFootprint });
const vegetationView = mountVegetation($("vegetation"));
// What the map is called in the game's New Game list: a name typed into the name field, else
// the preset's or searched place's name, else the name field.
let typedTitle = null, searched = null;
const titleFor = () => typedTitle ?? checkedPreset()?.name ??
  (searched && Math.abs(searched.lon - state.lon) < 0.05 && Math.abs(searched.lat - state.lat) < 0.05 ? searched.q : null) ??
  ($("name").value.trim() || "My region");

// ---------------------------------------------------------------- URL state

function readHash() {
  const { name, ...o } = parseHash(location.hash);
  Object.assign(state, o);
  if (name !== undefined) $("name").value = name;
}
const dramaOn = () => state.terrain === "drama" && state.vscale === "auto";
const withDrama = (hash) => dramaOn() ? hash + "&terrain=drama" : hash;
const link = () => location.origin + location.pathname + withDrama(squareHash({ ...state, name: $("name").value }));
function writeHash() {
  history.replaceState(null, "", withDrama(squareHash({ ...state, name: $("name").value })));
}
readHash();
state.terrain = new URLSearchParams(location.hash.replace(/^#/, "")).get("terrain") === "drama" ? "drama" : "auto";
$("drama").checked = state.terrain === "drama";
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
  map.addSource("footprint",{type:"geojson",data:{type:"FeatureCollection",features:[]}});
  map.addLayer({id:"footprint",type:"line",source:"footprint",paint:{"line-color":"#2f7d4f","line-width":3}});
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
function autoHeight() { state.vscale = "auto"; $("vscale").value = "auto"; }
map.on("moveend", () => {
  if (result && (Math.abs(state.lon-result.sq.lon)>1e-5 || Math.abs(state.lat-result.sq.lat)>1e-5)) autoHeight();
  writeHash(); schedule();
});
map.on("movestart", () => { job?.abort(); capabilityView.reset(); vegetationView.reset(); });

// ---------------------------------------------------------------- controls

function renderPresets() {
  $("presets").replaceChildren(...PRESETS.map((p) => {
    const b = document.createElement("button");
    b.textContent = p.name;
    const on = Math.abs(p.lon - state.lon) < 0.01 && Math.abs(p.lat - state.lat) < 0.01;
    b.setAttribute("aria-pressed", on);
    b.onclick = () => usePreset(p);
    return b;
  }));
}
renderPresets();
function usePreset(p) {
  map.stop();
  autoHeight();
  Object.assign(state, { lon: p.lon, lat: p.lat, rotation: 0 });
  typedTitle = null;
  $("rot").value = state.rotation; $("rotOut").textContent = `${state.rotation}°`;
  $("name").value = p.slug;
  refreshSquare();
  fitToSquare(false);
  writeHash();
  schedule(0);
}

$("rot").oninput = (e) => {
  state.rotation = Number(e.target.value);
  $("rotOut").textContent = `${state.rotation}°`;
  refreshSquare();
  map.jumpTo({ bearing: state.rotation });
};
$("rot").onchange = () => { fitToSquare(); writeHash(); schedule(); };
$("scale").onchange = (e) => { state.scale = Number(e.target.value); refreshSquare(); fitToSquare(); };

/** Real ground in km, one way everywhere: 2 decimals at true size (17.28, 9.6, 1.92), else 1 (25.9). */
const km = (metres, s = state.scale) =>
  (metres / 1000).toFixed(s === 1 ? 2 : 1).replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "") + " km";
$("vscale").onchange = (e) => {
  state.vscale = ["auto", "slopes"].includes(e.target.value) ? e.target.value : Number(e.target.value);
  writeHash();
  if (result) finish(result.raw); // no refetch needed
};
$("rivers").onchange = (e) => { state.rivers = e.target.checked; writeHash(); schedule(0); };
$("drama").onchange = (e) => { state.terrain = e.target.checked ? "drama" : "auto"; writeHash(); if (result) finish(result.raw); };
for (const k of Object.keys(DEFAULTS)) $(k).onchange = (e) => { state[k] = Number(e.target.value); writeHash(); if (result) finish(result.raw); };
$("resetplay").onclick = () => { Object.assign(state, DEFAULTS); for (const k of Object.keys(DEFAULTS)) $(k).value = String(state[k]); writeHash(); if (result) finish(result.raw); };
$("name").onchange = () => { typedTitle = $("name").value.trim() || null; resetWaterRisk(); writeHash(); finishLabel(); if (result) setDownload(result.raw.water); };

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
  setStatus(`Searching "${q}"…`);
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
    if (!hit) return setStatus(`No place called "${q}"`);
    Object.assign(state, { lon: Number(hit.lon), lat: Number(hit.lat) });
    autoHeight();
    $("name").value = slugify(q) || coordName(state.lat, state.lon);
    searched = { q, lon: state.lon, lat: state.lat };
    typedTitle = null;
    refreshSquare();
    fitToSquare(false);
    schedule(0);
  } catch {
    setStatus("Search failed; drag the map instead");
  }
};

// ---------------------------------------------------------------- build

let timer;
function schedule(delay = 450) {
  job?.abort();
  capabilityView.reset();
  vegetationView.reset();
  resetWaterRisk();
  clearTimeout(timer);
  $("previewwrap").setAttribute("aria-busy", "true");
  $("preview3d").hidden = true;
  $("clip-warning").hidden = true;
  $("preview-place").textContent = titleFor(); $("retry").hidden = true;
  $("mapname").textContent = titleFor();
  setDownload("busy"); timer = setTimeout(build, delay);
}
const setStatus = (t) => ($("status").textContent = t);
function terrainUnavailable() {
  $("previewwrap").setAttribute("aria-busy", "false");
  setStatus("Terrain unavailable"); $("retry").hidden = false;
  capabilityView.unavailable(); vegetationView.unavailable();
}

async function build() {
  job?.abort();
  const ctl = (job = new AbortController());
  // the square as the link records it (5 decimals), so the page builds what the link and the CLI build
  const deadline = setTimeout(() => {
    ctl.abort(new Error("Terrain deadline"));
    if(job===ctl)terrainUnavailable();
  }, 30000);
  const sq = { ...state, lon: +state.lon.toFixed(5), lat: +state.lat.toFixed(5) };
  vegetationView.update(sq);
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
    if (!sq.rivers) {
      finish({ sq, elev, w: null, waterNote: "off", water: "off" });
      void capabilityView.update(sq);
      return;
    }
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
    void capabilityView.update(sq);
  } catch (err) {
    if (job === ctl) terrainUnavailable();
  } finally { clearTimeout(deadline); }
}
$("retry").onclick = () => schedule(0);
$("fit-height").onclick = () => { $("vscale").value = "auto"; $("vscale").dispatchEvent(new Event("change")); };

/**
 * The download button: the ready-to-play map file, or the heightmap if this browser couldn't
 * build one. `water` is the build's water state ("busy" while terrain loads); the map file
 * needs the rivers.
 */
function setDownload(water) {
  const dl = $("dl"), busy = water === "busy" || building;
  for (const id of ["dlpng", "dljson", "dlwater"]) $(id).disabled = water === "busy";
  $("dlpng").textContent = { loading: "Heightmap now (rivers still loading)", failed: "Heightmap (no rivers or lakes)" }[water] ?? "Heightmap (.png)";
  if (building) return;
  dl.dataset.kind = fallback ? "png" : "crp";
  dl.disabled = busy || (!fallback && water !== "basemap" && water !== "off");
  dl.classList.toggle("partial", fallback && (water === "loading" || water === "failed"));
  dl.textContent = fallback
    ? ({ loading: "Download heightmap now (rivers still loading)", failed: "Download heightmap (no rivers or lakes)" }[water] ?? "Download heightmap")
    : ({ loading: "Ready-to-play map: loading rivers…", failed: "Ready-to-play map: rivers didn't load, move the map to retry" }[water] ?? "Download ready-to-play map");
  if (pendingRiskMap && pendingRiskMap.selection === result && pendingRiskMap.key === selectionKey()) dl.textContent = "Review water risk";
  const clipped = water !== "busy" && result?.fit.clipped > 0;
  dl.classList.toggle("clipped", clipped);
  if (clipped && !dl.disabled) dl.textContent = fallback ? "Download clipped heightmap" : "Download clipped map";
  const check = checkedPreset()?.check, note = fallback || check;
  $("crpnote").hidden = !note;
  $("crpnote").textContent = fallback ?? check ?? "";
  $("crpmapname").textContent = `"${titleFor()} - Ready to Play"`;
}
/** The preset whose square this is, if any (some carry a note from their game test). */
const checkedPreset = () => PRESETS.find((p) => Math.abs(p.lon - state.lon) < 1e-6 && Math.abs(p.lat - state.lat) < 1e-6 && state.rotation === 0 && state.scale === 1);

/** Smooth, carve and fit the fetched terrain with the current options; cheap enough to rerun on any change. */
function finish(raw, status = "") {
  resetWaterRisk();
  const { sq, elev, w } = raw;
  const built = dramaOn() ? buildDramaMap(raw, opts()) : buildMap(raw, opts());
  const { carved, fit, sources } = built;
  if (w) raw.waterNote = built.note;
  raw.carved = carved;
  result = { raw, fit, sq, sources, built };
  $("previewwrap").setAttribute("aria-busy", "false"); $("retry").hidden = raw.water !== "failed";
  $("preview3d").hidden = false;
  showStats(fit, elev, raw.waterNote, sq);
  drawPreview(fit, carved.wet);
  showSources(sources, fit);
  setStatus(status);
  setDownload(raw.water);
  $("mapname").textContent = `${fallback ? `${fileName()}.png` : `${baseName()}.crp`} · ${km(extentOf(sq), sq.scale)}`;
}

/** Water source suggestions: dots on the map, pins in the preview, a list in the panel. */
function showSources(sources, fit) {
  map.getSource("sources")?.setData({ type: "FeatureCollection", features: sources.map((s) => ({
    type: "Feature", properties: { kind: s.kind === "lake" ? "lake" : s.kind === "river exit" ? "exit" : "river" }, geometry: { type: "Point", coordinates: [s.lon, s.lat] } })) });
  const list = $("sources");
  if (!sources.length) {
    list.innerHTML = result.raw.water === "basemap" ? "<li>No sizeable river or lake in this square.</li>" : "<li>Waiting for rivers and lakes…</li>";
  } else {
    list.replaceChildren(...sources.map((s) => {
      const li = document.createElement("li");
      li.className = s.kind === "lake" ? "lake" : s.kind === "river exit" ? "exit" : "river";
      const where = describeSpot(s);
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
  const rows = [["Real ground", `${m(fit.realMin)} to ${m(fit.realMax)}`], ["Relief", m(fit.realMax - fit.base)], ["In game", `${m(fit.gameMin)} to ${m(fit.gameMax)}${fit.clipped > 0 ? " · limit 1,024 m" : ""}`], ["Water", result.raw.w ? `${new Set(result.raw.w.rivers.map(r=>r.name||"?")).size} rivers · ${result.built.carved.lakes} lakes` : "None mapped"]];
  const fill=(id,values)=>$(id).replaceChildren(...values.flatMap(([k,v])=>{const dt=document.createElement("dt"),dd=document.createElement("dd");dt.textContent=k;dd.textContent=v;return[dt,dd];}));
  fill("stats",rows);
  $("stats").querySelectorAll("dd")[2].classList.toggle("clipped",fit.clipped>0);
  fill("extra-stats",[["Height scale",`${fit.verticalScale.toFixed(2)}×`],["Map width",km(extentOf(sq),sq.scale)],["Elevation data",`zoom ${elev.zoom} · ${elev.metresPerTilePx.toFixed(1)} m/px · ${elev.tiles} tiles`],...(fit.seaLevel!==null?[["Sea level",m(fit.seaLevel)]]:[])]);
  $("clip-key").hidden=!fit.clipped;
  $("clip-warning").hidden=!(fit.clipped>0);
  $("clip-warning").querySelector("strong").textContent=`${Math.round(fit.clipped*100)}% of this map is cut off at the game's 1,024 m limit`;
  $("height-note").hidden=!(fit.verticalScale<1&&!fit.clipped);
  $("height-note").querySelector("span").textContent=`Heights scaled to ${fit.verticalScale.toFixed(2)}×.`;

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

// ---------------------------------------------------------------- the ready-to-play map file

let worker = null, building = false, fallback = null, nextId = 0;
let pendingRiskMap = null, lastWaterRisk = null;
const selectionKey = () => JSON.stringify({ square: state, options: opts(), name: baseName(), title: titleFor() });
function resetWaterRisk() {
  pendingRiskMap = lastWaterRisk = null;
  $("water-risk").hidden = true;
}
function showWaterRisk(map, selection, key) {
  const decision = waterRiskDecision(map.waterRisk);
  lastWaterRisk = { risk: map.waterRisk, selection, key };
  $("water-risk").hidden = false;
  $("water-risk-title").textContent = decision.title;
  $("water-risk-reasons").replaceChildren(...decision.reasons.map((text) => {
    const li = document.createElement("li"); li.textContent = text; return li;
  }));
  $("water-risk-calibration").textContent = "Based on terrain and mapped water, not a game test.";
  $("water-risk-continue").hidden = decision.action !== "review";
  pendingRiskMap = decision.action === "review" ? { map, selection, key } : null;
  return decision;
}
$("water-risk-continue").onclick = () => {
  const pending = pendingRiskMap;
  if (!pending || pending.selection !== result || pending.key !== selectionKey()) return resetWaterRisk();
  save(new Blob([pending.map.bytes], { type: "application/octet-stream" }), `${baseName()}.crp`);
  pendingRiskMap = null;
  $("water-risk-continue").hidden = true;
  setStatus(`Saved ${baseName()}.crp`);
};
$("water-risk-report").onclick = () => {
  if (!lastWaterRisk || lastWaterRisk.selection !== result || lastWaterRisk.key !== selectionKey()) return;
  save(new Blob([JSON.stringify({ square: result.sq, water_risk: lastWaterRisk.risk }, null, 2) + "\n"], { type: "application/json" }), `${baseName()}-water-risk.json`);
};
/**
 * The ready-to-play .crp for the current square: capture the writer's inputs here (inputs.js),
 * then run the reference writer under Pyodide in mapgen-worker.js. `progress(text)` reports.
 */
async function crpBytes(progress = () => {}) {
  const sq = { ...result.sq, name: titleFor(), slug: baseName() };
  const inputs = dramaOn()
    ? await captureDramaInputs(sq, { status: progress, about: { page: location.origin + location.pathname } })
    : await captureInputs(sq, { status: progress, about: { page: location.origin + location.pathname } });
  const w = (worker ??= new Worker(new URL("mapgen-worker.js", import.meta.url), { type: "module" }));
  const id = ++nextId;
  return new Promise((resolve, reject) => {
    const done = (fn) => (value) => { w.removeEventListener("message", onMessage); w.removeEventListener("error", onError); fn(value); };
    const onMessage = ({ data }) => {
      if (data.id !== id) return;
      if (data.status) progress(data.status);
      else if (data.error) done(reject)(new Error(data.error));
      else if (data.done) done(resolve)(data);
    };
    // the worker itself died (on a phone, most likely out of memory): start a new one next time
    const onError = (e) => { e.preventDefault?.(); w.terminate(); if (worker === w) worker = null; done(reject)(new Error(e.message || "the map builder stopped")); };
    w.addEventListener("message", onMessage);
    w.addEventListener("error", onError);
    w.postMessage({ id, sq, inputs }, [inputs.banks.buffer]);
  });
}
async function savePNG() {
  save(await png16(encode16(result.fit.game), CS1.px, CS1.px), `${fileName()}.png`);
  if (result.raw.water === "loading") setStatus("Saved without rivers; download again once they load");
}
$("dl").onclick = async () => {
  if (!result) return;
  const dl = $("dl");
  if (dl.dataset.kind !== "crp") return savePNG();
  if (pendingRiskMap && pendingRiskMap.selection === result && pendingRiskMap.key === selectionKey()) {
    $("water-risk").scrollIntoView({ block: "nearest" });
    return;
  }
  const selection = result, key = selectionKey();
  building = true;
  dl.disabled = true;
  const start = performance.now();
  let step = "Starting";
  const tick = () => (dl.textContent = `${step}… ${Math.round((performance.now() - start) / 1000)} s`);
  const timer = setInterval(tick, 1000);
  try {
    const map = await crpBytes((s) => { step = s; tick(); });
    lastBuild = { seconds: (performance.now() - start) / 1000, memory: map.memory, summary: map.summary };
    if (result === selection && selectionKey() === key) {
      const decision = showWaterRisk(map, selection, key);
      if (decision.action === "download") {
        save(new Blob([map.bytes], { type: "application/octet-stream" }), `${baseName()}.crp`);
        setStatus(`Saved ${baseName()}.crp: "${map.mapName}" in New Game`);
      } else setStatus(decision.action === "review" ? "Map built; review the water risk before downloading" : "Water check unavailable; choose another square or use the heightmap");
    } else setStatus("Square changed; map not saved");
  } catch (err) {
    lastBuild = { error: err.message };
    fallback = "Map export failed. Download a heightmap.";
  }
  clearInterval(timer);
  building = false;
  setDownload(result.raw.water);
  finishLabel();
};
let lastBuild = null;
$("dlpng").onclick = () => result && savePNG();
$("dlwater").onclick = async () => {
  if (!result) return;
  save(await pngRGB(waterMap(result.built), CS1.px, CS1.px), `${fileName()}-water.png`);
};
$("dljson").onclick = () => {
  if (!result) return;
  save(new Blob([JSON.stringify(details(), null, 2)], { type: "application/json" }), `${fileName()}.json`);
};

const opts = () => ({ vscale: state.vscale, ...Object.fromEntries(Object.keys(DEFAULTS).map((k) => [k, state[k]])) });
function details() {
  const { sq, raw, built } = result;
  const args = { sq, elev: raw.elev, w: raw.w, map: built, opts: opts(), file: `${fileName()}.png`, link: link(), note: raw.waterNote };
  return dramaOn() ? dramaDetails(args) : mapDetails(args);
}

// ---------------------------------------------------------------- hand it to an AI agent

// the command-line tool packed from this same deploy (build.mjs fills it in), so page and tool agree
const CLI_TGZ = "__CLI_TGZ__".startsWith("__") ? "https://codeload.github.com/frontierkodiak/region-to-skylines/tar.gz/main" : "__CLI_TGZ__";

/** A short prompt an agent can act on: this square's link, the instructions page and the one command. */
function agentPrompt() {
  return [
    "Please put this real-world map into Cities: Skylines (the first game) on this computer:",
    link(),
    "",
    `Instructions for AI agents: ${SITE}/agents.md`,
    `In short, run: npx -y ${CLI_TGZ} "${link()}" --install`,
    "If it stops with exit 5, show me the water-risk reasons; do not add --allow-water-risk without my agreement.",
    "Then tell me what it printed and what to do in the game.",
  ].join("\n");
}
$("agentcopy").onclick = async () => {
  const text = agentPrompt(), b = $("agentcopy");
  try { await navigator.clipboard.writeText(text); b.textContent = "Copied: paste it to your agent"; }
  catch { $("agentprompt").hidden = false; $("agentprompt").value = text; $("agentprompt").select(); b.textContent = "Copy the text below"; }
  setTimeout(() => (b.textContent = "Copy instructions for your AI agent"), 2500);
};

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
let mesh = null, water = null, ceiling = null;
let footprint = null;
const footprintLines = new THREE.Group(); scene.add(footprintLines);

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
      const i = r * n + c, src = r * STEP * CS1.px + c * STEP, rawHeight = fit.game[src], g = Math.min(1024, Math.max(0,rawHeight));
      pos.setY(i, (g - fit.gameMin) * k * EXAG * (17280 / extentOf(result.sq)));
      let rgb = tint((g - lo) / span);
      if (wet && anyWet(wet, r * STEP, c * STEP, STEP)) rgb = [0.24, 0.47, 0.78];
      if (fit.sea?.[src]) rgb = [0.18, 0.36, 0.6];
      if(rawHeight>1024||rawHeight<0)rgb=[1,0,0];
      col.set(rgb, 3 * i);
    }
  }
  geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
  geo.computeVertexNormals();
  if (mesh) { scene.remove(mesh); mesh.traverse(o=>o.geometry?.dispose()); mesh.material.dispose(); }
  mesh = new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ vertexColors: true, flatShading: true }));
  mesh.position.y = -0.25;
  mesh.add(skirt(pos, n));
  mesh.add(tileGrid(pos, n));
  scene.add(mesh);
  if (water) { scene.remove(water); water.geometry.dispose(); water.material.dispose(); water = null; }
  if (fit.seaLevel !== null) {
    water = new THREE.Mesh(new THREE.PlaneGeometry(size, size).rotateX(-Math.PI / 2),
      new THREE.MeshLambertMaterial({ color: 0x3f7fc0, transparent: true, opacity: 0.75 }));
    water.position.y = -0.25 + (fit.seaLevel + 1 - fit.gameMin) * k * EXAG * (17280 / extentOf(result.sq));
    scene.add(water);
  }
  placeNorth(result.sq.rotation);
  previewY = (g) => -0.25 + (g - fit.gameMin) * k * EXAG * (17280 / extentOf(result.sq));
  drawCeiling(fit, pos, n, STEP);
  $("legend").textContent = `Height ×${EXAG}`;
  resize();
  const box=new THREE.Box3().setFromObject(mesh),center=box.getCenter(new THREE.Vector3());
  controls.target.copy(center);camera.position.copy(center).add(new THREE.Vector3(10,10,10));camera.lookAt(center);camera.updateMatrixWorld();camera.zoom=1;camera.updateProjectionMatrix();
  const points=[];for(const x of[box.min.x,box.max.x])for(const y of[box.min.y,box.max.y])for(const z of[box.min.z,box.max.z])points.push(new THREE.Vector3(x,y,z).project(camera));
  const width=Math.max(...points.map(p=>p.x))-Math.min(...points.map(p=>p.x)),height=Math.max(...points.map(p=>p.y))-Math.min(...points.map(p=>p.y));
  camera.zoom=Math.min(1.65/width,1.65/height);camera.updateProjectionMatrix();drawFootprint();
  resize();
}

function drawCeiling(fit, pos, n, step) {
  if (ceiling) {
    scene.remove(ceiling);
    ceiling.traverse(o => { o.geometry?.dispose(); o.material?.dispose(); });
    ceiling = null;
  }
  if (!fit.clipped) return;
  ceiling = new THREE.Group();
  const y = previewY(CS1.maxHeight), cuts = [];
  // Intersect each preview triangle with the height limit: only its removed portion is red.
  const vertex = i => [pos.getX(i), pos.getZ(i), fit.game[Math.floor(i/n)*step*CS1.px+(i%n)*step]];
  for (let r=0;r<n-1;r++) for(let c=0;c<n-1;c++) {
    const a=r*n+c,b=a+1,d=a+n,e=d+1;
    for (const ids of [[a,d,b],[b,d,e]]) {
      const input=ids.map(vertex), polygon=[];
      for (let i=0;i<3;i++) {
        const p=input[i],q=input[(i+1)%3],inside=p[2]>CS1.maxHeight,next=q[2]>CS1.maxHeight;
        if(inside) polygon.push(p);
        if(inside!==next) {
          const t=(CS1.maxHeight-p[2])/(q[2]-p[2]);
          polygon.push([p[0]+(q[0]-p[0])*t,p[1]+(q[1]-p[1])*t,CS1.maxHeight]);
        }
      }
      for(let i=1;i<polygon.length-1;i++) for(const p of [polygon[0],polygon[i],polygon[i+1]]) cuts.push(p[0],y+.001,p[1]);
    }
  }
  const plane=new THREE.Mesh(new THREE.PlaneGeometry(2,2).rotateX(-Math.PI/2),
    new THREE.MeshBasicMaterial({color:0xe02020,transparent:true,opacity:.18,side:THREE.DoubleSide,depthWrite:false}));
  plane.position.y=y;plane.renderOrder=8;ceiling.add(plane);
  const border=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints([[-1,y,-1],[1,y,-1],[1,y,1],[-1,y,1]].map(p=>new THREE.Vector3(...p))),new THREE.LineBasicMaterial({color:0xc51d1d}));
  border.renderOrder=8;ceiling.add(border);
  const geometry=new THREE.BufferGeometry();geometry.setAttribute("position",new THREE.Float32BufferAttribute(cuts,3));
  const caps=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial({color:0xe02020,side:THREE.DoubleSide}));
  caps.renderOrder=9;ceiling.add(caps);scene.add(ceiling);
}

function showFootprint(value, square) {
  footprint=value?.footprint==='candidate'&&result&&(!square||square.lon===result.sq.lon&&square.lat===result.sq.lat)?value.center_xz:null;
  $('footprint-key').hidden=!footprint;
  const coords=footprint?[[-192,-192],[192,-192],[192,192],[-192,192],[-192,-192]].map(([x,z])=>squareToLonLat(result.sq,(footprint[0]+x)*result.sq.scale,(footprint[1]+z)*result.sq.scale)):[];
  map.getSource('footprint')?.setData({type:'FeatureCollection',features:coords.length?[{type:'Feature',properties:{},geometry:{type:'Polygon',coordinates:[coords]}}]:[]});
  drawFootprint();
}
function drawFootprint() {
  footprintLines.children.forEach(o=>{o.geometry.dispose();o.material.dispose();});footprintLines.clear();
  if(!footprint||!result)return render();
  const points=[],corners=[[-192,-192],[192,-192],[192,192],[-192,192],[-192,-192]];
  for(let k=0;k<4;k++)for(let t=0;t<1;t+=1/24){
    const x=footprint[0]+corners[k][0]*(1-t)+corners[k+1][0]*t,z=footprint[1]+corners[k][1]*(1-t)+corners[k+1][1]*t;
    const row=Math.max(0,Math.min(1080,Math.round((8640-z)/16))),col=Math.max(0,Math.min(1080,Math.round((x+8640)/16)));
    points.push(new THREE.Vector3(x/8640,previewY(Math.min(1024,Math.max(0,result.fit.game[row*1081+col])))+.012,-z/8640));
  }
  const path=new THREE.CatmullRomCurve3(points,true,'centripetal');
  for(const[radius,color,order]of[[.004,0x17462d,20],[.002,0xf7fff8,21]]){
    const line=new THREE.Mesh(new THREE.TubeGeometry(path,points.length*2,radius,4,true),new THREE.MeshBasicMaterial({color,depthTest:false}));
    line.renderOrder=order;footprintLines.add(line);
  }
  render();
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
  if (result) $("mapname").textContent = $("mapname").textContent.replace(/^[^ ]+\.(png|crp)/, fallback ? `${fileName()}.png` : `${baseName()}.crp`);
}

// for automated checks
window.__regionmap = { state, get result() { return result; }, details: () => details(), agentPrompt: () => agentPrompt(),
  png: () => png16(encode16(result.fit.game), CS1.px, CS1.px), crp: (progress) => crpBytes(progress), get lastBuild() { return lastBuild; } };

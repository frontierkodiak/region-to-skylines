#!/usr/bin/env node
// Region to Cities: Skylines from the command line: the page's own code run in Node, so a square
// gives the same file here as in the browser. The ready-to-play map file comes from the reference
// writer (tools/map-factory, Python) under Pyodide, as on the page; inputs.js captures its inputs
// and mapgen.js runs it. Optionally copies the file into the game.

import { parseArgs } from "node:util";
import { mkdir, writeFile, readFile, access } from "node:fs/promises";
import { homedir, platform } from "node:os";
import { join, resolve } from "node:path";
import { CS1, SITE, DEFAULTS, PRESETS, sampleElevation, seaMask, fetchBasemapWater, buildMap, mapDetails, parseHash, squareHash, extentOf, encode16, png16, pngRGB, waterMap, slugify, coordName, squareProblem, describeSpot } from "./terrain.js";

const presetNames = PRESETS.map((p) => p.name).join(", ");

const USAGE = `Region to Cities: Skylines: real terrain to a Cities: Skylines 1 map.

Usage: npx -y ${SITE}/cli.tgz <where> [options]

<where> is one of
  a link from ${SITE}  (keeps its rotation, scale and options)
  a preset             ${presetNames} (the page's buttons, with their square)
  "lat,lon"            decimal degrees, e.g. "35.58,-82.555"
  a place name         e.g. "Innsbruck", looked up once on OpenStreetMap's Nominatim

It makes a ready-to-play map file, <name>.crp: rivers with water in them, a highway and a
railway to the outside, real forests and farmland, so New Game lists it and there is no Map
Editor step. It runs the map writer in Python (Pyodide): the first run downloads about 30 MB,
and a map takes about a minute.

Options
  --heightmap        make the heightmap for the game's Map Editor instead (<name>.png)
  --title <name>     the map's name in New Game, before " - Ready to Play" (default: the place)
  --rotate <deg>     turn the square clockwise, -180 to 180 (default 0, or the preset's)
  --scale <x>        real ground per map: 0.5, 0.75, 1 (true size, 17.28 km), 1.5 or 2
  --height <h>       (heightmap) auto (default: 1:1, squeezed if too tall), slopes, or a factor
  --no-rivers        (heightmap) don't cut rivers and lakes
  --name <name>      file name without extension (default: from the place)
  --out <dir>        where to write the map file and <name>.json, plus <name>-water.png for a
                     heightmap (default: the current directory; with --install, a cache folder and
                     only the map file in the game)
  --install          put the map into the game: <name>.crp into its Maps folder, a heightmap into
                     Addons/MapEditor/Heightmaps
  --game-dir <dir>   the game's data folder, if not the usual one for this OS
  --force            replace files of the same name instead of stopping
  --json             print a JSON summary on stdout (progress still goes to stderr)
  -h, --help         this text

Exit codes: 0 done, 1 bad arguments, 2 download or build failed, 3 game folder not found,
4 a file of that name exists (use --force or --name).`;

const fail = (code, msg) => { process.stderr.write(`region-to-skylines: ${msg}\n`); process.exit(code); };
const log = (msg) => process.stderr.write(msg + "\n");
const exists = (p) => access(p).then(() => true, () => false);

if (typeof AbortSignal.any !== "function" || typeof DecompressionStream !== "function") fail(1, `needs Node 20.3 or newer (this is ${process.version})`);

// "-22.94,-43.205" and "--rotate -30" start with a dash: keep them from reading as options
const argv = [], coords = [], raw = process.argv.slice(2);
for (let k = 0; k < raw.length; k++) {
  if (/^-\d[\d.]*\s*,/.test(raw[k])) coords.push(raw[k]);
  else if (/^--(rotate|scale|height)$/.test(raw[k]) && /^-\d/.test(raw[k + 1] ?? "")) argv.push(`${raw[k]}=${raw[++k]}`);
  else argv.push(raw[k]);
}
let args;
try {
  args = parseArgs({
    args: coords.length ? [...argv, ...(argv.includes("--") ? [] : ["--"]), ...coords] : argv,
    allowPositionals: true,
    options: {
      heightmap: { type: "boolean" }, title: { type: "string" }, rotate: { type: "string" }, scale: { type: "string" }, height: { type: "string" },
      "no-rivers": { type: "boolean" }, name: { type: "string" }, out: { type: "string" },
      install: { type: "boolean" }, "game-dir": { type: "string" }, force: { type: "boolean" },
      json: { type: "boolean" }, help: { type: "boolean", short: "h" },
    },
  });
} catch (err) { fail(1, `${err.message}\n\n${USAGE}`); }
const { values: v, positionals } = args;
if (v.help) { console.log(USAGE); process.exit(0); }
if (!positionals.length) fail(1, `say where: a link, "lat,lon" or a place name.\n\n${USAGE}`);
const where = positionals.join(" ").trim();

/** The game's data folder per OS: where the game itself keeps Saves, Maps and Addons. */
function gameDir() {
  if (v["game-dir"]) return resolve(v["game-dir"]);
  const p = platform();
  if (p === "darwin") return join(homedir(), "Library", "Application Support", "Colossal Order", "Cities_Skylines");
  if (p === "win32") return join(process.env.LOCALAPPDATA || join(homedir(), "AppData", "Local"), "Colossal Order", "Cities_Skylines");
  return join(process.env.XDG_DATA_HOME || join(homedir(), ".local", "share"), "Colossal Order", "Cities_Skylines");
}

// ---------------------------------------------------------------- where

const sq = { lon: 0, lat: 0, rotation: 0, scale: 1, vscale: "auto", rivers: true, ...DEFAULTS };
let name, title;
const m = where.match(/^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/);
const preset = PRESETS.find((p) => [p.name, p.slug].some((n) => n.toLowerCase() === where.toLowerCase()));
if (/^https?:\/\//.test(where)) {
  const hash = where.includes("#") ? where.slice(where.indexOf("#")) : "";
  const o = parseHash(hash);
  if (o.lon === undefined) fail(1, `that link has no square in it (expected ${SITE}/#c=lon,lat&...)`);
  ({ name } = o); delete o.name;
  Object.assign(sq, o);
  title = PRESETS.find((p) => p.lon === sq.lon && p.lat === sq.lat)?.name ?? name;
  const bad = squareProblem(sq);
  if (bad) fail(1, `that link's square is not one the page makes: ${bad}`);
} else if (preset) {
  Object.assign(sq, { lon: preset.lon, lat: preset.lat });
  name = preset.slug;
  title = preset.name;
} else if (m) {
  const lat = Number(m[1]), lon = Number(m[2]);
  if (Math.abs(lat) > 85 || Math.abs(lon) > 180) fail(1, `"${where}" is not lat,lon (latitude first, within ±85)`);
  Object.assign(sq, { lat, lon });
  name = coordName(lat, lon);
} else {
  // Nominatim usage policy: one request, an identifying User-Agent, results credited to OSM.
  log(`Looking up "${where}" on OpenStreetMap Nominatim…`);
  let hit;
  try {
    const r = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q=${encodeURIComponent(where)}`, {
      headers: { "User-Agent": "region-to-skylines-cli/0.5 (+https://github.com/frontierkodiak/region-to-skylines)" },
      signal: AbortSignal.timeout(20000),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    [hit] = await r.json();
  } catch (err) { fail(2, `place search failed (${err.message}); pass "lat,lon" instead`); }
  if (!hit) fail(1, `no place called "${where}"; pass "lat,lon" instead`);
  Object.assign(sq, { lon: Number(hit.lon), lat: Number(hit.lat) });
  log(`  ${hit.display_name} (${Number(hit.lat).toFixed(5)}, ${Number(hit.lon).toFixed(5)})`);
  name = slugify(where) || coordName(sq.lat, sq.lon);
  title = where;
}
if (v.rotate !== undefined) sq.rotation = v.rotate.trim() === "" ? NaN : Number(v.rotate);
if (v.scale !== undefined) sq.scale = Number(v.scale);
if (v.height !== undefined) sq.vscale = ["auto", "slopes"].includes(v.height) ? v.height : v.height.trim() === "" ? NaN : Number(v.height);
{ const bad = squareProblem(sq); if (bad) fail(1, bad.replace(/^(rotation|scale|height)/, "--$1").replace("--rotation", "--rotate")); }
if (v["no-rivers"]) sq.rivers = false;
if (v.name) name = v.name;
name = String(name || "map").trim().replace(/[^\w.-]+/g, "-") || "map";
title = String(v.title ?? title ?? name).trim() || name;
const link = SITE + "/" + squareHash({ ...sq, name });

// ---------------------------------------------------------------- build

/** Where --install keeps the JSON and water map when no --out is given: this OS's cache folder, not the person's files. */
function cacheDir() {
  const p = platform();
  if (p === "darwin") return join(homedir(), "Library", "Caches", "region-to-skylines");
  if (p === "win32") return join(process.env.LOCALAPPDATA || join(homedir(), "AppData", "Local"), "region-to-skylines");
  return join(process.env.XDG_CACHE_HOME || join(homedir(), ".cache"), "region-to-skylines");
}
const crp = !v.heightmap;
const ext = crp ? "crp" : "png";
const install = v.install ? join(gameDir(), ...(crp ? ["Maps"] : ["Addons", "MapEditor", "Heightmaps"])) : null;
// with --install and no --out, the map goes only into the game; the extras go to the cache
const outDir = resolve(v.out || (install ? cacheDir() : "."));
const file = install && !v.out ? null : join(outDir, `${name}.${ext}`);
const jsonPath = join(outDir, `${name}.json`), waterPath = crp ? null : join(outDir, `${name}-water.png`);
const installed = install ? join(install, `${name}.${ext}`) : null;
// check everything that could stop us before downloading anything (the cache is ours to overwrite)
if (!v.force) for (const p of [file, ...(v.out || !install ? [jsonPath, waterPath] : []), installed].filter(Boolean))
  if (await exists(p)) fail(4, `${p} already exists; pass --force to replace it or --name to pick another name`);
if (install && !(await exists(gameDir())))
  fail(3, `Cities: Skylines data folder not found at ${gameDir()}. Start the game once on this computer, or pass --game-dir <its data folder>.`);

const opts = { vscale: sq.vscale, ...Object.fromEntries(Object.keys(DEFAULTS).map((k) => [k, sq[k]])) };
const check = PRESETS.find((p) => p.lon === sq.lon && p.lat === sq.lat && sq.rotation === 0 && sq.scale === 1)?.check ?? null;
let bytes, details, map = null, mapName = null, report = null;
log(`Building ${name}: ${(extentOf(sq) / 1000).toFixed(2)} km square at ${sq.lat.toFixed(5)}, ${sq.lon.toFixed(5)}, rotated ${sq.rotation}°`);
if (crp) {
  // ready-to-play: capture the writer's inputs as the page does, then run the writer
  const { captureInputs } = await import("./inputs.js");
  const { startFactory, landCover, deposits, buildMap: writeMap, WORLDCOVER_S3, worldCoverFile } = await import("./mapgen.js");
  let last = "";
  const status = (s) => { if (s !== last) log(`  ${(last = s)}…`); };
  try {
    const t = performance.now();
    const inputs = await captureInputs({ ...sq, name: title, slug: name }, { status, about: { cli: "region-to-skylines", link } });
    const { loadPyodide } = await import("pyodide");
    const { fromUrl } = await import("geotiff");
    status("Loading Python (the first run downloads about 30 MB)");
    const factory = await startFactory({ loadPyodide, read: async (f) => new Uint8Array(await readFile(new URL(`./tools/map-factory/${f}`, import.meta.url))) });
    const cover = await landCover(factory, sq, { fromUrl, tileUrl: (tile) => WORLDCOVER_S3 + worldCoverFile(tile), status });
    const found = await deposits(factory, sq, { status });
    const built = await writeMap(factory, { ...inputs, landcover: cover.path, evidence: found?.path ?? null }, { status });
    bytes = Buffer.from(built.bytes);
    mapName = built.mapName;
    const prep = built.receipt.preparation ?? {};
    report = { seconds: Math.round((performance.now() - t) / 1000), land_cover_tiles: cover.tiles, deposits: found?.count ?? null,
      starter_reservoir: !!prep.starter_reservoir, sea_level_game_m: inputs.seaLevel === null ? null : Math.round(inputs.seaLevel) };
    details = { game: "Cities: Skylines 1", map_file: `${name}.crp`, map_name: mapName, link,
      center: { lon: sq.lon, lat: sq.lat }, rotation_deg: sq.rotation, scale: sq.scale, game_test: check, build: report,
      writer: "tools/map-factory (PL-857 reference) under Pyodide",
      data: ["Elevation: AWS Terrain Tiles (Mapzen)", "Rivers, lakes, coast, roads: © OpenStreetMap contributors (ODbL), via OpenFreeMap",
        "Land cover: ESA WorldCover 2021 (CC BY 4.0)", "Ore and oil: USGS MRDS (public domain)"] };
  } catch (err) { fail(2, `building the map file failed: ${err.message}. Try again in a minute, or pass --heightmap.`); }
} else {
  let elev, w = null;
  try {
    elev = await sampleElevation(sq, { onProgress: (d, n) => d === n && log(`  elevation: ${n} tiles`) });
    elev.sea = seaMask(elev.heights);
    if (sq.rivers) {
      w = await fetchBasemapWater(sq);
      log(`  rivers and lakes: ${w.tiles} OpenStreetMap tiles at zoom ${w.zoom}`);
    }
  } catch (err) { fail(2, `download failed: ${err.message}. Try again in a minute.`); }
  map = buildMap({ sq, elev, w }, opts);
  details = mapDetails({ sq, elev, w, map, opts, file: `${name}.png`, link });
  bytes = Buffer.from(await (await png16(encode16(map.fit.game), CS1.px, CS1.px)).arrayBuffer());
}
await mkdir(outDir, { recursive: true });
if (file) await writeFile(file, bytes);
await writeFile(jsonPath, JSON.stringify(details, null, 2) + "\n");
if (waterPath) await writeFile(waterPath, Buffer.from(await (await pngRGB(waterMap(map), CS1.px, CS1.px)).arrayBuffer()));
if (install) {
  await mkdir(install, { recursive: true });
  await writeFile(installed, bytes);
}

// ---------------------------------------------------------------- report

const r = Math.round;
let steps;
if (crp) {
  steps = [
    `Start Cities: Skylines (the first game), choose New Game and pick "${mapName}".`,
    "That's all: the rivers already have water in them, a highway and a railway connect the starting tile to the outside, and there are forests, farmland, ore and oil. No Map Editor step.",
    "It was tested with no mods; the 81 Tiles 2 mod hasn't been tried with it.",
  ];
} else {
  const { fit, sources } = map;
  const seaStep = fit.seaLevel !== null
    ? `Set Sea level to ${r(fit.seaLevel)} m (this square has open sea).`
    : `Inland map: drag Sea level below ${r(fit.gameMin)} m, the lowest riverbed, so the valleys stay dry.`;
  const placed = sources.filter((s) => s.kind !== "river exit");
  steps = [
    `Start Cities: Skylines (the first game). Main menu > Tools > Map Editor, start a new map, then press Import heightmap and pick ${name}.`,
    seaStep,
    placed.length
      ? `Water: place a water source at each numbered pin on the water map (${waterPath}) and raise it until the bed fills; grey pins mark where a river leaves, put nothing there. The same spots, with this square's 3D preview, are on the web page: open ${link} and expand "Advanced: heightmap for the Map Editor".`
      : "Water: no sizeable river or lake here; place any water the start tile needs by hand.",
    "The start tile needs water and a highway in and out (Map Settings > Start Area moves it). Then save the map; New Game lists it.",
    "Using the 81 Tiles 2 mod? Disable it before opening the Map Editor.",
  ];
}
const summary = {
  name, link, kind: crp ? "ready-to-play map" : "heightmap",
  ...(crp ? { crp: file, map_name: mapName, game_test: check, build: report } : { png: file, water_map: waterPath }),
  json: jsonPath, installed, game_dir: v.install ? gameDir() : null,
  ...(crp ? {} : { heights_game_m: [r(map.fit.gameMin), r(map.fit.gameMax)], sea_level_game_m: map.fit.seaLevel === null ? null : r(map.fit.seaLevel),
    water_sources: details.water_sources }),
  next_steps: steps,
};
if (v.json) console.log(JSON.stringify(summary, null, 2));
else {
  const what = crp ? `ready-to-play map "${mapName}"` : `heightmap, ${CS1.px} x ${CS1.px}, 16-bit`;
  if (installed) console.log(`Installed into the game: ${installed} (${what})`);
  if (file) console.log(`Saved ${file} (${what})`);
  if (waterPath) console.log(`Water map (where the sources go): ${waterPath}`);
  console.log(`Details: ${jsonPath}`);
  if (!installed) console.log(`Not installed (add --install to put it into the game's ${crp ? "Maps" : "heightmap"} folder).`);
  if (check) console.log(`Note: ${check}`);
  console.log(`\nNext, in the game:`);
  steps.forEach((s, k) => console.log(`  ${k + 1}. ${s}`));
  if (!crp && map.sources.some((s) => s.kind !== "river exit")) {
    console.log(`\nWater sources (pin numbers as on the water map; "left" and "top" are the heightmap's own sides):`);
    map.sources.forEach((s, k) => console.log(`  ${k + 1}. ${s.name}, ${{ "river entry": "enters", "river start": "starts", "river exit": "leaves (nothing here)", lake: `lake, fill to ${r(s.surface_game_m)} m` }[s.kind]}: ${describeSpot(s)}`));
  }
  console.log(`\nSame square on the web: ${link}`);
  console.log(crp
    ? "Data: elevation from AWS Terrain Tiles (Mapzen); rivers, coast and roads © OpenStreetMap contributors (ODbL), via OpenFreeMap; land cover ESA WorldCover 2021 (CC BY 4.0); ore and oil USGS MRDS."
    : "Data: elevation from AWS Terrain Tiles (Mapzen); rivers and lakes © OpenStreetMap contributors (ODbL), via OpenFreeMap.");
}
// Pyodide can leave handles open; the work is done
process.exit(0);

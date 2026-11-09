#!/usr/bin/env node
// Region to Cities: Skylines from the command line: the page's own terrain.js, run in Node, so a
// square gives the same heightmap here as in the browser. Optionally copies it into the game.

import { parseArgs } from "node:util";
import { mkdir, writeFile, copyFile, access } from "node:fs/promises";
import { homedir, platform } from "node:os";
import { join, resolve } from "node:path";
import { CS1, SITE, DEFAULTS, sampleElevation, seaMask, fetchBasemapWater, buildMap, mapDetails, parseHash, squareHash, extentOf, encode16, png16 } from "./terrain.js";

const USAGE = `Region to Cities: Skylines: real terrain to a Cities: Skylines 1 heightmap.

Usage: npx -y github:frontierkodiak/region-to-skylines <where> [options]

<where> is one of
  a link from ${SITE}  (keeps its rotation, scale and options)
  "lat,lon"            decimal degrees, e.g. "35.58,-82.555"
  a place name         e.g. "Innsbruck", looked up once on OpenStreetMap's Nominatim

Options
  --rotate <deg>     turn the square clockwise, -180 to 180 (default 0)
  --scale <x>        real ground per map: 0.5, 0.75, 1 (true size, 17.28 km), 1.5 or 2
  --height <h>       auto (default: 1:1, squeezed if too tall), slopes, or a factor like 0.75
  --no-rivers        don't cut rivers and lakes
  --name <name>      file name without extension (default: from the place)
  --out <dir>        where to write <name>.png and <name>.json (default: current directory)
  --install          also copy the PNG into the game's heightmap folder
  --game-dir <dir>   the game's data folder, if not the usual one for this OS
  --force            replace files of the same name instead of stopping
  --json             print a JSON summary on stdout (progress still goes to stderr)
  -h, --help         this text

Exit codes: 0 done, 1 bad arguments, 2 download or build failed, 3 game folder not found,
4 a file of that name exists (use --force or --name).`;

const fail = (code, msg) => { process.stderr.write(`region-to-skylines: ${msg}\n`); process.exit(code); };
const log = (msg) => process.stderr.write(msg + "\n");
const exists = (p) => access(p).then(() => true, () => false);
const slug = (s) => s.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || "map";

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
      rotate: { type: "string" }, scale: { type: "string" }, height: { type: "string" },
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
let name;
const m = where.match(/^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/);
if (/^https?:\/\//.test(where)) {
  const hash = where.includes("#") ? where.slice(where.indexOf("#")) : "";
  const o = parseHash(hash);
  if (o.lon === undefined) fail(1, `that link has no square in it (expected ${SITE}/#c=lon,lat&...)`);
  ({ name } = o); delete o.name;
  Object.assign(sq, o);
} else if (m) {
  const lat = Number(m[1]), lon = Number(m[2]);
  if (Math.abs(lat) > 85 || Math.abs(lon) > 180) fail(1, `"${where}" is not lat,lon (latitude first, within ±85)`);
  Object.assign(sq, { lat, lon });
  name = `map-${lat.toFixed(3)}-${lon.toFixed(3)}`.replaceAll(".", "_");
} else {
  // Nominatim usage policy: one request, an identifying User-Agent, results credited to OSM.
  log(`Looking up "${where}" on OpenStreetMap Nominatim…`);
  let hit;
  try {
    const r = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q=${encodeURIComponent(where)}`, {
      headers: { "User-Agent": "region-to-skylines-cli/0.2 (+https://github.com/frontierkodiak/region-to-skylines)" },
      signal: AbortSignal.timeout(20000),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    [hit] = await r.json();
  } catch (err) { fail(2, `place search failed (${err.message}); pass "lat,lon" instead`); }
  if (!hit) fail(1, `no place called "${where}"; pass "lat,lon" instead`);
  Object.assign(sq, { lon: Number(hit.lon), lat: Number(hit.lat) });
  log(`  ${hit.display_name} (${Number(hit.lat).toFixed(5)}, ${Number(hit.lon).toFixed(5)})`);
  name = slug(where);
}
if (v.rotate !== undefined) {
  sq.rotation = Number(v.rotate);
  if (!isFinite(sq.rotation) || Math.abs(sq.rotation) > 180) fail(1, "--rotate takes degrees from -180 to 180");
}
if (v.scale !== undefined) {
  sq.scale = Number(v.scale);
  if (![0.5, 0.75, 1, 1.5, 2].includes(sq.scale)) fail(1, "--scale takes 0.5, 0.75, 1, 1.5 or 2");
}
if (v.height !== undefined) {
  sq.vscale = ["auto", "slopes"].includes(v.height) ? v.height : Number(v.height);
  if (typeof sq.vscale === "number" && !(sq.vscale > 0 && sq.vscale <= 4)) fail(1, "--height takes auto, slopes or a factor like 0.75");
}
if (v["no-rivers"]) sq.rivers = false;
if (v.name) name = v.name;
name = String(name || "map").trim().replace(/[^\w.-]+/g, "-") || "map";
const link = SITE + "/" + squareHash({ ...sq, name });

// ---------------------------------------------------------------- build

const outDir = resolve(v.out || ".");
const pngPath = join(outDir, `${name}.png`), jsonPath = join(outDir, `${name}.json`);
const install = v.install ? join(gameDir(), "Addons", "MapEditor", "Heightmaps") : null;
// check everything that could stop us before downloading anything
if (!v.force) for (const p of [pngPath, jsonPath, install && join(install, `${name}.png`)].filter(Boolean))
  if (await exists(p)) fail(4, `${p} already exists; pass --force to replace it or --name to pick another name`);
if (install && !(await exists(gameDir())))
  fail(3, `Cities: Skylines data folder not found at ${gameDir()}. Start the game once on this computer, or pass --game-dir <its data folder>.`);

let elev, w = null;
try {
  log(`Building ${name}: ${(extentOf(sq) / 1000).toFixed(2)} km square at ${sq.lat.toFixed(5)}, ${sq.lon.toFixed(5)}, rotated ${sq.rotation}°`);
  elev = await sampleElevation(sq, { onProgress: (d, n) => d === n && log(`  elevation: ${n} tiles`) });
  elev.sea = seaMask(elev.heights);
  if (sq.rivers) {
    w = await fetchBasemapWater(sq);
    log(`  rivers and lakes: ${w.tiles} OpenStreetMap tiles at zoom ${w.zoom}`);
  }
} catch (err) { fail(2, `download failed: ${err.message}. Try again in a minute.`); }

const opts = { vscale: sq.vscale, ...Object.fromEntries(Object.keys(DEFAULTS).map((k) => [k, sq[k]])) };
const map = buildMap({ sq, elev, w }, opts);
const png = Buffer.from(await (await png16(encode16(map.fit.game), CS1.px, CS1.px)).arrayBuffer());
const details = mapDetails({ sq, elev, w, map, opts, file: `${name}.png`, link });

await mkdir(outDir, { recursive: true });
await writeFile(pngPath, png);
await writeFile(jsonPath, JSON.stringify(details, null, 2) + "\n");
let installed = null;
if (install) {
  await mkdir(install, { recursive: true });
  installed = join(install, `${name}.png`);
  await copyFile(pngPath, installed);
}

// ---------------------------------------------------------------- report

const { fit, sources } = map, r = Math.round;
const seaStep = fit.seaLevel !== null
  ? `Set Sea level to ${r(fit.seaLevel)} m (this square has open sea).`
  : `Inland map: drag Sea level below ${r(fit.gameMin)} m, the lowest riverbed, so the valleys stay dry.`;
const placed = sources.filter((s) => s.kind !== "river exit");
const steps = [
  `Start Cities: Skylines (the first game). Main menu > Tools > Map Editor, start a new map, then press Import heightmap and pick ${name}.`,
  seaStep,
  placed.length
    ? `Water: place a water source at each spot below and raise it until the bed fills; nothing where a river leaves. The same list is in ${name}.json under water_sources.`
    : "Water: no sizeable river or lake here; place any water the start tile needs by hand.",
  "The start tile needs water and a highway in and out (Map Settings > Start Area moves it). Then save the map; New Game lists it.",
  "Using the 81 Tiles 2 mod? Disable it before opening the Map Editor.",
];
const summary = {
  name, link, png: pngPath, json: jsonPath, installed,
  game_dir: install ? gameDir() : null,
  heights_game_m: [r(fit.gameMin), r(fit.gameMax)], sea_level_game_m: fit.seaLevel === null ? null : r(fit.seaLevel),
  water_sources: details.water_sources, next_steps: steps,
};
if (v.json) console.log(JSON.stringify(summary, null, 2));
else {
  console.log(`Saved ${pngPath} (${CS1.px} x ${CS1.px}, 16-bit) and ${name}.json`);
  console.log(installed ? `Installed into the game: ${installed}` : `Not installed (add --install to copy it into the game's heightmap folder).`);
  console.log(`\nNext, in the game:`);
  steps.forEach((s, k) => console.log(`  ${k + 1}. ${s}`));
  if (placed.length) {
    console.log(`\nWater sources (Map Editor coordinates: metres from the centre, x east, z north):`);
    for (const s of sources) console.log(`  - ${s.name}, ${{ "river entry": "enters", "river start": "starts", "river exit": "leaves (nothing here)", lake: `lake, fill to ${r(s.surface_game_m)} m` }[s.kind]}: x ${s.x_m}, z ${s.z_m}`);
  }
  console.log(`\nSame square on the web: ${link}`);
  console.log(`Data: elevation from AWS Terrain Tiles (Mapzen); rivers and lakes © OpenStreetMap contributors (ODbL), via OpenFreeMap.`);
}

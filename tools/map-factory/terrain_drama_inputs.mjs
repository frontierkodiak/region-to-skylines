// Write a square's writer inputs under the per-square vertical transform (PL-1329), so the
// reference writer can be run on them exactly as it runs on the shipping capture.
//
//   node tools/map-factory/terrain_drama_inputs.mjs --fixture charleston --out DIR
//   node tools/map-factory/terrain_drama_inputs.mjs --name Boston --center 42.355,-71.06 --out DIR
//   ... --policy legacy   (the shipping fit, for the before side of a comparison)
//
// Writes input.png, geometry.json and banks.f32 in OUT, and OUT/inputs.json with the transform,
// the fitted gains and the water sources. Nothing here touches the shipping writer's own files.

import { mkdir, writeFile } from "node:fs/promises";
import { gunzipSync } from "node:zlib";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { CS1, DEFAULTS, sampleElevation, fetchBasemapWater, smooth, carveWater, encode16, png16 } from "../../terrain.js";
import { fitDrama, dramaFit, dramaSources } from "../../terrain-drama.mjs";
import { captureInputs, oceanMask } from "../../inputs.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const N = CS1.px;

function arg(name, fallback = null) {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : fallback;
}

const policy = arg("policy", "drama");
const fixture = arg("fixture");
const name = arg("name");
const center = arg("center");
const out = arg("out");
if (!out || (!fixture && !(name && center))) throw new Error("need --out and either --fixture or --name/--center");
const dir = join(out, policy);
await mkdir(dir, { recursive: true });

/** North-to-south float32 uncarved game heights, the writer's banks. */
const bankBytes = (banks) => {
  const bytes = Buffer.alloc(banks.length * 4);
  for (let i = 0; i < banks.length; i++) bytes.writeFloatLE(banks[i], i * 4);
  return bytes;
};

if (fixture) {
  const root = join(HERE, "fixtures", fixture);
  if (policy === "legacy") {
    // The fixture's stored inputs are the shipping capture: copy them byte for byte.
    for (const [from, to] of [["input.png", "input.png"], ["geometry.json.gz", "geometry.json"], ["banks.f32.gz", "banks.f32"]]) {
      let bytes = readFileSync(join(root, from));
      if (from.endsWith(".gz")) bytes = gunzipSync(bytes);
      await writeFile(join(dir, to), bytes);
    }
    await writeFile(join(dir, "inputs.json"), JSON.stringify({ policy: "legacy", copied_from: `fixtures/${fixture}` }, null, 2) + "\n");
    console.log(`${fixture}: legacy inputs copied to ${dir}`);
  } else {
    const geometry = JSON.parse(gunzipSync(readFileSync(join(root, "geometry.json.gz"))).toString());
    const sq = geometry.sq;
    const elev = await sampleElevation(sq);
    const sea = oceanMask(geometry.oceans ?? [], sq);
    const { spec, fit, banks, sources } = await buildDramaInputs({ sq, ground: smooth(elev.heights, DEFAULTS.sm), w: geometry, sea, elev });
    await writeFile(join(dir, "input.png"), new Uint8Array(await (await png16(encode16(fit.game), N, N)).arrayBuffer()));
    await writeFile(join(dir, "banks.f32"), bankBytes(banks));
    await writeFile(join(dir, "geometry.json"), JSON.stringify({ ...geometry, seaLevel: fit.seaLevel, sources,
      fit: { base: fit.base, verticalScale: fit.verticalScale, drama: fit.drama } }) + "\n");
    await writeFile(join(dir, "inputs.json"), JSON.stringify({ policy, square: sq, drama: fit.drama, sources }, null, 2) + "\n");
    console.log(`${fixture}: ${policy} gains ${spec.low} / ${spec.high} ${spec.limitedBy ?? ""} -> ${dir}`);
  }
} else {
  const [lat, lon] = center.split(",").map(Number);
  const sq = { lat, lon, rotation: 0, scale: 1, name, slug: name.toLowerCase().replace(/[^a-z0-9]+/g, "-"), vscale: "auto", rivers: true };
  if (policy === "legacy") {
    const inputs = await captureInputs(sq, { about: { tool: "terrain_drama_inputs.mjs" } });
    await writeFile(join(dir, "input.png"), inputs.png);
    await writeFile(join(dir, "banks.f32"), bankBytes(inputs.banks));
    await writeFile(join(dir, "geometry.json"), JSON.stringify(inputs.geometry) + "\n");
    await writeFile(join(dir, "inputs.json"), JSON.stringify({ policy, square: sq, geometry: inputs.geometry.fit }, null, 2) + "\n");
    console.log(`${name}: legacy inputs -> ${dir}`);
  } else {
    // A whole capture: the shape under drama is derived from the capture's own ground, so a
    // square gets the same ocean polygons, roads and water the shipping capture carries.
    const capture = await captureInputs(sq, { about: { tool: "terrain_drama_inputs.mjs" } });
    const { base, verticalScale } = capture.geometry.fit;
    const ground = Float32Array.from(capture.banks, (g) => (g - 50) / verticalScale + base);
    const sea = capture.geometry.seaLevel === null ? null : Uint8Array.from(ground, (v) => (v < -5 ? 1 : 0));
    const { spec, fit, banks, geometry, sources } = await buildDramaInputs({ sq, ground, w: capture.geometry, sea });
    await writeFile(join(dir, "input.png"), new Uint8Array(await (await png16(encode16(fit.game), N, N)).arrayBuffer()));
    await writeFile(join(dir, "banks.f32"), bankBytes(banks));
    await writeFile(join(dir, "geometry.json"), JSON.stringify(geometry) + "\n");
    await writeFile(join(dir, "inputs.json"), JSON.stringify({ policy, square: sq, drama: fit.drama, sources }, null, 2) + "\n");
    console.log(`${name}: ${policy} gains ${spec.low} / ${spec.high} ${spec.limitedBy ?? ""} -> ${dir}`);
  }
}

/** The shaped ground and the writer's geometry, from raw elevation and the captured water. */
async function buildDramaInputs({ sq, ground, w, sea, elev = null }) {
  const spec = fitDrama(ground, { sea, spacing: (CS1.extent * sq.scale) / (N - 1) });
  const carved = carveWater(ground, sq, w, { depth: DEFAULTS.rd / spec.high, halfWidth: DEFAULTS.rw, lakeDepth: DEFAULTS.ld / spec.high });
  const fit = dramaFit(ground, carved.heights, spec, { sea });
  const banks = dramaFit(ground, ground, spec, { sea }).game;
  const sources = (w.rivers?.length || w.lakes?.length) ? dramaSources(sq, w, carved, fit) : [];
  const geometry = {
    sq, rivers: w.rivers, lakes: w.lakes, riverAreas: w.riverAreas, fragments: w.fragments,
    source: w.source, zoom: w.zoom, tiles: w.tiles, streams: w.streams, roads: w.roads, oceans: w.oceans ?? [],
    sources, seaLevel: fit.seaLevel,
    fit: { base: fit.base, verticalScale: fit.verticalScale, drama: fit.drama },
    provenance: { capture: "terrain_drama_inputs.mjs", elevation: elev ? { source: "AWS Terrain Tiles / Terrarium", zoom: elev.zoom, tiles: elev.tiles } : { source: "shipping capture (inverted through its recorded fit)" },
      water: "OpenFreeMap / OpenStreetMap", terrain: "terrain-drama.mjs per-square-gain-v1" },
  };
  return { spec, fit, banks, geometry, sources };
}

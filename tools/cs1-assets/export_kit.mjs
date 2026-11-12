#!/usr/bin/env node
// Write one kudzu-kit building (PL-801) as plain triangles in the kit's local frame, so the
// Python side can texture it and Blender can write the FBX the CS1 Asset Editor imports.
//
//   node export_kit.mjs --kit <path to kudzu-kit> --type craftsman --seed 0.31 \
//        --width 10 --depth 12 --setback 3 --out house.json
//
// Local frame (the kit's own): u along the frontage, left to right seen from the street;
// y up from the floor base; w back from the street (the front wall faces -w). Metres.
import { pathToFileURL } from "node:url";
import { writeFileSync } from "node:fs";
import { resolve } from "node:path";

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, all) => (a.startsWith("--") ? [...acc, [a.slice(2), all[i + 1]]] : acc), []),
);
const need = (k) => {
  if (args[k] === undefined) throw new Error(`--${k} is required`);
  return args[k];
};
const kitDir = resolve(need("kit"));
const kit = await import(pathToFileURL(resolve(kitDir, "src/kit.js")).href);
const geom = await import(pathToFileURL(resolve(kitDir, "src/geom.js")).href);
const palette = await import(pathToFileURL(resolve(kitDir, "../pixel-asheville/src/palette.js")).href);

const type = args.type ?? "craftsman";
if (!kit.TYPES[type]) throw new Error(`unknown kit type ${type}; one of ${Object.keys(kit.TYPES).join(", ")}`);
const T = kit.TYPES[type];
const W = Number(args.width ?? T.size[0]);
const D = Number(args.depth ?? T.size[1]);
const seed = Number(args.seed ?? 0.31);
const setback = Number(args.setback ?? 3);
const kerb = 2.2;

// Footprint from w = 0 (front wall) to w = D, centred on u = 0; the street lies at -w, so the
// fitted frame has angle 0 and its origin at the middle of the front edge.
const ring = [[-W / 2, 0], [W / 2, 0], [W / 2, D], [-W / 2, D]];
const mesh = new geom.KitMesh();
const out = kit.buildKit(mesh, type, ring, {
  seed,
  front: [0, -(setback + kerb)],
  storeys: args.storeys ? Number(args.storeys) : T.storeys,
  variant: args.variant ? Number(args.variant) : undefined,
  heightAt: () => 0,
  kerb,
});
if (Math.abs(out.fit.ang) > 1e-6 || Math.hypot(out.fit.cx, out.fit.cz) > 1e-6)
  throw new Error(`unexpected kit frame ${JSON.stringify(out.fit)}`);

const n = mesh.p.length / 3;
const names = palette.NAMES;
const used = new Set(mesh.c);
writeFileSync(
  resolve(need("out")),
  JSON.stringify({
    source: { kit: kitDir, type, label: T.label, seed, width: W, depth: D, setback, storeys: args.storeys ?? T.storeys },
    frame: "kit-local: u right along the frontage, y up, w back from the street; metres",
    triangles: n / 3,
    // Flat-shaded triangles: 3 consecutive vertices each.
    position: Array.from(mesh.p, (v) => Math.round(v * 1e4) / 1e4),
    normal: Array.from(mesh.n, (v) => Math.round(v * 1e4) / 1e4),
    ramp: Array.from(mesh.c),
    style: Array.from(mesh.s),
    ramps: Object.fromEntries([...used].sort((a, b) => a - b).map((i) => [i, { name: names[i], hex: palette.RAMPS[names[i]] }])),
  }),
);
console.log(JSON.stringify({ type, triangles: n / 3, ramps: [...used].map((i) => names[i]) }));

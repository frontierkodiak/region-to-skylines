// Delivery check in three.js: put measured LoD2 buildings into the real pixel-asheville
// scene in place of the generator's, and photograph both at the city zoom and close in.
//
// Works on a scratch copy of pixel-asheville (see export_current.mjs); the copy's main.js
// gets two small hooks: the pilot ids join the generator's skip set, and their LoD2
// triangles are added as one more building chunk in pixel-asheville's own material, so the
// pixel pass, palette, shadows and terrain relief are the scene's own.
//
//   node current/pixel_import.mjs <workbench checkout> <id,id,...> [experiment dir]
import { cpSync, mkdirSync, readFileSync, writeFileSync, rmSync, symlinkSync, realpathSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { homedir } from "node:os";
import { chromium } from "playwright";
import { createServer } from "vite";

const here = dirname(fileURLToPath(import.meta.url));
const workbench = process.argv[2];
const ids = (process.argv[3] ?? "").split(",").map(Number).filter(Boolean);
const exp = realpathSync(process.argv[4] ?? join(homedir(), "experiments", "PL-900-lod2-pilot"));
const scratch = join(exp, "pixel-import");
rmSync(scratch, { recursive: true, force: true });
mkdirSync(scratch, { recursive: true });
for (const d of ["pixel-asheville", "kudzu-kit/src"]) cpSync(join(workbench, d), join(scratch, d), { recursive: true, filter: (s) => !s.includes("node_modules") });
symlinkSync(join(here, "../node_modules"), join(scratch, "pixel-asheville/node_modules"));

const file = join(scratch, "pixel-asheville/src/main.js");
let src = readFileSync(file, "utf8");
const swap = (a, b) => { if (!src.includes(a)) throw new Error("pixel-asheville changed; hook no longer applies: " + a.slice(0, 50)); src = src.replace(a, b); };
swap('import { buildBlocks, planBuildings, pointInRing, roadDistance } from "./buildings.js";',
  'import { buildBlocks, planBuildings, pointInRing, roadDistance, Mesh } from "./buildings.js";\nimport { R } from "./palette.js";\nimport { RELIEF } from "./world.js";');
swap("    skip: LANDMARK_SKIP,", "    skip: new Set([...LANDMARK_SKIP, ...(lod2 ? lod2.map((b) => b.id) : [])]),");
swap("  const clearance = footprintGrid(data.buildings);",
  '  const lod2 = params.has("lod2") ? await (await fetch("data/lod2.json")).json() : null;\n  const clearance = footprintGrid(data.buildings);');
swap('  chunks.set("landmarks", landmarks.mesh);', `  chunks.set("landmarks", landmarks.mesh);
  if (lod2) {
    const WALL = { brick: R.brick, stone: R.stone, concrete: R.concrete, stucco: R.stucco };
    const m = new Mesh();
    for (const b of lod2) {
      // scene.json triangles wind clockwise seen from outside; pixel-asheville culls back faces
      // the lidar ground beside the outline sits on the scene's lowest ground under it
      let base = Infinity;
      for (const [x, z] of b.ring) base = Math.min(base, heightAt(x + b.centre[0], z + b.centre[1]));
      m.roof = R.charcoal; m.seed = 0.5;
      for (let t = 0; t < b.kind.length; t++) {
        const o = t * 9, v = (i) => [b.tri[o + i] + b.centre[0], b.tri[o + i + 1] + base, b.tri[o + i + 2] + b.centre[1]];
        m.tri(v(0), v(6), v(3), b.kind[t] === "roof" ? R.charcoal : WALL[b.wall] ?? R.clapboard);
      }
    }
    chunks.set("lod2", m);
  }`);
writeFileSync(file, src);

const picked = ids.map((id) => {
  const s = JSON.parse(readFileSync(join(exp, "buildings", String(id), "scene.json"), "utf8"));
  const arm = s.arms.lod2;
  return { id, centre: s.centre, ring: s.ring, wall: s.wall, tri: arm.tri, kind: arm.kind };
});
writeFileSync(join(scratch, "pixel-asheville/public/data/lod2.json"), JSON.stringify(picked));

const out = join(exp, "pixel-import-shots");
mkdirSync(out, { recursive: true });
const server = await createServer({ root: join(scratch, "pixel-asheville"), server: { port: 5902, host: "127.0.0.1", fs: { strict: false } }, logLevel: "error" });
await server.listen();
const browser = await chromium.launch({ channel: "chrome", args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
try {
  for (const mode of (process.env.MODES ?? "generator,lod2").split(",")) {
    const page = await browser.newPage({ viewport: { width: 960, height: 720 } });
    page.on("pageerror", (e) => console.error("page error:", e.message));
    for (const b of picked) {
      for (const [name, zoom] of [["city", 2.8], ["close", 7]]) {
        await page.goto(`http://127.0.0.1:5902/index.html?x=${b.centre[0].toFixed(1)}&z=${b.centre[1].toFixed(1)}&zoom=${zoom}&season=summer${mode === "lod2" ? "&lod2=1" : ""}`);
        await page.waitForFunction(() => document.body.classList.contains("ready"), null, { timeout: 240000 });
        await page.waitForFunction(() => window.pixelAsheville.kitPending() === 0, null, { timeout: 240000 }).catch(() => {});
        await page.waitForTimeout(1500);
        await page.locator("#view").screenshot({ path: join(out, `${b.id}-${name}-${mode}.png`) });
        console.log(b.id, name, mode);
      }
    }
    await page.close();
  }
} finally {
  await browser.close();
  await server.close();
}

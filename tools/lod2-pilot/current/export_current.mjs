// Arm 1: the current pixel-asheville generator's geometry for the pilot buildings.
//
// Copies pixel-asheville and the kudzu kit (agentic-research-workbench, branch
// pl-778-pixel-asheville) into a scratch folder, adds bookkeeping to buildings.js so each
// footprint's triangles can be told apart (no change to what is drawn), runs the generator
// in a headless browser over the whole city with relief 1, and writes each pilot building's
// triangles. Close-view (kit) geometry is used where the generator has it.
//
//   node current/export_current.mjs <workbench checkout> [experiment dir]
import { cpSync, mkdirSync, readFileSync, writeFileSync, rmSync, symlinkSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { homedir } from "node:os";
import { chromium } from "playwright";
import { createServer } from "vite";

const here = dirname(fileURLToPath(import.meta.url));
const workbench = process.argv[2];
const exp = process.argv[3] ?? join(homedir(), "experiments", "PL-900-lod2-pilot");
if (!workbench) throw new Error("usage: export_current.mjs <workbench checkout> [experiment dir]");
const scratch = join(exp, "current-generator");
rmSync(scratch, { recursive: true, force: true });
mkdirSync(scratch, { recursive: true });
for (const d of ["pixel-asheville/src", "pixel-asheville/public", "kudzu-kit/src"]) cpSync(join(workbench, d), join(scratch, d), { recursive: true });
symlinkSync(join(here, "../node_modules"), join(scratch, "pixel-asheville/node_modules"));
const commit = execFileSync("git", ["-C", workbench, "rev-parse", "HEAD"]).toString().trim();

// Bookkeeping only: remember which slice of the chunk mesh each footprint wrote.
const file = join(scratch, "pixel-asheville/src/buildings.js");
let src = readFileSync(file, "utf8");
const swap = (a, b) => { if (!src.includes(a)) throw new Error("generator changed; patch no longer applies: " + a.slice(0, 60)); src = src.replace(a, b); };
swap("const out = buildKit(mesh, it.type, it.ring, {", "const s0 = mesh.p.length; const out = buildKit(mesh, it.type, it.ring, {");
swap("if (out.fallback) { stats.fallback++;", "it.span = [s0, mesh.p.length]; it.how = out.fallback ? 'block' : out.skipped ? 'skipped' : 'kit:' + out.type;\n      if (out.fallback) { stats.fallback++;");
swap(
  "buildBlocks({ fields: data.fields, rows: blocks }, nearestRoad, () => key, heightAt, { ...opts, skip, lookOf, chunks: new Map([[key, mesh]]) });",
  "for (const row of blocks) { const s1 = mesh.p.length; buildBlocks({ fields: data.fields, rows: [row] }, nearestRoad, () => key, heightAt, { ...opts, skip, lookOf, chunks: new Map([[key, mesh]]) }); (plan900.blockSpans ??= new Map()).set(row[F.id], [s1, mesh.p.length]); }",
);
swap("export function planBuildings(", "export const plan900 = {};\nexport function planBuildings(");
writeFileSync(file, src);
writeFileSync(join(scratch, "pixel-asheville/export.html"), `<!doctype html><meta charset="utf-8"><script type="module" src="./export.js"></script>`);
cpSync(join(here, "export_page.js"), join(scratch, "pixel-asheville/export.js"));

const ids = JSON.parse(readFileSync(join(exp, "selection/buildings.json"), "utf8")).buildings.map((b) => ({ id: b.id, ring: b.ring }));
const server = await createServer({ root: join(scratch, "pixel-asheville"), server: { port: 5900, host: "127.0.0.1", fs: { strict: false } }, logLevel: "error" });
await server.listen();
const browser = await chromium.launch({ channel: "chrome", args: ["--enable-unsafe-swiftshader"] });
try {
  const page = await browser.newPage();
  page.on("pageerror", (e) => console.error("page error:", e.message));
  await page.goto("http://127.0.0.1:5900/export.html?relief=1");
  await page.waitForFunction(() => window.exportBuildings, null, { timeout: 120000 });
  const out = await page.evaluate((ids) => window.exportBuildings(ids), ids);
  for (const b of out.buildings) {
    const dir = join(exp, "buildings", String(b.id));
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, "current.json"), JSON.stringify({ ...b, source: { repo: "frontierkodiak/agentic-research-workbench", commit } }));
    console.log(b.id, b.how, b.tri.length / 9, "tris", "height", b.height, b.estimated ? "(Microsoft estimate)" : "(6 m placeholder)");
  }
  console.log(JSON.stringify(out.stats));
} finally {
  await browser.close();
  await server.close();
}

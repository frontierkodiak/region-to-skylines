// Render every arm and the reference for each pilot building: city, close and top views.
//   node render.mjs [dev|locked|all] [experiment dir]
import { mkdirSync, readFileSync, writeFileSync, realpathSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { homedir } from "node:os";
import { chromium } from "playwright";
import { createServer } from "vite";

const here = dirname(fileURLToPath(import.meta.url));
const set = process.argv[2] ?? "dev";
const exp = realpathSync(process.argv[3] ?? join(homedir(), "experiments", "PL-900-lod2-pilot"));
const only = process.env.ONLY ? new Set(process.env.ONLY.split(",").map(Number)) : null;
const sel = JSON.parse(readFileSync(join(exp, "selection/buildings.json"), "utf8")).buildings
  .filter((b) => (set === "all" || b.set === set) && (!only || only.has(b.id)));
const server = await createServer({ root: join(here, "render"), server: { port: 5901, host: "127.0.0.1", fs: { strict: false } }, logLevel: "error" });
await server.listen();
const browser = await chromium.launch({ channel: "chrome", args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
try {
  const page = await browser.newPage();
  page.on("pageerror", (e) => console.error("page error:", e.message));
  page.on("console", (m) => { if (m.type() === "error") console.error("console:", m.text()); });
  await page.goto("http://127.0.0.1:5901/index.html");
  await page.waitForFunction(() => window.ready);
  const base = `/@fs${join(exp, "frozen")}`;
  for (const b of sel) {
    const dir = join(exp, "buildings", String(b.id));
    const scene = JSON.parse(readFileSync(join(dir, "scene.json"), "utf8"));
    mkdirSync(join(dir, "render"), { recursive: true });
    await page.evaluate((s) => { window.scene = s; }, scene);
    for (const what of ["ref", ...Object.keys(scene.arms)])
      for (const view of ["city", "close", "top"]) {
        const { url } = await page.evaluate(([w, v, base]) => window.renderScene(window.scene, w, v, base), [what, view, base]);
        writeFileSync(join(dir, "render", `${what}-${view}.png`), Buffer.from(url.split(",")[1], "base64"));
      }
    console.log(b.id, Object.keys(scene.arms).join(","));
  }
} finally {
  await browser.close();
  await server.close();
}

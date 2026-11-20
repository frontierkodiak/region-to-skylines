// Run on blade in the matching official Playwright image. Never on carbon.
// Usage: node test/capability-browser.mjs PLAYWRIGHT_CORE DIST OUTPUT [--live]
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { resolve, extname } from "node:path";
import { pathToFileURL } from "node:url";

const [modulePath, directory, output] = process.argv.slice(2);
const { chromium, webkit } = await import(pathToFileURL(resolve(modulePath, "index.mjs")));
const root = resolve(directory), out = resolve(output);
await mkdir(out, { recursive: true });
const section = (await readFile(resolve(root, "index.html"), "utf8")).match(/<section id="capabilities"[\s\S]*?<\/section>/)[0];
const server = createServer(async (req, res) => {
  const url = new URL(req.url, "http://local");
  if (url.pathname === "/__ui_probe") {
    res.setHeader("Content-Type", "text/html");
    return res.end(`<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/style.css"><main><aside id="panel">${section}</aside></main><script type="module">import {mountCapabilities} from '/capability-ui.js';window.capabilityProbe=mountCapabilities(document.querySelector('#capabilities'));</script>`);
  }
  const path = resolve(root, "." + (url.pathname === "/" ? "/index.html" : url.pathname));
  if (!path.startsWith(root + "/")) return res.writeHead(403).end();
  try {
    const bytes = await readFile(path);
    res.setHeader("Content-Type", ({ ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".css": "text/css" })[extname(path)] ?? "application/octet-stream");
    res.end(bytes);
  } catch { res.writeHead(404).end(); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const origin = `http://127.0.0.1:${server.address().port}`;
const results = { scope: "Synthetic UI state checks are not geographic/native evidence; live capture is recorded separately", browsers: [] };
try {
  for (const [name, engine] of [["chromium", chromium], ["webkit", webkit]]) {
    const browser = await engine.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    try {
      const page = await context.newPage();
      // Construction is deliberately explicit: these are controlled UI inputs.
      await page.route("**/capability-inputs.js", (route) => route.fulfill({ contentType: "text/javascript", body: `
        export async function captureEstimate(sq) {
          await new Promise((r) => setTimeout(r, sq.lat === 4 ? 1000 : 60));
          if (sq.lat === 3) throw new Error('constructed data failure');
          return { square:sq, input:{schema:1,mode:'estimate',transport:{road:sq.lat !== 1},buildable_fraction:sq.lat === 5 ? 0.1 : 0.8,grid:{size:17,spacing_m:1080,depth_m:new Array(289).fill(sq.lat === 1 ? 0 : 8)}} };
        }` }));
      await page.goto(origin + "/__ui_probe");
      await page.waitForFunction(() => !!window.capabilityProbe);
      assert.equal(await page.locator("[data-level=loading]").count(), 8);
      await page.evaluate(() => window.capabilityProbe.update({ lat: 1, lon: 0 }));
      assert.equal(await page.locator('[data-capability="ship"]').getAttribute("data-level"), "unknown");
      await page.locator('[data-capability="ship"]').focus();
      assert.match(await page.locator(".capability-detail").textContent(), /No broad deep corridor/);
      await page.evaluate(() => window.capabilityProbe.update({ lat: 2, lon: 0 }));
      assert.equal(await page.locator('[data-capability="ship"]').getAttribute("data-level"), "likely");
      assert.match(await page.locator(".capability-detail").textContent(), /game's ship path/);
      await page.evaluate(() => { window.capabilityProbe.update({lat:4,lon:0}); window.capabilityProbe.reset(); return window.capabilityProbe.update({lat:5,lon:0}); });
      await page.waitForTimeout(1100); // Intentionally wait past the stale constructed response.
      assert.match(await page.locator(".capability-status").textContent(), /5.000/);
      await page.locator('[data-capability="buildable"]').hover();
      assert.match(await page.locator(".capability-detail").textContent(), /10%/);
      await page.evaluate(() => window.capabilityProbe.update({ lat: 3, lon: 0 }));
      assert.equal(await page.locator("[data-level=unknown]").count(), 8);
      assert.match(await page.locator(".capability-status").textContent(), /unavailable/);
      assert.match(await page.locator(".capability-status").textContent(), /move the square to retry/);
      assert.ok(await page.locator(".capability-status").isVisible());
      await page.evaluate(() => window.capabilityProbe.update({ lat: 2, lon: 0 }));
      await page.screenshot({ path: resolve(out, `${name}-row-desktop.png`) });
      await page.setViewportSize({ width: 390, height: 844 });
      for (const box of await page.locator(".capability-row button").evaluateAll((els) => els.map((e) => ({ w: e.getBoundingClientRect().width, h: e.getBoundingClientRect().height })))) assert.ok(box.w >= 44 && box.h >= 44);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({ path: resolve(out, `${name}-row-phone.png`) });
      await page.unroute("**/capability-inputs.js");
      await page.goto(origin + "/capabilities.html");
      assert.equal(await page.locator("article").count(), 12);
      assert.match(await page.title(), /Map capabilities/);
      await page.screenshot({ path: resolve(out, `${name}-ledger-phone.png`) });
      const item = { browser: name, version: browser.version(), synthetic_states: "pass", ledger_page: "pass", live: "not_run" };
      if (process.argv.includes("--live")) {
        const errors = []; page.on("pageerror", (e) => errors.push(e.message));
        await page.setViewportSize({ width: 1440, height: 1000 });
        await page.goto(origin + "/#c=-71.057,42.36&r=0&s=1&h=auto&rivers=1&n=boston");
        await page.waitForFunction(() => /estimate|unavailable/.test(document.querySelector(".capability-status")?.textContent ?? ""), undefined, { timeout: 120000 });
        item.live = { status: await page.locator(".capability-status").textContent(), icons: await page.locator(".capability-row button").evaluateAll((els) => els.map((e) => ({ id: e.dataset.capability, level: e.dataset.level, description: e.title }))), errors };
        assert.match(item.live.status, /estimate/, "real capture must finish, not silently become unavailable");
        assert.deepEqual(errors, []);
        await page.screenshot({ path: resolve(out, `${name}-boston-live.png`) });
        const box = await page.locator("#map").boundingBox();
        const x = box.x + box.width / 2, y = box.y + box.height / 2;
        await page.mouse.move(x, y); await page.mouse.down();
        await page.mouse.move(x + 80, y, { steps: 10 });
        await page.waitForFunction(() => document.querySelectorAll('.capability-row [data-level="loading"]').length === 8);
        await page.mouse.up();
        await page.waitForFunction(() => /estimate|unavailable/.test(document.querySelector(".capability-status")?.textContent ?? ""), undefined, { timeout: 120000 });
        item.live.pan_status = await page.locator(".capability-status").textContent();
        assert.match(item.live.pan_status, /estimate/);
        assert.notEqual(item.live.pan_status, item.live.status, "pan must produce a different square, with stale indicators cleared first");
      }
      results.browsers.push(item);
      console.log(`${name}: synthetic states, mobile layout and ledger passed; live=${typeof item.live === "string" ? item.live : item.live.status}`);
    } finally { await context.close(); await browser.close(); }
  }
} finally { await new Promise((r) => server.close(r)); await writeFile(resolve(out, "browser-results.json"), JSON.stringify(results, null, 2)); }

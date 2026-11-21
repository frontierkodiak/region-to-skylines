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
// WorldCover has no CORS headers, so the page reads it through the same
// /worldcover/ rewrite the deployed site and dev.mjs use.
const WORLDCOVER = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/";
const TILE = /^\/worldcover\/(ESA_WorldCover_10m_2021_v200_[NS]\d{2}[EW]\d{3}_Map\.tif)$/;
const server = createServer(async (req, res) => {
  const url = new URL(req.url, "http://local");
  const tile = url.pathname.match(TILE);
  if (tile) {
    const upstream = await fetch(WORLDCOVER + tile[1], { headers: req.headers.range ? { Range: req.headers.range } : {} });
    const headers = { "Cache-Control": "public, max-age=31536000, immutable" };
    for (const name of ["content-type", "content-length", "content-range", "accept-ranges"]) if (upstream.headers.get(name)) headers[name] = upstream.headers.get(name);
    res.writeHead(upstream.status, headers);
    return res.end(Buffer.from(await upstream.arrayBuffer()));
  }
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
        const comparable = {
          terrain_relief_m: {comparable:true, basis:'capture_heightmap'},
          median_land_slope_percent: {comparable:false, detail:'Slope needs the prepared terrain and water mask; constructed UI input only.'},
          wet_central_fraction: {comparable:false, detail:'Carved-bed depth is not the prepared water level; constructed UI input only.'},
        };
        const N = 17, total = N * N, flat = new Array(total).fill(100);
        const cover = (cls) => ({status:'available', source:'ESA WorldCover (constructed)', fidelity:'constructed', cell_m:10, sample_m:40, tiles:['N00E000'], values:new Array(total).fill(cls)});
        const place = (sq) => sq.lat === 5
          ? {terrain_m:flat, landcover:{status:'unavailable', source:'ESA WorldCover (constructed)'}, deposits:{status:'unavailable', source:'USGS MRDS (constructed)', records:[]}}
          : sq.lat === 1
            ? {terrain_m:flat, landcover:cover(50), deposits:{status:'available', source:'USGS MRDS (constructed)', records:[]}}
            : sq.lat === 7
              ? {terrain_m:flat, landcover:cover(30), deposits:{status:'available', source:'USGS MRDS (constructed)', records:[]}}
              : {terrain_m:flat, landcover:cover(10), deposits:{status:'available', source:'USGS MRDS (constructed)', records:[{kind:'ore',x:0,z:0,weight:1}]}};
        export async function captureEstimate(sq) {
          await new Promise((r) => setTimeout(r, sq.lat === 4 ? 1000 : 60));
          if (sq.lat === 3) throw new Error('constructed data failure');
          const depth = new Array(total).fill([1, 6, 7].includes(sq.lat) ? 0 : 8);
          return { square:sq,
            input:{schema:1,mode:'estimate',transport:{road:sq.lat !== 1},buildable_fraction:sq.lat === 5 ? 0.1 : 0.8,grid:{size:N,spacing_m:1080,depth_m:depth},place:place(sq)},
            stock:{fidelity:'capture_estimate',measures:{terrain_relief_m:sq.lat === 1 ? 300 : sq.lat === 5 ? 1200 : 700,median_land_slope_percent:9.9,wet_central_fraction:0.5},comparability:comparable} };
        }` }));
      await page.goto(origin + "/__ui_probe");
      await page.waitForFunction(() => !!window.capabilityProbe);
      assert.equal(await page.locator("[data-level=loading]").count(), 8);
      assert.equal(await page.locator(".stock-row[data-state=checking]").count(), 3);
      await page.evaluate(() => window.capabilityProbe.update({ lat: 1, lon: 0 }));
      assert.equal(await page.locator('[data-capability="ship"]').getAttribute("data-level"), "unknown");
      await page.locator('[data-capability="ship"]').focus();
      assert.match(await page.locator(".capability-detail").textContent(), /No broad deep corridor/);
      // Constructed place evidence: built-up land with no deposit record is a
      // scoped No for trees and Unknown for resources, never a resource No.
      assert.equal(await page.locator('[data-capability="trees"]').getAttribute("data-level"), "unknown");
      await page.locator('[data-capability="trees"]').focus();
      assert.match(await page.locator(".capability-detail").textContent(), /No tree-supporting cover in this 40 m WorldCover sampling/);
      await page.locator('[data-capability="resources"]').focus();
      assert.equal(await page.locator('[data-capability="resources"]').getAttribute("data-level"), "unknown");
      assert.match(await page.locator(".capability-detail").textContent(), /A missing record is not absence/);
      // Constructed low/typical/high stock bands; the two capture-limited measures stay uncompared.
      assert.equal(await page.locator('[data-metric="terrain_relief_m"]').getAttribute("data-band"), "below_p25");
      assert.equal(await page.locator('[data-metric="terrain_relief_m"] .stock-value').textContent(), "300 m");
      for (const id of ["median_land_slope_percent", "wet_central_fraction"]) {
        const row = page.locator(`[data-metric="${id}"]`);
        assert.equal(await row.getAttribute("data-state"), "not_comparable");
        assert.equal(await row.locator(".stock-value").textContent(), "—");
        assert.equal(await row.locator(".stock-band").textContent(), "Not comparable");
      }
      assert.match(await page.locator(".stock-basis").textContent(), /^104 shipped maps/);
      await page.locator('[data-metric="terrain_relief_m"]').focus();
      assert.match(await page.locator(".capability-detail").textContent(), /p25 595\.9 m/, "bounds show at display precision, not ledger float noise");
      assert.doesNotMatch(await page.locator(".capability-detail").textContent(), /9999/);
      await page.locator('[data-metric="median_land_slope_percent"]').focus();
      assert.match(await page.locator(".capability-detail").textContent(), /not comparable from this square's map-time capture/);
      assert.match(await page.locator(".capability-detail").textContent(), /prepared terrain and water mask/);
      await page.locator('[data-capability="ship"]').focus(); // the icon detail still follows its own focus
      await page.evaluate(() => window.capabilityProbe.update({ lat: 2, lon: 0 }));
      assert.equal(await page.locator('[data-capability="ship"]').getAttribute("data-level"), "likely");
      assert.match(await page.locator(".capability-detail").textContent(), /game's ship path/);
      // This constructed square is all water, so trees cannot be judged while
      // the recorded deposit still stands on its own.
      await page.locator('[data-capability="trees"]').focus();
      assert.equal(await page.locator('[data-capability="trees"]').getAttribute("data-level"), "unknown");
      assert.match(await page.locator(".capability-detail").textContent(), /no dry land/);
      await page.locator('[data-capability="resources"]').focus();
      assert.equal(await page.locator('[data-capability="resources"]').getAttribute("data-level"), "likely");
      assert.match(await page.locator(".capability-detail").textContent(), /ore deposit recorded in the central tiles/);
      assert.match(await page.locator(".capability-detail").textContent(), /Records, not measured reserves/);
      // A positive icon is only Maybe, and its detail names the land-cover
      // measure separately from the export's planted trees.
      await page.evaluate(() => window.capabilityProbe.update({ lat: 6, lon: 0 }));
      await page.locator('[data-capability="trees"]').focus();
      assert.equal(await page.locator('[data-capability="trees"]').getAttribute("data-level"), "likely");
      assert.match(await page.locator(".capability-detail").textContent(), /Land cover, not the export's planted trees/);
      assert.match(await page.locator(".capability-detail").textContent(), /WorldCover sampling/);
      assert.match(await page.locator(".capability-detail").textContent(), /Tree cover on 100% of the central tiles/);
      // Grassland below the tree candidate level is Unknown, and the fertility
      // detail names cropland separately from the weighted suitability.
      await page.evaluate(() => window.capabilityProbe.update({ lat: 7, lon: 0 }));
      await page.locator('[data-capability="trees"]').focus();
      assert.equal(await page.locator('[data-capability="trees"]').getAttribute("data-level"), "unknown");
      assert.match(await page.locator(".capability-detail").textContent(), /below the 0\.05 candidate level/);
      await page.locator('[data-capability="resources"]').focus();
      assert.equal(await page.locator('[data-capability="resources"]').getAttribute("data-level"), "likely");
      assert.match(await page.locator(".capability-detail").textContent(), /Fertile-land suitability 0\.7/);
      assert.match(await page.locator(".capability-detail").textContent(), /cropland 0%/);
      assert.doesNotMatch(await page.locator(".capability-detail").textContent(), /Crop and pasture cover on 0%/);
      assert.equal(await page.locator('[data-metric="terrain_relief_m"]').getAttribute("data-band"), "typical");
      assert.equal(await page.locator('[data-metric="terrain_relief_m"] .stock-value').textContent(), "700 m");
      await page.evaluate(() => window.capabilityProbe.update({ lat: 5, lon: 0 }));
      assert.equal(await page.locator('[data-metric="terrain_relief_m"]').getAttribute("data-band"), "above_p75");
      assert.equal(await page.locator('[data-metric="terrain_relief_m"] .stock-value').textContent(), "1200 m");
      // Terrain loaded but land cover and deposits did not: Unknown, not No.
      await page.locator('[data-capability="trees"]').focus();
      assert.equal(await page.locator('[data-capability="trees"]').getAttribute("data-level"), "unknown");
      assert.match(await page.locator(".capability-detail").textContent(), /Land cover could not be loaded/);
      await page.locator('[data-capability="resources"]').focus();
      assert.equal(await page.locator('[data-capability="resources"]').getAttribute("data-level"), "unknown");
      assert.match(await page.locator(".capability-detail").textContent(), /Neither land cover nor deposits could be loaded/);
      await page.evaluate(() => window.capabilityProbe.reset());
      assert.equal(await page.locator(".stock-row[data-state=checking]").count(), 3);
      for (const id of ["trees", "resources"]) {
        assert.equal(await page.locator(`[data-capability="${id}"]`).getAttribute("data-level"), "loading");
        assert.equal(await page.locator(`[data-capability="${id}"] .capability-mark`).textContent(), "…");
      }
      assert.equal(await page.locator('[data-metric="terrain_relief_m"] .stock-value').textContent(), "…",
        "a pan clears the previous square instead of showing it against a new one");
      await page.evaluate(() => { window.capabilityProbe.update({lat:4,lon:0}); window.capabilityProbe.reset(); return window.capabilityProbe.update({lat:5,lon:0}); });
      await page.waitForTimeout(1100); // Intentionally wait past the stale constructed response.
      assert.match(await page.locator(".capability-status").textContent(), /5.000/);
      await page.locator('[data-capability="buildable"]').hover();
      assert.match(await page.locator(".capability-detail").textContent(), /10%/);
      await page.evaluate(() => window.capabilityProbe.update({ lat: 3, lon: 0 }));
      assert.equal(await page.locator("[data-level=unknown]").count(), 8);
      assert.equal(await page.locator(".stock-row[data-state=unknown]").count(), 3, "a failed capture leaves no stock band behind");
      assert.match(await page.locator('[data-capability="trees"]').getAttribute("title"), /Trees: unknown\. This square's data could not be loaded/);
      assert.match(await page.locator(".capability-status").textContent(), /unavailable/);
      assert.match(await page.locator(".capability-status").textContent(), /move the square to retry/);
      assert.ok(await page.locator(".capability-status").isVisible());
      await page.evaluate(() => window.capabilityProbe.update({ lat: 2, lon: 0 }));
      await page.screenshot({ path: resolve(out, `${name}-row-desktop.png`) });
      await page.setViewportSize({ width: 390, height: 844 });
      for (const box of await page.locator(".capability-row button").evaluateAll((els) => els.map((e) => ({ w: e.getBoundingClientRect().width, h: e.getBoundingClientRect().height })))) assert.ok(box.w >= 44 && box.h >= 44);
      for (const box of await page.locator(".stock-row").evaluateAll((els) => els.map((e) => ({ w: e.getBoundingClientRect().width, h: e.getBoundingClientRect().height })))) assert.ok(box.w >= 44 && box.h >= 44);
      await page.locator('[data-metric="terrain_relief_m"]').click();
      assert.match(await page.locator(".capability-detail").textContent(), /p25/, "a tap reveals the stock numbers on touch");
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({ path: resolve(out, `${name}-row-phone.png`) });
      await page.unroute("**/capability-inputs.js");
      await page.goto(origin + "/capabilities.html");
      assert.equal(await page.locator("article").count(), 12);
      assert.match(await page.title(), /Map capabilities/);
      assert.match(await page.locator("#trees").textContent(), /Place evidence measures/);
      assert.match(await page.locator("#trees").textContent(), /Sources, coverage and fidelity/);
      assert.match(await page.locator("#resources").textContent(), /balanced ore\/oil top-up/i);
      assert.match(await page.locator("#resources").textContent(), /Missing records are missing coverage, not absence/);
      await page.screenshot({ path: resolve(out, `${name}-ledger-phone.png`) });
      const item = { browser: name, version: browser.version(), synthetic_states: "pass", ledger_page: "pass", live: "not_run" };
      if (process.argv.includes("--live")) {
        const errors = []; page.on("pageerror", (e) => errors.push(e.message));
        await page.setViewportSize({ width: 1440, height: 1000 });
        await page.goto(origin + "/#c=-71.057,42.36&r=0&s=1&h=auto&rivers=1&n=boston");
        await page.waitForFunction(() => /estimate|unavailable/.test(document.querySelector(".capability-status")?.textContent ?? ""), undefined, { timeout: 120000 });
        item.live = { status: await page.locator(".capability-status").textContent(), icons: await page.locator(".capability-row button").evaluateAll((els) => els.map((e) => ({ id: e.dataset.capability, level: e.dataset.level, description: e.title }))), stock: await page.locator(".stock-row").evaluateAll((els) => els.map((e) => ({ id: e.dataset.metric, state: e.dataset.state, band: e.dataset.band ?? null, value: e.querySelector(".stock-value").textContent, band_text: e.querySelector(".stock-band").textContent, description: e.title }))), errors };
        assert.match(item.live.status, /estimate/, "real capture must finish, not silently become unavailable");
        const place = Object.fromEntries(item.live.icons.filter((icon) => ["trees", "resources"].includes(icon.id)).map((icon) => [icon.id, icon]));
        assert.equal(place.trees.description.includes("WorldCover"), true, "real trees evidence names its source");
        assert.ok(["likely", "unknown"].includes(place.trees.level), "real land cover is a candidate or unknown, never promised");
        assert.ok(["likely", "unknown"].includes(place.resources.level), "real deposits are a candidate or unknown, never promised");
        assert.doesNotMatch(`${place.trees.description} ${place.resources.description}`, /Verified/);
        const real = Object.fromEntries(item.live.stock.map((row) => [row.id, row]));
        assert.equal(real.terrain_relief_m.state, "measured", "real geography gives a real relief estimate, labelled as such");
        assert.match(real.terrain_relief_m.description, /Capture estimate, not the finished map/);
        assert.match(real.terrain_relief_m.description, /p25/);
        for (const id of ["median_land_slope_percent", "wet_central_fraction"])
          assert.equal(real[id].state, "not_comparable", "real capture never compares the prepared-only measures");
        assert.match(await page.locator(".stock-basis").textContent(), /^104 shipped maps/);
        assert.deepEqual(errors, []);
        await page.screenshot({ path: resolve(out, `${name}-boston-live.png`) });
        const box = await page.locator("#map").boundingBox();
        const x = box.x + box.width / 2, y = box.y + box.height / 2;
        await page.mouse.move(x, y); await page.mouse.down();
        await page.mouse.move(x + 80, y, { steps: 10 });
        await page.waitForFunction(() => document.querySelectorAll('.capability-row [data-level="loading"]').length === 8 && document.querySelectorAll('.stock-row[data-state="checking"]').length === 3);
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

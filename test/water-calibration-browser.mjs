// Static ledger and evidence only; run on blade in official Playwright 1.65.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { resolve, extname } from "node:path";
import { pathToFileURL } from "node:url";
const [modulePath, directory, output] = process.argv.slice(2);
const {chromium, webkit} = await import(pathToFileURL(resolve(modulePath, "index.mjs")));
const root = resolve(directory), out = resolve(output);
await mkdir(out, {recursive:true});
const server = createServer(async (req, res) => {
  const path = resolve(root, "." + new URL(req.url, "http://local").pathname);
  if (!path.startsWith(root + "/")) return res.writeHead(403).end();
  try {
    res.setHeader("Content-Type", ({".html":"text/html", ".js":"text/javascript", ".json":"application/json", ".css":"text/css"})[extname(path)] ?? "application/octet-stream");
    res.end(await readFile(path));
  } catch {res.writeHead(404).end();}
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const origin = `http://127.0.0.1:${server.address().port}`;
const results = {scope:"Static page and saved evidence HTTP bytes. No fresh native run, current-product qualification, or live Boston capture.", browsers:[]};
try {
  for (const [name, engine] of [["chromium",chromium],["webkit",webkit]]) {
    const browser = await engine.launch({headless:true});
    try {
      const page = await browser.newPage({viewport:{width:1440,height:1000}});
      const errors=[]; page.on("pageerror", (e) => errors.push(String(e)));
      await page.goto(origin + "/capabilities.html#water_risk");
      const study = page.locator('[data-calibration-study="pl1072-independent-geography"]');
      assert.match(await study.textContent(), /failed qualification/);
      assert.match(await study.locator('[data-water-targets]').textContent(), /20.0% \[0.5%, 71.6%\]/);
      assert.equal(await study.locator('[data-water-clearance] tbody tr').count(), 2);
      for (const row of await study.locator('[data-water-clearance] tbody tr').all()) {
        assert.match(await row.textContent(), /NOT ESTIMABLE \(n=0\)/);
        assert.equal(await row.locator("td").nth(2).textContent(), "NOT ESTIMABLE (n=0)");
      }
      assert.match(await study.textContent(), /Study deployed-screen comparator/);
      await study.locator('summary').filter({hasText:"30 squares, including both unknowns"}).click();
      assert.equal(await study.locator('[data-water-squares] tbody tr').count(), 30);
      for (const slug of ["lake-shore-south-america","low-coast-africa"]) {
        const row = study.locator('[data-water-squares] tbody tr').filter({hasText:slug});
        for (const cell of [row.locator("td").nth(1), row.locator("td").nth(2)])
          assert.match(await cell.textContent(), /\/ Unknown$/);
      }
      await study.locator('summary').filter({hasText:"Definitions, scope and provenance"}).click();
      assert.match(await study.textContent(), /initialized optional-water loss/);
      assert.match(await study.textContent(), /Native observation date: Unknown/);
      await page.screenshot({path:resolve(out,name+"-desktop.png"),fullPage:false});
      const ledger = await (await page.request.get(origin+"/capabilities.json")).json();
      const water = ledger.capabilities.find((c) => c.id === "water_risk").calibration_studies['pl1072-independent-geography'];
      const httpFiles=[];
      for (const ref of water.provenance.files) {
        const response = await page.request.get(origin+"/"+ref.file); assert.equal(response.status(), 200);
        const digest=createHash("sha256").update(await response.body()).digest("hex");
        assert.equal(digest,ref.sha256); httpFiles.push({file:ref.file,sha256:digest});
      }
      const checked = await page.evaluate(async () => {
        const {checkCapabilities} = await import('/capability-model.js');
        const ledger = await (await fetch('/capabilities.json')).json();
        return checkCapabilities({schema:1, mode:'estimate'},ledger);
      });
      for (const id of ['water','start']) assert.equal(checked.capabilities[id].level,'unknown');
      for (const width of [390,320]) {
        await page.setViewportSize({width,height:844});
        await page.locator('#water_risk').scrollIntoViewIfNeeded();
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'page must not overflow');
        const container = study.locator('.ledger-table').first();
        assert.equal(await container.evaluate((e) => getComputedStyle(e).overflowX), 'auto');
        assert.ok(await container.evaluate((e) => e.getBoundingClientRect().right <= innerWidth), 'table remains inside viewport');
        if (await container.evaluate((e) => e.scrollWidth > e.clientWidth)) {
          await container.evaluate((e) => {e.scrollLeft=e.scrollWidth;});
          assert.ok(await container.evaluate((e) => e.scrollLeft > 0));
        }
        if (width === 390) {
          await study.locator('h3').evaluate((e) => e.scrollIntoView({block:'start'}));
          await page.screenshot({path:resolve(out,name+'-phone.png')});
        }
      }
      await page.setViewportSize({width:390,height:844});
      const summary = study.locator('summary').filter({hasText:'By world region'});
      await summary.focus(); await page.keyboard.press('Enter');
      assert.equal(await summary.evaluate((e) => e.parentElement.open),true);
      assert.deepEqual(errors,[]);
      results.browsers.push({name, widths:[1440,390,320], unknown_rows:2, no_clearance_rows:2, httpFiles, page_errors:errors});
    } finally {await browser.close();}
  }
  await writeFile(resolve(out,'results.json'),JSON.stringify(results,null,2)+'\n');
  console.log(JSON.stringify(results));
} finally {await new Promise((r) => server.close(r));}

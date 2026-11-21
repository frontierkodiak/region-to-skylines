// Run only on blade in the official matching Playwright image.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { resolve, extname } from "node:path";
import { pathToFileURL } from "node:url";

const [modulePath, directory, inputsFile, output] = process.argv.slice(2);
const { chromium, webkit } = await import(pathToFileURL(resolve(modulePath, "index.mjs")));
const root = resolve(directory), out = resolve(output);
const inputs = JSON.parse(await readFile(inputsFile, "utf8"));
assert.equal(inputs.cases.length, 9);
await mkdir(out, { recursive: true });
const server = createServer(async (request, response) => {
  const path = resolve(root, "." + new URL(request.url, "http://local").pathname);
  if (!path.startsWith(root + "/")) return response.writeHead(403).end();
  try {
    response.setHeader("Content-Type", ({".html":"text/html", ".js":"text/javascript", ".json":"application/json", ".css":"text/css"})[extname(path)] ?? "application/octet-stream");
    response.end(await readFile(path));
  } catch {response.writeHead(404).end();}
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const origin = `http://127.0.0.1:${server.address().port}`;
const results = { scope: "Real retained export inputs. Activation is a constructed test proposal, not production acceptance, fresh game evidence, or a pan-time promise.", browsers: [] };
try {
  for (const [name, engine] of [["chromium", chromium], ["webkit", webkit]]) {
    const browser = await engine.launch({headless:true});
    try {
      const page = await browser.newPage({viewport:{width:1280,height:960}});
      const errors = [];
      page.on("pageerror", (e) => errors.push(String(e)));
      await page.goto(origin + "/capabilities.html");
      assert.equal(await page.locator("[data-study]").count(), 2);
      assert.match(await page.locator('[data-study="outside-targeted-v2"]').textContent(), /4 awaiting independent review. Active certificates: 0/);
      assert.match(await page.locator('[data-study="outside-v1"]').textContent(), /11 boundary witnesses/);
      assert.match(await page.locator('[data-study="outside-targeted-v2"]').textContent(), /not accuracy/);
      const calculated = await page.evaluate(async (input) => {
        const {checkCapabilities} = await import("/capability-model.js");
        const ledger = await (await fetch("/capabilities.json")).json();
        const staged = ledger.evidence_studies["outside-targeted-v2"].qualification_candidates;
        for (const c of staged) {
          const raw = await (await fetch("/" + c.runtime_identity_evidence.file)).arrayBuffer();
          const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", raw))).map((v) => v.toString(16).padStart(2,"0")).join("");
          if (digest !== c.runtime_identity_evidence.sha256) throw new Error("Served receipt changed");
        }
        const levels = (d, l) => Object.fromEntries(Object.entries(checkCapabilities(d,l).capabilities).map(([k,v])=>[k,v.level]));
        const real = input.cases.map((d) => levels(d, ledger));
        const proposal = structuredClone(ledger);
        proposal.native_path_certificates = staged.map((c) => {const o=structuredClone(c);delete o.blocked_by;return o;});
        const planned = input.cases.map((d) => levels(d, proposal));
        const pan = input.cases.map((d) => levels({...d, mode:"estimate"}, proposal));
        const mutated = input.cases.map((d) => {
          const x=structuredClone(d);
          if(x.export_identity.native_context) x.export_identity.native_context.opening_runtime_identity.assemblies[1].sha256="0".repeat(64);
          return levels(x,proposal);
        });
        return {real, planned, pan, mutated, servedReceipts:staged.length};
      }, inputs);
      const count = (rows) => rows.flatMap(Object.values).filter((level) => level === "promised").length;
      assert.equal(count(calculated.real), 0);
      assert.equal(count(calculated.planned), 4);
      assert.equal(count(calculated.pan), 0);
      assert.equal(count(calculated.mutated), 0);
      assert.deepEqual(errors, []);
      await page.screenshot({path:resolve(out, `${name}-ledger.png`)});
      await page.setViewportSize({width:390,height:844});
      await page.locator('[data-study="outside-targeted-v2"]').scrollIntoViewIfNeeded();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.screenshot({path:resolve(out, `${name}-ledger-phone.png`)});
      results.browsers.push({engine:name, served_receipts:calculated.servedReceipts, real_promotions:0, constructed_activation_promotions:4, pan_promotions:0, mutated_context_promotions:0, ledger: "v1/targeted-v2 distinct; not accuracy; independent review pending; phone no horizontal overflow"});
    } finally {await browser.close();}
  }
} finally {await new Promise((r) => server.close(r));}
results.ledger_sha256 = createHash("sha256").update(await readFile(resolve(root, "capabilities.json"))).digest("hex");
await writeFile(resolve(out, "results.json"), JSON.stringify(results,null,2)+"\n");
console.log(JSON.stringify(results));

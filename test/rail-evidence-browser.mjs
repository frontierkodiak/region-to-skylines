// Run on blade in the official mcr.microsoft.com/playwright:v1.65.0-noble image.
// This checks the generated ledger page and the served evidence bytes; it is not a
// native observation, a live question or geographic evidence.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { resolve, extname } from "node:path";
import { pathToFileURL } from "node:url";

const [modulePath, directory, output] = process.argv.slice(2);
const { chromium, webkit } = await import(pathToFileURL(resolve(modulePath, "index.mjs")));
const root = resolve(directory), out = resolve(output);
await mkdir(out, { recursive: true });
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".css": "text/css" };
const server = createServer(async (request, response) => {
  const path = resolve(root, "." + new URL(request.url, "http://local").pathname);
  if (!path.startsWith(root + "/")) return response.writeHead(403).end();
  try {
    const bytes = await readFile(path);
    response.setHeader("Content-Type", TYPES[extname(path)] ?? "application/octet-stream");
    response.end(bytes);
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const origin = `http://127.0.0.1:${server.address().port}`;
const results = {
  scope: "Generated ledger page and served archived bytes; not fresh native evidence, service or a geographic claim.",
  page: `${origin}/capabilities.html`,
  browsers: [],
};
try {
  for (const [name, engine] of [["chromium", chromium], ["webkit", webkit]]) {
    const browser = await engine.launch({ headless: true });
    try {
      const page = await browser.newPage({ viewport: { width: 1280, height: 960 } });
      const errors = [];
      page.on("pageerror", (error) => errors.push(String(error)));
      await page.goto(origin + "/capabilities.html");
      assert.equal(errors.length, 0, `${name}: page errors: ${errors.join("; ")}`);

      const study = page.locator("#rail-directed-study");
      assert.equal(await study.count(), 1, `${name}: missing rail study section`);
      assert.equal(await page.locator("[data-rail-controls] tbody tr").count(), 2);
      assert.equal(await page.locator("[data-rail-cohort] tbody tr").count(), 10);
      assert.equal(await page.locator("[data-rail-attempts] tbody tr").count(), 10);
      const text = await study.textContent();
      for (const phrase of ["Asanu Beach", "Hanami Bay", "Pittsburgh", "Boston", "244", "233", "112", "Unknown",
        "positive-witness agreement", "not accuracy", "strict-verifier-failure.txt", "later", "rail-v1/README.md"]) {
        assert.ok(text.includes(phrase), `${name}: rail section is missing ${phrase}`);
      }
      assert.ok(!/accuracy: \d/.test(text), `${name}: page flattens the study into an accuracy headline`);

      const evidence = await page.$$eval("[data-evidence]", (nodes) => nodes.map((node) => ({
        href: node.getAttribute("href"),
        sha256: node.getAttribute("data-sha256"),
        text: node.textContent,
      })));
      assert.ok(evidence.length >= 170, `${name}: only ${evidence.length} evidence links rendered`);
      const external = evidence.filter((item) => /^https?:/.test(item.href));
      assert.deepEqual(external, [], `${name}: evidence is not served locally`);
      const missingSha = evidence.filter((item) => !/^[a-f0-9]{64}$/.test(item.sha256 ?? ""));
      assert.deepEqual(missingSha, [], `${name}: an evidence link has no hash`);

      // Every link the page presents must return exactly the bytes it names.
      const checked = await page.evaluate(async (items) => {
        const hex = (buffer) => [...new Uint8Array(buffer)].map((b) => b.toString(16).padStart(2, "0")).join("");
        const failures = [];
        for (const item of items) {
          try {
            const response = await fetch(item.href);
            if (!response.ok) { failures.push(`${item.href}: HTTP ${response.status}`); continue; }
            const actual = hex(await crypto.subtle.digest("SHA-256", await response.arrayBuffer()));
            if (actual !== item.sha256) failures.push(`${item.href}: ${actual} != ${item.sha256}`);
          } catch (error) {
            failures.push(`${item.href}: ${String(error)}`);
          }
        }
        return failures;
      }, evidence);
      assert.deepEqual(checked, [], `${name}: served evidence bytes changed`);

      // Keyboard access: the case table and every evidence link are reachable.
      await page.locator('[data-rail-cohort] tbody tr th').first().click();
      const before = await page.evaluate(() => document.activeElement?.tagName ?? "BODY");
      await page.keyboard.press("Tab");
      const after = await page.evaluate(() => ({
        tag: document.activeElement?.tagName ?? "BODY",
        visible: document.activeElement?.matches(":focus-visible") ?? false,
      }));
      assert.notEqual(after.tag, "BODY", `${name}: keyboard focus does not advance`);
      assert.ok(after.visible || before === "BODY", `${name}: keyboard focus is not visible`);
      const reachable = await page.evaluate(() => {
        const link = document.querySelector("[data-evidence]");
        link.focus();
        return document.activeElement === link && link.tabIndex >= 0;
      });
      assert.ok(reachable, `${name}: evidence links are not focusable`);

      // Phone layouts: the document itself never scrolls sideways; tables scroll inside.
      for (const width of [390, 320]) {
        await page.setViewportSize({ width, height: 844 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true,
          `${name}: page overflows at ${width}px`);
        await page.locator("#rail-directed-study").scrollIntoViewIfNeeded();
        await page.screenshot({ path: resolve(out, `${name}-rail-${width}.png`), fullPage: false });
        const readable = await page.evaluate(() => {
          const section = document.querySelector("#rail-directed-study");
          const rect = section.getBoundingClientRect();
          return rect.width > 0 && rect.left >= 0 && rect.right <= innerWidth + 1;
        });
        assert.ok(readable, `${name}: rail section is not readable at ${width}px`);
      }
      results.browsers.push({ name, evidence: evidence.length, viewport: "390/320", status: "pass" });
    } finally {
      await browser.close();
    }
  }
  results.status = "pass";
} finally {
  server.close();
  await writeFile(resolve(out, "rail-browser.json"), JSON.stringify(results, null, 2) + "\n");
}
console.log(JSON.stringify(results, null, 2));

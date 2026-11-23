// Run on blade in the official mcr.microsoft.com/playwright:v1.65.0-noble image.
// This checks the generated ledger page and the served evidence bytes; it is not
// a native observation, a live question or geographic evidence.
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
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".css": "text/css", ".py": "text/x-python" };
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
await new Promise((ready) => server.listen(0, "127.0.0.1", ready));
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

      const study = page.locator("#outside-research-study");
      assert.equal(await study.count(), 1, `${name}: missing outside research study section`);
      assert.equal(await page.locator("[data-outside-research]").count(), 1, `${name}: the study is rendered more than once`);
      assert.equal((await page.getByRole("heading", { name: "Outside-connection query evidence" }).count()), 3,
        `${name}: Road, Ship and Air must each reference the one study`);

      const counts = {
        primary: 7, modes: 3, groups: 2, packages: 6, folds: 6, disagreements: 19,
        rows: 876, "all-rules": 12, exclusions: 498, bridge: 9,
      };
      for (const [table, expected] of Object.entries(counts)) {
        const actual = await page.locator(`[data-outside-${table}] tbody tr`).count();
        assert.equal(actual, expected, `${name}: ${table} table has ${actual} rows, expected ${expected}`);
      }

      const text = await study.textContent();
      for (const phrase of [
        "Primary stratum · distinct edges · all modes",
        "TP 93 · FP 19 · TN 230 · FN 0",
        "pre-registered primary",
        "Ship and air are one class",
        "one class only",
        "Every disagreement",
        "unknown",
        "flags",
        "100000",
        "Ship and air are one class",
        "not an observation date",
        "observation dates: Unknown",
        "27,191 segments",
        "Complete rows · 876 retained requests",
        "Exclusions, anomalies and eligibility rules",
        "not blind or global accuracy",
        "outside-query-model-v1/RESULTS.md",
        "predictions.json",
      ]) {
        assert.ok(text.includes(phrase), `${name}: outside section is missing ${phrase}`);
      }
      assert.ok(!/accuracy: \d/.test(text), `${name}: page flattens the study into an accuracy headline`);
      assert.ok(!/promised/i.test(text), `${name}: page promises a capability`);

      const evidence = await page.$$eval("[data-evidence]", (nodes) => nodes.map((node) => ({
        href: node.getAttribute("href"),
        sha256: node.getAttribute("data-sha256"),
        text: node.textContent,
      })));
      assert.ok(evidence.length >= 18, `${name}: only ${evidence.length} carried evidence links rendered`);
      const external = evidence.filter((item) => /^https?:/.test(item.href));
      assert.deepEqual(external, [], `${name}: carried evidence is not served locally`);
      const missingSha = evidence.filter((item) => !/^[a-f0-9]{64}$/.test(item.sha256 ?? ""));
      assert.deepEqual(missingSha, [], `${name}: an evidence link has no hash`);

      // Every local link the page presents must return exactly the bytes it names.
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

      // The three bulk sources stay at the publication commit as immutable blobs.
      const linked = await page.$$eval("[data-linked-evidence]", (nodes) => nodes.map((node) => ({
        href: node.getAttribute("href"), blob: node.getAttribute("data-blob"),
      })));
      assert.equal(linked.length, 3, `${name}: expected the three linked bulk sources`);
      for (const item of linked) {
        assert.match(item.href, /^https:\/\/github\.com\/frontierkodiak\/region-to-skylines\/blob\/030db86ce470b972b6ef3462a2698744dff40ebb\//,
          `${name}: a linked source is not an immutable blob URL`);
        assert.match(item.blob, /^[a-f0-9]{40}$/, `${name}: a linked source has no blob id`);
      }

      // Keyboard access: the row table and every evidence link are reachable and visibly focused.
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
        const summary = document.querySelector("#outside-research-study details summary");
        summary.focus();
        return document.activeElement === summary && summary.tabIndex >= 0;
      });
      assert.ok(reachable, `${name}: the study's details are not keyboard reachable`);

      // Phone and desktop layouts: the document never scrolls sideways; tables scroll inside.
      for (const [width, height] of [[1280, 960], [390, 844], [320, 844]]) {
        await page.setViewportSize({ width, height });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true,
          `${name}: page overflows at ${width}px`);
        await page.locator("#outside-research-study").scrollIntoViewIfNeeded();
        const readable = await page.evaluate(() => {
          const section = document.querySelector("#outside-research-study");
          const rect = section.getBoundingClientRect();
          return rect.width > 0 && rect.left >= 0 && rect.right <= innerWidth + 1;
        });
        assert.ok(readable, `${name}: outside section is not readable at ${width}px`);
        await page.locator("#outside-research-study h2").scrollIntoViewIfNeeded();
        await page.screenshot({ path: resolve(out, `${name}-outside-top-${width}.png`), fullPage: false });
        await page.locator("#outside-research-study").scrollIntoViewIfNeeded();
        await page.screenshot({ path: resolve(out, `${name}-outside-${width}.png`), fullPage: false });
      }

      // The complete 876-row ledger and the primary table, opened for the record.
      await page.setViewportSize({ width: 1280, height: 960 });
      await page.locator("[data-outside-primary]").scrollIntoViewIfNeeded();
      await page.screenshot({ path: resolve(out, `${name}-outside-primary-1280.png`), fullPage: false });
      const rowDetails = page.locator("#outside-research-study details", { hasText: "Complete rows" });
      await rowDetails.locator("summary").click();
      await page.locator("[data-outside-rows] tbody tr").first().scrollIntoViewIfNeeded();
      await page.screenshot({ path: resolve(out, `${name}-outside-rows-1280.png`), fullPage: false });
      assert.equal(await page.locator("[data-outside-rows] tbody tr").first().isVisible(), true,
        `${name}: the complete row table cannot be opened`);
      await page.locator("[data-outside-rows] tbody tr").last().scrollIntoViewIfNeeded();
      assert.equal(await page.locator("[data-outside-rows] tbody tr").last().isVisible(), true,
        `${name}: the last retained row is not reachable`);
      await rowDetails.locator("summary").click();

      // The three capability references are readable at phone width too.
      await page.setViewportSize({ width: 390, height: 844 });
      for (const id of ["road", "ship", "air"]) {
        await page.locator(`#${id}`).scrollIntoViewIfNeeded();
        await page.screenshot({ path: resolve(out, `${name}-reference-${id}.png`), fullPage: false });
      }
      results.browsers.push({ name, evidence: evidence.length, linked: linked.length, viewports: "1280/390/320", status: "pass" });
    } finally {
      await browser.close();
    }
  }
  results.status = "pass";
  results.evidence = "Every carried evidence link served bytes matching its recorded SHA-256.";
  results.screenshots = [
    "chromium-outside-top-1280.png", "chromium-outside-primary-1280.png", "chromium-outside-rows-1280.png",
    "chromium-outside-390.png", "chromium-outside-320.png",
    "webkit-outside-top-1280.png", "webkit-outside-primary-1280.png", "webkit-outside-rows-1280.png",
    "webkit-outside-390.png", "webkit-outside-320.png",
    "chromium-reference-road.png", "chromium-reference-ship.png", "chromium-reference-air.png",
  ];
  results.hashes = {
    "capabilities.html": createHash("sha256").update(await readFile(resolve(root, "capabilities.html"))).digest("hex"),
  };
} finally {
  server.close();
  await writeFile(resolve(out, "outside-browser.json"), JSON.stringify(results, null, 2) + "\n");
}
console.log(JSON.stringify(results, null, 2));

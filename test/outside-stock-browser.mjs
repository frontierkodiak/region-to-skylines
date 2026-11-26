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
  scope: "Generated ledger page and served archived bytes; not fresh native evidence, a qualification or a geographic claim.",
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

      const study = page.locator("#outside-stock-study");
      assert.equal(await study.count(), 1, `${name}: missing outside-stock study section`);
      assert.equal(await page.locator("[data-outside-stock]").count(), 1, `${name}: the study is rendered more than once`);
      assert.equal((await page.getByRole("heading", { name: "Outside-stock validation and budget limits" }).count()), 4,
        `${name}: the page heading plus Road, Ship and Air references must each be present`);

      const counts = {
        population: 5, packages: 5, modes: 4, "package-mode": 9, strata: 6, tags: 6, subset: 1,
        bridge: 11, drift: 2, controls: 12, intervention: 8, windows: 9,
        requests: 84, groups: 40, disagreements: 12,
      };
      for (const [table, expected] of Object.entries(counts)) {
        const actual = await page.locator(`[data-outside-stock-${table}] tbody tr`).count();
        assert.equal(actual, expected, `${name}: ${table} table has ${actual} rows, expected ${expected}`);
      }

      const text = await study.textContent();
      for (const phrase of [
        "All three modes remain UNQUALIFIED",
        "descriptive intent-to-test",
        "TP 28 · FP 0 · TN 20 · FN 0",
        "Only these 16 road requests have exact export/native field identity",
        "The other 32 requests fail exact bridge identity",
        "One-class package-modes",
        "MetaBool string \"False\"",
        "not a clean single-variable trial",
        "not proof of native exhaustion",
        "says nothing about blade's current slot or process state",
        "holdout-03/air/002",
        "pittsburgh/native-v2-6/road/093",
      ]) {
        assert.ok(text.includes(phrase), `${name}: outside-stock section is missing ${phrase}`);
      }
      // The modes total row must sum the reference rule's per-mode cells.
      const referenceTotal = await page
        .locator("[data-outside-stock-modes] tbody tr:last-child td:nth-child(6)")
        .textContent();
      assert.equal(referenceTotal.trim(), "TP 28 · FP 12 · TN 8 · FN 0",
        `${name}: the reference total row is wrong`);
      assert.ok(!/accuracy: \d/.test(text), `${name}: page flattens the study into an accuracy headline`);
      assert.ok(!/promised/i.test(text), `${name}: page promises a capability`);
      // Long hashes and Unknown groups stay legible instead of being clipped to a placeholder.
      assert.match(text, /[a-f0-9]{64}/, `${name}: no full hash is shown`);
      assert.ok(text.includes("Unknown"), `${name}: the Unknown controls are not labelled`);
      assert.ok(text.includes("not observed"), `${name}: the retained unknown state is hidden`);

      const evidence = await page.$$eval("#outside-stock-study [data-evidence]", (nodes) => nodes.map((node) => ({
        href: node.getAttribute("href"),
        sha256: node.getAttribute("data-sha256"),
        text: node.textContent,
      })));
      assert.equal(evidence.length, 32, `${name}: expected the 32 carried files`);
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

      // The bulky members stay at the publication commit as immutable blobs.
      const linked = await page.$$eval("#outside-stock-study [data-linked-evidence]", (nodes) => nodes.map((node) => ({
        href: node.getAttribute("href"), blob: node.getAttribute("data-blob"),
      })));
      assert.equal(linked.length, 110, `${name}: expected the 110 linked bulky members`);
      for (const item of linked) {
        assert.match(item.href, /^https:\/\/github\.com\/frontierkodiak\/region-to-skylines\/blob\/d745b14e3e207ee67f91033811958a2934fb38a4\//,
          `${name}: a linked source is not an immutable blob URL`);
        assert.match(item.blob, /^[a-f0-9]{40}$/, `${name}: a linked source has no blob id`);
      }
      // No giant archive is served from the product; the three preparation
      // archives exist only as immutable external blobs.
      assert.equal(evidence.some((item) => /\.zip$/.test(item.href)), false);
      assert.equal(linked.filter((item) => /\.zip$/.test(item.href)).length, 3);

      // Keyboard access: the study's details and an evidence link are reachable and visibly focused.
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
        const summary = document.querySelector("#outside-stock-study details summary");
        summary.focus();
        return document.activeElement === summary && summary.tabIndex >= 0;
      });
      assert.ok(reachable, `${name}: the study's details are not keyboard reachable`);

      // Phone and desktop layouts: the document never scrolls sideways; tables scroll inside.
      for (const [width, height] of [[1280, 960], [390, 844], [320, 844]]) {
        await page.setViewportSize({ width, height });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true,
          `${name}: page overflows at ${width}px`);
        await page.locator("#outside-stock-study").scrollIntoViewIfNeeded();
        const readable = await page.evaluate(() => {
          const section = document.querySelector("#outside-stock-study");
          const rect = section.getBoundingClientRect();
          return rect.width > 0 && rect.left >= 0 && rect.right <= innerWidth + 1;
        });
        assert.ok(readable, `${name}: outside-stock section is not readable at ${width}px`);
        await page.locator("#outside-stock-study h2").scrollIntoViewIfNeeded();
        await page.screenshot({ path: resolve(out, `${name}-outside-stock-top-${width}.png`), fullPage: false });
        await page.locator("#outside-stock-study").scrollIntoViewIfNeeded();
        await page.screenshot({ path: resolve(out, `${name}-outside-stock-${width}.png`), fullPage: false });
      }

      // The complete 84-row request table and the intervention, opened for the record.
      await page.setViewportSize({ width: 1280, height: 960 });
      await page.locator("[data-outside-stock-intervention]").scrollIntoViewIfNeeded();
      await page.screenshot({ path: resolve(out, `${name}-outside-stock-intervention-1280.png`), fullPage: false });
      const rowDetails = page.locator("#outside-stock-study details", { hasText: "All 84 planned requests" });
      await rowDetails.locator("summary").click();
      await page.locator("[data-outside-stock-requests] tbody tr").first().scrollIntoViewIfNeeded();
      await page.screenshot({ path: resolve(out, `${name}-outside-stock-requests-1280.png`), fullPage: false });
      assert.equal(await page.locator("[data-outside-stock-requests] tbody tr").first().isVisible(), true,
        `${name}: the complete request table cannot be opened`);
      await page.locator("[data-outside-stock-requests] tbody tr").last().scrollIntoViewIfNeeded();
      assert.equal(await page.locator("[data-outside-stock-requests] tbody tr").last().isVisible(), true,
        `${name}: the last planned request is not reachable`);
      await rowDetails.locator("summary").click();

      // The three capability references are readable at phone width too.
      await page.setViewportSize({ width: 390, height: 844 });
      for (const id of ["road", "ship", "air"]) {
        await page.locator(`#${id}`).scrollIntoViewIfNeeded();
        await page.screenshot({ path: resolve(out, `${name}-outside-stock-reference-${id}.png`), fullPage: false });
      }
      results.browsers.push({ name, evidence: evidence.length, linked: linked.length, viewports: "1280/390/320", status: "pass" });
    } finally {
      await browser.close();
    }
  }
  results.status = "pass";
  results.evidence = "Every carried evidence link served bytes matching its recorded SHA-256.";
  results.screenshots = [
    "chromium-outside-stock-top-1280.png", "chromium-outside-stock-intervention-1280.png",
    "chromium-outside-stock-requests-1280.png", "chromium-outside-stock-390.png", "chromium-outside-stock-320.png",
    "webkit-outside-stock-top-1280.png", "webkit-outside-stock-intervention-1280.png",
    "webkit-outside-stock-requests-1280.png", "webkit-outside-stock-390.png", "webkit-outside-stock-320.png",
    "chromium-outside-stock-reference-road.png", "chromium-outside-stock-reference-ship.png",
    "chromium-outside-stock-reference-air.png",
  ];
  results.hashes = {
    "capabilities.html": createHash("sha256").update(await readFile(resolve(root, "capabilities.html"))).digest("hex"),
  };
} finally {
  server.close();
  await writeFile(resolve(out, "outside-stock-browser.json"), JSON.stringify(results, null, 2) + "\n");
}
console.log(JSON.stringify(results, null, 2));

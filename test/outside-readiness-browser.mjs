// Run on blade in the official mcr.microsoft.com/playwright:v1.65.0-noble image.
// This checks the generated ledger page and the served archived bytes; it is not
// a native observation, a live question or geographic evidence.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { resolve, extname } from "node:path";
import { pathToFileURL } from "node:url";
import { gunzipSync } from "node:zlib";

const [modulePath, directory, output] = process.argv.slice(2);
const { chromium, webkit } = await import(pathToFileURL(resolve(modulePath, "index.mjs")));
const root = resolve(directory), out = resolve(output);
await mkdir(out, { recursive: true });
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".css": "text/css", ".py": "text/x-python", ".gz": "application/gzip" };
const server = createServer(async (request, response) => {
  const path = resolve(root, "." + new URL(request.url, "http://local").pathname);
  if (!path.startsWith(root + "/")) return response.writeHead(403).end();
  try {
    const bytes = await readFile(path);
    const type = TYPES[extname(path)] ?? "application/octet-stream";
    response.setHeader("Content-Type", type);
    if (extname(path) === ".gz") response.setHeader("Content-Encoding", "identity");
    response.end(bytes);
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise((ready) => server.listen(0, "127.0.0.1", ready));
const origin = `http://127.0.0.1:${server.address().port}`;
const hex = (buffer) => createHash("sha256").update(buffer).digest("hex");
const results = {
  scope: "Generated ledger page and served archived bytes for one stopped evidence study; not fresh native evidence, a qualification or a geographic claim.",
  page: `${origin}/capabilities.html`,
  browsers: [],
};
try {
  const projection = await (await fetch(`${origin}/tools/map-factory/capability-evidence/outside-readiness-studies.json`)).json();
  const study = projection.studies["outside-readiness-stock-v2"];
  assert.ok(study, "the served projection lost the study");

  // HTTP raw hashes: every served raw gzip returns exactly the bytes it names
  // and decompresses to the recorded original bytes.
  const rawFailures = [];
  for (const record of study.raw) {
    const response = await fetch(origin + "/" + record.path);
    if (!response.ok) { rawFailures.push(`${record.path}: HTTP ${response.status}`); continue; }
    const served = Buffer.from(await response.arrayBuffer());
    if (hex(served) !== record.sha256) rawFailures.push(`${record.path}: gzip hash`);
    try {
      const original = gunzipSync(served);
      if (hex(original) !== record.raw_sha256 || original.length !== record.raw_bytes) rawFailures.push(`${record.path}: decompressed bytes`);
    } catch (error) {
      rawFailures.push(`${record.path}: ${String(error)}`);
    }
  }
  assert.deepEqual(rawFailures, [], "a served raw gzip does not match its recorded hashes");
  results.rawEvidence = { files: study.raw.length, checked: study.raw.length, status: "pass" };

  for (const [name, engine] of [["chromium", chromium], ["webkit", webkit]]) {
    const browser = await engine.launch({ headless: true });
    try {
      const page = await browser.newPage({ viewport: { width: 1280, height: 960 } });
      const errors = [];
      page.on("pageerror", (error) => errors.push(String(error)));
      await page.goto(origin + "/capabilities.html");
      assert.equal(errors.length, 0, `${name}: page errors: ${errors.join("; ")}`);

      const section = page.locator("#outside-readiness-study");
      assert.equal(await section.count(), 1, `${name}: missing outside-readiness study section`);
      assert.equal(await page.locator("[data-outside-readiness]").count(), 1, `${name}: the study is rendered more than once`);
      assert.equal((await page.getByRole("heading", { name: "Outside-query controls on a frozen unseen cohort — Unknown" }).count()), 4,
        `${name}: the page heading plus Road, Ship and Air references must each be present`);

      const counts = { outcome: 1, holdout: 6, digests: 3, controls: 12, selection: 1, windows: 2, untouched: 4, raw: 51 };
      for (const [table, expected] of Object.entries(counts)) {
        const actual = await page.locator(`[data-outside-readiness-${table}] tbody tr`).count();
        assert.equal(actual, expected, `${name}: ${table} table has ${actual} rows, expected ${expected}`);
      }

      const text = await section.textContent();
      for (const phrase of [
        "Outcome · Unknown",
        "Zero of six planned holdout requests were issued",
        "not estimable",
        "never 0%",
        "82",
        "30",
        "03f7fb7c8eb8e3d6dd94f6444c5cd0cbd2156c325148b1006b564776a34f226d",
        "561e4b522bc27fe9c06eb59a0ed875461b47277a2379c18d5998b8e753854860",
        "not a qualification",
        "post-exit audit",
        "fresh clone cannot reproduce the full verify",
      ]) {
        assert.ok(text.includes(phrase), `${name}: outside-readiness section is missing ${phrase}`);
      }
      assert.ok(!/accuracy:\s*\d/.test(text), `${name}: page flattens the study into an accuracy headline`);
      assert.ok(!/(?:accuracy|precision|recall)[^.]{0,40}\b\d+%/i.test(text), `${name}: page presents a numeric accuracy figure`);
      assert.ok(!/promised/i.test(text), `${name}: page promises a capability`);
      assert.equal((text.match(/Unknown/g) ?? []).length >= 6, true, `${name}: the six Unknown cells are not labelled`);
      assert.match(text, /[a-f0-9]{64}/, `${name}: no full hash is shown`);

      const evidence = await page.$$eval("#outside-readiness-study [data-evidence]", (nodes) => nodes.map((node) => ({
        href: node.getAttribute("href"),
        sha256: node.getAttribute("data-sha256"),
        text: node.textContent,
      })));
      assert.equal(evidence.length, 25, `${name}: expected the 25 carried files`);
      assert.deepEqual(evidence.filter((item) => /^https?:/.test(item.href)), [], `${name}: carried evidence is not served locally`);
      assert.deepEqual(evidence.filter((item) => !/^[a-f0-9]{64}$/.test(item.sha256 ?? "")), [], `${name}: an evidence link has no hash`);
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

      // The bulk frozen feature dump stays at the publication commit as an immutable blob.
      const linked = await page.$$eval("#outside-readiness-study [data-linked-evidence]", (nodes) => nodes.map((node) => ({
        href: node.getAttribute("href"), blob: node.getAttribute("data-blob"),
      })));
      assert.equal(linked.length, 1, `${name}: expected the one linked bulk member`);
      assert.match(linked[0].href, /^https:\/\/github\.com\/frontierkodiak\/region-to-skylines\/blob\/4eca4d291cc133513e8bac6484185d3a3b6e80ae\//,
        `${name}: the linked source is not an immutable blob URL`);
      assert.match(linked[0].blob, /^[a-f0-9]{40}$/, `${name}: the linked source has no blob id`);
      assert.equal(linked.some((item) => /\.zip$/.test(item.href)), false);

      // The five carried raw gzip files are served locally with both hashes.
      const rawLinks = await page.$$eval("#outside-readiness-study [data-raw-evidence]", (nodes) => nodes.map((node) => ({
        href: node.getAttribute("href"), sha256: node.getAttribute("data-sha256"), raw: node.getAttribute("data-raw-sha256"),
      })));
      assert.equal(rawLinks.length, 5, `${name}: expected five carried raw files`);
      for (const item of rawLinks) {
        assert.ok(!/^https?:/.test(item.href), `${name}: raw evidence is not served locally`);
        assert.match(item.sha256, /^[a-f0-9]{64}$/);
        assert.match(item.raw, /^[a-f0-9]{64}$/);
      }

      // Long hashes wrap instead of being clipped at the phone widths.
      for (const width of [320, 390, 1280]) {
        await page.setViewportSize({ width, height: 844 });
        const clipped = await page.evaluate(() => [...document.querySelectorAll("#outside-readiness-study code")]
          .filter((node) => /^[a-f0-9]{40,64}$/.test(node.textContent.trim()))
          .filter((node) => node.scrollWidth > node.clientWidth + 1).length);
        assert.equal(clipped, 0, `${name}: a full hash is clipped at ${width}px`);
      }

      // Keyboard access: tab advances and the study's details are reachable and visibly focused.
      await page.setViewportSize({ width: 1280, height: 960 });
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.keyboard.press("Tab");
      const after = await page.evaluate(() => ({
        tag: document.activeElement?.tagName ?? "BODY",
        visible: document.activeElement?.matches(":focus-visible") ?? false,
      }));
      assert.notEqual(after.tag, "BODY", `${name}: keyboard focus does not advance`);
      assert.ok(after.visible, `${name}: keyboard focus is not visible`);
      const reachable = await page.evaluate(() => {
        const link = document.querySelector("#outside-readiness-study [data-evidence]");
        link.focus();
        const summary = document.querySelector("#outside-readiness-study details summary");
        summary.focus();
        return document.activeElement === summary && summary.tabIndex >= 0;
      });
      assert.ok(reachable, `${name}: the study's details are not keyboard reachable`);

      // Phone and desktop layouts: the document never scrolls sideways; tables scroll inside.
      for (const [width, height] of [[1280, 960], [390, 844], [320, 844]]) {
        await page.setViewportSize({ width, height });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true,
          `${name}: page overflows at ${width}px`);
        await page.locator("#outside-readiness-study").scrollIntoViewIfNeeded();
        const readable = await page.evaluate(() => {
          const section = document.querySelector("#outside-readiness-study");
          const rect = section.getBoundingClientRect();
          return rect.width > 0 && rect.left >= 0 && rect.right <= innerWidth + 1;
        });
        assert.ok(readable, `${name}: outside-readiness section is not readable at ${width}px`);
        await page.locator("#outside-readiness-study h2").scrollIntoViewIfNeeded();
        await page.screenshot({ path: resolve(out, `${name}-outside-readiness-top-${width}.png`), fullPage: false });
        await page.locator("#outside-readiness-study").scrollIntoViewIfNeeded();
        await page.screenshot({ path: resolve(out, `${name}-outside-readiness-${width}.png`), fullPage: false });
      }

      // The refusal digests and the full 51-row raw hash table, opened for the record.
      await page.setViewportSize({ width: 1280, height: 960 });
      await page.locator("[data-outside-readiness-digests]").scrollIntoViewIfNeeded();
      await page.screenshot({ path: resolve(out, `${name}-outside-readiness-refusal-1280.png`), fullPage: false });
      const rawDetails = page.locator("#outside-readiness-study details", { hasText: "All 51 retained raw hashes" });
      await rawDetails.locator("summary").click();
      await page.locator("[data-outside-readiness-raw] tbody tr").first().scrollIntoViewIfNeeded();
      assert.equal(await page.locator("[data-outside-readiness-raw] tbody tr").first().isVisible(), true,
        `${name}: the raw hash table cannot be opened`);
      await page.locator("[data-outside-readiness-raw] tbody tr").last().scrollIntoViewIfNeeded();
      assert.equal(await page.locator("[data-outside-readiness-raw] tbody tr").last().isVisible(), true,
        `${name}: the last raw hash is not reachable`);
      await page.screenshot({ path: resolve(out, `${name}-outside-readiness-raw-1280.png`), fullPage: false });
      await rawDetails.locator("summary").click();

      // The three capability references are readable at phone width too.
      await page.setViewportSize({ width: 390, height: 844 });
      for (const id of ["road", "ship", "air"]) {
        await page.locator(`#${id}`).scrollIntoViewIfNeeded();
        await page.screenshot({ path: resolve(out, `${name}-outside-readiness-reference-${id}.png`), fullPage: false });
      }
      results.browsers.push({ name, evidence: evidence.length, linked: linked.length, raw: rawLinks.length, viewports: "1280/390/320", status: "pass" });
    } finally {
      await browser.close();
    }
  }
  results.status = "pass";
  results.evidence = "Every carried evidence link served bytes matching its recorded SHA-256, and every raw gzip decompressed to its recorded original hash.";
  results.screenshots = [
    "chromium-outside-readiness-top-1280.png", "chromium-outside-readiness-refusal-1280.png",
    "chromium-outside-readiness-raw-1280.png", "chromium-outside-readiness-390.png", "chromium-outside-readiness-320.png",
    "webkit-outside-readiness-top-1280.png", "webkit-outside-readiness-refusal-1280.png",
    "webkit-outside-readiness-raw-1280.png", "webkit-outside-readiness-390.png", "webkit-outside-readiness-320.png",
    "chromium-outside-readiness-reference-road.png", "chromium-outside-readiness-reference-ship.png",
    "chromium-outside-readiness-reference-air.png",
  ];
  results.hashes = {
    "capabilities.html": hex(await readFile(resolve(root, "capabilities.html"))),
  };
} finally {
  server.close();
  await writeFile(resolve(out, "outside-readiness-browser.json"), JSON.stringify(results, null, 2) + "\n");
}
console.log(JSON.stringify(results, null, 2));

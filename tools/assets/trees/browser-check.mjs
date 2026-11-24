import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdir, writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';

const [modulePath, gallery, out] = process.argv.slice(2);
const {chromium} = createRequire(import.meta.url)(modulePath);
await mkdir(out, {recursive: true});
const browser = await chromium.launch({headless: true, chromiumSandbox: true});
const results = [];
try {
  for (const width of [1440, 390]) {
    const page = await browser.newPage({viewport: {width, height: 1000}});
    const errors = [];
    page.on('pageerror', error => errors.push(String(error)));
    await page.goto(pathToFileURL(gallery).href);
    assert.equal(await page.locator('article').count(), 18);
    assert.equal(await page.locator('article small').filter({hasText: 'CS1'}).count(), 18);
    await page.locator('img').evaluateAll(images => images.forEach(img => img.loading = 'eager'));
    await page.waitForFunction(() => [...document.images].every(img => img.complete && img.naturalWidth > 0));
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.locator('#genus').selectOption('Tilia');
    assert.equal(await page.locator('article:visible').count(), 6);
    await page.locator('#route').selectOption('sand3d');
    assert.equal(await page.locator('article:visible').count(), 3);
    await page.locator('#view').selectOption('gameplay');
    assert(await page.locator('article:visible img').evaluateAll(images => images.every(img => img.src.endsWith('-gameplay.png'))));
    await page.waitForFunction(() => [...document.images].every(img => img.complete && img.naturalWidth > 0));
    assert.equal(errors.length, 0, errors.join('\n'));
    await page.screenshot({path: `${out}/gallery-${width}.png`, fullPage: true});
    results.push({width, nativeCards: 18, filteredCards: 3, imagesLoaded: true, horizontalOverflow: false, errors});
    await page.close();
  }
  await writeFile(`${out}/browser-check.json`, JSON.stringify(results, null, 2) + '\n');
  console.log(JSON.stringify(results));
} finally {
  await browser.close();
}

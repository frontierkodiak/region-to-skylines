// Run inside the matching Playwright container against the generated shelf.
import assert from 'node:assert/strict';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
const { chromium } = await import(process.argv[2]);
const url = process.argv[3];
const out = process.argv[4];
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ headless: true });
const receipts = [];
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(url);
  await page.getByRole('heading', { name: 'What can we plant?' }).waitFor();
  assert.ok(await page.locator('#rows tr').count() > 0);
  receipts.push('Workshop results render');
  assert.ok(await page.locator('#best-rows tr').count() > 0);
  await page.locator('#best-biome').selectOption('14');
  assert.ok((await page.locator('#best-rows').innerText()).includes('Mangroves'));
  await page.locator('#best-biome').selectOption('4');
  receipts.push('Best-form references can be compared by biome');
  await page.locator('#quality').selectOption('near_reference');
  assert.ok(await page.locator('#rows tr').count() > 0);
  await page.locator('#quality').selectOption('');
  receipts.push('Qualified near-art references are distinct from full forest passes');
  const handbackUrl = new URL('reference-handback.json', url);
  const handback = handbackUrl.protocol === 'file:'
    ? JSON.parse(readFileSync(handbackUrl, 'utf8'))
    : await (await page.request.get(handbackUrl.href)).json();
  assert.equal(handback.genera.Gleditsia.status, 'no_vetted_match');
  for (const ref of [handback.genera.Tilia.best_intrinsic_size_match,
    handback.genera.Tilia.best_near_art_alternative, handback.genera.Ulmus.reference]) {
    assert.equal(ref.save_reload_identity_stable, true);
    assert.equal(ref.native_frame_hashes.length, 7);
    assert.equal(ref.bioclip_qualification, 'not_run');
  }
  receipts.push('Genus handback retains exact anchors, missing genus and BioCLIP uncertainty');
  await page.locator('#source').selectOption('base');
  assert.ok(await page.locator('#rows tr').count() > 0);
  await page.locator('#biome').selectOption('14');
  assert.ok(await page.locator('#empty').isVisible());
  receipts.push('Unestablished built-in mangrove coverage is empty');
  await page.locator('#biome').selectOption('');
  await page.locator('#source').selectOption('workshop');
  await page.locator('#quality').selectOption('pass');
  assert.ok(await page.locator('#empty').isVisible());
  receipts.push('No unreviewed asset appears as a pass');
  await page.locator('#quality').selectOption('fail');
  assert.ok(await page.locator('#rows tr').count() > 0);
  receipts.push('Forest-fill failures can be browsed');
  await page.locator('#quality').selectOption('');
  await page.locator('#search').fill('pine');
  assert.ok(await page.locator('#rows tr').count() > 0);
  await page.locator('#search').fill('no-such-vegetation-427141');
  assert.ok(await page.locator('#empty').isVisible());
  receipts.push('Search and empty state work');
  await page.locator('#search').fill('');
  await page.locator('#more').click();
  assert.ok(await page.locator('#rows tr').count() > 60);
  receipts.push('Pagination adds the next results');
  await page.evaluate(() => {
    workshop[0].title = '<img src="missing" onerror="globalThis.vegetationInjected=true">';
    render();
  });
  assert.equal(await page.locator('#rows img').count(), 0);
  assert.equal(await page.evaluate(() => globalThis.vegetationInjected), undefined);
  receipts.push('Author-provided HTML-like titles stay text');
  await page.goto('about:blank');
  await page.goto(url);
  await page.evaluate(() => window.scrollTo(0, 0));
  assert.equal(await page.evaluate(() => scrollY), 0);
  await page.screenshot({ path: `${out}/shelf-desktop.png` });
  if (await page.locator('.specimen').count()) {
    assert.equal(await page.locator('.specimen').count(), 20);
    await page.locator('#sheet img').evaluateAll(async images => {
      images.forEach(image => { image.loading = 'eager'; });
      for (const image of images) await image.decode();
    });
    await page.locator('#specimens').screenshot({ path: `${out}/native-contact-sheet.png` });
    receipts.push('Native contact sheet captured');
  }
  await page.setViewportSize({ width: 390, height: 844 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  await page.locator('#source').selectOption('base');
  assert.ok(await page.locator('#rows tr').count() > 0);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `${out}/shelf-mobile.png` });
  receipts.push('Mobile layout and source filter work');
  assert.deepEqual(errors, []);
  writeFileSync(`${out}/browser-checks.json`, JSON.stringify({ passed: receipts, pageErrors: errors }, null, 2));
  console.log(JSON.stringify({ passed: receipts.length, checks: receipts }));
} finally {
  await browser.close();
}

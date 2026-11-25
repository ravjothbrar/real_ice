// Screenshot + perf check. Usage: node dev/screenshots.cjs [baseUrl] [suffix]
//   baseUrl default http://localhost:5173/?fixture=1 ; suffix default "fixture"
// Needs Playwright with Chromium (global install is fine: NODE_PATH=$(npm root -g)).
const { chromium } = require('playwright');
const path = require('path');

const base = process.argv[2] || 'http://localhost:5173/?fixture=1';
const suffix = process.argv[3] || 'fixture';
const out = path.join(__dirname, '..', 'screenshots');

async function ready(page) {
  await page.waitForFunction(() => window.__atlasReady != null, null, { timeout: 20000 });
  await page.waitForTimeout(400);
}

(async () => {
  const browser = await chromium.launch();
  for (const width of [1440, 390]) {
    const ctx = await browser.newContext({ viewport: { width, height: width > 900 ? 900 : 844 }, deviceScaleFactor: 1, reducedMotion: 'no-preference' });
    const page = await ctx.newPage();
    page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log(`[${width}] console.${m.type()}: ${m.text()}`); });
    page.on('pageerror', (e) => console.log(`[${width}] pageerror: ${e.message}`));
    await page.goto(base, { waitUntil: 'load' });
    await ready(page);
    const ms = await page.evaluate(() => [window.__atlasRender, window.__atlasReady]);
    console.log(`[${width}] data load + first render: ${ms[0]} ms (boot finished at ${ms[1]} ms)`);
    // Chromium's fullPage capture drops the canvas/absolutely-positioned map layer, so grow the
    // viewport to the document height instead.
    const tall = async () => {
      const hgt = await page.evaluate(() => document.documentElement.scrollHeight);
      await page.setViewportSize({ width, height: hgt });
      await page.waitForTimeout(400);
    };
    await tall();
    await page.screenshot({ path: `${out}/page-${width}-${suffix}.png` });

    const inst = page.locator('#instrument');
    await inst.scrollIntoViewIfNeeded();
    // SURVIVAL GAP on, winter 2024
    await page.click('.lrow[data-layer="band"]');
    await page.click('.wbtn[data-w="2024"]');
    await page.waitForTimeout(300);
    await inst.screenshot({ path: `${out}/instrument-band-${width}-${suffix}.png` });
    // cell card: Cambridge Bay marker
    await page.locator('[data-marker="cambridge-bay"]').dispatchEvent('click');
    await page.waitForTimeout(300);
    if (width > 900) await inst.screenshot({ path: `${out}/instrument-cell-${width}-${suffix}.png` });
    else await page.locator('.p-cell').screenshot({ path: `${out}/cell-card-${width}-${suffix}.png` });
    if (width > 900) { await page.click('.rt[data-tab="scale"]'); await page.waitForTimeout(150); }
    await page.locator('.p-scale').screenshot({ path: `${out}/scale-${width}-${suffix}.png` });
    await page.click('.btn-guide');
    await page.waitForTimeout(200);
    await inst.screenshot({ path: `${out}/guide-${width}-${suffix}.png` });
    await page.click('.gm-close');
    await page.click('.mode');
    await tall();
    await page.waitForTimeout(200);
    await inst.screenshot({ path: `${out}/table-${width}-${suffix}.png` });
    await ctx.close();
  }
  await browser.close();
})();

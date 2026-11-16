// Render the social banners (docs/brand/social/banners.html) to PNG files beside their source,
// one per <section>, at the section's exact pixel size.
//
//   node scripts/brand_banners.js
//
// Needs Playwright with Chromium (the same as scripts/site_browser_check.js).
const { chromium } = require('playwright');
const path = require('path');
const { pathToFileURL } = require('url');

const DIR = path.join(__dirname, '..', 'docs', 'brand', 'social');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1700, height: 2000 }, deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(path.join(DIR, 'banners.html')).href);
  await page.evaluate(() => document.fonts.ready);
  for (const font of ['400 20px Newsreader', '400 20px "IBM Plex Mono"']) {
    if (!(await page.evaluate(f => document.fonts.check(f), font))) throw new Error(`font not loaded: ${font}`);
  }
  for (const section of await page.locator('section.b').all()) {
    const id = await section.getAttribute('id');
    const box = await section.boundingBox();
    const file = path.join(DIR, `tracefix-${id}-${box.width}x${box.height}.png`);
    await section.screenshot({ path: file });
    console.log(`wrote ${path.relative(process.cwd(), file)}`);
  }
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });

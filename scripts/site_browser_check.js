// The website's browser checks (website plan S8). Not part of CI: it needs a browser, Node and axe-core.
// Run from the repo root, with the site served on port 8000 and axe-core 4.10.2 installed anywhere:
//   python3 -m http.server 8000 --bind 127.0.0.1 --directory docs/landing &
//   (cd SOMEWHERE && npm i axe-core@4.10.2)
//   AXE_JS=SOMEWHERE/node_modules/axe-core/axe.min.js node scripts/site_browser_check.js [axe|cases|s10|all] [page regex]
// axe:   axe-core on every page x desktop, iPhone 13, 320px x dark, light, System on a light and on a dark
//        device (reduced motion, reveals shown); sideways page scroll; console errors and failed requests.
// cases: the council's cases (docs/landing-notes/council-verdict-site-2026-11-06.md): Tab stops per page; focus hidden under the
//        header at 200% zoom; site.js blocked or slow and no JavaScript (no text left invisible); the receipt
//        page's hairline and arrow keys; pressed states in forced colours; print; nothing past the screen edge
//        at 320px. Print PDFs and a forced-colours screenshot go to SHOT (default: a new temp dir).
// s10:   the parts added in round S10 (also run by cases and all): the field to try a value, the command
//        palette, the section bar, the linkable tabs, the receipt-on-a-pull-request tabs, the marks'
//        tooltip, Method's fixture picker on the ladder, and all of them without JavaScript and on a phone.
// Prints FAIL lines and a count; exit code 1 when anything failed.
const { chromium, devices } = require('playwright');
const fs = require('fs'), os = require('os'), path = require('path');

const ROOT = path.join(__dirname, '..', 'docs', 'landing'), BASE = 'http://127.0.0.1:8000/';
const SHOT = process.env.SHOT || fs.mkdtempSync(path.join(os.tmpdir(), 'site-check-'));
const MODE = process.argv[2] || 'all', only = process.argv[3] ? new RegExp(process.argv[3]) : null;
const recs = fs.readdirSync(path.join(ROOT, 'receipts'), { withFileTypes: true })
  .filter(d => d.isDirectory()).map(d => 'receipts/' + d.name + '/');
// 404.html: its links start at "/", which is this server's root, so it loads here as on a host.
const ALL = ['', 'benchmark/', 'receipts/', 'method/', 'talk/', '404.html'].concat(recs).filter(p => !only || only.test(p));
const SAMPLE = ['', 'benchmark/', 'receipts/', 'method/', 'talk/', recs[0], 'receipts/partial_fix/']
  .filter(p => !only || only.test(p));

let fails = 0;
const ok = (cond, msg) => { if (!cond) { fails++; console.log('FAIL', msg); } };
const showAll = pg => pg.evaluate(() => document.querySelectorAll('[data-reveal],[data-words],[data-reveal-group],.hero')
  .forEach(e => e.classList.add('is-in')));

// Text blocks in <main> left at opacity 0 (a reveal that never ran).
function hiddenText(pg) {
  return pg.evaluate(() => {
    let n = 0; const ex = [];
    document.querySelectorAll('main p, main h1, main h2, main h3, main li, main td').forEach(el => {
      if (!el.textContent.trim() || el.closest('[hidden],noscript,details:not([open])')) return;
      let o = 1;
      for (let e = el; e && e !== document; e = e.parentElement) {
        const s = getComputedStyle(e); o *= +s.opacity; if (s.display === 'none') { o = -1; break; }
      }
      if (o === 0) { n++; if (ex.length < 3) ex.push(el.textContent.trim().slice(0, 40)); }
    });
    return { n, ex };
  });
}

async function axeMatrix(b) {
  const AXE = fs.readFileSync(process.env.AXE_JS, 'utf8');
  const sizes = { desktop: { viewport: { width: 1440, height: 900 } }, phone: devices['iPhone 13'], w320: { viewport: { width: 320, height: 640 } } };
  const themes = [['dark', 'dark'], ['light', 'dark'], ['system', 'light'], ['system', 'dark']];
  let runs = 0;
  for (const [sz, opts] of Object.entries(sizes)) for (const [theme, scheme] of themes) {
    const ctx = await b.newContext({ ...opts, colorScheme: scheme, reducedMotion: 'reduce' });
    await ctx.addInitScript(t => { try { if (t !== 'dark') localStorage.setItem('tracefix-theme', t); } catch (e) {} }, theme);
    for (const p of ALL) {
      const pg = await ctx.newPage(); const errs = [];
      pg.on('pageerror', e => errs.push('pageerror ' + e.message));
      pg.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') errs.push(m.type() + ' ' + m.text()); });
      pg.on('requestfailed', r => errs.push('failed ' + r.url()));
      await pg.goto(BASE + p, { waitUntil: 'networkidle' });
      await showAll(pg); await pg.waitForTimeout(150);
      await pg.addScriptTag({ content: AXE });
      const v = await pg.evaluate(async () => (await axe.run(document, { resultTypes: ['violations'] })).violations
        .map(x => x.id + ': ' + x.nodes.map(n => n.target.join(' ')).slice(0, 4).join(' | ')));
      const sw = await pg.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      runs++;
      ok(!v.length && sw <= 0 && !errs.length, `axe ${sz} ${theme}/${scheme} /${p}: ${v.join('; ')} ${sw > 0 ? 'sideways ' + sw : ''} ${errs.join('; ')}`);
      await pg.close();
    }
    await ctx.close();
  }
  console.log(`axe: ${runs} runs`);
}

async function tabStops(b) {
  for (const [label, vp] of [['desktop', { width: 1440, height: 900 }], ['zoom200', { width: 720, height: 450 }]]) {
    const ctx = await b.newContext({ viewport: vp, reducedMotion: 'reduce' });
    for (const p of SAMPLE) {
      const pg = await ctx.newPage(); await pg.goto(BASE + p, { waitUntil: 'networkidle' }); await showAll(pg);
      await pg.evaluate(() => { if (document.activeElement) document.activeElement.blur(); window.scrollTo(0, 0); });
      const seen = [], under = [];
      for (const dir of ['Tab', 'Shift+Tab']) for (let i = 0; i < 400; i++) {
        await pg.keyboard.press(dir);
        const r = await pg.evaluate(() => {
          const a = document.activeElement; if (!a || a === document.body) return null;
          const h = document.getElementById('head'), hb = h ? h.getBoundingClientRect().bottom : 0, rc = a.getBoundingClientRect();
          const id = a.tagName + '#' + (a.id || '') + '.' + (a.className || '') + ':' + (a.textContent || '').trim().slice(0, 25);
          // Before the header in the page (skip link, preview note), in it, or taller than the space below it: not judged.
          const exempt = h && (h.contains(a) || (a.compareDocumentPosition(h) & Node.DOCUMENT_POSITION_FOLLOWING))
            || rc.height > innerHeight - (h ? h.offsetHeight : 0);
          return { key: a.outerHTML.slice(0, 120) + rc.left + ',' + (rc.top + scrollY),
            bad: !exempt && rc.height > 0 && (rc.top < hb - 2 || rc.top > innerHeight - 4) ? `${id} top ${Math.round(rc.top)} header ${Math.round(hb)}` : null };
        });
        if (!r) break;
        if (dir === 'Tab') { if (seen.includes(r.key)) break; seen.push(r.key); } else if (r.key === seen[0]) break;
        if (r.bad) under.push(dir + ' ' + r.bad);
      }
      if (label === 'desktop') console.log(`tab stops /${p}: ${seen.length}`);
      else ok(!under.length, `200% zoom /${p}: ${under.length} focused under the header or off screen: ${under.slice(0, 4).join(' || ')}`);
      await pg.close();
    }
    await ctx.close();
  }
}

async function scriptFailures(b) {
  for (const mode of ['blocked', 'slow', 'nojs']) {
    const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, javaScriptEnabled: mode !== 'nojs' });
    if (mode === 'blocked') await ctx.route('**/site.js', r => r.abort());
    if (mode === 'slow') await ctx.route('**/site.js', async r => { await new Promise(s => setTimeout(s, 6000)); r.continue(); });
    for (const p of SAMPLE) {
      const pg = await ctx.newPage(); await pg.goto(BASE + p, { waitUntil: 'domcontentloaded' }); await pg.waitForTimeout(3200);
      const h = await hiddenText(pg); ok(h.n === 0, `site.js ${mode} /${p}: ${h.n} text blocks invisible ${JSON.stringify(h.ex)}`);
      await pg.close();
    }
    await ctx.close();
  }
}

async function receiptKeys(b) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } }); const pg = await ctx.newPage();
  const u = BASE + 'receipts/partial_fix/'; await pg.goto(u, { waitUntil: 'networkidle' });
  await pg.mouse.wheel(0, 900); await pg.waitForTimeout(400);
  ok(await pg.evaluate(() => document.getElementById('head').classList.contains('scrolled')), 'receipt page: the header hairline shows after a scroll');
  await pg.locator('main button').first().focus(); await pg.keyboard.press('ArrowRight'); await pg.waitForTimeout(500);
  ok(pg.url() === u, 'receipt page: an arrow key with a focused button stays on the page');
  await pg.evaluate(() => document.activeElement.blur()); await pg.mouse.click(5, 300); // focuses <main>
  await pg.keyboard.press('ArrowRight'); await pg.waitForLoadState('domcontentloaded'); await pg.waitForTimeout(800);
  ok(pg.url() !== u, 'receipt page: after a click on the page, the right arrow goes to the next receipt');
  await ctx.close();
}

async function forcedColors(b) {
  for (const scheme of ['light', 'dark']) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, forcedColors: 'active', colorScheme: scheme, reducedMotion: 'reduce' });
  for (const p of SAMPLE) {
    const pg = await ctx.newPage(); await pg.goto(BASE + p, { waitUntil: 'networkidle' }); await showAll(pg); await pg.waitForTimeout(200);
    const pairs = await pg.evaluate(() => {
      const out = [];
      document.querySelectorAll('[aria-pressed="true"],[aria-selected="true"]').forEach((on, i) => {
        const attr = on.hasAttribute('aria-pressed') ? 'aria-pressed' : 'aria-selected';
        const off = Array.from(on.parentElement.children).find(x => x.getAttribute(attr) === 'false');
        if (!off || !on.getBoundingClientRect().width) return;
        on.dataset.fcOn = i; off.dataset.fcOff = i; out.push(i + ' ' + (on.className || on.tagName));
      });
      return out;
    });
    // Pressed means the system Highlight fill and its unpressed neighbour without it (a darker author
    // fill can differ in the computed style and still be invisible on a dark High Contrast theme).
    const highlight = await pg.evaluate(() => { const d = document.createElement('i'); d.style.cssText = 'forced-color-adjust:none;background:Highlight'; document.body.append(d); const c = getComputedStyle(d).backgroundColor; d.remove(); return c; });
    for (const pair of pairs) {
      const i = pair.split(' ')[0];
      const a = await pg.locator(`[data-fc-on="${i}"]`).evaluate(e => getComputedStyle(e).backgroundColor);
      const c = await pg.locator(`[data-fc-off="${i}"]`).evaluate(e => getComputedStyle(e).backgroundColor);
      ok(a === highlight && c !== highlight, `forced colours ${scheme} /${p}: pressed ${pair} has ${a}, its neighbour ${c}, Highlight is ${highlight}`);
    }
    if (p === '') await pg.screenshot({ path: path.join(SHOT, `forced-colours-${scheme}-home.png`) });
    await pg.close();
  }
  await ctx.close();
  }
}

async function print(b) {
  const ctx = await b.newContext({ viewport: { width: 900, height: 1200 } });
  for (const p of SAMPLE) {
    const pg = await ctx.newPage(); await pg.goto(BASE + p, { waitUntil: 'networkidle' });
    await pg.emulateMedia({ media: 'print' }); await pg.waitForTimeout(300);
    const r = await pg.evaluate(() => {
      const vis = s => { const e = document.querySelector(s); return !!e && getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().height > 0; };
      return { nav: vis('#head .nav'), theme: vis('.foot .theme'), bg: getComputedStyle(document.body).backgroundColor };
    });
    const h = await hiddenText(pg);
    ok(!r.nav && !r.theme && /255, 255, 255/.test(r.bg) && h.n === 0, `print /${p}: ${JSON.stringify(r)}, ${h.n} text blocks invisible`);
    if (p === '' || p === 'receipts/partial_fix/') await pg.pdf({ path: path.join(SHOT, 'print-' + (p.replace(/\W/g, '') || 'home') + '.pdf') });
    await pg.close();
  }
  await ctx.close();
}

async function edges(b) {
  for (const w of [320, 360]) {
    const pg = await (await b.newContext({ viewport: { width: w, height: 640 } })).newPage();
    for (const p of SAMPLE) {
      await pg.goto(BASE + p, { waitUntil: 'networkidle' });
      const out = await pg.evaluate(() => {
        const cw = document.documentElement.clientWidth, bad = [];
        document.querySelectorAll('main *').forEach(e => {
          const rc = e.getBoundingClientRect();
          if (!rc.width || (rc.right <= cw + 0.5 && rc.left >= -0.5) || e.closest('.sr-only')) return;
          for (let a = e.parentElement; a && a !== document.body; a = a.parentElement) {
            if (/auto|scroll|hidden|clip/.test(getComputedStyle(a).overflowX)) return; // inside a scroller: fine
          }
          bad.push(e.tagName + '.' + e.className + ' ' + Math.round(rc.left) + '-' + Math.round(rc.right));
        });
        return bad.slice(0, 6);
      });
      ok(!out.length, `${w}px /${p}: past the screen edge: ${out.join(' | ')}`);
    }
  }
}

// Method's ladder: scrolled to, it plays the home replay's receipt on its own (on a phone too, where the
// ladder is taller than the screen); a picked fixture climbs with its receipt's reasons and links to it.
async function climbs(pg, where) {
  await pg.evaluate(() => { const l = document.querySelector('[data-climb-ladder]'); window.scrollTo(0, l.getBoundingClientRect().top + scrollY - innerHeight * 0.3); });
  await pg.waitForTimeout(3500);
  ok((await pg.locator('[data-climb-status]').innerText()).startsWith('partial_fix: COUNTEREXAMPLE'), `climb ${where}: plays the replay's receipt when the ladder comes on screen`);
  await pg.locator('.climb-pick[data-case="good_fix"]').click(); await pg.waitForTimeout(4500);
  ok((await pg.locator('[data-climb-status]').innerText()) === 'good_fix climbs to L4: nothing broke it.'
    && await pg.locator('[data-rung="L4"].top').count() === 1 && await pg.locator('.why-yes').count() === 4, `climb ${where}: a picked fixture climbs with its reasons`);
  ok((await pg.locator('.climb-open').getAttribute('href')) === '../receipts/good_fix/', `climb ${where}: links to the receipt`);
}

async function s10(b) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } }); const pg = await ctx.newPage();
  const errs = []; pg.on('pageerror', e => errs.push(e.message)); pg.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await pg.goto(BASE, { waitUntil: 'networkidle' });
  // The field: the same function and contract as the replay, three kinds of answer.
  await pg.locator('#try-in').scrollIntoViewIfNeeded();
  const read = async () => (await pg.locator('#read-call').innerText()) + ' | ' + (await pg.locator('#read-result').innerText());
  const tries = [['8080', 'returns 8080, as documented'], [' 80 ', 'returns 80, as documented'], ['0', 'raises ConfigError'],
    ['70000', 'raises ConfigError'], ['abc', 'no promise'], ['8_080', 'returns 8080'], ['_80', 'no promise'], ['+80', 'returns 80'],
    ["a'b", `raw="a'b"`], ['\u00e9', 'plain ASCII']];
  for (const [value, want] of tries) { await pg.fill('#try-in', value); const got = await read(); ok(got.includes(want), `try ${JSON.stringify(value)}: ${got}`); }
  await pg.fill('#try-in', '8'); await pg.fill('#try-in', '');
  let got = await read();
  ok(got.includes("parse_port(raw='')") && got.includes('The docstring says 8080') && got.includes('You broke it'), `try: a cleared field is a finding: ${got}`);
  ok(await pg.locator('.try-row.broke').count() === 1 && await pg.locator('#doc-line.broken').count() === 1
    && await pg.locator('#try-mark .mark-fail').count() === 1, 'try: a finding marks the field, the docstring line and the mark');
  await pg.getByRole('button', { name: 'Try PORT unset' }).click();
  got = await read(); ok(got.includes('parse_port(raw=None)') && got.includes('returns 8080, as documented'), `try: unset: ${got}`);
  await pg.getByRole('button', { name: "Try PORT=' '" }).click(); await pg.waitForTimeout(800);
  ok((await pg.locator('#try-out').textContent()).includes('You broke it'), 'try: the result is announced once');
  await pg.locator('#try-in').press('Enter'); ok(pg.url() === BASE, 'try: Enter stays on the page');

  // The palette: keys, search, a section, a theme, a receipt, an inner page's own sections.
  const open = () => pg.locator('#palette[open]').count();
  await pg.keyboard.press('Control+k');
  ok(await open() === 1 && await pg.evaluate(() => document.activeElement.id) === 'pal-in', 'palette: Ctrl+K opens it with the caret in the field');
  ok(await pg.locator('#pal-list [role=option]').count() >= 36, 'palette: lists the pages, receipts and sections');
  await pg.keyboard.type('lawyer');
  ok(await pg.locator('#pal-list [role=option]').count() === 1, 'palette: typing filters');
  await pg.keyboard.press('Enter'); await pg.waitForTimeout(300);
  ok(pg.url().endsWith('#lawyer') && await pg.locator('#lawyer[aria-selected=true]').count() === 1 && await open() === 0, 'palette: Enter opens the Lawyer tab and closes');
  await pg.keyboard.press('/'); ok(await open() === 1, 'palette: "/" opens it');
  await pg.keyboard.type('counterexample method');
  ok((await pg.locator('#pal-list [aria-selected=true]').innerText()).includes('method_partial'), 'palette: every word must match');
  await pg.fill('#pal-in', 'zzzz'); ok(await pg.locator('#pal-none').isVisible(), 'palette: says when nothing matches');
  await pg.fill('#pal-in', 'light'); await pg.keyboard.press('Enter');
  ok(await pg.evaluate(() => document.documentElement.getAttribute('data-theme')) === 'light' && await open() === 1, 'palette: a theme entry switches the theme and stays open');
  await pg.fill('#pal-in', 'dark'); await pg.keyboard.press('Enter'); await pg.keyboard.press('Escape');
  ok(await open() === 0, 'palette: Escape closes it');
  await pg.keyboard.press('Control+k'); await pg.keyboard.type('partial_fix'); await pg.keyboard.press('ArrowDown'); await pg.keyboard.press('ArrowUp'); await pg.keyboard.press('Enter');
  await pg.waitForURL('**/receipts/partial_fix/'); await pg.waitForLoadState('networkidle'); await pg.waitForTimeout(300);
  await pg.keyboard.press('Control+k');
  ok(/on this page/i.test(await pg.locator('#pal-list .pal-group').first().innerText()), 'palette: an inner page lists its own sections first');
  await pg.keyboard.type('benchmark'); await pg.keyboard.press('Enter');
  await pg.waitForURL('**/benchmark/'); await pg.waitForLoadState('networkidle'); await pg.waitForTimeout(300);
  await pg.locator('[data-miss-find]').focus(); await pg.keyboard.type('/');
  ok(await open() === 0 && (await pg.locator('[data-miss-find]').inputValue()) === '/', 'palette: "/" typed in a field stays in the field');

  // The section bar on a long page.
  await pg.goto(BASE + 'method/', { waitUntil: 'networkidle' });
  ok(await pg.locator('.subnav.on').count() === 0 && await pg.locator('.subnav[inert]').count() === 1, 'section bar: hidden and inert at the top');
  await pg.keyboard.press('Control+k'); await pg.keyboard.type('ladder');
  ok(await pg.locator('#pal-list [role=option]').count() === 1, 'palette: a section of this page is listed once');
  await pg.keyboard.press('Escape');
  await pg.evaluate(() => document.getElementById('ladder').scrollIntoView({ behavior: 'instant' })); await pg.waitForTimeout(600);
  ok(await pg.locator('.subnav.on').count() === 1 && (await pg.locator('.subnav a[aria-current]').allInnerTexts()).join() === 'The ladder', 'section bar: shown after the list, the ladder marked');
  await pg.locator('.subnav a', { hasText: 'Fork pull requests' }).click(); await pg.waitForTimeout(1200);
  const gap = await pg.evaluate(() => document.getElementById('forks').getBoundingClientRect().top - document.querySelector('.subnav').getBoundingClientRect().bottom);
  ok(gap >= -1 && (await pg.locator('.subnav a[aria-current]').innerText()) === 'Fork pull requests', `section bar: a link lands its section below the bar (${gap}px)`);
  await pg.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' })); await pg.waitForTimeout(600);
  ok(await pg.locator('.subnav.on').count() === 0, 'section bar: hides again at the top');

  // Linkable tabs, the receipt on a pull request, the marks.
  await pg.goto(BASE + '#hard-code', { waitUntil: 'networkidle' });
  ok(await pg.locator('#hard-code[aria-selected=true]').count() === 1 && (await pg.locator('#mv-file').innerText()).includes('calendar'), 'tabs: #hard-code opens that tab');
  await pg.locator('#butterfly').click(); ok(pg.url().endsWith('#butterfly'), 'tabs: a click writes the address');
  await pg.keyboard.press('ArrowDown'); ok(pg.url().endsWith('#hard-code'), 'tabs: an arrow key writes the address too');
  await pg.keyboard.press('Control+k'); await pg.keyboard.type('butterfly'); await pg.keyboard.press('Enter'); await pg.waitForTimeout(300);
  ok(await pg.locator('#butterfly[aria-selected=true]').count() === 1, 'tabs: the palette opens a tab after the keys moved off it');
  await pg.locator('.marks .mk-cx').first().scrollIntoViewIfNeeded(); await pg.locator('.marks .mk-cx').first().hover();
  ok((await pg.locator('.tip').innerText()).includes('own mistake'), 'marks: a mark says what it stands for');

  // The Method page since the home page cut: the receipt on a pull request and the fixture picker.
  await pg.goto(BASE + 'method/#loop', { waitUntil: 'networkidle' });
  ok(await pg.locator('.lp:visible').count() === 1, 'pull request: one panel at a time');
  await pg.locator('#ltab-comment').click(); await pg.keyboard.press('ArrowRight');
  ok(await pg.locator('#lp-json').isVisible() && (await pg.locator('#lp-json pre').innerText()).includes('"level": "COUNTEREXAMPLE"'), 'pull request: arrows move between the tabs');
  await climbs(pg, 'desktop');
  ok(!errs.length, 's10: console errors: ' + errs.join('; '));
  await ctx.close();

  const nojs = await b.newContext({ javaScriptEnabled: false, viewport: { width: 1280, height: 800 } }); const q = await nojs.newPage();
  await q.goto(BASE + 'method/', { waitUntil: 'load' });
  ok(await q.locator('.lp:visible').count() === 3 && !(await q.locator('#ltabs').isVisible()), 'no JS: the three panels show, their tabs do not');
  ok(!(await q.locator('.climb').isVisible()) && await q.locator('.mt-ladder li').first().isVisible(), 'no JS: the fixture picker stays hidden, the ladder shows');
  await q.goto(BASE, { waitUntil: 'load' });
  ok(!(await q.locator('#try').isVisible()) && !(await q.locator('[data-palette-open]').isVisible()), 'no JS: the field and the palette button stay hidden');
  ok(await q.locator('.marks .mk').first().isVisible(), 'no JS: the marks show');
  await nojs.close();

  const phone = await b.newContext({ ...devices['iPhone 13'] }); const m = await phone.newPage();
  await m.goto(BASE, { waitUntil: 'networkidle' });
  await m.locator('[data-palette-open]').tap();
  const box = await m.locator('#palette').boundingBox();
  ok(box && box.x >= 0 && box.x + box.width <= 390, 'phone: the palette fits the screen');
  await m.goto(BASE + 'method/', { waitUntil: 'networkidle' });
  await climbs(m, 'phone');
  await phone.close();
}

(async () => {
  const b = await chromium.launch();
  if (MODE === 'axe' || MODE === 'all') await axeMatrix(b);
  if (MODE === 'cases' || MODE === 'all') {
    await tabStops(b); await scriptFailures(b); await receiptKeys(b); await forcedColors(b); await print(b); await edges(b);
    await s10(b);
    console.log('print PDFs and the forced-colours screenshot: ' + SHOT);
  }
  if (MODE === 's10') await s10(b);
  await b.close();
  console.log('failures:', fails);
  process.exit(fails ? 1 : 0);
})();

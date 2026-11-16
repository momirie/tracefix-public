// The home page only: the hero's entrance, the scroll-lit paragraph, the input field behind the
// hero, the partial_fix replay and the field to try a value of your own, the tabs and Copy.
// Loaded after site.js.
(function () {
  'use strict';

  function $(id) { return document.getElementById(id); }
  var REDUCED = false;
  try { REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}

  // The hero is on screen at load: start it on the next frame so its transition runs.
  requestAnimationFrame(function () { requestAnimationFrame(function () { $('top').classList.add('is-in'); }); });

  // ---- Scroll-lit paragraph -------------------------------------------------------------------
  Array.prototype.forEach.call(document.querySelectorAll('[data-scrub]'), function (el) {
    if (REDUCED) return;
    var words = el.textContent.split(/\s+/).filter(Boolean);
    el.textContent = '';
    var spans = words.map(function (w, i) {
      var s = document.createElement('span');
      s.className = 'sw';
      s.textContent = w;
      el.appendChild(s);
      if (i < words.length - 1) el.appendChild(document.createTextNode(' '));
      return s;
    });
    el.classList.add('scrub');
    var queued = false;
    function paint() {
      queued = false;
      var r = el.getBoundingClientRect(), vh = window.innerHeight;
      // 0 when the paragraph's top reaches 90% of the screen, 1 when its bottom reaches 55%.
      var p = (vh * 0.9 - r.top) / (vh * 0.9 - vh * 0.55 + r.height);
      p = Math.max(0, Math.min(1, p));
      var lit = Math.round(p * spans.length);
      for (var i = 0; i < spans.length; i++) spans[i].classList.toggle('lit', i < lit);
    }
    window.addEventListener('scroll', function () { if (!queued) { queued = true; requestAnimationFrame(paint); } }, { passive: true });
    window.addEventListener('resize', paint);
    paint();
  });

  // ---- The input field behind the hero --------------------------------------------------------
  // A grid of inputs. A scan sweeps across and lights the ones it tries; once a sweep, one input
  // turns into a red square (a counterexample), holds, and fades back. The cursor probes nearby
  // inputs on devices with a fine pointer. It runs only while the hero is on screen.
  (function field() {
    var canvas = $('field');
    var ctx = canvas && canvas.getContext && canvas.getContext('2d');
    if (!ctx) return;
    var GAP = 26, R = 1.2, BAND = 110, SWEEP = 6400, REST = 1800, HOLD = 2800, POP = 420;
    var W = 0, H = 0, dots = [], cycle = -1, visible = true, raf = 0, px = -1e4, py = -1e4;
    var t0 = performance.now(), paused = false, ink = '#000', red = '#cf222e';
    function readColors() {
      var cs = getComputedStyle(document.documentElement);
      ink = cs.getPropertyValue('--ink').trim() || '#000'; red = cs.getPropertyValue('--red').trim() || '#cf222e';
    }
    readColors();

    function build() {
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = canvas.clientWidth; H = canvas.clientHeight;
      canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      var cols = Math.max(1, Math.floor(W / GAP)), rows = Math.max(1, Math.floor(H / GAP));
      var ox = (W - (cols - 1) * GAP) / 2, oy = (H - (rows - 1) * GAP) / 2;
      dots = [];
      for (var r = 0; r < rows; r++) for (var c = 0; c < cols; c++) {
        dots.push({ x: ox + c * GAP, y: oy + r * GAP, heat: 0, red: 0, hit: 0, until: 0, bug: false });
      }
    }
    // Counterexamples land where the field is visible: away from the headline in the middle.
    function outer(d) {
      // Phones show the field only around the headline (CSS mask): use the outer columns, clear of its letters.
      if (W < 640) return (d.x < 32 || d.x > W - 32) && d.y > H * 0.1 && d.y < H * 0.3;
      var nx = (d.x - W / 2) / (W * 0.4), ny = (d.y - H * 0.7) / (H * 0.36);
      var edge = d.x > GAP * 2 && d.x < W - GAP * 2 && d.y > H * 0.16 && d.y < H * 0.8;
      var headline = Math.abs(d.x - W / 2) < W * 0.4 && d.y < H * 0.55; // not under the headline's letters
      return edge && !headline && nx * nx + ny * ny > 1;
    }
    function pickBugs() {
      var pool = dots.filter(outer);
      var n = W < 640 ? 1 : 2;
      for (var k = 0; k < n && pool.length; k++) pool.splice(Math.floor(Math.random() * pool.length), 1)[0].bug = true;
    }
    function draw(now) {
      ctx.clearRect(0, 0, W, H);
      var period = SWEEP + REST, el = (now - t0) % period, c = Math.floor((now - t0) / period);
      if (c !== cycle) { cycle = c; pickBugs(); }
      var sx = el < SWEEP ? -BAND + (W + 2 * BAND) * (el / SWEEP) : -1e5;
      ctx.fillStyle = ink;
      for (var i = 0; i < dots.length; i++) {
        var d = dots[i], dx = Math.abs(d.x - sx), target = dx < BAND ? Math.exp(-4 * (dx / BAND) * (dx / BAND)) : 0;
        var pd = Math.hypot(d.x - px, d.y - py);
        if (pd < 120) target = Math.max(target, (1 - pd / 120) * 0.9);
        d.heat += (target - d.heat) * 0.14;
        if (d.bug && dx < GAP / 2) { d.bug = false; d.red = 1; d.hit = now; d.until = now + HOLD; }
        if (d.red > 0 && now > d.until) d.red = Math.max(0, d.red - 0.025);
        if (d.red > 0.02) continue;
        ctx.globalAlpha = 0.1 + d.heat * 0.42;
        ctx.beginPath();
        ctx.arc(d.x, d.y, R + d.heat * 1.2, 0, 6.2832);
        ctx.fill();
      }
      ctx.fillStyle = red;
      for (var j = 0; j < dots.length; j++) {
        var b = dots[j];
        if (b.red <= 0.02) continue;
        // Pops in like the replay's red squares (overshoot, then settle), then shrinks as it fades.
        var k = Math.min(1, (now - b.hit) / POP), back = 1 + 2.7 * Math.pow(k - 1, 3) + 1.7 * Math.pow(k - 1, 2);
        var s = 4.5 * back * (0.6 + 0.4 * b.red);
        ctx.globalAlpha = b.red;
        ctx.fillRect(b.x - s, b.y - s, 2 * s, 2 * s);
      }
      ctx.globalAlpha = 1;
    }
    // 30 frames a second is plenty for a slow scan, at half the work of 60.
    var last = 0;
    function loop(now) {
      if (now - last >= 32) { last = now; draw(now); }
      raf = visible && !paused ? requestAnimationFrame(loop) : 0;
    }
    function start() { if (!raf && !REDUCED && !paused && !document.hidden && visible) raf = requestAnimationFrame(loop); }
    function still() {
      // Reduced motion: one quiet frame, the logo's idea: every input passes but one.
      draw(t0 + SWEEP + 1);
      var pool = dots.filter(outer);
      if (pool.length) {
        var d = pool[Math.floor(pool.length * 0.15)];
        ctx.fillStyle = red; ctx.globalAlpha = 1; ctx.fillRect(d.x - 4.5, d.y - 4.5, 9, 9);
      }
    }

    build();
    if (window.ResizeObserver) new ResizeObserver(function () { build(); if (REDUCED) still(); }).observe(canvas);
    document.addEventListener('tracefix:theme', function () { readColors(); if (REDUCED || paused) still(); });
    if (REDUCED) { still(); return; }
    // Anything that moves on its own for more than 5 seconds gets a Pause (WCAG 2.2.2).
    var toggle = $('field-toggle'), PAUSE_ICON = toggle.querySelector('svg').innerHTML;
    var PLAY_ICON = '<path d="M3 1.5v9l7.5-4.5z"/>';
    toggle.hidden = false;
    toggle.addEventListener('click', function () {
      paused = !paused;
      toggle.querySelector('span').textContent = paused ? 'Play background' : 'Pause background';
      toggle.querySelector('svg').innerHTML = paused ? PLAY_ICON : PAUSE_ICON;
      if (paused) { cancelAnimationFrame(raf); raf = 0; still(); } else start();
    });
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (es) { visible = es[0].isIntersecting; if (visible) start(); }).observe(canvas);
    }
    document.addEventListener('visibilitychange', function () { if (!document.hidden) start(); else { cancelAnimationFrame(raf); raf = 0; } });
    if (window.matchMedia && window.matchMedia('(pointer: fine)').matches) {
      var hero = $('top');
      hero.addEventListener('pointermove', function (e) { var r = canvas.getBoundingClientRect(); px = e.clientX - r.left; py = e.clientY - r.top; });
      hero.addEventListener('pointerleave', function () { px = py = -1e4; });
    }
    start();
  })();


  // ---- Replay: the real partial_fix logic, ported -------------------------------------------
  // Inputs and code come from the real partial_fix fixture (tests/fixtures/partial_fix).
  var INPUTS = [null,'8080','80','443',' 8080','3000','22','5432','0080','+80','1','65535','8443','','6379','27017',
    '9000','8080 ','1024','25','0','53','65536','3306',' 443 ','587',' ','8000','9200','49152','\t','11211',
    '110','-1','993','5000','8888','70000','\n','143','4000','995','9090','2048','100','127','10','999'];
  var STEP_MS = 55;
  var FIRST_BREAK = 13; // INPUTS[13] is '': the readout shows it when the replay ends

  function pyRepr(v) {
    if (v === null) return 'None';
    var body = v.replace(/\\/g, '\\\\').replace(/\t/g, '\\t').replace(/\n/g, '\\n');
    // As Python's repr: double quotes when the text has a single quote and no double one.
    if (v.indexOf("'") !== -1 && v.indexOf('"') === -1) return '"' + body + '"';
    return "'" + body.replace(/'/g, "\\'") + "'";
  }
  function pyInt(s) {
    // int() as Python reads plain ASCII text: an optional sign, digits, single underscores between digits.
    if (!/^[+-]?\d+(?:_\d+)*$/.test(s)) return { err: 'ValueError', msg: 'invalid literal for int() with base 10: ' + pyRepr(s) };
    return { val: parseInt(s.replace(/_/g, ''), 10) };
  }
  function inRange(n) { return n >= 1 && n <= 65535; }
  // The fixed code, exactly as in head: None -> 8080, else int(raw.strip()), then the range check.
  function fixedCode(raw) {
    if (raw === null) return { val: 8080 };
    var r = pyInt(raw.trim());
    if (r.err) return r;
    if (!inRange(r.val)) return { err: 'ConfigError', msg: 'PORT must be between 1 and 65535, got ' + r.val };
    return r;
  }
  // The documented contract: unset or blank -> 8080; whitespace ignored; ConfigError outside 1..65535.
  function contract(raw) {
    if (raw === null || raw.trim() === '') return { val: 8080 };
    return fixedCode(raw);
  }
  function show(o) { return o.err ? 'raises ' + o.err : 'returns ' + o.val; }

  var RESULTS = INPUTS.map(function (raw) {
    var got = fixedCode(raw), want = contract(raw);
    return { call: 'parse_port(raw=' + pyRepr(raw) + ')', got: got, want: want, ok: show(got) === show(want) };
  });

  var replay = { tried: 0, running: false, peek: -1, timer: null, own: null };
  var grid = $('grid'), runBtn = $('run'), tally = $('tally'), tallySay = $('tally-say'), doneBlock = $('done'), docLine = $('doc-line');
  var read = $('read'), readCall = $('read-call'), readResult = $('read-result');
  var cells = RESULTS.map(function (r, i) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'cell';
    b.tabIndex = i === 0 ? 0 : -1; // one Tab stop for the whole grid; arrows move inside it
    var mark = document.createElement('span');
    b.appendChild(mark);
    function peek() { replay.peek = i; replay.own = null; tryOut.textContent = ''; paintOwn(); paintRead(); paintCells(); }
    b.addEventListener('mouseenter', peek);
    b.addEventListener('focus', function () {
      cells.forEach(function (c, j) { c.button.tabIndex = j === i ? 0 : -1; });
      peek();
    });
    b.addEventListener('click', peek);
    grid.appendChild(b);
    return { button: b, mark: mark, shown: '' };
  });

  // The ARIA grid keys: arrows move one input (up and down a row), Home and End jump to the ends.
  grid.addEventListener('keydown', function (e) {
    var at = cells.findIndex(function (c) { return c.button === document.activeElement; });
    if (at < 0) return;
    var cols = getComputedStyle(grid).gridTemplateColumns.split(' ').length || 1, to = at;
    if (e.key === 'ArrowRight') to = at + 1;
    else if (e.key === 'ArrowLeft') to = at - 1;
    else if (e.key === 'ArrowDown') to = at + cols;
    else if (e.key === 'ArrowUp') to = at - cols;
    else if (e.key === 'Home') to = 0;
    else if (e.key === 'End') to = cells.length - 1;
    else return;
    e.preventDefault();
    cells[Math.max(0, Math.min(cells.length - 1, to))].button.focus();
  });

  function paintCell(i) {
    var c = cells[i], r = RESULTS[i], tested = i < replay.tried;
    var kind = !tested ? 'pending' : (r.ok ? 'pass' : 'fail');
    if (c.shown !== kind) {
      // A fresh element runs the land/pop animation once, when the input is tried.
      var fresh = document.createElement('span');
      fresh.className = 'mark mark-' + kind + (kind === 'pass' ? ' land' : kind === 'fail' ? ' pop' : '');
      c.button.replaceChild(fresh, c.mark);
      c.mark = fresh;
      c.shown = kind;
    }
    c.mark.classList.toggle('peek', kind === 'pending' && i === replay.peek);
    c.button.setAttribute('aria-label', r.call + (tested
      ? (r.ok ? ', ' + show(r.got) + ' as documented' : ', ' + show(r.got) + ', breaks the docstring')
      : ', not tried yet'));
  }
  function paintCells() { for (var i = 0; i < cells.length; i++) paintCell(i); }

  function paintRead() {
    var p = replay.peek >= 0 ? RESULTS[replay.peek] : null;
    var text, tone = 'var(--mute)', bar = 'var(--line)';
    if (replay.own) {
      // The visitor's own value takes the readout until they point at an input in the grid.
      var o = replay.own;
      readCall.textContent = o.call;
      readResult.textContent = o.text;
      readResult.style.color = o.kind === 'fail' ? 'var(--red-text)' : o.kind === 'pass' ? 'var(--ink)' : 'var(--mute)';
      read.style.borderLeftColor = o.kind === 'fail' ? 'var(--red)' : o.kind === 'pass' ? 'var(--ink)' : 'var(--line-strong)';
      return;
    }
    if (!p) text = replay.tried === 0 ? 'Not tried yet. Each circle is one input.' : '';
    else if (replay.peek >= replay.tried) text = 'Not tried yet.';
    else if (p.ok) { text = '→ ' + show(p.got) + ', as documented'; tone = bar = 'var(--ink)'; }
    else {
      text = '→ ' + show(p.got) + ': ' + p.got.msg + '. The docstring says ' + show(p.want).replace('returns ', '') + '.';
      tone = 'var(--red-text)'; bar = 'var(--red)';
    }
    readCall.textContent = p ? p.call : 'parse_port(raw=None)';
    readResult.textContent = text;
    readResult.style.color = tone;
    read.style.borderLeftColor = bar;
  }

  function paintReplay() {
    var done = replay.tried >= INPUTS.length, broke = 0;
    for (var i = 0; i < replay.tried; i++) if (!RESULTS[i].ok) broke++;
    tally.textContent = replay.tried === 0 ? INPUTS.length + ' inputs ready'
      : 'tried ' + replay.tried + ' of ' + INPUTS.length + ', ' + broke + ' broke it';
    // The tally ticks for every input; a screen reader hears only the start and the result.
    var said = replay.running ? 'Replaying ' + INPUTS.length + ' inputs.'
      : done ? 'Tried ' + INPUTS.length + ' of ' + INPUTS.length + ', ' + broke + ' broke it.' : '';
    if (tallySay.textContent !== said) tallySay.textContent = said;
    runBtn.disabled = replay.running;
    runBtn.textContent = replay.running ? 'Replaying…' : (done ? 'Replay it again' : 'Replay the attack');
    paintDoc();
    doneBlock.hidden = !done;
    paintCells();
    paintRead();
  }

  function finish() {
    if (replay.timer) { clearInterval(replay.timer); replay.timer = null; }
    replay.tried = INPUTS.length; replay.running = false; replay.peek = FIRST_BREAK;
    paintReplay();
  }
  function startReplay() {
    if (replay.timer) clearInterval(replay.timer);
    if (REDUCED) { finish(); return; }
    replay.tried = 0; replay.running = true; replay.peek = -1;
    paintReplay();
    replay.timer = setInterval(function () {
      var t = replay.tried + 1;
      if (t >= INPUTS.length) { finish(); return; }
      replay.tried = t; replay.peek = t - 1;
      paintReplay();
    }, STEP_MS);
  }
  runBtn.addEventListener('click', startReplay);
  paintReplay();

  // ---- Try your own value: the same ported function, judged against the same docstring ---------
  // Three outcomes: as documented; breaks a promise (a finding); or the docstring promises nothing
  // for this text, so nothing counts against the fix. The port models plain ASCII text only.
  var tryForm = $('try'), tryIn = $('try-in'), tryMark = $('try-mark'), tryOut = $('try-out'), tryPicks = $('try-picks');
  var tryRow = tryIn.parentNode, trySay = null, tryKind = '';
  function judge(raw) {
    if (raw !== null && /[^\x20-\x7e\t\n]/.test(raw)) {
      // Outside the port: no call is shown either, since Python would write this text differently.
      return { call: 'parse_port(raw=\u2026)', kind: 'none', text: 'This replay models plain ASCII text only. The real run executes the Python code.' };
    }
    var call = 'parse_port(raw=' + pyRepr(raw) + ')';
    var got = fixedCode(raw), want = contract(raw);
    if (show(got) !== show(want)) {
      return { call: call, kind: 'fail', text: '→ ' + show(got) + ': ' + got.msg + '. The docstring says ' + show(want).replace('returns ', '') + '. You broke it.' };
    }
    if (got.err === 'ValueError') {
      return { call: call, kind: 'none', text: '→ ' + show(got) + ': ' + got.msg + '. The docstring makes no promise about text that is not a number, so this is not a finding.' };
    }
    return { call: call, kind: 'pass', text: '→ ' + show(got) + (got.err ? ': ' + got.msg : '') + ', as documented' };
  }
  function paintOwn() {
    var kind = replay.own ? replay.own.kind : 'pending';
    if (kind !== tryKind) {
      tryKind = kind;
      var fresh = document.createElement('span');
      fresh.className = 'mark mark-' + kind + (kind === 'pass' ? ' land' : kind === 'fail' ? ' pop' : '');
      tryMark.textContent = ''; tryMark.appendChild(fresh);
    }
    tryRow.classList.toggle('broke', kind === 'fail');
    paintDoc();
  }
  // The docstring's promise lights up once it is broken: by the finished replay, or by the visitor.
  function paintDoc() {
    docLine.classList.toggle('broken', replay.tried >= INPUTS.length || !!(replay.own && replay.own.kind === 'fail'));
  }
  function tryValue(raw) {
    replay.own = judge(raw); replay.peek = -1;
    paintOwn(); paintRead(); paintCells();
    // A screen reader hears the result once typing pauses, not at every key.
    clearTimeout(trySay);
    var said = replay.own.call + ' ' + replay.own.text.replace('→ ', '');
    trySay = setTimeout(function () { tryOut.textContent = said; }, 600);
  }
  // Values worth a try: [what parse_port gets, the button's label]. null is PORT unset.
  [[null, 'unset'], ['', "''"], [' ', "' '"], [' 8080 ', "' 8080 '"], ['70000', "'70000'"], ['8_080', "'8_080'"], ['http', "'http'"]].forEach(function (pick) {
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'try-pick'; b.textContent = pick[1];
    b.setAttribute('aria-label', 'Try ' + (pick[0] === null ? 'PORT unset' : 'PORT=' + pick[1]));
    b.addEventListener('click', function () { tryIn.value = pick[0] === null ? '' : pick[0]; tryValue(pick[0]); });
    tryPicks.appendChild(b);
  });
  tryIn.placeholder = '8080';
  tryIn.maxLength = 12;
  tryIn.addEventListener('input', function () { tryValue(tryIn.value); });
  tryForm.addEventListener('submit', function (e) { e.preventDefault(); tryValue(tryIn.value); });
  tryForm.hidden = false;
  paintOwn();

  // Start once, when the demo is mostly on screen. Without IntersectionObserver the button still works.
  if ('IntersectionObserver' in window) {
    var demoIO = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting && replay.tried === 0 && !replay.running) { demoIO.disconnect(); setTimeout(startReplay, 350); }
      });
    }, { threshold: 0.35 });
    demoIO.observe($('attack'));
  }

  // ---- Tabs: site.js's (window.tracefixTabs). If site.js failed to load, the tabs stay on their
  // first panel, which the page already shows; the rest of this file still runs. ----
  var tabs = window.tracefixTabs || function () { var none = function () {}; none.buttons = []; return none; };

  // The tabs' fixtures as their receipts report them: built into the page (scripts/site_home.py).
  var MOVES = JSON.parse($('moves-data').textContent);
  var casePanel = $('case');
  var pickMove = tabs('moves', function (i, button) {
    var m = MOVES[i];
    casePanel.setAttribute('aria-labelledby', button.id);
    $('mv-issue').textContent = '“' + m.issue + '”';
    $('mv-file').textContent = m.file;
    $('mv-finds').textContent = m.finds;
    $('mv-open').href = 'receipts/' + m.case + '/';
    var diff = $('mv-diff');
    diff.textContent = '';
    m.diff.forEach(function (d) {
      var line = document.createElement('div');
      line.className = 'd ' + (d[0] === '+' ? 'd-add' : 'd-del');
      line.textContent = d[0] + ' ' + d[1];
      diff.appendChild(line);
    });
    casePanel.classList.remove('swap');
    void casePanel.offsetWidth; // restart the swap animation
    casePanel.classList.add('swap');
    // Each tab has an address (#butterfly, #hard-code, #lawyer): picking one, by click or by
    // key, writes it to the address bar without adding a history entry.
    try { if (location.hash !== '#' + button.id) history.replaceState(null, '', '#' + button.id); } catch (e) {}
  });
  // A link to a tab's address opens the page on that tab.
  function moveFromHash() {
    var i = pickMove.buttons.findIndex(function (b) { return '#' + b.id === location.hash; });
    if (i >= 0 && pickMove.buttons[i].getAttribute('aria-selected') !== 'true') pickMove(i, false);
  }
  window.addEventListener('hashchange', moveFromHash);
  moveFromHash();

  // Command line: the README Quickstart plus the clone it assumes. Action: docs/examples/tracefix.yml, trimmed.
  // momirie/tracefix is pinned to the commit docs/examples/tracefix.yml pins until a release tag exists.
  var TABS = [
    { where: 'Terminal, in your project',
      code: 'git clone https://github.com/momirie/tracefix ~/tracefix\nuv add --dev ~/tracefix\nexport ANTHROPIC_API_KEY=sk-ant-...\nuv run tracefix verify --repo . --base main --head my-fix \\\n    --issue "Service crashes at startup when PORT is not set"' },
    { where: '.github/workflows/tracefix.yml (pinned to a commit until the first release)',
      code: 'on: pull_request\npermissions: {}\njobs:\n  tracefix:\n    runs-on: ubuntu-24.04\n    permissions: {contents: read, checks: write, pull-requests: write, issues: read, actions: read}\n    steps:\n      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n        with: {fetch-depth: 0, persist-credentials: false}\n      - uses: astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2 # v10.3.3\n      - run: uv sync --locked # your project\'s own install step\n      - uses: momirie/tracefix@b46825b4fbfde70f66ff5b024e76a54c212a28f0\n        with:\n          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}' }
  ];
  var install = 0, copyBtn = $('copy');
  tabs('itabs', function (i, button) {
    install = i;
    $('term').setAttribute('aria-labelledby', button.id);
    $('term-where').textContent = TABS[i].where;
    $('term-code').textContent = TABS[i].code;
    copyBtn.textContent = 'Copy';
  });

  if (navigator.clipboard && window.isSecureContext) {
    copyBtn.hidden = false;
    var reset = null;
    copyBtn.addEventListener('click', function () {
      navigator.clipboard.writeText(TABS[install].code).then(function () {
        copyBtn.textContent = 'Copied';
      }, function () {
        copyBtn.textContent = 'Copy failed';
      }).then(function () {
        clearTimeout(reset);
        reset = setTimeout(function () { copyBtn.textContent = 'Copy'; }, 1600);
      });
    });
  }
})();

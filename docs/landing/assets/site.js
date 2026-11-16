// Every page: the theme switch, the nav's hairline, headline words and reveals, the command palette,
// the section bar on long pages, the gallery filter, the tabs (home.js uses them too), and on the
// Method page the receipt-on-a-pull-request panels and the fixture picker on the ladder. The theme
// itself is applied before first paint by the small script in each page's head
// (docs/landing/_src/partials/head.html).
(function () {
  'use strict';

  function $(id) { return document.getElementById(id); }
  var REDUCED = false;
  try { REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}

  // ---- Tabs (click, and arrow keys as in the ARIA tabs pattern). home.js uses them too, through
  // window.tracefixTabs: site.js runs first on every page. Set first, so an error further down this
  // file cannot leave the home page's tabs without it. ----
  function tabs(listId, onPick) {
    var buttons = Array.prototype.slice.call($(listId).querySelectorAll('[role="tab"]'));
    function pick(i, focus) {
      buttons.forEach(function (b, j) {
        b.setAttribute('aria-selected', j === i ? 'true' : 'false');
        b.tabIndex = j === i ? 0 : -1;
      });
      if (focus) buttons[i].focus();
      onPick(i, buttons[i]);
    }
    pick.buttons = buttons;
    buttons.forEach(function (b, i) {
      b.addEventListener('click', function () { pick(i, false); });
      b.addEventListener('keydown', function (e) {
        var n = buttons.length, k = e.key, next = null;
        if (k === 'ArrowDown' || k === 'ArrowRight') next = (i + 1) % n;
        else if (k === 'ArrowUp' || k === 'ArrowLeft') next = (i - 1 + n) % n;
        else if (k === 'Home') next = 0;
        else if (k === 'End') next = n - 1;
        if (next !== null) { e.preventDefault(); pick(next, true); }
      });
    });
    return pick;
  }
  window.tracefixTabs = tabs;

  // ---- Theme: Dark (the default), Light or System (the device setting); the choice is saved ----
  var root = document.documentElement, themeMeta = $('theme-color');
  var lightMQ = window.matchMedia ? window.matchMedia('(prefers-color-scheme: light)') : null;
  function themeChoice() { return root.getAttribute('data-theme') || 'dark'; }
  function isDark() { var c = themeChoice(); return c === 'dark' || (c === 'system' && !(lightMQ && lightMQ.matches)); }
  function paintTheme() {
    var c = themeChoice();
    Array.prototype.forEach.call(document.querySelectorAll('[data-theme-pick]'), function (b) {
      b.setAttribute('aria-pressed', b.getAttribute('data-theme-pick') === c ? 'true' : 'false');
    });
    if (themeMeta) themeMeta.setAttribute('content', isDark() ? '#0b0b0b' : '#ffffff');
    document.dispatchEvent(new Event('tracefix:theme'));
  }
  Array.prototype.forEach.call(document.querySelectorAll('[data-theme-pick]'), function (b) {
    b.addEventListener('click', function () {
      var c = b.getAttribute('data-theme-pick');
      root.setAttribute('data-theme', c);
      try { if (c === 'dark') localStorage.removeItem('tracefix-theme'); else localStorage.setItem('tracefix-theme', c); } catch (e) {}
      paintTheme();
    });
  });
  if (lightMQ) {
    if (lightMQ.addEventListener) lightMQ.addEventListener('change', paintTheme);
    else if (lightMQ.addListener) lightMQ.addListener(paintTheme);
  }
  paintTheme();

  // ---- Phone menu: a native <details>; close it on a link, Escape or a click outside ----
  var menu = document.querySelector('.menu');
  if (menu) {
    menu.addEventListener('click', function (e) { if (e.target.closest('a')) menu.open = false; });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && menu.open) { menu.open = false; menu.querySelector('summary').focus(); }
    });
    document.addEventListener('pointerdown', function (e) { if (menu.open && !menu.contains(e.target)) menu.open = false; });
  }

  // ---- Nav hairline ---------------------------------------------------------------------------
  var head = $('head');
  if (head) {
    var onScrollHead = function () { head.classList.toggle('scrolled', window.scrollY > 8); };
    window.addEventListener('scroll', onScrollHead, { passive: true });
    onScrollHead();
  }
  // ---- Headlines: split into words that rise from behind a mask ------------------------------
  function splitWords(el, baseMs) {
    var i = 0;
    (function walk(node) {
      Array.prototype.slice.call(node.childNodes).forEach(function (ch) {
        if (ch.nodeType === 1) {
          if (ch.getAttribute('aria-hidden') === 'true' || ch.classList.contains('sr-only')) return;
          walk(ch);
          return;
        }
        if (ch.nodeType !== 3 || !ch.data.trim()) return;
        var frag = document.createDocumentFragment();
        ch.data.split(/(\s+)/).forEach(function (part) {
          if (!part) return;
          if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(part)); return; }
          var outer = document.createElement('span'), inner = document.createElement('span');
          outer.className = 'w';
          inner.textContent = part;
          inner.style.setProperty('--i', String(i++));
          if (baseMs) inner.style.setProperty('--base', baseMs + 'ms');
          outer.appendChild(inner);
          frag.appendChild(outer);
        });
        node.replaceChild(frag, ch);
      });
    })(el);
  }
  Array.prototype.forEach.call(document.querySelectorAll('[data-words]'), function (el) { splitWords(el, 0); });

  // ---- Reveal once on entering the screen -----------------------------------------------------
  var revealables = document.querySelectorAll('[data-reveal], [data-words], [data-reveal-group]');
  if (REDUCED || !('IntersectionObserver' in window)) {
    Array.prototype.forEach.call(revealables, function (el) { el.classList.add('is-in'); });
  } else {
    var revealIO = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        // A block taller than most of the screen can never show 12% of itself at once: it is shown
        // as soon as any of it is on screen, or it would stay invisible on a phone.
        var tall = e.boundingClientRect.height > window.innerHeight * 0.8;
        if (e.isIntersecting && (tall || e.intersectionRatio >= 0.12)) {
          e.target.classList.add('is-in'); revealIO.unobserve(e.target);
        }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: [0, 0.12] });
    Array.prototype.forEach.call(revealables, function (el) { revealIO.observe(el); });
  }
  // The reveals run: the head's fail-safe, which shows every block, is no longer needed.
  root.classList.add('reveals-on');

  // ---- A change inside the page, animated where the browser can (View Transitions). Only the
  // named parts move; the page itself does not fade (html.vt-local, site.css). ----
  var morphing = 0;
  function morph(change) {
    if (!document.startViewTransition || REDUCED) { change(); return; }
    // A second change while one still runs skips the first: keep the class until the last ends.
    root.classList.add('vt-local'); morphing++;
    var t = document.startViewTransition(change);
    t.finished.then(done, done);
    function done() { if (--morphing === 0) root.classList.remove('vt-local'); }
  }
  function each(sel, fn, from) { Array.prototype.forEach.call((from || document).querySelectorAll(sel), fn); }
  function press(group, attr, value) {
    each('[' + attr + ']', function (b) { b.setAttribute('aria-pressed', b.getAttribute(attr) === value ? 'true' : 'false'); }, group);
  }
  function fmt(sec) { sec = Math.max(0, Math.floor(sec)); return Math.floor(sec / 60) + ':' + (sec % 60 < 10 ? '0' : '') + (sec % 60); }

  // ---- A small tooltip that follows the pointer (bar pieces, timeline stages) ----
  var tip = document.createElement('div');
  tip.className = 'tip'; tip.setAttribute('aria-hidden', 'true'); tip.hidden = true;
  document.body.appendChild(tip);
  function tipAt(e, text) {
    tip.textContent = text; tip.hidden = false;
    var x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
    var y = e.clientY - tip.offsetHeight - 12;
    tip.style.transform = 'translate(' + Math.max(8, x) + 'px,' + (y < 8 ? e.clientY + 18 : y) + 'px)';
  }
  function tipOff() { tip.hidden = true; }
  // The home page's one-mark-per-fix figures: a mark's tooltip is its row of the figure's key.
  each('.tally', function (fig) {
    var box = fig.querySelector('.marks'), words = {};
    each('.tally-key li', function (li) { words['mk-' + li.getAttribute('data-k')] = li.textContent; }, fig);
    function show(e) {
      var kind = e.target !== box && e.target.classList ? e.target.classList[1] : '';
      if (words[kind]) tipAt(e, words[kind]); else tipOff();
    }
    box.addEventListener('pointermove', show);
    box.addEventListener('pointerdown', show);
    box.addEventListener('pointerleave', tipOff);
  });

  // ---- Command palette: Ctrl or Cmd + K, or "/", opens a search over the pages, their sections
  // and every receipt (the entries are built into the page: scripts/site_palette.py), plus the
  // sections of this page and the theme. Arrows move, Enter opens, Escape closes. ----
  var pal = $('palette'), palData = $('palette-data'), palEntries = null;
  // A payload that does not parse costs the palette only, never the rest of this file.
  try { palEntries = JSON.parse(palData.textContent); } catch (e) {}
  if (pal && palEntries && pal.showModal) {
    var palIn = $('pal-in'), palList = $('pal-list'), palNone = $('pal-none');
    var palRoot = pal.getAttribute('data-root') || '';
    function absolute(href) { try { return new URL(href, location.href).href; } catch (e) { return href; } }
    // This page's own sections, from its "On this page" links; the site-wide list then leaves
    // those out, so a section is never listed twice.
    var here = [], hereUrls = {};
    each('.page-head .jump a', function (a) {
      here.push({ g: 'On this page', t: a.textContent, h: '', href: a.getAttribute('href') });
      hereUrls[absolute(a.getAttribute('href'))] = true;
    });
    var entries = palEntries.map(function (x) {
      return { g: x.g, t: x.t, h: x.h, lv: x.lv, href: palRoot + x.u };
    }).filter(function (x) { return !hereUrls[absolute(x.href)]; });
    ['System', 'Light', 'Dark'].forEach(function (name) {
      entries.push({ g: 'Theme', t: name + ' theme', h: '', theme: name.toLowerCase() });
    });
    entries = here.concat(entries);
    entries.forEach(function (x) { x.find = (x.t + ' ' + x.h + ' ' + (x.lv || '') + ' ' + x.g).toLowerCase(); });
    var shown = [], active = 0, opener = null;

    function marked(text, words) {
      // The text with each matched word underlined (built as nodes: no HTML from the data).
      var frag = document.createDocumentFragment(), low = text.toLowerCase(), at = 0;
      while (at < text.length) {
        var best = -1, len = 0;
        for (var i = 0; i < words.length; i++) {
          var k = low.indexOf(words[i], at);
          if (k !== -1 && (best === -1 || k < best)) { best = k; len = words[i].length; }
        }
        if (best === -1) break;
        frag.appendChild(document.createTextNode(text.slice(at, best)));
        var m = document.createElement('mark'); m.textContent = text.slice(best, best + len); frag.appendChild(m);
        at = best + len;
      }
      frag.appendChild(document.createTextNode(text.slice(at)));
      return frag;
    }
    function score(x, words) {
      // Every word must be somewhere in the entry; a name that starts with one ranks first.
      var title = x.t.toLowerCase(), n = 0;
      for (var i = 0; i < words.length; i++) {
        if (x.find.indexOf(words[i]) === -1) return -1;
        var k = title.indexOf(words[i]);
        n += k === 0 ? 3 : k > 0 ? 2 : 1;
      }
      return n;
    }
    function setActive(i, scroll) {
      active = Math.max(0, Math.min(shown.length - 1, i));
      shown.forEach(function (row, j) { row.el.setAttribute('aria-selected', j === active ? 'true' : 'false'); });
      if (shown.length) {
        palIn.setAttribute('aria-activedescendant', shown[active].el.id);
        if (scroll) shown[active].el.scrollIntoView({ block: 'nearest' });
      } else palIn.removeAttribute('aria-activedescendant');
    }
    function paintPalette() {
      var words = palIn.value.toLowerCase().split(/\s+/).filter(Boolean);
      var found = entries.map(function (x, i) { return { x: x, s: words.length ? score(x, words) : 0, i: i }; })
        .filter(function (r) { return r.s >= 0; });
      // With a query the best matches come first; without one the list keeps its groups.
      if (words.length) found.sort(function (a, b) { return b.s - a.s || a.i - b.i; });
      palList.textContent = ''; shown = [];
      var group = null, into = palList;
      found.forEach(function (r, n) {
        var x = r.x;
        if (!words.length && x.g !== group) {
          // Without a query the options sit in named groups: a heading, then a group it labels.
          group = x.g;
          var wrap = document.createElement('li'), name = document.createElement('div');
          wrap.setAttribute('role', 'presentation');
          name.className = 'pal-group'; name.id = 'pal-g' + n; name.textContent = group;
          into = document.createElement('ul');
          into.setAttribute('role', 'group'); into.setAttribute('aria-labelledby', name.id);
          wrap.appendChild(name); wrap.appendChild(into); palList.appendChild(wrap);
        }
        if (words.length) into = palList;
        var li = document.createElement('li'), t = document.createElement('span'), h = document.createElement('span');
        li.id = 'pal-o' + n; li.className = 'pal-item' + (x.lv ? ' pal-receipt' : ''); li.setAttribute('role', 'option');
        t.className = 'pal-t'; t.appendChild(marked(x.t, words));
        h.className = 'pal-h'; h.appendChild(marked(words.length && x.h === '' ? x.g : x.h, words));
        li.appendChild(t); li.appendChild(h);
        if (x.lv) {
          var lv = document.createElement('span');
          lv.className = 'lvl' + (x.lv === 'COUNTEREXAMPLE' ? ' red' : ''); lv.textContent = x.lv; li.appendChild(lv);
        }
        li.addEventListener('pointermove', function () { if (shown[active] && shown[active].el !== li) setActive(n, false); });
        li.addEventListener('click', function (e) { go(x, e.ctrlKey || e.metaKey); });
        into.appendChild(li);
        shown.push({ el: li, x: x });
      });
      palNone.hidden = shown.length > 0;
      palList.hidden = shown.length === 0;
      palIn.setAttribute('aria-expanded', shown.length ? 'true' : 'false');
      setActive(0, false); palList.scrollTop = 0;
    }
    function go(x, newTab) {
      if (x.theme) {
        var b = document.querySelector('[data-theme-pick="' + x.theme + '"]');
        if (b) b.click();
        return;  // stays open: the page behind shows the change
      }
      if (newTab) { window.open(x.href, '_blank', 'noopener'); return; }
      opener = null;  // the page moves on: no focus to hand back
      pal.close();
      location.href = x.href;
    }
    function openPalette(from) {
      if (pal.open) return;
      opener = from || document.activeElement;
      if (menu) menu.open = false;
      palIn.value = ''; paintPalette();
      pal.showModal(); palIn.focus();
    }
    palIn.addEventListener('input', paintPalette);
    palIn.addEventListener('keydown', function (e) {
      var k = e.key;
      if (k === 'ArrowDown') setActive(active + 1 >= shown.length ? 0 : active + 1, true);
      else if (k === 'ArrowUp') setActive(active - 1 < 0 ? shown.length - 1 : active - 1, true);
      else if (k === 'Home' && !palIn.value) setActive(0, true);
      else if (k === 'End' && !palIn.value) setActive(shown.length - 1, true);
      else if (k === 'Enter') {
        if (e.isComposing) return;  // Enter that confirms an input method's text is not "open"
        if (shown[active]) go(shown[active].x, e.ctrlKey || e.metaKey);
      }
      else return;
      e.preventDefault();
    });
    // A click on the dimmed page behind closes it (the dialog element itself is the backdrop's target).
    // Only when the press started there too: a text selection dragged out of the field does not.
    var pressedOn = null;
    pal.addEventListener('pointerdown', function (e) { pressedOn = e.target; });
    pal.addEventListener('click', function (e) { if (e.target === pal && pressedOn === pal) pal.close(); });
    pal.addEventListener('close', function () { if (opener && opener.focus) opener.focus(); opener = null; });
    each('[data-palette-close]', function (b) { b.addEventListener('click', function () { pal.close(); }); }, pal);
    var mac = /Mac|iPhone|iPad/.test(navigator.platform || '');
    each('[data-palette-open]', function (b) {
      b.hidden = false;
      b.addEventListener('click', function () { openPalette(b); });
    });
    each('[data-palette-key]', function (k) { k.textContent = mac ? '\u2318K' : 'Ctrl K'; });
    document.addEventListener('keydown', function (e) {
      var typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target && e.target.tagName) || '') || (e.target && e.target.isContentEditable);
      // On a Mac only Cmd + K: Control + K deletes to the end of the line in a text field there.
      var chord = mac ? e.metaKey && !e.ctrlKey : e.ctrlKey && !e.metaKey;
      if (e.repeat) return;
      if ((e.key === 'k' || e.key === 'K') && chord && !e.altKey && !e.shiftKey) {
        e.preventDefault();
        if (pal.open) pal.close(); else openPalette(null);
      } else if (e.key === '/' && !typing && !e.ctrlKey && !e.metaKey && !e.altKey && !pal.open) {
        e.preventDefault(); openPalette(null);
      }
    });
  }

  // ---- Section bar: on a page with "On this page" links, the same links come back under the
  // header once the list has scrolled away, and the section on screen is marked. ----
  var jump = document.querySelector('.page-head .jump');
  if (jump && head && 'IntersectionObserver' in window) {
    var bar = document.createElement('nav'), barFrame = document.createElement('div');
    bar.className = 'subnav'; bar.setAttribute('aria-label', 'Sections of this page');
    barFrame.className = 'frame';
    var barLinks = [];
    each('a[href^="#"]', function (a) {
      var target = $(a.getAttribute('href').slice(1));
      if (!target) return;
      var link = document.createElement('a');
      link.href = a.getAttribute('href'); link.textContent = a.textContent;
      barFrame.appendChild(link);
      barLinks.push({ link: link, target: target });
    }, jump);
    if (barLinks.length > 1) {
      bar.appendChild(barFrame); head.appendChild(bar);
      // While one of its links has the focus the bar stays, so hiding it never drops the focus.
      var barWanted = false;
      var barOn = function () {
        var on = barWanted || bar.contains(document.activeElement);
        bar.classList.toggle('on', on); root.classList.toggle('has-subnav', on);
        if (on) bar.removeAttribute('inert'); else bar.setAttribute('inert', '');
      };
      barOn();
      bar.addEventListener('focusout', function () { setTimeout(barOn, 0); });
      // Shown while the list is above the screen (not while it is still below it, on a short screen).
      new IntersectionObserver(function (es) {
        barWanted = !es[0].isIntersecting && es[0].boundingClientRect.top < 0; barOn();
      }).observe(jump);
      var current = null;
      var markCurrent = function () {
        // The last section whose top has passed under the header (and the bar).
        var line = head.getBoundingClientRect().bottom + 60, now = null;
        barLinks.forEach(function (b) { if (b.target.getBoundingClientRect().top <= line) now = b; });
        if (now === current) return;
        current = now;
        barLinks.forEach(function (b) {
          if (b === now) b.link.setAttribute('aria-current', 'true'); else b.link.removeAttribute('aria-current');
        });
        // Keep the marked link in view where the bar scrolls sideways (phones).
        if (now) {
          var l = now.link, left = l.offsetLeft - (barFrame.clientWidth - l.offsetWidth) / 2;
          barFrame.scrollTo({ left: Math.max(0, left), behavior: REDUCED ? 'auto' : 'smooth' });
        }
      };
      var barQueued = false;
      window.addEventListener('scroll', function () {
        if (!barQueued) { barQueued = true; requestAnimationFrame(function () { barQueued = false; markCurrent(); }); }
      }, { passive: true });
      window.addEventListener('resize', markCurrent);
      markCurrent();
    }
  }

  // ---- Benchmark: pick a level out of the bars (legend or a bar piece), switch slices ----
  var results = $('results');
  if (results) {
    var pinned = '';
    function highlight(lv) { if (lv) results.setAttribute('data-hl', lv); else results.removeAttribute('data-hl'); }
    each('.bar .lv', function (seg) {
      var n = +seg.getAttribute('data-n'), of = +seg.getAttribute('data-of'), lv = seg.getAttribute('data-lv');
      var text = lv + ' · ' + n + ' of ' + of + ' runs · ' + Math.round(n * 100 / of) + '%';
      seg.removeAttribute('title');
      seg.addEventListener('pointermove', function (e) { tipAt(e, text); highlight(lv); });
      seg.addEventListener('pointerleave', function () { tipOff(); highlight(pinned); });
    }, results);
    each('[data-legend] .lg', function (b) {
      var lv = b.getAttribute('data-lv');
      b.addEventListener('pointerenter', function () { highlight(lv); });
      b.addEventListener('pointerleave', function () { highlight(pinned); });
      b.addEventListener('focus', function () { highlight(lv); });
      b.addEventListener('blur', function () { highlight(pinned); });
      b.addEventListener('click', function () {
        pinned = pinned === lv ? '' : lv;
        each('[data-legend] .lg', function (x) { x.setAttribute('aria-pressed', x.getAttribute('data-lv') === pinned ? 'true' : 'false'); }, results);
        highlight(pinned);
      });
    }, results);
    var sw = results.querySelector('[data-slice-switch]');
    var tables = results.querySelectorAll('.levels-wrap[data-slice]');
    if (sw && tables.length > 1) {
      sw.hidden = false;
      function showSlice(name) {
        each('.levels-wrap[data-slice]', function (t) {
          var on = t.getAttribute('data-slice') === name;
          t.hidden = !on; if (on) t.classList.add('is-in');
        }, results);
        press(sw, 'data-show-slice', name);
      }
      showSlice(tables[0].getAttribute('data-slice'));
      each('[data-show-slice]', function (b) {
        b.addEventListener('click', function () { var n = b.getAttribute('data-show-slice'); morph(function () { showSlice(n); }); });
      }, sw);
    }
  }

  // ---- Benchmark: find a miss by project, or by slice ----
  var tools = document.querySelector('[data-miss-tools]');
  if (tools) {
    tools.hidden = false;
    var find = tools.querySelector('[data-miss-find]'), count = tools.querySelector('[data-miss-count]');
    var slice = 'all', total = document.querySelectorAll('.miss').length;
    function filterMisses() {
      var q = find.value.trim().toLowerCase(), shown = 0;
      each('.miss-group', function (g) {
        var n = 0;
        each('.miss', function (m) {
          var on = (slice === 'all' || m.getAttribute('data-slice') === slice) && m.getAttribute('data-find').indexOf(q) !== -1;
          m.hidden = !on; if (on) { n++; m.classList.add('is-in'); }
        }, g);
        var c = g.querySelector('[data-group-count]'); if (c) c.textContent = String(n);
        var none = g.querySelector('.none-match'); if (none) none.hidden = n > 0;
        shown += n;
      });
      count.textContent = shown === total ? '' : shown + ' of ' + total + ' shown';
    }
    find.addEventListener('input', filterMisses);
    each('[data-miss-slice]', function (b) {
      b.addEventListener('click', function () {
        slice = b.getAttribute('data-miss-slice');
        press(tools, 'data-miss-slice', slice);
        morph(filterMisses);
      });
    }, tools);
  }

  // ---- Receipt gallery: filter the cards by level; a soft light follows the pointer ----
  var filters = document.querySelector('[data-filters]');
  if (filters) {
    filters.hidden = false;
    var cards = document.querySelectorAll('[data-level]');
    var shownLabel = $('filter-shown');
    function apply(want) {
      var n = 0;
      Array.prototype.forEach.call(cards, function (c) {
        var on = want === 'all' || c.getAttribute('data-level') === want;
        c.hidden = !on; if (on) n++;
      });
      press(filters, 'data-filter', want);
      if (shownLabel) shownLabel.textContent = n === cards.length ? '' : n + ' of ' + cards.length + ' shown';
    }
    each('[data-filter]', function (b) {
      b.addEventListener('click', function () {
        Array.prototype.forEach.call(cards, function (c) { c.classList.add('is-in'); });
        var want = b.getAttribute('data-filter');
        morph(function () { apply(want); });
      });
    }, filters);
  }
  each('.rc', function (c) {
    c.addEventListener('pointermove', function (e) {
      var r = c.getBoundingClientRect();
      c.style.setProperty('--mx', (e.clientX - r.left) + 'px');
      c.style.setProperty('--my', (e.clientY - r.top) + 'px');
    });
  });

  // ---- Receipt: a counterexample's outcome before and after the fix; copy its test ----
  each('.cx-card', function (card) {
    var sw = card.querySelector('.cx-switch'), touched = false;
    sw.hidden = false; card.classList.add('switchable');
    function show(when) { card.setAttribute('data-when', when); press(sw, 'data-when', when); }
    each('button[data-when]', function (b) {
      b.addEventListener('click', function () { touched = true; show(b.getAttribute('data-when')); });
    }, sw);
    // Once, when it first comes into view: show the input before the fix, then flip to after.
    if (!REDUCED && 'IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (es) {
        if (!es[0].isIntersecting) return;
        io.disconnect();
        show('before');
        setTimeout(function () { if (!touched) show('after'); }, 1400);
      }, { threshold: 0.6 });
      io.observe(card);
    }
  });
  each('[data-copy]', function (b) {
    var src = document.querySelector('[data-copy-src="' + b.getAttribute('data-copy') + '"]');
    if (!src) return;
    b.hidden = false;
    b.addEventListener('click', function () {
      function ok() { b.textContent = 'Copied'; setTimeout(function () { b.textContent = 'Copy the test'; }, 1600); }
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(src.value).then(ok, fallback);
      else fallback();
      function fallback() { src.select(); try { document.execCommand('copy'); ok(); } catch (e) {} }
    });
  });

  // ---- Receipt: replay the run in the terminal, a playhead moving along the stage timeline. The
  // timeline is also a slider: drag along it, or use the arrow keys, to move through the run. ----
  var replay = document.querySelector('[data-replay]');
  var out = document.querySelector('[data-replay-out]');
  var line = document.querySelector('.timeline');
  if (replay && out && line) {
    var lines = Array.prototype.slice.call(out.querySelectorAll('.o'));
    var segs = Array.prototype.slice.call(line.querySelectorAll('.tl-seg'));
    var playhead = line.querySelector('.tl-head'), clock = document.querySelector('[data-replay-clock]');
    var end = +line.getAttribute('data-end'), raf = 0, at = end;
    var speed = Math.max(1, end / 9);  // the whole run in about nine seconds
    if (!REDUCED) replay.hidden = false;
    each('.tl-seg', function (seg) {
      var text = seg.getAttribute('title'); seg.removeAttribute('title');
      seg.addEventListener('pointermove', function (e) { if (!dragging) tipAt(e, text); });
      seg.addEventListener('pointerleave', tipOff);
    }, line);
    function stageAt(sim) {
      for (var i = 0; i < segs.length; i++) if (sim < +segs[i].getAttribute('data-to')) return segs[i].textContent;
      return 'the end of the run';
    }
    function paintAt(sim, last) {
      at = sim;
      var shownT = -1;
      lines.forEach(function (l) {
        var t = l.hasAttribute('data-t') ? +l.getAttribute('data-t') : shownT;
        var on = last || t <= sim; l.classList.toggle('wait', !on); if (on) shownT = t;
      });
      segs.forEach(function (s) {
        var from = +s.getAttribute('data-from'), to = +s.getAttribute('data-to');
        s.classList.toggle('done', last || sim >= to);
        s.classList.toggle('now', !last && sim >= from && sim < to);
      });
      playhead.style.left = (last ? 100 : Math.min(100, sim / end * 100)) + '%';
      clock.textContent = 'Run time ' + fmt(last ? end : sim) + (last ? '' : ' of ' + fmt(end));
      line.setAttribute('aria-valuenow', String(Math.round(last ? end : sim)));
      line.setAttribute('aria-valuetext', fmt(last ? end : sim) + ', ' + (last ? 'the end of the run' : stageAt(sim)));
    }
    function stop() { cancelAnimationFrame(raf); replay.disabled = false; replay.textContent = 'Replay the run'; }
    function seek(sim) {
      stop(); sim = Math.max(0, Math.min(end, sim));
      line.classList.add('playing'); paintAt(sim, false);
      if (sim >= end) { paintAt(end, true); line.classList.remove('playing'); }
    }
    line.removeAttribute('aria-hidden');
    line.setAttribute('role', 'slider'); line.setAttribute('tabindex', '0');
    line.setAttribute('aria-label', 'Run timeline');
    line.setAttribute('aria-valuemin', '0'); line.setAttribute('aria-valuemax', String(Math.round(end)));
    paintAt(end, true);
    var dragging = false;
    function fromPointer(e) { var r = line.getBoundingClientRect(); return (e.clientX - r.left) / r.width * end; }
    line.addEventListener('pointerdown', function (e) {
      dragging = true; tipOff(); line.setPointerCapture(e.pointerId); seek(fromPointer(e)); e.preventDefault();
    });
    line.addEventListener('pointermove', function (e) { if (dragging) seek(fromPointer(e)); });
    line.addEventListener('pointerup', function () { dragging = false; });
    line.addEventListener('pointercancel', function () { dragging = false; });
    line.addEventListener('keydown', function (e) {
      var step = e.shiftKey ? 10 : 2, k = e.key;
      if (k === 'ArrowRight' || k === 'ArrowUp') seek(at + step);
      else if (k === 'ArrowLeft' || k === 'ArrowDown') seek(at - step);
      else if (k === 'Home') seek(0);
      else if (k === 'End') seek(end);
      else return;
      e.preventDefault(); e.stopPropagation();
    });
    replay.addEventListener('click', function () {
      stop();
      line.classList.add('playing');
      var start = at >= end ? 0 : at, t0 = performance.now();
      replay.textContent = 'Replaying…'; replay.disabled = true;
      (function tick(now) {
        var sim = start + (now - t0) / 1000 * speed;
        if (sim >= end) { paintAt(end, true); line.classList.remove('playing'); stop(); replay.textContent = 'Replay it again'; return; }
        paintAt(sim, false); raf = requestAnimationFrame(tick);
      })(t0);
    });
  }

  // ---- Receipt: the left and right arrow keys go to the previous and next receipt, but only while
  // nothing has focus or a selection, and the last click was not in a block that scrolls sideways
  // (there the arrows scroll it). ----
  var prev = document.querySelector('a[rel="prev"].pg'), next = document.querySelector('a[rel="next"].pg');
  if (prev && next) {
    var keys = document.querySelector('.pg-keys'); if (keys) keys.hidden = false;
    var SCROLLERS = 'pre,.lines,.md-scroll,.table-wrap,.levels-wrap,.timeline';
    var lastDown = null;
    document.addEventListener('pointerdown', function (e) { lastDown = e.target; }, true);
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || e.defaultPrevented) return;
      // A click on the page's text focuses <main> (the skip link's target, tabindex -1): nothing to
      // steal the arrows from, so it counts as no focus.
      var focused = document.activeElement;
      if (focused && focused !== document.body && focused !== root && focused.id !== 'main') return;
      var sel = window.getSelection ? window.getSelection() : null;
      if (sel && !sel.isCollapsed) return;
      if (lastDown && lastDown.closest && lastDown.closest(SCROLLERS)) return;
      if (e.key === 'ArrowLeft') location.href = prev.href;
      else if (e.key === 'ArrowRight') location.href = next.href;
    });
  }

  // ---- Method: where the receipt goes, one panel at a time (without JavaScript all three show) ----
  if ($('ltabs')) {
    var loopPanels = ['lp-check', 'lp-comment', 'lp-json'].map($);
    var showLoop = function (i) { loopPanels.forEach(function (p, j) { p.hidden = j !== i; }); };
    tabs('ltabs', showLoop);
    showLoop(0);
  }

  // ---- Method: put a fixture's real receipt through the evidence ladder. Each rung it reaches shows
  // the receipt's own reason (the ladder code wrote them into receipt.json's level_reasons). ----
  var climb = document.querySelector('[data-climb]'), climbData = $('climb-data');
  var ladder = document.querySelector('[data-climb-ladder]');
  if (climb && climbData && ladder) {
    var climbs = {}; JSON.parse(climbData.textContent).forEach(function (c) { climbs[c.case] = c; });
    var status = climb.querySelector('[data-climb-status]'), open = climb.querySelector('.climb-open');
    var timers = [], receiptsAt = open.getAttribute('href');
    climb.hidden = false;
    function rung(lv) { return ladder.querySelector('[data-rung="' + lv + '"]'); }
    function reset() {
      timers.forEach(clearTimeout); timers = [];
      each('[data-rung]', function (r) { r.classList.remove('lit', 'stop', 'hit', 'blocked', 'top'); }, ladder);
      each('.why', function (w) { w.parentNode.removeChild(w); }, ladder);
      ladder.classList.add('climbing'); open.hidden = true; status.textContent = '';
    }
    function mark(lv, cls, lines, kind) {
      var r = rung(lv); if (!r) return;
      r.classList.add(cls);
      var box = r.querySelector('.why');
      if (!box) { box = document.createElement('div'); box.className = 'why'; r.lastElementChild.appendChild(box); }
      lines.forEach(function (t) {
        var p = document.createElement('p'); p.className = 'why-' + kind; p.textContent = t; box.appendChild(p);
      });
    }
    function play(c) {
      reset();
      var steps = [], wait = REDUCED ? 0 : 650, n = 0, ending = '';
      if (c.level === 'COUNTEREXAMPLE') {
        steps.push(function () { mark('COUNTEREXAMPLE', 'hit', c.reasons, 'cx'); });
        ending = c.case + ': COUNTEREXAMPLE, proof against the fix.';
      } else if (c.level === 'L0') {
        steps.push(function () { mark('L0', 'stop', c.reasons, 'stop'); rung('L0').classList.add('top'); });
        ending = c.case + ': L0, the run stopped.';
      } else {
        steps.push(function () { mark('L0', 'lit', [], 'yes'); });
        c.reasons.forEach(function (r) {
          if (r.indexOf('not ') === 0) {
            var next = 'L' + (n + 1);
            steps.push(function () { mark(next, 'blocked', [r.replace(/^not L\d: /, '')], 'no'); });
          } else {
            var lv = 'L' + (++n);
            steps.push(function () { mark(lv, 'lit', [r], 'yes'); });
          }
        });
        steps.push(function () { rung(c.level).classList.add('top'); });
        ending = c.case + ' climbs to ' + c.level + (c.level === 'L4' ? ': nothing broke it.' : '.');
      }
      steps.push(function () { status.textContent = ending; open.hidden = false; });
      steps.forEach(function (fn, i) { timers.push(setTimeout(fn, i * wait)); });
      open.href = receiptsAt + c.case + '/';
      var top = ladder.getBoundingClientRect().top;
      // The picker sits right above the ladder: it stays in view for the next pick.
      if (picked && (top > window.innerHeight * 0.6 || top < 0)) climb.scrollIntoView({ behavior: REDUCED ? 'auto' : 'smooth', block: 'start' });
    }
    var picked = false;
    function pick(name) { press(climb, 'data-case', name); play(climbs[name]); }
    each('.climb-pick', function (b) {
      b.addEventListener('click', function () { picked = true; pick(b.getAttribute('data-case')); });
    }, climb);
    // The first time the ladder's top is well on screen, one receipt climbs it on its own, so the
    // idea shows before anyone clicks: the page's `data-first`, the receipt the home replay ends in
    // (a fixture at L4 would suggest real fixes get there; none has yet). Measured from the top, not
    // as a share of the ladder: on a phone the ladder is taller than the screen.
    // It plays only if the ladder is still on screen when the short wait ends: a jump link that
    // scrolls past the ladder must not have the reasons grow it mid-scroll and land short.
    var first = climbs[climb.getAttribute('data-first')] ? climb.getAttribute('data-first') : null;
    if (first && !REDUCED && 'IntersectionObserver' in window) {
      var seenWait = 0;
      var seen = new IntersectionObserver(function (es) {
        clearTimeout(seenWait);
        if (!es[0].isIntersecting) return;
        seenWait = setTimeout(function () {
          var r = ladder.getBoundingClientRect();
          if (picked || r.bottom < 0 || r.top > window.innerHeight * 0.6) return;
          seen.disconnect(); pick(first);
        }, 700);
      }, { rootMargin: '0px 0px -40% 0px' });
      seen.observe(ladder);
    }
    // Point at a rung: the fixtures whose receipts landed there stand out.
    each('[data-rung]', function (r) {
      var lv = r.getAttribute('data-rung');
      r.addEventListener('pointerenter', function () {
        climb.classList.add('matching');
        each('.climb-pick', function (b) { b.classList.toggle('match', b.getAttribute('data-level') === lv); }, climb);
      });
      r.addEventListener('pointerleave', function () { climb.classList.remove('matching'); });
    }, ladder);
  }
})();

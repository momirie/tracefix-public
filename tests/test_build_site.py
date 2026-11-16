"""scripts/build_site.py: the committed website equals a fresh build, and every built page holds
together (links and assets resolve, one h1, a title, the skip link and the theme switch). Also what
a host and a search engine read: the 404 page, robots.txt and sitemap.xml."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import build_site
import pytest
from defusedxml import ElementTree

SITE = build_site.SITE


class _Page(HTMLParser):
    """What the tests need from one page: links, ids, headings, the title and the theme buttons."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[str] = []
        self.ids: set[str] = set()
        self.h1 = 0
        self.title = ""
        self.skip_href: str | None = None
        self.theme_picks: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        if "id" in a:
            self.ids.add(a["id"])
        for key in ("href", "src"):
            if key in a and not (tag == "link" and a.get("rel") in {"canonical", "preconnect"}):
                self.refs.append(a[key])
        if tag == "h1":
            self.h1 += 1
        if tag == "title":
            self._in_title = True
        if tag == "a" and "skip" in a.get("class", "").split():
            self.skip_href = a.get("href")
        if "data-theme-pick" in a:
            self.theme_picks.append(a["data-theme-pick"])

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def _parse(path: Path) -> _Page:
    page = _Page()
    page.feed(path.read_text(encoding="utf-8"))
    return page


BUILT = [SITE / page.out for page in build_site.PAGES]
NOT_FOUND = SITE / build_site.NOT_FOUND.out
# The 404 page holds together like any other page; it is not one of PAGES (no nav link, no
# palette entry, no sitemap line), so the tests about those keep to BUILT.
EVERY = [*BUILT, NOT_FOUND]


def test_committed_site_equals_a_fresh_build() -> None:
    assert build_site.stale() == [], "run: uv run python scripts/build_site.py"


def test_build_writes_every_page(tmp_path: Path) -> None:
    written = build_site.build(tmp_path)
    assert [p.relative_to(tmp_path).as_posix() for p in written] == [
        *(page.out for page in build_site.PAGES),
        "404.html",
        "robots.txt",
        "sitemap.xml",
    ]
    for page in (*build_site.PAGES, build_site.NOT_FOUND):
        assert (tmp_path / page.out).read_text(encoding="utf-8") == build_site.render(page)
    assert (tmp_path / "robots.txt").read_text(encoding="utf-8") == build_site.robots()
    assert (tmp_path / "sitemap.xml").read_text(encoding="utf-8") == build_site.sitemap()


@pytest.mark.parametrize("path", EVERY, ids=lambda p: p.relative_to(SITE).as_posix())
def test_page_has_one_h1_a_title_the_skip_link_and_the_theme_switch(path: Path) -> None:
    page = _parse(path)
    assert page.h1 == 1
    assert page.title.strip()
    assert page.skip_href == "#main" and "main" in page.ids
    # Nav and footer each carry the System / Light / Dark switch.
    assert sorted(page.theme_picks) == sorted(["system", "light", "dark"] * 2)
    assert "{{" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", EVERY, ids=lambda p: p.relative_to(SITE).as_posix())
def test_every_internal_link_and_asset_resolves(path: Path) -> None:
    for ref in _parse(path).refs:
        parts = urlsplit(ref)
        if parts.scheme or parts.netloc:
            continue  # external: https://, mailto:
        # Links are relative, so the site works in any folder; only the 404 page's start at "/".
        from_root = parts.path.startswith("/")
        assert from_root == (path == NOT_FOUND and bool(parts.path)), f"{ref} in {path.name}"
        base = SITE if from_root else path.parent
        target = (base / unquote(parts.path).lstrip("/")).resolve() if parts.path else path
        if target.is_dir():
            target = target / "index.html"
        assert target.is_file(), f"{ref} in {path.name}: no file {target}"
        assert SITE.resolve() in target.parents, f"{ref} in {path.name} leaves the site"
        if parts.fragment and target.suffix == ".html":
            assert parts.fragment in _parse(target).ids, f"{ref} in {path.name}: no such id"


def test_root_and_path_follow_the_folder() -> None:
    home = build_site.PAGES[0]
    sub = build_site.Page(
        body="x",
        out="benchmark/index.html",
        title="",
        description="",
        og_title="",
        og_description="",
    )
    assert (home.root, home.path) == ("", "")
    assert (sub.root, sub.path) == ("../", "benchmark/")


def test_holes_are_filled_and_dollar_signs_stay_literal() -> None:
    text = build_site.SiteTemplate("$ uv run {{title}} $0.15").substitute(title="x")
    assert text == "$ uv run x $0.15"


@pytest.mark.parametrize("source", ["{{missing}}", "a {{ stray", "{{Title}}"])
def test_an_unfilled_or_malformed_hole_is_an_error(source: str) -> None:
    with pytest.raises((KeyError, ValueError)):
        build_site.SiteTemplate(source).substitute(title="x")


def test_check_flag_reports_a_stale_page(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    build_site.build(tmp_path)
    monkeypatch.setattr(build_site, "SITE", tmp_path)
    assert build_site.main(["--check"]) == 0
    (tmp_path / "index.html").write_text("hand-edited", encoding="utf-8")
    assert build_site.main(["--check"]) == 1
    assert "out of date: docs/landing/index.html" in capsys.readouterr().out


def test_every_url_in_the_stylesheets_resolves() -> None:
    for css in (SITE / "assets").glob("*.css"):
        for ref in re.findall(r"url\(([^)]+)\)", css.read_text(encoding="utf-8")):
            ref = ref.strip("'\"")
            if ref.startswith("data:"):
                continue
            assert (css.parent / ref).is_file(), f"{ref} in {css.name}"


def test_the_site_loads_nothing_from_a_third_party() -> None:
    # Fonts are self-hosted (assets/fonts/README.md): only the links people click leave the site.
    texts = [p.read_text(encoding="utf-8") for p in EVERY]
    texts += [p.read_text(encoding="utf-8") for p in (SITE / "assets").glob("*.css")]
    for text in texts:
        assert "fonts.googleapis" not in text and "fonts.gstatic" not in text
    for page in EVERY:
        for tag in re.findall(r"<(?:script|link|img)\b[^>]*>", page.read_text(encoding="utf-8")):
            if 'rel="canonical"' in tag:
                continue
            assert not re.search(r'(?:src|href)="(?:https?:)?//', tag), tag


def test_the_site_folder_holds_only_the_site() -> None:
    """docs/landing/ is hosted as is, so a note, log or draft left in it would be published
    (they live in docs/landing-notes/). Only built pages, assets, sources and data belong here."""
    built = set(build_site.files())
    stray = [
        rel
        for path in sorted(SITE.rglob("*"))
        if path.is_file()
        and (rel := path.relative_to(SITE).as_posix()) not in built
        and rel.split("/")[0] not in {"_src", "_data", "assets"}
    ]
    assert stray == []


def _is_binary(path: Path) -> bool:
    try:
        path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def test_git_leaves_the_bytes_of_fonts_and_images_alone() -> None:
    """`docs/landing/** text eol=lf` alone makes git drop the CR of every CRLF byte pair in a
    font or image on commit. Each binary kind in the site must be marked binary after that rule."""
    rules = (SITE.parent.parent / ".gitattributes").read_text(encoding="utf-8").splitlines()
    kinds = {path.suffix for path in SITE.rglob("*") if path.is_file() and _is_binary(path)}
    assert {".woff2", ".png", ".ico"} <= kinds
    text_rule = rules.index("docs/landing/** text eol=lf")
    for kind in sorted(kinds):
        assert f"docs/landing/**/*{kind} binary" in rules[text_rule + 1 :], kind


def test_every_font_ships_with_its_licence() -> None:
    fonts = SITE / "assets" / "fonts"
    for name in ("Newsreader", "Inter", "IBM-Plex-Mono"):
        assert "SIL Open Font License" in (fonts / f"OFL-{name}.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("out", "benchmark", "receipts"),
    [
        ("index.html", "", ""),
        ("benchmark/index.html", ' aria-current="page"', ""),
        ("receipts/index.html", "", ' aria-current="page"'),
        ("receipts/good_fix/index.html", "", ' aria-current="true"'),
    ],
)
def test_the_nav_marks_the_current_section(out: str, benchmark: str, receipts: str) -> None:
    page = next(p for p in build_site.PAGES if p.out == out)
    assert build_site.current(page, "benchmark") == benchmark
    assert build_site.current(page, "receipts") == receipts


@pytest.mark.parametrize("path", EVERY, ids=lambda p: p.relative_to(SITE).as_posix())
def test_reveals_fail_safe_when_site_js_does_not_run(path: Path) -> None:
    """site.css hides reveal blocks under `.js` until site.js shows them; the head script shows them
    itself if site.js fails to load (onerror) or has not started them in time (council D1)."""
    html = path.read_text(encoding="utf-8")
    head = html.split("</head>", 1)[0]
    assert "d.className = 'js'" in head
    assert "window.tracefixShowAll = showAll" in head and "setTimeout(showAll," in head
    assert re.search(r'<script src="[^"]*assets/site\.js" onerror="tracefixShowAll\(\)">', html)
    site_js = (SITE / "assets" / "site.js").read_text(encoding="utf-8")
    assert "root.classList.add('reveals-on')" in site_js
    assert "contains('reveals-on')" in head


def _media_block(css: str, query: str) -> str:
    """The body of the `@media <query>{...}` block (braces balanced)."""
    start = css.index("@media " + query + "{") + len("@media " + query + "{")
    depth, i = 1, start
    while depth:
        depth += {"{": 1, "}": -1}.get(css[i], 0)
        i += 1
    return css[start : i - 1]


def test_pressed_and_selected_controls_show_in_forced_colors() -> None:
    """Council D7: High Contrast drops the fills and borders that mark the pressed theme button, the
    selected tab or filter; a system highlight colour marks them instead."""
    block = _media_block(
        (SITE / "assets" / "site.css").read_text(encoding="utf-8"), "(forced-colors: active)"
    )
    rule = (
        '[aria-pressed="true"],[aria-selected="true"]'
        "{forced-color-adjust:none;background:Highlight !important;"
    )
    assert rule in block


def test_print_shows_the_content_in_ink_on_paper() -> None:
    """Print: light colours whatever the theme, no controls, every reveal shown, code wrapped."""
    block = _media_block((SITE / "assets" / "site.css").read_text(encoding="utf-8"), "print")
    assert "--ink:#000; --paper:#fff;" in block and "--band:#fff; --on-ink:#000;" in block
    hidden = block.split("{display:none !important}", 1)[0].rsplit("\n", 1)[-1].strip()
    for control in (".site-head .nav", ".menu", ".theme", ".skip", ".btn", ".field", ".pg-keys"):
        assert control in hidden.split(",")
    for control in (".try", ".pal-open", ".palette", ".subnav", "#ltabs"):  # S10's controls
        assert control in hidden.split(",")
    assert ".lp[hidden]{display:block !important}" in block
    assert (
        "[data-reveal],[data-words],[data-reveal-group],.hero" in block
        and "opacity:1 !important" in block
    )
    assert "pre{white-space:pre-wrap" in block


def test_receipt_arrows_work_after_a_click_on_the_page() -> None:
    """A click on text focuses <main> (the skip link's target); that must not count as focus, or the
    arrows to the next receipt stop working after any click."""
    site_js = (SITE / "assets" / "site.js").read_text(encoding="utf-8")
    assert "focused !== root && focused.id !== 'main') return;" in site_js


def _canonical(html: str) -> str:
    (found,) = re.findall(r'<link rel="canonical" href="([^"]+)">', html)
    return str(found)


def test_the_404_page_works_at_any_address() -> None:
    """A host serves 404.html for /x and for /a/b/c alike, so no link on it may be relative: the
    stylesheet, the scripts, the nav and the palette's links all start at the site's root."""
    assert build_site.NOT_FOUND not in build_site.PAGES
    assert (build_site.NOT_FOUND.root, build_site.NOT_FOUND.path) == ("/", "404.html")
    html = NOT_FOUND.read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="/assets/site.css">' in html
    assert '<script src="/assets/site.js" onerror="tracefixShowAll()">' in html
    assert 'aria-label="Search this site" data-root="/">' in html
    assert '<a class="btn" href="/">Home</a>' in html
    assert "aria-current" not in html
    # Like every page of the preview: the note, and no way into the private repository.
    assert '<aside class="preview-note" aria-label="Private preview"><p>Private preview:' in html
    assert "github.com/momirie/tracefix/issues" not in html


def test_the_sitemap_lists_the_canonical_address_of_every_page_and_not_the_404() -> None:
    root = ElementTree.fromstring((SITE / "sitemap.xml").read_text(encoding="utf-8"))
    assert root.tag == "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset"
    listed = [loc.text for loc in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    assert listed == [_canonical(path.read_text(encoding="utf-8")) for path in BUILT]
    assert listed[0] == f"{build_site.ORIGIN}/" and len(set(listed)) == len(listed)
    assert not any("404" in url for url in listed)


def test_the_preview_is_kept_out_of_search_engines_but_crawlers_may_read_it() -> None:
    """While the site is a preview every page says noindex, and a crawler has to be allowed to
    fetch a page to read that. robots.txt names no sitemap until the site may be listed."""
    assert build_site.SEARCHABLE is False
    assert (SITE / "robots.txt").read_text(encoding="utf-8") == "User-agent: *\nAllow: /\n"
    for path in EVERY:
        assert '<meta name="robots" content="noindex, nofollow">' in path.read_text(
            encoding="utf-8"
        )


def test_at_release_one_switch_lists_the_pages_and_names_the_sitemap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(build_site, "SEARCHABLE", True)
    assert build_site.robots().endswith(f"\nSitemap: {build_site.ORIGIN}/sitemap.xml\n")
    for page in build_site.PAGES[:2]:
        assert '<meta name="robots" content="index, follow">' in build_site.render(page)
    # The 404 page is never listed.
    not_found = build_site.render(build_site.NOT_FOUND)
    assert '<meta name="robots" content="noindex, nofollow">' in not_found


def test_check_flag_reports_a_missing_robots_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    build_site.build(tmp_path)
    monkeypatch.setattr(build_site, "SITE", tmp_path)
    (tmp_path / "robots.txt").unlink()
    assert build_site.main(["--check"]) == 1
    assert "out of date: docs/landing/robots.txt" in capsys.readouterr().out

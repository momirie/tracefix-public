"""scripts/site_palette.py: the command palette lists every page and every receipt, each entry
leads somewhere real, and every page carries the palette's markup with its entries."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit

import build_site
import pytest
import site_palette
import site_receipts
from test_build_site import BUILT, SITE, _parse


def _target(url: str) -> tuple[Path, str]:
    """The built file an entry's link opens from the site's root, and its fragment."""
    parts = urlsplit(url)
    return SITE / parts.path / "index.html", parts.fragment


def test_every_entry_leads_to_a_built_page_and_an_id_on_it() -> None:
    built = {SITE / page.out for page in build_site.PAGES}
    for entry in site_palette.entries():
        path, fragment = _target(entry["u"])
        assert path in built, entry
        if fragment:
            assert fragment in _parse(path).ids, entry


def test_every_page_and_every_receipt_is_listed() -> None:
    links = {entry["u"] for entry in site_palette.entries()}
    # Every built page is an entry of its own (the home page is the empty link).
    assert {page.path for page in build_site.PAGES} <= links
    by_link = {entry["u"]: entry for entry in site_palette.entries()}
    for name in site_receipts.cases():
        case = site_receipts.load(name)
        entry = by_link[f"receipts/{name}/"]
        assert (entry["t"], entry["h"], entry["lv"]) == (
            name,
            site_receipts.title(case),
            case.level,
        )


def test_the_home_sections_are_the_ids_the_page_has() -> None:
    # The tabs are linkable (#butterfly, #hard-code, #lawyer), and so are the parts added with them.
    ids = _parse(SITE / "index.html").ids
    home = {url[1:] for url, _, page in site_palette.SECTIONS if page == "Home"}
    assert {"butterfly", "hard-code", "lawyer", "try", "stands", "faq"} <= home <= ids
    # The receipt on a pull request moved to the Method page with the home page cut.
    assert ("method/#loop", "In the pull request", "Method") in site_palette.SECTIONS


@pytest.mark.parametrize("path", BUILT, ids=lambda p: p.relative_to(SITE).as_posix())
def test_every_page_carries_the_palette_and_its_entries(path: Path) -> None:
    html = path.read_text(encoding="utf-8")
    found = re.search(
        r'<script type="application/json" id="palette-data">(.*?)</script>', html, re.S
    )
    assert found is not None
    assert json.loads(found.group(1)) == site_palette.entries()
    page = next(p for p in build_site.PAGES if SITE / p.out == path)
    # The entries' links start at the site's root: the dialog carries this page's way back to it.
    dialog = '<dialog id="palette" class="palette" aria-label="Search this site" data-root="{}">'
    assert dialog.format(page.root) in html
    assert 'role="combobox"' in html and '<ul id="pal-list" class="pal-list" role="listbox"' in html
    # The buttons that open it need JavaScript, so they stay hidden until site.js shows them.
    buttons = re.findall(r"<button[^>]*data-palette-open[^>]*>", html)
    assert buttons and all(" hidden" in b for b in buttons)


def test_the_entries_cannot_close_their_script_element(tmp_path: Path) -> None:
    receipts, fixtures = tmp_path / "receipts", tmp_path / "fixtures"
    shutil.copytree(site_receipts.RECEIPTS / "good_fix", receipts / "good_fix")
    shutil.copytree(site_receipts.FIXTURES / "good_fix", fixtures / "good_fix")
    path = receipts / "good_fix" / "receipt.json"
    found = json.loads(path.read_text(encoding="utf-8"))
    found["issue"]["title"] = "</script><script>alert(1)</script>"
    path.write_text(json.dumps(found), encoding="utf-8")
    data = site_palette.data(receipts, fixtures)
    assert "<" not in data
    assert found["issue"]["title"] in {entry["h"] for entry in json.loads(data)}


def test_the_palette_is_built_from_text_never_from_html() -> None:
    # Entry names come from receipts (an issue title is untrusted text): site.js must add them as
    # text nodes, so nothing in an entry can become markup.
    js = (SITE / "assets" / "site.js").read_text(encoding="utf-8")
    palette = js[js.index("// ---- Command palette") : js.index("// ---- Section bar")]
    assert "innerHTML" not in palette and "insertAdjacentHTML" not in palette
    assert "createTextNode" in palette and "textContent" in palette

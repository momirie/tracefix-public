"""scripts/site_talk.py: the Talk page types no number, every way to reach the developer is a
mailto to one address, the gate it cites is the data's, and no page links to a GitHub issue form
(which 404s while the repo is private: council 2026-11-07, "no dead ends")."""

from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import build_site
import pytest
import site_benchmark
import site_talk
from test_site_benchmark import _text

SOURCE = build_site.SRC / "pages" / "talk.html"
PAGE = build_site.SITE / "talk" / "index.html"
BUILT = [build_site.SITE / page.out for page in build_site.PAGES]


def test_the_page_source_types_no_number() -> None:
    text = re.sub(r"\{\{[a-z_]+\}\}", "", _text(SOURCE.read_text(encoding="utf-8")))
    assert re.findall(r".{0,20}\d.{0,20}", text) == []


def test_the_page_source_types_no_number_word() -> None:
    text = re.sub(r"\{\{[a-z_]+\}\}", "", _text(SOURCE.read_text(encoding="utf-8"))).lower()
    words = ("two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "twenty")
    assert [w for w in words if re.search(rf"\b{w}\b", text)] == []


def test_every_hole_is_filled() -> None:
    fields = site_talk.fields()
    holes = set(re.findall(r"\{\{([a-z_]+)\}\}", SOURCE.read_text(encoding="utf-8")))
    assert holes <= set(fields) | {"root"}
    assert set(fields) <= holes, "a field the page never uses"


def test_the_gate_is_the_data_s() -> None:
    gates, _, _ = site_benchmark.load()
    gate = next(g for g in gates["gates"] if g["number"] == site_talk.TALK_GATE)
    assert gate["title"] == "Someone wants it"
    assert "conversations" in gate["measures"]
    fields = site_talk.fields()
    latest = gates["columns"][2:-2][-1]
    assert fields["talk_gate_count"] == html.escape(gate["results"][latest])
    assert fields["gates_total"] == str(len(gates["gates"]))
    assert fields["gates_holding"] == str(gates["holding"])


@pytest.mark.parametrize("kind", sorted(site_talk.MESSAGES))
def test_each_mailto_goes_to_the_one_address_with_its_template(kind: str) -> None:
    link = urlsplit(site_talk.mailto(kind))
    assert link.scheme == "mailto" and link.path == site_talk.EMAIL
    query = parse_qs(link.query, keep_blank_values=True)
    subject, body = site_talk.MESSAGES[kind]
    assert query["subject"] == [subject]
    assert query.get("body", [""]) == [body]
    assert html.escape(site_talk.mailto(kind)) in PAGE.read_text(encoding="utf-8")


def test_the_page_is_built_and_marked_current_in_the_nav() -> None:
    page = next(p for p in build_site.PAGES if p.out == "talk/index.html")
    assert build_site.current(page, "talk") == ' aria-current="page"'
    built = PAGE.read_text(encoding="utf-8")
    assert '<a class="btn btn-sm" href="../talk/" aria-current="page">Talk to me</a>' in built
    assert '<a href="../talk/" aria-current="page">Talk to me</a>' in built  # the phone menu


@pytest.mark.parametrize("path", BUILT, ids=lambda p: p.relative_to(build_site.SITE).as_posix())
def test_every_page_is_a_marked_private_preview_with_no_issue_form_link(path: Path) -> None:
    built = path.read_text(encoding="utf-8")
    assert '<meta name="robots" content="noindex, nofollow">' in built
    assert '<aside class="preview-note" aria-label="Private preview"><p>Private preview:' in built
    assert "github.com/momirie/tracefix/issues" not in built
    assert 'href="https://github.com/momirie/tracefix">GitHub (after release)</a>' in built
    assert "Talk to me</a>" in built

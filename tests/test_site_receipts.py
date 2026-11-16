"""scripts/site_receipts.py: the Receipt gallery shows every fixture's receipt, its numbers come
from the receipts and fixtures (the page sources type none), receipt.md renders as GitHub shows it
with no raw HTML but its own `<details>`, and data text is escaped."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import build_site
import pytest
import site_receipts
from test_site_benchmark import _text

SOURCES = [build_site.SRC / "pages" / name for name in ("receipts.html", "receipt.html")]
GALLERY = build_site.SITE / "receipts" / "index.html"


@pytest.mark.parametrize("source", SOURCES, ids=lambda p: p.name)
def test_the_page_sources_type_no_number(source: Path) -> None:
    text = re.sub(r"\{\{[a-z_]+\}\}", "", _text(source.read_text(encoding="utf-8")))
    assert re.findall(r".{0,20}\d.{0,20}", text) == []


def test_every_fixture_has_a_receipt_a_card_and_a_page() -> None:
    names = site_receipts.cases()
    fixtures = {p.parent.name for p in site_receipts.FIXTURES.glob("*/expected.json")}
    assert set(names) == fixtures
    assert names[: len(site_receipts.ORDER_ON_PAGE)] == list(site_receipts.ORDER_ON_PAGE)
    html = GALLERY.read_text(encoding="utf-8")
    assert html.count('<li class="rc') == len(names)
    for name in names:
        assert f'href="{name}/"' in html
        assert (build_site.SITE / "receipts" / name / "index.html").is_file()


def test_every_receipt_meets_its_known_answer_and_the_page_says_so() -> None:
    found = [site_receipts.load(name) for name in site_receipts.cases()]
    assert all(case.matches for case in found)
    text = _text(GALLERY.read_text(encoding="utf-8"))
    assert f"{len(found)} of {len(found)} receipts meet their known answer" in text


@pytest.mark.parametrize(
    ("how", "want", "got", "meets"),
    [
        ("at_most", "L2", "COUNTEREXAMPLE", True),  # COUNTEREXAMPLE is below L0
        ("at_least", "L2", "L1", False),
        ("exactly", "L1", "L1", True),
        ("exactly", "COUNTEREXAMPLE", "L4", False),
    ],
)
def test_the_known_answer_uses_the_ladder_order(how: str, want: str, got: str, meets: bool) -> None:
    case = site_receipts.load("good_fix")
    case.receipt["level"] = got
    case.expected["receipt"]["level"] = {how: want}
    assert case.matches is meets
    assert site_receipts.known_answer(case).endswith("meets it" if meets else "does not meet it")


def test_each_case_page_shows_its_findings_tests_and_run() -> None:
    for name in site_receipts.cases():
        case = site_receipts.load(name)
        html = (build_site.SITE / "receipts" / name / "index.html").read_text(encoding="utf-8")
        text = _text(html)
        for finding in case.receipt["findings"]:
            assert finding["call"] in text
        for path, _ in case.written:
            assert path in text
        assert case.run_log.splitlines()[-1] in text
        assert f"run {site_receipts.run_time(case)}" in text


def test_the_diff_is_the_fixtures_head_against_its_base() -> None:
    case = site_receipts.load("partial_fix")
    assert [d.path for d in case.diffs] == ["src/svc/config.py", "tests/test_config.py"]
    assert site_receipts.diffstat(case) == f"2 files changed, +7 {site_receipts.MINUS}0"
    assert "+    if raw is None:" in case.diffs[0].lines


def test_run_time_reads_the_last_stamp() -> None:
    case = site_receipts.load("partial_fix")
    stamp = re.findall(r"^\[\s*([\d.]+)\]", case.run_log, flags=re.M)[-1]
    seconds = round(float(stamp))
    assert site_receipts.run_time(case) == f"{seconds // 60}:{seconds % 60:02d}"


def test_receipt_md_renders_like_github() -> None:
    md = site_receipts.load("partial_fix").receipt_md
    html = site_receipts.markdown(md, shift=1, html=True)
    assert "<h1" not in html and "<h2" not in html and "<h3>Fix Receipt" in html
    assert '<div class="alert alert-warning">' in html and "[!WARNING]" not in html
    assert "<blockquote>" not in html
    assert '<div class="md-scroll" tabindex="0" role="region" aria-label="Stages">' in html
    assert "<details>" in html and "<summary>Run log</summary>" in html
    assert "<table>" in html and "<br />" in html


@pytest.mark.parametrize(
    "extra", ["<script>alert(1)</script>", '<img src=x onerror="x">', "text <b>inline</b> text"]
)
def test_raw_html_other_than_the_run_log_wrapper_is_refused(extra: str) -> None:
    md = site_receipts.load("partial_fix").receipt_md + "\n\n" + extra + "\n"
    with pytest.raises(ValueError, match="unexpected raw HTML"):
        site_receipts.markdown(md, shift=1, html=True)


def test_the_issue_renders_with_no_raw_html_at_all() -> None:
    html = site_receipts.markdown("# Title\n\n<script>x()</script>\n", shift=2, html=False)
    assert "<h3>Title</h3>" in html and "<script>" not in html and "&lt;script&gt;" in html


def _copy(tmp_path: Path, name: str) -> tuple[Path, Path]:
    receipts, fixtures = tmp_path / "receipts", tmp_path / "fixtures"
    shutil.copytree(site_receipts.RECEIPTS / name, receipts / name)
    shutil.copytree(site_receipts.FIXTURES / name, fixtures / name)
    return receipts, fixtures


def test_data_text_is_escaped(tmp_path: Path) -> None:
    receipts, fixtures = _copy(tmp_path, "partial_fix")
    path = receipts / "partial_fix" / "receipt.json"
    found = json.loads(path.read_text(encoding="utf-8"))
    found["issue"]["title"] = '<script>alert("x")</script>'
    found["findings"][0]["call"] = "<img src=x>"
    path.write_text(json.dumps(found), encoding="utf-8")
    log = receipts / "partial_fix" / "run.log"
    log.write_text(log.read_text(encoding="utf-8") + "</pre><script>\n", encoding="utf-8")
    page = site_receipts.case_fields("partial_fix", receipts, fixtures)
    cards = site_receipts.gallery_fields(receipts, fixtures)["cards"]
    for html in (*page.values(), cards):
        assert "<script>" not in html and "<img src=x>" not in html
    assert "&lt;script&gt;" in cards and "&lt;img src=x&gt;" in cards


def test_the_filter_chips_count_every_level_reached() -> None:
    found = [site_receipts.load(name) for name in site_receipts.cases()]
    html = site_receipts.filters(found)
    assert f'data-filter="all" aria-pressed="true">All <span>{len(found)}</span>' in html
    for level in {c.level for c in found}:
        n = sum(c.level == level for c in found)
        assert f'data-filter="{level}" aria-pressed="false">{level} <span>{n}</span>' in html
    cards = GALLERY.read_text(encoding="utf-8")
    assert sorted(re.findall(r'data-level="([A-Z0-9]+)"', cards)) == sorted(c.level for c in found)


def test_the_pager_links_the_neighbours_and_wraps_round() -> None:
    names = site_receipts.cases()
    first, last = site_receipts.pager(names[0]), site_receipts.pager(names[-1])
    assert f'rel="prev" href="../{names[-1]}/"' in first
    assert f'rel="next" href="../{names[1]}/"' in first
    assert f'rel="next" href="../{names[0]}/"' in last


def test_a_card_and_its_page_share_the_names_the_transition_morphs() -> None:
    case = site_receipts.load("partial_fix")
    page = (build_site.SITE / "receipts" / "partial_fix" / "index.html").read_text(encoding="utf-8")
    for kind in ("title", "lvl"):
        name = f"view-transition-name:{kind}-partial_fix"
        assert name in site_receipts.card(case) and page.count(name) == 1


def test_each_climb_has_one_reason_per_rung_it_opened() -> None:
    for climb in site_receipts.climb_data():
        opened = [r for r in climb["reasons"] if not r.startswith("not ")]
        if climb["level"] not in ("COUNTEREXAMPLE", "L0"):
            assert len(opened) == int(climb["level"][1:])
        assert climb["reasons"]


def test_a_climb_that_does_not_add_up_stops_the_build(tmp_path: Path) -> None:
    receipts, fixtures = _copy(tmp_path, "good_fix")
    path = receipts / "good_fix" / "receipt.json"
    found = json.loads(path.read_text(encoding="utf-8"))
    found["level_reasons"] = found["level_reasons"][:2]  # L4 with two rungs explained
    path.write_text(json.dumps(found), encoding="utf-8")
    with pytest.raises(ValueError, match="2 rung reasons for L4"):
        site_receipts.climb_data(receipts, fixtures)


def test_the_climb_data_cannot_close_its_script_element(tmp_path: Path) -> None:
    receipts, fixtures = _copy(tmp_path, "partial_fix")
    path = receipts / "partial_fix" / "receipt.json"
    found = json.loads(path.read_text(encoding="utf-8"))
    found["level_reasons"] = ["</script><script>alert(1)</script>"]
    path.write_text(json.dumps(found), encoding="utf-8")
    data = site_receipts.climb_fields(receipts, fixtures)["climb_data"]
    assert "<" not in data and json.loads(data)[0]["reasons"] == found["level_reasons"]


def test_the_timeline_follows_the_log_and_marks_evidence_against_the_fix() -> None:
    case = site_receipts.load("no_fix")
    html = site_receipts.timeline(case)
    assert html.count('class="tl-seg') == len(case.receipt["stages"])
    bad = re.findall(r'class="tl-seg tl-bad"[^>]*><span class="tl-name">(\w+)<', html)
    assert bad == ["reproduce", "break_my_fix"]
    assert site_receipts.timeline(site_receipts.load("good_fix")).count("tl-bad") == 0


def test_every_finding_has_a_card_with_both_outcomes() -> None:
    for name in site_receipts.cases():
        case = site_receipts.load(name)
        html = site_receipts.counterexample_section(case)
        assert html.count('class="cx-card"') == len(case.receipt["findings"])
        for finding in case.receipt["findings"]:
            text = _text(html)
            assert finding["outcome"] in text and finding["base_outcome"] in text


def test_the_stages_marked_against_the_fix_are_real_stages() -> None:
    from tracefix.record import STAGES

    assert {name for name, _ in site_receipts.BROKE} <= set(STAGES)


def test_no_page_claims_a_fix_is_correct_for_all_inputs() -> None:
    # Two fixtures' descriptions say so; no receipt can show it, so the site drops the claim.
    said = [
        n
        for n in site_receipts.cases()
        if "correct for all inputs" in site_receipts.load(n).expected["summary"]
    ]
    assert sorted(said) == ["good_fix", "method_good"]
    assert site_receipts.fix_summary(site_receipts.load("good_fix")) == (
        "Rounds the page count up so a partial last page exists; guarded by a new test."
    )
    for page in build_site.PAGES:
        assert "correct for all inputs" not in (build_site.SITE / page.out).read_text(
            encoding="utf-8"
        )


def test_a_cards_headline_is_its_highest_reason_not_the_first() -> None:
    # Council 2026-11-07: an L4 card showed the L1 sentence.
    for name in site_receipts.cases():
        case = site_receipts.load(name)
        if case.receipt["findings"] or case.receipt["status"] != "ok":
            continue
        opened = [r for r in case.receipt["level_reasons"] if not r.startswith("not ")]
        assert site_receipts.headline(case) == opened[-1]
    good = site_receipts.headline(site_receipts.load("good_fix"))
    assert good.startswith("Break My Fix attacked every changed function")


def test_no_block_taller_than_a_phone_screen_waits_for_a_reveal() -> None:
    # The receipt article is 6,000 to 9,000 px tall on a phone: 12% of it never fits on screen, so
    # with data-reveal it stayed invisible (verifier B1, website S9).
    source = (build_site.SRC / "pages" / "receipt.html").read_text(encoding="utf-8")
    article = re.search(r"<article[^>]*md-receipt[^>]*>", source)
    assert article is not None and "data-reveal" not in article.group(0)


def test_a_tall_block_is_revealed_as_soon_as_it_is_on_screen() -> None:
    js = (build_site.SITE / "assets" / "site.js").read_text(encoding="utf-8")
    assert "threshold: [0, 0.12]" in js
    assert "e.boundingClientRect.height > window.innerHeight * 0.8" in js


def test_receipt_markdown_never_renders_an_image() -> None:
    # An image would load from another host; receipt_md escapes "![" today, this is the backstop.
    assert "<img" not in site_receipts.markdown("![x](https://example.com/a.png)", 0, html=False)

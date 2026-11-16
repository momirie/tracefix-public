"""scripts/site_method.py: the Method page types no number; every limit it names is the constant
the code uses, and the page is built, linked from the nav and marked as the current section. Its
fixture picker and the receipt on a pull request (moved from the home page, DECISIONS 2026-11-14
"Home page cut") are the receipts' own and the Action's own."""

from __future__ import annotations

import html
import json
import re

import build_site
import pytest
import site_home
import site_method
import site_receipts
from test_site_benchmark import _text
from test_site_home import NUMBER_WORDS

from tracefix import action_report, attack, behaviour_rules, guard, ladder, llm, repro
from tracefix.ladder import ORDER
from tracefix.receipt import Receipt

SOURCE = build_site.SRC / "pages" / "method.html"
PAGE = build_site.SITE / "method" / "index.html"


def _page_text() -> str:
    return re.sub(r"\s+", " ", _text(PAGE.read_text(encoding="utf-8")))


def test_the_page_source_types_no_number() -> None:
    # The site rule: a number on the page comes through a {{hole}}. Level names are labels.
    text = re.sub(r"\{\{[a-z_]+\}\}", "", _text(SOURCE.read_text(encoding="utf-8")))
    text = re.sub(r"\bL[0-4]\b", "", text)
    assert re.findall(r".{0,20}\d.{0,20}", text) == []


def test_the_page_source_types_no_number_word() -> None:
    # A count written as a word is still a typed number: it must come from a hole too.
    text = re.sub(r"\{\{[a-z_]+\}\}", "", _text(SOURCE.read_text(encoding="utf-8"))).lower()
    # The home page's list (it includes "eleven", "twelve", "dozen"): the text that moved here from
    # the home page keeps the check it had there.
    assert [w for w in NUMBER_WORDS if re.search(rf"\b{w}\b", text)] == []


def test_every_hole_is_filled_from_the_code() -> None:
    fields = site_method.fields()
    holes = set(re.findall(r"\{\{([a-z_]+)\}\}", SOURCE.read_text(encoding="utf-8")))
    assert holes <= set(fields)
    assert set(fields) <= holes, "a field the page never uses"


def test_the_numbers_are_the_code_constants() -> None:
    text = _text(PAGE.read_text(encoding="utf-8"))
    assert f"at least {ladder.L4_MIN_INPUTS:,} inputs of its own" in text
    assert f"at least {behaviour_rules.MIN_COMPARED:,} per changed function" in text
    assert f"at most {round(behaviour_rules.MAX_LOST_SHARE * 100)}% lost" in text
    assert f"at least {guard.KILL_PERCENT}% must be killed" in text
    assert f"in a row. Up to {site_method.word(repro.MAX_ATTEMPTS)} attempts" in text
    assert f"fails on head {site_method.times(attack.FINDING_RERUNS + 1)} in a row" in text
    assert f"at most {llm.DEFAULT_MAX_CALLS:,} model calls" in text
    assert f"{llm.DEFAULT_TOKEN_BUDGET:,} tokens per run" in text
    for model in llm.DEFAULT_MODELS.values():
        assert model in text


@pytest.mark.parametrize(
    ("n", "word", "times"),
    [(1, "one", "once"), (2, "two", "twice"), (3, "three", "three times"), (12, "12", "12 times")],
)
def test_counts_read_as_words(n: int, word: str, times: str) -> None:
    assert site_method.word(n) == word
    assert site_method.times(n) == times


def test_the_nav_and_footer_link_the_page_and_mark_it_current() -> None:
    page = next(p for p in build_site.PAGES if p.out == "method/index.html")
    assert build_site.current(page, "method") == ' aria-current="page"'
    html = PAGE.read_text(encoding="utf-8")
    assert html.count('<a href="../method/" aria-current="page">Method') == 2  # nav, phone menu
    home = (build_site.SITE / "index.html").read_text(encoding="utf-8")
    assert home.count('href="method/"') == 4  # the nav, the phone menu, the footer and the hero


def test_every_role_table_cell_is_labelled_with_its_column() -> None:
    # On a phone the tables stack and each cell shows its column's name (site.css, data-label).
    source = SOURCE.read_text(encoding="utf-8")
    for table in re.findall(r'<table class="mt-roles">.*?</table>', source, flags=re.S):
        heads = re.findall(r'<th scope="col">(.*?)</th>', table)[1:]
        for row in re.findall(r"<tr><th scope=\"row\">.*?</tr>", table):
            assert re.findall(r'<td[^>]* data-label="([^"]*)"', row) == heads
            assert row.count("<td") == len(heads)


def test_the_ladder_autoplays_the_replays_counterexample() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert f'data-climb data-first="{site_home.REPLAY}"' in page
    assert site_receipts.load(site_home.REPLAY).level == "COUNTEREXAMPLE"


def test_the_check_run_is_what_the_action_would_send() -> None:
    case = site_receipts.load(site_home.REPLAY)
    receipt = Receipt.model_validate(case.receipt)
    notes, _ = action_report.annotations_for(receipt)
    page, text = PAGE.read_text(encoding="utf-8"), _page_text()
    assert action_report.conclusion(receipt, "") == "failure"
    assert '<dd><span class="ck-failure">failure</span></dd>' in page
    assert action_report.check_title(action_report.Report(receipt), "") in text
    assert f"{notes[0].path}, line {notes[0].line}" in text
    assert notes[0].title in text and notes[0].message in text


def test_the_conclusion_for_each_level_is_the_actions_own() -> None:
    clean = Receipt.model_validate(site_receipts.load(site_method.CLEAN).receipt)
    assert not clean.findings and not clean.tampering
    rows = re.findall(
        r'<li><span class="lvl[^"]*">(\w+)</span><span class="ck-(\w+)">(\w+)</span></li>',
        site_method.check_by_level(clean),
    )
    assert [level for level, _, _ in rows] == [level.value for level in reversed(ORDER)]
    for level, css, says in rows:
        swapped = clean.model_copy(update={"level": type(clean.level)(level)})
        assert css == says == action_report.conclusion(swapped, "")
    assert site_method.check_by_level(clean) in PAGE.read_text(encoding="utf-8")


def test_the_comment_and_the_json_are_the_receipts_own() -> None:
    case = site_receipts.load(site_home.REPLAY)
    page = PAGE.read_text(encoding="utf-8")
    assert site_receipts.markdown(case.receipt_md, shift=1, html=True) in page
    found = re.search(r'<pre class="code lp-body"[^>]*>(.*?)</pre>', page, re.S)
    assert found is not None
    excerpt = json.loads(html.unescape(found.group(1)))
    finding = case.receipt["findings"][0]
    assert excerpt["level"] == case.receipt["level"]
    assert excerpt["level_reasons"] == case.receipt["level_reasons"]
    for key in ("call", "outcome", "file", "path", "line"):
        assert excerpt["findings"][0][key] == finding[key]
    assert excerpt["findings"][0]["property"]["quote"] == finding["property"]["quote"]


def test_the_pull_request_panels_read_without_javascript() -> None:
    """Without JavaScript the three panels of the receipt on a pull request show one under the
    other (none is hidden in the page, the tab buttons are hidden by `.no-js`), and the fixture
    picker on the ladder, which needs a script, stays hidden."""
    page = PAGE.read_text(encoding="utf-8")
    for panel in ("lp-check", "lp-comment", "lp-json"):
        assert re.search(
            rf'<div id="{panel}" class="lp" role="tabpanel" aria-labelledby="[\w-]+">', page
        )
    css = (build_site.SITE / "assets" / "site.css").read_text(encoding="utf-8")
    assert ".no-js #ltabs{display:none}" in css
    assert re.search(r'<div class="climb" data-climb [^>]*\bhidden>', page)

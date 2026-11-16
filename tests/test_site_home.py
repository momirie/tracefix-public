"""scripts/site_home.py: the home page types no number; its standing, costs, code panels, tabs and
requirements are the repo's own (the benchmark data, the receipts, the fixtures, pyproject.toml),
and the copy the council found flattering is gone
(docs/landing-notes/council-verdict-site-2026-11-06.md)."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import tomllib
from collections.abc import Callable
from pathlib import Path

import build_site
import pytest
import site_benchmark
import site_home
import site_receipts
from test_site_benchmark import _copy_data, _text

from tracefix import interpreter

SOURCE = build_site.SRC / "pages" / "index.html"
PAGE = build_site.SITE / "index.html"
APOS = "\N{RIGHT SINGLE QUOTATION MARK}"
NUMBER_WORDS = (
    "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
    "twice", "dozen",
)  # fmt: skip


def _source_text() -> str:
    return re.sub(r"\{\{[a-z_]+\}\}", "", _text(SOURCE.read_text(encoding="utf-8")))


def _page_text() -> str:
    return re.sub(r"\s+", " ", _text(PAGE.read_text(encoding="utf-8")))


def test_the_page_source_types_no_number() -> None:
    # The site rule: a number on the page comes through a {{hole}}. Level names are labels.
    text = re.sub(r"\bL[0-4]\b", "", _source_text())
    assert re.findall(r".{0,20}\d.{0,20}", text) == []


def test_the_page_source_types_no_number_word() -> None:
    text = _source_text().lower()
    assert [w for w in NUMBER_WORDS if re.search(rf"\b{w}\b", text)] == []


def test_every_hole_is_filled_and_every_field_used() -> None:
    holes = set(re.findall(r"\{\{([a-z_]+)\}\}", SOURCE.read_text(encoding="utf-8")))
    assert holes == set(site_home.fields())


def test_where_it_stands_is_the_benchmark_with_its_caveat() -> None:
    gates, benchmark, _ = site_benchmark.load()
    section = benchmark[site_benchmark.standing_slice(benchmark)]
    wrong, own = section["agent_wrong"], section["own_mistake"]
    text = _page_text()
    assert site_benchmark.standing(gates, benchmark) in text
    assert (
        f"gave {wrong['detection']['n']} a counterexample, but only {own['n']} of those"
        f" {own['of']} rests on the agent{APOS}s own mistake" in text
    )
    assert f"{gates['holding']} of {len(gates['gates'])} release gates hold" in text


def test_the_costs_and_times_are_the_benchmark_medians() -> None:
    _, benchmark, _ = site_benchmark.load()
    cost = benchmark[site_benchmark.standing_slice(benchmark)]["cost_and_time"]
    text = _page_text()
    assert f"a live run took {cost['seconds_per_run']['median'] / 60:.1f} minutes" in text
    assert f"${cost['usd_per_run']['median']:.2f} of model calls at the median" in text
    assert "about 4 minutes" not in text and "$0.15 of model calls" not in text


def test_the_replay_shows_the_fixtures_code_and_the_receipts_run() -> None:
    case = site_receipts.load(site_home.REPLAY)
    head = (site_receipts.FIXTURES / site_home.REPLAY / "head" / site_home.REPLAY_FILE).read_text(
        encoding="utf-8"
    )
    text = _page_text()
    for line in site_home.function_lines(head, site_home.REPLAY_FUNCTION):
        assert line.strip() in text
    attack = next(s for s in case.receipt["stages"] if s["name"] == "break_my_fix")["evidence"]
    assert f"Break My Fix: {attack['inputs_tried']:,} inputs" in text
    assert f"Run time {site_receipts.run_time(case)}" in text
    assert f"{case.receipt['llm']['calls']} model calls" in text
    added = re.findall(r'<div class="ln ln-add">(.*?)</div>', PAGE.read_text(encoding="utf-8"))
    diff = next(d for d in case.diffs if d.path == site_home.REPLAY_FILE)
    assert [a.strip() for a in added] == [ln[1:].strip() for ln in diff.lines if ln[0] == "+"]


def test_the_finding_test_is_the_one_tracefix_wrote() -> None:
    case = site_receipts.load(site_home.REPLAY)
    finding = case.receipt["findings"][0]
    written = dict(case.written)[finding["file"]]
    assert site_home.finding_fields(case)["finding_test"].startswith("from ")
    for line in written[written.index("from ") :].splitlines():
        assert line.strip() in _page_text()


def test_each_tab_reports_its_receipts_level() -> None:
    page = PAGE.read_text(encoding="utf-8")
    found = re.search(r'<script type="application/json" id="moves-data">(.*?)</script>', page, re.S)
    assert found is not None
    tabs = json.loads(found.group(1))
    assert [t["case"] for t in tabs] == [name for name, _ in site_home.MOVES]
    for tab in tabs:
        level = site_receipts.load(tab["case"]).level
        assert tab["finds"].endswith(f"Level: {level}.")
    # The Butterfly's receipt is a counterexample, not "at most L2" (council 2026-11-07).
    assert "at most L2" not in _page_text()


def test_the_tab_data_cannot_close_its_script_element(tmp_path: Path) -> None:
    receipts, fixtures = tmp_path / "receipts", tmp_path / "fixtures"
    for name, _ in site_home.MOVES:
        shutil.copytree(site_receipts.RECEIPTS / name, receipts / name)
        shutil.copytree(site_receipts.FIXTURES / name, fixtures / name)
    path = receipts / "wrong_but_green" / "receipt.json"
    found = json.loads(path.read_text(encoding="utf-8"))
    found["issue"]["title"] = "</script><script>alert(1)</script>"
    path.write_text(json.dumps(found), encoding="utf-8")
    tabs = site_home.moves(receipts, fixtures)
    data = site_home._script_json(tabs)
    assert "<" not in data and json.loads(data)[0]["issue"] == found["issue"]["title"]


def test_the_rule_line_no_longer_overclaims() -> None:
    text = _page_text()
    assert f"rests on anyone{APOS}s opinion" not in text
    assert "Some of what runs was written by a model, and the receipt says which" in text


def test_the_top_rung_says_no_real_fix_got_there_until_one_does(tmp_path: Path) -> None:
    data = _copy_data(tmp_path)
    note = site_home.standing_fields(data)["top_rung_note"]
    assert note.startswith(" No real correct fix has reached L3 yet: 0 of")
    assert note.strip() in _page_text()
    path = data / "benchmark.json"
    found = json.loads(path.read_text(encoding="ascii"))
    found["slice1"]["gold"]["at_least_l3"]["n"] = 1
    path.write_text(json.dumps(found), encoding="ascii")
    assert site_home.standing_fields(data)["top_rung_note"] == ""


def test_the_requirements_come_from_pyproject_and_the_code() -> None:
    pyproject = tomllib.loads(site_home.PYPROJECT.read_text(encoding="utf-8"))
    found = site_home.requirement_fields()
    assert pyproject["project"]["requires-python"] == f">={found['python_min']}"
    assert found["project_python_min"] == ".".join(map(str, interpreter.MIN_PYTHON))
    text = _page_text()
    assert f"Python {found['python_min']}+, git {found['git_min']}+" in text


def test_the_home_page_cut_moved_its_parts_to_method_one_click_away() -> None:
    """DECISIONS 2026-11-14 "Home page cut": the fixture picker and the receipt on a pull request
    are on the Method page; the home page links to each of them."""
    page = PAGE.read_text(encoding="utf-8")
    for gone in ("data-climb", 'id="climb-data"', 'id="loop"', 'id="ltabs"'):
        assert gone not in page
    assert 'href="method/#ladder"' in page and 'href="method/#loop"' in page
    method = build_site.SITE / "method" / "index.html"
    ids = re.findall(r'\bid="([\w-]+)"', method.read_text(encoding="utf-8"))
    assert {"ladder", "loop", "climb-data", "ltabs"} <= set(ids)


def test_the_cut_sections_are_gone_and_one_click_away() -> None:
    page = PAGE.read_text(encoding="utf-8")
    for gone in ('id="run-out"', 'class="keys"', 'class="fixtures"', 'href="#how"'):
        assert gone not in page
    for link in ('href="receipts/partial_fix/"', 'href="benchmark/"', 'href="method/"'):
        assert link in page


def test_the_tab_diff_scrolls_by_keyboard() -> None:
    """On a narrow screen the tabs' diff scrolls sideways, so a keyboard must reach it (S8, axe
    `scrollable-region-focusable` at 320px)."""
    page = PAGE.read_text(encoding="utf-8")
    assert re.search(
        r'<div id="mv-diff" class="lines" tabindex="0" role="region" aria-labelledby="mv-file">',
        page,
    )
    assert 'id="mv-file"' in page


def test_the_attack_grid_is_one_tab_stop_and_speaks_once() -> None:
    """Council D4: the grid's inputs were a Tab stop each and its tally a live region that spoke
    for every input. Now one input holds the Tab stop (arrows move it) and only a hidden line, set
    at the start and the end of a replay, is live."""
    page = PAGE.read_text(encoding="utf-8")
    assert re.search(r'<p id="tally" class="label"(?![^>]*aria-live)[^>]*>', page)
    assert '<p id="tally-say" class="sr-only" aria-live="polite"></p>' in page
    home_js = (build_site.SITE / "assets" / "home.js").read_text(encoding="utf-8")
    assert "b.tabIndex = i === 0 ? 0 : -1" in home_js
    for key in ("'ArrowRight'", "'ArrowLeft'", "'ArrowDown'", "'ArrowUp'", "'Home'", "'End'"):
        assert key in home_js


REPO = Path(__file__).resolve().parent.parent
HOME_JS = build_site.SITE / "assets" / "home.js"
FIXTURE_CONFIG = Path("tests/fixtures/partial_fix/head/src/svc/config.py")


def test_the_replays_port_range_is_the_fixtures() -> None:
    # home.js re-implements parse_port to replay it in the browser; its range must stay the
    # fixture's MIN_PORT..MAX_PORT (verifier S4, website S9).
    config = (REPO / FIXTURE_CONFIG).read_text(encoding="utf-8")
    low = re.search(r"^MIN_PORT = (\d+)$", config, re.M)
    high = re.search(r"^MAX_PORT = (\d+)$", config, re.M)
    assert low and high
    js = HOME_JS.read_text(encoding="utf-8")
    assert f"n >= {low.group(1)} && n <= {high.group(1)}" in js
    assert f"between {low.group(1)} and {high.group(1)}" in js


def test_the_action_snippet_pins_what_the_example_workflow_pins() -> None:
    example = (REPO / "docs/examples/tracefix.yml").read_text(encoding="utf-8")
    pins = re.findall(r"uses: ([\w./-]+@[0-9a-f]{40})", example)
    assert len(pins) == 3
    js = HOME_JS.read_text(encoding="utf-8")
    assert re.findall(r"uses: ([\w./-]+@[0-9a-f]{40})", js) == pins


# ---- S10: the standing drawn, the receipt on a pull request, the field to try a value ----


def _marks(figure: str) -> list[str]:
    return re.findall(r'<i class="mk mk-(\w+)" style="--n:\d+"></i>', figure)


def test_where_it_stands_is_drawn_from_the_sentences_counts() -> None:
    _, benchmark, _ = site_benchmark.load()
    section = benchmark[site_benchmark.standing_slice(benchmark)]
    wrong, own = section["agent_wrong"], section["own_mistake"]
    _, fixes = site_benchmark.correct(section)
    page = PAGE.read_text(encoding="utf-8")
    assert site_home.standing_marks() in page
    first, second = re.findall(r'<figure class="tally".*?</figure>', page, re.S)
    # One mark per fix: the wrong agent fixes, then the correct ones.
    caught, passed = wrong["detection"]["n"], wrong["false_pass_l2"]["n"]
    assert len(_marks(first)) == wrong["detection"]["of"]
    assert _marks(first).count("cx") == own["n"]
    assert _marks(first).count("cxo") == caught - own["n"]
    assert _marks(first).count("l2") == passed
    assert _marks(first).count("low") == wrong["levels"]["L0"] + wrong["levels"]["L1"]
    assert len(_marks(second)) == fixes["false_alarm"]["of"]
    assert _marks(second).count("cxo") == fixes["false_alarm"]["n"]
    assert _marks(second).count("cx") + _marks(second).count("cxo") == fixes["counterexample"]["n"]
    assert _marks(second).count("l2") == fixes["at_least_l2"]["n"]
    # The key says every count in words (the marks themselves are hidden from a screen reader).
    text = _page_text()
    assert f"{own['n']} counterexample that rests on the agent{APOS}s own mistake" in text
    assert f"{passed} reached L2: a wrong fix that looked guarded" in text
    assert (
        f"{fixes['false_alarm']['n']} false alarms: a counterexample that was not a real bug"
        in text
    )
    assert f"{fixes['real_bug_in_gold']['n']} of them labelled a real bug in the fix" in text
    assert '<div class="marks" style="--cols:10" aria-hidden="true">' in first


def test_marks_that_do_not_add_up_stop_the_build(tmp_path: Path) -> None:
    data = _copy_data(tmp_path)
    path = data / "benchmark.json"
    found = json.loads(path.read_text(encoding="ascii"))
    name = site_benchmark.standing_slice(found)
    found[name]["agent_wrong"]["false_pass_l2"]["n"] += 1
    path.write_text(json.dumps(found), encoding="ascii")
    with pytest.raises(ValueError, match="do not add up"):
        site_home.standing_marks(data)


def test_a_slice_without_the_benchmarks_reading_stops_the_build(tmp_path: Path) -> None:
    # Without "N of those M rests on the agent's own mistake" no mark may claim a real catch.
    data = _copy_data(tmp_path)
    path = data / "benchmark.json"
    found = json.loads(path.read_text(encoding="ascii"))
    del found[site_benchmark.standing_slice(found)]["own_mistake"]
    path.write_text(json.dumps(found), encoding="ascii")
    with pytest.raises(ValueError, match="own_mistake"):
        site_home.standing_marks(data)


def test_the_new_parts_read_without_javascript() -> None:
    """Without JavaScript the controls that need a script (the field to try a value) stay hidden.
    (The receipt-on-a-pull-request panels moved to the Method page: tests/test_site_method.py.)"""
    page = PAGE.read_text(encoding="utf-8")
    assert '<form id="try" class="try" hidden>' in page
    assert "tryForm.hidden = false" in HOME_JS.read_text(encoding="utf-8")


def test_the_field_judges_a_value_the_way_the_replay_does() -> None:
    """The field runs the visitor's value through the same ported function and the same contract
    as the replay, and says so when the docstring promises nothing or the port does not model the
    text. Its behaviour is checked in a browser by scripts/site_browser_check.js (s10)."""
    js = HOME_JS.read_text(encoding="utf-8")
    judge = js[js.index("function judge(raw)") : js.index("function paintOwn()")]
    assert "var got = fixedCode(raw), want = contract(raw);" in judge
    assert "if (show(got) !== show(want))" in judge
    assert "makes no promise about text that is not a number, so this is not a finding" in judge
    assert "models plain ASCII text only" in judge
    # The result is spoken once typing pauses, through the form's <output>.
    page = PAGE.read_text(encoding="utf-8")
    assert '<output id="try-out" class="sr-only" for="try-in"></output>' in page


# What the field may be given: every text of up to three of these pieces (the port models ASCII).
PORT_PIECES = ("", " ", "\t", "\n", "0", "8", "80", "65535", "65536", "+", "-", "_", "a", "'", '"')
NODE_HARNESS = """
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const port = src.slice(src.indexOf('function pyRepr'), src.indexOf('var RESULTS'));
const m = new Function(port + '; return { pyRepr: pyRepr, fixedCode: fixedCode };')();
const out = JSON.parse(fs.readFileSync(0, 'utf8')).map(function (raw) {
  const got = m.fixedCode(raw);
  return [m.pyRepr(raw), got.err ? got.err + ': ' + got.msg : 'returns ' + got.val];
});
process.stdout.write(JSON.stringify(out));
"""


def _python_says(parse_port: Callable[[str | None], int], raw: str | None) -> str:
    try:
        return f"returns {parse_port(raw)}"
    except Exception as error:
        return f"{type(error).__name__}: {error}"


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node to run home.js's functions")
def test_the_port_agrees_with_the_fixtures_python(tmp_path: Path) -> None:
    """home.js says its parse_port is the fixture's, "ported line for line": the same result, the
    same error and message, and the same repr of the input, for every text in the table."""
    spec = importlib.util.spec_from_file_location("svc_config", REPO / FIXTURE_CONFIG)
    assert spec is not None and spec.loader is not None
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    texts = sorted({a + b + c for a in PORT_PIECES for b in PORT_PIECES for c in PORT_PIECES})
    cases: list[str | None] = [None, *texts]
    harness = tmp_path / "port.js"
    harness.write_text(NODE_HARNESS, encoding="utf-8")
    done = subprocess.run(
        ["node", str(harness), str(HOME_JS)],
        input=json.dumps(cases), capture_output=True, text=True, encoding="utf-8", check=True,
        timeout=60,
    )  # fmt: skip
    got = json.loads(done.stdout)
    want = [[repr(raw), _python_says(config.parse_port, raw)] for raw in cases]
    assert len(got) == len(want) > 1000
    assert [(c, g) for c, g, w in zip(cases, got, want, strict=True) if g != w] == []


def test_each_tab_has_an_address() -> None:
    page = PAGE.read_text(encoding="utf-8")
    ids = re.findall(r'<button class="move" type="button" role="tab" id="([\w-]+)"', page)
    assert ids == ["butterfly", "hard-code", "lawyer"]
    assert 'id="case" class="case" role="tabpanel" aria-labelledby="butterfly"' in page
    js = HOME_JS.read_text(encoding="utf-8")
    assert "history.replaceState(null, '', '#' + button.id)" in js
    assert "window.addEventListener('hashchange', moveFromHash)" in js

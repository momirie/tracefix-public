"""scripts/site_benchmark.py: the Benchmark page's numbers all come from docs/landing/_data/,
the page's own source types none, and every gate and every miss is on the built page."""

from __future__ import annotations

import json
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path

import build_site
import pytest
import site_benchmark

SOURCE = build_site.SRC / "pages" / "benchmark.html"
BUILT = build_site.SITE / "benchmark" / "index.html"


class _Text(HTMLParser):
    """The text a visitor reads (no tags, attributes or comments)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _text(html: str) -> str:
    parser = _Text()
    parser.feed(html)
    return " ".join(parser.parts)


def _copy_data(tmp_path: Path) -> Path:
    data = tmp_path / "_data"
    shutil.copytree(site_benchmark.DATA, data, ignore=shutil.ignore_patterns("receipts"))
    return data


def test_the_page_source_types_no_number() -> None:
    # The site rule: a number on the page comes through a {{hole}}. Level names are labels.
    text = re.sub(r"\{\{[a-z_]+\}\}", "", _text(SOURCE.read_text(encoding="utf-8")))
    text = re.sub(r"\bL[0-4]\b", "", text)
    assert re.findall(r".{0,20}\d.{0,20}", text) == []


@pytest.mark.parametrize(
    ("n", "of", "want"),
    [(3, 19, "3/19 (16%)"), (1, 8, "1/8 (13%)"), (0, 85, "0/85 (0%)"), (0, 0, "not measured")],
)
def test_rates_round_halves_up_and_nothing_measured_says_so(n: int, of: int, want: str) -> None:
    assert site_benchmark.rate({"n": n, "of": of}) == want


def test_every_gate_is_on_the_page_with_its_latest_result_and_target() -> None:
    gates, _, _ = site_benchmark.load()
    text = _text(BUILT.read_text(encoding="utf-8"))
    latest = gates["columns"][-3]
    for gate in gates["gates"]:
        for part in (f"Gate {gate['number']}", gate["title"], gate["target"], gate["status"]):
            assert part in text
        assert gate["results"][latest] in text
    assert f"{gates['holding']} of {len(gates['gates'])} hold" in text


def test_every_miss_links_its_receipt() -> None:
    _, _, found = site_benchmark.load()
    html = BUILT.read_text(encoding="utf-8")
    assert found["misses"]
    for miss in found["misses"]:
        assert f'href="{site_benchmark.GITHUB}{miss["receipt"]}"' in html
    assert html.count('class="miss"') == len(found["misses"])


def test_every_slice_fills_every_results_row() -> None:
    _, benchmark, _ = site_benchmark.load()
    rows = [dict(site_benchmark._rows(benchmark[n])) for n in site_benchmark.slices(benchmark)]
    assert all(r.keys() == rows[0].keys() for r in rows)
    first = rows[-1]  # slice 1: no agent fixes, gold is the only correct fix
    assert first["Wrong agent fixes caught (COUNTEREXAMPLE)"] == "not measured"
    assert first["Correct fixes with a false alarm (developer label)"].endswith(", gold only")


def test_the_level_counts_match_the_summary() -> None:
    _, benchmark, _ = site_benchmark.load()
    table = site_benchmark.level_table({"columns": []}, benchmark, "slice2")
    levels = benchmark["slice2"]["agent_wrong"]["levels"]
    counts = [str(levels[lv]) for lv in site_benchmark.LEVELS]
    total = str(sum(levels.values()))
    row = re.search(r"Wrong agent fix</span>.*?</tr>", table)
    assert row is not None
    assert re.findall(r"<td[^>]*>(\d+)</td>", row.group(0)) == [*counts, total]


def test_data_text_is_escaped(tmp_path: Path) -> None:
    data = _copy_data(tmp_path)
    path = data / "misses.json"
    found = json.loads(path.read_text(encoding="ascii"))
    found["misses"][0]["notes"] = ['<script>alert("x")</script>']
    path.write_text(json.dumps(found), encoding="ascii")
    html = site_benchmark.fields(data)["misses_false"] + site_benchmark.fields(data)["misses_wrong"]
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_the_ladder_note_goes_once_a_correct_fix_reaches_l3(tmp_path: Path) -> None:
    data = _copy_data(tmp_path)
    assert site_benchmark.fields(data)["ladder_note"].startswith("No correct fix has reached L3")
    path = data / "benchmark.json"
    found = json.loads(path.read_text(encoding="ascii"))
    found["slice1"]["gold"]["at_least_l3"]["n"] = 1
    path.write_text(json.dumps(found), encoding="ascii")
    assert site_benchmark.fields(data)["ladder_note"] == ""


def test_the_limits_come_from_the_harness() -> None:
    from bench import choose, prepare

    found = site_benchmark.fields()
    assert found["per_repo"] == str(choose.PER_REPO)
    assert found["suite_cap"] == f"{prepare.SUITE_CAP_S} s"
    assert found["verify_timeout"] == f"{prepare.VERIFY_TIMEOUT_S / 3600:g} hours"


def test_the_standing_carries_the_own_mistake_caveat(tmp_path: Path) -> None:
    gates, benchmark, _ = site_benchmark.load()
    caveat = "but only 1 of those 6 rests on the agent\N{RIGHT SINGLE QUOTATION MARK}s own mistake"
    assert f"{caveat}; 4 still reached L2" in site_benchmark.standing(gates, benchmark)
    data = _copy_data(tmp_path)
    path = data / "benchmark.json"
    found = json.loads(path.read_text(encoding="ascii"))
    found["slice2"]["own_mistake"] = {"n": 6, "of": 6}
    path.write_text(json.dumps(found), encoding="ascii")
    gates, benchmark, _ = site_benchmark.load(data)
    assert "a counterexample, and 4 still reached L2" in site_benchmark.standing(gates, benchmark)


def test_the_lede_does_not_claim_the_projects_were_never_seen() -> None:
    assert "never seen" not in SOURCE.read_text(encoding="utf-8")

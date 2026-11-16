"""scripts/site_data.py: the website's numbers come from the repo. The committed data equals a
fresh run, the release gates parse from docs/ROADMAP.md, and the misses agree with the benchmark
summaries they are read beside."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import site_data

ROOT = Path(__file__).parent.parent

TABLE = """# Roadmap

## Release gate

| # | Gate | Slice 1 (20 Oct 2026) | Target | Status |
|---|---|---|---|---|
| 1 | **Certifies correct fixes**: gold fixes at ≥ L2 | 5/19 (26%) | ≥ 50% | Open |
| 2 | **Few false alarms**: correct fixes given a false COUNTEREXAMPLE | 1/40 (3%) | ≤ 5% | Holds |

## Pace
"""


def test_committed_data_equals_a_fresh_run() -> None:
    assert site_data.stale() == [], "run: uv run python scripts/site_data.py"


def test_gates_parse_row_by_row() -> None:
    found = site_data.gates(TABLE)
    assert found["columns"] == ["#", "Gate", "Slice 1 (20 Oct 2026)", "Target", "Status"]
    assert found["holding"] == 1
    first = found["gates"][0]
    assert first == {
        "number": 1,
        "title": "Certifies correct fixes",
        "measures": "gold fixes at ≥ L2",
        "results": {"Slice 1 (20 Oct 2026)": "5/19 (26%)"},
        "target": "≥ 50%",
        "status": "Open",
        "holds": False,
    }


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (("| Open |", "| Nearly |"), "starts with none of"),
        (("**Certifies correct fixes**: ", "Certifies correct fixes "), "**Title**"),
        (("## Release gate", "## Gates"), "no '## Release gate' section"),
        (("| Target |", "| Goal |"), "unexpected release gate columns"),
    ],
)
def test_a_gate_table_in_another_shape_stops_the_script(
    change: tuple[str, str], message: str
) -> None:
    with pytest.raises(site_data.SiteDataError, match=message.replace("*", r"\*")):
        site_data.gates(TABLE.replace(*change))


def test_the_real_gate_table_has_seven_gates_none_holding_yet() -> None:
    found = site_data.gates((ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8"))
    assert [g["number"] for g in found["gates"]] == [1, 2, 3, 4, 5, 6, 7]
    assert found["holding"] == sum(g["status"].startswith("Holds") for g in found["gates"])


@pytest.mark.parametrize("slice_name", site_data.SLICES)
def test_misses_agree_with_the_summary_and_their_receipts_exist(slice_name: str) -> None:
    found = site_data.misses(slice_name)
    site_data._check_counts(slice_name, found, site_data.summary(slice_name))
    for miss in found:
        assert (ROOT / miss["receipt"]).is_file()
        receipt = json.loads((ROOT / miss["receipt"]).with_suffix(".json").read_text("utf-8"))
        assert receipt["level"] == miss["level"]
        if miss["why"] == "false_alarm":
            assert miss["level"] == "COUNTEREXAMPLE" and miss["notes"]


def test_a_count_that_disagrees_with_the_summary_stops_the_script() -> None:
    sections = site_data.summary("slice2")
    found = site_data.misses("slice2")
    with pytest.raises(site_data.SiteDataError, match=r"differ from summary\.json"):
        site_data._check_counts("slice2", found[1:], sections)


def test_check_flag_reports_a_stale_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, text in site_data.files().items():
        (tmp_path / name).write_text(text, encoding="ascii", newline="\n")
    monkeypatch.setattr(site_data, "OUT", tmp_path)
    assert site_data.main(["--check"]) == 0
    (tmp_path / "gates.json").write_text("{}\n", encoding="ascii")
    assert site_data.main(["--check"]) == 1
    assert "out of date: docs/landing/_data/gates.json" in capsys.readouterr().out


READING = """## Results: slice 2 (November 2026, dev split)

- **A brake.** It kept 16 of 20 wrong agent fixes from looking verified, but caught only 6, and
  by our own runs only 1 of those 6
  rests on what the agent got wrong: dissect.cstruct-88.

## Caveats
"""
SECTIONS = {"agent_wrong": {"detection": {"n": 6, "of": 20}}}


def test_the_own_mistake_reading_comes_from_benchmark_md() -> None:
    assert site_data.own_mistake(READING, "slice2", SECTIONS) == {"n": 1, "of": 6}
    assert site_data.own_mistake(READING, "slice1", {"gold": {}}) is None


@pytest.mark.parametrize(
    ("reading", "message"),
    [
        (READING.replace("caught only 6", "caught only 5"), "summary.json counts 6"),
        (READING.replace("rests on what", "rest on what"), "no 'only N of those M rests on'"),
        (READING.replace("slice 2", "slice 3"), "no '## Results: slice 2' section"),
    ],
)
def test_an_own_mistake_reading_that_disagrees_stops_the_script(reading: str, message: str) -> None:
    with pytest.raises(site_data.SiteDataError, match=re.escape(message)):
        site_data.own_mistake(reading, "slice2", SECTIONS)


def test_the_reading_is_outside_the_next_slices_section() -> None:
    later = READING.replace("## Caveats", "## Results: slice 3\n\nby our own runs only 2 of those")
    assert site_data.own_mistake(later, "slice2", SECTIONS) == {"n": 1, "of": 6}

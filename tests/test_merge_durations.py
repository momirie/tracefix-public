"""scripts/merge_durations.py: one Windows durations file from what each CI job measured."""

from __future__ import annotations

import json
from pathlib import Path

import merge_durations as md
import pytest

BASE = {"t::a": 1.0, "t::b": 2.0, "t::c": 3.0}


def write(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_each_test_takes_the_time_of_the_job_that_ran_it() -> None:
    job1 = {**BASE, "t::a": 10.0}  # group 1 ran a
    job2 = {**BASE, "t::b": 20.0, "t::new": 5.0}  # group 2 ran b and a test BASE didn't know
    merged, twice = md.merge(BASE, [job1, job2])
    assert merged == {"t::a": 10.0, "t::b": 20.0, "t::c": 3.0, "t::new": 5.0}
    assert twice == []


def test_a_test_no_job_measured_keeps_its_old_time() -> None:
    """A job cut off by its timeout never writes its file: its tests keep BASE's times."""
    merged, _ = md.merge(BASE, [{**BASE, "t::a": 9.0}])
    assert merged["t::b"] == 2.0 and merged["t::c"] == 3.0


def test_a_test_measured_twice_keeps_the_longer_time_and_is_reported() -> None:
    merged, twice = md.merge(BASE, [{**BASE, "t::a": 4.0}, {**BASE, "t::a": 7.0}])
    assert merged["t::a"] == 7.0 and twice == ["t::a"]
    merged, twice = md.merge(BASE, [{**BASE, "t::a": 7.0}, {**BASE, "t::a": 4.0}])
    assert merged["t::a"] == 7.0 and twice == ["t::a"]


def test_the_script_writes_pytest_splits_layout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = write(tmp_path / "base.json", BASE)
    job = write(tmp_path / "job1.json", {**BASE, "t::c": 30.0})
    out = tmp_path / "merged" / "out.json"  # its folder is made too
    assert md.main([str(base), str(job), "--out", str(out)]) == 0
    text = out.read_bytes().decode("utf-8")
    assert "\r" not in text
    assert text == json.dumps({**BASE, "t::c": 30.0}, sort_keys=True, indent=4)
    assert "job1.json: 1 tests, 0.5 min" in capsys.readouterr().out


@pytest.mark.parametrize("data", [[1, 2], {"t::a": "slow"}, {"t::a": None}])
def test_a_file_that_is_not_a_durations_map_is_refused(tmp_path: Path, data: object) -> None:
    with pytest.raises(ValueError, match="not a durations file"):
        md.load(write(tmp_path / "bad.json", data))

"""scripts/check.py's test phases: the parallel pass, the acceptance cases with few workers, then
the serial tests. The acceptance cases are load-sensitive: beside the whole suite on every core,
Break My Fix on method_good hit its 120 s safety limit and the case failed (docs/NOTES.md)."""

import subprocess
import sys
from pathlib import Path

import check
import yaml

ROOT = Path(__file__).parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
MAX_ACCEPTANCE_WORKERS = 4  # measured: method_good's attack run took 89 s of 120 at -n 4


def phases() -> dict[str, list[str]]:
    """check.py's pytest runs, by name, in order."""
    return {name: cmd for name, cmd in check.CHECKS if cmd[0] == "pytest"}


def collected(*args: str) -> set[str]:
    """The test ids pytest collects with these arguments (no test runs)."""
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )  # fmt: skip
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    return {line for line in done.stdout.splitlines() if "::" in line}


def test_the_acceptance_cases_run_in_a_phase_of_their_own_with_few_workers() -> None:
    tests = phases()
    assert list(tests) == ["tests", "tests-acceptance", "tests-serial"]  # in this order
    main = tests["tests"]
    assert main[main.index("-m") + 1] == check.MAIN_TESTS == "not serial and not acceptance"
    assert main[main.index("-n") + 1] == "auto"
    acceptance = tests["tests-acceptance"]
    assert acceptance[acceptance.index("-m") + 1] == "acceptance"
    assert 1 <= int(acceptance[acceptance.index("-n") + 1]) <= MAX_ACCEPTANCE_WORKERS
    serial = tests["tests-serial"]
    assert serial[serial.index("-m") + 1] == "serial" and "-n" not in serial


def test_the_acceptance_marker_selects_exactly_the_end_to_end_cases() -> None:
    """Every test of test_pipeline_recorded.py and nothing else, none of them serial (they would
    run twice); and at least one per CI group, or a group's acceptance step collects nothing
    and fails (pytest exits 5)."""
    marked = collected("-m", "acceptance and not serial", "tests")
    assert marked == collected("tests/test_pipeline_recorded.py")
    splits = [
        yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))["jobs"]["check"]["with"][
            "splits"
        ]
        for name in ("ci.yml", "ci-windows.yml")
    ]
    assert len(marked) >= max(splits)

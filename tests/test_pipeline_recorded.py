"""M8 acceptance: `tracefix verify` end to end on every fixture, graded from receipt.json alone
against expected.json (ground truth).

The models' answers are replayed from tests/recordings; everything else is real: the CLI, the
pipeline, copies, pytest runs, the tamper watch. A missing recording is a failure here (never a
quietly skipped stage).

Record missing answers (costs money, needs ANTHROPIC_API_KEY); existing ones are replayed:
    TRACEFIX_RECORD=1 uv run pytest tests/test_pipeline_recorded.py -k CASE
"""

import json
from pathlib import Path
from typing import Any

import make_fixtures
import pytest
from conftest import old_python
from test_fixtures import load_expected
from test_guard_recorded import expected, provider

from tracefix.attack import ADVERSARY_SAMPLES
from tracefix.attack_runtime import from_source
from tracefix.cli import main
from tracefix.guard import MUTATOR_CALLS
from tracefix.judge import JUDGE_CALLS, JUDGE_SAMPLES
from tracefix.ladder import EvidenceLevel, rank
from tracefix.receipt_md import MAX_LINES, MAX_MAIN_LINES, text
from tracefix.repro import BLIND_ATTEMPTS, MAX_ATTEMPTS
from tracefix.sandbox import BASIC_WARNING

# A phase of their own with few workers (scripts/check.py, CI): beside the whole parallel suite,
# Break My Fix on method_good hit its 120 s safety limit (docs/NOTES.md, load-sensitive).
pytestmark = pytest.mark.acceptance

CASES = sorted(make_fixtures.ALL_CASES)  # the older-Python cases run with --python
# The most calls one run may make: the Reproducer's attempts, the mutator's request and one
# follow-up, the adversary's (ADVERSARY_SAMPLES and one follow-up), the Judge's labels, the
# blind test's attempts, and the summary.
MAX_CALLS = (
    MAX_ATTEMPTS + MUTATOR_CALLS + ADVERSARY_SAMPLES + 1 + JUDGE_SAMPLES * JUDGE_CALLS
    + BLIND_ATTEMPTS + 1
)  # fmt: skip


def verify(case: str, repo: Path, out: Path) -> dict[str, Any]:
    issue = make_fixtures.FIXTURES_DIR / case / "ISSUE.md"
    argv = ["verify", "--repo", str(repo), "--base", "base", "--head", "head",
            "--issue", str(issue), "--out", str(out)]  # fmt: skip
    version = load_expected(case).get("python")
    if version is not None:
        argv += ["--python", str(old_python(version))]
    assert main(argv, provider=provider()) == 0
    receipt: dict[str, Any] = json.loads((out / "receipt.json").read_text("utf-8"))
    return receipt


def summary(receipt: dict[str, Any]) -> str:
    """What a failure shows: the level and why, each stage, and everything found."""
    lines = [f"{receipt['status']} {receipt['level']}: {receipt['level_reasons']}"]
    for s in receipt["stages"]:
        lines.append(f"  {s['name']}: {s['status']} {s['reason'][:200]} {s['error'] or ''}")
    lines += [f"  finding {f['function']} {f['input']} {f['outcome']} (expected {f['expected']})"
              for f in receipt["findings"]]  # fmt: skip
    for c in receipt["behaviour_changes"]:
        labels = [(x["change"], x["label"]) for x in c["labels"]]
        examples = [(e["call"], e["before"], e["after"]) for e in c["examples"]]
        lines.append(f"  change {c['function']} {c['kind']} {examples} {labels}")
    lines += [f"  flag {f['kind']} {f['file']} {f['detail']!r}" for f in receipt["integrity_flags"]]
    lines += [f"  regression {r['file']} {r['test']}" for r in receipt["regressions"]]
    lines += [f"  problem {p['stage']} {p['role']} {p['kind']}" for p in receipt["llm"]["problems"]]
    return "\n".join(lines)


def level_within(level: str, bound: dict[str, str]) -> bool:
    got = rank(EvidenceLevel(level))
    [(how, wanted)] = bound.items()
    want = rank(EvidenceLevel(wanted))
    return {"exactly": got == want, "at_least": got >= want, "at_most": got <= want}[how]


def stage(receipt: dict[str, Any], name: str) -> dict[str, Any]:
    [entry] = [s for s in receipt["stages"] if s["name"] == name]
    return entry


def finding_matches(f: dict[str, Any], must: dict[str, Any]) -> bool:
    """The expected counterexample: same function, the expected input (a method's input without
    "self" matches on any object), and the expected outcome ("ValueError": the type raised;
    "returns 29, not 28": the value and what was expected)."""
    if f["function"] != must["function"]:
        return False
    shown = {
        k: from_source(v) for k, v in f["input"].items() if k != "self" or "self" in must["input"]
    }
    if shown != must["input"]:
        return False
    outcome: str = must["outcome"]
    if outcome.startswith("returns "):
        value, _, should = outcome.removeprefix("returns ").partition(", not ")
        return f["outcome"] == f"returns {value}" and (not should or f["expected"] == should)
    return f["outcome"] == f"raises {outcome}" or f["outcome"].startswith(f"raises {outcome}: ")


def change_matches(c: dict[str, Any], must: dict[str, Any]) -> bool:
    """The expected behaviour change: same function, an example with the expected input and
    answers before and after the fix, and the expected label on the group."""
    if c["function"] != must["function"]:
        return False
    name = must["function"].rsplit(".", 1)[-1]
    call = f"{name}({', '.join(f'{k}={v!r}' for k, v in must['input'].items())})"
    before, after = f"returns {must['base']}", f"returns {must['head']}"
    shown = any(
        e["call"] == call and e["before"].startswith(before) and e["after"].startswith(after)
        for e in c["examples"]
    )
    return shown and any(x["label"] == must["label"] for x in c["labels"])


def found(receipt: dict[str, Any], must: dict[str, Any]) -> bool:
    kind = must["stage"]
    if kind == "environment":
        evidence = stage(receipt, "environment")["evidence"]
        return (evidence["error"], evidence["module"]) == (must["error"], must["module"])
    if kind == "reproduce":
        return bool(stage(receipt, "reproduce")["status"] == must["outcome"])
    if kind == "guard":
        findings = stage(receipt, "guard")["evidence"]["findings"]
        return any(f.startswith(f"{must['kind']}: ") and must["file"] in f for f in findings)
    if kind == "integrity":
        wanted = (must["kind"], must["file"], must["detail"])
        flags = receipt["integrity_flags"]
        return any((f["kind"], f["file"], f["detail"]) == wanted for f in flags)
    if kind == "break_my_fix":
        return any(finding_matches(f, must) for f in receipt["findings"])
    if kind == "behaviour_diff":
        return any(change_matches(c, must) for c in receipt["behaviour_changes"])
    raise AssertionError(f"unknown must_find stage {kind}")


ABSENT = {
    "break_my_fix_finding": lambda r: not r["findings"],
    "integrity_flag": lambda r: not r["integrity_flags"],
    "suspicious_behaviour_change": lambda r: (
        not any(x["label"] == "suspicious" for c in r["behaviour_changes"] for x in c["labels"])
    ),
}


def test_every_expectation_kind_is_graded() -> None:
    kinds = {m["stage"] for c in CASES for m in expected(c)["must_find"]}
    assert kinds == {"environment", "reproduce", "guard", "integrity", "break_my_fix",
                     "behaviour_diff"}  # fmt: skip
    assert {n for c in CASES for n in expected(c)["must_not_find"]} == set(ABSENT)


@pytest.mark.parametrize("case", CASES)
def test_verify_matches_expected_json(case: str, built: dict[str, Path], tmp_path: Path) -> None:
    out = tmp_path / "out"
    receipt = verify(case, built[case], out)
    answer = expected(case)
    why = summary(receipt)
    assert receipt["status"] == answer["status"], why
    assert level_within(receipt["level"], answer["level"]), why
    for name, status in answer["stages"].items():
        assert stage(receipt, name)["status"] == status, why
    for must in answer["must_find"]:
        assert found(receipt, must), f"{must}\n{why}"
    for absent in answer["must_not_find"]:
        assert ABSENT[absent](receipt), f"{absent}\n{why}"
    # Every stage ran as our code meant it to, every answer was recorded, within the call bound.
    assert not [s["name"] for s in receipt["stages"] if s["error"]], why
    assert not receipt["llm"]["problems"], why
    assert receipt["llm"]["calls"] <= MAX_CALLS, why
    # receipt.md: within its limits, and it says how isolated the run was.
    markdown = (out / "receipt.md").read_text("utf-8")
    lines = markdown.splitlines()
    assert len(lines) <= MAX_LINES
    assert lines.index("<details>") - 1 <= MAX_MAIN_LINES
    isolation = receipt["isolation"]
    assert f"**Isolation:** {isolation['level']}" in markdown
    assert (text(BASIC_WARNING) in markdown) == (isolation["level"] == "basic")
    # The project's Python is named exactly when it isn't Tracefix's own.
    version = load_expected(case).get("python")
    if version is None:
        assert isolation["python"] is None, isolation
    else:
        assert isolation["python"].startswith(f"{version}."), isolation

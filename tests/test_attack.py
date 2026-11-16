"""M6: the Break My Fix stage (attack.py), end to end with scripted adversary answers.

Everything but the model is real: copies, watched pytest runs, the in-run harness, probes and the
repro-file runs. Each test pins one rule of SPEC 2.6 (Decided in M6).
"""

import ast
import json
import sys
from pathlib import Path
from typing import Any

import make_fixtures
import pytest
from conftest import make_repo

from tracefix import attack
from tracefix.attack import AttackResult, AttackStatus, break_my_fix
from tracefix.attack_methods import ABSTRACT as ABSTRACT_WHY
from tracefix.attack_rules import Expectation
from tracefix.diffscope import compute_scope
from tracefix.llm import FakeProvider, LLMClient
from tracefix.prompts import adversary
from tracefix.repro import ReproResult, ReproStatus
from tracefix.runner import Attempt, FailureInfo, Outcome, RunResult
from tracefix.sandbox import sandbox_level
from tracefix.workspace import Workspace

PYPROJECT = '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n'
FIXTURE = ("base", "head")  # the fixture repos' tags; make_repo's are c0, c1


def prop(name: str, quote: str, **fields: Any) -> dict[str, Any]:
    base = {
        "function": "t1",
        "name": name,
        "kind": "returns",
        "claim": f"The {name} rule.",
        "source": "docstring",
        "quote": quote,
        "when": "True",
        "check": "",
        "expected": "",
        "exceptions": [],
        "transform": "",
    }
    return base | fields


def answer(*properties: dict[str, Any], **lists: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "properties": list(properties),
        "strategies": lists.get("strategies", []),
        "examples": lists.get("examples", []),
    }


def run(
    repo: Path,
    *answers: dict[str, Any] | str,
    issue: str = "",
    repro: ReproResult | None = None,
    refs: tuple[str, str] = ("c0", "c1"),
) -> tuple[AttackResult, FakeProvider]:
    provider = FakeProvider(list(answers))
    with Workspace(repo, *refs) as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        result = break_my_fix(ws, scope, repro, issue, LLMClient(provider))
        assert ws.copies == [ws.base, ws.head]  # nothing left behind
    return result, provider


def summary(result: AttackResult) -> str:
    lines = [f"{result.status}: {result.reason}"]
    lines += [
        f"  finding {f.function} {f.input} {f.outcome} | {f.relation}" for f in result.findings
    ]
    lines += [f"  pre {f.function} {f.input} | {f.relation}" for f in result.pre_existing]
    lines += [f"  discarded {d.input} {d.property}: {d.reason}" for d in result.discarded]
    lines += [f"  property {p.id or p.name} {p.status} {p.reason[:120]}" for p in result.properties]
    lines += [f"  note {n}" for n in result.notes]
    lines += [f"  run {label}: {r.outcome}" for label, r in result.runs]
    return "\n".join(lines)


def issue_of(case: str) -> str:
    return (make_fixtures.FIXTURES_DIR / case / "ISSUE.md").read_text(encoding="utf-8")


BLANK = prop(
    "blank",
    "if unset or blank, DEFAULT_PORT (8080) is used",
    when="raw is None or raw.strip() == ''",
    expected="DEFAULT_PORT",
)
GREGORIAN = prop(
    "gregorian",
    "That date doesn't exist.",
    source="issue",
    when="1 <= month <= 12 and year >= 1",
    expected="calendar.monthrange(year, month)[1]",
)
CEILING = prop(
    "ceiling",
    "how many pages are needed to show n_items",
    when="n_items >= 0 and per_page > 0",
    expected="-(-n_items // per_page)",
)
NEVER_RAISES = prop(
    "never-raises",
    "def total_pages(n_items: int, per_page: int) -> int:",
    kind="raises_only",
    source="signature",
)


# --- the acceptance cases, with scripted answers --------------------------------------------------


def test_partial_fix_blank_port_is_found_and_proven(built: dict[str, Path]) -> None:
    result, provider = run(
        built["partial_fix"], answer(BLANK), issue=issue_of("partial_fix"), refs=FIXTURE
    )
    assert result.status is AttackStatus.FOUND, summary(result)
    (finding,) = result.findings
    assert (finding.function, dict(finding.input)) == ("svc.config.parse_port", {"raw": "''"})
    assert finding.outcome["kind"] == "raised" and finding.outcome["type"] == "ValueError"
    # Base fails the same way, but the call runs the fix's new `if raw is None:` (Decided in M1).
    assert finding.relation.startswith("the same before the fix, but the failing call runs")
    assert finding.fix_lines_run == (("src/svc/config.py", (34,)),)
    assert (finding.path, finding.line) == ("src/svc/config.py", 34)  # where it is annotated
    assert finding.expect == Expectation(frozenset({"ValueError"}), False)  # raised in the code
    assert finding.base_outcome is not None and finding.base_outcome["type"] == "ValueError"
    assert finding.repro_run is not None and finding.repro_run.outcome is Outcome.FAILED
    assert len(finding.repro_run.attempts) == 1 + attack.FINDING_RERUNS  # failed every time
    assert finding.property is not None and finding.property.status == "counted"
    assert "result = parse_port(raw=raw)" in finding.repro_code
    # Other blank strings break it the same way; one property only, so nothing else is violated.
    assert (("raw", "' '"),) in finding.other_inputs and finding.also_violates == ()
    assert result.fix_lines == (("src/svc/config.py", (34, 35)),)
    # Nothing rejected: no follow-up call; the only other request is the independent second
    # sample (a fresh conversation, so no feedback in it).
    assert len(provider.requests) == 2
    assert len(provider.requests[1].messages) == 1
    assert adversary.SECOND_SAMPLE in provider.requests[1].messages[0].content


def test_special_cased_neighbouring_century_year_is_found(built: dict[str, Path]) -> None:
    year = {"function": "t1", "param": "year", "strategy": "st.integers(1, 3000)"}
    result, _ = run(
        built["special_cased"],
        answer(GREGORIAN, strategies=[year]),
        issue=issue_of("special_cased"),
        refs=FIXTURE,
    )
    assert result.status is AttackStatus.FOUND, summary(result)
    (finding,) = result.findings
    assert dict(finding.input) == {"year": "2200", "month": "2"} and finding.phase == "grid"
    assert finding.outcome == {"kind": "returned", "type": "int", "repr": "29"}
    assert finding.expected == "28"
    assert "import calendar" in finding.repro_code


def test_good_fix_has_no_finding_and_a_sloppy_property_is_contradicted(
    built: dict[str, Path],
) -> None:
    result, provider = run(
        built["good_fix"],
        answer(CEILING, NEVER_RAISES),
        answer(CEILING, NEVER_RAISES),
        issue=issue_of("good_fix"),
        refs=FIXTURE,
    )
    assert result.status is AttackStatus.NONE_FOUND, summary(result)
    assert not result.findings and not result.pre_existing
    statuses = {p.name: (p.status, p.reason) for p in result.properties}
    assert statuses["ceiling"] == ("counted", "")
    status, reason = statuses["never-raises"]
    assert status == "contradicted" and "tests/test_pagination.py::test_invalid_sizes" in reason
    assert result.inputs_tried >= attack.SEARCH_EXAMPLES  # the search spends its budget usefully
    # The follow-up told the model which project test contradicted its property.
    assert len(provider.requests) == 3  # the request, its follow-up, the second sample
    follow_up = provider.requests[1].messages[-1].content
    assert "contradicted" in follow_up
    assert "n_items=5, per_page=0, which raises ValueError" in follow_up


def test_a_docstring_example_counts_without_any_model_property(built: dict[str, Path]) -> None:
    # wrong_but_green documents bucket_of(-5, 10) == 0; the fix floors negatives (-10).
    result, _ = run(
        built["wrong_but_green"],
        answer(),
        answer(),  # nothing proposed: the follow-up asks again
        issue=issue_of("wrong_but_green"),
        refs=FIXTURE,
    )
    assert result.status is AttackStatus.FOUND, summary(result)
    finding = result.findings[0]
    assert dict(finding.input) == {"value": "-5", "width": "10"} and finding.phase == "doc"
    assert finding.property is not None and finding.property.origin == "docstring"
    assert finding.relation.startswith("new with the fix: before it, this input returns 0")


def test_a_target_that_cannot_import_is_inconclusive(built: dict[str, Path]) -> None:
    week = prop("week", "weeks start on Monday", check="1 <= result <= 53")
    result, _ = run(built["env_broken"], answer(week), refs=FIXTURE)
    assert result.status is AttackStatus.INCONCLUSIVE, summary(result)
    assert not result.findings
    assert any("could not be imported" in t.reason for t in result.targets)


# --- synthetic repos: one rule each ---------------------------------------------------------------


def repo_of(tmp_path: Path, base: dict[str, str], head: dict[str, str | None]) -> Path:
    files = {"pyproject.toml": PYPROJECT, "tests/__init__.py": "", **base}
    return make_repo(tmp_path / "repo", [files, head])


SIGN = '''\
def sign(x: int) -> int:
    """Return -1, 0 or 1: the sign of x."""
    if x > 100:
        return 1
    return 0 if x == 0 else 1
'''
SIGN_FIXED = SIGN.replace("if x > 100:", "if x > 1000:")
SIGN_PROP = prop("sign", "Return -1, 0 or 1: the sign of x.", when="x < 0", expected="-1")
EARLY_BUG = '''\
def sign(x: int) -> int:
    """Return -1, 0 or 1: the sign of x."""
    if x < 0:
        return 1
    if x == 7:
        return 7
    return 0 if x == 0 else 1
'''


def test_a_failure_the_fix_never_touches_is_pre_existing_not_counted(tmp_path: Path) -> None:
    # Negatives are wrong before and after the fix (which only fixes x == 7), and the failing
    # call returns before it reaches the fixed line: pre-existing, reported but not counted.
    head = EARLY_BUG.replace("        return 7\n", "        return 1\n")
    repo = repo_of(tmp_path, {"m.py": EARLY_BUG}, {"m.py": head})
    result, _ = run(repo, answer(SIGN_PROP))
    assert not result.findings, summary(result)
    pre = result.pre_existing[0]
    assert pre.relation.startswith("pre-existing:") and pre.fix_lines_run == ()
    assert (pre.path, pre.line) == ("m.py", 1)  # no fix line ran: the function's first line
    assert pre.outcome == {"kind": "returned", "type": "int", "repr": "1"}
    assert result.status is AttackStatus.NONE_FOUND


def test_the_same_failure_on_a_path_through_the_fix_counts(tmp_path: Path) -> None:
    # SIGN: negatives fall through the changed `if x > 1000:` line, so it counts (Decided in M1).
    repo = repo_of(tmp_path, {"m.py": SIGN}, {"m.py": SIGN_FIXED})
    result, _ = run(repo, answer(SIGN_PROP))
    assert result.status is AttackStatus.FOUND, summary(result)
    assert "runs the fix's line(s) 3" in result.findings[0].relation


def test_a_property_without_a_real_quote_is_rejected_and_the_model_hears_why(
    tmp_path: Path,
) -> None:
    repo = repo_of(tmp_path, {"m.py": SIGN}, {"m.py": SIGN_FIXED})
    made_up = SIGN_PROP | {"quote": "sign returns minus one for negatives", "name": "made-up"}
    result, provider = run(repo, answer(made_up), answer(SIGN_PROP))
    rejected = [p for p in result.properties if p.status == "rejected"]
    assert [p.name for p in rejected] == ["made-up"]
    assert "not found word for word" in rejected[0].reason
    assert "made-up" in provider.requests[1].messages[-1].content
    assert result.status is AttackStatus.FOUND, summary(result)  # the repaired property found it


COUNTER = '''\
import itertools

_calls = itertools.count()


def tag(x: int) -> list[int]:
    """Return [x, 0]."""
    return [x, next(_calls)]
'''


def test_an_outcome_a_fresh_call_does_not_repeat_is_discarded(tmp_path: Path) -> None:
    base = COUNTER.replace("[x, next", "[x + 0, next")
    repo = repo_of(tmp_path, {"m.py": base}, {"m.py": COUNTER})
    result, _ = run(repo, answer(prop("pair", "Return [x, 0].", expected="[x, 0]")))
    assert not result.findings, summary(result)
    assert result.discarded and all("not reproducible" in d.reason for d in result.discarded)


POINT = '''\
from dataclasses import dataclass


@dataclass
class Point:
    x: int


def norm(p: Point) -> int:
    """The distance from 0: never negative."""
    return p.x
'''


def test_an_input_that_cannot_be_written_as_code_is_discarded(tmp_path: Path) -> None:
    base = POINT.replace("return p.x", "return p.x + 0")
    repo = repo_of(tmp_path, {"m.py": base}, {"m.py": POINT})
    result, _ = run(repo, answer(prop("positive", "never negative", check="result >= 0")))
    assert not result.findings, summary(result)
    assert [d.reason for d in result.discarded] == ["its input cannot be written as code"]


def test_the_prs_own_test_disagreeing_is_noted_and_decides_nothing(tmp_path: Path) -> None:
    test = "from m import sign\n\n\ndef test_negative():\n    assert sign(-5) == 1\n"
    repo = repo_of(tmp_path, {"m.py": SIGN}, {"m.py": SIGN_FIXED, "tests/test_m.py": test})
    result, _ = run(repo, answer(SIGN_PROP))
    assert result.status is AttackStatus.FOUND, summary(result)
    (counted,) = [p for p in result.properties if p.name == "sign"]
    assert counted.status == "counted"
    assert counted.advisory == ("tests/test_m.py::test_negative",)


# --- methods (M7.5) -------------------------------------------------------------------------------

LISTENER = '''\
class Listener:
    def __init__(self, default_port: int = 8080) -> None:
        self.default_port = default_port

    def port(self, raw: str | None) -> int:
        """An unset (None) value gives the listener's default port."""
        return int(raw)
'''
LISTENER_PARTIAL = LISTENER.replace(
    "        return int(raw)",
    "        if raw is None:\n            return 8080\n        return int(raw)",
)
LISTENER_GOOD = LISTENER_PARTIAL.replace("return 8080", "return self.default_port")
UNSET = prop(
    "unset",
    "An unset (None) value gives the listener's default port.",
    when="raw is None",
    expected="self.default_port",
)
OBJECT_9000 = {
    "function": "t1",
    "args": [
        {"param": "self", "value": "Listener(default_port=9000)"},
        {"param": "raw", "value": "None"},
    ],
    "why": "a listener with its own default port",
}


def test_a_partial_method_fix_is_found_on_a_typical_object_and_proven(tmp_path: Path) -> None:
    # `when` doesn't name self, so made-up objects don't count (developer, 9 Oct 2026); the
    # model's typical object with its own default port does, and the repro file builds it.
    repo = repo_of(tmp_path, {"m.py": LISTENER}, {"m.py": LISTENER_PARTIAL})
    result, provider = run(repo, answer(UNSET, examples=[OBJECT_9000]))
    assert result.status is AttackStatus.FOUND, summary(result)
    (finding,) = result.findings
    assert finding.function == "m.Listener.port"
    # The object's code travels as a string literal, like any input (M7.5 plan, D2).
    assert dict(finding.input) == {"self": "'Listener(default_port=9000)'", "raw": "None"}
    assert finding.outcome == {"kind": "returned", "type": "int", "repr": "8080"}
    assert "self_after = Listener(default_port=9000)" in finding.repro_code
    assert "result = self_after.port(raw=raw)" in finding.repro_code
    assert finding.repro_run is not None and finding.repro_run.outcome is Outcome.FAILED
    # The model was told about the object, only because a method is attacked.
    request = provider.requests[0].messages[0].content
    assert "Listener.port" in request and "`self_after`" in request


def asynced(text: str) -> str:
    return text.replace("    def port(", "    async def port(")


def test_m11_an_async_method_is_awaited_and_its_repro_file_awaits_it(tmp_path: Path) -> None:
    # Until M11 (early) an async method was "not called yet" (param-1117, M10).
    repo = repo_of(tmp_path, {"m.py": asynced(LISTENER)}, {"m.py": asynced(LISTENER_PARTIAL)})
    result, _ = run(repo, answer(UNSET, examples=[OBJECT_9000]))
    assert result.status is AttackStatus.FOUND, summary(result)
    (finding,) = result.findings
    assert finding.outcome == {"kind": "returned", "type": "int", "repr": "8080"}  # the value
    assert "import asyncio" in finding.repro_code
    assert "result = asyncio.run(self_after.port(raw=raw))" in finding.repro_code
    assert finding.repro_run is not None and finding.repro_run.outcome is Outcome.FAILED


def test_m11_a_correct_async_method_fix_has_no_finding(tmp_path: Path) -> None:
    repo = repo_of(tmp_path, {"m.py": asynced(LISTENER)}, {"m.py": asynced(LISTENER_GOOD)})
    result, _ = run(repo, answer(UNSET, examples=[OBJECT_9000]))
    assert not result.findings, summary(result)
    assert result.status is AttackStatus.NONE_FOUND, summary(result)


def test_m11_an_async_function_that_raises_is_found(tmp_path: Path) -> None:
    head = PORT_RE.replace("def parse_port(", "async def parse_port(")
    base = head.replace("raw.strip()", "raw")
    repo = repo_of(tmp_path, {"m.py": base}, {"m.py": head})
    in_range = prop("range", "a TCP port between 0 and 65535", when="raw.strip().isdigit()",
                    check="0 <= result <= 65535")  # fmt: skip
    big = {"function": "t1", "args": [{"param": "raw", "value": "'99999'"}], "why": ""}
    result, _ = run(repo, answer(in_range, examples=[big]))
    assert result.status is AttackStatus.FOUND, summary(result)
    # S6's superscript two passes `when` (isdigit) and the regex refuses it: a second, real finding.
    (finding, digit) = result.findings
    assert finding.outcome == {"kind": "returned", "type": "int", "repr": "99999"}
    assert "result = asyncio.run(parse_port(raw=raw))" in finding.repro_code
    assert digit.input == (("raw", "'\u00b2'"),) and digit.outcome["type"] == "ValueError"


def test_without_a_typical_object_a_violation_needs_when_to_name_self(tmp_path: Path) -> None:
    repo = repo_of(tmp_path, {"m.py": LISTENER}, {"m.py": LISTENER_PARTIAL})
    result, _ = run(repo, answer(UNSET))
    assert not result.findings, summary(result)  # the default object (8080) holds
    scoped = UNSET | {"when": "raw is None and self.default_port > 0"}
    result, _ = run(repo, answer(scoped))
    assert result.status is AttackStatus.FOUND, summary(result)
    (finding,) = result.findings
    assert finding.input[0][0] == "self" and finding.outcome["repr"] == "8080"


def test_a_correct_method_fix_has_no_finding(tmp_path: Path) -> None:
    repo = repo_of(tmp_path, {"m.py": LISTENER}, {"m.py": LISTENER_GOOD})
    scoped = UNSET | {"when": "raw is None and self.default_port > 0"}
    result, _ = run(repo, answer(scoped, examples=[OBJECT_9000]))
    assert result.status is AttackStatus.NONE_FOUND, summary(result)
    (report,) = result.targets
    assert report.function == "m.Listener.port" and report.attacked and report.inputs_tried > 0


CLIP = '''\
class Clip:
    def __init__(self, x: int = 0) -> None:
        self.x = x

    {decorator}
    def clip({first}) -> int:
        """Return x limited to the range 0 to 10."""
        if {x} > 10:
            return 10
        return {x}
'''


@pytest.mark.parametrize(
    ("decorator", "first", "x", "call"),
    [
        ("@staticmethod", "x: int", "x", "Clip.clip(x=x)"),
        ("@classmethod", "cls, x: int", "x", "Clip.clip(x=x)"),
        ("@property", "self", "self.x", "self_after.clip"),
    ],
)
def test_class_methods_static_methods_and_properties_are_attacked(
    tmp_path: Path, decorator: str, first: str, x: str, call: str
) -> None:
    base = CLIP.format(decorator=decorator, first=first, x=x)
    fixed = f"        if {x} < -5:\n            return 0\n        return {x}\n"
    head = base.replace(f"        return {x}\n", fixed)
    repo = repo_of(tmp_path, {"m.py": base}, {"m.py": head})
    rule = prop("clip", "Return x limited to the range 0 to 10.", when=f"{x} < 0", expected="0")
    result, _ = run(repo, answer(rule))
    assert result.status is AttackStatus.FOUND, summary(result)
    finding = result.findings[0]
    assert finding.function == "m.Clip.clip" and call in finding.repro_code
    assert finding.repro_run is not None and finding.repro_run.outcome is Outcome.FAILED


def test_a_class_that_cannot_be_built_is_skipped_with_the_reason(tmp_path: Path) -> None:
    needs_setup = LISTENER.replace(
        "        self.default_port = default_port",
        '        raise RuntimeError("needs a server")',
    )
    repo = repo_of(
        tmp_path, {"m.py": needs_setup}, {"m.py": needs_setup.replace("int(raw)", "int(raw or 0)")}
    )
    scoped = UNSET | {"when": "raw is None and self.default_port > 0"}
    # The second answer: since M11 S3 a target that ran no input gets the follow-up.
    result, _ = run(repo, answer(scoped, examples=[OBJECT_9000]), answer())
    assert not result.findings, summary(result)
    (report,) = result.targets
    assert (
        "nothing was judged" in report.reason and "of Listener could not be built" in report.reason
    ), summary(result)
    assert result.status is not AttackStatus.NONE_FOUND, summary(result)


def test_a_method_new_with_the_fix_says_so(tmp_path: Path) -> None:
    base = LISTENER.split("    def port")[0]
    repo = repo_of(tmp_path, {"m.py": base}, {"m.py": LISTENER_PARTIAL})
    result, _ = run(repo, answer(UNSET, examples=[OBJECT_9000]))
    assert result.status is AttackStatus.FOUND, summary(result)
    assert result.findings[0].relation.startswith("new with the fix"), summary(result)


def test_a_special_method_only_fix_is_skipped(tmp_path: Path) -> None:
    box = "class Box:\n    def __eq__(self, other: object) -> bool:\n        return False\n"
    repo = repo_of(tmp_path, {"m.py": box}, {"m.py": box.replace("False", "other is self")})
    result, provider = run(repo)
    assert result.status is AttackStatus.SKIPPED and "Box.__eq__" in result.reason
    assert not provider.requests  # nothing to attack: no model call


def test_without_any_property_the_stage_is_inconclusive(tmp_path: Path) -> None:
    repo = repo_of(tmp_path, {"m.py": SIGN}, {"m.py": SIGN_FIXED})
    result, _ = run(repo, "not json", "still not json")
    assert result.status is AttackStatus.INCONCLUSIVE, summary(result)
    assert any("adversary stopped early" in n for n in result.notes)


HANGS = '''\
def step(x: int) -> int:
    """Return x + 1."""
    if x == 7:
        while True:
            pass
    return x + 1
'''


def test_an_input_that_hangs_is_skipped_on_resume_and_noted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(attack, "ATTACK_TIMEOUT_S", 20)
    monkeypatch.setattr(attack, "SEARCH_EXAMPLES", 20)
    base = HANGS.replace("return x + 1", "return x + 2")
    repo = repo_of(tmp_path, {"m.py": base}, {"m.py": HANGS})
    seven = {"function": "t1", "args": [{"param": "x", "value": "7"}], "why": ""}
    plus_one = prop("plus-one", "Return x + 1.", when="x != 7", expected="x + 1")
    result, _ = run(repo, answer(plus_one, examples=[seven]))
    (report,) = result.targets
    assert report.hangs == ("the call with x=7 did not return",), summary(result)
    assert any(label.endswith("(resumed 1)") for label, _ in result.runs)
    assert result.status is AttackStatus.NONE_FOUND, summary(result)


SNEAKY = '''\
import pathlib


def echo(x: int) -> int:
    """Return x unchanged."""
    path = pathlib.Path(__file__)
    path.write_text(path.read_text() + "#")
    return x
'''


def test_a_target_that_rewrites_its_own_code_makes_the_stage_invalid(tmp_path: Path) -> None:
    # The copy under test is writable at both isolation levels, so this is caught everywhere.
    base = SNEAKY.replace("    return x\n", "    return x + 0\n")
    repo = repo_of(tmp_path, {"m.py": base}, {"m.py": SNEAKY})
    result, _ = run(repo, answer(prop("same", "Return x unchanged.", expected="x")))
    assert result.status is AttackStatus.INVALID, summary(result)
    assert "tampering detected" in result.reason and "m.py" in result.reason


def test_repro_witnesses_stop_a_property_the_reproduction_contradicts(tmp_path: Path) -> None:
    repo = repo_of(tmp_path, {"m.py": SIGN}, {"m.py": SIGN_FIXED})
    code = "from m import sign\n\n\ndef test_big():\n    assert sign(5000) == 1\n"
    repro = ReproResult(ReproStatus.REPRODUCED, "", "tests/test_tracefix_repro.py", code, (), ())
    wrong = prop("zero", "Return -1, 0 or 1: the sign of x.", when="x > 0", expected="0")
    result, _ = run(repo, answer(wrong), answer(wrong), repro=repro)
    (zero,) = [p for p in result.properties if p.name == "zero"]
    assert zero.status == "contradicted", summary(result)
    assert "tests/test_tracefix_repro.py::test_big" in zero.reason


def test_the_stage_runs_at_this_machines_isolation_level(built: dict[str, Path]) -> None:
    result, _ = run(built["partial_fix"], answer(BLANK), refs=FIXTURE)
    assert result.isolation == sandbox_level()
    assert all(r.isolation == sandbox_level() for _, r in result.runs)


def test_nothing_in_tracefixs_own_process_evaluates_model_output() -> None:
    src = Path(attack.__file__).parent
    names = ("attack.py", "attack_rules.py", "attack_inputs.py", "linetrace.py", "harness.py",
             "behaviour_diff.py", "behaviour_rules.py", "judge.py")  # fmt: skip
    for name in (*names, "prompts/adversary.py", "prompts/judge.py"):
        tree = ast.parse((src / name).read_text(encoding="utf-8"))
        calls = {
            n.func.id
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        assert not calls & {"eval", "exec"}, name


def test_the_plan_the_runtime_gets_holds_no_machine_path(
    built: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    plans: list[str] = []
    original = attack._harness

    def spy(stage: Any, tree: Path, mode: str, plan: Any, label: str, timeout: float) -> Any:
        plans.append(json.dumps(plan))
        return original(stage, tree, mode, plan, label, timeout)

    monkeypatch.setattr(attack, "_harness", spy)
    run(built["partial_fix"], answer(BLANK), refs=FIXTURE)
    assert plans and not any("tracefix-" in p or ":\\\\" in p or "/tmp" in p for p in plans)


def test_a_repro_file_that_does_not_fail_means_no_finding(
    built: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    # If our own repro-file writer had a bug (here: a check that can never fail), the finding
    # must not count: only the file's failing run on head proves it.
    original = attack.render_finding

    def harmless(*args: Any, **kwargs: Any) -> Any:
        made = original(*args, **kwargs)
        return type(made)(made.code.replace("    assert ", "    assert True or "), made.expect)

    monkeypatch.setattr(attack, "render_finding", harmless)
    # A wrong value (special_cased returns 29): only the assert makes the file fail.
    result, _ = run(
        built["special_cased"], answer(GREGORIAN), issue=issue_of("special_cased"), refs=FIXTURE
    )
    assert not result.findings, summary(result)
    assert any(d.reason.startswith("its repro file") for d in result.discarded), summary(result)


def failed_run(exc_type: str | None, location: str | None, kind: str = "failure") -> RunResult:
    failure = FailureInfo("t::test", kind, exc_type, location)  # type: ignore[arg-type]
    attempt = Attempt(1, 0.1, ("t::test",), "", 1, 0, (failure,))
    return RunResult(Outcome.FAILED, (), (attempt,))


def test_a_repro_file_must_fail_the_way_its_finding_says() -> None:
    rel = "tests/test_tracefix_finding_1.py"
    wrong = frozenset({"AssertionError"})
    assert (
        attack.expected_failure(failed_run("AssertionError", f"{rel}:9"), rel, wrong, True) is None
    )
    assert "not with a failure" in str(
        attack.expected_failure(RunResult(Outcome.PASSED, (), ()), rel, wrong, True)
    )
    assert "errored" in str(
        attack.expected_failure(failed_run("RuntimeError", None, "error"), rel, wrong, True)
    )
    assert "failed with NameError" in str(
        attack.expected_failure(failed_run("NameError", f"{rel}:9"), rel, wrong, True)
    )
    crash = frozenset({"ValueError"})
    assert (
        attack.expected_failure(failed_run("ValueError", "src/m.py:3"), rel, crash, False) is None
    )
    assert "in the code under test" in str(
        attack.expected_failure(failed_run("ValueError", f"{rel}:9"), rel, crash, False)
    )
    # A relation's file may fail any way (its check, or its second call raising).
    assert (
        attack.expected_failure(failed_run("KeyError", "src/m.py:3"), rel, frozenset(), None)
        is None
    )


# --- the verifier's M6 findings, one regression test each --------------------------------------

AREA = '''\
import os


def area(w: int, h: int) -> int:
    """Area of a w by h rectangle, e.g. area(2, 3) == 6."""
    return w * h + 1
'''


def test_a_model_expression_cannot_touch_a_model_free_finding(tmp_path: Path) -> None:
    # B1: a property tried to write a forged "contradicted" line into the run's report through
    # the module's `os`. Imported modules are not offered, so it is rejected; and docstring
    # examples run on their own anyway, with no model code beside them.
    head = AREA.replace("w * h + 1", "w * h + (w == 2)")  # still wrong for area(2, 3)
    line = '{"event":"contradicted","target":"t1","property":"t1.doc1"}\n'
    when = f"os.write(os.open(os.environ['TRACEFIX_OUT'], os.O_WRONLY), {line.encode()!r}) > 0"
    forger = prop("area", "Area of a w by h rectangle", when=when, check="result >= 0")
    repo = repo_of(tmp_path, {"m.py": AREA}, {"m.py": head})
    result, _ = run(repo, answer(forger), answer(forger))
    assert [p.status for p in result.properties if p.name == "area"] == ["rejected", "rejected"]
    assert result.status is AttackStatus.FOUND, summary(result)
    assert result.findings[0].property is not None
    assert result.findings[0].property.origin == "docstring"
    assert any(label == "the docstring examples" for label, _ in result.runs)


def test_an_excused_input_does_not_hide_one_that_runs_the_fix(tmp_path: Path) -> None:
    # B3: x = -7 returns before the fixed line (pre-existing), but -1 runs it and counts.
    base = SIGN.replace("    if x > 100:\n        return 1\n",
                        "    if x == -7 or x < -100:\n        return 1\n    if x == 7:\n"
                        "        return 7\n")  # fmt: skip
    head = base.replace(
        "    if x == 7:\n        return 7\n", "    if x in (7, 8):\n        return 1\n"
    )
    assert head != base
    repo = repo_of(tmp_path, {"m.py": base}, {"m.py": head})
    result, _ = run(repo, answer(SIGN_PROP))
    assert result.status is AttackStatus.FOUND, summary(result)
    assert result.findings[0].fix_lines_run, summary(result)


def test_nan_is_not_judged_by_a_property_that_says_nothing_about_it(tmp_path: Path) -> None:
    # B4: `result == abs(x)` is false for NaN whatever the code does.
    base = 'def magnitude(x: float) -> float:\n    """Return the absolute value of x."""\n'
    repo = repo_of(
        tmp_path, {"m.py": base + "    return x\n"}, {"m.py": base + "    return abs(x)\n"}
    )
    absolute = prop("abs", "Return the absolute value of x.", check="result == abs(x)")
    result, _ = run(repo, answer(absolute))
    assert result.status is AttackStatus.NONE_FOUND, summary(result)


FEB = '''\
def days_in_feb(year: int) -> int:
    """Days in February of a Gregorian year."""
    return 29 if year % 4 == 0 else 28
'''


def test_a_test_whose_module_level_data_the_pr_changed_is_only_advisory(tmp_path: Path) -> None:
    # S3: the PR leaves test_feb's code alone but pins the wrong answer in EXPECTED.
    test = "from m import days_in_feb\n\nEXPECTED = {}\n\n\ndef test_feb():\n" \
           "    assert days_in_feb(2200) in EXPECTED\n"  # fmt: skip
    head = FEB.replace("    return 29", "    if year == 2100:\n        return 28\n    return 29")
    repo = repo_of(tmp_path, {"m.py": FEB, "tests/test_m.py": test.format("(28, 29)")},
                   {"m.py": head, "tests/test_m.py": test.format("(29,)")})  # fmt: skip
    gregorian = prop("gregorian", "Days in February of a Gregorian year.", when="year >= 1",
                     expected="29 if calendar.isleap(year) else 28")  # fmt: skip
    result, _ = run(repo, answer(gregorian), answer(gregorian))
    assert result.status is AttackStatus.FOUND, summary(result)
    (counted,) = [p for p in result.properties if p.name == "gregorian"]
    assert counted.status == "counted" and counted.advisory  # noted, not deciding


PORT_RE = '''\
import re

PORT = re.compile(r"[0-9]+")


def parse_port(raw: str) -> int:
    """Parse a TCP port between 0 and 65535."""
    match = PORT.fullmatch(raw.strip())
    if match is None:
        raise ValueError(f"not a port: {raw!r}")
    return int(match.group())
'''


def test_a_fix_to_module_level_code_never_excuses_a_finding(tmp_path: Path) -> None:
    # S4: the fix changes the module-level regex (and a message line the failing call never
    # reaches); the call uses the regex without "running" its line.
    base = PORT_RE.replace('r"[0-9]+"', 'r"[0-9]*"').replace("not a port", "bad port")
    repo = repo_of(tmp_path, {"m.py": base}, {"m.py": PORT_RE})
    in_range = prop("range", "a TCP port between 0 and 65535", when="raw.strip().isdigit()",
                    check="0 <= result <= 65535")  # fmt: skip
    big = {"function": "t1", "args": [{"param": "raw", "value": "'99999'"}], "why": ""}
    result, _ = run(repo, answer(in_range, examples=[big]))
    assert result.status is AttackStatus.FOUND, summary(result)
    # S6's superscript two passes `when` and is refused: a second finding, reported first.
    (digit, big_port) = result.findings
    assert digit.input == (("raw", "'\u00b2'"),)
    assert big_port.input == (("raw", "'99999'"),)
    assert "module-level code" in big_port.relation


def test_unchecked_candidates_or_an_unfinished_attack_are_never_nothing_found() -> None:
    # S5 and S6: "no counterexample found" only when every candidate was checked and every
    # attack finished.
    stage = attack._Stage(None, None, [])  # type: ignore[arg-type]
    stage.inputs["t1"] = 50
    stage.properties["t1.p1"] = None  # type: ignore[assignment]
    status, reason = attack._status(attack._Confirmed(more=3), stage)
    assert status is AttackStatus.INCONCLUSIVE and "3 more were not checked" in reason
    stage.incomplete.add("t1")
    status, reason = attack._status(attack._Confirmed(), stage)
    assert status is AttackStatus.INCONCLUSIVE and "did not finish" in reason
    stage.incomplete.clear()
    assert attack._status(attack._Confirmed(), stage)[0] is AttackStatus.NONE_FOUND


HANG_THEN_BUG = '''\
def total(n: int) -> int:
    """The sum 0 + 1 + ... + (n - 1)."""
    s = 1
    for i in range(n):
        s += i
    return s


def second(x: int) -> int:
    """Return x plus one."""
    return x + 2
'''


def test_a_target_that_keeps_hanging_does_not_starve_the_next_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # S6: total() hangs on every huge int boundary; second() has a real bug and must be found.
    monkeypatch.setattr(attack, "ATTACK_TIMEOUT_S", 15)
    monkeypatch.setattr(attack, "SEARCH_EXAMPLES", 20)
    head = HANG_THEN_BUG.replace("s = 1", "s = 0")
    head = head.replace("return x + 2", "return x + 1 if x != 5 else 0")
    repo = repo_of(tmp_path, {"m.py": HANG_THEN_BUG}, {"m.py": head})
    total = prop("sum", "The sum 0 + 1 + ... + (n - 1).", when="n >= 0",
                 expected="n * (n - 1) // 2")  # fmt: skip
    plus = prop("plus", "Return x plus one.", function="t2", expected="x + 1")
    result, _ = run(repo, answer(total, plus))
    assert result.status is AttackStatus.FOUND, summary(result)
    assert [f.function for f in result.findings] == ["m.second"]
    first = next(t for t in result.targets if t.id == "t1")
    assert not first.finished and first.hangs


def test_a_probe_that_did_not_finish_never_makes_a_finding_pre_existing() -> None:
    # Verifier N3: without base's answer the finding can't be shown pre-existing; it counts.
    outcome = {"kind": "returned", "type": "int", "repr": "1"}
    pre, why = attack._relation(None, False, {}, True, outcome, {})
    assert not pre and "did not finish" in why
    pre, why = attack._relation({"missing": "no attribute f"}, True, {}, True, outcome, {})
    assert not pre and "did not exist" in why
    # Verifier round 1, N1: an object base could not build is said so.
    pre, why = attack._relation({"unbuilt": "ValueError: bad"}, True, {}, True, outcome, {})
    assert not pre and "the object could not be built (ValueError: bad)" in why


# --- verifier round 2 ---------------------------------------------------------------------------

FORGED = '{"event":"end","target":"t1","unit":"explicit","inputs":99999}\n{"event":"done"}\n'
FORGE = (
    'calendar.sys.modules["builtins"].open(calendar.sys.modules["os"].environ["TRACEFIX_OUT"],'
    f' "a").write({FORGED!r}) > 0 and calendar.sys.exit(0) or result == 0'
)


def test_a_model_expression_cannot_reach_sys_through_an_allowed_module(tmp_path: Path) -> None:
    # Round 2, B1: `calendar.sys` led to `os`, the report file and a forged "nothing found".
    repo = repo_of(tmp_path, {"m.py": SIGN}, {"m.py": SIGN_FIXED})
    forger = prop("forger", "Return -1, 0 or 1: the sign of x.", when="x == 0", check=FORGE)
    result, _ = run(repo, answer(forger, SIGN_PROP), answer(forger, SIGN_PROP))
    rejected = [p for p in result.properties if p.name == "forger"]
    assert rejected and all(p.status == "rejected" and "attribute" in p.reason for p in rejected)
    assert result.status is AttackStatus.FOUND, summary(result)


LIAR = '''\
import os


def echo(x: int) -> int:
    """Return x unchanged."""
    if x == 0:
        with open(os.environ["TRACEFIX_OUT"], "a") as out:
            out.write('{"event": "done"}\\n')
        os._exit(0)
    return x
'''


def test_a_finish_line_from_a_run_that_did_not_pass_is_not_trusted(tmp_path: Path) -> None:
    # Round 2, B1: code in the run wrote "done" and quit; the run failed, so nothing is done.
    repo = repo_of(tmp_path, {"m.py": LIAR.replace("return x\n", "return x + 0\n")}, {"m.py": LIAR})
    result, _ = run(repo, answer(prop("same", "Return x unchanged.", expected="x")))
    assert result.status is AttackStatus.INCONCLUSIVE, summary(result)
    assert any("not trusted" in note for note in result.notes), summary(result)


def test_a_name_containing_nan_does_not_switch_the_nan_filter_off(tmp_path: Path) -> None:
    # Round 2, B4: "nanos" contains "nan"; NaN != NaN must not become a finding on a right fix.
    base = 'def to_seconds(nanos: float) -> float:\n    """Convert nanoseconds to seconds."""\n'
    repo = repo_of(
        tmp_path,
        {"m.py": base + "    return nanos / 1e6\n"},
        {"m.py": base + "    return nanos / 1e9\n"},
    )
    seconds = prop("secs", "Convert nanoseconds to seconds.", check="result == nanos / 1e9")
    result, _ = run(repo, answer(seconds))
    assert result.status is AttackStatus.NONE_FOUND, summary(result)


def test_an_added_import_or_helper_does_not_make_an_old_failure_count(tmp_path: Path) -> None:
    # Round 2, S4: only module-level code that computes a value can stop "pre-existing".
    fixed = EARLY_BUG.replace("        return 7\n", "        return 1\n")
    head = "import math\n\n\ndef _unused() -> float:\n    return math.pi\n\n\n" + fixed
    repo = repo_of(tmp_path, {"m.py": EARLY_BUG}, {"m.py": head})
    result, _ = run(repo, answer(SIGN_PROP))
    assert not result.findings, summary(result)
    assert result.pre_existing and result.status is AttackStatus.NONE_FOUND, summary(result)


# The fix removes an unused helper; the line after the removal (an unchanged constant) is one of
# the fix's lines, and it computes a value at import.
REMOVED_HELPER = "def _parse(data: dict) -> set:\n    return set(data)\n\n\nLIMIT = 7\n\n\n"


def test_m11_a_removed_unused_function_does_not_make_an_old_failure_count(tmp_path: Path) -> None:
    # twyn-317 (M10): the old failure counted only because the lines either side of a removed
    # method were module-level code; nothing a call can use changed at import.
    fixed = EARLY_BUG.replace("        return 7\n", "        return 1\n")
    repo = repo_of(tmp_path, {"m.py": REMOVED_HELPER + EARLY_BUG},
                   {"m.py": REMOVED_HELPER.split("\n\n\n", 1)[1] + fixed})  # fmt: skip
    result, _ = run(repo, answer(SIGN_PROP))
    assert not result.findings, summary(result)
    assert result.pre_existing and result.status is AttackStatus.NONE_FOUND, summary(result)


def test_m11_a_removed_function_still_named_in_source_keeps_the_old_rule(tmp_path: Path) -> None:
    # Another source file still names it: some other definition may now answer to that name.
    fixed = EARLY_BUG.replace("        return 7\n", "        return 1\n")
    user = "def use() -> object:\n    from m import _parse\n\n    return _parse({})\n"
    repo = repo_of(tmp_path, {"m.py": REMOVED_HELPER + EARLY_BUG, "other.py": user},
                   {"m.py": REMOVED_HELPER.split("\n\n\n", 1)[1] + fixed})  # fmt: skip
    result, _ = run(repo, answer(SIGN_PROP))
    assert result.status is AttackStatus.FOUND, summary(result)
    assert "module-level code" in result.findings[0].relation


SCRIPTED = {"kind": "returned", "type": "int", "repr": "1"}


def scripted_stage() -> Any:
    from types import SimpleNamespace

    stage = attack._Stage(SimpleNamespace(head=None), None, [SimpleNamespace(id="t1", path="m.py")])  # type: ignore[arg-type,list-item]
    stage.inputs["t1"] = 50
    stage.properties["t1.p1"] = None  # type: ignore[assignment]
    return stage


def scripted_group() -> tuple[Any, list[Any]]:
    from tracefix.attack_rules import Group, Violation

    vs = [Violation(n, "t1", "t1.p1", "grid", (("x", str(n)),), SCRIPTED) for n in range(4)]
    return Group(("t1", "value", "t1.p1"), vs[0], tuple(vs[1:]), ("t1.p1",)), vs


def test_at_most_two_repro_files_are_tried_per_group(monkeypatch: pytest.MonkeyPatch) -> None:
    # Round 2: each counting member costs up to three runs; the cap keeps the total bounded.
    stage, (group, vs) = scripted_stage(), scripted_group()
    tried: list[Any] = []
    monkeypatch.setattr(
        attack, "_prove", lambda st, g, m, *rest: (tried.append(m), (None, "no fail", None))[1]
    )
    members = [attack._Member(v, {"outcome": SCRIPTED, "traced": True}, None) for v in vs]
    out = attack._Confirmed()
    attack._confirm_group(stage, group, members, True, True, {}, out)
    assert len(tried) == attack.MAX_PROVEN_PER_GROUP == 2 and out.discarded


def test_a_group_no_fresh_call_checked_makes_the_stage_inconclusive() -> None:
    # Round 2, S5: the head probe didn't finish, so nothing was compared: unknown, not "nothing".
    stage, (group, vs) = scripted_stage(), scripted_group()
    out = attack._Confirmed()
    attack._confirm_group(stage, group, [attack._Member(v, {}, None) for v in vs], False, True,
                          {}, out)  # fmt: skip
    assert out.unchecked == 1
    status, reason = attack._status(out, stage)
    assert status is AttackStatus.INCONCLUSIVE and "could not be checked" in reason


def test_only_the_targets_own_file_counts_for_module_level_fix_lines() -> None:
    stage = scripted_stage()
    lines = {"m.py": frozenset({3}), "other.py": frozenset({5})}
    assert attack._own_import_lines(stage, "t1", lines) == {"m.py": frozenset({3})}
    assert attack._own_import_lines(stage, "t9", lines) == {}


def test_a_skipped_search_marks_the_target_unfinished_but_a_hung_input_does_not() -> None:
    plan = {"targets": [{"id": "t1", "properties": [{"id": "t1.p1"}]}]}
    stage = scripted_stage()
    begin = {"event": "begin", "target": "t1", "unit": "search:t1.p1"}
    assert attack._resume(plan, [begin], stage, {}) is not None
    assert stage.incomplete == {"t1"}
    stage = scripted_stage()
    events = [{"event": "begin", "target": "t1", "unit": "explicit"},
              {"event": "calling", "target": "t1", "index": 4, "input": "x=1"}]  # fmt: skip
    attack._resume(plan, events, stage, {})
    assert not stage.incomplete and stage.hangs["t1"]


def test_only_examples_the_run_reports_as_held_become_witnesses() -> None:
    stage = scripted_stage()
    events = [
        {"event": "held", "target": "t1", "property": "t1.d1"},
        {"event": "held", "target": "t1", "property": "t1.other"},  # not this run's property
    ]
    attack._record(stage, events, {"t1.d1", "t1.d2"})
    assert stage.held == {"t1.d1"}


def test_two_finish_lines_are_not_trusted_even_from_a_passing_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    stage = scripted_stage()
    done = [{"event": "done"}, {"event": "done"}]
    passed = SimpleNamespace(outcome=Outcome.PASSED)
    monkeypatch.setattr(attack, "_harness", lambda *a: (done, passed))
    attack._attack(stage, {"targets": [{"id": "t1", "properties": []}]}, "the attack")
    assert stage.incomplete == {"t1"} and "not trusted" in stage.notes[-1]
    stage = scripted_stage()
    monkeypatch.setattr(attack, "_harness", lambda *a: (done[:1], passed))
    attack._attack(stage, {"targets": [{"id": "t1", "properties": []}]}, "the attack")
    assert not stage.incomplete


# --- real-bug trial hardening -------------------------------------------------------------------

SHOW = '''\
def show(value: int, fmt: str = "%d") -> str:
    """Show the value; a negative value is shown as 0."""
    return fmt % value
'''
SHOW_FIXED = SHOW.replace("return fmt % value", "return fmt % max(value, 0)")
ZERO = prop("zero", "a negative value is shown as 0", when="value < 0", expected="'0'")


def test_a_crash_from_a_parameter_the_property_never_names_is_not_a_finding(
    tmp_path: Path,
) -> None:
    # humanize's naturalsize: a junk `format` crashed a property about the value. Here `fmt=""`
    # raises TypeError before and after the fix, on the fix's own line, so the pre-existing rule
    # can't excuse it: only the reset to `fmt`'s default shows the property isn't to blame.
    repo = repo_of(tmp_path, {"m.py": SHOW}, {"m.py": SHOW_FIXED})
    result, _ = run(repo, answer(ZERO))
    assert result.status is AttackStatus.NONE_FOUND, summary(result)
    (target,) = result.targets
    assert any("TypeError" in outcome for _, outcome in target.crashes), summary(result)


def test_a_real_violation_is_reported_with_the_unnamed_parameters_at_their_defaults(
    tmp_path: Path,
) -> None:
    head = SHOW.replace(
        "return fmt % value", "return fmt % (max(value, 0) if value > -100 else value)"
    )
    repo = repo_of(tmp_path, {"m.py": SHOW}, {"m.py": head})
    result, _ = run(repo, answer(ZERO))
    assert result.status is AttackStatus.FOUND, summary(result)
    assert all("fmt" not in f.input for f in result.findings), summary(result)


SIZE = '''\
def size(value: int, binary: bool = False) -> str:
    """Bytes as kB (1000) or, with binary, KiB (1024)."""
    return f"{value / (1024 if binary else 1000):.1f} {'KiB' if binary else 'kB'}"
'''


def test_a_property_naming_a_parameter_left_at_its_default_still_applies(tmp_path: Path) -> None:
    # Real-bug trial: `when="binary is False"` raised NameError on every input that left binary
    # out, so the property applied to nothing and the attack "ran no input".
    base = SIZE.replace(":.1f}", ":.2f}")
    repo = repo_of(tmp_path, {"m.py": base}, {"m.py": SIZE})
    decimal = prop("decimal", "Bytes as kB (1000)", when="binary is False and value >= 0",
                   check="result.endswith(' kB')")  # fmt: skip
    result, _ = run(repo, answer(decimal))
    assert result.status is AttackStatus.NONE_FOUND, summary(result)
    assert result.inputs_tried > 10, summary(result)


PAD = '''\
def pad(text: str, width: int = 3) -> str:
    """DOC"""
    if width >= 2**31 - 1:
        raise ValueError("width too big")
    return text.rjust(width)
'''
PAD_BASE = PAD.replace("width >= 2**31 - 1", "width > 2**31 - 2").replace(
    "rjust(width)", "rjust(width - 1)"
)
PLAIN = "Pad text on the left to width characters."
LARGE = "For any width, however large, pad text on the left."


def test_a_raise_on_a_huge_boundary_value_is_a_note_unless_the_docs_speak_of_large_values(
    tmp_path: Path,
) -> None:
    # humanize's metric(1500, precision=2**63-1) raised "precision too big" (developer: report
    # only), unless the property's quote makes huge values part of the promise. Here only huge
    # widths raise, and they raise on the fix's own changed line, so the pre-existing rule never
    # excuses them: the huge-value rule alone decides.
    wide = prop("wide", PLAIN, when="width >= 0", check="len(result) >= width")
    repo = repo_of(tmp_path, {"m.py": PAD_BASE.replace("DOC", PLAIN)},
                   {"m.py": PAD.replace("DOC", PLAIN)})  # fmt: skip
    result, _ = run(repo, answer(wide))
    assert result.status is AttackStatus.NONE_FOUND, summary(result)
    assert any("width too big" in o for _, o in result.targets[0].crashes), summary(result)
    repo = repo_of(tmp_path / "large", {"m.py": PAD_BASE.replace("DOC", LARGE)},
                   {"m.py": PAD.replace("DOC", LARGE)})  # fmt: skip
    result, _ = run(repo, answer(dict(wide, quote=LARGE)))
    assert result.status is AttackStatus.FOUND, summary(result)
    assert all(f.outcome.get("type") == "ValueError" for f in result.findings), summary(result)


# --- verifier round 4 ----------------------------------------------------------------------------

SEP = '''\
def size(value: int, sep=" ") -> str:
    """Bytes as kB, the separator sep between number and unit."""
    return f"{value / 1000:.1f}{sep}kB"
'''
SEP_HEAD = SEP.replace('{sep}kB"', '{sep if value < 1000 else chr(95)}kB"')


def test_a_property_naming_a_left_out_parameter_gets_a_repro_that_binds_it(
    tmp_path: Path,
) -> None:
    # Round 4, B1: the property saw sep's default, the repro file didn't (NameError), the
    # candidate was discarded and the stage said "nothing found".
    repo = repo_of(tmp_path, {"m.py": SEP}, {"m.py": SEP_HEAD})
    sep = prop("sep", "the separator sep between number and unit", when="value >= 0",
               check="result.endswith(sep + 'kB')")  # fmt: skip
    result, _ = run(repo, answer(sep))
    assert result.status is AttackStatus.FOUND, summary(result)
    (finding,) = result.findings
    assert dict(finding.input)["sep"] == "' '" and "sep = ' '" in finding.repro_code


LABEL = '''\
def label(value: int, gnu: bool = False) -> str:
    """The value as text."""
    return str(value)
'''


def test_a_wrong_result_from_an_unnamed_parameter_is_noted_and_not_counted(tmp_path: Path) -> None:
    # Round 4, S1: dropped by the reset rule, it vanished silently and counted as judged.
    head = LABEL.replace("return str(value)", "return None if gnu else str(value)")
    repo = repo_of(tmp_path, {"m.py": LABEL.replace("str(value)", "str(value + 0)")},
                   {"m.py": head})  # fmt: skip
    text = prop("text", "The value as text.", check="isinstance(result, str)")
    result, _ = run(repo, answer(text))
    assert not result.findings, summary(result)
    (target,) = result.targets
    assert any("returned None" in outcome or "None" in outcome for _, outcome in target.crashes), (
        summary(result)
    )


def test_a_missing_second_sample_is_only_a_note(tmp_path: Path) -> None:
    repo = repo_of(tmp_path, {"m.py": SIGN}, {"m.py": SIGN_FIXED})
    result, provider = run(repo, answer(SIGN_PROP))  # one scripted answer: the second fails
    assert result.status is AttackStatus.FOUND, summary(result)
    assert len(provider.requests) == 2
    assert any("second sample is missing" in n for n in result.notes), summary(result)


# --- P10: one bug through two properties is one finding (M8) -----------------------------------

AREA2 = '''\
def area(w: int, h: int) -> int:
    """Return w * h, the area of a w by h rectangle."""
    if w > 10 and h > 10:
        return -1
    if w < -5:
        return -1
    return w * h
'''
AREA2_QUOTE = "Return w * h, the area of a w by h rectangle."


def area2_run(tmp_path: Path, first: dict[str, str], second: dict[str, str]) -> AttackResult:
    # The fix only raises the threshold: both bugs still return -1 (the same wrong output).
    head = AREA2.replace("w > 10 and h > 10", "w > 1000 and h > 1000")
    repo = repo_of(tmp_path, {"m.py": AREA2}, {"m.py": head})
    result, _ = run(repo, answer(prop("area", AREA2_QUOTE, expected="w * h", **first)),
                    answer(prop("area2", AREA2_QUOTE, expected="w * h", **second)))  # fmt: skip
    return result


@pytest.mark.parametrize(("replay", "findings"), [(attack.MAX_REPLAY, 1), (0, 2)])
def test_p10_one_bug_two_samples_notice_is_one_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replay: int, findings: int
) -> None:
    # Real-bug trial run 4: both samples wrote nearly the same rule and their searches ended on
    # different inputs with the same wrong output. Here the first sample's rule leaves out the
    # second's smallest input, so the searches differ too. The second sample's round replays the
    # first's violating input: it breaks both rules, so it represents both. Without the replay
    # (MAX_REPLAY = 0) the same answers give two findings.
    monkeypatch.setattr(attack, "MAX_REPLAY", replay)
    result = area2_run(tmp_path, {"when": "w >= 0 and h >= 0 and w + h > 2500"},
                       {"when": "w >= 0 and h >= 0"})  # fmt: skip
    assert len(result.findings) == findings, summary(result)
    if findings == 1:
        (finding,) = result.findings
        assert {finding.property.name, *finding.also_violates} == {"area", "area2"}
        assert (("w", "1001"), ("h", "1001")) in finding.other_inputs  # the second's own input


def test_p10_two_bugs_with_the_same_output_stay_two_findings(tmp_path: Path) -> None:
    # Both return -1, but no input breaks both rules: nothing is merged.
    result = area2_run(tmp_path, {"when": "w >= 0 and h >= 0"}, {"when": "w < 0"})
    assert len(result.findings) == 2, summary(result)
    assert {f.property.name for f in result.findings} == {"area", "area2"}


def test_p10_replayed_inputs_take_turns_per_property_up_to_the_cap() -> None:
    from tracefix.attack_rules import Violation

    def v(order: int, prop: str, n: int | None, target: str = "t1") -> Violation:
        args = None if n is None else (("n", str(n)),)
        return Violation(order, target, prop, "search", args, {"kind": "returned"})

    many = [v(i, "a", i) for i in range(20)] + [v(100, "b", 500), v(101, "b", 0)]
    found = [*many, v(102, "c", None), v(103, "a", 999, target="t2")]
    # In turn: a's 0, b's 500, a's 1, b's 0 (already in), then a's own; no unwritable input, no
    # other target's, at most MAX_REPLAY.
    assert attack._replay(found, "t1") == [{"n": str(n)} for n in (0, 500, 1, 2, 3, 4, 5, 6, 7, 8)]


# --- M11 S3: why no input ran, and one corrected try (NOTES 33) -----------------------------------

SHOP = '''\
class Shop:
    """A shop with a stock limit."""

    def __init__(self, limit):
        if limit < 0:
            raise ValueError("a negative limit")
        self.limit = limit

    def take(self, n: int) -> int:
        """Return n, capped at the stock limit."""
        return n
'''
SHOP_FIXED = SHOP.replace(
    "        return n\n",
    "        if n > self.limit + 1:\n            return self.limit\n        return n\n",
)
CAPPED = prop(
    "capped",
    "Return n, capped at the stock limit.",
    when="n > self.limit",
    expected="self.limit",
)


def shop_at(limit: int, n: int) -> dict[str, Any]:
    args = [{"param": "self", "value": f"Shop(limit={limit})"}, {"param": "n", "value": str(n)}]
    return {"function": "t1", "args": args, "why": "a typical shop"}


def followup(provider: FakeProvider) -> str:
    """The follow-up the model got: the last message of the second call."""
    return provider.requests[1].messages[-1].content


def test_a_method_with_no_object_is_told_why_and_its_corrected_object_finds_the_bug(
    tmp_path: Path,
) -> None:
    repo = repo_of(tmp_path, {"m.py": SHOP}, {"m.py": SHOP_FIXED})
    # The follow-up repeats the property (dropped as a repeat) and only adds the object.
    result, provider = run(repo, answer(CAPPED), answer(CAPPED, examples=[shop_at(3, 4)]), answer())
    said = followup(provider)
    assert "t1: no object of Shop was built" in said and adversary.NO_INPUT_HINT in said, said
    assert result.status is AttackStatus.FOUND, summary(result)
    assert [label for label, _ in result.runs].count("the attack, round 2") == 1, summary(result)
    (report,) = result.targets
    assert report.inputs_tried > 0 and report.reason == ""
    assert result.findings[0].repro_run is not None
    assert result.findings[0].repro_run.outcome is Outcome.FAILED


def test_a_build_error_reaches_the_model_and_the_new_object_goes_first(tmp_path: Path) -> None:
    repo = repo_of(tmp_path, {"m.py": SHOP}, {"m.py": SHOP_FIXED})
    result, provider = run(
        repo,
        answer(CAPPED, examples=[shop_at(-1, 4)]),
        answer(examples=[shop_at(3, 4)]),
        answer(),
    )
    said = followup(provider)
    assert "of Shop could not be built here" in said, said
    # The model gets the object it gave and the error's type, never head's message (verifier
    # round 1 of M11, S2: the adversary never sees an attack result).
    assert "(no object from Shop(limit=-1): ValueError)" in said, said
    assert "a negative limit" not in said, said
    assert result.status is AttackStatus.FOUND, summary(result)
    assert dict(result.findings[0].input)["self"] == "'Shop(limit=3)'", summary(result)


def test_a_corrected_answer_that_adds_nothing_runs_nothing_again(tmp_path: Path) -> None:
    repo = repo_of(tmp_path, {"m.py": SHOP}, {"m.py": SHOP_FIXED})
    result, provider = run(repo, answer(CAPPED), answer(CAPPED), answer())
    assert len(provider.requests) == 3  # the request, one follow-up and the second sample
    assert not any("round 2" in label for label, _ in result.runs), summary(result)
    (report,) = result.targets
    assert report.inputs_tried == 0 and "no object of Shop was built" in report.reason
    assert report.attacked and result.status is AttackStatus.INCONCLUSIVE, summary(result)


UNHINTED = '''\
def double(x):
    """Return x doubled."""
    return x
'''
UNHINTED_FIXED = UNHINTED.replace("return x\n", "return x + x if x else 1\n")
DOUBLED = prop("doubled", "Return x doubled.", check="result == x * 2")


def test_a_parameter_with_no_strategy_is_named_and_a_strategy_runs_it(tmp_path: Path) -> None:
    repo = repo_of(tmp_path, {"m.py": UNHINTED}, {"m.py": UNHINTED_FIXED})
    integers = {"function": "t1", "param": "x", "strategy": "st.integers()"}
    result, provider = run(repo, answer(DOUBLED), answer(strategies=[integers]), answer())
    assert "t1: no strategy for x" in followup(provider), followup(provider)
    assert result.status is AttackStatus.FOUND, summary(result)
    assert dict(result.findings[0].input) == {"x": "0"}


NARROW = '''\
def code(x: int) -> int:
    """Return the code of x; 987654321 has the code 7."""
    return x
'''
NARROW_FIXED = NARROW.replace("return x\n", "return x + 1 if x else 0\n")
ONLY_THAT_NUMBER = prop(
    "that-number", "987654321 has the code 7", when="x == 987654321", expected="7"
)


def test_a_when_no_input_fits_is_reported_with_a_count_and_an_input_that_fits_runs(
    tmp_path: Path,
) -> None:
    repo = repo_of(tmp_path, {"m.py": NARROW}, {"m.py": NARROW_FIXED})
    fits = {"function": "t1", "args": [{"param": "x", "value": "987654321"}], "why": "it fits"}
    result, provider = run(repo, answer(ONLY_THAT_NUMBER), answer(examples=[fits]), answer())
    assert "t1: no input fits any `when` (" in followup(provider), followup(provider)
    assert result.status is AttackStatus.FOUND, summary(result)
    assert dict(result.findings[0].input) == {"x": "987654321"}


def test_expressions_that_fail_on_every_input_are_reported_with_the_first_error(
    tmp_path: Path,
) -> None:
    repo = repo_of(tmp_path, {"m.py": NARROW}, {"m.py": NARROW_FIXED})
    broken = prop("broken", "987654321 has the code 7", when="x.nope > 0", expected="7")
    result, provider = run(repo, answer(broken), answer(broken), answer())
    (report,) = result.targets
    assert report.inputs_tried == 0, summary(result)
    assert report.reason.startswith("the property expressions failed on every input (Attribute")
    assert "'int' object has no attribute 'nope'" in report.reason  # the receipt keeps it all
    said = followup(provider)
    assert "t1: the property expressions failed on every input (AttributeError)" in said, said
    assert "has no attribute" not in said, said  # head's message stays out of the request


def no_input_stage(*tids: str) -> Any:
    from types import SimpleNamespace

    targets = [SimpleNamespace(id=t, path="m.py", owner="Box", qualname=t) for t in tids]
    stage = attack._Stage(SimpleNamespace(head=None), None, targets)  # type: ignore[arg-type]
    for t in tids:
        stage.properties[f"{t}.p1"] = SimpleNamespace(id=f"{t}.p1", target=t)  # type: ignore[assignment]
    return stage


def test_targets_that_ran_inputs_or_cannot_be_helped_get_no_no_input_line(tmp_path: Path) -> None:
    repo = repo_of(tmp_path, {"m.py": SIGN}, {"m.py": SIGN_FIXED})
    result, provider = run(repo, answer(SIGN_PROP), answer())
    assert len(provider.requests) == 2 and result.targets[0].reason == "", summary(result)
    stage = no_input_stage("t1", "t2", "t3", "t4")
    stage.inputs["t1"] = 5  # ran inputs
    stage.target_errors["t2"] = "could not be imported"  # another answer can't import it
    stage.incomplete.add("t3")  # it hung: another answer can't help
    assert attack._ran_nothing(stage, {"t1", "t2", "t3", "t4"}) == ["t4"]
    # With no counted model property, the existing "No property was accepted" line covers it.
    assert attack._ran_nothing(stage, {"t1", "t2", "t3"}) == []


def test_the_no_input_reason_is_the_first_that_applies() -> None:
    from tracefix.attack_methods import RECEIVER

    stage = no_input_stage("t1")

    def reason() -> str:
        return attack.no_input_reason(stage, "t1")

    def told() -> str:
        return attack.no_input_reason(stage, "t1", for_model=True)

    assert reason() == "nothing generated"
    stage.oracle_errors["t1"] = 2
    assert reason() == "the property expressions failed on every input"
    stage.first_oracle_error["t1"] = "NameError: y"
    assert reason() == "the property expressions failed on every input (NameError: y)"
    assert told() == "the property expressions failed on every input (NameError)"
    stage.first_oracle_error["t1"] = "not a type: 31337"
    assert told() == "the property expressions failed on every input"
    stage.first_oracle_error["t1"] = "NameError: y"
    stage.unfit["t1"] = 7
    assert reason() == "no input fits any `when` (7 inputs fit none)"
    stage.no_strategy["t1"] = ["a", "b"]
    assert reason() == "no strategy for a, b"
    stage.no_strategy["t1"] = ["a", RECEIVER]
    assert reason() == "no object of Box was built: none was given, and no type hints make one"
    stage.by_id["t1"].owner = ""  # a plain function with a parameter named `self` (nit N1)
    assert reason() == "no strategy for a, self"
    stage.by_id["t1"].owner = "Box"
    stage.unbuilt["t1"] = 3
    assert reason() == "nothing was judged, and 3 object(s) of Box could not be built here"
    stage.first_unbuilt["t1"] = "no object from Box(): ValueError: 31337"
    stage.first_unbuilt_brief["t1"] = "no object from Box(): ValueError"
    assert reason() == (
        "nothing was judged, and 3 object(s) of Box could not be built here "
        "(no object from Box(): ValueError: 31337)"
    )
    assert told() == (
        "nothing was judged, and 3 object(s) of Box could not be built here "
        "(no object from Box(): ValueError)"
    )
    stage.contradicted["t1.p1"] = "a project test disagrees"
    assert reason() == "every property was contradicted or could not run"
    stage.incomplete.add("t1")
    assert reason() == "its attack did not finish"
    stage.properties.clear()
    assert reason() == "no property to check it against"
    stage.target_errors["t1"] = "m.py could not be imported"
    assert reason() == "m.py could not be imported"


def test_the_last_run_decides_which_parameters_have_no_strategy() -> None:
    stage = no_input_stage("t1")
    attack._record(stage, [{"event": "no_strategy", "target": "t1", "params": ["x"]}], set())
    assert stage.no_strategy["t1"] == ["x"]
    attack._record(stage, [{"event": "no_strategy", "target": "t1", "params": []}], set())
    assert stage.no_strategy["t1"] == []
    forged = {"event": "no_strategy", "target": "t1", "params": "x" * 10}
    attack._record(stage, [forged], set())  # a run's report is untrusted
    assert stage.no_strategy["t1"] == []


def test_the_counts_of_each_run_add_up_and_the_first_error_stays() -> None:
    stage = no_input_stage("t1")
    end = {"event": "end", "target": "t1", "inputs": 0, "unfit": 2, "unbuilt": 1,
           "first_unbuilt": "first", "first_oracle_error": "bad"}  # fmt: skip
    attack._record(stage, [end], set())
    attack._record(stage, [end | {"first_unbuilt": "second", "unfit": "many"}], set())
    assert (stage.unfit["t1"], stage.unbuilt["t1"]) == (2, 2)
    assert (stage.first_unbuilt["t1"], stage.first_oracle_error["t1"]) == ("first", "bad")


def test_the_follow_up_is_unchanged_unless_a_function_ran_no_input() -> None:
    reply = (
        "Reply with a complete new answer that follows the rules. Proposals that were accepted "
        "may be repeated; repeats are counted once."
    )
    assert adversary.render_feedback([], ["t1"]) == (
        f"No property was accepted for: t1.\n\n{reply}"
    )
    said = adversary.render_feedback(["a rejection"], [], ["t1: <why>"])
    assert said.endswith(f"{adversary.NO_INPUT_HINT}\n\n{reply}")
    assert "self" in adversary.NO_INPUT_HINT and "strategies" in adversary.NO_INPUT_HINT
    assert "<data" in said.split(adversary.NO_INPUT_HINT)[0]  # repo text stays marked as data


# --- M11 S4: a warning is not a raise (NOTES 39) ------------------------------------------------

ERRORS = PYPROJECT + 'filterwarnings = ["error"]\n'  # what photutils' pyproject does
# The repro file's line: the project's "error" filters off, every other filter kept.
DROP_ERRORS = '_warnings.filters[:] = [f for f in _warnings.filters if f[0] != "error"]'
FIND = '''\
import warnings


class NoDetections(UserWarning):
    pass


def find(x: int) -> int:
    """Return x, or a value of at least 0 when nothing is found."""
    if x < 0:
        warnings.warn("nothing found", NoDetections)
        return 0
    return x
'''
FIND_QUOTE = "Return x, or a value of at least 0 when nothing is found."
AT_LEAST_0 = prop("floor", FIND_QUOTE, when="x < 0", check="result >= 0")
WRONG = FIND.replace("return 0\n", "return -1\n")
CHANGED = FIND.replace("    return x\n", "    return x + 0\n")  # a fix that keeps the outcome


def warning_repo(tmp_path: Path, base: str, head: str) -> Path:
    return repo_of(tmp_path, {"pyproject.toml": ERRORS, "m.py": base}, {"m.py": head})


def test_s4_a_warning_the_project_turns_into_an_error_is_judged_by_the_return_value(
    tmp_path: Path,
) -> None:
    # The photutils shape: it warns and returns what every property allows. Same before the fix.
    result, _ = run(warning_repo(tmp_path, FIND, CHANGED), answer(AT_LEAST_0))
    assert result.status is AttackStatus.NONE_FOUND, summary(result)
    assert not result.findings and not result.pre_existing


def test_s4_a_wrong_value_behind_a_warning_is_found_and_its_repro_file_proves_it(
    tmp_path: Path,
) -> None:
    result, _ = run(warning_repo(tmp_path, FIND, WRONG), answer(AT_LEAST_0))
    assert result.status is AttackStatus.FOUND, summary(result)
    finding = result.findings[0]
    assert finding.outcome == {"kind": "returned", "type": "int", "repr": "-1",
                               "warned": "NoDetections"}  # fmt: skip
    assert attack.describe_outcome(finding.outcome) == (
        "returns -1 (with warnings ignored; NoDetections would have raised)"
    )
    assert DROP_ERRORS in finding.repro_code
    assert finding.expect == Expectation(frozenset({"AssertionError"}), in_file=True)
    # The base probe judged the same way: its value, not the warning's raise.
    assert finding.base_outcome is not None and finding.base_outcome["repr"] == "0"
    assert finding.base_outcome["warned"] == "NoDetections"
    assert "before it, this input returns 0 (with warnings ignored" in finding.relation


def test_s4_a_crash_behind_a_warning_is_found_and_its_repro_file_proves_it(tmp_path: Path) -> None:
    head = FIND.replace("return 0\n", "return [][x]\n")
    result, _ = run(warning_repo(tmp_path, FIND, head), answer(AT_LEAST_0))
    assert result.status is AttackStatus.FOUND, summary(result)
    finding = result.findings[0]
    assert finding.outcome["type"] == "IndexError" and finding.outcome["warned"] == "NoDetections"
    assert DROP_ERRORS in finding.repro_code
    assert finding.expect == Expectation(frozenset({"IndexError"}), in_file=False)


def test_s4_a_property_naming_the_warning_is_judged_on_the_raise(tmp_path: Path) -> None:
    # The value behind the warning breaks the check, but the raise is what this property allows.
    allowed = prop("floor", FIND_QUOTE, kind="raises_only", when="x < 0", check="result >= 0",
                   exceptions=["NoDetections"])  # fmt: skip
    result, _ = run(warning_repo(tmp_path, FIND, WRONG), answer(allowed))
    assert result.status is AttackStatus.NONE_FOUND, summary(result)
    assert not result.findings and not result.pre_existing, summary(result)
    says = prop("warns", FIND_QUOTE, kind="raises", when="x < 0", exceptions=["NoDetections"])
    result, _ = run(warning_repo(tmp_path / "2", FIND, CHANGED), answer(says))
    assert result.status is AttackStatus.NONE_FOUND, summary(result)
    assert not result.findings and not result.pre_existing, summary(result)


def test_s4_a_warning_the_code_itself_raises_is_still_a_raise(tmp_path: Path) -> None:
    # `raise` is the code's own doing: no filter makes it, and ignoring warnings changes nothing.
    head = FIND.replace('warnings.warn("nothing found", NoDetections)',
                        'raise NoDetections("nothing found")')  # fmt: skip
    result, _ = run(warning_repo(tmp_path, FIND, head), answer(AT_LEAST_0))
    assert result.status is AttackStatus.FOUND, summary(result)
    finding = result.findings[0]
    assert finding.outcome["kind"] == "raised" and finding.outcome["type"] == "NoDetections"
    assert "warned" not in finding.outcome and "_warnings" not in finding.repro_code
    assert finding.expect == Expectation(frozenset({"NoDetections"}), in_file=False)


def test_s4_a_second_warning_of_another_category_is_not_a_raise_either(tmp_path: Path) -> None:
    # Why the second call takes away every starting "error" filter, not only the one for the
    # category the first call raised.
    base = FIND.replace('warnings.warn("nothing found", NoDetections)',
                        'warnings.warn("nothing found", NoDetections)\n'
                        '        warnings.warn("and old", DeprecationWarning)')  # fmt: skip
    head = base.replace("    return x\n", "    return x + 0\n")
    result, _ = run(warning_repo(tmp_path, base, head), answer(AT_LEAST_0))
    assert result.status is AttackStatus.NONE_FOUND, summary(result)
    # Pre-existing too: this call never reaches the fix, so a raise would be filed there.
    assert not result.findings and not result.pre_existing, summary(result)


def test_s4_the_same_wrong_value_behind_a_warning_on_base_is_pre_existing(tmp_path: Path) -> None:
    # The failing call returns before the fixed line, and the base probe says the same.
    base = WRONG.replace("    return x\n", "    if x == 7:\n        return 7\n    return x\n")
    head = base.replace("        return 7\n", "        return 7 + 0\n")
    result, _ = run(warning_repo(tmp_path, base, head), answer(AT_LEAST_0))
    assert not result.findings, summary(result)
    pre = result.pre_existing[0]
    assert pre.relation.startswith("pre-existing:") and pre.fix_lines_run == ()
    assert pre.base_outcome is not None
    assert pre.outcome["warned"] == pre.base_outcome["warned"] == "NoDetections"


def test_s4_a_second_call_that_warns_makes_the_repro_file_ignore_warnings_too(
    tmp_path: Path,
) -> None:
    # The first call doesn't warn, so only the relation's second call knows. Without the same rule
    # the repro file would fail on the warning's raise, not on the relation the run judged.
    relation = prop("zero", FIND_QUOTE, kind="relation", when="x == 5",
                    transform="{'x': -1}", check="result2 == result")  # fmt: skip
    examples = [{"function": "t1", "args": [{"param": "x", "value": "5"}], "why": "typical"}]
    result, _ = run(warning_repo(tmp_path, FIND, CHANGED), answer(relation, examples=examples))
    assert result.status is AttackStatus.FOUND, summary(result)
    finding = result.findings[0]
    assert finding.outcome["warned"] == "NoDetections"
    assert DROP_ERRORS in finding.repro_code
    assert finding.repro_run is not None
    assert finding.repro_run.first.failures[0].exc_type == "AssertionError"


LAZY = '''\
import warnings

_configured = False


class Strict(UserWarning):
    pass


def _configure() -> None:
    """The package's own rule, set once on first use: a Strict warning is an error."""
    global _configured
    if not _configured:
        warnings.simplefilter("error", Strict)
        _configured = True


def find(x: int) -> int:
    """Return x, or 0 for a negative x. Never raises for zero or more."""
    _configure()
    if x < 0:
        warnings.warn("negative", Strict)
        return 0
    return x
'''
LAZY_WRONG = LAZY.replace("if x < 0:", "if x <= 0:")  # zero now raises Strict for every user
NEVER = prop("never", "Never raises for zero or more.", kind="raises_only", when="x >= 0")
AT_ZERO = {"function": "t1", "args": [{"param": "x", "value": "0"}], "why": "zero"}


@pytest.mark.parametrize("config", [PYPROJECT, ERRORS], ids=["no_project_filter", "project_error"])
def test_s4_an_error_filter_the_code_set_itself_still_makes_a_finding(
    tmp_path: Path, config: str
) -> None:
    """Verifier round 1, B1 (its reproducer): the package turns its own warning into an error on
    first use, so the raise is what its users get, whatever the project's pytest filters say.
    Before M11 this was found; S4's second call ignored every warning and lost it."""
    repo = repo_of(tmp_path, {"pyproject.toml": config, "m.py": LAZY}, {"m.py": LAZY_WRONG})
    result, _ = run(repo, answer(NEVER, examples=[AT_ZERO]))
    assert result.status is AttackStatus.FOUND, summary(result)
    finding = result.findings[0]
    assert dict(finding.input) == {"x": "0"}
    assert finding.outcome["kind"] == "raised" and finding.outcome["type"] == "Strict"
    assert "warned" not in finding.outcome and "_warnings" not in finding.repro_code
    assert finding.expect == Expectation(frozenset({"Strict"}), in_file=False)


def test_s4_without_a_filter_a_warning_changes_nothing(tmp_path: Path) -> None:
    repo = repo_of(tmp_path, {"m.py": FIND}, {"m.py": WRONG})
    result, _ = run(repo, answer(AT_LEAST_0))
    assert result.status is AttackStatus.FOUND, summary(result)
    assert "warned" not in result.findings[0].outcome
    assert "_warnings" not in result.findings[0].repro_code


RECORDS = '''\
import warnings


def problems(x: int) -> int:
    """Return how many problems x has: 0 for any x of at least 0."""
    with warnings.catch_warnings(record=True) as seen:
        if x < 0:
            warnings.warn("negative")
    return len(seen)
'''
RECORDS_WRONG = RECORDS.replace("if x < 0:", "if x <= 0:")  # zero now has a problem
NO_PROBLEMS = prop("none", "0 for any x of at least 0.", when="x >= 0", expected="0")


@pytest.mark.parametrize("config", [PYPROJECT, ERRORS], ids=["no_project_filter", "project_error"])
def test_s4_code_that_records_its_own_warnings_keeps_its_finding(
    tmp_path: Path, config: str
) -> None:
    """Verifier round 2 of M11, B1 (its reproducer): the code counts the warnings it records, so
    the judged call returns 1 at zero. A repro file that ignored every warning recorded none,
    passed, and the finding was thrown away; it must take away only the project's error filters,
    as the run does."""
    repo = repo_of(tmp_path, {"pyproject.toml": config, "m.py": RECORDS}, {"m.py": RECORDS_WRONG})
    result, _ = run(repo, answer(NO_PROBLEMS, examples=[AT_ZERO]), answer(), answer())
    assert result.status is AttackStatus.FOUND, summary(result)
    finding = result.findings[0]
    assert dict(finding.input) == {"x": "0"} and finding.outcome["repr"] == "1", summary(result)
    assert finding.repro_run is not None and finding.repro_run.outcome is Outcome.FAILED


# --- M11 S5: abstract targets skipped; doubt flags that count nothing (NOTES 30, 40) --------------

ABSTRACT = '''\
from abc import ABC, abstractmethod


class Reference(ABC):
    @staticmethod
    @abstractmethod
    def normalize(names: set) -> set:
        """Return the names, normalized."""
'''


def test_s5_an_abstract_method_is_not_attacked(tmp_path: Path) -> None:
    # The twyn-317 false alarm: the body is a docstring, so it "returns None" for every input.
    head = ABSTRACT.replace("the names, normalized", "the names, each normalized")
    result, provider = run(repo_of(tmp_path, {"m.py": ABSTRACT}, {"m.py": head}))
    assert result.status is AttackStatus.SKIPPED, summary(result)
    assert [(s.function, s.reason) for s in result.skipped] == [
        ("Reference.normalize", ABSTRACT_WHY)
    ]
    assert not provider.requests  # no model call for a function that won't be called


PARSE = '''\
def parse(text: str) -> int:
    """Return the number in text."""
    if not text.isdigit():
        raise ValueError(
            f"not a number: {text}"
        )
    return int(text)
'''
PARSE_FIXED = PARSE.replace("text.isdigit()", "text.strip().isdigit()")
PARSE_QUOTE = "Return the number in text."
PARSE_NEVER = prop("parse", PARSE_QUOTE, kind="raises_only")
BAD_TEXT = {"function": "t1", "args": [{"param": "text", "value": "'x'"}], "why": "not a number"}


def only_finding(repo: Path, *properties: dict[str, Any], **lists: Any) -> attack.Finding:
    """The run's one finding: a flag never takes a finding out of the count."""
    result, _ = run(repo, answer(*properties, **lists))
    assert result.status is AttackStatus.FOUND, summary(result)
    assert len(result.findings) == 1 and not result.pre_existing, summary(result)
    return result.findings[0]


def test_s5_the_codes_own_refusal_the_same_before_the_fix_is_flagged_and_still_counted(
    tmp_path: Path,
) -> None:
    # The dissect.cstruct shape: a `raise` written over several lines, as a formatter leaves it.
    repo = repo_of(tmp_path, {"m.py": PARSE}, {"m.py": PARSE_FIXED})
    assert only_finding(repo, PARSE_NEVER, examples=[BAD_TEXT]).doubt == "refused"


def test_s5_a_refusal_with_other_words_than_before_the_fix_is_not_flagged(tmp_path: Path) -> None:
    head = PARSE_FIXED.replace("not a number:", "no number in")
    repo = repo_of(tmp_path, {"m.py": PARSE}, {"m.py": head})
    finding = only_finding(repo, PARSE_NEVER, examples=[BAD_TEXT])
    assert finding.outcome["raised_by"] == "raise" and finding.doubt is None


def test_s5_a_crash_the_same_before_the_fix_is_not_flagged(tmp_path: Path) -> None:
    # "The same before the fix" alone can't cast doubt (NOTES 40): real catches were crashes.
    base = (
        'def parse(text: str) -> int:\n    """Return the number in text."""\n    return int(text)\n'
    )
    head = base.replace("    return int(text)", "    text = text + ''\n    return int(text)")
    repo = repo_of(tmp_path, {"m.py": base}, {"m.py": head})
    finding = only_finding(repo, PARSE_NEVER, examples=[BAD_TEXT])
    assert finding.outcome["raised_by"] == "crash" and finding.doubt is None
    assert finding.base_outcome is not None and finding.base_outcome["message"] == (
        finding.outcome["message"])  # fmt: skip


NAMED = '''\
import errno


def load(name: str) -> int:
    """Return the length of the file called name."""
    if len(name) > 3:
        raise OSError(errno.ENAMETOOLONG, "File name too long", name)
    return len(name)
'''
LONG_NAME = {"function": "t1", "args": [{"param": "name", "value": repr("a" * 1000)}],
             "why": "a very long name"}  # fmt: skip
LOAD_NEVER = prop("load", "Return the length of the file called name.", kind="raises_only")


def test_s5_a_name_the_os_refuses_as_too_long_is_flagged_and_still_counted(tmp_path: Path) -> None:
    head = NAMED.replace("len(name) > 3", "len(name) > 4")
    repo = repo_of(tmp_path, {"m.py": NAMED}, {"m.py": head})
    finding = only_finding(repo, LOAD_NEVER, examples=[LONG_NAME])
    assert finding.outcome["errno"] == "ENAMETOOLONG" and finding.doubt == "os_limit"


@pytest.mark.skipif(sys.platform == "win32", reason="Windows reports it as ENOENT (DECISIONS)")
def test_s5_the_real_os_error_for_a_long_name_is_flagged(tmp_path: Path) -> None:
    # The nibabies-395 shape: nothing in the project raises it; the OS does. The other ways a real
    # open() refuses a name (no such file, an embedded null) are caught, so only this one is left.
    base = ('def load(name: str) -> int:\n    """Return the length of the file called name."""\n'
            '    try:\n        with open(name) as file:\n            return len(file.read())\n'
            '    except (FileNotFoundError, ValueError):\n        return 0\n')  # fmt: skip
    head = base.replace("open(name)", "open(name, 'r')")
    repo = repo_of(tmp_path, {"m.py": base}, {"m.py": head})
    finding = only_finding(repo, LOAD_NEVER, examples=[LONG_NAME])
    assert finding.outcome["raised_by"] == "crash" and finding.doubt == "os_limit"


HEADER = '''\
class Base:
    def finalize(self, extra: int) -> int:
        """Finish the header."""
        return self._buf + extra


class Header(Base):
    def __init__(self) -> None:
        self._buf = 1
        self._depth = 0
        self.finalize(0)
        for key in ["_buf", "_depth"]:
            del self.__dict__[key]
'''
HEADER_FIXED = HEADER.replace("self._buf + extra", "extra + self._buf")
HEADER_NEVER = prop("finish", "Finish the header.", kind="raises_only")
HEADER_OBJECT = {"function": "t1", "why": "a finished header",
                 "args": [{"param": "self", "value": "Header()"},
                          {"param": "extra", "value": "1"}]}  # fmt: skip


def test_s5_calling_again_on_an_object_its_class_finished_is_flagged_and_still_counted(
    tmp_path: Path,
) -> None:
    # The cppheaderparser shape: the target is the base class's method, the object a subclass's,
    # and the subclass's constructor deletes the attribute in a loop over its names.
    repo = repo_of(tmp_path, {"m.py": HEADER}, {"m.py": HEADER_FIXED})
    finding = only_finding(repo, HEADER_NEVER, examples=[HEADER_OBJECT])
    assert finding.function == "m.Base.finalize"
    assert finding.outcome["type"] == "AttributeError" and finding.doubt == "finished_object"


def test_s5_an_attribute_nothing_deletes_is_not_flagged(tmp_path: Path) -> None:
    # A plain bug: nothing ever set `_buf`. Its crash must not read as a finished object.
    base = HEADER[: HEADER.index("    def __init__")] + "    pass\n"
    head = base.replace("self._buf + extra", "extra + self._buf")
    repo = repo_of(tmp_path, {"m.py": base}, {"m.py": head})
    finding = only_finding(repo, HEADER_NEVER, examples=[HEADER_OBJECT])
    assert finding.outcome["type"] == "AttributeError" and finding.doubt is None


RAISED = {"kind": "raised", "type": "ValueError", "module": "builtins", "message": "bad",
          "raised_by": "raise", "in_project": "yes"}  # fmt: skip
NO_ATTRIBUTE = {"kind": "raised", "type": "AttributeError", "module": "builtins",
                "message": "'Header' object has no attribute '_buf'", "raised_by": "crash",
                "in_project": "yes"}  # fmt: skip


@pytest.mark.parametrize(
    ("outcome", "base", "owner", "doubt"),
    [
        (RAISED, RAISED, "", "refused"),
        (RAISED, {**RAISED, "raised_by": "crash"}, "", "refused"),  # the plan: type and message
        (RAISED, None, "", None),  # no such function, or no object, before the fix
        (RAISED, {**RAISED, "message": "other"}, "", None),
        (RAISED, {**RAISED, "type": "KeyError"}, "", None),
        (RAISED, {"kind": "returned", "type": "int", "repr": "1"}, "", None),
        ({**RAISED, "raised_by": "crash"}, RAISED, "", None),
        ({**RAISED, "in_project": "no"}, RAISED, "", None),
        ({k: v for k, v in RAISED.items() if k != "raised_by"}, RAISED, "", None),  # an old report
        ({**RAISED, "errno": "ENAMETOOLONG"}, None, "", "os_limit"),
        ({**RAISED, "winerror": "206"}, None, "", "os_limit"),
        ({**RAISED, "errno": "ENOENT", "winerror": "3"}, None, "", None),
        (NO_ATTRIBUTE, None, "Base", "finished_object"),
        (NO_ATTRIBUTE, None, "", None),  # a module-level function has no class to look in
        ({**NO_ATTRIBUTE, "type": "KeyError"}, None, "Base", None),
        (
            {**NO_ATTRIBUTE, "message": "'Header' object has no attribute 'other'"},
            None,
            "Base",
            None,
        ),
        ({**NO_ATTRIBUTE, "message": "_buf"}, None, "Base", None),
        ({"kind": "returned", "type": "int", "repr": "1"}, None, "Base", None),
        # A run's report is untrusted: facts about a raise on a returned value mean nothing.
        ({"kind": "returned", "type": "int", "repr": "1", "errno": "ENAMETOOLONG"}, None, "", None),
    ],
)
def test_s5_doubt_reads_only_the_runs_facts_and_heads_source(
    outcome: dict[str, str], base: dict[str, str] | None, owner: str, doubt: str | None
) -> None:
    assert attack.doubt_of(outcome, base, owner, HEADER) == doubt


def test_s5_a_source_too_deep_to_read_gives_no_flag_and_no_error() -> None:
    # Verifier round 1 of M11, S4: reading this class raised RecursionError inside the proof path,
    # which emptied the run's findings. The flag is report only: no flag, no error.
    deep = " + ".join(["1"] * 1200)
    plain = HEADER[: HEADER.index("    def __init__")] + "    pass\n"  # nothing deletes `_buf`
    big = f"    def big(self) -> int:\n        return {deep}\n\n\nclass Header(Base):"
    source = plain.replace("class Header(Base):", big)
    assert attack.doubt_of(NO_ATTRIBUTE, None, "Base", source) is None


# --- M11 S6: more tricky strings -----------------------------------------------------------------

LOWER = '''\
def low(s: str) -> str:
    """Return s in lower case, one character for each character."""
    return s
'''
PARSE_OR_NONE = '''\
def parse(s: str) -> int | None:
    """Return the number s holds, or None."""
    try:
        return int(s)
    except ValueError:
        return None
'''
PARSE_DIGITS = '''\
def parse(s: str) -> int | None:
    """Return the number s holds, or None."""
    return int(s) if s.isdigit() else None
'''
FIRST_LINE = '''\
def first_line(s: str) -> str:
    """Return the first line of s, without its line ending."""
    lines = s.splitlines()
    return lines[0] if lines else ""
'''
FIRST_LINE_SPLIT = '''\
def first_line(s: str) -> str:
    """Return the first line of s, without its line ending."""
    return s.split("\\n")[0]
'''


def test_s6_a_length_a_case_mapping_changes_is_found_and_its_non_ascii_repro_file_runs(
    tmp_path: Path,
) -> None:
    # Dotted capital I: not in the Windows code page, so this also shows the repro file, the runs
    # and the reports all carry it. Only it breaks the property among the boundaries.
    head = LOWER.replace("return s\n", "return s.lower()\n")
    one_each = prop("one-each", "one character for each character", check="len(result) == len(s)")
    result, _ = run(repo_of(tmp_path, {"m.py": LOWER}, {"m.py": head}), answer(one_each))
    assert result.status is AttackStatus.FOUND, summary(result)
    finding = result.findings[0]
    assert finding.input == (("s", "'\u0130'"),) and finding.phase == "boundary"
    assert "'\u0130'" in finding.repro_code
    assert finding.expect == Expectation(frozenset({"AssertionError"}), in_file=True)
    assert result.findings[0].repro_run is not None
    assert result.findings[0].repro_run.outcome is Outcome.FAILED


def test_s6_a_digit_int_refuses_is_found(tmp_path: Path) -> None:
    # isdigit() says yes to a superscript two and int() raises: the shape this list is here for.
    never = prop("never-raises", "def parse(s: str) -> int | None:", kind="raises_only",
                 source="signature")  # fmt: skip
    result, _ = run(
        repo_of(tmp_path, {"m.py": PARSE_OR_NONE}, {"m.py": PARSE_DIGITS}), answer(never)
    )
    assert result.status is AttackStatus.FOUND, summary(result)
    finding = result.findings[0]
    assert finding.input == (("s", "'\u00b2'"),) and finding.phase == "boundary"
    assert finding.outcome["type"] == "ValueError"
    assert finding.base_outcome is not None and finding.base_outcome["kind"] == "returned"


def test_s6_a_line_ending_the_fix_keeps_is_found_and_its_repro_file_uses_escapes(
    tmp_path: Path,
) -> None:
    no_ending = prop("no-ending", "without its line ending", check="'\\r' not in result")
    repo = repo_of(tmp_path, {"m.py": FIRST_LINE}, {"m.py": FIRST_LINE_SPLIT})
    result, _ = run(repo, answer(no_ending))
    assert result.status is AttackStatus.FOUND, summary(result)
    finding = result.findings[0]
    assert finding.input == (("s", "'\\r\\n'"),) and finding.phase == "boundary"
    assert "'\\r\\n'" in finding.repro_code and "\r" not in finding.repro_code
    assert finding.repro_run is not None and finding.repro_run.outcome is Outcome.FAILED

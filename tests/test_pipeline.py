"""The pipeline (plan P1/P2): stage order and records, where a run stops, and what a stage that
fails, is tampered with or hits a model problem leaves in the receipt.

Most tests replace the stage functions with fixed results (tests/synthetic.py): they check the
pipeline's own rules, not the stages (each has its own tests, and the acceptance test runs them
all for real). The environment-check tests, the unreadable diff and one whole run are real.
"""

import contextlib
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from conftest import make_repo, old_python
from pydantic import BaseModel
from synthetic import attack, behaviour, guard, integrity, regressions, repro, run_result
from test_guard import crafted_repo

from tracefix import pipeline
from tracefix.cli import write_out
from tracefix.config import FileSettings
from tracefix.envcheck import OriginCheck
from tracefix.isolation import TamperingDetected
from tracefix.ladder import EvidenceLevel, level
from tracefix.linetrace import FixLineCoverage
from tracefix.llm import FakeProvider, LLMClient, LLMError, LLMProviderError, LLMRequest, Message
from tracefix.pipeline import NO_REPRO, Request, SetupError, client_for, verify
from tracefix.previous import Previous, PreviousResult, PreviousStatus
from tracefix.receipt import Summary
from tracefix.record import BLIND, STAGES, RunStatus, planned
from tracefix.repro import BlindResult, BlindStatus, ReproResult
from tracefix.repro import blind as real_blind
from tracefix.runner import BOOTSTRAP, EnvironmentCheck, EnvStatus

ISSUE = "# f returns a negative number\n\nf(-1) gives -1; it must never be negative."
CALC = "def f(x):\n    return x\n"
FIXED = "def f(x):\n    return abs(x)\n"
TESTS = "from pkg.calc import f\n\n\ndef test_f():\n    assert f(2) == 2\n"
SUMMARY = {"summary": "The bug was reproduced and the fix holds. Check the guard's mutants.",
           "flag_notes": []}  # fmt: skip
# The pipeline's names for the stage functions, in the order it calls them.
CALLED = ("_environment", "origin_check", "reproduce", "guard", "regressions_check",
          "fix_line_coverage", "behaviour_diff", "break_my_fix", "audit", "blind")  # fmt: skip


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    files = {"pkg/__init__.py": "", "pkg/calc.py": CALC, "tests/test_calc.py": TESTS}
    return make_repo(tmp_path / "repo", [files, {"pkg/calc.py": FIXED}])


def request(repo: Path, **changes: Any) -> Request:
    return replace(Request(repo, "c0", "c1", ISSUE), **changes)


def results() -> dict[str, object]:
    """A run whose every stage meets its level's conditions (L4)."""
    env = EnvironmentCheck(EnvStatus.OK, "base suite passed", None, None, run_result())
    return {
        "_environment": env,
        "origin_check": OriginCheck(EnvStatus.OK, "1 changed module import(s)", (), ()),
        "reproduce": repro(),
        "guard": guard(),
        "regressions_check": regressions(),
        "fix_line_coverage": FixLineCoverage({}, {}, ()),
        "behaviour_diff": behaviour(),
        "break_my_fix": attack(),
        "audit": integrity(),
        "blind": BlindResult(BlindStatus.REPRODUCED, "attempt 1", "t.py", "def test_x(): pass\n"),
    }


def stub(monkeypatch: pytest.MonkeyPatch, **overrides: object) -> list[tuple[str, tuple[Any, ...]]]:
    """Replace the stage functions: a result is returned, an exception raised, a function called
    with the stage's arguments. Returns the calls made, in order."""
    calls: list[tuple[str, tuple[Any, ...]]] = []
    for name, result in {**results(), **overrides}.items():

        def fake(*args: Any, _name: str = name, _result: object = result) -> object:
            calls.append((_name, args))
            if isinstance(_result, BaseException):
                raise _result
            if callable(_result):
                return _result(*args)
            return _result

        monkeypatch.setattr(pipeline, name, fake)
    return calls


def test_every_stage_runs_in_order_and_the_summary_comes_last(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = stub(monkeypatch)
    provider = FakeProvider([SUMMARY])
    lines: list[str] = []
    verified = verify(request(repo), provider, lines.append)
    assert [name for name, _ in calls] == list(CALLED)
    run, receipt = verified.run, verified.receipt
    assert run.status is RunStatus.OK and [s.name for s in run.stages] == list(STAGES)
    assert all(s.error is None and s.duration_s >= 0 for s in run.stages)
    assert receipt.level is EvidenceLevel.L4
    assert receipt.summary == Summary(text=SUMMARY["summary"], by="judge")
    assert [r.role for r in provider.requests] == ["judge"]  # after the level, words only
    assert receipt.llm.calls == 1
    # Each stage gets what the earlier ones found.
    args = dict(calls)
    found_repro, found_guard = results()["reproduce"], results()["guard"]
    assert args["guard"][2] == found_repro and args["fix_line_coverage"][2] == found_repro
    assert args["behaviour_diff"][2:4] == (found_repro, ISSUE)
    assert args["behaviour_diff"][5] == found_guard and args["break_my_fix"][5] == found_guard
    assert args["regressions_check"][2] == results()["_environment"]
    assert args["blind"][2:4] == (found_repro, ISSUE)
    # One progress line per stage, plus start, summary and level; ASCII for any console.
    assert len(lines) == len(STAGES) + 3 and all(line.isascii() for line in lines)
    assert lines[-1] == "level: L4"


def test_the_blind_stage_is_last_of_the_stages_and_its_test_is_saved(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = stub(monkeypatch)
    verified = verify(request(repo), FakeProvider([SUMMARY]))
    assert calls[-1][0] == "blind" and verified.run.stages[-1].name == BLIND
    out = tmp_path / "out"
    write_out(out, verified)
    saved = (out / "repro" / "test_tracefix_blind.py").read_text(encoding="utf-8")
    assert saved == "def test_x(): pass\n"


@pytest.mark.parametrize(
    ("result", "status"),
    [(KeyError("x"), "error"),
     (BlindResult(BlindStatus.FAILS_ON_HEAD, "attempt 1", "t.py", "code"), "fails_on_head")],
)  # fmt: skip
def test_the_blind_stage_never_moves_the_level(
    repo: Path, monkeypatch: pytest.MonkeyPatch, result: object, status: str
) -> None:
    stub(monkeypatch, blind=result)
    verified = verify(request(repo), FakeProvider([SUMMARY]))
    assert verified.receipt.level is EvidenceLevel.L4
    assert next(s for s in verified.receipt.stages if s.name == BLIND).status == status


def test_tampering_by_the_blind_test_makes_its_stage_invalid_and_caps_the_level(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one way it reaches a level, by the ladder's rule for any stage: a test that changes the
    other copy or the verifier's files means what ran afterwards can't be trusted (SPEC §4)."""
    stub(monkeypatch, blind=TamperingDetected("tampering detected: a file changed"))
    verified = verify(request(repo), FakeProvider([SUMMARY]))
    assert verified.run.stage(BLIND).status == "invalid"  # type: ignore[union-attr]
    assert verified.receipt.level is not EvidenceLevel.L4


def test_a_blind_model_failure_is_named_for_its_stage_and_moves_nothing(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real stage: the model call fails, the stage ends `not_run`, and the problem is on it."""
    stub(monkeypatch)
    monkeypatch.setattr(pipeline, "blind", real_blind)
    verified = verify(request(repo), FakeProvider([]))
    assert verified.receipt.level is EvidenceLevel.L4
    entry = next(s for s in verified.receipt.stages if s.name == BLIND)
    assert entry.status == "not_run" and [p.role for p in entry.problems] == ["reproducer"]


def test_a_stage_that_raises_is_an_error_with_no_evidence_and_the_run_goes_on(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = stub(monkeypatch, break_my_fix=KeyError("target"))
    verified = verify(request(repo), FakeProvider([SUMMARY]))
    record = verified.run.stage("break_my_fix")
    assert record is not None and record.status == "error" and record.result is None
    assert record.error is not None and "KeyError: 'target'" in record.error
    assert "test_pipeline.py" in record.error  # where it came from, without a machine path
    assert [name for name, _ in calls[-2:]] == ["audit", "blind"]  # the later stages still ran
    # No evidence from the failed stage: L4 needs Break My Fix.
    assert verified.receipt.level is EvidenceLevel.L3
    assert "break_my_fix: failed inside Tracefix" in verified.receipt.unchecked


def test_without_a_reproduction_result_the_stages_that_need_one_are_skipped(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = stub(monkeypatch, reproduce=RuntimeError("bug"))
    verified = verify(request(repo), FakeProvider([SUMMARY]))
    statuses = {s.name: (s.status, s.reason) for s in verified.run.stages}
    for name in ("guard", "fix_line_coverage", "integrity"):
        assert statuses[name] == ("skipped", NO_REPRO)
    assert [name for name, _ in calls] == ["_environment", "origin_check", "reproduce",
                                           "regressions_check", "behaviour_diff",
                                           "break_my_fix", "blind"]  # fmt: skip
    assert dict(calls)["break_my_fix"][2] is None and dict(calls)["break_my_fix"][5] is None
    assert verified.receipt.level is EvidenceLevel.L0


def test_tampering_a_stage_does_not_catch_makes_it_invalid_and_caps_the_level(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tampered = TamperingDetected(["the copy under test: pkg/calc.py"])
    stub(monkeypatch, fix_line_coverage=tampered)
    verified = verify(request(repo), FakeProvider([SUMMARY]))
    record = verified.run.stage("fix_line_coverage")
    assert record is not None and record.status == "invalid" and "pkg/calc.py" in record.reason
    assert verified.run.status is RunStatus.OK  # later stages still ran
    assert verified.receipt.level is EvidenceLevel.L0
    assert [t.stage for t in verified.receipt.tampering] == ["fix_line_coverage"]


@pytest.mark.parametrize(
    ("name", "result", "status"),
    [
        ("_environment", EnvironmentCheck(EnvStatus.ENVIRONMENT_ERROR, "no pytest", "Error", None,
                                          run_result()), RunStatus.ENVIRONMENT_ERROR),
        ("origin_check", OriginCheck(EnvStatus.ENVIRONMENT_ERROR, "imported from elsewhere", (),
                                     ()), RunStatus.ENVIRONMENT_ERROR),
        ("_environment", TamperingDetected(["x"]), RunStatus.INVALID),
        ("origin_check", TamperingDetected(["x"]), RunStatus.INVALID),
        ("_environment", ValueError("bug"), RunStatus.ERROR),
        ("origin_check", ValueError("bug"), RunStatus.ERROR),
    ],
)  # fmt: skip
def test_the_environment_checks_stop_the_run(
    repo: Path, monkeypatch: pytest.MonkeyPatch, name: str, result: object, status: RunStatus
) -> None:
    calls = stub(monkeypatch, **{name: result})
    provider = FakeProvider([])
    verified = verify(request(repo), provider)
    assert verified.run.status is status and verified.receipt.level is EvidenceLevel.L0
    assert calls[-1][0] == name and len(verified.run.stages) == CALLED.index(name) + 1
    assert provider.requests == []  # no model call, not even the summary
    assert verified.receipt.summary.by == "tracefix"
    assert verified.run.status_reason in verified.receipt.level_reasons[0]


def test_a_project_python_that_cannot_be_used_stops_the_run_in_fixed_words(
    repo: Path, tmp_path: Path
) -> None:
    """M10 part 2: --python names no usable interpreter. The environment stage says why (no
    machine path) and nothing else runs; the receipt is written as for any environment error."""
    provider = FakeProvider([])
    verified = verify(request(repo, python=str(tmp_path / "no-python")), provider)
    run, receipt = verified.run, verified.receipt
    assert run.status is RunStatus.ENVIRONMENT_ERROR and run.python is None
    assert [(s.name, s.status) for s in run.stages] == [("environment", "ENVIRONMENT_ERROR")]
    assert run.status_reason == "the project's Python (--python) was not found"
    assert receipt.level is EvidenceLevel.L0 and provider.requests == []
    assert receipt.isolation.python is None
    assert str(tmp_path) not in receipt.model_dump_json()


def test_the_project_s_python_runs_every_test_and_the_receipt_names_its_version(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python = old_python("3.9")
    environment = pipeline._environment  # the real one: the base suite runs with Python 3.9
    calls = stub(monkeypatch, _environment=environment)
    lines: list[str] = []
    verified = verify(request(repo, python=str(python)), FakeProvider([SUMMARY]), lines.append)
    run, receipt = verified.run, verified.receipt
    assert run.python is not None and run.python.label.startswith("3.9.")
    assert receipt.isolation.python == run.python.label
    ws = dict(calls)["origin_check"][0]
    assert ws.settings.python == run.python  # every later stage's runs use it (run_checked)
    env = run.stage("environment")
    assert env is not None and env.status == "ok"
    assert env.result.run.command[:3] == (str(python.absolute()), "-c", BOOTSTRAP)
    entry = next(s for s in receipt.stages if s.name == "environment")
    assert entry.commands[0].startswith(f"python -c {BOOTSTRAP} -q ")  # no machine path
    assert f", Python {run.python.label})" in lines[0]


def test_without_python_the_receipt_names_no_version(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = stub(monkeypatch)
    verified = verify(request(repo), FakeProvider([SUMMARY]))
    assert verified.run.python is None and verified.receipt.isolation.python is None
    assert dict(calls)["origin_check"][0].settings.python.own


class _Answer(BaseModel):
    text: str


def _ask(client: LLMClient, role: Any) -> None:
    with contextlib.suppress(LLMError):  # stages carry on after a model problem
        client.complete(role, "system", [Message("user", "hi")], _Answer)


def test_model_problems_and_the_budget_show_on_the_stage_that_hit_them(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def reproduce(*args: Any) -> ReproResult:
        client = args[3]
        _ask(client, "reproducer")  # within the budget of 1 call
        _ask(client, "reproducer")  # over it
        return repro()

    stub(monkeypatch, reproduce=reproduce)
    flags = FileSettings(max_llm_calls=1)
    verified = verify(request(repo, flags=flags), FakeProvider([{"text": "ok"}]))
    record = verified.run.stage("reproduce")
    assert record is not None and [p.kind for p in record.problems] == ["budget"]
    assert all(not s.problems for s in verified.run.stages if s.name != "reproduce")
    assert [p.kind for p in verified.run.problems] == ["budget"]  # the summary call
    receipt = verified.receipt
    assert receipt.summary.by == "tracefix" and receipt.llm.settings.max_calls == 1
    assert [(p.stage, p.kind) for p in receipt.llm.problems] == [("reproduce", "budget"),
                                                                 ("summary", "budget")]  # fmt: skip


class _Broken:
    """A provider with a bug of its own: not an LLMError."""

    def send(self, request: object) -> object:
        raise RuntimeError("provider bug")


def test_a_bug_in_the_summary_call_keeps_the_receipt(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The summary is words only, the last call: it must never cost the run (verifier S6)."""
    stub(monkeypatch)
    verified = verify(request(repo), _Broken())  # type: ignore[arg-type]
    receipt = verified.receipt
    assert receipt.summary.by == "tracefix"
    assert receipt.level is level(verified.run).level
    said = "summary: the Judge's summary call failed inside Tracefix: RuntimeError: provider bug"
    assert any(n.startswith(said) for n in receipt.notes), receipt.notes


def test_the_client_carries_every_model_setting(repo: Path) -> None:
    flags = FileSettings(max_llm_calls=7, token_budget=20_000, max_tokens=2_000, effort="high",
                         models={"adversary": "claude-sonnet-5-5"})  # fmt: skip
    *_, settings = pipeline.settings_for(request(repo, flags=flags))
    client = client_for(FakeProvider([]), settings)
    assert (client.max_calls, client.token_budget, client.max_tokens, client.effort) == (
        7, 20_000, 2_000, "high")  # fmt: skip
    assert client.models["adversary"] == "claude-sonnet-5-5"
    assert client.models["reproducer"] == settings.models["reproducer"]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"base": "nope"}, "unknown ref"),
        ({"base": "c1"}, "the base and head commits hold the same files"),
        ({"config_file": Path("missing.yml")}, "can't read missing.yml"),
    ],
)
def test_nothing_to_verify_raises_setup_error(
    repo: Path, changes: dict[str, Any], message: str
) -> None:
    with pytest.raises(SetupError, match=message):
        verify(request(repo, **changes), FakeProvider([]))


def test_not_a_repo_raises_setup_error(tmp_path: Path) -> None:
    with pytest.raises(SetupError, match="not a git repository"):
        verify(request(tmp_path), FakeProvider([]))


def _no_copies(*_args: object) -> None:
    raise AssertionError("a copy of the code was made")


def test_require_strict_at_basic_isolation_stops_before_any_copy(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Untrusted code (a fork PR, plan P2) may only run inside bubblewrap: without it, nothing
    runs and the probe's reason is the message."""
    monkeypatch.setattr(pipeline, "probe", lambda: ("basic", "bubblewrap (bwrap) is not installed"))
    monkeypatch.setattr(pipeline, "Workspace", _no_copies)
    provider = FakeProvider([])
    with pytest.raises(SetupError) as exc:
        verify(request(repo, require_strict=True), provider)
    assert str(exc.value) == ("strict isolation is required, but this run would be basic: "
                              "bubblewrap (bwrap) is not installed")  # fmt: skip
    assert provider.requests == []


def test_require_strict_at_strict_isolation_runs(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pipeline, "probe", lambda: ("strict", "bubblewrap works"))
    stub(monkeypatch)
    verified = verify(request(repo, require_strict=True), FakeProvider([SUMMARY]))
    assert verified.run.isolation == "strict" and verified.receipt.level is EvidenceLevel.L4


def test_without_require_strict_basic_isolation_runs(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pipeline, "probe", lambda: ("basic", "bubblewrap needs Linux"))
    stub(monkeypatch)
    verified = verify(request(repo), FakeProvider([SUMMARY]))
    assert verified.run.isolation == "basic" and verified.run.status is RunStatus.OK


# --- real runs ------------------------------------------------------------------------------------


def test_a_diff_that_cannot_be_read_is_an_error_status(tmp_path: Path) -> None:
    """NOTES 25: a crafted `..` tree entry makes git refuse the diff."""
    repo = crafted_repo(tmp_path / "repo")
    verified = verify(request(repo), FakeProvider([]))
    assert verified.run.status is RunStatus.ERROR and verified.run.stages == ()
    assert "the fix's diff can't be read (WorkspaceError" in verified.run.status_reason
    assert verified.receipt.level is EvidenceLevel.L0
    assert any("not copied: head: a/../../../evil.py" in n for n in verified.receipt.notes)


def test_tampering_during_the_environment_check_makes_the_run_invalid(tmp_path: Path) -> None:
    conftest = "from pathlib import Path\n\n(Path(__file__).parent / 'pkg' / 'calc.py').write_text('x = 1\\n')\n"  # noqa: E501
    files = {"pkg/__init__.py": "", "pkg/calc.py": CALC, "tests/test_calc.py": TESTS,
             "conftest.py": conftest}  # fmt: skip
    repo = make_repo(tmp_path / "repo", [files, {"pkg/calc.py": FIXED}])
    verified = verify(request(repo), FakeProvider([]))
    assert verified.run.status is RunStatus.INVALID
    assert [(s.name, s.status) for s in verified.run.stages] == [("environment", "invalid")]
    assert "pkg/calc.py" in verified.run.status_reason
    assert verified.receipt.level is EvidenceLevel.L0
    assert [t.stage for t in verified.receipt.tampering] == ["environment"]


def test_a_base_that_cannot_be_collected_but_head_can_is_worded_as_such(tmp_path: Path) -> None:
    """NOTES 7: the bug itself may be the import error; head's suite only words the message."""
    broken = "from pkg.missing import helper\n\n\n" + CALC
    files = {"pkg/__init__.py": "", "pkg/calc.py": broken, "tests/test_calc.py": TESTS}
    repo = make_repo(tmp_path / "repo", [files, {"pkg/calc.py": FIXED}])
    verified = verify(request(repo), FakeProvider([]))
    assert verified.run.status is RunStatus.ENVIRONMENT_ERROR
    reason = verified.run.status_reason
    assert "cannot import 'pkg.missing'" in reason and "but the suite runs after the fix" in reason
    assert "perhaps because of the bug itself" in reason


class _Failing:
    """Every call fails: a rate limit for the adversary, an overloaded API for the rest."""

    def send(self, request: LLMRequest) -> Any:
        if request.role == "adversary":
            raise LLMProviderError("rate limited", "rate_limit", 429)
        raise LLMProviderError("overloaded", "api_unavailable", 529)


def test_a_whole_run_attributes_a_rate_limit_to_break_my_fix_only(repo: Path) -> None:
    lines: list[str] = []
    verified = verify(request(repo), _Failing(), lines.append)
    run, receipt = verified.run, verified.receipt
    assert run.status is RunStatus.OK and [s.name for s in run.stages] == list(STAGES)
    assert all(s.error is None for s in run.stages), [s.error for s in run.stages]
    hit = {(s.name, p.kind) for s in run.stages for p in s.problems}
    assert ("break_my_fix", "rate_limit") in hit and ("reproduce", "api_unavailable") in hit
    assert {name for name, kind in hit if kind == "rate_limit"} == {"break_my_fix"}
    assert receipt.level is EvidenceLevel.L0  # nothing reproduced: the model never answered
    assert receipt.summary.by == "tracefix"
    words = [p.words for p in receipt.llm.problems if p.stage == "break_my_fix"]
    assert words and all("HTTP 429" in w and "not because of the fix" in w for w in words)
    assert all(line.isascii() for line in lines)


def test_the_last_receipt_is_replayed_right_after_the_import_check(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = Previous("c" * 40, "L2", "2026-10-14T09:00:00+00:00")
    replayed = PreviousResult(PreviousStatus.SKIPPED, "the last receipt has no findings",
                              old.head_sha, old.level, old.created_at)  # fmt: skip
    calls = stub(monkeypatch, replay=replayed)
    plain_provider, provider = FakeProvider([SUMMARY]), FakeProvider([SUMMARY])
    plain = verify(request(repo), plain_provider)
    calls.clear()
    lines: list[str] = []
    verified = verify(request(repo, previous=old), provider, lines.append)
    names = [name for name, _ in calls]
    assert names == [*CALLED[:2], "replay", *CALLED[2:]]
    assert dict(calls)["replay"][1] is old
    assert [s.name for s in verified.run.stages] == list(planned(True))
    assert lines[3] == f"[3/{len(STAGES) + 1}] previous: skipped (0.0s)"
    assert lines[-1] == "level: L4" and verified.receipt.previous is not None
    # The Judge is asked exactly what it is asked without the replay (recordings still match).
    assert provider.requests == plain_provider.requests
    assert plain.receipt.previous is None and len(plain.run.stages) == len(STAGES)

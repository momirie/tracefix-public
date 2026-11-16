"""Synthetic stage results and run records for the ladder and receipt tests (no runs, no model)."""

from dataclasses import replace
from typing import Any

from tracefix.attack import (
    AttackResult,
    AttackStatus,
    Finding,
    PropertyResult,
    TargetReport,
)
from tracefix.behaviour_diff import BehaviourResult, BehaviourStatus
from tracefix.behaviour_rules import Gate
from tracefix.config import FileSettings, Settings, resolve
from tracefix.guard import GuardResult, GuardStatus, Mutant, MutantResult, MutantStatus
from tracefix.integrity import IntegrityFlag, IntegrityResult, IntegrityStatus
from tracefix.record import RunRecord, RunStatus, StageRecord
from tracefix.regressions import Regression, RegressionResult, RegressionStatus
from tracefix.repro import ReproResult, ReproStatus
from tracefix.runner import Attempt, Outcome, RunResult

PATH = "pkg/calc.py"
FIX_LINES = ((PATH, (3, 4)),)


def settings() -> Settings:
    return resolve(FileSettings(), FileSettings())


def run_result(*command: str, outcome: Outcome = Outcome.PASSED) -> RunResult:
    return RunResult(outcome, command, (Attempt(0, 0.1, (), ""),))


def prop(target: str = "t1", **changes: Any) -> PropertyResult:
    base = PropertyResult(id="p1", target=target, name="never negative", kind="invariant",
                          claim="result >= 0", source="issue", quote="must never be negative",
                          status="counted", constrains_result=True, origin="model")  # fmt: skip
    return replace(base, **changes)


def target(tid: str = "t1", **changes: Any) -> TargetReport:
    base = TargetReport(id=tid, function=f"pkg.calc.f_{tid}", path=PATH, attacked=True,
                        inputs_tried=150, reached=FIX_LINES, finished=True)  # fmt: skip
    return replace(base, **changes)


def attack(**changes: Any) -> AttackResult:
    """A Break My Fix result that meets every L4 condition."""
    base = AttackResult(AttackStatus.NONE_FOUND, "nothing found", properties=(prop(),),
                        targets=(target(),), fix_lines=FIX_LINES)  # fmt: skip
    return replace(base, **changes)


def finding(number: int = 1, **changes: Any) -> Finding:
    base = Finding(number=number, function="pkg.calc.f_t1", target="t1",
                   input=(("x", "-1"),), outcome={"kind": "returned", "repr": "-1"},
                   property=prop(), base_outcome={"kind": "returned", "repr": "-1"},
                   repro_code="def test_break_my_fix_1() -> None:\n    assert False\n")  # fmt: skip
    return replace(base, **changes)


def repro(status: ReproStatus = ReproStatus.REPRODUCED, **changes: Any) -> ReproResult:
    base = ReproResult(status, f"{status.value}", "tests/test_tracefix_repro.py",
                       "def test_bug() -> None:\n    assert True\n", (), ())  # fmt: skip
    return replace(base, **changes)


def guard(status: GuardStatus = GuardStatus.GUARDED, **changes: Any) -> GuardResult:
    return replace(GuardResult(status, status.value), **changes)


def mutant(number: int = 1, status: MutantStatus = MutantStatus.SURVIVED, **changes: Any
           ) -> MutantResult:  # fmt: skip
    m = Mutant(number=number, path=PATH, line=3, original="x < 0", replacement="x <= 0",
               description="off by one", diff="--- a\n+++ b\n", text="")  # fmt: skip
    return MutantResult(replace(m, **changes), status, (), (), False, "", ())


def behaviour(l3: bool = True, **changes: Any) -> BehaviourResult:
    gate = Gate(True) if l3 else Gate(False, ("a change nothing explains",))
    base = BehaviourResult(BehaviourStatus.COMPARED, "compared", checks=gate, l3=gate)
    return replace(base, **changes)


def integrity(*flags: IntegrityFlag) -> IntegrityResult:
    if flags:
        return IntegrityResult(IntegrityStatus.FLAGGED, "flagged", flags=flags)
    return IntegrityResult(IntegrityStatus.CLEAN, "clean")


def flag() -> IntegrityFlag:
    return IntegrityFlag(kind="weakened_assert", file="tests/test_calc.py", line=7,
                         detail="assert loosened", evidence="fails on head with the old assert",
                         test="test_calc")  # fmt: skip


def regressions(*found: Regression) -> RegressionResult:
    if found:
        return RegressionResult(RegressionStatus.FOUND, "found", regressions=found, compared=5)
    return RegressionResult(RegressionStatus.NONE_FOUND, "none", compared=5)


def regression() -> Regression:
    return Regression(file="tests/test_other.py", test="test_total",
                      evidence="passed on base every time, failed on head 4 times")  # fmt: skip


def stage(name: str, result: object | None, status: str | None = None, **changes: Any
          ) -> StageRecord:  # fmt: skip
    own = getattr(result, "status", None)
    shown = status or (own.value if own is not None else "ok")
    return replace(StageRecord(name, shown, getattr(result, "reason", ""), 1.0, result), **changes)


def run(*stages: StageRecord, **changes: Any) -> RunRecord:
    base = RunRecord(status=RunStatus.OK, status_reason="", repo_name="calc", base_ref="main",
                     base_sha="a" * 40, head_ref="fix", head_sha="b" * 40,
                     issue="# f returns a negative number\n\nf(-1) gives -1.", settings=settings(),
                     isolation="basic", isolation_why="bubblewrap needs Linux",
                     stages=stages)  # fmt: skip
    return replace(base, **changes)


def l4_run(**overrides: object) -> RunRecord:
    """A run whose every stage meets its level's conditions (L4); `overrides` replace a stage's
    result by name (None: the stage raised inside Tracefix)."""
    results: dict[str, object | None] = {
        "reproduce": repro(), "guard": guard(), "regressions": regressions(),
        "behaviour_diff": behaviour(), "break_my_fix": attack(), "integrity": integrity(),
    }  # fmt: skip
    results.update(overrides)
    records = [
        stage(name, result) if result is not None
        else StageRecord(name, "error", "Tracefix raised", 0.0, None, error="KeyError: 'x'")
        for name, result in results.items()
    ]  # fmt: skip
    return run(*records)

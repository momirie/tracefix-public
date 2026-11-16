"""What one run produced: each stage's result and how it went (SPEC 2.8, plan P1/P2).

The pipeline fills a `RunRecord`; the ladder and the receipt read only this, so the level and the
receipt can't disagree about what happened.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, TypeVar

from tracefix.config import Settings
from tracefix.interpreter import Interpreter
from tracefix.llm import CallRecord, Problem
from tracefix.sandbox import Level

if TYPE_CHECKING:
    from tracefix.previous import StillOpen

T = TypeVar("T")

BLIND = "blind"  # report only, so last: its model calls can't use up a stage a level reads
# The stages, in the order the pipeline runs them (the receipt lists them in this order).
STAGES = (
    "environment",  # the base suite runs (runner.EnvironmentCheck)
    "import_check",  # every changed module imports from the copy (envcheck.OriginCheck)
    "reproduce",
    "guard",
    "regressions",
    "fix_line_coverage",
    "behaviour_diff",
    "break_my_fix",
    "integrity",
    BLIND,
)
# Optional: replays the last receipt's findings (`--previous`), right after import_check. Not in
# STAGES, so a run without it, its receipt and its progress lines are as before.
PREVIOUS = "previous"


def planned(previous: bool) -> tuple[str, ...]:
    """The stages a run goes through, in order."""
    if not previous:
        return STAGES
    at = STAGES.index("import_check") + 1
    return (*STAGES[:at], PREVIOUS, *STAGES[at:])


class RunStatus(StrEnum):
    OK = "ok"  # the stages ran (any may be skipped, inconclusive or invalid)
    ENVIRONMENT_ERROR = "ENVIRONMENT_ERROR"  # the base suite can't run, or code from elsewhere
    INVALID = "INVALID"  # tampering during the environment check: nothing could run safely
    ERROR = "ERROR"  # the fix's diff can't be read, or a check every stage relies on failed


@dataclass(frozen=True)
class StageRecord:
    name: str  # one of STAGES, or PREVIOUS
    status: str  # the stage's own status value, e.g. "reproduced" or "invalid"
    reason: str
    duration_s: float = 0.0
    result: object | None = None  # the stage's result (ReproResult, GuardResult, ...)
    problems: tuple[Problem, ...] = ()  # model calls that failed while it ran
    error: str | None = None  # Tracefix's own code raised (a bug): no evidence from this stage


@dataclass(frozen=True)
class RunRecord:
    status: RunStatus
    status_reason: str
    repo_name: str
    base_ref: str
    base_sha: str
    head_ref: str
    head_sha: str
    issue: str
    settings: Settings
    isolation: Level = "basic"
    isolation_why: str = ""
    python: Interpreter | None = None  # the project's Python (--python), when it could be used
    stages: tuple[StageRecord, ...] = ()
    calls: tuple[CallRecord, ...] = ()  # every model call of the run
    problems: tuple[Problem, ...] = ()  # model problems outside any stage (the summary)
    warnings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    # With --previous: the old findings not shown fixed, carried into the receipt (else None).
    still_open: StillOpen | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def stage(self, name: str) -> StageRecord | None:
        return next((s for s in self.stages if s.name == name), None)

    def result(self, kind: type[T]) -> T | None:
        """The result of the stage that produced a `kind` (None: it didn't run, or raised)."""
        return next((s.result for s in self.stages if isinstance(s.result, kind)), None)

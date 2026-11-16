"""The pipeline (SPEC §1, plan P1/P2): every stage, in a fixed order, into one RunRecord.

A deterministic state machine. Each stage runs on whatever the earlier ones found and gets a
record: its own status, reason, duration, result, and the model problems hit while it ran. The
run stops early only when nothing after that point could be trusted: the environment can't run
the tests, tampering during the environment checks, or a diff that can't be read. A stage that
raises inside Tracefix is a bug: that stage is `error`, gives no evidence, and the run goes on.
The level comes from ladder.py and the receipt from receipt.py; the Judge's summary is the last
model call and changes only words.
"""

from __future__ import annotations

import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import ParamSpec, TypeVar

from tracefix import config, interpreter
from tracefix.attack import AttackResult, break_my_fix
from tracefix.behaviour_diff import behaviour_diff
from tracefix.config import ConfigError, FileSettings, Settings
from tracefix.diffscope import DiffScope, compute_scope
from tracefix.envcheck import origin_check
from tracefix.guard import guard
from tracefix.integrity import audit
from tracefix.interpreter import InterpreterCheck
from tracefix.isolation import TamperingDetected, check_environment
from tracefix.judge import JudgeSummary, summarize
from tracefix.linetrace import fix_line_coverage
from tracefix.llm import LLMClient, Provider
from tracefix.previous import Previous, PreviousResult, replay, still_open
from tracefix.receipt import Receipt, build, summary_facts
from tracefix.record import BLIND, PREVIOUS, RunRecord, RunStatus, StageRecord, planned
from tracefix.regressions import check as regressions_check
from tracefix.repro import blind, reproduce
from tracefix.runner import EnvironmentCheck, EnvStatus
from tracefix.sandbox import probe
from tracefix.workspace import (
    RunSettings,
    Workspace,
    WorkspaceError,
    git,
    require_repo,
    resolve_ref,
)

P = ParamSpec("P")
R = TypeVar("R")
Progress = Callable[[str], None]

ERROR_REASON = "Tracefix's own code failed in this stage (a bug in Tracefix): it gives no evidence"
NO_REPRO = "the reproduce stage failed inside Tracefix, so there is no reproduction result"


class SetupError(Exception):
    """Nothing to verify: not a repo, an unknown ref, unusable settings. No receipt (exit 2)."""


@dataclass(frozen=True)
class Request:
    repo: Path
    base: str
    head: str
    issue: str
    config_file: Path | None = None
    flags: FileSettings = field(default_factory=FileSettings)  # from the command line
    require_strict: bool = False  # refuse to run at basic isolation (untrusted code, plan P2)
    previous: Previous | None = None  # the last receipt, to replay its findings (plan P6)
    python: str | None = None  # the project's Python (--python); None: Tracefix's own


@dataclass(frozen=True)
class Verified:
    run: RunRecord
    receipt: Receipt


def _quiet(_line: str) -> None:
    pass


def _where(exc: BaseException) -> str:
    """The exception and the innermost frame it came from (file name only, no machine path)."""
    frames = traceback.extract_tb(exc.__traceback__)
    at = f" at {Path(frames[-1].filename).name}:{frames[-1].lineno}" if frames else ""
    return f"{type(exc).__name__}: {exc}"[:300] + at


def _status_of(result: object) -> tuple[str, str]:
    """A stage result's own status value and reason ("ok" for report-only results)."""
    status = getattr(result, "status", None)
    reason = getattr(result, "reason", "report only: which fix lines the tests run")
    return (status.value if isinstance(status, Enum) else "ok"), str(reason)


class _Stages:
    """Runs stages one at a time and keeps their records."""

    def __init__(self, client: LLMClient, progress: Progress, order: tuple[str, ...]) -> None:
        self.client = client
        self.progress = progress
        self.order = order
        self.records: list[StageRecord] = []

    def run(self, name: str, stage: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R | None:
        """The stage's result, or None when it was tampered with or raised (the record says)."""
        seen = len(self.client.problems)
        start = time.monotonic()
        result: R | None = None
        error = None
        try:
            result = stage(*args, **kwargs)
            status, reason = _status_of(result)
        except TamperingDetected as exc:  # a stage that doesn't catch it itself
            status, reason = "invalid", str(exc)
        except Exception as exc:  # Tracefix's own bug: no evidence from here, the run goes on
            status, reason, error = "error", ERROR_REASON, _where(exc)
        problems = tuple(self.client.problems[seen:])
        self._add(StageRecord(name, status, reason, time.monotonic() - start, result, problems,
                              error))  # fmt: skip
        return result

    def skip(self, name: str, reason: str) -> None:
        self._add(StageRecord(name, "skipped", reason))

    def _add(self, record: StageRecord) -> None:
        self.records.append(record)
        number = self.order.index(record.name) + 1
        self.progress(f"[{number}/{len(self.order)}] {record.name}: {record.status} "
                      f"({record.duration_s:.1f}s)")  # fmt: skip

    @property
    def last(self) -> StageRecord:
        return self.records[-1]


def _environment(ws: Workspace, checked: InterpreterCheck | None = None) -> EnvironmentCheck:
    """The project's Python (when --python was given) must be usable and the base suite must
    run. When it can't be collected, head's suite runs once too, only to say why (NOTES 7): it
    never raises a level."""
    if checked is not None and checked.interpreter is None:
        return EnvironmentCheck(EnvStatus.ENVIRONMENT_ERROR, checked.reason, "Interpreter", None,
                                checked.run)  # fmt: skip
    base = check_environment(ws)
    if base.status is EnvStatus.OK or base.error == "Timeout":
        return base
    head = check_environment(ws, ws.head)
    if head.status is EnvStatus.OK:
        why = (f"{base.reason}, but the suite runs after the fix: the code before the fix can't "
               "be collected, perhaps because of the bug itself, and Tracefix needs a base whose "
               "tests can run")  # fmt: skip
    elif base.module is not None and base.module == head.module:
        why = (f"{base.reason}, before and after the fix: the environment Tracefix runs in lacks "
               f"{base.module!r} (install the project's dependencies and run Tracefix from that "
               "environment)")  # fmt: skip
    else:
        why = (f"{base.reason}, and after the fix too: the environment Tracefix runs in can't run "
               "the project's tests")  # fmt: skip
    return replace(base, reason=why)


def _stopped(stage: StageRecord) -> tuple[RunStatus, str] | None:
    """Why the run stops after one of the environment checks, or None (go on)."""
    if stage.status == "invalid":
        return RunStatus.INVALID, f"tampering during the {stage.name} check: {stage.reason}"
    if stage.status == "error":
        return RunStatus.ERROR, (f"Tracefix's own code failed in the {stage.name} check, which "
                                 f"every later stage relies on ({stage.error})")  # fmt: skip
    if stage.status == EnvStatus.ENVIRONMENT_ERROR.value:
        return RunStatus.ENVIRONMENT_ERROR, stage.reason
    return None


def _stages(ws: Workspace, scope: DiffScope, request: Request, client: LLMClient,
            stages: _Stages, checked: InterpreterCheck | None,
            ) -> tuple[RunStatus, str]:  # fmt: skip
    """Run every stage into `stages`; the run's status and why."""
    issue = request.issue
    env = stages.run("environment", _environment, ws, checked)
    stop = _stopped(stages.last)
    if env is None or stop is not None:
        return stop or (RunStatus.ERROR, stages.last.reason)
    stages.run("import_check", origin_check, ws, scope)
    stop = _stopped(stages.last)
    if stop is not None:
        return stop
    if request.previous is not None:  # runs only on head; only the ladder reads it
        stages.run(PREVIOUS, replay, ws, request.previous)
    repro = stages.run("reproduce", reproduce, ws, scope, issue, client)
    guarded = None
    if repro is None:
        stages.skip("guard", NO_REPRO)
    else:
        guarded = stages.run("guard", guard, ws, scope, repro, client)
    stages.run("regressions", regressions_check, ws, scope, env)
    if repro is None:
        stages.skip("fix_line_coverage", NO_REPRO)
    else:
        stages.run("fix_line_coverage", fix_line_coverage, ws, scope, repro)
    stages.run("behaviour_diff", behaviour_diff, ws, scope, repro, issue, client, guarded)
    stages.run("break_my_fix", break_my_fix, ws, scope, repro, issue, client, guarded)
    if repro is None:
        stages.skip("integrity", NO_REPRO)
    else:
        stages.run("integrity", audit, ws, scope, repro, issue)
    stages.run(BLIND, blind, ws, scope, repro, issue, client)
    return RunStatus.OK, ""


def settings_for(request: Request) -> tuple[str, str, Settings]:
    """The commits and settings of a run; SetupError when there is nothing to verify."""
    try:
        require_repo(request.repo)
        base_sha = resolve_ref(request.repo, request.base)
        head_sha = resolve_ref(request.repo, request.head)
        trees = {git(request.repo, "rev-parse", f"{sha}^{{tree}}").strip()
                 for sha in (base_sha, head_sha)}  # fmt: skip
        if len(trees) == 1:
            raise SetupError("the base and head commits hold the same files: no fix to verify")
        file, source, notes = config.load(request.repo, base_sha, head_sha, request.config_file)
    except (WorkspaceError, ConfigError) as exc:
        raise SetupError(str(exc)) from None
    return base_sha, head_sha, config.resolve(file, request.flags, source, notes, request.python)


def client_for(provider: Provider, s: Settings) -> LLMClient:
    """One client per run, so the call limit and token budget cover the whole run (SPEC §3)."""
    return LLMClient(provider, models=dict(s.models), max_calls=s.max_llm_calls,
                     token_budget=s.token_budget, effort=s.effort,
                     max_tokens=s.max_tokens)  # fmt: skip


def _run(request: Request, ws: Workspace, client: LLMClient, progress: Progress,
         record: RunRecord, checked: InterpreterCheck | None) -> RunRecord:  # fmt: skip
    stages = _Stages(client, progress, planned(request.previous is not None))
    notes = [f"not copied: {s}" for s in ws.skipped]
    try:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
    except (WorkspaceError, RecursionError, OSError) as exc:  # NOTES 25: e.g. a `..` tree entry
        status, why = RunStatus.ERROR, f"the fix's diff can't be read ({type(exc).__name__}: {exc})"
    else:
        status, why = _stages(ws, scope, request, client, stages, checked)
    done = replace(record, status=status, status_reason=why, stages=tuple(stages.records),
                   warnings=tuple(ws.notes), notes=tuple(notes))  # fmt: skip
    if request.previous is None:
        return done
    attack = done.result(AttackResult)
    own = tuple(f.repro_code for f in (attack.findings if attack else ()) if f.repro_code)
    found = still_open(request.previous, done.result(PreviousResult), own)
    return replace(done, still_open=found)


def verify(request: Request, provider: Provider, progress: Progress = _quiet) -> Verified:
    """Verify one fix: the run record and its receipt. Raises SetupError (nothing to verify)."""
    base_sha, head_sha, settings = settings_for(request)
    client = client_for(provider, settings)
    isolation, why = probe()
    if request.require_strict and isolation != "strict":  # before any copy of the code exists
        raise SetupError(f"strict isolation is required, but this run would be {isolation}: {why}")
    # Before any copy of the code exists: the check runs no code from the fix.
    checked = interpreter.check(settings.python, isolation) if settings.python else None
    python = checked.interpreter if checked is not None else None
    record = RunRecord(status=RunStatus.OK, status_reason="",
                       repo_name=request.repo.resolve().name, base_ref=request.base,
                       base_sha=base_sha, head_ref=request.head, head_sha=head_sha,
                       issue=request.issue, settings=settings, isolation=isolation,
                       isolation_why=why, python=python)  # fmt: skip
    on = f", Python {python.label}" if python is not None else ""
    progress(f"tracefix: verifying {base_sha[:7]}..{head_sha[:7]} (isolation: {isolation}{on})")
    ws = Workspace(request.repo, base_sha, head_sha,
                   RunSettings(settings.suite_timeout_s, settings.pytest_plugins,
                               python or interpreter.current()))  # fmt: skip
    try:
        ws.__enter__()
    except WorkspaceError as exc:
        raise SetupError(str(exc)) from None
    try:
        record = _run(request, ws, client, progress, record, checked)
    finally:
        ws.cleanup()
    left = tuple(f"a temporary folder could not be removed: {p}" for p in ws.leftovers)
    record = replace(record, calls=tuple(client.calls), warnings=(*record.warnings, *left))
    receipt = build(record, ws)
    if record.status is RunStatus.OK:  # the summary is the last call: words only (plan P14)
        seen = len(client.problems)
        try:
            judged = summarize(client, request.issue, summary_facts(receipt))
        except Exception as exc:  # words only: a bug here must not lose the receipt (verifier S6)
            judged = JudgeSummary(
                None, notes=(f"the Judge's summary call failed inside Tracefix: {_where(exc)}",)
            )
        record = replace(record, calls=tuple(client.calls),
                         problems=tuple(client.problems[seen:]))  # fmt: skip
        receipt = build(record, ws, judged)
        progress(f"summary: by {receipt.summary.by}")
    progress(f"level: {receipt.level.value}")
    return Verified(record, receipt)

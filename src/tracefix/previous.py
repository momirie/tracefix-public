"""Replaying the last receipt's findings on a new commit (SPEC 2.10, plan P6).

`tracefix verify --previous DIR` names an earlier receipt folder (an earlier `--out`, or the
Action's downloaded artifact). `load` reads it into memory first, within limits: receipt.json
(validated as a `Receipt`) and the counted findings' standalone files. Anything unreadable makes
the stage inconclusive, and the run goes on. `replay` then runs each old finding file on head,
watched, with no reruns: `fixed` needs PASSES clean passes in a row (one pass by luck is not a
fix); every other outcome is named. Nothing here can produce a COUNTEREXAMPLE or raise a level:
the ladder's `previous_gate` only keeps L4 out of reach while an old finding is not shown fixed.
No model is involved.

An old finding stays open until a run shows it fixed (developer, 14 Oct 2026): `still_open` lists
the ones this run did not show fixed, and the receipt carries them (`findings/previous_<n>.py`),
so the next run replays them too, beside the last receipt's own findings. The same check is
carried once (`same_check`), and never beside this run's own finding that runs it. Two ways out
(developer, verifier M9 round 2): a finding that can't run any more (e.g. its function was
renamed) keeps L4 out of reach on that push only, and is not carried; and when a run can't tell
which are open (its last receipt unreadable, or it carried more than MAX_OPEN), its replay is
inconclusive and its receipt starts afresh from its own findings.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from tracefix.attack import FINDING_TIMEOUT_S, expected_failure
from tracefix.attack_rules import Expectation
from tracefix.harness import placed, run_file
from tracefix.isolation import TamperingDetected
from tracefix.runner import Outcome, RunResult
from tracefix.sandbox import BASIC_WARNING, Level, sandbox_level
from tracefix.workspace import Workspace, WorkspaceError

MAX_RECEIPT_BYTES = 5_000_000
MAX_FINDINGS = 5  # Break My Fix keeps at most 5 counted findings (attack.MAX_SHOWN)
MAX_FINDING_CHARS = 50_000
MAX_CALL_CHARS = 300
PASSES = 3  # clean passes in a row for `fixed`
MAX_OPEN = 20  # earlier findings a receipt carries forward (more: the next replay is inconclusive)
UNUSABLE = "unusable.txt"  # instead of receipt.json: the last receipt exists but can't be used
MAX_UNUSABLE_CHARS = 1_000
_SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")

if TYPE_CHECKING:  # receipt.py imports the ladder, which imports this module
    from tracefix.receipt import FindingEntry, OpenFinding


class PreviousError(Exception):
    """--previous names no earlier receipt: nothing to verify against (exit 2)."""


class _Unreadable(Exception):
    """The earlier receipt's content can't be used (the stage is inconclusive)."""


class PreviousStatus(StrEnum):
    REPLAYED = "replayed"  # every old finding was run on head (each has its result)
    SKIPPED = "skipped"  # the last receipt has no findings
    INCONCLUSIVE = "inconclusive"  # its content can't be used, or a run could not be set up
    INVALID = "invalid"  # tampering detected: no result at all


class Replay(StrEnum):
    FIXED = "fixed"  # PASSES clean passes in a row
    STILL_FAILS = "still_fails"  # failed on every attempt, the way the finding said it would
    FAILS_DIFFERENTLY = "fails_differently"  # failed on every attempt, but some other way
    CANNOT_RUN = "cannot_run"  # an import or collection error, e.g. the function was renamed
    FLAKY = "flaky"  # passed and failed in turn
    UNFINISHED = "unfinished"  # a run timed out


# How the ladder and receipt.md say each result (fixed words, never from the files).
WORDS: dict[Replay, str] = {
    Replay.FIXED: "fixed",
    Replay.STILL_FAILS: "still fails",
    Replay.FAILS_DIFFERENTLY: "still fails, in a different way",
    Replay.CANNOT_RUN: "can't run",
    Replay.FLAKY: "passed and failed in turn",
    Replay.UNFINISHED: "did not finish",
}


@dataclass(frozen=True)
class OldFinding:
    number: int
    call: str  # e.g. "parse_port(raw='')"
    file: str  # "findings/finding_<number>.py" (or previous_<number>.py), as the receipt names it
    code: str
    expect: Expectation | None  # None: a receipt from before M9 doesn't say
    path: str | None = None  # where the last receipt put it (its commit's lines; None before M9)
    line: int | None = None
    carried: bool = False  # an earlier finding the last receipt carried, still open there


def label(number: int, carried: bool) -> str:
    """How receipts, the ladder and the Action name an old finding (fixed words)."""
    if carried:
        return f"earlier finding {number} (still open in the last receipt)"
    return f"finding {number} of the last receipt"


@dataclass(frozen=True)
class StillOpen:
    """The old findings this run carries into its receipt. `known` is False when more than
    MAX_OPEN are open: the next run can't know which, so its replay is inconclusive."""

    findings: tuple[OldFinding, ...] = ()
    known: bool = True


@dataclass(frozen=True)
class Previous:
    """An earlier receipt, read into memory. `problem`: why its content can't be used."""

    head_sha: str = ""
    level: str = ""
    created_at: str = ""
    findings: tuple[OldFinding, ...] = ()
    problem: str = ""


@dataclass(frozen=True)
class Replayed:
    number: int
    call: str
    file: str
    result: Replay
    detail: str  # what the runs showed, in words
    path: str | None = None  # the last receipt's place for it (lines of the last receipt's commit)
    line: int | None = None
    carried: bool = False

    @property
    def label(self) -> str:
        return label(self.number, self.carried)


@dataclass(frozen=True)
class PreviousResult:
    status: PreviousStatus
    reason: str
    head_sha: str = ""  # the last receipt's commit ("" when it could not be read)
    level: str = ""
    created_at: str = ""
    findings: tuple[Replayed, ...] = ()
    runs: tuple[tuple[str, RunResult], ...] = ()
    isolation: Level = "basic"
    warnings: tuple[str, ...] = ()


# --- reading the folder ---------------------------------------------------------------------------


def _read(path: Path, limit: int) -> str:
    """A regular file's UTF-8 text, at most `limit` bytes (a link is never followed)."""
    if path.is_symlink() or not path.is_file():
        raise _Unreadable(f"{path.name} is missing or not a regular file")
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise _Unreadable(f"{path.name} is larger than {limit:,} bytes")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise _Unreadable(f"{path.name} is not UTF-8 text") from None


def file_name(number: int, carried: bool) -> str:
    """The standalone file of a counted finding, or of an earlier one carried forward."""
    return f"findings/{'previous' if carried else 'finding'}_{number}.py"


def _old_finding(folder: Path, f: FindingEntry | OpenFinding, carried: bool) -> OldFinding:
    number, call, file = f.number, f.call, f.file
    expect = None if f.expect is None else Expectation(frozenset(f.expect.types), f.expect.in_file)
    name = file_name(number, carried)
    if file != name:
        raise _Unreadable(f"{label(number, carried)} names the file {file!r}, not {name!r}")
    code = _read(folder / name, 4 * MAX_FINDING_CHARS)
    if len(code) > MAX_FINDING_CHARS:
        raise _Unreadable(f"{name} is longer than {MAX_FINDING_CHARS:,} characters")
    try:
        compile(code, name, "exec", dont_inherit=True)
    except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
        raise _Unreadable(f"{name} does not compile ({type(exc).__name__})") from None
    return OldFinding(number, call[:MAX_CALL_CHARS], name, code, expect, f.path, f.line, carried)


def _numbered(numbers: list[int], limit: int, what: str) -> None:
    if len(numbers) > limit:
        raise _Unreadable(f"receipt.json lists {len(numbers)} {what} (at most {limit})")
    if len(set(numbers)) != len(numbers) or any(n < 1 for n in numbers):
        raise _Unreadable(f"receipt.json's {what} numbers are not distinct positive numbers")


def _parsed(folder: Path) -> Previous:
    # Imported here: receipt.py imports the ladder, which imports this module.
    from pydantic import ValidationError

    from tracefix.receipt import Receipt

    text = _read(folder / "receipt.json", MAX_RECEIPT_BYTES)
    try:
        receipt = Receipt.model_validate_json(text, strict=True)
    except ValidationError as exc:
        errors = exc.error_count()
        raise _Unreadable(f"receipt.json is not a valid receipt ({errors} errors)") from None
    if not _SHA.fullmatch(receipt.head.sha):
        raise _Unreadable("receipt.json's head commit is not a commit id")
    try:
        datetime.fromisoformat(receipt.created_at)
    except ValueError:
        raise _Unreadable("receipt.json's creation time is not a date") from None
    _numbered([f.number for f in receipt.findings], MAX_FINDINGS, "findings")
    carried = receipt.previous.still_open if receipt.previous else []
    if receipt.previous and not receipt.previous.still_open_known:
        raise _Unreadable("it could not tell which earlier findings were still open, so they were "
                          "never shown fixed")  # fmt: skip
    _numbered([f.number for f in carried], MAX_OPEN, "earlier open findings")
    findings = (*(_old_finding(folder, f, False) for f in receipt.findings),
                *(_old_finding(folder, f, True) for f in carried))  # fmt: skip
    return Previous(receipt.head.sha, receipt.level.value, receipt.created_at, findings)


def load(folder: Path) -> Previous:
    """The earlier receipt in `folder`, read into memory. Raises PreviousError when there is no
    receipt there; content that can't be used comes back as `problem` (the stage says why). The
    Action writes UNUSABLE instead of a receipt when the last one exists but can't be used."""
    if not folder.is_dir():
        raise PreviousError(f"--previous: {folder} is not a folder")
    if os.path.lexists(folder / UNUSABLE):
        try:
            why = " ".join(_read(folder / UNUSABLE, MAX_UNUSABLE_CHARS).split())
        except (_Unreadable, OSError):
            why = ""
        return Previous(problem=f"the last receipt can't be used: {why or 'no reason given'}")
    if not os.path.lexists(folder / "receipt.json"):
        raise PreviousError(f"--previous: {folder} holds no receipt.json")
    try:
        return _parsed(folder)
    except _Unreadable as exc:
        return Previous(problem=f"the last receipt can't be used: {exc}")
    except OSError as exc:
        return Previous(problem=f"the last receipt can't be read: {exc.strerror or exc}")


# --- replaying on head ----------------------------------------------------------------------------


def _failure(run: RunResult) -> str:
    failures = run.first.failures
    if not failures:
        return f"its run ended {run.outcome}"
    f = failures[0]
    return (f.detail or f.message or f.exc_type or f.kind)[:300]  # detail: an error's E line


def _attempt(run: RunResult, rel: str, expect: Expectation | None) -> tuple[str, str]:
    """One run's kind (pass, same, other, error, timeout) and what it showed."""
    if run.outcome is Outcome.PASSED:
        if run.first.tests == 0 or run.first.skipped:  # a skipped test passes nothing
            return "error", "its test was skipped or never ran"
        return "pass", "passed"
    if run.outcome is Outcome.TIMEOUT:
        return "timeout", f"timed out ({FINDING_TIMEOUT_S} s)"
    if run.outcome is not Outcome.FAILED or any(f.kind != "failure" for f in run.first.failures):
        return "error", f"errored: {_failure(run)}"
    types, in_file = (expect.types, expect.in_file) if expect else (frozenset(), None)
    problem = expected_failure(run, rel, types, in_file)
    if problem is None:
        return "same", f"failed: {_failure(run)}"
    return "other", f"{problem} ({_failure(run)})"


def _verdict(kinds: list[str], details: list[str]) -> tuple[Replay, str]:
    """The finding's result from its attempts (stopped at a timeout or an error)."""
    shown = details[-1]
    if "timeout" in kinds:
        return Replay.UNFINISHED, shown
    if kinds == ["pass"] * PASSES:
        return Replay.FIXED, f"passed {PASSES} times in a row"
    if "pass" in kinds:
        return Replay.FLAKY, "; ".join(dict.fromkeys(details))
    if "error" in kinds:
        return Replay.CANNOT_RUN, shown
    if all(k == "same" for k in kinds):
        return Replay.STILL_FAILS, f"{details[0]} ({len(kinds)} of {len(kinds)} attempts)"
    other = next(d for k, d in zip(kinds, details, strict=True) if k == "other")
    return Replay.FAILS_DIFFERENTLY, other


def _replay_one(ws: Workspace, old: OldFinding, runs: list[tuple[str, RunResult]]) -> Replayed:
    kind = "earlier" if old.carried else "previous"
    rel = placed(ws, f"test_tracefix_{kind}_{old.number}.py")
    kinds: list[str] = []
    details: list[str] = []
    for attempt in range(1, PASSES + 1):
        run = run_file(ws, ws.head, rel, old.code, FINDING_TIMEOUT_S, 0)
        runs.append((f"{label(old.number, old.carried)}, attempt {attempt}", run))
        kind, detail = _attempt(run, rel, old.expect)
        kinds.append(kind)
        details.append(detail)
        if kind in ("timeout", "error"):
            break
    result, detail = _verdict(kinds, details)
    if old.expect is None and result is Replay.STILL_FAILS:
        detail += "; the last receipt doesn't say how it must fail, so any test failure counts"
    return Replayed(old.number, old.call, old.file, result, detail, old.path, old.line, old.carried)


def _summary(found: tuple[Replayed, ...]) -> str:
    counts = {r: sum(f.result is r for f in found) for r in Replay}
    parts = [f"{n} {WORDS[r]}" for r, n in counts.items() if n]
    return f"{len(found)} earlier findings replayed: {', '.join(parts)}"


def _at(previous: Previous, index: int) -> str:
    old = previous.findings[index]
    return label(old.number, old.carried)


def replay(ws: Workspace, previous: Previous) -> PreviousResult:
    """Run each finding of the last receipt on head (watched, no reruns): its result."""
    level = sandbox_level()
    base = PreviousResult(PreviousStatus.REPLAYED, "", previous.head_sha, previous.level,
                          previous.created_at, isolation=level,
                          warnings=(BASIC_WARNING,) if level == "basic" else ())  # fmt: skip
    if previous.problem:
        return replace(base, status=PreviousStatus.INCONCLUSIVE, reason=previous.problem)
    if not previous.findings:
        return replace(base, status=PreviousStatus.SKIPPED,
                       reason="the last receipt has no findings")  # fmt: skip
    runs: list[tuple[str, RunResult]] = []
    found: list[Replayed] = []
    try:
        for old in previous.findings:
            found.append(_replay_one(ws, old, runs))
    except TamperingDetected as exc:  # never a result: the stage is invalid (Decided in M3.5)
        why = f"while replaying {_at(previous, len(found))}: {exc}"
        return replace(base, status=PreviousStatus.INVALID, reason=why, runs=tuple(runs))
    except (OSError, WorkspaceError) as exc:
        why = f"could not replay {_at(previous, len(found))}: {type(exc).__name__}: {exc}"
        return replace(base, status=PreviousStatus.INCONCLUSIVE, reason=why, runs=tuple(runs))
    done = tuple(found)
    return replace(base, reason=_summary(done), findings=done, runs=tuple(runs))


_NUMBERED = re.compile(r"(?m)^#.*$|\b(test_break_my_fix_)[0-9]+\b")


def same_check(code: str) -> str:
    """A finding file's code without its comments and its number: two files with the same key
    run the same check (a later run re-finding a counterexample writes it again)."""
    return " ".join(_NUMBERED.sub(r"\1", code).split())


def still_open(previous: Previous, result: PreviousResult | None,
               own: tuple[str, ...] = ()) -> StillOpen:  # fmt: skip
    """The old findings this run did not show fixed and still carries: not `fixed` and not
    `cannot_run` in a finished replay, all of them when the replay did not finish (the run stopped
    first, tampering, a run that could not be set up); each check once, and none that one of this
    run's own findings (`own`: their files' code) runs. Nothing when the last receipt could not be
    read: this run's replay is inconclusive, and the chain starts afresh from its own findings.
    `known` is False past MAX_OPEN: the next run's replay is inconclusive, then it starts afresh."""
    if previous.problem:
        return StillOpen()
    if result is not None and result.status is PreviousStatus.REPLAYED:
        done = {(f.carried, f.number) for f in result.findings
                if f.result in (Replay.FIXED, Replay.CANNOT_RUN)}  # fmt: skip
        found = [f for f in previous.findings if (f.carried, f.number) not in done]
    else:
        found = list(previous.findings)
    seen = {same_check(code) for code in own}
    kept: list[OldFinding] = []
    for f in found:
        key = same_check(f.code)
        if key not in seen:
            seen.add(key)
            kept.append(f)
    return StillOpen(tuple(kept[:MAX_OPEN]), known=len(kept) <= MAX_OPEN)

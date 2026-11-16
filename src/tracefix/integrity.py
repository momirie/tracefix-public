"""Integrity audit: did the fix weaken its tests or hard-code the reported example? (SPEC 2.7,
Decided in M5)

integrity_rules.py lists candidates from the code alone. Here they are confirmed by runs, every
one watched (isolation.py); only a confirmed candidate becomes a flag (Decided in M5 by the
developer), and every flag is backed by exit codes and JUnit results:

- old tests, new code: the test-layout files and pytest config the PR changed go back to their
  base version, and each changed test file runs twice, in the base copy and in a copy of head. A
  test the PR deleted, weakened or skipped that passes before the fix and fails on it (on the
  check itself, with a real check failure rather than an import or type error) shows the PR's
  test change hid a failure. This mirrors Guard's revert check: Guard puts the source back,
  integrity puts the tests back.
- branch removed (report only): a special case that returns a literal is cut out of head and the
  reproduction test (or else the PR's tests) run again, to show whether the fix depends on the
  hard-coded answer. A fix for one specific value can be legitimate, so it never decides.

Changed expected values, special cases, changed test collection and new pragmas are report only
(Decided in M5 by the developer). No model is involved at all. Tampering makes the stage
invalid, never a verdict.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath

from tracefix.diffscope import DiffScope, FileChange, FileKind
from tracefix.guard import collection_error, fixed_lines, pr_test_candidates, source_files
from tracefix.integrity_rules import (
    CONFIRMABLE,
    Candidate,
    CandidateKind,
    SourceText,
    Value,
    added_pragmas,
    candidates_in_tests,
    config_candidates,
    conftest_candidates,
    evidence_lines,
    special_cases,
    without_branch,
)
from tracefix.isolation import TamperingDetected, run_checked
from tracefix.repro import REPRO_TIMEOUT_S, ReproResult, ReproStatus
from tracefix.runner import FailureInfo, Outcome, RunResult, pytest_config
from tracefix.sandbox import BASIC_WARNING, Level, sandbox_level
from tracefix.variant import swapped, variant_copy
from tracefix.workspace import Workspace, WorkspaceError, blob_text, git_bytes, safe_relpath

MAX_BRANCH_RUNS = 5  # special-case branches checked per audit (report only)
INTEGRITY_RERUNS = 1  # a failure must repeat once to count (as in Guard)
# A check failing: an assert, or pytest's Failed (DID NOT RAISE, pytest.fail).
CHECK_FAILURES = frozenset({"AssertionError", "Failed"})
# The old test no longer fits the new code (an API change), which is not a hidden failure. Any
# other crash (KeyError, ValueError, ...) may be a regression or a deliberate change: unjudged.
DOES_NOT_FIT = frozenset({"ImportError", "ModuleNotFoundError", "AttributeError", "TypeError",
                          "NameError"})  # fmt: skip
CONFIG_NAMES = frozenset({"pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini"})
REPORT_ONLY = "report only (Decided in M5)"
# Decided in M5 by the developer: no fixed rule can tell `if year == 2100: return 28` from a
# legitimate fix for one value (`if status == 429: return True`); Break My Fix (M6) gives the
# general evidence instead.
SPECIAL_CASE_ONLY = "report only (Decided in M5: a fix for one specific value can be legitimate)"
# Kinds that are run for the record: the run is shown with the candidate, never counted.
RECORDED: dict[CandidateKind, str] = {"changed_expectation": REPORT_ONLY,
                                      "special_case": SPECIAL_CASE_ONLY}  # fmt: skip
_PARAM = re.compile(r"\[.*\]$", re.DOTALL)


class IntegrityStatus(StrEnum):
    FLAGGED = "flagged"  # at least one confirmed flag
    CLEAN = "clean"  # every confirmation ran; nothing confirmed
    INCONCLUSIVE = "inconclusive"  # some confirmation could not run or be judged; no flags
    SKIPPED = "skipped"  # the fix changes no test file and no Python source
    INVALID = "invalid"  # tampering detected: no verdict at all


@dataclass(frozen=True)
class IntegrityFlag:
    """A confirmed candidate: it decides the receipt (an integrity flag is a COUNTEREXAMPLE)."""

    kind: CandidateKind
    file: str
    line: int
    detail: str
    evidence: str  # what the runs showed, in words
    test: str | None = None
    literal: Value | None = None


@dataclass(frozen=True)
class IntegrityCandidate:
    """A candidate that was not confirmed, or is report only: shown, never in the verdict."""

    kind: CandidateKind
    file: str
    line: int
    detail: str
    why_not_flag: str
    test: str | None = None
    literal: Value | None = None


@dataclass(frozen=True)
class IntegrityResult:
    status: IntegrityStatus
    reason: str
    flags: tuple[IntegrityFlag, ...] = ()
    candidates: tuple[IntegrityCandidate, ...] = ()
    runs: tuple[tuple[str, RunResult], ...] = ()  # (what was run, its result), in order
    isolation: Level = "basic"
    warnings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


# --- reading the fix ----------------------------------------------------------------------------


def _base_path(change: FileChange) -> str:
    return change.old_path or change.path


def versions(ws: Workspace, change: FileChange) -> tuple[str | None, str | None]:
    """(base text, head text) of a changed file; None where the file doesn't exist on that side
    or isn't UTF-8."""
    base = None if change.status in "AC" else blob_text(ws.repo, ws.base_sha, _base_path(change))
    head = None if change.status == "D" else blob_text(ws.repo, ws.head_sha, change.path)
    return base, head


def test_texts(ws: Workspace, scope: DiffScope) -> tuple[list[SourceText], list[str]]:
    """Each changed test file, named by its base path (candidate lines refer to base), and notes
    on files that can't be read as UTF-8 (never treated as deleted)."""
    found, notes = [], []
    for change in scope.test_files:
        if not _base_path(change).endswith(".py"):
            continue
        base, head = versions(ws, change)
        if (base is None and change.status not in "AC") or (head is None and change.status != "D"):
            notes.append(f"{change.path} is not UTF-8 text, so its tests are not compared")
            continue
        fixed = frozenset() if head is None else fixed_lines(change, len(head.split("\n")))
        found.append(SourceText(_base_path(change), head, base, fixed))
    return found, notes


def config_texts(ws: Workspace, scope: DiffScope) -> list[SourceText]:
    found = []
    for change in scope.files:
        if change.kind is FileKind.OTHER and PurePosixPath(change.path).name in CONFIG_NAMES:
            base, head = versions(ws, change)
            found.append(SourceText(change.path, head, base))
    return found


def evidence(issue: str, repro: ReproResult, tests: Sequence[SourceText]) -> list[str]:
    """Where a special-cased literal may come from: the issue, the repro test, and the lines the
    PR added or changed in its tests."""
    texts = [issue, *(evidence_lines(t) for t in tests)]
    if repro.test_code:
        texts.append(repro.test_code)
    return [t for t in texts if t]


# --- matching JUnit results to candidates (pure) ------------------------------------------


def module_of(tree: Path, path: str) -> str:
    """The dotted name pytest gives the test file at `path` in JUnit reports: its path relative to
    the rootdir the runner pins (the folder of the pytest config that applies, else the copy)."""
    config = pytest_config(tree, [path])
    root = config.parent if config is not None else tree
    try:
        rel = (tree / path).relative_to(root).as_posix()
    except ValueError:
        rel = path
    return rel.removesuffix(".py").replace("/", ".")


def matches(test_id: str, module: str, qualname: str | None) -> bool:
    """A JUnit "classname::name" id belongs to the test `qualname` of the file whose dotted name
    is `module` (any parametrized case of it); with no qualname, to any test of that file."""
    classname, _, name = test_id.partition("::")
    if qualname is None:
        return classname == module or classname.startswith(module + ".")
    *classes, function = qualname.split(".")
    return classname == ".".join([module, *classes]) and _PARAM.sub("", name) == function


def located(failure: FailureInfo, path: str, first: int, last: int) -> bool:
    """The failure's crash site is on lines first..last of `path`."""
    if failure.location is None:
        return False
    file, _, line = failure.location.rpartition(":")
    in_file = file == path or file.endswith("/" + path)
    return in_file and line.isdigit() and first <= int(line) <= last


STILL_PASSES = (False, "the old version still passes on the fixed code: the change hid nothing")


def judge(candidate: Candidate, module: str, before: RunResult,
          after: RunResult) -> tuple[bool | None, str]:  # fmt: skip
    """Whether the old version of a test confirms the candidate: (True, evidence) if it passes
    before the fix and fails on it, on the check itself, with a real check failure; (False,
    why not); (None, why) when the runs can't tell. `module`: the file's JUnit name."""
    ids = {t for t in before.first.passed if matches(t, module, candidate.test)}
    if before.outcome not in (Outcome.PASSED, Outcome.FAILED):
        return None, f"the old tests did not run cleanly before the fix ({before.outcome})"
    if any(matches(t, module, candidate.test) for t in before.first.failed):
        return False, "the old test already failed before the fix"
    if not ids:
        return False, "the old test did not run before the fix (skipped or not collected)"
    if collection_error(after):
        return False, ("the old test file no longer imports on the fixed code: it does not fit "
                       "the new code, which is not a hidden failure")  # fmt: skip
    if after.outcome not in (Outcome.PASSED, Outcome.FAILED):
        return None, f"the old tests could not be judged on the fixed code ({after.outcome})"
    failures = [f for f in after.first.failures if f.test in ids]
    if not failures:
        # Passed only if it is really there: a test id that vanished can't be judged.
        found = ids <= set(after.first.passed)
        return STILL_PASSES if found else (None, "the old test was not found in the run on the "
                                                 "fixed code")  # fmt: skip
    if after.outcome is not Outcome.FAILED:
        return None, f"the old tests could not be judged on the fixed code ({after.outcome})"
    if candidate.pinned:
        last = candidate.end_line or candidate.line
        here = [f for f in failures if located(f, candidate.file, candidate.line, last)]
        # A crash inside the code under test is reported at its deepest frame, so it can't be
        # tied to a line of the test: it may come from this very check.
        elsewhere = [f for f in failures if f.exc_type not in CHECK_FAILURES
                     and not located(f, candidate.file, 1, 10**9)]  # fmt: skip
        if not here and not elsewhere:
            return False, "the old test fails on the fixed code, but not on this check"
        failures = here or elsewhere
    real = [f for f in failures if f.kind == "failure" and (
        candidate.kind == "broadened_raises" or f.exc_type in CHECK_FAILURES)]  # fmt: skip
    if real:
        return True, f"passes before the fix and fails on it: {real[0].message or real[0].exc_type}"
    crash = failures[0].exc_type or failures[0].kind
    if crash in DOES_NOT_FIT:
        return False, (f"the old test errors on the fixed code ({crash}): it no longer fits the "
                       "code, which is not a hidden failure")  # fmt: skip
    return None, (
        f"the old test now raises {crash} on the fixed code: either the fix changed "
        "this behaviour on purpose or it broke it; the runs can't tell which"
    )


# --- the runs -----------------------------------------------------------------------------------


@dataclass
class _Audit:
    ws: Workspace
    scope: DiffScope
    phase: str = "the export of the variant copy"
    runs: list[tuple[str, RunResult]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def run(self, label: str, tree: Path, targets: Sequence[str],
            files: Mapping[str, bytes | None], timeout_s: float) -> RunResult:  # fmt: skip
        self.phase = label
        with swapped(tree, files):
            result = run_checked(self.ws, tree, targets, placed=list(files), timeout_s=timeout_s,
                                 reruns=INTEGRITY_RERUNS)  # fmt: skip
        self.runs.append((label, result))
        return result


def old_test_files(ws: Workspace, scope: DiffScope, wanted: set[str],
                   notes: list[str]) -> tuple[dict[str, bytes | None], list[str]]:  # fmt: skip
    """{path: base bytes, or None to remove} that put every test-layout file the PR changed
    (tests, conftests, helpers, data) and every pytest config it changed back to base in a copy of
    head, and the wanted test files that can be run. The old tests then run as they were written,
    collected the way they were."""
    files: dict[str, bytes | None] = {}
    targets = []
    for change in scope.files:
        path = _base_path(change)
        if change.kind is not FileKind.TEST and PurePosixPath(change.path).name not in CONFIG_NAMES:
            continue
        if safe_relpath(path) is None or safe_relpath(change.path) is None:
            notes.append(f"{change.path} is not a safe path, so its old version is not put back")
            continue
        if change.status in "ACR" and ws.in_head(change.path):
            files[change.path] = None  # added (or the new name of a move): not in the old tests
        if change.status in "AC":
            continue
        try:
            files[path] = git_bytes(ws.repo, "show", f"{ws.base_sha}:{path}")
        except WorkspaceError as exc:
            notes.append(f"{path} could not be put back for the old tests: {exc}")
            continue
        if path in wanted:
            targets.append(path)
    return files, sorted(targets)


# (confirmed, evidence or why not) per candidate; None: the runs could not tell
Judged = dict[Candidate, tuple[bool | None, str]]
NOT_PUT_BACK = (None, "its old version could not be put back")


def _confirm_tests(audit: _Audit, tree: Path, confirmable: Sequence[Candidate],
                   out: Judged) -> None:  # fmt: skip
    files, targets = old_test_files(audit.ws, audit.scope, {c.file for c in confirmable},
                                    audit.notes)  # fmt: skip
    out.update({c: NOT_PUT_BACK for c in confirmable if c.file not in targets})
    # One file at a time: a file that no longer imports stops pytest's whole session, which
    # would otherwise hide every other file's results.
    for target in targets:
        module = module_of(audit.ws.base, target)
        timeout = audit.ws.settings.suite_timeout_s
        before = audit.run(f"the old {target} before the fix", audit.ws.base, [target], {},
                           timeout)  # fmt: skip
        after = audit.run(f"the old {target} on the fixed code", tree, [target], files,
                          timeout)  # fmt: skip
        for c in confirmable:
            if c.file == target:
                out[c] = judge(c, module, before, after)


def _judge_set(audit: _Audit, tree: Path, repro: ReproResult) -> tuple[
        str, tuple[str, ...], dict[str, bytes | None], float] | None:  # fmt: skip
    """The tests that judge a cut branch: the reproduction test, else the PR's test files."""
    if repro.status is ReproStatus.REPRODUCED and repro.test_code is not None:
        return ("the reproduction test", (repro.test_path,),
                {repro.test_path: repro.test_code.encode("utf-8")}, REPRO_TIMEOUT_S)  # fmt: skip
    pr_files = pr_test_candidates(audit.scope, tree)
    if pr_files:
        return "the PR's tests", pr_files, {}, audit.ws.settings.suite_timeout_s
    return None


def _confirm_branches(audit: _Audit, tree: Path, repro: ReproResult, heads: Mapping[str, str],
                      branches: Sequence[Candidate], out: Judged) -> None:  # fmt: skip
    judging = _judge_set(audit, tree, repro)
    if judging is None:
        why = "there is no reproduction test or PR test to confirm it with"
        out.update(dict.fromkeys(branches, (None, why)))
        return
    name, targets, placed, timeout = judging
    baseline = audit.run(f"{name} on the fixed code", tree, targets, placed, timeout)
    if baseline.outcome is not Outcome.PASSED or baseline.first.skipped:
        why = f"{name} does not pass cleanly on the fixed code ({baseline.outcome})"
        out.update(dict.fromkeys(branches, (None, why)))
        return
    for candidate in branches:
        assert candidate.branch is not None  # only hard-coded special cases get here
        cut = without_branch(heads[candidate.file], *candidate.branch)
        if cut is None:
            out[candidate] = (None, "the branch could not be cut out")
            continue
        files = {**placed, candidate.file: cut.encode("utf-8")}
        run = audit.run(f"{name} with the branch at {candidate.file}:{candidate.line} removed",
                        tree, targets, files, timeout)  # fmt: skip
        newly = set(run.first.failed) & set(baseline.first.passed)
        if run.outcome is Outcome.FAILED and newly:
            failure = next(f for f in run.first.failures if f.test in newly)
            out[candidate] = (True, f"with this branch removed, {name} fails: "
                              f"{failure.message or failure.exc_type}")  # fmt: skip
        elif run.outcome in (Outcome.PASSED, Outcome.FAILED):
            out[candidate] = (False, f"with this branch removed, {name} still passes: "
                              "the fix does not depend on it")  # fmt: skip
        else:
            out[candidate] = (None, f"{name} could not be judged without it ({run.outcome})")


# --- the stage --------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Found:
    tests: list[Candidate]  # confirmable or report-only, from the test files
    branches: list[Candidate]  # hard-coded special cases to confirm (capped)
    report_only: list[tuple[Candidate, str]]  # never confirmed, with the reason
    heads: dict[str, str]  # head text of each source file with a special case
    notes: list[str]  # e.g. a source file that can't be read as Python


def _find(ws: Workspace, scope: DiffScope, repro: ReproResult, issue: str) -> _Found:
    tests, unreadable = test_texts(ws, scope)
    sources, notes = source_files(ws, scope)
    notes = unreadable + notes
    texts = [SourceText(s.path, s.head, s.base, s.fixed) for s in sources]
    clues = evidence(issue, repro, tests)
    in_tests = [c for t in tests for c in candidates_in_tests(t)]
    plain = [c for t in tests if PurePosixPath(t.path).name == "conftest.py"
             for c in conftest_candidates(t)]  # fmt: skip
    plain += [c for t in config_texts(ws, scope) for c in config_candidates(t)]
    plain += [c for t in [*tests, *texts] for c in added_pragmas(t)]
    report = [(c, REPORT_ONLY) for c in plain]
    branches: list[Candidate] = []
    places: set[tuple[str, tuple[int, int] | None]] = set()  # one run per branch
    for text in texts:
        for c in special_cases(text, clues):
            if not c.hard_coded:
                report.append((c, "the branch does more than return a literal, so it is not "
                                  "confirmed (report only)"))  # fmt: skip
            elif (c.file, c.branch) not in places and len(places) == MAX_BRANCH_RUNS:
                report.append((c, f"only the first {MAX_BRANCH_RUNS} hard-coded branches are "
                                  "checked"))  # fmt: skip
            else:
                places.add((c.file, c.branch))
                branches.append(c)
    heads = {t.path: t.head for t in texts if t.head is not None}
    return _Found(in_tests, branches, report, heads, notes)


def _to_run(found: _Found) -> list[Candidate]:
    """Test candidates the old-tests run judges (changed expectations only for the record)."""
    return [c for c in found.tests if c.kind in CONFIRMABLE or c.kind in RECORDED]


def _flag(c: Candidate, evidence_text: str) -> IntegrityFlag:
    return IntegrityFlag(c.kind, c.file, c.line, c.detail, evidence_text, c.test, c.literal)


def _candidate(c: Candidate, why: str) -> IntegrityCandidate:
    return IntegrityCandidate(c.kind, c.file, c.line, c.detail, why, c.test, c.literal)


def _assemble(found: _Found, judged: Judged
              ) -> tuple[list[IntegrityFlag], list[IntegrityCandidate], bool]:  # fmt: skip
    """Flags (confirmed, flaggable kinds), candidates, and whether anything went unjudged."""
    flags, candidates, unjudged = [], [], False
    for c in [*found.tests, *found.branches]:
        verdict, text = judged.get(c, (None, "it was not checked"))
        if c.kind in RECORDED:  # the run is shown, never counted
            candidates.append(_candidate(c, f"{RECORDED[c.kind]}; {text}"))
        elif verdict:
            flags.append(_flag(c, text))
        else:
            unjudged = unjudged or verdict is None
            candidates.append(_candidate(c, text))
    candidates += [_candidate(c, why) for c, why in found.report_only]
    return flags, candidates, unjudged


def audit(ws: Workspace, scope: DiffScope, repro: ReproResult, issue: str) -> IntegrityResult:
    """Run the integrity audit on a fix (SPEC 2.7). Never raises for problems in the repo."""
    level = sandbox_level()
    warnings = ((BASIC_WARNING,) if level == "basic" else ()) + tuple(ws.notes)
    if not scope.test_files and not scope.source_files:
        reason = "the fix changes no test file and no Python source file"
        return IntegrityResult(IntegrityStatus.SKIPPED, reason, isolation=level, warnings=warnings)
    found = _find(ws, scope, repro, issue)
    state = _Audit(ws, scope, notes=list(found.notes))
    judged: Judged = {}  # filled run by run, so an error later can't hide a confirmed flag
    error = None
    to_run = _to_run(found)
    try:
        if found.branches or to_run:
            with variant_copy(ws, ws.head_sha, "head") as tree:
                if to_run:
                    _confirm_tests(state, tree, to_run, judged)
                if found.branches:
                    _confirm_branches(state, tree, repro, found.heads, found.branches, judged)
                state.phase = "the final check of the variant copy"
    except TamperingDetected as exc:
        # Never a verdict: the stage is invalid, whatever the runs said (Decided in M3.5).
        return IntegrityResult(IntegrityStatus.INVALID, f"during {state.phase}: {exc}",
                               runs=tuple(state.runs), isolation=level, warnings=warnings,
                               notes=tuple(state.notes))  # fmt: skip
    except (OSError, WorkspaceError, RecursionError) as exc:
        error = f"Integrity could not finish {state.phase}: {type(exc).__name__}: {exc}"
    flags, candidates, unjudged = _assemble(found, judged)
    status, reason = _status(flags, candidates, unjudged, error)
    return IntegrityResult(status, reason, tuple(flags), tuple(candidates), tuple(state.runs),
                           level, warnings, tuple(state.notes))  # fmt: skip


def _status(flags: Sequence[IntegrityFlag], candidates: Sequence[IntegrityCandidate],
            unjudged: bool, error: str | None) -> tuple[IntegrityStatus, str]:  # fmt: skip
    # A flag found before an error stands: an error must never hide confirmed evidence.
    if flags:
        kinds = ", ".join(sorted({f.kind for f in flags}))
        rest = f"; {error}" if error else ""
        return IntegrityStatus.FLAGGED, f"{len(flags)} confirmed: {kinds}{rest}"
    if error or unjudged:
        return IntegrityStatus.INCONCLUSIVE, error or "some candidates could not be judged"
    if candidates:
        return IntegrityStatus.CLEAN, f"no candidate was confirmed ({len(candidates)} reported)"
    return IntegrityStatus.CLEAN, "nothing suspicious in the fix's test or source changes"

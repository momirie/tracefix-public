"""No-regression check: does the fix break a test it left alone? (SPEC 2.9, Decided in M8)

The environment check ran the whole base suite before any change, so we know which tests passed
before the fix. Here the whole suite runs once on head (the runner's reruns on failure). A test
the PR left untouched (`attack_inputs.head_tests`: its file unchanged, or the test and the code
around it unchanged, and no conftest or helper the PR changed in its folder or above) that
passed on base and failed in every head attempt is a candidate, and so is an untouched test file
that no longer collects. Each candidate is confirmed by running the candidates' files again: on
base it must pass in every attempt, on head it must fail in every attempt. A confirmed regression
is a COUNTEREXAMPLE (the developer, M8 plan mode); flaky or unfinished runs are inconclusive,
never a regression. No model is involved. Tampering makes the stage invalid, never a verdict.

Both head runs use --continue-on-collection-errors, so a file that no longer imports neither
hides the rest of the suite nor escapes the reruns. When the PR changes pytest's own options the
two suites are not run the same way, and the check is skipped.
"""

import ast
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from functools import partial
from pathlib import Path, PurePosixPath

from tracefix.attack_inputs import head_tests
from tracefix.diffscope import DiffScope
from tracefix.integrity import config_texts, module_of, versions
from tracefix.integrity_rules import pytest_options
from tracefix.isolation import TamperingDetected, run_checked
from tracefix.runner import Attempt, EnvironmentCheck, Outcome, RunResult
from tracefix.sandbox import BASIC_WARNING, Level, sandbox_level
from tracefix.workspace import Workspace, WorkspaceError

KEEP_GOING = ("--continue-on-collection-errors",)
MAX_LISTED = 5  # tests named in a reason
_NO_MODULE = re.compile(r"ModuleNotFoundError: No module named '([\w.]+)'")


class RegressionStatus(StrEnum):
    FOUND = "found"  # at least one confirmed regression
    NONE_FOUND = "none_found"  # every compared test still passes (or was not run) on head
    INCONCLUSIVE = "inconclusive"  # a run did not finish, or a candidate was not confirmed
    SKIPPED = "skipped"  # nothing comparable: changed pytest options, no base report, no tests
    INVALID = "invalid"  # tampering detected: no verdict at all


@dataclass(frozen=True)
class Compared:
    """One test that passed on base, in a place the PR left untouched."""

    path: str  # head path of its file
    base_path: str  # its file's path at base (differs only for a renamed file)
    base_id: str  # JUnit "classname::name" in the base run
    head_id: str  # the same test's id in a head run
    test: str  # "test_x" or "TestK.test_x[1]", as the receipt names it
    line: int | None = None  # its def line at head


@dataclass(frozen=True)
class Candidate:
    """A compared test that failed in every attempt of the head suite (test None: its file no
    longer collects on head)."""

    file: str
    test: str | None
    tests: tuple[Compared, ...]  # the compared tests it covers (one, or the whole file's)
    head_id: str  # what the head runs report for it
    message: str  # the head suite's failure line, e.g. "AssertionError: assert 2 == 1"


@dataclass(frozen=True)
class Regression:
    """A confirmed regression: it decides the receipt (a COUNTEREXAMPLE)."""

    file: str
    test: str | None  # None: the whole file no longer collects after the fix
    evidence: str  # what the runs showed, in words
    line: int | None = None  # the test's def line at head (None for a whole file)


@dataclass(frozen=True)
class Unconfirmed:
    """A candidate the confirmation runs did not confirm: shown, never in the verdict."""

    file: str
    test: str | None
    why_not: str


@dataclass(frozen=True)
class RegressionResult:
    status: RegressionStatus
    reason: str
    regressions: tuple[Regression, ...] = ()
    unconfirmed: tuple[Unconfirmed, ...] = ()
    compared: int = 0  # tests that passed on base in places the PR left untouched
    not_run: int = 0  # of those, tests head's suite neither passed nor failed (e.g. skipped)
    runs: tuple[tuple[str, RunResult], ...] = ()  # (what was run, its result), in order
    isolation: Level = "basic"
    warnings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


# --- what is compared (pure apart from reading the copies) -------------------------------------


def changed_options(ws: Workspace, scope: DiffScope) -> list[str]:
    """Config files whose pytest options the PR changed: then base's and head's suites don't run
    the same way, so their results can't be compared."""
    return [
        f.path
        for f in config_texts(ws, scope)
        if pytest_options(PurePosixPath(f.path).name, f.base)
        != pytest_options(PurePosixPath(f.path).name, f.head)
    ]


def compared_tests(ws: Workspace, scope: DiffScope, base_passed: Sequence[str]) -> list[Compared]:
    """The base run's passing tests that the PR left untouched, with their ids on head."""
    renamed = {f.path: f.old_path for f in scope.test_files if f.status == "R" and f.old_path}
    cases: dict[tuple[str, str], list[str]] = {}  # (classname, function) -> its cases' names
    for test_id in sorted(set(base_passed)):
        classname, _, case = test_id.partition("::")
        cases.setdefault((classname, case.split("[", 1)[0]), []).append(case)
    found = []
    for file in head_tests(ws, scope):
        base_path = renamed.get(file.path, file.path)
        base_module = module_of(ws.base, base_path)
        head_module = module_of(ws.head, file.path)
        for name, node, untouched in file.tests:
            if not untouched:
                continue
            *classes, function = name.split(".")
            base_class = ".".join([base_module, *classes])
            head_class = ".".join([head_module, *classes])
            for case in cases.get((base_class, function), []):
                test = ".".join([*classes, case])
                found.append(Compared(file.path, base_path, f"{base_class}::{case}",
                                      f"{head_class}::{case}", test, node.lineno))  # fmt: skip
    return found


# --- reading runs (pure) -------------------------------------------------------------------------


def _readable(run: RunResult) -> list[Attempt]:
    return [a for a in run.attempts if a.report_ok]


def failed_every_time(run: RunResult) -> set[str]:
    """Ids that failed or errored in every attempt with a readable report."""
    attempts = _readable(run)
    if not attempts:
        return set()
    return set.intersection(*(set(a.failed) for a in attempts))


def passed_every_time(run: RunResult) -> set[str]:
    attempts = _readable(run)
    if not attempts or len(attempts) != len(run.attempts):
        return set()
    return set.intersection(*(set(a.passed) for a in attempts))


def _message(run: RunResult, test_id: str) -> str:
    """What went wrong, in pytest's words: for a collection error, its own last line (e.g. the
    ModuleNotFoundError) rather than "collection failure"."""
    for failure in run.first.failures:
        if failure.test == test_id:
            return failure.detail or failure.message or failure.exc_type or failure.kind
    return ""


def _imported(text: str | None) -> set[str]:
    """Top-level names of the absolute imports in a file's code (read with `ast`, never run)."""
    try:
        tree = ast.parse(text or "")
    except (SyntaxError, ValueError, RecursionError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def added_imports(ws: Workspace, scope: DiffScope) -> set[str]:
    """Top-level names the PR's changed .py files import on head and did not on base: an
    `import` statement the fix added, not a name it passes to importlib."""
    added: set[str] = set()
    for change in scope.files:
        if change.path.endswith(".py"):
            base, head = versions(ws, change)
            added |= _imported(head) - _imported(base)
    return added


def missing_dependency(ws: Workspace, candidate: Candidate, added: set[str]) -> str | None:
    """Why a candidate is an environment problem, not a regression: on head it fails because a
    module is not installed, the fix added an import of it, and it is no module of either copy
    (the fix needs a dependency this environment lacks; developer, 13 Oct 2026, verifier S2).
    None otherwise: a module a test merely asks for by name, with the same test passing on base,
    is the fix's doing (verifier round 2)."""
    missing = _NO_MODULE.search(candidate.message)
    if missing is None:
        return None
    top = missing.group(1).split(".")[0]
    if top not in added:
        return None
    for copy in ws.copies:
        for path in ws.pristine[copy]:
            parts = PurePosixPath(path).parts
            if top in parts[:-1] or parts[-1] in (f"{top}.py", f"{top}.pyi"):
                return None
    return (f"the fixed code imports {missing.group(1)}, which is not installed in this "
            "environment and is no module of the project: an environment problem, not a "
            "regression")  # fmt: skip


def candidates(ws: Workspace, compared: Sequence[Compared], head: RunResult) -> list[Candidate]:
    """Compared tests that failed in every attempt of the head suite, and compared files whose
    collection failed in every attempt (each such file once, covering all its compared tests)."""
    failed = failed_every_time(head)
    found: list[Candidate] = []
    by_file: dict[str, list[Compared]] = {}
    for c in compared:
        by_file.setdefault(c.path, []).append(c)
    for path, tests in by_file.items():
        module = module_of(ws.head, path)
        # JUnit names a file (or package) that failed to collect "::<dotted name>".
        errors = [f for f in sorted(failed) if f.startswith("::") and _covers(f[2:], module)]
        if errors:
            found.append(Candidate(path, None, tuple(tests), errors[0], _message(head, errors[0])))
            continue
        found += [Candidate(path, c.test, (c,), c.head_id, _message(head, c.head_id))
                  for c in tests if c.head_id in failed]  # fmt: skip
    return found


def _covers(collected: str, module: str) -> bool:
    """A collection error for `collected` (a module or a package) stops `module` collecting."""
    return module == collected or module.startswith(collected + ".")


def confirm(candidate: Candidate, base: RunResult, head: RunResult) -> Regression | Unconfirmed:
    """Confirmed only if every test it covers passes in every base attempt and the head run
    failed the same way in all its attempts, this candidate among them."""
    passed = passed_every_time(base)
    if not all(c.base_id in passed for c in candidate.tests):
        why = (
            "it does not pass again before the fix when its file runs alone"
            if base.outcome not in (Outcome.TIMEOUT, Outcome.ERROR)
            else f"the confirmation run before the fix ended with {base.outcome}"
        )
        return Unconfirmed(candidate.file, candidate.test, why)
    if head.outcome is Outcome.FLAKY:
        why = "its file's results on the fixed code changed between reruns (flaky)"
        return Unconfirmed(candidate.file, candidate.test, why)
    if head.outcome is not Outcome.FAILED:
        why = (
            f"the confirmation run on the fixed code ended with {head.outcome}"
            if head.outcome is not Outcome.PASSED
            else "it passes when its file runs again on the fixed code"
        )
        return Unconfirmed(candidate.file, candidate.test, why)
    if candidate.head_id not in head.first.failed:
        why = "it passes when its file runs again on the fixed code"
        return Unconfirmed(candidate.file, candidate.test, why)
    attempts = len(head.attempts)
    if candidate.test is None:
        evidence = (f"{candidate.file} collected and its {len(candidate.tests)} test(s) passed "
                    f"before the fix; after it the file fails to collect in all {attempts} "
                    f"attempts")  # fmt: skip
    else:
        evidence = (f"passed before the fix (also when its file ran alone); fails after it in all "
                    f"{attempts} attempts")  # fmt: skip
    message = _message(head, candidate.head_id) or candidate.message
    if message:
        evidence += f": {message}"
    line = candidate.tests[0].line if candidate.test is not None else None
    return Regression(candidate.file, candidate.test, evidence, line)


# --- the stage -----------------------------------------------------------------------------------


@dataclass
class _Check:
    ws: Workspace
    phase: str = "reading the tests"
    runs: list[tuple[str, RunResult]] = field(default_factory=list)

    def run(self, label: str, tree: Path, targets: Sequence[str]) -> RunResult:
        self.phase = label
        result = run_checked(self.ws, tree, targets, pytest_args=KEEP_GOING)
        self.runs.append((label, result))
        return result


def check(ws: Workspace, scope: DiffScope, env: EnvironmentCheck) -> RegressionResult:
    """Run the no-regression check (SPEC 2.9). `env` is the environment check's base suite run.
    Never raises for problems in the repo."""
    level = sandbox_level()
    warnings = ((BASIC_WARNING,) if level == "basic" else ()) + tuple(ws.notes)

    result = partial(RegressionResult, isolation=level, warnings=warnings)

    if not env.run.first.report_ok:
        return result(RegressionStatus.SKIPPED, "the base suite's run left no readable report")
    state = _Check(ws)
    try:
        options = changed_options(ws, scope)
        if options:
            reason = (f"the fix changes pytest's options ({', '.join(options)}), so the suites "
                      f"before and after it don't run the same way")  # fmt: skip
            return result(RegressionStatus.SKIPPED, reason)
        compared = compared_tests(ws, scope, env.run.first.passed)
        if not compared:
            return result(RegressionStatus.SKIPPED,
                          "no test the fix left untouched passed before it")  # fmt: skip
        head = state.run("the whole suite on the fixed code", ws.head, ())
        found = candidates(ws, compared, head)
        confirmed: list[Regression] = []
        unconfirmed: list[Unconfirmed] = []
        if found:
            base_files = sorted({c.base_path for f in found for c in f.tests})
            head_files = sorted({f.file for f in found})
            base = state.run("the candidates' files before the fix", ws.base, base_files)
            again = state.run("the candidates' files on the fixed code", ws.head, head_files)
            added = added_imports(ws, scope)
            for candidate in found:
                missing = missing_dependency(ws, candidate, added)
                outcome = (Unconfirmed(candidate.file, candidate.test, missing) if missing
                           else confirm(candidate, base, again))  # fmt: skip
                if isinstance(outcome, Regression):
                    confirmed.append(outcome)
                else:
                    unconfirmed.append(outcome)
        state.phase = "the final check"
    except TamperingDetected as exc:
        # Never a verdict: the stage is invalid, whatever the runs said (Decided in M3.5).
        return result(RegressionStatus.INVALID, f"during {state.phase}: {exc}",
                      runs=tuple(state.runs))  # fmt: skip
    except (OSError, WorkspaceError, RecursionError) as exc:
        reason = f"could not finish {state.phase}: {type(exc).__name__}: {exc}"
        return result(RegressionStatus.INCONCLUSIVE, reason, runs=tuple(state.runs))
    seen = set().union(*(set(a.passed) | set(a.failed) for a in _readable(head)))
    not_run = sum(1 for c in compared if c.head_id not in seen)
    status, reason = _status(head, compared, confirmed, unconfirmed)
    return result(status, reason, regressions=tuple(confirmed), unconfirmed=tuple(unconfirmed),
                  compared=len(compared), not_run=not_run, runs=tuple(state.runs),
                  notes=_notes(not_run))  # fmt: skip


def _named(items: Sequence[Regression | Unconfirmed]) -> str:
    names = [f"{i.file}::{i.test}" if i.test else i.file for i in items[:MAX_LISTED]]
    more = f" and {len(items) - MAX_LISTED} more" if len(items) > MAX_LISTED else ""
    return ", ".join(names) + more


def _status(head: RunResult, compared: Sequence[Compared], confirmed: Sequence[Regression],
            unconfirmed: Sequence[Unconfirmed]) -> tuple[RegressionStatus, str]:  # fmt: skip
    # A confirmed regression stands whatever else happened: nothing may hide it.
    if confirmed:
        return RegressionStatus.FOUND, f"{len(confirmed)} confirmed: {_named(confirmed)}"
    if unconfirmed:
        return RegressionStatus.INCONCLUSIVE, f"not confirmed: {_named(unconfirmed)}"
    if head.outcome in (Outcome.TIMEOUT, Outcome.ERROR, Outcome.NO_TESTS):
        return (
            RegressionStatus.INCONCLUSIVE,
            f"the suite on the fixed code ended with {head.outcome}",
        )
    return (RegressionStatus.NONE_FOUND,
            f"none of the {len(compared)} untouched tests that passed before the fix fails "
            f"after it")  # fmt: skip


def _notes(not_run: int) -> tuple[str, ...]:
    if not not_run:
        return ()
    return (f"{not_run} untouched test(s) that passed before the fix did not run after it "
            f"(skipped or not collected), so they were not compared",)  # fmt: skip

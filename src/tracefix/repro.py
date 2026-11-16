"""Reproducer: an LLM writes a fail-to-pass test; our runner decides what it proves (SPEC 2.3).

The model only proposes test code. Every verdict here comes from pytest exit codes and the
JUnit report: `reproduced`, `not_reproduced` or `fix_does_not_fix`.
"""

import ast
import re
import sys
import tempfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path, PurePosixPath

from tracefix.diffscope import DiffScope, FileKind, unified_diff
from tracefix.diffscope import classify as file_kind
from tracefix.isolation import TamperingDetected, run_checked
from tracefix.llm import (
    BudgetExceeded,
    LLMClient,
    LLMError,
    LLMOutputError,
    LLMProviderError,
    Message,
)
from tracefix.prompts import python_note, reproducer
from tracefix.runner import Outcome, RunResult
from tracefix.sandbox import BASIC_WARNING, Level, sandbox_level
from tracefix.workspace import Workspace, git, git_bytes, safe_relpath

REPRO_FILE = "test_tracefix_repro.py"
BLIND_FILE = "test_tracefix_blind.py"  # the blind shadow test's (M11; report only)
BLIND_ATTEMPTS = 2
MAX_BLIND_CLASS_CHARS = 6_000
MAX_ATTEMPTS = 3
REPRO_TIMEOUT_S = 60
MAX_TEST_CHARS = 50_000
MAX_SNIPPETS = 8
STYLE_EXAMPLE_CHARS = 6_000
CONFIG_CHARS = 3_000
FEEDBACK_CHARS = 4_000
# A base failure of these types usually means the test uses something only the fix added.
NOT_A_REPRODUCTION = {"ImportError", "ModuleNotFoundError", "NameError", "SyntaxError",
                      "IndentationError"}  # fmt: skip
# The same, recognised by message: a module/class attribute or a keyword the fix added.
_NEW_NAME_MESSAGE = re.compile(
    r"^(AttributeError: (module|type object) '[^']+' has no attribute"
    r"|TypeError: .*unexpected keyword argument)"
)
HEAD_PASS_REPEATS = 2  # extra head runs after a pass, to catch a test that passes only sometimes
# Names a test has no reason to use: they can fake a result, tell base from head, or reach the
# verifier. Defence in depth only; the runs are not a sandbox.
FORBIDDEN_NAMES = {"_exit", "kill", "killpg", "getppid", "system", "popen", "fork", "argv",
                   "__file__", "getcwd", "cwd", "subprocess", "ctypes", "signal",
                   "multiprocessing", "inspect",
                   # Ways to reach the behaviour diff's call recorder (verifier, M7 round 4).
                   "getprofile", "setprofile", "gettrace", "settrace", "_getframe", "f_back",
                   "f_globals", "f_locals", "tb_frame", "get_referrers",
                   "get_objects",
                   # Ways round the `inspect` allow-list: a module's globals, or the module
                   # itself by a name the check can't see (verifier, M11 early round 1).
                   "__globals__", "__builtins__", "__import__", "import_module", "gi_frame",
                   "cr_frame", "ag_frame"}  # fmt: skip
FORBIDDEN_STRINGS = ("junit",)  # a report file
# A reproduction test may `import inspect` (M11 early: a test of a signature bug needs
# `inspect.signature`), but may use it for these alone: nothing that reaches frames (the call
# recorder) or source text (tells base from head). Any other use of the name, `getattr(inspect,
# ...)` included, is refused. Break My Fix inputs still refuse `inspect` (FORBIDDEN_NAMES).
INSPECT_ALLOWED = frozenset({
    "signature", "Signature", "Parameter", "BoundArguments", "getfullargspec", "getcallargs",
    "getdoc", "cleandoc", "getmro", "unwrap", "isabstract", "isclass",
    "isfunction", "ismethod", "ismodule", "isroutine", "isbuiltin", "isdatadescriptor",
    "ismethoddescriptor", "iscoroutinefunction", "isgeneratorfunction", "isasyncgenfunction",
    "iscoroutine", "isgenerator", "isasyncgen", "isawaitable",
})  # fmt: skip
_DURATION = re.compile(r"\bin \d+(?:\.\d+)?s\b")
# pytest pads separators and the progress line to the terminal width (one column less on Windows).
_SEPARATOR = re.compile(r"^([=_-])\1{2,}(?: (.*?) \1+| ?)$", re.MULTILINE)
_PROGRESS = re.compile(r" {2,}(\[ *\d+%\])$", re.MULTILINE)
# The "_ _ _" divider between traceback frames ends on a space where the width is even (Linux).
_FRAME_DIVIDER = re.compile(r"^(_(?: _)+) +$", re.MULTILINE)
_ADDRESS = re.compile(r"\b0x[0-9a-fA-F]+\b")
MIN_MASKED_PATH = 4  # never mask "/" or "C:\\" (a home folder of "/" in some containers)
_DRIVE = re.compile(r"^[A-Za-z]:/")
# A path under a masked folder, e.g. "<work>\base\tests\x.py": always use "/".
_MASKED_PATH = re.compile(r"<(?:repo|work|venv|python|tmp|home)>[^\s'\"]*")
# Traceback location lines: "<path>.py:<line>: <ExcType>" or "<path>.py:<line>: in <func>".
_LOCATION_LINE = re.compile(r"^(\S+?\.py)(:\d+:)", re.MULTILINE)
_JUNIT_LINE = re.compile(r"^.*generated xml file.*$", re.MULTILINE)


class ReproStatus(StrEnum):
    REPRODUCED = "reproduced"
    NOT_REPRODUCED = "not_reproduced"
    FIX_DOES_NOT_FIX = "fix_does_not_fix"
    INVALID = "invalid"  # tampering detected: no verdict at all (Decided in M3.5)


class Verdict(StrEnum):
    """What one attempt showed."""

    REPRODUCED = "reproduced"  # fails properly on base, passes cleanly on head
    FAILS_ON_BOTH = "fails_on_both"  # same tests, same failure signature on base and head
    BASE_PASSES = "base_passes"
    BASE_BROKEN = "base_broken"  # error, timeout, flaky, wrong kind of failure on base
    PARTLY_FIXED = "partly_fixed"  # some tests pass on head; the rest still fail the same way
    HEAD_DIFFERENT_FAILURE = "head_different_failure"  # fails on head, but not the same way
    HEAD_NOT_CLEAN = "head_not_clean"  # error, timeout, flaky, skipped or no tests on head
    ORDER_DEPENDENT = "order_dependent"  # a test's result depends on the others in the file
    INVALID_TEST = "invalid_test"  # rejected before running


@dataclass(frozen=True)
class AttemptResult:
    number: int
    verdict: Verdict
    reason: str
    test_code: str
    base: RunResult | None
    head: RunResult | None
    # The model had been shown a fails-on-both result before it submitted (or kept) this test.
    confirmed: bool = False


@dataclass(frozen=True)
class ReproResult:
    status: ReproStatus
    reason: str
    test_path: str  # repo-relative path the test was run at
    test_code: str | None  # the test behind the status (None if no attempt ran)
    attempts: tuple[AttemptResult, ...]
    notes: tuple[str, ...]  # e.g. what was truncated in the prompt
    isolation: Level = "basic"  # how the runs were confined (sandbox.py)
    warnings: tuple[str, ...] = ()  # e.g. the basic-isolation warning, shown in the receipt


class BlindStatus(StrEnum):
    """What the blind shadow test showed. Report only: no level reads it (M11, NOTES 42)."""

    REPRODUCED = "reproduced"  # fails properly on base, passes cleanly on head
    FAILS_ON_HEAD = "fails_on_head"  # some of it still fails the same way after the fix
    FAILS_DIFFERENTLY = "fails_differently"  # fails after the fix too, but not the same way
    HEAD_NOT_CLEAN = "head_not_clean"  # error, timeout, flaky, skipped or order-dependent on head
    NOT_REPRODUCED_ON_BASE = "not_reproduced_on_base"  # no attempt failed properly on base
    NOT_RUN = "not_run"


@dataclass(frozen=True)
class BlindResult:
    status: BlindStatus
    reason: str
    test_path: str = ""  # repo-relative path the test was run at
    test_code: str | None = None  # the last test written
    attempts: tuple[AttemptResult, ...] = ()
    notes: tuple[str, ...] = ()  # e.g. what was truncated in the prompt


# What a test that failed properly on base showed on head. Any other verdict is a test that never
# got that far: the model is told and may try again, and head is not run.
_BLIND_STATUS = {
    Verdict.REPRODUCED: BlindStatus.REPRODUCED,
    Verdict.FAILS_ON_BOTH: BlindStatus.FAILS_ON_HEAD,
    Verdict.PARTLY_FIXED: BlindStatus.FAILS_ON_HEAD,
    Verdict.HEAD_DIFFERENT_FAILURE: BlindStatus.FAILS_DIFFERENTLY,
    Verdict.HEAD_NOT_CLEAN: BlindStatus.HEAD_NOT_CLEAN,
    Verdict.ORDER_DEPENDENT: BlindStatus.HEAD_NOT_CLEAN,
}


# --- deterministic classification --------------------------------------------------------------


def classify(base: RunResult, head: RunResult | None) -> tuple[Verdict, str]:
    """Verdict for one attempt from the two runs. `head` is None when base already failed it."""
    verdict = _check_base(base)
    if verdict is not None:
        return verdict
    if head is None:
        raise ValueError("head run required when the base run is a valid failure")
    return _check_head(base, head)


def _in_test_file(location: str | None) -> bool:
    """True if the crash is in the generated test (or the location is unknown, to be safe)."""
    if location is None:
        return True
    return location.rpartition(":")[0].endswith((REPRO_FILE, BLIND_FILE))


def _check_base(base: RunResult) -> tuple[Verdict, str] | None:
    if base.outcome is Outcome.PASSED:
        return Verdict.BASE_PASSES, "the test passes on the code before the fix"
    if base.outcome is not Outcome.FAILED:
        return (
            Verdict.BASE_BROKEN,
            f"the test could not run cleanly before the fix ({base.outcome})",
        )
    failures = base.first.failures
    if not failures:
        return Verdict.BASE_BROKEN, "pytest reported a failure but no failing test details"
    for f in failures:
        if f.kind == "error":
            return Verdict.BASE_BROKEN, f"{f.test} errors in setup/teardown before the fix"
        new_name = f.exc_type in NOT_A_REPRODUCTION or _NEW_NAME_MESSAGE.match(f.message)
        # A crash inside the code under test is the bug itself, whatever its type; only a crash
        # in the test file means the test reached for something the fix added.
        if new_name and _in_test_file(f.location):
            return Verdict.BASE_BROKEN, (
                f"{f.test} fails with {f.exc_type} before the fix, which usually means it uses "
                "something that only exists after the fix"
            )
    return None


def _check_head(base: RunResult, head: RunResult) -> tuple[Verdict, str]:
    attempt = head.first
    if head.outcome is Outcome.PASSED:
        if attempt.tests > 0 and attempt.skipped == 0:
            return Verdict.REPRODUCED, "fails before the fix and passes after it"
        return Verdict.HEAD_NOT_CLEAN, "after the fix some tests were skipped or none ran"
    if head.outcome is Outcome.FAILED:
        base_sigs = {f.signature for f in base.first.failures}
        head_sigs = {f.signature for f in attempt.failures}
        if base_sigs == head_sigs:
            return Verdict.FAILS_ON_BOTH, "fails the same way before and after the fix"
        if head_sigs < base_sigs:
            still = ", ".join(sorted(f.test.rsplit("::", 1)[-1] for f in attempt.failures))
            return Verdict.PARTLY_FIXED, (
                f"after the fix some tests pass, but these still fail the same way: {still}"
            )
        return Verdict.HEAD_DIFFERENT_FAILURE, "fails after the fix too, but differently"
    return Verdict.HEAD_NOT_CLEAN, f"the test could not run cleanly after the fix ({head.outcome})"


def final_status(attempts: list[AttemptResult]) -> tuple[ReproStatus, str]:
    """Reproduced if any attempt reproduced; fix_does_not_fix only if the LAST attempt failed the
    same way on both sides AND the model had already seen that kind of result (Decided in M3);
    otherwise not_reproduced."""
    for a in attempts:
        if a.verdict is Verdict.REPRODUCED:
            return ReproStatus.REPRODUCED, f"attempt {a.number}: {a.reason}"
    if not attempts:
        return ReproStatus.NOT_REPRODUCED, "no attempt ran"
    last = attempts[-1]
    if last.verdict is Verdict.FAILS_ON_BOTH and last.confirmed:
        return ReproStatus.FIX_DOES_NOT_FIX, (
            f"attempt {last.number}: the test fails before and after the fix with the same "
            "failure signature, also after the model was shown the result"
        )
    if last.verdict is Verdict.FAILS_ON_BOTH:
        return ReproStatus.NOT_REPRODUCED, (
            f"attempt {last.number} failed the same way before and after the fix, but the model "
            "never got to review that result, so it does not count as fix_does_not_fix"
        )
    return ReproStatus.NOT_REPRODUCED, f"no attempt reproduced the bug; last: {last.reason}"


# --- prompt context (read from git objects only: no worktree or user paths) ----------------------


def _read(ws: Workspace, sha: str, path: str) -> str:
    return git_bytes(ws.repo, "show", f"{sha}:{path}").decode("utf-8", errors="replace")


def _tree_files(ws: Workspace, sha: str) -> list[str]:
    return [p for p in git(ws.repo, "ls-tree", "-r", "-z", "--name-only", sha).split("\0") if p]


def _lines(text: str, span: tuple[int, int]) -> str:
    return "\n".join(text.splitlines()[span[0] - 1 : span[1]])


def _cap(text: str, limit: int, what: str, notes: list[str]) -> str:
    if len(text) <= limit:
        return text
    notes.append(f"{what} truncated to {limit} characters for the prompt")
    return text[:limit] + "\n[... truncated ...]"


def _callers(
    ws: Workspace, sha: str, names: set[str], skip: set[tuple[str, str]]
) -> list[reproducer.Snippet]:
    """Functions at `sha`, in source files, that call one of `names` directly (by name or
    attribute)."""
    found = []
    for path in _tree_files(ws, sha):
        if not path.endswith(".py") or file_kind(path) is not FileKind.SOURCE:
            continue
        text = _read(ws, sha, path)
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if (path, node.name) in skip:
                continue
            for call in ast.walk(node):
                if isinstance(call, ast.Call) and called_name(call) in names:
                    span = (node.lineno, node.end_lineno or node.lineno)
                    title = f"function {node.name}, which calls {called_name(call)}"
                    found.append(reproducer.Snippet(path, title, _lines(text, span)))
                    break
    return found


def called_name(call: ast.Call) -> str | None:
    """What a call calls, by name: `f(x)` and `obj.items[0].f(x)` both call `f`; None for
    anything else (e.g. `(lambda: 0)()`)."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _style_example(ws: Workspace, scope: DiffScope) -> tuple[str, str] | None:
    """(path, base text) of one existing test file: one the fix touched, else the first one."""
    base_files = set(_tree_files(ws, ws.base_sha))
    touched = [f.old_path or f.path for f in scope.test_files]
    candidates = [p for p in touched if p in base_files] + sorted(base_files)
    for path in candidates:
        name = PurePosixPath(path).name
        if path.endswith(".py") and file_kind(path) is FileKind.TEST and name != "conftest.py":
            return path, _read(ws, ws.base_sha, path)
    return None


def repro_test_path(ws: Workspace, style_path: str | None) -> str:
    """Next to the existing tests (so their conftest and config apply), else tests/, else root."""
    folders = []
    if style_path is not None:
        folders.append(str(PurePosixPath(style_path).parent))
    folders += ["tests", "."]
    for folder in folders:
        if folder != "." and safe_relpath(folder) is None:
            continue  # e.g. "a/../.." from a crafted test path: never write outside the copies
        if (ws.base / folder).is_dir() and (ws.head / folder).is_dir():
            return str(PurePosixPath(folder) / REPRO_FILE) if folder != "." else REPRO_FILE
    return REPRO_FILE


def build_context(
    ws: Workspace, scope: DiffScope, issue: str
) -> tuple[reproducer.ReproContext, list[str]]:
    notes: list[str] = []
    issue = issue.replace("\r\n", "\n").strip()  # same prompt on every OS
    source_paths = sorted({p for f in scope.source_files for p in (f.old_path, f.path) if p})
    diff = unified_diff(ws.repo, ws.base_sha, ws.head_sha, source_paths)
    snippets = []
    for fn in scope.source_functions:
        if fn.head_span is None:
            continue
        text = _read(ws, ws.head_sha, fn.path)
        snippets.append(reproducer.Snippet(fn.path, f"changed function {fn.qualname}",
                                           _lines(text, fn.head_span)))  # fmt: skip
    changed = {(fn.path, fn.qualname.rsplit(".", 1)[-1]) for fn in scope.source_functions}
    snippets += _callers(ws, ws.head_sha, {name for _, name in changed}, changed)
    if len(snippets) > MAX_SNIPPETS:
        notes.append(f"only the first {MAX_SNIPPETS} of {len(snippets)} functions were shown")
        snippets = snippets[:MAX_SNIPPETS]
    style = _style_example(ws, scope)
    example = None
    if style is not None:
        text = _cap(style[1], STYLE_EXAMPLE_CHARS, f"style example {style[0]}", notes)
        example = reproducer.Snippet(style[0], "existing test file", text)
    config = None
    if "pyproject.toml" in _tree_files(ws, ws.base_sha):
        config = _cap(_read(ws, ws.base_sha, "pyproject.toml"), CONFIG_CHARS, "pyproject", notes)
    ctx = reproducer.ReproContext(issue, diff, tuple(snippets), example, config,
                                  repro_test_path(ws, style[0] if style else None),
                                  python_note(ws.settings.python.version))  # fmt: skip
    return ctx, notes


# --- feedback (sanitised: no worktree paths, stable across runs and operating systems) -----------


def _known_dirs(ws: Workspace, extra: Sequence[tuple[Path, str]] = ()) -> list[tuple[str, str]]:
    """(path, token) pairs, longest path first, so the most specific token wins."""
    python = ws.settings.python
    project = () if python.own else ((prefix, "<python>") for prefix in python.prefixes)
    dirs = [(ws.root, "<work>"), *((copy.parent, "<work>") for copy in ws.copies),
            (Path(sys.prefix), "<venv>"), (Path(sys.exec_prefix), "<venv>"),
            (Path(sys.base_prefix), "<python>"), *project, (Path(tempfile.gettempdir()), "<tmp>"),
            (Path.home(), "<home>"), *extra]  # fmt: skip
    pairs = {(str(path), token) for path, token in dirs if len(str(path)) >= MIN_MASKED_PATH}
    return sorted(pairs, key=lambda p: len(p[0]), reverse=True)


def _dir_pattern(path: str) -> re.Pattern[str]:
    """A folder however it is written: each separator "/" or any run of backslashes (a repr
    doubles them, a repr of a repr doubles them again: verifier round 2)."""
    parts = re.split(r"[\\/]", path)
    return re.compile(r"(?:\\+|/)".join(map(re.escape, parts)), re.IGNORECASE)


def _generic_path(path: str) -> str:
    """A location path outside the known folders: keep it relative, else only its file name."""
    path = path.replace("\\", "/")
    if path.startswith("<") or not (path.startswith(("/", "../")) or _DRIVE.match(path)):
        return path
    return "<abs>/" + path.rsplit("/", 1)[-1]


def mask_paths(text: str, ws: Workspace, extra: Sequence[tuple[Path, str]] = ()) -> str:
    """The path part of `sanitize` alone (the receipt: values such as `0x1f` stay as they are):
    known folders (and `extra` ones) become tokens, other paths on traceback location lines keep
    only their file name."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for path, token in _known_dirs(ws, extra):
        text = _dir_pattern(path).sub(token, text)
    text = _MASKED_PATH.sub(lambda m: re.sub(r"\\+", "/", m.group(0)), text)
    return _LOCATION_LINE.sub(lambda m: _generic_path(m.group(1)) + m.group(2), text)


def sanitize(text: str, ws: Workspace) -> str:
    """No user or machine paths, timings or addresses: the feedback goes into the prompt, and the
    prompt names the recording, so it must be the same on every run, OS and Python install.

    Known folders are masked everywhere; other paths only on traceback location lines, so values
    inside assertion messages reach the model unchanged."""
    text = _JUNIT_LINE.sub("", mask_paths(text, ws))
    text = _DURATION.sub("in <t>", text)
    text = _SEPARATOR.sub(lambda m: f"{m.group(1) * 3} {m.group(2) or ''} {m.group(1) * 3}", text)
    text = _PROGRESS.sub(lambda m: " " + m.group(1), text)
    text = _FRAME_DIVIDER.sub(r"\1", text)
    return _ADDRESS.sub("0x?", text)


def _location(location: str | None) -> str:
    if location is None:
        return "unknown location"
    path, _, line = location.rpartition(":")
    return f"{_generic_path(path)}:{line}"


def _details(result: AttemptResult, ws: Workspace) -> str:
    runs = [("before the fix", result.base), ("after the fix", result.head)]
    parts = []
    for label, run in runs:
        if run is None:
            continue
        parts.append(f"{label}: {run.outcome}")
        for f in run.first.failures:
            line = f"  {f.test}: {f.kind} {f.exc_type} at {_location(f.location)}"
            parts.append(sanitize(line, ws))
        tail = sanitize(run.first.output, ws).strip()
        parts.append(tail[-FEEDBACK_CHARS:])
    return "\n".join(parts)


# --- the attempt loop ------------------------------------------------------------------------


def _run_in(ws: Workspace, tree: Path, rel: str, code: str, nodes: Sequence[str] = ()) -> RunResult:
    """Run the candidate test in one copy, watched for tampering (isolation.run_checked):
    the whole file, or only `nodes` (pytest node ids) in the order given."""
    target = tree / rel
    target.write_text(code, encoding="utf-8", newline="\n")
    try:
        return run_checked(ws, tree, list(nodes) or [rel], placed=[rel], timeout_s=REPRO_TIMEOUT_S)
    finally:
        target.unlink(missing_ok=True)


def _testcase(node: ast.ClassDef) -> bool:
    """A unittest.TestCase subclass, by its base's name (as Break My Fix's `test_functions`)."""
    return any(
        (isinstance(b, ast.Name) and b.id == "TestCase")
        or (isinstance(b, ast.Attribute) and b.attr == "TestCase"
            and isinstance(b.value, ast.Name) and b.value.id == "unittest")
        for b in node.bases
    )  # fmt: skip


def _tests_in(body: list[ast.stmt], chain: tuple[str, ...]) -> Iterator[tuple[str, ...]]:
    for node in body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.startswith("test"):
                yield (*chain, node.name)
        elif isinstance(node, ast.ClassDef) and _testcase(node):
            # Any name; only its own `test*` methods (unittest collects no nested classes).
            yield from (
                (*chain, node.name, item.name)
                for item in node.body
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
                and item.name.startswith("test")
            )
        elif (
            isinstance(node, ast.ClassDef)
            and node.name.startswith("Test")
            and not any(isinstance(n, ast.FunctionDef) and n.name == "__init__" for n in node.body)
        ):
            yield from _tests_in(node.body, (*chain, node.name))


def node_chains(code: str) -> list[tuple[str, ...]]:
    """The tests pytest collects from the file by default, in file order, from its syntax tree:
    `test*` functions, the `test*` methods of `Test*` classes without `__init__` (nested too),
    and the `test*` methods of unittest.TestCase subclasses of any name. Each as its chain of
    names, e.g. ("TestK", "test_b"); a name defined twice counts once."""
    return list(dict.fromkeys(_tests_in(ast.parse(code).body, ())))


def _node_of(test: str, nodes: list[tuple[str, ...]]) -> tuple[str, ...] | None:
    """The node behind a JUnit "classname::name" (e.g. "tests.test_x.TestK::test_b[1]"): the
    longest chain the dotted name ends with."""
    classname, _, name = test.rpartition("::")
    full = f"{classname}.{name.split('[', 1)[0]}"
    matches = [n for n in nodes if full == ".".join(n) or full.endswith("." + ".".join(n))]
    return max(matches, key=len, default=None)


def order_problem(ws: Workspace, rel: str, code: str, base: RunResult) -> str:
    """For a file of 2+ tests that reproduced: why its result depends on order, or "" if it
    doesn't. Each test that failed before the fix must fail properly on base and pass on head when
    run alone, and the whole file must still pass on head in reverse order (plan P9)."""
    nodes = node_chains(code)
    if len(nodes) < 2:
        return ""
    failing = dict.fromkeys(_node_of(f.test, nodes) for f in base.first.failures)
    for node in failing:
        if node is None:
            return "a test that failed before the fix could not be found in the file to run alone"
        ids = ["::".join((rel, *node))]
        alone = _run_in(ws, ws.base, rel, code, ids)
        if _check_base(alone) is not None:
            return f"{node[-1]} does not fail properly before the fix when it runs alone"
        if _check_head(alone, _run_in(ws, ws.head, rel, code, ids))[0] is not Verdict.REPRODUCED:
            return f"{node[-1]} does not pass after the fix when it runs alone"
    backwards = ["::".join((rel, *n)) for n in reversed(nodes)]
    if _check_head(base, _run_in(ws, ws.head, rel, code, backwards))[0] is not Verdict.REPRODUCED:
        return "after the fix the tests fail when they run in reverse order"
    return ""


def _sys_monitoring(node: ast.AST) -> bool:
    """`sys.monitoring`, or `from sys import monitoring`: a way to reach the call recorder. A
    project's own `monitoring` module is fine (verifier, M7 round 5)."""
    if isinstance(node, ast.Attribute):
        return (
            node.attr == "monitoring"
            and isinstance(node.value, ast.Name)
            and (node.value.id == "sys")
        )
    if isinstance(node, ast.ImportFrom):
        return node.module == "sys" and any(a.name == "monitoring" for a in node.names)
    return False


def _inspect_misuse(tree: ast.AST) -> set[str]:
    """Uses of the `inspect` module other than `inspect.<one of INSPECT_ALLOWED>`, under any name
    `import inspect [as x]` binds it to, and `from inspect import` of anything else."""
    names = {"inspect"}
    names |= {a.asname for n in ast.walk(tree) if isinstance(n, ast.Import)
              for a in n.names if a.name == "inspect" and a.asname}  # fmt: skip
    allowed_uses: set[int] = set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "inspect":
            found.update(f"inspect.{a.name}" for a in node.names if a.name not in INSPECT_ALLOWED)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in names and node.attr in INSPECT_ALLOWED:
                allowed_uses.add(id(node.value))
            elif node.value.id in names:
                found.add(f"inspect.{node.attr}")
                allowed_uses.add(id(node.value))  # already named, by its attribute
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in names and id(node) not in allowed_uses:
            found.add("inspect")
    return found


def forbidden_names(code: str) -> list[str]:
    """Names, attributes, imports and strings in the test that it has no business using."""
    tree = ast.parse(code)
    found = _inspect_misuse(tree)
    banned = FORBIDDEN_NAMES - {"inspect"}  # checked by _inspect_misuse
    for node in ast.walk(tree):
        if _sys_monitoring(node):
            found.add("sys.monitoring")
        if isinstance(node, ast.Name) and node.id in banned:
            found.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_NAMES:
            found.add(node.attr)  # `x.inspect` too: a module that imported inspect re-exports it
        elif isinstance(node, ast.Import | ast.ImportFrom):
            modules = [a.name for a in node.names]
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            found.update(m.split(".")[0] for m in modules if m.split(".")[0] in banned)
            if isinstance(node, ast.ImportFrom):  # `from x import inspect` too
                found.update(a.name for a in node.names if a.name in FORBIDDEN_NAMES)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.update(word for word in FORBIDDEN_STRINGS if word in node.value.lower())
    return sorted(found)


def _invalid(number: int, code: str, reason: str) -> AttemptResult:
    return AttemptResult(number, Verdict.INVALID_TEST, reason, code, None, None)


def run_attempt(ws: Workspace, number: int, rel: str, code: str) -> AttemptResult:
    """Run one candidate test on base, then head. Raises TamperingDetected (isolation.py)."""
    if len(code) > MAX_TEST_CHARS:
        return _invalid(number, code, f"the test file is longer than {MAX_TEST_CHARS} characters")
    try:
        compile(code, REPRO_FILE, "exec")
    except (SyntaxError, ValueError) as exc:
        return _invalid(number, code, f"the file does not compile: {exc}")
    bad = forbidden_names(code)
    if bad:
        return _invalid(number, code, f"the test uses names it must not use: {', '.join(bad)}")
    base = _run_in(ws, ws.base, rel, code)
    early = _check_base(base)
    if early is not None:
        return AttemptResult(number, early[0], early[1], code, base, None)
    head = _run_in(ws, ws.head, rel, code)
    verdict, reason = classify(base, head)
    if verdict is Verdict.REPRODUCED:
        for _ in range(HEAD_PASS_REPEATS):
            if _run_in(ws, ws.head, rel, code).outcome is not Outcome.PASSED:
                verdict, reason = Verdict.HEAD_NOT_CLEAN, "after the fix it passes only sometimes"
                break
    if verdict is Verdict.REPRODUCED:
        problem = order_problem(ws, rel, code, base)
        if problem:
            verdict, reason = Verdict.ORDER_DEPENDENT, problem
    return AttemptResult(number, verdict, reason, code, base, head)


def _result(status: ReproStatus, reason: str, rel: str, code: str | None,
            attempts: list[AttemptResult], notes: list[str]) -> ReproResult:  # fmt: skip
    level = sandbox_level()
    warnings = (BASIC_WARNING,) if level == "basic" else ()
    return ReproResult(status, reason, rel, code, tuple(attempts), tuple(notes), level, warnings)


def reproduce(ws: Workspace, scope: DiffScope, issue: str, client: LLMClient) -> ReproResult:
    ctx, notes = build_context(ws, scope, issue)
    rel = ctx.test_path
    if (ws.base / rel).exists() or (ws.head / rel).exists():
        reason = f"{rel} already exists in the repo"
        return _result(ReproStatus.NOT_REPRODUCED, reason, rel, None, [], notes)
    history = [Message("user", reproducer.render_request(ctx))]
    attempts: list[AttemptResult] = []
    stopped = ""
    for number in range(1, MAX_ATTEMPTS + 1):
        try:
            answer = client.complete("reproducer", reproducer.SYSTEM, history, reproducer.ReproTest)
        except (BudgetExceeded, LLMOutputError, LLMProviderError) as exc:
            stopped = f"; stopped early: {exc}"
            break
        history.append(Message("assistant", answer.model_dump_json()))
        last = attempts[-1] if attempts else None
        seen_both = last is not None and last.verdict is Verdict.FAILS_ON_BOTH
        if last and seen_both and answer.test_code == last.test_code:
            attempts[-1] = replace(last, confirmed=True)
            break  # the model stands by its test: rerunning it would show the same thing
        try:
            result = run_attempt(ws, number, rel, answer.test_code)
        except TamperingDetected as exc:
            # Never a verdict: the stage is invalid, whatever the runs said.
            attempts.append(_invalid(number, answer.test_code, str(exc)))
            return _result(ReproStatus.INVALID, str(exc), rel, answer.test_code, attempts, notes)
        result = replace(result, confirmed=seen_both)
        attempts.append(result)
        if result.verdict is Verdict.REPRODUCED:
            break
        problem = result.reason
        if result.verdict is Verdict.FAILS_ON_BOTH:
            problem += ". " + reproducer.FAILS_ON_BOTH_HINT
        elif result.verdict is Verdict.PARTLY_FIXED:
            problem += ". " + reproducer.PARTLY_FIXED_HINT
        elif result.verdict is Verdict.ORDER_DEPENDENT:
            problem += ". " + reproducer.ORDER_DEPENDENT_HINT
        feedback = reproducer.render_feedback(number, problem, _details(result, ws))
        history.append(Message("user", feedback))
    status, reason = final_status(attempts)
    code = next((a.test_code for a in attempts if a.verdict is Verdict.REPRODUCED), None)
    if code is None and attempts:
        code = attempts[-1].test_code
    return _result(status, reason + stopped, rel, code, attempts, notes)


# --- the blind shadow test (M11, NOTES 42; report only) -------------------------------------------


def class_source(text: str, qualname: str) -> str | None:
    """The source of the class `qualname` ("Outer.Inner"), its decorators included; None unless
    every part of the name is a class."""
    try:
        body = ast.parse(text).body
    except (SyntaxError, ValueError):
        return None
    found = None
    for part in qualname.split("."):
        found = next((n for n in body if isinstance(n, ast.ClassDef) and n.name == part), None)
        if found is None:
            return None
        body = found.body
    if found is None:
        return None
    first = min([found.lineno, *(d.lineno for d in found.decorator_list)])
    return _lines(text, (first, found.end_lineno or found.lineno))


def _blind_snippets(ws: Workspace, scope: DiffScope, notes: list[str]) -> list[reproducer.Snippet]:
    """The code the fix touches as it was before the fix: each function it changed or removed; for
    a method it added, the class that method joins. A function added outside a class has nothing
    to show, and neither has a file the fix added."""
    at_base = {f.path: f.old_path or f.path for f in scope.source_files}
    files = set(_tree_files(ws, ws.base_sha))
    found: dict[tuple[str, str], reproducer.Snippet] = {}
    for fn in scope.source_functions:
        path = at_base.get(fn.path, fn.path)
        if path not in files:
            continue
        text = _read(ws, ws.base_sha, path)
        if fn.base_span is not None:
            shown = _lines(text, fn.base_span)
            found[(path, fn.qualname)] = reproducer.Snippet(path, f"function {fn.qualname}", shown)
            continue
        owner = fn.qualname.rpartition(".")[0]
        source = class_source(text, owner) if owner else None
        if source is not None:
            shown = _cap(source, MAX_BLIND_CLASS_CHARS, f"class {owner}", notes)
            found[(path, owner)] = reproducer.Snippet(path, f"class {owner}", shown)
    return list(found.values())


def build_blind_context(
    ws: Workspace, scope: DiffScope, issue: str, test_path: str
) -> tuple[reproducer.BlindContext, list[str]]:
    """What the blind test is written from: the issue and the base commit, read from git objects.
    Never the diff, head's code or head's results."""
    notes: list[str] = []
    snippets = _blind_snippets(ws, scope, notes)
    changed = {(fn.path, fn.qualname.rsplit(".", 1)[-1]) for fn in scope.source_functions}
    snippets += _callers(ws, ws.base_sha, {name for _, name in changed}, changed)
    if len(snippets) > MAX_SNIPPETS:
        notes.append(f"only the first {MAX_SNIPPETS} of {len(snippets)} functions were shown")
        snippets = snippets[:MAX_SNIPPETS]
    style = _style_example(ws, scope)
    example = None
    if style is not None:
        text = _cap(style[1], STYLE_EXAMPLE_CHARS, f"style example {style[0]}", notes)
        example = reproducer.Snippet(style[0], "existing test file", text)
    config = None
    if "pyproject.toml" in _tree_files(ws, ws.base_sha):
        config = _cap(_read(ws, ws.base_sha, "pyproject.toml"), CONFIG_CHARS, "pyproject", notes)
    ctx = reproducer.BlindContext(issue.replace("\r\n", "\n").strip(), tuple(snippets), example,
                                  config, test_path,
                                  python_note(ws.settings.python.version))  # fmt: skip
    return ctx, notes


def blind(
    ws: Workspace, scope: DiffScope, repro: ReproResult | None, issue: str, client: LLMClient
) -> BlindResult:
    """A second reproduction test, written without seeing the fix. Report only: no level reads
    it, so the pipeline runs it after every stage a level does read, and a model failure only
    leaves it unfinished. Tampering isn't caught here: the stage is invalid, as for the main
    test."""
    if repro is None or repro.status is not ReproStatus.REPRODUCED:
        return BlindResult(BlindStatus.NOT_RUN, "the main test did not reproduce the bug")
    rel = str(PurePosixPath(repro.test_path).with_name(BLIND_FILE))
    if (ws.base / rel).exists() or (ws.head / rel).exists():
        return BlindResult(BlindStatus.NOT_RUN, f"{rel} already exists in the repo", rel)
    ctx, notes = build_blind_context(ws, scope, issue, rel)
    history = [Message("user", reproducer.render_blind_request(ctx))]
    attempts: list[AttemptResult] = []
    stopped = ""
    for number in range(1, BLIND_ATTEMPTS + 1):
        try:
            answer = client.complete("reproducer", reproducer.BLIND_SYSTEM, history,
                                     reproducer.ReproTest)  # fmt: skip
        except LLMError as exc:
            stopped = f"; stopped early: {exc}"
            break
        history.append(Message("assistant", answer.model_dump_json()))
        result = run_attempt(ws, number, rel, answer.test_code)
        attempts.append(result)
        status = _BLIND_STATUS.get(result.verdict)
        if status is not None:
            why = f"attempt {number}: {result.reason}"
            return BlindResult(status, why, rel, answer.test_code, tuple(attempts), tuple(notes))
        # This attempt never reached head, so what the model is told comes from base alone.
        feedback = reproducer.render_feedback(number, result.reason, _details(result, ws))
        history.append(Message("user", feedback))
    if not attempts:
        return BlindResult(BlindStatus.NOT_RUN, "no test was written" + stopped, rel,
                           notes=tuple(notes))  # fmt: skip
    last = attempts[-1]
    why = f"no attempt failed properly on base; last: {last.reason}{stopped}"
    return BlindResult(BlindStatus.NOT_REPRODUCED_ON_BASE, why, rel, last.test_code,
                       tuple(attempts), tuple(notes))  # fmt: skip

"""Guard: would the tests notice if the fix were broken again? (SPEC 2.4, Decided in M1 and M4)

Two experiments in an extra copy of head (the variant), every run watched (isolation.py):
- revert: the fix's non-test files go back to base while the tests stay at head. The repro test
  must fail, and if the PR added or changed tests, at least one of their files must fail too;
- mutation: a model proposes small bugs in the fixed lines, our hygiene rules decide which ones
  count, and a mutant is killed when a test that passed on head fails on it. Fixed rule mutants
  (mutation_rules.py) run the same way but are report only: they never count toward the verdict.

The model only proposes mutants. Every verdict here comes from pytest exit codes, JUnit reports
and counts: `guarded` needs both experiments to pass and at least 80% of 3+ valid mutants killed.
Anything that can't be judged cleanly is `inconclusive`, never a pass.
"""

import ast
import configparser
import difflib
import fnmatch
import hashlib
import json
import tomllib
from collections import Counter
from collections.abc import Callable, Mapping, Sequence, Set
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal

from tracefix.diffscope import DiffScope, FileChange, FileKind, function_spans
from tracefix.isolation import TamperingDetected, run_checked
from tracefix.llm import BudgetExceeded, LLMClient, LLMOutputError, LLMProviderError, Message
from tracefix.mutation_rules import (
    KINDS,
    RuleKind,
    RuleProposal,
    body_proposals,
    rule_proposals,
)
from tracefix.prompts import mutator, python_note
from tracefix.repro import REPRO_TIMEOUT_S, ReproResult, ReproStatus, called_name
from tracefix.runner import FailureInfo, Outcome, RunResult, pytest_config
from tracefix.sandbox import BASIC_WARNING, Level, sandbox_level
from tracefix.variant import swapped, variant_copy
from tracefix.workspace import Workspace, WorkspaceError, blob_text, git_bytes, safe_relpath

MIN_MUTANTS = 3  # fewer valid mutants: inconclusive (Decided in M4 by the developer)
MAX_MUTANTS = 10
# The mutator is asked for 8-10; fewer valid than this after its first answer gets the one
# follow-up (M11, NOTES 24: a median of 4 valid mutants made one survivor flip verdicts).
WANT_MUTANTS = 6
MAX_RULE_MUTANTS = 10  # report only (Decided 3 Oct 2026 by the developer); one per kind fits
KILL_PERCENT = 80
MUTATOR_CALLS = 2  # one request, plus one follow-up if fewer than WANT_MUTANTS passed hygiene
GUARD_RERUNS = 1  # a failure must repeat once to count; so must a timeout
MIN_TIMEOUT_S = 30.0
TIMEOUT_FACTOR = 10  # a mutant run may take this many times its baseline run
MAX_EDIT_LINES = 5
MAX_EDIT_CHARS = 300
MAX_LISTING_LINES = 400
CONTEXT_LINES = 3  # around fixed lines outside any function
# A mutant may not add any of these. They would let a "small edit" reach outside the code under
# test, crash or hang every call (an easy kill), or hide new behaviour (Decided in M4: hygiene).
LIMITED_NODES: tuple[type[ast.AST], ...] = (
    ast.Import, ast.ImportFrom, ast.Raise, ast.Assert, ast.Call, ast.Lambda, ast.Yield,
    ast.YieldFrom, ast.Await, ast.Global, ast.Nonlocal, ast.Delete, ast.With, ast.AsyncWith,
    ast.Try, ast.TryStar, ast.While, ast.For, ast.AsyncFor, ast.FunctionDef,
    ast.AsyncFunctionDef, ast.ClassDef, ast.ListComp, ast.SetComp, ast.DictComp,
    ast.GeneratorExp,
)  # fmt: skip
HUGE_OPS = (ast.Pow, ast.LShift)  # `10 ** 10 ** 10` or `1 << 10**12` takes forever to compute
DUPLICATE = "the same code as an earlier mutant"
SKIPPED_TEST_NAMES = ("conftest.py", "__init__.py")  # never run as a PR test file
DEFAULT_PYTHON_FILES = ("test_*.py", "*_test.py")  # pytest's default
SET_NAMES: dict[str, str] = {"repro": "reproduction test", "pr_test": "PR's tests",
                             "suite": "existing suite"}  # fmt: skip

TestSet = Literal["repro", "pr_test", "suite"]
FindingKind = Literal[
    "repro_passes_on_revert", "pr_tests_pass_on_revert", "low_kill_rate", "too_few_mutants"
]


class GuardStatus(StrEnum):
    GUARDED = "guarded"
    NOT_GUARDED = "not_guarded"
    INCONCLUSIVE = "inconclusive"  # too few valid mutants, or a run that couldn't be judged
    SKIPPED = "skipped"  # nothing to guard with (not reproduced) or nothing to revert
    INVALID = "invalid"  # tampering detected: no verdict at all


class MutantStatus(StrEnum):
    KILLED = "killed"
    SURVIVED = "survived"
    DISCARDED = "discarded"  # does not import or collect: not counted


@dataclass(frozen=True)
class Mutant:
    number: int
    path: str
    line: int
    original: str
    replacement: str
    description: str  # the model's words: shown, never used for a verdict
    diff: str  # unified diff from head
    text: str = field(repr=False)  # the whole mutated file
    lines: frozenset[int] = frozenset()  # lines of `text` the edit wrote
    origin: Literal["model", "rule"] = "model"  # rule mutants are report only
    kind: RuleKind | None = None  # a rule mutant's kind; not part of its id

    @property
    def id(self) -> str:
        """The same edit has the same id in every run and receipt (`number` is per run)."""
        edit = json.dumps([self.path, self.line, self.original, self.replacement])
        return "m-" + hashlib.sha256(edit.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class Rejected:
    proposal: mutator.MutantProposal
    reason: str


@dataclass(frozen=True)
class MutantResult:
    mutant: Mutant
    status: MutantStatus
    killed_by: tuple[TestSet, ...]
    not_run: tuple[TestSet, ...]  # e.g. the suite, for a mutant already killed
    timed_out: bool
    reason: str
    runs: tuple[tuple[TestSet, RunResult], ...]
    # Every kill came from an exception (not a failed check) raised on the mutated lines: the
    # mutant breaks every call, which any test notices. Reported, still counted (open q 26).
    crash_only: bool = False


@dataclass(frozen=True)
class PrFileCheck:
    path: str
    run: RunResult
    caught: bool  # failed (or could no longer be collected) with the fix reverted
    usable: bool = True  # ran cleanly on head, so its result on the reverted code means something

    @property
    def clean(self) -> bool:
        """It caught the revert, or ended passed/failed: either way a clear answer."""
        return self.caught or self.run.outcome in (Outcome.PASSED, Outcome.FAILED)


@dataclass(frozen=True)
class RevertCheck:
    files: tuple[str, ...]  # put back to base (or removed, if the fix added them)
    repro: RunResult
    repro_fails: bool  # failed on every attempt
    pr_files: tuple[PrFileCheck, ...]

    @property
    def repro_clean(self) -> bool:
        return self.repro.outcome in (Outcome.PASSED, Outcome.FAILED)


@dataclass(frozen=True)
class GuardFinding:
    kind: FindingKind
    detail: str
    file: str | None = None


@dataclass(frozen=True)
class GuardResult:
    status: GuardStatus
    reason: str
    pr_test_files: tuple[str, ...] = ()
    revert: RevertCheck | None = None
    mutants: tuple[MutantResult, ...] = ()
    rejected: tuple[Rejected, ...] = ()
    kill_rate: float | None = None  # all test sets together, over valid mutants
    repro_kill_rate: float | None = None
    pr_kill_rate: float | None = None
    findings: tuple[GuardFinding, ...] = ()
    baselines: tuple[RunResult, ...] = ()  # each test set's run on unmodified head
    isolation: Level = "basic"
    warnings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    crash_kills: int = 0  # killed mutants whose kills were all crashes on the mutated lines
    # Fixed rule mutants: shown with their own kill rate, never part of the verdict.
    rule_mutants: tuple[MutantResult, ...] = ()
    rule_kill_rate: float | None = None
    # Model mutants left unrun once "not guarded" was certain (certain_not_guarded).
    not_run: tuple[Mutant, ...] = ()


# --- the fixed lines and the hygiene rules (pure) ----------------------------------------------


@dataclass(frozen=True)
class SourceFile:
    """A changed Python source file, as text, with the head lines the fix added or changed."""

    path: str
    head: str
    base: str | None  # None if the fix added the file
    fixed: frozenset[int]


def fixed_lines(change: FileChange, n_lines: int) -> frozenset[int]:
    """Head lines the fix added or changed; for a pure deletion, the lines either side of it."""
    lines: set[int] = set()
    for hunk in change.hunks:
        if hunk.head_len:
            lines.update(hunk.head_lines)
        else:
            lines.update({hunk.head_start, hunk.head_start + 1})
    return frozenset(n for n in lines if 1 <= n <= n_lines)


def _line_starts(text: str) -> list[int]:
    starts = [0]
    starts += [i + 1 for i, ch in enumerate(text) if ch == "\n"]
    return starts


def _locate(text: str, line: int, original: str) -> int | str:
    """Offset of the one occurrence of `original` that starts on `line`, or why there isn't one."""
    starts = _line_starts(text)
    if not 1 <= line <= len(starts):
        return f"line {line} is not in the file"
    begin = starts[line - 1]
    end = starts[line] if line < len(starts) else len(text) + 1
    hits = []
    index = text.find(original, begin)
    while index != -1 and index < end:
        hits.append(index)
        index = text.find(original, index + 1)
    if not hits:
        return f"`original` does not start on line {line}"
    if len(hits) > 1:
        return f"`original` occurs more than once on line {line}"
    return hits[0]


def _edits(before: str, after: str) -> list[tuple[int, int, int, int]]:
    """(i1, i2, j1, j2) of every non-equal block, as difflib's line opcodes (0-based, end-open)."""
    matcher = difflib.SequenceMatcher(None, before.split("\n"), after.split("\n"), autojunk=False)
    return [(i1, i2, j1, j2) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]


def outside_fixed(before: str, after: str, fixed: frozenset[int]) -> int | None:
    """The first head line an edit touched that the fix didn't add or change, else None. A
    replaced or deleted line must be fixed; an insertion needs a fixed line on either side."""
    for i1, i2, _j1, _j2 in _edits(before, after):
        if i2 > i1:
            bad = [n for n in range(i1 + 1, i2 + 1) if n not in fixed]
            if bad:
                return bad[0]
        elif not {i1, i1 + 1} & fixed:
            return max(i1, 1)
    return None


def changed_lines(before: str, after: str) -> frozenset[int]:
    """Lines (1-based) of `after` that an edit wrote: where a mutant's own crash would point."""
    return frozenset(n for _i1, _i2, j1, j2 in _edits(before, after) for n in range(j1 + 1, j2 + 1))


def _names(tree: ast.AST) -> dict[str, set[str]]:
    """Identifiers by kind: a name can only be swapped for another name, an attribute for an
    attribute, a keyword for a keyword (an attribute reused as a bare name is a NameError)."""
    kinds: dict[str, set[str]] = {"name": set(), "attribute": set(), "keyword": set()}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            kinds["name"].add(node.id)
        elif isinstance(node, ast.Attribute):
            kinds["attribute"].add(node.attr)
        elif isinstance(node, ast.keyword) and node.arg:
            kinds["keyword"].add(node.arg)
        elif isinstance(node, ast.arg):
            kinds["name"].add(node.arg)
        elif isinstance(node, ast.alias):
            kinds["name"].add(node.asname or node.name.split(".")[0])
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            kinds["name"].add(node.name)
    return kinds


def _is_zero(node: ast.AST) -> bool:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
        return _is_zero(node.operand)
    value = node.value if isinstance(node, ast.Constant) else None
    return isinstance(value, int | float | complex) and value == 0  # False counts: x / False


def _is_none(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _is_empty_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.List | ast.Tuple | ast.Set):
        return not node.elts
    if isinstance(node, ast.Dict):
        return not node.keys
    return isinstance(node, ast.Constant) and node.value in ("", b"")


def _limited(tree: ast.AST) -> Counter[str]:
    """Counts of what a mutant may not add: limited nodes, huge-result operators, division by a
    constant zero, arithmetic with None, indexing an empty literal, and each callee by name.

    These only bound edits that fail on every call; kills by such crashes that still get through
    (e.g. `+ ""`) are reported separately (crash_only)."""
    found: Counter[str] = Counter()
    for node in ast.walk(tree):
        if isinstance(node, LIMITED_NODES):
            found[type(node).__name__] += 1
        if isinstance(node, ast.Call):
            # By name: `self.items[n].get(k)` calls `get`, so an off-by-one in its receiver is
            # still a small edit, while swapping `int(x)` for `system(x)` is not.
            found[f"a call to {called_name(node) or 'an expression'}"] += 1
        operands: tuple[ast.AST | None, ...] = ()
        op = None
        if isinstance(node, ast.BinOp):
            op, operands = node.op, (node.left, node.right)
        elif isinstance(node, ast.AugAssign):
            op, operands = node.op, (node.target, node.value)
        if isinstance(op, HUGE_OPS):
            found[type(op).__name__] += 1
        divisor = operands[1] if operands else None
        if isinstance(op, ast.Div | ast.FloorDiv | ast.Mod) and divisor and _is_zero(divisor):
            found["division by a constant 0"] += 1
        if any(_is_none(o) for o in operands):
            found["arithmetic with None"] += 1
        if isinstance(node, ast.Subscript) and _is_empty_literal(node.value):
            found["indexing into an empty literal"] += 1
    return found


def _size_problem(proposal: mutator.MutantProposal) -> str | None:
    if not proposal.original:
        return "`original` is empty"
    for name in ("original", "replacement"):
        text = getattr(proposal, name)
        if len(text) > MAX_EDIT_CHARS or len(text.split("\n")) > MAX_EDIT_LINES:
            return f"`{name}` is longer than {MAX_EDIT_LINES} lines or {MAX_EDIT_CHARS} characters"
    return None


def _apply(source: SourceFile, proposal: mutator.MutantProposal) -> str:
    """The mutated file text, or raise ValueError with the reason (rules 2-3). Which lines the
    edit touched is measured on the result, so an edit can't reach an unfixed line by eating a
    newline."""
    problem = _size_problem(proposal)
    if problem:
        raise ValueError(problem)
    found = _locate(source.head, proposal.line, proposal.original)
    if isinstance(found, str):
        raise ValueError(found)
    end = found + len(proposal.original)
    text = source.head[:found] + proposal.replacement + source.head[end:]
    outside = outside_fixed(source.head, text, source.fixed)
    if outside is not None:
        raise ValueError(f"line {outside} is not a line the fix added or changed")
    return text


def _tree_problem(source: SourceFile, text: str, allowed: Counter[str]) -> tuple[str | None, str]:
    """(reason the mutated text is rejected or None, its AST dump): rules 4-7."""
    try:
        tree = ast.parse(text)
        compile(text, source.path, "exec")
    except (SyntaxError, ValueError, RecursionError) as exc:
        return f"the mutated file does not compile: {exc}", ""
    dump = ast.dump(tree)
    head_tree = ast.parse(source.head)  # source_files only keeps files that parse
    if dump == ast.dump(head_tree):
        return "it changes no code (only layout or comments)", dump
    if source.base is not None and _same_code(dump, source.base):
        return "it is the code from before the fix (the revert check covers that)", dump
    head_names = _names(head_tree)
    for kind, names in _names(tree).items():
        new = sorted(names - head_names[kind])
        if new:
            return f"it uses {kind}s not already in the file: {', '.join(new)}", dump
    added = _limited(tree) - _limited(head_tree) - allowed
    if added:
        return f"it adds {', '.join(sorted(added))} (only small edits count)", dump
    return None, dump


def _same_code(dump: str, other: str) -> bool:
    try:
        return dump == ast.dump(ast.parse(other))
    except (SyntaxError, ValueError, RecursionError):
        return False


def check_proposal(
    proposal: mutator.MutantProposal, sources: Mapping[str, SourceFile], seen: set[str]
) -> str:
    """The mutated file text if the proposal follows every hygiene rule, else raise ValueError
    with the reason. `seen` holds the code of mutants accepted so far (rule 8)."""
    source = sources.get(proposal.path)
    if source is None:
        raise ValueError(f"{proposal.path} is not a Python source file the fix changed")
    return _accept(source, _apply(source, proposal), seen)


def check_body(proposal: mutator.MutantProposal, source: SourceFile, seen: set[str]) -> str:
    """The mutated file text for a body mutant (mutation_rules.body_proposals), else raise
    ValueError. Our own code wrote it, so the line rules (2-3), which keep the model to small
    edits on the fixed lines, don't apply; rules 4-8 do."""
    found = _locate(source.head, proposal.line, proposal.original)
    if isinstance(found, str):
        raise ValueError(found)
    end = found + len(proposal.original)
    return _accept(source, source.head[:found] + proposal.replacement + source.head[end:], seen)


def check_reraise(proposal: mutator.MutantProposal, source: SourceFile, seen: set[str]) -> str:
    """The mutated file text for a re-raise (mutation_rules._reraise_edits), else raise ValueError.
    The one exception to "no added raise", and only our own code gets here (rule_mutants): model
    mutants go through check_proposal and still can't add one. Every other rule applies."""
    added, _, rest = proposal.replacement.partition("\n")
    if added.strip() != "raise" or rest != proposal.original:
        raise ValueError("a re-raise adds a bare `raise` line and nothing else")
    return _accept(source, _apply(source, proposal), seen, Counter({"Raise": 1}))


def _accept(
    source: SourceFile, text: str, seen: set[str], allowed: Counter[str] | None = None
) -> str:
    """`text` if it passes rules 4-8, else raise ValueError with the reason. `allowed`: limited
    nodes this edit may add (only ever a rule mutant's)."""
    try:
        problem, dump = _tree_problem(source, text, allowed or Counter())
    except RecursionError:  # e.g. a 1,500-term `+` chain elsewhere in the file: ast.dump recurses
        raise ValueError("the file is too deeply nested to compare mutants") from None
    if problem:
        raise ValueError(problem)
    if dump in seen:
        raise ValueError(DUPLICATE)
    seen.add(dump)
    return text


def _diff(path: str, before: str, after: str) -> str:
    lines = difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                 f"a/{path}", f"b/{path}", n=1)  # fmt: skip
    return "".join(lines)


# --- reading the fix (git objects only) ---------------------------------------------------------


def _parses(text: str) -> bool:
    try:
        ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return False
    return True


def source_files(ws: Workspace, scope: DiffScope) -> tuple[list[SourceFile], list[str]]:
    """The changed Python source files that can be mutated, and notes on any that can't."""
    found, notes = [], []
    for change in scope.source_files:
        if change.status == "D" or not change.path.endswith(".py"):
            continue
        if not ws.in_head(change.path):
            notes.append(f"{change.path} was not exported, so it is not mutated")
            continue
        head = blob_text(ws.repo, ws.head_sha, change.path)
        if head is None or not _parses(head):
            notes.append(f"{change.path} is not UTF-8 Python that parses, so it is not mutated")
            continue
        base = None
        if change.status not in "AC":
            base = blob_text(ws.repo, ws.base_sha, change.old_path or change.path)
        fixed = fixed_lines(change, len(head.split("\n")))
        if fixed:
            found.append(SourceFile(change.path, head, base, fixed))
    return found, notes


def revert_files(ws: Workspace, scope: DiffScope) -> tuple[dict[str, bytes | None], list[str]]:
    """{path: base bytes, or None to delete} that turn head back into base for every non-test
    file the fix changed, tests untouched: the fix's source hunks reversed, file by file."""
    files: dict[str, bytes | None] = {}
    notes = []
    for change in scope.files:
        if change.kind is FileKind.TEST:
            continue
        restore = None if change.status in "AC" else (change.old_path or change.path)
        if change.status in "ACR" and ws.in_head(change.path):
            files[change.path] = None  # added (or the new name of a rename): remove it
        if restore is None:
            continue
        if safe_relpath(restore) is None:
            notes.append(f"{restore} is not a safe path, so it is not put back")
            continue
        try:
            files[restore] = git_bytes(ws.repo, "show", f"{ws.base_sha}:{restore}")
        except WorkspaceError as exc:
            notes.append(f"{restore} could not be put back for the revert check: {exc}")
    return files, notes


def _patterns(value: object) -> tuple[str, ...] | None:
    if isinstance(value, str):
        return tuple(value.split())
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return tuple(value)
    return None


def python_files(config: Path | None) -> tuple[str, ...]:
    """pytest's `python_files` patterns from its config file (default `test_*.py *_test.py`).
    The file is only parsed, never run; anything unreadable gives the default."""
    found: tuple[str, ...] | None = None
    try:
        if config is None:
            pass
        elif config.name == "pyproject.toml":
            tool = tomllib.loads(config.read_text(encoding="utf-8")).get("tool", {})
            table = tool.get("pytest", {}) if isinstance(tool, dict) else {}
            for options in (table.get("ini_options", {}), table):  # pytest 9 reads [tool.pytest]
                if isinstance(options, dict) and found is None:
                    found = _patterns(options.get("python_files"))
        else:
            parser = configparser.ConfigParser(interpolation=None)
            parser.read_string(config.read_text(encoding="utf-8"))
            section = "tool:pytest" if config.name == "setup.cfg" else "pytest"
            if parser.has_option(section, "python_files"):
                found = _patterns(parser.get(section, "python_files"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, configparser.Error):
        found = None
    return found or DEFAULT_PYTHON_FILES


def pr_test_candidates(scope: DiffScope, tree: Path) -> tuple[str, ...]:
    """Test files the PR added or modified that pytest would collect, by the `python_files` of
    the config that applies to each (read from head's copy at `tree`). Helpers are never run as
    tests; which candidates actually hold tests is decided by running them (_pr_files)."""
    root = tree.resolve()
    found = []
    for change in scope.test_files:
        name = PurePosixPath(change.path).name
        if change.status == "D" or not name.endswith(".py") or name in SKIPPED_TEST_NAMES:
            continue
        patterns = python_files(pytest_config(root, [change.path]))
        if any(fnmatch.fnmatch(change.path if "/" in p else name, p) for p in patterns):
            found.append(change.path)
    return tuple(sorted(found))


def _listing(source: SourceFile) -> str:
    """Head's lines around the fix, numbered, fixed lines marked ">": every function holding a
    fixed line, and a few lines of context around fixed lines outside functions."""
    lines = source.head.split("\n")
    try:
        spans = list(function_spans(source.head.encode("utf-8")).values())
    except (SyntaxError, ValueError):
        spans = []
    shown: set[int] = set()
    for n in source.fixed:
        holding = [s for s in spans if s[0] <= n <= s[1]]
        first, last = (n - CONTEXT_LINES, n + CONTEXT_LINES)
        if holding:
            first, last = min(holding, key=lambda s: s[1] - s[0])  # the innermost function
        shown.update(range(max(first, 1), min(last, len(lines)) + 1))
    out, previous = [], 0
    for n in sorted(shown)[:MAX_LISTING_LINES]:
        if previous and n != previous + 1:
            out.append("        ...")
        out.append(f"{'>' if n in source.fixed else ' '} {n:>5} | {lines[n - 1]}")
        previous = n
    if len(shown) > MAX_LISTING_LINES:
        out.append(f"[... {len(shown) - MAX_LISTING_LINES} more lines not shown ...]")
    return "\n".join(out)


def mutator_context(
    sources: Sequence[SourceFile], python: tuple[int, ...] = (3, 11)
) -> mutator.MutatorContext:
    """Head's numbered fixed lines only: no diff, so the base code isn't put in front of the
    model as a ready-made mutant (it would be killed whenever the revert check passes).
    `python`: the project's Python version (prompts.python_note)."""
    listings = tuple(mutator.Listing(s.path, _listing(s)) for s in sources)
    return mutator.MutatorContext(listings, python_note(python))


def propose(
    client: LLMClient, ctx: mutator.MutatorContext, sources: Sequence[SourceFile]
) -> tuple[list[Mutant], list[Rejected], list[str]]:
    """Ask the mutator, keep what passes hygiene; one follow-up call if fewer than WANT_MUTANTS."""
    by_path = {s.path: s for s in sources}
    history = [Message("user", mutator.render_request(ctx))]
    mutants: list[Mutant] = []
    rejected: list[Rejected] = []
    notes: list[str] = []
    seen: set[str] = set()
    for _ in range(MUTATOR_CALLS):
        try:
            answer = client.complete("mutator", mutator.SYSTEM, history, mutator.MutantProposals)
        except (BudgetExceeded, LLMOutputError, LLMProviderError) as exc:
            notes.append(f"the mutator stopped early: {exc}")
            break
        history.append(Message("assistant", answer.model_dump_json()))
        reasons = []
        for proposal in answer.mutants:
            try:
                text = check_proposal(proposal, by_path, seen)
            except ValueError as exc:
                if str(exc) != DUPLICATE:  # repeats are counted once, not rejected
                    rejected.append(Rejected(proposal, str(exc)))
                    reasons.append(f"{proposal.path}:{proposal.line}: {exc}")
                continue
            source = by_path[proposal.path]
            mutants.append(Mutant(len(mutants) + 1, proposal.path, proposal.line,
                                  proposal.original, proposal.replacement, proposal.description,
                                  _diff(proposal.path, source.head, text), text,
                                  changed_lines(source.head, text)))  # fmt: skip
        if len(mutants) >= WANT_MUTANTS:
            break
        history.append(
            Message("user", mutator.render_feedback(len(mutants), WANT_MUTANTS, reasons))
        )
    if len(mutants) > MAX_MUTANTS:
        notes.append(f"only the first {MAX_MUTANTS} of {len(mutants)} valid mutants were run")
    return mutants[:MAX_MUTANTS], rejected, notes


def _check_rule(proposal: RuleProposal, source: SourceFile, seen: set[str]) -> str:
    """The mutated file text for one rule edit, by the checks its kind goes through."""
    if proposal.kind == "body":
        return check_body(proposal, source, seen)
    if proposal.kind == "reraise":
        return check_reraise(proposal, source, seen)
    return check_proposal(proposal, {source.path: source}, seen)


def _spread(checked: Sequence[tuple[RuleProposal, str]]) -> list[tuple[RuleProposal, str]]:
    """Round-robin over the kinds, in KINDS' order, keeping each kind's own order: one of every
    kind comes before a second of any, so which kinds run doesn't depend on line order."""
    groups = [[c for c in checked if c[0].kind == kind] for kind in KINDS]
    rounds = max(len(group) for group in groups)
    return [group[i] for i in range(rounds) for group in groups if i < len(group)]


def rule_mutants(sources: Sequence[SourceFile], first: int) -> tuple[list[Mutant], list[str]]:
    """The fixed rule edits that pass hygiene, numbered from `first`, at most MAX_RULE_MUTANTS,
    spread over their kinds (_spread)."""
    by_path = {s.path: s for s in sources}
    proposals = [p for s in sources for p in body_proposals(s.path, s.head, s.fixed)]
    proposals += [p for s in sources for p in rule_proposals(s.path, s.head, s.fixed)]
    checked: list[tuple[RuleProposal, str]] = []
    seen: set[str] = set()  # their own pool: a rule mutant equal to a model one still counts here
    for proposal in proposals:
        try:
            checked.append((proposal, _check_rule(proposal, by_path[proposal.path], seen)))
        except ValueError:
            continue  # e.g. `for x not in y` does not compile: simply not a mutant
    ordered = _spread(checked)
    mutants: list[Mutant] = []
    for proposal, text in ordered[:MAX_RULE_MUTANTS]:
        head = by_path[proposal.path].head
        mutants.append(Mutant(first + len(mutants), proposal.path, proposal.line,
                              proposal.original, proposal.replacement, proposal.description,
                              _diff(proposal.path, head, text), text, changed_lines(head, text),
                              "rule", proposal.kind))  # fmt: skip
    notes = []
    if len(ordered) > MAX_RULE_MUTANTS:
        notes.append(f"only the first {MAX_RULE_MUTANTS} of {len(ordered)} rule mutants were run")
    return mutants, notes


# --- runs in the variant copy --------------------------------------------------------------------


@dataclass(frozen=True)
class _Set:
    name: TestSet
    targets: tuple[str, ...]  # () runs the whole suite
    with_repro: bool = False


@dataclass
class _Variant:
    """The extra copy of head, and the head-baseline result of each test set run in it."""

    ws: Workspace
    tree: Path
    repro_path: str
    repro_code: bytes
    baselines: dict[_Set, RunResult] = field(default_factory=dict)
    phase: str = "setup"  # named in the reason when tampering is detected

    def run(self, test_set: _Set, files: Mapping[str, bytes | None], timeout_s: float) -> RunResult:
        placed = dict(files)
        if test_set.with_repro:
            placed[self.repro_path] = self.repro_code
        with swapped(self.tree, placed):
            return run_checked(self.ws, self.tree, test_set.targets, placed=list(placed),
                               timeout_s=timeout_s, reruns=GUARD_RERUNS)  # fmt: skip

    def baseline(self, test_set: _Set) -> RunResult:
        if test_set not in self.baselines:
            timeout = REPRO_TIMEOUT_S if test_set.with_repro else self.ws.settings.suite_timeout_s
            phase, self.phase = self.phase, f"the run of the {SET_NAMES[test_set.name]} on the "
            self.phase += "fixed code"
            self.baselines[test_set] = self.run(test_set, {}, timeout)
            self.phase = phase
        return self.baselines[test_set]

    def usable(self, test_set: _Set) -> bool:
        return usable_baseline(self.baseline(test_set))

    def timeout(self, test_set: _Set) -> float:
        return max(MIN_TIMEOUT_S, TIMEOUT_FACTOR * self.baseline(test_set).first.duration_s)

    def run_twice_if_slow(
        self, test_set: _Set, files: Mapping[str, bytes | None]
    ) -> list[RunResult]:
        """A run, and if it timed out one more (a timeout counts only if it repeats); the last
        one decides."""
        results = [self.run(test_set, files, self.timeout(test_set))]
        if results[0].outcome is Outcome.TIMEOUT:
            results.append(self.run(test_set, files, self.timeout(test_set)))
        return results


# --- the rules (pure) ----------------------------------------------------------------------------


def kill(run: RunResult, baseline: RunResult) -> tuple[bool, bool]:
    """(killed, timed out) for one test set's run on a mutant, against its run on head.

    Killed: a test that passed on head now fails on every attempt, or the run times out (the
    caller makes a timeout repeat). A flaky failure is not a kill. A set that couldn't run
    cleanly on head kills nothing."""
    if baseline.outcome not in (Outcome.PASSED, Outcome.FAILED):
        return False, False
    if run.outcome is Outcome.TIMEOUT:
        return True, True
    if run.outcome is Outcome.FAILED:
        return bool(set(run.first.failed) & set(baseline.first.passed)), False
    return False, False


def usable_baseline(run: RunResult) -> bool:
    """A test set's run on head can judge a change: it ran cleanly (some tests may fail there)
    and at least one test passed. All skipped (e.g. a platform skipif) judges nothing."""
    return run.outcome in (Outcome.PASSED, Outcome.FAILED) and bool(run.first.passed)


def crash_only(failures: Sequence[FailureInfo], path: str, lines: Set[int]) -> bool:
    """Every failure is an exception other than AssertionError raised on one of the mutated
    `lines` of `path`: the mutant crashes, rather than a test checking a wrong result."""
    if not failures:
        return False
    for failure in failures:
        if failure.exc_type in (None, "AssertionError") or failure.location is None:
            return False
        file, _, line = failure.location.rpartition(":")
        in_file = file == path or file.endswith("/" + path)
        if not in_file or not line.isdigit() or int(line) not in lines:
            return False
    return True


def collection_error(run: RunResult) -> bool:
    """pytest stopped at collection (exit 2) and its report says so: only errors, no failures.
    Not an internal error, a usage error, or a report that disagrees with the exit code."""
    attempt = run.first
    return (run.outcome is Outcome.ERROR and attempt.exit_code == 2 and attempt.report_ok
            and bool(attempt.failures)
            and all(f.kind == "error" for f in attempt.failures))  # fmt: skip


def caught_revert(run: RunResult, baseline: RunResult) -> bool:
    """A PR test file catches the revert if a test that passed on head fails, or if a file that
    passed on head can no longer be collected (e.g. it imports a name only the fix added)."""
    if run.outcome is Outcome.ERROR:
        return baseline.outcome is Outcome.PASSED and collection_error(run)
    killed, timed_out = kill(run, baseline)
    return killed and not timed_out


def revert_findings(revert: RevertCheck) -> list[GuardFinding]:
    findings = []
    if revert.repro.outcome is Outcome.PASSED:
        detail = "the reproduction test still passes with the fix reverted"
        findings.append(GuardFinding("repro_passes_on_revert", detail))
    usable = [c for c in revert.pr_files if c.usable]
    if usable and not any(c.caught for c in usable) and all(c.clean for c in usable):
        for check in usable:
            detail = (f"the PR's test file {check.path} does not fail with the fix reverted "
                      f"({check.run.outcome})")  # fmt: skip
            findings.append(GuardFinding("pr_tests_pass_on_revert", detail, check.path))
    return findings


def _mutation_finding(results: Sequence[MutantResult]) -> GuardFinding | None:
    valid = [r for r in results if r.status is not MutantStatus.DISCARDED]
    killed = sum(r.status is MutantStatus.KILLED for r in valid)
    if len(valid) < MIN_MUTANTS:
        detail = (f"only {len(valid)} valid mutants were run; at least {MIN_MUTANTS} are needed "
                  "to judge the tests")  # fmt: skip
        return GuardFinding("too_few_mutants", detail)
    if killed * 100 < len(valid) * KILL_PERCENT:
        detail = f"the tests killed {killed} of {len(valid)} mutants; {KILL_PERCENT}% is needed"
        return GuardFinding("low_kill_rate", detail)
    return None


def certain_not_guarded(killed: int, valid: int, remaining: int) -> bool:
    """True once the mutants already run settle the rate: at least MIN_MUTANTS valid, and even if
    every one of the `remaining` were valid and killed, under KILL_PERCENT% would be killed.
    Remaining ones that turn out discarded only lower the rate further, so stopping here never
    changes what `decide` says (M11, NOTES 24; property-tested)."""
    if valid < MIN_MUTANTS:
        return False
    return (killed + remaining) * 100 < (valid + remaining) * KILL_PERCENT


def run_until_certain(
    mutants: Sequence[Mutant], run: Callable[[Mutant], MutantResult]
) -> tuple[list[MutantResult], tuple[Mutant, ...]]:
    """Run the mutants in order until `certain_not_guarded`; returns the results and the
    mutants left unrun."""
    results: list[MutantResult] = []
    for i, mutant in enumerate(mutants):
        valid = [r for r in results if r.status is not MutantStatus.DISCARDED]
        killed = sum(r.status is MutantStatus.KILLED for r in valid)
        if certain_not_guarded(killed, len(valid), len(mutants) - i):
            return results, tuple(mutants[i:])
        results.append(run(mutant))
    return results, ()


def decide(
    revert: RevertCheck, results: Sequence[MutantResult], unusable: Sequence[str] = ()
) -> tuple[GuardStatus, str, tuple[GuardFinding, ...]]:
    """The verdict. A revert finding means not_guarded whatever the mutants say (Decided in M1).
    Anything that couldn't be judged cleanly is inconclusive, never guarded. Then at least
    MIN_MUTANTS valid mutants, of which at least KILL_PERCENT% killed. `unusable` names the test
    sets that couldn't run cleanly on head (so they could kill nothing)."""
    findings = revert_findings(revert)
    mutation = _mutation_finding(results)
    if findings:
        reason = "; ".join(f.detail for f in findings)
        return GuardStatus.NOT_GUARDED, reason, tuple(findings + ([mutation] if mutation else []))
    extra = (mutation,) if mutation else ()
    if not revert.repro_clean:
        reason = (f"the reproduction test did not run cleanly with the fix reverted "
                  f"({revert.repro.outcome}), so the revert check can't be judged")  # fmt: skip
        return GuardStatus.INCONCLUSIVE, reason, extra
    usable = [c for c in revert.pr_files if c.usable]
    unclean = [c for c in usable if not c.clean]
    if unclean and not any(c.caught for c in usable):
        check = unclean[0]
        reason = (f"the PR's test file {check.path} did not run cleanly with the fix reverted "
                  f"({check.run.outcome}), so the revert check can't be judged")  # fmt: skip
        return GuardStatus.INCONCLUSIVE, reason, extra
    if revert.pr_files and not usable:
        reason = "none of the PR's test files runs cleanly on the fixed code, so none can judge it"
        return GuardStatus.INCONCLUSIVE, reason, extra
    if mutation is None:
        valid = [r for r in results if r.status is not MutantStatus.DISCARDED]
        killed = sum(r.status is MutantStatus.KILLED for r in valid)
        reason = (f"the reproduction test fails with the fix reverted, and the tests killed "
                  f"{killed} of {len(valid)} mutants")  # fmt: skip
        return GuardStatus.GUARDED, reason, ()
    if mutation.kind == "too_few_mutants":
        return GuardStatus.INCONCLUSIVE, mutation.detail, extra
    if unusable:
        reason = (f"{mutation.detail}, but the {' and '.join(unusable)} could not run cleanly on "
                  "the fixed code, so the rate is incomplete")  # fmt: skip
        return GuardStatus.INCONCLUSIVE, reason, extra
    return GuardStatus.NOT_GUARDED, mutation.detail, extra


def rate(results: Sequence[MutantResult], test_set: TestSet | None = None) -> float | None:
    """Share of valid mutants killed (by `test_set`, or by any set); None with no valid mutant."""
    valid = [r for r in results if r.status is not MutantStatus.DISCARDED]
    if not valid:
        return None
    if test_set is None:
        hits = sum(r.status is MutantStatus.KILLED for r in valid)
    else:
        hits = sum(test_set in r.killed_by for r in valid)
    return round(hits / len(valid), 3)


# --- the stage -----------------------------------------------------------------------------------


def _new_failures(run: RunResult, baseline: RunResult) -> list[FailureInfo]:
    passed = set(baseline.first.passed)
    return [f for f in run.first.failures if f.test in passed]


def _run_mutant(variant: _Variant, sets: Sequence[_Set], suite: _Set, m: Mutant) -> MutantResult:
    """Repro and PR tests on every mutant; the suite only if neither killed it (Decided in M4)."""
    kind = "rule mutant" if m.origin == "rule" else "mutant"
    variant.phase = f"the run of {kind} {m.number}"
    files = {m.path: m.text.encode("utf-8")}
    runs: list[tuple[TestSet, RunResult]] = []
    killed_by: list[TestSet] = []
    timed_out = False
    killing: list[FailureInfo] = []  # what failed in the kills, to tell crashes from checks
    for test_set in [*sets, suite]:
        if test_set is suite and killed_by:
            break
        attempts = variant.run_twice_if_slow(test_set, files)
        runs += [(test_set.name, r) for r in attempts]
        run = attempts[-1]
        if test_set.with_repro and run.outcome is Outcome.ERROR:
            reason = "the mutated code does not import or collect (pytest error); not counted"
            return MutantResult(m, MutantStatus.DISCARDED, (), (), False, reason, tuple(runs))
        killed, slow = kill(run, variant.baseline(test_set))
        if killed:
            killed_by.append(test_set.name)
            timed_out = timed_out or slow
            killing += _new_failures(run, variant.baseline(test_set))
    if not killed_by:
        survived = "no test caught it"
        return MutantResult(m, MutantStatus.SURVIVED, (), (), False, survived, tuple(runs))
    crash = not timed_out and crash_only(killing, m.path, m.lines)
    reason = f"killed by {', '.join(killed_by)}" + (", by crashing on the mutated line" * crash)
    not_run: tuple[TestSet, ...] = ("suite",) if "suite" not in killed_by else ()
    return MutantResult(m, MutantStatus.KILLED, tuple(killed_by), not_run, timed_out, reason,
                        tuple(runs), crash)  # fmt: skip


def _rule_step(variant: _Variant, sets: Sequence[_Set], suite: _Set, sources: Sequence[SourceFile],
               first: int) -> tuple[list[MutantResult], list[str]]:  # fmt: skip
    """Make and run the rule mutants. Report only: an error here becomes a note, never a changed
    verdict. Tampering still escapes, so the stage is invalid as for any other run. Any other
    error is caught, not only the expected ones: a bug in our own rules (verifier B1, an
    IndexError) must not throw away a verdict that is already decided."""
    try:
        rules, notes = rule_mutants(sources, first)
        results = [_run_mutant(variant, sets, suite, m) for m in rules]
    except TamperingDetected:
        raise
    except Exception as exc:
        return [], [f"the rule mutants could not finish ({type(exc).__name__}: {exc}); "
                    "they never count toward the verdict"]  # fmt: skip
    crashes = sum(r.crash_only for r in results)
    if crashes:
        notes.append(f"{crashes} of the rule mutant kills were crashes on the mutated line")
    return results, notes


def _revert(variant: _Variant, files: Mapping[str, bytes | None], repro: _Set,
            pr_sets: Sequence[_Set]) -> RevertCheck:  # fmt: skip
    variant.phase = "the revert check"
    repro_run = variant.run_twice_if_slow(repro, files)[-1]
    checks = []
    for test_set in pr_sets:
        run = variant.run_twice_if_slow(test_set, files)[-1]
        caught = caught_revert(run, variant.baseline(test_set))
        checks.append(PrFileCheck(test_set.targets[0], run, caught, variant.usable(test_set)))
    fails = repro_run.outcome is Outcome.FAILED
    return RevertCheck(tuple(sorted(files)), repro_run, fails, tuple(checks))


def _pr_files(variant: _Variant, candidates: Sequence[str], notes: list[str]) -> tuple[str, ...]:
    """The candidate files that hold tests, from their run on head (exit 5: no tests in it)."""
    kept = []
    for path in candidates:
        if variant.baseline(_Set("pr_test", (path,))).outcome is Outcome.NO_TESTS:
            notes.append(f"{path} has no tests, so it is not counted as a PR test")
        else:
            kept.append(path)
    return tuple(kept)


def guard(ws: Workspace, scope: DiffScope, repro: ReproResult, client: LLMClient) -> GuardResult:
    """Run the revert and mutation checks for a reproduced fix (SPEC 2.4)."""
    level = sandbox_level()
    warnings = ((BASIC_WARNING,) if level == "basic" else ()) + tuple(ws.notes)

    def early(status: GuardStatus, reason: str, notes: Sequence[str] = ()) -> GuardResult:
        return GuardResult(status, reason, notes=tuple(notes), isolation=level, warnings=warnings)

    if repro.status is not ReproStatus.REPRODUCED or repro.test_code is None:
        return early(GuardStatus.SKIPPED, "there is no reproduction test to judge the tests "
                     f"with ({repro.status})")  # fmt: skip
    files, notes = revert_files(ws, scope)
    if not files:
        reason = "the fix changes no non-test file, so there is nothing to revert"
        return early(GuardStatus.SKIPPED, reason, notes)
    variant: _Variant | None = None
    phase = "the export of the variant copy"
    try:
        with variant_copy(ws, ws.head_sha, "head") as tree:
            variant = _Variant(ws, tree, repro.test_path, repro.test_code.encode())
            result = _check(ws, scope, client, variant, files, notes, level, warnings)
            variant.phase = "the final check of the variant copy"
        return result
    except TamperingDetected as exc:
        # Never a verdict: the stage is invalid, whatever the runs said (Decided in M3.5).
        return early(GuardStatus.INVALID, f"during {variant.phase if variant else phase}: {exc}",
                     notes)  # fmt: skip
    except (OSError, WorkspaceError, RecursionError) as exc:
        where = variant.phase if variant else phase
        return early(GuardStatus.INCONCLUSIVE, f"Guard could not finish {where}: "
                     f"{type(exc).__name__}: {exc}", notes)  # fmt: skip


def _check(ws: Workspace, scope: DiffScope, client: LLMClient, variant: _Variant,
           files: Mapping[str, bytes | None], notes: list[str], level: Level,
           warnings: tuple[str, ...]) -> GuardResult:  # fmt: skip
    variant.phase = "the runs on the fixed code"
    repro = _Set("repro", (variant.repro_path,), with_repro=True)
    head = variant.baseline(repro)
    if head.outcome is not Outcome.PASSED or head.first.skipped:
        reason = (f"the reproduction test does not pass cleanly on the fixed code here "
                  f"({head.outcome}), so it cannot judge the tests")  # fmt: skip
        return GuardResult(GuardStatus.INCONCLUSIVE, reason, notes=tuple(notes),
                           baselines=(head,), isolation=level, warnings=warnings)  # fmt: skip
    pr_files = _pr_files(variant, pr_test_candidates(scope, variant.tree), notes)
    revert = _revert(variant, files, repro, [_Set("pr_test", (p,)) for p in pr_files])
    sources, source_notes = source_files(ws, scope)
    notes += source_notes
    mutants: list[Mutant] = []
    rejected: list[Rejected] = []
    if sources:
        context = mutator_context(sources, ws.settings.python.version)
        mutants, rejected, llm_notes = propose(client, context, sources)
        notes += llm_notes
    else:
        notes.append("the fix has no Python source lines to mutate")
    # Only PR files that ran cleanly on head: one broken file would make the set kill nothing.
    usable_pr = tuple(c.path for c in revert.pr_files if c.usable)
    sets = [repro] + ([_Set("pr_test", usable_pr)] if usable_pr else [])
    suite = _Set("suite", ())
    results, not_run = run_until_certain(mutants, lambda m: _run_mutant(variant, sets, suite, m))
    if not_run:
        notes.append(f"{len(not_run)} of the {len(mutants)} mutants were not run: the tests could "
                     f"no longer reach {KILL_PERCENT}% even if they killed them all")  # fmt: skip
    ran = [s for s in [*sets, suite] if s in variant.baselines]
    unusable = [SET_NAMES[s.name] for s in ran if not variant.usable(s)]
    if unusable:
        notes.append(f"the {' and '.join(unusable)} did not run cleanly on the fixed code")
    crashes = sum(r.crash_only for r in results)
    if crashes:
        notes.append(f"{crashes} of the kills were crashes on the mutated line rather than failed "
                     "checks; they still count (open question 26)")  # fmt: skip
    status, reason, findings = decide(revert, results, unusable)
    # Only now the report-only rule mutants: nothing they do can reach the verdict above.
    rule_results, rule_notes = _rule_step(variant, sets, suite, sources, len(mutants) + 1)
    notes += rule_notes
    return GuardResult(
        status, reason, pr_files, revert, tuple(results), tuple(rejected), rate(results),
        rate(results, "repro"), rate(results, "pr_test") if usable_pr else None, findings,
        tuple(variant.baselines.values()), level, warnings, tuple(notes), crashes,
        tuple(rule_results), rate(rule_results), not_run,
    )  # fmt: skip

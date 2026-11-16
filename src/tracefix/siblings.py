"""Sibling sites: code a fix replaced that still exists elsewhere, and same-named functions it
left alone (M11 S0, docs/plans/M11.md). Report only: nothing here sets a verdict or a level.

Static and deterministic: git objects of the two commits, read with git; no repo code runs.
- replaced code: the lines a hunk removed or changed (normalised, significant lines only) still
  appear, in order, in a non-test .py file at head, outside the lines the fix changed. A fix
  that edits one copy of the same code and misses another is the classic incomplete fix;
- same name: a function the fix changed or added has a namesake elsewhere at head (a base or
  sibling class, another module) that the fix did not touch;
- constants: the module-level values a fix assigns, and the ones a test reads by name (a test
  that reads the code's own constant can't notice that value going wrong).
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from tracefix.diffscope import ChangeKind, DiffScope, FileChange, FileKind, classify
from tracefix.workspace import WorkspaceError, blob_text, git_run

MIN_CHARS = 12  # non-space characters for a line to count (`return x` alone matches everywhere)
MIN_LINE_CHARS = 30  # the single-line variant: only long lines
MAX_SITES = 10  # per check and fix
MAX_TEXT = 200

SiteKind = Literal["replaced_code", "replaced_line", "same_name"]


@dataclass(frozen=True)
class SiblingSite:
    kind: SiteKind
    fixed_at: str  # where the fix is: "path:line" before the fix, or a changed function
    path: str  # the other place, at head
    line: int
    text: str  # its first line there, normalised


def normalise(line: str) -> str | None:
    """The line with its spacing collapsed, or None if it doesn't count: blank, a comment, or
    fewer than MIN_CHARS non-space characters."""
    text = " ".join(line.split())
    if not text or text.startswith("#") or len(text.replace(" ", "")) < MIN_CHARS:
        return None
    return text


def _significant(lines: list[str], numbers: range) -> list[tuple[int, str]]:
    found = []
    for n in numbers:
        if 1 <= n <= len(lines):
            text = normalise(lines[n - 1])
            if text is not None:
                found.append((n, text))
    return found


def find_runs(block: list[str], lines: list[str]) -> list[list[int]]:
    """Every place `block` (normalised lines) appears in `lines` in order, lines that don't count
    skipped: the matched line numbers (1-based) of each place."""
    if not block:
        return []
    counted = _significant(lines, range(1, len(lines) + 1))
    texts = [t for _, t in counted]
    places = []
    for i in range(len(texts) - len(block) + 1):
        if texts[i : i + len(block)] == block:
            places.append([n for n, _ in counted[i : i + len(block)]])
    return places


def _changed_head_lines(scope: DiffScope) -> dict[str, set[int]]:
    """Head lines the fix wrote, per file (a pure deletion marks the lines either side)."""
    out: dict[str, set[int]] = {}
    for change in scope.files:
        lines = out.setdefault(change.path, set())
        for hunk in change.hunks:
            if hunk.head_len:
                lines.update(hunk.head_lines)
            else:
                lines.update({hunk.head_start, hunk.head_start + 1})
    return out


def _grep(repo: Path, sha: str, pattern: str, *, regex: bool = False) -> list[tuple[str, int]]:
    """(path, line) of every line of a .py file at `sha` that holds `pattern` (fixed text, or an
    extended regex). Nothing found, or git failing, gives []."""
    mode = "-E" if regex else "-F"
    try:
        run = git_run(repo, "grep", "-n", "-I", mode, "-e", pattern, sha, "--", "*.py")
    except WorkspaceError:
        return []
    if run.returncode != 0:
        return []
    found = []
    prefix = f"{sha}:"
    for raw in run.stdout.decode("utf-8", errors="replace").splitlines():
        rest = raw.removeprefix(prefix)
        path, _, tail = rest.partition(":")
        number, _, _ = tail.partition(":")
        if number.isdigit():
            found.append((path, int(number)))
    return found


def _source_file(path: str) -> bool:
    return path.endswith(".py") and classify(path) is FileKind.SOURCE


def _base_text(repo: Path, scope: DiffScope, change: FileChange) -> list[str] | None:
    if change.status in "AC" or not change.path.endswith(".py"):
        return None
    text = blob_text(repo, scope.base_sha, change.old_path or change.path)
    return None if text is None else text.split("\n")


def _elsewhere(
    repo: Path, scope: DiffScope, block: list[str], first: str, changed: dict[str, set[int]]
) -> list[tuple[str, int]]:
    """Places at head where `block` still is, outside every line the fix changed. `first` is
    the raw text grep looks for (spacing as in the code), the block checks the rest."""
    places = []
    heads: dict[str, list[str]] = {}
    for path in sorted({p for p, _ in _grep(repo, scope.head_sha, first)}):
        if not _source_file(path):
            continue
        if path not in heads:
            text = blob_text(repo, scope.head_sha, path)
            heads[path] = [] if text is None else text.split("\n")
        for run in find_runs(block, heads[path]):
            if not set(run) & changed.get(path, set()):
                places.append((path, run[0]))
    return places


def replaced_code(repo: Path, scope: DiffScope, *, single_lines: bool = False) -> list[SiblingSite]:
    """Where the code each source hunk removed or changed still is at head. By block (all the
    hunk's counting lines, in order), or with `single_lines`, each removed line of at least
    MIN_LINE_CHARS characters on its own (the looser variant)."""
    changed = _changed_head_lines(scope)
    sites: list[SiblingSite] = []
    for change in scope.source_files:
        base = _base_text(repo, scope, change)
        if base is None:
            continue
        where = change.old_path or change.path
        for hunk in change.hunks:
            removed = _significant(base, hunk.base_lines)
            if not removed:
                continue
            fixed_at = f"{where}:{hunk.base_start}"
            if single_lines:
                pieces = [[(n, t)] for n, t in removed if len(t.replace(" ", "")) >= MIN_LINE_CHARS]
                kind: SiteKind = "replaced_line"
            else:
                pieces, kind = [removed], "replaced_code"
            for piece in pieces:
                block = [t for _, t in piece]
                first = base[piece[0][0] - 1].strip()
                for path, line in _elsewhere(repo, scope, block, first, changed):
                    site = SiblingSite(kind, fixed_at, path, line, block[0][:MAX_TEXT])
                    if site not in sites:
                        sites.append(site)
    return sites[:MAX_SITES]


def _def_pattern(name: str) -> str:
    return rf"^[[:space:]]*(async[[:space:]]+)?def[[:space:]]+{re.escape(name)}[[:space:]]*\("


def same_name(repo: Path, scope: DiffScope) -> list[SiblingSite]:
    """Functions at head named like one the fix changed or added (special methods aside) that
    the fix did not touch: in another class, a base class or another module."""
    touched: dict[str, list[tuple[int, int]]] = {}
    for fn in scope.functions:
        if fn.head_span is not None:
            touched.setdefault(fn.path, []).append(fn.head_span)
    sites: list[SiblingSite] = []
    for fn in scope.functions:
        if fn.kind is not FileKind.SOURCE or fn.head_span is None:
            continue
        if fn.change not in (ChangeKind.MODIFIED, ChangeKind.ADDED):
            continue
        name = fn.qualname.rsplit(".", 1)[-1]
        if name.startswith("__") and name.endswith("__"):
            continue
        for path, line in _grep(repo, scope.head_sha, _def_pattern(name), regex=True):
            if not _source_file(path):
                continue
            if any(a <= line <= b for a, b in touched.get(path, [])):
                continue  # the function itself, or another one the fix changed
            text = (blob_text(repo, scope.head_sha, path) or "").split("\n")
            shown = normalise(text[line - 1]) if line <= len(text) else None
            site = SiblingSite("same_name", f"{fn.path}:{fn.head_span[0]} {fn.qualname}", path,
                               line, (shown or f"def {name}(...)")[:MAX_TEXT])  # fmt: skip
            if site not in sites:
                sites.append(site)
    return sites[:MAX_SITES]


# --- constants ----------------------------------------------------------------------------------


def _module_values(text: str | None) -> dict[str, str]:
    """Module-level names assigned a value, with the value's AST (for comparing two sides)."""
    if text is None:
        return {}
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return {}
    found: dict[str, str] = {}
    for node in tree.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        for target in targets:
            if isinstance(target, ast.Name) and value is not None:
                found[target.id] = ast.dump(value)
    return found


def fix_constants(repo: Path, scope: DiffScope) -> frozenset[str]:
    """Module-level names in the fix's source files whose value the fix sets or changes
    (dunders such as `__all__` aside)."""
    names: set[str] = set()
    for change in scope.source_files:
        if not change.path.endswith(".py"):
            continue
        head = _module_values(blob_text(repo, scope.head_sha, change.path))
        base: dict[str, str] = {}
        if change.status not in "AC":
            base = _module_values(blob_text(repo, scope.base_sha, change.old_path or change.path))
        for name, value in head.items():
            if base.get(name) != value and not (name.startswith("__") and name.endswith("__")):
                names.add(name)
    return frozenset(names)


def constant_reads(test_code: str, names: frozenset[str]) -> list[str]:
    """The `names` a test reads: as a bare name, an attribute (`mod.LIMIT`) or an import."""
    try:
        tree = ast.parse(test_code)
    except (SyntaxError, ValueError, RecursionError):
        return []
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            used.update(alias.name for alias in node.names)
    return sorted(used & names)

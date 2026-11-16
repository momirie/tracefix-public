"""What a fix changed: files, hunks, Python functions, and the test-vs-source split.

Fully deterministic: `git diff` between two commit ids plus `ast` on both sides.
"""

import ast
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath

from tracefix.workspace import git, git_bytes

# Fixed diff settings, so neither repo config nor .gitattributes can change the hunks.
# --text stops a `*.py -diff` attribute from hiding a file as binary.
_DIFF_FLAGS = (
    "-M", "--text", "--no-ext-diff", "--no-textconv", "--no-color",
    "--inter-hunk-context=0", "--diff-algorithm=myers", "--no-indent-heuristic",
)  # fmt: skip
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)
_BARE_CR = re.compile(rb"\r(?!\n)")

Key = tuple[str, int]  # (qualname, occurrence)


class FileKind(StrEnum):
    SOURCE = "source"  # a .py file outside the test layout
    TEST = "test"  # test_*.py, *_test.py, conftest.py, or anything under tests/
    OTHER = "other"  # docs, config, data


class ChangeKind(StrEnum):
    ADDED = "added"
    MODIFIED = "modified"
    REMOVED = "removed"


@dataclass(frozen=True)
class Hunk:
    """One `git diff -U0` hunk. A length of 0 means a pure insertion or deletion."""

    base_start: int
    base_len: int
    head_start: int
    head_len: int

    @property
    def base_lines(self) -> range:
        return range(self.base_start, self.base_start + self.base_len)

    @property
    def head_lines(self) -> range:
        return range(self.head_start, self.head_start + self.head_len)


@dataclass(frozen=True)
class FileChange:
    path: str  # posix path at head (at base for deleted files)
    old_path: str | None  # set for renames
    status: str  # git status letter: A, M, D, R, C, T
    kind: FileKind  # TEST if the file is a test file on either side
    hunks: tuple[Hunk, ...]


@dataclass(frozen=True)
class FunctionChange:
    path: str  # head path; the base path for a function removed along with its file name
    qualname: str  # e.g. "total_pages", "Parser.parse", "outer.inner"
    occurrence: int  # 0 for the first definition of qualname in the file, 1 for the next, ...
    change: ChangeKind
    kind: FileKind
    base_span: tuple[int, int] | None  # first and last line, decorators included
    head_span: tuple[int, int] | None


@dataclass(frozen=True)
class DiffScope:
    base_sha: str
    head_sha: str
    files: tuple[FileChange, ...]
    functions: tuple[FunctionChange, ...]
    module_level: tuple[str, ...]  # .py files with changed code outside every function
    unparseable: tuple[str, ...]  # .py files that failed to parse on either side

    @property
    def source_files(self) -> tuple[FileChange, ...]:
        return tuple(f for f in self.files if f.kind is FileKind.SOURCE)

    @property
    def test_files(self) -> tuple[FileChange, ...]:
        return tuple(f for f in self.files if f.kind is FileKind.TEST)

    @property
    def source_functions(self) -> tuple[FunctionChange, ...]:
        return tuple(f for f in self.functions if f.kind is FileKind.SOURCE)

    @property
    def test_functions(self) -> tuple[FunctionChange, ...]:
        return tuple(f for f in self.functions if f.kind is FileKind.TEST)


def classify(path: str) -> FileKind:
    """Test vs source split from SPEC 2.2."""
    p = PurePosixPath(path)
    if "tests" in p.parts[:-1]:
        return FileKind.TEST
    if p.suffix != ".py":
        return FileKind.OTHER
    if p.name.startswith("test_") or p.name.endswith("_test.py") or p.name == "conftest.py":
        return FileKind.TEST
    return FileKind.SOURCE


def classify_change(path: str, old_path: str | None) -> FileKind:
    """A test file on either side counts as a test change, so moving a test out of the test
    layout (e.g. tests/test_x.py -> disabled/test_x.txt) can't hide it."""
    kinds = {classify(path)} | ({classify(old_path)} if old_path else set())
    for kind in (FileKind.TEST, FileKind.SOURCE):
        if kind in kinds:
            return kind
    return FileKind.OTHER


def parse_name_status(raw: str) -> list[tuple[str, str | None, str]]:
    """Parse `git diff -z --name-status` into (status, old_path, path) tuples."""
    fields = raw.split("\0")
    entries: list[tuple[str, str | None, str]] = []
    i = 0
    while i < len(fields) and fields[i]:
        status = fields[i][0]
        if status in "RC":
            entries.append((status, fields[i + 1], fields[i + 2]))
            i += 3
        else:
            entries.append((status, None, fields[i + 1]))
            i += 2
    return entries


def parse_hunks(diff: str) -> tuple[Hunk, ...]:
    hunks = []
    for m in _HUNK.finditer(diff):
        base_len = 1 if m.group(2) is None else int(m.group(2))
        head_len = 1 if m.group(4) is None else int(m.group(4))
        hunks.append(Hunk(int(m.group(1)), base_len, int(m.group(3)), head_len))
    return tuple(hunks)


def function_spans(source: bytes) -> dict[Key, tuple[int, int]]:
    """(qualname, occurrence) -> (first line, last line) for every function and method.

    Every definition counts, so a property setter, or a function defined in both branches of
    an `if`, is tracked apart from the first definition of the same name. Bytes go straight
    to `ast`, which handles a UTF-8 BOM and `# coding:` lines.
    Raises SyntaxError or ValueError if the source does not parse, or has bare-CR line
    endings (git and ast would count its lines differently).
    """
    if _BARE_CR.search(source):
        raise ValueError("bare CR line endings")
    spans: dict[Key, tuple[int, int]] = {}
    seen: dict[str, int] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                name = f"{prefix}{child.name}"
                if not isinstance(child, ast.ClassDef):
                    first = min([child.lineno, *(d.lineno for d in child.decorator_list)])
                    occurrence = seen.get(name, 0)
                    seen[name] = occurrence + 1
                    spans[(name, occurrence)] = (first, child.end_lineno or child.lineno)
                visit(child, f"{name}.")
            else:
                visit(child, prefix)

    visit(ast.parse(source), "")
    return spans


def innermost(spans: dict[Key, tuple[int, int]], line: int) -> Key | None:
    """The smallest function span containing line, or None at module level."""
    best: tuple[int, Key] | None = None
    for key, (first, last) in spans.items():
        if first <= line <= last and (best is None or last - first < best[0]):
            best = (last - first, key)
    return None if best is None else best[1]


def is_code(text: bytes) -> bool:
    """False for blank and comment-only lines, which change no behaviour at module level."""
    stripped = text.strip()
    return bool(stripped) and not stripped.startswith(b"#")


def _changed_in(
    source: bytes, spans: dict[Key, tuple[int, int]], lines: list[int]
) -> tuple[set[Key], bool]:
    """Functions touched by `lines`, and whether any changed code line is outside them all."""
    text = source.split(b"\n")  # git and ast both count lines by \n only
    keys: set[Key] = set()
    module_level = False
    for line in lines:
        key = innermost(spans, line)
        if key is not None:
            keys.add(key)
        elif line <= len(text) and is_code(text[line - 1]):
            module_level = True
    return keys, module_level


def _side(repo: Path, sha: str, path: str | None) -> bytes:
    """A file's bytes at sha, or b"" if it doesn't exist there or isn't Python."""
    if path is None or not path.endswith(".py"):
        return b""
    return git_bytes(repo, "show", f"{sha}:{path}")


def _all_lines(source: bytes) -> list[int]:
    return list(range(1, source.count(b"\n") + 2))


def _function_changes(
    repo: Path, base_sha: str, head_sha: str, change: FileChange
) -> tuple[list[FunctionChange], bool]:
    """Changed functions in a file that is Python on at least one side, and whether it has
    module-level changes."""
    base_path = None if change.status == "A" else change.old_path or change.path
    head_path = None if change.status == "D" else change.path
    base_src = _side(repo, base_sha, base_path)
    head_src = _side(repo, head_sha, head_path)
    base_spans = function_spans(base_src)
    head_spans = function_spans(head_src)

    base_lines = [n for h in change.hunks for n in h.base_lines]
    head_lines = [n for h in change.hunks for n in h.head_lines]
    # Python on one side only (e.g. renamed to .txt): all of the Python side changed.
    if base_src and not head_src:
        base_lines = _all_lines(base_src)
    if head_src and not base_src:
        head_lines = _all_lines(head_src)
    base_touched, base_module = _changed_in(base_src, base_spans, base_lines)
    head_touched, head_module = _changed_in(head_src, head_spans, head_lines)

    result = []
    for key in sorted(base_touched | head_touched):
        path = change.path
        if key in base_spans and key in head_spans:
            kind = ChangeKind.MODIFIED
        elif key in head_spans:
            kind = ChangeKind.ADDED
        else:
            kind = ChangeKind.REMOVED
            path = base_path or change.path
        name, occurrence = key
        result.append(
            FunctionChange(
                path,
                name,
                occurrence,
                kind,
                change.kind,
                base_spans.get(key),
                head_spans.get(key),
            )
        )
    return result, base_module or head_module


def compute_scope(repo: Path, base_sha: str, head_sha: str) -> DiffScope:
    """Everything that changed between two commit ids (resolve refs with workspace first)."""
    raw = git(repo, "diff", *_DIFF_FLAGS, "-z", "--name-status", base_sha, head_sha)
    files = []
    for status, old_path, path in parse_name_status(raw):
        paths = [p for p in (old_path, path) if p is not None]
        diff = git(repo, "diff", *_DIFF_FLAGS, "-U0", base_sha, head_sha, "--", *paths)
        kind = classify_change(path, old_path)
        files.append(FileChange(path, old_path, status, kind, parse_hunks(diff)))

    functions: list[FunctionChange] = []
    module_level: list[str] = []
    unparseable: list[str] = []
    for change in files:
        if not any(p is not None and p.endswith(".py") for p in (change.path, change.old_path)):
            continue
        try:
            found, at_module = _function_changes(repo, base_sha, head_sha, change)
        except (SyntaxError, ValueError):
            unparseable.append(change.path)
            continue
        functions.extend(found)
        if at_module:
            module_level.append(change.path)
    return DiffScope(
        base_sha, head_sha, tuple(files), tuple(functions), tuple(module_level), tuple(unparseable)
    )


def unified_diff(
    repo: Path, base_sha: str, head_sha: str, paths: Sequence[str], context: int = 3
) -> str:
    """`git diff` text for some paths, with the same fixed flags as the scope (repo-relative)."""
    if not paths:
        return ""
    return git(repo, "diff", *_DIFF_FLAGS, f"-U{context}", base_sha, head_sha, "--", *paths)

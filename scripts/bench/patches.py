"""The patches per task (M10 plan P4): the gold fix, and the gold fix without one source hunk.

A git diff is parsed into file sections and hunks, strictly (it is untrusted data): every hunk's
body must hold exactly the lines its header counts, and anything unexpected rejects the whole
patch. Rendering a parsed patch gives back the same text, byte for byte.

A variant drops one hunk of a plainly modified source file and moves the new-side line numbers of
that file's later hunks by what the dropped hunk added, so the variant is the exact diff `git diff`
would print for its result. Every other hunk (non-`.py`, tests, new, deleted, renamed or binary
files) is always kept.

Which variant a task keeps is decided from our own hidden-test runs (`label`, `keep`), never by a
model: a variant the hidden tests can't tell from gold is never used as an incorrect fix.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from bench.choose import header_paths
from tracefix.diffscope import FileKind, classify_change

MAX_TRIED = 4  # hunks tried per task, in patch order
_DIFF = "diff --git "
_HUNK_HEADER = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@([^\n]*)\n")
# Header lines that make a file section more than a plain edit of an existing file.
_NOT_PLAIN = (
    "new file mode ", "deleted file mode ", "old mode ", "new mode ", "rename from ",
    "copy from ", "Binary files ", "GIT binary patch",
)  # fmt: skip


class PatchError(Exception):
    """The patch can't be read; `str(exc)` is a reason in our own words."""


@dataclass(frozen=True)
class PatchHunk:
    old_start: int
    old_len: int
    new_start: int
    new_len: int
    tail: str  # what follows the closing "@@" (git's function context), kept as it was
    body: tuple[str, ...]  # the lines after the header, each with its "\n"
    written: tuple[bool, bool] = (True, True)  # the header spelled out each count (git omits 1)

    def text(self) -> str:
        old = _span(self.old_start, self.old_len, self.written[0])
        new = _span(self.new_start, self.new_len, self.written[1])
        return f"@@ -{old} +{new} @@{self.tail}\n" + "".join(self.body)


@dataclass(frozen=True)
class FileDiff:
    header: tuple[str, ...]  # "diff --git ..." up to the first hunk (the whole section if binary)
    old_path: str
    new_path: str
    hunks: tuple[PatchHunk, ...]

    @property
    def kind(self) -> FileKind:
        return classify_change(
            self.new_path, None if self.old_path == self.new_path else self.old_path
        )

    @property
    def removable(self) -> bool:
        """A hunk of this file may be dropped: a plain edit of an existing source file."""
        plain = not any(line.startswith(_NOT_PLAIN) for line in self.header)
        return plain and self.old_path == self.new_path and self.kind is FileKind.SOURCE

    def text(self) -> str:
        return "".join(self.header) + "".join(h.text() for h in self.hunks)


@dataclass(frozen=True)
class Variant:
    index: int  # the dropped hunk's place among the patch's removable hunks, in patch order
    path: str
    old_start: int  # where the dropped hunk sits in the base file
    old_len: int
    patch: str


def _span(start: int, length: int, written: bool) -> str:
    return f"{start},{length}" if written else str(start)


def _lines(patch: str) -> list[str]:
    """Lines split on "\\n" only (a "\\r" or form feed is content), each with its "\\n"."""
    if not patch.endswith("\n"):
        raise PatchError("the patch doesn't end with a newline")
    return [line + "\n" for line in patch[:-1].split("\n")]


def _hunk(lines: list[str], i: int) -> tuple[PatchHunk, int]:
    """The hunk whose header is lines[i], and the index after it."""
    match = _HUNK_HEADER.fullmatch(lines[i])
    if match is None:
        raise PatchError(f"line {i + 1}: unreadable hunk header")
    old_start, new_start = int(match[1]), int(match[3])
    old_len = 1 if match[2] is None else int(match[2])
    new_len = 1 if match[4] is None else int(match[4])
    old_left, new_left = old_len, new_len
    j = i + 1
    while old_left > 0 or new_left > 0:
        if j >= len(lines):
            raise PatchError(f"line {i + 1}: the hunk is shorter than its header says")
        mark = lines[j][0]
        if mark in " -":
            old_left -= 1
        if mark in " +":
            new_left -= 1
        if mark not in " -+\\" or (mark == "\\" and j == i + 1) or old_left < 0 or new_left < 0:
            raise PatchError(f"line {j + 1}: doesn't fit the hunk")
        j += 1
    if j < len(lines) and lines[j].startswith("\\"):  # "\ No newline at end of file"
        j += 1
    body, written = tuple(lines[i + 1 : j]), (match[2] is not None, match[4] is not None)
    hunk = PatchHunk(old_start, old_len, new_start, new_len, match[5], body, written)
    return hunk, j


def parse(patch: str) -> tuple[FileDiff, ...]:
    """Every file section of a git diff, or PatchError."""
    lines = _lines(patch)
    if not lines[0].startswith(_DIFF):
        raise PatchError("the patch doesn't start with a diff header")
    files: list[FileDiff] = []
    i = 0
    while i < len(lines):
        start = i
        paths = header_paths(lines[i][len(_DIFF) : -1])
        if paths is None:
            raise PatchError(f"line {i + 1}: unreadable file paths")
        i += 1
        while i < len(lines) and not lines[i].startswith(("@@ ", _DIFF)):
            i += 1
        header = tuple(lines[start:i])
        hunks: list[PatchHunk] = []
        while i < len(lines) and lines[i].startswith("@@ "):
            hunk, i = _hunk(lines, i)
            hunks.append(hunk)
        if i < len(lines) and not lines[i].startswith(_DIFF):
            raise PatchError(f"line {i + 1}: neither a hunk nor a file header")
        files.append(FileDiff(header, paths[0], paths[1], tuple(hunks)))
    return tuple(files)


def files(patch: str) -> frozenset[str]:
    """Every path the patch touches (old and new side), or PatchError."""
    return frozenset(path for f in parse(patch) for path in (f.old_path, f.new_path))


def render(files: Iterable[FileDiff]) -> str:
    return "".join(f.text() for f in files)


def without(files: Sequence[FileDiff], file_index: int, hunk_index: int) -> tuple[FileDiff, ...]:
    """The patch without one hunk; the file's later hunks move by what that hunk added. A file
    left with no hunks is dropped (only plain edits are cut, so its header says nothing else)."""
    old = files[file_index]
    gone = old.hunks[hunk_index]
    delta = gone.old_len - gone.new_len
    later = tuple(replace(h, new_start=h.new_start + delta) for h in old.hunks[hunk_index + 1 :])
    hunks = old.hunks[:hunk_index] + later
    kept = (replace(old, hunks=hunks),) if hunks else ()
    return (*files[:file_index], *kept, *files[file_index + 1 :])


def source_hunks(files: Iterable[FileDiff]) -> int:
    return sum(len(f.hunks) for f in files if f.kind is FileKind.SOURCE)


def variants(patch: str, limit: int = MAX_TRIED) -> list[Variant]:
    """The gold patch without one source hunk, for the first `limit` removable hunks. None for a
    fix with a single source hunk: without it nothing of the fix would be left."""
    files = parse(patch)
    if source_hunks(files) < 2:
        return []
    spots = [(fi, hi) for fi, f in enumerate(files) if f.removable for hi in range(len(f.hunks))]
    found = []
    for index, (fi, hi) in enumerate(spots[:limit]):
        gone = files[fi].hunks[hi]
        text = render(without(files, fi, hi))
        found.append(Variant(index, files[fi].new_path, gone.old_start, gone.old_len, text))
    return found


# --- labels, from our own hidden-test runs ----------------------------------------------------


class Label(StrEnum):
    """What the hidden tests say about a variant. The order of `label`'s rules is the order here."""

    DOES_NOT_APPLY = "does_not_apply"
    UNSETTLED = "unsettled"  # flaky, timed out or tampering detected: proves nothing either way
    BROKEN = "broken"  # pytest couldn't collect or run the hidden tests
    NO_EFFECT = "no_effect"  # every FAIL_TO_PASS test still fails
    HIDDEN_TESTS_PASS = "hidden_tests_pass"  # can't be told from gold: never used as incorrect
    PARTIAL = "partial"  # some FAIL_TO_PASS test passes, some hidden test fails


USABLE = frozenset({Label.PARTIAL, Label.NO_EFFECT, Label.BROKEN})  # incorrect by our runs


@dataclass(frozen=True)
class HiddenRun:
    """The hidden tests on one variant, as step 3 runs them."""

    applies: bool  # `git apply --check` accepted the variant
    error: bool  # the run's outcome was an error (collection, usage or internal)
    passed: frozenset[str]  # hidden test ids (SWE-rebench's form) that ran and passed
    settled: bool = True  # ended the same way on every attempt, in time, with no tampering


@dataclass(frozen=True)
class Tried:
    variant: Variant
    label: Label
    failing: int  # hidden tests that didn't pass (missing from the run counts as not passing)


def label(run: HiddenRun, fail_to_pass: Sequence[str], pass_to_pass: Sequence[str]) -> Label:
    if not fail_to_pass:
        raise ValueError("a task without FAIL_TO_PASS tests can't label a variant")
    if not run.applies:
        return Label.DOES_NOT_APPLY
    if not run.settled:
        return Label.UNSETTLED
    if run.error:
        return Label.BROKEN
    if not any(t in run.passed for t in fail_to_pass):
        return Label.NO_EFFECT
    if failing(run, (*fail_to_pass, *pass_to_pass)) == 0:
        return Label.HIDDEN_TESTS_PASS
    return Label.PARTIAL


def failing(run: HiddenRun, hidden: Iterable[str]) -> int:
    return sum(t not in run.passed for t in hidden)


def tried(
    variant: Variant, run: HiddenRun, fail_to_pass: Sequence[str], pass_to_pass: Sequence[str]
) -> Tried:
    count = failing(run, (*fail_to_pass, *pass_to_pass))
    return Tried(variant, label(run, fail_to_pass, pass_to_pass), count)


def keep(candidates: Iterable[Tried]) -> Tried | None:
    """The one variant a task keeps: `partial` first, then the fewest failing hidden tests, then
    hunk order. None when no variant is incorrect by our runs."""
    usable = [t for t in candidates if t.label in USABLE]
    return min(
        usable,
        key=lambda t: (t.label is not Label.PARTIAL, t.failing, t.variant.index),
        default=None,
    )

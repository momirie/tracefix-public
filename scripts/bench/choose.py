"""Which tasks a slice uses (M10 plan P3): pure rules, every exclusion with its reason.

The metadata rules run first (`check`). Slice 2's agent rule runs in `sample`, only on tasks
that could still be chosen, so a task it refuses doesn't use up its repo's places. The checks
that need the task's image come later (prepare). The sample is ordered by sha256(slice name,
instance id), with at most `PER_REPO` tasks per repo, so it is fixed and not hand-picked, and a
shorter sample is always a prefix of a longer one (the smoke run's candidates are the first of
slice 1's). The dev/held-out split depends on the instance id alone, so a task keeps its side in
every slice.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal

from bench.data import AgentRun, Task
from tracefix.diffscope import FileKind, classify_change

PER_REPO = 2
# Sources a git-exported copy can't build: a fix in any of them is out of scope.
COMPILED = frozenset(
    {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".pyx", ".pxd", ".rs", ".f", ".f90", ".cu"}
)
# `pytest` run as a command: bare, from a path (.venv/bin/pytest), or as `-m pytest`.
_PYTEST = re.compile(r"(?:^|[\s/])pytest(?:\s|$)")
_DIFF_HEADER = re.compile(r"^diff --git (.*)$", re.MULTILINE)
_HEADER_PATHS = re.compile(r"^a/(\S+) b/(\S+)$")

Split = Literal["dev", "held_out"]


class Reason(StrEnum):
    """Why a task left the funnel. The order of `check`'s rules is the order here."""

    INVALID = "invalid_row"  # data.parse_row rejected it (the detail is kept beside it)
    PYTHON = "python_below_3_11"  # slice 1
    PYTHON_RANGE = "python_outside_3_9_to_3_13"  # slice 2
    NO_PYTEST = "no_pytest_command"
    NO_IMAGE = "no_image"
    NO_FAIL_TO_PASS = "no_fail_to_pass_tests"
    UNREADABLE_PATCH = "unreadable_patch"
    COMPILED = "compiled_sources"
    NO_SOURCE_CHANGE = "no_source_change"
    NO_AGENT_RUNS = "no_agent_runs"  # slice 2: the agent dataset has no readable run of it
    NO_AGENT_PATCH = "no_usable_agent_patch"  # slice 2: none of its runs passes `usable`
    REPO_CAP = "repo_cap"  # the repo already has PER_REPO tasks earlier in the order
    OVER_LIMIT = "over_limit"  # eligible, but past the slice's size


@dataclass(frozen=True)
class Rules:
    """A slice's metadata rules: the projects' Python versions, and whether agent runs count."""

    min_python: tuple[int, int]
    max_python: tuple[int, int] | None
    python_reason: Reason
    agents: bool


SLICES = {
    "slice1": Rules((3, 11), None, Reason.PYTHON, agents=False),
    "slice2": Rules((3, 9), (3, 13), Reason.PYTHON_RANGE, agents=True),
}


@dataclass(frozen=True)
class Excluded:
    row: int
    instance_id: str | None  # None when the row's id itself was invalid
    reason: Reason
    detail: str = ""  # our own words only (data.reason), never the row's text


def patch_paths(patch: str) -> list[tuple[str, str]] | None:
    """(old, new) path of every file in a git diff; None when a header can't be read."""
    pairs = []
    for header in _DIFF_HEADER.findall(patch):
        paths = header_paths(header)
        if paths is None:
            return None
        pairs.append(paths)
    return pairs or None


def header_paths(header: str) -> tuple[str, str] | None:
    """(old, new) path from what follows "diff --git "; None when it can't be read."""
    match = _HEADER_PATHS.match(header)
    if match is not None:
        return match[1], match[2]
    same = _same_path(header)
    if same is not None:
        return same, same
    return None  # quoted paths, or a rename with spaces: not worth guessing


def _same_path(header: str) -> str | None:
    """P from "a/P b/P", the one readable header shape when P has spaces."""
    if not header.startswith("a/") or (len(header) - 5) % 2:
        return None
    end = (len(header) - 5) // 2 + 2  # the end of "a/" + P
    path = header[2:end]
    return path if header[end:] == f" b/{path}" else None


def added_files(patch: str) -> set[str]:
    """The paths the patch creates ("new file mode" in a file's header)."""
    added: set[str] = set()
    current: str | None = None
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            paths = header_paths(line.removeprefix("diff --git "))
            current = paths[1] if paths else None
        elif line.startswith("new file mode ") and current is not None:
            added.add(current)  # never a hunk line: those start with " ", "+", "-", "@" or "\"
    return added


def check(task: Task, rules: Rules = SLICES["slice1"]) -> Reason | None:
    """The first metadata rule the task fails, or None when it may go on to prepare."""
    version = task.python_version
    if version < rules.min_python or (rules.max_python and version > rules.max_python):
        return rules.python_reason
    if not _PYTEST.search(task.test_cmd):
        return Reason.NO_PYTEST
    if not task.image:
        return Reason.NO_IMAGE
    if not task.fail_to_pass:
        return Reason.NO_FAIL_TO_PASS
    return patch_problem(task.patch)


def patch_problem(patch: str, *, existing_only: bool = False) -> Reason | None:
    """Why a fix can't be verified from its diff, or None. With `existing_only`, a source file
    the patch creates doesn't count as a source change."""
    paths = patch_paths(patch)
    if paths is None:
        return Reason.UNREADABLE_PATCH
    if any(PurePosixPath(p).suffix.lower() in COMPILED for pair in paths for p in pair):
        return Reason.COMPILED
    added = added_files(patch) if existing_only else set()
    kinds = {classify_change(new, old if old != new else None)
             for old, new in paths if new not in added}  # fmt: skip
    if FileKind.SOURCE not in kinds:
        return Reason.NO_SOURCE_CHANGE
    return None


def usable(run: AgentRun) -> bool:
    """An agent run that may stand for a fix: it finished, and its patch changes a non-test
    .py file that exists at the base commit. A patch that only adds files (OpenHands often
    leaves a reproduce_issue.py behind) is no attempt at the fix."""
    return run.submitted and patch_problem(run.patch, existing_only=True) is None


def pick_agents(slice_name: str, runs: Iterable[AgentRun]) -> tuple[AgentRun, ...]:
    """The task's first usable run the hidden tests failed and the first they passed, in a
    fixed hash order (not the dataset's)."""
    ordered = sorted(
        (r for r in runs if usable(r)),
        key=lambda r: rank_key(slice_name, f"{r.instance_id}#{r.source_row}"),
    )
    first: dict[bool, AgentRun] = {}
    for run in ordered:
        first.setdefault(run.resolved, run)
    return tuple(first[resolved] for resolved in (False, True) if resolved in first)


def rank_key(slice_name: str, instance_id: str) -> str:
    return hashlib.sha256(f"{slice_name}\n{instance_id}".encode()).hexdigest()


def sample(
    tasks: Iterable[Task],
    slice_name: str,
    limit: int,
    per_repo: int = PER_REPO,
    admit: Callable[[Task], Reason | None] | None = None,
) -> tuple[list[Task], list[Excluded]]:
    """The slice's tasks in rank order, and the eligible ones left out (with why). `admit`, a
    rule too costly for every row, runs only on a task that would otherwise be chosen; a task
    it refuses takes no place in its repo's cap."""
    ordered = sorted(tasks, key=lambda t: rank_key(slice_name, t.instance_id))
    chosen: list[Task] = []
    left: list[Excluded] = []
    per: Counter[str] = Counter()
    for task in ordered:
        repo = task.repo.lower()
        if per[repo] >= per_repo:
            left.append(Excluded(task.source_row, task.instance_id, Reason.REPO_CAP))
        elif len(chosen) >= limit:
            left.append(Excluded(task.source_row, task.instance_id, Reason.OVER_LIMIT))
        elif admit is not None and (why := admit(task)) is not None:
            left.append(Excluded(task.source_row, task.instance_id, why))
        else:
            per[repo] += 1
            chosen.append(task)
    return chosen, left


def split(instance_id: str) -> Split:
    """About a third of tasks are held out; M11 tunes on dev only."""
    held = int(hashlib.sha256(instance_id.encode()).hexdigest()[:8], 16) % 3 == 0
    return "held_out" if held else "dev"


def funnel(considered: int, excluded: Sequence[Excluded], chosen: int) -> dict[str, object]:
    """Counts per reason, in the rules' order, for the funnel file and the report."""
    counts = Counter(e.reason for e in excluded)
    return {
        "considered": considered,
        "excluded": {r.value: counts[r] for r in Reason if counts[r]},
        "chosen": chosen,
    }

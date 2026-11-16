"""Agent patches in: OpenHands runs on SWE-rebench tasks (M10 part 2 plan C1).

`nebius/SWE-rebench-openhands-trajectories` (CC BY 4.0) has 67,074 runs of OpenHands with
Qwen3-Coder, each with the agent's final diff and the hidden tests' verdict. Its rows hold whole
conversations, so only four fields are kept. The datasets-server's per-task search kept breaking
(21 Oct 2026: "index corrupted", then "loading" for 30+ minutes at a time), so the dataset's one
parquet file is read once by `scripts/extract_agents.py` (pyarrow, run with `uv run --with`; not
a Tracefix dependency). It writes the runs JSONL this module reads, and the pin: the revision,
the parquet file's sha256 (the Hub's LFS id) and the JSONL's sha256.

Every field is untrusted text (CLAUDE.md rule 7). A run that fails strict parsing is dropped and
counted, never half-used. The agent's `exit_status` is either "submit" or an error message: only
"is it submit" is kept.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from bench import data, patches

NAME = "swe-rebench-openhands"  # the key in sources.json and the cache file's prefix
DATASET = "nebius/SWE-rebench-openhands-trajectories"
FILE = "trajectories.parquet"
COLUMNS = ("instance_id", "model_patch", "exit_status", "resolved")
MAX_ROWS = 100_000


class Pin(BaseModel):
    """The trajectories' entry in sources.json, written by scripts/extract_agents.py."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    dataset: str
    revision: data.Sha
    file: str
    file_sha256: data.Digest
    rows: Annotated[int, Field(ge=0, le=MAX_ROWS)]
    unreadable_rows: Annotated[int, Field(ge=0)]  # rows without a valid instance id
    runs_sha256: data.Digest
    license: str
    url: str


class TaskRuns(BaseModel):
    """One line of the runs file: a task's readable runs, and how many of its runs were dropped."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    instance_id: data.InstanceId
    runs: tuple[data.AgentRun, ...]
    dropped: Annotated[int, Field(ge=0)]


def parse_run(instance_id: str, row_idx: int, row: dict[str, Any]) -> data.AgentRun:
    """One run as an AgentRun, or InvalidRow with a reason in our own words."""
    resolved, status = row.get("resolved"), row.get("exit_status")
    if row.get("instance_id") != instance_id:
        raise data.InvalidRow("invalid instance_id (another task's run)")
    if type(resolved) is not int or resolved not in (0, 1):
        raise data.InvalidRow("invalid resolved (not 0 or 1)")
    if not isinstance(status, str):
        raise data.InvalidRow("invalid exit_status (not text)")
    fields = {
        "instance_id": instance_id,
        "source_row": row_idx,
        "patch": row.get("model_patch") or "",
        "submitted": status == "submit",
        "resolved": resolved == 1,
    }
    try:
        return data.AgentRun.model_validate(fields)
    except ValidationError as exc:
        raise data.InvalidRow(data.reason(exc)) from exc


def group(rows: Iterable[tuple[int, dict[str, Any]]]) -> tuple[list[TaskRuns], int]:
    """The runs of every task, in instance id order, and the number of rows whose instance id
    isn't one (those can't be put with any task)."""
    by_task: defaultdict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    unreadable = 0
    for row_idx, row in rows:
        instance_id = row.get("instance_id")
        if isinstance(instance_id, str) and _valid_id(instance_id):
            by_task[instance_id].append((row_idx, row))
        else:
            unreadable += 1
    tasks = []
    for instance_id in sorted(by_task):
        runs: list[data.AgentRun] = []
        dropped = 0
        for row_idx, row in sorted(by_task[instance_id], key=lambda pair: pair[0]):
            try:
                runs.append(parse_run(instance_id, row_idx, row))
            except data.InvalidRow:
                dropped += 1
        tasks.append(TaskRuns(instance_id=instance_id, runs=tuple(runs), dropped=dropped))
    return tasks, unreadable


def _valid_id(instance_id: str) -> bool:
    try:
        TaskRuns(instance_id=instance_id, runs=(), dropped=0)
    except ValidationError:
        return False
    return True


def runs_path(cache_dir: Path, revision: str) -> Path:
    return cache_dir / f"{NAME}-{revision}.jsonl"


def encode(tasks: Iterable[TaskRuns]) -> bytes:
    """The runs file: one task per line, JSON with every non-ASCII character escaped."""
    lines = (json.dumps(t.model_dump(mode="json"), ensure_ascii=True) for t in tasks)
    return "".join(f"{line}\n" for line in lines).encode("ascii")


def read_pin(path: Path) -> Pin:
    entry = data.read_pins(path).get(NAME)
    if entry is None:
        raise data.DataError(
            f"{path} has no pin for {DATASET}: run scripts/extract_agents.py first"
        )
    return Pin.model_validate_json(json.dumps(entry))


def write_pin(path: Path, value: Pin) -> None:
    data.write_pins(path, data.read_pins(path) | {NAME: value.model_dump()})


Runs = Callable[[str], TaskRuns]  # instance id -> its runs


def load(value: Pin, cache_dir: Path) -> Runs:
    """The pinned runs file, checked against its digest; a task it lacks has no runs."""
    path = runs_path(cache_dir, value.revision)
    if not path.is_file():
        raise data.DataError(f"{path} is missing: run scripts/extract_agents.py")
    raw = path.read_bytes()
    if data.digest(raw) != value.runs_sha256:
        raise data.DataError(f"{path.name} doesn't match its pin: run scripts/extract_agents.py")
    found = {}
    for line in raw.decode("ascii").splitlines():
        task = TaskRuns.model_validate_json(line)
        found[task.instance_id] = task

    def runs(instance_id: str) -> TaskRuns:
        return found.get(instance_id) or TaskRuns(instance_id=instance_id, runs=(), dropped=0)

    return runs


# --- the patch as the agent made it -------------------------------------------------------------

ISSUE_FILE = "issue.md"  # where OpenHands put the issue for the agent (some images have it too)


def agent_patch(run: data.AgentRun, issue: str) -> str:
    """The run's patch as prepare and run apply it (C3). The dataset strips each diff's last
    newline (all 180 of slice 2's runs), so git refuses most of them: it is put back. The issue
    file OpenHands wrote into the repo is dropped: the agent didn't write it, and where the image
    already has it the patch can't apply. Only the exact issue text is dropped (`issue_file`);
    a patch that doesn't parse is left as it is, and then won't apply."""
    patch = run.patch
    if patch and not patch.endswith("\n"):
        patch += "\n"
    if f"diff --git a/{ISSUE_FILE} b/{ISSUE_FILE}\n" not in patch:
        return patch
    try:
        files = patches.parse(patch)
    except patches.PatchError:
        return patch
    kept = [f for f in files if not issue_file(f, issue)]
    return patches.render(kept) if len(kept) < len(files) else patch


def issue_file(diff: patches.FileDiff, issue: str) -> bool:
    """A new top-level issue.md holding exactly what OpenHands writes: "### " and the issue,
    with its CRLFs as LFs."""
    new = diff.old_path == diff.new_path == ISSUE_FILE and "new file mode 100644\n" in diff.header
    body = [line for hunk in diff.hunks for line in hunk.body]
    if not new or any(not line.startswith(("+", "\\")) for line in body):
        return False
    text = "".join(line[1:] for line in body if line.startswith("+"))
    return text.rstrip("\n") == f"### {issue}".replace("\r\n", "\n").rstrip("\n")

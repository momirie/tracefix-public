"""A fake box and synthetic receipts for the benchmark's run and report tests (no Docker, no
model, no runs). The fake box answers inside.py's commands with fixed results, so the host's
real code (Session, prepare.verify, prepare.replay, bench.run) is what the tests exercise."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Mapping, Sequence
from functools import cache
from pathlib import Path
from typing import Any

from bench.box import BoxError, Exec, Installed
from bench.data import AgentRun, Case, Task, image_for
from bench.patches import Label
from bench.prepare import Prepared, TriedAgent
from synthetic import attack, behaviour, finding, guard, l4_run, target

from tracefix.attack import AttackStatus
from tracefix.guard import GuardStatus
from tracefix.receipt import Receipt, build
from tracefix.workspace import Workspace

# Two hunks in one source file: variants 0 and 1 each drop one.
GOLD = (
    "diff --git a/pkg/calc.py b/pkg/calc.py\n"
    "--- a/pkg/calc.py\n"
    "+++ b/pkg/calc.py\n"
    "@@ -1,2 +1,2 @@\n"
    " def double(x):\n"
    "-    return x + x + 1\n"
    "+    return x + x\n"
    "@@ -16,2 +16,2 @@\n"
    " def half(x):\n"
    "-    return x // 2 + 1\n"
    "+    return x // 2\n"
)
COMMITS = {"base": "a" * 40, "gold": "b" * 40, "v0": "c" * 40}
F2P = "tests/test_calc.py::test_a"
TIMEOUT = object()  # an answer: the step ran past its timeout
GONE = object()  # an answer: the box was removed under the step (`docker exec` exits 137)


def task(instance_id: str = "tracefix__synthetic-1") -> Task:
    return Task(
        instance_id=instance_id, repo="tracefix/synthetic", base_commit="d" * 40, patch=GOLD,
        test_patch="", issue="double and half are off by one", fail_to_pass=(F2P,),
        pass_to_pass=(), image=image_for(instance_id), python="3.11", test_cmd="pytest",
        created_at="2026-01-01 00:00:00", source_row=0, source_revision="a" * 40,
    )  # fmt: skip


def case(instance_id: str = "tracefix__synthetic-1", rank: int = 0) -> Case:
    return Case(slice="slice1", rank=rank, split="dev", task=task(instance_id))


def ready(
    instance_id: str = "tracefix__synthetic-1", kept: int | None = 0,
    agents: tuple[TriedAgent, ...] = (),
) -> Prepared:  # fmt: skip
    commits = dict(COMMITS) if kept is not None else {k: COMMITS[k] for k in ("base", "gold")}
    commits |= {a.kind: AGENT_COMMITS[a.kind] for a in agents if a.kept}
    return Prepared(instance_id=instance_id, excluded=None, suite_timeout=120, kept=kept,
                    agents=agents, commits=commits, isolation="strict")  # fmt: skip


# Slice 2: an agent's patch the hidden tests fail (row 7) and one they pass (row 8).
AGENT_COMMITS = {"agent_wrong": "e" * 40, "agent_ok": "f" * 40}
AGENT_PATCH = GOLD.replace("x + x\n", "x + x  # agent\n")


def agent_run(resolved: bool, instance_id: str = "tracefix__synthetic-1") -> AgentRun:
    return AgentRun(instance_id=instance_id, source_row=8 if resolved else 7,
                    patch=AGENT_PATCH, submitted=True, resolved=resolved)  # fmt: skip


def tried(kind: str, kept: bool = True) -> TriedAgent:
    label = Label.PARTIAL if kind == "agent_wrong" else Label.HIDDEN_TESTS_PASS
    return TriedAgent.model_validate({"kind": kind, "source_row": 7 if kind == "agent_wrong" else 8,
                                      "label": label, "failing": 1, "kept": kept})  # fmt: skip


def agent_case(instance_id: str = "tracefix__synthetic-1", rank: int = 0) -> Case:
    runs = (agent_run(False, instance_id), agent_run(True, instance_id))
    return Case(slice="slice2", rank=rank, split="dev", task=task(instance_id), agents=runs)


# --- receipts -----------------------------------------------------------------------------------


def _runs() -> dict[str, Any]:
    found = attack(status=AttackStatus.FOUND, findings=(finding(), finding(2)))
    return {
        "L4": l4_run(),
        "L3": l4_run(break_my_fix=attack(targets=(target(finished=False),))),
        "L2": l4_run(behaviour_diff=behaviour(l3=False)),
        "L1": l4_run(guard=guard(GuardStatus.NOT_GUARDED)),
        "COUNTEREXAMPLE": l4_run(break_my_fix=found),
    }


@cache
def _built(level: str) -> Receipt:
    folder = Path(__file__).parent  # only named, to be masked; nothing is written there
    return build(_runs()[level], Workspace(folder, "main", "fix"))


CREATED_AT = "2026-01-01T00:00:00+00:00"  # every fake receipt's (a label names its receipt by it)


def receipt(level: str, cost: float | None = 0.5) -> Receipt:
    """A real receipt (built from synthetic stage results) at `level`, with this cost estimate.
    A COUNTEREXAMPLE receipt has findings 1 and 2."""
    built = _built(level)
    estimate = built.llm.cost_estimate.model_copy(update={"usd": cost})
    llm = built.llm.model_copy(update={"cost_estimate": estimate})
    return built.model_copy(update={"llm": llm, "created_at": CREATED_AT})


# --- the fake box -------------------------------------------------------------------------------

Answer = Callable[[str, dict[str, Any], "FakeBox"], object]


class FakeBox:
    """A Box whose inside.py answers come from `answer(command, request, box)`."""

    repo = "/testbed"
    python = "python"
    project_python: str | None = None

    def __init__(self, home: Path, answer: Answer) -> None:
        home.mkdir(parents=True, exist_ok=True)
        self.home = str(home)
        self.answer = answer
        self.commands: list[str] = []
        self.env_names: list[tuple[str, ...]] = []
        self.closed = False

    def path(self, *parts: str) -> str:
        return str(Path(self.home, *parts))

    def run(self, argv: Sequence[str], *, timeout: float, env_names: Sequence[str] = ()) -> Exec:
        command, request, result = argv[3], Path(argv[4]), Path(argv[5])
        self.commands.append(command)
        self.env_names.append(tuple(env_names))
        reply = self.answer(command, json.loads(request.read_text(encoding="utf-8")), self)
        if reply is TIMEOUT:
            self.closed = True
            return Exec(None, "", float(timeout))
        if reply is GONE:
            return Exec(137, "", 1.0)
        result.write_text(json.dumps({"ok": True, "result": reply}), encoding="utf-8")
        return Exec(0, "", 2.0)

    def put(self, local: Path, remote: str) -> None:
        if local.is_dir():
            shutil.copytree(local, remote)
        else:
            shutil.copyfile(local, remote)

    def get(self, remote: str, local: Path) -> None:
        if local.exists() or not Path(remote).exists():
            raise BoxError("cannot copy")
        if Path(remote).is_dir():
            shutil.copytree(remote, local)
        else:
            shutil.copyfile(remote, local)

    def install(self, wheel: Path) -> Installed:
        return Installed({}, {})

    def close(self) -> None:
        self.closed = True


PROBE = {"python": "3.11.9", "level": "strict", "why": "bubblewrap works", "plugins": []}


def answers(
    receipts: Mapping[str, Receipt | str | object], *, commits: Mapping[str, str] = COMMITS,
    replay: str = "fixed",
) -> Answer:  # fmt: skip
    """inside.py as a dict: `receipts` maps a head ("tf-gold") to the receipt verify writes, to
    text written as receipt.json, or to TIMEOUT."""

    def answer(command: str, request: dict[str, Any], box: FakeBox) -> object:
        if command == "probe":
            return PROBE
        if command == "commits":
            assert request["test_patch"] is None, "a run box never gets the test patch (P5)"
            return {"commits": {k: commits.get(k) for k in ("base", *request["patches"])}}
        if command == "verify":
            written = receipts[request["head"]]
            if written is TIMEOUT:
                return TIMEOUT
            out = Path(request["out"])
            out.mkdir()
            text = written.model_dump_json() if isinstance(written, Receipt) else str(written)
            (out / "receipt.json").write_text(text, encoding="utf-8")
            return {"exit_code": 0}
        if command == "replay":
            found = [{"number": 1, "carried": False, "result": replay},
                     {"number": 2, "carried": False, "result": "still_fails"}]  # fmt: skip
            return {"status": "replayed", "isolation": "strict", "findings": found}
        raise AssertionError(command)

    return answer

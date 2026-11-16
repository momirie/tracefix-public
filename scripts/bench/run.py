"""Running prepared tasks (M10 plan P6): a pool of boxes, resuming, and the spend guard.

Each ready task runs in one box of its own: `tracefix verify` on the gold fix, on the kept
partial fix and on each kept agent patch (slice 2), each `repeats` times, and the findings of
every run but gold's replayed on gold. The box is
set up again from the image, and its commits must have the ids prepare recorded (fixed author and
date), so a run checks exactly what prepare checked.

Every run appends one line to runs.jsonl. When the pool starts again, a run already there is
skipped, except a harness error, an API error or a missing recording, which is tried again, and a
run of a partial fix prepare no longer keeps; the report reads a run's last line. An API error is
a receipt in which a model call that could change the verdict failed for a reason outside
Tracefix (the network, the API, the account): it measured the API, not the fix, so it counts
nowhere. Nor does a replay that met a model call with no recorded answer (a run never recorded
live): its model stages never ran. `reclassify` applies these rules again to lines already
written, appending a line for each run whose outcome they change (no line is edited by hand).

Live runs call the model API, and only the spend guard starts them. Before each one it adds
what has been spent (each receipt's cost estimate; a run with no known cost counts as a whole
reserve) to a reserve for every run in flight and the new one; if that could pass the ceiling,
it starts no more. Tracefix checks its token budget before each model call, so one run can't run
away; the reserve also grows to the dearest run seen. The ceiling is only as safe as the reserve:
a run dearer than it can pass it, and `run` says so when the reserve is below what Tracefix's
token budget allows a run (`worst_run_usd`). An anchored run's estimate includes the calls it
replayed for free, so what counts for it is the cost of the recordings it added (`live_usd`).

Everything a box sends back is untrusted: receipts are parsed with the strict receipt model.
"""

from __future__ import annotations

import os
import shutil
import signal
import sys
import threading
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import FrameType
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from bench import patches, prepare
from bench.agents import agent_patch
from bench.box import Box, BoxError
from bench.data import Case, Task
from bench.prepare import (
    AGENT_OK,
    AGENT_WRONG,
    GOLD,
    Mode,
    Prepared,
    Replays,
    Session,
    StepFailed,
    StepTimeout,
    agent_patches,
)
from tracefix import llm
from tracefix.receipt import ModelProblem, Receipt
from tracefix.record import BLIND

Kind = Literal["gold", "partial", "agent_wrong", "agent_ok"]
KINDS: tuple[Kind, ...] = ("gold", "partial", AGENT_WRONG, AGENT_OK)  # the order runs go in
Outcome = Literal[
    "receipt", "timeout", "no_receipt", "unreadable_receipt", "harness_error", "api_error",
    "no_recording",
]  # fmt: skip
RETRIED: frozenset[Outcome] = frozenset({"harness_error", "api_error", "no_recording"})
# Model problems from outside Tracefix (llm.ProblemKind). Budget, refusal, invalid output, a
# rejected request and "other" are Tracefix's own doing, so a run with only those still counts.
API_KINDS = frozenset({"no_credentials", "auth", "billing", "permission", "model_unavailable",
                       "rate_limit", "api_unavailable", "network"})  # fmt: skip
# The Judge can only veto L3 (`ladder`), so its failure changed nothing at any other level; the
# summary's words never set a level.
JUDGE, VETOED_AT, SUMMARY = "judge", "L2", "summary"
RESERVE_USD = 3.0  # held back for each live run in flight (the plan's figure; it grows, below)
MAX_RECEIPT_BYTES = 50 * 1024 * 1024
LOCK = "run.lock"
NOT_STARTED, CUT_SHORT = "not started (Ctrl+C)", "cut short (Ctrl+C)"
WAKE_S = 0.5  # the pool's main thread looks for Ctrl+C this often
# M11's thin arm: Tracefix sees the issue's title only (`title`), our own cut of the text.
IssueArm = Literal["full", "title"]
WheelSha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class RunLine(BaseModel):
    """One line of runs.jsonl: one verify, what came of it, and the replay of its findings."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    instance_id: str
    kind: Kind
    variant: str  # "gold", the kept partial fix's "v<index>", or the agent kind
    repeat: Annotated[int, Field(ge=1)]
    live: bool
    outcome: Outcome
    exit_code: int | None = None
    seconds: float = 0.0
    receipt: str | None = None  # the receipt's folder, relative to the results folder
    level: str | None = None
    cost_usd: float | None = None  # the receipt's estimate; None: unknown
    replay: Replays | None = None  # non-gold runs with findings: each one on the gold commit
    detail: str = ""  # our own words
    reclassified: bool = False  # written by `reclassify`: not an attempt, so nothing spent
    # Added in M11 (optional, so earlier lines parse unchanged):
    issue: IssueArm = "full"  # the issue text Tracefix saw: all of it, or its title (`title`)
    wheel: WheelSha | None = None  # sha256 of the Tracefix wheel the box ran
    mode: Mode | None = None  # how the model answers came (None: a line from before M11)
    live_usd: float | None = None  # anchored: the cost of the recordings it added; None: unknown

    @property
    def key(self) -> tuple[str, str, int]:
        return (self.instance_id, self.kind, self.repeat)

    @property
    def spend_usd(self) -> float | None:
        """What this attempt cost in money: an anchored run replayed most of its calls for free,
        so only its new recordings count; any other run's estimate is what it paid."""
        return self.live_usd if self.mode == "anchored" else self.cost_usd

    @property
    def tag(self) -> str:
        return tag(self.variant, self.repeat)


def tag(variant: str, repeat: int) -> str:
    return f"{variant}-r{repeat}"


def title(issue: str) -> str:
    """The issue's first non-empty line, stripped (the thin arm's whole issue); "" if none."""
    return next((line.strip() for line in issue.splitlines() if line.strip()), "")


def issue_text(issue: str, arm: IssueArm) -> str:
    return issue if arm == "full" else title(issue)


class Results:
    """benchmarks/results/<slice>/: runs.jsonl and one folder per receipt. Appends are locked,
    so the pool's threads write whole lines."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.path = folder / "runs.jsonl"
        self._lock = threading.Lock()

    def lines(self) -> list[RunLine]:
        if not self.path.is_file():
            return []
        text = self.path.read_text(encoding="utf-8")
        return [RunLine.model_validate_json(line) for line in text.splitlines() if line]

    def append(self, line: RunLine) -> None:
        with self._lock:
            self.folder.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line.model_dump_json() + "\n")

    def receipt_folder(self, instance_id: str, run_tag: str) -> Path:
        return self.folder / instance_id / run_tag

    def receipt(self, line: RunLine) -> Receipt | None:
        """The receipt of a run that counts (an API error's stays on disk, for a look)."""
        if line.receipt is None or line.outcome != "receipt":
            return None
        return read_receipt(self.folder / line.receipt / "receipt.json")


def read_receipt(path: Path) -> Receipt | None:
    """The receipt, strictly parsed; None when it is missing, too large or not a receipt."""
    if not path.is_file() or path.stat().st_size > MAX_RECEIPT_BYTES:
        return None
    try:
        return Receipt.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValidationError, UnicodeDecodeError):
        return None


def latest(lines: Iterable[RunLine]) -> dict[tuple[str, str, int], RunLine]:
    """Each run's last line (a run tried again is replaced by its new line)."""
    return {line.key: line for line in lines}


def could_change_verdict(problem: ModelProblem, receipt: Receipt) -> bool:
    """Every model call feeds a verdict except the summary's and the blind test's (report only),
    and the Judge's only at L2."""
    if problem.stage in (SUMMARY, BLIND):
        return False
    return problem.role != JUDGE or receipt.level.value == VETOED_AT


def api_problem(receipt: Receipt) -> str | None:
    """Our words for the receipt's first model problem from outside Tracefix that could have
    changed its verdict, or None."""
    found = next((p for p in receipt.llm.problems
                  if p.kind in API_KINDS and could_change_verdict(p, receipt)), None)  # fmt: skip
    return None if found is None else f"api: {found.stage}: {found.kind}"


def recording_problem(receipt: Receipt) -> str | None:
    """Our words for the receipt's first model call that had no recorded answer, or None. The
    blind test's doesn't count: it is report only, and a run recorded before it had none."""
    found = next((p for p in receipt.llm.problems
                  if p.kind == "missing_recording" and p.stage != BLIND), None)  # fmt: skip
    return None if found is None else f"replay: {found.stage}: no recorded answer"


def python_refused(receipt: Receipt) -> bool:
    """Whether the check of the project's Python (--python) refused it. It runs on the box's own
    Python before any copy, so it is the same for every fix, and prepare checked that Python:
    the run measured the harness (or Tracefix's check), not the fix (S10: 11 runs)."""
    return any(s.name == "environment" and s.status == "ENVIRONMENT_ERROR"
               and s.evidence.get("error") == "Interpreter" for s in receipt.stages)  # fmt: skip


def classify(receipt: Receipt) -> tuple[Outcome, str]:
    """A receipt's outcome under today's rules, and our words for it."""
    if python_refused(receipt):
        return "harness_error", "the project's Python was refused"
    if (problem := api_problem(receipt)) is not None:
        return "api_error", problem
    if (problem := recording_problem(receipt)) is not None:
        return "no_recording", problem
    return "receipt", ""


def attempts(lines: Iterable[RunLine]) -> list[RunLine]:
    """The live runs that were started (a line `reclassify` wrote is the same run again)."""
    return [line for line in lines if line.live and not line.reclassified]


# --- what to run --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Unit:
    kind: Kind
    repeat: int


def variant_for(prepared: Prepared, kind: Kind) -> str | None:
    """The variant a run of `kind` checks: gold, the partial fix prepare keeps, or the agent's
    patch prepare keeps (None: none)."""
    if kind == GOLD:
        return GOLD
    if kind == "partial":
        return None if prepared.kept is None else prepare.variant_kind(prepared.kept)
    return kind if any(a.kind == kind and a.kept for a in prepared.agents) else None


def stale(lines: Iterable[RunLine], ready: Mapping[str, Prepared]) -> list[RunLine]:
    """Each run's last line that checked another variant than prepare keeps now: it counts
    nowhere, and `run` does it again."""
    return [
        line
        for line in latest(lines).values()
        if (p := ready.get(line.instance_id)) is not None
        and line.variant != variant_for(p, line.kind)
    ]


@dataclass(frozen=True)
class Job:
    """One task's runs still to do, in one box."""

    case: Case
    prepared: Prepared
    units: tuple[Unit, ...]
    last: bool = True  # nothing of the task is left to run after these: its image can go

    @property
    def task(self) -> Task:
        return self.case.task

    def variant(self, kind: Kind) -> str:
        found = variant_for(self.prepared, kind)
        if found is None:
            raise ValueError(f"this task has no {kind} fix")
        return found


def plan(
    cases: Sequence[Case], ready: Mapping[str, Prepared], done: Iterable[RunLine], repeats: int,
    split: str | None = None,
) -> list[Job]:  # fmt: skip
    """Every ready task's runs not done yet, in rank order; first repeats first. With `split`,
    only the cases of that split (dev or held_out)."""
    last = latest(done)
    jobs = []
    for case in cases:
        if split is not None and case.split != split:
            continue
        prepared = ready.get(case.task.instance_id)
        if prepared is None or prepared.excluded is not None:
            continue
        kinds = tuple(k for k in KINDS if variant_for(prepared, k) is not None)
        units = tuple(
            Unit(kind, r)
            for r in range(1, repeats + 1)
            for kind in kinds
            if not _finished(last.get((case.task.instance_id, kind, r)), prepared)
        )
        if units:
            jobs.append(Job(case, prepared, units))
    return jobs


def _finished(line: RunLine | None, prepared: Prepared) -> bool:
    return (
        line is not None
        and line.outcome not in RETRIED
        and line.variant == variant_for(prepared, line.kind)
    )


def by_repeat(jobs: Sequence[Job]) -> list[list[Job]]:
    """The jobs in rounds, one per repeat: every task's first runs before any task's second, so
    a ceiling stop costs repeats, never a later task's first runs. A task gets a box per round,
    and its image goes after its last round."""
    rounds = []
    for r in sorted({u.repeat for job in jobs for u in job.units}):
        found = []
        for job in jobs:
            units = tuple(u for u in job.units if u.repeat == r)
            if units:
                last = max(u.repeat for u in job.units) == r
                found.append(replace(job, units=units, last=last))
        rounds.append(found)
    return rounds


# --- the spend guard ----------------------------------------------------------------------------


def spent(lines: Iterable[RunLine], reserve: float) -> float:
    """What live runs have cost so far: every attempt, tried-again ones too (money is spent per
    attempt); an attempt with no known cost counts as a whole reserve."""
    return sum(
        (line.spend_usd if line.spend_usd is not None else reserve) for line in attempts(lines)
    )


@dataclass
class SpendGuard:
    """Live runs start only while spent + reserve x (runs in flight + 1) stays within the
    ceiling. Too little room even for one run alone stops the guard for good; too little room
    only because others are in flight is a wait (`start(wait=True)`), not a stop."""

    ceiling: float
    spent: float = 0.0
    reserve: float = RESERVE_USD
    in_flight: int = 0
    stopped: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _turn: threading.Condition = field(init=False)

    def __post_init__(self) -> None:
        self._turn = threading.Condition(self._lock)

    def _alone_fits(self) -> bool:
        if self.spent + self.reserve > self.ceiling:
            self.stopped = True
        return not self.stopped

    def room(self) -> bool:
        """Could one more run start, once the runs in flight end? Asked before opening a box
        (pulling an image costs minutes); `start` still decides. Once refused, never again."""
        with self._lock:
            return self._alone_fits()

    def start(self, *, wait: bool = False) -> bool:
        """May one more run start? If so, it is in flight until `finish`. With `wait`, a run that
        doesn't fit only because of the runs in flight waits for them instead of being refused."""
        with self._turn:
            while self._alone_fits():
                if self.spent + self.reserve * (self.in_flight + 1) <= self.ceiling:
                    self.in_flight += 1
                    return True
                if not wait:
                    return False
                self._turn.wait()
            return False

    def finish(self, cost: float | None) -> None:
        with self._turn:
            self.in_flight -= 1
            self.spent += self.reserve if cost is None else cost
            if cost is not None:
                self.reserve = max(self.reserve, cost)
            self._turn.notify_all()

    def release(self) -> None:
        """A run `start` let in that didn't start after all (Ctrl+C): nothing was spent."""
        with self._turn:
            self.in_flight -= 1
            self._turn.notify_all()


def live_guard(
    lines: Sequence[RunLine], ceiling: float, reserve: float = RESERVE_USD
) -> SpendGuard:
    """The guard for a live pool: what earlier runs spent, and a reserve per run of `reserve`
    or the dearest run seen, whichever is more. Earlier runs with no known cost still count as
    RESERVE_USD each, however low `reserve` is set."""
    known = [line.spend_usd for line in attempts(lines) if line.spend_usd is not None]
    return SpendGuard(ceiling, spent(lines, RESERVE_USD), max([reserve, *known]))


def worst_run_usd() -> float:
    """What Tracefix's own limits let one run cost: its whole token budget and one more answer
    (the budget is checked before each call), all at the dearest output price of the models it
    runs with (the benchmark sets none). The last call's prompt isn't bounded by our limits, so
    this is a floor for the worst case, far above any run seen (slice 1's dearest: $0.68)."""
    price = max(llm.PRICES_PER_MTOK[model][1] for model in llm.DEFAULT_MODELS.values())
    return (llm.DEFAULT_TOKEN_BUDGET + llm.DEFAULT_MAX_TOKENS) * price / 1_000_000


def reserve_warning(guard: SpendGuard) -> str | None:
    """Our words when the ceiling rests on no run costing more than the reserve, or None."""
    worst = worst_run_usd()
    if guard.reserve >= worst:
        return None
    return (
        f"the ceiling holds only while no run costs more than the reserve "
        f"(${guard.reserve:.2f}); Tracefix's token budget allows ${worst:.2f} a run"
    )


def free() -> SpendGuard:
    """Recorded runs cost nothing."""
    return SpendGuard(ceiling=float("inf"), reserve=0.0)


# --- one job in one box -------------------------------------------------------------------------


class SetupFailed(Exception):
    """The box couldn't be set up as prepare had it; `str(exc)` is in our own words."""


@dataclass
class Pool:
    results: Results
    recordings: Path  # one folder per task under it
    work: Path  # one scratch folder per task under it
    wheel: Path
    mode: Mode
    guard: SpendGuard
    make_box: Callable[[Task], Box]  # a started box
    remove_image: Callable[[str], object] | None = None  # after a task's last run
    verify_timeout: float = prepare.VERIFY_TIMEOUT_S
    issue: IssueArm = "full"
    wheel_sha256: str | None = None  # recorded in every line
    anchor: Path | None = None  # adversary_live, anchored: the recordings replayed
    stopping: threading.Event = field(default_factory=threading.Event)  # Ctrl+C once
    halted: threading.Event = field(default_factory=threading.Event)  # Ctrl+C again
    # Every box opened, for a second Ctrl+C to remove (closing a closed box does nothing).
    _boxes: list[Box] = field(default_factory=list)
    _boxes_lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def live(self) -> bool:
        """Any live mode calls the model API: its lines are attempts the guard counts."""
        return self.mode != "replay"

    def opened(self, box: Box) -> Box:
        with self._boxes_lock:
            self._boxes.append(box)
        return box

    def interrupt(self) -> None:
        """Ctrl+C. Once: no run starts any more, and the runs going on finish and write their
        lines (their model calls are paid for). Again: their boxes are removed, by a thread of
        its own (removing one takes seconds; a third Ctrl+C must not stop it halfway), and the
        runs cut short are not counted as failed runs (`cut_short`, NOTES 38). More: nothing."""
        if not self.stopping.is_set():
            self.stopping.set()
            print("benchmark: Ctrl+C: no new run starts; the runs going on finish "
                  "(Ctrl+C again stops them now)", file=sys.stderr, flush=True)  # fmt: skip
            return
        if self.halted.is_set():
            return
        self.halted.set()
        print("benchmark: Ctrl+C again: removing the boxes; the runs cut short are done again "
              "next time", file=sys.stderr, flush=True)  # fmt: skip
        threading.Thread(target=self._close_all, daemon=True).start()

    def _close_all(self) -> None:
        with self._boxes_lock:
            going = list(self._boxes)
        for box in going:
            box.close()

    def go_on(self, box: Box) -> None:
        """Between a box's setup steps: after Ctrl+C the box goes and its job starts nothing."""
        if self.stopping.is_set():
            box.close()
            raise SetupFailed("stopped by Ctrl+C")


def cut_short(line: RunLine) -> RunLine | None:
    """The line of a run going on when the second Ctrl+C removed its box. A run that ended
    with its receipt (and its replay) keeps it. Otherwise the outcome is our doing: a known cost
    stays on record as a harness error (spent, and done again); with none, there is no line
    (a run that cost nothing known isn't counted at a whole reserve)."""
    if line.outcome == "receipt" and not line.detail:
        return line
    if line.spend_usd is None:
        return None
    return line.model_copy(update={"outcome": "harness_error", "detail": "cut short (Ctrl+C)",
                                   "receipt": None, "level": None, "replay": None})  # fmt: skip


def open_session(job: Job, pool: Pool) -> Session:
    """A fresh box with Tracefix installed and the same commits as prepare made."""
    scratch = pool.work / job.task.instance_id / "run"
    scratch.mkdir(parents=True, exist_ok=True)
    try:
        box = pool.opened(pool.make_box(job.task))
    except BoxError as exc:
        raise SetupFailed(str(exc)) from exc
    pool.go_on(box)
    session = Session(box, scratch)
    try:
        prepare.setup(session, pool.wheel)
        pool.go_on(box)
        kinds = {GOLD: job.task.patch}
        if job.prepared.kept is not None:
            kept = [v for v in patches.variants(job.task.patch) if v.index == job.prepared.kept]
            if not kept:
                raise SetupFailed("the kept variant is no longer among the patch's variants")
            kinds[job.variant("partial")] = kept[0].patch
        kinds |= _agent_patches(job)
        made = prepare.make_commits(session, job.task, kinds, hidden_tests=False)
    except (BoxError, StepFailed, patches.PatchError) as exc:
        box.close()
        raise SetupFailed(str(exc)) from exc
    except SetupFailed:
        box.close()
        raise
    wanted = dict(job.prepared.commits)
    got = {kind: made.commits.get(kind) for kind in wanted}
    if got != wanted:
        box.close()
        raise SetupFailed("the box's commits differ from prepare's")
    return session


def _agent_patches(job: Job) -> dict[str, str]:
    """The kept agents' patches, from the case: the very runs prepare labelled, applied as
    prepare applied them (agents.agent_patch)."""
    runs = agent_patches(job.case.agents)
    found: dict[str, str] = {}
    for agent in job.prepared.agents:
        if not agent.kept:
            continue
        run = runs.get(agent.kind)
        if run is None or run.source_row != agent.source_row:
            raise SetupFailed(f"the case's {agent.kind} run is not the one prepare labelled")
        found[agent.kind] = agent_patch(run, job.task.issue)
    return found


def run_job(job: Job, pool: Pool) -> Counter[str]:
    """The job's runs, in a box set up again after a timeout removed it. Stops when the guard
    refuses; removes the image once the task has nothing left to run."""
    counts: Counter[str] = Counter()
    units = list(job.units)
    while units:
        if pool.stopping.is_set():
            counts[NOT_STARTED] += len(units)
            return counts
        if not pool.guard.room():
            counts["not started (spend ceiling)"] += len(units)
            return counts
        session = open_session(job, pool)
        try:
            units = run_units(session, job, units, pool, counts)
        finally:
            session.box.close()
        if units and pool.guard.stopped:
            counts["not started (spend ceiling)"] += len(units)
            return counts
    if pool.remove_image is not None and job.last:
        pool.remove_image(job.task.image)
    return counts


def run_units(
    session: Session, job: Job, units: list[Unit], pool: Pool, counts: Counter[str]
) -> list[Unit]:
    """Runs units until one ends with the box gone; the units still to run."""
    for i, unit in enumerate(units):
        if not pool.guard.start(wait=True):
            return units[i:]
        if pool.stopping.is_set():  # checked after `start`: it may have waited for room
            pool.guard.release()
            return units[i:]
        cost: float | None = None
        try:
            line, alive = one_run(session, job, unit, pool)
            cost = line.spend_usd
        finally:
            pool.guard.finish(cost)
        if pool.halted.is_set():  # its box may have been removed under it
            kept = cut_short(line)
            if kept is not line:
                counts[CUT_SHORT] += 1
                print(f"  {job.task.instance_id} {line.tag}: cut short", file=sys.stderr,
                      flush=True)  # fmt: skip
                if kept is not None:
                    pool.results.append(kept)
                return units[i + 1 :]
        pool.results.append(line)
        counts[line.outcome] += 1
        print(f"  {job.task.instance_id} {line.tag}: {line.outcome} {line.level or ''} "
              f"({line.seconds:.0f}s)", file=sys.stderr, flush=True)  # fmt: skip
        if not alive:
            return units[i + 1 :]
    return []


def one_run(session: Session, job: Job, unit: Unit, pool: Pool) -> tuple[RunLine, bool]:
    """One verify (and, for any fix but gold with findings, their replay on gold); the line, and
    whether the box is still there."""
    variant = job.variant(unit.kind)
    run_tag = tag(variant, unit.repeat)
    base = {"instance_id": job.task.instance_id, "kind": unit.kind, "variant": variant,
            "repeat": unit.repeat, "live": pool.live, "issue": pool.issue,
            "wheel": pool.wheel_sha256, "mode": pool.mode}  # fmt: skip
    out = pool.results.receipt_folder(job.task.instance_id, run_tag)
    if out.exists():  # an earlier attempt's (a run being tried again)
        shutil.rmtree(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    recordings = pool.recordings / job.task.instance_id
    anchor = None if pool.anchor is None else pool.anchor / job.task.instance_id
    issue = issue_text(job.task.issue, pool.issue)
    try:
        ran = prepare.verify(session, job.prepared, issue, variant, run_tag, out, recordings,
                             mode=pool.mode, anchor=anchor,
                             timeout=pool.verify_timeout)  # fmt: skip
    except (StepFailed, BoxError) as exc:
        return RunLine.model_validate(
            {**base, "outcome": "harness_error", "detail": str(exc)}
        ), True
    facts = {**base, "exit_code": ran.exit_code, "seconds": ran.seconds, "live_usd": ran.live_usd}
    if ran.exit_code is None:
        return RunLine.model_validate({**facts, "outcome": "timeout"}), False
    if ran.out is None or not (out / "receipt.json").is_file():
        return RunLine.model_validate({**facts, "outcome": "no_receipt"}), True
    receipt = read_receipt(out / "receipt.json")
    if receipt is None:
        return RunLine.model_validate({**facts, "outcome": "unreadable_receipt"}), True
    facts |= {"outcome": "receipt", "receipt": out.relative_to(pool.results.folder).as_posix(),
              "level": receipt.level.value,
              "cost_usd": receipt.llm.cost_estimate.usd}  # fmt: skip
    outcome, problem = classify(receipt)
    if outcome != "receipt":
        return RunLine.model_validate({**facts, "outcome": outcome, "detail": problem}), True
    if unit.kind != GOLD and receipt.findings:
        try:
            facts["replay"] = prepare.replay(session, job.prepared, run_tag)
        except StepTimeout as exc:
            return RunLine.model_validate({**facts, "detail": f"replay: {exc}"}), False
        except (StepFailed, BoxError) as exc:
            facts["detail"] = f"replay: {exc}"
    return RunLine.model_validate(facts), True


# --- the pool -----------------------------------------------------------------------------------


def run_all(jobs: Sequence[Job], pool: Pool, workers: int) -> dict[str, int]:
    """Up to `workers` tasks at once, each in its own box, a round per repeat (`by_repeat`);
    counts per outcome."""
    counts: Counter[str] = Counter()
    with _counted_ctrl_c() as presses:
        for round_jobs in by_repeat(jobs):
            counts.update(_run_round(round_jobs, pool, workers, presses))
    return dict(counts)


@contextmanager
def _counted_ctrl_c() -> Iterator[list[int]]:
    """While the pool runs, Ctrl+C only adds one to `presses[0]`; `_wait` hands each press to
    `Pool.interrupt`. A KeyboardInterrupt could arrive at any line of the main thread (before
    `_wait` starts, between rounds, inside `submit`) and escape the pool or leave a lock held; a
    handler that only counts can't. Off the main thread (signals never reach it) nothing changes."""
    presses = [0]
    if threading.current_thread() is not threading.main_thread():
        yield presses
        return

    def count(_signum: int, _frame: FrameType | None) -> None:
        presses[0] += 1

    before = signal.signal(signal.SIGINT, count)
    try:
        yield presses
    finally:
        signal.signal(signal.SIGINT, before)


def _handle(presses: list[int], pool: Pool) -> None:
    """Each press counted so far, once (a press during `interrupt` is counted and handled too)."""
    while presses[0]:
        presses[0] -= 1
        pool.interrupt()


def _run_round(jobs: Sequence[Job], pool: Pool, workers: int, presses: list[int]) -> Counter[str]:
    counts: Counter[str] = Counter()
    lock = threading.Lock()

    def one(job: Job) -> None:
        if pool.stopping.is_set():
            found: Counter[str] = Counter({NOT_STARTED: len(job.units)})
        elif pool.guard.stopped:
            found = Counter({"not started (spend ceiling)": len(job.units)})
        else:
            print(f"run {job.task.instance_id}", file=sys.stderr, flush=True)
            try:
                found = run_job(job, pool)
            except SetupFailed as exc:
                print(f"  {job.task.instance_id}: setup failed: {exc}", file=sys.stderr,
                      flush=True)  # fmt: skip
                why = NOT_STARTED if pool.stopping.is_set() else "setup failed"
                found = Counter({why: len(job.units)})
        with lock:
            counts.update(found)

    _handle(presses, pool)  # a press between rounds: the next round starts nothing
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(one, job) for job in jobs]
        _wait(futures, pool, presses)
    for future in futures:
        future.result()  # a worker's exception, raised here
    return counts


def _wait(futures: Sequence[Future[None]], pool: Pool, presses: list[int]) -> None:
    """Until every job is done, handling Ctrl+C presses every WAKE_S: on Windows Ctrl+C reaches
    a main thread only between waits (one that never woke held it off until a whole job ended)."""
    pending = set(futures)
    while pending:
        _handle(presses, pool)
        _, pending = wait(pending, timeout=WAKE_S)


# --- one process at a time, and the rules applied again -----------------------------------------


class Locked(Exception):
    """Another `run` or `reclassify` holds the slice's lock; `str(exc)` is in our own words."""


@contextmanager
def only_one(path: Path) -> Iterator[None]:
    """One process at a time per slice: two would run the same units and append both lines.
    A lock left by a process that crashed stays, and the words say what to do."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise Locked(f"{path} exists: another run is going, or one crashed (then delete the "
                     "file)") from None  # fmt: skip
    with os.fdopen(fd, "w", encoding="ascii") as f:
        f.write(f"{os.getpid()}\n")
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def reclassify(results: Results) -> dict[str, int]:
    """Each run's last line with a receipt, classified again by today's rules (`classify`). A
    changed outcome gets a new line (`reclassified`, so it isn't spent twice). A run (not
    gold's) with findings that was never replayed can't become a receipt here: `run` tries it
    again."""
    counts: Counter[str] = Counter()
    for line in latest(results.lines()).values():
        if line.outcome not in ("receipt", *RETRIED) or line.receipt is None:
            continue
        receipt = read_receipt(results.folder / line.receipt / "receipt.json")
        if receipt is None:
            counts["unreadable"] += 1
            continue
        outcome, detail = classify(receipt)
        unreplayed = line.kind != GOLD and bool(receipt.findings) and line.replay is None
        if outcome == line.outcome:
            counts["unchanged"] += 1
        elif outcome == "receipt" and unreplayed:
            counts["left to run (no replay)"] += 1
        else:
            update = {"outcome": outcome, "detail": detail, "reclassified": True}
            results.append(line.model_copy(update=update))
            counts[f"{line.outcome} -> {outcome}"] += 1
    return dict(counts)

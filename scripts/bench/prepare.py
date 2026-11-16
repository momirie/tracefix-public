"""Preparing one task in its box, and the two run steps on a prepared box (M10 plan P3, P4, P5).

`prepare` sets the box up, makes the commits, measures the base suite under Tracefix's runner
and runs the hidden tests on base, gold, each variant and each agent's patch (slice 2). Every
check that fails excludes the task with a reason in our own words; the partial-fix variant is
chosen from our own runs (patches.label, patches.keep), never by a model. An agent's patch is
kept only when our runs agree with the dataset's verdict (`agrees`): one they disagree on is
recorded, and never run. The result is a `Prepared` record, committed
under benchmarks/prepared/.

Each variant and agent patch also records the functions it touches (`changed_functions`, by
tracefix.diffscope in the box): the report's miss causes read them (M11).

`verify` runs `tracefix verify` on one prepared commit; `replay` runs a receipt's findings on the
gold commit. The run pool (step 4) calls them.

Everything the box sends back is parsed strictly: the box ran the project's code.
"""

from __future__ import annotations

import json
import math
import secrets
import shutil
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final, Literal, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    StringConstraints,
    ValidationError,
)

from bench import patches
from bench.agents import agent_patch
from bench.box import Box, BoxError, Installed, normalise
from bench.data import AgentRun, Sha, Task
from tracefix import llm
from tracefix.config import MAX_PLUGINS
from tracefix.previous import PreviousStatus, Replay

INSIDE = Path(__file__).with_name("inside.py")
# Read once: every box of one harness run gets the same steps, even if the file is edited while
# the run goes on (the host side of the protocol is already loaded).
INSIDE_SOURCE = INSIDE.read_bytes()
SUITE_CAP_S = 180  # the base suite must finish within this under Tracefix's runner (P3)
MIN_SUITE_TIMEOUT_S = 120
SUITE_TIMEOUT_FACTOR = 3  # suite_timeout_seconds = max(120, 3 x the measured base suite)
HIDDEN_RERUNS = 2  # a failing hidden run is rerun; a different ending makes it unsettled
STEP_TIMEOUT_S = 3_600  # one inside.py step (prepare)
VERIFY_TIMEOUT_S = 7_200  # one verify; past it the box is removed and the run is a timeout
MAX_RESULT_BYTES = 50 * 1024 * 1024
# A folder copied back from a box (a receipt folder, recordings): untrusted, so capped.
MAX_FOLDER_BYTES = 200 * 1024 * 1024
MAX_FOLDER_ENTRIES = 10_000
# Plugins that change how tests execute (order, repeats, processes, coverage): never loaded.
EXECUTION_PLUGINS = frozenset({
    "pytest-xdist", "pytest-randomly", "pytest-random-order", "pytest-rerunfailures", "flaky",
    "pytest-repeat", "pytest-cov", "pytest-forked",
})  # fmt: skip
GOLD = "gold"
# An agent's patch the hidden tests fail / pass (by the dataset; our runs label it: `agrees`).
AGENT_WRONG: Final = "agent_wrong"
AGENT_OK: Final = "agent_ok"
AgentKind = Literal["agent_wrong", "agent_ok"]
# How a verify gets its model answers: replayed from the recordings (no network), live (and
# recorded), or the adversary live and every other role replayed, live only on a missing
# recording (M11: one role measured, the rest held fixed), or every role replayed and live only
# on a request with no recorded answer (M11's arm B: only what changed costs money). Every mode
# but replay spends money.
Mode = Literal["replay", "live", "adversary_live", "anchored"]
ADVERSARY_RECORDING = "adversary-"  # a recording's file name starts with its role (tracefix.llm)
MAX_RECORDED_TOKENS = 100_000_000  # far above any answer; what a float can always be priced at

Isolation = Literal["strict", "basic"]
Module = Annotated[
    str, StringConstraints(pattern=r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$", max_length=200)
]
RelPath = Annotated[str, StringConstraints(pattern=r"^[^\x00-\x1f\x7f]+$", max_length=1_000)]
TestName = Annotated[str, StringConstraints(max_length=4_000)]
Outcome = Literal["passed", "failed", "flaky", "error", "timeout", "no_tests", "tampering"]


class Reason(StrEnum):
    """Why prepare excluded a task. The order of `prepare`'s checks is the order here."""

    INSTALL_FAILED = "tracefix_install_failed"
    PYTHON_UNUSABLE = "project_python_unusable"  # Tracefix's interpreter check refused it
    TOO_MANY_PLUGINS = "too_many_pytest_plugins"
    NOT_AT_BASE = "image_not_at_base_commit"
    SETUP_TOO_LARGE = "setup_commit_too_large"
    GOLD_DOES_NOT_APPLY = "gold_patch_does_not_apply"
    TESTS_DO_NOT_APPLY = "test_patch_does_not_apply"
    SUITE_TOO_SLOW = "base_suite_too_slow"
    SUITE_ERROR = "base_suite_cannot_run"
    UNSETTLED = "hidden_runs_unsettled"
    UNMATCHED = "hidden_test_ids_unmatched"
    BASE_PASSES = "fail_to_pass_passes_on_base"
    GOLD_FAILS = "hidden_tests_fail_on_gold"
    HARNESS_ERROR = "harness_error"


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


# --- what inside.py sends back --------------------------------------------------------------------


class Plugin(_Strict):
    name: Annotated[str, StringConstraints(max_length=200)]
    module: Module
    dist: Annotated[str, StringConstraints(max_length=200)]


class Probe(_Strict):
    python: Annotated[str, StringConstraints(pattern=r"^([0-9]+\.[0-9]+\.[0-9]+)?$")]
    level: Isolation
    why: Annotated[str, StringConstraints(max_length=2_000)]
    plugins: tuple[Plugin, ...] = Field(max_length=500)
    unusable: Annotated[str, StringConstraints(max_length=2_000)] = ""  # Tracefix's own words


class Commits(_Strict):
    error: Literal["not_at_base", "setup_too_large"] | None = None
    setup: tuple[RelPath, ...] = Field(default=(), max_length=1_000)
    changed: tuple[RelPath, ...] = Field(default=(), max_length=1_000)
    commits: dict[str, Sha | None] = {}
    with_tests: dict[str, Sha | None] = {}


class Suite(_Strict):
    status: Literal["ok", "ENVIRONMENT_ERROR", "tampering"]
    error: Module | None = None  # the environment check's exception name, e.g. ImportError
    module: Module | None = None  # the module it names as missing
    outcome: Outcome | None = None
    seconds: float | None = None
    tests: int | None = None
    isolation: Isolation | None = None


class Hidden(_Strict):
    outcome: Outcome
    rootdir: RelPath = "."
    passed: tuple[TestName, ...] = Field(default=(), max_length=200_000)
    failed: tuple[TestName, ...] = Field(default=(), max_length=200_000)
    tests: int = 0
    seconds: float = 0.0
    isolation: Isolation | None = None


class HiddenRuns(RootModel[dict[str, Hidden]]):
    model_config = ConfigDict(frozen=True, strict=True)


class Replayed(_Strict):
    number: int
    carried: bool
    result: Replay


class Replays(_Strict):
    status: PreviousStatus
    isolation: Isolation
    findings: tuple[Replayed, ...] = Field(max_length=1_000)


class Verified(_Strict):
    exit_code: int


class Touched(_Strict):
    """Source code one commit changes against another, by tracefix.diffscope's parse: a
    function or method (`function`: its qualname), or code outside every function (None:
    module or class level, or a file that doesn't parse)."""

    path: RelPath
    function: Annotated[str, StringConstraints(max_length=500)] | None


class Functions(RootModel[dict[str, tuple[Touched, ...]]]):
    model_config = ConfigDict(frozen=True, strict=True)


MAX_TOUCHED = 500  # per pair; more is not a fix this benchmark runs


# --- the record ---------------------------------------------------------------------------------


class TriedVariant(_Strict):
    index: int
    path: RelPath
    old_start: int
    old_len: int
    label: patches.Label
    failing: int
    # M11 (optional, so earlier records parse): what the dropped hunk touches, i.e. what the
    # variant's commit and gold's differ in; None: not recorded (or the variant didn't apply).
    functions: tuple[Touched, ...] | None = Field(default=None, max_length=MAX_TOUCHED)


class TriedAgent(_Strict):
    """An agent's patch (slice 2), labelled by our own hidden-test runs."""

    kind: AgentKind  # from the dataset's verdict (`resolved`), which only selects
    source_row: Annotated[int, Field(ge=0)]  # the run's row in the agent dataset
    label: patches.Label
    failing: int
    kept: bool  # our runs agree with the dataset's verdict (`agrees`): it is run
    # M11 (optional): what the patch touches (base to agent), and where the agent's code
    # differs from gold's (agent to gold); None: not recorded (or the patch didn't apply).
    functions: tuple[Touched, ...] | None = Field(default=None, max_length=MAX_TOUCHED)
    differs: tuple[Touched, ...] | None = Field(default=None, max_length=MAX_TOUCHED)


class Prepared(_Strict):
    """One task after prepare: excluded with a reason, or ready to run."""

    instance_id: str
    excluded: Reason | None
    detail: str = ""  # our own words only
    python: str = ""
    isolation: Isolation | None = None
    pip_changes: tuple[str, ...] = ()
    setup_files: tuple[RelPath, ...] = ()  # the setup commit's ignored files
    changed_files: tuple[RelPath, ...] = ()  # the image's own changes to its checkout
    plugins: tuple[Module, ...] = ()
    suite_seconds: float | None = None
    suite_timeout: int | None = None
    source_hunks: int = 0
    variants: tuple[TriedVariant, ...] = ()
    kept: int | None = None  # the kept variant's index; None: the task has no incorrect variant
    agents: tuple[TriedAgent, ...] = ()
    commits: dict[str, Sha] = {}  # base, gold, the kept variant and agents (fixed dates)
    seconds: float = 0.0

    def config(self) -> str:
        """The run's `--config`: suite timeout and plugins only, no model settings (P5)."""
        if self.suite_timeout is None:
            raise ValueError("an excluded task has no config")
        return config_text(self.suite_timeout, self.plugins)


def config_text(suite_timeout: int, plugins: Sequence[str]) -> str:
    return f"suite_timeout_seconds: {suite_timeout}\npytest_plugins: [{', '.join(plugins)}]\n"


def variant_kind(index: int) -> str:
    return f"v{index}"


def agent_kind(run: AgentRun) -> AgentKind:
    return AGENT_OK if run.resolved else AGENT_WRONG


def agrees(kind: AgentKind, label: patches.Label) -> bool:
    """Our hidden runs say what the dataset says: an agent_wrong patch is incorrect by them
    (patches.USABLE, as a partial variant must be), an agent_ok one can't be told from gold."""
    if kind == AGENT_WRONG:
        return label in patches.USABLE
    return label is patches.Label.HIDDEN_TESTS_PASS


def agent_patches(runs: Sequence[AgentRun]) -> dict[str, AgentRun]:
    """The task's agent runs by kind; two of one kind are refused (choose picks one each)."""
    found: dict[str, AgentRun] = {agent_kind(r): r for r in runs}
    if len(found) != len(runs):
        raise ValueError("more than one agent run of one kind")
    return found


# --- talking to inside.py -----------------------------------------------------------------------


class StepFailed(Exception):
    """inside.py crashed, timed out or sent something unreadable; `str(exc)` is our own words."""


class StepTimeout(StepFailed):
    """The step ran past its timeout (a DockerBox is removed then)."""


@dataclass
class Session:
    """One box, and a local folder for requests, results and logs."""

    box: Box
    scratch: Path
    calls: int = 0
    # In every remote file name: a result left by an earlier session's step is never read.
    token: str = field(default_factory=lambda: secrets.token_hex(4))
    seconds: float = 0.0  # the last call's wall time

    def call(
        self, command: str, request: Mapping[str, object], *, timeout: float = STEP_TIMEOUT_S,
        env_names: Sequence[str] = (),
    ) -> str:  # fmt: skip
        """Run one inside.py command; its result as JSON text (the caller parses it strictly).
        A box whose project has an interpreter of its own names it in every request."""
        self.calls += 1
        if self.box.project_python is not None:
            request = {**request, "python": self.box.project_python}
        stem = f"{self.token}-{self.calls:03d}-{command}"
        local = self.scratch / f"{stem}.request.json"
        local.write_text(json.dumps(request), encoding="utf-8")
        remote_request, remote_result = self.box.path(local.name), self.box.path(f"{stem}.json")
        self.box.put(local, remote_request)
        argv = [self.box.python, "-s", self.box.path("inside.py"), command, remote_request,
                remote_result]  # fmt: skip
        ran = self.box.run(argv, timeout=timeout, env_names=env_names)
        self.seconds = ran.seconds
        (self.scratch / f"{stem}.log").write_text(ran.output, encoding="utf-8")
        if ran.code is None:
            raise StepTimeout(f"{command} timed out after {timeout:g}s")
        result = self.scratch / f"{stem}.result.json"
        try:
            self.box.get(remote_result, result)
        except BoxError as exc:
            raise StepFailed(f"{command} wrote no result (exit {ran.code})") from exc
        try:
            check_copy(result, MAX_RESULT_BYTES)
        except BoxError as exc:
            raise StepFailed(f"{command}'s result: {exc}") from exc
        try:
            envelope = json.loads(result.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise StepFailed(f"{command}'s result is not JSON") from exc
        if not isinstance(envelope, dict) or envelope.get("ok") is not True:
            raise StepFailed(f"{command} failed (exit {ran.code})")
        return json.dumps(envelope.get("result"))


def check_copy(local: Path, max_bytes: int | None = None) -> None:
    """What a box sent back must be plain files and folders within the caps (MAX_FOLDER_BYTES
    unless given): a symlink would point into this PC. Anything else is removed and refused
    (BoxError, in our own words)."""
    problem = _copy_problem(local, MAX_FOLDER_BYTES if max_bytes is None else max_bytes)
    if problem is None:
        return
    if local.is_symlink() or local.is_file():
        local.unlink()
    else:
        shutil.rmtree(local)  # never follows a symlink inside it
    raise BoxError(f"{local.name} from the box {problem}")


def _copy_problem(local: Path, max_bytes: int) -> str | None:
    if local.is_symlink():
        return "is a symlink"
    if local.is_file():
        return "is too large" if local.stat().st_size > max_bytes else None
    total = 0
    for entries, path in enumerate(local.rglob("*"), 1):
        if entries > MAX_FOLDER_ENTRIES:
            return "holds too many files"
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            return "holds something other than files and folders"
        total += path.stat().st_size if path.is_file() else 0
        if total > max_bytes:
            return "is too large"
    return None


M = TypeVar("M", bound=BaseModel)


def parsed(model: type[M], text: str, command: str) -> M:
    """A step's result as `model`, strictly; StepFailed (our words, not the box's) otherwise."""
    try:
        return model.model_validate_json(text)
    except ValidationError as exc:
        raise StepFailed(f"{command}'s result is not what the harness expects") from exc


def setup(session: Session, wheel: Path) -> tuple[Installed, Probe]:
    installed = session.box.install(wheel)
    local = session.scratch / "inside.py"
    local.write_bytes(INSIDE_SOURCE)
    session.box.put(local, session.box.path("inside.py"))
    return installed, parsed(Probe, session.call("probe", {}), "probe")


def choose_plugins(probe: Probe, installed: Installed) -> list[str]:
    """The project's own pytest plugins: from distributions installed before Tracefix was, minus
    the ones that change how tests execute, plus the option stubs installed for those (so addopts
    such as `-n auto` or `--cov` still parse). Tracefix runs with plugin autoload off, so these
    are loaded by name (`pytest_plugins`), as a user would list them."""
    chosen = {
        p.module
        for p in probe.plugins
        if normalise(p.dist) in installed.before and normalise(p.dist) not in EXECUTION_PLUGINS
    }
    return sorted(chosen | set(installed.stubs))


def make_commits(
    session: Session, task: Task, kinds: Mapping[str, str], *, hidden_tests: bool,
    reset: Sequence[str] = (),
) -> Commits:  # fmt: skip
    """The commits; the hidden-test ones (`tf-<kind>-t`) only with `hidden_tests`. A run box
    never gets them, nor the test patch, so code run during verify can't read them (plan P5).
    The kinds in `reset` (agents' patches, which may change the tests) get the test patch's
    files back from base before it is applied."""
    request: dict[str, object] = {
        "repo": session.box.repo, "base_commit": task.base_commit,
        "test_patch": task.test_patch if hidden_tests else None, "patches": dict(kinds),
    }  # fmt: skip
    if hidden_tests and reset:
        tests = sorted(patches.files(task.test_patch)) if task.test_patch else []
        request["reset"] = dict.fromkeys(reset, tests)
    return parsed(Commits, session.call("commits", request), "commits")


# --- hidden test ids ----------------------------------------------------------------------------


def junit_id(test_id: str, rootdir: str) -> str | None:
    """A SWE-rebench id (`tests/test_x.py::TestA::test_b[p]`, from the repo's top) as the
    runner's JUnit id (`tests.test_x.TestA::test_b[p]`), as pytest builds JUnit names from a node
    id relative to its rootdir. None when the file isn't under the rootdir."""
    path, bracket, params = test_id.partition("[")
    names = path.split("::")
    file = names[0]
    if rootdir != ".":
        prefix = rootdir.rstrip("/") + "/"
        if not file.startswith(prefix):
            return None
        file = file[len(prefix) :]
    names[0] = file.replace("/", ".").removesuffix(".py")
    names[-1] += bracket + params
    return f"{'.'.join(names[:-1])}::{names[-1]}"


def truncated(test_id: str) -> bool:
    """SWE-rebench's log parser cuts an id at its first space, so a parameter such as
    `[(21.7, 61.0)-0.0]` arrives as `[(21.7,`: an unclosed bracket."""
    return "[" in test_id and not test_id.endswith("]")


def _matching(test_id: str, rootdir: str, ran: Sequence[str]) -> list[str]:
    """The run's JUnit ids that `test_id` names: itself, or for a truncated id every id that
    starts with it."""
    wanted = junit_id(test_id, rootdir)
    if wanted is None:
        return []
    if truncated(test_id):
        return [name for name in ran if name.startswith(wanted)]
    return [wanted] if wanted in ran else []


def _passed(run: Hidden, ids: Sequence[str]) -> frozenset[str]:
    """Ids whose tests all ran and passed (a truncated id: every test it names)."""
    ran, passed = (*run.passed, *run.failed), frozenset(run.passed)
    return frozenset(
        t for t in ids if (m := _matching(t, run.rootdir, ran)) and all(n in passed for n in m)
    )


def hidden_run(run: Hidden | None, ids: Sequence[str]) -> patches.HiddenRun:
    """The run as patches.label reads it: hidden ids that ran and passed, in SWE-rebench's form.
    None: the variant didn't apply."""
    if run is None:
        return patches.HiddenRun(False, False, frozenset())
    settled = run.outcome in ("passed", "failed", "error", "no_tests")
    error = run.outcome in ("error", "no_tests")
    return patches.HiddenRun(True, error, _passed(run, ids), settled)


def seen(run: Hidden, ids: Sequence[str]) -> frozenset[str]:
    ran = (*run.passed, *run.failed)
    return frozenset(t for t in ids if _matching(t, run.rootdir, ran))


def test_files(task: Task) -> list[str]:
    return sorted({t.split("::", 1)[0] for t in (*task.fail_to_pass, *task.pass_to_pass)})


# --- prepare ------------------------------------------------------------------------------------


class Excluded(Exception):
    def __init__(self, reason: Reason, detail: str = "") -> None:
        super().__init__(reason.value)
        self.reason, self.detail = reason, detail


def prepare(
    session: Session, task: Task, wheel: Path, *, agents: Sequence[AgentRun] = (),
    suite_cap: float = SUITE_CAP_S,
) -> Prepared:  # fmt: skip
    """Every check of P3's second stage, then P4's variants and the agents' patches (C3);
    `Prepared` either way."""
    facts: dict[str, object] = {"instance_id": task.instance_id}
    start = time.monotonic()
    reason: Reason | None = None
    detail = ""
    try:
        _prepare(session, task, wheel, agent_patches(agents), suite_cap, facts)
    except Excluded as exc:
        reason, detail = exc.reason, exc.detail
    except (StepFailed, BoxError, patches.PatchError) as exc:
        reason, detail = Reason.HARNESS_ERROR, str(exc)
    seconds = round(time.monotonic() - start, 3)
    return Prepared.model_validate({**facts, "excluded": reason, "detail": detail,
                                    "seconds": seconds})  # fmt: skip


def _prepare(
    session: Session, task: Task, wheel: Path, agents: Mapping[str, AgentRun], suite_cap: float,
    facts: dict[str, object],
) -> None:  # fmt: skip
    try:
        installed, probe = setup(session, wheel)
    except BoxError as exc:
        raise Excluded(Reason.INSTALL_FAILED, str(exc)) from exc
    if probe.unusable:
        raise Excluded(Reason.PYTHON_UNUSABLE, probe.unusable)
    plugins = choose_plugins(probe, installed)
    facts |= {"python": probe.python, "isolation": probe.level,
              "pip_changes": tuple(installed.changes()), "plugins": tuple(plugins)}  # fmt: skip
    if len(plugins) > MAX_PLUGINS:
        raise Excluded(Reason.TOO_MANY_PLUGINS, f"{len(plugins)} plugins")
    found = patches.variants(task.patch)
    facts["source_hunks"] = patches.source_hunks(patches.parse(task.patch))
    kinds = {GOLD: task.patch} | {variant_kind(v.index): v.patch for v in found}
    kinds |= {kind: agent_patch(run, task.issue) for kind, run in agents.items()}
    made = make_commits(session, task, kinds, hidden_tests=True, reset=tuple(agents))
    if made.error == "not_at_base":
        raise Excluded(Reason.NOT_AT_BASE)
    if made.error == "setup_too_large":
        raise Excluded(Reason.SETUP_TOO_LARGE)
    facts |= {"setup_files": made.setup, "changed_files": made.changed}
    if made.commits.get(GOLD) is None:
        raise Excluded(Reason.GOLD_DOES_NOT_APPLY)
    if made.with_tests.get("base") is None or made.with_tests.get(GOLD) is None:
        raise Excluded(Reason.TESTS_DO_NOT_APPLY)
    suite_timeout = _suite(session, plugins, suite_cap, facts)
    hidden_ids = (*task.fail_to_pass, *task.pass_to_pass)
    refs = {kind: f"tf-{kind}-t" for kind, sha in made.with_tests.items() if sha is not None}
    request = {"repo": session.box.repo, "refs": refs, "files": test_files(task),
               "plugins": plugins, "timeout": suite_timeout, "reruns": HIDDEN_RERUNS}  # fmt: skip
    runs = parsed(HiddenRuns, session.call("hidden", request), "hidden").root
    if set(runs) != set(refs):
        raise StepFailed("hidden's result is not what the harness expects")
    check_hidden(task, runs["base"], runs[GOLD], hidden_ids)
    tried = [
        patches.tried(v, hidden_run(runs.get(variant_kind(v.index)), hidden_ids),
                      task.fail_to_pass, task.pass_to_pass)
        for v in found
    ]  # fmt: skip
    kept = patches.keep(tried)
    touched = changed_functions(session, made, [variant_kind(v.index) for v in found], agents)
    facts["variants"] = tuple(
        TriedVariant(index=t.variant.index, path=t.variant.path, old_start=t.variant.old_start,
                     old_len=t.variant.old_len, label=t.label, failing=t.failing,
                     functions=touched.get(variant_kind(t.variant.index)))
        for t in tried
    )  # fmt: skip
    commits = {"base": made.commits["base"], GOLD: made.commits[GOLD]}
    if kept is not None:
        facts["kept"] = kept.variant.index
        commits[variant_kind(kept.variant.index)] = made.commits[variant_kind(kept.variant.index)]
    tried_agents = [
        _tried_agent(run, runs.get(kind), task).model_copy(
            update={"functions": touched.get(kind), "differs": touched.get(f"{kind}{TO_GOLD}")}
        )
        for kind, run in agents.items()
    ]
    facts["agents"] = tuple(tried_agents)
    for agent in tried_agents:
        sha = made.commits.get(agent.kind)
        if agent.kept and sha is not None:
            commits[agent.kind] = sha
    facts["commits"] = commits


TO_GOLD = "-to-gold"  # a pair's name: where this kind's commit and gold's differ


def changed_functions(
    session: Session, made: Commits, variants: Sequence[str], agents: Mapping[str, AgentRun]
) -> dict[str, tuple[Touched, ...]]:
    """By tracefix.diffscope in the box: what each variant's dropped hunk touches (variant to
    gold), what each agent's patch touches (base to agent) and where it differs from gold
    (agent to gold, under "<kind>-to-gold"). A commit that didn't apply has none."""
    pairs: dict[str, tuple[str, str]] = {}
    for kind in variants:
        if made.commits.get(kind) is not None:
            pairs[kind] = (f"tf-{kind}", f"tf-{GOLD}")
    for kind in agents:
        if made.commits.get(kind) is not None:
            pairs[kind] = ("tf-base", f"tf-{kind}")
            pairs[f"{kind}{TO_GOLD}"] = (f"tf-{kind}", f"tf-{GOLD}")
    if not pairs:
        return {}
    request = {"repo": session.box.repo, "pairs": {k: list(v) for k, v in pairs.items()}}
    found = parsed(Functions, session.call("functions", request), "functions").root
    if set(found) != set(pairs) or any(len(v) > MAX_TOUCHED for v in found.values()):
        raise StepFailed("functions's result is not what the harness expects")
    return found


def _tried_agent(run: AgentRun, hidden: Hidden | None, task: Task) -> TriedAgent:
    """The agent's patch labelled from its hidden run (None: it didn't apply)."""
    ids = (*task.fail_to_pass, *task.pass_to_pass)
    found = hidden_run(hidden, ids)
    label = patches.label(found, task.fail_to_pass, task.pass_to_pass)
    agent = agent_kind(run)
    return TriedAgent(kind=agent, source_row=run.source_row, label=label,
                      failing=patches.failing(found, ids), kept=agrees(agent, label))  # fmt: skip


def _suite(session: Session, plugins: list[str], cap: float, facts: dict[str, object]) -> int:
    request = {"repo": session.box.repo, "plugins": plugins, "timeout": cap}
    suite = parsed(Suite, session.call("suite", request), "suite")
    if suite.status == "tampering":
        raise Excluded(Reason.SUITE_ERROR, "tampering detected in the base suite's run")
    if suite.outcome == "timeout":
        raise Excluded(Reason.SUITE_TOO_SLOW, f"over {cap:g}s")
    if suite.status != "ok" or suite.seconds is None:
        named = " ".join(n for n in (suite.error, suite.module) if n)
        raise Excluded(
            Reason.SUITE_ERROR, f"pytest outcome {suite.outcome}; {named or 'no error named'}"
        )
    timeout = max(MIN_SUITE_TIMEOUT_S, math.ceil(SUITE_TIMEOUT_FACTOR * suite.seconds))
    facts |= {"suite_seconds": suite.seconds, "suite_timeout": timeout}
    return timeout


def check_hidden(task: Task, base: Hidden, gold: Hidden, hidden_ids: Sequence[str]) -> None:
    base_run, gold_run = hidden_run(base, hidden_ids), hidden_run(gold, hidden_ids)
    if not base_run.settled or not gold_run.settled:
        raise Excluded(Reason.UNSETTLED, f"base {base.outcome}, gold {gold.outcome}")
    found = seen(base, task.fail_to_pass) | seen(gold, task.fail_to_pass)
    missing = [t for t in task.fail_to_pass if t not in found]
    if missing:
        raise Excluded(Reason.UNMATCHED, f"{len(missing)} of {len(task.fail_to_pass)} ids")
    passing = [t for t in task.fail_to_pass if t in base_run.passed]
    if passing:
        raise Excluded(Reason.BASE_PASSES, f"{len(passing)} of {len(task.fail_to_pass)}")
    failing = patches.failing(gold_run, hidden_ids)
    if failing:
        raise Excluded(Reason.GOLD_FAILS, f"{failing} of {len(hidden_ids)}")


# --- the run steps (step 4's pool calls these) ---------------------------------------------------


@dataclass(frozen=True)
class VerifyRun:
    exit_code: int | None  # None: timed out (the box was removed)
    seconds: float
    out: Path | None  # the local copy of the receipt folder; None when there is none
    live_usd: float | None = None  # anchored: what its new recordings cost; None: unknown


def verify(
    session: Session, prepared: Prepared, issue: str, kind: str, tag: str, out: Path,
    recordings: Path, *, mode: Mode, anchor: Path | None = None,
    timeout: float = VERIFY_TIMEOUT_S,
) -> VerifyRun:  # fmt: skip
    """`tracefix verify` from tf-base to tf-<kind>, its receipt folder copied to `out`. Live
    (either live mode): the API key passes to this one step by name, and the model's answers
    are recorded into `recordings` (new files only); replay: they are replayed from it, with no
    network. `adversary_live` first copies `anchor`'s answers of every other role into
    `recordings` (`seed`), so those roles replay them; `anchored` copies every role's, and prices
    the answers the run adds (`recordings_usd`)."""
    box = session.box
    live = mode != "replay"
    remote_out, remote_rec = box.path(f"out-{tag}"), box.path(f"recordings-{tag}")
    # Always there, so a live run that made no model call (e.g. ENVIRONMENT_ERROR) still has a
    # folder to copy back.
    recordings.mkdir(parents=True, exist_ok=True)
    # Our own copy from an earlier attempt (or result set) would stop the copy back only after
    # the model was paid, so it goes first; the answers kept are in `recordings`.
    copied = session.scratch / f"recordings-{tag}"
    if live and copied.exists():
        shutil.rmtree(copied)
    if mode in ("adversary_live", "anchored") and anchor is not None:
        seed(recordings, anchor, adversary=mode == "anchored")
    box.put(recordings, remote_rec)
    request = {"repo": box.repo, "head": f"tf-{kind}", "issue": issue,
               "config": prepared.config(), "out": remote_out, "recordings": remote_rec,
               "mode": mode}  # fmt: skip
    env = ("ANTHROPIC_API_KEY",) if live else ()
    try:
        answer = session.call("verify", request, timeout=timeout, env_names=env)
        result = parsed(Verified, answer, "verify")
    except StepTimeout:
        return VerifyRun(None, session.seconds, None)
    seconds = session.seconds
    try:
        box.get(remote_out, out)
        check_copy(out)
    except BoxError:
        return VerifyRun(result.exit_code, seconds, None)
    live_usd = None
    if live:
        new = _merge_recordings(box, remote_rec, copied, recordings)
        if mode == "anchored":
            live_usd = recordings_usd(new)
    return VerifyRun(result.exit_code, seconds, out, live_usd)


def seed(recordings: Path, anchor: Path, *, adversary: bool = False) -> int:
    """`anchor`'s recorded answers, the adversary's only with `adversary`, copied into
    `recordings` where it has none of that name (a file there is never replaced), so the run
    replays those roles and its own folder replays alone later. Returns how many were copied.
    Plain files only: a symlink is never followed."""
    if not anchor.is_dir():
        return 0
    copied = 0
    for path in sorted(anchor.glob("*.json")):
        target = recordings / path.name
        plain = path.is_file() and not path.is_symlink()
        wanted = adversary or not path.name.startswith(ADVERSARY_RECORDING)
        if plain and wanted and not target.exists():
            shutil.copyfile(path, target)
            copied += 1
    return copied


def _merge_recordings(box: Box, remote: str, local: Path, into: Path) -> list[Path]:
    """The box's recordings copied into `into`, never over a file there; the ones it added."""
    box.get(remote, local)
    check_copy(local)
    into.mkdir(parents=True, exist_ok=True)
    added: list[Path] = []
    for path in sorted(local.glob("*.json")):
        target = into / path.name
        if not target.exists():
            shutil.copyfile(path, target)
            added.append(target)
    return added


class _RecordedUsage(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    input_tokens: Annotated[int, Field(ge=0, le=MAX_RECORDED_TOKENS)]
    output_tokens: Annotated[int, Field(ge=0, le=MAX_RECORDED_TOKENS)]


class _Recorded(BaseModel):
    """The part of a recording (tracefix.llm.RecordingProvider) that prices its call."""

    model_config = ConfigDict(frozen=True, strict=True)

    role: llm.Role
    model: str
    response: _RecordedUsage


def recordings_usd(paths: Sequence[Path]) -> float | None:
    """What these recordings' calls cost at list prices. A box sent them back, so they are
    untrusted: None if any one can't be read or priced, and the spend guard then counts a whole
    reserve, which can only stop a run sooner."""
    calls: list[llm.CallRecord] = []
    for path in paths:
        try:
            found = _Recorded.model_validate_json(path.read_bytes())
        except ValidationError:
            return None
        calls.append(llm.CallRecord(found.role, found.model, found.response.input_tokens,
                                    found.response.output_tokens, 0.0, True))  # fmt: skip
    return llm.cost_usd(calls)


def replay(session: Session, prepared: Prepared, tag: str) -> Replays:
    """The findings of run `tag` (a partial fix's receipt) replayed on the gold commit."""
    request = {"repo": session.box.repo, "head": f"tf-{GOLD}",
               "previous": session.box.path(f"out-{tag}"), "plugins": list(prepared.plugins),
               "timeout": prepared.suite_timeout}  # fmt: skip
    return parsed(Replays, session.call("replay", request), "replay")

"""Break My Fix: concrete inputs that break the fixed code (SPEC 2.6, Decided in M6).

The hero stage. In order:
1. targets: the changed functions (attack_inputs), and the witnesses: literal calls to them in
   the project's untouched tests, kept only if those tests pass on head (one watched run);
2. the adversary model proposes properties (contracts) from what is written down; hygiene and the
   quote check (attack_rules) decide which count, and docstring examples count without a model;
3. the attack: attack_runtime runs inside a watched pytest run in head's copy, tries the explicit
   inputs and a Hypothesis search per property, and reports violations;
4. confirmation, for each deduplicated candidate: a probe calls it again on head (same outcome)
   and on base, and a standalone repro file written by our code must fail on head;
5. the pre-existing rule (Decided in M1): a finding that base shares and whose failing call runs
   none of the fix's lines is reported, not counted.

The model only proposes. A finding counts only through runs: an exit code, a JUnit report and
the line tracer. Model expressions are never evaluated in this process. Tampering makes the stage
invalid; an error after a confirmed finding keeps the finding.
"""

import ast
import itertools
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from tracefix.attack_inputs import (
    Args,
    AttackTarget,
    Seeds,
    Skipped,
    WitnessCall,
    doc_examples,
    dotted_suffixes,
    evidence_texts,
    fixed_by_file,
    readme,
    seeds_for,
    select_targets,
    survivors_in,
    test_functions,
    witness_calls,
)
from tracefix.attack_methods import RECEIVER, deleted_attributes
from tracefix.attack_rules import (
    MAX_EXAMPLES_PER_TARGET,
    MAX_PROPERTIES_PER_TARGET,
    SAFE_BUILTINS,
    STDLIB_MODULES,
    CheckedProperty,
    Expectation,
    Group,
    Violation,
    check_example,
    check_property,
    check_strategy,
    doc_property,
    group_violations,
    outcome_of,
    receiver_of,
    receiver_spec,
    render_finding,
    same_property,
    shadowed_stdlib,
    violation_of,
)
from tracefix.diffscope import DiffScope, FileKind, classify, unified_diff
from tracefix.guard import GuardResult
from tracefix.harness import placed, run_file, run_harness
from tracefix.integrity import matches, module_of
from tracefix.isolation import TamperingDetected, run_checked
from tracefix.linetrace import (
    dynamic_lookup,
    executable_lines,
    import_time_value_lines,
    removed_marked_defs,
)
from tracefix.llm import (
    BudgetExceeded,
    LLMClient,
    LLMError,
    LLMOutputError,
    LLMProviderError,
    Message,
)
from tracefix.prompts import adversary, python_note
from tracefix.repro import ReproResult, sanitize
from tracefix.runner import Outcome, RunResult
from tracefix.sandbox import BASIC_WARNING, Level, sandbox_level
from tracefix.workspace import Workspace, WorkspaceError, blob_text, git_run

ADVERSARY_CALLS = 2  # one request, plus one follow-up to repair rejected or contradicted ones
# Then one more, independent sample of the same request (developer, 6 Oct 2026: the model's
# properties vary from run to run, so two samples and all their properties; at most 3 calls).
ADVERSARY_SAMPLES = 2
SEARCH_EXAMPLES = 200  # Hypothesis examples per property
MAX_EXPLICIT = 400  # explicit inputs per target (witnesses and docstring examples on top)
MAX_REPLAY = 10  # earlier rounds' violating inputs run again per target (on top of the cap)
MAX_CONFIRM = 10  # candidate groups confirmed by runs
MAX_PROVEN_PER_GROUP = 2  # repro files tried per group (each one is up to three runs)
MAX_SHOWN = 5  # counting findings kept (SPEC 2.6)
MAX_PRE_EXISTING = 5
MAX_RESUMES = 2  # restarts after a hang, per target
MAX_WITNESS_FILES = 10
MAX_NAMES_SHOWN = 20  # parameters named in a no-input reason
ATTACK_TIMEOUT_S = 120  # a safety net only: limits are counts (a normal attack takes seconds)
PROBE_TIMEOUT_S = 120
FINDING_TIMEOUT_S = 60
FINDING_RERUNS = 2  # a repro file must fail three times in a row
DIFF_CHARS = 12_000
SOURCE_CHARS = 6_000
TESTS_CHARS = 6_000


class AttackStatus(StrEnum):
    FOUND = "found"  # at least one counting finding
    NONE_FOUND = "none_found"  # attacked with live properties, nothing found
    INCONCLUSIVE = "inconclusive"  # nothing could really be attacked or judged
    SKIPPED = "skipped"  # no changed function Break My Fix can call
    INVALID = "invalid"  # tampering detected: no verdict at all


@dataclass(frozen=True)
class PropertyResult:
    """A proposed or docstring property and what became of it."""

    id: str  # "" for a rejected proposal
    target: str
    name: str
    kind: str
    claim: str
    source: str
    quote: str
    status: str  # counted | rejected | contradicted | error
    reason: str = ""
    constrains_result: bool = False
    origin: str = "model"
    advisory: tuple[str, ...] = ()  # the PR's tests that disagree with it (never decides)


# Why a counted finding may be a false alarm (NOTES 40; developer, 4 Nov 2026: flagged, measured).
Doubt = Literal["os_limit", "finished_object", "refused"]
WINDOWS_NAME_TOO_LONG = "206"  # ERROR_FILENAME_EXCED_RANGE


@dataclass(frozen=True)
class Finding:
    number: int
    function: str  # dotted: module.name
    target: str
    input: Args
    outcome: dict[str, str] = field(hash=False)
    expected: str | None = None
    property: PropertyResult | None = None
    also_violates: tuple[str, ...] = ()
    other_inputs: tuple[Args | None, ...] = ()
    phase: str = ""
    base_outcome: dict[str, str] | None = field(default=None, hash=False)  # None: no such function
    fix_lines_run: tuple[tuple[str, tuple[int, ...]], ...] = ()
    relation: str = ""
    repro_path: str = ""
    repro_code: str = ""
    repro_run: RunResult | None = None
    path: str = ""  # the target's repo-relative file
    line: int = 0  # the first fix line the failing call ran there, else the target's first line
    expect: Expectation | None = None  # the failure its repro file must end with on head
    doubt: Doubt | None = None  # report only: no count or level reads it (M11 S5)


@dataclass(frozen=True)
class Discarded:
    target: str
    input: Args | None
    property: str
    reason: str
    run: RunResult | None = None


@dataclass(frozen=True)
class TargetReport:
    id: str
    function: str
    path: str
    via: str = ""
    module: str | None = None
    attacked: bool = False
    reason: str = ""
    inputs_tried: int = 0
    oracle_errors: int = 0
    reached: tuple[tuple[str, tuple[int, ...]], ...] = ()  # fixed lines the attack's calls ran
    crashes: tuple[tuple[str, str], ...] = ()  # (input, outcome) no property covered: report only
    hangs: tuple[str, ...] = ()  # report only
    notes: tuple[str, ...] = ()
    finished: bool = True  # False: its attack never finished (it hung too often, or a run broke)


@dataclass(frozen=True)
class AttackResult:
    status: AttackStatus
    reason: str
    findings: tuple[Finding, ...] = ()
    more: int = 0  # candidates left unconfirmed once MAX_SHOWN findings were found
    pre_existing: tuple[Finding, ...] = ()
    discarded: tuple[Discarded, ...] = ()
    properties: tuple[PropertyResult, ...] = ()
    targets: tuple[TargetReport, ...] = ()
    skipped: tuple[Skipped, ...] = ()
    fix_lines: tuple[tuple[str, tuple[int, ...]], ...] = ()  # executable fix lines in bodies
    runs: tuple[tuple[str, RunResult], ...] = ()
    isolation: Level = "basic"
    warnings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def inputs_tried(self) -> int:
        return sum(t.inputs_tried for t in self.targets)


# --- the stage's state ----------------------------------------------------------------------------


@dataclass
class _Stage:
    ws: Workspace
    scope: DiffScope
    targets: list[AttackTarget]
    phase: str = "the start"
    runs: list[tuple[str, RunResult]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    properties: dict[str, CheckedProperty] = field(default_factory=dict)  # by id
    results: list[PropertyResult] = field(default_factory=list)  # rejected proposals
    contradicted: dict[str, str] = field(default_factory=dict)  # property id -> why
    errors: dict[str, str] = field(default_factory=dict)  # property id -> why it couldn't run
    advisory: dict[str, list[str]] = field(default_factory=dict)  # property id -> PR tests
    violations: list[Violation] = field(default_factory=list)
    modules: dict[str, str] = field(default_factory=dict)  # target id -> dotted module
    target_errors: dict[str, str] = field(default_factory=dict)
    inputs: dict[str, int] = field(default_factory=dict)
    oracle_errors: dict[str, int] = field(default_factory=dict)
    reached: dict[str, dict[str, set[int]]] = field(default_factory=dict)
    crashes: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    hangs: dict[str, list[str]] = field(default_factory=dict)
    target_notes: dict[str, list[str]] = field(default_factory=dict)
    order: int = 0
    numbers: int = 0  # repro files written so far
    incomplete: set[str] = field(default_factory=set)  # targets whose attack did not finish
    held: set[str] = field(default_factory=set)  # docstring examples the run saw hold
    stdlib: frozenset[str] = frozenset()  # modules expressions (and objects' code) may use
    unbuilt: dict[str, int] = field(default_factory=dict)  # objects that could not be built
    first_unbuilt: dict[str, str] = field(default_factory=dict)
    first_unbuilt_brief: dict[str, str] = field(default_factory=dict)  # the error's type only
    first_oracle_error: dict[str, str] = field(default_factory=dict)
    unfit: dict[str, int] = field(default_factory=dict)  # inputs no property's `when` fits
    no_strategy: dict[str, list[str]] = field(default_factory=dict)  # as of the last run

    @property
    def by_id(self) -> dict[str, AttackTarget]:
        return {t.id: t for t in self.targets}


def _run_file(
    stage: _Stage, tree: Path, rel: str, code: str, label: str, timeout: float, reruns: int
) -> RunResult:
    """Write a generated test file into a copy, run it watched, and remove it again."""
    stage.phase = label
    run = run_file(stage.ws, tree, rel, code, timeout, reruns)
    stage.runs.append((label, run))
    return run


def _harness(
    stage: _Stage, tree: Path, mode: str, plan: Mapping[str, Any], label: str, timeout: float
) -> tuple[list[dict[str, Any]], RunResult]:
    """Run attack_runtime with a plan, inside a watched run; its events and the run."""
    stage.phase = label
    events, bad, run = run_harness(stage.ws, tree, mode, plan, timeout)
    stage.runs.append((label, run))
    if bad:
        stage.notes.append(f"{label}: {bad} unreadable lines in the run's report were ignored")
    return events, run


# --- witnesses ------------------------------------------------------------------------------------


def _passing(stage: _Stage, calls: Sequence[WitnessCall]) -> list[WitnessCall]:
    """The witnesses whose tests pass on head (repro witnesses already proved it). Each test file
    runs on its own, watched: a file that no longer imports would hide the others."""
    files = sorted({c.file for c in calls if not c.repro})
    if len(files) > MAX_WITNESS_FILES:
        stage.notes.append(
            f"only {MAX_WITNESS_FILES} of {len(files)} test files were run for witnesses"
        )
        files = files[:MAX_WITNESS_FILES]
    passed: dict[str, tuple[str, ...]] = {}
    for path in files:
        stage.phase = f"the witness run of {path}"
        run = run_checked(stage.ws, stage.ws.head, [path], reruns=0)  # the suite timeout
        stage.runs.append((f"the witness run of {path}", run))
        if run.outcome in (Outcome.PASSED, Outcome.FAILED):
            passed[path] = run.first.passed
    kept = []
    for call in calls:
        if call.repro:
            kept.append(call)
            continue
        if call.file not in passed:
            continue
        module = module_of(stage.ws.head, call.file)
        ids = [t for t in passed[call.file] if matches(t, module, call.test)]
        if ids:
            kept.append(call)
    return kept


def _tests_text(ws: Workspace, calls: Sequence[WitnessCall]) -> str:
    """The source of the untouched witness tests, as shown to the adversary (and quotable)."""
    wanted = {(c.file, c.test) for c in calls if not c.advisory and not c.repro}
    parts: list[str] = []
    for file in sorted({f for f, _ in wanted}):
        text = blob_text(ws.repo, ws.head_sha, file)
        if text is None:
            continue
        tree = ast.parse(text)
        for name, node in test_functions(tree):
            if (file, name) in wanted:
                segment = ast.get_source_segment(text, node) or ""
                parts.append(f"# {file}\n{segment}")
    joined = "\n\n".join(parts)
    return joined[:TESTS_CHARS]


# --- the adversary --------------------------------------------------------------------------------


def _context(
    stage: _Stage, issue: str, docs: str, tests: str, stdlib: frozenset[str]
) -> adversary.AdversaryContext:
    ws, scope = stage.ws, stage.scope
    paths = sorted({p for f in scope.source_files for p in (f.old_path, f.path) if p})
    diff = unified_diff(ws.repo, ws.base_sha, ws.head_sha, paths)[:DIFF_CHARS]
    functions = tuple(
        adversary.FunctionView(
            t.id,
            t.name,
            t.path,
            t.module_candidates[0],
            t.source[:SOURCE_CHARS],
            tuple(text for _, text in t.module_names),
            t.via,
            t.owner,
            t.kind,
            t.owner_context[:SOURCE_CHARS],
        )
        for t in stage.targets
    )
    return adversary.AdversaryContext(
        issue, diff, functions, docs, tests, tuple(sorted(SAFE_BUILTINS)), tuple(sorted(stdlib)),
        python_note(stage.ws.settings.python.version),
    )  # fmt: skip


@dataclass
class _Proposals:
    """What the model has proposed so far, as it will run."""

    strategies: dict[str, dict[str, str]] = field(default_factory=dict)  # target -> param -> text
    examples: dict[str, list[Args]] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)


def _accept(
    stage: _Stage,
    plan: adversary.AttackPlan,
    proposals: _Proposals,
    evidence: Mapping[str, Mapping[Any, Sequence[str]]],
    stdlib: frozenset[str],
    retrying: Collection[str] = (),
) -> tuple[list[CheckedProperty], list[str]]:
    """The new properties that pass hygiene and the quote check (repeats dropped), and the
    rejections as lines for the follow-up. Strategies and examples are taken too."""
    new: list[CheckedProperty] = []
    rejections: list[str] = []
    for p in plan.properties:
        try:
            target = next(t for t in stage.targets if p.function in (t.id, t.name))
        except StopIteration:
            target = None
        number = proposals.counters.get(target.id if target else "", 0) + 1
        pid = f"{target.id}.p{number}" if target else ""
        try:
            checked = check_property(p, stage.targets, evidence, stdlib, pid)
        except ValueError as exc:
            rejections.append(f"property {p.name!r} of {p.function}: {exc}")
            stage.results.append(
                PropertyResult(
                    "", p.function, p.name, p.kind, p.claim, p.source, p.quote, "rejected", str(exc)
                )
            )
            continue
        if any(same_property(checked, old) for old in stage.properties.values()):
            continue  # a repeat counts once
        count = sum(
            1
            for q in stage.properties.values()
            if q.target == checked.target and q.origin == "model"
        )
        if count >= MAX_PROPERTIES_PER_TARGET:
            rejections.append(
                f"property {p.name!r}: more than {MAX_PROPERTIES_PER_TARGET} "
                "properties for one function"
            )
            continue
        proposals.counters[checked.target] = number
        stage.properties[checked.id] = checked
        new.append(checked)
    return new, rejections + _take_inputs(stage, plan, proposals, stdlib, retrying)


def _take_inputs(
    stage: _Stage,
    plan: adversary.AttackPlan,
    proposals: _Proposals,
    stdlib: frozenset[str],
    retrying: Collection[str],
) -> list[str]:
    """Take the plan's strategies and examples; the rejections. For a target in `retrying` (it ran
    no input) the new ones go first and a new strategy replaces the old: the old ones ran nothing,
    so they must not use up the cap or be chosen as the typical input again."""
    rejections: list[str] = []
    for s in plan.strategies:
        try:
            tid, param, text = check_strategy(s, stage.targets)
        except ValueError as exc:
            rejections.append(f"strategy for {s.function}.{s.param}: {exc}")
            continue
        mine = proposals.strategies.setdefault(tid, {})
        if tid in retrying:
            mine[param] = text
        else:
            mine.setdefault(param, text)
    first: dict[str, list[Args]] = {}
    for e in plan.examples:
        try:
            tid, args = check_example(e, stage.targets, stdlib)
        except ValueError as exc:
            rejections.append(f"example for {e.function}: {exc}")
            continue
        if tid in retrying:
            first.setdefault(tid, []).append(args)
            continue
        listed = proposals.examples.setdefault(tid, [])
        if args not in listed and len(listed) < MAX_EXAMPLES_PER_TARGET:
            listed.append(args)
    for tid, args_list in first.items():
        merged = dict.fromkeys([*args_list, *proposals.examples.get(tid, [])])
        proposals.examples[tid] = list(merged)[:MAX_EXAMPLES_PER_TARGET]
    return rejections


# --- the attack runs ------------------------------------------------------------------------------


def _typical_objects(
    stage: _Stage,
    target: AttackTarget,
    found: Seeds,
    witnesses: Sequence[WitnessCall],
    proposals: _Proposals,
) -> list[str]:
    """The code of a method's typical objects, first seen first: the ones the project's tests
    (and the reproduction test) build, its docstring examples, the issue's calls, and the
    model's examples (developer, 9 Oct 2026: made-up objects count only for properties whose
    `when` names `self`; these are the others)."""
    if not target.has_receiver:
        return []
    docs = [p.example_args for p in stage.properties.values()
            if p.target == target.id and p.origin == "docstring"]  # fmt: skip
    inputs = [
        *(w.args for w in witnesses if w.target == target.id),
        *docs,
        *(e.args for e in found.examples),
        *proposals.examples.get(target.id, []),
    ]
    codes = (receiver_of(args, target) for args in inputs)
    return list(dict.fromkeys(code for code in codes if code is not None))


def _plan(
    stage: _Stage,
    props: Sequence[CheckedProperty],
    proposals: _Proposals,
    seeds: Mapping[str, Seeds],
    witnesses: Sequence[WitnessCall],
    fixed: Mapping[str, frozenset[int]],
    held: Sequence[CheckedProperty] = (),
) -> dict[str, Any]:
    """The runtime's plan for these properties. `held`: docstring examples that held in their own
    run, passed on as witnesses (their run had no model code in it)."""
    targets = []
    for target in stage.targets:
        mine = [p for p in props if p.target == target.id]
        if not mine:
            continue
        found = seeds[target.id]
        examples: list[dict[str, object]] = [
            {"phase": e.phase, "args": dict(e.args)} for e in found.examples
        ]
        examples += [
            {"phase": "model", "args": dict(a)} for a in proposals.examples.get(target.id, [])
        ]
        candidates: dict[str, list[dict[str, object]]] = {}
        for seed in found.seeds:
            candidates.setdefault(seed.param, []).append(
                {"value": seed.value, "compared": seed.compared}
            )
        objects = _typical_objects(stage, target, found, witnesses, proposals)
        method = receiver_spec(target, objects, stage.stdlib)
        if target.has_receiver:
            method["vouched"] = objects
        targets.append(
            {
                **method,
                "id": target.id,
                "path": target.path,
                "name": target.name,
                "async": target.is_async,
                "module_candidates": list(target.module_candidates),
                "properties": [p.spec() for p in mine],
                "examples": examples,
                "replay": _replay(stage.violations, target.id),
                "candidates": candidates,
                "strategies": proposals.strategies.get(target.id, {}),
                "witnesses": [
                    *(
                        {"id": w.id, "args": dict(w.args), "advisory": w.advisory}
                        for w in witnesses
                        if w.target == target.id
                    ),
                    *(
                        {"id": f"the docstring example {d.id}", "args": dict(d.example_args)}
                        for d in held
                        if d.target == target.id
                    ),
                ],
            }
        )
    return {
        "mode": "attack",
        "search_examples": SEARCH_EXAMPLES,
        "max_explicit": MAX_EXPLICIT,
        "backend": "hypothesis",
        "fixed": {p: sorted(lines) for p, lines in fixed.items()},
        "targets": targets,
    }


def _replay(violations: Sequence[Violation], tid: str) -> list[dict[str, str]]:
    """The inputs that broke a property of this target in an earlier round, for the next round to
    judge too, so one bug that two properties notice becomes one finding (plan P10). Taken in turn
    from each property (first found first), at most MAX_REPLAY."""
    by_prop: dict[str, list[Args]] = {}
    for v in violations:
        if v.target == tid and v.args is not None:
            by_prop.setdefault(v.prop, []).append(v.args)
    taken: dict[Args, None] = {}
    for column in itertools.zip_longest(*by_prop.values()):
        for args in column:
            if args is not None and len(taken) < MAX_REPLAY:
                taken.setdefault(args)
    return [dict(args) for args in taken]


def _record(stage: _Stage, events: Sequence[Mapping[str, Any]], owned: Collection[str]) -> None:
    """Fold one attack run's events into the stage (untrusted data, validated on the way). Only
    events about the run's own properties (`owned`) count: a run's report can't decide anything
    about a property it didn't run (verifier B1: code in a run could forge any line)."""
    last_end: dict[str, Mapping[str, Any]] = {}
    for event in events:
        kind = event.get("event")
        tid = str(event.get("target", ""))
        prop = event.get("property")
        if kind in ("violation", "contradicted", "advisory", "property_error", "held") and (
            not isinstance(prop, str) or prop not in owned
        ):
            continue
        assert prop is None or isinstance(prop, str)
        if kind == "target":
            if event.get("error"):
                stage.target_errors[tid] = str(event["error"])[:500]
            elif tid in stage.by_id and event.get("module") in _modules_of(stage.by_id[tid]):
                stage.modules[tid] = str(event["module"])
        elif kind == "violation":
            stage.order += 1
            found = violation_of(event, stage.order, stage.by_id, stage.stdlib)
            if found is not None:
                stage.violations.append(found)
        elif kind == "contradicted" and prop is not None:
            outcome = outcome_of(event.get("outcome"))
            shown = describe_outcome(outcome) if outcome else "an unexpected outcome"
            stage.contradicted.setdefault(
                prop,
                f"the project's test {str(event.get('witness'))[:200]} calls it "
                f"with {_input_text(event.get('args'))}, which {shown}",
            )
        elif kind == "held" and prop is not None:
            stage.held.add(prop)
        elif kind == "advisory" and prop is not None:
            stage.advisory.setdefault(prop, []).append(str(event.get("witness"))[:200])
        elif kind == "property_error" and prop is not None:
            stage.errors.setdefault(prop, str(event.get("error"))[:500])
        elif kind == "crash":
            outcome = outcome_of(event.get("outcome"))
            crashes = stage.crashes.setdefault(tid, [])
            if outcome and len(crashes) < 10:
                shown = describe_outcome(outcome, full=True)
                crashes.append((_input_text(event.get("args")), shown))
        elif kind == "note":
            stage.target_notes.setdefault(tid, []).append(str(event.get("note"))[:300])
        elif kind == "no_strategy":
            params = event.get("params")
            names = params if isinstance(params, list) else []
            stage.no_strategy[tid] = [str(n)[:100] for n in names[:MAX_NAMES_SHOWN]]
        elif kind == "end":
            last_end[tid] = event
        elif kind == "target_error":
            stage.target_errors[tid] = str(event.get("error"))[:500]
    for tid, end in last_end.items():
        _record_end(stage, tid, end)


def _record_end(stage: _Stage, tid: str, end: Mapping[str, Any]) -> None:
    """Add up what one run's last "end" event says about a target (each count is per run)."""
    stage.inputs[tid] = stage.inputs.get(tid, 0) + _int(end.get("inputs"))
    stage.unbuilt[tid] = stage.unbuilt.get(tid, 0) + _int(end.get("unbuilt"))
    stage.unfit[tid] = stage.unfit.get(tid, 0) + _int(end.get("unfit"))
    stage.oracle_errors[tid] = stage.oracle_errors.get(tid, 0) + _int(end.get("oracle_errors"))
    if end.get("first_unbuilt"):
        stage.first_unbuilt.setdefault(tid, str(end["first_unbuilt"])[:500])
        stage.first_unbuilt_brief.setdefault(tid, str(end.get("first_unbuilt_brief", ""))[:500])
    if end.get("first_oracle_error"):
        stage.first_oracle_error.setdefault(tid, str(end["first_oracle_error"])[:500])
    reached = end.get("reached")
    if isinstance(reached, dict):
        for path, lines in reached.items():
            if isinstance(lines, list):
                stage.reached.setdefault(tid, {}).setdefault(str(path), set()).update(
                    n for n in lines if isinstance(n, int)
                )


def _modules_of(target: AttackTarget) -> set[str]:
    """The dotted names a target's module may truthfully be reported under (verifier S1: the
    name goes into a repro file's import line)."""
    return {*target.module_candidates, *dotted_suffixes(target.path)}


def _int(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _input_text(args: object) -> str:
    if not isinstance(args, dict):
        return "an input"
    return ", ".join(
        f"{k}={v if isinstance(v, str) else '<not a literal>'}" for k, v in args.items()
    )[:300]


def describe_outcome(outcome: Mapping[str, str], *, full: bool = False) -> str:
    """An outcome in words. Without `full`, a raise is named by type only: exception messages can
    differ between Python versions, and this text goes into the follow-up prompt."""
    warned = outcome.get("warned")
    note = f" (with warnings ignored; {warned} would have raised)" if warned else ""
    if outcome.get("kind") == "raised":
        message = f": {outcome.get('message', '')[:200]}" if full and outcome.get("message") else ""
        return f"raises {outcome.get('type', '')}{message}{note}"
    return f"returns {outcome.get('repr', '')[:200]}{note}"


def _units(plan: Mapping[str, Any], tid: str) -> list[str]:
    """Every unit of a target's attack: its explicit inputs and one search per property."""
    target: Mapping[str, Any] = next(
        (t for t in plan["targets"] if t["id"] == tid), {"properties": []}
    )
    return ["explicit", *(f"search:{p['id']}" for p in target["properties"])]


def _resume(
    plan: dict[str, Any],
    events: Sequence[Mapping[str, Any]],
    stage: _Stage,
    resumes: dict[str, int],
) -> dict[str, Any] | None:
    """After a run that was killed (no "done"), the plan for the rest of it: finished units
    skipped, the input or search that hung skipped too (and noted, report only). A target that
    hung MAX_RESUMES times already is given up (verifier S6: one target must not starve the
    others) and marked incomplete. None if there is nothing to point at."""
    finished: dict[str, list[str]] = {}
    open_unit: dict[str, str] = {}
    calling: dict[str, Mapping[str, Any]] = {}
    for event in events:
        tid, unit = str(event.get("target", "")), str(event.get("unit", ""))
        if event.get("event") == "begin":
            open_unit[tid] = unit
        elif event.get("event") == "end":
            finished.setdefault(tid, []).append(unit)
            open_unit.pop(tid, None)
        elif event.get("event") == "calling":
            calling[tid] = event
    if not open_unit:
        return None  # killed between targets: nothing to point at
    tid, unit = next(iter(open_unit.items()))
    skip = {t: list(units) for t, units in plan.get("skip", {}).items()}
    for t, units in finished.items():
        skip.setdefault(t, []).extend(units)
    starts = dict(plan.get("explicit_from", {}))
    resumes[tid] = resumes.get(tid, 0) + 1
    if resumes[tid] > MAX_RESUMES:
        skip.setdefault(tid, []).extend(_units(plan, tid))
        stage.incomplete.add(tid)
        stage.hangs.setdefault(tid, []).append(
            f"gave up after {MAX_RESUMES} resumes: the rest of its attack did not run"
        )
    elif unit == "explicit" and tid in calling:
        index = _int(calling[tid].get("index"))
        starts[tid] = index + 1
        stage.hangs.setdefault(tid, []).append(
            f"the call with {str(calling[tid].get('input'))[:200]} did not return"
        )
    else:
        skip.setdefault(tid, []).append(unit)
        stage.hangs.setdefault(tid, []).append(f"the {unit} did not finish")
        if unit.startswith("search:"):
            stage.incomplete.add(tid)  # a whole search never ran: not "nothing found" (round 2)
    contradicted = {
        t["id"]: [p for p in stage.contradicted if p.startswith(t["id"] + ".")]
        for t in plan["targets"]
    }
    return {**plan, "skip": skip, "explicit_from": starts, "contradicted": contradicted}


def _attack(stage: _Stage, plan: dict[str, Any], label: str) -> None:
    """One attack, resumed after a hang (each target at most MAX_RESUMES times)."""
    owned = {p["id"] for t in plan["targets"] for p in t["properties"]}
    resumes: dict[str, int] = {}
    for attempt in range((MAX_RESUMES + 1) * len(plan["targets"]) + 1):
        name = label if attempt == 0 else f"{label} (resumed {attempt})"
        events, run = _harness(stage, stage.ws.head, "attack", plan, name, ATTACK_TIMEOUT_S)
        _record(stage, events, owned)
        done = sum(e.get("event") == "done" for e in events)
        if done and (done > 1 or run.outcome is not Outcome.PASSED):
            # A finished run ends with one "done" and a passing test. Anything else means code in
            # the run wrote the line itself (verifier round 2): nothing about it counts as done.
            stage.notes.append(f"{name} reported it finished but ended {run.outcome}: not trusted")
            stage.incomplete.update(t["id"] for t in plan["targets"])
            return
        if done:
            return
        resumed = None
        if run.outcome is Outcome.TIMEOUT:
            resumed = _resume(plan, events, stage, resumes)
        if resumed is None:
            stage.notes.append(f"{name} ended {run.outcome} before it finished: "
                               f"{_tail(run, stage.ws)}")  # fmt: skip
            stage.incomplete.update(t["id"] for t in plan["targets"])
            return
        plan = resumed


def _tail(run: RunResult, ws: Workspace) -> str:
    return sanitize(run.first.output, ws).strip()[-300:]


# --- confirmation ---------------------------------------------------------------------------------


def _same(a: Mapping[str, str] | None, b: Mapping[str, str] | None) -> bool:
    """Two outcome reports describe the same outcome (kind, type, and value or message)."""
    if a is None or b is None:
        return False
    keys = ("kind", "type", "repr") if a.get("kind") == "returned" else ("kind", "type", "message")
    return all(a.get(k) == b.get(k) for k in keys)


_NO_ATTRIBUTE = re.compile(r"'(\w+)' object has no attribute '(\w+)'")


def _finished_object(outcome: Mapping[str, str], owner: str, source: str) -> bool:
    """A method's `AttributeError` on what the object's class (the one the message names, if it is
    in the file; else the method's) deletes from itself: the cppheaderparser shape, where its
    constructor already finished the object."""
    found = _NO_ATTRIBUTE.fullmatch(outcome.get("message", ""))
    if found is None or not owner or outcome.get("type") != "AttributeError":
        return False
    tree = ast.parse(source)
    classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    return found[2] in deleted_attributes(tree, found[1] if found[1] in classes else owner)


def doubt_of(
    outcome: Mapping[str, str], base: Mapping[str, str] | None, owner: str, source: str
) -> Doubt | None:
    """Why this raise may be a false alarm, in a fixed word, from our runs and head's source: the
    first that applies (M11 S5). The word is measured and shown; the finding still counts. It is
    report only, so it can never cost a finding: any error reading the source gives no flag
    (verifier round 1 of M11, S4: a very deep expression made `ast` raise `RecursionError`)."""
    try:
        return _doubt(outcome, base, owner, source)
    except Exception:  # report only: the finding stands without a flag
        return None


def _doubt(
    outcome: Mapping[str, str], base: Mapping[str, str] | None, owner: str, source: str
) -> Doubt | None:
    if outcome.get("kind") != "raised":
        return None
    if outcome.get("errno") == "ENAMETOOLONG" or outcome.get("winerror") == WINDOWS_NAME_TOO_LONG:
        return "os_limit"
    if _finished_object(outcome, owner, source):
        return "finished_object"
    refusal = outcome.get("raised_by") == "raise" and outcome.get("in_project") == "yes"
    return "refused" if refusal and _same(outcome, base) else None


@dataclass(frozen=True)
class _Probed:
    """One probe run's answers: index -> its probe event, and whether the run finished."""

    events: Mapping[int, Mapping[str, Any]]
    finished: bool


def _probe(
    stage: _Stage,
    tree: Path,
    base: bool,
    calls: Sequence[tuple[AttackTarget, Args]],
    fixed: Mapping[str, frozenset[int]],
) -> _Probed:
    """One traced call per input, in `tree`."""
    targets, seen = [], set()
    renamed = {f.path: f.old_path for f in stage.scope.files if f.old_path}
    for target, _ in calls:
        if target.id not in seen:
            seen.add(target.id)
            path = renamed.get(target.path, target.path) if base else target.path
            codes = [receiver_of(args, target) for t, args in calls if t.id == target.id]
            method = receiver_spec(target, (c for c in codes if c is not None), stage.stdlib)
            targets.append({**method, "id": target.id, "path": path, "name": target.name,
                            "async": target.is_async,
                            "module_candidates": list(target.module_candidates)})  # fmt: skip
    plan = {
        "mode": "probe",
        "targets": targets,
        "fixed": {} if base else {p: sorted(lines) for p, lines in fixed.items()},
        "calls": [{"target": t.id, "args": dict(args)} for t, args in calls],
    }
    side = "before the fix" if base else "on the fixed code"
    events, run = _harness(stage, tree, "probe", plan, f"the probe {side}", PROBE_TIMEOUT_S)
    answers = {_int(e.get("index")): e for e in events if e.get("event") == "probe"}
    done = sum(e.get("event") == "done" for e in events)
    return _Probed(answers, done == 1 and run.outcome is Outcome.PASSED)


def expected_failure(
    run: RunResult, rel: str, types: frozenset[str], in_file: bool | None
) -> str | None:
    """None if the repro file failed the way it must; else why not."""
    if run.outcome is not Outcome.FAILED:
        return f"its run ended {run.outcome}, not with a failure"
    failures = run.first.failures
    if not failures or any(f.kind != "failure" for f in failures):
        return "it errored instead of failing"
    failure = failures[0]
    if types and failure.exc_type not in types:
        return f"it failed with {failure.exc_type}, not {' or '.join(sorted(types))}"
    if in_file is not None:
        file = (failure.location or "").rpartition(":")[0]
        here = file == rel or file.endswith("/" + PurePosixPath(rel).name) or file.endswith(rel)
        if here != in_file:
            where = "in the repro file" if in_file else "in the code under test"
            return f"it did not fail {where} ({failure.location})"
    return None


def _relation(
    base: Mapping[str, Any] | None,
    base_finished: bool,
    head_lines: Mapping[str, Sequence[int]],
    traced: bool,
    outcome: Mapping[str, str],
    import_lines: Mapping[str, frozenset[int]],
) -> tuple[bool, str]:
    """(pre-existing, relation to base). Pre-existing only if base gives the same outcome AND
    the failing call on head runs none of the fix's lines (SPEC 2.6, Decided in M1) AND the fix
    changed no module-level code (verifier S4: a changed constant or regex runs at import, so
    no call "runs" it, yet the call uses it)."""
    if base is None:
        if not base_finished:
            return (
                False,
                "the probe before the fix did not finish, so it can't be shown pre-existing",
            )
        return (
            False,
            "the probe before the fix gave nothing for it, so it can't be shown pre-existing",
        )
    base_outcome = outcome_of(base.get("outcome"))
    if base_outcome is None and base.get("unbuilt"):  # verifier round 1, N1
        unbuilt = str(base["unbuilt"])[:200]
        return False, f"new with the fix: before it, the object could not be built ({unbuilt})"
    if base_outcome is None:
        return False, "new with the fix: the function did not exist (or did not import) before it"
    if not _same(base_outcome, outcome):
        return (
            False,
            f"new with the fix: before it, this input {describe_outcome(base_outcome, full=True)}",
        )
    lines = sorted(n for ns in head_lines.values() for n in ns)
    if lines:
        shown = ", ".join(map(str, lines[:10]))
        return False, (
            f"the same before the fix, but the failing call runs the fix's line(s) "
            f"{shown}: the fix touched this path and left it broken"
        )
    changed = [
        f"{p} {', '.join(map(str, sorted(ns)[:5]))}" for p, ns in sorted(import_lines.items())
    ]
    if changed:
        return False, (
            "the same before the fix, but the fix changed module-level code that runs when the "
            f"module is imported ({'; '.join(changed)}), so it can't be shown untouched"
        )
    if not traced:
        return False, (
            "the same before the fix; line tracing was not available, so it can't be "
            "shown pre-existing and counts"
        )
    return True, "the same before the fix, and the failing call runs none of the fix's lines"


@dataclass
class _Confirmed:
    findings: list[Finding] = field(default_factory=list)
    pre_existing: list[Finding] = field(default_factory=list)
    discarded: list[Discarded] = field(default_factory=list)
    more: int = 0  # candidate groups left unchecked (past MAX_CONFIRM, or after MAX_SHOWN)
    unchecked: int = 0  # groups that could not be checked (no literal input, no head probe)


PRE_EXISTING = "pre-existing:"


@dataclass(frozen=True)
class _Member:
    """One input of a group, with what the two probes said about it."""

    violation: Violation
    head: Mapping[str, Any]
    base: Mapping[str, Any] | None


def _confirm(
    stage: _Stage,
    groups: Sequence[Group],
    fixed: Mapping[str, frozenset[int]],
    import_lines: Mapping[str, frozenset[int]],
) -> _Confirmed:
    """Prove the candidates with runs, best first. For each group, its representable inputs
    (the representative and up to MAX_OTHER_INPUTS others) are probed on head (the same outcome
    again) and on base. The first one that counts is proven by its repro file; only if none
    counts is a pre-existing one reported (verifier B3: one excused input must not hide the
    others)."""
    out = _Confirmed(more=max(0, len(groups) - MAX_CONFIRM))
    todo: list[tuple[Group, list[Violation]]] = []
    for g in groups[:MAX_CONFIRM]:
        members = [v for v in (g.representative, *g.others) if v.args is not None]
        if members:
            todo.append((g, members))
        else:
            out.discarded.append(Discarded(g.key[0], None, g.representative.prop,
                                           "its input cannot be written as code"))  # fmt: skip
            out.unchecked += 1
    if not todo:
        return out
    flat = [(stage.by_id[v.target], v.args or ()) for _, members in todo for v in members]
    head = _probe(stage, stage.ws.head, False, flat, fixed)
    base = _probe(stage, stage.ws.base, True, flat, fixed)
    index = 0
    for number, (group, members) in enumerate(todo):
        if len(out.findings) >= MAX_SHOWN:
            out.more += len(todo) - number
            break
        probed = []
        for v in members:
            probed.append(_Member(v, head.events.get(index, {}), base.events.get(index)))
            index += 1
        _confirm_group(stage, group, probed, head.finished, base.finished, import_lines, out)
    return out


def _own_import_lines(
    stage: _Stage, tid: str, import_lines: Mapping[str, frozenset[int]]
) -> dict[str, frozenset[int]]:
    """The module-level fix lines in the target's own file only: a constant changed elsewhere
    that the call uses, but whose change didn't alter the outcome, does not make an old failure
    the fix's (verifier round 2)."""
    own = stage.by_id[tid].path if tid in stage.by_id else ""
    return {p: ns for p, ns in import_lines.items() if p == own}


def _confirm_group(
    stage: _Stage,
    group: Group,
    members: Sequence[_Member],
    head_finished: bool,
    base_finished: bool,
    import_lines: Mapping[str, frozenset[int]],
    out: _Confirmed,
) -> None:
    counting: list[tuple[_Member, dict[str, str], str, dict[str, tuple[int, ...]]]] = []
    excused: list[tuple[_Member, dict[str, str], str, dict[str, tuple[int, ...]]]] = []
    problems: list[tuple[Violation, str, RunResult | None]] = []
    for m in members:
        v = m.violation
        fresh = outcome_of(m.head.get("outcome"))
        if fresh is None or not _same(fresh, v.outcome):
            if fresh is None and not head_finished:
                seen = "the probe on the fixed code did not finish"
            else:
                seen = "a fresh call " + (describe_outcome(fresh, full=True) if fresh
                                          else "gave nothing")  # fmt: skip
            saw = describe_outcome(v.outcome, full=True)
            problems.append((v, f"not reproducible: the attack saw it {saw}, {seen}", None))
            continue
        raw = m.head.get("lines")
        lines = {
            str(p): tuple(sorted(n for n in ns if isinstance(n, int)))
            for p, ns in (raw.items() if isinstance(raw, dict) else [])
            if isinstance(ns, list)
        }
        mine = _own_import_lines(stage, v.target, import_lines)
        pre, relation = _relation(m.base, base_finished, lines, m.head.get("traced") is True,
                                  fresh, mine)  # fmt: skip
        (excused if pre else counting).append((m, fresh, relation, lines))
    if not counting and not excused and not head_finished:
        out.unchecked += 1  # never compared with a fresh call: unknown, not "nothing"
    for m, fresh, relation, lines in counting[:MAX_PROVEN_PER_GROUP]:
        finding, problem, run = _prove(stage, group, m, fresh, relation, lines)
        if finding is not None:
            out.findings.append(finding)
            return
        problems.append((m.violation, problem, run))
    for m, fresh, relation, lines in excused[:1]:
        finding, problem, run = _prove(stage, group, m, fresh, f"{PRE_EXISTING} {relation}", lines)
        if finding is not None:
            if len(out.pre_existing) < MAX_PRE_EXISTING:
                out.pre_existing.append(finding)
            return
        problems.append((m.violation, problem, run))
    if problems:
        v, problem, run = problems[0]
        out.discarded.append(Discarded(v.target, v.args, v.prop, problem, run))
    if any(r is not None and r.outcome is not Outcome.PASSED for _, _, r in problems):
        # A repro file that errored, timed out or failed the wrong way proves nothing either way
        # (only one that passes shows the candidate was wrong): not "nothing found" (round 4).
        out.unchecked += 1


def _prove(
    stage: _Stage,
    group: Group,
    member: _Member,
    fresh: dict[str, str],
    relation: str,
    lines: Mapping[str, tuple[int, ...]],
) -> tuple[Finding | None, str, RunResult | None]:
    """(the finding, "", its repro run) if its repro file fails on head the way the finding
    says, else (None, why not, the run)."""
    v = member.violation
    assert v.args is not None
    if v.outcome.get("warned"):  # a relation's second call warned: the probe can't know (M11 S4)
        fresh = {"warned": v.outcome["warned"], **fresh}
    target = stage.by_id[v.target]
    module = stage.modules.get(v.target, target.module_candidates[0])
    stage.numbers += 1
    number = stage.numbers
    prop = stage.properties[v.prop]
    try:
        repro = render_finding(number, module, target, prop, v.args, fresh, stage.stdlib)
    except ValueError as exc:
        return None, f"no repro file could be written: {exc}", None
    rel = placed(stage.ws, f"test_tracefix_finding_{number}.py")
    run = _run_file(stage, stage.ws.head, rel, repro.code, f"the repro file of finding {number}",
                    FINDING_TIMEOUT_S, FINDING_RERUNS)  # fmt: skip
    problem = expected_failure(run, rel, repro.expect.types, repro.expect.in_file)
    if problem is not None:
        return None, f"its repro file {problem}", run
    # What else the proven input breaks is known only for the representative (verifier round 2).
    also = tuple(
        stage.properties[p].name
        for p in (group.properties[1:] if member.violation is group.representative else ())
        if p in stage.properties
    )
    others = tuple(o.args for o in (group.representative, *group.others) if o is not v)
    base_outcome = outcome_of(member.base.get("outcome")) if member.base else None
    finding = Finding(
        number,
        f"{module}.{target.qualname}",
        v.target,
        v.args,
        dict(fresh),
        v.expected,
        _result_of(stage, prop),
        also,
        others[:3],
        v.phase,
        base_outcome,
        tuple((p, ns) for p, ns in sorted(lines.items()) if ns),
        relation,
        rel,
        repro.code,
        run,
        target.path,
        _first_line(target, lines),
        repro.expect,
        doubt_of(
            fresh,
            base_outcome,
            target.owner,
            blob_text(stage.ws.repo, stage.ws.head_sha, target.path) or "",
        ),
    )
    return finding, "", run


def _first_line(target: AttackTarget, lines: Mapping[str, tuple[int, ...]]) -> int:
    """Where a finding points: the first fix line the failing call ran in the target's own file,
    else the target's first line."""
    ran = [n for n in lines.get(target.path, ()) if n >= 1]
    return min(ran) if ran else target.span[0]


# --- results --------------------------------------------------------------------------------------


def _result_of(stage: _Stage, prop: CheckedProperty) -> PropertyResult:
    if prop.id in stage.contradicted:
        status, reason = "contradicted", stage.contradicted[prop.id]
    elif prop.id in stage.errors:
        status, reason = "error", stage.errors[prop.id]
    else:
        status, reason = "counted", ""
    return PropertyResult(
        prop.id,
        prop.target,
        prop.name,
        prop.kind,
        prop.claim,
        prop.source,
        prop.quote,
        status,
        reason,
        prop.constrains_result,
        prop.origin,
        tuple(stage.advisory.get(prop.id, ())),
    )


def _counted(stage: _Stage) -> set[str]:
    return {
        pid for pid in stage.properties if pid not in stage.contradicted and pid not in stage.errors
    }


def _type_only(detail: str) -> str:
    """ "KeyError: 31337" -> "KeyError": an error's type without its message."""
    name = detail.split(":", 1)[0].strip()
    return name if name.isidentifier() else ""


def no_input_reason(stage: _Stage, tid: str, *, for_model: bool = False) -> str:
    """Why a target ran no input, in fixed words: the first that applies (M11 S3, NOTES 33). Harness
    facts only, for the receipt and the follow-up; nothing decides on it. `for_model` keeps only an
    error's type: its message comes from running head, and the adversary never sees an attack
    result (SPEC 2.6; verifier round 1, S2)."""
    target = stage.by_id[tid]
    if tid in stage.target_errors:
        return stage.target_errors[tid]
    mine = {p.id for p in stage.properties.values() if p.target == tid}
    if not mine:
        return "no property to check it against"
    if tid in stage.incomplete:
        return "its attack did not finish"
    if not mine & _counted(stage):
        return "every property was contradicted or could not run"
    missing = stage.no_strategy.get(tid, [])
    if stage.unbuilt.get(tid):
        # MILESTONES M7.5: a class that needs I/O or setup to build is skipped with a reason.
        # Verifier round 1, N5: some objects may have built but met no property.
        first = (stage.first_unbuilt_brief if for_model else stage.first_unbuilt).get(tid)
        return (
            f"nothing was judged, and {stage.unbuilt[tid]} object(s) of {target.owner} could not "
            f"be built here{f' ({first})' if first else ''}"
        )
    if RECEIVER in missing and target.owner:  # a plain function's parameter may be named `self`
        return f"no object of {target.owner} was built: none was given, and no type hints make one"
    if missing:
        return f"no strategy for {', '.join(missing)}"
    if stage.unfit.get(tid):
        return f"no input fits any `when` ({stage.unfit[tid]} inputs fit none)"
    if stage.oracle_errors.get(tid):
        first = stage.first_oracle_error.get(tid, "")
        first = _type_only(first) if for_model else first
        return f"the property expressions failed on every input{f' ({first})' if first else ''}"
    return "nothing generated"


def _reports(stage: _Stage) -> tuple[TargetReport, ...]:
    out = []
    for t in stage.targets:
        attacked = t.id in stage.inputs and t.id not in stage.target_errors
        reason = stage.target_errors.get(t.id, "")
        if not reason and not stage.inputs.get(t.id):
            reason = no_input_reason(stage, t.id)
        reached = tuple(
            (p, tuple(sorted(ns))) for p, ns in sorted(stage.reached.get(t.id, {}).items())
        )
        out.append(
            TargetReport(
                t.id,
                f"{stage.modules.get(t.id, t.module_candidates[0])}.{t.qualname}",
                t.path,
                t.via,
                stage.modules.get(t.id),
                attacked,
                reason,
                stage.inputs.get(t.id, 0),
                stage.oracle_errors.get(t.id, 0),
                reached,
                tuple(stage.crashes.get(t.id, ())),
                tuple(stage.hangs.get(t.id, ())),
                tuple(stage.target_notes.get(t.id, ())),
                t.id not in stage.incomplete,
            )
        )
    return tuple(out)


def _fix_lines(
    stage: _Stage, fixed: Mapping[str, frozenset[int]]
) -> tuple[tuple[str, tuple[int, ...]], ...]:
    """The fix's lines that a call can run (inside function bodies), per file."""
    out = []
    for path, lines in sorted(fixed.items()):
        text = blob_text(stage.ws.repo, stage.ws.head_sha, path)
        if text is not None:
            body = executable_lines(text, path, bodies_only=True) & lines
            if body:
                out.append((path, tuple(sorted(body))))
    return tuple(out)


def _status(confirmed: _Confirmed, stage: _Stage) -> tuple[AttackStatus, str]:
    tried = sum(stage.inputs.values())
    counted = _counted(stage)
    if confirmed.findings:
        return (
            AttackStatus.FOUND,
            f"{len(confirmed.findings)} finding(s), each proven by a failing repro file",
        )
    # "Nothing found" must mean it: not while candidates went unchecked (verifier S5) or an
    # attack never finished (S6).
    if confirmed.more:
        return AttackStatus.INCONCLUSIVE, (
            f"no candidate checked counts, but {confirmed.more} more were not checked"
        )
    if confirmed.unchecked:
        return AttackStatus.INCONCLUSIVE, (
            f"no candidate checked counts, but {confirmed.unchecked} could not be checked"
        )
    if stage.incomplete:
        names = ", ".join(
            stage.by_id[t].qualname for t in sorted(stage.incomplete) if t in stage.by_id
        )
        return AttackStatus.INCONCLUSIVE, f"the attack on {names} did not finish"
    if counted and tried:
        return AttackStatus.NONE_FOUND, (
            f"no counterexample found in {tried} inputs against {len(counted)} properties"
        )
    if not stage.properties:
        return AttackStatus.INCONCLUSIVE, "no property to check the fixed code against"
    if stage.target_errors and not tried:
        first = next(iter(stage.target_errors.values()))
        return AttackStatus.INCONCLUSIVE, f"no target could be attacked: {first}"
    if not counted:
        return AttackStatus.INCONCLUSIVE, "every property was contradicted or could not run"
    return AttackStatus.INCONCLUSIVE, "the attack ran no input"


def _import_lines(stage: _Stage, fixed: Mapping[str, frozenset[int]]) -> dict[str, frozenset[int]]:
    """The fix's lines that compute values when a module is imported (constants, regexes,
    defaults, decorators), not inside a call: a call uses them without "running" them (verifier
    S4). Imports, `def` lines and docstrings are not among them (verifier round 2)."""
    out = {}
    for path, lines in fixed.items():
        text = blob_text(stage.ws.repo, stage.ws.head_sha, path)
        if text is None:
            continue
        changed = import_time_value_lines(text) & lines
        if changed and not _only_unused_defs_removed(stage.ws, path, text):
            out[path] = changed
    return out


def _only_unused_defs_removed(ws: Workspace, path: str, head: str) -> bool:
    """True if all the fix changed in this file at import time is functions removed (marked by
    decorators only, linetrace.removed_marked_defs) that no source file at head names, and the
    file reads no namespace dynamically: then no value a call can use changed at import, and
    the lines either side of a removal are not a reason to count an old failure (M11 early,
    twyn-317). Anything else, or any doubt, keeps the old rule."""
    base = blob_text(ws.repo, ws.base_sha, path)
    names = removed_marked_defs(base, head) if base is not None else frozenset()
    if not names or dynamic_lookup(head):
        return False
    return not any(_named_in_source(ws, name) for name in sorted(names))


def _named_in_source(ws: Workspace, name: str) -> bool:
    """Does any non-test .py file at head use `name` as a word? True if git can't tell."""
    try:
        run = git_run(ws.repo, "grep", "-l", "-w", "-F", "-e", name, ws.head_sha, "--", "*.py")
    except WorkspaceError:
        return True
    if run.returncode == 1:
        return False
    if run.returncode != 0:
        return True
    prefix = f"{ws.head_sha}:"
    files = run.stdout.decode("utf-8", errors="replace").splitlines()
    return any(classify(f.removeprefix(prefix)) is not FileKind.TEST for f in files)


def break_my_fix(
    ws: Workspace,
    scope: DiffScope,
    repro: ReproResult | None,
    issue: str,
    client: LLMClient,
    guard: GuardResult | None = None,
) -> AttackResult:
    """Attack the fixed code (SPEC 2.6). Runs whatever the Reproducer found; never raises for
    problems in the repo."""
    level = sandbox_level()
    warnings = ((BASIC_WARNING,) if level == "basic" else ()) + tuple(ws.notes)
    targets, skipped, notes = select_targets(ws, scope)
    if not targets:
        reason = "the fix changes no function Break My Fix can call"
        if skipped:
            reason += f" ({'; '.join(f'{s.function}: {s.reason}' for s in skipped[:3])})"
        return AttackResult(
            AttackStatus.SKIPPED,
            reason,
            skipped=tuple(skipped),
            isolation=level,
            warnings=warnings,
            notes=tuple(notes),
        )
    problem = ws.settings.python.hypothesis_problem()
    if problem is not None:  # before any model call: nothing could run what it proposes
        return AttackResult(
            AttackStatus.INCONCLUSIVE,
            f"Break My Fix can't run in the project's Python: {problem}",
            skipped=tuple(skipped),
            isolation=level,
            warnings=warnings,
            notes=tuple(notes),
        )
    stage = _Stage(ws, scope, targets, notes=list(notes))
    fixed = fixed_by_file(ws, scope)
    confirmed = _Confirmed()
    error = None
    try:
        _attack_all(stage, issue, client, guard, fixed, repro)
        groups = group_violations(stage.violations, _counted(stage))
        if groups:
            confirmed = _confirm(stage, groups, fixed, _import_lines(stage, fixed))
    except TamperingDetected as exc:
        # Never a verdict: the stage is invalid, whatever the runs said (Decided in M3.5).
        return AttackResult(
            AttackStatus.INVALID,
            f"during {stage.phase}: {exc}",
            properties=_all_results(stage),
            targets=_reports(stage),
            skipped=tuple(skipped),
            runs=tuple(stage.runs),
            isolation=level,
            warnings=warnings,
            notes=tuple(stage.notes),
        )
    except (OSError, WorkspaceError, RecursionError) as exc:
        error = f"Break My Fix could not finish {stage.phase}: {type(exc).__name__}: {exc}"
        stage.notes.append(error)
    status, reason = _status(confirmed, stage)
    if error is not None and status is not AttackStatus.FOUND:
        status, reason = AttackStatus.INCONCLUSIVE, error  # a finding proven before it stands
    return AttackResult(
        status,
        reason,
        tuple(confirmed.findings),
        confirmed.more,
        tuple(confirmed.pre_existing),
        tuple(confirmed.discarded),
        _all_results(stage),
        _reports(stage),
        tuple(skipped),
        _fix_lines(stage, fixed),
        tuple(stage.runs),
        level,
        warnings,
        tuple(stage.notes),
    )


def _all_results(stage: _Stage) -> tuple[PropertyResult, ...]:
    return (*(_result_of(stage, p) for p in stage.properties.values()), *stage.results)


def _run_problems(
    stage: _Stage, contradicted_before: set[str], errors_before: set[str]
) -> list[str]:
    """What the last attack run showed about the model's own properties: the ones the project's
    tests contradicted, and the ones that could not run here, as lines for the follow-up."""
    lines = []
    for pid in sorted(set(stage.contradicted) - contradicted_before):
        prop = stage.properties[pid]
        if prop.origin == "model":
            lines.append(
                f"property {prop.name!r} of {prop.target}: contradicted: {stage.contradicted[pid]}"
            )
    for pid in sorted(set(stage.errors) - errors_before):
        prop = stage.properties[pid]
        if prop.origin == "model":
            lines.append(
                f"property {prop.name!r} of {prop.target}: could not run: {stage.errors[pid]}"
            )
    return lines


def _ran_nothing(stage: _Stage, counted: Collection[str]) -> list[str]:
    """The targets a corrected answer could still help: they load, the model has a property that
    counts on them, the run finished, and no input was judged (M11 S3)."""
    return [
        t.id
        for t in stage.targets
        if t.id in counted
        and t.id not in stage.target_errors
        and t.id not in stage.incomplete
        and not stage.inputs.get(t.id)
    ]


def _offered(proposals: _Proposals, tids: Sequence[str]) -> list[object]:
    """What the model has given for these targets to run on, to see whether an answer changed it."""
    return [
        (dict(proposals.strategies.get(t, {})), list(proposals.examples.get(t, []))) for t in tids
    ]


def _to_run_again(
    stage: _Stage,
    tids: Sequence[str],
    before: Sequence[object],
    proposals: _Proposals,
    new: Sequence[CheckedProperty],
) -> list[CheckedProperty]:
    """The counted model properties (not the `new` ones) of each target that ran nothing and now
    has something new to run on. They come back from the model as repeats, which are dropped, so
    without this a corrected object or strategy would never be used."""
    counted = _counted(stage)
    fresh = {p.id for p in new}
    offered = zip(tids, before, _offered(proposals, tids), strict=True)
    changed = {t for t, old, now in offered if old != now}
    return [
        p
        for p in stage.properties.values()
        if p.target in changed and p.origin == "model" and p.id in counted and p.id not in fresh
    ]


def _attack_all(
    stage: _Stage,
    issue: str,
    client: LLMClient,
    guard: GuardResult | None,
    fixed: Mapping[str, frozenset[int]],
    repro: ReproResult | None,
) -> None:
    ws = stage.ws
    issue = issue.replace("\r\n", "\n").strip()  # the same prompt on every OS
    stage.phase = "the search for witnesses"
    witnesses = _passing(stage, witness_calls(ws, stage.scope, stage.targets, repro))
    docs = readme(ws)
    tests = _tests_text(ws, witnesses)
    stdlib = frozenset(STDLIB_MODULES) - shadowed_stdlib(ws.pristine[ws.head])
    stage.stdlib = stdlib
    evidence = {t.id: evidence_texts(t, issue, docs, tests) for t in stage.targets}
    seeds = {}
    for t in stage.targets:
        head = blob_text(ws.repo, ws.head_sha, t.path) or ""
        seeds[t.id] = seeds_for(t, head, fixed, issue, repro, survivors_in(guard, t.path))
        for n, example in enumerate(doc_examples(t), 1):
            prop = doc_property(example, f"{t.id}.doc{n}")
            stage.properties[prop.id] = prop
    proposals = _Proposals()
    held = _docstring_examples(stage, proposals, seeds, witnesses, fixed)
    request = adversary.render_request(_context(stage, issue, docs, tests, stdlib))
    history = [Message("user", request)]
    pending: list[CheckedProperty] = []
    errors_before: set[str] = set()
    retrying: list[str] = []
    for call in range(ADVERSARY_CALLS):
        stage.phase = "the adversary"
        try:
            plan = client.complete("adversary", adversary.SYSTEM, history, adversary.AttackPlan)
        except (BudgetExceeded, LLMOutputError, LLMProviderError) as exc:
            stage.notes.append(f"the adversary stopped early: {exc}")
            break
        history.append(Message("assistant", plan.model_dump_json()))
        offered = _offered(proposals, retrying)
        new, rejections = _accept(stage, plan, proposals, evidence, stdlib, retrying)
        pending += new + _to_run_again(stage, retrying, offered, proposals, new)
        before = set(stage.contradicted)
        if pending:
            label = "the attack" if call == 0 else f"the attack, round {call + 1}"
            _attack(stage, _plan(stage, pending, proposals, seeds, witnesses, fixed, held), label)
            pending = []
        # The model hears only about its own properties: a docstring example is not its to fix.
        problems = _run_problems(stage, before, errors_before)
        errors_before = set(stage.errors)
        counted = {
            stage.properties[p].target
            for p in _counted(stage)
            if stage.properties[p].origin == "model"
        }
        reachable = [t for t in stage.targets if t.id not in stage.target_errors]
        uncovered = [t.id for t in reachable if t.id not in counted]
        retrying = _ran_nothing(stage, counted)
        if call == ADVERSARY_CALLS - 1 or not reachable:
            break  # no target imports: another call can't help
        if not (rejections or problems or uncovered or retrying):
            break
        no_input = [
            sanitize(f"{t}: {no_input_reason(stage, t, for_model=True)}", ws) for t in retrying
        ]
        history.append(
            Message("user", adversary.render_feedback(rejections + problems, uncovered, no_input))
        )
    if ADVERSARY_SAMPLES > 1 and any(t.id not in stage.target_errors for t in stage.targets):
        _second_sample(stage, client, request, proposals, evidence, stdlib, seeds, witnesses,
                       fixed, held)  # fmt: skip


def _second_sample(
    stage: _Stage,
    client: LLMClient,
    request: str,
    proposals: _Proposals,
    evidence: Mapping[str, Mapping[Any, Sequence[str]]],
    stdlib: frozenset[str],
    seeds: Mapping[str, Seeds],
    witnesses: Sequence[WitnessCall],
    fixed: Mapping[str, frozenset[int]],
    held: Sequence[CheckedProperty],
) -> None:
    """One more, independent answer to the same request, from a fresh conversation; its new
    properties go through the same checks and are attacked in one more run. Optional: any model
    error only adds a note."""
    stage.phase = "the adversary's second sample"
    messages = [Message("user", f"{request}\n\n{adversary.SECOND_SAMPLE}")]
    try:
        plan = client.complete("adversary", adversary.SYSTEM, messages, adversary.AttackPlan)
    except LLMError as exc:
        stage.notes.append(f"the adversary's second sample is missing: {exc}")
        return
    new, _ = _accept(stage, plan, proposals, evidence, stdlib)
    if new:
        _attack(stage, _plan(stage, new, proposals, seeds, witnesses, fixed, held),
                "the attack, second sample")  # fmt: skip


def _docstring_examples(
    stage: _Stage,
    proposals: _Proposals,
    seeds: Mapping[str, Seeds],
    witnesses: Sequence[WitnessCall],
    fixed: Mapping[str, frozenset[int]],
) -> list[CheckedProperty]:
    """Run the docstring examples on their own, with no model code in the run (verifier B1: a
    model expression must never be able to touch a model-free finding). Their own inputs and the
    witnesses only. The ones that held come back, to be witnesses for the model's properties."""
    examples = [p for p in stage.properties.values() if p.origin == "docstring"]
    if not examples:
        return []
    plan = _plan(stage, examples, proposals, seeds, witnesses, fixed)
    plan["max_explicit"] = 0
    _attack(stage, plan, "the docstring examples")
    out = {v.prop for v in stage.violations} | set(stage.contradicted) | set(stage.errors)
    return [p for p in examples if p.id in stage.held and p.id not in out]

"""receipt.json, schema v1 (SPEC 2.8, plan P12): the Fix Receipt, built from stage results only.

`build` fills the models from a `RunRecord` and the ladder's level; nothing here reads model text
to decide anything (the Judge's labels and notes are shown beside the facts, never instead of
them). Every string is masked on the way out (`mask_paths`, the repo as `<repo>`), so no path of
this machine leaves it. `docs/receipt.schema.json` is generated from these models
(`scripts/receipt_schema.py`); a test keeps it current.
"""

from __future__ import annotations

import hashlib
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import fields, is_dataclass
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict

from tracefix import __version__
from tracefix.attack import AttackResult, Doubt, Finding, PropertyResult, describe_outcome
from tracefix.attack_inputs import Args
from tracefix.attack_rules import Expectation
from tracefix.behaviour_diff import BehaviourResult, SurvivorCheck
from tracefix.behaviour_rules import UNOBSERVED, ChangeGroup, Kind, Seen, describe, shown_side
from tracefix.envcheck import OriginCheck
from tracefix.guard import GuardResult, MutantResult, MutantStatus
from tracefix.integrity import IntegrityResult
from tracefix.interpreter import Interpreter
from tracefix.judge import JudgeSummary, Label, ascii_only
from tracefix.ladder import EvidenceLevel, Rung, level
from tracefix.linetrace import FixLineCoverage
from tracefix.llm import PRICES_PER_MTOK, Problem, ProblemKind, cost_usd
from tracefix.mutation_rules import KINDS
from tracefix.previous import PreviousResult, Replay, StillOpen, file_name
from tracefix.prompts.judge import SummaryFacts
from tracefix.record import BLIND, PREVIOUS, RunRecord, RunStatus, StageRecord, planned
from tracefix.regressions import RegressionResult
from tracefix.repro import BLIND_FILE, BlindResult, ReproResult, ReproStatus, mask_paths
from tracefix.runner import EnvironmentCheck, RunResult
from tracefix.sandbox import BASIC_WARNING
from tracefix.workspace import Workspace

SCHEMA_VERSION: Literal[1] = 1
MAX_COMMANDS = 20  # distinct commands listed per stage
MAX_EDIT_CHARS = 200  # a mutant's original and replacement text
MAX_DIFF_LINES = 30  # a mutant's diff (big body mutants)
MAX_EXAMPLES = 3  # inputs shown per behaviour change group
TITLE_CHARS = 120
COST_LABEL = "estimate at list prices"
MAX_FACTS = 10  # findings, flags and behaviour changes each, in the Judge's summary request
FACT_CHARS = 300
_NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")  # counts and line numbers vary between machines
_ADDRESS = re.compile(r"\b0x[0-9a-fA-F]{6,}\b")  # an object's memory address
# SPEC 2.8: never checked by any stage.
NOT_CHECKED = (
    "concurrency",
    "database state",
    "network and external services",
    "authentication and authorisation",
    "performance",
    "configuration",
)
# Why a model call failed, in fixed words (llm.ProblemKind); never from model text.
PROBLEM_WORDS: dict[ProblemKind, str] = {
    "no_credentials": "no Anthropic API credentials were found (API key, auth token or login)",
    "auth": "the API rejected the credentials",
    "billing": "the API account has a billing problem, e.g. no credit left",
    "permission": "the API account may not use this model or feature",
    "model_unavailable": "the model is not available to this API account",
    "rate_limit": "the API account's rate limit was reached",
    "api_unavailable": "the API was failing or overloaded",
    "network": "the API could not be reached, or the call timed out",
    "rejected": "the API rejected Tracefix's request",
    "budget": "Tracefix's model call limit or token budget for this run was used up",
    "refusal": "the model declined the request",
    "invalid_output": "the model's answer did not match the expected format, even after a retry",
    "missing_recording": "no recorded model answer for this request (tests only)",
    "other": "the model call failed",
}
UNOBSERVED_PREFIX = "not observed by the behaviour diff: "
NOT_THE_FIX = "this stage's evidence is lower because of that, not because of the fix"

Value = str | int | float | bool | list[str] | None


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Ref(_Model):
    ref: str
    sha: str


class RepoInfo(_Model):
    name: str


class IssueInfo(_Model):
    title: str  # the issue's first line
    sha256: str  # of the whole issue text (UTF-8)


class IsolationInfo(_Model):
    level: Literal["strict", "basic"]
    why: str
    warning: str | None = None  # the basic-isolation warning, when it applies
    python: str | None = None  # the project's Python version (--python), when it isn't Tracefix's


class Summary(_Model):
    text: str
    by: Literal["judge", "tracefix"]  # judge: advisory words; tracefix: our own "why this level"


class ModelProblem(_Model):
    stage: str  # the stage it hurt ("summary": the receipt's own call)
    role: str
    model: str
    kind: str
    status: int | None
    words: str  # fixed wording of `kind`
    detail: str  # the exception's own text, masked: shown, never decides anything


class StageEntry(_Model):
    name: str
    status: str
    reason: str
    duration_s: float
    commands: list[str]
    problems: list[ModelProblem]
    error: str | None  # Tracefix's own code raised: a bug, and no evidence from this stage
    evidence: dict[str, Value]  # the stage's key numbers


class PropertyInfo(_Model):
    id: str
    name: str
    kind: str
    claim: str
    source: str
    quote: str
    origin: str  # model | docstring


class Expect(_Model):
    """The failure a finding's file must end with on head: one of `types` (empty: any test
    failure), raised inside the file (True), outside it (False) or anywhere (None)."""

    types: list[str]
    in_file: bool | None


class FindingEntry(_Model):
    number: int
    function: str
    call: str
    input: dict[str, str]  # parameter -> literal
    outcome: str  # what the fixed code did
    base_outcome: str | None  # what the code before the fix did (None: no such function)
    expected: str | None
    property: PropertyInfo | None
    also_violates: list[str]
    other_inputs: int  # more inputs that break it the same way
    relation: str
    file: str | None  # the standalone pytest file beside the receipt
    # Added in M9 (optional, so earlier v1 receipts still validate):
    path: str | None = None  # the attacked function's repo-relative file
    line: int | None = None  # the first fix line the failing call ran there, else the def's
    expect: Expect | None = None
    # Added in M11 (optional): why this may be a false alarm. Report only: it still counts.
    doubt: Doubt | None = None


class AttackTargetEntry(_Model):
    """One function Break My Fix set out to attack, and how many inputs it ran against it
    (M11; facts from our own runs, report only: it sets no level)."""

    function: str  # dotted: module.qualname
    path: str  # its repo-relative file
    via: str  # set for a public caller attacked on behalf of a changed private function
    attacked: bool
    inputs_tried: int
    finished: bool  # False: its attack never finished (it hung too often, or a run broke)
    reason: str  # why it was not attacked, or nothing was judged ("" when it was)


class Example(_Model):
    call: str
    before: str
    after: str


class ChangeLabel(_Model):
    change: str  # c1, c2, ...
    label: str  # the Judge's: intended | suspicious (it can only keep L3 out of reach)
    reason: str


class BehaviourChange(_Model):
    function: str
    kind: str
    count: int
    before: str
    after: str
    explained: list[str]  # what explains it, found by our own code
    contradicts: list[str]  # documented promises it breaks
    labels: list[ChangeLabel]
    examples: list[Example]


class IntegrityFlagEntry(_Model):
    id: str  # f1, f2, ...
    kind: str
    file: str
    line: int
    test: str | None
    detail: str
    evidence: str
    note: str | None = None  # the Judge's one line beside it (it never removes a flag)


class RegressionEntry(_Model):
    file: str
    test: str | None  # None: the whole file no longer collects
    evidence: str
    line: int | None = None  # the test's def line at head (added in M9, optional)


class SurvivorExample(_Model):
    call: str
    fix: str  # what the fixed code gives
    mutant: str  # what the changed code gives


class Survivor(_Model):
    """A change to the fixed code that no test noticed (a Guard mutant that survived)."""

    id: str  # stable: the same edit has the same id in every run
    origin: str  # model | rule
    file: str
    line: int
    original: str
    replacement: str
    description: str
    diff: str
    words: str
    check: str  # differs | no_difference_found | not_checked (behaviour diff, report only)
    examples: list[SurvivorExample]
    # Added in M11 (optional, so earlier v1 receipts still validate):
    kind: str | None = None  # a rule mutant's kind (mutation_rules.KINDS); None for the model's


class CoverageSet(_Model):
    name: str
    ran: int
    total: int


class FixLineCoverageEntry(_Model):
    lines: dict[str, list[int]]  # executable fix lines, per file
    sets: list[CoverageSet]
    notes: list[str]


class Cost(_Model):
    usd: float | None
    label: str


class LLMSettings(_Model):
    models: dict[str, str]
    effort: str
    max_tokens: int
    max_calls: int
    token_budget: int


class LLMUse(_Model):
    calls: int
    input_tokens: int
    output_tokens: int
    cost_estimate: Cost
    settings: LLMSettings
    problems: list[ModelProblem]


class ReplayedFinding(_Model):
    number: int
    call: str
    file: str
    result: Replay
    detail: str
    path: str | None = None  # the last receipt's place for it (its commit's lines)
    line: int | None = None
    carried: bool = False  # an earlier finding the last receipt carried (still open there)


class OpenFinding(_Model):
    """An old finding no run has shown fixed yet: the next run replays its file."""

    number: int
    call: str
    file: str  # findings/previous_<number>.py beside this receipt
    expect: Expect | None
    path: str | None = None
    line: int | None = None


class PreviousInfo(_Model):
    """The last receipt's findings, run again on this commit (`--previous`, added in M9), and
    the old findings still open after this run (carried, so the next run replays them)."""

    head_sha: str  # the last receipt's commit ("" when it could not be read)
    level: EvidenceLevel | None  # the last receipt's level (None when it could not be read)
    created_at: str
    findings: list[ReplayedFinding]
    still_open: list[OpenFinding]  # carried: the next run replays them too
    still_open_known: bool  # False: the next run can't know which are open (inconclusive)


class Tampering(_Model):
    stage: str
    detail: str


class Receipt(_Model):
    """A Fix Receipt, schema v1: what Tracefix's own runs showed about one bug fix. `level` is
    computed by Tracefix's code from the stages' results; model text never sets it."""

    schema_version: Literal[1]
    tracefix_version: str
    created_at: str
    status: RunStatus
    status_reason: str
    level: EvidenceLevel
    level_reasons: list[str]
    repo: RepoInfo
    base: Ref
    head: Ref
    issue: IssueInfo
    isolation: IsolationInfo
    summary: Summary
    stages: list[StageEntry]
    findings: list[FindingEntry]
    pre_existing: list[FindingEntry]
    behaviour_changes: list[BehaviourChange]
    integrity_flags: list[IntegrityFlagEntry]
    regressions: list[RegressionEntry]
    survivors: list[Survivor]
    fix_line_coverage: FixLineCoverageEntry | None
    unchecked: list[str]
    llm: LLMUse
    tampering: list[Tampering]
    warnings: list[str]
    notes: list[str]
    previous: PreviousInfo | None = None  # added in M9 (optional, so earlier v1 receipts validate)
    # Added in M11 (optional, so earlier v1 receipts validate): Break My Fix's targets and the
    # inputs run against each; None when the stage left no result.
    attack_targets: list[AttackTargetEntry] | None = None


# --- files beside the receipt ---------------------------------------------------------------------


def repro_file(repro: ReproResult) -> str:
    return f"repro/{PurePosixPath(repro.test_path).name}"


BLIND_TEST_FILE = f"repro/{BLIND_FILE}"


def finding_file(finding: Finding) -> str:
    return f"findings/finding_{finding.number}.py"


# --- stages ---------------------------------------------------------------------------------------


def _runs(value: object, out: list[RunResult]) -> None:
    """Every RunResult inside a stage result (results are trees of frozen dataclasses)."""
    if isinstance(value, RunResult):
        out.append(value)
    elif is_dataclass(value) and not isinstance(value, type):
        for f in fields(value):
            _runs(getattr(value, f.name), out)
    elif isinstance(value, tuple | list):
        for item in value:
            _runs(item, out)


def _commands(result: object, python: Interpreter | None = None) -> list[str]:
    runs: list[RunResult] = []
    _runs(result, runs)
    texts = []
    pythons = {sys.executable, *([python.executable] if python is not None else [])}
    for run in runs:
        command = list(run.command)
        if command and command[0] in pythons:
            command[0] = "python"
        texts.append(" ".join(command))
    distinct = list(dict.fromkeys(texts))
    if len(distinct) > MAX_COMMANDS:
        more = len(distinct) - MAX_COMMANDS
        distinct = [*distinct[:MAX_COMMANDS], f"... {more} more commands"]
    return distinct


def _problem(stage: str, p: Problem) -> ModelProblem:
    words = PROBLEM_WORDS.get(p.kind, PROBLEM_WORDS["other"])
    if p.status is not None:
        words += f" (HTTP {p.status})"
    return ModelProblem(
        stage=stage,
        role=p.role,
        model=p.model,
        kind=p.kind,
        status=p.status,
        words=f"{words}: {NOT_THE_FIX}",
        detail=p.detail,
    )


def _rate(value: float | None) -> float | None:
    return None if value is None else round(value, 3)


def _rule_kinds(g: GuardResult) -> list[str]:
    """Each rule kind that ran, as "compare: 2 of 3 killed" (report only; valid mutants only)."""
    lines = []
    for kind in KINDS:
        ran = [r for r in g.rule_mutants if r.mutant.kind == kind]
        valid = [r for r in ran if r.status is not MutantStatus.DISCARDED]
        killed = sum(r.status is MutantStatus.KILLED for r in valid)
        if ran:
            lines.append(f"{kind}: {killed} of {len(valid)} killed")
    return lines


def _rule_kinds_absent(g: GuardResult) -> list[str]:
    """The kinds with no valid edit on the fixed lines: at most 10 mutants and 10 kinds, so every
    kind with one ran. With no rule mutant at all nothing is claimed: their step may have failed."""
    ran = {r.mutant.kind for r in g.rule_mutants}
    return [kind for kind in KINDS if kind not in ran] if ran else []


def _guard_evidence(g: GuardResult) -> dict[str, Value]:
    counted = [m for m in g.mutants if m.status is not MutantStatus.DISCARDED]
    return {
        "kill_rate": _rate(g.kill_rate),
        "repro_kill_rate": _rate(g.repro_kill_rate),
        "pr_kill_rate": _rate(g.pr_kill_rate),
        "mutants": len(counted),
        "killed": sum(m.status is MutantStatus.KILLED for m in counted),
        "survived": sum(m.status is MutantStatus.SURVIVED for m in counted),
        "discarded": len(g.mutants) - len(counted),
        "rejected": len(g.rejected),
        "not_run": len(g.not_run),  # left once "not guarded" was certain (M11)
        "crash_kills": g.crash_kills,  # still counted (NOTES 26)
        "killed_ids": [m.mutant.id for m in counted if m.status is MutantStatus.KILLED],
        "rule_mutants": len(g.rule_mutants),
        "rule_kill_rate": _rate(g.rule_kill_rate),  # report only
        "rule_kinds": _rule_kinds(g),  # report only
        "rule_kinds_absent": _rule_kinds_absent(g),  # report only
        "pr_test_files": list(g.pr_test_files),
        "findings": [f"{f.kind}: {f.detail}" for f in g.findings],
    }


def _evidence(record: StageRecord, run: RunRecord) -> dict[str, Value]:
    r = record.result
    if isinstance(r, EnvironmentCheck):
        return {"base_suite": r.run.outcome.value, "error": r.error, "module": r.module}
    if isinstance(r, OriginCheck):
        outside = [f"{o.side}: {o.module}" for o in r.origins if o.file and not o.inside]
        return {"modules": len({o.module for o in r.origins}), "outside_copy": outside}
    if isinstance(r, ReproResult):
        return {
            "attempts": len(r.attempts),
            "test_file": repro_file(r) if r.test_code is not None else None,
            "oracle": f"a test written by the model {run.settings.models['reproducer']}",
            "isolation": r.isolation,
        }
    if isinstance(r, BlindResult):
        return {
            "attempts": len(r.attempts),
            "test_file": BLIND_TEST_FILE if r.test_code is not None else None,
            "oracle": f"a test written by the model {run.settings.models['reproducer']}, "
            "not shown the fix",
            "report_only": True,  # no level reads it
        }
    if isinstance(r, GuardResult):
        return _guard_evidence(r)
    if isinstance(r, RegressionResult):
        return {
            "compared": r.compared,
            "not_run": r.not_run,
            "regressions": len(r.regressions),
            "unconfirmed": len(r.unconfirmed),
        }
    if isinstance(r, FixLineCoverage):
        return {"fix_lines": sum(len(lines) for lines in r.lines.values())}
    if isinstance(r, BehaviourResult):
        compared = sum(t.comparison.compared for t in r.targets if t.comparison)
        return {
            "targets": len(r.targets),
            "finished": sum(t.finished for t in r.targets),
            "inputs_compared": compared,
            "changes": r.changes,
            "groups": len(r.groups),
            "l3_checks": r.checks.allowed,
            "l3_gate": r.l3.allowed,
            "judge": r.judge.status.value,
        }
    if isinstance(r, AttackResult):
        counted = [p for p in r.properties if p.status == "counted"]
        return {
            "targets": len(r.targets),
            "inputs_tried": r.inputs_tried,
            "properties_counted": len(counted),
            "findings": len(r.findings),
            "unconfirmed": r.more,
            "pre_existing": len(r.pre_existing),
            "discarded": len(r.discarded),
            "crashes_reported": sum(len(t.crashes) for t in r.targets),
        }
    if isinstance(r, IntegrityResult):
        return {"flags": len(r.flags), "candidates": len(r.candidates)}
    if isinstance(r, PreviousResult):
        return {
            "findings": len(r.findings),
            "fixed": sum(f.result is Replay.FIXED for f in r.findings),
            "last_level": r.level or None,
        }
    return {}


def _reason(record: StageRecord, run: RunRecord) -> str:
    """The stage's own reason; fix_does_not_fix also says what it rests on (NOTES 14, 17)."""
    r = record.result
    if isinstance(r, ReproResult) and r.status is ReproStatus.FIX_DOES_NOT_FIX:
        model = run.settings.models["reproducer"]
        return f"{record.reason} This rests on a test written by the model {model}."
    return record.reason


def _stage(record: StageRecord, run: RunRecord) -> StageEntry:
    return StageEntry(
        name=record.name,
        status=record.status,
        reason=_reason(record, run),
        duration_s=round(record.duration_s, 2),
        commands=_commands(record.result, run.python),
        problems=[_problem(record.name, p) for p in record.problems],
        error=record.error,
        evidence=_evidence(record, run),
    )


# --- findings, changes, flags ---------------------------------------------------------------------


def _call(function: str, args: Args) -> str:
    shown = ", ".join(f"{name}={source}" for name, source in args)
    return f"{function.rsplit('.', 1)[-1]}({shown})"


def _property(p: PropertyResult | None) -> PropertyInfo | None:
    if p is None:
        return None
    return PropertyInfo(
        id=p.id,
        name=p.name,
        kind=p.kind,
        claim=p.claim,
        source=p.source,
        quote=p.quote,
        origin=p.origin,
    )


def _finding(f: Finding, file: str | None) -> FindingEntry:
    return FindingEntry(
        number=f.number,
        function=f.function,
        call=_call(f.function, f.input),
        input=dict(f.input),
        outcome=describe_outcome(f.outcome, full=True),
        base_outcome=None
        if f.base_outcome is None
        else describe_outcome(f.base_outcome, full=True),
        expected=f.expected,
        property=_property(f.property),
        also_violates=list(f.also_violates),
        other_inputs=len(f.other_inputs),
        relation=f.relation,
        file=file,
        path=f.path or None,
        line=f.line or None,
        expect=_expect(f.expect),
        doubt=f.doubt,
    )


def _answer(seen: Seen, kind: Kind, also: Iterable[str]) -> str:
    side = shown_side(seen, kind, tuple(also))
    return describe(seen) + (f"; {side}" if side else "")


def _change(g: ChangeGroup, names: Mapping[str, str], labels: Iterable[Label]) -> BehaviourChange:
    function = names.get(g.target, g.target)
    first = g.changes[0]
    shown = {c.id for c in g.shown}
    examples = [
        Example(
            call=_call(function, c.args),
            before=_answer(c.before, c.kind, c.also),
            after=_answer(c.after, c.kind, c.also),
        )
        for c in (g.shown or g.changes)[:MAX_EXAMPLES]
    ]
    return BehaviourChange(
        function=function,
        kind=g.kind.value,
        count=len(g.changes),
        before=_answer(first.before, first.kind, first.also),
        after=_answer(first.after, first.kind, first.also),
        explained=list(g.explained),
        contradicts=sorted({x for c in g.changes for x in c.contradicts}),
        labels=[
            ChangeLabel(change=label.change, label=label.label, reason=label.reason)
            for label in labels
            if label.change in shown
        ],
        examples=examples,
    )


def _cut(text: str, chars: int = MAX_EDIT_CHARS) -> str:
    return text if len(text) <= chars else text[:chars] + "..."


def _diff(text: str) -> str:
    lines = text.splitlines()
    if len(lines) <= MAX_DIFF_LINES:
        return text
    return "\n".join([*lines[:MAX_DIFF_LINES], f"... {len(lines) - MAX_DIFF_LINES} more lines"])


def _survivor(m: MutantResult, check: SurvivorCheck | None) -> Survivor:
    mut = m.mutant
    words = (
        f"{mut.path}:{mut.line}: changing `{_cut(mut.original, 60)}` to "
        f"`{_cut(mut.replacement, 60)}` made no test fail"
    )
    status = check.status if check else "not_checked"
    if status == "differs":
        words += "; it behaves differently from the fix on inputs no test checks"
    elif status == "no_difference_found":
        words += "; no input tried behaved differently from the fix (it may be equivalent)"
    elif check is not None and check.reason:
        words += f"; not compared with the fix: {check.reason}"
    return Survivor(
        id=mut.id,
        origin=mut.origin,
        file=mut.path,
        line=mut.line,
        original=_cut(mut.original),
        replacement=_cut(mut.replacement),
        description=mut.description,
        diff=_diff(mut.diff),
        words=words,
        check=status,
        examples=[
            SurvivorExample(call=call, fix=fix, mutant=other)
            for call, fix, other in (check.examples if check else ())
        ],
        kind=mut.kind,
    )


def _survivors(run: RunRecord) -> list[Survivor]:
    guard = run.result(GuardResult)
    if guard is None:
        return []
    behaviour = run.result(BehaviourResult)
    checks = {(s.number, s.origin): s for s in (behaviour.survivors if behaviour else ())}
    return [
        _survivor(m, checks.get((m.mutant.number, m.mutant.origin)))
        for m in (*guard.mutants, *guard.rule_mutants)
        if m.status is MutantStatus.SURVIVED
    ]


def _coverage(cov: FixLineCoverage | None) -> FixLineCoverageEntry | None:
    if cov is None:
        return None
    names = list(dict.fromkeys(name for name, _ in cov.runs))
    sets = []
    for name in names:
        ran, total = cov.summary(name)
        sets.append(CoverageSet(name=name, ran=ran, total=total))
    return FixLineCoverageEntry(
        lines={path: sorted(lines) for path, lines in cov.lines.items()},
        sets=sets,
        notes=list(cov.notes),
    )


def _unchecked(run: RunRecord) -> list[str]:
    behaviour = run.result(BehaviourResult)
    unobserved = behaviour.unobserved if behaviour else UNOBSERVED
    out = [*NOT_CHECKED, *(f"{UNOBSERVED_PREFIX}{u}" for u in unobserved)]
    for name in planned(run.stage(PREVIOUS) is not None):
        record = run.stage(name)
        if name == BLIND:  # report only: without it, nothing the receipt rests on went unchecked
            continue
        if record is None:
            out.append(f"{name}: did not run")
        elif record.error is not None:
            out.append(f"{name}: failed inside Tracefix")
        elif record.status == "skipped":
            out.append(f"{name}: skipped ({record.reason})")
    origin = run.result(OriginCheck)
    out += [
        f"the import origin check could not check {path}: it has no import name (outside the "
        "package folders, e.g. a namespace package)"
        for path in (origin.unchecked if origin else ())
    ]
    attack = run.result(AttackResult)
    out += [
        f"Break My Fix could not attack {s.function}: {s.reason}"
        for s in (attack.skipped if attack else ())
    ]
    out += [
        f"the behaviour diff could not compare {s.function}: {s.reason}"
        for s in (behaviour.skipped if behaviour else ())
    ]
    return out


def _expect(expect: Expectation | None) -> Expect | None:
    return None if expect is None else Expect(types=sorted(expect.types), in_file=expect.in_file)


def _previous(run: RunRecord) -> PreviousInfo | None:
    """None without --previous. The replay's results, if it ran, and the findings still open."""
    if run.still_open is None and run.stage(PREVIOUS) is None:
        return None
    still = run.still_open or StillOpen(known=False)  # never left out unknowingly
    result = run.result(PreviousResult)
    head_sha, level, created_at = (
        (result.head_sha, result.level, result.created_at) if result else ("", "", "")
    )
    return PreviousInfo(
        head_sha=head_sha,
        level=EvidenceLevel(level) if level else None,
        created_at=created_at,
        findings=[
            ReplayedFinding(number=f.number, call=f.call, file=f.file, result=f.result,
                            detail=f.detail, path=f.path, line=f.line, carried=f.carried)
            for f in (result.findings if result else ())
        ],
        still_open=[
            OpenFinding(number=i, call=f.call, file=file_name(i, True), expect=_expect(f.expect),
                        path=f.path, line=f.line)
            for i, f in enumerate(still.findings, start=1)
        ],
        still_open_known=still.known,
    )  # fmt: skip


def _llm(run: RunRecord) -> LLMUse:
    usd = cost_usd(run.calls)
    if usd is None:
        unknown = sorted({c.model for c in run.calls if c.model not in PRICES_PER_MTOK})
        cost = Cost(usd=None, label=f"unknown: no list price for {', '.join(unknown)}")
    else:
        cost = Cost(usd=round(usd, 4), label=COST_LABEL)
    s = run.settings
    problems = [_problem(r.name, p) for r in run.stages for p in r.problems]
    problems += [_problem("summary", p) for p in run.problems]
    return LLMUse(
        calls=len(run.calls),
        input_tokens=sum(c.input_tokens for c in run.calls),
        output_tokens=sum(c.output_tokens for c in run.calls),
        cost_estimate=cost,
        settings=LLMSettings(
            models={str(role): model for role, model in s.models.items()},
            effort=s.effort,
            max_tokens=s.max_tokens,
            max_calls=s.max_llm_calls,
            token_budget=s.token_budget,
        ),
        problems=problems,
    )


def _tampering(run: RunRecord) -> list[Tampering]:
    out = [Tampering(stage=r.name, detail=r.reason) for r in run.stages if r.status == "invalid"]
    if run.status is RunStatus.INVALID and not out:
        out.append(Tampering(stage="environment", detail=run.status_reason))
    return out


def _texts(run: RunRecord, attribute: str) -> list[str]:
    """Each stage result's warnings or notes (notes prefixed with the stage), without repeats."""
    out: list[str] = []
    for record in run.stages:
        for text in getattr(record.result, attribute, ()):
            out.append(text if attribute == "warnings" else f"{record.name}: {text}")
    return out


def _title(issue: str) -> str:
    line = next((ln.strip() for ln in issue.splitlines() if ln.strip()), "")
    return _cut(line.lstrip("#").strip(), TITLE_CHARS)


def own_summary(rung: Rung) -> str:
    """Our own "why this level" line: the summary when the Judge gives none."""
    reasons = rung.reasons
    if rung.level is EvidenceLevel.COUNTEREXAMPLE:
        more = f" (and {len(reasons) - 1} more)" if len(reasons) > 1 else ""
        return f"COUNTEREXAMPLE: {reasons[0]}{more}."
    if rung.level is EvidenceLevel.L4:
        return f"L4: {reasons[-1]}."
    why = next((r for r in reasons if r.startswith("not L")), reasons[0])
    return f"{rung.level.value}: {why}."


# --- the receipt ----------------------------------------------------------------------------------


def _mask(value: object, ws: Workspace) -> object:
    if isinstance(value, str):
        return mask_paths(value, ws, [(ws.repo, "<repo>")])
    if isinstance(value, list):
        return [_mask(v, ws) for v in value]
    if isinstance(value, dict):
        return {k: _mask(v, ws) for k, v in value.items()}
    return value


def build(run: RunRecord, ws: Workspace, judged: JudgeSummary | None = None) -> Receipt:
    """The receipt of one run. `ws` only names the folders to mask (it may be cleaned up).
    `judged`: the Judge's summary and flag notes (display only; see `summary_facts`)."""
    rung = level(run)
    attack = run.result(AttackResult)
    behaviour = run.result(BehaviourResult)
    integrity = run.result(IntegrityResult)
    regressions = run.result(RegressionResult)
    names = {t.id: t.function for t in behaviour.targets} if behaviour else {}
    notes = dict(judged.flag_notes) if judged is not None else {}
    said = [f"summary: {n}" for n in judged.notes] if judged is not None else []
    receipt = Receipt(
        schema_version=SCHEMA_VERSION,
        tracefix_version=__version__,
        created_at=run.created_at.isoformat(timespec="seconds"),
        status=run.status,
        status_reason=run.status_reason,
        level=rung.level,
        level_reasons=list(rung.reasons),
        repo=RepoInfo(name=run.repo_name),
        base=Ref(ref=run.base_ref, sha=run.base_sha),
        head=Ref(ref=run.head_ref, sha=run.head_sha),
        issue=IssueInfo(
            title=_title(run.issue), sha256=hashlib.sha256(run.issue.encode("utf-8")).hexdigest()
        ),
        isolation=IsolationInfo(
            level=run.isolation,
            why=run.isolation_why,
            warning=BASIC_WARNING if run.isolation == "basic" else None,
            python=run.python.label if run.python is not None else None,
        ),
        summary=Summary(text=judged.text, by="judge")
        if judged is not None and judged.text is not None
        else Summary(text=own_summary(rung), by="tracefix"),
        stages=[_stage(r, run) for r in run.stages],
        findings=[
            _finding(f, finding_file(f) if f.repro_code else None)
            for f in (attack.findings if attack else ())
        ],
        pre_existing=[_finding(f, None) for f in (attack.pre_existing if attack else ())],
        behaviour_changes=[_change(g, names, behaviour.judge.labels) for g in behaviour.groups]
        if behaviour
        else [],
        integrity_flags=[
            IntegrityFlagEntry(
                id=f"f{i}",
                kind=f.kind,
                file=f.file,
                line=f.line,
                test=f.test,
                detail=f.detail,
                evidence=f.evidence,
                note=notes.get(f"f{i}"),
            )
            for i, f in enumerate(integrity.flags if integrity else (), start=1)
        ],
        regressions=[
            RegressionEntry(file=r.file, test=r.test, evidence=r.evidence, line=r.line)
            for r in (regressions.regressions if regressions else ())
        ],
        survivors=_survivors(run),
        fix_line_coverage=_coverage(run.result(FixLineCoverage)),
        unchecked=_unchecked(run),
        llm=_llm(run),
        tampering=_tampering(run),
        warnings=[
            w
            for w in dict.fromkeys([*run.warnings, *_texts(run, "warnings")])
            if w != BASIC_WARNING
        ],
        notes=list(dict.fromkeys([*run.notes, *run.settings.notes, *_texts(run, "notes"), *said])),
        previous=_previous(run),
        attack_targets=_attack_targets(attack),
    )
    return Receipt.model_validate(_mask(receipt.model_dump(mode="json"), ws))


def _attack_targets(attack: AttackResult | None) -> list[AttackTargetEntry] | None:
    if attack is None:
        return None
    return [
        AttackTargetEntry(function=t.function, path=t.path, via=t.via, attacked=t.attacked,
                          inputs_tried=t.inputs_tried, finished=t.finished, reason=t.reason)
        for t in attack.targets
    ]  # fmt: skip


def _fact(text: str) -> str:
    return _cut(ascii_only(" ".join(_ADDRESS.sub("0x?", text).split())), FACT_CHARS)


def summary_facts(receipt: Receipt) -> SummaryFacts:
    """What the Judge reads to write the summary (plan P14): taken from the built receipt, so
    already masked; no counts, durations or addresses, and ASCII only, so the request (its
    recording key) is the same on every machine. The replay of the last receipt is left out, so
    a run with `--previous` asks the Judge what the same run without it would; so is the blind
    test, which is report only."""
    flags = [f"{f.kind} in {f.file}" + (f", test {f.test}" if f.test else "") + f": {f.detail}"
             for f in receipt.integrity_flags]  # fmt: skip
    changes = [
        f"{c.function}: {c.kind} change; labels: "
        + (", ".join(label.label for label in c.labels) or "none")
        for c in receipt.behaviour_changes
    ]
    return SummaryFacts(
        level=receipt.level.value,
        reasons=tuple(_fact(_NUMBER.sub("N", r)) for r in receipt.level_reasons),
        stages=tuple(
            f"{s.name}: {s.status}" for s in receipt.stages if s.name not in (PREVIOUS, BLIND)
        ),
        findings=tuple(_fact(f"{f.call} -> {f.outcome}") for f in receipt.findings[:MAX_FACTS]),
        flags=tuple(
            (f.id, _fact(text)) for f, text in zip(receipt.integrity_flags, flags, strict=True)
        )[:MAX_FACTS],
        changes=tuple(_fact(c) for c in changes[:MAX_FACTS]),
    )


def schema() -> dict[str, object]:
    """receipt.json's JSON schema (docs/receipt.schema.json)."""
    return Receipt.model_json_schema()

"""The evidence ladder (SPEC 2.8, plan P3/P4): the receipt's level, computed by our own code.

`facts` reads the stages' statuses and results; `climb` turns the facts into a level with plain
reasons. The only model influence is the behaviour diff's L3 gate, where the Judge can only veto
(proven in M7). Pure: no runs, no model calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from tracefix.attack import AttackResult, AttackStatus
from tracefix.behaviour_diff import BehaviourResult
from tracefix.behaviour_rules import Gate
from tracefix.guard import GuardResult, GuardStatus
from tracefix.integrity import IntegrityResult, IntegrityStatus
from tracefix.previous import WORDS, PreviousResult, PreviousStatus, Replay
from tracefix.record import PREVIOUS, RunRecord, RunStatus
from tracefix.regressions import RegressionResult, RegressionStatus
from tracefix.repro import ReproResult, ReproStatus

L4_MIN_INPUTS = 100  # inputs tried per changed function (developer, 13 Oct 2026)
MAX_LINES_LISTED = 10  # fix lines named in one reason


class EvidenceLevel(StrEnum):
    COUNTEREXAMPLE = "COUNTEREXAMPLE"
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


ORDER = tuple(EvidenceLevel)  # lowest first: COUNTEREXAMPLE < L0 < ... < L4


def rank(level: EvidenceLevel) -> int:
    return ORDER.index(level)


UNCHECKED = Gate(False, ("not checked",))


@dataclass(frozen=True)
class Facts:
    """What the ladder reads. Gates carry why they are closed, in plain words."""

    stopped: str | None = None  # the run status is not ok: why
    counterexamples: tuple[str, ...] = ()  # each proven counterexample, in words
    tampering: tuple[str, ...] = ()  # each stage where tampering was detected
    reproduced: Gate = UNCHECKED
    guarded: Gate = UNCHECKED
    l3: Gate = UNCHECKED
    l4: Gate = UNCHECKED


@dataclass(frozen=True)
class Rung:
    level: EvidenceLevel
    reasons: tuple[str, ...]  # why this level, and what kept the next one out of reach


# What each gate shows when open, and the level it opens.
_STEPS = (
    ("reproduced", EvidenceLevel.L1, "the bug was reproduced: a test fails before the fix and "
                                     "passes after it"),
    ("guarded", EvidenceLevel.L2, "the tests guard the fix: they fail when it is reverted or "
                                  "broken"),
    ("l3", EvidenceLevel.L3, "the behaviour diff found no unexplained change in what it observes"),
    ("l4", EvidenceLevel.L4, "Break My Fix attacked every changed function to the end and found "
                             "nothing"),
)  # fmt: skip


def climb(facts: Facts) -> Rung:
    """The level the facts allow: a stopped run is L0; any counterexample is COUNTEREXAMPLE (even
    with tampering elsewhere: it was proven); tampering caps at L0; then each gate in turn."""
    if facts.stopped is not None:
        return Rung(EvidenceLevel.L0, (f"the run stopped: {facts.stopped}",))
    if facts.counterexamples:
        return Rung(EvidenceLevel.COUNTEREXAMPLE, facts.counterexamples)
    if facts.tampering:
        lines = tuple(f"tampering detected in {where}" for where in facts.tampering)
        return Rung(EvidenceLevel.L0, (*lines, "no evidence from a tampered run counts"))
    level = EvidenceLevel.L0
    shown: list[str] = []
    for name, opens, says in _STEPS:
        gate: Gate = getattr(facts, name)
        if not gate.allowed:
            why = gate.reasons or ("its conditions were not met",)
            return Rung(level, (*shown, *(f"not {opens}: {r}" for r in why)))
        level = opens
        shown.append(says)
    return Rung(level, tuple(shown))


# --- reading the stages ---------------------------------------------------------------------------


def _absent(run: RunRecord, name: str) -> Gate:
    record = run.stage(name)
    if record is None:
        return Gate(False, (f"the {name} stage did not run",))
    if record.error is not None:
        return Gate(False, (f"the {name} stage failed inside Tracefix, so it gives no evidence",))
    return Gate(False, (f"the {name} stage gave no result",))


def _gate(allowed: bool, reason: str) -> Gate:
    return Gate(True) if allowed else Gate(False, (reason,))


def counterexamples(run: RunRecord) -> tuple[str, ...]:
    """Every proven counterexample: a counted Break My Fix finding, an integrity flag, a fix that
    doesn't fix the bug, a confirmed regression."""
    found: list[str] = []
    repro = run.result(ReproResult)
    if repro is not None and repro.status is ReproStatus.FIX_DOES_NOT_FIX:
        found.append("the fix does not fix the bug: the reproduction test fails the same way "
                     "before and after it")  # fmt: skip
    attack = run.result(AttackResult)
    if attack is not None and attack.status is AttackStatus.FOUND:
        found += [f"Break My Fix finding {f.number}: an input that breaks {f.function}"
                  for f in attack.findings]  # fmt: skip
    integrity = run.result(IntegrityResult)
    if integrity is not None and integrity.status is IntegrityStatus.FLAGGED:
        found += [f"integrity flag: {f.kind} at {f.file}:{f.line}" for f in integrity.flags]
    regressions = run.result(RegressionResult)
    if regressions is not None and regressions.status is RegressionStatus.FOUND:
        found += [f"regression: {r.file}{'::' + r.test if r.test else ''} passed before the fix "
                  "and fails after it" for r in regressions.regressions]  # fmt: skip
    return tuple(found)


def l4_gate(attack: AttackResult | None) -> Gate:
    """Strict L4 (developer, 13 Oct 2026): Break My Fix found nothing; no changed function was
    skipped; every target was attacked to the end with at least L4_MIN_INPUTS inputs and has a
    counted model property that constrains its result (a docstring example checks one input);
    the attacks ran every executable fix line inside a function."""
    if attack is None:
        return Gate(False, ("Break My Fix did not run",))
    reasons: list[str] = []
    if attack.status is not AttackStatus.NONE_FOUND:
        reasons.append(f"Break My Fix ended {attack.status.value}: {attack.reason}")
    reasons += [f"{s.function} could not be attacked: {s.reason}" for s in attack.skipped]
    if not attack.targets:
        reasons.append("no changed function was attacked")
    for t in attack.targets:
        if not t.attacked:
            reasons.append(f"{t.function} was not attacked: {t.reason or 'no reason given'}")
            continue
        if not t.finished:
            reasons.append(f"{t.function}: its attack did not finish")
        if t.inputs_tried < L4_MIN_INPUTS:
            reasons.append(f"{t.function}: {t.inputs_tried} inputs tried "
                           f"(at least {L4_MIN_INPUTS} needed)")  # fmt: skip
        if not any(p.target == t.id and p.status == "counted" and p.origin == "model"
                   and p.constrains_result for p in attack.properties):  # fmt: skip
            reasons.append(f"{t.function}: no counted model property constrains its result")
    reasons += _unreached(attack)
    return Gate(not reasons, tuple(reasons))


def audits_gate(run: RunRecord) -> Gate:
    """L4 also needs the integrity audit and the no-regression check to have finished with
    nothing found (or been skipped for their stated reason): one that failed, did not run or was
    inconclusive could have hidden a counterexample (developer, 13 Oct 2026, verifier S1)."""
    reasons: list[str] = []
    integrity = run.result(IntegrityResult)
    if integrity is None:
        reasons += _absent(run, "integrity").reasons
    elif integrity.status is IntegrityStatus.INCONCLUSIVE:
        reasons.append(f"the integrity audit was inconclusive: {integrity.reason}")
    regressions = run.result(RegressionResult)
    if regressions is None:
        reasons += _absent(run, "regressions").reasons
    elif regressions.status is RegressionStatus.INCONCLUSIVE:
        reasons.append(f"the no-regression check was inconclusive: {regressions.reason}")
    return Gate(not reasons, tuple(reasons))


def previous_gate(run: RunRecord) -> Gate:
    """With `--previous`, L4 also needs every finding of the last receipt shown fixed on this
    commit (developer, 14 Oct 2026): one that still fails, or could not be replayed, keeps only L4
    out of reach. It never makes a COUNTEREXAMPLE: this run's own stages decide that."""
    if run.stage(PREVIOUS) is None:
        return Gate(True)
    result = run.result(PreviousResult)
    if result is None:
        return _absent(run, PREVIOUS)
    if result.status is PreviousStatus.SKIPPED:
        return Gate(True)
    if result.status is not PreviousStatus.REPLAYED:
        return Gate(False, (f"the last receipt's findings were not replayed: {result.reason}",))
    reasons = tuple(
        f"{f.label} ({f.call}) {WORDS[f.result]} on this commit"
        for f in result.findings
        if f.result is not Replay.FIXED
    )
    return Gate(not reasons, reasons)


def _both(first: Gate, second: Gate) -> Gate:
    return Gate(first.allowed and second.allowed, (*first.reasons, *second.reasons))


def _unreached(attack: AttackResult) -> list[str]:
    reached = {(path, line) for t in attack.targets for path, lines in t.reached for line in lines}
    out = []
    for path, lines in attack.fix_lines:
        missing = [line for line in lines if (path, line) not in reached]
        if missing:
            listed = ", ".join(map(str, missing[:MAX_LINES_LISTED]))
            extra = len(missing) - MAX_LINES_LISTED
            more = f" and {extra} more" if extra > 0 else ""
            out.append(f"{path}: fix lines {listed}{more} were never run by the attacks")
    return out


def facts(run: RunRecord) -> Facts:
    """The ladder's facts, read from the stages' statuses and results by our own code."""
    if run.status is not RunStatus.OK:
        return Facts(stopped=run.status_reason or run.status.value)
    tampering = tuple(f"{s.name} ({s.reason})" for s in run.stages if s.status == "invalid")
    repro = run.result(ReproResult)
    guard = run.result(GuardResult)
    behaviour = run.result(BehaviourResult)
    return Facts(
        counterexamples=counterexamples(run),
        tampering=tampering,
        reproduced=_absent(run, "reproduce") if repro is None
        else _gate(repro.status is ReproStatus.REPRODUCED, repro.reason),
        guarded=_absent(run, "guard") if guard is None
        else _gate(guard.status is GuardStatus.GUARDED, guard.reason),
        l3=_absent(run, "behaviour_diff") if behaviour is None else behaviour.l3,
        l4=_both(_both(l4_gate(run.result(AttackResult)), audits_gate(run)), previous_gate(run)),
    )  # fmt: skip


def level(run: RunRecord) -> Rung:
    return climb(facts(run))

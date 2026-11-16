"""The Judge: labels the behaviour diff's shown changes `intended` or `suspicious` (M7), and
writes the receipt's two-sentence summary (M8, `summarize`).

Advisory. The labels go into `behaviour_rules.l3_gate`, where they can only keep L3 out of reach;
everything that decides is ours: which changes exist (runs), which are shown (fixed rules), what
explains or contradicts one (text and runs), and how a reply is read (here):
- an id that was not shown is ignored (and noted);
- two labels for one change: suspicious wins;
- a reason is cut to one line of at most MAX_REASON characters, and is only ever shown;
- ids the reply leaves out get one follow-up; after it they stay unlabelled, which keeps L2.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from tracefix.attack_inputs import AttackTarget, readme
from tracefix.behaviour_rules import Change, ChangeGroup, Seen, call_text, describe, shown_side
from tracefix.diffscope import DiffScope, unified_diff
from tracefix.llm import LLMClient, LLMError, Message
from tracefix.prompts import judge as prompt
from tracefix.repro import sanitize
from tracefix.workspace import Workspace

JUDGE_CALLS = 2  # per sample: the request, and one follow-up for changes left without a label
JUDGE_SAMPLES = 2  # independent conversations; any suspicious label wins (round 5)
MAX_REASON = 300
MAX_SUMMARY = 400  # characters, at most two sentences
MAX_NOTE = 300  # characters, one line per integrity flag
DIFF_CHARS = 12_000
SOURCE_CHARS = 6_000
OUTCOME_CHARS = 600


class JudgeStatus(StrEnum):
    NOT_NEEDED = "not_needed"  # no change to label
    LABELLED = "labelled"  # every shown change has a label
    INCOMPLETE = "incomplete"  # some stayed without one
    FAILED = "failed"  # the model could not answer (error, budget, refusal)


@dataclass(frozen=True)
class Label:
    change: str  # c1, c2, ...
    label: str  # intended | suspicious
    reason: str


@dataclass(frozen=True)
class JudgeResult:
    status: JudgeStatus
    labels: tuple[Label, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def by_id(self) -> dict[str, str]:
        return {label.change: label.label for label in self.labels}


def merge(
    answer: prompt.JudgeAnswer, shown: Sequence[str], into: dict[str, Label], notes: list[str]
) -> None:
    """Fold one reply into the labels so far, by our rules (see the module docstring)."""
    unknown = []
    for entry in answer.labels:
        if entry.change not in shown:
            unknown.append(entry.change[:20])
            continue
        reason = " ".join(entry.reason.split())[:MAX_REASON]
        old = into.get(entry.change)
        if old is None or (old.label == "intended" and entry.label == "suspicious"):
            into[entry.change] = Label(entry.change, entry.label, reason)
    if unknown:
        notes.append(f"the Judge labelled ids that were not shown (ignored): {', '.join(unknown)}")


def ascii_only(text: str) -> str:
    """Non-ASCII written as escapes: `repr` prints a character or its escape depending on the
    Python version's Unicode tables (3.11 vs 3.13), and this text is part of the recording key
    (verifier B3)."""
    return text.encode("ascii", "backslashreplace").decode("ascii")


def _view(change: Change, ws: Workspace, target: AttackTarget) -> prompt.ChangeView:
    """One change as the Judge reads it: the result, and for a change in what the call printed,
    logged or did to its arguments, that part too (verifier round 5: before and after must
    show the difference). If the shown texts are still the same, a fact says where it is."""

    def text(seen: Seen) -> str:
        side = shown_side(seen, change.kind, change.also)
        answer = describe(seen) + (f"; {side}" if side else "")
        return ascii_only(sanitize(answer, ws))[:OUTCOME_CHARS]

    before, after = text(change.before), text(change.after)
    if before == after:  # the plain texts look the same: show the snapshots (verifier round 7, S3)
        before, after = text(_shot(change.before)), text(_shot(change.after))
    facts = (*change.contradicts, *change.explains, *change.notes)
    if before == after:
        facts = (*facts, "the two differ past the part shown here (compared in full by digest)")
    return prompt.ChangeView(
        change.id, ascii_only(call_text(target, change.args)), before, after, facts
    )


def _shot(seen: Seen) -> Seen:
    """The answer with its result shown as its snapshot (the whole state, by attribute)."""
    if seen.outcome is None or not seen.outcome.get("shot"):
        return seen
    return replace(seen, outcome={**seen.outcome, "text": seen.outcome["shot"]})


def context(
    ws: Workspace,
    scope: DiffScope,
    issue: str,
    targets: Sequence[AttackTarget],
    groups: Sequence[ChangeGroup],
) -> prompt.JudgeContext:
    by_id = {t.id: t for t in targets}
    paths = sorted({p for f in scope.source_files for p in (f.old_path, f.path) if p})
    diff = unified_diff(ws.repo, ws.base_sha, ws.head_sha, paths)[:DIFF_CHARS]
    used = [t for t in targets if any(g.target == t.id and g.shown for g in groups)]
    functions = tuple(
        prompt.FunctionSource(
            t.qualname, t.path, t.source[:SOURCE_CHARS], t.owner_context[:SOURCE_CHARS]
        )
        for t in used
    )
    views = tuple(
        prompt.GroupView(
            by_id[g.target].qualname,
            g.kind.value + "".join(f" and {a}" for a in g.changes[0].also),
            g.key[1],
            g.key[2],
            len(g.changes),
            tuple(_view(c, ws, by_id[g.target]) for c in g.shown),
        )
        for g in groups
        if g.shown
    )
    return prompt.JudgeContext(issue, diff, functions, readme(ws), views)


def _sample(
    client: LLMClient, request: str, shown: Sequence[str], notes: list[str]
) -> dict[str, Label]:
    """One conversation: the request, and one follow-up for the ids it left without a label."""
    history = [Message("user", request)]
    labels: dict[str, Label] = {}
    for _ in range(JUDGE_CALLS):
        try:
            answer = client.complete("judge", prompt.SYSTEM, history, prompt.JudgeAnswer)
        except LLMError as exc:
            notes.append(f"the Judge stopped: {exc}")
            break
        merge(answer, shown, labels, notes)
        missing = [i for i in shown if i not in labels]
        if not missing:
            break
        history += [
            Message("assistant", answer.model_dump_json()),
            Message("user", prompt.render_feedback(missing)),
        ]
    return labels


def label_changes(
    ws: Workspace,
    scope: DiffScope,
    issue: str,
    targets: Sequence[AttackTarget],
    groups: Sequence[ChangeGroup],
    client: LLMClient,
) -> JudgeResult:
    """Ask the Judge for a label on every shown change, in JUDGE_SAMPLES independent
    conversations. A change is `intended` only if every sample says so; `suspicious` from any
    sample wins; a change any sample left without a label stays unlabelled (round 5: one sample
    can miss a suspicious change, and its label can only ever veto). Never raises for a model
    problem."""
    shown = [c.id for g in groups for c in g.shown]
    if not shown:
        return JudgeResult(JudgeStatus.NOT_NEEDED)
    request = prompt.render_request(context(ws, scope, issue, targets, groups))
    notes: list[str] = []
    samples = [
        _sample(client, request if n == 0 else f"{request}\n\n{prompt.SECOND_SAMPLE}", shown, notes)
        for n in range(JUDGE_SAMPLES)
    ]
    labels: dict[str, Label] = {}
    for change in shown:
        given = [sample[change] for sample in samples if change in sample]
        suspicious = next((g for g in given if g.label == "suspicious"), None)
        if suspicious is not None:
            labels[change] = suspicious
        elif len(given) == len(samples):
            labels[change] = given[0]
    ordered = tuple(labels[i] for i in shown if i in labels)
    if len(ordered) == len(shown):
        status = JudgeStatus.LABELLED
    elif ordered:
        status = JudgeStatus.INCOMPLETE
    else:
        status = JudgeStatus.FAILED
    return JudgeResult(status, ordered, tuple(notes))


# --- the receipt's summary (M8, plan P14) ---------------------------------------------------------

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class JudgeSummary:
    """The Judge's words for the receipt, as our code kept them. Display only: the level, the
    findings and the flags were computed before the call."""

    text: str | None  # None: the receipt shows our own "why this level" line
    flag_notes: tuple[tuple[str, str], ...] = ()  # (flag id, note), only for flags that exist
    notes: tuple[str, ...] = ()  # how the reply was read (for the receipt's notes)


def one_line(text: str, chars: int) -> str:
    line = " ".join(text.split())
    return line if len(line) <= chars else line[: chars - 1].rstrip() + "…"


def keep_summary(text: str) -> str | None:
    """At most two sentences on one line, cut to MAX_SUMMARY characters; empty gives None."""
    sentences = _SENTENCE_END.split(" ".join(text.split()))
    return one_line(" ".join(sentences[:2]), MAX_SUMMARY) or None


def keep_notes(
    answer: prompt.SummaryAnswer, flags: Sequence[str]
) -> tuple[tuple[tuple[str, str], ...], list[str]]:
    """One note per known flag (the first one given), one line of at most MAX_NOTE characters;
    unknown ids are ignored (and noted)."""
    kept: dict[str, str] = {}
    unknown = []
    for entry in answer.flag_notes:
        note = one_line(entry.note, MAX_NOTE)
        if entry.flag not in flags:
            unknown.append(entry.flag[:20])
        elif note and entry.flag not in kept:
            kept[entry.flag] = note
    notes = [f"the Judge noted flags that do not exist (ignored): {', '.join(unknown)}"]
    return tuple(kept.items()), notes if unknown else []


def summarize(client: LLMClient, issue: str, facts: prompt.SummaryFacts) -> JudgeSummary:
    """One call, role `judge`, for the receipt's summary and flag notes, read by our rules.
    Never raises for a model problem: the receipt then shows our own line."""
    request = prompt.render_summary_request(issue, facts)
    try:
        answer = client.complete(
            "judge", prompt.SUMMARY_SYSTEM, [Message("user", request)], prompt.SummaryAnswer
        )
    except LLMError as exc:
        return JudgeSummary(None, notes=(f"the Judge wrote no summary: {exc}",))
    text = keep_summary(answer.summary)
    flag_notes, notes = keep_notes(answer, [flag for flag, _ in facts.flags])
    if text is None:
        notes.append("the Judge's summary was empty")
    return JudgeSummary(text, flag_notes, tuple(notes))

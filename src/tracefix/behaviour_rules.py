"""The behaviour diff's rules (SPEC 2.5, Decided in M7): pure, no runs, no model.

- reading the diff runs' reports (untrusted: written inside the process under test);
- comparing base and head input by input: the kind of each change and its group;
- deterministic tags: what explains a group (the reproduction test, the issue, a docstring
  example the fix makes true), what contradicts a change (a docstring example it breaks), and
  advisory notes that never decide;
- which changes the Judge is shown (a fixed order, then variety);
- the L3 gate. `checks_gate` uses no model output at all; `l3_gate` adds the Judge, who can only
  turn "allowed" into "not allowed" (developer, 7 Oct 2026: a label can never raise the level).
"""

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any

from tracefix.attack_inputs import Args, AttackTarget
from tracefix.attack_methods import RECEIVER
from tracefix.attack_rules import args_of
from tracefix.attack_runtime import from_source

MIN_COMPARED = 50  # inputs per target, unless the generator ran out of new ones
MAX_LOST_SHARE = 0.2  # of a target's inputs that may go uncompared (unstable, unbindable...)
SHOWN_PER_GROUP = 5
SHOWN_IN_ALL = 40
SHOWN_CHARS = 1_000  # of a value, message or output, as reported
MAX_INPUTS_READ = 5_000  # per target: a report claiming more is cut there
HUGE = 2**31 - 1
LONG_TEXT = 100
_HEX = re.compile(r"[0-9a-f]{1,64}")
PHASE_RANK = {"doc": 0, "repro": 1, "witness": 1, "advisory": 1, "call": 1, "grid": 2,
              "evidence": 3,
              "model": 4, "boundary": 5, "draw": 6}  # fmt: skip


class Kind(StrEnum):
    VALUE = "value"  # returns, then returns another value of the same type
    TYPE = "type"  # returns, then returns another type
    NEW_RAISE = "new_raise"  # returned before the fix, raises after it
    NO_RAISE = "no_raise"  # raised before the fix, returns after it
    EXCEPTION = "exception"  # raises another exception type
    MESSAGE = "message"  # the same exception type with another message
    OUTPUT = "output"  # the same outcome, other printed or logged output, warnings or stderr
    ARGUMENTS = "arguments"  # the same outcome, but the call left its arguments different
    STATE = "state"  # the same outcome, but the call left module data different
    HANG = "hang"  # did not return on one side only


EXEMPT = frozenset({Kind.MESSAGE})  # kinds no evidence has to explain (an error's wording)

# What L3 does not claim (developer, 8 Oct 2026, after verifier round 9): L3 means no unexplained
# change in what the diff observes (SPEC 2.5 "What is compared"), not that nothing else changed.
# These channels are not observed; the receipt lists them under `unchecked` (SPEC 2.8).
UNOBSERVED = (
    "files written outside the copy, and anything sent off the machine",
    "in the copy: folders made or removed, file modes and other metadata, and files under "
    "__pycache__, .pytest_cache, .hypothesis or .git folders",
    "state of dependencies and C extensions (an lru_cache's contents, a C object's fields)",
    "process-wide state the function's code doesn't reach by name (os.environ, the working "
    "directory, sys.path, logging setup beyond the loggers it reaches, the decimal context, "
    "warning filters, the random module's state)",
    "module data reached only through importlib, sys.modules or getattr with a computed name",
    "code put into module data during a call (it is walked as it was before the first call)",
    "threads and processes a call starts, and what they do after it returns",
    "objects shared between the result, the arguments and module data",
    "output past 1 MB, and output a C library flushes after the call",
)


# --- what the runs reported -----------------------------------------------------------------------


@dataclass(frozen=True)
class Seen:
    """One side's answer for one input."""

    outcome: Mapping[str, str] | None = field(default=None, hash=False)  # None: no outcome
    stable: bool = False  # both calls gave the same outcome
    unbindable: str = ""  # why the input can't be passed on this side
    hung: bool = False  # the call did not return (the run was resumed past it)
    docs: Mapping[str, str] = field(default_factory=dict, hash=False)  # doc id -> verdict
    ran: bool = False  # a call ran a line the fix added or changed (head; report only)
    unbuilt: str = ""  # a method's object could not be built: the error's type (M7.5)


@dataclass(frozen=True)
class HeadInput:
    index: int
    phase: str
    args: Args


@dataclass
class DiffEvents:
    """What one or more diff runs on one side reported (merged: the first report of an index
    wins, so a resumed run can't overwrite what an earlier one said)."""

    inputs: dict[str, list[HeadInput]] = field(default_factory=dict)
    stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    seen: dict[str, dict[int, Seen]] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    modules: dict[str, str] = field(default_factory=dict)
    ended: set[str] = field(default_factory=set)
    reached: dict[str, dict[str, set[int]]] = field(default_factory=dict)
    notes: dict[str, list[str]] = field(default_factory=dict)
    bound: set[tuple[str, str]] = field(default_factory=set)  # (path, name) base has
    wrote: dict[str, str] = field(default_factory=dict)  # files a target changed


def _hex(value: object) -> str | None:
    return value if isinstance(value, str) and (not value or _HEX.fullmatch(value)) else None


def _dotted(text: object) -> bool:
    return isinstance(text, str) and bool(text) and all(p.isidentifier() for p in text.split("."))


def diff_outcome_of(value: object) -> dict[str, str] | None:
    """A diff outcome report ({kind, type, module, text, digest, out[, where]}), or None if any
    part is malformed (a forged or broken line)."""
    if not isinstance(value, dict) or value.get("kind") not in ("returned", "raised"):
        return None
    digest, out = _hex(value.get("digest")), _hex(value.get("out"))
    args, side = _hex(value.get("args", "")), _hex(value.get("side", ""))
    state, rest = _hex(value.get("state", "")), _hex(value.get("rest", ""))
    if not digest or out is None or args is None or side is None or state is None or rest is None:
        return None
    if not _dotted(value.get("type")) or not _dotted(value.get("module")):
        return None
    report = {
        "kind": str(value["kind"]),
        "type": str(value["type"])[:200],
        "module": str(value["module"])[:200],
        "digest": digest,
        "out": out,
        "args": args,
        "side": side,
        "state": state,
        "rest": rest,
    }
    for name in ("text", "out_text", "side_text", "args_text", "state_text", "opaque",
                 "data_opaque", "shot"):  # fmt: skip
        given = value.get(name)
        report[name] = given[:SHOWN_CHARS] if isinstance(given, str) else ""
    if report["kind"] == "raised":
        report["where"] = "repo" if value.get("where") == "repo" else "python"
    return report


def _index(value: object) -> int | None:
    return value if isinstance(value, int) and 0 <= value < MAX_INPUTS_READ else None


def read_diff_events(
    events: Iterable[Mapping[str, Any]], targets: Mapping[str, AttackTarget], into: DiffEvents
) -> None:
    """Fold one diff run's events into `into`, validating every part (untrusted data)."""
    for event in events:
        tid = str(event.get("target", ""))
        target = targets.get(tid)
        kind = event.get("event")
        if (
            kind == "bound"
            and isinstance(event.get("path"), str)
            and isinstance(event.get("name"), str)
        ):
            into.bound.add((str(event["path"])[:500], str(event["name"])[:200]))
            continue
        if target is None:
            continue
        if kind == "target":
            if event.get("error"):
                into.errors.setdefault(tid, str(event["error"])[:500])
            elif _dotted(event.get("module")):
                into.modules.setdefault(tid, str(event["module"]))
        elif kind == "target_error":
            into.errors.setdefault(tid, str(event.get("error"))[:500])
        elif kind == "inputs":
            keys = ("count", "drawn", "requested", "exhausted", "dropped")
            if tid not in into.stats:
                into.stats[tid] = {k: event.get(k) for k in keys}
                notes = event.get("notes")
                for note in notes[:10] if isinstance(notes, list) else []:
                    into.notes.setdefault(tid, []).append(str(note)[:300])
        elif kind == "input":
            index, args = _index(event.get("index")), args_of(event.get("args"), target)
            listed = into.inputs.setdefault(tid, [])
            if index is not None and args is not None and index == len(listed):
                listed.append(HeadInput(index, str(event.get("phase", ""))[:20], args))
        elif kind == "outcome":
            index = _index(event.get("index"))
            if index is not None:
                into.seen.setdefault(tid, {}).setdefault(index, _seen_of(event))
        elif kind == "end":
            into.ended.add(tid)
            wrote = event.get("files_changed")
            if isinstance(wrote, str) and wrote:
                into.wrote.setdefault(tid, wrote[:300])
            reached = event.get("reached")
            if isinstance(reached, dict):
                for path, lines in reached.items():
                    if isinstance(lines, list):
                        found = into.reached.setdefault(tid, {}).setdefault(str(path), set())
                        found.update(n for n in lines if isinstance(n, int))
        elif kind == "note":
            into.notes.setdefault(tid, []).append(str(event.get("note"))[:300])


def _seen_of(event: Mapping[str, Any]) -> Seen:
    if event.get("unbindable"):
        return Seen(unbindable=str(event["unbindable"])[:300])
    if event.get("unbuilt"):
        return Seen(unbuilt=str(event["unbuilt"])[:200])
    docs = event.get("docs")
    verdicts = {
        str(k): v
        for k, v in (docs.items() if isinstance(docs, dict) else [])
        if v in ("holds", "violated", "oracle_error")
    }
    return Seen(
        diff_outcome_of(event.get("outcome")),
        event.get("stable") is True,
        docs=verdicts,
        ran=event.get("ran") is True,
    )


# --- comparing ------------------------------------------------------------------------------------


def _same(a: Mapping[str, str], b: Mapping[str, str], *keys: str) -> bool:
    return all(a.get(k) == b.get(k) for k in keys)


def change_kind(before: Seen, after: Seen) -> Kind | None:
    """The kind of change between two comparable answers, or None if they are the same."""
    if before.hung != after.hung:
        return Kind.HANG
    a, b = before.outcome, after.outcome
    assert a is not None and b is not None
    if a["kind"] != b["kind"]:
        return Kind.NEW_RAISE if b["kind"] == "raised" else Kind.NO_RAISE
    if not _same(a, b, "type", "module"):
        return Kind.TYPE if a["kind"] == "returned" else Kind.EXCEPTION
    if a["digest"] != b["digest"]:
        if a["kind"] == "returned":
            return Kind.VALUE
        # Only the wording changed, or more of the exception (its fields, cause, attributes):
        # verifier round 7, an exception's state is not its message.
        return Kind.MESSAGE if a.get("rest", "") == b.get("rest", "") else Kind.EXCEPTION
    if a["out"] != b["out"] or a.get("side", "") != b.get("side", ""):
        return Kind.OUTPUT
    if a.get("args", "") != b.get("args", ""):
        return Kind.ARGUMENTS
    if a.get("state", "") != b.get("state", ""):
        return Kind.STATE
    return None


_ASPECTS = (  # what else a call does besides its result, and the kind a change in it alone has
    ("output", Kind.OUTPUT, ("out", "side")),
    ("arguments", Kind.ARGUMENTS, ("args",)),
    ("state", Kind.STATE, ("state",)),
)


def also_differs(before: Seen, after: Seen, kind: Kind) -> tuple[str, ...]:
    """The aspects besides `kind` that differ between two answers: a new message, value or
    exception can come with changed output, arguments or module data, and those must be
    explained and shown too, not hidden behind the first difference (verifier round 8, B1)."""
    a, b = before.outcome, after.outcome
    if a is None or b is None:
        return ()
    return tuple(
        name
        for name, own, keys in _ASPECTS
        if own is not kind and any(a.get(k, "") != b.get(k, "") for k in keys)
    )


def outcome_class(seen: Seen) -> str:
    """ "returns int", "raises ValueError" or "does not return": what a group is named by."""
    if seen.hung or seen.outcome is None:
        return "does not return"
    verb = "returns" if seen.outcome["kind"] == "returned" else "raises"
    return f"{verb} {seen.outcome['type']}"


def shown_side(seen: Seen | None, kind: "Kind", also: Sequence[str] = ()) -> str:
    """The parts of an answer a change of this kind is about, beside its result: what it printed
    or logged (`output`), its arguments as the call left them (`arguments`), the module data it
    left (`state`); and every other aspect that differs too (`also`: verifier round 8, B1)."""
    parts = [_side(seen, kind)]
    parts += [_side(seen, own) for name, own, _ in _ASPECTS if name in also]
    return "; ".join(p for p in parts if p)


def _side(seen: Seen | None, kind: "Kind") -> str:
    if seen is None or seen.outcome is None:
        return ""
    o = seen.outcome
    if kind is Kind.OUTPUT:
        parts = [f"printed {o.get('out_text', '')!r}"] if o.get("out_text") else ["printed nothing"]
        if o.get("side_text"):
            parts.append(f"wrote {o['side_text']!r}")
        return "; ".join(parts)
    if kind is Kind.ARGUMENTS:
        return f"left its arguments as {o.get('args_text', '')}"
    if kind is Kind.STATE:
        return f"left module data as {o.get('state_text', '') or 'nothing'}"
    return ""


def describe(seen: Seen | None, *, messages: bool = True) -> str:
    """An answer in words. A raise's message only if `messages` and the repo's own code wrote it
    (Python's wording differs between versions)."""
    if seen is None or seen.hung or seen.outcome is None:
        return "does not return"
    o = seen.outcome
    if o["kind"] == "returned":
        return f"returns {o['text']}"
    if messages and o.get("where") == "repo" and o["text"]:
        return f"raises {o['type']}: {o['text']}"
    return f"raises {o['type']}"


@dataclass(frozen=True)
class DocInfo:
    """A docstring example the runs judged on both sides."""

    id: str
    target: str
    args: Args
    origin: str  # "both" (unchanged by the PR), "base" (the PR removed or changed it), "head"
    quote: str
    expected: str = ""  # a literal (eq), the printed repr (repr) or an exception name (raises)
    compare: str = "eq"


@dataclass(frozen=True)
class Evidence:
    """What can explain, contradict or annotate a change: all of it from text and code, read by
    our own code. The PR's own tests and docstrings never explain a change (an AI fix often
    writes them to match its own behaviour)."""

    repro: frozenset[tuple[str, Args]] = frozenset()  # literal calls of a test that reproduced
    # The same calls, check by check (the calls inside one failing assert): blind spots.
    checks: frozenset[frozenset[tuple[str, Args]]] = frozenset()
    issue: frozenset[tuple[str, Args]] = frozenset()  # literal calls written in the issue
    witnesses: frozenset[tuple[str, Args]] = frozenset()  # the project's untouched tests
    pr_tests: frozenset[tuple[str, Args]] = frozenset()  # tests the PR added or changed
    docs: Mapping[str, DocInfo] = field(default_factory=dict, hash=False)


@dataclass(frozen=True)
class Change:
    target: str
    index: int
    args: Args
    phase: str
    kind: Kind
    before: Seen = field(hash=False)
    after: Seen = field(hash=False)
    explains: tuple[str, ...] = ()  # why this change is the one the fix is for
    contradicts: tuple[str, ...] = ()  # a documented promise it breaks: blocks L3
    notes: tuple[str, ...] = ()  # advisory facts, shown, never decide
    id: str = ""  # "c1", ... for a change shown to the Judge

    @property
    def also(self) -> tuple[str, ...]:
        """What else differs on this input besides its kind (verifier round 8, B1)."""
        return also_differs(self.before, self.after, self.kind)

    @property
    def group_key(self) -> tuple[str, str, str, str]:
        own = (Kind.MESSAGE, Kind.OUTPUT, Kind.ARGUMENTS, Kind.STATE)
        extra = self.kind.value if self.kind in own else ""
        extra += "".join(f"+{aspect}" for aspect in self.also)  # its own group, explained apart
        return self.target, outcome_class(self.before), outcome_class(self.after), extra


@dataclass(frozen=True)
class Comparison:
    """One target's comparison: how many inputs were listed, compared, the same, and lost."""

    target: str
    inputs: int
    compared: int
    same: int
    lost: Mapping[str, int] = field(default_factory=dict, hash=False)  # reason -> count
    exhausted: bool = False  # the generator made every input it could
    # Compared inputs that count toward the input floor: all but the reproduction test's own
    # calls, which a model wrote (verifier round 5, S5).
    counted: int | None = None

    @property
    def toward_floor(self) -> int:
        return self.compared if self.counted is None else self.counted

    @property
    def changed(self) -> int:
        return self.compared - self.same


def _tags(
    tid: str, args: Args, before: Seen, after: Seen, evidence: Evidence
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    explains, contradicts, notes = [], [], []
    if (tid, args) in evidence.repro:
        explains.append("the reproduction test calls this input")
    if (tid, args) in evidence.issue:
        explains.append("the issue names this call")
    for doc_id, doc in sorted(evidence.docs.items()):
        if doc.target != tid or doc.args != args:
            continue
        was, now = before.docs.get(doc_id), after.docs.get(doc_id)
        if was == "violated" and now == "holds":
            if doc.origin == "both":
                explains.append(f"it now keeps the docstring example {doc.quote}")
            elif doc.origin == "head":
                notes.append(f"it matches a docstring example the PR added: {doc.quote}")
        elif was == "holds" and now == "violated" and doc.origin in ("both", "base"):
            changed = "" if doc.origin == "both" else " (the PR removed or changed it)"
            contradicts.append(f"it breaks the docstring example {doc.quote}{changed}")
    if (tid, args) in evidence.witnesses:
        notes.append("an untouched project test calls this input")
    if (tid, args) in evidence.pr_tests:
        notes.append("the PR's new or changed tests call this input")
    return tuple(explains), tuple(contradicts), tuple(notes)


def compare_target(
    tid: str,
    inputs: Sequence[HeadInput],
    head: Mapping[int, Seen],
    base: Mapping[int, Seen],
    evidence: Evidence,
    *,
    dropped: int = 0,
    exhausted: bool = False,
) -> tuple[Comparison, list[Change]]:
    """Compare one target input by input. An input counts as compared only if both sides
    answered, both bind it, neither was unstable and at least one side returned or raised; a
    missing answer is "not compared", never "the same"."""
    lost: dict[str, int] = {"unrepresentable": dropped} if dropped else {}
    changes: list[Change] = []
    same = counted = not_inputs = 0
    for item in inputs:
        after, before = head.get(item.index), base.get(item.index)
        if _never_built(before, after):
            not_inputs += 1
            continue
        reason = _lost(before, after)
        if reason:
            lost[reason] = lost.get(reason, 0) + 1
            continue
        assert before is not None and after is not None
        counted += item.phase != "repro"
        kind = change_kind(before, after)
        if kind is None:
            same += 1
            continue
        explains, contradicts, notes = _tags(tid, item.args, before, after, evidence)
        changes.append(Change(tid, item.index, item.args, item.phase, kind, before, after,
                              explains, contradicts, notes))  # fmt: skip
    compared = same + len(changes)
    listed = len(inputs) - not_inputs + dropped
    comparison = Comparison(tid, listed, compared, same, lost, exhausted, counted)
    return comparison, changes


Look = tuple[Sequence[HeadInput], Mapping[int, Seen], Mapping[int, Seen]]


def blind_spots(
    checks: Iterable[frozenset[tuple[str, Args]]], looks: Mapping[str, Look]
) -> list[tuple[str, Args]]:
    """Reproduction checks our own recorded run proved changed (each failed before the fix and
    holds after it) in which the comparison sees no difference at all: every call in the check
    was compared, and each is the same. There the comparison is blind, so it can't vouch for
    the function (verifier round 5). One call that differs, or one not compared, is enough:
    a check also holding a helper the fix only refactored is not blind (round 7, S1). Each
    blind check is given by its first call."""
    blind = []
    for check in sorted(checks, key=repr):
        calls = sorted(check, key=repr)
        if calls and all(_compares_same(tid, args, looks) for tid, args in calls):
            blind.append(calls[0])
    return blind


def _compares_same(tid: str, args: Args, looks: Mapping[str, Look]) -> bool:
    if tid not in looks:
        return False
    inputs, head, base = looks[tid]
    for item in inputs:
        if item.args != args:
            continue
        after, before = head.get(item.index), base.get(item.index)
        if before is None or after is None or _lost(before, after):
            return False
        return change_kind(before, after) is None
    return False


def _never_built(before: Seen | None, after: Seen | None) -> bool:
    """A method's object failed to build on both sides, the same way: not an input at all,
    neither compared nor lost (M7.5 plan, D5)."""
    return (
        before is not None
        and after is not None
        and bool(before.unbuilt)
        and before.unbuilt == after.unbuilt
    )


def _lost(before: Seen | None, after: Seen | None) -> str:
    if before is None or after is None:
        return "no answer from one side"
    if before.unbindable or after.unbindable:
        # First: a side that can't take the input never tries to build its object either.
        return "does not fit the signature before the fix"
    if before.unbuilt or after.unbuilt:
        # Built on one side only, or failing differently: the constructor changed, and what the
        # method does there is never seen (M7.5 plan, D5).
        return UNBUILT
    if before.hung and after.hung:
        return "did not return on either side"
    if (not before.hung and before.outcome is None) or (not after.hung and after.outcome is None):
        return "unreadable answer"
    if (not before.hung and not before.stable) or (not after.hung and not after.stable):
        return "unstable (two calls disagreed)"
    for s in (before, after):
        opaque = s.outcome.get("opaque", "") if s.outcome is not None else ""
        if opaque:
            # A result whose whole state can't be read (a function, an iterator, C state) can't
            # be called "the same" (verifier round 5): not compared.
            return UNREAD_ARGUMENTS if opaque.startswith("the arguments") else UNREAD_RESULT
    if any(s.outcome is not None and s.outcome.get("data_opaque") for s in (before, after)):
        return UNREAD_DATA  # round 7, S2
    return ""


UNREAD_RESULT = "its result can't be compared in full"
UNREAD_ARGUMENTS = "its arguments can't be compared in full"
UNREAD_DATA = "the module data it uses can't be compared in full"
UNREAD = (UNREAD_RESULT, UNREAD_ARGUMENTS, UNREAD_DATA)
UNBUILT = "its object can be built on one side only (or fails differently)"


# --- groups ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ChangeGroup:
    """Changes of one kind on one target: the same outcome class before and after the fix."""

    key: tuple[str, str, str, str]  # target, before class, after class, message/output marker
    kind: Kind
    changes: tuple[Change, ...]  # every one, in input order
    shown: tuple[Change, ...] = ()  # the ones the Judge sees, with ids

    @property
    def target(self) -> str:
        return self.key[0]

    @property
    def explained(self) -> tuple[str, ...]:
        """Why this kind of change is the one the fix is for (empty: nothing explains it)."""
        return tuple(dict.fromkeys(reason for c in self.changes for reason in c.explains))

    @property
    def contradictions(self) -> tuple[Change, ...]:
        return tuple(c for c in self.changes if c.contradicts)

    @property
    def needs_explaining(self) -> bool:
        """A new message alone needs no explanation; with anything else changed, it does."""
        return self.kind not in EXEMPT or bool(self.changes[0].also)


def group_changes(changes: Iterable[Change]) -> list[ChangeGroup]:
    """Group by (target, before class, after class); contradicted groups first, then the
    unexplained ones, then the rest; larger groups first within each."""
    grouped: dict[tuple[str, str, str, str], list[Change]] = {}
    for change in changes:
        grouped.setdefault(change.group_key, []).append(change)
    groups = [ChangeGroup(key, members[0].kind, tuple(members)) for key, members in grouped.items()]

    def rank(g: ChangeGroup) -> tuple[bool, bool, int, tuple[str, str, str, str]]:
        return not g.contradictions, bool(g.explained), -len(g.changes), g.key

    return sorted(groups, key=rank)


def shape(source: str) -> str:
    """A coarse shape of one literal value, so the Judge sees different kinds of input."""
    try:
        value = from_source(source)
    except ValueError:
        return "?"
    if value is None or isinstance(value, bool):
        return repr(value)
    if isinstance(value, int):
        size = "huge" if abs(value) >= HUGE else "small"
        return "0" if value == 0 else f"{'-' if value < 0 else '+'}{size}"
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return repr(value)
        return "0.0" if value == 0 else f"{'-' if value < 0 else '+'}float"
    if isinstance(value, str | bytes):
        text = value.decode("latin-1") if isinstance(value, bytes) else value
        if not text:
            return f"empty {type(value).__name__}"
        if not text.strip():
            return "blank"
        if len(text) >= LONG_TEXT:
            return "long"
        return "text" if text.isascii() else "non-ascii"
    if isinstance(value, list | tuple | set | frozenset | dict):
        return f"{'empty ' if not value else ''}{type(value).__name__}"
    return type(value).__name__


def _direction(change: Change) -> str:
    """For numbers on both sides: did the result go up or down."""
    a, b = change.before.outcome, change.after.outcome
    if not a or not b or a["kind"] != "returned" or b["kind"] != "returned":
        return ""
    try:  # the shown text may be cut short: then it is no number
        old, new = from_source(a["text"]), from_source(b["text"])
    except ValueError:
        return ""
    if type(old) in (int, float) and type(new) in (int, float):
        assert isinstance(old, int | float) and isinstance(new, int | float)
        return "up" if new > old else "down" if new < old else ""
    return ""


def _variety(change: Change) -> tuple[str, ...]:
    return (*(f"{name}:{shape(source)}" for name, source in change.args), _direction(change))


def _rank(change: Change) -> tuple[bool, bool, bool, int, int, int]:
    # Measured as ASCII: repr prints a character or its escape depending on the Python version.
    size = sum(len(source.encode("ascii", "backslashreplace")) for _, source in change.args)
    return (
        not change.contradicts,
        not change.explains,
        not change.notes,
        PHASE_RANK.get(change.phase, 9),  # draws last: they depend on the Hypothesis version
        size,
        change.index,
    )


def _shapes(group: ChangeGroup) -> list[Change]:
    """One change of each shape of input (and direction of the result) in a group, best ranked
    first: the ones the Judge must see."""
    picked: list[Change] = []
    seen: set[tuple[str, ...]] = set()
    for change in sorted(group.changes, key=_rank):
        if _variety(change) not in seen:
            seen.add(_variety(change))
            picked.append(change)
    return picked


def choose_shown(
    groups: Sequence[ChangeGroup],
    per_group: int = SHOWN_PER_GROUP,
    in_all: int = SHOWN_IN_ALL,
) -> tuple[list[ChangeGroup], bool]:
    """The groups with the changes the Judge is shown (ids c1, c2, ... in order), and whether all
    that must be shown fit: one change of every shape of input in every group (round 5: a shape
    the Judge never saw can't be vetoed). If they fit, the rest of the budget goes to the best
    ranked other changes, up to `per_group` per group; if not, L3 is out of reach."""
    must = {g.key: _shapes(g) for g in groups}
    needed = sum(len(m) for m in must.values())
    left = max(0, in_all - needed)
    chosen: dict[tuple[str, str, str, str], list[Change]] = {}
    budget = in_all
    for g in groups:
        take = must[g.key][:budget]
        budget -= len(take)
        chosen[g.key] = take
    for g in groups:
        rest = [c for c in sorted(g.changes, key=_rank) if c not in chosen[g.key]]
        extra = min(left, max(0, per_group - len(chosen[g.key])), len(rest))
        chosen[g.key] += rest[:extra]
        left -= extra
    number = 0
    out: list[ChangeGroup] = []
    for g in groups:
        shown = []
        for change in sorted(chosen[g.key], key=_rank):
            number += 1
            shown.append(replace(change, id=f"c{number}"))
        out.append(replace(g, shown=tuple(shown)))
    return out, needed <= in_all


def call_text(target: AttackTarget, args: Args) -> str:
    """`bucket_of(value=-5, width=10)`: an input as a call, for people and the Judge; a method's
    on the object its input builds (`Listener(default_port=9000).port(raw=None)`) or on its
    class (`Version.parse(text='1.2')`), a property as a read (`Version(1).label`)."""
    given = dict(args)
    shown = ", ".join(f"{name}={source}" for name, source in args if name != RECEIVER)
    if not target.owner:
        return f"{target.name}({shown})"
    on = target.owner
    if target.has_receiver:
        try:
            code = from_source(given.get(RECEIVER, "''"))
        except ValueError:
            code = None
        on = code if isinstance(code, str) and code else f"{target.owner}(...)"
    if target.kind == "property":
        return f"{on}.{target.name}"
    return f"{on}.{target.name}({shown})"


# --- the L3 gate ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Gate:
    allowed: bool
    reasons: tuple[str, ...] = ()  # why not, in plain words (empty when allowed)


def insufficient(c: Comparison, name: str) -> str | None:
    """Why one target's comparison is too thin to vouch for, or None."""
    if c.compared == 0:
        return f"{name}: no input could be compared"
    if c.toward_floor < MIN_COMPARED and not c.exhausted:
        return (
            f"{name}: only {c.toward_floor} inputs compared besides the reproduction test's own "
            f"(at least {MIN_COMPARED} needed)"
        )
    unread = sum(n for r, n in c.lost.items() if r in UNREAD)
    if unread:
        # Unlike a call that hung or gave two answers, these are a kind of outcome the diff
        # can't see into: a change there would never show (verifier round 7), so none is
        # allowed, not even within the lost share.
        return f"{name}: {unread} input(s) whose outcome can't be read in full"
    if c.lost.get(UNBUILT):
        # The same for an object only one side can build: never allowed (M7.5 plan, D5).
        return f"{name}: {c.lost[UNBUILT]} input(s) whose object only one side could build"
    lost = sum(c.lost.values())
    if c.inputs and lost / c.inputs > MAX_LOST_SHARE:
        why = ", ".join(f"{n} {r}" for r, n in sorted(c.lost.items()) if n)
        return f"{name}: {lost} of {c.inputs} inputs could not be compared ({why})"
    return None


def checks_gate(
    incomplete: Sequence[str],
    comparisons: Sequence[tuple[str, Comparison]],
    groups: Sequence[ChangeGroup],
    all_shown: bool,
) -> Gate:
    """Whether the behaviour diff allows L3 by deterministic checks alone (no model output):
    1. it examined every changed function to the end (`incomplete` lists what it didn't);
    2. each target was compared on enough inputs, with few lost;
    3. every kind of change is explained by the reproduction test, the issue or a docstring
       example (an error message's wording is exempt);
    4. no change breaks a docstring example;
    5. every group can be shown to the Judge."""
    reasons = list(incomplete)
    reasons += [r for name, c in comparisons if (r := insufficient(c, name)) is not None]
    for g in groups:
        if g.needs_explaining and not g.explained:
            reasons.append(
                f"{len(g.changes)} input(s) changed from '{g.key[1]}' to '{g.key[2]}' and "
                "nothing explains it (not the reproduction test, the issue or a docstring example)"
            )
        for change in g.contradictions[:1]:
            reasons.append(change.contradicts[0])
    if not all_shown:
        reasons.append("more kinds or shapes of change than can be shown to the Judge")
    return Gate(not reasons, tuple(reasons))


def l3_gate(checks: Gate, groups: Sequence[ChangeGroup], labels: Mapping[str, str]) -> Gate:
    """`checks` plus the Judge, who can only veto: with changes, every shown change needs the
    label "intended"; one "suspicious" label, or a missing one (no Judge, a failed call, a
    skipped id), keeps L3 out of reach. Nothing here can turn a "not allowed" into "allowed"."""
    reasons = list(checks.reasons)
    shown = [c for g in groups for c in g.shown]
    suspicious = [c.id for c in shown if labels.get(c.id) == "suspicious"]
    unlabelled = [c.id for c in shown if labels.get(c.id) not in ("intended", "suspicious")]
    if suspicious:
        reasons.append(f"the Judge labelled {', '.join(suspicious)} suspicious")
    if unlabelled:
        reasons.append(f"no Judge label for {', '.join(unlabelled)}")
    return Gate(checks.allowed and not reasons, tuple(reasons))

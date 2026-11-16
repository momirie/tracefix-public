"""M7: the behaviour diff's pure rules (behaviour_rules): reading reports, comparing, tags,
groups, what the Judge is shown, and the L3 gate, with property tests that a Judge label can
never raise the level."""

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from tracefix import behaviour_rules as br
from tracefix.attack_inputs import Args, AttackTarget, Param
from tracefix.behaviour_rules import (
    Change,
    ChangeGroup,
    Comparison,
    DiffEvents,
    DocInfo,
    Evidence,
    Gate,
    HeadInput,
    Kind,
    Seen,
)


def target(tid: str = "t1", params: Sequence[str] = ("value", "width")) -> AttackTarget:
    return AttackTarget(
        tid,
        "src/stats/buckets.py",
        "bucket_of",
        tuple(Param(p, "positional", "int", False) for p in params),
        (1, 5),
        "def bucket_of(value, width):",
        "def bucket_of(value, width): ...",
        "",
        "",
        "",
        (),
        ("stats.buckets",),
    )


def returned(text: str, digest: str = "", type_: str = "int", out: str = "") -> dict[str, str]:
    return {"kind": "returned", "type": type_, "module": "builtins", "text": text,
            "digest": digest or format(abs(hash(text)) % 16**12, "x"), "out": out}  # fmt: skip


def raised(type_: str, text: str = "", where: str = "repo", digest: str = "") -> dict[str, str]:
    return {"kind": "raised", "type": type_, "module": "builtins", "text": text,
            "digest": digest or format(abs(hash(type_ + text)) % 16**12, "x"), "out": "",
            "where": where}  # fmt: skip


def seen(outcome: dict[str, str] | None, **extra: Any) -> Seen:
    return Seen(outcome, extra.pop("stable", True), **extra)


def args(**values: int | str) -> Args:
    return tuple((k, str(v)) for k, v in values.items())


# --- reading the runs' reports --------------------------------------------------------------------


def test_a_malformed_outcome_is_no_outcome() -> None:
    good = returned("0", "ab12")
    assert br.diff_outcome_of(good) is not None
    assert br.diff_outcome_of({**good, "digest": "not hex"}) is None
    assert br.diff_outcome_of({**good, "digest": ""}) is None
    assert br.diff_outcome_of({**good, "type": "int; import os"}) is None
    assert br.diff_outcome_of({**good, "module": ""}) is None
    assert br.diff_outcome_of({**good, "out": "zz"}) is None
    assert br.diff_outcome_of({**good, "args": "not hex"}) is None
    assert br.diff_outcome_of({**good, "kind": "printed"}) is None
    assert br.diff_outcome_of("returned") is None
    assert br.diff_outcome_of(raised("ValueError", where="anywhere"))["where"] == "python"  # type: ignore[index]


def test_reports_are_validated_and_the_first_answer_for_an_input_wins() -> None:
    t = target()
    events: list[dict[str, Any]] = [
        {"event": "target", "target": "t1", "module": "stats.buckets"},
        {"event": "input", "target": "t1", "index": 0, "phase": "doc",
         "args": {"value": "-5", "width": "10"}},
        {"event": "input", "target": "t1", "index": 2, "phase": "draw",
         "args": {"value": "1", "width": "1"}},  # out of order: ignored
        {"event": "input", "target": "t1", "index": 1, "phase": "draw",
         "args": {"value": "os.system('x')", "width": "1"}},  # not a literal: ignored
        {"event": "input", "target": "t9", "index": 0, "args": {}},  # unknown target
        {"event": "outcome", "target": "t1", "index": 0, "outcome": returned("0", "aa"),
         "stable": True, "docs": {"t1.doc1": "holds", "t1.doc2": "lies"}},
        {"event": "outcome", "target": "t1", "index": 0, "outcome": returned("9", "bb"),
         "stable": True},  # a later answer for the same input
        {"event": "outcome", "target": "t1", "index": 3, "unbindable": "no parameter x here"},
        {"event": "outcome", "target": "t1", "index": 10**9, "outcome": returned("1", "cc")},
        {"event": "end", "target": "t1", "reached": {"src/stats/buckets.py": [7, "x"]}},
    ]  # fmt: skip
    into = DiffEvents()
    br.read_diff_events(events, {"t1": t}, into)
    assert into.modules == {"t1": "stats.buckets"}
    assert into.inputs["t1"] == [HeadInput(0, "doc", (("value", "-5"), ("width", "10")))]
    first = into.seen["t1"][0]
    assert first.outcome is not None and first.outcome["text"] == "0"
    assert first.docs == {"t1.doc1": "holds"}
    assert into.seen["t1"][3].unbindable == "no parameter x here"
    assert 10**9 not in into.seen["t1"]
    assert into.ended == {"t1"} and into.reached["t1"] == {"src/stats/buckets.py": {7}}


# --- comparing ------------------------------------------------------------------------------------


def test_each_kind_of_change_is_named() -> None:
    zero, ten = returned("0", "a0"), returned("-10", "a1")
    cases = [
        (zero, ten, Kind.VALUE),
        (zero, returned("0.0", "a2", "float"), Kind.TYPE),
        (zero, raised("ValueError"), Kind.NEW_RAISE),
        (raised("ValueError"), zero, Kind.NO_RAISE),
        (raised("ValueError", "x"), raised("TypeError", "x"), Kind.EXCEPTION),
        (raised("ValueError", "a"), raised("ValueError", "b"), Kind.MESSAGE),
        (zero, {**zero, "out": "ff"}, Kind.OUTPUT),
        ({**zero, "args": "a1"}, {**zero, "args": "a2"}, Kind.ARGUMENTS),
        (zero, zero, None),
    ]
    for before, after, kind in cases:
        assert br.change_kind(seen(before), seen(after)) is kind, (before, after)
    assert br.change_kind(seen(zero), Seen(hung=True)) is Kind.HANG


def test_two_values_whose_shown_text_is_the_same_still_differ_by_digest() -> None:
    a, b = returned("x" * 300, "a1"), returned("x" * 300, "b2")
    assert br.change_kind(seen(a), seen(b)) is Kind.VALUE


def head_and_base(
    pairs: Sequence[tuple[Args, Seen | None, Seen | None]], phase: str = "draw"
) -> tuple[list[HeadInput], dict[int, Seen], dict[int, Seen]]:
    inputs = [HeadInput(i, phase, a) for i, (a, _, _) in enumerate(pairs)]
    head = {i: h for i, (_, h, _) in enumerate(pairs) if h is not None}
    base = {i: b for i, (_, _, b) in enumerate(pairs) if b is not None}
    return inputs, head, base


def test_an_input_counts_as_compared_only_when_both_sides_answered_cleanly() -> None:
    ok = seen(returned("1", "a1"))
    pairs = [
        (args(value=1, width=1), ok, ok),  # the same
        (args(value=2, width=1), ok, None),  # base never answered
        (args(value=3, width=1), ok, Seen(unbindable="no parameter width here")),
        (args(value=4, width=1), seen(returned("1", "a1"), stable=False), ok),
        (args(value=5, width=1), Seen(hung=True), Seen(hung=True)),
        (args(value=6, width=1), seen(None), ok),
        (args(value=7, width=1), Seen(hung=True), ok),  # a hang on one side is a change
    ]
    comparison, changes = br.compare_target("t1", *head_and_base(pairs), Evidence(), dropped=2)
    assert comparison.inputs == 9 and comparison.compared == 2 and comparison.same == 1
    assert comparison.lost == {
        "unrepresentable": 2,
        "no answer from one side": 1,
        "does not fit the signature before the fix": 1,
        "unstable (two calls disagreed)": 1,
        "did not return on either side": 1,
        "unreadable answer": 1,
    }
    assert [(c.index, c.kind) for c in changes] == [(6, Kind.HANG)]


DOC = DocInfo("t1.doc1", "t1", args(value=-5, width=10), "both", "`bucket_of(-5, 10) == 0`")


def test_what_explains_contradicts_or_annotates_a_change() -> None:
    a = args(value=-5, width=10)
    evidence = Evidence(
        repro=frozenset({("t1", args(value=15, width=10))}),
        issue=frozenset({("t1", args(value=25, width=10))}),
        witnesses=frozenset({("t1", a)}),
        pr_tests=frozenset({("t1", a), ("t1", args(value=35, width=10))}),
        docs={DOC.id: DOC},
    )
    before = seen(returned("0", "b0"), docs={DOC.id: "holds"})
    after = seen(returned("-10", "b1"), docs={DOC.id: "violated"})
    plain_b, plain_a = seen(returned("1", "c0")), seen(returned("2", "c1"))
    pairs = [
        (a, after, before),
        (args(value=15, width=10), plain_a, plain_b),
        (args(value=25, width=10), plain_a, plain_b),
        (args(value=35, width=10), plain_a, plain_b),
    ]
    _, changes = br.compare_target("t1", *head_and_base(pairs), evidence)
    broken, repro, issue, pr = changes
    assert broken.contradicts == ("it breaks the docstring example `bucket_of(-5, 10) == 0`",)
    assert broken.notes == (
        "an untouched project test calls this input",
        "the PR's new or changed tests call this input",
    )
    assert repro.explains == ("the reproduction test calls this input",)
    assert issue.explains == ("the issue names this call",)
    # The PR's own tests never explain a change: an AI fix writes them to fit itself.
    assert pr.explains == () and pr.notes == ("the PR's new or changed tests call this input",)


def test_docstring_examples_explain_only_when_the_pr_left_them_alone() -> None:
    a = args(value=-5, width=10)

    def tags(origin: str, was: str, now: str) -> Change:
        doc = DocInfo("t1.d", "t1", a, origin, "`x`")
        before = seen(returned("0", "d0"), docs={"t1.d": was})
        after = seen(returned("1", "d1"), docs={"t1.d": now})
        _, [change] = br.compare_target(
            "t1", [HeadInput(0, "doc", a)], {0: after}, {0: before}, Evidence(docs={"t1.d": doc})
        )
        return change

    assert tags("both", "violated", "holds").explains == ("it now keeps the docstring example `x`",)
    head_only = tags("head", "violated", "holds")
    assert head_only.explains == () and "the PR added" in head_only.notes[0]
    removed = tags("base", "holds", "violated")
    assert removed.contradicts == (
        "it breaks the docstring example `x` (the PR removed or changed it)",
    )
    assert tags("head", "holds", "violated").contradicts == ()
    assert tags("both", "oracle_error", "holds").explains == ()


# --- groups and what the Judge is shown -----------------------------------------------------------


def change(
    index: int,
    before: dict[str, str],
    after: dict[str, str],
    *,
    tid: str = "t1",
    phase: str = "draw",
    value: int | None = None,
    **tags: tuple[str, ...],
) -> Change:
    b, a = seen(before), seen(after)
    kind = br.change_kind(b, a)
    assert kind is not None
    return Change(tid, index, args(value=index if value is None else value, width=10), phase,
                  kind, b, a, **tags)  # fmt: skip


def test_changes_are_grouped_by_what_happened_before_and_after() -> None:
    changes = [
        change(1, returned("1", "e1"), returned("2", "e2"), explains=("repro",)),
        change(2, returned("1", "e1"), returned("3", "e3")),
        change(3, returned("1", "e1"), raised("ValueError")),
        change(4, raised("ValueError", "a"), raised("ValueError", "b")),
        change(5, returned("1", "e1"), returned("0", "e0"), contradicts=("breaks a doc",)),
        change(6, returned("1", "e1"), raised("ValueError"), tid="t2"),
    ]
    groups = br.group_changes(changes)
    keys = [(g.key, len(g.changes)) for g in groups]
    # Contradicted first, then the unexplained ones (bigger first), then the explained ones.
    assert keys[0] == (("t1", "returns int", "returns int", ""), 3)
    assert {k for k, _ in keys[1:]} == {
        ("t1", "returns int", "raises ValueError", ""),
        ("t1", "raises ValueError", "raises ValueError", "message"),
        ("t2", "returns int", "raises ValueError", ""),
    }
    assert groups[0].explained == ("repro",) and len(groups[0].contradictions) == 1
    message = next(g for g in groups if g.kind is Kind.MESSAGE)
    assert not message.needs_explaining


def test_the_judge_sees_the_telling_changes_first_and_variety_after() -> None:
    inputs = [(5, "draw"), (6, "draw"), (-7, "draw"), (-8, "draw"), (0, "boundary"), (9, "doc")]
    changes = [
        change(i, returned("1", "f1"), returned("2", f"f{i + 2}"), value=v, phase=p)
        for i, (v, p) in enumerate(inputs)
    ]
    changes[1] = replace(changes[1], explains=("the issue names this call",))
    [group], all_shown = br.choose_shown(br.group_changes(changes), per_group=4)
    assert all_shown
    assert [c.id for c in group.shown] == ["c1", "c2", "c3", "c4"]
    # One change of each shape of input (the explained one, a zero, a negative), then the
    # best-ranked of the rest (the docstring example, before any draw); shown in rank order.
    assert [c.index for c in group.shown] == [1, 5, 4, 2]


def test_every_shape_of_input_is_shown_even_past_the_per_group_cap() -> None:
    # Round 5: a shape of change the Judge never saw can't be vetoed.
    values = [0, 1, -1, 2**40, -(2**40), 7, 8, 9]
    changes = [change(i, returned("1", "s1"), returned("2", f"s{i + 2}"), value=v)
               for i, v in enumerate(values)]  # fmt: skip
    [group], all_shown = br.choose_shown(br.group_changes(changes), per_group=2, in_all=40)
    shapes = {br.shape(dict(c.args)["value"]) for c in group.shown}
    assert all_shown and shapes == {"0", "+small", "-small", "+huge", "-huge"}
    _, fits = br.choose_shown(br.group_changes(changes), per_group=2, in_all=4)
    assert not fits  # five shapes, room for four: L3 is out of reach


def test_logged_output_warnings_and_stderr_count_as_output() -> None:
    zero = returned("0", "t0")
    assert br.change_kind(seen(zero), seen({**zero, "side": "ab"})) is Kind.OUTPUT
    assert br.diff_outcome_of({**zero, "side": "not hex"}) is None


def test_every_group_is_shown_once_before_any_gets_more() -> None:
    singles = [change(i, returned("1", "g1"), returned(str(i), f"g{i + 2}"), tid=f"t{i}")
               for i in range(4)]  # fmt: skip
    more = [change(10 + i, returned("1", "g1"), returned("x", f"h{i}"), tid="t0") for i in range(5)]
    groups = br.group_changes(singles + more)
    shown, all_shown = br.choose_shown(groups, per_group=5, in_all=6)
    assert all_shown and sum(len(g.shown) for g in shown) == 6
    assert all(g.shown for g in shown)
    ids = [c.id for g in shown for c in g.shown]
    assert ids == [f"c{n}" for n in range(1, 7)]
    _, too_many = br.choose_shown(groups, per_group=5, in_all=3)
    assert not too_many  # more groups than can be shown


def test_shapes() -> None:
    assert [br.shape(s) for s in ("0", "-3", "2147483647", "None", "True")] == [
        "0", "-small", "+huge", "None", "True"]  # fmt: skip
    assert [br.shape(s) for s in ("''", "'  '", "'é'", repr("a" * 100), "[]", "(1,)")] == [
        "empty str", "blank", "non-ascii", "long", "empty list", "tuple"]  # fmt: skip
    assert br.shape('float("nan")') == "nan" and br.shape("os.system(1)") == "?"


# --- the L3 gate ----------------------------------------------------------------------------------


def comparison(compared: int = 200, **lost: int) -> tuple[str, Comparison]:
    total = compared + sum(lost.values())
    return "bucket_of", Comparison("t1", total, compared, compared - 1, lost)


def explained_group() -> list[ChangeGroup]:
    groups = br.group_changes(
        [change(1, returned("1", "j1"), returned("2", "j2"), explains=("repro",))]
    )
    shown, _ = br.choose_shown(groups)
    return shown


def test_the_checks_allow_l3_only_when_every_condition_holds() -> None:
    groups = explained_group()
    assert br.checks_gate([], [comparison()], groups, True) == Gate(True)
    assert not br.checks_gate(["a changed method was not compared"], [comparison()], groups,
                              True).allowed  # fmt: skip
    assert not br.checks_gate([], [comparison(10)], groups, True).allowed
    assert not br.checks_gate([], [comparison(100, unstable=40)], groups, True).allowed
    assert not br.checks_gate([], [comparison(0)], groups, True).allowed
    assert not br.checks_gate([], [comparison()], groups, False).allowed
    few = ("bucket_of", Comparison("t1", 10, 10, 9, {}, exhausted=True))
    assert br.checks_gate([], [few], groups, True).allowed  # every input it could make


def test_an_unexplained_kind_of_change_or_a_broken_docstring_blocks_l3() -> None:
    unexplained = br.choose_shown(br.group_changes(
        [change(1, returned("1", "k1"), raised("ValueError"))]))[0]  # fmt: skip
    gate = br.checks_gate([], [comparison()], unexplained, True)
    assert not gate.allowed and "nothing explains it" in gate.reasons[0]
    contradicted = br.choose_shown(br.group_changes([change(
        1, returned("1", "k1"), returned("2", "k2"), explains=("repro",),
        contradicts=("it breaks the docstring example `f(1) == 1`",))]))[0]  # fmt: skip
    gate = br.checks_gate([], [comparison()], contradicted, True)
    assert gate.reasons == ("it breaks the docstring example `f(1) == 1`",)
    message = br.choose_shown(br.group_changes(
        [change(1, raised("ValueError", "a"), raised("ValueError", "b"))]))[0]  # fmt: skip
    assert br.checks_gate([], [comparison()], message, True).allowed  # wording is exempt


def test_the_judge_can_only_veto() -> None:
    groups = explained_group()
    checks = br.checks_gate([], [comparison()], groups, True)
    assert br.l3_gate(checks, groups, {"c1": "intended"}) == checks
    assert not br.l3_gate(checks, groups, {"c1": "suspicious"}).allowed
    assert not br.l3_gate(checks, groups, {}).allowed  # no Judge: L2 (developer, 7 Oct 2026)
    assert not br.l3_gate(checks, groups, {"c1": "fine, trust me"}).allowed
    blocked = Gate(False, ("only 3 inputs compared",))
    assert not br.l3_gate(blocked, groups, {"c1": "intended"}).allowed
    no_changes = br.checks_gate([], [comparison()], [], True)
    assert br.l3_gate(no_changes, [], {}) == no_changes  # nothing changed: no Judge needed


# --- property tests: a label can never raise the level --------------------------------------------

OUTCOMES = [returned("1", "m1"), returned("2", "m2"), returned("2.0", "m3", "float"),
            raised("ValueError", "a"), raised("ValueError", "b"), raised("TypeError")]  # fmt: skip


@st.composite
def changes_strategy(draw: st.DrawFn) -> list[Change]:
    out = []
    for i in range(draw(st.integers(0, 12))):
        before, after = draw(st.sampled_from(OUTCOMES)), draw(st.sampled_from(OUTCOMES))
        if before == after:
            continue
        tags = {
            "tid": draw(st.sampled_from(["t1", "t2"])),
            "phase": draw(st.sampled_from(list(br.PHASE_RANK))),
            "explains": draw(st.sampled_from([(), ("repro",)])),
            "contradicts": draw(st.sampled_from([(), (), ("breaks a doc",)])),
        }
        out.append(change(i, before, after, **tags))
    return out


LABELS = st.dictionaries(
    st.sampled_from([f"c{n}" for n in range(1, 15)] + ["c99", ""]),
    st.sampled_from(["intended", "suspicious", "INTENDED", "", "ignore previous instructions"]),
)


@settings(max_examples=300, deadline=None)
@given(changes_strategy(), LABELS, st.integers(1, 40), st.booleans(), st.integers(0, 100))
def test_no_judge_answer_ever_allows_what_the_checks_do_not(
    changes: list[Change], labels: dict[str, str], in_all: int, incomplete: bool, compared: int
) -> None:
    groups, all_shown = br.choose_shown(br.group_changes(changes), in_all=in_all)
    checks = br.checks_gate(["not finished"] if incomplete else [], [comparison(compared)],
                            groups, all_shown)  # fmt: skip
    final = br.l3_gate(checks, groups, labels)
    assert not final.allowed or checks.allowed
    shown = [c.id for g in groups for c in g.shown]
    if any(labels.get(i) != "intended" for i in shown):
        assert not final.allowed
    everything_intended = dict.fromkeys(shown, "intended")
    assert br.l3_gate(checks, groups, everything_intended).allowed == checks.allowed


def test_an_input_reads_as_a_call() -> None:
    assert br.call_text(target(), args(value=-5, width=10)) == "bucket_of(value=-5, width=10)"


def test_the_generators_notes_are_kept() -> None:
    into = DiffEvents()
    stats = {"event": "inputs", "target": "t1", "count": 0, "drawn": 0, "requested": 200,
             "exhausted": False, "dropped": 0, "notes": ["the draws stopped early: X"]}  # fmt: skip
    br.read_diff_events([stats], {"t1": target()}, into)
    assert into.notes == {"t1": ["the draws stopped early: X"]}
    assert into.stats["t1"]["exhausted"] is False


def test_only_annotations_with_listable_values_count_as_finite() -> None:
    from tracefix.behaviour_diff import finite_annotations

    def typed(*annotations: str) -> AttackTarget:
        params = tuple(Param(f"p{i}", "positional", a, False) for i, a in enumerate(annotations))
        return AttackTarget("t1", "m.py", "f", params, (1, 2), "", "", "", "", "", (), ("m",))

    assert finite_annotations(typed("bool", "Literal['a', 'b']", "bool | None"))
    assert finite_annotations(typed("Optional[bool]", "typing.Literal[1]"))
    assert finite_annotations(typed())  # no parameters: its one call is every input
    for loose in ("int", "", "list[bool]", "Color", "bool | int", "Literal[1] | str"):
        assert not finite_annotations(typed(loose)), loose


# --- round 6 --------------------------------------------------------------------------------------


def test_an_opaque_result_is_never_the_same() -> None:
    opaque = returned("<fn>", "o1") | {"opaque": "a builtins.function keeps state"}
    pairs = [(args(value=1, width=1), seen(opaque), seen(opaque))]
    comparison, changes = br.compare_target("t1", *head_and_base(pairs), Evidence())
    assert comparison.compared == 0 and not changes
    assert comparison.lost == {"its result can't be compared in full": 1}


def test_the_floor_counts_no_reproduction_input() -> None:
    same = seen(returned("1", "r1"))
    inputs = [HeadInput(i, "repro" if i < 60 else "draw", args(value=i, width=1))
              for i in range(70)]  # fmt: skip
    answers = dict.fromkeys(range(70), same)
    comparison, _ = br.compare_target("t1", inputs, answers, answers, Evidence())
    assert comparison.compared == 70 and comparison.toward_floor == 10
    assert "besides the reproduction test's own" in str(br.insufficient(comparison, "f"))


def test_a_proven_change_the_comparison_calls_the_same_is_a_blind_spot() -> None:
    same = seen(returned("1", "b1"))
    proven = args(value=0, width=10)
    inputs = [HeadInput(0, "repro", proven), HeadInput(1, "draw", args(value=1, width=10))]
    check = frozenset({("t1", proven)})
    blind = br.blind_spots([check], {"t1": (inputs, {0: same, 1: same}, {0: same, 1: same})})
    assert blind == [("t1", proven)]
    changed = {0: seen(returned("2", "b2")), 1: same}
    assert br.blind_spots([check], {"t1": (inputs, changed, {0: same, 1: same})}) == []


def test_a_check_is_blind_only_if_none_of_its_calls_differs() -> None:
    # Verifier round 7, S1: `assert (sign(0), double(2)) == ...` where only sign changed.
    same, other = seen(returned("1", "b1")), seen(returned("2", "b2"))
    sign, double = args(value=0, width=1), args(value=2, width=1)
    looks = {
        "sign": ([HeadInput(0, "repro", sign)], {0: other}, {0: same}),
        "double": ([HeadInput(0, "repro", double)], {0: same}, {0: same}),
    }
    check = frozenset({("sign", sign), ("double", double)})
    assert br.blind_spots([check], looks) == []
    looks["sign"] = ([HeadInput(0, "repro", sign)], {0: same}, {0: same})
    assert br.blind_spots([check], looks) == [("double", double)]  # every call the same: blind
    lost = seen(returned("1", "b1") | {"opaque": "builtins.map keeps state"})
    looks["sign"] = ([HeadInput(0, "repro", sign)], {0: lost}, {0: lost})
    assert br.blind_spots([check], looks) == []  # a call not compared: can't say


def test_an_exception_whose_state_changed_is_not_a_message_change() -> None:
    # Round 7: only the wording alone is exempt; fields, cause or attributes are not.
    a = seen(raised("ValueError", "x1") | {"rest": "aa"})
    worded = seen(raised("ValueError", "x2") | {"rest": "aa"})
    deeper = seen(raised("ValueError", "x2") | {"rest": "bb"})
    assert br.change_kind(a, worded) is Kind.MESSAGE
    assert br.change_kind(a, deeper) is Kind.EXCEPTION


def test_inputs_lost_to_module_data_or_arguments_say_so() -> None:
    plain = returned("1", "c1")
    data = seen(plain | {"data_opaque": "too large to compare in full"})
    argued = seen(plain | {"opaque": "the arguments: builtins.map keeps state"})
    pairs = [(args(value=1, width=1), data, data), (args(value=2, width=1), argued, argued)]
    comparison, _ = br.compare_target("t1", *head_and_base(pairs), Evidence())
    assert dict(comparison.lost) == {
        "the module data it uses can't be compared in full": 1,
        "its arguments can't be compared in full": 1,
    }


def test_output_and_argument_changes_show_what_differs() -> None:
    before = seen(returned("1", "w1") | {"out_text": "a", "side_text": "log INFO x: 1"})
    after = seen(returned("1", "w1") | {"out_text": "b", "side_text": "log INFO x: 2"})
    assert "printed 'a'" in br.shown_side(before, Kind.OUTPUT)
    assert "log INFO x: 2" in br.shown_side(after, Kind.OUTPUT)
    moved = seen(returned("None", "w2") | {"args_text": "[('items', [1, 2])]"})
    assert "[1, 2]" in br.shown_side(moved, Kind.ARGUMENTS)


def test_module_data_left_different_is_its_own_kind() -> None:
    zero = returned("0", "m0")
    assert br.change_kind(seen(zero), seen({**zero, "state": "ab"})) is Kind.STATE
    assert br.diff_outcome_of({**zero, "state": "not hex"}) is None
    shown = seen({**zero, "state": "ab", "state_text": "{'SEEN': [1]}"})
    assert "[1]" in br.shown_side(shown, Kind.STATE)


def test_one_input_that_cannot_be_read_in_full_blocks_l3_whatever_the_share() -> None:
    # Verifier round 7: re.search's Match objects were 18% of the inputs, under the 20% lost
    # share, and the change hid exactly there.
    same = seen(returned("1", "s1"))
    opaque = seen(returned("<m>", "o1") | {"opaque": "re.Match keeps state Tracefix can't read"})
    pairs = [(args(value=i, width=1), same, same) for i in range(99)]
    pairs.append((args(value=99, width=1), opaque, opaque))
    comparison, _ = br.compare_target("t1", *head_and_base(pairs), Evidence())
    assert comparison.compared == 99
    reason = br.insufficient(comparison, "find")
    assert reason == "find: 1 input(s) whose outcome can't be read in full"
    assert not br.checks_gate([], [("find", comparison)], [], True).allowed


# --- round 8 --------------------------------------------------------------------------------------


def test_a_new_message_with_other_changes_needs_explaining_and_shows_them() -> None:
    # Verifier round 8, B1: a reworded error hid a list it now appends to and module data it
    # writes, needed no explanation, and the Judge saw only the two messages.
    before = seen(
        raised("ValueError", "no items", digest="m1")
        | {"rest": "aa", "args": "a1", "args_text": "[1]"}
    )
    after = seen(raised("ValueError", "no item", digest="m2") | {"rest": "aa", "args": "a2",
                 "args_text": "[1, 99]", "state": "b2", "state_text": "{'n': 1}"})  # fmt: skip
    pairs = [(args(value=1, width=1), before, after)]
    _, changes = br.compare_target("t1", *head_and_base(pairs), Evidence())
    [change] = changes
    assert change.kind is Kind.MESSAGE and change.also == ("arguments", "state")
    [group] = br.group_changes(changes)
    assert group.needs_explaining
    assert not br.checks_gate([], [], [group], True).allowed
    side = br.shown_side(after, change.kind, change.also)
    assert "left its arguments as [1, 99]" in side and "left module data as {'n': 1}" in side


def test_an_explained_value_change_does_not_cover_one_that_also_changes_arguments() -> None:
    one, two = args(value=1, width=1), args(value=2, width=1)
    pairs = [
        (one, seen(returned("1", "v1")), seen(returned("2", "v2"))),
        (
            two,
            seen(returned("1", "v1") | {"args": "a1"}),
            seen(returned("2", "v2") | {"args": "a2"}),
        ),
    ]
    evidence = Evidence(repro=frozenset({("t1", one)}))
    _, changes = br.compare_target("t1", *head_and_base(pairs), evidence)
    groups = br.group_changes(changes)
    assert len(groups) == 2
    hidden = next(g for g in groups if g.changes[0].also)
    assert not hidden.explained and hidden.needs_explaining
    assert not br.checks_gate([], [], groups, True).allowed


def test_what_l3_does_not_claim_is_listed_for_the_receipt() -> None:
    # Developer, 8 Oct 2026: L3 means no unexplained change in what the diff observes; every
    # channel it doesn't observe goes to the receipt's `unchecked`.
    from tracefix.behaviour_diff import BehaviourResult, BehaviourStatus

    text = " ".join(br.UNOBSERVED)
    for channel in ("outside the copy", "lru_cache", "os.environ", "threads", "during a call"):
        assert channel in text, channel
    assert BehaviourResult(BehaviourStatus.SKIPPED, "").unobserved == br.UNOBSERVED


def test_files_a_function_changed_are_read_from_the_end_event() -> None:
    # Round 11: a function that changed files in the copy; the stage keeps L3 out of reach.
    into = br.DiffEvents()
    end = {"event": "end", "target": "t1", "unit": "diff", "files_changed": "app.log"}
    br.read_diff_events([end, {**end, "files_changed": 7}], {"t1": target()}, into)
    assert into.wrote == {"t1": "app.log"} and "t1" in into.ended


# --- methods (M7.5) -------------------------------------------------------------------------------


def test_an_object_built_on_one_side_only_blocks_l3_but_one_never_built_is_no_input() -> None:
    same = seen(returned("1", "s1"))
    pairs = [(args(value=i, width=1), same, same) for i in range(100)]
    pairs += [
        (args(value=100, width=1), Seen(unbuilt="ValueError"), Seen(unbuilt="ValueError")),
        (args(value=101, width=1), Seen(unbuilt="ValueError"), Seen(unbuilt="TypeError")),
        (args(value=102, width=1), same, Seen(unbuilt="ValueError")),
        # A side that can't take the input never builds its object: the signature decides.
        (args(value=103, width=1), Seen(unbuilt="ValueError"), Seen(unbindable="no width")),
    ]
    comparison, changes = br.compare_target("t1", *head_and_base(pairs), Evidence())
    assert not changes and comparison.compared == 100
    assert comparison.inputs == 103  # the one never built on either side is not an input
    assert comparison.lost == {br.UNBUILT: 2, "does not fit the signature before the fix": 1}
    reason = br.insufficient(comparison, "Box.size")
    assert reason == "Box.size: 2 input(s) whose object only one side could build"
    assert not br.checks_gate([], [("Box.size", comparison)], [], True).allowed


def test_an_unbuilt_outcome_is_read_from_the_report() -> None:
    into = DiffEvents()
    events = [{"event": "outcome", "target": "t1", "index": 0, "unbuilt": "ValueError"}]
    br.read_diff_events(events, {"t1": target()}, into)
    assert into.seen["t1"][0] == Seen(unbuilt="ValueError")


def test_a_method_call_reads_as_a_call_on_its_object_or_class() -> None:
    method = replace(target(params=("raw",)), name="port", owner="Listener", kind="method")
    self = ("self", "'Listener(default_port=9000)'")
    assert br.call_text(method, (self, ("raw", "None"))) == (
        "Listener(default_port=9000).port(raw=None)"
    )
    assert br.call_text(method, (("self", "not a literal"), ("raw", "''"))) == (
        "Listener(...).port(raw='')"
    )
    prop = replace(method, name="label", kind="property", params=())
    assert br.call_text(prop, (("self", "'Listener()'"),)) == "Listener().label"
    static = replace(method, name="parse", kind="staticmethod")
    assert br.call_text(static, (("raw", "'80'"),)) == "Listener.parse(raw='80')"


def test_a_method_called_on_an_object_never_has_finite_inputs() -> None:
    from tracefix.behaviour_diff import finite_annotations

    flag = (Param("on", "positional", "bool", False),)
    method = replace(target(params=()), params=flag, owner="Box", kind="method")
    assert not finite_annotations(method)  # no __init__ of its own
    assert not finite_annotations(replace(method, init_params=()))  # Box(): state comes later
    assert not finite_annotations(replace(method, init_params=flag))
    assert not finite_annotations(replace(method, kind="property", params=(), init_params=()))
    assert finite_annotations(replace(method, kind="staticmethod"))  # no object at all
    assert finite_annotations(replace(method, kind="classmethod"))

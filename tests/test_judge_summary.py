"""M8 (plan P14): the Judge's receipt summary. One call after the ladder, read by our rules; it
only ever fills `summary` and the flags' notes, so the level and every finding stay ours."""

import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st
from synthetic import attack, behaviour, finding, flag, integrity, l4_run, target

from tracefix.attack import AttackStatus
from tracefix.behaviour_rules import Change, ChangeGroup, Kind, Seen
from tracefix.judge import MAX_NOTE, MAX_SUMMARY, JudgeResult, JudgeStatus, Label, summarize
from tracefix.ladder import level
from tracefix.llm import FakeProvider, LLMClient
from tracefix.prompts import judge as prompt
from tracefix.receipt import Receipt, build, own_summary, summary_facts
from tracefix.record import RunRecord
from tracefix.workspace import Workspace

ISSUE = "# f returns a negative number\n\nf(-1) gives -1."


def _ws(name: str = "my repo") -> Workspace:
    """Only the folders matter: the receipt masks them (nothing is created)."""
    root = Path(tempfile.gettempdir()) / "tracefix-summary-test" / name
    workspace = Workspace(root / "repo", "main", "fix")
    workspace.root = root / "work"
    return workspace


def _flagged(*flags: Any, **overrides: object) -> RunRecord:
    found = finding(input=(("x", "-1"),), outcome={"kind": "returned", "repr": "-1"})
    before = Seen({"kind": "returned", "type": "int", "text": "0"})
    after = Seen({"kind": "returned", "type": "int", "text": "-10"})
    change = Change("t1", 0, (("x", "-5"),), "doc", Kind.VALUE, before, after, id="c1")
    group = ChangeGroup(change.group_key, Kind.VALUE, (change,), (change,))
    judged = JudgeResult(JudgeStatus.LABELLED, (Label("c1", "suspicious", "not asked for"),))
    return l4_run(
        break_my_fix=attack(status=AttackStatus.FOUND, findings=(found,)),
        integrity=integrity(*(flags or (flag(),))),
        behaviour_diff=behaviour(groups=(group,), judge=judged),
        **overrides,
    )


def _ask(receipt: Receipt, *answers: dict[str, Any] | str) -> tuple[Any, FakeProvider]:
    provider = FakeProvider(list(answers))
    return summarize(LLMClient(provider), ISSUE, summary_facts(receipt)), provider


def _reply(summary: str = "It was shown.", **notes: str) -> dict[str, Any]:
    return {"summary": summary, "flag_notes": [{"flag": k, "note": v} for k, v in notes.items()]}


def test_the_request_holds_the_receipts_facts_as_data() -> None:
    receipt = build(_flagged(), _ws())
    _, provider = _ask(receipt, _reply())
    request = provider.requests[0]
    text = request.messages[0].content
    assert request.role == "judge" and request.system == prompt.SUMMARY_SYSTEM
    assert len(provider.requests) == 1  # one call
    assert f'<data name="issue">\n{ISSUE}\n</data>' in text  # untrusted: data only
    assert "Evidence level (final): COUNTEREXAMPLE." in text
    assert "integrity flag: weakened_assert at tests/test_calc.py:N" in text  # a level reason
    assert "reproduce: reproduced" in text  # each stage's status
    assert "f_t1(x=-1) -> returns -1" in text  # a finding: input -> outcome
    assert "f1: weakened_assert in tests/test_calc.py, test test_calc: assert loosened" in text
    assert ": value change; labels: suspicious" in text


def test_the_request_is_the_same_on_every_machine() -> None:
    """No machine path, count or address, and ASCII only: the request names the recording."""
    requests = []
    for name, address, tried in (("one", "0x7f12ab34cd56", 37), ("two", "0x21f9a8b7c60", 41)):
        ws = _ws(name)
        found = finding(input=(("x", "'café'"),),
                        outcome={"kind": "returned", "repr": f"<Obj at {address}>"})  # fmt: skip
        cut_short = l4_run(break_my_fix=attack(  # L3; the L4 gate's reasons hold counts, a path
            status=AttackStatus.INCONCLUSIVE, targets=(target(inputs_tried=tried),),
            reason=f"stopped in {ws.repo / 'calc.py'}"))  # fmt: skip
        broken = l4_run(break_my_fix=attack(status=AttackStatus.FOUND, findings=(found,)))
        for record in (cut_short, broken):
            _, provider = _ask(build(record, ws), _reply())
            requests.append(provider.requests[0])
    assert [r.key() for r in requests[:2]] == [r.key() for r in requests[2:]]
    short, broke = (r.messages[0].content for r in requests[:2])
    assert "f_t1: N inputs tried (at least N needed)" in short
    assert "Break My Fix ended inconclusive: stopped in <repo>/calc.py" in short
    assert "f_t1(x='caf\\xe9') -> returns <Obj at 0x?>" in broke
    assert all(t.isascii() and "tracefix-summary-test" not in t for t in (short, broke))


def test_a_reply_is_read_by_our_rules() -> None:
    record = _flagged()
    long = "Break My Fix found f(-1) still returns -1. " + "Look closer " * 50 + "\nnow."
    reply = _reply(long + " Third sentence. Fourth.", f1="deliberate?\n\nCheck " + "x" * 400,
                   f9="a flag that does not exist")  # fmt: skip
    reply["flag_notes"].append({"flag": "f1", "note": "a second note for f1"})
    judged, _ = _ask(build(record, _ws()), reply)
    assert judged.text is not None and "\n" not in judged.text and "Third" not in judged.text
    assert judged.text.startswith("Break My Fix found f(-1) still returns -1. Look closer")
    assert len(judged.text) <= MAX_SUMMARY and judged.text.endswith("…")
    ((flag_id, note),) = judged.flag_notes
    assert flag_id == "f1" and note.startswith("deliberate? Check xxx") and len(note) <= MAX_NOTE
    receipt = build(record, _ws(), judged)
    assert receipt.summary.by == "judge" and receipt.summary.text == judged.text
    assert receipt.integrity_flags[0].note == note
    assert "summary: the Judge noted flags that do not exist (ignored): f9" in receipt.notes
    assert receipt.level == level(record).level


def test_a_short_answer_is_kept_as_written() -> None:
    receipt = build(_flagged(), _ws())
    words = "The fix still breaks on f(-1).   Start with finding 1! Then the flag?\nAnd more."
    judged, _ = _ask(receipt, _reply(words))
    assert judged.text == "The fix still breaks on f(-1). Start with finding 1!"
    assert judged.flag_notes == () and judged.notes == ()


def test_any_model_problem_leaves_our_own_line() -> None:
    record = _flagged()
    draft = build(record, _ws())
    for answers in ((), ("not json", "still not json"), (_reply("   \n "),)):
        judged, _ = _ask(draft, *answers)
        assert judged.text is None and judged.notes
        receipt = build(record, _ws(), judged)
        assert receipt.summary.by == "tracefix"
        assert receipt.summary.text == own_summary(level(record))
        assert all(f.note is None for f in receipt.integrity_flags)


TEXT = st.text(max_size=600)
ANSWER = st.fixed_dictionaries({
    "summary": TEXT,
    "flag_notes": st.lists(st.fixed_dictionaries(
        {"flag": st.sampled_from(["f1", "f2", "f3", "x", ""]) | st.text(max_size=8),
         "note": TEXT}), max_size=4),
})  # fmt: skip


def _without_words(receipt: Receipt) -> dict[str, Any]:
    dumped = receipt.model_dump(mode="json")
    del dumped["summary"], dumped["notes"]
    for f in dumped["integrity_flags"]:
        del f["note"]
    return dumped


@settings(max_examples=60, deadline=None)
@given(answer=ANSWER)
def test_arbitrary_answers_never_change_the_level_or_the_evidence(answer: dict[str, Any]) -> None:
    record = _flagged(flag(), replace(flag(), line=9))
    plain = build(record, _ws())
    judged, _ = _ask(plain, answer)
    receipt = build(record, _ws(), judged)
    assert _without_words(receipt) == _without_words(plain)
    assert (receipt.level, receipt.level_reasons) == (plain.level, plain.level_reasons)
    text = receipt.summary.text
    assert len(text) <= MAX_SUMMARY + 40 and "\n" not in text  # + masking may lengthen it
    for f in receipt.integrity_flags:
        assert f.note is None or ("\n" not in f.note and f.id in ("f1", "f2"))

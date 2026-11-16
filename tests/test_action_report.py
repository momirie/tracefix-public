"""The Action's verdict and words (plan P4, P5): the conclusion table, annotations, the PR comment
and its history state. Pure: receipts are built from synthetic run records, no runs, no API."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import example, given
from hypothesis import strategies as st
from synthetic import attack, finding, flag, integrity, l4_run, regression, regressions

from tracefix import action_report as ar
from tracefix.action_report import MARKER, Entry, Header, Report
from tracefix.attack import AttackStatus
from tracefix.github_api import Comment
from tracefix.ladder import ORDER, EvidenceLevel, rank
from tracefix.previous import Replay
from tracefix.receipt import PreviousInfo, Receipt, ReplayedFinding, Summary, Tampering, build
from tracefix.receipt_md import render
from tracefix.record import RunStatus
from tracefix.workspace import Workspace

HEAD = "b" * 40
HEADER = Header(HEAD, "https://github.com/octo/svc/actions/runs/500", "tracefix-receipt-pr-7",
                "from #1")  # fmt: skip
WHEN = "2026-10-14T12:00:00Z"
CONTROL = "line\nnext\r\x1b[31m\u202e\x00\t"


def run_url(run: int) -> str:
    return f"https://github.com/octo/svc/actions/runs/{run}"


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    workspace = Workspace(tmp_path / "repo", "main", "fix")
    workspace.root = tmp_path / "work"
    return workspace


def receipt(ws: Workspace, **overrides: object) -> Receipt:
    return build(l4_run(**overrides), ws)


def with_level(r: Receipt, level: EvidenceLevel, **changes: object) -> Receipt:
    return r.model_copy(update={"level": level, **changes})


# --- the conclusion -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("level", "changes", "min_level", "expected"),
    [
        (EvidenceLevel.L4, {}, "", "success"),
        (EvidenceLevel.L1, {}, "", "success"),
        (EvidenceLevel.L0, {}, "", "neutral"),
        (EvidenceLevel.COUNTEREXAMPLE, {}, "", "failure"),
        (EvidenceLevel.L4, {"tampering": [Tampering(stage="guard", detail="x")]}, "", "failure"),
        (EvidenceLevel.L0, {"status": RunStatus.INVALID}, "", "failure"),
        (EvidenceLevel.L2, {}, "L3", "failure"),
        (EvidenceLevel.L3, {}, "L3", "success"),
        (EvidenceLevel.L0, {}, "L1", "failure"),
        (EvidenceLevel.L0, {"status": RunStatus.ENVIRONMENT_ERROR}, "", "neutral"),
    ],
)
def test_the_conclusion_table(ws: Workspace, level: EvidenceLevel, changes: dict[str, object],
                              min_level: str, expected: str) -> None:  # fmt: skip
    assert ar.conclusion(with_level(receipt(ws), level, **changes), min_level) == expected


def test_no_receipt_is_neutral_unless_a_minimum_is_set() -> None:
    assert ar.conclusion(None, "") == "neutral"
    assert ar.conclusion(None, "L1") == "failure"


LEVELS = st.sampled_from(ORDER)
MINIMUMS = st.sampled_from(["", "L1", "L2", "L3", "L4"])
STATUSES = st.sampled_from(list(RunStatus))
WORSE = {"failure": 0, "neutral": 1, "success": 2}


@given(level=LEVELS, higher=LEVELS, status=STATUSES, tampered=st.booleans(), minimum=MINIMUMS)
def test_conclusion_properties(tmp_path_factory: pytest.TempPathFactory, level: EvidenceLevel,
                               higher: EvidenceLevel, status: RunStatus, tampered: bool,
                               minimum: str) -> None:  # fmt: skip
    """Tampering and COUNTEREXAMPLE always fail; a minimum fails closed; raising the level never
    makes the conclusion worse."""
    base = _base_receipt(tmp_path_factory)
    tampering = [Tampering(stage="guard", detail="x")] if tampered else []
    low = with_level(base, level, status=status, tampering=tampering)
    verdict = ar.conclusion(low, minimum)
    if tampered or status is RunStatus.INVALID or level is EvidenceLevel.COUNTEREXAMPLE:
        assert verdict == "failure"
    if minimum and rank(level) < rank(EvidenceLevel(minimum)):
        assert verdict == "failure"
    if verdict == "success":
        assert level not in (EvidenceLevel.COUNTEREXAMPLE, EvidenceLevel.L0)
    if rank(higher) >= rank(level):
        raised = ar.conclusion(with_level(low, higher), minimum)
        assert WORSE[raised] >= WORSE[verdict]


_BASE: list[Receipt] = []


def _base_receipt(factory: pytest.TempPathFactory) -> Receipt:
    if not _BASE:
        root = factory.mktemp("base")
        workspace = Workspace(root / "repo", "main", "fix")
        workspace.root = root / "work"
        _BASE.append(receipt(workspace))
    return _BASE[0]


def test_check_titles(ws: Workspace) -> None:
    r = receipt(ws)
    assert ar.check_title(Report(r), "") == f"L4: {ar.LEVEL_WORDS[EvidenceLevel.L4]}"
    low = with_level(r, EvidenceLevel.L2)
    assert ar.check_title(Report(low), "L3").endswith("(below min-level L3)")
    tampered = r.model_copy(update={"tampering": [Tampering(stage="guard", detail="x")]})
    assert ar.check_title(Report(tampered), "") == "L4: tampering detected"
    assert ar.check_title(Report(None, "no API key"), "") == "Not verified: no API key"
    failed = ar.check_title(Report(None, "x" * 300 + CONTROL, failed=True), "")
    assert failed.startswith("Tracefix failed: ") and len(failed) <= ar.MAX_TITLE_CHARS


# --- annotations ----------------------------------------------------------------------------------


def located(ws: Workspace) -> Receipt:
    """A receipt with one of each annotated thing, at known places."""
    found = finding(1, path="src/svc/config.py", line=12)
    r = receipt(
        ws,
        break_my_fix=attack(status=AttackStatus.FOUND, findings=(found,)),
        regressions=regressions(replace(regression(), line=8)),
        integrity=integrity(flag()),
    )
    replayed = [
        ReplayedFinding(number=1, call="parse_port(raw='')", file="findings/finding_1.py",
                        result=Replay.STILL_FAILS, detail="failed", path="src/svc/config.py",
                        line=10),
        ReplayedFinding(number=2, call="parse_port(raw=' ')", file="findings/finding_2.py",
                        result=Replay.FIXED, detail="passed 3 times", path="src/svc/config.py",
                        line=11),
        ReplayedFinding(number=1, call="parse_port(raw='x')", file="findings/previous_1.py",
                        result=Replay.STILL_FAILS, detail="failed", path="src/svc/config.py",
                        line=9, carried=True),
    ]  # fmt: skip
    previous = PreviousInfo(head_sha="c" * 40, level=EvidenceLevel.COUNTEREXAMPLE,
                            created_at="2026-10-13T12:00:00+00:00", findings=replayed,
                            still_open=[], still_open_known=True)  # fmt: skip
    return r.model_copy(update={"previous": previous})


def test_annotations_sit_on_the_receipts_places_failures_first(ws: Workspace) -> None:
    r = located(ws)
    r = r.model_copy(update={"survivors": [s.model_copy(update={"file": "pkg/calc.py", "line": 3})
                                           for s in r.survivors]})  # fmt: skip
    shown, more = ar.annotations_for(r)
    places = [(a.level, a.path, a.line, a.title) for a in shown]
    assert places[0] == ("failure", "src/svc/config.py", 12, "Break My Fix: finding 1")
    assert places[1] == ("failure", "tests/test_other.py", 8, "Regression")
    assert places[2][0:1] == ("failure",) and places[2][3].startswith("Test integrity: ")
    assert places[3] == ("warning", "src/svc/config.py", 10, "Finding 1 of the last receipt")
    assert "line as of commit ccccccc" in shown[3].message
    assert all(a.title != "Finding 2 of the last receipt" for a in shown)  # fixed: no annotation
    # A carried one's place is an older commit's line (verifier M9 round 2): no annotation.
    assert not any(a.title.startswith("Earlier finding") for a in shown)
    assert [a.level for a in shown[4:]] == ["notice"] * len(r.survivors)
    assert more == 0
    payload = shown[0].payload()
    assert payload["start_line"] == payload["end_line"] == 12
    assert payload["annotation_level"] == "failure"


def test_annotations_are_capped_and_counted(ws: Workspace) -> None:
    many = tuple(finding(i, path="src/a.py", line=i, input=(("x", CONTROL * 100),))
                 for i in range(1, 61))  # fmt: skip
    r = receipt(ws, break_my_fix=attack(status=AttackStatus.FOUND, findings=many),
                guard=None)  # fmt: skip
    shown, more = ar.annotations_for(r)
    assert len(shown) == ar.MAX_ANNOTATIONS and more == 60 - ar.MAX_ANNOTATIONS
    for a in shown:
        assert a.line >= 1 and len(a.message) <= ar.MAX_MESSAGE_CHARS
        assert len(a.title) <= ar.MAX_TITLE_CHARS
        assert all(c.isprintable() for c in a.message + a.title)


@pytest.mark.parametrize(
    "path",
    ["../etc/passwd", "/abs/x.py", "<repo>/x.py", "a\nb.py", "", "a/./b.py", "a//b.py", "C:\\x.py"],
)
def test_a_place_github_cant_take_is_counted_not_annotated(ws: Workspace, path: str) -> None:
    r = receipt(ws, break_my_fix=attack(status=AttackStatus.FOUND,
                                        findings=(finding(1, path=path, line=3),)))  # fmt: skip
    shown, more = ar.annotations_for(r)
    assert [a for a in shown if a.title.startswith("Break My Fix")] == []
    assert more >= 1


def test_a_missing_line_is_line_one() -> None:
    made = ar._annotation("src/a.py", 0, "notice", "t", "m")
    assert made is not None and made.line == 1


@given(st.text(max_size=2_000))
def test_plain_text_is_one_printable_line(value: str) -> None:
    shown = ar.plain(value, 500)
    assert len(shown) <= 500 and all(c.isprintable() for c in shown)


# --- the check run --------------------------------------------------------------------------------


def test_the_check_run_is_created_complete_from_the_model(ws: Workspace) -> None:
    r = located(ws)
    shown, more = ar.annotations_for(r)
    fields = ar.check_run(HEADER, Report(r), "", shown, more, WHEN)
    assert (fields["name"], fields["head_sha"], fields["status"]) == ("Tracefix", HEAD, "completed")
    assert fields["conclusion"] == "failure"  # a COUNTEREXAMPLE
    assert fields["details_url"] == HEADER.run_url and fields["completed_at"] == WHEN
    output = fields["output"]
    assert isinstance(output, dict)
    assert output["summary"].startswith("Tracefix on commit `bbbbbbb` · [workflow run](")
    assert render(r, max_chars=ar.CHECK_RECEIPT_CHARS) in output["summary"]
    assert len(output["annotations"]) == len(shown)


def test_a_huge_receipts_check_summary_fits(ws: Workspace) -> None:
    many = [f"reason {i} " + "x" * 300 for i in range(300)]
    r = receipt(ws).model_copy(update={"level_reasons": many, "warnings": many, "notes": many})
    summary = ar.check_summary(HEADER, Report(r), 7)
    assert len(summary) <= 65_535
    assert summary.endswith("7 more annotation(s) in receipt.json\n")


# --- the comment and its history ------------------------------------------------------------------


def entries(n: int, *, level: EvidenceLevel | None = EvidenceLevel.L2) -> list[Entry]:
    return [Entry(sha=f"{i:040x}", level=level, status="ok", when=WHEN, run=100 + i)
            for i in range(n)]  # fmt: skip


def test_the_comment_round_trips_its_history(ws: Workspace) -> None:
    r = receipt(ws)
    history = ar.with_entry(entries(3), ar.entry(HEAD, Report(r), WHEN, 500))
    body = ar.comment_body(HEADER, Report(r), history, run_url)
    assert body.startswith(MARKER + "\n" + ar.header_line(HEADER) + "\n")
    assert render(r, max_chars=ar.COMMENT_RECEIPT_CHARS) in body
    assert "<summary>Earlier receipts on this pull request (3)</summary>" in body
    assert f"[100]({run_url(100)})" in body
    assert ar.parse_history(body) == history
    assert history[0] == Entry(sha=HEAD, level=EvidenceLevel.L4, status="ok", when=WHEN, run=500)


def test_a_rerun_on_the_same_commit_replaces_its_entry() -> None:
    old = entries(2)
    new = Entry(sha=old[1].sha, level=EvidenceLevel.L4, status="ok", when=WHEN, run=999)
    assert ar.with_entry(old, new) == (new, old[0])
    assert len(ar.with_entry(entries(ar.MAX_HISTORY), entries(1)[0].model_copy(
        update={"sha": "f" * 40}))) == ar.MAX_HISTORY  # fmt: skip


def test_a_comment_without_a_receipt_says_why_and_keeps_the_history() -> None:
    report = Report(None, "the checkout is shallow", failed=False)
    history = ar.with_entry(entries(1), ar.entry(HEAD, report, WHEN, 500))
    body = ar.comment_body(HEADER, report, history, run_url)
    assert "Tracefix did not verify this commit: the checkout is shallow" in body
    assert "Earlier receipts on this pull request (1)" in body
    assert history[0].status == "not_verified" and history[0].level is None
    crashed = ar.entry(HEAD, Report(None, "boom", failed=True), WHEN, 500)
    assert crashed.status == "failed"


def test_the_maximal_comment_fits_in_one_github_comment(ws: Workspace) -> None:
    many = [f"pkg.mod.function_{i}: " + "<x> @y #1 " * 100 for i in range(300)]
    r = receipt(ws).model_copy(update={"level_reasons": many, "unchecked": many,
                                       "warnings": many, "notes": many})  # fmt: skip
    header = Header("f" * 64, HEADER.run_url + "9" * 200, "a" * 200, "from #1, #2 and #3")
    history = entries(ar.MAX_HISTORY, level=EvidenceLevel.COUNTEREXAMPLE)
    body = ar.comment_body(header, Report(r), history, lambda run: run_url(run) + "9" * 50)
    assert len(body) < 65_536
    assert ar.parse_history(body) == tuple(history)


STATE_TEXT = st.one_of(
    st.text(max_size=3_000),
    st.builds(lambda s: f"{ar.STATE_OPEN}{s}{ar.STATE_CLOSE}", st.text(max_size=500)),
    st.builds(
        lambda h: f"{ar.STATE_OPEN}{json.dumps({'v': 1, 'history': h})}{ar.STATE_CLOSE}",
        st.lists(st.dictionaries(st.sampled_from(["sha", "level", "status", "when", "run", "x"]),
                                 st.one_of(st.text(max_size=70), st.integers(), st.none())),
                 max_size=25),
    ),
)  # fmt: skip


@given(STATE_TEXT)
@example(f'{ar.STATE_OPEN}{{"v": 1, "history": [{{"sha": "{"a" * 40}", "level": "L9"}}]}} -->')
@example("<!-- tracefix-state \ud800 -->")
def test_the_state_parser_never_raises_or_yields_a_bad_entry(body: str) -> None:
    for e in ar.parse_history(body):
        assert len(e.sha) in (40, 64) and set(e.sha) <= set("0123456789abcdef")
        assert e.level is None or e.level in ORDER
        assert e.status in ar.STATUS_WORDS
        assert e.run >= 0 and len(e.when) == 20


@pytest.mark.parametrize(
    "change",
    [
        {"sha": "B" * 40},
        {"sha": "a" * 39},
        {"level": "L5"},
        {"status": "great"},
        {"when": "2026-10-14 12:00"},
        {"when": "2026-10-14T12:00:00Z<script>"},
        {"run": -1},
        {"run": "5"},
        {"extra": 1},
    ],
)
def test_a_forged_history_is_no_history(change: dict[str, object]) -> None:
    good = {"sha": "a" * 40, "level": "L2", "status": "ok", "when": WHEN, "run": 1}
    body = f"{MARKER}\n{ar.STATE_OPEN}{json.dumps({'v': 1, 'history': [{**good, **change}]})} -->"
    assert ar.parse_history(body) == ()
    fine = f"{MARKER}\n{ar.STATE_OPEN}{json.dumps({'v': 1, 'history': [good]})} -->"
    assert len(ar.parse_history(fine)) == 1


def test_more_than_the_history_cap_is_no_history() -> None:
    state = ar.CommentState(history=tuple(entries(ar.MAX_HISTORY))).model_dump()
    state["history"] = [*state["history"], state["history"][0]]
    body = f"{ar.STATE_OPEN}{json.dumps(state, default=str)}{ar.STATE_CLOSE}"
    assert ar.parse_history(body) == ()


def comment(cid: int, body: str, author: str = ar.BOT_LOGIN) -> Comment:
    return Comment(cid, body, author, f"https://github.com/x#{cid}", WHEN)


def test_only_our_own_marked_comment_is_ours() -> None:
    forged = comment(9, f"{MARKER}\nforged", author="mallory")
    quoted = comment(8, f"> {MARKER}\nquoted")
    old, new = comment(3, f"{MARKER}\nold"), comment(5, f"{MARKER}\nnew")
    assert ar.ours([forged, quoted, new, old], ar.BOT_LOGIN) == new
    assert ar.ours([forged, quoted], ar.BOT_LOGIN) is None
    assert ar.ours([forged], "mallory") == forged  # a personal token's own login


def test_untrusted_text_cant_break_out_of_the_comment(ws: Workspace) -> None:
    hostile = "--> <!-- tracefix-state {} --> </details> @octocat"
    r = receipt(ws).model_copy(
        update={"level_reasons": [hostile], "summary": Summary(text=hostile, by="judge")}
    )
    header = Header(HEAD, HEADER.run_url, "art", hostile)
    history = ar.with_entry((), ar.entry(HEAD, Report(r), WHEN, 500))
    body = ar.comment_body(header, Report(r), history, run_url)
    assert body.count("-->") == 2 and body.count(ar.STATE_OPEN) == 1  # the marker, the state
    assert "@octocat" not in body
    assert ar.parse_history(body) == history


def test_a_finding_without_a_place_is_counted(ws: Workspace) -> None:
    """A receipt from before M9 has no finding places: such a finding is counted, not placed."""
    r = receipt(ws, guard=None, break_my_fix=attack(status=AttackStatus.FOUND,
                                                    findings=(finding(1),)))  # fmt: skip
    assert r.findings[0].path is None
    shown, more = ar.annotations_for(r)
    assert all(a.title != "Break My Fix: finding 1" for a in shown) and more >= 1

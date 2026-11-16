"""receipt.md (plan P13): golden file, line limits, and untrusted text rendered inert."""

import os
import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args

import pytest
from hypothesis import example, given
from hypothesis import strategies as st
from markdown_it import MarkdownIt
from markdown_it.token import Token
from synthetic import (
    attack,
    behaviour,
    finding,
    flag,
    guard,
    integrity,
    l4_run,
    mutant,
    regression,
    regressions,
    run_result,
    target,
)

from tracefix.attack import AttackStatus, Doubt
from tracefix.behaviour_diff import SurvivorCheck
from tracefix.behaviour_rules import Change, ChangeGroup, Kind, Seen
from tracefix.guard import MutantStatus
from tracefix.judge import JudgeResult, JudgeStatus, Label
from tracefix.ladder import EvidenceLevel
from tracefix.llm import CallRecord, Problem
from tracefix.mutation_rules import KINDS
from tracefix.previous import Replay
from tracefix.receipt import PreviousInfo, Receipt, ReplayedFinding, Summary, Tampering, build
from tracefix.receipt_md import (
    DOUBT_WORDS,
    ELLIPSIS,
    MAX_CHARS,
    MAX_LINES,
    MAX_MAIN_LINES,
    MORE,
    _fit,
    code,
    render,
    text,
)
from tracefix.record import PREVIOUS, STAGES, RunRecord, RunStatus, StageRecord
from tracefix.sandbox import BASIC_WARNING
from tracefix.workspace import Workspace

GOLDEN = Path(__file__).parent / "golden" / "receipt.md"
HOSTILE = (
    "x`` ` </details><script>alert(1)</script>\n# Approved\n- [ok](https://evil.example) "
    "![i](https://evil.example/i.png) <img src=x onerror=y> @octocat org/repo#12 *b* _i_ "
    "| a | b | ~~s~~ $x$ &lt; \u202e\u0000\t1. one\n> quote\n```\n<details>"
)
HEADINGS = ("Fix Receipt:", "Counterexamples", "Stages", "Behaviour changes",
            "Changes no test noticed", "Integrity flags", "More ", "Found before",
            "Fix lines run", "Not checked", "Warnings", "Notes", "This receipt",
            "Break My Fix targets")  # fmt: skip


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    workspace = Workspace(tmp_path / "repo", "main", "fix")
    workspace.root = tmp_path / "work"
    return workspace


def _parse(markdown: str) -> list[Token]:
    return MarkdownIt("commonmark").enable(["table", "strikethrough"]).parse(markdown)


def _flat(tokens: list[Token]) -> list[Token]:
    return [t for tok in tokens for t in (tok, *_flat(tok.children or []))]


def _change(text_: str, explains: str | None = None) -> ChangeGroup:
    before = Seen({"kind": "returned", "type": "int", "text": text_})
    after = Seen({"kind": "returned", "type": "int", "text": "0"})
    change = Change("t1", 0, (("x", text_),), "explicit", Kind.VALUE, before, after,
                    explains=(explains or text_,), id="c1")  # fmt: skip
    return ChangeGroup(change.group_key, Kind.VALUE, (change,), (change,))


RULE_KILLED = mutant(9, MutantStatus.KILLED, origin="rule", kind="compare")


def _record(words: str = "a value", *, many: int = 1) -> RunRecord:
    """A run with something in every section; `words` goes into every untrusted string."""
    found = tuple(
        finding(i, input=(("x", words),), outcome={"kind": "raised", "type": "E", "message": words},
                property=replace(finding().property, name=words, quote=words))  # type: ignore[arg-type]
        for i in range(1, many + 1)
    )  # fmt: skip
    mutants = tuple(mutant(i, original=words, replacement=words) for i in range(1, many + 1))
    check = SurvivorCheck(1, "model", "pkg/calc.py", 3, "differs", examples=(("f(x=0)", "0", "1"),))
    labels = JudgeResult(JudgeStatus.LABELLED, (Label("c1", "suspicious", words),))
    flagged = tuple(replace(flag(), detail=words, test=words) for _ in range(many))
    problem = Problem("adversary", "claude-opus-5-5", "rate_limit", 429, words)
    targets = tuple(
        target(f"t{i}", function=words, path=words, via=words, reason=words, attacked=i > 1,
               finished=i > 2)
        for i in range(1, many + 2)
    )  # fmt: skip
    record = l4_run(
        reproduce=None,
        guard=guard(mutants=mutants, rule_mutants=(RULE_KILLED,)),
        regressions=regressions(*(replace(regression(), evidence=words) for _ in range(many))),
        behaviour_diff=behaviour(groups=(_change(words),) * many, judge=labels,
                                 survivors=(check,)),
        break_my_fix=attack(status=AttackStatus.FOUND, findings=found, pre_existing=found,
                            targets=targets),
        integrity=integrity(*flagged),
    )  # fmt: skip
    suite = run_result("python", "-m", "pytest", words)
    stages = tuple(replace(s, reason=words, problems=(problem,) * many) for s in record.stages)
    stages += (StageRecord("environment", "ok", words, 2.5, suite),)
    calls = (CallRecord("adversary", "claude-opus-5-5", 12_000, 3_000, 4.0, True),)
    return replace(record, stages=stages, issue=f"# {words}\n\nbody", repo_name=words,
                   warnings=tuple(f"{words} {i}" for i in range(many)),
                   notes=tuple(f"{words} {i}" for i in range(many)), calls=calls,
                   created_at=datetime(2026, 10, 13, 12, 0, tzinfo=UTC))  # fmt: skip


def _receipt(ws: Workspace, words: str = "a value", *, many: int = 1) -> Receipt:
    built = build(_record(words, many=many), ws)
    flags = [f.model_copy(update={"note": words}) for f in built.integrity_flags]
    return built.model_copy(update={
        "tracefix_version": "0.0.0-test",
        "summary": Summary(text=words, by="judge"),
        "integrity_flags": flags,
        "tampering": [Tampering(stage="guard", detail=words)] * many,
    })  # fmt: skip


def _golden(ws: Workspace) -> Receipt:
    """A plausible receipt with one of each section (the golden file shows what people see)."""
    check = SurvivorCheck(1, "model", "pkg/calc.py", 3, "differs", examples=(("f(x=0)", "0", "1"),))
    labels = JudgeResult(JudgeStatus.LABELLED, (Label("c1", "intended", "the issue's own case"),))
    record = l4_run(
        guard=guard(mutants=(mutant(1), mutant(2, MutantStatus.KILLED)),
                    rule_mutants=(RULE_KILLED,)),
        regressions=regressions(regression()),
        behaviour_diff=behaviour(groups=(_change("-1", "the issue calls f(-1)"),), judge=labels,
                                 survivors=(check,)),
        break_my_fix=attack(status=AttackStatus.FOUND, findings=(finding(1),)),
        integrity=integrity(flag()),
    )  # fmt: skip
    suite = run_result("python", "-m", "pytest", "-q", "tests")
    stages = (StageRecord("environment", "ok", "the base suite runs", 3.2, suite), *record.stages)
    calls = (CallRecord("adversary", "claude-opus-5-5", 12_000, 3_000, 4.0, True),)
    built = build(replace(record, stages=stages, calls=calls,
                          issue="# f(-1) returns -1 instead of 0\n\nSee `abs` <docs>.",
                          created_at=datetime(2026, 10, 13, 12, 0, tzinfo=UTC)), ws)  # fmt: skip
    note = "The old assert encoded the bug; check `test_calc` still covers negative inputs."
    return built.model_copy(update={
        "tracefix_version": "0.0.0-test",
        "summary": Summary(text="Break My Fix found `f_t1(x=-1)` still returns -1. Start there.",
                           by="judge"),
        "integrity_flags": [f.model_copy(update={"note": note}) for f in built.integrity_flags],
    })  # fmt: skip


def test_golden(ws: Workspace) -> None:
    rendered = render(_golden(ws))
    if os.environ.get("TRACEFIX_UPDATE_GOLDEN") == "1":
        GOLDEN.parent.mkdir(exist_ok=True)
        GOLDEN.write_text(rendered, encoding="utf-8", newline="\n")
    expected = GOLDEN.read_text(encoding="utf-8")
    assert rendered == expected, "if intended: TRACEFIX_UPDATE_GOLDEN=1 uv run pytest " + __file__


def test_rule_mutants_by_kind_get_one_line_under_the_stages_only_if_any_ran(ws: Workspace) -> None:
    survived = mutant(8, origin="rule", kind="reraise")
    markdown = render(build(l4_run(guard=guard(rule_mutants=(RULE_KILLED, survived))), ws))
    lines = _main_lines(markdown)
    [line] = [x for x in lines if x.startswith("**Rule mutants by kind")]
    assert line == (
        "**Rule mutants by kind (report only):** compare: 1 of 1 killed; reraise: 0 of 1 killed; "
        "no place for body, logic, negate\\_if, constant, arithmetic, membership, loop, drop\\_call"
    )
    assert lines[lines.index(line) - 1] == ""  # a line right after the table would join it
    assert "Rule mutants by kind" not in render(build(l4_run(), ws))
    all_kinds = tuple(mutant(i, origin="rule", kind=k) for i, k in enumerate(KINDS))
    full = render(build(l4_run(guard=guard(rule_mutants=all_kinds)), ws))
    assert "no place for" not in full


def test_the_run_log_lists_break_my_fixs_targets_and_their_inputs(ws: Workspace) -> None:
    targets = (target("t1", inputs_tried=1),
               target("t2", attacked=False, inputs_tried=0, reason="no property to check it"),
               target("t3", finished=False, via="a public caller of the changed _p"))  # fmt: skip
    markdown = render(build(l4_run(break_my_fix=attack(targets=targets)), ws))
    log = markdown.splitlines()
    at = log.index("#### Break My Fix targets")
    assert log[at + 1 : at + 4] == [
        "- `pkg.calc.f_t1` (`pkg/calc.py`): 1 input",
        "- `pkg.calc.f_t2` (`pkg/calc.py`): not attacked (no property to check it)",
        "- `pkg.calc.f_t3` (`pkg/calc.py`): 150 inputs; its attack did not finish; a public "
        "caller of the changed \\_p",
    ]
    assert at > log.index("<details>")  # in the run log, never above it
    assert "Break My Fix targets" not in render(build(run_without_attack(), ws))


def run_without_attack() -> RunRecord:
    record = l4_run()
    return replace(record, stages=tuple(s for s in record.stages if s.name != "break_my_fix"))


def _main_lines(markdown: str) -> list[str]:
    lines = markdown.splitlines()
    assert lines.count("<details>") == 1
    return lines[: lines.index("<details>") - 1]


@pytest.mark.parametrize("words", ["short", HOSTILE * 5])
def test_a_maximal_receipt_stays_within_its_limits(ws: Workspace, words: str) -> None:
    receipt = _receipt(ws, words, many=20).model_copy(
        update={"status": RunStatus.ENVIRONMENT_ERROR, "status_reason": words,
                "level_reasons": [words] * 20, "unchecked": [words] * 20}
    )  # fmt: skip
    commands = [f"python -m pytest {i}" for i in range(21)]
    stage = receipt.stages[0].model_copy(update={"commands": commands})
    receipt = receipt.model_copy(update={"stages": [
        stage.model_copy(update={"name": name}) for name in STAGES]})  # fmt: skip
    markdown = render(receipt)
    main = _main_lines(markdown)
    assert len(main) <= MAX_MAIN_LINES
    assert len(markdown.splitlines()) <= MAX_LINES
    assert markdown.splitlines()[-1] == "</details>"
    # Each capped section says what it cut (also the level's reasons and "Not checked").
    assert sum(MORE in line for line in main) == 8
    assert MORE in markdown.splitlines()[-3]  # the run log's own cut


def test_a_huge_receipt_stays_within_one_github_comment(ws: Workspace) -> None:
    """300 functions not attacked to the end gave a 94,762-character page (verifier S5)."""
    many = [f"pkg.mod.function_{i}: its attack did not finish " + "x" * 300 for i in range(300)]
    receipt = _receipt(ws, "y" * 5_000, many=20).model_copy(
        update={"level_reasons": many, "unchecked": many, "warnings": many, "notes": many}
    )
    markdown = render(receipt)
    assert len(markdown) <= MAX_CHARS
    assert len(_main_lines(markdown)) <= MAX_MAIN_LINES
    assert len(markdown.splitlines()) <= MAX_LINES
    assert markdown.splitlines()[-1] == "</details>"
    assert "and 294 more in receipt.json" in markdown  # the level's reasons, cut at 6


def test_a_page_over_the_character_cap_is_cut_at_a_line_and_says_so() -> None:
    lines = ["## top", "", "<details>", *(["z" * 1_000] * 100), "", "</details>"]
    fitted = _fit(lines)
    assert len("\n".join(fitted)) <= MAX_CHARS and len(fitted) <= len(lines)
    assert fitted[-3].endswith(f"{MORE} (receipt.md stays within {MAX_CHARS:,} characters)")
    assert fitted[-1] == "</details>"
    assert _fit(lines[:10]) == lines[:10]  # within the cap: unchanged


def test_a_cut_right_after_the_summary_line_still_shows_a_list_item() -> None:
    """Straight after an HTML line the note would be raw HTML-block text (verifier round 2)."""
    lines = ["## top", "", "<details>", "<summary>Run log</summary>", "z" * MAX_CHARS, *["x"] * 9]
    fitted = _fit(lines)
    assert fitted[3:5] == ["<summary>Run log</summary>", ""]
    assert fitted[5].startswith("- ") and fitted[-1] == "</details>"
    assert len(fitted) <= len(lines)
    tokens = _flat(_parse("\n".join(fitted)))
    assert any(t.type == "list_item_open" for t in tokens)


def _allowed_html(token: Token) -> bool:
    return token.content in ("<details>\n<summary>Run log</summary>\n", "</details>\n")


def test_untrusted_text_renders_inert(ws: Workspace) -> None:
    receipt = _receipt(ws, HOSTILE, many=2)
    piped = receipt.stages[0].model_copy(update={"name": "a | b", "status": "c|d`|"})
    markdown = render(receipt.model_copy(update={"stages": [piped, *receipt.stages[1:]]}))
    tokens = _flat(_parse(markdown))
    types = {t.type for t in tokens}
    assert not types & {"link_open", "image", "html_inline", "em_open", "s_open", "fence"}
    assert all(_allowed_html(t) for t in tokens if t.type == "html_block")
    headings = [tokens[i + 1].content for i, t in enumerate(tokens) if t.type == "heading_open"]
    assert all(h.startswith(HEADINGS) for h in headings), headings
    assert sum(t.type == "blockquote_open" for t in tokens) == 2  # the warning and tampering alerts
    assert sum(t.type == "table_open" for t in tokens) == 1
    rows = [t for t in tokens if t.type == "tr_open"]
    cells = [t for t in tokens if t.type in ("th_open", "td_open")]
    assert len(cells) == 3 * len(rows)
    # GitHub splits cells at a `|` even inside a code span (markdown-it does not), so count them.
    table = [line for line in markdown.splitlines() if line.startswith("| ")]
    assert all(len(re.findall(r"(?<!\\)\|", line)) == 4 for line in table), table
    shown = "".join(t.content for t in tokens if t.type == "text")  # code spans never mention
    assert "@octocat" not in shown and "#12" not in shown
    assert "@\u200boctocat" in shown and "#\u200b12" in shown
    assert "\u202e" not in markdown and "\\u202e" in shown


URLS = [
    "https://evil.example/login",
    "HTTP://evil.example",
    "www.evil.example",
    "(WWW.evil.example)",
    "ftp://x.y",
]


@pytest.mark.parametrize("url", URLS)
def test_bare_urls_are_never_linked(url: str) -> None:
    """GitHub links bare URLs (its autolink extension, which markdown-it's commonmark preset
    lacks), so no "x://" and no "www." may survive whole (verifier S4)."""
    shown = text(f"log in at {url} today")
    assert "://" not in shown and "www." not in shown.lower().replace("www.\u200b", "")
    assert shown.replace("\u200b", "") == f"log in at {url} today"


def test_www_after_an_underscore_is_never_linked() -> None:
    """GitHub links "www." right after "_", where there is no word boundary (verifier round 2)."""
    shown = text("see _www.evil.example/x")
    assert "www.\u200b" in shown and "www.e" not in shown


def test_inputs_keep_their_backticks(ws: Workspace) -> None:
    literal = "'a``b`'"
    tokens = _flat(_parse(render(_receipt(ws, literal))))
    spans = [t.content for t in tokens if t.type == "code_inline"]
    assert "f_t1(x='a``b`')" in spans
    assert literal in spans


def test_the_basic_warning_shows_exactly_when_basic(ws: Workspace) -> None:
    basic = render(build(l4_run(), ws))
    assert text(BASIC_WARNING) in basic
    strict = render(build(replace(l4_run(), isolation="strict", isolation_why="bwrap works"), ws))
    assert text(BASIC_WARNING) not in strict
    assert "[!WARNING]" not in strict
    assert "**Isolation:** strict (bwrap works)" in strict


def test_the_judges_summary_is_marked_advisory(ws: Workspace) -> None:
    built = build(l4_run(), ws)
    assert f"**Summary:** {text(built.summary.text)}" in render(built)
    judged = built.model_copy(update={"summary": Summary(text="Looks right.", by="judge")})
    assert "**Summary** (advisory, written by the model claude-opus-5-5" in render(judged)


def _inline(markdown: str) -> list[Token]:
    (paragraph,) = [t for t in _parse(markdown) if t.type == "inline"]
    return paragraph.children or []


@given(st.text(min_size=1))
@example("1. one")
@example("12) two")
@example("# x")
@example("- x")
@example("> x")
@example("+ x")
def test_text_shows_exactly_its_characters(value: str) -> None:
    flat = " ".join(value.split())
    if not flat:
        return
    expected = "".join(c if c.isprintable() else c.encode("unicode_escape").decode() for c in flat)
    children = _inline(f"- {text(value)}")  # at the start of a list item: block syntax counts
    assert [c.type for c in children] == ["text"]
    assert children[0].content.replace("\u200b", "") == expected


@given(st.text(min_size=1).filter(lambda s: s.strip(" ")))
def test_code_is_one_span_with_exactly_its_characters(value: str) -> None:
    expected = "".join(c if c.isprintable() else c.encode("unicode_escape").decode() for c in value)
    children = _inline(f"- {code(value)}")
    assert [c.type for c in children] == ["code_inline"]
    assert children[0].content == expected


@pytest.mark.parametrize("extra", range(0, 6))
def test_a_cut_code_span_always_saves_room(extra: int) -> None:
    value = "x" * (10 + extra)
    shown = code(value, 10).strip("`")
    assert shown == value if extra <= len(ELLIPSIS) else shown == "x" * 10 + ELLIPSIS
    assert len(shown) <= len(value)


# --- the last receipt's findings (M9) -----------------------------------------------------------


def _replayed(n: int, result: Replay, call: str = "parse_port(raw='')") -> ReplayedFinding:
    return ReplayedFinding(number=n, call=call, file=f"findings/finding_{n}.py", result=result,
                           detail="ran")  # fmt: skip


def _since(receipt: Receipt, status: str = "replayed", reason: str = "replayed",
           findings: list[ReplayedFinding] | None = None) -> Receipt:  # fmt: skip
    stage = receipt.stages[0].model_copy(update={"name": PREVIOUS, "status": status,
                                                 "reason": reason, "evidence": {}})  # fmt: skip
    previous = None if findings is None else PreviousInfo(
        head_sha="c" * 40, level=EvidenceLevel.COUNTEREXAMPLE,
        created_at="2026-10-14T09:00:00+00:00", findings=findings, still_open=[],
        still_open_known=True)  # fmt: skip
    return receipt.model_copy(update={"stages": [stage, *receipt.stages], "previous": previous})


def _line(markdown: str) -> str:
    return next(line for line in markdown.splitlines() if "Since the last receipt" in line)


def test_the_replay_shows_under_the_counterexamples(ws: Workspace) -> None:
    found = [_replayed(1, Replay.FIXED), _replayed(2, Replay.STILL_FAILS, "parse_port(raw=' ')")]
    markdown = render(_since(_golden(ws), findings=found))
    assert _line(markdown) == (
        "**Since the last receipt** (`ccccccc`, COUNTEREXAMPLE): finding 1 `parse_port(raw='')` "
        "fixed; finding 2 `parse_port(raw=' ')` still fails"
    )
    lines = markdown.splitlines()
    at = lines.index(_line(markdown))
    assert lines[at - 1] == "" and lines[at - 2].startswith("2. ")  # its own paragraph
    assert "| `previous` | `replayed` |" in markdown
    assert render(_golden(ws)) == GOLDEN.read_text(encoding="utf-8")  # unchanged without it


def test_a_replay_that_did_not_run_says_why(ws: Workspace) -> None:
    unread = _since(_golden(ws), "inconclusive", "the last receipt can't be used: x")
    assert _line(render(unread)) == (
        "**Since the last receipt:** not replayed (the last receipt can't be used: x)"
    )
    empty = _since(_golden(ws), "skipped", "the last receipt has no findings", findings=[])
    assert _line(render(empty)).endswith("COUNTEREXAMPLE): it had no findings")


def test_a_hostile_old_call_renders_inert(ws: Workspace) -> None:
    call = "f(x=`` \u202e<b>@octocat</b>\n# Approved)"
    markdown = render(_since(_golden(ws), findings=[_replayed(1, Replay.FIXED, call)]))
    tokens = _flat(_parse(markdown))
    assert not {t.type for t in tokens} & {"link_open", "image", "html_inline", "fence"}
    assert all(_allowed_html(t) for t in tokens if t.type == "html_block")
    assert "\u202e" not in markdown and "\\u202e" in _line(markdown)  # shown, on its one line


@pytest.mark.parametrize("words", ["short", HOSTILE * 5])
def test_a_maximal_receipt_with_a_replay_stays_within_its_limits(ws: Workspace, words: str
                                                                  ) -> None:  # fmt: skip
    receipt = _receipt(ws, words, many=20).model_copy(
        update={"status": RunStatus.ENVIRONMENT_ERROR, "status_reason": words,
                "level_reasons": [words] * 20, "unchecked": [words] * 20}
    )  # fmt: skip
    commands = [f"python -m pytest {i}" for i in range(21)]
    stage = receipt.stages[0].model_copy(update={"commands": commands})
    receipt = receipt.model_copy(update={"stages": [
        stage.model_copy(update={"name": name}) for name in STAGES]})  # fmt: skip
    found = [_replayed(i, Replay.STILL_FAILS, words) for i in range(1, 21)]
    markdown = render(_since(receipt, reason=words, findings=found))
    assert len(_main_lines(markdown)) <= MAX_MAIN_LINES
    assert len(markdown.splitlines()) <= MAX_LINES and len(markdown) <= MAX_CHARS
    assert "and 15 more in receipt.json" in _line(markdown)


def test_the_page_can_be_cut_shorter(ws: Workspace) -> None:
    receipt = _receipt(ws, "y" * 5_000, many=20)
    markdown = render(receipt, max_chars=20_000)
    assert len(markdown) <= 20_000
    assert "(receipt.md stays within 20,000 characters)" in markdown
    assert render(receipt) == render(receipt, max_chars=MAX_CHARS)


@pytest.mark.parametrize(
    ("doubt", "words"),
    [
        ("refused", "the code's own refusal"),
        ("os_limit", "the operating system's limit"),
        ("finished_object", "deletes this attribute"),
    ],
)
def test_s5_a_doubted_finding_says_so_and_that_it_still_counts(
    ws: Workspace, doubt: Doubt, words: str
) -> None:
    def page(flag: Doubt | None) -> str:
        return render(build(l4_run(break_my_fix=attack(
            status=AttackStatus.FOUND, findings=(finding(1, doubt=flag),))), ws))  # fmt: skip

    line = next(line for line in page(doubt).split("\n") if "**Doubt (still counted):**" in line)
    assert words in line and "f_t1(x=-1)" in line
    assert "Doubt" not in page(None)
    assert set(DOUBT_WORDS) == set(get_args(Doubt))

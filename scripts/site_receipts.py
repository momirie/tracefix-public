"""The Receipt gallery's data-made parts (docs/landing/receipts/ and receipts/<case>/).

Each fixture's receipt folder in docs/landing/_data/receipts/<case>/ (written by
`scripts/landing_run.py --all`, recorded model answers) and the fixture itself in
tests/fixtures/<case>/ (the issue, the known answer, the base and head snapshots) become one card
on the gallery and one page per case: the issue, the fix's diff, the receipt as it reads in a PR
comment, the test files Tracefix wrote and the terminal run.

`receipt.md` is rendered with markdown-it-py the way GitHub renders it (tables, a WARNING alert,
the run log folded in a `<details>`). Its text is escaped by `tracefix.receipt_md`; the only raw
HTML it may hold is that `<details>` wrapper, and rendering refuses anything else. Everything else
from the data is escaped here.
"""

from __future__ import annotations

import difflib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from markdown_it.utils import EnvType, OptionsDict

from tracefix.attack import AttackStatus
from tracefix.integrity import IntegrityStatus
from tracefix.ladder import ORDER
from tracefix.regressions import RegressionStatus
from tracefix.repro import ReproStatus

ROOT = Path(__file__).resolve().parent.parent
RECEIPTS = ROOT / "docs" / "landing" / "_data" / "receipts"
FIXTURES = ROOT / "tests" / "fixtures"
GITHUB = "https://github.com/momirie/tracefix/blob/main/"
SKIP = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
# The fixtures in the order the home page and tests/fixtures/README.md list them.
ORDER_ON_PAGE = (
    "good_fix",
    "partial_fix",
    "wrong_but_green",
    "test_weakened",
    "special_cased",
    "unguarded_test",
    "no_fix",
    "env_broken",
    "method_partial",
    "method_good",
    "py39_partial",
)
# The only raw HTML receipt.md writes: the folded run log.
ALLOWED_HTML = {"<details>", "</details>", "<summary>Run log</summary>"}
ALERTS = {"NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION"}
MINUS = "\u2212"  # the typographic minus in a diff's size
# Stage results that are evidence against the fix (what tracefix.ladder.counterexamples reads),
# with the stages' own status enums (the names are checked in tests/test_site_receipts.py).
BROKE = {
    ("break_my_fix", AttackStatus.FOUND.value),
    ("integrity", IntegrityStatus.FLAGGED.value),
    ("regressions", RegressionStatus.FOUND.value),
    ("reproduce", ReproStatus.FIX_DOES_NOT_FIX.value),
}
_STAGE_LINE = re.compile(r"^\[\s*([\d.]+)\] \[\d+/\d+\] (\w+): ")
_STAMP = re.compile(r"^\[\s*([\d.]+)\]")
HOW = {"exactly": "exactly", "at_least": "at least", "at_most": "at most"}

Json = dict[str, Any]


def e(text: object) -> str:
    return escape(str(text), quote=True)


def cases(receipts: Path | None = None) -> list[str]:
    """Every case with a receipt folder, in the page order (unknown names last, sorted)."""
    found = sorted(p.name for p in (receipts or RECEIPTS).iterdir() if p.is_dir())
    rank = {name: i for i, name in enumerate(ORDER_ON_PAGE)}
    return sorted(found, key=lambda name: (rank.get(name, len(rank)), name))


# ---- One case's facts ----


@dataclass(frozen=True)
class Diff:
    """One changed file: its path and its unified diff lines (no file header)."""

    path: str
    lines: tuple[str, ...]

    @property
    def added(self) -> int:
        return sum(1 for line in self.lines if line.startswith("+"))

    @property
    def removed(self) -> int:
        return sum(1 for line in self.lines if line.startswith("-"))


@dataclass(frozen=True)
class Case:
    name: str
    receipt: Json
    receipt_md: str
    run_log: str
    expected: Json
    issue_md: str
    diffs: tuple[Diff, ...]
    written: tuple[tuple[str, str], ...]  # (path in the receipt folder, text) of the tests

    @property
    def level(self) -> str:
        return str(self.receipt["level"])

    @property
    def want(self) -> tuple[str, str]:
        """The known answer: ("exactly" | "at_least" | "at_most", level)."""
        ((how, level),) = self.expected["receipt"]["level"].items()
        return str(how), str(level)

    @property
    def matches(self) -> bool:
        """Whether the receipt's level meets the known answer (the order of tracefix.ladder)."""
        how, level = self.want
        got, want = ORDER.index(self.level), ORDER.index(level)
        return {"exactly": got == want, "at_least": got >= want, "at_most": got <= want}[how]


def _files(root: Path) -> dict[str, Path]:
    return {
        p.relative_to(root).as_posix(): p
        for p in sorted(root.rglob("*"))
        if p.is_file() and not SKIP.intersection(p.relative_to(root).parts)
    }


def diffs(fixture: Path) -> tuple[Diff, ...]:
    """The fix as the fixture repo's head commit makes it: base/ against head/, file by file."""
    base, head = _files(fixture / "base"), _files(fixture / "head")
    out = []
    for path in sorted(base.keys() | head.keys()):
        old = base[path].read_text(encoding="utf-8").splitlines() if path in base else []
        new = head[path].read_text(encoding="utf-8").splitlines() if path in head else []
        lines = list(difflib.unified_diff(old, new, lineterm=""))[2:]  # drop the ---/+++ header
        if lines:
            out.append(Diff(path, tuple(lines)))
    return tuple(out)


def load(name: str, receipts: Path | None = None, fixtures: Path | None = None) -> Case:
    folder = (receipts or RECEIPTS) / name
    fixture = (fixtures or FIXTURES) / name
    written = tuple(
        (p.relative_to(folder).as_posix(), p.read_text(encoding="utf-8"))
        for sub in ("repro", "findings")
        for p in sorted((folder / sub).glob("*.py"))
    )
    return Case(
        name=name,
        receipt=json.loads((folder / "receipt.json").read_text(encoding="utf-8")),
        receipt_md=(folder / "receipt.md").read_text(encoding="utf-8"),
        run_log=(folder / "run.log").read_text(encoding="utf-8"),
        expected=json.loads((fixture / "expected.json").read_text(encoding="utf-8")),
        issue_md=(fixture / "ISSUE.md").read_text(encoding="utf-8"),
        diffs=diffs(fixture),
        written=written,
    )


def title(case: Case) -> str:
    return str(case.receipt["issue"]["title"])


def run_time(case: Case) -> str:
    """The run's length from its terminal log's last stamp, as "1:14"."""
    stamps = re.findall(r"^\[\s*([\d.]+)\]", case.run_log, flags=re.M)
    seconds = round(float(stamps[-1])) if stamps else 0
    return f"{seconds // 60}:{seconds % 60:02d}"


def headline(case: Case) -> str:
    """What the receipt found first: its first counterexample, else the reason for the highest
    rung it opened (the L4 reason on an L4 receipt, not the L1 one), else its first reason."""
    if case.receipt["findings"]:
        first = case.receipt["findings"][0]
        return f"{first['call']} → {first['outcome']}"
    reasons = [str(r) for r in case.receipt["level_reasons"]]
    opened = [r for r in reasons if not r.startswith("not ")]
    if opened:
        return opened[-1]
    return reasons[0] if reasons else str(case.receipt["status_reason"])


# ---- Markdown, as GitHub shows it in a PR comment ----


def _check_html(tokens: Sequence[Token]) -> None:
    for token in tokens:
        if token.type in ("html_block", "html_inline"):
            for line in token.content.splitlines():
                if line.strip() and line.strip() not in ALLOWED_HTML:
                    raise ValueError(f"unexpected raw HTML in a receipt: {line.strip()!r}")
        if token.children:
            _check_html(token.children)


def _alerts(tokens: list[Token]) -> None:
    """GitHub's `> [!WARNING]` blockquotes as a titled box, as GitHub shows them."""
    for i, token in enumerate(tokens[:-3]):
        inline = tokens[i + 2]
        found = re.fullmatch(r"\[!([A-Z]+)\]", inline.content.strip())
        if token.type != "blockquote_open" or inline.type != "inline" or not found:
            continue
        kind = found.group(1)
        if kind not in ALERTS:
            continue
        token.tag = "div"
        token.attrSet("class", f"alert alert-{kind.lower()}")
        tokens[i + 1].attrSet("class", "alert-title")
        text = Token("text", "", 0)
        text.content = kind.capitalize()
        inline.children = [text]
        close = next(
            t for t in tokens[i + 1 :] if t.type == "blockquote_close" and t.level == token.level
        )
        close.tag = "div"


def _shift(tokens: list[Token], by: int) -> None:
    """Headings `by` levels down, under the page's own h1 and h2."""
    for token in tokens:
        if token.type in ("heading_open", "heading_close"):
            token.tag = f"h{min(6, int(token.tag[1]) + by)}"


def _label_tables(tokens: list[Token]) -> None:
    """Each table's scroll box is named after the heading above it."""
    heading = "Table"
    for i, token in enumerate(tokens):
        if token.type == "heading_open":
            heading = tokens[i + 1].content
        if token.type == "table_open":
            token.meta["label"] = heading


def _table_open(
    self: RendererHTML, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
) -> str:
    label = e(tokens[idx].meta.get("label", "Table"))
    return f'<div class="md-scroll" tabindex="0" role="region" aria-label="{label}">\n<table>\n'


def _table_close(
    self: RendererHTML, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
) -> str:
    return "</table>\n</div>\n"


def markdown(text: str, shift: int, html: bool) -> str:
    """Markdown as HTML. `html=True` lets through only receipt.md's `<details>` wrapper."""
    md = MarkdownIt("commonmark", {"html": html}).enable("table").disable("image")
    md.add_render_rule("table_open", _table_open)
    md.add_render_rule("table_close", _table_close)
    tokens = md.parse(text)
    _check_html(tokens)
    _alerts(tokens)
    _shift(tokens, shift)
    _label_tables(tokens)
    return str(md.renderer.render(tokens, md.options, {}))


# ---- Fragments ----


def vt(kind: str, case: Case) -> str:
    """A view-transition name shared by a card's part and the case page's: the browser morphs
    one into the other when the visitor goes from the gallery to the case (site.css)."""
    return f"view-transition-name:{kind}-{case.name};view-transition-class:rc-{kind}"


def level_badge(level: str, style: str = "") -> str:
    red = " red" if level == "COUNTEREXAMPLE" else ""
    attr = f' style="{style}"' if style else ""
    return f'<span class="lvl{red}"{attr}>{e(level)}</span>'


def known_answer(case: Case) -> str:
    how, level = case.want
    mark = "meets it" if case.matches else "does not meet it"
    return f"Known answer: {HOW[how]} {e(level)} · {mark}"


def diffstat(case: Case) -> str:
    files = len(case.diffs)
    added = sum(d.added for d in case.diffs)
    removed = sum(d.removed for d in case.diffs)
    noun = "file" if files == 1 else "files"
    return f"{files} {noun} changed, +{added} {MINUS}{removed}"


# A fixture's description may say the fix is "correct for all inputs": true of the toy bug by
# construction, but no receipt can show it, so the site leaves it out (the developer, 2026-11-07).
UNPROVABLE = "correct for all inputs and "


def fix_summary(case: Case) -> str:
    """What the fix does, from the fixture's description, without a claim no receipt can prove."""
    return str(case.expected["summary"]).replace(UNPROVABLE, "")


def card(case: Case, i: int = 0) -> str:
    """One case on the gallery: the issue, what the fix does, the diff's size, the level."""
    paths = "".join(f"<li>{e(d.path)}</li>" for d in case.diffs)
    cx = " rc-cx" if case.level == "COUNTEREXAMPLE" else ""
    return (
        f'<li class="rc{cx}" data-level="{e(case.level)}" data-reveal'
        f' style="--d:{i % 3};{vt("card", case)}">'
        f'<p class="rc-top"><span class="rc-name">{e(case.name)}</span>'
        f"{level_badge(case.level, vt('lvl', case))}</p>"
        f'<h2 class="rc-title" style="{vt("title", case)}">'
        f'<a href="{e(case.name)}/">{e(title(case))}</a></h2>'
        f'<p class="rc-fix">{e(fix_summary(case))}</p>'
        f'<p class="rc-diff">{e(diffstat(case))}</p><ul class="rc-files">{paths}</ul>'
        f'<p class="rc-head"><span class="label">Receipt</span>{e(headline(case))}</p>'
        f'<p class="rc-want">{known_answer(case)}</p>'
        "</li>"
    )


def _diff_line(line: str) -> str:
    kind = {"+": " d-add", "-": " d-del", "@": " d-hunk"}.get(line[:1], "")
    return f'<div class="d{kind}">{e(line) or " "}</div>'


def diff_panels(case: Case) -> str:
    out = []
    for d in case.diffs:
        lines = "".join(_diff_line(line) for line in d.lines)
        out.append(
            f'<figure class="panel diff"><figcaption>{e(d.path)}'
            f' <span class="soft">+{d.added} {MINUS}{d.removed}</span></figcaption>'
            f'<div class="lines" tabindex="0" role="region" aria-label="Diff of {e(d.path)}">'
            f'<div class="lines-in">{lines}</div></div></figure>'
        )
    return "\n".join(out)


def written_panels(case: Case) -> str:
    if not case.written:
        return (
            '<p class="mute">This run wrote no test files:'
            " it stopped before the reproduction stage.</p>"
        )
    return "\n".join(
        f'<figure class="panel"><figcaption>{e(path)}</figcaption>'
        f'<pre class="code" tabindex="0">{e(text.rstrip())}</pre></figure>'
        for path, text in case.written
    )


def _quote(prop: Json) -> str:
    quote = prop.get("quote") or prop.get("claim") or ""
    source = prop.get("source") or ""
    cite = f"<cite>{e(source)}</cite>" if source else ""
    return f'<blockquote class="cx-promise"><p>{e(quote)}</p>{cite}</blockquote>' if quote else ""


def finding_card(finding: Json, written: dict[str, str]) -> str:
    """One counterexample: the call, its outcome before and after the fix (site.js turns the two
    rows into a switch), the promise it breaks, and its pytest file with a Copy button."""
    prop = finding.get("property") or {}
    expected = finding.get("expected")
    want = f'<p class="cx-want">Promised: <code>{e(expected)}</code></p>' if expected else ""
    file = finding.get("file") or ""
    test = written.get(file, "")
    copy = (
        f'<button type="button" class="copy cx-copy" data-copy="{e(file)}" hidden>'
        "Copy the test</button>"
        f'<textarea class="sr-only" data-copy-src="{e(file)}" tabindex="-1" aria-hidden="true"'
        f" readonly>{e(test)}</textarea>"
        if test
        else ""
    )
    same = finding["base_outcome"] == finding["outcome"]
    relation = (
        "Unchanged by the fix: the fix left this input broken."
        if same
        else str(finding.get("relation") or "")
    )
    return (
        f'<article class="cx-card" data-reveal data-when="after">'
        f'<p class="eyebrow">Finding {e(finding["number"])} · {e(finding["function"])}</p>'
        f'<p class="cx-call"><code>{e(finding["call"])}</code></p>'
        '<div class="cx-switch" role="group" aria-label="Show the outcome" hidden>'
        '<button type="button" data-when="before" aria-pressed="false">Before the fix</button>'
        '<button type="button" data-when="after" aria-pressed="true">After the fix</button></div>'
        '<dl class="cx-outs">'
        f'<div class="cx-row" data-row="before"><dt>Before the fix</dt>'
        f"<dd><code>{e(finding['base_outcome'])}</code></dd></div>"
        f'<div class="cx-row" data-row="after"><dt>After the fix</dt>'
        f'<dd><code class="cx-bad">{e(finding["outcome"])}</code></dd></div>'
        "</dl>"
        f'<p class="cx-rel">{e(relation)}</p>'
        f"{want}{_quote(prop)}"
        f'<p class="cx-file"><span class="label">{e(file)}</span>{copy}</p>'
        "</article>"
    )


def counterexample_section(case: Case) -> str:
    """The findings as cards, between the fix and the receipt; nothing when there are none."""
    if not case.receipt["findings"]:
        return ""
    written = dict(case.written)
    cards = "\n".join(finding_card(f, written) for f in case.receipt["findings"])
    return (
        '<section id="cx" class="band" aria-labelledby="cx-h">\n<div class="frame pad">\n'
        '<div class="sec-head"><h2 id="cx-h" class="h2" data-words>The counterexample. '
        '<span class="soft">An input the fixed code still gets wrong.</span></h2>'
        '<p class="mute" data-reveal style="--d:2">Each comes with a pytest file that fails on the'
        " fixed code. Switch between before and after the fix to see what the fix changed for"
        " this input.</p></div>\n"
        f'<div class="cx-cards">\n{cards}\n</div>\n</div>\n</section>'
    )


def timeline(case: Case) -> str:
    """The run's stages as one bar, each piece as long as the stage took (from the log's stamps),
    red where a stage found evidence against the fix; site.js moves a playhead along it."""
    reasons = {st["name"]: st for st in case.receipt["stages"]}
    marks = [
        (float(m.group(1)), m.group(2))
        for m in map(_STAGE_LINE.match, case.run_log.splitlines())
        if m
    ]
    stamps = [float(m.group(1)) for m in map(_STAMP.match, case.run_log.splitlines()) if m]
    end = stamps[-1] if stamps else 0.0
    if not marks or end <= 0:
        return ""
    pieces, start = [], 0.0
    for at, name in marks:
        stage = reasons.get(name, {})
        status = str(stage.get("status", ""))
        bad = " tl-bad" if (name, status) in BROKE else ""
        tip = f"{name}: {status}, {at - start:.1f} s. {stage.get('reason', '')}"
        pieces.append(
            f'<span class="tl-seg{bad}" data-from="{start:g}" data-to="{at:g}"'
            f' style="flex-grow:{max(at - start, 0.05):.2f}" title="{e(tip)}">'
            f'<span class="tl-name">{e(name)}</span></span>'
        )
        start = at
    return (
        f'<div class="timeline" data-end="{end:g}" aria-hidden="true">'
        f'{"".join(pieces)}<i class="tl-head"></i></div>'
    )


def log_lines(case: Case) -> str:
    """The terminal log, one span per line with its second (site.js replays it)."""
    out = []
    for line in case.run_log.rstrip().splitlines():
        stamp = _STAMP.match(line)
        at = f' data-t="{float(stamp.group(1)):g}"' if stamp else ""
        bad = " cxw" if "COUNTEREXAMPLE" in line else ""
        out.append(f'<span class="o{bad}"{at}>{e(line)}\n</span>')
    return "".join(out)


def climb_data(receipts: Path | None = None, fixtures: Path | None = None) -> list[Json]:
    """Each fixture's climb up the ladder, as its receipt's level reasons give it: one reason per
    rung opened (L1 upward), then why the next rung stayed shut; a counterexample or a stopped run
    has only its own reasons. Checked against the level, so a changed format stops the build."""
    out = []
    for name in cases(receipts):
        case = load(name, receipts, fixtures)
        reasons = [str(r) for r in case.receipt["level_reasons"]]
        opened = [r for r in reasons if not r.startswith("not ")]
        level = case.level
        climbed = level.startswith("L") and case.receipt["status"] == "ok"
        if climbed and len(opened) != int(level[1:]):
            raise ValueError(f"{name}: {len(opened)} rung reasons for {level}")
        out.append({"case": name, "level": level, "title": title(case), "reasons": reasons})
    return out


# ---- The pages' holes ----


def filters(found: list[Case]) -> str:
    """One chip per level the receipts reached (ladder order) and All: site.js shows them and
    filters the cards; without JavaScript they stay hidden and every card shows."""
    chip = (
        '<button type="button" class="chip" data-filter="{}" aria-pressed="{}">'
        "{} <span>{}</span></button>"
    )
    levels = sorted({c.level for c in found}, key=lambda lv: ORDER.index(lv))
    chips = [chip.format("all", "true", "All", len(found))]
    for lv in reversed(levels):
        n = sum(c.level == lv for c in found)
        chips.append(chip.format(e(lv), "false", e(lv), n))
    return "".join(chips)


def gallery_fields(receipts: Path | None = None, fixtures: Path | None = None) -> dict[str, str]:
    found = [load(name, receipts, fixtures) for name in cases(receipts)]
    return {
        "cases_total": str(len(found)),
        "cases_matching": str(sum(c.matches for c in found)),
        "cases_cx": str(sum(c.level == "COUNTEREXAMPLE" for c in found)),
        "filters": filters(found),
        "cards": "\n".join(card(c, i) for i, c in enumerate(found)),
    }


def pager(name: str, receipts: Path | None = None, fixtures: Path | None = None) -> str:
    """The previous and next receipts in the gallery's order (round the end), as two cards."""
    names = cases(receipts)
    i = names.index(name)
    out = []
    for rel, step in (("prev", -1), ("next", 1)):
        other = load(names[(i + step) % len(names)], receipts, fixtures)
        word = "Previous receipt" if rel == "prev" else "Next receipt"
        out.append(
            f'<a class="pg pg-{rel}" rel="{rel}" href="../{e(other.name)}/">'
            f'<span class="eyebrow">{word}</span>'
            f'<span class="pg-name">{e(other.name)}{level_badge(other.level)}</span>'
            f'<span class="pg-title">{e(title(other))}</span></a>'
        )
    keys = '<p class="pg-keys" hidden>Or press <kbd>←</kbd> and <kbd>→</kbd></p>'
    return "".join(out) + keys


def case_fields(
    name: str, receipts: Path | None = None, fixtures: Path | None = None
) -> dict[str, str]:
    case = load(name, receipts, fixtures)
    return {
        "case": e(case.name),
        "issue_title": e(title(case)),
        "fix_summary": e(fix_summary(case)),
        "level_badge": level_badge(case.level, vt("lvl", case)),
        "vt_title": vt("title", case),
        "pager": pager(name, receipts, fixtures),
        "known_answer": known_answer(case),
        "run_time": e(run_time(case)),
        "diffstat": e(diffstat(case)),
        "issue": markdown(case.issue_md, shift=2, html=False),
        "diff": diff_panels(case),
        "receipt": markdown(case.receipt_md, shift=1, html=True),
        "written": written_panels(case),
        "run_log": log_lines(case),
        "timeline": timeline(case),
        "cx_section": counterexample_section(case),
        "jump_cx": '<li><a href="#cx">The counterexample</a></li>'
        if case.receipt["findings"]
        else "",
        "receipt_json": f"{GITHUB}docs/landing/_data/receipts/{e(case.name)}/receipt.json",
        "receipt_md": f"{GITHUB}docs/landing/_data/receipts/{e(case.name)}/receipt.md",
        "fixture": f"https://github.com/momirie/tracefix/tree/main/tests/fixtures/{e(case.name)}",
    }


def head_title(name: str) -> str:
    """The case page's <title> and og:title (escaped: the head puts it in attributes)."""
    return e(f"{name}: {title(load(name))}")


def head_description(name: str) -> str:
    return e(f"The receipt Tracefix wrote for the {name} fixture. {fix_summary(load(name))}")


def _red(level: str) -> str:
    return " red" if level == "COUNTEREXAMPLE" else ""


def climb_fields(receipts: Path | None = None, fixtures: Path | None = None) -> dict[str, str]:
    """The Method page's ladder: a button per fixture, the climbs as JSON (site.js plays them)."""
    climbs = climb_data(receipts, fixtures)
    buttons = "".join(
        f'<button type="button" class="climb-pick{_red(str(c["level"]))}"'
        f' data-case="{e(c["case"])}" data-level="{e(c["level"])}" aria-pressed="false">'
        f"{e(c['case'])}</button>"
        for c in climbs
    )
    # JSON inside <script>: "<" escaped so no text can close the element.
    data = json.dumps(climbs, ensure_ascii=True).replace("<", "\\u003c")
    return {"climb_buttons": buttons, "climb_data": data}

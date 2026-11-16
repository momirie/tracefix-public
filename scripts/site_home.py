"""The home page's data-made parts (docs/landing/index.html), from the repo's own records.

The site rule (docs/plans/website-pages.md): the home page's source types no number
(tests/test_site_home.py). Every number a visitor reads comes from here: the benchmark standing
(as a sentence and as one mark per measured fix) and gates from docs/landing/_data/, the real
run's numbers from the partial_fix receipt the replay links to, the code panels from the fixture
and the finding Tracefix wrote, the three tabs from their fixtures' receipts, and the requirements
from pyproject.toml and the code's constants. Every string from the data is escaped. The fixture
picker on the ladder and the receipt on a pull request moved to the Method page with the home page
cut (scripts/site_method.py).
"""

from __future__ import annotations

import json
import re
import textwrap
import tomllib
from collections.abc import Sequence
from html import escape
from pathlib import Path
from typing import Any

import make_fixtures
import site_benchmark
import site_receipts

from tracefix import interpreter

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
# The replay's fixture, its function and the file the code panel shows.
REPLAY = "partial_fix"
REPLAY_FILE = "src/svc/config.py"
REPLAY_FUNCTION = "parse_port"
# The tabs: (fixture, the changed file the tab shows). Their names and one-line descriptions are
# copy in the page source; everything a receipt says comes from here.
MOVES = (
    ("wrong_but_green", "src/stats/buckets.py"),
    ("special_cased", "src/billing/calendar.py"),
    ("test_weakened", "tests/test_slug.py"),
)

Json = dict[str, Any]


def e(text: object) -> str:
    return escape(str(text), quote=True)


def _script_json(value: object) -> str:
    """JSON for a <script> element: "<" escaped so no text can close the element."""
    return json.dumps(value, ensure_ascii=True).replace("<", "\\u003c")


def _stage(case: site_receipts.Case, name: str) -> Json:
    found: Json = next(s for s in case.receipt["stages"] if s["name"] == name)
    return found


# ---- The replay: partial_fix's fixed function, its finding and the real run ----


def function_lines(source: str, name: str) -> list[str]:
    """The lines of top-level function `name`, from its `def` to the line before the next
    top-level statement, without trailing blank lines."""
    lines = source.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"def {name}("))
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i] and not lines[i][0].isspace()),
        len(lines),
    )
    body = lines[start:end]
    while body and not body[-1].strip():
        body.pop()
    return body


def code_panel(case: site_receipts.Case, fixture: Path) -> str:
    """The fixed function as head has it: the fix's added lines marked, and the docstring line
    the finding's property quotes marked as the promise the replay checks."""
    source = (fixture / "head" / REPLAY_FILE).read_text(encoding="utf-8")
    diff = next(d for d in case.diffs if d.path == REPLAY_FILE)
    added = {line[1:] for line in diff.lines if line.startswith("+")}
    quote = case.receipt["findings"][0]["property"]["quote"]
    out = []
    for line in function_lines(source, REPLAY_FUNCTION):
        kind, mark = "", ""
        if line in added:
            kind = " ln-add"
        elif quote in line:
            kind, mark = " ln-doc", ' id="doc-line"'
        out.append(f'<div class="ln{kind}"{mark}>{e(line) or " "}</div>')
    if 'id="doc-line"' not in "".join(out):
        raise ValueError(f"{REPLAY}: the finding's quote is not in {REPLAY_FUNCTION}'s source")
    return "\n          ".join(out)


def _money(usd: float) -> str:
    return f"${usd:.2f}"


def real_run(case: site_receipts.Case) -> str:
    """The real run behind the replay, from its receipt: one short line per stage that counts."""
    guard = _stage(case, "guard")["evidence"]
    diff = _stage(case, "behaviour_diff")["evidence"]
    attack = _stage(case, "break_my_fix")["evidence"]
    llm = case.receipt["llm"]
    explained = sum(
        all(lab["label"] == "intended" for lab in c["labels"])
        for c in case.receipt["behaviour_changes"]
    )
    changes = int(diff["changes"])
    items = (
        f"Break My Fix: {attack['inputs_tried']:,} inputs, {attack['findings']} finding"
        + ("" if attack["findings"] == 1 else "s"),
        f"Guard: {guard['killed']} of {guard['mutants']} mutants killed",
        f"Behaviour diff: {diff['inputs_compared']:,} inputs, {changes} change"
        + ("" if changes == 1 else "s")
        + (", explained" if explained == changes else f", {explained} explained"),
        f"{llm['calls']} model calls ({_money(llm['cost_estimate']['usd'])} when live)",
        f"Run time {site_receipts.run_time(case)} (model answers replayed)",
    )
    return "".join(f"<li>{e(item)}</li>" for item in items)


def finding_fields(case: site_receipts.Case) -> dict[str, str]:
    """The receipt's first finding: the call, what it did, the promise it breaks, its test."""
    finding = case.receipt["findings"][0]
    path = str(finding["file"])
    written = dict(case.written)
    others = int(finding["other_inputs"])
    more = (
        f" {others} more input{'' if others == 1 else 's'} break it the same way." if others else ""
    )
    return {
        "finding_call": e(finding["call"]),
        "finding_outcome": e(finding["outcome"]),
        "finding_quote": e(finding["property"]["quote"]),
        "finding_source": e(finding["property"]["source"]),
        "finding_more": e(more),
        "finding_file": e(path),
        # The test as Tracefix wrote it, from its first import (the header comments repeat the
        # receipt's words, which the block above already says).
        "finding_test": e(written[path][written[path].index("from ") :].rstrip()),
    }


# ---- The tabs: three more fixtures, each as its receipt reports it ----


def changed_lines(case: site_receipts.Case, path: str) -> list[list[str]]:
    """The file's added and removed lines (no context), as [sign, text], dedented together."""
    diff = next(d for d in case.diffs if d.path == path)
    picked = [line for line in diff.lines if line[:1] in "+-"]
    body = textwrap.dedent("\n".join(line[1:] for line in picked)).split("\n")
    return [[line[0], text] for line, text in zip(picked, body, strict=True)]


def finds(case: site_receipts.Case) -> str:
    """What the receipt reports first: an integrity flag, else its first counterexample."""
    receipt = case.receipt
    if receipt["integrity_flags"]:
        flag = receipt["integrity_flags"][0]
        text = (
            f"Integrity check: the fix removes {flag['detail']} from {flag['file']}, an assert"
            f" that {flag['evidence']}."
        )
    elif receipt["findings"]:
        first = receipt["findings"][0]
        base = first["base_outcome"]
        before = " (the same before the fix)" if base == first["outcome"] else f" (before: {base})"
        text = f"Break My Fix: {first['call']} {first['outcome']}{before}."
    else:
        text = str(receipt["level_reasons"][-1]).capitalize() + "."
    return f"{text} Level: {receipt['level']}."


def moves(receipts: Path | None = None, fixtures: Path | None = None) -> list[Json]:
    out = []
    for name, path in MOVES:
        case = site_receipts.load(name, receipts, fixtures)
        out.append({
            "case": name, "issue": site_receipts.title(case), "file": path,
            "diff": changed_lines(case, path), "finds": finds(case),
        })  # fmt: skip
    return out


def diff_html(diff: list[list[str]]) -> str:
    return "".join(
        f'<div class="d {"d-add" if sign == "+" else "d-del"}">{e(sign + " " + text)}</div>'
        for sign, text in diff
    )


# ---- Where it stands, drawn: one mark per measured fix ----

# A figure's groups: (the mark's kind in site.css, how many fixes, what the receipts said).
Groups = Sequence[tuple[str, int, str]]
# Marks per row: the small figure and the large one use the same mark size, so areas compare.
MARK_COLS = (10, 17)


def _s(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def tally(heading: str, groups: Groups) -> str:
    """One figure: a mark per fix in group order, and a key that gives every count in words
    (the marks are decoration for a screen reader; the key is the table view)."""
    groups = [g for g in groups if g[1] > 0]
    total = sum(n for _, n, _ in groups)
    cols = MARK_COLS[0] if total <= MARK_COLS[0] * 4 else MARK_COLS[1]
    # A mark's tooltip is its row of the key (site.js reads it there, by the mark's kind).
    kinds = [kind for kind, n, _ in groups for _ in range(n)]
    marks = [f'<i class="mk mk-{kind}" style="--n:{at}"></i>' for at, kind in enumerate(kinds)]
    key = "".join(
        f'<li data-k="{kind}"><i class="mk mk-{kind}" aria-hidden="true"></i>'
        f"<span><b>{n}</b> {e(label)}</span></li>"
        for kind, n, label in groups
    )
    return (
        '<figure class="tally" data-reveal>'
        f"<figcaption><b>{total}</b> {e(heading)}</figcaption>"
        f'<div class="marks" style="--cols:{cols}" aria-hidden="true">{"".join(marks)}</div>'
        f'<ul class="tally-key">{key}</ul>'
        "</figure>"
    )


def _low(levels: Json) -> int:
    """The fixes whose receipt stopped below L2 without a counterexample."""
    return int(levels["L0"]) + int(levels["L1"])


def standing_marks(data: Path | None = None) -> str:
    """The standing sentence as two figures, from the same counts: every wrong agent fix and every
    correct fix of the standing slice as one mark, by what its receipt said. A count that does not
    add up to the slice's levels stops the build."""
    _, benchmark, _ = site_benchmark.load(data)
    section = benchmark[site_benchmark.standing_slice(benchmark)]
    wrong, (_, fixes) = section["agent_wrong"], site_benchmark.correct(section)
    caught, of = int(wrong["detection"]["n"]), int(wrong["detection"]["of"])
    if "own_mistake" not in section:
        # Without the benchmark's own reading, no counterexample may be drawn as a real catch.
        raise ValueError("the standing slice has no own_mistake record (scripts/site_data.py)")
    own = int(section["own_mistake"]["n"])
    passed = int(wrong["false_pass_l2"]["n"])
    if of - caught - passed != _low(wrong["levels"]):
        raise ValueError("wrong agent fixes: the counts do not add up to the levels")
    alarms, total = int(fixes["false_alarm"]["n"]), int(fixes["false_alarm"]["of"])
    found, real = int(fixes["counterexample"]["n"]), int(fixes["real_bug_in_gold"]["n"])
    high = int(fixes["at_least_l2"]["n"])
    if total - found - high != _low(fixes["levels"]) or real > found - alarms:
        raise ValueError("correct fixes: the counts do not add up to the levels")
    rest = "counterexample" if found - alarms == 1 else "counterexamples"
    return tally(
        _s(of, "wrong fix", "wrong fixes") + " written by a coding agent",
        (
            ("cx", own, _s(own, "counterexample that rests", "counterexamples that rest")
             + " on the agent\u2019s own mistake"),
            ("cxo", caught - own,
             _s(caught - own, "counterexample that rests", "counterexamples that rest")
             + " on something the merged fix shares"),
            ("l2", passed, "reached L2: a wrong fix that looked guarded"),
            ("low", of - caught - passed, "stopped at L1 or below"),
        ),
    ) + tally(
        _s(total, "correct fix", "correct fixes"),
        (
            ("cxo", alarms, _s(alarms, "false alarm", "false alarms")
             + ": a counterexample that was not a real bug"),
            ("cx", found - alarms, f"other {rest}, {real} of them labelled a real bug in the fix"),
            ("l2", high, "reached L2"),
            ("low", total - found - high, "stopped at L1 or below"),
        ),
    )  # fmt: skip


# ---- Where it stands, the costs, the requirements ----


def _minutes(seconds: float) -> str:
    return f"{seconds / 60:.1f} minutes"


def standing_fields(data: Path | None = None) -> dict[str, str]:
    gates, benchmark, _ = site_benchmark.load(data)
    name = site_benchmark.standing_slice(benchmark)
    section = benchmark[name]
    cost = section["cost_and_time"]
    usd, secs = cost["usd_per_run"], cost["seconds_per_run"]
    _, fixes = site_benchmark.correct(section)
    reached_l3 = any(
        site_benchmark.correct(benchmark[n])[1]["at_least_l3"]["n"]
        for n in site_benchmark.slices(benchmark)
    )
    top_rung_note = (
        ""
        if reached_l3
        else (
            f" No real correct fix has reached L3 yet: {fixes['at_least_l3']['n']} of"
            f" {fixes['at_least_l3']['of']} in {site_benchmark.slice_label(gates, name)}."
        )
    )
    return {
        "standing": e(site_benchmark.standing(gates, benchmark)),
        "standing_slice": e(site_benchmark.slice_label(gates, name)),
        "gates_holding": str(gates["holding"]),
        "gates_total": str(len(gates["gates"])),
        "false_alarms": f"{fixes['false_alarm']['n']} of {fixes['false_alarm']['of']}",
        "live_minutes": _minutes(secs["median"]),
        "live_minutes_slow": f"{_minutes(secs['p90'])} at the 90th percentile",
        "live_cost": _money(usd["median"]),
        "live_cost_max": _money(usd["max"]),
        "top_rung_note": e(top_rung_note),
    }


def requirement_fields() -> dict[str, str]:
    """Tracefix's own Python (pyproject.toml), the oldest project Python `--python` runs
    (interpreter.MIN_PYTHON) and git (the GIT_CONFIG_GLOBAL that workspace.py sets needs the
    version make_fixtures checks for)."""
    requires = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["requires-python"]
    found = re.fullmatch(r">=\s*([\d.]+)", requires)
    if found is None:
        raise ValueError(f"pyproject.toml: requires-python {requires!r} is not '>=X.Y.Z'")
    return {
        "python_min": found.group(1),
        "project_python_min": ".".join(map(str, interpreter.MIN_PYTHON)),
        "git_min": ".".join(map(str, make_fixtures.MIN_GIT_VERSION)),
    }


def fields(
    receipts: Path | None = None, fixtures: Path | None = None, data: Path | None = None
) -> dict[str, str]:
    """Every hole the home page fills."""
    case = site_receipts.load(REPLAY, receipts, fixtures)
    fixture = (fixtures or site_receipts.FIXTURES) / REPLAY
    tabs = moves(receipts, fixtures)
    first = tabs[0]
    return {
        **standing_fields(data),
        **requirement_fields(),
        **finding_fields(case),
        "standing_marks": standing_marks(data),
        "replay_case": REPLAY,
        "replay_file": e(REPLAY_FILE),
        "replay_code": code_panel(case, fixture),
        "real_run": real_run(case),
        "mv_case": e(first["case"]),
        "mv_issue": e(f"“{first['issue']}”"),
        "mv_file": e(first["file"]),
        "mv_diff": diff_html(first["diff"]),
        "mv_finds": e(first["finds"]),
        "moves_data": _script_json(tabs),
    }

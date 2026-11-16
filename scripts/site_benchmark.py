"""The Benchmark page's data-made parts (docs/landing/benchmark/), from docs/landing/_data/.

`scripts/site_data.py` writes the data from the repo's own records; this module turns it into
HTML fragments that `scripts/build_site.py` puts into the page's `{{name}}` holes. The page's
source has no number of its own (a test checks it): every count, rate and limit on the page
comes from here. Every string from the data is escaped.
"""

from __future__ import annotations

import json
import math
import re
from html import escape
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parent.parent / "docs" / "landing" / "_data"
GITHUB = "https://github.com/momirie/tracefix/blob/main/"
LEVELS = ("COUNTEREXAMPLE", "L0", "L1", "L2", "L3", "L4")

Json = dict[str, Any]

# Each fix kind a slice can measure: its name on the page and what Tracefix should do with it.
KINDS = {
    "gold": ("Upstream fix (gold)", "correct", "should get no counterexample"),
    "agent_ok": ("Correct agent fix", "correct", "should get no counterexample"),
    "partial": ("Upstream fix minus a hunk (partial)", "wrong", "should not reach L2"),
    "agent_wrong": ("Wrong agent fix", "wrong", "should not reach L2"),
}


def load(data: Path | None = None) -> tuple[Json, Json, Json]:
    """The gates, the per-slice summaries (and `method`) and the misses."""
    data = data or DATA

    def read(name: str) -> Json:
        found: Json = json.loads((data / name).read_text(encoding="ascii"))
        return found

    return read("gates.json"), read("benchmark.json"), read("misses.json")


def e(text: object) -> str:
    return escape(str(text), quote=True)


def pct(n: int, of: int) -> int:
    """A rate in whole percent, halves rounded up (as the benchmark report writes them)."""
    return math.floor(n * 100 / of + 0.5)


def rate(count: Json) -> str:
    """`{"n": 6, "of": 20}` as "6/20 (30%)"; a count over nothing was not measured."""
    n, of = int(count["n"]), int(count["of"])
    return f"{n}/{of} ({pct(n, of)}%)" if of else "not measured"


def slices(benchmark: Json) -> list[str]:
    """The slice names, newest first."""
    return sorted((k for k in benchmark if k.startswith("slice")), key=_slice_number, reverse=True)


def _slice_number(name: str) -> int:
    return int(name.removeprefix("slice"))


def slice_label(gates: Json, name: str) -> str:
    """The slice's column title in the release gate table, e.g. "Slice 2, dev (4 Nov 2026)"."""
    want = f"Slice {_slice_number(name)}"
    for column in gates["columns"]:
        if re.match(rf"{want}\b", column):
            return str(column)
    return want


def correct(section: Json) -> tuple[str, Json]:
    """The correct fixes a slice measured: gold and agent_ok together when it has both, else
    gold alone (with a note that says so beside each number)."""
    if "correct_fixes" in section:
        return "", section["correct_fixes"]
    return ", gold only", section["gold"]


def _stagger(i: int, per_row: int = 3) -> str:
    """Reveal attributes for the i-th card of a grid: cards in a row fade in one after another."""
    return f' data-reveal style="--d:{i % per_row}"'


def _gate_card(gate: Json, latest: str, earlier: list[str], i: int = 0) -> str:
    status = "holds" if gate["holds"] else "open"
    before = "".join(
        f'<p class="g-before"><span>{e(col)}</span> {e(gate["results"][col])}</p>'
        for col in earlier
    )
    return (
        f'<li class="gate g-{status}"{_stagger(i)}>'
        f'<p class="g-num">Gate {gate["number"]}</p>'
        f'<h3 class="g-title">{e(gate["title"])}</h3>'
        f'<p class="g-measures">{e(gate["measures"])}</p>'
        f'<p class="g-now"><span class="label">{e(latest)}</span>'
        f'<span class="g-val">{e(gate["results"][latest])}</span></p>'
        f"{before}"
        f'<p class="g-target"><span class="label">Target</span> {e(gate["target"])}</p>'
        f'<p class="g-status"><i aria-hidden="true"></i>{e(gate["status"])}</p>'
        "</li>"
    )


def gate_cards(gates: Json) -> str:
    """One card per release gate: what it measures, the latest result first, the target."""
    results = gates["columns"][2:-2]
    latest, earlier = results[-1], list(reversed(results[:-1]))
    return "\n".join(_gate_card(g, latest, earlier, i) for i, g in enumerate(gates["gates"]))


def _minutes(seconds: float) -> str:
    return f"{seconds / 60:.1f} min"


def _rows(section: Json) -> list[tuple[str, str]]:
    """The headline rows one slice can fill: (row name, value), in the page's order."""
    wrong = section.get("agent_wrong")
    rows = [
        ("Wrong agent fixes not green-lit (COUNTEREXAMPLE or L1 and below)",
         rate(wrong["not_green_lit"]) if wrong else "not measured"),
        ("Wrong agent fixes caught (COUNTEREXAMPLE)",
         rate(wrong["detection"]) if wrong else "not measured"),
        ("Wrong agent fixes at L2 (a false pass)",
         rate(wrong["false_pass_l2"]) if wrong else "not measured"),
    ]  # fmt: skip
    part = section["partial"]
    rows += [
        ("Partial fixes not green-lit", rate(part["not_green_lit"])),
        ("Partial fixes caught", rate(part["detection"])),
    ]
    only, fixes = correct(section)
    rows += [
        ("Correct fixes with a false alarm (developer label)", rate(fixes["false_alarm"]) + only),
        ("Real bugs found in correct fixes", rate(fixes["real_bug_in_gold"]) + only),
        ("Correct fixes at L2 or above", rate(fixes["at_least_l2"]) + only),
        ("Correct fixes at L3 or above", rate(fixes["at_least_l3"]) + only),
    ]
    cost = section["cost_and_time"]
    usd, secs = cost["usd_per_run"], cost["seconds_per_run"]
    rows += [
        ("Cost per run (mean / median / max)",
         f"${usd['mean']:.2f} / ${usd['median']:.2f} / ${usd['max']:.2f}"),
        ("Time per run (median / 90th percentile)",
         f"{_minutes(secs['median'])} / {_minutes(secs['p90'])}"),
    ]  # fmt: skip
    return rows


def results_table(gates: Json, benchmark: Json) -> str:
    """The slices side by side, newest first, one row per headline number."""
    names = slices(benchmark)
    per = [dict(_rows(benchmark[n])) for n in names]
    order = [row for row, _ in _rows(benchmark[names[0]])]
    head = "".join(f'<th scope="col">{e(slice_label(gates, n))}</th>' for n in names)
    body = "".join(
        f'<tr><th scope="row">{e(row)}</th>'
        + "".join(f"<td>{e(found[row])}</td>" for found in per)
        + "</tr>"
        for row in order
    )
    return (
        f'<thead><tr><th scope="col"><span class="sr-only">Measure</span></th>{head}</tr></thead>'
        f"<tbody>{body}</tbody>"
    )


def _bar(levels: Json, total: int, kind: str) -> str:
    """The run's levels as one stacked bar; the counts beside it carry the same numbers. Each
    piece knows its level and count (site.js shows them on hover) and has a view-transition name
    per fix kind and level, so switching slices morphs one slice's bar into the other's."""
    segments = "".join(
        f'<i class="lv lv-{lv.lower()}" data-lv="{lv}" data-n="{levels[lv]}" data-of="{total}"'
        f' style="flex-grow:{levels[lv]};view-transition-name:seg-{kind}-{lv.lower()}"'
        f' title="{lv}: {levels[lv]} of {total}"></i>'
        for lv in LEVELS
        if levels[lv]
    )
    return f'<span class="bar" aria-hidden="true">{segments}</span>'


def level_table(gates: Json, benchmark: Json, name: str) -> str:
    """One slice's levels per fix kind: a bar and the count at each level."""
    section = benchmark[name]
    head = "".join(f'<th scope="col" data-lv="{lv}">{lv}</th>' for lv in LEVELS)
    rows: list[str] = []
    for kind, (label, side, want) in KINDS.items():
        if kind not in section:
            continue
        levels = section[kind]["levels"]
        total = sum(levels[lv] for lv in LEVELS)
        counts = "".join(
            f'<td class="{"zero" if not levels[lv] else ""}" data-lv="{lv}">{levels[lv]}</td>'
            for lv in LEVELS
        )
        rows.append(
            f'<tr class="k-{side}" style="--r:{len(rows)}"><th scope="row"'
            f' style="view-transition-name:row-{kind}">'
            f'<span class="k-name">{e(label)}</span>'
            f'<span class="k-want">{e(want)}</span></th>'
            f"<td>{_bar(levels, total, kind)}</td>{counts}<td>{total}</td></tr>"
        )
    caption = f"Levels per fix, {e(slice_label(gates, name))}"
    return (
        f'<div class="levels-wrap" data-reveal data-slice="{name}" tabindex="0" role="region"'
        f' aria-label="{caption}">'
        f'<table class="levels"><caption class="label">{caption}</caption>'
        f'<thead><tr><th scope="col">Fix</th><th scope="col"><span class="sr-only">Bar</span></th>'
        f'{head}<th scope="col">Runs</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def slice_switch(gates: Json, benchmark: Json) -> str:
    """Buttons that show one slice's level table at a time (site.js; hidden without it)."""
    return "".join(
        f'<button type="button" class="chip" data-show-slice="{n}"'
        f' aria-pressed="{"true" if i == 0 else "false"}">{e(slice_label(gates, n))}</button>'
        for i, n in enumerate(slices(benchmark))
    )


def funnel(gates: Json, benchmark: Json, name: str) -> str:
    """One sentence on where a slice's numbers come from."""
    section = benchmark[name]
    f, aside = section["funnel"], section["set_aside"]
    receipts = sum(outcomes.get("receipt", 0) for outcomes in f["runs"].values())
    counted = sum(sum(section[kind]["levels"].values()) for kind in KINDS if kind in section)
    set_aside = sum(v["n"] for k, v in aside.items() if k != "tasks")
    split_n = {split.replace("_", " "): n for split, n in section["splits"].items()}
    covered = f"The numbers cover {sum(split_n.values())} tasks"
    if len(split_n) == 1:
        covered += f", all {next(iter(split_n))}"
    else:
        covered += " (" + " and ".join(f"{n} {split}" for split, n in split_n.items()) + ")"
    return (
        f"<p><b>{e(slice_label(gates, name))}.</b> {f['cases']} tasks chosen,"
        f" {f['prepared']} prepared, {f['ready']} passed every check. {covered}."
        f" {receipts} runs with a receipt (repeats included): {counted} counted,"
        f" {set_aside} set aside. Spent by the receipts:"
        f" ${section['cost_and_time']['usd_spent_known']:.2f}.</p>"
    )


def _miss(miss: Json, i: int = 0) -> str:
    kind = KINDS[miss["kind"]][0]
    notes = "".join(f"<p>{e(note)}</p>" for note in miss["notes"])
    why = (
        f"<details><summary>The developer\u2019s label</summary>{notes}</details>" if notes else ""
    )
    lv = miss["level"]
    return (
        f'<li class="miss"{_stagger(i)} data-slice="{e(miss["slice"])}"'
        f' data-find="{e(miss["instance_id"].lower())}">'
        f'<p class="m-id">{e(miss["instance_id"])}</p>'
        f'<p class="m-facts"><span>{e(kind)}</span><span>Slice {_slice_number(miss["slice"])}'
        f'</span><span class="m-lv{" m-cx" if lv == "COUNTEREXAMPLE" else ""}">{e(lv)}</span></p>'
        f"{why}"
        f'<a class="more" href="{e(GITHUB + miss["receipt"])}">Read the receipt'
        f'<span class="sr-only"> for {e(miss["instance_id"])}, {e(miss["run"])}</span></a></li>'
    )


def misses(found: Json, why: str) -> tuple[int, str]:
    """The misses of one kind, newest slice first: how many, and their list items."""
    picked = [m for m in found["misses"] if m["why"] == why]
    picked.sort(key=lambda m: (-_slice_number(m["slice"]), m["instance_id"].lower(), m["run"]))
    return len(picked), "\n".join(_miss(m, i) for i, m in enumerate(picked))


def standing_slice(benchmark: Json) -> str:
    """The newest slice that measured wrong agent fixes: the one the plain-words summary reads."""
    return next(n for n in slices(benchmark) if "agent_wrong" in benchmark[n])


def standing(gates: Json, benchmark: Json) -> str:
    """The plain-words summary, from the newest slice that measured wrong agent fixes, with the
    benchmark's own caveat on the counterexamples (how many rest on the agent's mistake)."""
    section = benchmark[standing_slice(benchmark)]
    wrong, (_, fixes) = section["agent_wrong"], correct(section)
    caught = f" {wrong['detection']['n']} a counterexample"
    own = section.get("own_mistake")
    if own and own["n"] < own["of"]:
        caught += (
            f", but only {own['n']} of those {own['of']} rests on the agent\u2019s own mistake;"
        )
    else:
        caught += ", and"
    return (
        f"Of {wrong['detection']['of']} wrong fixes written by a coding agent, Tracefix gave"
        f"{caught} {wrong['false_pass_l2']['n']} still reached L2. Of"
        f" {fixes['false_alarm']['of']} correct fixes, {fixes['false_alarm']['n']} got a false"
        " alarm."
    )


def ladder_note(benchmark: Json) -> str:
    """Why correct fixes stall, said only while no correct fix in any slice has reached L3."""
    if any(correct(benchmark[n])[1]["at_least_l3"]["n"] for n in slices(benchmark)):
        return ""
    return (
        "No correct fix has reached L3 yet: the tests rarely guard a fix strongly enough, and"
        " the behaviour diff rarely finishes. "
    )


def _hours(seconds: int) -> str:
    hours = seconds / 3600
    return f"{hours:g} hour" + ("" if hours == 1 else "s")


def fields(data: Path | None = None) -> dict[str, str]:
    """Every hole the Benchmark page fills."""
    gates, benchmark, found = load(data)
    method = benchmark["method"]
    names = slices(benchmark)
    n_wrong, wrong_items = misses(found, "wrong_fix_reached_l2")
    n_false, false_items = misses(found, "false_alarm")
    reports = " · ".join(
        f'<a href="{GITHUB}benchmarks/results/{n}/report.md">{e(slice_label(gates, n))} report</a>'
        for n in names
    )
    return {
        "gates_total": str(len(gates["gates"])),
        "gates_holding": str(gates["holding"]),
        "gate_cards": gate_cards(gates),
        "standing": e(standing(gates, benchmark)),
        "results_table": results_table(gates, benchmark),
        "funnels": "\n".join(funnel(gates, benchmark, n) for n in names),
        "level_tables": "\n".join(level_table(gates, benchmark, n) for n in names),
        "slice_switch": slice_switch(gates, benchmark),
        "miss_slices": "".join(
            f'<button type="button" class="chip" data-miss-slice="{n}" aria-pressed="false">'
            f"{e(slice_label(gates, n))}</button>"
            for n in names
        ),
        "misses_total": str(n_wrong + n_false),
        "misses_wrong_count": str(n_wrong),
        "misses_wrong": wrong_items,
        "misses_false_count": str(n_false),
        "misses_false": false_items,
        "per_repo": str(method["per_repo"]),
        "suite_cap": f"{method['suite_cap_s']} s",
        "verify_timeout": _hours(method["verify_timeout_s"]),
        "ladder_note": ladder_note(benchmark),
        "reports": reports,
    }

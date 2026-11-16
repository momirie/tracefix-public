"""Write the website's data (docs/landing/_data/*.json) from the repo's own records.

The site rule (docs/plans/website-pages.md): every number on every page comes from the repo,
never typed into a page. This script is where the numbers come from:

- `gates.json`: the release gate table in docs/ROADMAP.md, row by row.
- `benchmark.json`: each slice's headline sections from its committed summary.json, and the
  harness limits the method names (`method`: from `scripts/bench/`'s own constants).
- `benchmark.json`'s `own_mistake` per slice: how many of the counterexamples on wrong agent fixes
  rest on what the agent got wrong, as docs/BENCHMARK.md's reading of that slice says (a person
  read each receipt against gold; summary.json can't say it). Checked against summary.json's count.
- `misses.json`: the runs the benchmark counts against Tracefix: wrong agent fixes that still
  reached L2 or above, and correct fixes given a COUNTEREXAMPLE the developer labelled a false
  alarm. Read with the benchmark report's own rules (`bench.report.judged_runs`), and checked
  against summary.json's counts.

`tests/test_site_data.py` fails when the committed files differ from a fresh run.

    uv run python scripts/site_data.py          # write docs/landing/_data/
    uv run python scripts/site_data.py --check  # exit 1 if a committed file is out of date
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import benchmark
from bench import choose, data, prepare, report, run

from tracefix.ladder import EvidenceLevel, rank

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "benchmarks"
ROADMAP = ROOT / "docs" / "ROADMAP.md"
BENCHMARK_MD = ROOT / "docs" / "BENCHMARK.md"
OUT = ROOT / "docs" / "landing" / "_data"
SLICES = ("slice1", "slice2")
# The summary.json sections the pages may show; a slice has only those its kinds produce.
SECTIONS = (
    "funnel", "splits", "set_aside", "gold", "partial", "agent_wrong", "agent_ok",
    "correct_fixes", "cost_and_time", "stability",
)  # fmt: skip
# A gate's status starts with one of these words. Any other word stops the script: whether a
# gate holds is the developer's call, never a guess from free text.
STATUSES = ("Open", "Holds")

Json = dict[str, Any]


class SiteDataError(Exception):
    """A source the site reads from is not in the shape this script expects."""


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def gates(roadmap: str) -> Json:
    """The release gate table: its column names and one entry per gate."""
    section = roadmap.split("\n## Release gate\n", 1)
    if len(section) != 2:
        raise SiteDataError("docs/ROADMAP.md has no '## Release gate' section")
    rows = [line for line in section[1].split("\n## ", 1)[0].splitlines() if line.startswith("|")]
    if len(rows) < 3:
        raise SiteDataError("the release gate table has no rows")
    columns = _cells(rows[0])
    if columns[:2] != ["#", "Gate"] or columns[-2:] != ["Target", "Status"]:
        raise SiteDataError(f"unexpected release gate columns: {columns}")
    out = []
    for line in rows[2:]:
        cells = _cells(line)
        if len(cells) != len(columns):
            raise SiteDataError(f"release gate row has {len(cells)} cells: {line}")
        title = re.fullmatch(r"\*\*(.+?)\*\*:\s*(.+)", cells[1])
        if title is None:
            raise SiteDataError(f"gate {cells[0]}: expected '**Title**: what is measured'")
        status = cells[-1]
        word = status.split(" ", 1)[0]
        if word not in STATUSES:
            raise SiteDataError(
                f"gate {cells[0]}: status {status!r} starts with none of {STATUSES}"
            )
        out.append({
            "number": int(cells[0]),
            "title": title.group(1),
            "measures": title.group(2),
            "results": dict(zip(columns[2:-2], cells[2:-2], strict=True)),
            "target": cells[-2],
            "status": status,
            "holds": word == "Holds",
        })  # fmt: skip
    return {"columns": columns, "gates": out, "holding": sum(g["holds"] for g in out)}


def method() -> Json:
    """The limits the benchmark's method states, read from the harness that applies them."""
    return {
        "per_repo": choose.PER_REPO,
        "suite_cap_s": prepare.SUITE_CAP_S,
        "verify_timeout_s": prepare.VERIFY_TIMEOUT_S,
    }


# Markdown wraps lines anywhere, so any run of whitespace between the words matches.
_READING = r"caught only (\d+), and by our own runs only (\d+) of those (\d+) rests on what"
_OWN_MISTAKE = re.compile(re.sub(r" +", r"\\s+", _READING))


def own_mistake(benchmark_md: str, slice_name: str, sections: Json) -> Json | None:
    """The slice's reading in docs/BENCHMARK.md: of the wrong agent fixes given a counterexample,
    how many rest on the agent's own mistake. None for a slice with no wrong agent fixes."""
    if "agent_wrong" not in sections:
        return None
    number = slice_name.removeprefix("slice")
    parts = re.split(rf"^## Results: slice {number}\b.*$", benchmark_md, maxsplit=1, flags=re.M)
    if len(parts) != 2:
        raise SiteDataError(f"docs/BENCHMARK.md has no '## Results: slice {number}' section")
    section = parts[1].split("\n## ", 1)[0]
    found = _OWN_MISTAKE.search(section)
    if found is None:
        raise SiteDataError(f"slice {number}: no 'only N of those M rests on' in BENCHMARK.md")
    caught, n, of = (int(g) for g in found.groups())
    want = sections["agent_wrong"]["detection"]["n"]
    if caught != want or of != want:
        raise SiteDataError(
            f"slice {number}: BENCHMARK.md reads {n} of {of} (caught {caught}), "
            f"summary.json counts {want} counterexamples on wrong agent fixes"
        )
    return {"n": n, "of": of}


def summary(slice_name: str) -> Json:
    path = BENCH / "results" / slice_name / "summary.json"
    found: Json = json.loads(path.read_text(encoding="ascii"))
    return {key: found[key] for key in SECTIONS if key in found}


def _receipt_path(slice_name: str, line: run.RunLine) -> str:
    assert line.receipt is not None
    return f"benchmarks/results/{slice_name}/{line.receipt}/receipt.md"


def _notes(
    found: report.Run, labels: Mapping[report.Key, report.FindingLabel], label: str
) -> list[str]:
    return [
        lab.note
        for (iid, tag, _), lab in sorted(labels.items())
        if (iid, tag) == (found.line.instance_id, found.line.tag)
        and lab.label == label and lab.by == "developer"
    ]  # fmt: skip


def misses(slice_name: str) -> list[Json]:
    """The slice's counted runs that went against Tracefix, with their receipts."""
    cases = data.read_cases(BENCH / "cases" / f"{slice_name}.jsonl")
    lines, receipts = benchmark.runs_with_receipts(run.Results(BENCH / "results" / slice_name))
    labels = benchmark.read_labels(BENCH / "labels" / f"{slice_name}.json")
    by_key = {lab.key: lab for lab in labels.labels if lab.label is not None}
    _, first, aside = report.judged_runs(cases, lines, receipts)
    out = []
    for found in (r for r in first if r not in aside):
        assert found.receipt is not None
        kind, level = found.line.kind, found.receipt.level
        if kind in report.CORRECT and report.is_false_alarm(found, by_key):
            why, notes = "false_alarm", _notes(found, by_key, "false_alarm")
        elif kind == "agent_wrong" and rank(level) >= rank(EvidenceLevel.L2):
            why, notes = "wrong_fix_reached_l2", []
        else:
            continue
        out.append({
            "slice": slice_name, "instance_id": found.line.instance_id, "run": found.line.tag,
            "kind": kind, "level": level.value, "why": why,
            "receipt": _receipt_path(slice_name, found.line), "notes": notes,
        })  # fmt: skip
    return out


def _check_counts(slice_name: str, found: list[Json], sections: Json) -> None:
    """The misses must be exactly the runs summary.json counts, or the pages would disagree."""
    # Slice 1 has only gold among the correct fixes; later slices sum them in `correct_fixes`.
    fixes: Json = sections["correct_fixes"] if "correct_fixes" in sections else sections["gold"]
    correct = fixes["false_alarm"]["n"]
    wrong = sections.get("agent_wrong", {}).get("false_pass_l2", {}).get("n", 0)
    got = {
        why: sum(m["why"] == why for m in found) for why in ("false_alarm", "wrong_fix_reached_l2")
    }
    if got != {"false_alarm": correct, "wrong_fix_reached_l2": wrong}:
        raise SiteDataError(
            f"{slice_name}: misses {got} differ from summary.json "
            f"(false alarms {correct}, wrong fixes at L2+ {wrong})"
        )


def files() -> dict[str, str]:
    """Every data file's name and its exact text."""
    benchmarks: Json = {"method": method()}
    found: list[Json] = []
    reading = BENCHMARK_MD.read_text(encoding="utf-8")
    for name in SLICES:
        sections = summary(name)
        mistake = own_mistake(reading, name, sections)
        if mistake is not None:
            sections["own_mistake"] = mistake
        slice_misses = misses(name)
        _check_counts(name, slice_misses, sections)
        benchmarks[name] = sections
        found += slice_misses
    content = {
        "gates.json": gates(ROADMAP.read_text(encoding="utf-8")),
        "benchmark.json": benchmarks,
        "misses.json": {"misses": found},
    }
    return {
        name: json.dumps(value, indent=1, ensure_ascii=True) + "\n"
        for name, value in content.items()
    }


def stale(out: Path | None = None) -> list[str]:
    out = out or OUT
    return [
        name
        for name, text in files().items()
        if not (out / name).is_file() or (out / name).read_text(encoding="ascii") != text
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="only report out-of-date files")
    args = parser.parse_args(argv)
    try:
        if args.check:
            bad = stale()
            for name in bad:
                print(f"out of date: docs/landing/_data/{name} (run scripts/site_data.py)")
            return 1 if bad else 0
        OUT.mkdir(parents=True, exist_ok=True)
        for name, text in files().items():
            (OUT / name).write_text(text, encoding="ascii", newline="\n")
            print(f"wrote {OUT / name}")
    except SiteDataError as exc:
        print(f"site_data: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

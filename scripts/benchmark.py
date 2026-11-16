"""The M10 benchmark harness (docs/plans/M10.md, docs/BENCHMARK.md later).

    uv run python scripts/benchmark.py select             # the pinned rows -> slice1 cases
    uv run python scripts/benchmark.py select --limit 10  # a prefix of the same order
    uv run python scripts/benchmark.py select --repin     # pin the current revision
    uv run python scripts/benchmark.py select --slice slice2 --limit 200  # agent patches too

    uv run python scripts/benchmark.py prepare --limit 3  # the first 3 cases, in Docker

    uv run python scripts/benchmark.py run                       # replay recorded answers
    uv run python scripts/benchmark.py run --live --max-spend 5  # call the model API
    uv run python scripts/benchmark.py reclassify                # today's rules on old lines
    uv run python scripts/benchmark.py label                     # findings to review
    uv run python scripts/benchmark.py report                    # report.md, summary.json

`select` reads the pinned SWE-rebench rows (downloading them into benchmarks/cache/ once),
parses every row strictly, applies the metadata rules and writes:
- benchmarks/cases/<slice>.jsonl: the chosen tasks in rank order, with their split;
- benchmarks/cases/<slice>.funnel.json: every row left out, with its reason, and the counts.
Slice 1 reads the leaderboard (Python 3.11+). Slice 2 reads SWE-rebench (Python 3.9-3.13) and,
for each task that could be chosen, its OpenHands runs (bench.agents, extracted once by
scripts/extract_agents.py); a case keeps at most one agent run the hidden tests fail and one
they pass.

`prepare` runs each case's checks in a container from its image (Docker Desktop must be
running) and writes benchmarks/prepared/<slice>/<instance id>.json: excluded with a reason, or
ready with its kept partial-fix variant. A case already prepared is skipped, and an excluded
case's image is removed. `--split dev` prepares one split only (of the first `--limit` cases).
Requests, results and logs stay in benchmarks/work/ (not committed).

`run` verifies each ready case's gold and partial fix in a fresh container (bench.run), appends
one line per run to benchmarks/results/<slice>/runs.jsonl beside the receipts, and resumes where
it stopped. `--live` calls the model API and records its answers in benchmarks/recordings/;
the spend guard starts no run that could pass `--max-spend`. Without `--live` the recorded
answers are replayed, with no network. A task's image is removed after its last run. One `run`
(or `reclassify`) at a time per slice: a lock in benchmarks/work/<slice>/ refuses a second.

M11's A/B options: `--results NAME` keeps a result set apart (results, recordings, work and
labels under <slice>-<NAME>; `report`, `label` and `reclassify` take it too), `--split dev`
runs one split only, `--issue title` shows Tracefix only the issue's first non-empty line (the
thin arm; one arm per result set), and `--adversary-live --max-spend X` calls the model API for
the adversary only: every other role replays the anchor's recordings (`--anchor NAME`, default
the slice's own) and goes live only where none was recorded. `--anchored --max-spend X` replays
every role's answer to an identical request and goes live only on a new request; the ceiling then
counts only the cost of the recordings a run adds, not its receipt's estimate, which includes the
calls replayed. Every run line records its issue
arm, its mode and the sha256 of the wheel it ran. `compare --a NAME --b NAME` writes
compare-<A>.json and .md into B's folder: the units both ran (task, kind, repeat), B's wins and
losses on wrong fixes with a one-sided exact sign test, each arm's false alarms, and why each
wrong fix's leftover was missed (bench.report.miss_cause). Without --b (or --a) a set is the
slice's own, so `compare --slice slice2` lists slice 2's misses.

    uv run python scripts/benchmark.py run --split dev --results m11-a \
        --adversary-live --max-spend 8
    uv run python scripts/benchmark.py report --results m11-a

`reclassify` applies today's outcome rules (bench.run.classify) to the runs already written and
appends a line for each run whose outcome they change, so runs.jsonl stays code-written.

`label` adds an empty entry to benchmarks/labels/<slice>.json for each finding a person must
judge and lists the entries that count nowhere; `report` writes report.md and summary.json from
the committed files (bench.report).

`siblings` (M11 S0) checks each fix of the ready dev tasks statically, with no model and no
Docker: is the code it replaced still elsewhere, does a changed function have an untouched
namesake, does its test read a value the fix assigns (bench.siblings). It fetches each base
commit from GitHub into benchmarks/work/ and writes benchmarks/results/sibling-sites/.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from bench import agents, box, choose, data, prepare, report, run, siblings
from pydantic import ValidationError

from tracefix.receipt import Receipt

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks"
WORKERS = 2  # boxes at once: Docker Desktop has ~15.6 GB here, and each box may use 8 GB


TASKS = {"slice1": data.LEADERBOARD, "slice2": data.REBENCH}  # each slice's task dataset
RESULTS_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")  # a folder name, never a path
RESULTS_HELP = "a result set of its own: results, recordings, work and labels under <slice>-NAME"


def named(slice_name: str, results: str | None) -> str:
    """A result set's folder name: the slice's own, or `<slice>-<NAME>` (`--results NAME`)."""
    if results is None:
        return slice_name
    if not RESULTS_NAME.match(results):
        raise data.DataError(f"--results/--anchor {results!r}: use a-z, 0-9, '-' and '_' only")
    return f"{slice_name}-{results}"


def select(
    bench: Path,
    slice_name: str,
    limit: int,
    repin: bool,
    get: data.Get = data.patient_get,
) -> dict[str, object]:
    if slice_name not in choose.SLICES:
        raise data.DataError(f"no selection rules for {slice_name} (known: {', '.join(TASKS)})")
    rules, dataset = choose.SLICES[slice_name], TASKS[slice_name]
    sources, cache = bench / "sources.json", bench / "cache"
    if repin:
        source = data.repin(dataset, cache, get)
        data.write_source(sources, dataset, source)
    source = data.read_source(sources, dataset)
    rows = data.load_rows(dataset, source, cache, get)
    tasks: list[data.Task] = []
    excluded: list[choose.Excluded] = []
    for raw in rows:
        row = int(raw["row_idx"])
        try:
            task = data.parse_row(raw, source.revision)
        except data.InvalidRow as exc:
            excluded.append(choose.Excluded(row, None, choose.Reason.INVALID, str(exc)))
            continue
        why = choose.check(task, rules)
        if why is None:
            tasks.append(task)
        else:
            excluded.append(choose.Excluded(row, task.instance_id, why))
    picks: dict[str, tuple[data.AgentRun, ...]] = {}
    pin = agents.read_pin(sources) if rules.agents else None
    admit = None if pin is None else agent_rule(slice_name, agents.load(pin, cache), picks)
    chosen, left = choose.sample(tasks, slice_name, limit, admit=admit)
    excluded += left
    cases = [
        data.Case(slice=slice_name, rank=i, split=choose.split(t.instance_id), task=t,
                  agents=picks.get(t.instance_id, ()))
        for i, t in enumerate(chosen)
    ]  # fmt: skip
    data.write_cases(bench / "cases" / f"{slice_name}.jsonl", cases)
    summary = choose.funnel(len(rows), excluded, len(cases))
    summary["splits"] = {s: sum(c.split == s for c in cases) for s in ("dev", "held_out")}
    if pin is not None:
        summary["by_python"] = by_python(tasks, cases)
    funnel = {
        "source": source.model_dump(),
        **({} if pin is None else {"agents_source": pin.model_dump()}),
        "slice": slice_name,
        "limit": limit,
        **summary,
        "rows": [
            {
                "row": e.row,
                "instance_id": e.instance_id,
                "reason": e.reason.value,
                "detail": e.detail,
            }
            for e in sorted(excluded, key=lambda e: e.row)
        ],
    }
    text = json.dumps(funnel, indent=1, ensure_ascii=True) + "\n"
    (bench / "cases" / f"{slice_name}.funnel.json").write_text(text, "ascii", newline="\n")
    return summary


def agent_rule(
    slice_name: str, runs: agents.Runs, picks: dict[str, tuple[data.AgentRun, ...]]
) -> Callable[[data.Task], choose.Reason | None]:
    """Slice 2's last rule: the task needs a usable agent run; the runs chosen go to `picks`."""

    def admit(task: data.Task) -> choose.Reason | None:
        found = runs(task.instance_id)
        if not found.runs:
            return choose.Reason.NO_AGENT_RUNS
        chosen = choose.pick_agents(slice_name, found.runs)
        if not chosen:
            return choose.Reason.NO_AGENT_PATCH
        picks[task.instance_id] = chosen
        return None

    return admit


def by_python(eligible: list[data.Task], cases: list[data.Case]) -> dict[str, dict[str, int]]:
    """Per project Python: tasks past the metadata rules, tasks chosen, and how many of those
    have an agent run the hidden tests fail (agent_wrong), pass (agent_ok), or one of each."""
    counts: dict[str, Counter[str]] = {}
    for task in eligible:
        counts.setdefault(_minor(task), Counter())["eligible"] += 1
    for case in cases:
        kinds = {run.resolved for run in case.agents}
        count = counts.setdefault(_minor(case.task), Counter())
        count["chosen"] += 1
        count["agent_wrong"] += False in kinds
        count["agent_ok"] += True in kinds
        count["both"] += kinds == {False, True}
    keys = ("eligible", "chosen", "agent_wrong", "agent_ok", "both")
    ordered = sorted(counts, key=lambda v: tuple(int(p) for p in v.split(".")))
    return {v: {k: counts[v][k] for k in keys} for v in ordered}


def _minor(task: data.Task) -> str:
    major, minor = task.python_version
    return f"{major}.{minor}"


def build_wheel(folder: Path) -> Path:
    """Tracefix's wheel, as it is now, for installing into each box, and beside it uv.lock's
    versions of its dependencies (box.PINS: a box below Python 3.11 installs from those)."""
    if folder.exists():
        for old in folder.glob("*.whl"):
            old.unlink()
    command = ["uv", "build", "--wheel", "--quiet", "--out-dir", str(folder)]
    subprocess.run(command, cwd=ROOT, check=True)
    pins = ["uv", "export", "--frozen", "--no-dev", "--no-hashes", "--no-emit-project",
            "--quiet", "--output-file", str(folder / box.PINS)]  # fmt: skip
    subprocess.run(pins, cwd=ROOT, check=True)
    [wheel] = folder.glob("tracefix-*.whl")
    return wheel


def to_prepare(cases: list[data.Case], limit: int, split: str | None) -> list[data.Case]:
    """The first `limit` cases in rank order, then only those of `split` (dev or held_out;
    None: both), the way `run --limit --split` picks them."""
    return [c for c in cases[:limit] if split is None or c.split == split]


def prepare_cases(
    bench: Path, slice_name: str, limit: int, keep_images: bool = False,
    split: str | None = None,
) -> dict[str, int]:  # fmt: skip
    """Prepare the slice's first `limit` cases (of `split` only, if given), one container at a
    time; counts per outcome. An excluded task's image is removed (no later step needs it)
    unless `keep_images`."""
    cases = to_prepare(data.read_cases(bench / "cases" / f"{slice_name}.jsonl"), limit, split)
    folder = bench / "prepared" / slice_name
    folder.mkdir(parents=True, exist_ok=True)
    wheel = build_wheel(bench / "work" / "wheel")
    counts: Counter[str] = Counter()
    for case in cases:
        task = case.task
        path = folder / f"{task.instance_id}.json"
        if path.exists():
            counts["already prepared"] += 1
            continue
        print(f"prepare {task.instance_id}", file=sys.stderr, flush=True)
        scratch = bench / "work" / slice_name / task.instance_id
        scratch.mkdir(parents=True, exist_ok=True)
        docker_box = box.DockerBox(task.image, box.container_name(task.instance_id))
        try:
            docker_box.start()
            done = prepare.prepare(
                prepare.Session(docker_box, scratch), task, wheel, agents=case.agents
            )
        except box.BoxError as exc:
            failed = prepare.Reason.HARNESS_ERROR
            done = prepare.Prepared(instance_id=task.instance_id, excluded=failed, detail=str(exc))
        finally:
            docker_box.close()
        path.write_text(done.model_dump_json(indent=1) + "\n", "utf-8", newline="\n")
        outcome = done.excluded.value if done.excluded else "ready"
        counts[outcome] += 1
        print(f"  {outcome} {done.detail} ({done.seconds:.0f}s)", file=sys.stderr, flush=True)
        if done.excluded is not None and not keep_images:
            box.remove_image(task.image)
    return dict(counts)


def read_prepared(folder: Path) -> dict[str, prepare.Prepared]:
    records = (prepare.Prepared.model_validate_json(p.read_text(encoding="utf-8"))
               for p in sorted(folder.glob("*.json")))  # fmt: skip
    return {r.instance_id: r for r in records}


def docker_box(task: data.Task) -> box.Box:
    """A started container for one task's runs (removed again if it couldn't start)."""
    started = box.DockerBox(task.image, box.container_name(task.instance_id) + "-run")
    try:
        started.start()
    except box.BoxError:
        started.close()
        raise
    return started


@dataclass(frozen=True)
class Options:
    """`run`'s M11 options; the defaults run as before M11 (replayed, both splits, the whole
    issue, the slice's own result set)."""

    mode: prepare.Mode = "replay"
    results: str | None = None  # --results NAME: the result set <slice>-<NAME>
    split: str | None = None  # dev or held_out; None: both
    issue: run.IssueArm = "full"
    anchor: str | None = None  # adversary_live, anchored: whose recordings are replayed


DEFAULTS = Options()


def run_cases(
    bench: Path, slice_name: str, limit: int | None, *, repeats: int, workers: int,
    max_spend: float | None, reserve: float, keep_images: bool, options: Options = DEFAULTS,
) -> dict[str, object]:  # fmt: skip
    """Every ready case's runs not done yet; live (model API) in a live mode, which needs
    `max_spend`."""
    if (options.mode != "replay") != (max_spend is not None):
        raise data.DataError("a live mode and a spend ceiling go together")
    with locked(bench, named(slice_name, options.results)):
        return _run_cases(bench, slice_name, limit, repeats=repeats, workers=workers,
                          max_spend=max_spend, reserve=reserve, keep_images=keep_images,
                          options=options)  # fmt: skip


def locked(bench: Path, name: str) -> contextlib.AbstractContextManager[None]:
    return run.only_one(bench / "work" / name / run.LOCK)


def anchor_folder(bench: Path, slice_name: str, options: Options) -> Path | None:
    """adversary_live's or anchored's anchor recordings; None in any other mode. Its own result
    set is required (slice results stay as committed) and must not be its own anchor."""
    if options.mode not in ("adversary_live", "anchored"):
        return None
    if options.results is None:
        flag = options.mode.replace("_", "-")
        raise data.DataError(f"--{flag} needs --results NAME: a result set of its own")
    if options.anchor == options.results:
        raise data.DataError("--anchor must name another result set than --results")
    folder = bench / "recordings" / named(slice_name, options.anchor)
    if not folder.is_dir():
        raise data.DataError(f"no anchor recordings at {folder}")
    return folder


def check_arm(lines: Sequence[run.RunLine], issue: run.IssueArm, wheel: str) -> None:
    """One issue arm per result set: its run keys don't say the arm. A different wheel than
    earlier lines' is only noted (each line records its own)."""
    other = sorted({line.issue for line in lines} - {issue})
    if other:
        raise data.DataError(f"this result set holds runs with --issue {other[0]}; use "
                             f"another --results NAME for --issue {issue}")  # fmt: skip
    wheels = {line.wheel for line in lines if line.wheel is not None}
    if wheels - {wheel}:
        print("benchmark: note: earlier runs in this result set ran another wheel",
              file=sys.stderr, flush=True)  # fmt: skip


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_cases(
    bench: Path, slice_name: str, limit: int | None, *, repeats: int, workers: int,
    max_spend: float | None, reserve: float, keep_images: bool, options: Options,
) -> dict[str, object]:  # fmt: skip
    name = named(slice_name, options.results)
    cases = data.read_cases(bench / "cases" / f"{slice_name}.jsonl")[:limit]
    results = run.Results(bench / "results" / name)
    lines = results.lines()
    anchor = anchor_folder(bench, slice_name, options)
    wheel = build_wheel(bench / "work" / "wheel")
    wheel_sha = sha256(wheel)
    check_arm(lines, options.issue, wheel_sha)
    guard = run.free() if max_spend is None else run.live_guard(lines, max_spend, reserve)
    if max_spend is not None and (warning := run.reserve_warning(guard)) is not None:
        print(f"benchmark: note: {warning}", file=sys.stderr, flush=True)
    prepared = read_prepared(bench / "prepared" / slice_name)
    jobs = run.plan(cases, prepared, lines, repeats, split=options.split)
    pool = run.Pool(
        results=results, recordings=bench / "recordings" / name, work=bench / "work" / name,
        wheel=wheel, mode=options.mode, guard=guard, make_box=docker_box,
        remove_image=None if keep_images else box.remove_image, issue=options.issue,
        wheel_sha256=wheel_sha, anchor=anchor,
    )  # fmt: skip
    counts: dict[str, object] = dict(run.run_all(jobs, pool, workers))
    if max_spend is not None:
        counts |= {"spent_usd": round(guard.spent, 2), "ceiling_usd": max_spend}
    return counts


def runs_with_receipts(
    results: run.Results,
) -> tuple[list[run.RunLine], dict[tuple[str, str, int], Receipt | None]]:
    """Each run's last line and its receipt. A line that counts on a receipt which no longer
    parses (deleted, edited, or written before a receipt schema change) stops the report: it
    would otherwise drop out of every rate uncounted."""
    lines = results.lines()
    last = run.latest(lines)
    receipts = {key: results.receipt(line) for key, line in last.items()}
    lost = [f"{line.instance_id} {line.tag}" for key, line in sorted(last.items())
            if line.outcome == "receipt" and receipts[key] is None]  # fmt: skip
    if lost:
        raise data.DataError(f"runs.jsonl counts on receipts that can't be read: "
                             f"{', '.join(lost)}")  # fmt: skip
    return lines, receipts


def reclassify(bench: Path, slice_name: str, results: str | None = None) -> dict[str, int]:
    """Today's outcome rules on the runs already written (bench.run.reclassify)."""
    name = named(slice_name, results)
    with locked(bench, name):
        return run.reclassify(run.Results(bench / "results" / name))


def refuse_stale(lines: list[run.RunLine], prepared: dict[str, prepare.Prepared]) -> None:
    """A run of a partial fix prepare no longer keeps counts nowhere; `run` does it again."""
    found = [f"{line.instance_id} {line.tag}" for line in run.stale(lines, prepared)]
    if found:
        raise data.DataError(f"runs.jsonl has runs of variants prepare no longer keeps (run "
                             f"them again): {', '.join(sorted(found))}")  # fmt: skip


def read_labels(path: Path) -> report.Labels:
    if not path.is_file():
        return report.Labels()
    try:
        return report.Labels.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise data.DataError(f"{path.name}: {exc}") from None


def write_report(
    bench: Path, slice_name: str, results_name: str | None = None
) -> dict[str, object]:
    """summary.json and report.md in the result set's folder, from committed files only."""
    name = named(slice_name, results_name)
    cases = data.read_cases(bench / "cases" / f"{slice_name}.jsonl")
    results = run.Results(bench / "results" / name)
    lines, receipts = runs_with_receipts(results)
    labels = read_labels(bench / "labels" / f"{name}.json")
    prepared = read_prepared(bench / "prepared" / slice_name)
    refuse_stale(lines, prepared)
    summary = report.summarise(cases, prepared, lines, receipts, labels, run.RESERVE_USD)
    results.folder.mkdir(parents=True, exist_ok=True)
    text = json.dumps(summary, indent=1, ensure_ascii=True) + "\n"
    # "\n" on every OS: the files are rebuilt byte for byte (N1, verifier round 1)
    (results.folder / "summary.json").write_text(text, "ascii", newline="\n")
    title = f"Tracefix benchmark: {name}"
    md = report.markdown(summary, title)
    (results.folder / "report.md").write_text(md, "utf-8", newline="\n")
    return {"runs": len(run.latest(lines)), "findings": len(summary["findings"])}


def add_labels(bench: Path, slice_name: str, results_name: str | None = None) -> dict[str, object]:
    """An empty entry in labels/<set>.json for each finding that needs a person's review."""
    name = named(slice_name, results_name)
    results = run.Results(bench / "results" / name)
    lines, receipts = runs_with_receipts(results)
    path = bench / "labels" / f"{name}.json"
    labels = read_labels(path)
    runs = [report.Run(line, receipts.get(key)) for key, line in run.latest(lines).items()]
    updated = report.with_missing(labels, runs)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated.model_dump_json(indent=1) + "\n", "utf-8", newline="\n")
    empty = sum(label.label is None for label in updated.labels)
    return {"labels": len(updated.labels), "added": len(updated.labels) - len(labels.labels),
            "unlabelled": empty, "count_nowhere": report.orphaned(updated, runs)}  # fmt: skip


def result_set(
    bench: Path, name: str, prepared: dict[str, prepare.Prepared], tasks: set[str]
) -> tuple[list[report.Run], report.Labels]:
    """One result set's runs (each run's last line, of the slice's cases) and its labels. A set
    with no runs.jsonl is refused: a mistyped name would otherwise be compared as no runs."""
    results = run.Results(bench / "results" / name)
    if not results.path.is_file():
        raise data.DataError(f"{name}: no runs.jsonl in {results.folder.name}/ (check --a/--b)")
    lines, receipts = runs_with_receipts(results)
    refuse_stale(lines, prepared)
    runs = [report.Run(line, receipts.get(key)) for key, line in sorted(run.latest(lines).items())
            if line.instance_id in tasks]  # fmt: skip
    return runs, read_labels(bench / "labels" / f"{name}.json")


def write_compare(bench: Path, slice_name: str, a: str | None, b: str | None) -> dict[str, object]:
    """Result set B against A (each the slice's own when not named): compare-<A>.json and .md in
    B's folder, from committed files only (bench.report.compare_by_split)."""
    a_name, b_name = named(slice_name, a), named(slice_name, b)
    cases = data.read_cases(bench / "cases" / f"{slice_name}.jsonl")
    prepared = read_prepared(bench / "prepared" / slice_name)
    tasks = {c.task.instance_id for c in cases}
    a_runs, a_labels = result_set(bench, a_name, prepared, tasks)
    b_runs, b_labels = result_set(bench, b_name, prepared, tasks)
    summary = report.compare_by_split(cases, a_runs, b_runs, prepared, a_labels, b_labels)
    summary["all"]["live_spend_usd"] = {
        arm: round(run.spent(run.Results(bench / "results" / name).lines(), run.RESERVE_USD), 2)
        for arm, name in (("a", a_name), ("b", b_name))
    }
    folder = bench / "results" / b_name
    folder.mkdir(parents=True, exist_ok=True)
    text = json.dumps(summary, indent=1, ensure_ascii=True) + "\n"
    (folder / f"compare-{a_name}.json").write_text(text, "ascii", newline="\n")
    md = report.compare_markdown(summary, f"Tracefix benchmark: {b_name} against {a_name}")
    (folder / f"compare-{a_name}.md").write_text(md + "\n", "utf-8", newline="\n")
    found = summary["all"]
    return {"pairs": found["pairs"], "sign_test_p": found["wrong_fixes"]["sign_test_p"]}


def command(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "prepare":
        return dict(prepare_cases(BENCH, args.slice, args.limit, args.keep_images, args.split))
    if args.command == "run":
        mode: prepare.Mode = "replay"
        if args.live or args.adversary_live or args.anchored:
            mode = "live" if args.live else "adversary_live" if args.adversary_live else "anchored"
        options = Options(mode=mode, results=args.results, split=args.split, issue=args.issue,
                          anchor=args.anchor)  # fmt: skip
        return run_cases(BENCH, args.slice, args.limit, repeats=args.repeats,
                         workers=args.workers, max_spend=args.max_spend, reserve=args.reserve,
                         keep_images=args.keep_images, options=options)  # fmt: skip
    if args.command == "report":
        return write_report(BENCH, args.slice, args.results)
    if args.command == "compare":
        return write_compare(BENCH, args.slice, args.a, args.b)
    if args.command == "label":
        return add_labels(BENCH, args.slice, args.results)
    if args.command == "reclassify":
        return dict(reclassify(BENCH, args.slice, args.results))
    if args.command == "siblings":
        return siblings.measure(BENCH, args.slice or ["slice1", "slice2"], args.split, args.limit)
    return select(BENCH, args.slice, args.limit, args.repin)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="benchmark.py", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    pick = commands.add_parser("select", help="choose a slice's tasks from the pinned rows")
    pick.add_argument("--slice", default="slice1", help="slice name (default: slice1)")
    pick.add_argument("--limit", type=int, default=60, help="tasks to choose (default: 60)")
    pick.add_argument("--repin", action="store_true", help="pin the dataset's current revision")
    ready = commands.add_parser("prepare", help="run each case's checks in its container")
    ready.add_argument("--slice", default="slice1", help="slice name (default: slice1)")
    ready.add_argument("--limit", type=int, required=True, help="cases to prepare, in rank order")
    ready.add_argument("--keep-images", action="store_true", help="keep excluded tasks' images")
    ready.add_argument("--split", choices=("dev", "held_out"), help="only this split (both)")
    go = commands.add_parser("run", help="verify every ready case (gold and partial fix)")
    go.add_argument("--slice", default="slice1", help="slice name (default: slice1)")
    go.add_argument("--limit", type=int, default=None, help="only the first N cases, in rank order")
    go.add_argument("--repeats", type=int, default=1, help="runs per fix (default: 1)")
    go.add_argument("--workers", type=int, default=WORKERS, help=f"boxes at once ({WORKERS})")
    live = go.add_mutually_exclusive_group()
    live.add_argument("--live", action="store_true", help="call the model API (needs --max-spend)")
    live.add_argument("--adversary-live", action="store_true",
                      help="call the model API for the adversary only; the other roles replay "
                           "the anchor's recordings (needs --max-spend and --results)")  # fmt: skip
    live.add_argument("--anchored", action="store_true",
                      help="replay the anchor's answer to an identical request, call the model "
                           "API only on a new one; the ceiling counts those calls only (needs "
                           "--max-spend and --results)")  # fmt: skip
    go.add_argument("--max-spend", type=float, help="the live runs' ceiling in US dollars")
    go.add_argument("--reserve", type=float, default=run.RESERVE_USD,
                    help=f"US dollars held back per live run in flight ({run.RESERVE_USD}); "
                         "never below the dearest run seen")  # fmt: skip
    go.add_argument("--keep-images", action="store_true", help="keep images after a task's runs")
    go.add_argument("--split", choices=("dev", "held_out"), help="only this split (default: both)")
    go.add_argument(
        "--issue",
        choices=("full", "title"),
        default="full",
        help="the issue Tracefix sees: all of it, or its first non-empty line",
    )
    go.add_argument("--anchor", metavar="NAME",
                    help="--adversary-live and --anchored replay the result set <slice>-NAME's "
                         "recordings (default: the slice's own)")  # fmt: skip
    go.add_argument("--results", metavar="NAME", help=RESULTS_HELP)
    for name, text in (
        ("report", "write report.md and summary.json from the results"),
        ("label", "add an empty label for each finding that needs review"),
        ("reclassify", "apply today's outcome rules to the runs already written"),
    ):
        sub = commands.add_parser(name, help=text)
        sub.add_argument("--slice", default="slice1", help="slice name (default: slice1)")
        sub.add_argument("--results", metavar="NAME", help=RESULTS_HELP)
    near = commands.add_parser("siblings", help="M11 S0: static sibling-site checks of each fix")
    near.add_argument("--slice", action="append", help="a slice (repeat it; default: both)")
    near.add_argument("--split", choices=("dev", "held_out"), default="dev",
                      help="the split to measure (default: dev)")  # fmt: skip
    near.add_argument("--limit", type=int, default=None, help="only the first N cases per slice")
    versus = commands.add_parser("compare", help="result set B against A: pairs, sign test, misses")
    versus.add_argument("--slice", default="slice1", help="slice name (default: slice1)")
    versus.add_argument("--a", metavar="NAME", help="arm A's result set (default: the slice's)")
    versus.add_argument("--b", metavar="NAME", help="arm B's result set (default: the slice's)")
    args = parser.parse_args(argv)
    live_mode = args.command == "run" and (args.live or args.adversary_live or args.anchored)
    if args.command == "run" and live_mode != (args.max_spend is not None):
        parser.error("--live (or --adversary-live, --anchored) and --max-spend go together")
    if args.command == "run" and not (math.isfinite(args.reserve) and args.reserve > 0):
        parser.error("--reserve must be a number more than 0")
    if args.command == "run" and args.max_spend is not None and not (
        math.isfinite(args.max_spend) and args.max_spend >= 0
    ):  # fmt: skip
        parser.error("--max-spend must be a number, 0 or more")
    if live_mode and not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("the live modes need ANTHROPIC_API_KEY in the environment")
    try:
        summary = command(args)
    except (data.DataError, run.Locked) as exc:
        print(f"benchmark: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

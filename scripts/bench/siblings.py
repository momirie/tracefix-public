"""M11 S0: the $0 sibling-site measurement on the slices' dev splits (docs/plans/M11.md).

For each ready dev task: the base commit is fetched from GitHub alone (`git fetch --depth 1`,
no checkout: everything reads git objects, and no code from the repo ever runs), each fix the
benchmark runs (gold, the kept partial fix, the kept agent patches) is committed on it the way
prepare commits them (`inside._Index`), and tracefix.siblings checks each one:
- replaced_code: the code a hunk replaced still exists elsewhere (block), and its looser
  single-line variant;
- same_name: a changed or added function has an untouched namesake;
- constant_reads: the reproduction test of that fix's run (committed under results/) or the
  agent's own test files read a module-level value the fix assigns.

Rates by kind go to benchmarks/results/sibling-sites/<slice>.json and .md, and every slice file
there is summed into summary.json and .md with the plan's pre-registered rule applied. No model
and no Docker; the fetches are the only network use.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from bench import inside, patches, prepare
from bench.agents import agent_patch
from bench.data import Case, read_cases
from tracefix.diffscope import DiffScope, FileKind, compute_scope
from tracefix.siblings import (
    SiblingSite,
    constant_reads,
    fix_constants,
    replaced_code,
    same_name,
)
from tracefix.workspace import WorkspaceError, blob_text, git_env, user_safe_directories

Json = dict[str, Any]
Url = Callable[[str], str]

FETCH_TIMEOUT_S = 900
GROUPS = ("gold", "partial", "agent_wrong", "agent_ok")
WRONG = ("partial", "agent_wrong")
CORRECT = ("gold", "agent_ok")
SIGNALS = ("replaced_code", "replaced_line", "same_name", "constant_reads")
RULED = ("replaced_code", "same_name")  # the plan's rule A/B; replaced_line is shown beside A
MIN_GAP = 0.15  # wrong-fix rate at least this much above the correct-fix rate
MAX_CORRECT = 0.10  # and the correct-fix rate at most this
MIN_CONSTANT_RUNS = 3


class TreeError(Exception):
    """The base commit can't be fetched; `str(exc)` says why in our own words."""


def github(repo: str) -> str:
    return f"https://github.com/{repo}.git"


def _git(tree: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    command = ["git", "-c", "core.longpaths=true"]
    for directory in user_safe_directories():
        command += ["-c", f"safe.directory={directory}"]
    return subprocess.run([*command, *args], cwd=tree, env=git_env(), stdin=subprocess.DEVNULL,
                          capture_output=True, timeout=FETCH_TIMEOUT_S)  # fmt: skip


def fetch(url: str, sha: str, tree: Path) -> None:
    """Make `tree` a bare-bones repo holding commit `sha` (kept for the next run)."""
    if (tree / ".git").is_dir() and _git(
        tree, "cat-file", "-e", f"{sha}^{{commit}}"
    ).returncode == 0:
        return
    shutil.rmtree(tree, ignore_errors=True)
    tree.mkdir(parents=True)
    try:
        for args in (("init", "--quiet", "--template="), ("config", "core.autocrlf", "false"),
                     ("fetch", "--quiet", "--depth", "1", "--no-tags", url, sha)):  # fmt: skip
            done = _git(tree, *args)
            if done.returncode != 0:
                tail = done.stderr.decode("utf-8", "replace").strip().splitlines()[-1:]
                raise TreeError(f"git {args[0]} failed: {' '.join(tail)}"[:300])
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TreeError(f"git could not run: {type(exc).__name__}") from exc
    if _git(tree, "cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
        raise TreeError("the fetch did not bring the base commit")


def fix_patches(case: Case, ready: prepare.Prepared) -> tuple[dict[str, str], list[str]]:
    """{variant: patch} for the fixes the benchmark runs on this task, and notes on any left
    out: gold, the kept partial fix (v<index>) and each kept agent patch, built as run builds
    them (bench.run)."""
    found = {"gold": case.task.patch}
    notes = []
    if ready.kept is not None:
        kept = [v for v in patches.variants(case.task.patch) if v.index == ready.kept]
        if kept:
            found[prepare.variant_kind(ready.kept)] = kept[0].patch
        else:
            notes.append("the kept variant is no longer among the patch's variants")
    runs = prepare.agent_patches(case.agents)
    for agent in ready.agents:
        run = runs.get(agent.kind)
        if not agent.kept:
            continue
        if run is None or run.source_row != agent.source_row:
            notes.append(f"the case's {agent.kind} run is not the one prepare labelled")
            continue
        found[agent.kind] = agent_patch(run, case.task.issue)
    return found, notes


def commit_fixes(repo: Path, base: str, fixes: Mapping[str, str]) -> dict[str, str | None]:
    """Each fix committed on `base` with a temporary index (None: it does not apply)."""
    made: dict[str, str | None] = {}
    with tempfile.TemporaryDirectory(prefix="tfbench-siblings-") as tmp:
        folder = Path(tmp)
        index = inside._Index(repo, folder)
        for variant, text in fixes.items():
            patch = folder / f"{variant}.patch"
            patch.write_bytes(text.encode("utf-8", "surrogatepass"))
            made[variant] = inside._patched(index, base, patch, f"tracefix-bench: {variant}")
    return made


def group_of(variant: str) -> str:
    return "partial" if variant.startswith("v") and variant[1:].isdigit() else variant


def touched_lines(scope: DiffScope) -> dict[str, set[int]]:
    """The base-side lines each file's hunks change (a pure insertion: the lines either side)."""
    out: dict[str, set[int]] = {}
    for change in scope.files:
        lines = out.setdefault(change.old_path or change.path, set())
        for hunk in change.hunks:
            lines.update(
                hunk.base_lines if hunk.base_len else {hunk.base_start, hunk.base_start + 1}
            )
    return out


def _site(site: SiblingSite) -> Json:
    return {"fixed_at": site.fixed_at, "path": site.path, "line": site.line, "text": site.text}


def _test_texts(repo: Path, scope: DiffScope, repro: str | None) -> list[str] | None:
    """The fix's own added or changed test files at head, and the run's reproduction test.
    None when neither exists (nothing to read)."""
    texts = [repro] if repro is not None else []
    for change in scope.files:
        if change.kind is FileKind.TEST and change.status != "D" and change.path.endswith(".py"):
            text = blob_text(repo, scope.head_sha, change.path)
            if text is not None:
                texts.append(text)
    return texts or None


def check_fix(repo: Path, base: str, head: str, repro: str | None,
              dropped: Mapping[str, set[int]] | None = None) -> Json:  # fmt: skip
    """The four signals for one fix; `dropped`: for a partial fix, its lines the gold fix
    changes (the dropped hunk), so a flag there is told apart."""
    scope = compute_scope(repo, base, head)
    block = replaced_code(repo, scope)
    lines = replaced_code(repo, scope, single_lines=True)
    names = same_name(repo, scope)
    constants = fix_constants(repo, scope)
    tests = _test_texts(repo, scope, repro)
    reads = sorted({n for t in tests or [] for n in constant_reads(t, constants)})
    out: Json = {
        "replaced_code": [_site(s) for s in block],
        "replaced_line": [_site(s) for s in lines],
        "same_name": [_site(s) for s in names],
        "constants": sorted(constants),
        "constant_reads": reads if tests is not None else None,
    }
    if dropped is not None:
        out["in_dropped_hunk"] = any(s.line in dropped.get(s.path, set()) for s in block)
    return out


def _repro(bench: Path, slice_name: str, instance_id: str, variant: str) -> str | None:
    path = bench / "results" / slice_name / instance_id / f"{variant}-r1" / "repro"
    path = path / "test_tracefix_repro.py"
    return path.read_text(encoding="utf-8") if path.is_file() else None


def measure_task(bench: Path, slice_name: str, case: Case, ready: prepare.Prepared,
                 url: Url = github) -> Json:  # fmt: skip
    task = case.task
    out: Json = {"instance_id": task.instance_id, "excluded": None, "notes": [], "fixes": {}}
    tree = bench / "work" / slice_name / task.instance_id / "tree"
    try:
        fetch(url(task.repo), task.base_commit, tree)
        fixes, out["notes"] = fix_patches(case, ready)
        made = commit_fixes(tree, task.base_commit, fixes)
    except (TreeError, WorkspaceError, patches.PatchError, ValueError) as exc:
        out["excluded"] = str(exc)[:300]
        return out
    gold = made.get("gold")
    for variant, sha in made.items():
        if sha is None:
            out["notes"].append(f"{variant} does not apply on the base commit")
            continue
        dropped = None
        if group_of(variant) == "partial" and gold is not None:
            dropped = touched_lines(compute_scope(tree, sha, gold))
        repro = _repro(bench, slice_name, task.instance_id, variant)
        checked = check_fix(tree, task.base_commit, sha, repro, dropped)
        out["fixes"][variant] = {"group": group_of(variant), **checked}
    return out


# --- the numbers and the plan's rule ------------------------------------------------------------


def _fires(fix: Mapping[str, Any], signal: str) -> bool | None:
    value = fix.get(signal)
    return None if value is None else bool(value)


def summarise(tasks: Iterable[Mapping[str, Any]]) -> Json:
    """Per group and signal: fixes measured and fixes the signal fires on; for partial fixes,
    how many replaced_code flags sit in the dropped hunk."""
    counts: Json = {g: {"fixes": 0, **{s: {"n": 0, "of": 0} for s in SIGNALS}} for g in GROUPS}
    counts["partial"]["in_dropped_hunk"] = 0
    excluded = 0
    for task in tasks:
        if task["excluded"] is not None:
            excluded += 1
            continue
        for fix in task["fixes"].values():
            row = counts[fix["group"]]
            row["fixes"] += 1
            for signal in SIGNALS:
                fired = _fires(fix, signal)
                if fired is not None:
                    row[signal]["of"] += 1
                    row[signal]["n"] += fired
            if fix.get("in_dropped_hunk"):
                row["in_dropped_hunk"] += 1
    return {"excluded_tasks": excluded, "groups": counts}


def _rate(groups: Mapping[str, Any], names: Sequence[str], signal: str) -> tuple[int, int]:
    return (sum(groups[g][signal]["n"] for g in names), sum(groups[g][signal]["of"] for g in names))


def decide(summary: Mapping[str, Any]) -> Json:
    """The plan's pre-registered rule (S0): build a sibling signal, report only, if its
    wrong-fix rate is at least MIN_GAP above its correct-fix rate and that is at most
    MAX_CORRECT; build constant reads if they fire in at least MIN_CONSTANT_RUNS fixes."""
    groups = summary["groups"]
    out: Json = {}
    for signal in RULED:
        wn, wof = _rate(groups, WRONG, signal)
        cn, cof = _rate(groups, CORRECT, signal)
        wrong, correct = (wn / wof if wof else 0.0), (cn / cof if cof else 0.0)
        out[signal] = {"wrong": f"{wn}/{wof}", "correct": f"{cn}/{cof}",
                       "build": wof > 0 and cof > 0 and wrong - correct >= MIN_GAP
                       and correct <= MAX_CORRECT}  # fmt: skip
    n, of = _rate(groups, GROUPS, "constant_reads")
    out["constant_reads"] = {"fires": f"{n}/{of}", "build": n >= MIN_CONSTANT_RUNS}
    return out


def _cell(rate: Mapping[str, int]) -> str:
    n, of = rate["n"], rate["of"]
    return f"{n}/{of} ({100 * n / of:.0f}%)" if of else "0/0"


def markdown(title: str, summary: Mapping[str, Any], decision: Mapping[str, Any] | None) -> str:
    groups = summary["groups"]
    out = [f"# {title}", "",
           "Static checks of each fix the benchmark runs (scripts/bench/siblings.py, M11 S0): no",
           "model, no Docker, no repo code run. A cell is fixes the signal fires on / fixes",
           "measured. replaced_code: the code a hunk replaced is still elsewhere at head (block);",
           "replaced_line: the same for single lines of 30+ characters; same_name: an untouched",
           "namesake of a changed function; constant_reads: a test of that fix reads a value",
           "the fix assigns.", "",
           f"Tasks excluded (base commit not fetched, or a setup error): "
           f"{summary['excluded_tasks']}",
           "", "| group | fixes | " + " | ".join(SIGNALS) + " |",
           "|---|---|" + "---|" * len(SIGNALS)]  # fmt: skip
    for g in GROUPS:
        row = groups[g]
        out.append(f"| {g} | {row['fixes']} | " + " | ".join(_cell(row[s]) for s in SIGNALS) + " |")
    out += ["", f"Partial fixes with a replaced_code flag in the dropped hunk: "
            f"{groups['partial']['in_dropped_hunk']}"]  # fmt: skip
    if decision is not None:
        out += ["", "## The plan's rule", "",
                f"Build a sibling signal (report only) if wrong fixes (partial + agent_wrong) "
                f"fire at least {MIN_GAP:.0%} points more often than correct fixes (gold + "
                f"agent_ok) and correct fixes at most {MAX_CORRECT:.0%}; constant reads if "
                f"they fire in at least {MIN_CONSTANT_RUNS} fixes.", ""]  # fmt: skip
        for signal, verdict in decision.items():
            rates = ", ".join(f"{k} {v}" for k, v in verdict.items() if k != "build")
            out.append(
                f"- {signal}: {rates}: **{'build' if verdict['build'] else 'do not build'}**"
            )
    return "\n".join(out) + "\n"


def _write(folder: Path, stem: str, data: Json, md: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=1, ensure_ascii=True, sort_keys=True) + "\n"
    (folder / f"{stem}.json").write_text(text, "ascii", newline="\n")
    (folder / f"{stem}.md").write_text(md, "utf-8", newline="\n")


def measure(bench: Path, slices: Sequence[str], split: str = "dev", limit: int | None = None,
            url: Url = github, progress: Callable[[str], None] = print) -> Json:  # fmt: skip
    """Measure each slice's ready tasks of `split` (the first `limit` in rank order), write its
    file, then sum every slice file in the folder and apply the rule."""
    folder = bench / "results" / "sibling-sites"
    for slice_name in slices:
        cases = [c for c in read_cases(bench / "cases" / f"{slice_name}.jsonl") if c.split == split]
        found = []
        for case in cases[:limit] if limit is not None else cases:
            path = bench / "prepared" / slice_name / f"{case.task.instance_id}.json"
            if not path.is_file():
                continue
            ready = prepare.Prepared.model_validate_json(path.read_text(encoding="utf-8"))
            if ready.excluded is not None:
                continue
            progress(f"{slice_name} {case.task.instance_id}")
            found.append(measure_task(bench, slice_name, case, ready, url))
        summary = summarise(found)
        data = {"slice": slice_name, "split": split, "summary": summary, "tasks": found}
        _write(folder, slice_name, data, markdown(f"Sibling sites: {slice_name} {split}",
                                                  summary, None))  # fmt: skip
    every = []
    for path in sorted(folder.glob("slice*.json")):
        every += json.loads(path.read_text(encoding="ascii"))["tasks"]
    summary = summarise(every)
    decision = decide(summary)
    _write(
        folder,
        "summary",
        {"summary": summary, "decision": decision},
        markdown("Sibling sites: every slice measured", summary, decision),
    )
    return {"tasks": len(every), "excluded": summary["excluded_tasks"], "decision": decision}

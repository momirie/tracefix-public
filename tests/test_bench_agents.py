"""Slice 2's data (M10 part 2 plan C1-C2): SWE-rebench rows, the OpenHands runs file, the agent
rule and the funnel's counts. No network: the Hub is a fake, and the runs file is written here
the way scripts/extract_agents.py writes it (its pyarrow reading is the only part not tested)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import benchmark
import pytest
from bench import agents, choose, data
from test_bench_data import REV, FakeHub, diff, raw, task

AGENT_REV = "d" * 40
SCRATCH = (
    "diff --git a/reproduce_issue.py b/reproduce_issue.py\nnew file mode 100644\n"
    "index 0000000..1111111\n--- /dev/null\n+++ b/reproduce_issue.py\n@@ -0,0 +1 @@\n+x = 1\n"
)
FIX = diff("src/widgets/core.py")


def run_row(
    instance_id: Any = "acme__widgets-12",
    patch: str | None = FIX,
    status: Any = "submit",
    resolved: Any = 0,
) -> dict[str, Any]:
    """The four columns the extraction reads from one trajectories row."""
    return {
        "instance_id": instance_id,
        "model_patch": patch,
        "exit_status": status,
        "resolved": resolved,
    }


def write_runs(cache: Path, sources: Path, rows: list[dict[str, Any]]) -> agents.Pin:
    """What scripts/extract_agents.py leaves behind: the runs file and its pin."""
    tasks, unreadable = agents.group(enumerate(rows))
    blob = agents.encode(tasks)
    cache.mkdir(parents=True, exist_ok=True)
    agents.runs_path(cache, AGENT_REV).write_bytes(blob)
    pin = agents.Pin(
        dataset=agents.DATASET,
        revision=AGENT_REV,
        file=agents.FILE,
        file_sha256="e" * 64,
        rows=len(rows),
        unreadable_rows=unreadable,
        runs_sha256=data.digest(blob),
        license=data.LICENSE,
        url="https://huggingface.co/datasets/nebius/SWE-rebench-openhands-trajectories",
    )
    agents.write_pin(sources, pin)
    return pin


def agent(resolved: bool, row: int = 0, patch: str = FIX, submitted: bool = True) -> data.AgentRun:
    return data.AgentRun(
        instance_id="acme__widgets-12",
        source_row=row,
        patch=patch,
        submitted=submitted,
        resolved=resolved,
    )


# --- SWE-rebench rows ---------------------------------------------------------------------------


def test_an_untagged_image_name_means_latest() -> None:
    untagged = data.image_for("acme__widgets-12").removesuffix(":latest")
    assert task(image_name=untagged).image == data.image_for("acme__widgets-12")


def test_each_dataset_keeps_its_own_pin(tmp_path: Path) -> None:
    sources = tmp_path / "sources.json"
    for dataset in (data.LEADERBOARD, data.REBENCH):
        hub = FakeHub([raw(0)], dataset=dataset)
        data.write_source(sources, dataset, data.repin(dataset, tmp_path / "cache", hub))
    write_runs(tmp_path / "cache", sources, [run_row()])
    pins = json.loads(sources.read_text("utf-8"))
    assert list(pins) == ["swe-rebench-leaderboard", "swe-rebench", "swe-rebench-openhands"]
    assert data.read_source(sources, data.REBENCH).dataset == "nebius/SWE-rebench"
    assert agents.read_pin(sources).revision == AGENT_REV
    with pytest.raises(data.DataError, match="not nebius/SWE-rebench's"):
        data.load_rows(data.REBENCH, data.read_source(sources, data.LEADERBOARD), tmp_path, hub)


# --- the runs ------------------------------------------------------------------------------------


def test_runs_are_grouped_by_task_in_row_order_keeping_four_fields() -> None:
    rows = [run_row(resolved=i % 2) for i in range(5)] + [run_row("acme__other-1")]
    rows[3]["exit_status"] = "RuntimeError: Agent reached maximum iteration."
    rows[4]["model_patch"] = None
    tasks, unreadable = agents.group(reversed(list(enumerate(rows))))
    assert [t.instance_id for t in tasks] == ["acme__other-1", "acme__widgets-12"]
    found = tasks[1]
    assert [r.source_row for r in found.runs] == [0, 1, 2, 3, 4] and found.dropped == 0
    assert [r.resolved for r in found.runs] == [False, True, False, True, False]
    assert [r.submitted for r in found.runs] == [True, True, True, False, True]
    assert found.runs[4].patch == "" and unreadable == 0


@pytest.mark.parametrize(
    "bad",
    [
        {"resolved": 2},
        {"resolved": True},
        {"resolved": "1"},
        {"resolved": None},
        {"exit_status": None},
        {"model_patch": "x\x00y"},
    ],
)
def test_a_run_that_fails_strict_parsing_is_dropped_and_counted(bad: dict[str, Any]) -> None:
    [found], _ = agents.group(enumerate([run_row(), run_row() | bad]))
    assert [r.source_row for r in found.runs] == [0] and found.dropped == 1


@pytest.mark.parametrize("instance_id", [None, 7, "", "no-separator", "a__b-1' OR '1'='1"])
def test_a_row_without_a_valid_task_id_belongs_to_no_task(instance_id: Any) -> None:
    tasks, unreadable = agents.group(enumerate([run_row(), run_row(instance_id)]))
    assert [t.instance_id for t in tasks] == ["acme__widgets-12"] and unreadable == 1


def test_another_tasks_row_is_never_taken_for_this_one() -> None:
    with pytest.raises(data.InvalidRow, match="another task"):
        agents.parse_run("acme__widgets-12", 0, run_row("acme__widgets-13"))


def test_the_runs_file_is_ascii_and_read_back_under_its_pin(tmp_path: Path) -> None:
    emoji = FIX.replace("+x = 2", "+x = '\U0001f389 done'")  # the first real read had one
    rows = [run_row(patch=emoji), run_row(resolved=1)]
    pin = write_runs(tmp_path, tmp_path / "sources.json", rows)
    path = agents.runs_path(tmp_path, AGENT_REV)
    path.read_bytes().decode("ascii")
    runs = agents.load(pin, tmp_path)
    assert runs("acme__widgets-12").runs[0].patch == emoji
    assert runs("acme__absent-1") == agents.TaskRuns(
        instance_id="acme__absent-1", runs=(), dropped=0
    )
    assert agents.read_pin(tmp_path / "sources.json") == pin


def test_a_changed_or_missing_runs_file_is_refused(tmp_path: Path) -> None:
    pin = write_runs(tmp_path, tmp_path / "sources.json", [run_row(resolved=0)])
    path = agents.runs_path(tmp_path, AGENT_REV)
    path.write_bytes(path.read_bytes().replace(b'"resolved": false', b'"resolved": true'))
    with pytest.raises(data.DataError, match="doesn't match its pin"):
        agents.load(pin, tmp_path)
    path.unlink()
    with pytest.raises(data.DataError, match="extract_agents"):
        agents.load(pin, tmp_path)
    with pytest.raises(data.DataError, match="extract_agents"):
        agents.read_pin(tmp_path / "no-sources.json")


# --- the agent rule -----------------------------------------------------------------------------


def test_added_files_are_read_from_the_headers_only() -> None:
    body = "+new file mode 100644\n"  # a hunk line that looks like a header
    sneaky = FIX.replace("+x = 2\n", f"+x = 2\n{body}")
    assert choose.added_files(SCRATCH + sneaky) == {"reproduce_issue.py"}


@pytest.mark.parametrize(
    ("run", "ok"),
    [
        (agent(False), True),
        (agent(False, patch=SCRATCH + FIX), True),  # a scratch script beside a real change
        (agent(False, submitted=False), False),  # it stopped on an error
        (agent(False, patch=""), False),
        (agent(False, patch=SCRATCH), False),  # only adds a file
        (agent(False, patch=diff("tests/test_core.py")), False),
        (agent(False, patch=diff("src/widgets/fast.pyx", "src/widgets/core.py")), False),
        (agent(False, patch="not a diff"), False),
    ],
)
def test_a_usable_agent_run_finished_and_changed_existing_source(
    run: data.AgentRun, ok: bool
) -> None:
    assert choose.usable(run) is ok


def test_at_most_one_run_of_each_verdict_is_picked_in_a_fixed_order() -> None:
    runs = [agent(n % 2 == 0, n) for n in range(10)] + [agent(True, 10, submitted=False)]
    picked = choose.pick_agents("slice2", runs)
    assert [r.resolved for r in picked] == [False, True]
    assert choose.pick_agents("slice2", list(reversed(runs))) == picked
    only_wrong = [r for r in runs if not r.resolved]
    assert [r.resolved for r in choose.pick_agents("slice2", only_wrong)] == [False]
    assert choose.pick_agents("slice2", [agent(True, submitted=False)]) == ()


@pytest.mark.parametrize(
    ("python", "slice1", "slice2"),
    [
        ("3.8", choose.Reason.PYTHON, choose.Reason.PYTHON_RANGE),
        ("3.9", choose.Reason.PYTHON, None),
        ("3.10", choose.Reason.PYTHON, None),
        ("3.13", None, None),
        ("3.14", None, choose.Reason.PYTHON_RANGE),
    ],
)
def test_each_slice_has_its_python_range(
    python: str, slice1: choose.Reason | None, slice2: choose.Reason | None
) -> None:
    case = task(config={"python": python})
    assert choose.check(case, choose.SLICES["slice1"]) == slice1
    assert choose.check(case, choose.SLICES["slice2"]) == slice2


def test_a_task_the_agent_rule_refuses_leaves_its_repo_place_free() -> None:
    tasks = [task(repo="Org/repo1", instance_id=f"org__repo1-{n}") for n in range(1, 7)]
    asked: list[str] = []
    refused = {t.instance_id for t in tasks[::2]}

    def admit(t: data.Task) -> choose.Reason | None:
        asked.append(t.instance_id)
        return choose.Reason.NO_AGENT_PATCH if t.instance_id in refused else None

    plain, _ = choose.sample([t for t in tasks if t.instance_id not in refused], "slice2", 10)
    chosen, left = choose.sample(tasks, "slice2", 10, admit=admit)
    assert chosen == plain and len(chosen) == choose.PER_REPO
    reasons = sorted(e.reason.value for e in left)
    assert reasons == ["no_usable_agent_patch"] * len(set(asked) & refused) + ["repo_cap"] * (
        len(tasks) - len(chosen) - len(set(asked) & refused)
    )
    assert not set(asked) & {e.instance_id for e in left if e.reason is choose.Reason.REPO_CAP}


def test_the_agent_rule_is_not_asked_past_the_limit() -> None:
    tasks = [task(repo=f"Org/r{n}", instance_id=f"org__r{n}-1") for n in range(10)]
    asked: list[str] = []

    def admit(t: data.Task) -> choose.Reason | None:
        asked.append(t.instance_id)
        return None

    chosen, _ = choose.sample(tasks, "slice2", 3, admit=admit)
    assert asked == [t.instance_id for t in chosen]


# --- select, slice 2 ----------------------------------------------------------------------------


def slice2_rows() -> list[data.RawRow]:
    def row(i: int, n: int, python: str = "3.9") -> data.RawRow:
        name = f"acme__w{n}-{n}"  # one repo each: the repo cap stays out of the way
        image = data.image_for(name).removesuffix(":latest")
        return raw(i, {"python": python}, repo=f"Acme/w{n}", instance_id=name, image_name=image)

    return [
        row(0, 1),  # wrong and right agent runs
        row(1, 2, "3.12"),  # only a wrong one
        row(2, 3),  # only a scratch script: refused by the agent rule
        row(3, 4, "3.8"),  # Python outside 3.9-3.13
        row(4, 5),  # no runs at all
    ]


def slice2_runs() -> list[dict[str, Any]]:
    return [
        run_row("acme__w1-1", resolved=0),
        run_row("acme__w1-1", resolved=1),
        run_row("acme__w1-1", status="RuntimeError: out of budget"),
        run_row("acme__w2-2", resolved=0),
        run_row("acme__w3-3", patch=SCRATCH, resolved=1),
    ]


def test_select_slice2_keeps_agent_runs_and_counts_them_by_python(tmp_path: Path) -> None:
    hub = FakeHub(slice2_rows(), dataset=data.REBENCH)
    write_runs(tmp_path / "cache", tmp_path / "sources.json", slice2_runs())
    summary = benchmark.select(tmp_path, "slice2", 10, repin=True, get=hub)
    assert summary["excluded"] == {
        "python_outside_3_9_to_3_13": 1,
        "no_agent_runs": 1,
        "no_usable_agent_patch": 1,
    }
    assert summary["by_python"] == {
        "3.9": {"eligible": 3, "chosen": 1, "agent_wrong": 1, "agent_ok": 1, "both": 1},
        "3.12": {"eligible": 1, "chosen": 1, "agent_wrong": 1, "agent_ok": 0, "both": 0},
    }
    cases = {c.task.instance_id: c for c in data.read_cases(tmp_path / "cases" / "slice2.jsonl")}
    assert set(cases) == {"acme__w1-1", "acme__w2-2"}
    assert [(r.source_row, r.resolved) for r in cases["acme__w1-1"].agents] == [
        (0, False),
        (1, True),
    ]
    assert cases["acme__w1-1"].task.image == data.image_for("acme__w1-1")
    funnel_file = tmp_path / "cases" / "slice2.funnel.json"
    funnel = json.loads(funnel_file.read_text("ascii"))
    assert funnel["source"]["dataset"] == "nebius/SWE-rebench"
    assert funnel["agents_source"]["revision"] == AGENT_REV
    assert funnel["source"]["revision"] == REV
    before = (tmp_path / "cases" / "slice2.jsonl").read_bytes(), funnel_file.read_bytes()

    def offline(url: str) -> bytes:
        raise AssertionError(f"network used: {url}")

    benchmark.select(tmp_path, "slice2", 10, repin=False, get=offline)
    assert ((tmp_path / "cases" / "slice2.jsonl").read_bytes(), funnel_file.read_bytes()) == before


def test_select_refuses_a_slice_without_rules(tmp_path: Path) -> None:
    with pytest.raises(data.DataError, match="no selection rules"):
        benchmark.select(tmp_path, "slice9", 10, repin=False, get=FakeHub([]))


def test_slice1s_committed_cases_are_rewritten_byte_for_byte(tmp_path: Path) -> None:
    committed = Path(__file__).parents[1] / "benchmarks" / "cases" / "slice1.jsonl"
    copy = tmp_path / "slice1.jsonl"
    data.write_cases(copy, data.read_cases(committed))
    assert copy.read_bytes() == committed.read_bytes()


# --- the patch as the agent made it -------------------------------------------------------------

ISSUE = "Widgets break\r\nWhen a widget is empty\r\n"  # the dataset's issue text keeps its CRLFs


def new_file(path: str, *lines: str, end: str = "") -> str:
    """A diff that creates `path`; `end` follows the last line (git's no-newline marker)."""
    body = "".join(f"+{line}\n" for line in lines)
    return (f"diff --git a/{path} b/{path}\nnew file mode 100644\nindex 0000000..3333333\n"
            f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n{body}{end}")  # fmt: skip


# What OpenHands left in the repo: "### " and the issue, its last line without a newline.
ISSUE_FILE = new_file("issue.md", "### Widgets break", "When a widget is empty",
                      end="\\ No newline at end of file\n")  # fmt: skip


@pytest.mark.parametrize("patch", [FIX, SCRATCH + FIX, ""])
def test_the_last_newline_the_dataset_stripped_is_put_back(patch: str) -> None:
    """The dataset's model_patch is the diff without its last newline; git calls most of those
    corrupt (all 180 of slice 2's runs lack it)."""
    stripped = agent(False, patch=patch.removesuffix("\n"))
    assert agents.agent_patch(stripped, ISSUE) == patch
    assert agents.agent_patch(agent(False, patch=patch), ISSUE) == patch


@pytest.mark.parametrize("patch", [ISSUE_FILE + FIX, FIX + ISSUE_FILE, SCRATCH + ISSUE_FILE + FIX])
def test_the_issue_file_openhands_wrote_is_dropped_and_the_rest_kept_byte_for_byte(
    patch: str,
) -> None:
    kept = patch.replace(ISSUE_FILE, "")
    assert agents.agent_patch(agent(False, patch=patch.removesuffix("\n")), ISSUE) == kept


@pytest.mark.parametrize(
    "lookalike",
    [
        new_file("issue.md", "### Widgets break", "When a widget is EMPTY"),  # other text
        new_file("issue.md", "Widgets break", "When a widget is empty"),  # not OpenHands' form
        new_file("docs/issue.md", "### Widgets break", "When a widget is empty"),  # not top-level
        "diff --git a/issue.md b/issue.md\nindex 1111111..2222222 100644\n--- a/issue.md\n"
        "+++ b/issue.md\n@@ -1 +1,2 @@\n ### Widgets break\n+When a widget is empty\n",  # an edit
    ],
)
def test_an_issue_file_that_isnt_exactly_the_one_openhands_wrote_is_kept(lookalike: str) -> None:
    assert agents.agent_patch(agent(False, patch=lookalike + FIX), ISSUE) == lookalike + FIX


def test_a_patch_that_doesnt_parse_is_left_as_it_is() -> None:
    broken = ISSUE_FILE + FIX.replace("@@ -1 +1 @@", "@@ -1 +1,5 @@")  # shorter than its header
    assert agents.agent_patch(agent(False, patch=broken), ISSUE) == broken

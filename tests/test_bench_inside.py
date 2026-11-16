"""The benchmark's box (M10 plan P5, P9): inside.py's steps, the host's checks of what comes back,
and the run steps. No Docker, no network: DockerBox is driven against a fake `docker`, and the
real steps run in a LocalBox (a local clone, this interpreter). The partial_fix fixture goes
through `verify` and the gold replay with the recorded model answers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import bench_fakes
import make_fixtures
import pytest
from bench import box, inside, patches, prepare
from bench.agents import agent_patch
from bench.data import AgentRun, Task
from bench.prepare import Hidden, Prepared, Reason, Session, TriedAgent
from conftest import make_repo, old_python

from tracefix.config import parse
from tracefix.llm import (
    FakeProvider,
    LLMRequest,
    Message,
    MissingRecording,
    RecordedProvider,
    RecordingProvider,
    Role,
)
from tracefix.previous import PreviousStatus, Replay

ROOT = Path(__file__).resolve().parent.parent
RECORDINGS = ROOT / "tests" / "recordings"
WHEEL = Path("unused.whl")  # LocalBox installs nothing

# --- the synthetic task: two bugs, one hunk each, an ignored _version.py -----------------------

FILLER = "".join(f"# line {i}\n" for i in range(12))  # keeps the two hunks apart
CALC = (
    "def double(x):\n    return x + x + 1\n\n" + FILLER + "\ndef half(x):\n    return x // 2 + 1\n"
)
FIXED = CALC.replace("x + x + 1", "x + x").replace("x // 2 + 1", "x // 2")
BASE = {
    ".gitignore": "pkg/_version.py\n",
    "pkg/__init__.py": "from pkg._version import VERSION\n",
    "pkg/calc.py": CALC,
    "tests/test_calc.py": "import pkg\n\n\ndef test_version():\n    assert pkg.VERSION == '1'\n",
}
HIDDEN = (
    "from pkg.calc import double, half\n\n\n"
    "def test_double():\n    assert double(2) == 4\n\n\n"
    "def test_half():\n    assert half(4) == 2\n"
)
F2P = ("tests/test_fix.py::test_double", "tests/test_fix.py::test_half")
P2P = ("tests/test_calc.py::test_version",)


def raw_diff(repo: Path, *args: str) -> str:
    """`git diff` exactly as printed (make_fixtures.git strips the last newline)."""
    done = subprocess.run(["git", "diff", *args], cwd=repo, capture_output=True, check=True)
    return done.stdout.decode("utf-8")


def synthetic(tmp_path: Path) -> tuple[Path, Task]:
    """A repo at the base commit (tag c0), and its task: gold fixes both bugs (two hunks), the
    test patch adds the hidden tests."""
    repo = make_repo(
        tmp_path / "source",
        [BASE, {"pkg/calc.py": FIXED}, {"pkg/calc.py": CALC, "tests/test_fix.py": HIDDEN}],
    )
    gold = raw_diff(repo, "c0", "c1")
    tests = raw_diff(repo, "c0", "c2", "--", "tests")
    return repo, task(make_fixtures.git(repo, "rev-parse", "c0").strip(), gold, tests)


def task(base: str, patch: str, test_patch: str, f2p: Sequence[str] = F2P,
         p2p: Sequence[str] = P2P) -> Task:  # fmt: skip
    return Task(
        instance_id="tracefix__synthetic-1", repo="tracefix/synthetic", base_commit=base,
        patch=patch, test_patch=test_patch, issue="double and half are off by one",
        fail_to_pass=tuple(f2p), pass_to_pass=tuple(p2p), image="", python="3.11",
        test_cmd="pytest", created_at="2026-01-01 00:00:00", source_row=0,
        source_revision="a" * 40,
    )  # fmt: skip


def local_box(source: Path, checkout: str, tmp_path: Path) -> box.LocalBox:
    found = box.LocalBox(source, checkout, tmp_path / "box")
    (Path(found.repo) / "pkg").mkdir(exist_ok=True)
    return found


def touched(function: str | None, path: str = "pkg/calc.py") -> prepare.Touched:
    return prepare.Touched(path=path, function=function)


def session(b: box.Box, tmp_path: Path) -> Session:
    scratch = tmp_path / "scratch"
    scratch.mkdir(exist_ok=True)
    return Session(b, scratch)


def test_a_two_hunk_task_is_prepared_with_a_partial_variant(tmp_path: Path) -> None:
    """One test, not three: preparing the task is the slow part (a fixture shared by several
    tests would be built once per xdist worker)."""
    source, t = synthetic(tmp_path)
    b = local_box(source, "c0", tmp_path)
    (Path(b.repo) / "pkg" / "_version.py").write_text("VERSION = '1'\n", encoding="utf-8")
    (Path(b.repo) / "notes.txt").write_text("left in the image's checkout\n", encoding="utf-8")
    prepared = prepare.prepare(session(b, tmp_path), t, WHEEL)
    assert prepared.excluded is None, prepared.detail
    assert prepared.source_hunks == 2
    labels = [(v.index, v.label, v.failing) for v in prepared.variants]
    assert labels == [(0, patches.Label.PARTIAL, 1), (1, patches.Label.PARTIAL, 1)]
    assert prepared.kept == 0  # equal failing counts: hunk order
    # M11 S2: the function each dropped hunk touches, by Tracefix's own diff parse.
    assert [v.functions for v in prepared.variants] == [(touched("double"),), (touched("half"),)]
    assert set(prepared.commits) == {"base", "gold", "v0"}
    assert prepared.suite_seconds is not None and prepared.suite_timeout == 120
    assert prepared.seconds > 0
    # The setup commit: without pkg/_version.py in it, the copies couldn't import pkg at all.
    assert prepared.setup_files == ("pkg/_version.py",)
    assert prepared.changed_files == ("notes.txt",)
    # The config: the suite timeout and plugins only, no model settings, and Tracefix reads it.
    settings = parse(prepared.config().encode(), "config")
    assert settings.suite_timeout_seconds == prepared.suite_timeout
    assert set(settings.model_dump(exclude_none=True)) == {"suite_timeout_seconds",
                                                           "pytest_plugins"}  # fmt: skip


def test_agent_patches_are_labelled_by_our_hidden_runs(tmp_path: Path) -> None:
    """Plan C3. agent_wrong fixes one bug of two: partial, kept. agent_ok fixes both and adds
    its own tests/test_fix.py, the very file the hidden-test patch creates: the test patch's
    files are put back as base has them first (else it wouldn't apply and the label would be
    does_not_apply), while the run commit keeps the agent's test, as a reviewer would see it."""
    source, t = synthetic(tmp_path)
    own = "def test_mine():\n    assert True\n"
    half = CALC.replace("x + x + 1", "x + x")
    agents_repo = make_repo(tmp_path / "agents",
                            [BASE, {"pkg/calc.py": half},
                             {"pkg/calc.py": FIXED, "tests/test_fix.py": own}])  # fmt: skip
    runs = [
        AgentRun(instance_id=t.instance_id, source_row=row, patch=raw_diff(agents_repo, *refs),
                 submitted=True, resolved=resolved)
        for row, refs, resolved in ((7, ("c0", "c1"), False), (8, ("c0", "c2"), True))
    ]  # fmt: skip
    b = local_box(source, "c0", tmp_path)
    (Path(b.repo) / "pkg" / "_version.py").write_text("VERSION = '1'\n", encoding="utf-8")
    prepared = prepare.prepare(session(b, tmp_path), t, WHEEL, agents=runs)
    assert prepared.excluded is None, prepared.detail
    # functions: what the patch touches (tests left out); differs: where it isn't gold's.
    assert prepared.agents == (
        TriedAgent(kind="agent_wrong", source_row=7, label=patches.Label.PARTIAL, failing=1,
                   kept=True, functions=(touched("double"),), differs=(touched("half"),)),
        TriedAgent(kind="agent_ok", source_row=8, label=patches.Label.HIDDEN_TESTS_PASS,
                   failing=0, kept=True, functions=(touched("double"), touched("half")),
                   differs=()),
    )  # fmt: skip
    assert set(prepared.commits) == {"base", "gold", "v0", "agent_wrong", "agent_ok"}
    shown = make_fixtures.git(Path(b.repo), "show", "tf-agent_ok:tests/test_fix.py")
    assert shown == own.rstrip("\n")


def test_agent_patches_as_the_dataset_has_them_apply(tmp_path: Path) -> None:
    """The dataset's form: the diff without its last newline, with the issue file OpenHands
    wrote, in an image that already has that file. Both apply (agents.agent_patch), and run's
    commits are prepare's."""
    source, t = synthetic(tmp_path)
    issue_md = f"### {t.issue}"
    half = CALC.replace("x + x + 1", "x + x")
    agents_repo = make_repo(tmp_path / "agents",
                            [BASE, {"pkg/calc.py": half, "issue.md": issue_md},
                             {"pkg/calc.py": FIXED, "issue.md": issue_md}])  # fmt: skip
    runs = [
        AgentRun(instance_id=t.instance_id, source_row=row,
                 patch=raw_diff(agents_repo, *refs).removesuffix("\n"), submitted=True,
                 resolved=resolved)
        for row, refs, resolved in ((7, ("c0", "c1"), False), (8, ("c0", "c2"), True))
    ]  # fmt: skip
    assert all("issue.md" in r.patch and not r.patch.endswith("\n") for r in runs)
    b = local_box(source, "c0", tmp_path)
    (Path(b.repo) / "pkg" / "_version.py").write_text("VERSION = '1'\n", encoding="utf-8")
    (Path(b.repo) / "issue.md").write_text(issue_md, encoding="utf-8")
    prepared = prepare.prepare(session(b, tmp_path), t, WHEEL, agents=runs)
    assert prepared.excluded is None, prepared.detail
    assert prepared.changed_files == ("issue.md",)
    assert [(a.kind, a.label, a.kept) for a in prepared.agents] == [
        ("agent_wrong", patches.Label.PARTIAL, True),
        ("agent_ok", patches.Label.HIDDEN_TESTS_PASS, True),
    ]
    again = prepare.make_commits(session(b, tmp_path), t,
                                 {"agent_ok": agent_patch(runs[1], t.issue)},
                                 hidden_tests=False)  # fmt: skip
    assert again.commits["agent_ok"] == prepared.commits["agent_ok"]


@pytest.mark.parametrize(
    ("kind", "label", "kept"),
    [
        ("agent_wrong", patches.Label.PARTIAL, True),
        ("agent_wrong", patches.Label.NO_EFFECT, True),
        ("agent_wrong", patches.Label.BROKEN, True),
        ("agent_wrong", patches.Label.HIDDEN_TESTS_PASS, False),  # the dataset disagrees
        ("agent_wrong", patches.Label.UNSETTLED, False),
        ("agent_wrong", patches.Label.DOES_NOT_APPLY, False),
        ("agent_ok", patches.Label.HIDDEN_TESTS_PASS, True),
        ("agent_ok", patches.Label.PARTIAL, False),  # the dataset disagrees
        ("agent_ok", patches.Label.UNSETTLED, False),
    ],
)
def test_an_agent_patch_is_kept_only_when_our_runs_agree_with_the_dataset(
    kind: prepare.AgentKind, label: patches.Label, kept: bool
) -> None:
    assert prepare.agrees(kind, label) is kept


def test_two_agent_runs_of_one_kind_are_refused() -> None:
    with pytest.raises(ValueError, match="more than one"):
        prepare.agent_patches([bench_fakes.agent_run(True), bench_fakes.agent_run(True)])


def test_commits_are_reproducible_and_leave_the_checkout_alone(tmp_path: Path) -> None:
    """Prepare's box (hidden tests) and a run box (none) make the same commits; the run box
    never gets the test patch or a hidden-test commit, so verify can't read them (plan P5)."""
    source, t = synthetic(tmp_path)
    shas, tags = [], []
    for n in range(2):
        b = local_box(source, "c0", tmp_path / f"run{n}")
        (Path(b.repo) / "pkg" / "_version.py").write_text("VERSION = '1'\n", encoding="utf-8")
        s = session(b, tmp_path / f"run{n}")
        s.box.put(prepare.INSIDE, s.box.path("inside.py"))
        made = prepare.make_commits(s, t, {"gold": t.patch, "nope": "not a patch\n"},
                                    hidden_tests=n == 0)  # fmt: skip
        shas.append(made.commits)
        tags.append(set(make_fixtures.git(Path(b.repo), "tag", "--list", "tf-*").split()))
        status = make_fixtures.git(Path(b.repo), "status", "--porcelain")
        assert status == "", "the checkout's files are never touched"
    assert shas[0] == shas[1]
    assert shas[0]["nope"] is None and shas[0]["gold"] is not None
    assert tags == [{"tf-base", "tf-gold", "tf-base-t", "tf-gold-t"}, {"tf-base", "tf-gold"}]
    sent = [p.read_text(encoding="utf-8") for p in (tmp_path / "run1").rglob("*.json")]
    assert sent and not any("test_fix.py" in text for text in sent)


def test_a_checkout_away_from_the_base_commit_is_excluded(tmp_path: Path) -> None:
    source, t = synthetic(tmp_path)
    b = local_box(source, "c1", tmp_path)
    found = prepare.prepare(session(b, tmp_path), t, WHEEL)
    assert found.excluded is Reason.NOT_AT_BASE
    assert found.python and found.isolation in ("strict", "basic")


def commit_on_head(repo: Path, email: str = inside.SETUP_COMMIT_EMAIL,
                   subject: str = inside.SETUP_COMMIT_SUBJECT) -> None:  # fmt: skip
    """A commit as SWE-rebench's eval agent makes them: an empty `=2.1`, left by an unquoted
    `pip install x>=2.1`."""
    (repo / "=2.1").write_text("", encoding="utf-8")
    env = {**make_fixtures.git_env(make_fixtures.BASE_DATE), "GIT_AUTHOR_EMAIL": email}
    for args in (["add", "-A"], ["commit", "-q", "-m", subject]):
        subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True)


def test_swe_rebenchs_setup_commit_on_the_base_is_the_base(tmp_path: Path) -> None:
    """Some SWE-rebench images sit one commit past the base: its eval agent's environment
    setup, which its hidden tests ran on. tf-base keeps it; the record lists its files."""
    source, t = synthetic(tmp_path)
    b = local_box(source, "c0", tmp_path)
    commit_on_head(Path(b.repo))
    s = session(b, tmp_path)
    s.box.put(prepare.INSIDE, s.box.path("inside.py"))
    made = prepare.make_commits(s, t, {"gold": t.patch}, hidden_tests=True)
    assert made.error is None and made.changed == ("=2.1",)
    assert made.commits["gold"] is not None and made.with_tests["gold"] is not None
    files = make_fixtures.git(Path(b.repo), "ls-tree", "--name-only", "tf-base").split()
    assert "=2.1" in files
    assert make_fixtures.git(Path(b.repo), "status", "--porcelain") == ""


@pytest.mark.parametrize(
    ("email", "subject", "commits"),
    [("someone@example.com", inside.SETUP_COMMIT_SUBJECT, 1),
     (inside.SETUP_COMMIT_EMAIL, "Fix the bug", 1),
     (inside.SETUP_COMMIT_EMAIL, inside.SETUP_COMMIT_SUBJECT, 2)],  # not right on the base
)  # fmt: skip
def test_any_other_commit_past_the_base_is_not_the_base(
    tmp_path: Path, email: str, subject: str, commits: int
) -> None:
    repo = make_repo(tmp_path / "r", [{"a.py": ""}])
    base = make_fixtures.git(repo, "rev-parse", "HEAD").strip()
    assert inside.image_setup_files(repo, base) == []
    for n in range(commits):
        (repo / f"b{n}.py").write_text("", encoding="utf-8")
        commit_on_head(repo, email, subject)
    assert inside.image_setup_files(repo, base) is None
    found = inside.commits({"repo": str(repo), "base_commit": base})
    assert found == {"error": "not_at_base"}


def test_a_base_suite_over_the_cap_is_excluded(tmp_path: Path) -> None:
    source, t = synthetic(tmp_path)
    b = local_box(source, "c0", tmp_path)
    (Path(b.repo) / "pkg" / "_version.py").write_text(
        "import time\ntime.sleep(60)\nVERSION = '1'\n", encoding="utf-8"
    )
    found = prepare.prepare(session(b, tmp_path), t, WHEEL, suite_cap=3)
    assert (found.excluded, found.detail) == (Reason.SUITE_TOO_SLOW, "over 3s")


def test_a_base_suite_that_cannot_import_is_excluded_naming_the_missing_module(
    tmp_path: Path,
) -> None:
    """As in SWE-rebench images that hold only what the task's own test files need."""
    source, t = synthetic(tmp_path)
    b = local_box(source, "c0", tmp_path)
    (Path(b.repo) / "pkg" / "_version.py").write_text(
        "import tracefix_bench_not_installed\nVERSION = '1'\n", encoding="utf-8"
    )
    found = prepare.prepare(session(b, tmp_path), t, WHEEL)
    assert found.excluded is Reason.SUITE_ERROR
    assert found.detail == (
        "pytest outcome error; ModuleNotFoundError tracefix_bench_not_installed"
    )


def test_a_crash_inside_is_a_harness_error_in_our_own_words(tmp_path: Path) -> None:
    source, _ = synthetic(tmp_path)
    s = session(local_box(source, "c0", tmp_path), tmp_path)
    s.box.put(prepare.INSIDE, s.box.path("inside.py"))
    with pytest.raises(prepare.StepFailed, match=r"^commits failed \(exit 1\)$"):
        s.call("commits", {"repo": s.box.repo})  # no base_commit: KeyError inside


def test_setup_files_are_ignored_code_beside_a_tracked_init(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path / "r",
        [{".gitignore": "*.so\n_version.py\nbuild/\n", "pkg/__init__.py": "", "top.py": ""}],
    )
    for rel in ("pkg/_version.py", "pkg/_speed.cpython-311-x86_64-linux-gnu.so", "_version.py",
                "build/lib/pkg/__init__.py", "pkg/__pycache__/x.py"):  # fmt: skip
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("", encoding="utf-8")
    assert inside.setup_files(repo) == [
        "pkg/_speed.cpython-311-x86_64-linux-gnu.so",
        "pkg/_version.py",
    ]


# --- hidden test ids and checks (pure) ------------------------------------------------------------


@pytest.mark.parametrize(
    ("test_id", "rootdir", "expected"),
    [
        ("tests/test_x.py::test_a", ".", "tests.test_x::test_a"),
        ("tests/test_x.py::TestA::test_b", ".", "tests.test_x.TestA::test_b"),
        ("tests/test_x.py::TestA::TestB::test_c", ".", "tests.test_x.TestA.TestB::test_c"),
        ("tests/test_x.py::test_p[a/b::c.py]", ".", "tests.test_x::test_p[a/b::c.py]"),
        ("pkg/tests/test_x.py::test_a", "pkg", "tests.test_x::test_a"),
        ("other/test_x.py::test_a", "pkg", None),
        ("test_x.py::test_a", ".", "test_x::test_a"),
    ],
)
def test_swe_rebench_ids_map_to_the_runners_junit_ids(
    test_id: str, rootdir: str, expected: str | None
) -> None:
    assert prepare.junit_id(test_id, rootdir) == expected


def hidden(outcome: str = "failed", passed: Sequence[str] = (), failed: Sequence[str] = (),
           rootdir: str = ".") -> Hidden:  # fmt: skip
    """A hidden run whose JUnit names are the ids' names from the repo's top; `rootdir` is the
    folder the run says they are relative to."""
    junit = [prepare.junit_id(t, ".") for t in (*passed, *failed)]
    return Hidden.model_validate_json(json.dumps({
        "outcome": outcome, "rootdir": rootdir, "passed": junit[: len(passed)],
        "failed": junit[len(passed) :],
    }))  # fmt: skip


CUT = "tests/test_points.py::TestEight::test_distance[(21.7,"  # SWE-rebench's id, cut at a space
CUT_RUNS = ("tests.test_points.TestEight::test_distance[(21.7, 61.0)-0.0]",
            "tests.test_points.TestEight::test_distance[(21.7, 62.5)-1.5]")  # fmt: skip
OTHER = "tests.test_points.TestEight::test_distance[(21.75, 61.0)-0.0]"  # "(21.7," isn't its start


def junit_run(outcome: str, passed: Sequence[str] = (), failed: Sequence[str] = ()) -> Hidden:
    return Hidden.model_validate_json(
        json.dumps(
            {"outcome": outcome, "rootdir": ".", "passed": list(passed), "failed": list(failed)}
        )
    )


def test_a_truncated_id_names_every_test_it_starts() -> None:
    assert prepare.truncated(CUT) and not prepare.truncated("t.py::test_b[p q]")
    assert not prepare.truncated("t.py::test_b")
    base = junit_run("failed", failed=(*CUT_RUNS, OTHER))
    gold = junit_run("passed", passed=(*CUT_RUNS, OTHER))
    prepare.check_hidden(task("c" * 40, "x\n", "y\n", f2p=[CUT], p2p=[]),
                         base, gold, [CUT])  # fmt: skip
    assert prepare.hidden_run(gold, [CUT]).passed == {CUT}


def test_a_truncated_id_passes_only_when_every_test_it_names_passed() -> None:
    half = junit_run("failed", passed=CUT_RUNS[:1], failed=CUT_RUNS[1:])
    assert prepare.seen(half, [CUT]) == {CUT}
    assert prepare.hidden_run(half, [CUT]).passed == frozenset()
    # the one failing test it names makes it fail even when another test of the run passed
    assert prepare.hidden_run(junit_run("failed", (OTHER,), CUT_RUNS), [CUT]).passed == set()


def test_a_truncated_id_that_names_no_test_is_unmatched() -> None:
    base = junit_run("failed", failed=(OTHER,))
    gold = junit_run("passed", passed=(OTHER,))
    with pytest.raises(prepare.Excluded) as caught:
        prepare.check_hidden(task("c" * 40, "x\n", "y\n", f2p=[CUT], p2p=[]),
                             base, gold, [CUT])  # fmt: skip
    assert caught.value.reason is Reason.UNMATCHED


@pytest.mark.parametrize(
    ("outcome", "settled", "error"),
    [("passed", True, False), ("failed", True, False), ("error", True, True),
     ("no_tests", True, True), ("flaky", False, False), ("timeout", False, False),
     ("tampering", False, False)],
)  # fmt: skip
def test_hidden_runs_read_as_labels_need(outcome: str, settled: bool, error: bool) -> None:
    run = prepare.hidden_run(hidden(outcome, passed=F2P[:1]), (*F2P, *P2P))
    assert (run.applies, run.settled, run.error) == (True, settled, error)
    assert run.passed == frozenset(F2P[:1])
    assert not prepare.hidden_run(None, F2P).applies


SOME = task("c" * 40, "x\n", "y\n")


@pytest.mark.parametrize(
    ("base", "gold", "reason"),
    [
        (hidden("flaky"), hidden("passed", (*F2P, *P2P)), Reason.UNSETTLED),
        (hidden(failed=F2P), hidden("timeout"), Reason.UNSETTLED),
        (hidden(failed=F2P[:1]), hidden("passed", (F2P[0], *P2P)), Reason.UNMATCHED),
        (hidden(passed=F2P[:1], failed=F2P[1:]), hidden("passed", (*F2P, *P2P)),
         Reason.BASE_PASSES),
        (hidden(failed=F2P), hidden(passed=(*F2P,), failed=P2P), Reason.GOLD_FAILS),
        (hidden("error"), hidden("passed", (*F2P,)), Reason.GOLD_FAILS),  # P2P didn't run
        # the runner's names are under another rootdir than the ids say: nothing matches
        (hidden("error"), hidden("passed", (*F2P, *P2P), rootdir="pkg"), Reason.UNMATCHED),
    ],
)  # fmt: skip
def test_hidden_checks_exclude_with_their_reason(
    base: Hidden, gold: Hidden, reason: Reason
) -> None:
    with pytest.raises(prepare.Excluded) as caught:
        prepare.check_hidden(SOME, base, gold, (*F2P, *P2P))
    assert caught.value.reason is reason


def test_hidden_checks_pass_a_proper_task() -> None:
    # An error on base is fine: new hidden tests often can't even import there.
    prepare.check_hidden(SOME, hidden("error", failed=F2P), hidden("passed", (*F2P, *P2P)),
                         (*F2P, *P2P))  # fmt: skip


def test_plugins_are_the_projects_own_minus_the_ones_that_change_execution() -> None:
    probe = prepare.Probe.model_validate_json(json.dumps({
        "python": "3.11.4", "level": "strict", "why": "", "plugins": [
            {"name": "asyncio", "module": "pytest_asyncio.plugin", "dist": "pytest-asyncio"},
            {"name": "xdist.plugin", "module": "xdist.plugin", "dist": "pytest_xdist"},
            {"name": "cov", "module": "pytest_cov.plugin", "dist": "pytest-cov"},
            {"name": "hypothesispytest", "module": "hypothesis.extra.pytestplugin",
             "dist": "hypothesis"},
        ]}))  # fmt: skip
    before = {"pytest-asyncio": "1", "pytest-xdist": "3", "pytest-cov": "5"}
    installed = box.Installed(before, {**before, "hypothesis": "6"})
    assert prepare.choose_plugins(probe, installed) == ["pytest_asyncio.plugin"]
    assert installed.changes() == ["hypothesis - -> 6"]


def test_the_option_stubs_installed_for_never_loaded_plugins_are_loaded() -> None:
    probe = prepare.Probe.model_validate_json(json.dumps({
        "python": "3.11.4", "level": "strict", "why": "", "plugins": [
            {"name": "xdist.plugin", "module": "xdist.plugin", "dist": "pytest_xdist"},
            {"name": "cov", "module": "pytest_cov.plugin", "dist": "pytest-cov"},
        ]}))  # fmt: skip
    before = {"pytest-xdist": "3", "pytest-cov": "5"}
    installed = box.Installed(before, before, ("tracefix_stub_cov", "tracefix_stub_xdist"))
    assert prepare.choose_plugins(probe, installed) == ["tracefix_stub_cov", "tracefix_stub_xdist"]


def test_a_plugin_module_that_isnt_a_module_name_is_refused() -> None:
    bad = {"python": "3.11.4", "level": "basic", "why": "", "plugins": [
        {"name": "x", "module": "x\npytest_plugins: [evil]", "dist": "x"}]}  # fmt: skip
    with pytest.raises(ValueError):
        prepare.Probe.model_validate_json(json.dumps(bad))


# --- DockerBox, against a fake docker ------------------------------------------------------------


class FakeDocker:
    def __init__(self, replies: dict[str, bytes] | None = None, fail: str = "",
                 hang: str = "") -> None:  # fmt: skip
        self.calls: list[list[str]] = []
        self.replies, self.fail, self.hang = replies or {}, fail, hang

    def __call__(self, args: Sequence[str], timeout: float) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(list(args))
        line = " ".join(args)
        if self.hang and self.hang in line:
            raise subprocess.TimeoutExpired(line, timeout, output=b"partial")
        reply = next((v for k, v in self.replies.items() if k in line), b"")
        return subprocess.CompletedProcess(args, 1 if self.fail and self.fail in line else 0,
                                           reply, b"")  # fmt: skip


def test_the_container_gets_bubblewraps_permissions_and_limits() -> None:
    fake = FakeDocker({"test -x": b"yes\n"})
    b = box.DockerBox("swerebench/x:latest", "tfbench-x", fake)
    b.start()
    assert fake.calls[0] == ["rm", "-f", "tfbench-x"]  # one left by an interrupted run
    run = fake.calls[1]
    assert run[:2] == ["run", "-d"]
    assert "--init" in run  # reaps finished bubblewrap processes; `sleep` as PID 1 never does
    for flag in ("SYS_ADMIN", "seccomp=unconfined", "apparmor=unconfined",
                 "systempaths=unconfined"):  # fmt: skip
        assert flag in run
    assert run[run.index("--memory") + 1] == "8g"
    assert run[run.index("--pids-limit") + 1] == "4096"
    assert run[-3:] == ["sleep", "swerebench/x:latest", "infinity"]
    assert b.python == box.CONDA_PYTHON
    b.close()
    assert fake.calls[-1] == ["rm", "-f", "tfbench-x"]


def test_without_the_conda_env_the_path_python_is_used() -> None:
    fake = FakeDocker({"command -v python": b"/usr/local/bin/python\n"})
    b = box.DockerBox("img", "n", fake)
    b.start()
    assert b.python == "/usr/local/bin/python"


def test_the_api_key_goes_in_by_name_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret-value")
    fake = FakeDocker({"test -x": b"yes\n"})
    b = box.DockerBox("img", "n", fake)
    b.start()
    b.run(["python", "inside.py"], timeout=5, env_names=["ANTHROPIC_API_KEY"])
    assert fake.calls[-1][:4] == ["exec", "-e", "ANTHROPIC_API_KEY", "-w"]
    assert not any("sk-secret" in arg for call in fake.calls for arg in call)


def test_a_step_past_its_timeout_removes_the_container() -> None:
    fake = FakeDocker({"test -x": b"yes\n"}, hang="inside.py")
    b = box.DockerBox("img", "n", fake)
    b.start()
    ran = b.run(["python", "inside.py"], timeout=5)
    assert ran.code is None and ran.output == "partial"
    assert fake.calls[-1] == ["rm", "-f", "n"]


def test_docker_runs_in_a_process_group_of_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(box.subprocess, "run", fake_run)
    box.run_docker(["ps"], 5)
    assert box.own_group() and box.own_group().items() <= seen.items()


# Runs in a console of its own: a plain child and one started with own_group()'s flags, then
# Ctrl+C to the whole console (what the terminal does on Ctrl+C). Ctrl+C is switched back on
# first, as a console's first process has it (the processes that run the tests may not).
CTRL_C_CONSOLE = """
import ctypes, json, signal, subprocess, sys, time
ctypes.windll.kernel32.SetConsoleCtrlHandler(None, False)
signal.signal(signal.SIGINT, signal.SIG_IGN)
child = [sys.executable, "-c", "import time; time.sleep(60)"]
plain = subprocess.Popen(child, stdin=subprocess.DEVNULL)
grouped = subprocess.Popen(child, stdin=subprocess.DEVNULL, creationflags=int(sys.argv[2]))
time.sleep(1)
ctypes.windll.kernel32.GenerateConsoleCtrlEvent(0, 0)
deadline = time.monotonic() + 10
while plain.poll() is None and time.monotonic() < deadline:
    time.sleep(0.1)
alive = {"plain": plain.poll() is None, "grouped": grouped.poll() is None}
plain.kill(); grouped.kill()
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(alive, f)
"""


@pytest.mark.skipif(sys.platform != "win32", reason="Windows' console Ctrl+C (NOTES 38)")
def test_ctrl_c_in_the_terminal_does_not_reach_a_child_in_its_own_group(tmp_path: Path) -> None:
    script, out = tmp_path / "console.py", tmp_path / "alive.json"
    script.write_text(CTRL_C_CONSOLE, encoding="utf-8")
    flags = box.own_group()["creationflags"]
    hidden = subprocess.STARTUPINFO()
    hidden.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # wShowWindow 0: SW_HIDE
    console = subprocess.Popen([sys.executable, str(script), str(out), str(flags)],
                               creationflags=subprocess.CREATE_NEW_CONSOLE,
                               startupinfo=hidden)  # fmt: skip
    assert console.wait(timeout=60) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {"plain": False, "grouped": True}


ON_311 = {"test -x": b"yes\n", "version_info": b"3.11\n"}  # the conda env's Python is 3.11


def pip_list(**versions: str) -> bytes:
    return json.dumps([{"name": k, "version": v} for k, v in versions.items()]).encode()


def test_install_records_what_pip_changed_and_fails_in_our_words(tmp_path: Path) -> None:
    wheel = tmp_path / "tracefix-0.0.1-py3-none-any.whl"
    wheel.write_bytes(b"")
    fake = FakeDocker({**ON_311, "pip list": pip_list(Typing_Extensions="4.15")})
    b = box.DockerBox("img", "n", fake)
    b.start()
    installed = b.install(wheel)
    assert installed.before == {"typing-extensions": "4.15"}
    assert any(c[0] == "cp" and c[-1] == "n:/opt/tfbench/" + wheel.name for c in fake.calls)
    failing = FakeDocker({**ON_311, "pip list": pip_list()}, fail="pip install")
    b = box.DockerBox("img", "n", failing)
    b.start()
    with pytest.raises(box.BoxError, match=r"^pip could not install Tracefix"):
        b.install(wheel)


SITE = "/opt/conda/envs/testbed/lib/python3.11/site-packages"


def test_install_puts_an_option_stub_beside_each_never_loaded_plugin(tmp_path: Path) -> None:
    wheel = tmp_path / "tracefix-0.0.1-py3-none-any.whl"
    wheel.write_bytes(b"")
    listed = pip_list(**{"pytest-xdist": "3.6", "pytest_cov": "6.0", "pytest-mock": "3"})
    fake = FakeDocker({**ON_311, "pip list": listed, "sysconfig": SITE.encode()})
    b = box.DockerBox("img", "n", fake)
    b.start()
    installed = b.install(wheel)
    assert installed.stubs == ("tracefix_stub_cov", "tracefix_stub_xdist")
    copied = [(c[1], c[2]) for c in fake.calls if c[0] == "cp"]
    for module in installed.stubs:
        assert (str(box.STUBS / f"{module}.py"), f"n:{SITE}/{module}.py") in copied


def test_install_puts_no_stub_when_the_project_has_neither_plugin(tmp_path: Path) -> None:
    wheel = tmp_path / "tracefix-0.0.1-py3-none-any.whl"
    wheel.write_bytes(b"")
    fake = FakeDocker({**ON_311, "pip list": pip_list(**{"pytest-mock": "3"})})
    b = box.DockerBox("img", "n", fake)
    b.start()
    assert b.install(wheel).stubs == ()
    assert not any("sysconfig" in " ".join(c) for c in fake.calls)


@pytest.mark.parametrize("site", ["", "site-packages", "/a/../../etc", "/a b", "/a\n/b"])
def test_a_site_packages_folder_that_isnt_a_plain_path_is_refused(
    tmp_path: Path, site: str
) -> None:
    wheel = tmp_path / "tracefix-0.0.1-py3-none-any.whl"
    wheel.write_bytes(b"")
    listed = pip_list(**{"pytest-xdist": "3.6"})
    fake = FakeDocker({**ON_311, "pip list": listed, "sysconfig": site.encode()})
    b = box.DockerBox("img", "n", fake)
    b.start()
    with pytest.raises(box.BoxError, match="site-packages"):
        b.install(wheel)
    assert not any(c[0] == "cp" and "tracefix_stub" in c[1] for c in fake.calls)


def below_311(tmp_path: Path, **replies: bytes) -> tuple[Path, dict[str, bytes]]:
    wheel = tmp_path / "wheel" / "tracefix-0.0.1-py3-none-any.whl"
    wheel.parent.mkdir()
    wheel.write_bytes(b"")
    (wheel.parent / box.PINS).write_text("hypothesis==6.150.0\n", encoding="utf-8")
    return wheel, {"test -x": b"yes\n", "version_info": b"3.9\n", "pip list": pip_list(),
                   **replies}  # fmt: skip


def test_below_311_tracefix_gets_an_environment_of_its_own(tmp_path: Path) -> None:
    """Plan C4: uv (pinned, in a folder of its own), uv's Python 3.11, uv.lock's versions, the
    wheel alone; Hypothesis into the project's environment only because it had none. inside.py
    then runs with Tracefix's interpreter, and the project's is named for every run."""
    wheel, replies = below_311(tmp_path)
    fake = FakeDocker(replies, fail=box.HAS_HYPOTHESIS)
    b = box.DockerBox("img", "n", fake)
    b.start()
    b.install(wheel)
    lines = [" ".join(c) for c in fake.calls]
    env = "/opt/tfbench/env"
    expected = [
        f"--target /opt/tfbench/uv uv=={box.UV_VERSION}",
        f"/opt/tfbench/uv/bin/uv venv --quiet --no-project --python-preference only-managed "
        f"--python 3.11 {env}",
        f"uv pip install --quiet --python {env}/bin/python -r /opt/tfbench/{box.PINS}",
        f"uv pip install --quiet --python {env}/bin/python --no-deps /opt/tfbench/{wheel.name}",
        f"{box.CONDA_PYTHON} -m pip install --no-input --quiet --disable-pip-version-check "
        f"--root-user-action=ignore {box.HYPOTHESIS}",
    ]
    found = [next(i for i, line in enumerate(lines) if want in line) for want in expected]
    assert found == sorted(found)  # each step, in this order
    assert box.HYPOTHESIS == "hypothesis>=6.141"
    assert not any(f"{box.CONDA_PYTHON} -m pip install" in line and wheel.name in line
                   for line in lines)  # fmt: skip
    assert (b.python, b.project_python) == (f"{env}/bin/python", box.CONDA_PYTHON)


@pytest.mark.parametrize(("version", "code"), [
    (None, 1), ((6, 119, 3), 1), ((6, 140, 9), 1), ((6, 141, 0), 0), ((6, 150, 2), 0),
    ((7, 0, 0), 0),
])  # fmt: skip
def test_the_hypothesis_check_passes_only_from_the_oldest_tested_version(
    tmp_path: Path, version: tuple[int, int, int] | None, code: int
) -> None:
    """The slice 2 smoke run: SWE-rebench images ship Hypothesis 6.119.3, which only an
    "is it importable" check let through, so Break My Fix never ran there."""
    pkg = tmp_path / "hypothesis"
    if version is not None:
        pkg.mkdir()
        (pkg / "__init__.py").write_text(f"__version_info__ = {version!r}\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(tmp_path)}
    blocked = "import sys; sys.modules['hypothesis'] = None; "  # hides an installed one
    script = box.HAS_HYPOTHESIS if version is not None else blocked + box.HAS_HYPOTHESIS
    done = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True,
                          check=False)  # fmt: skip
    assert done.returncode == code, done.stderr


def test_below_311_hypothesis_is_left_alone_when_the_project_has_one(tmp_path: Path) -> None:
    wheel, replies = below_311(tmp_path)
    fake = FakeDocker(replies)
    b = box.DockerBox("img", "n", fake)
    b.start()
    b.install(wheel)
    assert not any("hypothesis>=" in " ".join(c) for c in fake.calls)


@pytest.mark.parametrize(("step", "words"), [
    ("uv==", "pip could not install uv"),
    ("venv", "could not install Python 3.11 for Tracefix's own environment"),
    ("-r /opt", "could not install Tracefix's dependencies"),
    ("--no-deps", "could not install Tracefix for"),
    ("hypothesis>=", "pip could not install Hypothesis"),
])  # fmt: skip
def test_below_311_a_failed_step_fails_in_our_words(tmp_path: Path, step: str, words: str) -> None:
    wheel, replies = below_311(tmp_path)
    fake = FakeDocker(replies, fail=step if step != "hypothesis>=" else "hypothesis")
    b = box.DockerBox("img", "n", fake)
    b.start()
    with pytest.raises(box.BoxError, match=words):
        b.install(wheel)


def test_below_311_without_the_pinned_versions_nothing_is_installed(tmp_path: Path) -> None:
    wheel, replies = below_311(tmp_path)
    (wheel.parent / box.PINS).unlink()
    fake = FakeDocker(replies)
    b = box.DockerBox("img", "n", fake)
    b.start()
    with pytest.raises(box.BoxError, match=f"{box.PINS} is missing"):
        b.install(wheel)
    assert not any("uv" in " ".join(c) for c in fake.calls)


@pytest.mark.parametrize("printed", [b"", b"3", b"Python 3.9.1", b"3.9\n3.10"])
def test_a_version_that_isnt_one_is_refused(tmp_path: Path, printed: bytes) -> None:
    wheel, replies = below_311(tmp_path, version_info=printed)
    b = box.DockerBox("img", "n", FakeDocker(replies))
    b.start()
    with pytest.raises(box.BoxError, match="printed no version"):
        b.install(wheel)


def test_every_request_names_the_projects_interpreter(tmp_path: Path) -> None:
    seen: list[dict[str, object]] = []

    def answer(command: str, request: dict[str, object], b: bench_fakes.FakeBox) -> object:
        seen.append(request)
        return bench_fakes.PROBE

    b = bench_fakes.FakeBox(tmp_path / "box", answer)
    s = session(b, tmp_path)
    s.call("probe", {})
    b.project_python = "/opt/conda/envs/testbed/bin/python"
    s.call("probe", {})
    assert seen == [{}, {"python": "/opt/conda/envs/testbed/bin/python"}]


def test_a_project_python_tracefix_refuses_excludes_the_task(tmp_path: Path) -> None:
    refused = {**bench_fakes.PROBE, "python": "", "unusable": "the project's Python is 3.8"}
    b = bench_fakes.FakeBox(tmp_path / "box", faulty("probe", refused))
    found = prepare.prepare(session(b, tmp_path), bench_fakes.task(), WHEEL)
    assert found.excluded is Reason.PYTHON_UNUSABLE
    assert found.detail == "the project's Python is 3.8"


def added(path: str, text: str) -> str:
    """A git diff that adds one file."""
    lines = text.splitlines(keepends=True)
    body = "".join(f"+{line}" for line in lines)
    return (f"diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n"
            f"+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n{body}")  # fmt: skip


def test_a_python_39_project_is_prepared_and_verified_with_its_own_interpreter(
    built: dict[str, Path], tmp_path: Path
) -> None:
    """Plan C4 in a LocalBox: Tracefix on this interpreter, the project's tests on a 3.9 venv.
    py39_partial's package imports `Iterable` from `collections`, so any step that ran its
    tests on this interpreter would fail. Prepare's probe, suite and hidden runs, then verify
    with the recorded answers (the fixture's known COUNTEREXAMPLE, ordinal(111))."""
    python = str(old_python("3.9"))
    repo = built["py39_partial"]
    oracle = make_fixtures.FIXTURES_DIR / "py39_partial" / "oracle" / "test_repro.py"
    tests = added("tests/test_hidden.py", oracle.read_text(encoding="utf-8"))
    base = make_fixtures.git(repo, "rev-parse", "base").strip()
    t = task(base, raw_diff(repo, "base", "head"), tests,
             f2p=("tests/test_hidden.py::test_teens_take_th",), p2p=())  # fmt: skip
    s = session(box.LocalBox(repo, "base", tmp_path / "box", python), tmp_path)
    ready = prepare.prepare(s, t, WHEEL)
    assert ready.excluded is None, (ready.excluded, ready.detail)
    assert ready.python.startswith("3.9.")
    issue = (make_fixtures.FIXTURES_DIR / "py39_partial" / "ISSUE.md").read_text(encoding="utf-8")
    run = prepare.verify(s, ready, issue, "gold", "gold-r1", tmp_path / "out", RECORDINGS,
                         mode="replay")  # fmt: skip
    assert run.exit_code == 0 and run.out is not None
    receipt = json.loads((run.out / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["isolation"]["python"].startswith("3.9."), receipt["isolation"]
    assert receipt["level"] == "COUNTEREXAMPLE", receipt["level_reasons"]


@pytest.mark.parametrize("printed", ["", "[1]", '{"name": "x"}', '[{"name": "x", "version": 1}]'])
def test_pip_list_output_is_checked(printed: str) -> None:
    with pytest.raises(box.BoxError):
        box.packages(printed)


def test_a_folder_is_never_copied_into_one_that_exists(tmp_path: Path) -> None:
    fake = FakeDocker()
    b = box.DockerBox("img", "n", fake)
    (tmp_path / "out").mkdir()
    with pytest.raises(box.BoxError, match="exists already"):
        b.get("/opt/tfbench/out", tmp_path / "out")
    assert fake.calls == []


# --- the run steps, end to end on the partial_fix fixture ----------------------------------------


def test_verify_the_partial_fix_then_replay_its_finding_on_gold(
    built: dict[str, Path], tmp_path: Path
) -> None:
    """Recorded model answers (the --config adds no model settings, so the M8 recordings match);
    everything else is real. The partial fix's counterexample (parse_port('')) is `fixed` on a
    gold fix that also handles a blank PORT."""
    repo = built["partial_fix"]
    partial = raw_diff(repo, "base", "head")
    gold = partial.replace("+    if raw is None:\n", "+    if raw is None or not raw.strip():\n")
    assert gold != partial
    base = make_fixtures.git(repo, "rev-parse", "base").strip()
    t = task(base, gold, partial)
    s = session(box.LocalBox(repo, "base", tmp_path / "box"), tmp_path)
    s.box.put(prepare.INSIDE, s.box.path("inside.py"))
    made = prepare.make_commits(s, t, {"gold": gold, "v0": partial}, hidden_tests=True)
    assert made.commits["gold"] and made.commits["v0"]
    ready = Prepared(instance_id=t.instance_id, excluded=None, suite_timeout=120)
    issue = (make_fixtures.FIXTURES_DIR / "partial_fix" / "ISSUE.md").read_text(encoding="utf-8")
    run = prepare.verify(s, ready, issue, "v0", "v0-r1", tmp_path / "out", RECORDINGS,
                         mode="replay")  # fmt: skip
    assert run.exit_code == 0 and run.out is not None and run.seconds > 0
    receipt = json.loads((run.out / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["level"] == "COUNTEREXAMPLE", receipt["level_reasons"]
    replayed = prepare.replay(s, ready, "v0-r1")
    assert replayed.status is PreviousStatus.REPLAYED
    assert replayed.findings and all(f.result is Replay.FIXED for f in replayed.findings)


def faulty(command: str, reply: object) -> bench_fakes.Answer:
    """inside.py with one command answering `reply`, the rest as a proper task would."""
    hidden = {"outcome": "failed", "failed": ["tests.test_calc::test_a"], "tests": 1}
    good: dict[str, object] = {
        "probe": bench_fakes.PROBE,
        "commits": {"commits": bench_fakes.COMMITS,
                    "with_tests": {"base": "1" * 40, "gold": "2" * 40}},
        "suite": {"status": "ok", "outcome": "passed", "seconds": 1.0, "tests": 3},
        "hidden": {"base": hidden, "gold": {**hidden, "outcome": "passed", "failed": [],
                                            "passed": hidden["failed"]}},
        "functions": {"v0": [{"path": "pkg/calc.py", "function": "double"}]},
    }  # fmt: skip
    return lambda c, request, b: reply if c == command else good[c]


@pytest.mark.parametrize(
    ("command", "reply"),
    [
        ("probe", {**bench_fakes.PROBE, "extra": 1}),
        ("suite", {"status": "ok", "outcome": "passed", "seconds": "1.0"}),
        ("suite", {"status": "ok", "outcome": "passed", "seconds": 1.0, "module": "a b"}),
        ("hidden", {"base": {"outcome": "failed"}}),  # gold's run is missing
        ("hidden", ["not", "a", "mapping"]),
        ("functions", {"v1": []}),  # not the pair asked for
        ("functions", {"v0": [{"path": "pkg/calc.py"}]}),
        ("functions", {"v0": [{"path": "a\nb", "function": None}]}),
    ],
)
def test_an_answer_the_harness_does_not_expect_is_a_harness_error(
    tmp_path: Path, command: str, reply: object
) -> None:
    """The box ran the project's code: one malformed answer excludes that task, in our own
    words, and never stops the whole prepare run."""
    b = bench_fakes.FakeBox(tmp_path / "box", faulty(command, reply))
    found = prepare.prepare(session(b, tmp_path), bench_fakes.task(), WHEEL)
    assert found.excluded is Reason.HARNESS_ERROR
    assert found.detail == f"{command}'s result is not what the harness expects"


def test_a_well_formed_functions_answer_is_recorded_on_its_variant(tmp_path: Path) -> None:
    b = bench_fakes.FakeBox(tmp_path / "box", faulty("none", None))
    found = prepare.prepare(session(b, tmp_path), bench_fakes.task(), WHEEL)
    assert found.excluded is None, found.detail
    assert [v.functions for v in found.variants] == [(touched("double"),), None]  # v1: no commit


def test_code_outside_every_function_and_test_files_are_told_apart(tmp_path: Path) -> None:
    """M11 S2: inside.touched on real commits. A class attribute is code outside every
    function (None); a method is its qualname; a test file's change is left out."""
    source = "class Shelf:\n    size = 1\n\n    def put(self):\n        return 1\n"
    repo = make_repo(tmp_path / "repo", [
        {"pkg/shelf.py": source, "tests/test_shelf.py": "def test_a():\n    pass\n"},
        {"pkg/shelf.py": source.replace("size = 1", "size = 2").replace("return 1", "return 2"),
         "tests/test_shelf.py": "def test_a():\n    assert True\n"},
    ])  # fmt: skip
    found = inside.touched(repo, "c0", "c1")
    assert found == [{"path": "pkg/shelf.py", "function": None},
                     {"path": "pkg/shelf.py", "function": "Shelf.put"}]  # fmt: skip
    assert inside.touched(repo, "c1", "c1") == []
    assert inside.functions({"repo": str(repo), "pairs": {"x": ["c0", "c1"]}}) == {"x": found}


# --- M11 S0: the adversary live, every other role replayed --------------------------------------


def request(role: Role, text: str = "q") -> LLMRequest:
    return LLMRequest(role, "claude-opus-5-5", "system", (Message("user", text),), {})


def test_adversary_live_sends_the_adversary_live_and_replays_the_rest(tmp_path: Path) -> None:
    """The adversary's call goes live even when an answer is recorded; any other role's
    recorded answer is replayed, and a role with none goes live and is recorded."""
    RecordingProvider(FakeProvider(["old adversary"]), tmp_path).send(request("adversary"))
    RecordingProvider(FakeProvider(["old judge"]), tmp_path).send(request("judge"))
    live = FakeProvider(["new adversary", "new reproducer"])
    provider = inside.provider("adversary_live", tmp_path, lambda: live)
    assert provider.send(request("adversary")).text == "new adversary"
    assert provider.send(request("judge")).text == "old judge"
    assert provider.send(request("reproducer")).text == "new reproducer"
    assert [r.role for r in live.requests] == ["adversary", "reproducer"]
    replayed = RecordedProvider(tmp_path)  # what a later replay of this folder answers
    assert replayed.send(request("reproducer")).text == "new reproducer"
    assert replayed.send(request("adversary")).text == "new adversary"


def test_anchored_replays_every_role_and_goes_live_only_on_a_new_request(tmp_path: Path) -> None:
    """Unlike adversary_live, the adversary's recorded answer is replayed too. A new request goes
    live once and is recorded, so the same request again costs nothing."""
    RecordingProvider(FakeProvider(["old adversary"]), tmp_path).send(request("adversary"))
    RecordingProvider(FakeProvider(["old judge"]), tmp_path).send(request("judge"))
    live = FakeProvider(["new adversary"])
    provider = inside.provider("anchored", tmp_path, lambda: live)
    assert provider.send(request("adversary")).text == "old adversary"
    assert provider.send(request("judge")).text == "old judge"
    assert live.requests == []
    assert provider.send(request("adversary", "a changed prompt")).text == "new adversary"
    assert provider.send(request("adversary", "a changed prompt")).text == "new adversary"
    assert [r.role for r in live.requests] == ["adversary"]
    replayed = RecordedProvider(tmp_path)  # what a later replay of this folder answers
    assert replayed.send(request("adversary", "a changed prompt")).text == "new adversary"


def test_the_modes_pick_their_providers_and_replay_never_goes_live(tmp_path: Path) -> None:
    def no_api() -> FakeProvider:
        raise AssertionError("replay made an API client")

    assert isinstance(inside.provider("replay", tmp_path, no_api), RecordedProvider)
    assert isinstance(inside.provider("live", tmp_path, lambda: FakeProvider([])),
                      RecordingProvider)  # fmt: skip
    with pytest.raises(ValueError, match="unknown mode"):
        inside.provider("both", tmp_path, no_api)
    with pytest.raises(MissingRecording):
        inside.provider("replay", tmp_path, no_api).send(request("judge"))

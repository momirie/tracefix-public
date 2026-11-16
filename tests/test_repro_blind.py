"""The blind shadow test (M11 S7, NOTES 42): written without seeing the fix, report only.

Real pytest runs in real copies; only the model's answers are scripted.
"""

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import make_fixtures
import pytest
from conftest import make_repo
from synthetic import guard, l4_run, repro, stage

from tracefix.diffscope import compute_scope
from tracefix.guard import GuardStatus
from tracefix.isolation import TamperingDetected
from tracefix.ladder import EvidenceLevel, level
from tracefix.llm import FakeProvider, LLMClient
from tracefix.prompts import reproducer
from tracefix.receipt import build, summary_facts
from tracefix.receipt_md import render
from tracefix.record import BLIND, RunRecord
from tracefix.repro import (
    BLIND_ATTEMPTS,
    BlindResult,
    BlindStatus,
    ReproStatus,
    Verdict,
    blind,
    build_blind_context,
    build_context,
    class_source,
    repro_test_path,
)
from tracefix.sandbox import sandbox_level
from tracefix.workspace import Workspace, git

ISSUE = "Pagination drops the last partial page."
IMPORT = "from pager.pagination import total_pages\n\n"
# total_pages(10, 3) is 3 at base and 4 at head.
GOOD = IMPORT + "def test_partial():\n    assert total_pages(10, 3) == 4\n"
PASSES_ON_BASE = IMPORT + "def test_exact():\n    assert total_pages(9, 3) == 3\n"
ALWAYS_FAILS = IMPORT + "def test_wrong():\n    assert total_pages(10, 3) == 5\n"
PARTLY = GOOD + "\ndef test_wrong():\n    assert total_pages(10, 3) == 5\n"
DIFFERENT = (
    IMPORT + "def test_x():\n    n = total_pages(10, 3)\n    if n == 4:\n"
    "        raise ValueError('after')\n    assert n == 4\n"
)
SKIPS_ON_HEAD = (
    "import pytest\n" + IMPORT + "def test_x():\n    n = total_pages(10, 3)\n    if n == 4:\n"
    "        pytest.skip('after')\n    assert n == 4\n"
)
NEW_NAME = "def test_new_name():\n    from pager.pagination import ceil_pages\n"
USES_SUBPROCESS = "import subprocess\n\ndef test_x():\n    assert False\n"


def answer(code: str) -> dict[str, str]:
    return {"test_code": code, "rationale": "scripted"}


@pytest.fixture
def good_ws(built: dict[str, Path]) -> Iterator[Workspace]:
    with Workspace(built["good_fix"], "base", "head") as ws:
        yield ws


def main_test(ws: Workspace) -> object:
    return replace(repro(), test_path=repro_test_path(ws, None))


def run_blind(ws: Workspace, *answers: str, **client_args: int) -> tuple[BlindResult, FakeProvider]:
    fake = FakeProvider([answer(code) for code in answers])
    client = LLMClient(fake, **client_args)  # type: ignore[arg-type]
    scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
    return blind(ws, scope, main_test(ws), ISSUE, client), fake  # type: ignore[arg-type]


# --- what it shows on head ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "status"),
    [
        (GOOD, BlindStatus.REPRODUCED),
        (ALWAYS_FAILS, BlindStatus.FAILS_ON_HEAD),
        (PARTLY, BlindStatus.FAILS_ON_HEAD),
        (DIFFERENT, BlindStatus.FAILS_DIFFERENTLY),
        (SKIPS_ON_HEAD, BlindStatus.HEAD_NOT_CLEAN),
    ],
)
def test_a_test_that_fails_properly_on_base_is_classified_by_its_head_run(
    good_ws: Workspace, code: str, status: BlindStatus
) -> None:
    result, fake = run_blind(good_ws, code, GOOD)
    assert result.status is status, result.reason
    assert result.test_code == code and len(result.attempts) == 1
    assert result.attempts[0].head is not None
    assert result.test_path.endswith("test_tracefix_blind.py")
    assert len(fake.requests) == 1  # head was run, so the model is asked nothing more


@pytest.mark.parametrize("code", [PASSES_ON_BASE, NEW_NAME, USES_SUBPROCESS])
def test_a_test_that_never_fails_properly_on_base_never_reaches_head(
    good_ws: Workspace, code: str
) -> None:
    """NEW_NAME's ImportError is raised in the blind file: it uses something only a fix adds."""
    result, fake = run_blind(good_ws, code, code)
    assert result.status is BlindStatus.NOT_REPRODUCED_ON_BASE, result.reason
    assert len(result.attempts) == BLIND_ATTEMPTS == len(fake.requests)
    assert all(a.head is None for a in result.attempts)
    assert result.test_code == code


def test_a_second_attempt_can_recover_and_its_feedback_holds_base_results_only(
    good_ws: Workspace,
) -> None:
    result, fake = run_blind(good_ws, PASSES_ON_BASE, GOOD)
    assert result.status is BlindStatus.REPRODUCED
    assert [a.verdict for a in result.attempts] == [Verdict.BASE_PASSES, Verdict.REPRODUCED]
    feedback = fake.requests[1].messages[-1].content
    assert "before the fix: passed" in feedback and "after the fix:" not in feedback
    assert fake.requests[1].system == reproducer.BLIND_SYSTEM


def test_the_files_are_gone_from_both_copies_afterwards(good_ws: Workspace) -> None:
    result, _ = run_blind(good_ws, GOOD)
    assert not (good_ws.base / result.test_path).exists()
    assert not (good_ws.head / result.test_path).exists()


# --- when it doesn't run --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "main", [None, repro(ReproStatus.NOT_REPRODUCED), repro(ReproStatus.FIX_DOES_NOT_FIX)]
)
def test_it_runs_only_after_the_main_test_reproduced(good_ws: Workspace, main: object) -> None:
    fake = FakeProvider([answer(GOOD)])
    scope = compute_scope(good_ws.repo, good_ws.base_sha, good_ws.head_sha)
    result = blind(good_ws, scope, main, ISSUE, LLMClient(fake))  # type: ignore[arg-type]
    assert result.status is BlindStatus.NOT_RUN
    assert fake.requests == []


def test_an_existing_file_of_that_name_is_never_overwritten(good_ws: Workspace) -> None:
    rel = str(Path(repro_test_path(good_ws, None)).with_name("test_tracefix_blind.py"))
    (good_ws.head / rel).write_text("# the project's\n", encoding="utf-8")
    result, fake = run_blind(good_ws, GOOD)
    assert result.status is BlindStatus.NOT_RUN and "already exists" in result.reason
    assert fake.requests == []
    assert (good_ws.head / rel).read_text(encoding="utf-8") == "# the project's\n"


def test_a_model_failure_only_leaves_it_unfinished(good_ws: Workspace) -> None:
    """FakeProvider runs out of answers: a plain LLMError, as a missing recording would be."""
    result, _ = run_blind(good_ws)
    assert result.status is BlindStatus.NOT_RUN and "stopped early" in result.reason
    assert result.test_code is None


def test_the_budget_stops_it_like_any_other_call(good_ws: Workspace) -> None:
    result, fake = run_blind(good_ws, GOOD, max_calls=0)
    assert result.status is BlindStatus.NOT_RUN and "call limit" in result.reason
    assert fake.requests == []


def test_a_failure_after_a_rejected_attempt_keeps_what_was_tried(good_ws: Workspace) -> None:
    result, _ = run_blind(good_ws, PASSES_ON_BASE)
    assert result.status is BlindStatus.NOT_REPRODUCED_ON_BASE and "stopped early" in result.reason
    assert result.test_code == PASSES_ON_BASE


def test_tampering_is_not_swallowed(good_ws: Workspace) -> None:
    """The pipeline's stage runner makes the stage invalid, as for the main test."""
    target = (good_ws.head / "src" / "pager" / "pagination.py").as_posix()
    tamper = (
        IMPORT + "def test_tamper():\n"
        f"    open({target!r}, 'w').write('def total_pages(a, b): 0\\n')\n"
        "    assert total_pages(10, 3) == 4\n"
    )
    with pytest.raises(TamperingDetected) as caught:
        run_blind(good_ws, tamper, GOOD)
    wanted = "the copy under test" if sandbox_level() == "strict" else "the other copy"
    assert wanted in str(caught.value)


# --- what the model is shown ----------------------------------------------------------------------


def head_only_lines(ws: Workspace) -> list[str]:
    """Lines the fix adds to any file, in no file at base (so a coincidence can't fail this)."""
    scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
    tree = git(ws.repo, "ls-tree", "-r", "-z", "--name-only", ws.base_sha).split("\0")
    at_base = {
        line.strip()
        for path in tree
        if path
        for line in git(ws.repo, "show", f"{ws.base_sha}:{path}").splitlines()
    }
    lines: list[str] = []
    for changed in scope.files:
        if changed.status == "D":
            continue
        text = git(ws.repo, "show", f"{ws.head_sha}:{changed.path}")
        lines += [ln.strip() for ln in text.splitlines()
                  if len(ln.strip()) >= 12 and ln.strip() not in at_base]  # fmt: skip
    return lines


@pytest.mark.parametrize("case", sorted(make_fixtures.ALL_CASES))
def test_no_fixtures_blind_request_holds_the_diff_or_a_head_only_line(
    case: str, built: dict[str, Path]
) -> None:
    issue = (make_fixtures.FIXTURES_DIR / case / "ISSUE.md").read_text(encoding="utf-8")
    with Workspace(built[case], "base", "head") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        ctx, _ = build_blind_context(ws, scope, issue, "tests/test_tracefix_blind.py")
        request = reproducer.render_blind_request(ctx)
        added = head_only_lines(ws)
    assert "fix_diff" not in request and "after the fix" not in request
    assert "@@" not in request
    assert added or case == "env_broken"  # the check below has something to check
    leaks = [line for line in added if line in request and line not in issue]
    assert not leaks, leaks


def test_the_request_shows_the_code_as_it_was_and_only_its_callers_at_base(tmp_path: Path) -> None:
    base = {
        "pkg/__init__.py": "",
        "pkg/box.py": "class Box:\n    def get(self):\n        return 1\n",
        "pkg/use.py": "def use(b):\n    return b.get()\n",
    }
    head = {
        "pkg/box.py": "class Box:\n    def get(self):\n        return 2\n\n"
                      "    def size(self):\n        return 3\n",
        "pkg/use.py": "def use(b):\n    return b.get()\n\n\ndef added_caller(b):\n"
                      "    return b.get() + 1\n",
        "pkg/new.py": "def brand_new():\n    return 4\n",
    }  # fmt: skip
    repo = make_repo(tmp_path / "repo", [base, head])
    with Workspace(repo, "c0", "c1") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        ctx, _ = build_blind_context(ws, scope, ISSUE, "test_tracefix_blind.py")
    request = reproducer.render_blind_request(ctx)
    assert (
        "return 1" in request and "class Box" in request
    )  # the changed method, its added one's class
    assert "def use(b)" in request
    for head_only in ("return 2", "def size", "return 3", "added_caller", "brand_new"):
        assert head_only not in request


def test_a_renamed_file_is_read_at_its_base_path(tmp_path: Path) -> None:
    body = "".join(f"# line {n}\n" for n in range(30))
    old = body + "def f():\n    return 1\n"
    repo = make_repo(tmp_path / "repo", [
        {"pkg/__init__.py": "", "pkg/old.py": old},
        {"pkg/old.py": None, "pkg/new.py": old.replace("return 1", "return 2")},
    ])  # fmt: skip
    with Workspace(repo, "c0", "c1") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        ctx, _ = build_blind_context(ws, scope, ISSUE, "test_tracefix_blind.py")
    request = reproducer.render_blind_request(ctx)
    assert "return 1" in request and "return 2" not in request and "pkg/old.py" in request


def test_a_caller_in_a_renamed_file_is_named_for_the_commit_each_request_reads(
    tmp_path: Path,
) -> None:
    """The main request reads head and the blind one base. Any caller whose code differs between
    them is itself a changed function, and left out, so a renamed file is where they differ."""
    body = "".join(f"# line {n}\n" for n in range(30))
    use = body + "def use(b):\n    return b.get()\n"
    box = "class Box:\n    def get(self):\n        return {}\n"
    repo = make_repo(tmp_path / "repo", [
        {"pkg/__init__.py": "", "pkg/box.py": box.format(1), "pkg/use.py": use},
        {"pkg/box.py": box.format(2), "pkg/use.py": None, "pkg/moved.py": use},
    ])  # fmt: skip
    with Workspace(repo, "c0", "c1") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        shadow, _ = build_blind_context(ws, scope, ISSUE, "test_tracefix_blind.py")
        main, _ = build_context(ws, scope, ISSUE)
    assert "pkg/use.py" in [s.path for s in shadow.snippets]
    assert "pkg/moved.py" not in reproducer.render_blind_request(shadow)
    assert "pkg/moved.py" in [s.path for s in main.snippets]


def test_a_huge_class_is_cut(tmp_path: Path) -> None:
    methods = "".join(f"    def m{n}(self):\n        return {n}\n" for n in range(1_000))
    source = f"class Big:\n{methods}"
    repo = make_repo(tmp_path / "repo", [
        {"pkg/__init__.py": "", "pkg/big.py": source},
        {"pkg/big.py": source + "    def added(self):\n        return -1\n"},
    ])  # fmt: skip
    with Workspace(repo, "c0", "c1") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        ctx, notes = build_blind_context(ws, scope, ISSUE, "test_tracefix_blind.py")
    assert any("class Big truncated" in note for note in notes)
    assert all(len(s.text) < 7_000 for s in ctx.snippets)


def test_class_source_needs_every_part_to_be_a_class() -> None:
    text = "@dec\nclass A:\n    class B:\n        x = 1\n\ndef f():\n    class C:\n        pass\n"
    assert class_source(text, "A") == "@dec\nclass A:\n    class B:\n        x = 1"
    assert class_source(text, "A.B") == "    class B:\n        x = 1"
    assert class_source(text, "f") is None
    assert class_source(text, "f.C") is None
    assert class_source(text, "Missing") is None
    assert class_source("def (:\n", "A") is None


# --- no level reads it ----------------------------------------------------------------------------

RESULTS = [BlindResult(s, s.value, "t.py", "code") for s in BlindStatus]


def with_blind(run: RunRecord, result: BlindResult) -> RunRecord:
    return replace(run, stages=(*run.stages, stage(BLIND, result)))


RUNS = {
    "L4": (l4_run, EvidenceLevel.L4),
    "L1": (lambda: l4_run(guard=guard(GuardStatus.NOT_GUARDED)), EvidenceLevel.L1),
    "L0": (lambda: l4_run(reproduce=repro(ReproStatus.NOT_REPRODUCED)), EvidenceLevel.L0),
}


@pytest.mark.parametrize("name", RUNS)
@pytest.mark.parametrize("result", RESULTS, ids=lambda r: r.status.value)
def test_no_level_reads_the_blind_result(name: str, result: BlindResult) -> None:
    make, wanted = RUNS[name]
    assert level(make()).level is wanted
    assert level(with_blind(make(), result)) == level(make())


def test_a_blind_stage_that_raised_changes_no_level() -> None:
    crashed = stage(BLIND, None, status="error", error="KeyError: 'x'")
    run = replace(l4_run(), stages=(*l4_run().stages, crashed))
    assert level(run) == level(l4_run())


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path, "main", "fix")  # only named, to be masked


def test_the_receipt_shows_it_and_the_judge_never_reads_it(ws: Workspace) -> None:
    plain = build(l4_run(), ws)
    run = with_blind(l4_run(), BlindResult(BlindStatus.FAILS_ON_HEAD, "attempt 1", "t.py", "code"))
    shown = build(run, ws)
    entry = next(s for s in shown.stages if s.name == BLIND)
    assert entry.status == "fails_on_head"
    assert entry.evidence["test_file"] == "repro/test_tracefix_blind.py"
    assert entry.evidence["report_only"] is True
    assert "a test written by the model" in str(entry.evidence["oracle"])
    assert (shown.level, shown.level_reasons) == (plain.level, plain.level_reasons)
    assert summary_facts(shown) == summary_facts(plain)
    assert "| `blind` | `fails_on_head` | attempts 0, report only" in render(shown)
    assert render(plain).count("`blind`") == 0


def test_a_run_without_it_lists_nothing_as_unchecked(ws: Workspace) -> None:
    assert not [u for u in build(l4_run(), ws).unchecked if "blind" in u]


def test_a_blind_test_with_no_code_names_no_file(ws: Workspace) -> None:
    run = with_blind(l4_run(), BlindResult(BlindStatus.NOT_RUN, "no test"))
    entry = next(s for s in build(run, ws).stages if s.name == BLIND)
    assert entry.evidence["test_file"] is None

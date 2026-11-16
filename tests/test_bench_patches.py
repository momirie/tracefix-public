"""The benchmark's patches (M10 plan P4): strict diff parsing, gold-minus-one-hunk variants, and
the labels and choice made from our own hidden-test runs."""

from __future__ import annotations

import subprocess
from pathlib import Path

import make_fixtures
import pytest
from bench import data, inside, patches
from bench.patches import HiddenRun, Label, PatchError, Tried, Variant
from conftest import make_repo
from hypothesis import given
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parents[1]
F2P = ("tests/test_core.py::test_a", "tests/test_core.py::test_b")
P2P = ("tests/test_core.py::test_old",)


def git(repo: Path, *args: str, stdin: str | None = None) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=stdin.encode() if stdin is not None else None,
        env=make_fixtures.git_env(make_fixtures.BASE_DATE),
        capture_output=True,
        timeout=60,
        check=True,
    )
    return done.stdout.decode()


def numbered(n: int, prefix: str) -> str:
    return "".join(f"{prefix}{i} = {i}\n" for i in range(1, n + 1))


def edited(text: str, edits: dict[int, str]) -> str:
    """`text` with whole lines replaced (line number -> new text; "" deletes the line)."""
    lines = text.splitlines(keepends=True)
    for number, new in edits.items():
        lines[number - 1] = new
    return "".join(lines)


CORE, UTIL = numbered(40, "x"), numbered(20, "u")
CORE_EDITS = {3: "x3 = 'three'\n", 15: "x15 = 15\ny15 = 'in'\nz15 = 'in'\n", 30: ""}
UTIL_EDITS = {10: "u10 = 'ten'\n"}


@pytest.fixture(scope="module")
def toy(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    """A repo whose gold fix has 4 removable source hunks (3 in core.py, 1 in util.py), plus a
    docs hunk, a test hunk and a new source file that are never removed."""
    repo = make_repo(
        tmp_path_factory.mktemp("toy") / "repo",
        [
            {
                "src/widgets/core.py": CORE,
                "src/widgets/util.py": UTIL,
                "CHANGES.md": "# Changes\n",
                "tests/test_core.py": "def test_old():\n    pass\n",
            },
            {
                "src/widgets/core.py": edited(CORE, CORE_EDITS),
                "src/widgets/util.py": edited(UTIL, UTIL_EDITS),
                "src/widgets/new.py": "NEW = 1\n",
                "CHANGES.md": "# Changes\n- fixed widgets\n",
                "tests/test_core.py": "def test_old():\n    assert True\n",
            },
        ],
    )
    return repo, git(repo, "diff", "c0", "c1")


def without_index_lines(diff: str) -> str:
    return "".join(line for line in diff.splitlines(keepends=True) if not line.startswith("index "))


# --- parsing --------------------------------------------------------------------------------------


def test_every_slice1_patch_reads_back_byte_for_byte() -> None:
    cases = data.read_cases(ROOT / "benchmarks" / "cases" / "slice1.jsonl")
    assert cases
    for case in cases:
        for text in (case.task.patch, case.task.test_patch):
            assert patches.render(patches.parse(text)) == text, case.task.instance_id


ODD = (
    "diff --git a/src/a.py b/src/a.py\nindex 1..2 100644\n--- a/src/a.py\n+++ b/src/a.py\n"
    "@@ -0,0 +1,1 @@\n+first\n"  # a count of 1 spelled out (some real patches do)
    "@@ -5 +6,2 @@ def f():\n- old\r\n+ new\r\n+ \x0cfeed\x1c\n"  # CRLF and odd line breaks
    "@@ -9 +11 @@\n-last\n\\ No newline at end of file\n+last\n"
    "diff --git a/img.png b/img.png\nindex 1..2 100644\nGIT binary patch\nliteral 3\nKcmZ?w\n\n"
    "literal 0\nHcmV?d00001\n\n"
    "diff --git a/old.py b/src/new.py\nsimilarity index 90%\nrename from old.py\n"
    "rename to src/new.py\n--- a/old.py\n+++ b/src/new.py\n@@ -1 +1 @@\n-a\n+b\n"
    "diff --git a/run.sh b/run.sh\nold mode 100644\nnew mode 100755\n"
)


def test_odd_but_valid_patches_read_back_byte_for_byte() -> None:
    files = patches.parse(ODD)
    assert patches.render(files) == ODD
    assert [len(f.hunks) for f in files] == [3, 0, 1, 0]
    assert [f.removable for f in files] == [True, False, False, False]
    assert files[0].hunks[1].body[2] == "+ \x0cfeed\x1c\n"  # split on "\n" only


HEAD = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n"


@pytest.mark.parametrize(
    ("patch", "reason"),
    [
        ("", "doesn't end with a newline"),
        (HEAD + "@@ -1 +1 @@\n-a\n+b", "doesn't end with a newline"),
        ("From 1234 Mon Sep 17\n" + HEAD, "doesn't start with a diff header"),
        ('diff --git "a/\\303\\251.py" "b/\\303\\251.py"\n', "unreadable file paths"),
        (HEAD + "@@ -1,2 +1,2 @@\n-a\n+b\n", "shorter than its header"),
        (HEAD + "@@ -1 +1 @@\n-a\n+b\n+c\n", "neither a hunk nor a file header"),
        (HEAD + "@@ -1 +1 @@\n-a\n-b\n", "doesn't fit the hunk"),
        (HEAD + "@@ -1,2 +1,2 @@\n-a\n\n+b\n", "doesn't fit the hunk"),  # a bare empty line
        (HEAD + "@@ -1 +1 @@\n\\ No newline at end of file\n-a\n+b\n", "doesn't fit the hunk"),
        (HEAD + "@@ -1 +1 @\n-a\n+b\n", "unreadable hunk header"),
        (HEAD + "@@ -1 +1 @@\n-a\n+b\ntrailing junk\n", "neither a hunk nor a file header"),
    ],
)
def test_unreadable_patches_are_rejected_whole(patch: str, reason: str) -> None:
    with pytest.raises(PatchError, match=reason):
        patches.parse(patch)


# --- variants -------------------------------------------------------------------------------------


def test_each_variant_is_the_diff_git_prints_for_its_result(toy: tuple[Path, str]) -> None:
    repo, gold = toy
    found = patches.variants(gold)
    # A hunk's old range starts at its first context line (git diff's 3 lines of context).
    assert [(v.index, v.path, v.old_start, v.old_len) for v in found] == [
        (0, "src/widgets/core.py", 1, 6),
        (1, "src/widgets/core.py", 13, 6),
        (2, "src/widgets/core.py", 27, 7),
        (3, "src/widgets/util.py", 7, 7),
    ]
    dropped = [*CORE_EDITS, *UTIL_EDITS]  # the edit each variant leaves out, in variant order
    for variant, line in zip(found, dropped, strict=True):
        git(repo, "checkout", "--quiet", "--detach", "c0")
        git(repo, "apply", "--check", "-", stdin=variant.patch)
        git(repo, "apply", "--index", "-", stdin=variant.patch)
        printed = git(repo, "diff", "--cached", "c0")
        assert without_index_lines(printed) == without_index_lines(variant.patch)
        core = {k: v for k, v in CORE_EDITS.items() if variant.index > 2 or k != line}
        util = {k: v for k, v in UTIL_EDITS.items() if variant.index <= 2}
        assert (repo / "src/widgets/core.py").read_text() == edited(CORE, core)
        assert (repo / "src/widgets/util.py").read_text() == edited(UTIL, util)
        git(repo, "reset", "--quiet", "--hard")
        git(repo, "clean", "-fdq")


def test_only_plain_edits_of_source_files_are_dropped(toy: tuple[Path, str]) -> None:
    _, gold = toy
    for variant in patches.variants(gold):
        kept = {f.new_path: len(f.hunks) for f in patches.parse(variant.patch)}
        assert kept["CHANGES.md"] == 1
        assert kept["tests/test_core.py"] == 1
        assert kept["src/widgets/new.py"] == 1
        assert patches.source_hunks(patches.parse(variant.patch)) == 5 - 1


FILLER = "".join(f"# filler {i}\n" for i in range(8))  # keeps the hunks apart
SHELF = (
    "class Shelf:\n    size = 1\n\n" + FILLER + "\n    def put(self, x):\n        return x + 1\n"
    "\n\n" + FILLER + "\ndef take(x):\n    return x - 1\n"
)


def test_each_variant_records_the_function_its_dropped_hunk_touches(tmp_path: Path) -> None:
    """M11 S2: a variant's commit against gold's differs exactly by its dropped hunk, so
    Tracefix's diff parse (inside.touched) names the function that hunk is in, a method by its
    qualname and a class attribute as code outside every function (None)."""
    fixed = SHELF.replace("size = 1", "size = 2").replace("x + 1", "x + 2").replace("x - 1", "x")
    repo = make_repo(tmp_path / "repo", [{"pkg/shelf.py": SHELF}, {"pkg/shelf.py": fixed}])
    gold = git(repo, "diff", "c0", "c1")
    found = patches.variants(gold)
    assert len(found) == 3
    touched = []
    for variant in found:
        git(repo, "checkout", "--quiet", "--detach", "c0")
        git(repo, "apply", "--index", "-", stdin=variant.patch)
        git(repo, "commit", "--quiet", "-m", f"v{variant.index}")
        touched.append(inside.touched(repo, "HEAD", "c1"))
    assert touched == [
        [{"path": "pkg/shelf.py", "function": None}],
        [{"path": "pkg/shelf.py", "function": "Shelf.put"}],
        [{"path": "pkg/shelf.py", "function": "take"}],
    ]


def test_a_file_left_without_hunks_is_dropped(toy: tuple[Path, str]) -> None:
    _, gold = toy
    util = patches.variants(gold)[3]
    assert "src/widgets/util.py" not in {f.new_path for f in patches.parse(util.patch)}


def test_later_hunks_of_the_same_file_move_by_what_the_dropped_hunk_added() -> None:
    hunk = patches.PatchHunk(5, 1, 5, 3, "", ("-a\n", "+b\n", "+c\n", "+d\n"), (False, True))
    later = patches.PatchHunk(20, 1, 22, 1, "", ("-e\n", "+f\n"), (False, False))
    other = patches.PatchHunk(20, 1, 20, 1, "", ("-e\n", "+f\n"), (False, False))
    a = patches.FileDiff(("diff --git a/a.py b/a.py\n",), "a.py", "a.py", (hunk, later))
    b = patches.FileDiff(("diff --git a/b.py b/b.py\n",), "b.py", "b.py", (other,))
    left = patches.without((a, b), 0, 0)
    assert left[0].hunks == (patches.PatchHunk(20, 1, 20, 1, "", ("-e\n", "+f\n"), (False, False)),)
    assert left[1] == b


def test_a_fix_with_one_source_hunk_gets_no_variant() -> None:
    gold = (
        HEAD + "@@ -1 +1 @@\n-a\n+b\n"
        "diff --git a/README.md b/README.md\n--- a/README.md\n+++ b/README.md\n"
        "@@ -1 +1 @@\n-a\n+b\n"
        "diff --git a/tests/test_a.py b/tests/test_a.py\n--- a/tests/test_a.py\n"
        "+++ b/tests/test_a.py\n@@ -1 +1 @@\n-a\n+b\n"
    )
    assert patches.variants(gold) == []


def test_a_new_source_file_counts_as_part_of_the_fix_but_is_never_dropped() -> None:
    gold = (
        HEAD + "@@ -1 +1 @@\n-a\n+b\n"
        "diff --git a/b.py b/b.py\nnew file mode 100644\n--- /dev/null\n+++ b/b.py\n"
        "@@ -0,0 +1 @@\n+B = 1\n"
    )
    (only,) = patches.variants(gold)
    assert only.path == "a.py"
    assert [f.new_path for f in patches.parse(only.patch)] == ["b.py"]


def test_at_most_max_tried_hunks_are_tried_in_patch_order() -> None:
    hunks = "".join(f"@@ -{10 * i} +{10 * i} @@\n-a\n+b\n" for i in range(1, 7))
    found = patches.variants(HEAD + hunks)
    assert [v.old_start for v in found] == [10, 20, 30, 40][: patches.MAX_TRIED]
    assert [v.index for v in patches.variants(HEAD + hunks, limit=2)] == [0, 1]


# --- labels and the kept variant ------------------------------------------------------------------


def run(*passed: str, applies: bool = True, error: bool = False, settled: bool = True) -> HiddenRun:
    return HiddenRun(applies, error, frozenset(passed), settled)


@pytest.mark.parametrize(
    ("hidden", "expected"),
    [
        (run(*F2P, *P2P, applies=False), Label.DOES_NOT_APPLY),
        (run(F2P[0], settled=False), Label.UNSETTLED),  # looks partial, but proves nothing
        (run(error=True, settled=False), Label.UNSETTLED),
        (run(*F2P, *P2P, error=True), Label.BROKEN),
        (run(*P2P), Label.NO_EFFECT),
        (run(), Label.NO_EFFECT),
        (run(*F2P, *P2P), Label.HIDDEN_TESTS_PASS),
        (run(F2P[0], *P2P), Label.PARTIAL),
        (run(*F2P), Label.PARTIAL),  # a PASS_TO_PASS test broke
        (run(F2P[0], P2P[0], "tests/other.py::test_x"), Label.PARTIAL),  # a test missing from it
    ],
)
def test_labels_come_from_the_hidden_test_results(hidden: HiddenRun, expected: Label) -> None:
    assert patches.label(hidden, F2P, P2P) is expected


def test_a_task_without_fail_to_pass_tests_cannot_label() -> None:
    with pytest.raises(ValueError, match="FAIL_TO_PASS"):
        patches.label(run(), (), P2P)


def variant(index: int) -> Variant:
    return Variant(index, "a.py", 10 * index + 1, 1, f"patch {index}\n")


def test_the_kept_variant_is_partial_first_then_fewest_failing_then_hunk_order() -> None:
    assert patches.keep([]) is None
    same = [Tried(variant(1), Label.PARTIAL, 2), Tried(variant(0), Label.PARTIAL, 2)]
    assert patches.keep(same) == same[1]
    fewer = [Tried(variant(0), Label.PARTIAL, 3), Tried(variant(1), Label.PARTIAL, 1)]
    assert patches.keep(fewer) == fewer[1]
    partial = [Tried(variant(0), Label.NO_EFFECT, 1), Tried(variant(1), Label.PARTIAL, 3)]
    assert patches.keep(partial) == partial[1]
    never = [
        Tried(variant(0), Label.HIDDEN_TESTS_PASS, 0),
        Tried(variant(1), Label.DOES_NOT_APPLY, 0),
    ]
    assert patches.keep(never) is None
    assert patches.keep([*never, Tried(variant(2), Label.BROKEN, 3)]) == Tried(
        variant(2), Label.BROKEN, 3
    )


def test_tried_counts_every_hidden_test_that_did_not_pass() -> None:
    result = patches.tried(variant(0), run(F2P[0]), F2P, P2P)
    assert result == Tried(variant(0), Label.PARTIAL, 2)


@given(
    st.sets(st.sampled_from((*F2P, *P2P, "tests/other.py::t"))),
    st.booleans(),
    st.booleans(),
    st.booleans(),
)
def test_labels_match_their_definitions(
    passed: set[str], applies: bool, error: bool, settled: bool
) -> None:
    hidden = run(*passed, applies=applies, error=error, settled=settled)
    found = patches.label(hidden, F2P, P2P)
    if found in patches.USABLE:
        assert applies and settled
    failing = patches.failing(hidden, (*F2P, *P2P))
    some_fixed = bool(passed & set(F2P))
    if found in (Label.PARTIAL, Label.HIDDEN_TESTS_PASS):
        assert applies and not error and some_fixed
    if found is Label.PARTIAL:
        assert failing > 0
    if found is Label.HIDDEN_TESTS_PASS:
        assert failing == 0
    if found is Label.NO_EFFECT:
        assert applies and not error and not some_fixed


@given(
    st.lists(
        st.builds(Tried, st.integers(0, 3).map(variant), st.sampled_from(Label), st.integers(0, 5)),
        max_size=6,
    )
)
def test_the_kept_variant_is_always_incorrect_by_our_runs(candidates: list[Tried]) -> None:
    kept = patches.keep(candidates)
    usable = [t for t in candidates if t.label in patches.USABLE]
    if not usable:
        assert kept is None
        return
    assert kept in usable
    if any(t.label is Label.PARTIAL for t in usable):
        assert kept.label is Label.PARTIAL
        assert kept.failing == min(t.failing for t in usable if t.label is Label.PARTIAL)

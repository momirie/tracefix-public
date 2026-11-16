"""Property tests (Hypothesis) for the pure helpers that Guard, Integrity, the diff scope and the
Reproducer rely on: rules that must hold for every input, not just the examples in the other test
files."""

import ast
import random
from collections.abc import Iterator
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tracefix.attack_inputs import AttackTarget, Param, neighbours
from tracefix.attack_rules import (
    MIN_QUOTE,
    QUOTE_MARKS,
    CheckedProperty,
    collapse,
    expression_names,
    literal_value,
    quote_found,
    render_finding,
)
from tracefix.attack_runtime import from_source, to_source
from tracefix.diffscope import FileChange, FileKind, Hunk, innermost, parse_hunks
from tracefix.guard import changed_lines, fixed_lines, outside_fixed
from tracefix.integrity_rules import SourceText, candidates_in_tests, special_cases, without_branch
from tracefix.repro import FORBIDDEN_NAMES, _known_dirs, sanitize
from tracefix.workspace import Workspace

# Modest example counts keep the suite fast; no deadline, since parallel runs make timings noisy.
FAST = settings(max_examples=200, deadline=None)

# Source-like texts from a small set of lines, so before/after pairs share lines and diffs vary.
TEXT = st.lists(st.sampled_from(["a", "b", "c", "x = 1", "", "pass"]), max_size=8).map("\n".join)
FIXED = st.frozensets(st.integers(1, 10))


def n_lines(text: str) -> int:
    return len(text.split("\n"))


def is_subsequence(part: list[str], whole: list[str]) -> bool:
    it = iter(whole)
    return all(line in it for line in part)


# --- guard: lines an edit touched -----------------------------------------------------------------


@FAST
@given(TEXT, TEXT)
def test_changed_lines_are_lines_of_after_and_the_rest_is_kept_from_before(
    before: str, after: str
) -> None:
    changed = changed_lines(before, after)
    assert changed <= set(range(1, n_lines(after) + 1))
    kept = [line for n, line in enumerate(after.split("\n"), 1) if n not in changed]
    assert is_subsequence(kept, before.split("\n"))
    assert changed_lines(after, after) == frozenset()


@FAST
@given(TEXT, TEXT, FIXED, FIXED)
def test_outside_fixed_names_an_unfixed_line_and_more_fixed_lines_never_add_one(
    before: str, after: str, fixed: frozenset[int], more: frozenset[int]
) -> None:
    line = outside_fixed(before, after, fixed)
    if line is not None:
        assert 1 <= line <= n_lines(before) and line not in fixed
    else:
        assert outside_fixed(before, after, fixed | more) is None


@FAST
@given(TEXT, TEXT)
def test_outside_fixed_with_nothing_or_everything_fixed(before: str, after: str) -> None:
    everything = frozenset(range(1, n_lines(before) + 2))  # +1: an insertion after the last line
    assert outside_fixed(before, after, everything) is None
    assert (outside_fixed(before, after, frozenset()) is None) == (before == after)


HUNKS = st.lists(
    st.builds(Hunk, st.integers(0, 20), st.integers(0, 5), st.integers(0, 20), st.integers(0, 5)),
    max_size=4,
)


@FAST
@given(HUNKS, st.integers(0, 25))
def test_fixed_lines_are_the_fixs_head_lines_or_a_deletions_neighbours_within_the_file(
    hunks: list[Hunk], length: int
) -> None:
    change = FileChange("m.py", None, "M", FileKind.SOURCE, tuple(hunks))
    lines = fixed_lines(change, length)
    in_file = set(range(1, length + 1))
    assert lines <= in_file
    allowed: set[int] = set()
    for h in hunks:
        touched = set(h.head_lines) if h.head_len else {h.head_start, h.head_start + 1}
        allowed |= touched
        if h.head_len:
            assert touched & in_file <= lines
    assert lines <= allowed


# --- diffscope ------------------------------------------------------------------------------------

COUNT = st.none() | st.integers(0, 10_000)
HEADER = st.tuples(st.integers(0, 10**6), COUNT, st.integers(0, 10**6), COUNT)
# Lines between headers, including content that merely looks like a header.
FILLER = st.one_of(
    st.text(st.characters(blacklist_characters="\n"), max_size=20),
    st.sampled_from(["+@@ -2 +2 @@", " @@ -1 +1 @@", "diff --git a/x.py b/x.py", "-x = 1"]),
).filter(lambda s: not s.startswith("@@"))


def header(base: int, base_len: int | None, head: int, head_len: int | None) -> str:
    def count(n: int | None) -> str:
        return "" if n is None else f",{n}"

    return f"@@ -{base}{count(base_len)} +{head}{count(head_len)} @@ def f():"


@FAST
@given(st.lists(st.tuples(HEADER, st.lists(FILLER, max_size=3)), max_size=5))
def test_parse_hunks_reads_every_header_and_only_headers(
    parts: list[tuple[tuple[int, int | None, int, int | None], list[str]]],
) -> None:
    diff = "\n".join(line for h, filler in parts for line in [header(*h), *filler])
    expected = tuple(
        Hunk(b, 1 if bl is None else bl, h, 1 if hl is None else hl) for (b, bl, h, hl), _ in parts
    )
    assert parse_hunks(diff) == expected


SPANS = st.dictionaries(
    st.tuples(st.sampled_from(["f", "g", "C.m", "outer.inner"]), st.integers(0, 2)),
    st.tuples(st.integers(1, 50), st.integers(0, 30)).map(lambda t: (t[0], t[0] + t[1])),
    max_size=6,
)


@FAST
@given(SPANS, st.integers(0, 90))
def test_innermost_is_a_smallest_span_containing_the_line(
    spans: dict[tuple[str, int], tuple[int, int]], line: int
) -> None:
    key = innermost(spans, line)
    containing = {k: last - first for k, (first, last) in spans.items() if first <= line <= last}
    if not containing:
        assert key is None
    else:
        assert key in containing and containing[key] == min(containing.values())


# --- repro.sanitize: the feedback text that goes into prompts and recording keys ------------------


@pytest.fixture(scope="module")
def ws(built: dict[str, Path]) -> Iterator[Workspace]:
    with Workspace(built["good_fix"], "base", "head") as ws:
        yield ws


# Printable text without "\r" (line endings are a separate property) and without "<", so random text
# never spells a mask token.
PLAIN = st.text(st.characters(min_codepoint=32, max_codepoint=126, blacklist_characters="<"))
LINES = st.lists(PLAIN, max_size=6).map("\n".join)


def spellings(ws: Workspace) -> list[str]:
    """Each known folder plainly, with "/", and as a repr and a repr of a repr write it."""
    return [form for path, _token in _known_dirs(ws)
            for form in (path, path.replace("\\", "/"), path.replace("\\", "\\\\"),
                         path.replace("\\", "\\\\\\\\"))]  # fmt: skip


def with_known_dirs(ws: Workspace) -> st.SearchStrategy[str]:
    forms = spellings(ws)
    piece = st.one_of(PLAIN, st.sampled_from(forms), st.sampled_from(forms).map(str.upper),
                      st.just("\n"), st.just(".py:3: in f"))  # fmt: skip
    return st.lists(piece, max_size=8).map("".join)


@FAST
@given(data=st.data())
def test_sanitize_leaves_no_known_folder_and_is_stable_when_reapplied(
    ws: Workspace, data: st.DataObject
) -> None:
    text = data.draw(with_known_dirs(ws))
    clean = sanitize(text, ws)
    for form in spellings(ws):
        assert form.lower() not in clean.lower()
    assert sanitize(clean, ws) == clean


@pytest.mark.parametrize("ending", ["\r\n", "\r"])
@FAST
@given(text=LINES)
def test_sanitize_ignores_line_endings(ws: Workspace, ending: str, text: str) -> None:
    assert sanitize(text.replace("\n", ending), ws) == sanitize(text, ws)


def report(seconds: str, address: int, left: int, right: int, pad: int) -> str:
    """A pytest-like report whose durations, addresses and terminal width vary between runs."""
    return (
        f"{'=' * left} FAILURES {'=' * right}\n"
        f"E   assert <Obj object at {hex(address)}> == 1\n"
        f"test_x.py .F{' ' * pad}[ 50%]\n"
        f"{'-' * left}\n"
        f"{'=' * left} 1 failed in {seconds}s {'=' * right}\n"
    )


VARIANT = st.tuples(
    st.one_of(st.integers(0, 999).map(str), st.floats(0, 999).map(lambda f: f"{f:.2f}")),
    st.integers(0, 2**48),
    st.integers(3, 60),
    st.integers(3, 60),
    st.integers(2, 60),
)


@FAST
@given(VARIANT, VARIANT)
def test_sanitize_hides_durations_addresses_and_terminal_width(
    ws: Workspace, one: tuple[str, int, int, int, int], other: tuple[str, int, int, int, int]
) -> None:
    assert sanitize(report(*one), ws) == sanitize(report(*other), ws)


def test_sanitize_gives_the_frame_divider_the_same_text_on_every_os(ws: Workspace) -> None:
    # pytest's divider between traceback frames at COLUMNS=80: Windows is one column short and
    # adds a closing "_"; Linux fills the width and ends on the space (codespace, 12 Oct 2026:
    # method_partial's recorded feedback was missed on Linux).
    windows, linux = "_ " * 39 + "_", "_ " * 40
    report = "tests/test_x.py:5: \n{}\n\nself = <X>\n"
    assert sanitize(report.format(linux), ws) == sanitize(report.format(windows), ws)
    # The Windows text the recordings were made from is unchanged.
    assert sanitize(report.format(windows), ws) == report.format(windows)


# --- integrity: candidate rules -------------------------------------------------------------------

CHECKS = ["assert f(1) == 1", "assert f(2) == 4", "assert g('a') == 'A'", "assert h() is None",
          "assert f(3)", "assert f(1) == 1"]  # fmt: skip
# A test file as a list of tests, each a list of checks (an empty test gets `pass`).
SUITE = st.lists(st.lists(st.sampled_from(CHECKS), max_size=4), min_size=1, max_size=4)


def suite_text(suite: list[list[str]], prefix: str = "test_", spaced: bool = False) -> str:
    gap = "\n\n\n# a comment\n" if spaced else "\n\n"
    return gap.join(f"def {prefix}{i}():\n" + "".join(f"    {c}\n" for c in checks or ["pass"])
                    for i, checks in enumerate(suite))  # fmt: skip


def scan(base: str, head: str) -> list[str]:
    return [c.kind for c in candidates_in_tests(SourceText("tests/test_p.py", head, base))]


@FAST
@given(SUITE, st.randoms(use_true_random=False))
def test_layout_order_and_comments_never_make_a_test_candidate(
    suite: list[list[str]], rng: random.Random
) -> None:
    shuffled = [rng.sample(checks, len(checks)) for checks in suite]
    assert scan(suite_text(suite), suite_text(suite)) == []
    assert scan(suite_text(suite), suite_text(shuffled, spaced=True)) == []


@FAST
@given(SUITE, SUITE)
def test_only_adding_tests_never_makes_a_test_candidate(
    suite: list[list[str]], more: list[list[str]]
) -> None:
    base = suite_text(suite)
    assert scan(base, base + "\n\n" + suite_text(more, prefix="test_new_")) == []


@FAST
@given(SUITE, st.data())
def test_every_removed_check_is_reported_once(suite: list[list[str]], data: st.DataObject) -> None:
    smaller = [[c for c in checks if data.draw(st.booleans())] for checks in suite]
    removed = sum(map(len, suite)) - sum(map(len, smaller))
    assert scan(suite_text(suite), suite_text(smaller)).count("removed_assert") == removed


CONDITIONS = st.sampled_from(["year == 2100", "year >= 2100", "year in (2100, 7)", "year < 2100",
                              "year != 2100 and month", "month == 2"])  # fmt: skip
BODIES = st.sampled_from(["return 28", "return year", "pass", "return (28, 'feb')"])
BASE_DAYS = "def days(year, month):\n    return 2\n\n\ndef other(year):\n    return 2\n"


@FAST
@given(st.lists(st.tuples(CONDITIONS, BODIES), min_size=1, max_size=4))
def test_cutting_any_special_case_leaves_valid_code_and_the_rest_alone(
    branches: list[tuple[str, str]],
) -> None:
    body = "".join(f"    if {cond}:\n        {stmt}\n" for cond, stmt in branches)
    head = BASE_DAYS.replace("    return 2\n", body + "    return 2\n", 1)
    file = SourceText("src/c.py", head, BASE_DAYS, changed_lines(BASE_DAYS, head))
    found = special_cases(file, ["2100"])
    assert all(c.literal == 2100 for c in found)  # ordering never counts; 2 is in base already
    others = [ast.dump(n) for n in ast.parse(head).body if getattr(n, "name", "") == "other"]
    for c in found:
        assert c.branch is not None
        cut = without_branch(head, *c.branch)
        assert cut is not None
        tree = ast.parse(cut)  # still valid Python
        assert [ast.dump(n) for n in tree.body if getattr(n, "name", "") == "other"] == others
        assert len(cut) < len(ast.unparse(ast.parse(head)))  # something was cut


# --- break my fix: literals, neighbours, quotes, hygiene, repro files (M6) ------------------------

LITERAL = st.recursive(
    st.none()
    | st.booleans()
    | st.integers()
    | st.text()
    | st.binary()
    | st.floats(allow_nan=True, allow_infinity=True),
    lambda inner: (
        st.lists(inner, max_size=3)
        | st.tuples(inner, inner)
        | st.dictionaries(st.text(max_size=3) | st.integers(), inner, max_size=3)
        | st.frozensets(st.integers() | st.text(max_size=3), max_size=3)
    ),
    max_leaves=8,
)


def same_value(a: object, b: object) -> bool:
    """Equal, with NaN equal to NaN and the exact types the same at every level."""
    if type(a) is not type(b):
        return False
    if isinstance(a, float):
        return (a != a and b != b) or (a == b and str(a) == str(b))
    if isinstance(a, list | tuple):
        return len(a) == len(b) and all(same_value(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same_value(a[k], b[k]) for k in a)
    return a == b


@FAST
@given(LITERAL)
def test_every_plain_literal_survives_the_trip_through_its_source(value: object) -> None:
    text = to_source(value)
    if text is None:  # too long: written as nothing at all, never as something else
        return
    assert same_value(from_source(text), value)
    assert literal_value(text) == text  # canonical: reading it back changes nothing


@FAST
@given(st.integers(-(10**30), 10**30))
def test_neighbours_of_an_int_include_the_next_and_previous_but_never_itself(value: int) -> None:
    near = neighbours(value)
    assert value + 1 in near and value - 1 in near and value not in near
    assert len(near) == len(set(near))


@FAST
@given(st.text(min_size=30, max_size=80), st.data())
def test_any_long_enough_slice_of_a_text_is_found_whatever_its_whitespace(
    text: str, data: st.DataObject
) -> None:
    words = text.split()
    start = data.draw(st.integers(0, len(words)))
    part = " ".join(words[start:])
    spaced = "\n  ".join(part.split(" "))
    assert quote_found(spaced, [text]) == (len(collapse(part).strip(QUOTE_MARKS)) >= MIN_QUOTE)


@FAST
@given(
    st.sampled_from(sorted(FORBIDDEN_NAMES)),
    st.sampled_from(["{} + x", "f({})", "{}.y", "[a for a in {}]", "x.{}"]),
)
def test_hygiene_never_lets_a_forbidden_name_through(name: str, shape: str) -> None:
    with pytest.raises(ValueError):
        expression_names(shape.format(name), "x", frozenset({"x", "f", "a", name}), "target")


@FAST
@given(st.lists(LITERAL, min_size=1, max_size=3))
def test_every_repro_file_compiles_and_holds_only_literals_and_the_property(
    values: list[object],
) -> None:
    sources = [to_source(v) for v in values]
    if any(s is None for s in sources):
        return
    params = tuple(Param(f"p{i}", "positional", "", False) for i in range(len(values)))
    target = AttackTarget("t1", "m.py", "f", params, (1, 2), "def f():", "", "doc", "", "", (),
                          ("m",))  # fmt: skip
    prop = CheckedProperty("t1.p1", "t1", "returns", "n", "A claim.", "docstring", "A quote.",
                           check="result is not None")  # fmt: skip
    args = tuple((p.name, s) for p, s in zip(params, sources, strict=True) if s is not None)
    code = render_finding(1, "m", target, prop, args, {"kind": "returned", "type": "int"}).code
    tree = ast.parse(code)
    assert [type(n).__name__ for n in tree.body] == ["ImportFrom", "FunctionDef"]

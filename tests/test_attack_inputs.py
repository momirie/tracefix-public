"""M6: Break My Fix's static inputs (attack_inputs): targets, seeds, witnesses, docstring examples.

Read from git objects and `ast` only, so these tests run no code from the repos.
"""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from conftest import make_repo

from tracefix.attack_inputs import (
    AttackTarget,
    Param,
    bind_call,
    doc_examples,
    fixed_by_file,
    head_tests,
    issue_values,
    module_guess,
    neighbours,
    readme,
    seeds_for,
    select_targets,
    witness_calls,
)
from tracefix.diffscope import compute_scope
from tracefix.repro import AttemptResult, ReproResult, ReproStatus, Verdict
from tracefix.workspace import Workspace


@pytest.fixture
def open_case(built: dict[str, Path]) -> Iterator[Callable[[str], Workspace]]:
    """Opens a fixture case's Workspace; every one opened is cleaned up at the end."""
    opened: list[Workspace] = []

    def open_(case: str) -> Workspace:
        ws = Workspace(built[case], "base", "head").__enter__()
        opened.append(ws)
        return ws

    yield open_
    for ws in opened:
        ws.cleanup()


Opener = Callable[[str], Workspace]


def targets_of(ws: Workspace) -> list[AttackTarget]:
    targets, _, _ = select_targets(ws, compute_scope(ws.repo, ws.base_sha, ws.head_sha))
    return targets


def reproduced(code: str, path: str = "tests/test_tracefix_repro.py") -> ReproResult:
    return ReproResult(ReproStatus.REPRODUCED, "", path, code, (), ())


# --- targets on the fixtures ----------------------------------------------------------------------


def test_partial_fix_attacks_parse_port_with_what_its_module_offers(open_case: Opener) -> None:
    ws = open_case("partial_fix")
    (target,) = targets_of(ws)
    assert (target.id, target.path, target.name) == ("t1", "src/svc/config.py", "parse_port")
    assert target.params == (Param("raw", "positional", "str | None", False),)
    assert target.module_candidates == ("svc.config",)
    assert "if unset or blank, DEFAULT_PORT (8080) is used" in " ".join(target.docstring.split())
    assert target.header.startswith("def parse_port(raw: str | None) -> int:")
    names = dict(target.module_names)
    assert names["DEFAULT_PORT"] == "DEFAULT_PORT = 8080"
    assert "ConfigError" in target.class_names() and "Settings" in target.class_names()
    assert target.required == {"raw"}


def test_special_cased_grid_starts_at_the_hard_coded_year_and_tries_its_neighbours(
    open_case,
) -> None:
    ws = open_case("special_cased")
    scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
    (target,) = targets_of(ws)
    head = (ws.head / target.path).read_text(encoding="utf-8")
    seeds = seeds_for(target, head, fixed_by_file(ws, scope), "", None)
    grid = [dict(e.args) for e in seeds.examples if e.phase == "grid"]
    assert grid[0] == {"year": "2100", "month": "2"}
    assert grid[1:6] == [
        {"year": y, "month": "2"} for y in ("2101", "2099", "2200", "2000", "-2100")
    ]
    assert {"year": "2100", "month": "3"} in grid and {"year": "2100", "month": "1"} in grid
    compared = {(s.param, s.value) for s in seeds.seeds if s.compared}
    assert {("year", "2100"), ("year", "2200"), ("month", "2")} <= compared


def test_good_fix_witnesses_come_from_untouched_tests_and_the_new_test_is_advisory(
    open_case,
) -> None:
    ws = open_case("good_fix")
    scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
    targets, _, _ = select_targets(ws, scope)
    calls = witness_calls(ws, scope, targets, None)
    plain = {(c.test, c.args) for c in calls if not c.advisory}
    advisory = {(c.test, c.args) for c in calls if c.advisory}
    assert ("test_invalid_sizes", (("n_items", "5"), ("per_page", "0"))) in plain
    assert ("test_invalid_sizes", (("n_items", "-1"), ("per_page", "3"))) in plain
    assert ("test_total_pages_exact_multiple", (("n_items", "9"), ("per_page", "3"))) in plain
    assert advisory == {
        ("test_total_pages_partial_last_page", (("n_items", "10"), ("per_page", "3")))
    }
    assert all(c.file == "tests/test_pagination.py" and c.target == "t1" for c in calls)
    assert calls[0].id.startswith("tests/test_pagination.py::test_")


def test_partial_fix_witnesses_skip_the_prs_new_test_and_the_repro_test_counts(
    open_case: Opener,
) -> None:
    ws = open_case("partial_fix")
    scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
    targets, _, _ = select_targets(ws, scope)
    repro = reproduced(
        "from svc.config import parse_port\n\n\ndef test_unset():\n"
        "    assert parse_port(None) == 8080\n"
    )
    calls = witness_calls(ws, scope, targets, repro)
    plain = [dict(c.args)["raw"] for c in calls if not c.advisory and not c.repro]
    assert plain == ["'9000'", "' 443\\n'", "'0'", "'70000'"]
    assert [dict(c.args)["raw"] for c in calls if c.advisory] == ["None"]
    (from_repro,) = [c for c in calls if c.repro]
    assert (from_repro.file, from_repro.test, dict(from_repro.args)) == (
        "tests/test_tracefix_repro.py",
        "test_unset",
        {"raw": "None"},
    )


def test_a_repro_that_did_not_reproduce_gives_no_witness(open_case: Opener) -> None:
    ws = open_case("partial_fix")
    scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
    targets, _, _ = select_targets(ws, scope)
    code = "from svc.config import parse_port\n\n\ndef test_x():\n    parse_port('7')\n"
    failed = ReproResult(ReproStatus.NOT_REPRODUCED, "", "t.py", code, (), ())
    assert not [c for c in witness_calls(ws, scope, targets, failed) if c.repro]


def test_wrong_but_green_docstring_examples_are_read_from_the_prose(open_case: Opener) -> None:
    (target,) = targets_of(open_case("wrong_but_green"))
    examples = doc_examples(target)
    assert [(dict(e.args), e.expected, e.compare) for e in examples] == [
        ({"value": "-5", "width": "10"}, "0", "eq"),
        ({"value": "-15", "width": "10"}, "-10", "eq"),
    ]
    assert examples[0].quote == "bucket_of(-5, 10) == 0"


def test_the_readme_is_read_from_head(open_case: Opener) -> None:
    assert "`8080` when unset or blank" in readme(open_case("partial_fix"))
    assert readme(open_case("good_fix")) == ""


def test_issue_values_take_numbers_and_quoted_strings() -> None:
    issue = "payment_dates(2099, 12, 29, 4) gives '2100-02-29' and `x`; v1.2 is 3.5 slower"
    values = issue_values(issue)
    assert values[:4] == ["2099", "12", "29", "4"]
    assert {"2100", "3.5", "'2100-02-29'", "'x'"} <= set(values)  # numbers inside a date too
    assert "1.2" not in values  # part of "v1.2", not a number on its own


def test_partly_fixed_attempts_and_guard_survivors_become_seeds(open_case: Opener) -> None:
    ws = open_case("special_cased")
    scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
    (target,) = targets_of(ws)
    code = (
        "from billing.calendar import days_in_month\n\n\ndef test_other_centuries():\n"
        "    assert days_in_month(1900, 2) == 28\n"
    )
    attempt = AttemptResult(1, Verdict.PARTLY_FIXED, "", code, None, None)
    repro = ReproResult(ReproStatus.REPRODUCED, "", "t.py", "", (attempt,), ())
    head = (ws.head / target.path).read_text(encoding="utf-8")
    seeds = seeds_for(target, head, fixed_by_file(ws, scope), "", repro, ["month == 13"])
    evidence = [dict(e.args) for e in seeds.examples if e.phase == "evidence"]
    assert evidence == [{"year": "1900", "month": "2"}]
    assert ("month", "13") in {(s.param, s.value) for s in seeds.seeds}


# --- targets on synthetic repos -------------------------------------------------------------------

MODULE = '''\
"""A module."""
from typing import overload

LIMIT = 10


class Box:
    def size(self, n: int) -> int:
        return n

    def __repr__(self) -> str:
        return "Box"


def outer(x: int) -> int:
    def inner(y: int) -> int:
        return y
    return inner(x)


async def stream(n: int):
    yield n


def items(n: int):
    yield n


def nothing() -> int:
    return 1


def _check(value: int) -> None:
    if value < 0:
        raise ValueError(value)


def api(value: int) -> int:
    """Public entry."""
    _check(value)
    return value


def also(value: int) -> int:
    _check(value)
    return -value


@overload
def twice(x: int) -> int: ...
def twice(x):
    return x * 2
'''


def changed_everything(text: str) -> str:
    """The same module with every function body changed (an extra line each)."""
    out = []
    for line in text.splitlines():
        out.append(line)
        if (
            line.startswith("    return ")
            or line.startswith("        return ")
            or line.startswith("    yield ")
            or line.startswith("        raise ")
        ):
            indent = line[: len(line) - len(line.lstrip())]
            out.insert(len(out) - 1, f"{indent}pass  # changed")
    return "\n".join(out) + "\n"


def test_methods_are_targets_and_nested_async_generators_special_and_parameterless_are_skipped(
    tmp_path: Path,
) -> None:
    # Until M7.5 a method was skipped too ("a method: methods need an instance"); now it is a
    # target with its object, and a special method is what stays skipped. Until M11 (early) an
    # async function was skipped here too ("async functions are not attacked yet"); now it is a
    # target (test_m11_an_async_function_is_a_target), and an async generator stays skipped.
    repo = make_repo(
        tmp_path / "r",
        [{"pkg/__init__.py": "", "pkg/mod.py": MODULE}, {"pkg/mod.py": changed_everything(MODULE)}],
    )
    with Workspace(repo, "c0", "c1") as ws:
        targets, skipped, notes = select_targets(
            ws, compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        )
    reasons = {s.function: s.reason for s in skipped}
    assert "Box.size" not in reasons
    assert reasons["Box.__repr__"].startswith("a special method")
    assert reasons["outer.inner"].startswith("a nested function")
    assert reasons["stream"] == "generators are not attacked yet"
    assert reasons["items"] == "generators are not attacked yet"
    assert reasons["nothing"] == "it takes no parameters to vary"
    # Public changed functions and methods first, in file order, then the private one (its
    # public callers are already in the list).
    assert [t.qualname for t in targets] == ["Box.size", "outer", "api", "also", "twice", "_check"]
    assert not any(t.is_async for t in targets)
    size = targets[0]
    assert (size.owner, size.kind, size.name) == ("Box", "method", "size")
    assert [p.name for p in size.params] == ["n"] and size.arg_names == ("self", "n")
    assert size.owner_context.startswith("class Box:") and "def size(self, n: int)" in size.header
    assert all(t.kind == "function" and t.arg_names == tuple(p.name for p in t.params)
               for t in targets[1:])  # fmt: skip
    assert any("twice is defined 2 times" in n for n in notes)
    assert all(t.module_candidates == ("pkg.mod",) for t in targets)


def test_m11_an_async_function_is_a_target(tmp_path: Path) -> None:
    # param-1117 (M10): an async method's change closed the L3 gate ("not called yet").
    text = (
        "async def fetch(url: str) -> str:\n    return url\n\n\n"
        "class Client:\n    async def get(self, path: str) -> str:\n        return path\n"
    )
    repo = make_repo(tmp_path / "r", [{"m.py": text}, {"m.py": changed_everything(text)}])
    with Workspace(repo, "c0", "c1") as ws:
        targets, skipped, _ = select_targets(ws, compute_scope(ws.repo, ws.base_sha, ws.head_sha))
    assert not skipped
    assert [(t.qualname, t.kind, t.is_async) for t in targets] == [
        ("fetch", "function", True),
        ("Client.get", "method", True),
    ]
    assert [p.name for p in targets[1].params] == ["path"]


def test_a_changed_private_helper_brings_in_its_public_callers(tmp_path: Path) -> None:
    clean = 'def clean(s: str) -> str:\n    """Documented."""\n    return _norm(s)\n'
    base = {"m.py": "def _norm(s: str) -> str:\n    return s\n\n\n" + clean}
    head = {"m.py": "def _norm(s: str) -> str:\n    return s.strip()\n\n\n" + clean}
    repo = make_repo(tmp_path / "r", [base, head])
    with Workspace(repo, "c0", "c1") as ws:
        targets, _, _ = select_targets(ws, compute_scope(ws.repo, ws.base_sha, ws.head_sha))
    assert [(t.name, t.via) for t in targets] == [
        ("_norm", ""),
        ("clean", "a public caller of the changed _norm"),
    ]
    assert targets[1].module_candidates == ("m",)


def test_a_witness_needs_the_target_from_its_own_module_and_literal_arguments(
    tmp_path: Path,
) -> None:
    lib = "def f(x: int, *, scale: int = 1) -> int:\n    return x * scale\n"
    fixed = "def f(x: int, *, scale: int = 1) -> int:\n    return (x + 0) * scale\n"
    tests = (
        "import pkg.lib as lib\nfrom pkg import lib as again\nfrom other import f as g\n"
        "from pkg.lib import f\n\n\n"
        "def test_calls():\n    n = 3\n    f(1)\n    f(n)\n    lib.f(2, scale=3)\n    again.f(4)\n"
        "    g(5)\n    f(*[6])\n    f(7, 8)\n\n\n"
        "class TestBox:\n    def test_method(self):\n        f(x=9)\n"
    )
    files = {"pkg/__init__.py": "", "pkg/lib.py": lib, "tests/test_lib.py": tests}
    repo = make_repo(tmp_path / "r", [files, {"pkg/lib.py": fixed}])
    with Workspace(repo, "c0", "c1") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        targets, _, _ = select_targets(ws, scope)
        calls = witness_calls(ws, scope, targets, None)
    assert [(c.test, dict(c.args)) for c in calls] == [
        ("test_calls", {"x": "1"}),
        ("test_calls", {"x": "2", "scale": "3"}),
        ("test_calls", {"x": "4"}),
        ("TestBox.test_method", {"x": "9"}),
    ]
    assert calls[-1].id == "tests/test_lib.py::TestBox::test_method"
    assert not any(c.advisory for c in calls)


def test_a_test_changed_by_the_pr_is_advisory_and_an_unchanged_one_in_the_same_file_is_not(
    tmp_path: Path,
) -> None:
    base = {
        "m.py": "def f(x: int) -> int:\n    return x\n",
        "tests/test_m.py": "from m import f\n\n\ndef test_a():\n    assert f(1) == 1\n\n\n"
        "def test_b():\n    assert f(2) == 2\n",
    }
    head = {
        "m.py": "def f(x: int) -> int:\n    return x + 0\n",
        "tests/test_m.py": "from m import f\n\n\ndef test_a():\n    assert f(1) == 1\n\n\n"
        "def test_b():\n    assert f(3) == 3\n",
    }
    repo = make_repo(tmp_path / "r", [base, head])
    with Workspace(repo, "c0", "c1") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        targets, _, _ = select_targets(ws, scope)
        calls = witness_calls(ws, scope, targets, None)
    assert [(c.test, c.advisory) for c in calls] == [("test_a", False), ("test_b", True)]


@pytest.mark.parametrize(
    ("deleted", "untouched"),
    [("tests/test_old.py", True), ("tests/helpers.py", False), ("tests/conftest.py", False)],
)
def test_deleting_a_test_file_leaves_its_neighbours_untouched_but_not_a_helper(
    tmp_path: Path, deleted: str, untouched: bool
) -> None:
    base = {
        "m.py": "def f(x: int) -> int:\n    return x\n",
        "tests/test_m.py": "from m import f\n\n\ndef test_a():\n    assert f(1) == 1\n",
        deleted: "X = 1\n",
    }
    repo = make_repo(tmp_path / "r", [base, {"m.py": base["m.py"] + "# tidy\n", deleted: None}])
    with Workspace(repo, "c0", "c1") as ws:
        files = head_tests(ws, compute_scope(ws.repo, ws.base_sha, ws.head_sha))
    assert [(f.path, [(name, u) for name, _, u in f.tests]) for f in files] == [
        ("tests/test_m.py", [("test_a", untouched)])
    ]


# --- pure helpers ---------------------------------------------------------------------------------


def test_neighbours_of_hard_coded_values() -> None:
    assert neighbours(2100) == [2101, 2099, 2200, 2000, -2100]
    assert neighbours(7) == [8, 6, -7]
    assert neighbours(0) == [1, -1]
    assert neighbours("Ab ") == ["", "Ab", "AB ", "ab ", " Ab  "]
    assert neighbours(True) == [False]
    assert neighbours(None) == [] and neighbours(b"x") == [b""]
    assert neighbours(1.5) == [2.5, 0.5, -1.5, 0.0]


def test_module_guess_follows_packages_up_from_the_file() -> None:
    files = frozenset(
        {
            "src/svc/__init__.py",
            "src/svc/config.py",
            "top.py",
            "a/b/__init__.py",
            "a/b/c.py",
            "a/__init__.py",
        }
    )
    assert module_guess("src/svc/config.py", files) == "svc.config"
    assert module_guess("top.py", files) == "top"
    assert module_guess("a/b/c.py", files) == "a.b.c"
    assert module_guess("src/svc/__init__.py", files) == "svc"


PARAMS = (
    Param("a", "positional_only", "", False),
    Param("b", "positional", "", False),
    Param("c", "keyword_only", "", True),
)


@pytest.mark.parametrize(
    ("call", "expected"),
    [
        ("f(1, 2)", (("a", "1"), ("b", "2"))),
        ("f(1, b=2, c=3)", (("a", "1"), ("b", "2"), ("c", "3"))),
        ("f(1)", None),  # b is required
        ("f(a=1, b=2)", None),  # a is positional-only
        ("f(1, 2, 3)", None),  # c is keyword-only
        ("f(1, x)", None),  # not a literal
        ("f(1, 2, d=4)", None),  # no such parameter
        ("f(-1, (1, [2]))", (("a", "-1"), ("b", "(1, [2])"))),
    ],
)
def test_calls_bind_to_parameters_only_with_plain_literals(call: str, expected: object) -> None:
    import ast

    node = ast.parse(call, mode="eval").body
    assert isinstance(node, ast.Call)
    assert bind_call(node, PARAMS) == expected


def test_doctests_give_repr_and_raise_examples() -> None:
    doc = (
        "Pages.\n\n>>> total(10, 3)\n4\n>>> total(1, 0)\nTraceback (most recent call last):\n"
        "  ...\npager.PageError: no pages\n>>> total(n, 3)\n1\n>>> other(1, 2)\n3\n"
    )
    target = AttackTarget(
        "t1",
        "p.py",
        "total",
        (Param("n", "positional", "int", False), Param("per", "positional", "int", False)),
        (1, 2),
        "def total(n, per):",
        "",
        doc,
        "",
        "",
        (),
        ("p",),
    )
    examples = doc_examples(target)
    assert [(dict(e.args), e.expected, e.compare) for e in examples] == [
        ({"n": "10", "per": "3"}, "4", "repr"),
        ({"n": "1", "per": "0"}, "PageError", "raises"),
    ]
    assert examples[0].quote == ">>> total(10, 3)\n4"


def test_doctests_with_a_directive_are_skipped() -> None:
    # Verifier S2: `+ELLIPSIS` makes `[0, 1, 4, ...]` match more than its own text.
    doc = ">>> squares(5)  # doctest: +ELLIPSIS\n[0, 1, 4, ...]\n>>> squares(2)\n[0, 1]\n"
    target = AttackTarget("t1", "p.py", "squares", (Param("n", "positional", "int", False),),
                          (1, 2), "def squares(n):", "", doc, "", "", (), ("p",))  # fmt: skip
    assert [(dict(e.args), e.expected) for e in doc_examples(target)] == [({"n": "2"}, "[0, 1]")]

"""Fixed mutation rules (report only, Decided 3 Oct 2026): which edits are proposed, and where."""

import ast

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tracefix.mutation_rules import (
    KINDS,
    RERAISE_WORDS,
    RuleKind,
    body_proposals,
    return_values,
    rule_proposals,
)
from tracefix.prompts import mutator


def edits(head: str, *fixed: int) -> list[tuple[int, str]]:
    """(line, mutated line) for every rule proposal on the given fixed lines."""
    found = []
    for p in rule_proposals("m.py", head, frozenset(fixed)):
        assert p.original == head.split("\n")[p.line - 1]  # a whole-line edit
        found.append((p.line, p.replacement.strip()))
    return found


IF_LT = "def f(x):\n    if x < 3:\n        return 1\n    return 0\n"


def test_comparisons_numbers_and_if_conditions_are_mutated_in_column_order() -> None:
    assert edits(IF_LT, 2) == [
        (2, "if not (x < 3):"),
        (2, "if x <= 3:"),
        (2, "if x < 2:"),
        (2, "if x < 4:"),
    ]


def test_only_the_fixed_lines_are_touched() -> None:
    assert edits(IF_LT, 4) == [(4, "return (-1)"), (4, "return 1")]  # brackets: -1 ** 2
    assert edits(IF_LT) == []


def test_identity_membership_and_boolean_operators_swap_both_ways() -> None:
    head = "def f(a, b, c):\n    if a is None and b not in c:\n        return a is not b or c\n"
    assert edits(head, 2, 3) == [
        (2, "if not (a is None and b not in c):"),
        (2, "if a is not None and b not in c:"),
        (2, "if a is None or b not in c:"),
        (2, "if a is None and b in c:"),
        (3, "return a is b or c"),
        (3, "return a is not b and c"),
    ]


def test_a_single_flippable_comparison_is_not_also_negated() -> None:
    # `if not (x == 1)` would repeat `if x != 1`.
    head = "def f(x):\n    if x == y:\n        pass\n"
    assert edits(head, 2) == [(2, "if x != y:")]


def test_strings_comments_and_other_operators_are_left_alone() -> None:
    head = 'def f(a, b):\n    s = "a < b"  # x < y\n    return a ** b % a @ b\n'
    assert edits(head, 2, 3) == []


def test_multiplication_and_division_swap_and_floor_division_becomes_division() -> None:
    head = "x = a * b // c / d\n"
    assert edits(head, 1) == [(1, "x = a / b // c / d"), (1, "x = a * b / c / d"),
                              (1, "x = a * b // c * d")]  # fmt: skip


def test_stars_and_slashes_that_are_not_arithmetic_are_left_alone() -> None:
    head = "def f(a, /, b, *args, c, **kw):\n    return g(*args, [*a], {**kw}) * 2\n"
    assert edits(head, 1) == []
    call = "return g(*args, [*a], {**kw})"
    assert edits(head, 2) == [(2, f"{call} / 2"), (2, f"{call} * 1"), (2, f"{call} * 3")]


def test_augmented_assignments_booleans_and_loop_jumps_swap() -> None:
    head = "while True:\n    n += 1\n    m -= k\n    if n:\n        break\n    continue\n"
    assert edits(head, 1, 2, 3, 5, 6) == [
        (1, "while False:"),
        (2, "n -= 1"),
        (2, "n += 0"),
        (2, "n += 2"),
        (3, "m += k"),
        (5, "continue"),
        (6, "break"),
    ]


def test_a_not_is_dropped_and_its_if_is_not_negated_again() -> None:
    # `if not (not ok)` would only repeat `if ok`; `is not` and `not in` keep their own swaps.
    head = "def f(ok, x, xs):\n    if not ok:\n        return x is not None or x not in xs\n"
    assert edits(head, 2, 3) == [
        (2, "if ok:"),
        (3, "return x is None or x not in xs"),
        (3, "return x is not None and x not in xs"),
        (3, "return x is not None or x in xs"),
    ]


def test_plus_and_minus_include_unary_signs() -> None:
    assert edits("x = -a + b\n", 1) == [(1, "x = +a + b"), (1, "x = -a - b")]


def test_negation_columns_count_characters_not_bytes() -> None:
    head = 'def f(x):\n    if "é" < x:\n        pass\n'
    assert (2, 'if not ("é" < x):') in edits(head, 2)


def test_a_loop_in_gets_a_proposal_that_hygiene_later_rejects() -> None:
    # `for x not in xs` does not compile; Guard's hygiene check drops it (see test_guard).
    assert edits("for x in xs:\n    pass\n", 1) == [(1, "for x not in xs:")]


def test_unparseable_code_gives_no_proposals() -> None:
    assert rule_proposals("m.py", "def f(:\n", frozenset({1})) == []


def test_windows_line_endings_are_kept_on_the_edited_line() -> None:
    (p,) = rule_proposals("m.py", "x = a + b\r\ny = 1.5\r\n", frozenset({1, 2}))
    assert p.original == "x = a + b\r" and p.replacement == "x = a - b\r"


def test_a_huge_hex_literal_is_skipped_not_a_crash() -> None:
    # Verifier S1: Python won't write an integer over 4300 digits in decimal (ValueError).
    head = "def f():\n    return 0x" + "f" * 4000 + " + 1\n"
    found = edits(head, 2)  # only `+` and the `1`
    assert len(found) == 3 and all(line.startswith("return 0xfff") for _, line in found)


def test_f_strings_are_left_alone_on_every_python_version() -> None:
    # 3.12+ tokenizes the inside of f-strings, 3.11 does not: skipping it keeps mutants the same.
    assert edits('x = f"{a + b} {c:<{w - 1}}"\n', 1) == []
    assert edits('x = f"{a}" + b\n', 1) == [(1, 'x = f"{a}" - b')]


LITERALS = st.integers(0, 10**30).flatmap(
    lambda n: st.sampled_from([str(n), hex(n), oct(n), bin(n), f"{n:_}"]).map(lambda t: (n, t))
)


@settings(max_examples=200, deadline=None)
@given(LITERALS)
def test_every_integer_literal_becomes_one_more_and_one_less(case: tuple[int, str]) -> None:
    n, literal = case
    found = rule_proposals("m.py", f"x = {literal}\n", frozenset({1}))
    values = sorted(ast.literal_eval(p.replacement.removeprefix("x = ")) for p in found)
    assert values == [n - 1, n + 1]


# --- body mutants (Decided 5 Oct 2026, from cargo-mutants and PIT Descartes) -------------------


def bodies(head: str, *fixed: int) -> list[tuple[int, str, str]]:
    """(first replaced line, mutated file, description) for every body proposal."""
    found = []
    for p in body_proposals("m.py", head, frozenset(fixed)):
        start = head.index(p.original)
        found.append((p.line, head[:start] + p.replacement + head[start + len(p.original) :],
                      p.description))  # fmt: skip
    return found


ANNOTATED = '''\
def pages(n: int, per: int) -> int:
    """How many pages."""
    if per <= 0:
        raise ValueError(per)
    return (n + per - 1) // per
'''


def test_a_changed_function_body_becomes_plain_values_of_its_return_type() -> None:
    kept = 'def pages(n: int, per: int) -> int:\n    """How many pages."""\n'
    assert bodies(ANNOTATED, 5) == [
        (3, kept + "    return 0\n", "rule: body of `pages` -> `return 0`"),
        (3, kept + "    return 1\n", "rule: body of `pages` -> `return 1`"),
    ]
    assert bodies(ANNOTATED) == []  # no fixed line in it: no body mutant


@pytest.mark.parametrize(
    ("annotation", "values"),
    [
        (None, ("None",)),
        ("None", ("None",)),
        ("str", ('""', '"xyzzy"')),
        ("bool", ("True", "False")),
        ("float", ("0.0", "1.0")),
        ("list[int]", ("[]",)),
        ("typing.Dict[str, int]", ("{}",)),
        ("tuple[int, ...]", ("()",)),
        ("bytes", ('b""',)),
        ("int | None", ("None", "0")),
        ("None | str", ("None", '""')),
        ("Optional[bool]", ("None", "True")),
        ("Pages", ("None",)),
        ("'Pages'", ("None",)),
    ],
)
def test_return_values_follow_the_annotation(annotation: str | None, values: tuple[str]) -> None:
    returns = None if annotation is None else ast.parse(annotation, mode="eval").body
    assert return_values(returns) == values


def test_only_the_innermost_function_holding_a_fixed_line_is_replaced() -> None:
    head = "class C:\n    def outer(self):\n        def inner():\n            return 1\n" \
           "        return inner()\n"  # fmt: skip
    found = bodies(head, 4, 5)
    assert [(line, desc) for line, _, desc in found] == [
        (3, "rule: body of `outer` -> `return None`"),
        (4, "rule: body of `inner` -> `return None`"),
    ]
    assert found[0][1] == "class C:\n    def outer(self):\n        return None\n"


def test_bodies_that_cannot_be_cut_as_whole_lines_or_generators_are_skipped() -> None:
    head = (
        "def one(): return 1\n"
        'def doc():\n    """Only a docstring."""\n'
        'def same():\n    """Doc."""; x = 1\n'
        "def gen():\n    yield 1\n"
        "def gen_from():\n    yield from range(3)\n"
    )
    assert bodies(head, *range(1, 11)) == []


def test_a_nested_generator_does_not_make_its_outer_function_one() -> None:
    head = "def f(xs):\n    def g():\n        yield 1\n    return list(g())\n"
    assert [desc for _, _, desc in bodies(head, 4)] == ["rule: body of `f` -> `return None`"]


def test_body_mutants_keep_windows_line_endings_and_handle_async() -> None:
    head = "async def f(x) -> bool:\r\n    await x\r\n    return True\r\n"
    found = bodies(head, 3)
    assert [text for _, text, _ in found] == [
        "async def f(x) -> bool:\r\n    return True\r\n",
        "async def f(x) -> bool:\r\n    return False\r\n",
    ]


def test_unparseable_code_gives_no_body_proposals() -> None:
    assert body_proposals("m.py", "def f(:\n", frozenset({1})) == []


# --- verifier review of 5 Oct 2026 ---------------------------------------------------------------


@pytest.mark.parametrize(
    "head",
    [
        "f = lambda *a: a\n",
        "from os import *\n",
        "try:\n    pass\nexcept* ValueError:\n    pass\n",
        "def f(a, *, b):\n    return [*a], {**b}\n",
    ],
)
def test_a_star_that_is_not_multiplication_is_never_swapped(head: str) -> None:
    fixed = range(1, head.count("\n") + 1)
    assert not [line for _, line in edits(head, *fixed) if "/" in line]


def test_operands_ending_in_a_constant_keyword_or_an_f_string_are_multiplied() -> None:
    assert (1, "x = True / 2") in edits("x = True * 2\n", 1)
    assert (1, 'x = f"{a}" / 2') in edits('x = f"{a}" * 2\n', 1)  # FSTRING_END on 3.12+
    assert edits("return *a, 1\n", 1) == [(1, "return *a, 0"), (1, "return *a, 2")]


def test_a_star_starting_a_continuation_line_is_swapped() -> None:
    # Verifier N2: the token before it is a line break; the left operand is on the line above.
    assert edits("x = (a  # first\n     * b)\n", 2) == [(2, "/ b)")]


def test_a_not_at_the_end_of_a_line_is_not_dropped_and_a_dropped_not_reads_well() -> None:
    # Verifier N1 (`return (` would not compile) and N4 (the description).
    assert edits("x = (not\n     y)\n", 1, 2) == []
    (p,) = rule_proposals("m.py", "x = not y\n", frozenset({1}))
    assert p.replacement == "x = y" and p.description == "rule: drop `not`"


def test_a_bare_carriage_return_anywhere_means_no_body_mutant() -> None:
    # Verifier B1: ast counts a lone \r as a line break, split("\n") does not, so the cut went
    # past the function (or off the end of the file).
    assert bodies("def f(x):\r    y = 1\r    return y\r", 1) == []
    assert bodies('def f(x):\n    y = """a\rb"""\n    return y\nZ = 5\n', 3) == []


def test_a_one_line_body_after_a_multi_line_signature_is_skipped() -> None:
    assert bodies("def f(\n    a,\n): return a\n", 1, 2, 3) == []


def test_a_very_deep_expression_does_not_stop_body_proposals() -> None:
    # Verifier S1: a recursive walk hit the recursion limit and lost every rule mutant.
    head = "def f(x):\n    return (0\n" + " + 1\n" * 1500 + ")\n"
    assert [desc for _, _, desc in bodies(head, 2)] == ["rule: body of `f` -> `return None`"]


def test_string_annotations_are_read_like_real_ones() -> None:
    parse = ast.parse
    assert return_values(parse("'int'", mode="eval").body) == ("0", "1")
    assert return_values(parse("'list[int] | None'", mode="eval").body) == ("None", "[]")
    assert return_values(parse("'not ( valid'", mode="eval").body) == ("None",)


# --- kinds, drop_call and reraise (M11, NOTES 24; the last two from prove-your-tests) -------------


def of_kind(kind: RuleKind, head: str, *fixed: int) -> list[str]:
    """The mutated line of every proposal of `kind`, stripped."""
    found = rule_proposals("m.py", head, frozenset(fixed))
    return [p.replacement.strip() for p in found if p.kind == kind]


def test_the_ten_kinds_are_in_their_fixed_order_body_first() -> None:
    assert KINDS == ("body", "compare", "logic", "negate_if", "constant", "arithmetic",
                     "membership", "loop", "drop_call", "reraise")  # fmt: skip


@pytest.mark.parametrize(
    ("line", "kind", "mutated"),
    [
        ("x = a < b", "compare", "x = a <= b"),
        ("x = a >= b", "compare", "x = a > b"),
        ("x = a != b", "compare", "x = a == b"),
        ("x = a and b", "logic", "x = a or b"),
        ("x = a or b", "logic", "x = a and b"),
        ("x = not a", "logic", "x = a"),
        ("x = 3", "constant", "x = 2"),
        ("x = True", "constant", "x = False"),
        ("x = a + b", "arithmetic", "x = a - b"),
        ("x += a", "arithmetic", "x -= a"),
        ("x = a * b", "arithmetic", "x = a / b"),
        ("x = a // b", "arithmetic", "x = a / b"),
        ("x = a is b", "membership", "x = a is not b"),
        ("x = a is not b", "membership", "x = a is b"),
        ("x = a in b", "membership", "x = a not in b"),
        ("x = a not in b", "membership", "x = a in b"),
    ],
)
def test_every_token_edit_has_its_kind(line: str, kind: RuleKind, mutated: str) -> None:
    assert mutated in of_kind(kind, line + "\n", 1)


def test_negated_ifs_and_loop_jumps_have_their_kinds() -> None:
    head = "for x in xs:\n    if x:\n        break\n    continue\n"
    assert of_kind("negate_if", head, 2) == ["if not (x):"]
    assert of_kind("loop", head, 3, 4) == ["continue", "break"]


def test_body_mutants_have_their_kind_and_the_models_schema_has_none() -> None:
    assert {p.kind for p in body_proposals("m.py", ANNOTATED, frozenset({5}))} == {"body"}
    assert "kind" not in mutator.MutantProposal.model_json_schema()["properties"]


def test_a_one_line_call_statement_becomes_pass() -> None:
    assert of_kind("drop_call", "f(x)\n", 1) == ["pass"]
    assert of_kind("drop_call", "a.b.c(1)  # why\n", 1) == ["pass  # why"]
    assert of_kind("drop_call", "if x:\n    f(x)\n", 2) == ["pass"]
    assert of_kind("drop_call", "if x: f(x)\n", 1) == ["if x: pass"]
    assert of_kind("drop_call", "async def g():\n    await f()\n", 2) == ["pass"]
    (p,) = (p for p in rule_proposals("m.py", "f(x)\n", frozenset({1})) if p.kind == "drop_call")
    assert p.description == "rule: `f(x)` -> `pass`"


@pytest.mark.parametrize(
    "head",
    ["x = f(y)\n", "return f(y)\n", "f(y) + 1\n", "f(\n    y,\n)\n", "f\n", '"""doc"""\n',
     "def g():\n    yield f(y)\n"],
)  # fmt: skip
def test_anything_else_is_not_a_dropped_call(head: str) -> None:
    assert of_kind("drop_call", head, *range(1, head.count("\n") + 1)) == []


def test_a_dropped_call_keeps_what_shares_its_line_and_counts_characters() -> None:
    assert of_kind("drop_call", "a(); b()\n", 1) == ["pass; b()", "a(); pass"]
    assert of_kind("drop_call", 'é("é"); b()\n', 1) == ["pass; b()", 'é("é"); pass']
    assert of_kind("drop_call", "f(x)\n", 2) == []  # not a fixed line
    (p,) = rule_proposals("m.py", "f()\r\n", frozenset({1}))
    assert p.replacement == "pass\r"


HANDLER = "try:\n    f()\nexcept KeyError:\n    g()\n    h()\n"
RAISED = "raise\n    g()"


def test_a_re_raise_goes_before_the_first_statement_of_an_except_body() -> None:
    assert of_kind("reraise", HANDLER, 4) == [RAISED]
    (p,) = (p for p in rule_proposals("m.py", HANDLER, frozenset({4})) if p.kind == "reraise")
    assert p.line == 4 and p.original == "    g()"
    assert p.replacement == "    raise\n    g()" and p.description == RERAISE_WORDS
    compile(HANDLER.replace(p.original, p.replacement), "m.py", "exec")


def test_a_re_raise_needs_the_first_statement_or_the_except_line_to_be_fixed() -> None:
    assert of_kind("reraise", HANDLER, 3) == [RAISED]  # e.g. a fix that widened the except
    assert of_kind("reraise", HANDLER, 5) == []
    assert of_kind("reraise", HANDLER, 1, 2) == []


@pytest.mark.parametrize(
    "head",
    [
        "try:\n    f()\nexcept E: g()\n",  # one line
        "try:\n    f()\nexcept (E,\n        F): g()\n",  # one line, after a two-line header
        "try:\n    f()\nexcept E:\n    raise\n",  # the same code
    ],
)
def test_a_re_raise_is_skipped_where_it_has_no_line_or_changes_nothing(head: str) -> None:
    assert of_kind("reraise", head, *range(1, head.count("\n") + 1)) == []


def test_a_handler_that_raises_something_else_can_still_re_raise() -> None:
    head = "try:\n    f()\nexcept E:\n    raise V\n"
    assert of_kind("reraise", head, 4) == ["raise\n    raise V"]


def test_a_re_raise_keeps_windows_line_endings() -> None:
    head = "try:\r\n    f()\r\nexcept E:\r\n    g()\r\n"
    (p,) = (p for p in rule_proposals("m.py", head, frozenset({4})) if p.kind == "reraise")
    assert p.original == "    g()\r" and p.replacement == "    raise\r\n    g()\r"


def test_a_bare_carriage_return_means_no_edit_that_reads_ast_line_numbers() -> None:
    # Same trap as body mutants (verifier B1): `ast` counts the \r, split("\n") does not. Token
    # edits use tokenize's lines, which agree with ours.
    head = 'y = """a\rb"""\nf(x)\nif x < 1:\n    pass\n'
    fixed = frozenset({2, 3, 4})
    kinds = {p.kind for p in rule_proposals("m.py", head, fixed)}
    assert not {"negate_if", "drop_call", "reraise"} & kinds
    assert of_kind("drop_call", head.replace("\r", ""), 2) == ["pass"]  # without it: yes

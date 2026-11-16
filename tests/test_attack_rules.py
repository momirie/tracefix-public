"""M6: Break My Fix's rules (attack_rules): hygiene, the quote check, literals, dedupe, repro files.

All pure: nothing here runs repo code or a model.
"""

import ast
from typing import Any

import pytest

from tracefix.attack_inputs import AttackTarget, DocExample, Param
from tracefix.attack_rules import (
    MIN_QUOTE,
    STDLIB_MODULES,
    CheckedProperty,
    Violation,
    args_of,
    check_example,
    check_property,
    check_strategy,
    doc_property,
    expression_names,
    group_violations,
    literal_value,
    outcome_of,
    quote_found,
    read_events,
    render_finding,
    same_property,
    shadowed_stdlib,
    violation_of,
)
from tracefix.prompts.adversary import (
    ArgValue,
    ExampleProposal,
    PropertyProposal,
    StrategyProposal,
)

DOC = """Parse the PORT variable.

PORT: TCP port to listen on. Optional; if unset or blank, DEFAULT_PORT (8080) is used.
Surrounding whitespace is ignored. Raises ConfigError if the port is outside 1..65535."""

PORT = AttackTarget(
    "t1",
    "src/svc/config.py",
    "parse_port",
    (Param("raw", "positional", "str | None", False),),
    (28, 39),
    "def parse_port(raw: str | None) -> int:",
    "def parse_port(raw):\n    ...",
    DOC,
    "",
    "Service settings.",
    (
        ("DEFAULT_PORT", "DEFAULT_PORT = 8080"),
        ("ConfigError", "class ConfigError(Exception)"),
        ("parse_port", "def parse_port(raw)"),
    ),
    ("svc.config",),
)
CAL = AttackTarget(
    "t2",
    "src/billing/calendar.py",
    "days_in_month",
    (Param("year", "positional", "int", False), Param("month", "positional", "int", False)),
    (15, 22),
    "def days_in_month(year: int, month: int) -> int:",
    "",
    "Days.",
    "",
    "",
    (),
    ("billing.calendar",),
)
EVIDENCE: dict[str, dict[Any, tuple[str, ...]]] = {
    "t1": {
        "issue": ("Service crashes at startup when PORT is not set.",),
        "docstring": (DOC,),
        "comment": ("",),
        "docs": ("| `PORT` | TCP port | `8080` when unset or blank |",),
        "signature": (PORT.header,),
        "test": ("",),
    },
    "t2": {
        "issue": ("A payment on 29 Feb 2100. That date doesn't exist.",),
        "docstring": ("Return the number of days in `month` (1-12) of `year`.",),
        "comment": ("",),
        "docs": ("",),
        "signature": (CAL.header,),
        "test": ("",),
    },
}
STDLIB = frozenset({"calendar", "math"})


def proposal(**fields: Any) -> PropertyProposal:
    base: dict[str, Any] = {
        "function": "t1",
        "name": "blank",
        "kind": "returns",
        "claim": "A blank or missing PORT gives the default port.",
        "source": "docstring",
        "quote": "if unset or blank, DEFAULT_PORT (8080) is used",
        "when": "True",
        "check": "",
        "expected": "",
        "exceptions": [],
        "transform": "",
    }
    return PropertyProposal(**(base | fields))


def check(**fields: Any) -> CheckedProperty:
    return check_property(proposal(**fields), [PORT, CAL], EVIDENCE, STDLIB, "t1.p1")


# --- the quote check ------------------------------------------------------------------------------


def test_a_quote_must_appear_word_for_word_whitespace_aside() -> None:
    assert quote_found("if unset or   blank,\n DEFAULT_PORT (8080) is used", [DOC])
    assert quote_found("“if unset or blank, DEFAULT_PORT”", [DOC])  # curly quotes dropped
    assert not quote_found("if unset or empty, DEFAULT_PORT (8080) is used", [DOC])
    assert not quote_found("x" * (MIN_QUOTE - 1), ["x" * 50])  # too short to mean anything
    assert not quote_found("if unset or blank", [])


# --- properties -----------------------------------------------------------------------------------


def test_a_good_property_is_accepted_with_the_names_it_uses() -> None:
    prop = check(when="raw is None or raw.strip() == ''", expected="DEFAULT_PORT")
    assert (prop.id, prop.target, prop.kind) == ("t1.p1", "t1", "returns")
    assert prop.names == ("DEFAULT_PORT",) and prop.stdlib == ()
    assert prop.when == "raw is None or raw.strip() == ''" and prop.constrains_result
    reference = check_property(
        proposal(
            function="days_in_month",
            source="issue",
            quote="That date doesn't exist.",
            when="1 <= month <= 12 and year >= 1",
            expected="calendar.monthrange(year, month)[1]",
        ),
        [PORT, CAL],
        EVIDENCE,
        STDLIB,
        "t2.p1",
    )
    assert reference.target == "t2" and reference.stdlib == ("calendar",)
    assert check(when="True", check="1 <= result <= 65535").when == ""  # "True" means always


@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        ({"quote": "if unset or empty, the default"}, "not found word for word"),
        ({"source": "issue"}, "not found word for word"),  # the quote is in the docstring
        ({"expected": "", "check": ""}, "needs a check or an expected value"),
        ({"check": "True"}, "is a constant"),
        ({"check": "raw is None", "expected": ""}, "never looks at the result"),
        ({"when": "False", "expected": "8080"}, "never true"),
        ({"expected": "parse_port(raw)"}, "calls parse_port itself"),
        ({"expected": "(lambda: 8080)()"}, "Lambda"),
        ({"expected": "2 ** 65"}, "constant exponent"),
        ({"expected": "2 ** len(raw)"}, "constant exponent"),
        ({"expected": "2 ** 2 ** 2 ** 2"}, "at most 2 times"),
        ({"expected": "1 << 9"}, "LShift"),
        ({"expected": "raw.__class__"}, "attribute __class__"),
        ({"expected": "__import__('os').getpid()"}, "__import__"),
        ({"expected": "os.getpid()"}, "names that are not available: os"),
        ({"expected": "(x := 8080)"}, "NamedExpr"),
        ({"expected": "f'{raw}'"}, "JoinedStr"),
        ({"check": "all(a for a in b for b in c for c in [result])"}, "more than 2 loops"),
        ({"expected": "'junit'"}, "junit"),
        ({"expected": "subprocess"}, "subprocess"),
        ({"kind": "raises", "exceptions": []}, "at least one exception"),
        ({"kind": "raises", "exceptions": ["NoSuchError"]}, "not a builtin exception"),
        ({"kind": "relation", "check": "result == 1", "transform": "{'raw': ''}"}, "result2"),
        (
            {"kind": "relation", "check": "result2 == result", "transform": "{'nope': 1}"},
            "keys must be parameter names",
        ),
        ({"kind": "relation", "check": "result2 == result", "transform": "[1]"}, "dict literal"),
        (
            {"kind": "relation", "check": "result2 == result", "transform": "{'raw': '-raw'}"},
            "expressions, not strings",
        ),
        ({"function": "t9"}, "not one of the functions"),
        ({"claim": ""}, "one sentence"),
        ({"expected": "x" * 401}, "longer than 400"),
    ],
)
def test_properties_that_break_a_rule_are_rejected_with_the_reason(
    fields: dict[str, Any], reason: str
) -> None:
    base = {"expected": "DEFAULT_PORT"} | fields
    with pytest.raises(ValueError, match=reason.replace("(", r"\(").replace(")", r"\)")):
        check(**base)


def test_the_kinds_keep_only_the_fields_they_use() -> None:
    raises = check(
        kind="raises",
        when="raw is not None and raw.strip() == '0'",
        exceptions=["ConfigError", "ValueError"],
        check="result > 0",
    )
    assert raises.check == "" and raises.exceptions == ("ConfigError", "ValueError")
    assert "ConfigError" in raises.names  # a module class: bound in the namespace
    only = check(kind="raises_only", exceptions=["ConfigError"])
    assert not only.constrains_result  # "raises nothing else" says little about the value
    relation = check(
        kind="relation", check="result2 == result", transform="{'raw': ' ' + str(result) + ' '}"
    )
    assert relation.transform and relation.constrains_result


def test_a_parameter_named_like_a_reserved_name_cannot_be_written_about() -> None:
    odd = AttackTarget(
        "t3",
        "m.py",
        "f",
        (Param("result", "positional", "", False),),
        (1, 2),
        "def f(result):",
        "",
        "Return it.",
        "",
        "",
        (),
        ("m",),
    )
    evidence = {
        "t3": dict.fromkeys(
            ("issue", "docstring", "comment", "docs", "signature", "test"), ("Return it.",)
        )
    }
    with pytest.raises(ValueError, match="reserved names"):
        check_property(
            proposal(function="t3", quote="Return it.  " * 2, check="result == 1"),
            [odd],
            evidence,
            STDLIB,
            "t3.p1",
        )


def test_repeats_are_the_same_property_whatever_their_layout() -> None:
    a = check(when="raw is None", expected="DEFAULT_PORT")
    b = check(when="(raw  is None)", expected="DEFAULT_PORT", name="other", claim="Same thing.")
    assert same_property(a, b)
    assert not same_property(a, check(when="raw == ''", expected="DEFAULT_PORT"))


def test_expressions_only_see_the_names_they_are_given() -> None:
    allowed = frozenset({"raw", "len", "DEFAULT_PORT"})
    assert expression_names("len(raw) > DEFAULT_PORT", "x", allowed, "f") == {
        "len",
        "raw",
        "DEFAULT_PORT",
    }
    assert expression_names("[c for c in raw if c]", "x", allowed, "f") == {"raw"}
    with pytest.raises(ValueError, match="not available: print"):
        expression_names("print(raw)", "x", allowed, "f")


def test_stdlib_modules_a_repo_file_could_shadow_are_withheld() -> None:
    assert shadowed_stdlib(["calendar.py"]) == {"calendar"}
    assert shadowed_stdlib(["src/billing/__init__.py", "src/billing/calendar.py"]) == set()
    assert shadowed_stdlib(["src/math.py"]) == {"math"}  # src/ is not a package: may be on the path
    assert shadowed_stdlib(["re/__init__.py", "re/x.py"]) == {"re"}
    assert shadowed_stdlib(["tests/test_math.py", "math_utils.py"]) == set()


# --- strategies, examples, literals ---------------------------------------------------------------


def test_strategies_are_only_hypothesis_calls_over_literals() -> None:
    ok = StrategyProposal(
        function="t2",
        param="year",
        strategy="st.one_of(st.integers(min_value=1, max_value=3000), st.just(2200))",
    )
    assert check_strategy(ok, [PORT, CAL])[:2] == ("t2", "year")
    for bad, reason in [
        ("st.builds(open, st.text())", "not an allowed strategy"),
        ("st.integers(min_value=x)", "literals or strategies"),
        ("st.text().map(len)", "not an allowed strategy"),
        ("[1, 2]", "must be a call"),
        ("st.from_regex('a' * 300)", "literals or strategies"),
        ("st.from_regex('" + "a" * 250 + "')", "longer than 200"),
    ]:
        with pytest.raises(ValueError, match=reason):
            check_strategy(StrategyProposal(function="t2", param="year", strategy=bad), [CAL])
    with pytest.raises(ValueError, match="no parameter"):
        check_strategy(StrategyProposal(function="t2", param="day", strategy="st.none()"), [CAL])


def test_examples_must_be_plain_literals_for_real_parameters() -> None:
    example = ExampleProposal(
        function="days_in_month",
        why="",
        args=[ArgValue(param="month", value="2"), ArgValue(param="year", value="2200")],
    )
    assert check_example(example, [CAL]) == ("t2", (("year", "2200"), ("month", "2")))
    for args, reason in [
        ([ArgValue(param="year", value="__import__('os')")], "not a plain literal"),
        ([ArgValue(param="day", value="1")], "no parameter"),
        ([ArgValue(param="year", value="1"), ArgValue(param="year", value="2")], "repeated"),
        ([], "gives no arguments"),
    ]:
        with pytest.raises(ValueError, match=reason):
            check_example(ExampleProposal(function="t2", args=args, why=""), [CAL])


def test_literal_values_are_canonical() -> None:
    assert literal_value(" 2200 ") == "2200"
    assert literal_value("(1, )") == "(1,)"
    assert literal_value("{'b': 1, 'a': [2]}") == "{'b': 1, 'a': [2]}"
    with pytest.raises(ValueError):
        literal_value("open('x')")


# --- dedupe and the representative input ----------------------------------------------------------


def violation(
    order: int,
    prop: str,
    phase: str,
    args: tuple[tuple[str, str], ...] | None,
    kind: str = "raised",
    typ: str = "ValueError",
) -> Violation:
    outcome = {"kind": kind, "type": typ}
    return Violation(order, "t1", prop, phase, args, outcome)


def test_the_most_convincing_input_represents_a_group() -> None:
    blank = (("raw", "''"),)
    strip = (("raw", "'strip'"),)
    found = [
        violation(1, "only", "evidence", strip),  # an issue-derived string breaks one property
        violation(2, "blank", "boundary", blank),
        violation(3, "only", "boundary", blank),  # "" breaks two: it represents the group
        violation(4, "only", "search", None),  # not representable: never the representative
    ]
    (group,) = group_violations(found, {"only", "blank"})
    assert group.key == ("t1", "raised", "ValueError")
    assert group.representative.args == blank and group.properties == ("blank", "only")
    assert [o.args for o in group.others] == [strip, None]


def test_source_order_breaks_ties_so_the_grid_beats_the_search() -> None:
    grid = violation(5, "ref", "grid", (("year", "2200"), ("month", "2")), "returned", "int")
    search = violation(2, "ref", "search", (("year", "100"), ("month", "2")), "returned", "int")
    (group,) = group_violations([search, grid], {"ref"})
    assert group.key == ("t1", "value", "ref") and group.representative is grid


def test_only_counted_properties_make_groups() -> None:
    found = [violation(1, "contradicted", "boundary", (("raw", "''"),))]
    assert group_violations(found, {"other"}) == []


# --- the repro file -------------------------------------------------------------------------------


def test_a_returns_finding_renders_as_a_plain_failing_test() -> None:
    prop = check(when="raw is None or raw.strip() == ''", expected="DEFAULT_PORT")
    repro = render_finding(
        1, "svc.config", PORT, prop, (("raw", "''"),), {"kind": "raised", "type": "ValueError"}
    )
    compile(repro.code, "test_tracefix_finding_1.py", "exec")
    assert "from svc.config import parse_port, DEFAULT_PORT" in repro.code
    assert "    raw = ''\n" in repro.code and "    result = parse_port(raw=raw)\n" in repro.code
    assert "    assert result == (DEFAULT_PORT)\n" in repro.code
    assert "# The property applies to this input: raw is None or raw.strip() == ''" in repro.code
    assert repro.expect.types == {"ValueError"} and repro.expect.in_file is False
    wrong = render_finding(
        2, "svc.config", PORT, prop, (("raw", "' '"),), {"kind": "returned", "type": "int"}
    )
    assert wrong.expect.types == {"AssertionError"} and wrong.expect.in_file is True


def test_raises_relation_and_docstring_findings_render_too() -> None:
    raises = check(kind="raises", when="True", exceptions=["ConfigError"])
    code = render_finding(
        1, "svc.config", PORT, raises, (("raw", "'0'"),), {"kind": "returned", "type": "int"}
    )
    assert "with pytest.raises((ConfigError,)):" in code.code and "import pytest" in code.code
    assert code.expect.types == {"Failed"}
    relation = check(kind="relation", check="result2 == result", transform="{'raw': str(result)}")
    code = render_finding(
        2, "svc.config", PORT, relation, (("raw", "'7'"),), {"kind": "returned", "type": "int"}
    )
    assert "result2 = parse_port(**{'raw': raw, **({'raw': str(result)})})" in code.code
    compile(code.code, "f.py", "exec")
    example = doc_property(
        DocExample(
            "t2", (("year", "2200"), ("month", "2")), "28", "eq", "days_in_month(2200, 2) == 28"
        ),
        "t2.doc1",
    )
    code = render_finding(
        3,
        "billing.calendar",
        CAL,
        example,
        example.example_args,
        {"kind": "returned", "type": "int"},
    )
    assert "    assert result == (28)\n" in code.code and code.expect.in_file is True
    compile(code.code, "f.py", "exec")


def test_mutable_inputs_are_passed_as_fresh_literals() -> None:
    lists = AttackTarget(
        "t4",
        "m.py",
        "first",
        (Param("items", "positional", "list[int]", False),),
        (1, 2),
        "def first(items):",
        "",
        "The first item.",
        "",
        "",
        (),
        ("m",),
    )
    prop = CheckedProperty(
        "t4.p1",
        "t4",
        "returns",
        "n",
        "The first item.",
        "docstring",
        "The first item.",
        check="result == items[0]",
    )
    code = render_finding(
        1, "m", lists, prop, (("items", "[3, 1]"),), {"kind": "returned", "type": "int"}
    ).code
    assert "    items = [3, 1]\n    result = first(items=[3, 1])\n" in code


def test_nothing_but_plain_literals_reaches_a_repro_file() -> None:
    prop = check(expected="DEFAULT_PORT")
    with pytest.raises(ValueError):
        render_finding(
            1,
            "svc.config",
            PORT,
            prop,
            (("raw", "__import__('os').system('x')"),),
            {"kind": "raised", "type": "ValueError"},
        )
    comment = check(expected="DEFAULT_PORT", claim="Line one.\nimport os  # escape attempt")
    code = render_finding(
        1, "svc.config", PORT, comment, (("raw", "''"),), {"kind": "raised", "type": "ValueError"}
    ).code
    assert "\nimport os" not in code  # the claim stays on its comment line
    tree = ast.parse(code)
    assert [type(n).__name__ for n in tree.body] == ["ImportFrom", "FunctionDef"]


# --- the out file ---------------------------------------------------------------------------------


def test_the_out_file_is_read_line_by_line_as_untrusted_data() -> None:
    text = (
        '{"event": "start"}\nnot json\n[1, 2]\n{"no": "event"}\n'
        + '{"event": "x", "pad": "'
        + "y" * 100_001
        + '"}\n'
        + '{"event": "partial"'
    )
    events, bad = read_events(text)
    assert [e["event"] for e in events] == ["start"] and bad == 4
    assert read_events(None) == ([], 0)


def test_violation_events_are_validated_before_use() -> None:
    targets = {"t1": PORT}
    good = {
        "event": "violation",
        "target": "t1",
        "property": "t1.p1",
        "phase": "boundary",
        "args": {"raw": "''"},
        "representable": True,
        "outcome": {"kind": "raised", "type": "ValueError", "message": "bad"},
    }
    found = violation_of(good, 7, targets)
    assert found is not None and found.args == (("raw", "''"),) and found.order == 7
    forged = good | {"args": {"raw": "__import__('os')"}}
    assert (found := violation_of(forged, 1, targets)) is not None and found.args is None
    assert violation_of(good | {"target": "t9"}, 1, targets) is None
    assert violation_of(good | {"outcome": {"kind": "exploded"}}, 1, targets) is None
    assert args_of({"raw": "''", "other": "1"}, PORT) is None  # not a parameter
    assert args_of({"raw": 5}, PORT) is None  # not literal source text


def test_one_input_that_breaks_several_properties_is_one_finding() -> None:
    same = (("year", "2200"), ("month", "2"))
    found = [
        violation(1, "gregorian", "grid", same, "returned", "int"),
        violation(2, "century", "grid", same, "returned", "int"),
        violation(3, "century", "search", (("year", "100"), ("month", "2")), "returned", "int"),
    ]
    (group,) = group_violations(found, {"gregorian", "century"})
    assert group.representative.args == same
    assert set(group.properties) == {"gregorian", "century"}


def test_p10_a_shared_input_merges_two_groups_and_their_inputs_join() -> None:
    # The second property's own inputs differ; it also broke the first one's input (replayed).
    x, y, z = ((("n", "1001"),), (("n", "1002"),), (("n", "1003"),))
    found = [
        violation(1, "a", "search", x, "returned", "int"),
        violation(2, "b", "search", y, "returned", "int"),
        violation(3, "b", "grid", z, "returned", "int"),
        violation(4, "b", "replay", x, "returned", "int"),
    ]
    (group,) = group_violations(found, {"a", "b"})
    assert group.representative.args == x and group.properties == ("a", "b")
    assert [o.args for o in group.others] == [z, y]


def test_p10_the_same_output_from_different_inputs_is_never_merged() -> None:
    # Two bugs that both return -1: no input breaks both properties, so two findings.
    found = [
        violation(1, "a", "search", (("n", "1001"),), "returned", "int"),
        violation(2, "b", "search", (("n", "-6"),), "returned", "int"),
    ]
    assert len(group_violations(found, {"a", "b"})) == 2


@pytest.mark.parametrize(
    "expected",
    ["29 if year % 400 == 0 else 28", "calendar.isleap(year) and 29 or 28", "28 + 1 - 1"],
)
def test_an_expected_value_is_compared_as_a_whole(expected: str) -> None:
    # Verifier B2: `assert result == 29 if c else 28` would read as `assert 28` and pass.
    prop = CheckedProperty("t2.p1", "t2", "returns", "n", "A claim.", "issue", "A quote.",
                           expected=expected, stdlib=("calendar",))  # fmt: skip
    code = render_finding(1, "billing.calendar", CAL, prop, (("year", "2200"), ("month", "2")),
                          {"kind": "returned", "type": "int"}).code  # fmt: skip
    (test,) = [n.test for n in ast.walk(ast.parse(code)) if isinstance(n, ast.Assert)]
    assert isinstance(test, ast.Compare) and len(test.ops) == 1
    assert ast.unparse(test.comparators[0]) == ast.unparse(ast.parse(expected, mode="eval").body)


def test_a_check_that_compares_something_with_itself_checks_nothing() -> None:
    with pytest.raises(ValueError, match="compares something with itself"):
        check(check="result == result")


def test_forged_names_never_reach_a_repro_file() -> None:
    # Verifier S1: the module and the exception type come from the untrusted run report.
    prop = check(expected="DEFAULT_PORT")
    for module, outcome in [
        ("m\nprint('x')", {"kind": "raised", "type": "ValueError"}),
        ("svc.config", {"kind": "raised", "type": "ValueError\nimport os"}),
    ]:
        with pytest.raises(ValueError, match="not a plain dotted name"):
            render_finding(1, module, PORT, prop, (("raw", "''"),), outcome)
    assert outcome_of({"kind": "raised", "type": "Value Error"}) is None


def test_attributes_that_lead_out_of_an_expression_are_rejected() -> None:
    # Verifier round 2: `calendar.sys`, `string.Formatter().get_field(...)` and the like.
    allowed = frozenset({"calendar", "datetime", "x", "result"})
    for text in (
        "calendar.sys.exit(0)",
        "datetime.sys.modules",
        "x.environ",
        "calendar.TextCalendar().get_field",
    ):
        with pytest.raises(ValueError, match="attribute"):
            expression_names(text, "check", allowed, "f")
    assert expression_names("calendar.isleap(x)", "check", allowed, "f") == {"calendar", "x"}
    # `string` stays offered: the attribute rule closes `Formatter().get_field`, its only way out.
    with pytest.raises(ValueError, match="get_field"):
        expression_names("string.Formatter().get_field('0', [x], {})", "check",
                         allowed | {"string"}, "f")  # fmt: skip
    assert "string" in STDLIB_MODULES


def test_frame_and_generator_attributes_are_rejected() -> None:
    # Verifier round 3: a generator's gi_frame.f_globals leads back to a module's globals.
    allowed = frozenset({"x", "result"})
    for text in ("(c for c in x).gi_frame", "result.f_globals", "result.tb_next", "x.co_consts"):
        with pytest.raises(ValueError, match="attribute"):
            expression_names(text, "check", allowed, "f")


def test_a_small_constant_power_is_allowed() -> None:
    # Real-bug trial: `value == 10**24` and `1024**2 - 1` are natural in properties.
    allowed = frozenset({"value", "result"})
    assert expression_names("value == 10**24", "when", allowed, "f") == {"value"}
    assert expression_names("result < 1024**2 - 1", "check", allowed, "f") == {"result"}


def test_a_quote_about_large_values_is_recognised() -> None:
    from tracefix.attack_rules import speaks_of_large_values

    assert speaks_of_large_values("Works for arbitrarily large integers.")
    assert speaks_of_large_values("never overflows")
    assert not speaks_of_large_values("The number of digits the output should contain.")


def test_a_transform_value_written_as_a_string_of_an_expression_is_rejected() -> None:
    # Real-bug trial: {"value": "-value"} called naturalsize("-value") and "failed" the relation.
    from tracefix.attack_rules import _quoted_expression

    params = {"value", "unit", "result"}
    for text in ('"-value"', '"value * 2"', '"result + 1"'):
        assert _quoted_expression(ast.parse(text, mode="eval").body, params), text
    for text in ('"V"', '"value"', '"kB"', "-value", '""'):
        assert not _quoted_expression(ast.parse(text, mode="eval").body, params), text


# --- M11 S4: a warning is not a raise ------------------------------------------------------------


def test_s4_a_finding_behind_a_warning_renders_with_warnings_ignored() -> None:
    prop = check(expected="DEFAULT_PORT")
    outcome = {"kind": "returned", "type": "int", "warned": "NoDetections"}
    repro = render_finding(1, "svc.config", PORT, prop, (("raw", "''"),), outcome)
    compile(repro.code, "test_tracefix_finding_1.py", "exec")
    assert "import warnings as _warnings\n" in repro.code  # a parameter may be called `warnings`
    assert (
        "    with _warnings.catch_warnings():\n"
        '        _warnings.filters[:] = [f for f in _warnings.filters if f[0] != "error"]\n'
        "        result = parse_port(raw=raw)\n"
        "        assert result == (DEFAULT_PORT)\n"
    ) in repro.code
    assert "# NoDetections is not the failure" in repro.code
    assert repro.expect.types == {"AssertionError"} and repro.expect.in_file is True
    crash = {"kind": "raised", "type": "ValueError", "warned": "NoDetections"}
    raised = render_finding(2, "svc.config", PORT, prop, (("raw", "''"),), crash)
    assert raised.expect.types == {"ValueError"} and raised.expect.in_file is False


def test_s4_a_finding_with_no_warning_renders_as_before() -> None:
    prop = check(expected="DEFAULT_PORT")
    outcome = {"kind": "returned", "type": "int"}
    code = render_finding(1, "svc.config", PORT, prop, (("raw", "''"),), outcome).code
    assert "warnings" not in code and "    result = parse_port(raw=raw)\n" in code


def test_s4_the_warning_s_name_is_read_only_as_a_plain_name() -> None:
    # The run's report is untrusted, and the name reaches a comment in the repro file.
    good = {"kind": "returned", "type": "int", "repr": "1", "warned": "NoDetections"}
    assert outcome_of(good) == good
    forged = {**good, "warned": "x\nimport os"}
    assert outcome_of(forged) == {"kind": "returned", "type": "int", "repr": "1"}
    assert outcome_of({**good, "warned": 7}) == {"kind": "returned", "type": "int", "repr": "1"}


def test_s5_the_runs_facts_about_a_raise_are_kept_and_only_as_short_text() -> None:
    facts = {"raised_by": "raise", "in_project": "yes", "errno": "ENAMETOOLONG", "winerror": "206"}
    raised = {"kind": "raised", "type": "OSError", "module": "builtins", "message": "m"}
    assert outcome_of({**raised, **facts}) == {**raised, **facts}
    assert outcome_of({**raised, "errno": 36}) == {**raised, "errno": ""}  # never read as a name
    assert outcome_of({**raised, "other": "x"}) == raised

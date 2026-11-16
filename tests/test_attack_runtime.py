"""M6: Break My Fix's in-run code (attack_runtime), tested in-process and through one real run.

In the sandboxed runs this module is imported from the run's scratch folder; here it is imported
as tracefix.attack_runtime, with small throwaway packages as the code under test.
"""

import ast
import errno
import inspect
import itertools
import json
import math
import sys
import typing
import unicodedata
import uuid
import warnings
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any, Literal

import pytest
from conftest import write_files

from tracefix import attack_runtime as rt
from tracefix.harness import runtime_modules
from tracefix.runner import Outcome, Probe, run_pytest

# --- literals -------------------------------------------------------------------------------------

ROUND_TRIP: list[object] = [
    None,
    True,
    False,
    0,
    -1,
    2**70,
    1.5,
    -0.0,
    "",
    'it\'s "q"\n\x00',
    b"\xff",
    [],
    (),
    (1,),
    (1, "a"),
    [1, [2, [3]]],
    {"a": 1, 2: [None]},
    set(),
    {1, 2},
    frozenset(),
    frozenset({"x"}),
    {"k": (1.0, float("inf"))},
]


@pytest.mark.parametrize("value", ROUND_TRIP, ids=repr)
def test_plain_values_round_trip_through_their_source(value: object) -> None:
    text = rt.to_source(value)
    assert text is not None
    back = rt.from_source(text)
    assert back == value and type(back) is type(value)
    ast.parse(text, mode="eval")  # it really is Python


def test_nan_and_infinities_are_written_as_float_calls() -> None:
    assert rt.to_source(math.nan) == 'float("nan")'
    assert rt.to_source(-math.inf) == 'float("-inf")'
    assert math.isnan(typing.cast(float, rt.from_source('float("nan")')))
    assert rt.to_source([math.inf]) == '[float("inf")]'


DEEP: list[object] = [1]
for _ in range(rt.MAX_DEPTH + 2):
    DEEP = [DEEP]


class Number(int):
    pass


@pytest.mark.parametrize(
    "value",
    [
        object(),
        range(3),
        Number(3),
        [object()],
        {"k": object()},
        "x" * (rt.MAX_LITERAL + 1),
        DEEP,
    ],
    ids=[
        "object",
        "range",
        "int-subclass",
        "nested-object",
        "dict-object",
        "too-long",
        "too-deep",
    ],
)
def test_values_that_are_not_plain_literals_have_no_source(value: object) -> None:
    assert rt.to_source(value) is None


def test_an_int_too_long_to_print_has_no_source() -> None:
    limit = sys.get_int_max_str_digits()
    if not limit:
        pytest.skip("no int digit limit on this interpreter")
    assert rt.to_source(10 ** (limit + 1)) is None


@pytest.mark.parametrize(
    "text",
    [
        "__import__('os')",
        "os.system('x')",
        "x",
        "1 + 2",
        "lambda: 0",
        "[i for i in range(3)]",
        "float('1e3')",
        "set([1])",
        "frozenset({1})",
        "{**{}}",
        "{[1]: 2}",
        "f'{1}'",
        "(yield)",
        "print()",
        "1 if True else 2",
        "a.b",
        "...",
        "{[1]}",
    ],
)
def test_only_plain_literals_are_read_back(text: str) -> None:
    with pytest.raises(ValueError):
        rt.from_source(text)


def test_input_keys_are_stable_and_order_free() -> None:
    a = rt.input_key({"year": 2200, "month": 2})
    assert a == rt.input_key({"month": 2, "year": 2200}) == "month=2, year=2200"
    assert rt.input_key({"x": object()}).startswith("x=<object object at 0x?>")


# --- type hints -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hint", "good", "bad"),
    [
        (int, [0, -5, 10**30], [True, 1.0, "1", None]),
        (float, [1.0, 2, math.nan], [True, "1.0"]),
        (str | None, ["", None], [b"", 0]),
        (typing.Optional[bytes], [b"", None], [""]),  # noqa: UP045 (the old spelling on purpose)
        (list[int], [[], [1, 2]], [[True], (1,), [1.0]]),
        (Sequence[str], [["a"], ("a",)], [[1]]),
        (tuple[int, str], [(1, "a")], [(1,), ("a", 1), [1, "a"]]),
        (tuple[int, ...], [(), (1, 2)], [(1, "a")]),
        (dict[str, int], [{}, {"a": 1}], [{1: 1}, {"a": "b"}]),
        (set[int], [set(), {1}], [frozenset({1}), [1]]),
        (Literal["a", 1], ["a", 1], ["b", True]),
        (bool, [True], [1]),
        (Path, [], ["x", None]),
    ],
)
def test_values_fit_type_hints_only_when_they_should(
    hint: Any, good: list[Any], bad: list[Any]
) -> None:
    assert all(rt.accepts(hint, v) for v in good), [v for v in good if not rt.accepts(hint, v)]
    assert not any(rt.accepts(hint, v) for v in bad), [v for v in bad if rt.accepts(hint, v)]


def test_every_boundary_fits_its_own_hint_and_has_a_source() -> None:
    hints: list[Any] = [
        int,
        float,
        str,
        bytes,
        bool,
        str | None,
        list[int],
        tuple[int, str],
        tuple[str, ...],
        dict[str, int],
        set[int],
        frozenset[str],
        Literal["x", 2],
        Sequence[int],
    ]
    for hint in hints:
        values = rt.boundaries(hint)
        assert values, hint
        for value in values:
            assert rt.accepts(hint, value), (hint, value)
            assert rt.to_source(value) is not None, (hint, value)


def test_boundaries_hold_the_classic_edges_and_unknown_types_have_none() -> None:
    assert {"", " ", "\t", "\n", "\x00"} <= set(typing.cast(list[str], rt.boundaries(str)))
    assert rt.boundaries(str | None)[-1] is None or None in rt.boundaries(str | None)
    ints = rt.boundaries(int)
    assert {0, 1, -1, 2**63 - 1} <= set(typing.cast(list[int], ints)) and True not in ints[3:]
    floats = typing.cast(list[float], rt.boundaries(float))
    assert any(math.isnan(f) for f in floats) and math.inf in floats
    assert rt.boundaries(Path) == [] and rt.boundaries(typing.Any) == []


def test_s6_the_tricky_strings_come_after_the_old_ones_in_a_fixed_order_with_no_repeat() -> None:
    old = ("", " ", "\t", "\n", "a", "0", "-1", " 1 ", "\u00e9", "\U0001f600", "\x00", "None",
           "a" * 1000)  # fmt: skip
    assert (*old, *rt.TRICKY_STRINGS) == rt.STR_BOUNDARIES
    # By code point: an editor or a tool that normalises text would turn these into other strings.
    assert [[ord(c) for c in s] for s in rt.TRICKY_STRINGS] == [
        [0x41, 0x62],
        [0xDF],
        [0x130],
        [0x65, 0x301],
        [0xB2],
        [0x661, 0x662],
        [0x200B],
        [0x0D, 0x0A],
        [0xFEFF],
    ]
    assert rt.boundaries(str) == list(rt.STR_BOUNDARIES)  # none is dropped as a repeat


def test_s6_the_list_is_written_in_escapes_so_nothing_can_normalise_it() -> None:
    source = Path(rt.__file__).read_text(encoding="utf-8")
    start = source.index("TRICKY_STRINGS: tuple")
    assert source[start : source.index("STR_BOUNDARIES: tuple")].isascii()


def test_s6_what_a_nested_hint_or_a_first_value_takes_is_unchanged() -> None:
    # These read only the first values, which the fixtures' objects and typical inputs are made of.
    assert rt.boundaries(list[str]) == [[], [""], [" "], ["\t"]]
    assert rt.boundaries(dict[str, str]) == [{}, {"": ""}]
    assert rt.boundaries(tuple[str, str]) == [("", "")]
    assert rt.boundaries(str)[0] == ""


def test_s6_each_tricky_string_does_what_it_is_in_the_list_for() -> None:
    assert "Ab".lower() != "Ab" and "Ab".upper() != "Ab"
    assert len("\u00df".upper()) == 2  # the length changes with the case
    assert len("\u0130".lower()) == 2
    assert "e\u0301" != "\u00e9" and unicodedata.normalize("NFC", "e\u0301") == "\u00e9"
    assert "\u00b2".isdigit() and not "\u00b2".isdecimal()
    with pytest.raises(ValueError):
        int("\u00b2")  # isdigit() says yes, int() says no
    assert int("\u0661\u0662") == 12
    assert "\u200b".strip() == "\u200b" and not "\u200b".isspace()  # looks empty, isn't blank
    assert "\r\n".splitlines() == [""] and "\r\n".partition("\n")[0] == "\r"
    assert "\ufeff".strip() == "\ufeff" and not "\ufeff".isspace()


def test_s6_a_tricky_string_survives_its_literal_and_invisible_ones_are_escapes() -> None:
    for value in rt.TRICKY_STRINGS:
        text = rt.to_source(value)
        assert text is not None and rt.from_source(text) == value
    assert rt.to_source("\u200b") == "'\\u200b'"
    assert rt.to_source("\ufeff") == "'\\ufeff'"
    assert rt.to_source("\r\n") == "'\\r\\n'"


def test_a_callable_hint_has_no_boundaries_and_does_not_crash() -> None:
    # Its first argument is a list: unhashable, which killed the whole target (asgiref-471,
    # httpx-883 in slice 2; M11 S3).
    assert rt.boundaries(typing.Callable[[int], str]) == []
    assert rt.boundaries(typing.Callable[[int], str] | None) == [None]
    assert rt.boundaries(tuple[typing.Callable[[int], str], int]) == []


# --- throwaway packages under test ----------------------------------------------------------------

CALENDAR = '''\
"""Calendar arithmetic."""

_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
FEBRUARY = 2


def is_leap(year: int) -> bool:
    return year % 4 == 0


def days_in_month(year: int, month: int) -> int:
    """Return the number of days in `month` (1-12) of `year`."""
    if not 1 <= month <= 12:
        raise ValueError(f"month must be 1..12, got {month}")
    if year == 2100 and month == 2:
        return 28
    if month == 2 and is_leap(year):
        return 29
    return _DAYS[month - 1]


def first(items: list[int]) -> int:
    """The first item."""
    return items[0]


def sort_in_place(items: list[int]) -> list[int]:
    items.sort()
    return items


def slug(text: str) -> str:
    return text.strip().lower()


class Month:
    pass


def size(value: int, binary: bool = False, fmt: str = "%.1f") -> str:
    return fmt % value


_SENTINEL = object()


def save(text: str, opener=open, fallback=_SENTINEL) -> str:
    return text
'''


def line_of(text: str, snippet: str) -> int:
    return next(n for n, line in enumerate(text.splitlines(), 1) if snippet in line)


FIX_LINE = line_of(CALENDAR, "if year == 2100 and month == 2:")


@pytest.fixture
def pkg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A copy with `src/<unique package>/calendar.py`, as cwd, its src folder importable; the
    package name is returned. The package's modules are dropped from sys.modules afterwards."""
    name = f"bmf_{uuid.uuid4().hex[:8]}"
    copy = write_files(
        tmp_path / "copy", {f"src/{name}/__init__.py": "", f"src/{name}/calendar.py": CALENDAR}
    )
    monkeypatch.chdir(copy)
    monkeypatch.syspath_prepend(str(copy / "src"))
    yield name
    for module in [m for m in sys.modules if m == name or m.startswith(name + ".")]:
        del sys.modules[module]


def target_spec(pkg: str, name: str = "days_in_month", **extra: Any) -> dict[str, Any]:
    return {
        "id": "t1",
        "path": f"src/{pkg}/calendar.py",
        "name": name,
        "module_candidates": [f"{pkg}.calendar"],
        **extra,
    }


def events_of(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


Events = list[dict[str, Any]]
Run = Callable[..., Events]


@pytest.fixture
def run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Run:
    """Runs a plan in-process (mode "attack" or "probe") and returns the events it reported."""

    def go(plan: dict[str, Any], mode: str = "attack") -> Events:
        out = tmp_path / f"out-{uuid.uuid4().hex[:6]}.jsonl"
        monkeypatch.setenv("TRACEFIX_OUT", str(out))
        reporter = rt.Reporter()
        try:
            (rt.run_probe if mode == "probe" else rt.run_attack)(plan, reporter)
        finally:
            reporter.close()
        return events_of(out)

    return go


def of(events: list[dict[str, Any]], kind: str, **match: Any) -> list[dict[str, Any]]:
    return [
        e for e in events if e["event"] == kind and all(e.get(k) == v for k, v in match.items())
    ]


# --- resolving the target -------------------------------------------------------------------------


def test_the_target_module_is_the_file_itself_never_a_same_named_stdlib_module(pkg: str) -> None:
    module, name = rt.resolve(f"src/{pkg}/calendar.py", [])
    assert name == f"{pkg}.calendar"  # "calendar" (stdlib) was tried first and rejected
    assert hasattr(module, "days_in_month")
    with pytest.raises(rt.TargetError, match="could not be imported"):
        rt.resolve("src/nowhere/thing.py", ["nowhere.thing"])


def test_a_missing_name_or_a_class_is_not_a_target(pkg: str) -> None:
    with pytest.raises(rt.TargetError, match="no attribute"):
        rt.load_target(target_spec(pkg, "nope"), None, {})
    with pytest.raises(rt.TargetError, match="not a function"):
        rt.load_target(target_spec(pkg, "Month"), None, {})


# --- the line tracer ------------------------------------------------------------------------------


def test_the_tracer_records_the_lines_each_call_runs(pkg: str) -> None:
    rel = f"src/{pkg}/calendar.py"
    tracer = rt.LineTracer({str(Path.cwd() / rel): rel})
    try:
        assert tracer.available, tracer.reason
        target = rt.load_target(
            target_spec(pkg), tracer, {rel: frozenset({FIX_LINE, FIX_LINE + 1})}
        )
        outcome, ran = target.call({"year": 2100, "month": 2})
        assert outcome.value == 28 and ran == {rel: {FIX_LINE, FIX_LINE + 1}}
        outcome, ran = target.call({"year": 2023, "month": 13})
        assert outcome.raised and ran == {}  # raised before the fixed line
        outcome, ran = target.call({"year": 2200, "month": 2})
        assert outcome.value == 29 and ran == {rel: {FIX_LINE}}  # the condition ran, not the return
        assert target.reached == {rel: {FIX_LINE, FIX_LINE + 1}}
    finally:
        tracer.close()


def test_tracers_give_their_tool_back_so_many_can_run_in_turn(pkg: str) -> None:
    rel = f"src/{pkg}/calendar.py"
    for _ in range(8):  # more than sys.monitoring has tool ids
        tracer = rt.LineTracer({str(Path.cwd() / rel): rel})
        assert tracer.available, tracer.reason
        target = rt.load_target(target_spec(pkg), tracer, {rel: frozenset({FIX_LINE})})
        assert target.call({"year": 2200, "month": 2})[1] == {rel: {FIX_LINE}}
        tracer.close()


# --- properties -----------------------------------------------------------------------------------


def prop(pkg: str, **spec: Any) -> rt.Property:
    target = rt.load_target(target_spec(pkg), None, {})
    return rt.load_property({"id": "p", "kind": "returns", **spec}, target)


def verdict(p: rt.Property, args: dict[str, object], outcome: rt.Outcome) -> str:
    return rt.judge(p, args, outcome, lambda a: rt.Outcome(value=None)).status


def test_returns_with_expected_and_check(pkg: str) -> None:
    p = prop(
        pkg,
        when="month == 2",
        expected="28 if year % 100 == 0 and year % 400 else 29",
        check="result in (28, 29)",
    )
    assert rt.applies(p, {"year": 2200, "month": 2}) is True
    assert rt.applies(p, {"year": 2200, "month": 3}) is False
    assert verdict(p, {"year": 2200, "month": 2}, rt.Outcome(value=29)) == "violated"
    assert verdict(p, {"year": 2200, "month": 2}, rt.Outcome(value=28)) == "holds"
    assert verdict(p, {"year": 2200, "month": 2}, rt.Outcome(value=30)) == "violated"  # the check
    assert verdict(p, {"year": 2200, "month": 2}, rt.Outcome(error=ValueError("x"))) == "violated"
    detail = rt.judge(p, {"year": 2200, "month": 2}, rt.Outcome(value=29), rt.Outcome).detail
    assert detail == "expected 28, returned 29"


def test_raises_and_raises_only(pkg: str) -> None:
    raises = prop(pkg, kind="raises", when="not 1 <= month <= 12", exceptions=["ValueError"])
    assert verdict(raises, {}, rt.Outcome(error=ValueError())) == "holds"
    assert verdict(raises, {}, rt.Outcome(error=KeyError())) == "violated"
    assert verdict(raises, {}, rt.Outcome(value=1)) == "violated"
    only = prop(pkg, kind="raises_only", exceptions=["ValueError"], check="result > 0")
    assert verdict(only, {}, rt.Outcome(error=ValueError())) == "holds"
    assert verdict(only, {}, rt.Outcome(error=IndexError())) == "violated"
    assert verdict(only, {}, rt.Outcome(value=0)) == "violated"
    never = prop(pkg, kind="raises_only", exceptions=[])
    assert verdict(never, {}, rt.Outcome(error=ValueError())) == "violated"


def test_a_relation_calls_the_function_again(pkg: str) -> None:
    target = rt.load_target(target_spec(pkg, "slug"), None, {})
    idem = rt.load_property(
        {
            "id": "p",
            "kind": "relation",
            "transform": "{'text': result}",
            "check": "result2 == result",
        },
        target,
    )
    again = lambda a: target.call(a)[0]  # noqa: E731
    args: dict[str, object] = {"text": " Ab "}
    assert rt.judge(idem, args, again(args), again).status == "holds"
    broken = rt.load_property(
        {
            "id": "q",
            "kind": "relation",
            "transform": "{'text': result + 'X'}",
            "check": "result2 == result",
        },
        target,
    )
    assert rt.judge(broken, args, again(args), again).status == "violated"


def test_errors_in_the_property_itself_are_oracle_errors_not_violations(pkg: str) -> None:
    p = prop(pkg, expected="[][0]", when="1 / 0")
    assert rt.applies(p, {"year": 1, "month": 2}) is None
    q = prop(pkg, expected="[][0]")
    assert verdict(q, {"year": 1, "month": 2}, rt.Outcome(value=28)) == "oracle_error"


def test_properties_that_cannot_work_here_are_errors(pkg: str) -> None:
    with pytest.raises(rt.PropertyError, match="no name"):
        prop(pkg, expected="MISSING", names=["MISSING"])
    with pytest.raises(rt.PropertyError, match="not an exception"):
        prop(pkg, kind="raises", exceptions=["FEBRUARY"], names=["FEBRUARY"])
    with pytest.raises(rt.PropertyError, match="does not compile"):
        prop(pkg, expected="1 +")
    assert prop(pkg, expected="FEBRUARY", names=["FEBRUARY"]).namespace["FEBRUARY"] == 2


def test_checks_see_the_arguments_as_they_were_before_the_call(pkg: str) -> None:
    target = rt.load_target(target_spec(pkg, "sort_in_place"), None, {})
    p = rt.load_property({"id": "p", "kind": "returns", "check": "items == [3, 1, 2]"}, target)
    args: dict[str, object] = {"items": [3, 1, 2]}
    outcome = target.call(args)[0]
    assert outcome.value == [1, 2, 3] and args == {"items": [3, 1, 2]}
    assert rt.judge(p, args, outcome, rt.Outcome).status == "holds"


def test_docstring_examples_compare_by_value_by_repr_or_by_exception(pkg: str) -> None:
    target = rt.load_target(target_spec(pkg), None, {})

    def example(expected: str, compare: str) -> rt.Property:
        spec = {
            "id": "d",
            "kind": "example",
            "args": {"year": "2200", "month": "2"},
            "example_expected": expected,
            "compare": compare,
        }
        return rt.load_property(spec, target)

    twenty_nine = rt.Outcome(value=29)
    assert verdict(example("28", "eq"), {}, twenty_nine) == "violated"
    assert verdict(example("29", "eq"), {}, twenty_nine) == "holds"
    assert verdict(example("29", "repr"), {}, twenty_nine) == "holds"
    assert verdict(example("ValueError", "raises"), {}, rt.Outcome(error=ValueError())) == "holds"
    assert verdict(example("ValueError", "raises"), {}, twenty_nine) == "violated"
    assert rt.applies(example("28", "eq"), {"year": 2200, "month": 2}) is True
    assert rt.applies(example("28", "eq"), {"year": 2100, "month": 2}) is False


# --- M11 S4: a warning is not a raise -------------------------------------------------------------


class Noisy(UserWarning):
    pass


def warned(value: object = None, error: BaseException | None = None) -> rt.Outcome:
    """A call that raised Noisy, and what it did with warnings ignored."""
    return rt.Outcome(value=value, error=error, warned=rt.Outcome(error=Noisy("loud")))


def test_s4_a_property_is_judged_on_what_the_call_did_with_warnings_ignored(pkg: str) -> None:
    p = prop(pkg, check="result > 0")
    assert verdict(p, {}, warned(1)) == "holds"
    assert verdict(p, {}, warned(0)) == "violated"
    assert verdict(p, {}, warned(error=KeyError("k"))) == "violated"
    assert rt.judge(p, {}, warned(0), rt.Outcome).detail == "returned 0; the check does not hold"


def test_s4_a_property_naming_the_warning_is_judged_on_the_raise(pkg: str) -> None:
    names = {"exceptions": ["Warning"]}
    assert verdict(prop(pkg, kind="raises", **names), {}, warned(1)) == "holds"
    named = prop(pkg, kind="raises_only", check="result > 0", **names)
    assert verdict(named, {}, warned(0)) == "holds"
    other = {"exceptions": ["ValueError"]}
    assert verdict(prop(pkg, kind="raises", **other), {}, warned(1)) == "violated"
    unnamed = prop(pkg, kind="raises_only", check="result > 0", **other)
    assert verdict(unnamed, {}, warned(0)) == "violated"
    assert verdict(unnamed, {}, warned(1)) == "holds"


def test_s4_exceptions_on_a_returns_property_name_nothing(pkg: str) -> None:
    # `judge` reads `exceptions` only for the other kinds, so this one is judged on the value:
    # a violation is never reported on a raise the probe, which ignores warnings, can't repeat.
    p = prop(pkg, check="result > 0", exceptions=["Warning"])
    assert verdict(p, {}, warned(1)) == "holds"
    assert rt.judge(p, {}, warned(0), rt.Outcome).detail == "returned 0; the check does not hold"


def test_s4_a_docstring_example_saying_it_raises_the_warning_is_judged_on_the_raise(
    pkg: str,
) -> None:
    target = rt.load_target(target_spec(pkg), None, {})

    def example(expected: str, compare: str) -> rt.Property:
        spec = {"id": "d", "kind": "example", "args": {"year": "2200", "month": "2"},
                "example_expected": expected, "compare": compare}  # fmt: skip
        return rt.load_property(spec, target)

    assert verdict(example("Noisy", "raises"), {}, warned(29)) == "holds"
    assert verdict(example("ValueError", "raises"), {}, warned(29)) == "violated"
    assert verdict(example("29", "eq"), {}, warned(29)) == "holds"
    assert verdict(example("28", "eq"), {}, warned(29)) == "violated"


def test_s4_a_relation_s_second_call_follows_the_same_rule(pkg: str) -> None:
    def relation(**spec: Any) -> rt.Property:
        return prop(pkg, kind="relation", transform="{'year': 1}", **spec)

    def second(_: object) -> rt.Outcome:
        return warned(5)

    def crash(_: object) -> rt.Outcome:
        return warned(error=KeyError("k"))

    first = rt.Outcome(value=5)
    same = rt.judge(relation(check="result2 == result"), {}, first, second)
    assert same.status == "holds" and same.warned == ""
    differs = rt.judge(relation(check="result2 != result"), {}, first, second)
    assert differs.status == "violated" and differs.warned == "Noisy"
    crashed = rt.judge(relation(check="result2 == result"), {}, first, crash)
    assert crashed.status == "violated" and crashed.warned == "Noisy"
    named = rt.judge(relation(check="result2 != result", exceptions=["Warning"]), {}, first, second)
    assert named.status == "not_applicable"
    first_named = rt.judge(relation(check="result2 != result", exceptions=["Warning"]), {},
                           warned(5), second)  # fmt: skip
    assert first_named.status == "not_applicable"


def test_s4_the_report_adds_the_warning_s_name() -> None:
    assert warned(1).report() == {"kind": "returned", "type": "int", "repr": "1", "warned": "Noisy"}
    assert "warned" not in rt.Outcome(value=1).report()
    assert "warned" not in rt.Outcome(error=Noisy("x")).report()
    assert warned(error=KeyError("k")).report()["warned"] == "Noisy"


def _plain_target(function: Callable[..., object]) -> rt.Target:
    return rt.Target("t1", "m.py", function.__name__, sys.modules[__name__], __name__, function,
                     inspect.signature(function), {}, None)  # fmt: skip


def test_s4_the_judged_call_runs_again_only_when_a_warning_was_raised() -> None:
    def noisy(x: int) -> object:
        warnings.warn("loud", Noisy, stacklevel=1)
        return 7

    target = _plain_target(noisy)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        plain, _ = rt.judged_call(target, {"x": 1})  # the warning stays a warning here
    assert plain.value == 7 and plain.warned is None
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        again, _ = rt.judged_call(target, {"x": 1})
        # The caller's filters are back, and `Target.call` itself (the diff's) keeps the raise.
        raw, _ = target.call({"x": 1})
    assert again.value == 7 and again.warned is not None and isinstance(again.warned.error, Noisy)
    assert isinstance(raw.error, Noisy) and raw.warned is None


def test_s4_an_error_filter_the_code_set_itself_is_kept_on_every_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifier round 1, B1: the second call used to ignore every warning, so a package that makes
    its own warning an error on first use lost a raise its users get. Only the filters in force
    when the run started (the project's) are taken away; the second input shows it is the run's
    start that counts, not what was in force before each call."""
    configured: list[bool] = []

    def strict(x: int) -> object:
        if not configured:  # the package's own rule, set once on first use
            warnings.simplefilter("error", Noisy)
            configured.append(True)
        warnings.warn("loud", Noisy, stacklevel=1)
        return 7

    def chatty(x: int) -> object:
        warnings.warn("old", DeprecationWarning, stacklevel=1)
        return 7

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # the project's, in force before any code under test ran
        monkeypatch.setattr(rt, "_START_FILTERS", list(warnings.filters))
        for x in (1, 2):
            outcome, _ = rt.judged_call(_plain_target(strict), {"x": x})
            assert isinstance(outcome.error, Noisy) and outcome.warned is None, x
        # The project's own "error" still isn't a raise, with the code's filter beside it.
        other, _ = rt.judged_call(_plain_target(chatty), {"x": 1})
    assert other.value == 7 and other.warned is not None


def test_s4_a_warning_the_code_raises_itself_stays_the_outcome() -> None:
    def rude(x: int) -> object:
        raise Noisy("loud")

    outcome, _ = rt.judged_call(_plain_target(rude), {"x": 1})
    assert isinstance(outcome.error, Noisy) and outcome.warned is None


def test_s4_any_other_error_is_not_called_again() -> None:
    calls = []

    def broken(x: int) -> object:
        calls.append(x)
        raise ValueError("no")

    outcome, _ = rt.judged_call(_plain_target(broken), {"x": 1})
    assert isinstance(outcome.error, ValueError) and calls == [1]


# --- the attack -----------------------------------------------------------------------------------

REFERENCE = {
    "id": "ref",
    "kind": "returns",
    "when": "1 <= month <= 12 and year >= 1",
    "expected": "calendar.monthrange(year, month)[1]",
    "stdlib": ["calendar"],
}


def attack_plan(pkg: str, **target: Any) -> dict[str, Any]:
    rel = f"src/{pkg}/calendar.py"
    spec = target_spec(pkg, **{"properties": [REFERENCE], **target})
    return {
        "mode": "attack",
        "search_examples": 60,
        "fixed": {rel: [FIX_LINE, FIX_LINE + 1]},
        "targets": [spec],
    }


def test_the_grid_finds_the_neighbouring_century_year(pkg: str, run: Run) -> None:
    examples = [
        {"phase": "grid", "args": {"year": str(y), "month": "2"}}
        for y in (2100, 2101, 2099, 2200, 2000, 1900)
    ]
    events = run(attack_plan(pkg, examples=examples))
    grid = of(events, "violation", phase="grid")
    assert [v["args"] for v in grid] == [
        {"year": "2200", "month": "2"},
        {"year": "1900", "month": "2"},
    ]
    assert grid[0]["outcome"] == {"kind": "returned", "type": "int", "repr": "29"}
    assert grid[0]["expected"] == "28" and grid[0]["representable"] is True
    explicit = of(events, "end", unit="explicit")[0]
    assert explicit["reached"] == {f"src/{pkg}/calendar.py": [FIX_LINE, FIX_LINE + 1]}
    assert explicit["inputs"] >= 6


SMALL_FIRST = {"id": "small", "kind": "returns", "when": "len(items) > 0", "check": "result < 3"}


def first_plan(pkg: str, examples: int = 100) -> dict[str, Any]:
    rel = f"src/{pkg}/calendar.py"
    lists = {"items": "st.lists(st.integers(0, 10), min_size=1)"}
    spec = target_spec(pkg, "first", properties=[SMALL_FIRST], strategies=lists)
    return {
        "mode": "attack",
        "search_examples": examples,
        "fixed": {rel: [FIX_LINE]},
        "targets": [spec],
    }


def test_the_search_shrinks_a_violation_it_finds(pkg: str, run: Run) -> None:
    events = run(first_plan(pkg))
    found = of(events, "violation", phase="search")
    assert [v["args"] for v in found] == [{"items": "[3]"}]  # shrunk to the smallest breaking list
    assert found[0]["outcome"] == {"kind": "returned", "type": "int", "repr": "3"}
    assert of(events, "end", unit="search:small")
    assert run(first_plan(pkg)) == events  # derandomized: the same answer every time


def test_a_witness_that_contradicts_a_property_stops_it(pkg: str, run: Run) -> None:
    never = {"id": "never", "kind": "raises_only", "exceptions": []}
    witnesses = [
        {"id": "tests/test_c.py::test_bad_month", "args": {"year": "2023", "month": "13"}},
        {"id": "tests/test_c.py::test_leap", "args": {"year": "2024", "month": "2"}},
    ]
    events = run(attack_plan(pkg, properties=[REFERENCE, never], witnesses=witnesses))
    contradicted = of(events, "contradicted")
    assert [(c["property"], c["witness"]) for c in contradicted] == [
        ("never", "tests/test_c.py::test_bad_month")
    ]
    assert not of(events, "violation", property="never")
    assert not of(events, "begin", unit="search:never")  # a contradicted property is not searched
    assert of(events, "end", unit="explicit")[0]["contradicted"] == ["never"]


def test_advisory_witnesses_are_noted_and_decide_nothing(pkg: str, run: Run) -> None:
    witnesses = [
        {
            "id": "tests/test_pr.py::test_new",
            "advisory": True,
            "args": {"year": "1900", "month": "2"},
        }
    ]
    events = run(attack_plan(pkg, witnesses=witnesses))
    assert [a["witness"] for a in of(events, "advisory")] == ["tests/test_pr.py::test_new"]
    assert not of(events, "contradicted")


def test_a_docstring_example_that_holds_is_a_witness_and_one_that_fails_is_a_violation(
    pkg: str, run: Run
) -> None:
    holds = {
        "id": "doc1",
        "kind": "example",
        "args": {"year": "2023", "month": "13"},
        "example_expected": "ValueError",
        "compare": "raises",
    }
    fails = {
        "id": "doc2",
        "kind": "example",
        "args": {"year": "2200", "month": "2"},
        "example_expected": "28",
        "compare": "eq",
    }
    never = {"id": "never", "kind": "raises_only", "exceptions": []}
    events = run(attack_plan(pkg, properties=[never, holds, fails]))
    assert [(c["property"], c["witness"]) for c in of(events, "contradicted")] == [
        ("never", "the docstring example doc1")
    ]
    doc = of(events, "violation", property="doc2")
    assert [(v["phase"], v["args"]) for v in doc] == [("doc", {"year": "2200", "month": "2"})]


def test_crashes_no_property_covers_are_reported_as_unjudged(pkg: str, run: Run) -> None:
    only_february = {**REFERENCE, "id": "feb", "when": "month == 2 and year >= 1"}
    examples = [{"phase": "model", "args": {"year": "2023", "month": "13"}}]
    events = run(attack_plan(pkg, properties=[only_february], examples=examples))
    crashes = [c for c in of(events, "crash") if c["args"] == {"year": "2023", "month": "13"}]
    assert crashes and crashes[0]["outcome"]["type"] == "ValueError"


def test_boundaries_are_swept_around_typical_inputs_and_counted_once(pkg: str, run: Run) -> None:
    rel = f"src/{pkg}/calendar.py"
    nonempty = {"id": "ne", "kind": "returns", "when": "True", "check": "isinstance(result, int)"}
    plan = {
        "mode": "attack",
        "search_examples": 10,
        "fixed": {rel: [FIX_LINE]},
        "targets": [target_spec(pkg, "first", properties=[nonempty])],
    }
    events = run(plan)
    found = of(events, "violation", phase="boundary")
    assert [v["args"] for v in found] == [{"items": "[]"}]  # IndexError on the empty list
    assert found[0]["outcome"]["type"] == "IndexError"
    explicit = of(events, "begin", unit="explicit")[0]
    calls = of(events, "calling")
    assert explicit["count"] == len(calls) == len({c["input"] for c in calls})


def test_a_resumed_run_skips_finished_units_and_starts_after_the_hung_input(
    pkg: str, run: Run
) -> None:
    examples = [{"phase": "grid", "args": {"year": str(y), "month": "2"}} for y in (2200, 1900)]
    plan = attack_plan(pkg, examples=examples)
    plan |= {"explicit_from": {"t1": 1}, "skip": {"t1": ["search:ref"]}}
    events = run(plan)
    assert next(c["index"] for c in of(events, "calling")) == 1
    assert [v["args"]["year"] for v in of(events, "violation", phase="grid")] == ["1900"]
    assert not of(events, "begin", unit="search:ref")
    plan["skip"] = {"t1": ["explicit"]}
    plan["contradicted"] = {"t1": ["ref"]}
    events = run(plan)
    assert not of(events, "calling") and not of(events, "begin", unit="search:ref")


def test_a_target_that_does_not_import_is_reported_and_others_still_run(pkg: str, run: Run) -> None:
    plan = attack_plan(pkg)
    plan["targets"].insert(0, {"id": "t0", "path": "src/gone/x.py", "name": "f"})
    events = run(plan)
    assert "could not be imported" in of(events, "target", target="t0")[0]["error"]
    assert of(events, "target", target="t1")[0]["module"] == f"{pkg}.calendar"


def test_a_property_error_is_reported_and_the_others_still_run(pkg: str, run: Run) -> None:
    broken = {"id": "broken", "kind": "returns", "expected": "NOPE", "names": ["NOPE"]}
    events = run(attack_plan(pkg, properties=[broken, REFERENCE]))
    assert of(events, "property_error", property="broken")
    assert of(events, "begin", unit="search:ref")


def test_unrepresentable_search_inputs_are_flagged(pkg: str, run: Run) -> None:
    rel = f"src/{pkg}/calendar.py"
    plan = {
        "mode": "attack",
        "search_examples": 30,
        "fixed": {rel: [FIX_LINE]},
        "targets": [
            target_spec(
                pkg,
                "first",
                properties=[{"id": "small", "kind": "returns", "check": "result < 0"}],
                strategies={"items": "st.lists(st.integers(0, 5), min_size=1)"},
            )
        ],
    }
    events = run(plan)
    assert all(v["representable"] for v in of(events, "violation"))  # lists of ints are literals


# --- probes ---------------------------------------------------------------------------------------


def test_a_probe_reports_each_outcome_and_the_fixed_lines_it_ran(pkg: str, run: Run) -> None:
    rel = f"src/{pkg}/calendar.py"
    plan = {
        "mode": "probe",
        "fixed": {rel: [FIX_LINE, FIX_LINE + 1]},
        "targets": [target_spec(pkg), {"id": "t9", "path": rel, "name": "missing"}],
        "calls": [
            {"target": "t1", "args": {"year": "2200", "month": "2"}},
            {"target": "t1", "args": {"year": "2023", "month": "13"}},
            {"target": "t9", "args": {}},
            {"target": "t1", "args": {"year": "__import__('os')"}},
        ],
    }
    probes = of(run(plan, "probe"), "probe")
    assert probes[0]["outcome"] == {"kind": "returned", "type": "int", "repr": "29"}
    assert probes[0]["lines"] == {rel: [FIX_LINE]} and probes[0]["traced"] is True
    assert probes[1]["outcome"]["type"] == "ValueError" and probes[1]["lines"] == {}
    assert "no attribute" in probes[2]["missing"]
    assert probes[3]["missing"].startswith("bad input")


def test_the_coverage_plugin_records_lines_for_the_whole_session(
    pkg: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rel = f"src/{pkg}/calendar.py"
    out = tmp_path / "cov.jsonl"
    monkeypatch.setenv("TRACEFIX_OUT", str(out))
    monkeypatch.setenv("TRACEFIX_TRACE", json.dumps([rel]))
    rt.pytest_configure(None)
    try:
        module, _ = rt.resolve(rel, [])
        module.days_in_month(2100, 2)
    finally:
        rt.pytest_unconfigure(None)
    coverage = events_of(out)[0]
    assert coverage["event"] == "coverage" and coverage["traced"] is True
    assert {FIX_LINE, FIX_LINE + 1} <= set(coverage["files"][rel])


# --- what the runtime may import ------------------------------------------------------------------


def import_roots(source: str) -> set[str]:
    roots = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "no relative imports: the file runs outside the package"
            roots.add((node.module or "").split(".")[0])
    return roots - set(sys.stdlib_module_names)


def test_the_runtime_imports_only_the_standard_library_and_hypothesis() -> None:
    # What runs in the repo's own environment: nothing in it may come from tracefix (not
    # installed there, and a repo could plant a package of that name). The state readers ship
    # beside the runtime under a random name (harness.runtime_modules).
    shipped = runtime_modules("tracefix_rt_test")
    assert set(shipped) == {"tracefix_rt_test", "tracefix_rt_test_state"}
    assert import_roots(shipped["tracefix_rt_test"]) == {"hypothesis", "tracefix_rt_test_state"}
    assert import_roots(shipped["tracefix_rt_test_state"]) == set()
    # In the package, the runtime's one tracefix import is the line pointed at that name.
    in_package = Path(rt.__file__).read_text(encoding="utf-8")
    assert import_roots(in_package) == {"hypothesis", "tracefix"}
    froms = [n.module for n in ast.walk(ast.parse(in_package)) if isinstance(n, ast.ImportFrom)]
    assert [m for m in froms if m and m.startswith("tracefix")] == ["tracefix.runtime_state"]


# --- through a real run ---------------------------------------------------------------------------


HARNESS = """\
import {module} as runtime

PLAN = {plan!r}


def test_tracefix_attack():
    runtime.main(PLAN)
"""


def test_an_attack_runs_inside_a_real_pytest_run_and_leaves_nothing_in_the_copy(
    tmp_path: Path,
) -> None:
    rel = "src/cal/calendar.py"
    files = {
        "pyproject.toml": '[tool.pytest.ini_options]\npythonpath = ["src"]\n',
        "src/cal/__init__.py": "",
        rel: CALENDAR,
    }
    copy = write_files(tmp_path / "repo", files)
    examples = [{"phase": "grid", "args": {"year": "2200", "month": "2"}}]
    first = first_plan("cal", 50)["targets"][0] | {"id": "t2", "path": rel}
    plan = {
        "mode": "attack",
        "search_examples": 30,
        "fixed": {rel: [FIX_LINE, FIX_LINE + 1]},
        "targets": [
            {
                "id": "t1",
                "path": rel,
                "name": "days_in_month",
                "properties": [REFERENCE],
                "examples": examples,
            },
            first,
        ],
    }
    module = f"tracefix_rt_{uuid.uuid4().hex[:8]}"
    (copy / "tests").mkdir()
    (copy / "tests" / "test_tracefix_attack.py").write_text(
        HARNESS.format(module=module, plan=json.dumps(plan)), encoding="utf-8"
    )
    before = sorted(p.relative_to(copy).as_posix() for p in copy.rglob("*"))
    result = run_pytest(
        copy,
        ["tests/test_tracefix_attack.py"],
        reruns=0,
        timeout_s=180,
        probe=Probe(runtime_modules(module)),  # as the product ships it
    )
    assert result.outcome is Outcome.PASSED, result.first.output[-3000:]
    assert result.first.out is not None
    events = [json.loads(line) for line in result.first.out.splitlines()]
    assert events[0]["event"] == "start" and events[-1]["event"] == "done"
    assert [e["module"] for e in of(events, "target")] == ["cal.calendar"] * 2
    assert [v["args"] for v in of(events, "violation", phase="grid")] == [
        {"year": "2200", "month": "2"}
    ]
    assert [v["args"] for v in of(events, "violation", phase="search")] == [{"items": "[3]"}]
    after = sorted(
        p.relative_to(copy).as_posix() for p in copy.rglob("*") if "__pycache__" not in p.parts
    )
    assert after == before  # no .hypothesis folder, no module, nothing else in the copy


def test_every_explicit_input_order_is_deterministic(pkg: str) -> None:
    target = rt.load_target(target_spec(pkg), None, {})
    examples = [
        {"phase": "model", "args": {"year": "5", "month": "1"}},
        {"phase": "grid", "args": {"year": "2100", "month": "2"}},
    ]
    candidates = {"year": [{"value": "2100"}], "month": [{"value": "'x'"}]}
    spec = target_spec(pkg, examples=examples, candidates=candidates)
    first = rt.explicit_inputs(target, spec, 400)
    again = rt.explicit_inputs(target, spec, 400)
    assert [(i.phase, rt.input_key(i.args)) for i in first] == [
        (i.phase, rt.input_key(i.args)) for i in again
    ]
    phases = [phase for phase, _ in itertools.groupby(i.phase for i in first)]
    assert phases == ["grid", "evidence", "model", "boundary"]
    assert all(rt.accepts(int, i.args["month"]) for i in first)  # 'x' doesn't fit `month: int`


def test_an_example_naming_some_parameters_takes_the_rest_from_a_typical_input(
    pkg: str, run: Run
) -> None:
    witnesses = [{"id": "tests/test_c.py::test_leap", "args": {"year": "2024", "month": "2"}}]
    examples = [{"phase": "grid", "args": {"year": "2200"}}]
    events = run(attack_plan(pkg, witnesses=witnesses, examples=examples))
    assert [v["args"] for v in of(events, "violation", phase="grid")] == [
        {"year": "2200", "month": "2"}
    ]


def test_an_example_that_cannot_be_completed_is_dropped(pkg: str) -> None:
    target = rt.load_target(target_spec(pkg, "slug"), None, {})
    target.hints = {}  # no type hints and no witness: nothing to complete it from
    spec = {"examples": [{"phase": "grid", "args": {}}], "properties": []}
    assert rt.explicit_inputs(target, spec, 400) == []


def test_a_relation_is_not_judged_on_a_witness_whose_second_call_nobody_vouched_for(
    pkg: str, run: Run
) -> None:
    # Symmetry: f(-x) relates to f(x). The project's test vouches for days_in_month(2024, 2);
    # the second call (with month moved) is not vouched for, so the witness proves nothing here.
    relation = {
        "id": "rel",
        "kind": "relation",
        "transform": "{'month': 1}",
        "check": "result2 == 99",
        "exceptions": [],
    }
    witnesses = [{"id": "tests/test_c.py::test_leap", "args": {"year": "2024", "month": "2"}}]
    events = run(attack_plan(pkg, properties=[relation], witnesses=witnesses))
    assert not of(events, "contradicted")
    assert of(events, "violation", property="rel")  # attack inputs still judge it


def test_only_inputs_a_property_applies_to_are_counted(pkg: str, run: Run) -> None:
    # Every int boundary is tried, but the property speaks only about x == 1: one input counts,
    # in the explicit phase and in the search alike.
    rel = f"src/{pkg}/calendar.py"
    one = {"id": "one", "kind": "returns", "when": "items == [1]", "check": "result == 1"}
    plan = {
        "mode": "attack",
        "search_examples": 30,
        "fixed": {rel: [FIX_LINE]},
        "targets": [target_spec(pkg, "first", properties=[one])],
    }
    events = run(plan)
    assert of(events, "end", unit="explicit")[0]["inputs"] == 1
    assert of(events, "end", unit="search:one")[0]["inputs"] == 1


def test_a_doctest_compares_printed_output_like_doctest_does(pkg: str) -> None:
    # Verifier S2: a function that prints its answer and returns None matches `>>> f()` / `4`.
    target = rt.load_target(target_spec(pkg), None, {})
    spec = {"id": "d", "kind": "example", "args": {"year": "1", "month": "1"},
            "example_expected": "4", "compare": "repr"}  # fmt: skip
    example = rt.load_property(spec, target)
    printed = rt.Outcome(value=None, stdout="4\n")
    assert rt.judge(example, {}, printed, rt.Outcome).status == "holds"
    assert rt.judge(example, {}, rt.Outcome(value=4), rt.Outcome).status == "holds"
    assert rt.judge(example, {}, rt.Outcome(value=5), rt.Outcome).status == "violated"


def test_only_object_addresses_are_masked_never_hex_values() -> None:
    # Verifier N1: `'0xff'` is a value; `<object at 0x1f2e>` is noise.
    assert rt.Outcome(value="0xff").report()["repr"] == "'0xff'"
    assert "at 0x?" in rt.Outcome(value=object()).report()["repr"]


# --- verifier round 2 ---------------------------------------------------------------------------


def test_standard_library_modules_reach_expressions_without_the_modules_they_import() -> None:
    import calendar
    import importlib
    import types

    for name in ("calendar", "datetime", "decimal", "fractions", "math", "re", "statistics"):
        stand_in = rt._stand_in(importlib.import_module(name))
        assert not any(isinstance(v, types.ModuleType) for v in vars(stand_in).values()), name
    shown = rt._stand_in(calendar)
    assert not hasattr(shown, "sys") and shown.isleap(2000) is True


def test_expressions_get_only_the_safe_builtins() -> None:
    from tracefix.attack_rules import SAFE_BUILTINS

    allowed = rt._builtins()
    assert set(rt.SAFE_BUILTINS) == SAFE_BUILTINS  # the runtime's copy of the list stays equal
    assert {"open", "__import__", "getattr", "eval", "exec", "vars"}.isdisjoint(allowed)
    assert allowed["ValueError"] is ValueError
    with pytest.raises(NameError):
        eval("open('x')", {"__builtins__": allowed})


def test_nan_and_infinity_mentions_are_read_from_the_syntax_tree() -> None:
    for text in ("math.isnan(result)", 'x == float("nan")', "result < math.inf", "isfinite(x)"):
        assert rt._mentions_non_finite(text), text
    for text in ("result == nanos / 1e9", "info == tenant_id", "finance > 0", ""):
        assert not rt._mentions_non_finite(text), text


def test_decimal_and_complex_nan_count_as_non_finite() -> None:
    from decimal import Decimal

    assert rt._non_finite(Decimal("NaN"), 0) and rt._non_finite(complex(math.inf, 0), 0)
    assert rt._non_finite([1, {"a": Decimal("-Infinity")}], 0)
    assert not rt._non_finite((Decimal("1.5"), complex(1, 2)), 0)


def test_a_loaded_property_sees_stand_ins_and_safe_builtins_only(pkg: str) -> None:
    # Round 3: the runtime layer on its own (hygiene would stop these expressions first).
    import types

    p = prop(pkg, check="calendar.isleap(year)", stdlib=["calendar", "decimal"])
    shown = p.namespace["calendar"]
    assert isinstance(shown, types.SimpleNamespace) and not hasattr(shown, "sys")
    assert not any(isinstance(v, types.ModuleType) for v in vars(shown).values())
    assert not hasattr(shown, "setfirstweekday") and not hasattr(shown, "c")
    assert not hasattr(p.namespace["decimal"], "getcontext")
    builtins_seen = p.namespace["__builtins__"]
    assert isinstance(builtins_seen, dict) and "open" not in builtins_seen
    escape = rt.load_property(
        {"id": "e", "kind": "returns", "when": "calendar.sys.exit(0)", "stdlib": ["calendar"]},
        rt.load_target(target_spec(pkg), None, {}),
    )
    assert rt.applies(escape, {"year": 2000, "month": 2}) is None  # an oracle error, no exit


def test_an_expression_cannot_change_the_module_data_the_target_uses(pkg: str) -> None:
    # Round 3: `TABLE.clear() or ...` must not blind the target or later properties.
    target = rt.load_target(target_spec(pkg), None, {})
    target.module.TABLE = {"a": 1}  # type: ignore[attr-defined]
    p = rt.load_property(
        {"id": "p", "kind": "returns", "when": "TABLE.clear() is None", "names": ["TABLE"]},
        target,
    )
    assert rt.applies(p, {"year": 2000, "month": 2}) is True
    assert target.module.TABLE == {"a": 1}  # type: ignore[attr-defined]


def test_expressions_see_left_out_parameters_at_their_defaults(pkg: str) -> None:
    # Real-bug trial: humanize's naturalsize properties said `binary == False and gnu == False
    # and format == '%.1f'`; inputs leave those out, and the property applied to nothing.
    target = rt.load_target(target_spec(pkg, "size"), None, {})
    p = rt.load_property(
        {"id": "p", "kind": "returns", "when": "binary == False and fmt == '%.1f' and value > 0",
         "check": "result == fmt % value"},
        target,
    )  # fmt: skip
    assert rt.applies(p, {"value": 5}) is True
    assert rt.applies(p, {"value": 5, "binary": True}) is False


def test_a_default_that_is_not_a_plain_literal_stays_out_of_reach(pkg: str) -> None:
    # Verifier round 4: `opener=open` as a default let an expression open files; a sentinel
    # `object()` default, copied, never matched itself. Only literal defaults are visible.
    target = rt.load_target(target_spec(pkg, "save"), None, {})
    escape = rt.load_property(
        {"id": "e", "kind": "returns", "when": "opener('pwned.txt', 'a') is not None"}, target
    )
    assert rt.applies(escape, {"text": "x"}) is None  # an oracle error: opener is unbound
    assert not Path("pwned.txt").exists()
    assert escape.defaults == {}


# --- M11 S5: what a raise was, for the doubt flags ------------------------------------------------

RAISE_SHAPES = """\
import json


def one_line(x):
    raise ValueError("no")


def several_lines(x):
    raise ValueError(
        f"no: {x}"
    )


def on_an_if(x):
    if x: raise ValueError("no")


def helper(x):
    one_line(x)


def translated(x):
    try:
        int("x")
    except ValueError as err:
        raise KeyError("no") from err


def in_a_with(x):
    with open(__file__):
        raise ValueError("no")


def in_a_finally(x):
    try:
        raise ValueError("no")
    finally:
        x = 1


def a_builtin(x):
    return int("x")


def re_raised_crash(x):
    try:
        int("x")
    except ValueError:
        raise


def divides(x):
    return 1 / 0


def attribute(x):
    return x.nope


def key(x):
    return {}[x]


def asserted(x):
    assert x == 2, "no"


def from_the_stdlib(x):
    return json.loads("x")
"""


def _raised(source: str, name: str, traced: bool = False) -> dict[str, str]:
    """The report of a call to `name`, its module's file in the current directory."""
    path = Path("shapes.py").resolve()
    path.write_text(source, encoding="utf-8")
    scope: dict[str, Any] = {"__file__": str(path)}
    exec(compile(source, str(path), "exec"), scope)
    tracer = rt.LineTracer({str(path): "shapes.py"}) if traced else None
    if tracer is not None:
        tracer.start()
    try:
        scope[name](1)
    except Exception as exc:
        return rt.Outcome(error=exc).report()
    finally:
        if tracer is not None:
            tracer.close()  # stop, and give the sys.monitoring tool id back
    raise AssertionError(f"{name} did not raise")


@pytest.mark.parametrize("traced", [False, True])
@pytest.mark.parametrize(
    "name",
    ["one_line", "several_lines", "on_an_if", "helper", "translated", "in_a_with", "in_a_finally"],
)
def test_s5_a_raise_statement_in_the_project_is_named(pkg: str, name: str, traced: bool) -> None:
    # Traced too: from 3.12 sys.monitoring rewrites the code object the opcode is read from.
    report = _raised(RAISE_SHAPES, name, traced)
    assert (report["raised_by"], report["in_project"]) == ("raise", "yes"), report


@pytest.mark.parametrize("traced", [False, True])
@pytest.mark.parametrize(
    "name", ["a_builtin", "re_raised_crash", "divides", "attribute", "key", "asserted"]
)
def test_s5_a_crash_is_not_a_raise_statement(pkg: str, name: str, traced: bool) -> None:
    # An `assert` compiles to a raise, but says the code never expected this: it is no refusal.
    report = _raised(RAISE_SHAPES, name, traced)
    assert (report["raised_by"], report["in_project"]) == ("crash", "yes"), report


def test_s5_a_raise_in_the_standard_library_is_not_in_the_project(pkg: str) -> None:
    report = _raised(RAISE_SHAPES, "from_the_stdlib")
    assert report["raised_by"] == "raise" and "in_project" not in report


def test_s5_an_outcome_without_a_traceback_has_no_origin_but_a_report() -> None:
    report = rt.Outcome(error=ValueError("no")).report()
    assert report["raised_by"] == "crash" and "in_project" not in report


class _WindowsError(OSError):
    winerror = 206


class _BrokenError(OSError):
    @property
    def errno(self) -> int:  # type: ignore[override]
        raise RuntimeError("no")


@pytest.mark.parametrize(
    ("error", "facts"),
    [
        (OSError(errno.ENAMETOOLONG, "too long"), {"errno": "ENAMETOOLONG"}),
        (OSError(errno.ENOENT, "gone"), {"errno": "ENOENT"}),
        (_WindowsError("too long"), {"winerror": "206"}),
        (OSError("no number"), {}),
        (OSError([], "not a number"), {}),  # `errno` is whatever the first argument was
        (OSError(10**9, "unknown"), {}),
        (_BrokenError("no"), {}),  # code of the project: reading it must not end the run
        (ValueError("not an OS error"), {}),
    ],
)
def test_s5_an_os_error_says_which(error: Exception, facts: dict[str, str]) -> None:
    report = rt.Outcome(error=error).report()
    assert {k: report[k] for k in ("errno", "winerror") if k in report} == facts


def test_s5_the_new_facts_stay_out_of_a_returned_value() -> None:
    assert rt.Outcome(value=1).report() == {"kind": "returned", "type": "int", "repr": "1"}

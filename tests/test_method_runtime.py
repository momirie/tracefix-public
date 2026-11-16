"""M7.5: methods in the in-run code (attack_runtime: attack, probe and diff modes).

Tested in-process with a small throwaway package, as tests/test_attack_runtime.py and
tests/test_diff_runtime.py do for functions.
"""

import inspect
import json
import math
import sys
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import write_files

from tracefix import attack_rules
from tracefix import attack_runtime as rt

SHELF = '''\
"""Shelves."""
import threading


class Shelf:
    """A shelf with `size` slots."""

    registry: list[str] = []

    def __init__(self, size: int = 3, name: str = "s") -> None:
        if size < 0:
            raise ValueError("size must not be negative")
        self.size = size
        self.name = name
        self.items: list[int] = []

    def put(self, item: int) -> int:
        """Put `item` on the shelf; returns how many are on it now. Never more than `size`."""
        self.items.append(item)
        return len(self.items)

    def free(self) -> int:
        return self.size - len(self.items)

    @property
    def full(self) -> bool:
        return len(self.items) >= self.size

    @classmethod
    def of(cls, size: int) -> "Shelf":
        return cls(size)

    @staticmethod
    def slots(n: int) -> int:
        return n * 2

    def remember(self) -> int:
        Shelf.registry.append(self.name)
        return len(Shelf.registry)

    def enrol(self) -> int:
        self.registry.append(self.name)
        return len(self.registry)

    @classmethod
    def enrol_all(cls, name: str) -> int:
        cls.registry.append(name)
        return len(cls.registry)


class Sub(Shelf):
    def put(self, item: int) -> int:
        return 0


class Locked:
    def __init__(self) -> None:
        self.lock = threading.Lock()

    def peek(self, n: int) -> int:
        return n


class Needs:
    def __init__(self, path: str) -> None:
        raise OSError("no such file")

    def read(self, n: int) -> int:
        return n
'''

Events = list[dict[str, Any]]


@pytest.fixture
def pkg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A copy with `src/<unique package>/shelf.py`, as cwd, its src folder importable."""
    name = f"m75_{uuid.uuid4().hex[:8]}"
    copy = write_files(
        tmp_path / "copy", {f"src/{name}/__init__.py": "", f"src/{name}/shelf.py": SHELF}
    )
    monkeypatch.chdir(copy)
    monkeypatch.syspath_prepend(str(copy / "src"))
    yield name
    for module in [m for m in sys.modules if m == name or m.startswith(name + ".")]:
        del sys.modules[module]


def spec(pkg: str, name: str = "put", kind: str = "method", **extra: Any) -> dict[str, Any]:
    return {
        "id": "t1",
        "path": f"src/{pkg}/shelf.py",
        "name": name,
        "module_candidates": [f"{pkg}.shelf"],
        "owner": extra.pop("owner", "Shelf"),
        "kind": kind,
        **extra,
    }


@pytest.fixture
def run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., Events]:
    """Runs a plan in-process (attack, probe or diff) and returns the events it reported."""

    def go(plan: dict[str, Any], mode: str = "attack") -> Events:
        out = tmp_path / f"out-{uuid.uuid4().hex[:6]}.jsonl"
        monkeypatch.setenv("TRACEFIX_OUT", str(out))
        reporter = rt.Reporter()
        runner = {"attack": rt.run_attack, "probe": rt.run_probe, "diff": rt.run_diff}[mode]
        try:
            runner(plan, reporter)
        finally:
            reporter.close()
        return [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]

    return go


def of(events: Events, kind: str, **match: Any) -> Events:
    return [
        e for e in events if e["event"] == kind and all(e.get(k) == v for k, v in match.items())
    ]


# --- loading and calling --------------------------------------------------------------------------


def test_each_kind_loads_as_its_class_holds_it(pkg: str) -> None:
    put = rt.load_target(spec(pkg), None, {})
    assert list(put.signature.parameters) == ["item"] and put.receivers is not None
    assert put.owner is not None and put.owner.__name__ == "Shelf"
    assert put.receivers.vouched == ["Shelf()"]  # every constructor parameter has a default
    full = rt.load_target(spec(pkg, "full", "property"), None, {})
    assert list(full.signature.parameters) == [] and full.receivers is not None
    of_ = rt.load_target(spec(pkg, "of", "classmethod"), None, {})
    assert list(of_.signature.parameters) == ["size"] and of_.receivers is None
    outcome, _ = of_.call({"size": 2})
    assert type(outcome.value).__name__ == "Shelf"
    slots = rt.load_target(spec(pkg, "slots", "staticmethod"), None, {})
    assert slots.call({"n": 4})[0].value == 8


def test_object_code_tracefix_would_refuse_is_never_used(pkg: str) -> None:
    # Verifier round 1, S1: longer code comes back refused, which cut a diff short.
    assert rt.MAX_OBJECT_CODE == attack_rules.MAX_EXPRESSION
    long = "x" * rt.MAX_OBJECT_CODE
    put = rt.load_target(spec(pkg, vouched=[f"Shelf(name={long!r})", "Shelf(2)"]), None, {})
    assert put.receivers is not None and put.receivers.vouched == ["Shelf()", "Shelf(2)"]
    assert put.receivers.render({"name": "short"}) == "Shelf(name='short')"
    assert put.receivers.render({"name": long}) is None


@pytest.mark.parametrize(
    ("given", "reason"),
    [
        ({"name": "put", "kind": "property"}, "is a method here, not a property"),
        ({"name": "free", "kind": "method", "owner": "Sub"}, "not defined in the class itself"),
        ({"name": "threading", "kind": "method", "owner": "threading"}, "is not a class"),
    ],
)
def test_a_method_that_is_not_what_the_source_said_is_not_loaded(
    pkg: str, given: dict[str, str], reason: str
) -> None:
    with pytest.raises(rt.TargetError, match=reason):
        rt.load_target(spec(pkg, **given), None, {})


def test_a_call_builds_the_object_and_keeps_it_as_it_was_and_as_the_call_left_it(pkg: str) -> None:
    put = rt.load_target(spec(pkg), None, {})
    outcome, _ = put.call({"self": "Shelf(2)", "item": 7})
    assert outcome.value == 1 and outcome.error is None
    assert outcome.receiver.items == [7]  # type: ignore[attr-defined]
    assert outcome.before.items == []  # type: ignore[attr-defined]
    full = rt.load_target(spec(pkg, "full", "property"), None, {})
    assert full.call({"self": "Shelf(0)"})[0].value is True  # read, not called


@pytest.mark.parametrize(
    ("args", "kind"),
    [
        ({"self": "Shelf(-1)", "item": 1}, "ValueError"),  # the constructor refuses
        ({"self": "Shelf.slots(1)", "item": 1}, "NotAnObject"),
        ({"self": "Sub()", "item": 1}, "Overridden"),  # its put is not the changed one
        ({"item": 1}, "NoObject"),
        ({"self": "Shelf(", "item": 1}, "SyntaxError"),
        ({"self": "Other()", "item": 1}, "NameError"),  # a name the plan didn't give its code
    ],
)
def test_an_object_that_cannot_be_built_is_no_input(
    pkg: str, args: dict[str, object], kind: str
) -> None:
    put = rt.load_target(spec(pkg, receiver_names=["Sub"]), None, {})
    with pytest.raises(rt.Unbuilt) as caught:
        put.call(args)
    assert caught.value.kind == kind


def test_an_object_needing_io_is_never_built(pkg: str) -> None:
    read = rt.load_target(spec(pkg, "read", owner="Needs"), None, {})
    assert read.receivers is not None and read.receivers.vouched == []  # `path` is required
    with pytest.raises(rt.Unbuilt, match="OSError"):
        read.call({"self": "Needs('x')", "n": 1})


# --- properties see the object before and after the call -----------------------------------------


def load(target: rt.Target, **fields: Any) -> rt.Property:
    return rt.load_property({"id": "p", "kind": "returns", **fields}, target)


def test_properties_see_self_before_the_call_and_self_after_after_it(pkg: str) -> None:
    put = rt.load_target(spec(pkg), None, {})
    args = {"self": "Shelf(1)", "item": 5}
    outcome = put.call(args)[0]
    grew = load(put, check="len(self_after.items) == len(self.items) + 1 and result == 1")
    assert rt.judge(grew, args, outcome, lambda a: put.call(a)[0]).status == "holds"
    capped = load(put, check="len(self_after.items) <= self_after.size")
    full = {"self": "Shelf(0)", "item": 5}
    verdict = rt.judge(capped, full, put.call(full)[0], lambda a: put.call(a)[0])
    assert verdict.status == "violated"
    assert grew.uses_self and not capped.uses_self and not capped.scopes_objects
    assert load(put, when="self.size > 0", check="result > 0").scopes_objects


def test_a_property_reading_an_object_that_cannot_be_copied_is_not_judged(pkg: str) -> None:
    peek = rt.load_target(spec(pkg, "peek", owner="Locked"), None, {})
    args = {"self": "Locked()", "n": 3}
    outcome = peek.call(args)[0]
    assert outcome.before is rt.NO_COPY and outcome.receiver is not None
    reads = load(peek, check="result == n and self.lock is not None")
    assert rt.judge(reads, args, outcome, lambda a: peek.call(a)[0]).status == "oracle_error"
    after = load(peek, check="result == n and self_after.lock is not None")
    assert rt.judge(after, args, outcome, lambda a: peek.call(a)[0]).status == "holds"


def test_nan_and_huge_values_in_an_objects_code_count_like_any_input() -> None:
    values = rt._plain_values({"self": 'Shelf(size=float("nan"), name="x")', "item": 2})
    assert any(isinstance(v, float) and math.isnan(v) for v in values)
    assert 2**63 - 1 in rt._plain_values({"self": "Shelf(size=9223372036854775807)"})


# --- the attack -----------------------------------------------------------------------------------


CAPPED = {"id": "capped", "kind": "returns", "when": "True", "check": "result <= self_after.size"}
SCOPED = {**CAPPED, "id": "scoped", "when": "self.size >= 0"}


def attack(pkg: str, *properties: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"mode": "attack", "search_examples": 30, "fixed": {},
            "targets": [spec(pkg, properties=list(properties), **extra)]}  # fmt: skip


def test_a_made_up_object_counts_only_for_a_property_whose_when_names_self(
    pkg: str, run: Callable[..., Events]
) -> None:
    events = run(attack(pkg, CAPPED, SCOPED))
    # Shelf(size=0) is made up (a boundary of `size`): putting one item breaks both checks there.
    scoped = [v["args"]["self"] for v in of(events, "violation", property="scoped")]
    assert "'Shelf(size=0)'" in scoped
    # The property that doesn't scope its objects is judged on the typical Shelf() instead, where
    # the call holds: no violation, only a report-only note.
    assert not of(events, "violation", property="capped")
    assert any(c["args"]["self"] == "'Shelf(size=0)'" for c in of(events, "crash"))
    assert all(v["representable"] for v in of(events, "violation"))


def test_objects_that_cannot_be_built_are_noted_and_never_judged(
    pkg: str, run: Callable[..., Events]
) -> None:
    events = run(attack(pkg, SCOPED))
    notes = [n["note"] for n in of(events, "note")]
    assert any(n.startswith("no object from Shelf(size=-1): ValueError") for n in notes)
    end = of(events, "end", unit="explicit")[0]
    assert end["unbuilt"] >= 1
    assert all("size=-1" not in v["args"]["self"] for v in of(events, "violation"))


def test_with_no_typical_object_a_violation_needs_a_property_scoping_its_objects(
    pkg: str, run: Callable[..., Events]
) -> None:
    read = {"id": "r", "kind": "returns", "when": "True", "check": "result == n + 1"}
    plan = attack(pkg, read, name="read", owner="Needs")
    events = run(plan)  # no object of Needs ever builds: nothing is judged, nothing found
    assert not of(events, "violation") and of(events, "end", unit="explicit")[0]["inputs"] == 0


def test_all_params_with_no_strategy_are_named_but_the_notes_stop_at_the_first() -> None:
    def two(a: Any, b: Any, c: int = 0) -> Any:
        return a

    target = SimpleNamespace(signature=inspect.signature(two), hints={"c": int}, receivers=None)
    strategies, notes, missing = rt._strategies(target, {})  # type: ignore[arg-type]
    assert strategies is None and missing == ["a", "b"]
    # As before M11 S3: behaviour-change notes reach the Judge's request (judge.py), so unchanged.
    assert notes == ["no way to generate a, so there is no search"]


def test_an_error_type_named_like_a_message_stays_out_of_the_models_copy() -> None:
    # Verifier round 2 of M11: a class made at run time can carry any text in its name.
    seen = SimpleNamespace(unbuilt=0, first_unbuilt="", first_unbuilt_brief="",
                           reporter=SimpleNamespace(emit=lambda event: None),
                           target=SimpleNamespace(id="t1"))  # fmt: skip
    rt._Attack.no_object(seen, {"self": "Box()"}, rt.Unbuilt("secret: 31337", "boom"))  # type: ignore[arg-type]
    assert seen.first_unbuilt == "no object from Box(): secret: 31337: boom"
    assert seen.first_unbuilt_brief == "no object from Box(): an error"


def test_a_run_says_why_it_judged_nothing(pkg: str, run: Callable[..., Events]) -> None:
    # M11 S3. No object builds: the first error, in the explicit inputs and the search alike.
    read = {"id": "r", "kind": "returns", "when": "True", "check": "result == n + 1"}
    events = run(attack(pkg, read, name="read", owner="Needs"))
    explicit, search = of(events, "end", unit="explicit")[0], of(events, "end", unit="search:r")[0]
    assert explicit["first_unbuilt"].startswith("no object from Needs(")
    assert "OSError: no such file" in explicit["first_unbuilt"]
    # The model's copy: the error's type, not head's message (verifier round 1 of M11, S2).
    brief = explicit["first_unbuilt_brief"]
    assert brief.startswith("no object from Needs(") and brief.endswith(": OSError"), brief
    assert search["unbuilt"] > explicit["unbuilt"] and search["inputs"] == 0
    assert of(events, "no_strategy", target="t1")[0]["params"] == []  # objects were drawn
    # The object builds, but no `when` fits: a count, and no error.
    never = {"id": "n", "kind": "returns", "when": "False", "check": "True"}
    end = of(run(attack(pkg, never)), "end")[-1]
    assert end["inputs"] == 0 and end["unfit"] > 0 and end["oracle_errors"] == 0
    # `when` itself fails: an oracle error with its text, and not a `when` that did not fit.
    broken = {"id": "b", "kind": "returns", "when": "item.nope > 0", "check": "True"}
    end = of(run(attack(pkg, broken)), "end")[-1]
    assert end["inputs"] == 0 and end["unfit"] == 0 and end["oracle_errors"] > 0
    assert end["first_oracle_error"].startswith("AttributeError")


def test_a_probe_reports_an_object_it_cannot_build(pkg: str, run: Callable[..., Events]) -> None:
    plan = {
        "mode": "probe",
        "fixed": {},
        "targets": [spec(pkg)],
        "calls": [
            {"target": "t1", "args": {"self": "'Shelf(-1)'", "item": "1"}},
            {"target": "t1", "args": {"self": "'Shelf(1)'", "item": "1"}},
        ],
    }
    probes = of(run(plan, "probe"), "probe")
    assert probes[0]["unbuilt"].startswith("ValueError") and "outcome" not in probes[0]
    assert probes[1]["outcome"] == {"kind": "returned", "type": "int", "repr": "1"}


# --- the behaviour diff ---------------------------------------------------------------------------


def test_the_object_as_the_call_left_it_is_compared_and_not_its_code(pkg: str) -> None:
    put = rt.load_target(spec(pkg), None, {})
    _, one, _ = rt._call_and_report(put, {"self": "Shelf(2)", "item": 7})
    _, same, _ = rt._call_and_report(put, {"self": "Shelf(size=2)", "item": 7})
    _, other, _ = rt._call_and_report(put, {"self": "Shelf(3)", "item": 7})
    assert "7" in one["args_text"] and one["args"] == same["args"]  # the same object state
    assert one["args"] != other["args"]  # size differs after the call too


def test_data_kept_on_the_class_is_module_data(pkg: str) -> None:
    remember = rt.load_target(spec(pkg, "remember"), None, {})
    _, report, _ = rt._call_and_report(remember, {"self": "Shelf(name='a')"})
    assert "Shelf.registry" in report["state_text"] and "'a'" in report["state_text"]


@pytest.mark.parametrize(
    ("name", "kind", "args"),
    [
        ("enrol", "method", {"self": "Shelf(name='a')"}),
        ("enrol_all", "classmethod", {"name": "'a'"}),
    ],
)
def test_class_data_reached_only_through_self_or_cls_is_module_data(
    pkg: str, name: str, kind: str, args: dict[str, str]
) -> None:
    target = rt.load_target(spec(pkg, name, kind), None, {})
    _, report, _ = rt._call_and_report(target, args)
    assert "Shelf.registry" in report["state_text"] and "'a'" in report["state_text"]


def test_the_diff_reports_an_object_it_cannot_build_by_its_error(
    pkg: str, run: Callable[..., Events]
) -> None:
    target = spec(pkg, inputs=[{"phase": "witness", "args": {"self": "'Shelf(-1)'", "item": "1"}},
                               {"phase": "witness", "args": {"item": "1"}}])  # fmt: skip
    events = run({"mode": "diff", "fixed": {}, "targets": [target]}, "diff")
    outcomes = of(events, "outcome")
    assert outcomes[0]["unbuilt"] == "ValueError"
    assert outcomes[1]["unbindable"] == "no object to call the method on"


def test_a_method_has_many_inputs_even_without_parameters(pkg: str) -> None:
    free = rt.load_target(spec(pkg, "free"), None, {})
    inputs, stats = rt.diff_inputs(free, spec(pkg, "free"), 50, 40)
    assert len(inputs) > 1 and all("self" in i.args for i in inputs)
    assert stats["exhausted"] is False  # int and str constructor parameters: not finite

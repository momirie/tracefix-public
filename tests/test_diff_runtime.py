"""M7: the behaviour diff's in-run code (attack_runtime's diff mode).

Tested in-process with small throwaway packages (imported as tracefix.attack_runtime), and through
real pytest runs on two copies, as the stage will run it.
"""

import array
import collections
import dataclasses
import datetime
import decimal
import functools
import io
import itertools
import json
import logging
import os
import re
import sys
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import write_files

from tracefix import attack_runtime as rt
from tracefix import runtime_state as rs
from tracefix.harness import runtime_modules
from tracefix.runner import Outcome, Probe, run_pytest

BUCKETS = '''\
"""Things for the behaviour diff to call."""

import random

COUNTER = [0]


def bucket_of(value: int, width: int) -> int:
    """Return the start of the bucket of size `width` that contains `value`.

    Buckets truncate toward zero: bucket_of(-5, 10) == 0, bucket_of(-15, 10) == -10.
    """
    if width <= 0:
        raise ValueError(f"width must be positive, got {width}")
    return int(value / width) * width


def noisy(x: int) -> float:
    return random.random() + x


def counter(x: int) -> int:
    COUNTER[0] += 1
    return COUNTER[0]


def flag(on: bool) -> bool:
    return not on


def nothing() -> int:
    return 7


def parse(text: str) -> int:
    return int(text)


def shout(text: str) -> str:
    print(text)
    return text.upper()


def scaled(n: int, *, factor: int = 2) -> int:
    return n * factor


def only(a: int, b: int = 0, /, c: int = 0) -> int:
    return a + b + c


class Needs:
    def __init__(self, a):
        self.a = a


def needs(x: Needs, n: int = 0) -> int:
    return n


def untyped(x):
    return x > 10


def strict(n: int) -> int:
    if n < 0: raise ValueError("negative")  # noqa: E701
    return n


def noisy_side(n: int) -> int:
    import logging, sys, warnings
    logging.getLogger("diffpkg").warning("n is %s", n)
    warnings.warn(f"careful with {n}", UserWarning)
    sys.stderr.write(f"err {n}\\n")
    return 0


def wordy(n: int) -> str:
    raise ValueError("cannot raise here: " + str(n))


def long_print(n: int) -> int:
    print("x" * 5000 + str(n))
    return 0


class Box:
    def __init__(self, n: int) -> None:
        self.n = n


def boxed(n: int) -> list:
    return [Box(n)]


def byte_writer(n: int) -> int:
    import sys
    sys.stdout.buffer.write(b"out")
    sys.stderr.buffer.write(b"err")
    return n + 1


def quiet_logger(n: int) -> int:
    import logging
    log = logging.getLogger("diffpkg.quiet")
    log.propagate = False
    log.setLevel(logging.INFO)
    log.info("n is %s", n)
    return 0


globals()["dynamic"] = len
'''


@pytest.fixture
def pkg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A copy with `src/<unique package>/buckets.py`, as cwd, its src folder importable."""
    name = f"diff_{uuid.uuid4().hex[:8]}"
    copy = write_files(
        tmp_path / "copy", {f"src/{name}/__init__.py": "", f"src/{name}/buckets.py": BUCKETS}
    )
    monkeypatch.chdir(copy)
    monkeypatch.syspath_prepend(str(copy / "src"))
    yield name
    for module in [m for m in sys.modules if m == name or m.startswith(name + ".")]:
        del sys.modules[module]


def spec(pkg: str, name: str = "bucket_of", tid: str = "t1", **extra: Any) -> dict[str, Any]:
    return {
        "id": tid,
        "path": f"src/{pkg}/buckets.py",
        "name": name,
        "module_candidates": [f"{pkg}.buckets"],
        **extra,
    }


DOCS = [
    {"id": "t1.doc1", "args": {"value": "-5", "width": "10"}, "example_expected": "0",
     "compare": "eq"},
    {"id": "t1.doc2", "args": {"value": "-15", "width": "10"}, "example_expected": "-10",
     "compare": "eq"},
]  # fmt: skip

Events = list[dict[str, Any]]


@pytest.fixture
def run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[dict[str, Any]], Events]:
    def go(plan: dict[str, Any]) -> Events:
        out = tmp_path / f"out-{uuid.uuid4().hex[:6]}.jsonl"
        monkeypatch.setenv("TRACEFIX_OUT", str(out))
        reporter = rt.Reporter()
        try:
            rt.run_diff(plan, reporter)
        finally:
            reporter.close()
        return [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]

    return go


def of(events: Events, kind: str, **match: Any) -> Events:
    return [
        e for e in events if e["event"] == kind and all(e.get(k) == v for k, v in match.items())
    ]


def outcome(value: object = None, error: BaseException | None = None, out: str = "") -> rt.Outcome:
    return rt.Outcome(value=value, error=error, stdout=out)


# --- inputs ---------------------------------------------------------------------------------------


def test_inputs_come_in_order_once_each_and_as_plain_literals(pkg: str) -> None:
    target = rt.load_target(spec(pkg), None, {})
    plan = spec(
        pkg,
        properties=[{"kind": "example", "id": d["id"], "args": d["args"]} for d in DOCS],
        witnesses=[{"id": "tests/test_b.py::test_a", "args": {"value": "25", "width": "10"}}],
        examples=[{"phase": "evidence", "args": {"value": "100000000000000015", "width": "10"}}],
    )
    items, stats = rt.diff_inputs(target, plan, 200, 50)
    phases = [i.phase for i in items]
    assert phases[:4] == ["doc", "doc", "witness", "evidence"]
    assert phases.index("boundary") < phases.index("draw")
    assert set(phases) <= {"doc", "witness", "evidence", "boundary", "draw"}
    keys = [rt.input_key(i.args) for i in items]
    assert len(keys) == len(set(keys))  # no input twice
    assert all(rt.to_source(v) is not None for i in items for v in i.args.values())
    assert stats["requested"] == 50 and 0 < stats["drawn"] <= 50
    again, _ = rt.diff_inputs(target, plan, 200, 50)
    assert [rt.input_key(i.args) for i in again] == keys  # derandomized: the same every time


def test_draws_report_when_the_generator_runs_out_of_new_inputs(pkg: str) -> None:
    target = rt.load_target(spec(pkg, "flag"), None, {})
    _, stats = rt.diff_inputs(target, spec(pkg, "flag"), 200, 200)
    assert stats["exhausted"] is True and stats["drawn"] < 200


def test_a_function_without_parameters_gets_its_one_call(pkg: str) -> None:
    target = rt.load_target(spec(pkg, "nothing"), None, {})
    items, stats = rt.diff_inputs(target, spec(pkg, "nothing"), 200, 200)
    assert [(i.phase, i.args) for i in items] == [("call", {})]
    assert stats["exhausted"] is True


def test_an_input_that_does_not_fit_the_signature_is_never_bent_to_fit(pkg: str) -> None:
    def why(name: str, args: dict[str, object]) -> str | None:
        return rt.unbindable(rt.load_target(spec(pkg, name), None, {}).signature, args)

    assert why("scaled", {"n": 1}) is None
    assert why("scaled", {"n": 1, "factor": 3}) is None
    assert why("scaled", {"n": 1, "strict": True}) == "no parameter strict here"
    assert why("scaled", {"factor": 3}) == "the required parameter n is not given"
    assert why("only", {"a": 1, "c": 2}) is None
    assert why("only", {"a": 1, "b": 2}) is None
    assert why("only", {"b": 2}) == "the required parameter a is not given"


def test_a_positional_only_argument_after_a_left_out_one_is_unbindable() -> None:
    def f(a: int = 0, b: int = 0, /) -> int:
        return a + b

    import inspect

    assert rt.unbindable(inspect.signature(f), {"b": 1}) is not None
    assert rt.unbindable(inspect.signature(f), {"a": 1}) is None


# --- outcomes -------------------------------------------------------------------------------------


def test_the_digest_sees_what_the_shown_text_cuts_off() -> None:
    a = rt.diff_report(outcome("x" * 1000 + "a"))
    b = rt.diff_report(outcome("x" * 1000 + "b"))
    assert a["text"] == b["text"] and len(a["text"]) == rt.SHOWN_TEXT
    assert a["digest"] != b["digest"]


def test_two_different_huge_ints_never_look_the_same() -> None:
    limit = sys.get_int_max_str_digits()
    if not limit:
        pytest.skip("no int digit limit on this interpreter")
    a = rt.diff_report(outcome(10 ** (limit + 5)))
    b = rt.diff_report(outcome(10 ** (limit + 5) + 1))
    assert a["digest"] != b["digest"] and a["type"] == "int"


def test_an_outcome_names_its_type_module_and_printed_output() -> None:
    plain = rt.diff_report(outcome(3))
    printed = rt.diff_report(outcome(3, out="hello\n"))
    assert plain["kind"] == "returned" and plain["type"] == "int" and plain["module"] == "builtins"
    assert plain["out"] == "" and printed["out"] and plain["digest"] == printed["digest"]
    # Object addresses differ between runs: never part of what is compared.
    plain = rt.diff_report(outcome(object()))
    assert "0x" not in plain["text"]  # a default-repr object is written by its attributes
    masked = rt.diff_report(outcome(lambda: 0))
    assert "at 0x?" in masked["text"]  # any other repr's address is masked


def test_a_raise_says_whether_the_repo_or_python_raised_it(pkg: str) -> None:
    target = rt.load_target(spec(pkg), None, {})
    repo, _ = target.call({"value": 1, "width": 0})
    assert rt.diff_report(repo)["where"] == "repo"
    parse = rt.load_target(spec(pkg, "parse"), None, {})
    builtin, _ = parse.call({"text": "x"})
    report = rt.diff_report(builtin)
    assert report["type"] == "ValueError" and report["where"] == "python"


# --- through run_diff -----------------------------------------------------------------------------


def generate_plan(pkg: str, *targets: dict[str, Any], draws: int = 30) -> dict[str, Any]:
    return {"mode": "diff", "generate": True, "draws": draws, "max_explicit": 50,
            "fixed": {}, "targets": list(targets)}  # fmt: skip


def test_generation_reports_every_input_then_two_calls_for_each(pkg: str, run: Any) -> None:
    events = run(generate_plan(pkg, spec(pkg, docs=DOCS)))
    [stats] = of(events, "inputs", target="t1")
    inputs = of(events, "input", target="t1")
    outcomes = of(events, "outcome", target="t1")
    assert stats["count"] == len(inputs) == len(outcomes) > 0
    assert [e["index"] for e in inputs] == list(range(len(inputs)))
    assert [e["index"] for e in outcomes] == list(range(len(inputs)))
    assert all(e["stable"] for e in outcomes)
    by_index = {e["index"]: e for e in outcomes}
    docs = [e for e in inputs if e["phase"] == "doc"]
    assert [d["args"] for d in docs] == [d["args"] for d in DOCS]
    assert by_index[docs[0]["index"]]["docs"] == {"t1.doc1": "holds"}
    assert by_index[docs[1]["index"]]["docs"] == {"t1.doc2": "holds"}
    assert of(events, "end", target="t1")


def test_a_function_whose_two_calls_disagree_is_unstable(pkg: str, run: Any) -> None:
    events = run(generate_plan(pkg, spec(pkg, "noisy"), spec(pkg, "counter", "t2"), draws=5))
    inputs = {e["index"]: e["args"] for e in of(events, "input", target="t1")}
    small = [e for e in of(events, "outcome", target="t1") if inputs[e["index"]] == {"x": "0"}]
    # random() + 0 differs between the two calls; random() + 2**63 rounds to the same float
    assert small and not small[0]["stable"]
    assert of(events, "outcome", target="t2")
    assert not any(e["stable"] for e in of(events, "outcome", target="t2"))


def test_a_replay_calls_the_given_inputs_from_the_start_index(pkg: str, run: Any) -> None:
    inputs = [
        {"phase": "doc", "args": {"value": "-5", "width": "10"}},
        {"phase": "draw", "args": {"value": "7", "width": "2"}},
        {"phase": "draw", "args": {"value": "7", "width": "2", "strict": "True"}},
        {"phase": "draw", "args": {"value": "os.system('x')"}},
    ]
    plan = {"mode": "diff", "fixed": {}, "start": {"t1": 1},
            "targets": [spec(pkg, docs=DOCS, inputs=inputs)]}  # fmt: skip
    events = run(plan)
    assert not of(events, "inputs") and not of(events, "input")  # nothing generated in a replay
    outcomes = {e["index"]: e for e in of(events, "outcome", target="t1")}
    assert sorted(outcomes) == [1, 2, 3]  # index 0 was before the start
    assert outcomes[1]["outcome"]["text"] == "6"
    assert outcomes[2]["unbindable"] == "no parameter strict here"
    assert outcomes[3]["unbindable"] == "not a plain literal"


def test_a_run_of_one_input_alone_calls_only_that_input(pkg: str, run: Any) -> None:
    # Round 11: after the time limit, the running input runs alone to tell a hang from a slow run.
    inputs = [{"phase": "draw", "args": {"value": str(v), "width": "2"}} for v in range(4)]
    plan = {"mode": "diff", "fixed": {}, "start": {"t1": 1}, "stop": {"t1": 2},
            "targets": [spec(pkg, inputs=inputs)]}  # fmt: skip
    assert [e["index"] for e in of(run(plan), "outcome", target="t1")] == [1]


def test_a_docstring_example_the_code_breaks_is_reported_violated(pkg: str, run: Any) -> None:
    docs = [{"id": "t1.doc9", "args": {"value": "-5", "width": "10"}, "example_expected": "-10",
             "compare": "eq"}]  # fmt: skip
    inputs = [{"phase": "doc", "args": {"value": "-5", "width": "10"}}]
    events = run({"mode": "diff", "fixed": {}, "targets": [spec(pkg, docs=docs, inputs=inputs)]})
    assert of(events, "outcome")[0]["docs"] == {"t1.doc9": "violated"}


def test_a_target_that_does_not_load_is_reported_and_the_others_still_run(
    pkg: str, run: Any
) -> None:
    missing = spec(pkg, "no_such_function")
    events = run(generate_plan(pkg, missing, spec(pkg, "flag", "t2")))
    assert "no attribute" in of(events, "target", target="t1")[0]["error"]
    assert of(events, "outcome", target="t2")


def test_fix_lines_are_traced_on_the_side_that_has_them(pkg: str, run: Any) -> None:
    path = f"src/{pkg}/buckets.py"
    line = next(n for n, t in enumerate(BUCKETS.splitlines(), 1) if "int(value / width)" in t)
    inputs = [{"phase": "draw", "args": {"value": "7", "width": "2"}},
              {"phase": "draw", "args": {"value": "7", "width": "0"}}]  # fmt: skip
    plan = {"mode": "diff", "fixed": {path: [line]}, "targets": [spec(pkg, inputs=inputs)]}
    outcomes = of(run(plan), "outcome")
    assert [e["ran"] for e in outcomes] == [True, False]  # the raise comes before the line


# --- through real runs, as the stage runs it ------------------------------------------------------

HARNESS = """\
import {module} as runtime

PLAN = {plan!r}


def test_tracefix_diff():
    runtime.main(PLAN)
"""


def real_run(copy: Path, plan: dict[str, Any]) -> list[dict[str, Any]]:
    module = f"tracefix_rt_{uuid.uuid4().hex[:8]}"
    (copy / "tests").mkdir(exist_ok=True)
    test = copy / "tests" / "test_tracefix_diff.py"
    test.write_text(HARNESS.format(module=module, plan=json.dumps(plan)), encoding="utf-8")
    try:
        result = run_pytest(
            copy,
            ["tests/test_tracefix_diff.py"],
            reruns=0,
            timeout_s=180,
            probe=Probe(runtime_modules(module)),  # as the product ships it
        )
    finally:
        test.unlink()
    assert result.outcome is Outcome.PASSED, result.first.output[-3000:]
    assert result.first.out is not None
    events = [json.loads(line) for line in result.first.out.splitlines()]
    assert events[0]["event"] == "start" and events[-1]["event"] == "done"
    return events


def test_base_replays_heads_inputs_and_only_the_changed_outcomes_differ(tmp_path: Path) -> None:
    rel = "src/stats/buckets.py"
    config = '[tool.pytest.ini_options]\npythonpath = ["src"]\n'
    head_source = BUCKETS.replace("int(value / width) * width", "value // width * width")
    common = {"pyproject.toml": config, "src/stats/__init__.py": "", "tests/conftest.py": ""}
    base = write_files(tmp_path / "base", {**common, rel: BUCKETS})
    head = write_files(tmp_path / "head", {**common, rel: head_source})
    target = {"id": "t1", "path": rel, "name": "bucket_of", "module_candidates": ["stats.buckets"],
              "docs": DOCS}  # fmt: skip
    before = sorted(p.relative_to(head).as_posix() for p in head.rglob("*"))
    generated = real_run(head, {"mode": "diff", "generate": True, "draws": 40, "max_explicit": 60,
                                "fixed": {}, "targets": [target]})  # fmt: skip
    inputs = [{"phase": e["phase"], "args": e["args"]} for e in of(generated, "input")]
    replayed = real_run(base, {"mode": "diff", "fixed": {},
                               "targets": [{**target, "inputs": inputs}]})  # fmt: skip
    head_out = {e["index"]: e for e in of(generated, "outcome")}
    base_out = {e["index"]: e for e in of(replayed, "outcome")}
    assert sorted(head_out) == sorted(base_out) == list(range(len(inputs)))
    changed = [i for i in head_out if head_out[i]["outcome"] != base_out[i]["outcome"]]
    assert changed  # the negative values
    for i in changed:  # negative values off a bucket edge, and huge ones (the float bug)
        value, width = int(inputs[i]["args"]["value"]), int(inputs[i]["args"]["width"])
        assert width > 0 and ((value < 0 and value % width) or abs(value) >= 2**53), inputs[i]
    doc = next(i for i, item in enumerate(inputs) if item["args"] == DOCS[0]["args"])
    assert base_out[doc]["docs"] == {"t1.doc1": "holds"}
    assert head_out[doc]["docs"] == {"t1.doc1": "violated"}
    assert (head_out[doc]["outcome"]["text"], base_out[doc]["outcome"]["text"]) == ("-10", "0")
    after = sorted(
        p.relative_to(head).as_posix() for p in head.rglob("*") if "__pycache__" not in p.parts
    )
    assert after == before  # nothing left in the copy


# --- verifier round 1 -----------------------------------------------------------------------------


def test_a_generator_that_breaks_never_counts_as_run_out(pkg: str) -> None:
    # B2a: Hypothesis can't build Needs (untyped __init__): zero draws, and not "exhausted".
    target = rt.load_target(spec(pkg, "needs"), None, {})
    _, stats = rt.diff_inputs(target, spec(pkg, "needs"), 200, 50)
    assert stats["drawn"] == 0 and stats["exhausted"] is False
    assert any("the draws stopped early" in n for n in stats["notes"])


def test_only_a_finite_domain_can_run_out(pkg: str) -> None:
    # B2b: an untyped parameter fed by a few seeds runs dry fast; that is not every input.
    target = rt.load_target(spec(pkg, "untyped"), None, {})
    seeds = {"x": [{"value": "10", "compared": True}, {"value": "11", "compared": True}]}
    _, stats = rt.diff_inputs(target, spec(pkg, "untyped", candidates=seeds), 200, 200)
    assert stats["drawn"] < 200 and stats["exhausted"] is False
    flag = rt.load_target(spec(pkg, "flag"), None, {})
    assert rt.finite_domain(flag) and not rt.finite_domain(target)


def test_the_copys_own_folder_never_looks_like_a_change(pkg: str) -> None:
    import os

    here = rt.diff_report(outcome(os.path.join(os.getcwd(), "data.txt")))
    assert os.getcwd() not in here["text"] and "<copy>" in here["text"]


def test_a_one_line_raise_is_the_repos_own_message(pkg: str) -> None:
    target = rt.load_target(spec(pkg, "strict"), None, {})
    raised, _ = target.call({"n": -1})
    assert rt.diff_report(raised)["where"] == "repo"


# --- round 5 --------------------------------------------------------------------------------------


def side_of(pkg: str, name: str, n: int) -> dict[str, str]:
    target = rt.load_target(spec(pkg, name), None, {})
    _, report, _ = rt._call_and_report(target, {"n": n})
    return report


def test_logged_output_warnings_and_stderr_are_compared(pkg: str) -> None:
    one, again, two = (
        side_of(pkg, "noisy_side", 1),
        side_of(pkg, "noisy_side", 1),
        side_of(pkg, "noisy_side", 2),
    )
    assert one["side"] and one["side"] == again["side"]  # stable: both calls agree
    assert one["side"] != two["side"]  # a different log line, warning and stderr
    assert one["digest"] == two["digest"]  # the result itself is the same


def test_objects_with_the_default_repr_are_compared_by_their_attributes(pkg: str) -> None:
    one, two = side_of(pkg, "boxed", 1), side_of(pkg, "boxed", 2)
    assert one["digest"] != two["digest"]
    assert "Box(n=1)" in one["text"] and "0x" not in one["text"]


def test_printed_output_is_compared_in_full(pkg: str) -> None:
    # Through a real call: what differs is past the first 5,000 printed characters.
    one, two = side_of(pkg, "long_print", 1), side_of(pkg, "long_print", 2)
    assert one["digest"] == two["digest"] and one["out"] != two["out"]


def test_the_word_raise_inside_a_string_is_not_a_raise(pkg: str) -> None:
    target = rt.load_target(spec(pkg, "wordy"), None, {})
    raised, _ = target.call({"n": 1})
    assert rt.diff_report(raised)["where"] == "repo"  # the real raise on that line
    assert not rt._raises('x = "raise ValueError"')
    assert rt._raises("if x: raise ValueError('no')")


# --- round 6: snapshots, streams, loggers, bound names --------------------------------------------


class Item:
    def __init__(self, n: int) -> None:
        self.n = n


@dataclasses.dataclass
class Holder:
    item: object


class StrSlots:
    __slots__ = "value"

    def __init__(self, v: int) -> None:
        self.value = v


class DictSlots:
    __slots__ = ("__dict__", "value")

    def __init__(self, v: int) -> None:
        self.value = v


class ListWithTag(list):  # type: ignore[type-arg]
    tag = 0


class Coded(Exception):
    code = 0


def tagged(x: int) -> ListWithTag:
    value = ListWithTag([1])
    value.tag = x  # type: ignore[assignment]
    return value


def coded(x: int) -> Coded:
    error = Coded("same message")
    error.code = x
    return error


class Node:
    def __init__(self, v: int, nxt: "Node | None" = None) -> None:
        self.v, self.nxt = v, nxt


def chain(length: int, first: int) -> Node | None:
    head = None
    for i in range(length):
        head = Node(first if i == 0 else i, head)
    return head


SAME_LOOKING = {
    "dataclass holding an object": (Holder(Item(1)), Holder(Item(2))),
    "namedtuple": (collections.namedtuple("NT", "item")(Item(1)),
                   collections.namedtuple("NT", "item")(Item(2))),
    "deque": (collections.deque([Item(1)]), collections.deque([Item(2)])),
    "defaultdict": (collections.defaultdict(list, a=[Item(1)]),
                    collections.defaultdict(list, a=[Item(2)])),
    "string __slots__": (StrSlots(1), StrSlots(2)),
    "slots with __dict__": (DictSlots(1), DictSlots(2)),
    "list subclass attribute": (tagged(1), tagged(2)),
    "exception attribute": (coded(1), coded(2)),
    "text that says at 0x": ("bad opcode at 0x10", "bad opcode at 0x2f"),
}  # fmt: skip


@pytest.mark.parametrize("name", list(SAME_LOOKING))
def test_values_whose_repr_looks_the_same_still_differ(name: str) -> None:
    a, b = SAME_LOOKING[name]
    (ta, oa), (tb, ob) = rt.snapshot(a), rt.snapshot(b)
    assert not oa and not ob and ta != tb


@pytest.mark.parametrize(
    "value",
    [map(str, [1]), (lambda: 0), (x for x in [1]), chain(300, 0)],
    ids=["iterator", "function", "generator", "too-deep"],
)
def test_values_whose_whole_state_cannot_be_read_are_opaque(value: object) -> None:
    _, opaque = rt.snapshot(value)
    assert opaque


def test_cycles_are_written_once_and_fast() -> None:
    nodes = [Node(i) for i in range(50)]
    for a, b in itertools.pairwise(nodes):
        a.nxt = b
        b.prev = a  # type: ignore[attr-defined]
    text, opaque = rt.snapshot(nodes[0])
    assert not opaque and "<cycle>" in text and len(text) < 50_000


def test_the_streams_have_a_buffer_like_the_real_ones(pkg: str) -> None:
    target = rt.load_target(spec(pkg, "byte_writer"), None, {})
    outcome, report, _ = rt._call_and_report(target, {"n": 1})
    assert outcome.error is None and outcome.value == 2  # no AttributeError on .buffer
    assert report["out"] and report["side"]  # both streams were read


def test_records_of_a_logger_that_does_not_propagate_are_seen(pkg: str) -> None:
    one, two = side_of(pkg, "quiet_logger", 1), side_of(pkg, "quiet_logger", 2)
    assert one["side"] and one["side"] != two["side"]


def test_a_name_bound_at_run_time_is_reported(pkg: str, run: Any) -> None:
    plan = {"mode": "diff", "fixed": {}, "targets": [],
            "absent": [{"path": f"src/{pkg}/buckets.py", "name": "dynamic",
                        "module_candidates": [f"{pkg}.buckets"]},
                       {"path": f"src/{pkg}/buckets.py", "name": "nowhere",
                        "module_candidates": [f"{pkg}.buckets"]}]}  # fmt: skip
    events = run(plan)
    assert [e["name"] for e in of(events, "bound")] == ["dynamic"]


# --- round 7: an allowlist snapshot ---------------------------------------------------------------


class Mixin:
    pass


class Tag(str, Mixin):
    pass


class Masked(str):
    def __str__(self) -> str:
        return "masked"

    def __repr__(self) -> str:
        return "Masked()"


class DunderSlot:
    __slots__ = ("__v__",)

    def __init__(self, v: int) -> None:
        self.__v__ = v


class Slot:
    __slots__ = ("x",)

    def __init__(self, v: int) -> None:
        self.x = v


class Shadowed(Slot):
    @property  # type: ignore[misc]
    def x(self) -> int:  # a property hiding the slot's value
        return 0


def shadowed(v: int) -> Shadowed:
    value = Shadowed.__new__(Shadowed)
    vars(Slot)["x"].__set__(value, v)
    return value


class Dec(decimal.Decimal):
    pass


def shared(copy: bool) -> list[list[int]]:
    inner = [1]
    return [inner, list(inner) if copy else inner]


READ_IN_FULL = {
    "str subclass with a mixin": (Tag("a"), Tag("b")),
    "str subclass hiding its value": (Masked("a"), Masked("b")),
    "slot named like a dunder": (DunderSlot(1), DunderSlot(2)),
    "slot under a property": (shadowed(1), shadowed(2)),
    "deque maxlen": (collections.deque([1], maxlen=3), collections.deque([1])),
    "partial of a named function": (functools.partial(pow, 2), functools.partial(pow, 3)),
    "Decimal subclass": (Dec(1), Dec(2)),
    "OSError filename": (OSError(2, "gone", "a.txt"), OSError(2, "gone", "b.txt")),
    "ImportError name": (ImportError("m", name="a"), ImportError("m", name="b")),
    "a shared list or a copy": (shared(False), shared(True)),
    "exception cause": (ValueError("x"), ValueError("x").with_traceback(None)),
}  # fmt: skip
READ_IN_FULL["exception cause"][1].__cause__ = KeyError("k")


@pytest.mark.parametrize("name", list(READ_IN_FULL))
def test_state_the_snapshot_used_to_miss_is_read(name: str) -> None:
    # Verifier round 7, B3 and B5 and the nits: each pair snapshotted the same.
    a, b = READ_IN_FULL[name]
    (ta, oa), (tb, ob) = rt.snapshot(a), rt.snapshot(b)
    assert not oa and not ob and ta != tb, (ta, tb)


C_STATE = {
    "re.Match": lambda: re.search("[0-9]+", "a12"),
    "partial of a lambda": lambda: functools.partial(lambda: 0),
    "array": lambda: array.array("i", [1]),
    "itertools.count": lambda: itertools.count(),
    "io.StringIO": lambda: io.StringIO("a"),
    "dict keys view": lambda: {}.keys(),
    "class made at run time": lambda: collections.namedtuple("Rec", "a"),
    "defaultdict with a lambda": lambda: collections.defaultdict(lambda: 0),
}


@pytest.mark.parametrize("name", list(C_STATE))
def test_c_state_and_code_made_at_run_time_are_opaque(name: str) -> None:
    # Verifier round 7, B2 and B4: these were read as "a Python class with no attributes".
    _, opaque = rt.snapshot(C_STATE[name]())
    assert opaque


def test_an_exception_reports_what_it_holds_besides_its_message() -> None:
    def report(error: BaseException) -> dict[str, str]:
        return rt.diff_report(rt.Outcome(error=error))

    plain, worded = report(ValueError("a")), report(ValueError("b"))
    assert plain["rest"] == worded["rest"] and plain["digest"] != worded["digest"]
    coded = ValueError("a")
    coded.code = 1  # type: ignore[attr-defined]
    assert report(coded)["rest"] != plain["rest"]


def test_what_reaches_the_file_descriptors_is_seen(pkg: str) -> None:
    # Round 7, B8: output that bypasses sys.stdout (a stream kept from import time, C code).
    write_files(Path.cwd(), {f"src/{pkg}/raw.py": RAW})
    target = rt.load_target(
        {
            "id": "t1",
            "path": f"src/{pkg}/raw.py",
            "name": "raw",
            "module_candidates": [f"{pkg}.raw"],
        },
        None,
        {},
    )
    one = rt._call_and_report(target, {"n": 1})[1]
    two = rt._call_and_report(target, {"n": 2})[1]
    assert "fd1 1" in one["side_text"] and one["side"] != two["side"]


RAW = "import os\n\n\ndef raw(n: int) -> int:\n    os.write(1, str(n).encode())\n    return 0\n"


def test_module_data_follows_the_code(pkg: str) -> None:
    # Round 7, B6 and B7: a rebound number, another module's list, a class attribute, a name
    # the call binds for the first time.
    write_files(Path.cwd(), {f"src/{pkg}/store.py": STORE, f"src/{pkg}/uses.py": USES})
    for name in ("bump", "saved", "registered", "first", "dynamic"):
        target = rt.load_target(
            {"id": "t1", "path": f"src/{pkg}/uses.py", "name": name,
             "module_candidates": [f"{pkg}.uses"]}, None, {},
        )  # fmt: skip
        _, report, _ = rt._call_and_report(target, {"n": 1})
        assert report["state"] and not report["data_opaque"], name
    pure = rt.load_target(spec(pkg), None, {})
    assert rt._call_and_report(pure, {"value": 1, "width": 1})[1]["state"] == ""


STORE = "ITEMS = []\n\n\ndef save(n):\n    ITEMS.append(n)\n"
USES = """\
from . import store

_COUNT = 0


class Registry:
    items: list = []


def bump(n: int) -> int:
    global _COUNT
    _COUNT += 1
    return n


def saved(n: int) -> int:
    store.save(n)
    return n


def registered(n: int) -> int:
    Registry.items.append(n)
    return n


def first(n: int) -> int:
    global _LATER
    _LATER = n
    return n


def dynamic(n: int) -> int:
    globals()["_MADE_" + str(n)] = n
    return n
"""
# --- round 8: more module data, value types that hide state, locks and loggers --------------------

HIDDEN = """\
import functools
import json
import time
import logging
import os
import threading
import types
from typing import Optional, TypeVar

T = TypeVar("T")
Alias = Optional[list[int]]
FIXED = types.MappingProxyType({"a": 1})
OPS = {"add": lambda a, b: a + b}


class Registry:
    items: list = []
    seen: dict = {}
    _cache: dict = {}

    def add(self, n):
        self.items.append(n)

    def mark(self, n):
        type(self).seen[n] = True

    @classmethod
    def remember(cls, n):
        cls._cache[n] = n

    def keep(self, n):
        self._cache.setdefault(n, []).append(n)


def via_self(n: int) -> int:
    Registry().add(n)
    return n


def via_type(n: int) -> int:
    Registry().mark(n)
    return n


def via_cls(n: int) -> int:
    Registry.remember(n)
    return n


def via_setdefault(n: int) -> int:
    Registry().keep(n)
    return n


def _factory():
    seen = []

    def record(n):
        seen.append(n)

    return record


_record = _factory()


def via_closure(n: int) -> int:
    _record(n)
    return n


_STORE = []


def _real(tag, n):
    _STORE.append((tag, n))


_helper = functools.partial(_real, "t")


def via_partial(n: int) -> int:
    _helper(n)
    return n


def counted(n: int) -> int:
    counted.calls = getattr(counted, "calls", 0) + 1
    return n


def memo(n: int, _memo={}) -> int:
    _memo[n] = n
    return n


_log = logging.getLogger("hidden.leaky")


def leaky(n: int) -> int:
    _log.addHandler(logging.NullHandler())
    return n


def configured(n: int, debug: bool = False) -> int:
    ns = types.SimpleNamespace()
    setattr(ns, "debug", debug)
    return n + len(FIXED) + OPS["add"](1, 1) + len(os.environ) * 0


def typed(n: int) -> int:
    return n if isinstance(n, int) and Alias is not None and T is not None else 0


_handler = logging.StreamHandler(open(1, "w", closefd=False, buffering=1))
_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
_timed = logging.getLogger("hidden.timed")
_timed.addHandler(_handler)
_timed.setLevel(logging.INFO)
_timed.propagate = False


def timed(n: int) -> int:
    _timed.info("doubling %s", n)
    return 2 * n


_precise = logging.getLogger("hidden.precise")
_precise_handler = logging.StreamHandler(open(1, "w", closefd=False, buffering=1))
_precise_handler.setFormatter(
    logging.Formatter("%(asctime)s.%(msecs)03d +%(relativeCreated)d pid=%(process)d "
                      "thread=%(thread)d %(message)s", datefmt="%H:%M:%S")
)
_precise.addHandler(_precise_handler)
_precise.setLevel(logging.INFO)
_precise.propagate = False


def precise(n: int) -> int:
    _precise.info("doubling %s", n)
    return 2 * n


def remember(func):
    seen = {}

    @functools.wraps(func)
    def wrapper(key):
        if key not in seen:
            seen[key] = func(key)
        return seen[key]

    return wrapper


@remember
def _square(n):
    return n * n


@remember
def _cube(n):
    return n * n * n


def via_wraps(n: int) -> int:
    return _square(n) + _cube(0) * 0


class Remembering:
    def __init__(self, func):
        functools.update_wrapper(self, func)
        self.seen = {}

    def __call__(self, key):
        self.seen[key] = self.__wrapped__(key)
        return self.seen[key]


@Remembering
def _double(n):
    return 2 * n


def via_decorator_object(n: int) -> int:
    return _double(n)


_SEEN = []


def _keep(n):
    _SEEN.append(n)
    return n


def _drop(n):
    return n


HANDLERS = {"keep": _keep, "drop": _drop}


def via_table(n: int) -> int:
    return HANDLERS["keep"](n)


@functools.lru_cache(maxsize=None)
def _slow(n):
    return n + 1


def cached(n: int) -> int:
    return _slow(n)


def plain_memo(func):
    cache = {}

    def wrapper(x):
        if x not in cache:
            cache[x] = func(x)
        return cache[x]

    return wrapper


@plain_memo
def _m2(x):
    return 2 * x


@plain_memo
def _m3(x):
    return 3 * x


def via_plain_memo(n: int) -> int:
    return _m3(n) + _m2(n)


def save(n: int) -> None:
    with open("last.txt", "w", encoding="utf-8") as file:
        file.write(str(n))


def stamped(n: int) -> None:
    with open("last.json", "w", encoding="utf-8") as file:
        json.dump({"n": n, "at": time.time_ns()}, file)


def log_line(n: int) -> None:
    with open("lines.log", "a", encoding="utf-8") as file:
        file.write(f"{n}\\n")


def moved(n: int) -> None:
    os.rename("a.txt", "b.txt")


LIMIT = 10
_hits = {}


def clamp(n: int) -> int:
    _hits[n] = _hits.get(n, 0) + 1
    return min(n, LIMIT)
"""


EVENTS = """\
import os

_events = open("events.log", "a", encoding="utf-8")


def note(n: int) -> int:
    _events.write(f"{n}\\n")
    _events.flush()
    return n


def note_and_mkdir(n: int) -> int:
    _events.write(f"{n}\\n")
    _events.flush()
    os.makedirs("made", exist_ok=True)  # an event that walks the copy again
    return n
"""


def hidden(pkg: str, name: str) -> Any:
    write_files(Path.cwd(), {f"src/{pkg}/hidden.py": HIDDEN})
    spec_ = {"id": "t1", "path": f"src/{pkg}/hidden.py", "name": name,
             "module_candidates": [f"{pkg}.hidden"]}  # fmt: skip
    return rt.load_target(spec_, None, {})


@pytest.mark.parametrize(
    "name",
    ["via_self", "via_type", "via_cls", "via_setdefault", "via_closure", "via_partial",
     "counted", "memo", "leaky", "via_wraps", "via_decorator_object", "via_table"],
)  # fmt: skip
def test_module_data_reached_through_classes_closures_and_functions(pkg: str, name: str) -> None:
    # Verifier round 8, B2: each call wrote state that module_data did not see.
    _, report, _ = rt._call_and_report(hidden(pkg, name), {"n": 1})
    assert report["state"] and not report["data_opaque"], report


@pytest.mark.parametrize("name", ["configured", "typed", "cached"])
def test_type_hints_proxies_environ_and_lambdas_in_data_are_read(pkg: str, name: str) -> None:
    # Round 8, S1: these made every input's module data unreadable (no L3 for a good fix).
    _, report, _ = rt._call_and_report(hidden(pkg, name), {"n": 1})
    assert not report["data_opaque"] and not report["state"], report


def test_log_times_do_not_make_a_call_unstable(pkg: str) -> None:
    # Round 8, S2: a handler printing %(asctime)s to stdout gave each call different output.
    target = hidden(pkg, "timed")
    one = rt._call_and_report(target, {"n": 1})[1]
    time.sleep(0.02)
    again = rt._call_and_report(target, {"n": 1})[1]
    two = rt._call_and_report(target, {"n": 2})[1]
    assert "<log time> doubling 1" in one["side_text"]
    assert one["side"] == again["side"] and one["side"] != two["side"]


class Zone(datetime.tzinfo):
    def __init__(self, hours: int) -> None:
        self.hours = hours

    def utcoffset(self, _dt: datetime.datetime | None) -> datetime.timedelta:
        return datetime.timedelta(hours=self.hours)


class Obj:
    def __init__(self, v: int) -> None:
        self.v = v


def held(lock: Any) -> Any:
    lock.acquire()
    return lock


def shared_bytes(copy: bool) -> list[bytearray]:
    buf = bytearray(b"x")
    return [buf, bytearray(buf) if copy else buf]


def event(on: bool) -> threading.Event:
    flag = threading.Event()
    if on:
        flag.set()
    return flag


def logger_at(level: int) -> logging.Logger:
    log = logging.getLogger("tracefix.probe.level")  # one logger: only its level differs
    log.setLevel(level)
    return log


class Stamp(datetime.datetime):
    pass


class Clock(datetime.time):
    @property
    def tzinfo(self) -> datetime.tzinfo | None:  # type: ignore[override]
        return None  # can't hide the real one: the base's own field is read


HIDING = {
    "datetime with a project tzinfo": (
        lambda: datetime.datetime(2020, 1, 1, tzinfo=Zone(5)),
        lambda: datetime.datetime(2020, 1, 1, tzinfo=Zone(3)),
    ),
    "datetime subclass with a project tzinfo": (
        lambda: Stamp(2020, 1, 1, 12, tzinfo=Zone(1)),
        lambda: Stamp(2020, 1, 1, 12, tzinfo=Zone(5)),
    ),
    "time subclass hiding its project tzinfo": (
        lambda: Clock(12, tzinfo=Zone(1)),
        lambda: Clock(12, tzinfo=Zone(5)),
    ),
    "long pattern": (lambda: re.compile("a" * 300 + "X"), lambda: re.compile("a" * 300 + "Y")),
    "slice of objects": (lambda: slice(Obj(1)), lambda: slice(Obj(2))),
    "shared bytearray": (lambda: shared_bytes(False), lambda: shared_bytes(True)),
    "event set or not": (lambda: event(False), lambda: event(True)),
    "semaphore value": (lambda: threading.Semaphore(1), lambda: threading.Semaphore(5)),
    "lock held or free": (lambda: threading.Lock(), lambda: held(threading.Lock())),
    "rlock held or free": (lambda: threading.RLock(), lambda: held(threading.RLock())),
    "logger level": (lambda: logger_at(logging.INFO), lambda: logger_at(logging.DEBUG)),
}


@pytest.mark.parametrize("name", list(HIDING))
def test_state_hidden_in_value_types_locks_and_loggers_is_read(name: str) -> None:
    # Round 8, B3 and B4: each pair snapshotted the same.
    make_a, make_b = HIDING[name]
    (ta, oa), (tb, ob) = rt.snapshot(make_a()), rt.snapshot(make_b())
    assert not oa and not ob and ta != tb, (ta, tb)


def test_a_lambda_is_read_by_its_code_only_in_module_data() -> None:
    shot = rs.Snapshot(code_by_print=True)
    one, two = shot.text(lambda a: a + 1), rs.Snapshot(code_by_print=True).text(lambda a: a + 2)
    assert not shot.opaque and one != two
    assert rt.snapshot(lambda a: a + 1)[1]  # a result that is a lambda stays opaque


def test_a_value_shown_only_by_an_address_is_opaque() -> None:
    # Round 9 (nit with B1): a zone read from an in-memory file shows only the file's address.
    shot = rs.Snapshot()
    assert shot._shown("ZoneInfo.from_file(<_io.BytesIO object at 0x1f2e>)") == "..."
    assert shot.opaque


def test_every_log_time_and_id_is_fixed(pkg: str) -> None:
    # Round 9, S1: %(msecs)03d and %(relativeCreated)d made every pair of calls differ.
    target = hidden(pkg, "precise")
    one = rt._call_and_report(target, {"n": 1})[1]
    time.sleep(0.02)
    again = rt._call_and_report(target, {"n": 1})[1]
    two = rt._call_and_report(target, {"n": 2})[1]
    assert "doubling 1" in one["side_text"] and "pid=0 thread=0" in one["side_text"]
    assert one["side"] == again["side"] and one["side"] != two["side"]


def test_wrappers_made_by_one_decorator_keep_their_own_state(pkg: str) -> None:
    # Round 9, B2: functools.wraps gives every wrapper the wrapped function's name, and both
    # wrappers share one code object: each still has its own closure.
    walk = rs._Walk(hidden(pkg, "via_wraps").function)
    closures = sorted(label for label in walk.places if "<closure seen>" in label)
    assert len(closures) == 2, closures
    assert all("remember.<locals>.wrapper" in label for label in closures), closures


def test_module_data_a_call_leaves_alone_is_not_part_of_its_change(pkg: str) -> None:
    # Round 10, B1: all module data was one text, so a constant only head reaches (a correct fix
    # that starts using LIMIT) made every input whose cache changed look changed.
    report = rt._call_and_report(hidden(pkg, "clamp"), {"n": 50})[1]
    assert "_hits" in report["state_text"] and "LIMIT" not in report["state_text"], report


def test_wrappers_are_named_by_their_binding_not_by_the_walk_order(pkg: str) -> None:
    # Round 10, B1: two wrappers from one decorator without functools.wraps were numbered in the
    # order the walk met them, which a fix calling them through a new helper changes.
    walk = rs._Walk(hidden(pkg, "via_plain_memo").function)
    closures = sorted(label for label in walk.places if "<closure cache>" in label)
    assert closures == [
        f"{pkg}.hidden._m2<plain_memo.<locals>.wrapper>.<closure cache>",
        f"{pkg}.hidden._m3<plain_memo.<locals>.wrapper>.<closure cache>",
    ], closures


def changed_by(pkg: str, name: str, module: str = "hidden", source: str = "") -> str:
    """What `name` changed in the copy over two calls, as the diff checks it per function."""
    if source:
        write_files(Path.cwd(), {f"src/{pkg}/{module}.py": source})
        target = rt.load_target({"id": "t1", "path": f"src/{pkg}/{module}.py", "name": name,
                                 "module_candidates": [f"{pkg}.{module}"]}, None, {})  # fmt: skip
    else:
        target = hidden(pkg, name)
    before = rt.copy_files()
    rt._call_and_report(target, {"n": 1})
    rt._call_and_report(target, {"n": 2})
    return rt.files_changed(before)


@pytest.mark.parametrize(
    ("name", "written"),
    [("save", "last.txt"), ("stamped", "last.json"), ("log_line", "lines.log"),
     ("moved", "a.txt, b.txt")],
)  # fmt: skip
def test_a_function_that_changes_files_in_the_copy_is_reported(
    pkg: str, name: str, written: str
) -> None:
    # Developer, 8 Oct 2026 (verifier round 11): what a function writes is not compared; that it
    # wrote anything keeps L3 out of reach for it. Round 9 and 10's per-call comparison is gone.
    Path("a.txt").write_text("x", encoding="utf-8")
    time.sleep(0.2)  # older than the racy window: read by its times only
    assert changed_by(pkg, name) == written


def test_writes_through_a_file_opened_at_import_are_reported(pkg: str) -> None:
    # A log opened before the calls (at import, or by the project's conftest) raises no event
    # per write: the check doesn't depend on seeing the writes, only on the files themselves.
    assert changed_by(pkg, "note", "events", EVENTS) == "events.log"
    assert changed_by(pkg, "note_and_mkdir", "events", EVENTS) == "events.log"


def test_a_function_that_writes_nothing_reports_nothing(pkg: str) -> None:
    assert changed_by(pkg, "cached") == ""


def test_a_same_size_rewrite_in_one_clock_tick_is_seen(pkg: str) -> None:
    # Round 11, B1: a rewrite with the same size and time (a coarse file clock) was missed.
    Path("tick.txt").write_text("1", encoding="utf-8")
    info = os.stat("tick.txt")
    before = rt.copy_files()  # the file is racy (just written): its content is read
    Path("tick.txt").write_text("2", encoding="utf-8")
    os.utime("tick.txt", ns=(info.st_atime_ns, info.st_mtime_ns))
    assert rt.files_changed(before) == "tick.txt"


def test_a_rewrite_given_a_fixed_time_is_seen(pkg: str) -> None:
    # Round 11, B1: reproducible-output code sets a fixed time after writing.
    Path("out.txt").write_text("00000001", encoding="utf-8")
    old = time.time_ns() - 10**9
    os.utime("out.txt", ns=(old, old))
    before = rt.copy_files()
    Path("out.txt").write_text("00000002", encoding="utf-8")
    os.utime("out.txt", ns=(10**18, 10**18))
    assert rt.files_changed(before) == "out.txt"


def test_a_copy_with_too_many_files_is_not_vouched_for(
    pkg: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rt, "MAX_WATCHED", 1)
    assert "not checked" in rt.files_changed(rt.copy_files())

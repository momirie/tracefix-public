"""M10 part 2: Tracefix's in-run code inside a project's Python 3.9 or 3.10.

The shipped runtime (harness.runtime_modules) runs the same fixed plans in real pytest runs on
3.9, 3.10 and Tracefix's own Python; what it reports must match, apart from what the version
itself changes (the start event's version). Plus the static rules that keep it runnable there.
"""

import ast
import json
import subprocess
import sys
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from conftest import make_repo, old_python, write_files
from synthetic import repro, settings
from test_attack_runtime import CALENDAR, FIX_LINE, REFERENCE, first_plan

from tracefix import attack_runtime, runtime_state
from tracefix import behaviour_diff as behaviour_diff_module
from tracefix.attack import AttackStatus, break_my_fix
from tracefix.behaviour_diff import BehaviourStatus, behaviour_diff
from tracefix.diffscope import compute_scope
from tracefix.guard import mutator_context, source_files
from tracefix.harness import HARNESS, runtime_modules
from tracefix.interpreter import check, current
from tracefix.linetrace import fix_line_coverage
from tracefix.llm import FakeProvider
from tracefix.pipeline import client_for
from tracefix.prompts import adversary, mutator, python_note, reproducer
from tracefix.repro import build_context
from tracefix.runner import Outcome, Probe, run_pytest
from tracefix.sandbox import sandbox_level
from tracefix.workspace import RunSettings, Workspace

OLD = ["3.9", "3.10"]
PKG = "cal"
REL = f"src/{PKG}/calendar.py"
Events = list[dict[str, Any]]
CALLER = """\
from cal.calendar import days_in_month, is_leap


def test_days():
    assert days_in_month(2024, 2) == 29
    assert is_leap(2000)


def test_fails():
    assert days_in_month(2100, 2) == 28
"""


def _python(version: str | None) -> tuple[str, bool]:
    """(executable, has -P) for an old version, or Tracefix's own Python for None."""
    if version is None:
        return sys.executable, True
    return str(old_python(version)), False


def _copy(tmp_path: Path, pytest_ini: str = "", source: str = CALENDAR) -> Path:
    files = {
        "pyproject.toml": f'[tool.pytest.ini_options]\npythonpath = ["src"]\n{pytest_ini}',
        f"src/{PKG}/__init__.py": "",
        REL: source,
        "tests/test_caller.py": CALLER,
    }
    return write_files(tmp_path / f"repo-{uuid.uuid4().hex[:6]}", files)


def shipped(
    tmp_path: Path,
    version: str | None,
    plan: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
    **project: str,
) -> Events:
    """The runtime's events from one real run: a harness test running `plan`, or (no plan) the
    copy's own test file with the runtime loaded as a plugin and `env` set. `project`: `_copy`'s
    pytest settings and source, for a project other than the calendar."""
    python, safe_path = _python(version)
    copy = _copy(tmp_path, **project)
    module = f"tracefix_rt_{uuid.uuid4().hex[:8]}"
    if plan is not None:
        mode = plan["mode"]
        code = HARNESS.format(mode=mode, module=module, plan=json.dumps(plan, sort_keys=True))
        (copy / "tests" / f"test_tracefix_{mode}.py").write_text(code, encoding="utf-8")
        targets = [f"tests/test_tracefix_{mode}.py"]
        probe = Probe(runtime_modules(module))
    else:
        targets = ["tests/test_caller.py"]
        probe = Probe(runtime_modules(module), (module,), env or {})
    result = run_pytest(copy, targets, reruns=0, timeout_s=180, python=python,
                        safe_path=safe_path, probe=probe, pytest_args=["-s"])  # fmt: skip
    assert result.outcome in (Outcome.PASSED, Outcome.FAILED), result.first.output[-3000:]
    return [json.loads(line) for line in (result.first.out or "").splitlines()]


def comparable(events: Events) -> Events:
    """Events without what the Python version itself changes."""
    return [{k: v for k, v in e.items() if not (e["event"] == "start" and k == "python")}
            for e in events]  # fmt: skip


def attack_plan() -> dict[str, Any]:
    examples = [{"phase": "grid", "args": {"year": "2200", "month": "2"}}]
    search = first_plan(PKG, 50)["targets"][0] | {"id": "t2", "path": REL}
    return {
        "mode": "attack",
        "search_examples": 30,
        "fixed": {REL: [FIX_LINE, FIX_LINE + 1]},
        "targets": [
            {"id": "t1", "path": REL, "name": "days_in_month", "module_candidates":
             [f"{PKG}.calendar"], "properties": [REFERENCE], "examples": examples},
            search,
        ],
    }  # fmt: skip


def probe_plan() -> dict[str, Any]:
    return {
        "mode": "probe",
        "fixed": {REL: [FIX_LINE, FIX_LINE + 1]},
        "targets": [{"id": "t1", "path": REL, "name": "days_in_month",
                     "module_candidates": [f"{PKG}.calendar"]}],
        "calls": [{"target": "t1", "args": {"year": "2200", "month": "2"}},
                  {"target": "t1", "args": {"year": "2023", "month": "13"}}],
    }  # fmt: skip


def diff_plan() -> dict[str, Any]:
    return {
        "mode": "diff", "generate": True, "draws": 25, "max_explicit": 40, "fixed": {},
        "targets": [{"id": "t1", "path": REL, "name": "days_in_month",
                     "module_candidates": [f"{PKG}.calendar"]}],
    }  # fmt: skip


def replay_plan(generated: Events) -> dict[str, Any]:
    """The diff as base runs it: the inputs head generated, given as a list (no Hypothesis)."""
    inputs = [{"phase": e["phase"], "args": e["args"]} for e in generated if e["event"] == "input"]
    target = diff_plan()["targets"][0]
    return {"mode": "diff", "fixed": {}, "targets": [{**target, "inputs": inputs}]}


def same_hypothesis(version: str) -> bool:
    """Whether the old venv has the Hypothesis Tracefix's own environment has (the pins: 3.10
    yes, 3.9 no, it can't install that one): only then are Hypothesis's draws the same."""
    found = check(str(old_python(version)), "basic").interpreter
    return found is not None and found.hypothesis == current().hypothesis


def outside_search(events: Events) -> Events:
    """The events that don't come from a Hypothesis search unit."""
    kept, searching = [], False
    for event in comparable(events):
        unit = str(event.get("unit", ""))
        searching = searching or (event["event"] == "begin" and unit.startswith("search"))
        if not searching:
            kept.append(event)
        searching = searching and not (event["event"] == "end" and unit.startswith("search"))
    return kept


def violations(events: Events) -> Events:
    return [e for e in events if e["event"] == "violation"]


@pytest.mark.parametrize("version", OLD)
@pytest.mark.parametrize("mode", ["attack", "probe", "diff"])
def test_the_runtime_reports_the_same_on_an_old_python(
    tmp_path: Path, version: str, mode: str
) -> None:
    """Everything matches where Hypothesis is the same version. Where it isn't (3.9), its draws
    differ, so: an attack's explicit inputs and its violations (shrunk) match, and the diff,
    replaying the inputs head generated as base does, matches exactly."""
    plan = {"attack": attack_plan, "probe": probe_plan, "diff": diff_plan}[mode]()
    own = shipped(tmp_path, None, plan)
    exact = same_hypothesis(version) or mode == "probe"
    if mode == "diff" and not exact:
        plan = replay_plan(own)
        own = shipped(tmp_path, None, plan)
        exact = True
    old = shipped(tmp_path, version, plan)
    assert old[0]["python"] == [int(n) for n in version.split(".")]
    assert old[-1]["event"] == "done" and own[-1]["event"] == "done"
    if exact:
        assert comparable(old) == comparable(own)
    else:
        assert outside_search(old) == outside_search(own)
        assert violations(old) == violations(own) != []


@pytest.mark.parametrize("version", OLD)
def test_s6_a_string_parameter_gets_the_same_boundaries_in_the_same_order(
    tmp_path: Path, version: str
) -> None:
    plan = diff_plan()
    plan["targets"][0]["name"] = "echo"
    source = "def echo(text: str) -> str:\n    return text\n"
    events = shipped(tmp_path, version, plan, source=source)
    sent = [e["args"]["text"] for e in events if e["event"] == "input" and e["phase"] == "boundary"]
    assert [attack_runtime.from_source(text) for text in sent] == list(
        attack_runtime.STR_BOUNDARIES
    )
    assert set(attack_runtime.TRICKY_STRINGS) <= set(attack_runtime.STR_BOUNDARIES)


def test_the_3_10_venv_has_the_same_hypothesis_so_one_comparison_is_exact() -> None:
    """Keeps the attack's search compared draw for draw somewhere: if Tracefix's Hypothesis
    moves on, re-pin tests/old_pythons/requirements-3.10.txt to match."""
    assert same_hypothesis("3.10")


@pytest.mark.parametrize("version", OLD)
def test_line_tracing_reports_the_same_on_an_old_python(tmp_path: Path, version: str) -> None:
    env = {"TRACEFIX_TRACE": json.dumps([REL])}
    old = shipped(tmp_path, version, env=env)
    own = shipped(tmp_path, None, env=env)
    coverage = [e for e in old if e["event"] == "coverage"]
    assert len(coverage) == 1 and coverage[0]["traced"] is True
    assert FIX_LINE in coverage[0]["files"][REL]
    assert old == own


@pytest.mark.parametrize("version", OLD)
def test_below_3_11_the_call_recorder_reports_nothing(tmp_path: Path, version: str) -> None:
    """Calls are placed by column, which code objects give from 3.11 on: an older Python
    reports no calls at all, so none can count (the behaviour diff doesn't even ask)."""
    spec = {"file": "tests/test_caller.py", "targets": [{"path": REL, "name": "days_in_month"}]}
    env = {"TRACEFIX_CALLS": json.dumps(spec)}
    assert [e for e in shipped(tmp_path, version, env=env) if e["event"] == "calls"] == []
    own = [e for e in shipped(tmp_path, None, env=env) if e["event"] == "calls"]
    assert len(own) == 1 and own[0]["calls"]  # the recorder itself works where it can


@pytest.mark.parametrize("version", OLD)
def test_the_runtime_runs_at_this_isolation_level(tmp_path: Path, version: str) -> None:
    python = old_python(version)
    found = check(str(python), sandbox_level()).interpreter
    assert found is not None and found.hypothesis is not None


WARNS = """\
import warnings


def days_in_month(year, month):
    warnings.warn("nothing found", UserWarning)
    return month + 1
"""
ERRORS = 'filterwarnings = ["error"]\n'  # what photutils' pyproject does
WARNS_TARGET = {"id": "t1", "path": REL, "name": "days_in_month",
                "module_candidates": [f"{PKG}.calendar"]}  # fmt: skip
WARNS_ARGS = {"year": "2200", "month": "2"}


def warning_plan(mode: str) -> dict[str, Any]:
    if mode == "probe":
        return {"mode": "probe", "fixed": {}, "targets": [WARNS_TARGET],
                "calls": [{"target": "t1", "args": WARNS_ARGS}]}  # fmt: skip
    if mode == "diff":
        inputs = [{"phase": "grid", "args": WARNS_ARGS}]
        return {"mode": "diff", "fixed": {}, "targets": [{**WARNS_TARGET, "inputs": inputs}]}
    wrong = {"id": "p", "kind": "returns", "check": "result == 0"}
    target = {**WARNS_TARGET, "properties": [wrong],
              "examples": [{"phase": "grid", "args": WARNS_ARGS}]}  # fmt: skip
    return {"mode": "attack", "search_examples": 5, "fixed": {}, "targets": [target]}


@pytest.mark.parametrize("version", OLD)
@pytest.mark.parametrize("mode", ["attack", "probe"])
def test_a_warning_is_judged_the_same_on_an_old_python(
    tmp_path: Path, version: str, mode: str
) -> None:
    """M11 S4. `catch_warnings` and `simplefilter` work the same from 3.9 on; what the run judged
    must too. Only the explicit inputs are compared: the search's draws depend on Hypothesis."""
    plan = warning_plan(mode)
    own = shipped(tmp_path, None, plan, pytest_ini=ERRORS, source=WARNS)
    old = shipped(tmp_path, version, plan, pytest_ini=ERRORS, source=WARNS)
    assert outside_search(old) == outside_search(own)
    found = [e for e in outside_search(own) if e["event"] in ("probe", "violation")]
    assert found and all(
        e["outcome"] == {"kind": "returned", "type": "int", "repr": "3", "warned": "UserWarning"}
        for e in found
    )


REFUSES = """\
def days_in_month(year, month):
    if month == 2:
        raise ValueError(
            f"no month {month}"
        )
    return int("x")
"""


@pytest.mark.parametrize("version", OLD)
def test_what_a_raise_was_reads_the_same_on_an_old_python(tmp_path: Path, version: str) -> None:
    """M11 S5: the opcode at the raise has another offset unit and other names on each Python
    (`tb_lasti`, CALL against CALL_FUNCTION), and must mean the same."""
    calls = [
        {"target": "t1", "args": WARNS_ARGS},
        {"target": "t1", "args": {**WARNS_ARGS, "month": "3"}},
    ]
    plan = {"mode": "probe", "fixed": {REL: [2, 3, 6]}, "targets": [WARNS_TARGET], "calls": calls}
    own = shipped(tmp_path, None, plan, source=REFUSES)
    old = shipped(tmp_path, version, plan, source=REFUSES)
    facts = [
        {k: e["outcome"].get(k) for k in ("type", "raised_by", "in_project")}
        for events in (own, old)
        for e in events
        if e["event"] == "probe"
    ]
    assert (
        facts
        == [
            {"type": "ValueError", "raised_by": "raise", "in_project": "yes"},
            {"type": "ValueError", "raised_by": "crash", "in_project": "yes"},
        ]
        * 2
    )


def test_a_warning_still_raises_in_the_behaviour_diff(tmp_path: Path) -> None:
    """M11 S4: the diff compares what each side did, warnings included (SPEC 2.5)."""
    events = shipped(tmp_path, None, warning_plan("diff"), pytest_ini=ERRORS, source=WARNS)
    outcomes = [e["outcome"] for e in events if e["event"] == "outcome"]
    assert outcomes and all(o["kind"] == "raised" and o["type"] == "UserWarning" for o in outcomes)
    assert not any("warned" in o for o in outcomes)


GLOBALS = """\
import json
import sys

sys.path.insert(0, sys.argv[1])
import state

COUNT = 0
NAMES = ["a"]


def bump(n):
    global COUNT, GONE
    COUNT += n
    GONE = NAMES[0]
    del GONE
    return COUNT


print(json.dumps(state.module_data(bump)[0], sort_keys=True))
"""


@pytest.mark.parametrize("version", OLD)
def test_the_bytecode_reader_finds_the_same_module_data_on_an_old_python(
    tmp_path: Path, version: str
) -> None:
    """runtime_state reads STORE_GLOBAL/DELETE_GLOBAL from the function's bytecode, which
    differs between versions; what it finds must not."""
    (tmp_path / "state.py").write_text(Path(runtime_state.__file__).read_text("utf-8"), "utf-8")
    script = tmp_path / "globals_main.py"
    script.write_text(GLOBALS, encoding="utf-8")
    found = {}
    for python in (str(old_python(version)), sys.executable):
        run = subprocess.run([python, "-I", str(script), str(tmp_path)], capture_output=True,
                             text=True, timeout=60, cwd=tmp_path)  # fmt: skip
        assert run.returncode == 0, run.stderr[-2000:]
        found[python] = json.loads(run.stdout)
    old, own = found.values()
    assert old == own and {"__main__.COUNT", "__main__.GONE", "__main__.NAMES"} <= set(own)


# --- static rules: what keeps the runtime runnable on 3.9 ---------------------------------------


def _annotation_nodes(tree: ast.AST) -> set[int]:
    found: set[int] = set()
    for node in ast.walk(tree):
        roots: list[ast.expr | None] = []
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            args = node.args
            every = [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]
            roots += [node.returns, *(a.annotation for a in every if a is not None)]
        if isinstance(node, ast.AnnAssign):
            roots.append(node.annotation)
        found |= {id(sub) for root in roots if root is not None for sub in ast.walk(root)}
    return found


@pytest.mark.parametrize("module", [attack_runtime, runtime_state], ids=lambda m: m.__name__)
def test_the_runtime_writes_no_x_or_y_types_outside_annotations(module: Any) -> None:
    """`X | Y` between types needs 3.10 at run time; annotations are never evaluated (the
    modules start with `from __future__ import annotations`). vermin can't tell the two apart."""
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert any(isinstance(n, ast.ImportFrom) and n.module == "__future__"
               and any(a.name == "annotations" for a in n.names) for n in tree.body)  # fmt: skip
    annotations = _annotation_nodes(tree)
    unions = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id in ("isinstance", "issubclass") and len(node.args) == 2
        and isinstance(node.args[1], ast.BinOp) and isinstance(node.args[1].op, ast.BitOr)
        and id(node.args[1]) not in annotations
    ]  # fmt: skip
    assert unions == []


# --- Tracefix's side: prompts, Hypothesis and the call recorder ----------------------------------

CALC = "def f(x: int) -> int:\n    return x\n"
FIXED = "def f(x: int) -> int:\n    return abs(x)\n"
TESTS = "from pkg.calc import f\n\n\ndef test_f():\n    assert f(2) == 2\n"


def project(tmp_path: Path, **python: Any) -> Workspace:
    """A one-function fix whose runs use Tracefix's own Python described with `python`'s changes
    (e.g. an older version, no Hypothesis): the stages read it from the settings."""
    files = {"pkg/__init__.py": "", "pkg/calc.py": CALC, "tests/test_calc.py": TESTS}
    repo = make_repo(tmp_path / "repo", [files, {"pkg/calc.py": FIXED}])
    return Workspace(repo, "c0", "c1", RunSettings(python=replace(current(), **python)))


def test_the_python_note_is_one_fixed_sentence_below_3_11_only() -> None:
    assert python_note((3, 11, 4)) is None and python_note((3, 13, 0)) is None
    assert python_note((3, 9, 25)) == (
        "The project's tests run with Python 3.9: everything you write must run on Python 3.9, "
        "without syntax or library features of later versions."
    )


def test_the_three_roles_that_write_code_are_told_the_project_s_old_python(
    tmp_path: Path,
) -> None:
    note = python_note((3, 9, 25))
    assert note is not None
    with project(tmp_path, version=(3, 9, 25)) as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        ctx, _ = build_context(ws, scope, "f(-1) is negative")
        sources, _ = source_files(ws, scope)
    assert reproducer.render_request(ctx).endswith("\n\n" + note)
    assert mutator.render_request(mutator_context(sources, (3, 9, 25))).endswith("\n\n" + note)
    assert note not in mutator.render_request(mutator_context(sources))
    view = adversary.AdversaryContext("issue", "diff", (), "", "", ("abs",), (), note)
    assert adversary.render_request(view).endswith("\n\n" + note)
    assert note not in adversary.render_request(replace(view, python=None))


def test_without_hypothesis_break_my_fix_and_the_diff_are_inconclusive_before_any_model_call(
    tmp_path: Path,
) -> None:
    provider = FakeProvider([])
    client = client_for(provider, settings())
    with project(tmp_path, hypothesis=None) as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        attack = break_my_fix(ws, scope, None, "issue", client)
        diff = behaviour_diff(ws, scope, None, "issue", client)
        coverage = fix_line_coverage(ws, scope, repro())
    assert attack.status is AttackStatus.INCONCLUSIVE and attack.runs == ()
    assert "Hypothesis is not installed in the project's Python (--python)" in attack.reason
    assert diff.status is BehaviourStatus.INCONCLUSIVE and not diff.l3.allowed
    assert "pip install hypothesis" in diff.reason
    assert coverage.runs == () and any("not measured: Hypothesis" in n for n in coverage.notes)
    assert provider.requests == []


def test_below_3_11_the_behaviour_diff_does_not_ask_for_the_calls_and_says_why(
    tmp_path: Path,
) -> None:
    with project(tmp_path, version=(3, 10, 21)) as ws:
        stage = behaviour_diff_module._Stage(ws, [])
        ran = behaviour_diff_module._ran_on_base(stage, None, repro())  # type: ignore[arg-type]
    assert ran == behaviour_diff_module.Ran() and stage.runs == []
    assert stage.notes == [
        "the reproduction test's calls are not proven on Python 3.10.21: the call recorder "
        "places calls by line and column, which Python gives from 3.11 on, so none of them "
        "counts as compared"
    ]

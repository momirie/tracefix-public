"""Tracefix's code inside the run: Break My Fix (SPEC 2.6, Decided in M6) and the behaviour diff
(SPEC 2.5, Decided in M7).

Tracefix writes this file's source into each run's scratch folder under a random module name and
imports it from a generated test (attack, probe and diff runs), or loads it with -p (coverage
runs). It runs inside the process under test, next to the repo's code, so:
- it imports only the standard library and Hypothesis, never tracefix (a test checks this);
- everything it reports goes to TRACEFIX_OUT as JSON lines, which Tracefix treats as untrusted:
  every candidate is proven again by Tracefix's own probe and repro-file runs;
- it decides nothing. It evaluates the properties it was given on the inputs it was given (and
  the ones Hypothesis generates) and reports what happened.

Modes:
- attack: per target, the explicit inputs (docstring examples, witnesses, the fix-comparison grid,
  evidence values, model examples, type boundaries), then a Hypothesis search per property;
- probe: one traced call per given input, reporting the outcome and the fix lines it ran;
- diff: per target, the inputs (generated once on head, or the list given, on base or a mutant),
  each called twice: the outcome, whether both calls agreed, and which docstring examples it
  keeps. No model code is ever in a diff run;
- coverage (pytest plugin): the lines of some files that ran during the whole session.
"""

from __future__ import annotations

import ast
import asyncio
import builtins
import collections.abc
import contextlib
import copy
import dataclasses
import decimal
import doctest
import enum
import errno
import functools
import hashlib
import importlib
import inspect
import io
import json
import linecache
import logging
import math
import opcode
import os
import stat
import sys
import tempfile
import time
import tokenize
import types
import typing
import warnings
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, TextIO

from hypothesis import HealthCheck, Phase, Verbosity, assume, find, settings
from hypothesis import strategies as st
from hypothesis.errors import HypothesisException, NoSuchExample, Unsatisfiable

from tracefix.runtime_state import (  # shipped beside the runtime (harness.runtime_modules)
    _ADDRESS,
    _digest,
    _error_fields,
    _masked,
    _norm,
    _plain_repr,
    _state,
    module_data,
    snapshot,
)

VERSION = 1
MAX_TEXT = 2_000  # characters kept of any repr or message
MAX_PRINTED = 1_000_000  # characters kept of what a call printed (compared in full, M7)
MAX_LITERAL = 2_000  # an input longer than this as code is "unrepresentable"
MAX_DEPTH = 20  # nesting of literals
MAX_VIOLATIONS = 5  # reported per property and outcome class
MAX_CRASHES = 10  # unjudged crashes reported per target
MAX_CALLING_TEXT = 200  # characters of an input named in a "calling" event (for hang notes)
_NONE = type(None)


class _Omit:
    """A parameter left out of the call, so its default is used."""

    def __repr__(self) -> str:
        return "<default>"


OMIT = _Omit()

INT_BOUNDARIES: tuple[int, ...] = (
    0,
    1,
    -1,
    2,
    -2,
    2**31 - 1,
    -(2**31 - 1),
    2**63 - 1,
    -(2**63 - 1),
    10**18,
    # Just below a round number, where rounding carries into the next digit or unit (real-bug
    # trial: humanize's `metric(9999)` and `naturalsize(999999)`).
    9,
    99,
    999,
    9999,
    999999,
    1023,
    1024**2 - 1,
    -999,
)
FLOAT_BOUNDARIES: tuple[float, ...] = (
    0.0,
    -0.0,
    1.0,
    -1.0,
    0.5,
    1e308,
    -1e308,
    5e-324,
    math.inf,
    -math.inf,
    math.nan,
    # Just below a round number (see INT_BOUNDARIES).
    0.999,
    9.999,
    99.99,
    999.9,
    999.99,
    9999.9,
    0.0009999,
    -9.999,
)
# Strings where text methods and number parsers surprise (M11 S6). Escapes, so that nothing that
# normalises text can turn one into another. After the older ones: what reads only the first
# values (nested hints, made-up objects, typical inputs) gets what it got before.
TRICKY_STRINGS: tuple[str, ...] = (
    "Ab",  # mixed case
    "\u00df",  # sharp s: upper() is two characters
    "\u0130",  # dotted capital I: lower() is two characters
    "e\u0301",  # e + combining acute: looks like the precomposed one, doesn't compare equal
    "\u00b2",  # superscript two: isdigit() yes, int() no
    "\u0661\u0662",  # Arabic-Indic 12: int() yes
    "\u200b",  # zero-width space: looks empty, strip() keeps it
    "\r\n",
    "\ufeff",  # byte-order mark
)
STR_BOUNDARIES: tuple[str, ...] = (
    "",
    " ",
    "\t",
    "\n",
    "a",
    "0",
    "-1",
    " 1 ",
    "é",
    "\U0001f600",
    "\x00",
    "None",
    "a" * 1000,
    *TRICKY_STRINGS,
)
BYTES_BOUNDARIES: tuple[bytes, ...] = (b"", b"\x00", b"a", b"\xff")
_SEQUENCES = {
    list,
    collections.abc.Sequence,
    collections.abc.MutableSequence,
    collections.abc.Iterable,
    collections.abc.Collection,
}
_SETS = {set, frozenset, collections.abc.Set, collections.abc.MutableSet}
_MAPPINGS = {dict, collections.abc.Mapping, collections.abc.MutableMapping}


# --- literals: inputs travel as code, never as pickles --------------------------------------------


def to_source(value: object, depth: int = 0) -> str | None:
    """`value` written as a plain Python literal, or None if it can't be (an object, an int too
    long to print, too deep or too long). Exact types only: a subclass's repr isn't a literal."""
    text = _source(value, depth)
    return text if text is not None and len(text) <= MAX_LITERAL else None


def _source(value: object, depth: int) -> str | None:
    if depth > MAX_DEPTH:
        return None
    kind = type(value)
    if value is None or kind in (bool, str, bytes):
        return repr(value)
    if kind is int:
        try:
            return repr(value)
        except ValueError:  # over sys.get_int_max_str_digits()
            return None
    if kind is float:
        assert isinstance(value, float)
        if math.isnan(value):
            return 'float("nan")'
        if math.isinf(value):
            return 'float("inf")' if value > 0 else 'float("-inf")'
        return repr(value)
    if kind in (list, tuple, set, frozenset):
        assert isinstance(value, (list, tuple, set, frozenset))
        items = [_source(item, depth + 1) for item in value]
        if any(item is None for item in items):
            return None
        parts = [item for item in items if item is not None]
        if kind is list:
            return f"[{', '.join(parts)}]"
        if kind is tuple:
            return (
                "()"
                if not parts
                else f"({parts[0]},)"
                if len(parts) == 1
                else f"({', '.join(parts)})"
            )
        parts.sort()  # a set has no order of its own; sorted text is stable
        if kind is set:
            return f"{{{', '.join(parts)}}}" if parts else "set()"
        return f"frozenset([{', '.join(parts)}])"
    if kind is dict:
        assert isinstance(value, dict)
        pairs = []
        for key, item in value.items():
            key_text, item_text = _source(key, depth + 1), _source(item, depth + 1)
            if key_text is None or item_text is None:
                return None
            pairs.append(f"{key_text}: {item_text}")
        return f"{{{', '.join(pairs)}}}"
    return None


def from_source(text: str) -> object:
    """The value of a plain literal (as written by to_source). Raises ValueError for anything
    else: no name, call or operator is ever evaluated, except the few constructors to_source
    writes (`float("nan")`, `set()`, `frozenset([...])`)."""
    if len(text) > MAX_LITERAL:
        raise ValueError(f"longer than {MAX_LITERAL} characters")
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise ValueError(f"not Python: {exc}") from None
    return _decode(tree.body, 0)


_FLOAT_WORDS = {"nan": math.nan, "inf": math.inf, "-inf": -math.inf}


def _decode(node: ast.expr, depth: int) -> object:
    if depth > MAX_DEPTH:
        raise ValueError("nested too deeply")
    if isinstance(node, ast.Constant) and type(node.value) in (int, float, str, bytes, bool, _NONE):
        return node.value
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.USub, ast.UAdd))
        and isinstance(node.operand, ast.Constant)
        and type(node.operand.value) in (int, float)
    ):
        number = node.operand.value
        assert isinstance(number, (int, float))
        return -number if isinstance(node.op, ast.USub) else number
    if isinstance(node, ast.Tuple):
        return tuple(_decode(e, depth + 1) for e in node.elts)
    if isinstance(node, ast.List):
        return [_decode(e, depth + 1) for e in node.elts]
    if isinstance(node, ast.Set):
        return {_hashable(_decode(e, depth + 1)) for e in node.elts}
    if isinstance(node, ast.Dict):
        if any(k is None for k in node.keys):
            raise ValueError("dict unpacking is not a literal")
        return {
            _hashable(_decode(k, depth + 1)): _decode(v, depth + 1)
            for k, v in zip(node.keys, node.values)
            if k is not None
        }
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        name, args = node.func.id, node.args
        if (
            name == "float"
            and len(args) == 1
            and isinstance(args[0], ast.Constant)
            and args[0].value in _FLOAT_WORDS
        ):
            return _FLOAT_WORDS[str(args[0].value)]
        if name == "set" and not args:
            return set()
        if name == "frozenset" and len(args) == 1 and isinstance(args[0], ast.List):
            return frozenset(_hashable(_decode(e, depth + 1)) for e in args[0].elts)
    raise ValueError(f"not a plain literal: {ast.dump(node)[:80]}")


def _hashable(value: object) -> object:
    try:
        hash(value)
    except TypeError:
        raise ValueError("an unhashable value in a set or as a dict key") from None
    return value


def input_key(args: Mapping[str, object]) -> str:
    """A stable text for one input, to count distinct inputs and to deduplicate them."""
    parts = []
    for name in sorted(args):
        value = args[name]
        parts.append(f"{name}={to_source(value) or _safe_repr(value)}")
    return ", ".join(parts)[:1000]


# --- type hints: which values a parameter accepts, and its boundaries -----------------------------


# `X | Y` hints are types.UnionType from 3.10 on; 3.9 has only typing.Union.
_UNION_TYPE = getattr(types, "UnionType", typing.Union)


def _members(hint: object) -> list[object]:
    origin = typing.get_origin(hint)
    if origin is typing.Union or origin is _UNION_TYPE:
        return list(typing.get_args(hint))
    return [hint]


def accepts(hint: object, value: object) -> bool:
    """True if `value` fits the type hint, for the plain types boundaries and seeds come in. An
    unknown hint accepts nothing (so no seed is forced on it); bool is never an int here."""
    return any(_accepts_one(member, value, 0) for member in _members(hint))


def _accepts_one(hint: object, value: object, depth: int) -> bool:
    if depth > MAX_DEPTH:
        return False
    if hint is typing.Any:
        return True
    if hint is None or hint is _NONE:
        return value is None
    if hint in (bool, int, str, bytes):
        return type(value) is hint
    if hint is float:
        return type(value) in (int, float)
    origin = typing.get_origin(hint) or hint
    args = typing.get_args(hint)
    if origin is typing.Literal:
        return any(type(value) is type(a) and value == a for a in args)
    if origin in _SEQUENCES:
        if type(value) is not list and not (origin is not list and type(value) is tuple):
            return False
        assert isinstance(value, (list, tuple))
        return not args or all(accepts(args[0], item) for item in value)
    if origin is tuple:
        if type(value) is not tuple:
            return False
        assert isinstance(value, tuple)
        if len(args) == 2 and args[1] is Ellipsis:
            return all(accepts(args[0], item) for item in value)
        if not args:
            return True
        pairs = zip(args, value)
        return len(args) == len(value) and all(accepts(a, item) for a, item in pairs)
    if origin in _SETS:
        wanted = frozenset if origin is frozenset else set
        if type(value) is not wanted:
            return False
        assert isinstance(value, (set, frozenset))
        return not args or all(accepts(args[0], item) for item in value)
    if origin in _MAPPINGS:
        if type(value) is not dict:
            return False
        assert isinstance(value, dict)
        if len(args) != 2:
            return True
        return all(accepts(args[0], k) and accepts(args[1], v) for k, v in value.items())
    return False


def boundaries(hint: object) -> list[object]:
    """Edge values for a type hint (unions merged, no duplicates); [] if the hint is unknown."""
    out: list[object] = []
    seen: set[str] = set()
    for member in _members(hint):
        for value in _boundaries_one(member, 0):
            key = f"{type(value).__name__}:{to_source(value)}"
            if key not in seen:
                seen.add(key)
                out.append(value)
    return out


def _boundaries_one(hint: object, depth: int) -> list[object]:
    # A list is no hint, but it comes up as one: Callable[[int], str]'s first argument (M11 S3).
    if depth > 3 or not isinstance(hint, collections.abc.Hashable):
        return []
    simple: dict[object, Iterable[object]] = {
        None: (None,),
        _NONE: (None,),
        bool: (False, True),
        int: INT_BOUNDARIES,
        float: FLOAT_BOUNDARIES,
        str: STR_BOUNDARIES,
        bytes: BYTES_BOUNDARIES,
    }
    if isinstance(hint, collections.abc.Hashable) and hint in simple:
        return list(simple[hint])
    origin = typing.get_origin(hint) or hint
    args = typing.get_args(hint)
    if origin is typing.Literal:
        return list(args)
    inner = _boundaries_one(args[0], depth + 1)[:3] if args else []
    if origin in _SEQUENCES:
        return [[], *([item] for item in inner)]
    if origin in _SETS:
        make = frozenset if origin is frozenset else set
        hashable = [item for item in inner if isinstance(item, collections.abc.Hashable)]
        return [make(), *(make([item]) for item in hashable)]
    if origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis:
            return [(), *((item,) for item in inner)]
        firsts = [_boundaries_one(a, depth + 1)[:1] for a in args]
        return [tuple(f[0] for f in firsts)] if args and all(firsts) else []
    if origin in _MAPPINGS:
        keys = _boundaries_one(args[0], depth + 1)[:1] if len(args) == 2 else []
        values = _boundaries_one(args[1], depth + 1)[:1] if len(args) == 2 else []
        hashable = [k for k in keys if isinstance(k, collections.abc.Hashable)]
        return [{}, *({k: values[0]} for k in hashable if values)]
    return []


# --- outcomes -------------------------------------------------------------------------------------


def _safe_repr(value: object) -> str:
    try:
        text = repr(value)
    except Exception as exc:  # a broken __repr__, or an int over the digit limit
        text = f"<unprintable {type(value).__name__}: {type(exc).__name__}>"
    return _ADDRESS.sub("at 0x?>", text)[:MAX_TEXT]


def _safe_str(value: object) -> str:
    try:
        text = str(value)
    except Exception as exc:
        text = f"<unprintable message: {type(exc).__name__}>"
    return _ADDRESS.sub("at 0x?>", text)[:MAX_TEXT]


def raise_facts(error: BaseException) -> dict[str, str]:
    """What kind of raise this was, for a finding's doubt flag (M11 S5; it decides nothing).
    `raised_by`: 'raise' if a `raise` statement made it, else 'crash' (Python or C code did, or an
    `assert`, which compiles to a raise but says the code never expected this). It reads the
    instruction the innermost frame stopped at: a formatter's `raise X(` over several lines has no
    whole statement on one line for `_raises` to read. `in_project`: that frame is in the copy."""
    tb = _innermost(error)
    facts = {"raised_by": "crash"}
    if tb is not None:
        code = tb.tb_frame.f_code
        at = code.co_code[tb.tb_lasti : tb.tb_lasti + 1]
        if at and opcode.opname[at[0]] == "RAISE_VARARGS" and not isinstance(error, AssertionError):
            facts["raised_by"] = "raise"
        if _in_copy(code.co_filename):
            facts["in_project"] = "yes"
    return {**facts, **_os_facts(error)}


def _os_facts(error: BaseException) -> dict[str, str]:
    """An OS error's name (`errno` numbers differ per system) and Windows code, if it has them."""
    if not isinstance(error, OSError):
        return {}
    try:  # a project's subclass may define these
        number, windows = error.errno, getattr(error, "winerror", None)
    except Exception:
        return {}
    facts = {}
    if isinstance(number, int) and number in errno.errorcode:
        facts["errno"] = errno.errorcode[number]
    if isinstance(windows, int):
        facts["winerror"] = str(windows)
    return facts


class _NoCopy:
    """The object a method was called on could not be copied before the call."""


NO_COPY = _NoCopy()


@dataclass(frozen=True)
class Outcome:
    """What one call did: returned a value, or raised an exception."""

    value: object = None
    error: BaseException | None = None
    stdout: str = ""  # what the call printed (a doctest compares it too)
    ran_fix: bool = False  # the call ran a line the fix added or changed
    # A method called on an object (M7.5): the object after the call, and a copy taken before.
    receiver: object = None
    before: object = NO_COPY
    # The first call raised a warning (M11 S4): that raise, and this is the call with warnings
    # ignored. Only the attack and the probes make these (`judged_call`).
    warned: Outcome | None = None

    @property
    def raised(self) -> bool:
        return self.error is not None

    def warned_name(self) -> str:
        return "" if self.warned is None else type(self.warned.error).__name__

    def report(self) -> dict[str, str]:
        note = {"warned": self.warned_name()} if self.warned is not None else {}
        if self.error is not None:
            kind = type(self.error)
            return {
                "kind": "raised",
                "type": kind.__name__,
                "module": kind.__module__,
                "message": _safe_str(self.error),
                **raise_facts(self.error),
                **note,
            }
        return {
            "kind": "returned",
            "type": type(self.value).__name__,
            "repr": _safe_repr(self.value),
            **note,
        }

    def describe(self) -> str:
        if self.error is not None:
            return f"raised {type(self.error).__name__}: {_safe_str(self.error)}"[:MAX_TEXT]
        return f"returned {_safe_repr(self.value)}"[:MAX_TEXT]


# --- line tracing ---------------------------------------------------------------------------------


class LineTracer:
    """Records which lines of some files run while it is on. Python 3.12+ uses sys.monitoring
    (other code is switched off for good after its first event, so it costs little); 3.11 uses
    sys.settrace with a local tracer only for frames of those files."""

    def __init__(self, files: Mapping[str, str]) -> None:
        """`files`: absolute path -> the name it is reported under (its repo-relative path)."""
        self.files = {_norm(path): rel for path, rel in files.items()}
        self.lines: dict[str, set[int]] = {rel: set() for rel in self.files.values()}
        self.available = bool(self.files)
        self.reason = "" if self.files else "no file to trace"
        self.disturbed = False  # someone else replaced our tracer while it was on
        self._known: dict[types.CodeType, str | None] = {}
        self._tool: int | None = None
        self._previous: Any = None
        self._on = False
        if self.files and sys.version_info >= (3, 12):
            self._claim_tool()

    def _rel(self, code: types.CodeType) -> str | None:
        if code not in self._known:
            self._known[code] = self.files.get(_norm(code.co_filename))
        return self._known[code]

    # sys.monitoring (3.12+)
    def _claim_tool(self) -> None:
        monitoring: Any = getattr(sys, "monitoring")  # noqa: B009 (absent on 3.11, for mypy)
        for tool in (3, 4, monitoring.COVERAGE_ID, monitoring.PROFILER_ID):
            if monitoring.get_tool(tool) is None:
                monitoring.use_tool_id(tool, "tracefix")
                monitoring.register_callback(tool, monitoring.events.LINE, self._on_line)
                # Locations an earlier tracer switched off (DISABLE) stay off for its tool id
                # until this; they may be in the files traced now.
                monitoring.restart_events()
                self._tool = tool
                return
        self.available = False
        self.reason = "no free sys.monitoring tool id"

    def _on_line(self, code: types.CodeType, line: int) -> object:
        rel = self._rel(code)
        if rel is None:
            return getattr(sys, "monitoring").DISABLE  # noqa: B009
        self.lines[rel].add(line)
        return None

    # sys.settrace (3.11)
    def _global(self, frame: types.FrameType, event: str, _arg: object) -> Any:
        rel = self._rel(frame.f_code)
        if rel is None:
            return None
        lines = self.lines[rel]

        def local(frame: types.FrameType, event: str, _arg: object) -> Any:
            if event == "line":
                lines.add(frame.f_lineno)
            return local

        return local

    def start(self) -> None:
        if not self.available or self._on:
            return
        self._on = True
        if self._tool is not None:
            monitoring: Any = getattr(sys, "monitoring")  # noqa: B009
            monitoring.set_events(self._tool, monitoring.events.LINE)
        else:
            self._previous = sys.gettrace()
            sys.settrace(self._global)

    def stop(self) -> None:
        if not self._on:
            return
        self._on = False
        if self._tool is not None:
            monitoring: Any = getattr(sys, "monitoring")  # noqa: B009
            monitoring.set_events(self._tool, 0)
        else:
            if sys.gettrace() != self._global:
                self.disturbed = True
            sys.settrace(self._previous)

    def take(self) -> dict[str, set[int]]:
        """The lines recorded since the last take, per file; the record starts empty again."""
        taken = {rel: set(lines) for rel, lines in self.lines.items() if lines}
        for lines in self.lines.values():
            lines.clear()
        return taken

    def close(self) -> None:
        """Stop, and give the sys.monitoring tool id back (there are only six)."""
        self.stop()
        if self._tool is not None:
            monitoring: Any = getattr(sys, "monitoring")  # noqa: B009
            monitoring.register_callback(self._tool, monitoring.events.LINE, None)
            monitoring.free_tool_id(self._tool)
            self._tool = None


# --- reporting ------------------------------------------------------------------------------------


class Reporter:
    """JSON lines to TRACEFIX_OUT, flushed one by one, so a run that is killed keeps what it
    reported until then."""

    def __init__(self) -> None:
        path = os.environ.get("TRACEFIX_OUT")
        self._file: TextIO | None = None
        if path:
            self._file = open(path, "a", encoding="utf-8", newline="\n")  # noqa: SIM115

    def emit(self, event: Mapping[str, object]) -> None:
        if self._file is not None:
            self._file.write(json.dumps(event, ensure_ascii=True, separators=(",", ":")) + "\n")
            self._file.flush()

    def close(self) -> None:
        if self._file is not None:
            self._file.close()


# --- the target -----------------------------------------------------------------------------------


class TargetError(Exception):
    """The target can't be attacked here (its module doesn't import, the name is missing...)."""


def resolve(path: str, candidates: Iterable[str]) -> tuple[types.ModuleType, str]:
    """The module whose file is `path` (repo-relative, in the copy this run is in), and the
    dotted name it imports under. Candidates are tried in order, then every dotted suffix of the
    path, shortest first; a module counts only if it IS that file (so the stdlib's `calendar`
    never stands in for a repo's `billing/calendar.py`)."""
    wanted = os.path.realpath(os.path.join(os.getcwd(), *PurePosixPath(path).parts))
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    suffixes = [".".join(parts[i:]) for i in range(len(parts) - 1, -1, -1)]
    tried: list[str] = []
    for name in [*candidates, *suffixes]:
        if not name or name in tried:
            continue
        tried.append(name)
        try:
            module = importlib.import_module(name)
        except (Exception, SystemExit):
            continue
        file = getattr(module, "__file__", None)
        try:
            same = isinstance(file, str) and os.path.samefile(file, wanted)
        except OSError:
            same = False
        if same:
            return module, name
    raise TargetError(f"{path} could not be imported as a module here (tried {', '.join(tried)})")


RECEIVER = "self"  # a method's input holding the code that builds its object (M7.5)
AFTER = "self_after"  # in property expressions: the object after the call
RECEIVER_KINDS = ("method", "property")  # called on an object
EVERY = f"{RECEIVER}.*"  # an evidence value for every constructor parameter
MAX_UNBUILT_NOTES = 3  # per target
# Object code longer than this comes back refused (attack_rules.MAX_EXPRESSION, a test keeps
# them equal), so the run never uses it: verifier round 1, S1.
MAX_OBJECT_CODE = 400


class Unbuilt(Exception):
    """The object a method is called on could not be built from its code. Such an input is no
    input at all: never judged, never counted, never proven as a finding (a constructor's own
    error is not the method's)."""

    def __init__(self, kind: str, reason: str = "") -> None:
        super().__init__(f"{kind}: {reason}" if reason else kind)
        self.kind = kind


@dataclass
class Target:
    """One function or method under attack, resolved in this run."""

    id: str
    path: str
    name: str
    module: types.ModuleType
    module_name: str
    function: Callable[..., object]
    signature: inspect.Signature  # what a call passes (a method's object is not in it)
    hints: dict[str, object]
    tracer: LineTracer | None
    # The fix's lines in every changed file (a call may run a fixed helper in another file).
    fixed: Mapping[str, frozenset[int]] = field(default_factory=dict)
    reached: dict[str, set[int]] = field(default_factory=dict)  # fixed lines any call ran
    owner: type | None = None  # a method's class: its data is module data too (M7.5)
    receivers: Receivers | None = None  # a method called on an object: how objects are built
    awaited: bool = False  # `async def`: each call runs on a fresh event loop (M11 early)

    def call(
        self, args: Mapping[str, object], *, copied: bool = True, keep_before: bool = True
    ) -> tuple[Outcome, dict[str, set[int]]]:
        """Call with a deep copy of `args` (missing parameters keep their defaults), or with
        `args` themselves if `copied` is False (the caller made fresh copies and wants to see what
        the call did to them); the outcome and the fixed lines this call ran, per file. For a
        method called on an object, the object is built from the input's `self` inside the
        traced region (building is part of the call), and a copy is kept from before the call
        (`keep_before`); `Unbuilt` if it can't be built."""
        given = _copied(args) if copied else dict(args)
        text = given.pop(RECEIVER, None) if self.receivers is not None else None
        positional, keywords = _bind(self.signature, given)
        printed = _stream()
        instance: object = None
        before: object = NO_COPY
        if self.tracer is not None:
            self.tracer.take()
            self.tracer.start()
        try:
            with contextlib.redirect_stdout(printed):
                if self.receivers is not None:
                    instance = self.receivers.build(text)
                    before = _copy_of(instance) if keep_before else NO_COPY
                value = self._invoke(instance, positional, keywords)
            outcome = Outcome(value=value, stdout=_written(printed)[:MAX_PRINTED],
                              receiver=instance, before=before)  # fmt: skip
        except Unbuilt:
            raise
        except (Exception, SystemExit, asyncio.CancelledError) as exc:
            outcome = Outcome(error=exc, stdout=_written(printed)[:MAX_PRINTED],
                              receiver=instance, before=before)  # fmt: skip
        finally:
            if self.tracer is not None:
                self.tracer.stop()
        ran: dict[str, set[int]] = {}
        if self.tracer is not None:
            for path, lines in self.tracer.take().items():
                hit = lines & self.fixed.get(path, frozenset())
                if hit:
                    ran[path] = hit
                    self.reached.setdefault(path, set()).update(hit)
        return outcome, ran

    def _invoke(
        self, instance: object, positional: list[object], keywords: dict[str, object]
    ) -> object:
        if self.receivers is None:  # a function, a class method or a static method
            value = self.function(*positional, **keywords)
        else:
            attribute = getattr(instance, self.name)
            if self.receivers.kind == "property":
                return attribute
            assert callable(attribute)
            value = attribute(*positional, **keywords)
        return asyncio.run(value) if self.awaited and inspect.iscoroutine(value) else value


# The warning filters in force when the run started, before any code under test ran: the project's
# pytest config, -W and PYTHONWARNINGS (set by `main`). None outside a run.
_START_FILTERS: list[object] | None = None


def _drop_start_errors(start: Sequence[object]) -> None:
    """Inside `catch_warnings`: take away the "error" filters that were in force at `start` and
    keep every filter set since, the code's own "error" included (verifier round 1, B1: a package
    that makes its own warning an error on first use raises it for every user). By identity: a
    filter the code sets again is a new entry, even when it reads the same as the project's."""
    filters = typing.cast("list[Any]", warnings.filters)  # a list, typed as a read-only sequence
    filters[:] = [f for f in filters if not (f[0] == "error" and any(f is s for s in start))]


def judged_call(target: Target, args: Mapping[str, object]) -> tuple[Outcome, dict[str, set[int]]]:
    """The attack's and the probes' call (M11 S4, NOTES 39): a warning the project's filters turn
    into a raise is not the call's outcome, so a call that raised one runs once more without the
    "error" filters the run started with, and that is judged. If it still raises a warning, the
    code raises it itself (`raise X`, or a filter it set): that raise stands. Outside a run the
    filters in force at this call stand in for the start's. `Target.call` stays as it is: the
    behaviour diff compares warnings too."""
    start = list(warnings.filters) if _START_FILTERS is None else _START_FILTERS
    outcome, ran = target.call(args)
    if not isinstance(outcome.error, Warning):
        return outcome, ran
    with warnings.catch_warnings():  # entering it also resets what Python remembers as shown
        _drop_start_errors(start)
        quiet, more = target.call(args)
    for path, lines in more.items():
        ran.setdefault(path, set()).update(lines)
    if isinstance(quiet.error, Warning):
        return outcome, ran
    return dataclasses.replace(quiet, warned=outcome), ran


def _copy_of(value: object) -> object:
    try:
        return copy.deepcopy(value)
    except Exception:  # not copyable: a property reading `self` can't be judged on it
        return NO_COPY


def _copied(args: Mapping[str, object]) -> dict[str, object]:
    try:
        return copy.deepcopy(dict(args))
    except Exception:  # not copyable: the call gets the objects themselves
        return dict(args)


Bound = tuple[list[object], dict[str, object]]


def _bind(signature: inspect.Signature, args: Mapping[str, object]) -> Bound:
    positional: list[object] = []
    keywords: dict[str, object] = {}
    for param in signature.parameters.values():
        if param.name not in args or args[param.name] is OMIT:
            continue
        if param.kind is inspect.Parameter.POSITIONAL_ONLY:
            positional.append(args[param.name])
        elif param.kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            keywords[param.name] = args[param.name]
    return positional, keywords


def fixed_lines(plan: Mapping[str, Any]) -> dict[str, frozenset[int]]:
    """The plan's fixed lines, per changed source file (repo-relative path)."""
    return {path: frozenset(lines) for path, lines in plan.get("fixed", {}).items() if lines}


def load_target(
    spec: Mapping[str, Any], tracer: LineTracer | None, fixed: Mapping[str, frozenset[int]]
) -> Target:
    module, module_name = resolve(spec["path"], spec.get("module_candidates", []))
    if spec.get("owner"):
        return _load_method(spec, module, module_name, tracer, fixed)
    function = getattr(module, spec["name"], None)
    if function is None:
        raise TargetError(f"{module_name} has no attribute {spec['name']}")
    if not callable(function) or inspect.isclass(function):
        raise TargetError(f"{module_name}.{spec['name']} is not a function")
    _check_async(f"{module_name}.{spec['name']}", function, bool(spec.get("async")))
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError) as exc:
        raise TargetError(f"no signature for {spec['name']}: {exc}") from None
    try:
        hints = typing.get_type_hints(function)
    except Exception:  # an annotation that doesn't resolve here: no type information
        hints = {}
    return Target(
        spec["id"],
        spec["path"],
        spec["name"],
        module,
        module_name,
        function,
        signature,
        hints,
        tracer,
        fixed,
        awaited=bool(spec.get("async")),
    )


def _check_async(label: str, function: object, awaited: bool) -> None:
    """A target is called only as head's source declared it: `async def` (awaited on a fresh
    event loop, never inside a running one) or a plain function; never a generator."""
    if inspect.isgeneratorfunction(function) or inspect.isasyncgenfunction(function):
        raise TargetError(f"{label} is a generator")
    if inspect.iscoroutinefunction(function) != awaited:
        raise TargetError(f"{label} is {'not ' if awaited else ''}async here")
    if not awaited:
        return
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    raise TargetError(f"{label} is async, but an event loop is already running here")


# --- the object a method is called on (M7.5) ------------------------------------------------------


class _Missing:
    pass


_MISSING = _Missing()


def _load_method(
    spec: Mapping[str, Any],
    module: types.ModuleType,
    module_name: str,
    tracer: LineTracer | None,
    fixed: Mapping[str, frozenset[int]],
) -> Target:
    """A method of a class of the module, checked to be what head's source said: defined in
    that class itself, of the kind the plan names (else it can't be loaded: fail-safe)."""
    owner_name, name, kind = str(spec["owner"]), str(spec["name"]), str(spec.get("kind", "method"))
    owner = getattr(module, owner_name, None)
    if not inspect.isclass(owner) or getattr(owner, "__module__", None) != module.__name__:
        raise TargetError(f"{module_name}.{owner_name} is not a class of the module")
    raw = vars(owner).get(name, _MISSING)
    if raw is _MISSING:
        raise TargetError(f"{owner_name}.{name} is not defined in the class itself here")
    function, signature = _method_parts(owner_name, name, kind, getattr(owner, name, None), raw)
    if kind != "property":
        _check_async(f"{owner_name}.{name}", function, bool(spec.get("async")))
    try:
        hints = typing.get_type_hints(function)
    except Exception:  # an annotation that doesn't resolve here: no type information
        hints = {}
    receivers = None
    if kind in RECEIVER_KINDS:
        receivers = _receivers(spec, module, owner, raw)
    return Target(spec["id"], spec["path"], name, module, module_name, function, signature,
                  hints, tracer, fixed, owner=owner, receivers=receivers,
                  awaited=bool(spec.get("async")))  # fmt: skip


def _kind_of(raw: object) -> str:
    """What a class holds under a name, as the plan names kinds."""
    if isinstance(raw, staticmethod):
        return "staticmethod"
    if isinstance(raw, classmethod):
        return "classmethod"
    if isinstance(raw, (property, functools.cached_property)):
        return "property"
    if callable(raw) and not inspect.isclass(raw):
        return "method"
    return type(raw).__name__


def _signature(function: object, name: str) -> inspect.Signature:
    try:
        return inspect.signature(function)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise TargetError(f"no signature for {name}: {exc}") from None


def _method_parts(
    owner_name: str, name: str, kind: str, bound: object, raw: object
) -> tuple[Callable[..., object], inspect.Signature]:
    """The function to call or read through, and what a call passes. A class or static method
    is called on the class; a method's own first parameter (the object) is not passed."""
    found = _kind_of(raw)
    if found != kind:
        raise TargetError(f"{owner_name}.{name} is a {found} here, not a {kind}")
    if isinstance(raw, property):
        if raw.fget is None:
            raise TargetError(f"{owner_name}.{name} is a property without a getter")
        return raw.fget, inspect.Signature()
    if isinstance(raw, functools.cached_property):
        return raw.func, inspect.Signature()
    if kind in ("staticmethod", "classmethod"):
        assert callable(bound)
        return bound, _signature(bound, name)
    assert callable(raw)
    full = _signature(raw, name)
    params = list(full.parameters.values())
    first = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    if not params or params[0].kind not in first:
        raise TargetError(f"{owner_name}.{name} takes no object as its first parameter")
    return raw, full.replace(parameters=params[1:])


def _constructor_hints(owner: type) -> dict[str, object]:
    """Type hints of the constructor's parameters: `__init__`'s, else the class's own
    annotations (a dataclass's fields)."""
    for source in (vars(owner).get("__init__"), owner):
        if source is None:
            continue
        try:
            hints = typing.get_type_hints(source)
        except Exception:
            continue
        if hints:
            return hints
    return {}


_PLAIN_TYPES: tuple[object, ...] = (_NONE, bool, int, float, str, bytes)


def _plain_hint(hint: object, depth: int = 0) -> bool:
    """A type hint whose values are all plain literals (so a made-up object can be written as
    code): None, bool, int, float, str, bytes, a Literal, and lists, tuples, sets and dicts of
    them."""
    if depth > 3:
        return False
    for member in _members(hint):
        if member is None or member in _PLAIN_TYPES:
            continue
        origin, args = typing.get_origin(member), typing.get_args(member)
        if origin is typing.Literal:
            continue
        if (
            origin in (list, tuple, set, frozenset, dict)
            and args
            and all(a is Ellipsis or _plain_hint(a, depth + 1) for a in args)
        ):
            continue
        return False
    return True


@functools.lru_cache(maxsize=4096)
def _object_literals(text: str) -> tuple[object, ...]:
    """The plain literals among the arguments of an object's code (for the NaN and huge-value
    rules, which look at every value an input holds)."""
    try:
        node = ast.parse(text.strip(), mode="eval").body
    except (SyntaxError, ValueError, RecursionError):
        return ()
    found: list[object] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            for arg in [*sub.args, *(k.value for k in sub.keywords)]:
                with contextlib.suppress(ValueError):
                    found.append(_decode(arg, 0))
    return tuple(found)


def _plain_values(args: Mapping[str, object]) -> list[object]:
    """An input's values, with a method's object read as the literals of its code."""
    out: list[object] = []
    for name, value in args.items():
        if name == RECEIVER and isinstance(value, str):
            out += _object_literals(value)
        else:
            out.append(value)
    return out


@dataclass
class Receivers:
    """How the objects a method is called on are built in this run: each from its code (the
    input's `self`), evaluated in a namespace of the module's own names, the safe builtins and
    standard-library stand-ins. Typical objects ("vouched": the default constructor, and the
    code the plan gives from tests, docstrings, the issue and the model) come first; objects
    made up from the constructor's parameters are written as literal-only `Owner(k=v)` code."""

    owner: type
    owner_name: str  # how code names the class
    name: str  # the method
    kind: str  # method | property
    raw: object  # what the class holds under `name`: a built object must not override it
    namespace: dict[str, object]
    data: tuple[str, ...]  # module data in the namespace: copied afresh for each build
    signature: inspect.Signature | None  # the constructor's (None: nothing is made up)
    hints: dict[str, object]  # the constructor's type hints
    vouched: list[str] = field(default_factory=list)
    codes: dict[str, types.CodeType] = field(default_factory=dict)

    def build(self, text: object) -> object:
        if not isinstance(text, str):
            raise Unbuilt("NoObject", "the input names no object to call the method on")
        code = self.codes.get(text)
        if code is None:
            try:
                code = compile(text, "<self>", "eval")
            except (SyntaxError, ValueError):
                raise Unbuilt("SyntaxError", "its code does not compile") from None
            self.codes[text] = code
        scope = {**self.namespace, **_copied({n: self.namespace[n] for n in self.data})}
        try:
            value = _eval(code, scope)
        except (Exception, SystemExit) as exc:
            raise Unbuilt(type(exc).__name__, _safe_str(exc)[:300]) from None
        if not isinstance(value, self.owner):
            raise Unbuilt(
                "NotAnObject", f"it gave a {type(value).__name__}, not a {self.owner_name}"
            )
        if inspect.getattr_static(type(value), self.name, None) is not self.raw:
            raise Unbuilt("Overridden", f"a {type(value).__name__} has its own {self.name}")
        return value

    def params(self) -> list[inspect.Parameter]:
        if self.signature is None:
            return []
        return [p for p in self.signature.parameters.values() if p.kind not in _VARIADIC]

    def defaults(self) -> list[str]:
        """`Owner()` when the constructor needs no argument: the author's own default object."""
        if self.signature is None or any(p.default is p.empty for p in self.params()):
            return []
        return [f"{self.owner_name}()"]

    def render(self, kwargs: Mapping[str, object]) -> str | None:
        """`Owner(a=1, b='x')`: code for a made-up object (literal values only, positional-only
        parameters by position), or None if it can't be written (or is too long)."""
        parts: list[str] = []
        skipped = False
        for p in self.params():
            value = kwargs.get(p.name, OMIT)
            if value is OMIT:
                if p.default is p.empty:
                    return None
                skipped = skipped or p.kind is inspect.Parameter.POSITIONAL_ONLY
                continue
            source = to_source(value)
            if source is None:
                return None
            if p.kind is inspect.Parameter.POSITIONAL_ONLY:
                if skipped:
                    return None
                parts.append(source)
            else:
                parts.append(f"{p.name}={source}")
        code = f"{self.owner_name}({', '.join(parts)})"
        return code if len(code) <= MAX_OBJECT_CODE else None

    def kwargs_of(self, text: str) -> dict[str, object] | None:
        """The constructor arguments of `Owner(literals)` code, by parameter name, or None."""
        try:
            node = ast.parse(text.strip(), mode="eval").body
        except (SyntaxError, ValueError, RecursionError):
            return None
        if (
            self.signature is None
            or not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Name)
            or node.func.id != self.owner_name
            or any(k.arg is None for k in node.keywords)
        ):
            return None
        try:
            args = [_decode(a, 0) for a in node.args]
            kwargs = {str(k.arg): _decode(k.value, 0) for k in node.keywords}
            bound = dict(self.signature.bind(*args, **kwargs).arguments)
        except (ValueError, TypeError):
            return None
        named = {p.name for p in self.params()}
        return bound if set(bound) <= named else None

    def first_kwargs(self) -> dict[str, object] | None:
        """Each required constructor parameter at its first boundary value (None if one has no
        type hint to take it from)."""
        out: dict[str, object] = {}
        for p in self.params():
            if p.default is not p.empty:
                continue
            values = boundaries(self.hints[p.name]) if p.name in self.hints else []
            if not values:
                return None
            out[p.name] = values[0]
        return out

    def seeds(self, spec: Mapping[str, Any]) -> dict[str, list[object]]:
        """Per constructor parameter: the values the fix compares the attribute of that name
        with (they fit even without a hint), then the evidence values that fit its hint."""
        candidates = spec.get("candidates", {})
        out: dict[str, list[object]] = {}
        for p in self.params():
            hint = self.hints.get(p.name)
            kept: list[object] = []
            for entry in [*candidates.get(f"{RECEIVER}.{p.name}", []), *candidates.get(EVERY, [])]:
                try:
                    value = from_source(entry["value"])
                except (ValueError, KeyError, TypeError):
                    continue
                if (hint is None and entry.get("compared")) or (
                    hint is not None and accepts(hint, value)
                ):
                    kept.append(value)
            out[p.name] = kept
        return out

    def sweep(
        self, around: str | None, seeds: Mapping[str, list[object]]
    ) -> tuple[list[str], list[str]]:
        """Made-up objects one constructor parameter away from a typical one (`around`, else
        the first boundaries): (with each parameter's seeds, with its type boundaries)."""
        base = self.kwargs_of(around) if around else None
        base = base if base is not None else self.first_kwargs()
        if base is None:
            return [], []
        evidence: list[str | None] = []
        edges: list[str | None] = []
        for p in self.params():
            evidence += [self.render({**base, p.name: v}) for v in seeds.get(p.name, [])]
            hint = self.hints.get(p.name)
            values = boundaries(hint) if hint is not None else []
            edges += [self.render({**base, p.name: v}) for v in values]
        return [t for t in evidence if t], [t for t in edges if t]

    def first(self) -> str | None:
        """A typical object's code: the first vouched one, else one made up from the first
        boundaries."""
        if self.vouched:
            return self.vouched[0]
        kwargs = self.first_kwargs()
        return self.render(kwargs) if kwargs is not None else None

    def strategy(self, seeds: Mapping[str, list[object]]) -> Any | None:
        """Hypothesis draws objects: typical ones first (shrinking prefers them), then made-up
        ones from the constructor's parameters, as literal-only code."""
        parts: list[Any] = []
        if self.vouched:
            parts.append(st.sampled_from(self.vouched))
        made = self._made_up(seeds)
        if made is not None:
            parts.append(made)
        if not parts:
            return None
        return st.one_of(*parts) if len(parts) > 1 else parts[0]

    def _made_up(self, seeds: Mapping[str, list[object]]) -> Any | None:
        if self.signature is None:
            return None
        required: dict[str, Any] = {}
        optional: dict[str, Any] = {}
        for p in self.params():
            hint = self.hints.get(p.name)
            parts: list[Any] = []
            values = [*seeds.get(p.name, []), *(boundaries(hint) if hint is not None else [])]
            if values:
                parts.append(st.sampled_from(values))
            if hint is not None and _plain_hint(hint):
                with contextlib.suppress(Exception):
                    parts.append(st.from_type(typing.cast(Any, hint)))
            if not parts:
                if p.default is p.empty:
                    return None
                continue
            chosen = st.one_of(*parts) if len(parts) > 1 else parts[0]
            (required if p.default is p.empty else optional)[p.name] = chosen
        drawn = st.fixed_dictionaries(required, optional=optional)
        return drawn.map(self.render).filter(lambda text: text is not None)

    def finite(self) -> bool:
        """Every constructor parameter's values can all be listed (or there is none)."""
        return self.signature is not None and all(
            p.name in self.hints and _finite(self.hints[p.name]) for p in self.params()
        )


def _receivers(
    spec: Mapping[str, Any], module: types.ModuleType, owner: type, raw: object
) -> Receivers:
    owner_name = str(spec["owner"])
    names = [owner_name, *(str(n) for n in spec.get("receiver_names", []) if n != owner_name)]
    try:
        namespace = _namespace_of(module, names, spec.get("receiver_stdlib", []))
    except PropertyError as exc:
        raise TargetError(f"its objects' code can't run here: {exc}") from None
    try:
        signature: inspect.Signature | None = inspect.signature(owner)
    except (TypeError, ValueError):
        signature = None
    receivers = Receivers(
        owner,
        owner_name,
        str(spec["name"]),
        str(spec.get("kind", "method")),
        raw,
        namespace,
        tuple(n for n in names if not callable(namespace.get(n))),
        signature,
        _constructor_hints(owner),
    )
    given = [str(t) for t in spec.get("vouched", []) if isinstance(t, str)]
    typical = [*receivers.defaults(), *given]
    receivers.vouched = list(dict.fromkeys(t for t in typical if len(t) <= MAX_OBJECT_CODE))
    return receivers


# --- properties -----------------------------------------------------------------------------------


class PropertyError(Exception):
    """A property that can't be evaluated at all here (a name it uses is missing...)."""


@dataclass
class Property:
    id: str
    kind: str  # returns | raises | raises_only | relation | example
    when: types.CodeType | None
    check: types.CodeType | None
    expected: types.CodeType | None
    transform: types.CodeType | None
    exceptions: tuple[type[BaseException], ...]
    namespace: dict[str, object]
    example: dict[str, object] | None = None  # a docstring example's input
    example_expected: str = ""  # its expected value (literal) or printed repr
    compare: str = "eq"  # docstring examples: "eq" (==), "repr" (doctest output) or "raises"
    contradicted: bool = False
    violations: dict[str, int] = field(default_factory=dict)  # outcome class -> reported
    data: tuple[str, ...] = ()  # module data it uses: copied for each evaluation (round 3)
    # The parameters its expressions name. A violation must survive putting every other
    # parameter back to its default (real-bug trial: a junk `format` crashed a property about
    # `value`).
    mentions: frozenset[str] = frozenset()
    # Whether its quote makes huge inputs part of the promise; if not, a raise on a huge boundary
    # value is only a crash note (developer, 6 Oct 2026: `precision=2**63-1` is not a finding).
    huge_ok: bool = False
    # The target's parameter defaults: an input that leaves a parameter out gets its default,
    # and the expressions must see it too (real-bug trial: `binary == False and gnu == False`
    # raised NameError on every input, so the property applied to nothing).
    defaults: dict[str, object] = field(default_factory=dict)
    # NaN is never equal to itself, so `result == abs(x)` would "fail" for every NaN: such inputs
    # (and infinities) are judged only by a property whose text speaks about them.
    finite_only: bool = True
    # A method called on an object (M7.5): its expressions see `self` (a copy of the object
    # from before the call) and `self_after`; `scopes_objects`: its `when` names `self`, so it
    # also judges objects the run made up (developer, 9 Oct 2026).
    receiver: bool = False
    uses_self: bool = False
    scopes_objects: bool = False

    def live(self) -> bool:
        return not self.contradicted


def _compile(text: str, label: str) -> types.CodeType | None:
    if not text.strip():
        return None
    try:
        return compile(text, f"<{label}>", "eval")
    except (SyntaxError, ValueError):
        # No error text: it differs between Python versions and reaches the follow-up prompt.
        raise PropertyError(f"{label} does not compile") from None


# The builtins an expression may call: the same list as attack_rules.SAFE_BUILTINS (a test keeps
# them equal; this module imports only the standard library), plus the builtin exceptions.
SAFE_BUILTINS = (
    "abs",
    "all",
    "any",
    "bool",
    "chr",
    "dict",
    "divmod",
    "enumerate",
    "float",
    "frozenset",
    "int",
    "isinstance",
    "len",
    "list",
    "max",
    "min",
    "ord",
    "repr",
    "reversed",
    "round",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
)


def _builtins() -> dict[str, object]:
    """Only the safe builtins and the exception classes: no `open`, `__import__`, `getattr`..."""
    allowed: dict[str, object] = {name: getattr(builtins, name) for name in SAFE_BUILTINS}
    for name, value in vars(builtins).items():
        if isinstance(value, type) and issubclass(value, BaseException):
            allowed[name] = value
    return allowed


# Module functions that change process-wide state one property could use to blind the others
# in the same run (verifier round 3: `decimal.getcontext().clear_traps()`).
STATEFUL = frozenset({"getcontext", "setcontext", "localcontext", "setfirstweekday"})
IMMUTABLE = (bool, int, float, complex, str, bytes, tuple, frozenset, type(None))


def _stand_in(module: types.ModuleType) -> types.SimpleNamespace:
    """A standard-library module as a read-only bag of its public functions, classes and
    immutable constants: not the modules it imported (verifier round 2: `calendar.sys`,
    `fractions.operator` led to `os`), not shared mutable objects such as `calendar.c` or
    `decimal.DefaultContext`, not the setters of global state (round 3)."""
    return types.SimpleNamespace(
        **{
            name: value
            for name, value in vars(module).items()
            if not name.startswith("_")
            and name not in STATEFUL
            and not isinstance(value, types.ModuleType)
            and (callable(value) or isinstance(value, IMMUTABLE))
        }
    )


def _namespace(target: Target, names: Iterable[str], stdlib: Iterable[str]) -> dict[str, object]:
    return _namespace_of(target.module, names, stdlib)


def _namespace_of(
    module: types.ModuleType, names: Iterable[str], stdlib: Iterable[str]
) -> dict[str, object]:
    """What an expression (a property's, or a method object's code) may use: the safe
    builtins, the module's own names it names, and standard-library stand-ins."""
    namespace: dict[str, object] = {"__builtins__": _builtins()}
    for name in names:
        if not hasattr(module, name):
            raise PropertyError(f"{module.__name__} has no name {name}")
        value = getattr(module, name)
        if not _usable(value, module.__name__):  # e.g. `os` or an imported `system`
            raise PropertyError(f"{name} is not the module's own name or plain data")
        namespace[name] = value
    copy_root = _norm(os.getcwd())
    for name in stdlib:
        try:
            module = importlib.import_module(name)
        except Exception as exc:
            raise PropertyError(
                f"the module {name} does not import ({type(exc).__name__})"
            ) from None
        origin = getattr(module, "__file__", None)
        if isinstance(origin, str) and _norm(origin).startswith(copy_root):
            raise PropertyError(f"{name} resolves to a file of the repo, not the standard library")
        namespace[name] = _stand_in(module)
    return namespace


# Types of plain values a property may use as they are (a compiled regex, a Decimal...).
PLAIN_MODULES = frozenset({"builtins", "re", "decimal", "fractions", "datetime", "enum"})


def _usable(value: object, module: str) -> bool:
    """A module-level name a property may use: never a module; a function or class only if the
    target's module defines it (an exception class from anywhere); otherwise plain data, whose
    type comes from the builtins, a few pure stdlib modules or the module itself. So no property
    can reach I/O through something the module imported."""
    if isinstance(value, types.ModuleType):
        return False
    if isinstance(value, type) and issubclass(value, BaseException):
        return True
    if callable(value):
        return getattr(value, "__module__", None) == module
    return type(value).__module__ in PLAIN_MODULES or type(value).__module__ == module


def _exceptions(
    names: Iterable[str], namespace: Mapping[str, object]
) -> tuple[type[BaseException], ...]:
    found: list[type[BaseException]] = []
    for name in names:
        value = namespace.get(name, getattr(builtins, name, None))
        if not (isinstance(value, type) and issubclass(value, BaseException)):
            raise PropertyError(f"{name} is not an exception class here")
        found.append(value)
    return tuple(found)


def load_property(spec: Mapping[str, Any], target: Target) -> Property:
    namespace = _namespace(target, spec.get("names", []), spec.get("stdlib", []))
    label = spec["id"]
    prop = Property(
        spec["id"],
        spec["kind"],
        _compile(spec.get("when", ""), f"{label}.when"),
        _compile(spec.get("check", ""), f"{label}.check"),
        _compile(spec.get("expected", ""), f"{label}.expected"),
        _compile(spec.get("transform", ""), f"{label}.transform"),
        _exceptions(spec.get("exceptions", []), namespace),
        namespace,
    )
    prop.data = tuple(name for name in spec.get("names", []) if not callable(namespace.get(name)))
    texts = [str(spec.get(k, "")) for k in ("when", "check", "expected", "transform")]
    params = {q.name for q in _parameters(target)}
    prop.mentions = frozenset(n for text in texts for n in _names_in(text)) & params
    prop.huge_ok = spec.get("huge_ok") is True
    prop.defaults = _literal_defaults(target)
    prop.finite_only = not any(_mentions_non_finite(text) for text in texts)
    if target.receivers is not None:
        prop.receiver = True
        prop.uses_self = any(RECEIVER in _names_in(text) for text in texts)
        prop.scopes_objects = RECEIVER in _names_in(texts[0])
    if prop.kind == "example":
        try:
            decoded = {k: from_source(v) for k, v in spec["args"].items()}
        except ValueError as exc:
            raise PropertyError(f"the example's input is not a literal: {exc}") from None
        prop.example = decoded
        prop.example_expected = spec.get("example_expected", "")
        prop.compare = spec.get("compare", "eq")
    return prop


@dataclass(frozen=True)
class Verdict:
    status: str  # holds | violated | not_applicable | oracle_error
    detail: str = ""
    expected: str | None = None  # the expected value's repr, when the property names one
    warned: str = ""  # a relation's second call raised this warning first (M11 S4)


HOLDS = Verdict("holds")
NOT_APPLICABLE = Verdict("not_applicable")


def _eval(code: types.CodeType, namespace: dict[str, object]) -> object:
    # Compiled from hygiene-checked text, run only here, inside the sandboxed run.
    return eval(code, namespace)


def _scope(
    prop: Property, args: Mapping[str, object], outcome: Outcome | None = None, **extra: object
) -> dict[str, object]:
    # Fresh copies of the module's data too: an expression like `TABLE.clear() or ...` must not
    # change what the target and later properties see (verifier round 3).
    data = _copied({name: prop.namespace[name] for name in prop.data})
    given = {k: v for k, v in args.items() if k != RECEIVER} if prop.receiver else args
    scope = {**prop.namespace, **data, **_copied(prop.defaults), **_copied(given), **extra}
    if prop.receiver and outcome is not None:
        # `self` as it was before the call (a fresh copy each time, like the arguments), and
        # `self_after`, the object the call ran on (M7.5, D3).
        if prop.uses_self:
            if outcome.before is NO_COPY:
                raise PropertyError("the object could not be copied before the call")
            scope[RECEIVER] = copy.deepcopy(outcome.before)
        scope[AFTER] = outcome.receiver
    return scope


def applies(
    prop: Property,
    args: Mapping[str, object],
    outcome: Outcome | None = None,
    on_error: Callable[[str], None] | None = None,
) -> bool | None:
    """Whether the property's `when` holds for these args (a method's `self`: the object as the
    call `outcome` found it); None if `when` itself errors (`on_error` hears what it said)."""
    if prop.kind == "example":
        return prop.example is not None and _same_input(prop.example, args)
    if prop.finite_only and _non_finite(_plain_values(args) if prop.receiver else args, 0):
        return False
    if prop.when is None:
        return True
    try:
        return bool(_eval(prop.when, _scope(prop, args, outcome)))
    except Exception as exc:
        if on_error is not None:
            on_error(f"{type(exc).__name__}: {_safe_str(exc)}")
        return None


HUGE_INT = 2**31 - 1
HUGE_FLOAT = 1e300


def _huge(value: object) -> bool:
    """One of the huge boundary values (or bigger): ±(2**31 - 1), ±(2**63 - 1), 10**18, ±1e308."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return abs(value) >= HUGE_INT
    if isinstance(value, float):
        return math.isfinite(value) and abs(value) >= HUGE_FLOAT
    return False


def _literal_defaults(target: Target) -> dict[str, object]:
    """The target's parameter defaults that are plain literals (they can be written in a repro
    file). Any other default, such as `opener=open` or a sentinel `object()`, stays unbound: a
    model expression must not reach it (verifier round 4)."""
    found: dict[str, object] = {}
    for q in _parameters(target):
        if q.default is q.empty:
            continue
        source = to_source(q.default)
        if source is not None:
            found[q.name] = from_source(source)
    return found


def _names_in(text: str) -> set[str]:
    """The names an expression uses (and the keys of a `transform` dict literal)."""
    if not text.strip():
        return set()
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except (SyntaxError, ValueError, RecursionError):
        return set()
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    if isinstance(tree.body, ast.Dict):
        names |= {k.value for k in tree.body.keys if isinstance(k, ast.Constant)
                  and isinstance(k.value, str)}  # fmt: skip
    return names


NON_FINITE_NAMES = frozenset({"nan", "inf", "isnan", "isinf", "isfinite", "infinity"})
NON_FINITE_STRINGS = frozenset({"nan", "inf", "-inf", "+inf", "infinity", "-infinity"})


def _mentions_non_finite(text: str) -> bool:
    """Whether an expression speaks about NaN or infinities: a name or attribute such as
    `math.isnan` or `math.inf`, or a string such as "nan" (`float("nan")`). Read from the syntax
    tree, so a name that merely contains the letters (`nanos`, `info`) does not count (verifier
    round 2)."""
    if not text.strip():
        return False
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except (SyntaxError, ValueError, RecursionError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id.lower() in NON_FINITE_NAMES:
            return True
        if isinstance(node, ast.Attribute) and node.attr.lower() in NON_FINITE_NAMES:
            return True
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.strip().lower() in NON_FINITE_STRINGS
        ):
            return True
    return False


def _non_finite(value: object, depth: int) -> bool:
    """A NaN or an infinity anywhere in the value (containers looked into)."""
    if depth > MAX_DEPTH:
        return False
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, complex):
        return not (math.isfinite(value.real) and math.isfinite(value.imag))
    if isinstance(value, decimal.Decimal):
        return not value.is_finite()
    if isinstance(value, Mapping):
        return any(_non_finite(v, depth + 1) for v in [*value.keys(), *value.values()])
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_non_finite(v, depth + 1) for v in value)
    return False


def _same_input(a: Mapping[str, object], b: Mapping[str, object]) -> bool:
    return input_key(a) == input_key(b)


def _judged(prop: Property, outcome: Outcome) -> Outcome:
    """What the property is judged on: the raise, if the first call raised a warning the property
    names as allowed or expected; else the call with warnings ignored (M11 S4). A `returns`
    property's `exceptions` mean nothing (`judge` reads them only for the other kinds)."""
    raised = outcome.warned
    if raised is None:
        return outcome
    if prop.kind == "example":
        named = prop.compare == "raises" and type(raised.error).__name__ == prop.example_expected
    else:
        named = prop.kind != "returns" and isinstance(raised.error, prop.exceptions)
    return raised if named else outcome


def judge(
    prop: Property,
    args: Mapping[str, object],
    outcome: Outcome,
    call_again: Callable[[Mapping[str, object]], Outcome],
) -> Verdict:
    """Does this outcome satisfy the property? Only for inputs it applies to. An error in the
    property's own expressions is an oracle error: the input is not judged."""
    outcome = _judged(prop, outcome)
    try:
        if prop.kind == "example":
            return _judge_example(prop, outcome)
        if prop.kind == "raises":
            return _judge_raises(prop, outcome)
        if prop.kind == "relation":
            return _judge_relation(prop, args, outcome, call_again)
        allowed = prop.kind == "raises_only" and outcome.raised
        if outcome.error is not None:
            if allowed and isinstance(outcome.error, prop.exceptions):
                return HOLDS
            return Verdict("violated", outcome.describe())
        if prop.check is not None and not _eval(
            prop.check, _scope(prop, args, outcome, result=outcome.value)
        ):
            return Verdict("violated", f"{outcome.describe()}; the check does not hold")
        if prop.expected is not None:
            expected = _eval(prop.expected, _scope(prop, args, outcome))
            if outcome.value != expected:
                shown = _safe_repr(expected)
                return Verdict("violated", f"expected {shown}, {outcome.describe()}", shown)
        return HOLDS
    except Exception as exc:
        return Verdict("oracle_error", f"{type(exc).__name__}: {_safe_str(exc)}")


def _judge_raises(prop: Property, outcome: Outcome) -> Verdict:
    names = ", ".join(e.__name__ for e in prop.exceptions)
    if outcome.error is None:
        return Verdict("violated", f"{outcome.describe()}, but should raise {names}")
    if not isinstance(outcome.error, prop.exceptions):
        return Verdict("violated", f"{outcome.describe()}, but should raise {names}")
    return HOLDS


def _judge_relation(
    prop: Property,
    args: Mapping[str, object],
    outcome: Outcome,
    call_again: Callable[[Mapping[str, object]], Outcome],
) -> Verdict:
    if outcome.error is not None:
        if isinstance(outcome.error, prop.exceptions):
            return NOT_APPLICABLE
        return Verdict("violated", outcome.describe())
    assert prop.transform is not None and prop.check is not None
    changes = _eval(prop.transform, _scope(prop, args, outcome, result=outcome.value))
    if not isinstance(changes, dict):
        raise TypeError("the transform must give a dict of new arguments")
    second_args = {**args, **changes}
    second = _judged(prop, call_again(second_args))
    if second.error is not None:
        if isinstance(second.error, prop.exceptions):
            return NOT_APPLICABLE
        return Verdict(
            "violated",
            f"the second call ({input_key(second_args)}) {second.describe()}",
            warned=second.warned_name(),
        )
    scope = _scope(prop, args, outcome, result=outcome.value, result2=second.value)
    if not _eval(prop.check, scope):
        return Verdict(
            "violated",
            f"{outcome.describe()}; the second call "
            f"({input_key(second_args)}) {second.describe()}; "
            "the relation does not hold",
            warned=second.warned_name(),
        )
    return HOLDS


def _judge_example(prop: Property, outcome: Outcome) -> Verdict:
    expected = prop.example_expected
    if prop.compare == "raises":
        if outcome.error is not None and type(outcome.error).__name__ == expected:
            return HOLDS
        return Verdict(
            "violated",
            f"the docstring says it raises {expected}; it {outcome.describe()}",
            expected,
        )
    if outcome.error is not None:
        return Verdict(
            "violated", f"the docstring says {expected}; it {outcome.describe()}", expected
        )
    if prop.compare == "repr":
        # What doctest itself would see: the printed output, then the result's repr unless None.
        shown = outcome.stdout + (repr(outcome.value) + "\n" if outcome.value is not None else "")
        same = doctest.OutputChecker().check_output(expected + "\n", shown, 0)
    else:
        same = outcome.value == from_source(expected)
    if same:
        return HOLDS
    return Verdict("violated", f"the docstring says {expected}; it {outcome.describe()}", expected)


def _outcome_class(outcome: Outcome) -> str:
    return f"raised:{type(outcome.error).__name__}" if outcome.error is not None else "value"


# --- the attack -----------------------------------------------------------------------------------


@dataclass
class _Input:
    phase: str  # doc | witness | advisory | grid | evidence | model | boundary
    args: dict[str, object]
    witness: str = ""  # the witness's test id, for witnesses
    doc: str = ""  # the docstring example's property id, for its own input


@dataclass
class _Attack:
    target: Target
    properties: list[Property]
    reporter: Reporter
    counted: set[str] = field(default_factory=set)
    crashes: int = 0
    oracle_errors: int = 0
    first_oracle_error: str = ""
    unbuilt: int = 0  # inputs whose object could not be built (not inputs at all)
    first_unbuilt: str = ""
    first_unbuilt_brief: str = ""  # the same with the error's type only: what the model is told
    unfit: int = 0  # inputs no property's `when` fits

    def call(self, args: Mapping[str, object]) -> Outcome:
        """One call (`Unbuilt` if a method's object can't be built)."""
        outcome, ran = judged_call(self.target, args)
        return dataclasses.replace(outcome, ran_fix=bool(ran))

    def no_object(self, args: Mapping[str, object], error: Unbuilt) -> None:
        """An input whose object could not be built: a note for the first few, never judged."""
        self.unbuilt += 1
        code = str(args.get(RECEIVER, ""))[:MAX_CALLING_TEXT]
        note = f"no object from {code}: {_safe_str(error)[:300]}"
        if not self.first_unbuilt:
            # The model's copy names the error by its type only, and only a plain name: a class
            # made at run time could carry a message in its name (verifier round 2 of M11).
            kind = error.kind if error.kind.isidentifier() else "an error"
            self.first_unbuilt, self.first_unbuilt_brief = note, f"no object from {code}: {kind}"
        if self.unbuilt <= MAX_UNBUILT_NOTES:
            self.reporter.emit({"event": "note", "target": self.target.id, "note": note})

    def oracle_error(self, detail: str) -> None:
        """A property's own expression failed on an input: that input is not judged by it."""
        self.oracle_errors += 1
        self.first_oracle_error = self.first_oracle_error or detail

    def blame(
        self, prop: Property, args: Mapping[str, object], outcome: Outcome, verdict: Verdict
    ) -> tuple[dict[str, object], Outcome, Verdict] | None:
        """The input the property is to blame for: the same input with every parameter it doesn't
        mention left at its default, if the violation survives that; None if it doesn't (then a
        parameter the property says nothing about caused it). Docstring examples are exact."""
        if prop.kind == "example":
            return dict(args), outcome, verdict
        defaults = {q.name for q in _parameters(self.target) if q.default is not q.empty}
        reset = {k: v for k, v in args.items() if k in prop.mentions or k not in defaults}
        receivers = self.target.receivers
        if (
            receivers is not None
            and not prop.scopes_objects
            and args.get(RECEIVER) not in receivers.vouched
        ):
            # Developer, 9 Oct 2026: an object the run made up counts only for a property whose
            # `when` names `self`; otherwise the typical object stands in, like a default.
            if not receivers.vouched:
                return None
            reset[RECEIVER] = receivers.vouched[0]
        if len(reset) == len(args) and reset.get(RECEIVER) == args.get(RECEIVER):
            blamed = dict(args), outcome, verdict
        else:
            try:
                fresh = self.call(reset)
            except Unbuilt:
                return None
            again = judge(prop, reset, fresh, self.call)
            if again.status != "violated":
                return None
            blamed = reset, fresh, again
        values = _plain_values(blamed[0]) if receivers is not None else blamed[0].values()
        if blamed[1].raised and not prop.huge_ok and any(_huge(v) for v in values):
            return None  # a resource limit the docs never promised about: a crash note
        args_, outcome_, verdict_ = blamed
        # A property that names a left-out parameter judged it at its default; the reported input
        # says so, so the repro file binds it too (verifier round 4).
        named = {
            n: prop.defaults[n]
            for n in sorted(prop.mentions)
            if n not in args_ and n in prop.defaults
        }
        return {**args_, **named}, outcome_, verdict_

    def crash(self, args: Mapping[str, object], outcome: Outcome, phase: str) -> None:
        """A crash, or a wrong result, no property is to blame for: report only (a wrong result
        when a parameter the property doesn't name caused it; verifier round 4)."""
        if self.crashes >= MAX_CRASHES:
            return
        self.crashes += 1
        self.reporter.emit(
            {
                "event": "crash",
                "target": self.target.id,
                "args": {k: to_source(v) for k, v in args.items()},
                "outcome": outcome.report(),
                "phase": phase,
            }
        )

    def violation(
        self,
        prop: Property,
        phase: str,
        args: Mapping[str, object],
        outcome: Outcome,
        verdict: Verdict,
    ) -> None:
        cls = _outcome_class(outcome)
        if prop.violations.get(cls, 0) >= MAX_VIOLATIONS:
            return
        prop.violations[cls] = prop.violations.get(cls, 0) + 1
        sources = {name: to_source(value) for name, value in args.items()}
        report = outcome.report()
        if verdict.warned:  # only the second call warned: the repro file must ignore it too
            report.setdefault("warned", verdict.warned)
        self.reporter.emit(
            {
                "event": "violation",
                "target": self.target.id,
                "property": prop.id,
                "phase": phase,
                "args": sources,
                "representable": all(s is not None for s in sources.values()),
                "outcome": report,
                "detail": verdict.detail[:MAX_TEXT],
                "expected": verdict.expected,
                "ran": outcome.ran_fix,
            }
        )

    def judge_doc(self, item: _Input, outcome: Outcome) -> bool:
        """Judge a docstring example on its own input; True if it holds (the input is then known
        good behaviour, a witness for every other property)."""
        doc = next((p for p in self.properties if p.id == item.doc), None)
        if doc is None:
            return False
        verdict = judge(doc, item.args, outcome, self.call)
        if verdict.status == "oracle_error":
            self.oracle_error(verdict.detail)
        elif verdict.status == "violated":
            self.violation(doc, "doc", item.args, outcome, verdict)
        else:
            # Said out loud: an example that never ran (a hang, a run cut short) is not "held".
            self.reporter.emit({"event": "held", "target": self.target.id, "property": doc.id})
        return verdict.status == "holds"

    def judge_all(self, item: _Input, outcome: Outcome) -> None:
        """Judge one explicit input against every property it applies to. On a witness (a call
        the project's own passing tests make, or a docstring example that holds) a violation
        contradicts the property; on an advisory witness (the PR's tests) it is only noted."""
        as_witness = item.phase == "witness"
        if item.doc:
            as_witness = self.judge_doc(item, outcome) or as_witness
        applied = bool(item.doc)
        unfit = not item.doc and bool(self.properties)
        for prop in self.properties:
            if prop.id == item.doc:
                continue
            if as_witness and prop.kind == "relation":
                # A relation also calls with changed arguments, and the test vouches only for
                # this call: the second one proves nothing either way.
                continue
            fits = applies(prop, item.args, outcome, self.oracle_error)
            unfit = unfit and fits is False
            if not fits:
                continue
            verdict = judge(prop, item.args, outcome, self.call)
            if verdict.status == "oracle_error":
                self.oracle_error(verdict.detail)
                continue
            if verdict.status != "violated":
                applied = True
                continue
            if as_witness:
                self.contradict(prop, item, outcome, verdict)
            elif item.phase == "advisory":
                self.reporter.emit(
                    {
                        "event": "advisory",
                        "target": self.target.id,
                        "property": prop.id,
                        "witness": item.witness,
                        "args": {k: to_source(v) for k, v in item.args.items()},
                        "detail": verdict.detail[:MAX_TEXT],
                    }
                )
            elif prop.live():
                blamed = self.blame(prop, item.args, outcome, verdict)
                if blamed is None:
                    self.crash(item.args, outcome, item.phase)  # not judged: not counted
                else:
                    applied = True
                    self.violation(prop, item.phase, *blamed)
        if as_witness or item.phase == "advisory":
            return
        self.unfit += unfit
        if applied:
            self.counted.add(input_key(item.args))
        elif outcome.raised:
            self.crash(item.args, outcome, item.phase)

    def contradict(self, prop: Property, item: _Input, outcome: Outcome, verdict: Verdict) -> None:
        if prop.contradicted:
            return
        prop.contradicted = True
        where = item.witness or f"the docstring example {item.doc}"
        self.reporter.emit(
            {
                "event": "contradicted",
                "target": self.target.id,
                "property": prop.id,
                "witness": where,
                "args": {k: to_source(v) for k, v in item.args.items()},
                "outcome": outcome.report(),
                "detail": verdict.detail[:MAX_TEXT],
            }
        )


def _decode_args(args: Mapping[str, str]) -> dict[str, object]:
    return {name: from_source(text) for name, text in args.items()}


def _parameters(target: Target) -> list[inspect.Parameter]:
    kinds = (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    )
    return [p for p in target.signature.parameters.values() if p.kind in kinds]


def _seeds(target: Target, spec: Mapping[str, Any]) -> dict[str, list[object]]:
    """Per parameter: the evidence values Tracefix found that fit its type hint (comparison-derived
    values also fit a parameter without one)."""
    seeds: dict[str, list[object]] = {}
    for name, values in spec.get("candidates", {}).items():
        hint = target.hints.get(name)
        kept: list[object] = []
        for entry in values:
            try:
                value = from_source(entry["value"])
            except ValueError:
                continue
            if (hint is None and entry.get("compared")) or (
                hint is not None and accepts(hint, value)
            ):
                kept.append(value)
        seeds[name] = kept
    return seeds


def _first_boundaries(
    target: Target, params: Sequence[inspect.Parameter]
) -> list[dict[str, object]]:
    """One input made of each parameter's first boundary value (parameters with defaults may be
    left out), or none if a required parameter has no type hint to take one from."""
    first: dict[str, object] = {}
    for p in params:
        values = boundaries(target.hints[p.name]) if p.name in target.hints else []
        if values:
            first[p.name] = values[0]
        elif p.default is inspect.Parameter.empty:
            return []
    return [first] if first else []


def _first_with_object(
    target: Target, receivers: Receivers, params: Sequence[inspect.Parameter]
) -> list[dict[str, object]]:
    """A method's typical input when no test or example gives one: each parameter's first
    boundary (as for a function), on the first typical object or one made up."""
    values: dict[str, object] = {}
    for p in params:
        found = boundaries(target.hints[p.name]) if p.name in target.hints else []
        if found:
            values[p.name] = found[0]
        elif p.default is inspect.Parameter.empty:
            return []
    code = receivers.first()
    return [{**values, RECEIVER: code}] if code is not None else []


def explicit_inputs(target: Target, spec: Mapping[str, Any], limit: int) -> list[_Input]:
    """Every explicit input, in order: docstring examples, witnesses, advisory witnesses, inputs
    replayed from earlier rounds, the grid and evidence examples, evidence values swept over
    typical inputs, model examples, then type boundaries swept over typical inputs. Duplicates
    dropped, at most `limit` (witnesses, docstring examples and replayed inputs always kept).
    For a method called on an object, every input has one (`self`), and objects made up one
    constructor parameter away from the typical one follow each kind of sweep (evidence values,
    then boundaries)."""
    out: list[_Input] = []
    for prop in spec.get("properties", []):
        if prop["kind"] == "example":
            out.append(_Input("doc", _decode_args(prop["args"]), doc=prop["id"]))
    witnesses = [
        _Input(
            "repro" if w.get("repro") else "advisory" if w.get("advisory") else "witness",
            _decode_args(w["args"]),
            witness=w["id"],
        )
        for w in spec.get("witnesses", [])
    ]
    out += witnesses
    # Inputs that broke an earlier round's properties, judged like any other input and on top of
    # the limit: one bug that two properties notice becomes one finding (plan P10).
    out += [_Input("replay", _decode_args(args)) for args in spec.get("replay", [])]
    params = _parameters(target)
    receivers = target.receivers
    required = {p.name for p in params if p.default is inspect.Parameter.empty}
    if receivers is not None:
        required.add(RECEIVER)
    examples = [(e["phase"], _decode_args(e["args"])) for e in spec.get("examples", [])]
    # Sweeps vary one parameter at a time around typical inputs: known-good calls first.
    typical = [w.args for w in witnesses if w.phase == "witness"][:2]
    typical = typical or [args for _, args in examples if required <= args.keys()][:1]
    if receivers is None:
        typical = typical or _first_boundaries(target, params)
    else:
        typical = typical or _first_with_object(target, receivers, params)
    # An example naming only some parameters (e.g. the ones the fix compares) takes the others
    # from a typical input; without one it is dropped: a missing argument is not a bug.
    examples = [
        (phase, args if required <= args.keys() else {**typical[0], **args})
        for phase, args in examples
        if required <= args.keys() or typical
    ]
    fixed = len(out)
    out += [_Input(phase, args) for phase, args in examples if phase in ("grid", "evidence")]
    seeds = _seeds(target, spec)
    for base in typical:
        for p in params:
            out += [_Input("evidence", {**base, p.name: value}) for value in seeds.get(p.name, [])]
    objects: tuple[list[str], list[str]] = ([], [])
    if receivers is not None and typical:
        around = typical[0].get(RECEIVER)
        objects = receivers.sweep(
            around if isinstance(around, str) else None, receivers.seeds(spec)
        )
    out += [_Input("evidence", {**typical[0], RECEIVER: code}) for code in objects[0]]
    out += [_Input(phase, args) for phase, args in examples if phase == "model"]
    for base in typical:
        for p in params:
            if p.name in target.hints:
                out += [
                    _Input("boundary", {**base, p.name: value})
                    for value in boundaries(target.hints[p.name])
                ]
    out += [_Input("boundary", {**typical[0], RECEIVER: code}) for code in objects[1]]
    kept = out[:fixed]
    seen = {input_key(i.args) for i in kept if i.phase in ("grid", "evidence", "model", "boundary")}
    for item in out[fixed:]:
        key = input_key(item.args)
        if key in seen:
            continue
        seen.add(key)
        kept.append(item)
        if len(kept) >= fixed + limit:
            break
    return kept


def _strategies(
    target: Target, spec: Mapping[str, Any]
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    """A Hypothesis strategy per parameter (seeds first, so shrinking prefers them), or None when
    a required parameter (or a method's `self`) has none; notes; and the ones that have none. The
    notes stop at the first one with none: they can reach the Judge's request, which must not
    change (M11 S3)."""
    notes: list[str] = []
    missing: list[str] = []
    kept = 0  # how many notes to keep once one has none
    seeds = _seeds(target, spec)
    model = spec.get("strategies", {})
    out: dict[str, Any] = {}
    for p in _parameters(target):
        parts: list[Any] = []
        hint = target.hints.get(p.name)
        values = [*seeds.get(p.name, []), *(boundaries(hint) if hint is not None else [])]
        if values:
            parts.append(st.sampled_from(values))
        if hint is not None and hint is not typing.Any:
            try:
                parts.append(st.from_type(typing.cast(Any, hint)))
            except Exception as exc:
                notes.append(f"no strategy from the type of {p.name}: {type(exc).__name__}")
        if p.name in model:
            try:
                parts.append(eval(model[p.name], {"st": st, "__builtins__": {}}))
            except Exception as exc:
                notes.append(f"the proposed strategy for {p.name} failed: {type(exc).__name__}")
        if p.default is not inspect.Parameter.empty:
            parts.append(st.just(OMIT))
        if not parts:
            if p.default is inspect.Parameter.empty:
                notes.append(f"no way to generate {p.name}, so there is no search")
                kept = kept or len(notes)
                missing.append(p.name)
            continue
        out[p.name] = st.one_of(*parts) if len(parts) > 1 else parts[0]
    if target.receivers is not None:
        objects = target.receivers.strategy(target.receivers.seeds(spec))
        if objects is None:
            owner = target.receivers.owner_name
            notes.append(f"no way to build an object of {owner}, so there is no search")
            kept = kept or len(notes)
            missing.append(RECEIVER)
        else:
            out[RECEIVER] = objects
    return (None, notes[:kept], missing) if missing else (out, notes, missing)


def _settings(plan: Mapping[str, Any]) -> settings:
    options: dict[str, Any] = {}
    if plan.get("backend", "hypothesis") != "hypothesis":
        options["backend"] = plan["backend"]  # the M7 hook (e.g. "crosshair")
    return settings(
        max_examples=int(plan.get("search_examples", 200)),
        derandomize=True,
        database=None,
        deadline=None,
        suppress_health_check=list(HealthCheck),
        phases=[Phase.generate, Phase.shrink],
        verbosity=Verbosity.quiet,
        **options,
    )


def _without_omitted(drawn: Mapping[str, object]) -> dict[str, object]:
    return {k: v for k, v in drawn.items() if v is not OMIT}


def search(
    attack: _Attack, prop: Property, strategies: Mapping[str, Any], config: settings
) -> None:
    """Hypothesis looks for an input the property applies to and that violates it, then shrinks
    it; the minimal one is reported (phase "search")."""

    def violated(drawn: Mapping[str, object]) -> bool:
        args = _without_omitted(drawn)
        if attack.target.receivers is not None:
            # A method's `when` may read its object as the call found it: the call comes first.
            try:
                outcome = attack.call(args)
            except Unbuilt as exc:
                attack.no_object(args, exc)
                assume(False)  # no object: not an input
            fits = applies(prop, args, outcome, attack.oracle_error)
        else:
            fits = applies(prop, args, None, attack.oracle_error)
        if not fits:
            # Not an input the property speaks about: discarded, so the budget of examples is
            # spent on inputs it applies to.
            attack.unfit += fits is False
            assume(False)
        if attack.target.receivers is None:
            outcome = attack.call(args)
        attack.counted.add(input_key(args))
        verdict = judge(prop, args, outcome, attack.call)
        if verdict.status == "oracle_error":
            attack.oracle_error(verdict.detail)
        return (
            verdict.status == "violated" and attack.blame(prop, args, outcome, verdict) is not None
        )

    try:
        drawn = find(st.fixed_dictionaries(dict(strategies)), violated, settings=config)
    except NoSuchExample:
        return
    except HypothesisException as exc:
        attack.reporter.emit(
            {
                "event": "note",
                "target": attack.target.id,
                "property": prop.id,
                "note": (
                    "the search found no input its `when` fits (a narrow rule: the explicit "
                    "inputs still judged it)"
                    if isinstance(exc, Unsatisfiable)
                    else f"the search could not run: {type(exc).__name__}: {_safe_str(exc)[:300]}"
                ),
            }
        )
        return
    args = _without_omitted(drawn)
    try:
        outcome = attack.call(args)
    except Unbuilt:
        return  # the object built during the search but not now: nothing to report
    verdict = judge(prop, args, outcome, attack.call)
    blamed = attack.blame(prop, args, outcome, verdict) if verdict.status == "violated" else None
    if blamed is not None:
        attack.violation(prop, "search", *blamed)


def _unit_end(attack: _Attack, unit: str) -> None:
    reached = {path: sorted(lines) for path, lines in attack.target.reached.items()}
    contradicted = [p.id for p in attack.properties if p.contradicted]
    attack.reporter.emit(
        {
            "event": "end",
            "target": attack.target.id,
            "unit": unit,
            "inputs": len(attack.counted),
            "oracle_errors": attack.oracle_errors,
            "first_oracle_error": attack.first_oracle_error[:MAX_TEXT],
            "unbuilt": attack.unbuilt,
            "first_unbuilt": attack.first_unbuilt[:MAX_TEXT],
            "first_unbuilt_brief": attack.first_unbuilt_brief[:MAX_TEXT],
            "unfit": attack.unfit,
            "reached": reached,
            "contradicted": contradicted,
        }
    )


def attack_target(
    spec: Mapping[str, Any],
    plan: Mapping[str, Any],
    config: settings,
    tracer: LineTracer | None,
    reporter: Reporter,
) -> None:
    tid = spec["id"]
    skip = set(plan.get("skip", {}).get(tid, []))
    try:
        target = load_target(spec, tracer, fixed_lines(plan))
    except TargetError as exc:
        reporter.emit({"event": "target", "target": tid, "error": str(exc)[:MAX_TEXT]})
        return
    reporter.emit(
        {
            "event": "target",
            "target": tid,
            "module": target.module_name,
            "params": [p.name for p in _parameters(target)],
            "hints": {k: _safe_repr(v)[:200] for k, v in target.hints.items()},
            "traced": bool(tracer and tracer.available),
            "trace_reason": tracer.reason if tracer else "no fixed lines",
        }
    )
    properties: list[Property] = []
    for prop_spec in spec.get("properties", []):
        try:
            properties.append(load_property(prop_spec, target))
        except PropertyError as exc:
            reporter.emit(
                {
                    "event": "property_error",
                    "target": tid,
                    "property": prop_spec["id"],
                    "error": str(exc)[:MAX_TEXT],
                }
            )
    for pid in plan.get("contradicted", {}).get(tid, []):
        for prop in properties:
            if prop.id == pid:
                prop.contradicted = True
    attack = _Attack(target, properties, reporter)
    if "explicit" not in skip:
        start = int(plan.get("explicit_from", {}).get(tid, 0))
        limit = int(plan.get("max_explicit", 400))
        inputs = explicit_inputs(target, spec, limit)
        reporter.emit({"event": "begin", "target": tid, "unit": "explicit", "count": len(inputs)})
        for index in range(start, len(inputs)):
            item = inputs[index]
            reporter.emit(
                {
                    "event": "calling",
                    "target": tid,
                    "index": index,
                    "input": input_key(item.args)[:MAX_CALLING_TEXT],
                }
            )
            try:
                outcome = attack.call(item.args)
            except Unbuilt as exc:
                attack.no_object(item.args, exc)
                continue
            attack.judge_all(item, outcome)
        _unit_end(attack, "explicit")
    strategies, notes, missing = _strategies(target, spec)
    for note in notes:
        reporter.emit({"event": "note", "target": tid, "note": note})
    reporter.emit({"event": "no_strategy", "target": tid, "params": missing})
    for prop in properties:
        unit = f"search:{prop.id}"
        if prop.kind == "example" or not prop.live() or unit in skip or strategies is None:
            continue
        reporter.emit({"event": "begin", "target": tid, "unit": unit})
        search(attack, prop, strategies, config)
        _unit_end(attack, unit)


def _tracer(plan: Mapping[str, Any]) -> LineTracer | None:
    """A tracer over every changed source file with fixed lines, or None if there is none."""
    files = {
        os.path.join(os.getcwd(), *PurePosixPath(path).parts): path for path in fixed_lines(plan)
    }
    return LineTracer(files) if files else None


def run_attack(plan: Mapping[str, Any], reporter: Reporter) -> None:
    tracer = _tracer(plan)
    config = _settings(plan)
    try:
        for spec in plan.get("targets", []):
            try:
                attack_target(spec, plan, config, tracer, reporter)
            except Exception as exc:  # a bug here must not hide the other targets' results
                reporter.emit(
                    {
                        "event": "target_error",
                        "target": spec.get("id"),
                        "error": f"{type(exc).__name__}: {_safe_str(exc)}",
                    }
                )
    finally:
        if tracer is not None:
            tracer.close()


def run_probe(plan: Mapping[str, Any], reporter: Reporter) -> None:
    """One traced call per input: its outcome and the fixed lines it ran."""
    tracer = _tracer(plan)
    try:
        _probe_calls(plan, reporter, tracer)
    finally:
        if tracer is not None:
            tracer.close()


def _probe_calls(plan: Mapping[str, Any], reporter: Reporter, tracer: LineTracer | None) -> None:
    targets: dict[str, Target | str] = {}
    for spec in plan.get("targets", []):
        try:
            targets[spec["id"]] = load_target(spec, tracer, fixed_lines(plan))
        except TargetError as exc:
            targets[spec["id"]] = str(exc)[:MAX_TEXT]
    for index, call in enumerate(plan.get("calls", [])):
        target = targets.get(call["target"], "unknown target")
        if isinstance(target, str):
            reporter.emit({"event": "probe", "index": index, "missing": target})
            continue
        try:
            args = _decode_args(call["args"])
        except ValueError as exc:
            reporter.emit({"event": "probe", "index": index, "missing": f"bad input: {exc}"})
            continue
        try:
            outcome, ran = judged_call(target, args)
        except Unbuilt as exc:
            reporter.emit({"event": "probe", "index": index, "unbuilt": _safe_str(exc)[:MAX_TEXT]})
            continue
        traced = tracer is not None and tracer.available and not tracer.disturbed
        reporter.emit(
            {
                "event": "probe",
                "index": index,
                "outcome": outcome.report(),
                "lines": {p: sorted(lines) for p, lines in ran.items()},
                "traced": traced,
            }
        )


# --- the behaviour diff (SPEC 2.5, Decided in M7) -------------------------------------------------

SHOWN_TEXT = (
    1_000  # characters of a value, message or output reported for display; digests cover all
)


def _full_str(error: BaseException) -> str:
    try:
        text = str(error)
    except Exception as exc:
        text = f"<unprintable message: {type(exc).__name__}>"
    return _masked(text)


def _innermost(error: BaseException) -> types.TracebackType | None:
    tb = error.__traceback__
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    return tb


def _in_copy(filename: str) -> bool:
    return _norm(filename).startswith(_norm(os.getcwd()) + os.sep)


def _raised_in(error: BaseException) -> str:
    """'repo' if a `raise` statement in a file of the copy under test raised it (its message is
    the repo's own words), else 'python': Python itself or a library made the message, and its
    wording can differ between Python versions (`int("x")` called from repo code is 'python')."""
    tb = _innermost(error)
    if tb is None:
        return "python"
    filename = tb.tb_frame.f_code.co_filename
    if not _in_copy(filename):
        return "python"
    return "repo" if _raises(linecache.getline(filename, tb.tb_lineno)) else "python"


def _raises(line: str) -> bool:
    """The line holds a `raise` statement (also `if x: raise ...`), read as tokens so the word
    inside a string doesn't count (verifier round 2, N-e). A line that doesn't tokenize alone
    (part of a longer statement) doesn't count either: then Python's words are not shown."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(line.strip() + "\n").readline))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return False
    return any(t.type == tokenize.NAME and t.string == "raise" for t in tokens)


def diff_report(outcome: Outcome) -> dict[str, str]:
    """One call's outcome as the behaviour diff compares it: kind, type (and its module), the
    shown text, a digest of its whole state (a snapshot: the message, args and attributes for a
    raise), a digest and the start of what it printed, for a raise where it was raised, and why it
    is opaque, if it is."""
    printed = _masked(outcome.stdout)
    if outcome.error is not None:
        error = type(outcome.error)
        message = _full_str(outcome.error)
        state, opaque = snapshot(outcome.error)
        rest, _ = snapshot(_beside_message(outcome.error))
        report = {
            "kind": "raised",
            "type": error.__name__,
            "module": error.__module__,
            "text": message[:SHOWN_TEXT],
            "digest": _digest(f"{message}\n{state}"),
            "rest": _digest(rest),
            "where": _raised_in(outcome.error),
        }
    else:
        state, opaque = snapshot(outcome.value)
        plain = _masked(_plain_repr(outcome.value))
        report = {
            "kind": "returned",
            "type": type(outcome.value).__name__,
            "module": type(outcome.value).__module__,
            # The repr reads best; where it shows an address, the snapshot shows the state.
            "text": (state if "at 0x?>" in plain and not opaque else plain)[:SHOWN_TEXT],
            "digest": _digest(state),
        }
    report["shot"] = state[:SHOWN_TEXT]  # shown when two plain texts look the same (round 7)
    report["out"] = _digest(printed) if printed else ""
    report["out_text"] = printed[:SHOWN_TEXT]
    report["opaque"] = opaque[:200]
    return report


def _beside_message(error: BaseException) -> object:
    """Everything a raised exception holds besides its message: args (unless they are just the
    message), C fields, cause, context and attributes. Only a change in the message alone is a
    "message" change (verifier round 7: an exception's state is not its wording)."""
    args = BaseException.args.__get__(error)  # type: ignore[attr-defined]
    try:
        text = str(error)
    except Exception:
        text = None
    just_message = args == () or (len(args) == 1 and isinstance(args[0], str) and args[0] == text)
    state = sorted((str(k), v) for k, v in _state(error).items())
    return ["<the message>" if just_message else args, sorted(_error_fields(error).items()), state]


def unbindable(signature: inspect.Signature, args: Mapping[str, object]) -> str | None:
    """Why `args` can't be passed to a function with this signature as they are (a parameter it
    doesn't have, a required one missing, a positional-only one after a missing one), or None.
    Never drops an argument: a parameter only the fix added must not quietly fall away."""
    params = {p.name: p for p in signature.parameters.values()}
    unknown = sorted(n for n in args if n not in params or params[n].kind in _VARIADIC)
    if unknown:
        return f"no parameter {', '.join(unknown)} here"
    missing = sorted(
        p.name
        for p in params.values()
        if p.kind not in _VARIADIC and p.default is p.empty and p.name not in args
    )
    if missing:
        return f"the required parameter {', '.join(missing)} is not given"
    skipped = False
    for p in params.values():
        if p.kind is not inspect.Parameter.POSITIONAL_ONLY:
            continue
        if p.name not in args:
            skipped = True
        elif skipped:
            return f"the positional-only {p.name} comes after one that is left out"
    return None


_VARIADIC = (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)


def _unbindable(target: Target, args: Mapping[str, object]) -> str | None:
    """`unbindable` for a target: a method called on an object needs the code that builds it,
    and the rest must fit the method's own parameters."""
    if target.receivers is None:
        return unbindable(target.signature, args)
    if not isinstance(args.get(RECEIVER), str):
        return "no object to call the method on"
    return unbindable(target.signature, {k: v for k, v in args.items() if k != RECEIVER})


def _draw(
    target: Target, spec: Mapping[str, Any], count: int
) -> tuple[list[dict[str, object]], bool, list[str]]:
    """`count` inputs drawn by Hypothesis from the type hints and seeds (derandomized, generate
    phase only, nothing shrunk): the draws, whether the generator ran out of new inputs before
    `count`, and notes."""
    strategies, notes, _ = _strategies(target, spec)
    if strategies is None or count <= 0:
        return [], False, notes
    found: list[dict[str, object]] = []

    def keep(drawn: Mapping[str, object]) -> bool:
        found.append(_without_omitted(drawn))
        return False

    config = settings(
        max_examples=count,
        derandomize=True,
        database=None,
        deadline=None,
        suppress_health_check=list(HealthCheck),
        phases=[Phase.generate],
        verbosity=Verbosity.quiet,
    )
    try:
        find(st.fixed_dictionaries(dict(strategies)), keep, settings=config)
    except NoSuchExample:
        pass
    except HypothesisException as exc:
        # A generator that broke did not run out of inputs (verifier B2a).
        notes.append(f"the draws stopped early: {type(exc).__name__}: {_safe_str(exc)[:300]}")
        return found, False, notes
    return found, len(found) < count, notes


def _finite(hint: object) -> bool:
    """A type whose values can all be listed: bool, None, a Literal or an Enum (and unions of
    them). Anything else, or no hint at all, is not (verifier B2b)."""
    for member in _members(hint):
        if member is bool or member is None or member is _NONE:
            continue
        if typing.get_origin(member) is typing.Literal:
            continue
        if isinstance(member, type) and issubclass(member, enum.Enum):
            continue
        return False
    return True


def finite_domain(target: Target) -> bool:
    """Every parameter's values can all be listed, so running out of new inputs means every
    input was tried, and the L3 input floor may be waived."""
    objects = target.receivers is None or target.receivers.finite()
    return objects and all(
        p.name in target.hints and _finite(target.hints[p.name]) for p in _parameters(target)
    )


def diff_inputs(
    target: Target, spec: Mapping[str, Any], limit: int, draws: int
) -> tuple[list[_Input], dict[str, Any]]:
    """Every input the behaviour diff compares for one target, in order: the explicit inputs (as
    for an attack: docstring examples, test calls, the grid and evidence, boundaries), then the
    draws. Only plain literals (the other side replays them as code), no repeats. A function
    without parameters gets its one call."""
    stats: dict[str, Any] = {"drawn": 0, "requested": draws, "exhausted": False, "dropped": 0}
    if not _parameters(target) and target.receivers is None:
        stats["exhausted"] = True
        return [_Input("call", {})], stats
    candidates = explicit_inputs(target, spec, limit)
    drawn, exhausted, notes = _draw(target, spec, draws)
    # "Exhausted" waives the L3 input floor: only when the generator ran out of a domain that
    # really is finite, never when its only sources were a few seeds or boundaries.
    stats.update(drawn=len(drawn), exhausted=exhausted and finite_domain(target), notes=notes)
    candidates += [_Input("draw", args) for args in drawn]
    kept: list[_Input] = []
    seen: set[str] = set()
    for item in candidates:
        if any(to_source(v) is None for v in item.args.values()):
            stats["dropped"] += 1
            continue
        key = input_key(item.args)
        if key not in seen:
            seen.add(key)
            kept.append(item)
    return kept, stats


def _doc_verdicts(
    docs: Sequence[Property], args: Mapping[str, object], outcome: Outcome
) -> dict[str, str]:
    """For each docstring example whose input this is: whether this outcome keeps it."""
    verdicts: dict[str, str] = {}
    for doc in docs:
        if doc.example is None or not _same_input(doc.example, args):
            continue
        try:
            verdicts[doc.id] = _judge_example(doc, outcome).status
        except Exception:  # an expected value that doesn't decode here
            verdicts[doc.id] = "oracle_error"
    return verdicts


def _doc_properties(target: Target, spec: Mapping[str, Any], reporter: Reporter) -> list[Property]:
    docs = []
    for doc in spec.get("docs", []):
        try:
            docs.append(load_property({**doc, "kind": "example"}, target))
        except PropertyError as exc:
            reporter.emit({"event": "note", "target": target.id, "note": f"{doc['id']}: {exc}"})
    return docs


MAX_WATCHED = 20_000  # files in the copy checked per function; past it, the check can't vouch
_UNWATCHED = frozenset({"__pycache__", ".pytest_cache", ".hypothesis", ".git"})
_RACY_NS = 100_000_000  # a file this close to the first look may still change within its tick
FileKey = tuple[int, int, int, str]  # size, modification time, change time, digest ("" unread)
Files = dict[str, FileKey]


def copy_files() -> tuple[Files, int] | None:
    """Every file in the copy, each looked at itself (a folder listing can show an old size for
    a file still held open), and when: None if there are more than MAX_WATCHED. A file changed
    too close to now to trust its times (git's "racily clean" rule) has its content read too.
    The change time is part of the key where `utime` can't set it (not on Windows)."""
    now = time.time_ns()
    found: Files = {}
    folders = [os.getcwd()]
    while folders:
        try:
            entries = list(os.scandir(folders.pop()))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name not in _UNWATCHED:
                        folders.append(entry.path)
                    continue
                info = os.stat(entry.path, follow_symlinks=False)
            except OSError:
                continue
            changed = 0 if os.name == "nt" else info.st_ctime_ns
            racy = max(info.st_mtime_ns, changed) >= now - _RACY_NS
            regular = stat.S_ISREG(info.st_mode)
            digest = _raw_digest(entry.path) if racy and regular else ""
            found[entry.path] = (info.st_size, info.st_mtime_ns, changed, digest)
            if len(found) > MAX_WATCHED:
                return None
    return found, now


def _raw_digest(path: str) -> str:
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as file:
            for chunk in iter(lambda: file.read(1 << 20), b""):
                digest.update(chunk)
    except OSError as exc:
        return f"<unreadable {type(exc).__name__}>"
    return digest.hexdigest()


def files_changed(before: tuple[Files, int] | None) -> str:
    """The files in the copy that changed since `before` (verifier round 11: what a function
    writes is not compared; that it wrote anything keeps L3 out of reach for it), "" if none.
    A file whose times are the same is unchanged unless its content was read and differs."""
    after = copy_files()
    if before is None or after is None:
        return f"more than {MAX_WATCHED} files in the copy: not checked"
    old, new = before[0], after[0]
    changed = [p for p in sorted(set(old) | set(new)) if not _same_file(p, old.get(p), new.get(p))]
    root = os.getcwd()
    names = [os.path.relpath(p, root).replace(os.sep, "/") for p in changed]
    return ", ".join(names[:5]) + (f" and {len(names) - 5} more" if len(names) > 5 else "")


def _same_file(path: str, was: FileKey | None, now: FileKey | None) -> bool:
    if was is None or now is None or was[:3] != now[:3]:
        return was is now
    return not was[3] or _raw_digest(path) == was[3]


def _call_and_report(
    target: Target, args: Mapping[str, object]
) -> tuple[Outcome, dict[str, str], dict[str, set[int]]]:
    """One call on fresh copies of the arguments: its outcome, its report (with a digest of the
    arguments as the call left them, so a changed in-place update counts: verifier S2), and the
    fixed lines it ran."""
    given = _copied(args)
    root = getattr(target.function, "__func__", target.function)  # a class method's function
    data_before, opaque_before = module_data(root, target.owner)
    outcome, ran, side = _watching_side(target, given)
    # By name: Hypothesis draws a dict in its own key order, the other side replays it in
    # parameter order, and the order must not look like a change. A method's object is an
    # argument too, as the call left it (M7.5); the code that built it is not compared.
    objects = [(RECEIVER, outcome.receiver)] if target.receivers is not None else []
    kept = [(name, given[name]) for name in sorted(given) if not (objects and name == RECEIVER)]
    after, opaque = snapshot([*objects, *kept])
    report = {**diff_report(outcome), "args": _digest(after), "args_text": after[:SHOWN_TEXT]}
    report["opaque"] = report["opaque"] or (f"the arguments: {opaque}" if opaque else "")
    side = _masked(side)
    report["side"] = _digest(side) if side else ""
    report["side_text"] = side[:SHOWN_TEXT]
    # What the call did to module data, place by place: only what it changed (a constant the
    # fix changed is a module-level change, reported on its own; a name only head reaches but
    # no call changes is nothing: round 10, B1).
    data, data_opaque = module_data(root, target.owner)
    changed = [
        f"{label}: {data_before.get(label, '<none>')} -> {data.get(label, '<none>')}"
        for label in sorted(set(data_before) | set(data))
        if data_before.get(label) != data.get(label)
    ]
    state = "\n".join(changed)
    report["state"] = _digest(state) if state else ""
    report["state_text"] = state[:SHOWN_TEXT]
    report["data_opaque"] = (data_opaque or opaque_before)[:200]  # a reason of its own (S2)
    return outcome, report, ran


def _without_state(report: Mapping[str, str]) -> dict[str, str]:
    return {k: v for k, v in report.items() if k not in ("state", "state_text")}


_FD_FILES: dict[int, Any] = {}


@contextlib.contextmanager
def _fd_capture() -> Iterator[dict[int, str]]:
    """What reaches file descriptors 1 and 2 during the call: through a stream a module kept
    from import time (`out=sys.stdout`), `sys.__stdout__`, or C code (verifier round 7, B8).
    Diff runs start pytest with `-s`, so those streams are the real ones."""
    captured: dict[int, str] = {}
    saved: dict[int, int] = {}
    _flush_streams()
    for fd in (1, 2):
        try:
            if fd not in _FD_FILES:
                _FD_FILES[fd] = tempfile.TemporaryFile()  # noqa: SIM115 (kept for the run)
            file = _FD_FILES[fd]
            file.seek(0)
            file.truncate()
            saved[fd] = os.dup(fd)
            os.dup2(file.fileno(), fd)
        except OSError:
            continue
    try:
        yield captured
    finally:
        _flush_streams()
        for fd, old in saved.items():
            os.dup2(old, fd)
            os.close(old)
            file = _FD_FILES[fd]
            file.seek(0)
            captured[fd] = file.read(MAX_PRINTED).decode("utf-8", "backslashreplace")


def _flush_streams() -> None:
    for stream in (sys.stdout, sys.stderr, sys.__stdout__, sys.__stderr__):
        with contextlib.suppress(Exception):
            if stream is not None:
                stream.flush()


def _stream() -> io.TextIOWrapper:
    """A text stream with a `.buffer`, like the real stdout and stderr (verifier round 5, S2: code
    writing bytes to `sys.stderr.buffer` must behave as in the project)."""
    return io.TextIOWrapper(io.BytesIO(), encoding="utf-8", errors="backslashreplace",
                            newline="", write_through=True)  # fmt: skip


def _written(stream: io.TextIOWrapper) -> str:
    stream.flush()
    buffer = stream.buffer
    assert isinstance(buffer, io.BytesIO)
    return buffer.getvalue().decode("utf-8", "backslashreplace")


def _watching_side(
    target: Target, given: Mapping[str, object]
) -> tuple[Outcome, dict[str, set[int]], str]:
    """One call, with what it wrote besides its result: stderr, warnings and every log record
    the loggers' levels let through, whatever handlers or `propagate` say (the record factory
    sees each one: verifier round 5, S3). Warning filters are left alone, so a warning the
    project turns into an error still raises. The times log handlers print for this call's
    records are masked: two calls of one input log at different times (round 8, S2)."""
    seen: list[str] = []
    records: list[logging.LogRecord] = []
    errors = _stream()

    def shown(
        message: Warning | str,
        category: type[Warning],
        filename: str,
        lineno: int,
        file: TextIO | None = None,
        line: str | None = None,
    ) -> None:
        seen.append(f"warning {category.__name__}: {message}")

    factory = logging.getLogRecordFactory()

    def recorded(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = factory(*args, **kwargs)
        # Every time and id a format can print is fixed (round 9, S1: `%(msecs)03d` and
        # `%(relativeCreated)d` were not masked; the process id differs between base and head).
        record.created, record.msecs, record.relativeCreated = _LOG_TIME, 0.0, 0.0
        record.thread, record.process = 0, 0
        records.append(record)
        try:
            seen.append(f"log {record.levelname} {record.name}: {record.getMessage()}")
        except Exception:  # a message that can't be formatted
            seen.append(f"log {record.levelname} {record.name}: <unprintable>")
        return record

    logging.setLogRecordFactory(recorded)
    try:
        with _fd_capture() as raw, warnings.catch_warnings(), contextlib.redirect_stderr(errors):
            warnings.showwarning = shown
            outcome, ran = target.call(given, copied=False, keep_before=False)
    finally:
        logging.setLogRecordFactory(factory)
    stamps = _stamps(records)
    written = _unstamped(_written(errors), stamps)
    if written:
        seen.append(f"stderr {written[:MAX_PRINTED]}")
    seen += [f"fd{fd} {_unstamped(text, stamps)}" for fd, text in sorted(raw.items()) if text]
    return outcome, ran, "\n".join(seen)


_LOG_TIME = 1_000_000_000.0  # the time every record shows (2001: no negative stamps on Windows)


def _stamps(records: Sequence[logging.LogRecord]) -> set[str]:
    """The times these records show, as any formatter the loggers' handlers use (or the
    default one) writes them."""
    formatters: list[logging.Formatter] = [logging.Formatter()]
    loggers = [logging.getLogger(), *logging.Logger.manager.loggerDict.values()]
    for logger in loggers:
        for handler in getattr(logger, "handlers", ()):
            if handler.formatter is not None:
                formatters.append(handler.formatter)
    stamps = set()
    for record in records:
        for formatter in formatters:
            with contextlib.suppress(Exception):
                stamps.add(formatter.formatTime(record, formatter.datefmt))
    return {stamp for stamp in stamps if len(stamp) >= 6}


def _unstamped(text: str, stamps: set[str]) -> str:
    for stamp in sorted(stamps, key=len, reverse=True):
        text = text.replace(stamp, "<log time>")
    return text


def diff_target(spec: Mapping[str, Any], plan: Mapping[str, Any], tracer: LineTracer | None,
                reporter: Reporter) -> None:  # fmt: skip
    """One target: its inputs (generated, or the ones given), then two calls per input."""
    tid = spec["id"]
    try:
        target = load_target(spec, tracer, fixed_lines(plan))
    except TargetError as exc:
        reporter.emit({"event": "target", "target": tid, "error": str(exc)[:MAX_TEXT]})
        return
    reporter.emit({"event": "target", "target": tid, "module": target.module_name,
                   "params": [p.name for p in _parameters(target)]})  # fmt: skip
    docs = _doc_properties(target, spec, reporter)
    if plan.get("generate") and "inputs" not in spec:
        examples = [
            {"kind": "example", "id": d["id"], "args": d["args"]} for d in spec.get("docs", [])
        ]
        items, stats = diff_inputs(
            target,
            {**spec, "properties": examples},
            int(plan.get("max_explicit", 200)),
            int(plan.get("draws", 200)),
        )
        reporter.emit({"event": "inputs", "target": tid, "count": len(items), **stats})
        for index, item in enumerate(items):
            args = {k: to_source(v) for k, v in item.args.items()}
            reporter.emit({"event": "input", "target": tid, "index": index,
                           "phase": item.phase, "args": args})  # fmt: skip
    else:
        items = []
        for given in spec.get("inputs", []):
            try:
                items.append(_Input(str(given.get("phase", "")), _decode_args(given["args"])))
            except ValueError:
                items.append(_Input("bad", {}))
    files = copy_files()  # the copy before this function's first call
    # A run that checks whether one input hangs calls only that input ("stop").
    stop = min(len(items), int(plan.get("stop", {}).get(tid, len(items))))
    for index in range(int(plan.get("start", {}).get(tid, 0)), stop):
        item = items[index]
        reporter.emit({"event": "calling", "target": tid, "index": index,
                       "input": input_key(item.args)[:MAX_CALLING_TEXT]})  # fmt: skip
        why = "not a plain literal" if item.phase == "bad" else None
        why = why or _unbindable(target, item.args)
        if why is not None:
            reporter.emit({"event": "outcome", "target": tid, "index": index, "unbindable": why})
            continue
        try:
            first, report, ran = _call_and_report(target, item.args)
            _, again, ran2 = _call_and_report(target, item.args)
        except Unbuilt as exc:
            reporter.emit({"event": "outcome", "target": tid, "index": index,
                           "unbuilt": exc.kind[:200]})  # fmt: skip
            continue
        reporter.emit(
            {
                "event": "outcome",
                "target": tid,
                "index": index,
                "outcome": report,
                # Module data may change from one call to the next by design (a counter, a
                # cache): it is compared across sides, call for call, not between the two calls.
                "stable": _without_state(report) == _without_state(again),
                "ran": bool(ran or ran2),
                "docs": _doc_verdicts(docs, item.args, first),
            }
        )
    reached = {path: sorted(lines) for path, lines in target.reached.items()}
    reporter.emit({"event": "end", "target": tid, "unit": "diff", "reached": reached,
                   "files_changed": files_changed(files)})  # fmt: skip


def _bound_names(plan: Mapping[str, Any], reporter: Reporter) -> None:
    """For each function the fix seems to add: does this copy's module have that name at all
    (bound by a loop over `globals()`, `setattr` on the module, ...: verifier round 5, S4)?"""
    for spec in plan.get("absent", []):
        try:
            module, _ = resolve(spec["path"], spec.get("module_candidates", []))
        except TargetError:
            continue
        owner = getattr(module, spec["owner"], None) if spec.get("owner") else module
        if owner is not None and hasattr(owner, spec["name"]):
            reporter.emit({"event": "bound", "path": spec["path"], "name": spec["name"]})


def run_diff(plan: Mapping[str, Any], reporter: Reporter) -> None:
    tracer = _tracer(plan)
    _bound_names(plan, reporter)
    try:
        for spec in plan.get("targets", []):
            try:
                diff_target(spec, plan, tracer, reporter)
            except Exception as exc:  # a bug here must not hide the other targets' results
                reporter.emit(
                    {
                        "event": "target_error",
                        "target": spec.get("id"),
                        "error": f"{type(exc).__name__}: {_safe_str(exc)}",
                    }
                )
    finally:
        if tracer is not None:
            tracer.close()


def main(plan_text: str) -> None:
    """Entry point of the generated test. Reports "start", then the mode's events, then "done"."""
    out = os.environ.get("TRACEFIX_OUT", "")
    if out:  # Hypothesis caches constants on disk: never in the copy under test
        os.environ["HYPOTHESIS_STORAGE_DIRECTORY"] = os.path.join(
            os.path.dirname(out), "hypothesis"
        )
    plan = json.loads(plan_text)
    reporter = Reporter()
    global _START_FILTERS
    _START_FILTERS = list(warnings.filters)  # before any target loads (judged_call, M11 S4)
    try:
        reporter.emit(
            {
                "event": "start",
                "version": VERSION,
                "mode": plan.get("mode"),
                "python": list(sys.version_info[:2]),
            }
        )
        if plan.get("mode") == "probe":
            run_probe(plan, reporter)
        elif plan.get("mode") == "diff":
            run_diff(plan, reporter)
        else:
            run_attack(plan, reporter)
        reporter.emit({"event": "done"})
    finally:
        reporter.close()


# --- coverage: a pytest plugin (loaded with -p only for fix-line coverage runs) -------------------

_SESSION: list[LineTracer] = []


if sys.version_info >= (3, 11):

    def _qualname(code: types.CodeType) -> str:
        return code.co_qualname

    def _positions(code: types.CodeType) -> list[Any]:
        return list(code.co_positions())

else:  # never used: the recorder runs on 3.11+ only (pytest_configure)

    def _qualname(code: types.CodeType) -> str:
        return code.co_name

    def _positions(code: types.CodeType) -> list[Any]:
        return []


class CallRecorder:
    """Which calls to some functions a test file made, by the call's exact place in that file
    (line and column span, from the calling instruction), and in which test (the behaviour
    diff's proof that a reproduction test's call really ran before the fix: verifier round 3)."""

    def __init__(self, spec: Mapping[str, Any]) -> None:
        root = os.getcwd()
        self.caller = _norm(os.path.join(root, *PurePosixPath(spec["file"]).parts))
        self.targets = {
            # A function's qualified name is its name; a method's is `Owner.name` (M7.5).
            (_norm(os.path.join(root, *PurePosixPath(t["path"]).parts)), t["name"])
            for t in spec["targets"]
        }
        self.test = ""
        self.seen: set[tuple[str, str, int, int, int, int]] = set()
        # Test node id (parameters included) -> the line of the test function where it failed:
        # only the check on that line failed before the fix (verifier round 4).
        self.failed: dict[str, int] = {}
        self._known: dict[types.CodeType, bool] = {}
        self._positions: dict[types.CodeType, list[Any]] = {}

    def failure(self, item: Any, call: Any) -> None:
        """Note where a test failed in its own function: the deepest frame of the test function
        in the failing traceback (present even when the crash was inside the code under test)."""
        excinfo = getattr(call, "excinfo", None)
        if excinfo is None or getattr(call, "when", "") != "call":
            return
        if getattr(excinfo, "typename", "") in ("Skipped", "XFailed", "Exit"):
            return
        name = str(getattr(item, "originalname", "") or getattr(item, "name", ""))
        tb, line = getattr(excinfo, "tb", None), None
        while tb is not None:
            code = tb.tb_frame.f_code
            if code.co_name == name and _norm(code.co_filename) == self.caller:
                line = tb.tb_lineno
            tb = tb.tb_next
        if line is not None:
            self.failed[str(getattr(item, "nodeid", ""))] = line

    def profile(self, frame: types.FrameType, event: str, _arg: object) -> None:
        if event != "call":
            return
        code = frame.f_code
        if code not in self._known:
            self._known[code] = (_norm(code.co_filename), _qualname(code)) in self.targets
        if not self._known[code]:
            return
        # Up to the nearest frame of the test file: through a decorator's wrapper too (round 5).
        # A call reached through some other function lands on that function's call in the test,
        # which doesn't name the target, so it explains nothing.
        caller = frame.f_back
        for _ in range(MAX_DEPTH):
            if caller is None or _norm(caller.f_code.co_filename) == self.caller:
                break
            caller = caller.f_back
        if caller is None or _norm(caller.f_code.co_filename) != self.caller:
            return  # not made from the test file
        positions = self._positions.setdefault(caller.f_code, _positions(caller.f_code))
        index = caller.f_lasti // 2
        if 0 <= index < len(positions) and None not in positions[index]:
            line, end_line, col, end_col = positions[index]
            self.seen.add((self.test, _qualname(code), line, end_line, col, end_col))


_CALLS: list[CallRecorder] = []


def pytest_runtest_setup(item: Any) -> None:
    if _CALLS:
        _CALLS[0].test = str(getattr(item, "nodeid", ""))


def pytest_runtest_makereport(item: Any, call: Any) -> None:
    if _CALLS:
        _CALLS[0].failure(item, call)


def pytest_configure(config: object) -> None:
    calls = os.environ.get("TRACEFIX_CALLS")
    # Calls are placed by line and column, which code objects give from 3.11 on; older ones
    # report no calls at all (the behaviour diff doesn't ask them: Tracefix's _ran_on_base).
    if calls and sys.version_info >= (3, 11):
        recorder = CallRecorder(json.loads(calls))
        _CALLS.append(recorder)
        sys.setprofile(recorder.profile)
    files = os.environ.get("TRACEFIX_TRACE")
    if not files:
        return
    tracer = LineTracer(
        {os.path.join(os.getcwd(), *PurePosixPath(rel).parts): rel for rel in json.loads(files)}
    )
    tracer.start()
    _SESSION.append(tracer)


def pytest_unconfigure(config: object) -> None:
    if _CALLS:
        sys.setprofile(None)
        recorder = _CALLS.pop()
        reporter = Reporter()
        try:
            calls = [list(c) for c in sorted(recorder.seen)]
            reporter.emit({"event": "calls", "calls": calls, "failed": recorder.failed})
        finally:
            reporter.close()
    if not _SESSION:
        return
    tracer = _SESSION.pop()
    tracer.close()
    reporter = Reporter()
    try:
        files = {rel: sorted(lines) for rel, lines in tracer.lines.items()}
        reporter.emit(
            {
                "event": "coverage",
                "traced": tracer.available and not tracer.disturbed,
                "reason": tracer.reason,
                "files": files,
            }
        )
    finally:
        reporter.close()

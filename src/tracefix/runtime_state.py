"""Reading the whole state of a value, and of the module data a function reaches (M7).

Part of Tracefix's in-run code: shipped beside attack_runtime into every run under a random
name (harness.runtime_modules), so it imports only the standard library, never tracefix.
Used by the behaviour diff: two outcomes compare equal only when nothing in them differs
(SPEC 2.5, "What is compared").
"""

from __future__ import annotations

import collections.abc
import decimal
import dis
import enum
import functools
import hashlib
import io
import logging
import os
import pkgutil
import re
import sys
import sysconfig
import types
import typing
from collections.abc import Callable, Iterable, Mapping
from typing import Any

# Type hints as values (a GenericAlias; `X | Y` is a types.UnionType from 3.10 on).
_HINT_TYPES = (types.GenericAlias, getattr(types, "UnionType", types.GenericAlias))

_ADDRESS = re.compile(r"\bat 0x[0-9a-fA-F]+>")  # "<object at 0x1f...>"; never data like 0xff


def _norm(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()[:32]


def _masked(text: str) -> str:
    """Object addresses and the copy's own folder masked: base and head live in different
    folders, so a repr built from `__file__` must not look like a change (verifier N2)."""
    for spelling in _copy_spellings(os.getcwd()):
        text = text.replace(spelling, "<copy>")
    return _ADDRESS.sub("at 0x?>", text)


@functools.cache
def _copy_spellings(root: str) -> tuple[str, ...]:
    """The ways the copy's folder can appear in text: as given and resolved, with either slash,
    and escaped as repr writes it. Longest first, so no part of one is replaced on its own."""
    found = set()
    for path in (root, os.path.realpath(root)):
        found |= {path, path.replace("\\", "/"), path.replace("\\", "\\\\")}
    return tuple(sorted(found, key=len, reverse=True))


# --- the snapshot: a value's whole state as text ---------------------------------------------

SNAPSHOT_NODES = 20_000  # values written per snapshot; past it, the outcome is opaque
SNAPSHOT_DEPTH = 200  # nesting (a linked list of 200 nodes); deeper, the outcome is opaque
_HEAP_TYPE = 1 << 9  # Py_TPFLAGS_HEAPTYPE: made at run time (by a class statement, or by C code)
_PLAIN = (type(None), bool, int, float, complex, str, bytes, bytearray)
_CONTAINERS = (dict, list, tuple, set, frozenset, collections.deque, collections.OrderedDict,
               collections.defaultdict)  # fmt: skip
# No state besides a __dict__ (datetime.tzinfo is an abstract base: its subclasses hold it).
_STATELESS = (object, typing.Generic, types.SimpleNamespace, __import__("datetime").tzinfo)
_C_DESCRIPTORS = (types.MethodDescriptorType, types.WrapperDescriptorType,
                  types.ClassMethodDescriptorType, types.BuiltinFunctionType,
                  types.GetSetDescriptorType, types.MemberDescriptorType)  # fmt: skip


def _lock_types() -> tuple[type, type]:
    import threading

    return type(threading.Lock()), type(threading.RLock())


# Locks are C objects: read by whether they are held (verifier round 8, B4). Event, Semaphore,
# Condition and Barrier are Python classes around them, read like any other.
_LOCK, _RLOCK = _lock_types()
_COUNT = re.compile(r"\bcount=(\d+)")


def _value_types() -> tuple[type, ...]:
    """Standard-library value types whose repr shows their whole value (their own attributes
    hold caches that come and go, so they are read by repr, not attribute by attribute)."""
    import datetime
    import fractions
    import ipaddress
    import pathlib
    import uuid
    import zoneinfo

    return (datetime.datetime, datetime.date, datetime.time, datetime.timedelta,
            datetime.timezone, zoneinfo.ZoneInfo, decimal.Decimal, fractions.Fraction, uuid.UUID,
            pathlib.PurePath, ipaddress.IPv4Address, ipaddress.IPv6Address,
            ipaddress.IPv4Network, ipaddress.IPv6Network, ipaddress.IPv4Interface,
            ipaddress.IPv6Interface, range, slice, re.Pattern)  # fmt: skip


_VALUES = _value_types()


class _Unset:
    def __repr__(self) -> str:
        return "<unset>"


_UNSET = _Unset()  # a slot never set, a name not bound (yet)


class _Budget(Exception):
    """The snapshot ran past SNAPSHOT_NODES: it stops at once (verifier round 7, S2)."""


def _builtin_error(base: type) -> bool:
    """A builtin exception class: its state is its args and its C fields, which are read."""
    return issubclass(base, BaseException) and base.__module__ == "builtins"


def _first(kind: type, among: tuple[type, ...]) -> type | None:
    """The first class of `kind`'s MRO that is one of `among`."""
    return next((base for base in kind.__mro__ if base in among), None)


def _known_c(base: type) -> bool:
    """A class built into Python whose whole state Tracefix reads (below)."""
    return (base in _STATELESS or base in _PLAIN or base in _CONTAINERS or base in _VALUES
            or _builtin_error(base))  # fmt: skip


@functools.cache
def _written_in_python(klass: type) -> bool:
    """A class whose instances keep all their state in their `__dict__` and the slots it
    declares: a class statement's class. Its own namespace holds no C methods or C fields, only
    Python functions, descriptors and its slot members. A C type made at run time (re.Match,
    functools.partial, array.array, every itertools and io type) is a heap type too, but has C
    methods there (verifier round 7, B2: "heap type" alone said nothing)."""
    if not klass.__flags__ & _HEAP_TYPE:
        return False
    own = vars(klass)
    slots = own.get("__slots__", ())
    declared = {slots} if isinstance(slots, str) else {str(s) for s in slots}
    declared |= {_mangled(klass, s) for s in declared}
    for name, item in own.items():
        if name in ("__dict__", "__weakref__") and isinstance(item, types.GetSetDescriptorType):
            continue
        if name in declared and isinstance(item, types.MemberDescriptorType):
            continue
        if isinstance(item, types.BuiltinFunctionType) and item.__self__ is not klass:
            continue  # a C function kept as a class attribute (`converter = time.localtime`)
        if name == "__dict__" or isinstance(item, _C_DESCRIPTORS):
            return False
    return True


def _mangled(klass: type, name: str) -> str:
    if not name.startswith("__") or name.endswith("__") or not klass.__name__.strip("_"):
        return name
    return f"_{klass.__name__.lstrip('_')}{name}"


def _readable(kind: type) -> str:
    """ "" if Tracefix reads every class of `kind` in full, else why not. Past a standard value
    type (a subclass of `date`), the rest of the MRO is that type's own."""
    for base in kind.__mro__:
        if base in _VALUES:
            return ""
        if not (_known_c(base) or _written_in_python(base)):
            return f"{_name(base)} keeps state Tracefix can't read"
    return ""


def _resolves(value: object) -> str | None:
    """`module.qualname` if that name leads back to this very object (a module-level function or
    class: code, which the diff compares by its source), else None (one made at run time)."""
    module = sys.modules.get(str(getattr(value, "__module__", "") or ""))
    qualname = getattr(value, "__qualname__", "")
    if module is None or not isinstance(qualname, str) or not qualname or "<" in qualname:
        return None
    found: object = module
    for part in qualname.split("."):
        found = getattr(found, part, _UNSET)
    return f"{module.__name__}.{qualname}" if found is value else None


@functools.cache
def _stdlib_names() -> frozenset[str]:
    """The standard library's top-level module names: sys.stdlib_module_names (3.10+), else
    (3.9) the built-in modules and those in the standard library's own folders."""
    names = getattr(sys, "stdlib_module_names", None)
    if names is not None:
        return frozenset(names)
    paths = sysconfig.get_paths()
    platstdlib = paths["platstdlib"]
    folders = [paths["stdlib"], platstdlib, os.path.join(platstdlib, "lib-dynload"),
               os.path.join(sys.base_prefix, "DLLs")]  # fmt: skip
    found = {info.name for info in pkgutil.iter_modules(folders)}
    return frozenset(found | set(sys.builtin_module_names))


def _stdlib(kind: type) -> bool:
    """A class of the standard library under its real name (a project or dependency class
    claiming a standard module's name doesn't count)."""
    module = sys.modules.get(kind.__module__)
    top = kind.__module__.partition(".")[0]
    return (
        module is not None
        and top in _stdlib_names()
        and not _local(module)
        and _resolves(kind) is not None
    )


class Snapshot:
    """A value's whole state as text, so two values compare equal only when nothing in them
    differs. Only what Tracefix provably understands is read (verifier round 7: an allowlist):
    - plain values by repr, standard-library value types by repr;
    - the builtin containers item by item (through the builtin's own methods, so a subclass
      can't hide items), with a deque's maxlen and a defaultdict's factory;
    - builtin exceptions by args, every C field, cause and context;
    - objects of classes written in Python by every attribute and slot, never by `__repr__`, and
      by their plain value or items if they subclass one;
    - functions, classes and modules by a name that leads back to them; a bound method by its
      function and its object; locks and loggers by kind.
    Anything else is opaque: the outcome can't be compared in full, so the input does not count
    as the same. A mutable object met again is written as a reference to its first place, so
    shared state and cycles show, and nothing is written twice."""

    def __init__(self, *, code_by_print: bool = False) -> None:
        self.nodes = 0
        self.opaque = ""
        # Module data may hold functions made at run time (a dispatch table of lambdas): there
        # they are written by their code, defaults and closure (round 8, S1); in a result they
        # stay opaque.
        self.code_by_print = code_by_print
        self._ids: dict[int, int] = {}
        self._path: set[int] = set()
        self._keep: list[object] = []  # keeps every numbered object alive: ids stay unique

    def text(self, value: object) -> str:
        try:
            return _masked(self._write(value, 0))
        except _Budget:
            return "..."
        except RecursionError:  # deep already where the call came from: deeper is not read
            self._hide("too deeply nested to compare in full")
            return "..."

    def _hide(self, why: str) -> str:
        self.opaque = self.opaque or why
        return "..."

    def _write(self, value: object, depth: int) -> str:
        self.nodes += 1
        if self.nodes > SNAPSHOT_NODES:
            self._hide("too large to compare in full")
            raise _Budget
        if depth > SNAPSHOT_DEPTH:
            return self._hide("too deeply nested to compare in full")
        kind = type(value)
        if kind in _PLAIN and kind is not bytearray:  # bytearray is mutable: numbered below
            return _plain_repr(value)
        if value is _UNSET:
            return "<unset>"
        if kind in _VALUES or (_first(kind, _VALUES) and _stdlib(kind)):
            return f"{_name(kind)}:{self._value(value, depth)}"
        named = self._by_name(value, kind, depth)
        if named is not None:
            return named
        key = id(value)
        if key in self._ids:
            where = "cycle> to" if key in self._path else "shared>"
            return f"<{where} #{self._ids[key]}"
        if not isinstance(
            value, (tuple, frozenset)
        ):  # immutable: whether it is shared can't matter
            self._ids[key] = len(self._ids) + 1
            self._keep.append(value)
        self._path.add(key)
        try:
            return self._object(value, kind, depth)
        finally:
            self._path.discard(key)

    def _value(self, value: Any, depth: int) -> str:
        """A standard value type by repr, except where the repr hides part of it (round 8, B3):
        a pattern's repr is cut at 200 characters, a slice holds any objects, a date or time
        with a project tzinfo shows only its address."""
        if isinstance(value, re.Pattern):
            return f"re.Pattern({value.pattern!r}, flags={value.flags})"
        if isinstance(value, slice):
            parts = self._each((value.start, value.stop, value.step), depth + 1)
            return f"slice({', '.join(parts)})"
        tz = getattr(value, "tzinfo", None)
        if tz is not None and type(tz) not in _VALUES and hasattr(value, "replace"):
            naive = _plain_repr(value.replace(tzinfo=None))
            return f"{naive} tzinfo={self._write(tz, depth + 1)}"
        return self._shown(_plain_repr(value))

    def _shown(self, text: str) -> str:
        """A value type's repr, unless it shows only an object's address (a zone read from an
        in-memory file: verifier round 9): then that part can't be compared."""
        if _ADDRESS.search(text):
            return self._hide("a value shows only an object's address")
        return text

    def _by_name(self, value: object, kind: type, depth: int) -> str | None:
        """Code, modules, typing objects, streams, locks, loggers and Enum members."""
        if isinstance(value, types.ModuleType):
            return f"<module {value.__name__}>"
        if kind.__module__ in ("typing", "typing_extensions") or isinstance(value, _HINT_TYPES):
            return f"<typing {_plain_repr(value)}>"  # a type hint: code (round 8, S1)
        if any(value is stream for stream in _std_streams()):
            return f"<stream {getattr(value, 'name', '?')}>"
        if isinstance(value, types.BuiltinFunctionType) and not isinstance(
            value.__self__, (types.ModuleType, type(None))
        ):
            return None  # a builtin method bound to an object: its object is state
        if isinstance(value, (types.MethodDescriptorType, types.WrapperDescriptorType,
                              types.ClassMethodDescriptorType)):  # fmt: skip
            owner = getattr(value, "__objclass__", None)
            name = getattr(value, "__name__", "")
            if isinstance(owner, type) and getattr(owner, name, None) is value:
                return f"<method {_name(owner)}.{name}>"
            return self._hide("a C method made at run time can't be compared")
        if (callable(value) and _wrapped(value) is not None and not _local(kind)
                and not _written_in_python(kind) and _resolves(value) is not None):  # fmt: skip
            # A C wrapper (an lru_cache) under its own name: code; its cache is not compared.
            return f"<function {_resolves(value)}>"
        if isinstance(value, (type, types.FunctionType, types.BuiltinFunctionType)):
            found = _resolves(value)
            if found is not None:
                return f"<{'class' if isinstance(value, type) else 'function'} {found}>"
            if self.code_by_print and isinstance(value, types.FunctionType):
                return self._printed(value, depth)
            return self._hide(f"a {kind.__name__} made at run time can't be compared")
        if kind is _LOCK:
            return f"<lock locked={value.locked()}>"  # type: ignore[attr-defined]
        if kind is _RLOCK:
            count = _COUNT.search(_plain_repr(value))
            owned = value._is_owned()  # type: ignore[attr-defined]
            return f"<rlock owned={owned} count={count.group(1) if count else '?'}>"
        if isinstance(value, logging.Logger) and _stdlib(kind):
            # What it logs is compared through the records; how it is set up, here.
            handlers = [f"{_name(type(h))}:{h.level}" for h in value.handlers]
            return (f"<logger {value.name} level={value.level} disabled={value.disabled} "
                    f"propagate={value.propagate} handlers={handlers}>")  # fmt: skip
        if isinstance(value, enum.Enum):
            extra = {k: v for k, v in vars(value).items() if not k.startswith("_")}
            more = f" {self._write(extra, depth + 1)}" if extra else ""
            return f"{_name(kind)}.{value.name}={self._write(value.value, depth + 1)}{more}"
        if _real_file(value):
            # An open file: which one, and how (what reaches stdout and stderr is compared as
            # output; a file written in the copy is the tamper watch's).
            name = getattr(value, "name", "?")
            mode = getattr(value, "mode", "?")
            return f"<file {name!r} mode={mode} closed={getattr(value, 'closed', '?')}>"
        if isinstance(value, types.MappingProxyType):
            return f"mappingproxy({self._write(dict(value), depth + 1)})"
        if isinstance(value, os._Environ):
            return f"os.environ({self._write(dict(value), depth + 1)})"
        return None

    def _printed(self, function: types.FunctionType, depth: int) -> str:
        """A function made at run time, by its code, defaults and closure."""
        cells = []
        for cell in function.__closure__ or ():
            try:
                cells.append(cell.cell_contents)
            except ValueError:
                cells.append(_UNSET)
        parts = self._each((function.__defaults__, function.__kwdefaults__, cells), depth + 1)
        code = _digest(_code_text(function.__code__))[:16]
        return f"<function {function.__qualname__} code={code} {'; '.join(parts)}>"

    def _object(self, value: Any, kind: type, depth: int) -> str:
        # Plain loops, no closures or generators: each nesting level costs few stack frames, so
        # SNAPSHOT_DEPTH levels fit in Python's recursion limit.
        d = depth + 1
        if isinstance(value, types.MethodType):
            return f"<method {self._write(value.__func__, d)} of {self._write(value.__self__, d)}>"
        if isinstance(value, types.BuiltinFunctionType):
            return f"<method {value.__qualname__} of {self._write(value.__self__, d)}>"
        if kind is functools.partial:
            inner = self._each((value.func, value.args, value.keywords), d)
            return f"functools.partial({', '.join(inner)})"
        if kind is bytearray:
            return _plain_repr(value)
        if kind is memoryview:
            try:
                return f"memoryview({value.format}, {value.shape}, {value.tobytes()!r})"
            except ValueError:
                return self._hide("a released memoryview")
        why = _readable(kind)
        if why:
            return self._hide(why)
        parts = self._items(value, kind, d)
        plain = _first(kind, _PLAIN)
        if plain is not None:
            parts.append(_plain_repr(_plain_value(value, plain)))  # a subclass's plain value
        base = _first(kind, _VALUES)
        if base is not None:  # a subclass's value, read as the base's own (round 9, B1)
            plain_base = _as_base(value, base)
            text = (
                self._shown(_base_repr(value, base))
                if plain_base is None
                else self._value(plain_base, d)
            )
            parts.append(f"{_name(base)}:{text}")
        pairs: list[tuple[str, object]] = []
        if isinstance(value, BaseException):
            pairs.append(("args", vars(BaseException)["args"].__get__(value)))
            pairs += sorted(_error_fields(value).items())
        pairs += sorted(((str(k), v) for k, v in _state(value).items()), key=lambda kv: kv[0])
        if pairs:
            texts = self._each([v for _, v in pairs], d)
            parts.append(", ".join(f"{k}={t}" for (k, _), t in zip(pairs, texts)))
        return f"{_name(kind)}({'; '.join(parts)})"

    def _each(self, values: Iterable[object], depth: int) -> list[str]:
        texts = []
        for item in values:
            texts.append(self._write(item, depth))
        return texts

    def _items(self, value: Any, kind: type, depth: int) -> list[str]:
        """A container's items, read through the builtin's own methods (a subclass's
        `__iter__` or `items` can't hide one)."""
        container: Any = _first(kind, _CONTAINERS)
        if container is None:
            return []
        if issubclass(container, dict):
            flat: list[object] = []
            for k, v in container.items(value):
                flat += (k, v)
            texts = self._each(flat, depth)
            pairs = (f"{texts[i]}: {texts[i + 1]}" for i in range(0, len(texts), 2))
            parts = ["{" + ", ".join(pairs) + "}"]
            if issubclass(container, collections.defaultdict):
                factory = vars(collections.defaultdict)["default_factory"].__get__(value)
                parts.append(f"default_factory={self._write(factory, depth)}")
            return parts
        items = list(container.__iter__(value))
        if issubclass(container, (set, frozenset)):
            items.sort(key=_alone)  # an order of its own, so numbering doesn't follow hashing
            return ["{" + ", ".join(self._each(items, depth)) + "}"]
        parts = ["[" + ", ".join(self._each(items, depth)) + "]"]
        if container is collections.deque:
            maxlen = vars(collections.deque)["maxlen"].__get__(value)
            parts.append(f"maxlen={maxlen}")
        return parts


def _real_file(value: object) -> bool:
    """A standard file object over an OS file (not an in-memory buffer: its content is state)."""
    layer = value
    for _ in range(3):
        if type(layer) is io.FileIO:
            return True
        if type(layer) not in (io.TextIOWrapper, io.BufferedReader, io.BufferedWriter,
                               io.BufferedRandom):  # fmt: skip
            return False
        layer = getattr(layer, "buffer", None) or getattr(layer, "raw", None)
    return False


def _std_streams() -> tuple[object, ...]:
    return (sys.stdin, sys.stdout, sys.stderr, sys.__stdin__, sys.__stdout__, sys.__stderr__)


def _code_text(code: types.CodeType) -> str:
    """A code object as text: its bytecode, names and constants (nested code too)."""
    consts = []
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            consts.append(_code_text(const))
        elif isinstance(const, frozenset):
            consts.append(repr(sorted(map(repr, const))))
        else:
            consts.append(repr(const))
    return f"{code.co_code.hex()}|{code.co_names}|{code.co_varnames}|{consts}"


def _alone(value: object) -> str:
    """A value's snapshot on its own (how a set's items are put in order)."""
    return Snapshot().text(value)


def _plain_value(value: Any, plain: Any) -> object:
    """A subclass's plain value, read by the builtin itself (its `__str__` or `__int__` can't
    hide it: verifier round 7, B5)."""
    if plain in (str, bytes, bytearray):
        return plain.__getitem__(value, slice(None))
    if plain is int:
        return int.__int__(value)
    if plain is float:
        return float.__float__(value)
    if plain is complex:
        return (
            complex(value.real, value.imag)
            if type(value) is complex
            else complex(vars(complex)["real"].__get__(value), vars(complex)["imag"].__get__(value))
        )
    return value


_TIME = ("hour", "minute", "second", "microsecond", "tzinfo", "fold")
_DATE_FIELDS = {
    "date": ("year", "month", "day"),
    "datetime": ("year", "month", "day", *_TIME),
    "time": _TIME,
    "timedelta": ("days", "seconds", "microseconds"),
}


def _as_base(value: object, base: Any) -> object | None:
    """A subclass of a `datetime` type as the plain base value, its fields read through the
    base's own descriptors (a property of the subclass can't hide one), or None for other bases
    (read by the base's repr). A date's repr shows a project tzinfo only by address (round 9, B1),
    so the tzinfo is read in full this way."""
    fields = _DATE_FIELDS.get(base.__name__) if base.__module__ == "datetime" else None
    if fields is None:
        return None
    read = {}
    for name in fields:
        owner = next(k for k in base.__mro__ if name in vars(k))
        read[name] = vars(owner)[name].__get__(value)
    try:
        made: object = base(**read)
        return made
    except (TypeError, ValueError):
        return None


def _base_repr(value: object, base: Any) -> str:
    try:
        return str(base.__repr__(value))
    except Exception as exc:
        return f"<unprintable {type(exc).__name__}>"


def _error_fields(error: BaseException) -> dict[str, object]:
    """A builtin exception's C fields besides args and the traceback (`name`, `path`,
    `filename`, `errno`, `obj`...), with its cause and context (verifier round 7)."""
    fields: dict[str, object] = {}
    for klass in type(error).__mro__:
        if not _builtin_error(klass):
            continue
        for name, item in vars(klass).items():
            if name in ("args", "__traceback__", "__dict__") or name in fields:
                continue
            if isinstance(item, (types.GetSetDescriptorType, types.MemberDescriptorType)):
                try:
                    fields[name] = item.__get__(error, type(error))
                except AttributeError:
                    fields[name] = _UNSET
    return fields


def _name(kind: type) -> str:
    return f"{kind.__module__}.{kind.__qualname__}"


def _state(value: object) -> dict[str, object]:
    """An object's attributes: its `__dict__`, and every slot of its Python classes, read
    through the slot's own member (a property of the same name, `__getattr__` or name mangling
    can't hide one: verifier round 7, B5)."""
    state: dict[str, object] = {}
    try:
        own = object.__getattribute__(value, "__dict__")
    except AttributeError:
        own = None
    if isinstance(own, dict):
        state.update(dict.items(own))
    for klass in type(value).__mro__:
        if not _written_in_python(klass):
            continue
        for name, item in vars(klass).items():
            if isinstance(item, types.MemberDescriptorType):
                try:
                    state[f"{klass.__qualname__}.{name}"] = item.__get__(value, type(value))
                except AttributeError:
                    state[f"{klass.__qualname__}.{name}"] = _UNSET
    return state


def snapshot(value: object) -> tuple[str, str]:
    """(the value's whole state as text, why it is opaque or "")."""
    shot = Snapshot()
    text = shot.text(value)
    return text, shot.opaque


def _plain_repr(value: object) -> str:
    try:
        return repr(value)
    except ValueError:
        if type(value) is int:
            return f"int:{value:x}"
        return f"<unprintable {type(value).__name__}>"
    except Exception as exc:
        return f"<unprintable {type(value).__name__}: {type(exc).__name__}>"


# --- module data: the places a function's code can reach -------------------------------------


if sys.version_info >= (3, 11):

    def _defined_as(func: types.FunctionType) -> str:
        """The qualified name a function's code was defined with (`functools.wraps` changes
        the function's __qualname__, never its code's)."""
        return func.__code__.co_qualname

else:

    def _defined_as(func: types.FunctionType) -> str:
        """Before 3.11 code has no qualified name: the function's own __qualname__ while it
        still names that code, else the code's plain name (a `functools.wraps` wrapper reads
        `wrapper` here, `deco.<locals>.wrapper` on 3.11+). Base and head always run on one
        Python, so their labels still match."""
        qualname = func.__qualname__
        own = qualname.rpartition(".")[2] == func.__code__.co_name
        return qualname if own else func.__code__.co_name


def _code_objects(code: types.CodeType) -> list[types.CodeType]:
    found, stack = [], [code]
    while stack:
        current = stack.pop()
        found.append(current)
        stack += [c for c in current.co_consts if isinstance(c, types.CodeType)]
    return found


def _local(item: object) -> bool:
    """Code, a module or a class from the copy under test (not the standard library or a
    dependency)."""
    if isinstance(item, type):
        module = sys.modules.get(item.__module__)
        return module is not None and _local(module)
    code = getattr(item, "__code__", None)
    path = code.co_filename if isinstance(code, types.CodeType) else getattr(item, "__file__", None)
    return isinstance(path, str) and _norm(path).startswith(_norm(os.getcwd()) + os.sep)


Getter = Callable[[], object]
_DYNAMIC = frozenset({"globals", "vars", "setattr", "delattr", "__dict__"})
_PLACES: dict[tuple[int, int], tuple[object, object, dict[str, Getter], list[str]]] = {}


def module_data(function: object, owner: type | None = None) -> tuple[dict[str, str], str]:
    """A snapshot of the data the function's code can reach (verifier rounds 7 and 8):
    - every global its code names, and the globals of the project's own functions it calls, in
      any module (helpers, methods of the project's classes, through decorators and partials);
    - every data attribute of the project's classes it reaches (named, or the class of a value
      it reaches; along the MRO): class-level caches and registries written through self or cls;
    - each reached function's closure cells, defaults and attributes, at every layer of its
      decorators (`__wrapped__`), with a decorator object's own state (round 9, B2);
    - the project's functions, methods, partials and classes kept in data it reaches (a dispatch
      table, a registry: round 9, B3);
    - attributes it names of a project module;
    - data of any kind (an immutable value can be rebound), and a name it binds with `global`
      that doesn't exist yet; the module's whole namespace if the code uses `globals`, `vars`,
      `setattr` or `delattr` (it may bind any name there).
    Functions, classes and modules are code (the diff compares code by its source). Once over
    the budget, it stays opaque for the run (it is read before and after every call). For a
    method, its class (`owner`) is reached too, whether its code names it or not: data kept on
    the class through `self` or `cls` (M7.5). Returns each place's snapshot by label, and why
    one is opaque ("" if none)."""
    key = (id(function), id(owner))
    known = _PLACES.get(key)
    if known is None or known[0] is not function or known[1] is not owner:
        walk = _Walk(function, owner)
        known = _PLACES[key] = (function, owner, walk.places, walk.incomplete)
    places, too_large = known[2], known[3]
    if too_large:
        return {}, too_large[0]
    texts: dict[str, str] = {}
    opaque, used = "", 0
    # Each place on its own (round 10, B1: one text for all of them made a name only head
    # reaches look like a change of the rest), under one budget for them all.
    for label, get in sorted(places.items()):
        shot = Snapshot(code_by_print=True)
        shot.nodes = used
        texts[label] = shot.text(get())
        used = shot.nodes
        opaque = opaque or (f"{label}: {shot.opaque}" if shot.opaque else "")
        if shot.opaque.startswith("too large"):
            too_large.append(shot.opaque)
            break
    return texts, opaque


def _cell(cell: Any) -> Getter:
    def get() -> object:
        try:
            return cell.cell_contents
        except ValueError:  # an empty cell
            return _UNSET

    return get


def _entry(space: Mapping[str, object], name: str) -> Getter:
    return lambda: space.get(name, _UNSET)


def _code(value: object) -> bool:
    """Code, not data: functions, classes, modules, C functions, properties and the like."""
    return isinstance(value, (types.FunctionType, type, types.ModuleType, property,
                              staticmethod, classmethod, types.BuiltinFunctionType,
                              types.MethodDescriptorType, types.WrapperDescriptorType,
                              types.MemberDescriptorType, types.GetSetDescriptorType))  # fmt: skip


class _Walk:
    """The places module data lives in, found by walking the code from the target."""

    def __init__(self, function: object, owner: type | None = None) -> None:
        self.places: dict[str, Getter] = {}
        self.todo: list[object] = [function]
        self.seen: set[int] = set()
        self.keep: list[object] = []  # every walked object stays alive: ids in `seen` stay unique
        self.classes: set[int] = set()
        self.labels: dict[str, int] = {}
        self.incomplete: list[str] = []  # why some code may not have been walked
        if owner is not None:  # a method's class, reached through `self` or `cls` (M7.5)
            self._class(owner)
        while self.todo:
            for layer in _layers(self.todo.pop()):
                self._layer(layer)

    def _layer(self, item: object) -> None:
        """One layer of a callable: a project function's own data and the names it uses, or a
        project object's state and class (a decorator class: round 9, B2). A C wrapper (an
        lru_cache) is code; the function under it is the next layer."""
        if id(item) in self.seen:
            return
        self.seen.add(id(item))
        self.keep.append(item)
        if isinstance(item, types.FunctionType):
            self._function(item)
        elif not _code(item) and _local(type(item)):
            self.places.setdefault(self._label(f"<object {_name(type(item))}>"), lambda: item)
            self._class(type(item))

    def _label(self, where: str) -> str:
        """`where`, numbered when used before (two wrappers made by one decorator share a name)."""
        count = self.labels.get(where, 0)
        self.labels[where] = count + 1
        return where if count == 0 else f"{where}#{count + 1}"

    def _function(self, current: types.FunctionType) -> None:
        code = current.__code__
        space = current.__globals__
        if not isinstance(space, dict) or not _local(current):
            return
        codes = _code_objects(code)
        names = {n for c in codes for n in c.co_names}
        module = str(space.get("__name__", "?"))
        # Named by what it is (`functools.wraps` gives each wrapper the name of what it wraps)
        # and by its code, so a label doesn't depend on the order of the walk (round 10, B1).
        # A wrapper without `functools.wraps` is named by the module-level name bound to it
        # (`memo.double`): two wrappers from one decorator share their qualname.
        bound = sorted(k for k, v in space.items() if v is current)
        name = bound[0] if bound else current.__qualname__
        defined = _defined_as(current)
        if name != defined:
            name = f"{name}<{defined}>"
        where = self._label(f"{module}.{name}")
        for c in codes:
            for ins in dis.get_instructions(c):
                if ins.opname in ("STORE_GLOBAL", "DELETE_GLOBAL"):
                    self.places.setdefault(f"{module}.{ins.argval}", _entry(space, ins.argval))
        if names & _DYNAMIC:  # it may bind any name of its module: all of them count
            self.places.setdefault(f"{module}.*", lambda: _namespace_data(space))
        # Its own data (round 8, B2): closure cells (code in them is walked), defaults, attributes.
        for var, cell in zip(code.co_freevars, current.__closure__ or ()):
            if not self._reach(_cell(cell)()):
                self.places.setdefault(f"{where}.<closure {var}>", _cell(cell))
        func = current
        self.places.setdefault(f"{where}.__defaults__", lambda: func.__defaults__)
        self.places.setdefault(f"{where}.__kwdefaults__", lambda: func.__kwdefaults__)
        self.places.setdefault(f"{where}.__dict__", lambda: _namespace_data(vars(func)))
        for value in (*(func.__defaults__ or ()), *(func.__kwdefaults__ or {}).values()):
            self._reach(value)
        visited: set[int] = set()
        for name in sorted(n for n in names if n in space):
            self._name(f"{module}.{name}", space, name, names, visited)

    def _name(self, label: str, space: Mapping[str, object], name: str, names: set[str],
              visited: set[int]) -> None:  # fmt: skip
        """One name the code uses: a project module to look inside, code to walk into, or data
        to keep (and to look through for code)."""
        value = space[name]
        if isinstance(value, types.ModuleType):
            if id(value) in visited or not _local(value):
                return
            visited.add(id(value))
            inner = vars(value)
            for attr in sorted(n for n in names if n in inner):
                self._name(f"{label}.{attr}", inner, attr, names, visited)
            return
        if not self._reach(value):
            self.places.setdefault(label, _entry(space, name))

    def _reach(self, value: object) -> bool:
        """Walk the code `value` is or holds; True if it is only code (nothing to compare)."""
        if isinstance(value, (staticmethod, classmethod)):
            value = value.__func__
        if isinstance(value, types.FunctionType):
            self.todo.append(value)
            return True
        if isinstance(value, type):
            self._class(value)
            return True
        if isinstance(value, types.BuiltinFunctionType):
            if isinstance(value.__self__, (types.ModuleType, type(None))):
                return True  # a C function: code
        elif callable(value) and _wrapped(value) is not None and not _local(type(value)):
            self.todo.append(value)  # a C wrapper (lru_cache): the function under it is walked
            return True
        elif _code(value):
            return True
        self._scan(value)
        return False

    def _scan(self, value: object) -> None:
        """Code kept in data (round 9, B3): the project's functions, methods, partials and
        classes inside builtin containers and project objects are walked too."""
        stack, met = [value], set()
        while stack:
            item = stack.pop()
            if id(item) in met or type(item) in _PLAIN:
                continue
            met.add(id(item))
            if len(met) > SNAPSHOT_NODES:
                self.incomplete[:] = ["too much data to look through for code"]
                return
            kind = type(item)
            if isinstance(item, (types.FunctionType, type, staticmethod, classmethod)) or (
                callable(item) and _wrapped(item) is not None and not _local(kind)
            ):
                self._reach(item)
            elif isinstance(item, types.MethodType):
                stack += [item.__func__, item.__self__]
            elif isinstance(item, types.BuiltinFunctionType):
                stack.append(item.__self__)
            elif isinstance(item, functools.partial):
                stack += [item.func, *item.args, *item.keywords.values()]
            else:
                stack += _contents(item, kind)

    def _class(self, klass: type) -> None:
        """A project class reached: its methods are walked, and every data attribute it and
        its project bases hold is a place (class-level caches and registries: round 8, B2)."""
        for base in klass.__mro__:
            if id(base) in self.classes or not _local(base) or issubclass(base, enum.Enum):
                continue
            self.classes.add(id(base))
            label = self._label(f"{base.__module__}.{base.__qualname__}")  # factory classes
            space = vars(base)
            for attr, item in sorted(space.items()):
                if (attr.startswith("__") and attr != "__call__") or attr.startswith("_abc_"):
                    continue
                if isinstance(item, property):
                    self.todo += [f for f in (item.fget, item.fset, item.fdel) if f is not None]
                elif not self._reach(item):
                    self.places.setdefault(f"{label}.{attr}", _entry(space, attr))


def _layers(item: object) -> list[object]:
    """A callable and every layer under it through `__wrapped__` (each decorator's wrapper may
    keep state of its own: round 9, B2)."""
    found: list[object] = []
    ids: set[int] = set()
    current: object | None = item
    while current is not None and id(current) not in ids and len(found) < 100:
        found.append(current)
        ids.add(id(current))
        current = _wrapped(current)
    return found


def _wrapped(item: object) -> object | None:
    try:
        return getattr(item, "__wrapped__", None)
    except Exception:  # a project __getattr__ that raises
        return None


def _contents(item: object, kind: type) -> list[object]:
    """What a builtin container or a project object holds (to look through for code)."""
    found: list[object] = []
    container: Any = _first(kind, _CONTAINERS)
    if container is not None and issubclass(container, dict):
        for k, v in container.items(item):
            found += (k, v)
    elif container is not None:
        found += list(container.__iter__(item))
    if _local(kind):
        found += list(_state(item).values())
    return found


def _namespace_data(space: Mapping[str, object]) -> dict[str, object]:
    """A namespace's entries, without its dunders (the module's own bookkeeping)."""
    return {k: v for k, v in sorted(space.items()) if not k.startswith("__")}

"""Break My Fix's rules (SPEC 2.6, Decided in M6), all pure: no run, no model.

- hygiene: which proposed properties, strategies and examples count. Their expressions are only
  ever checked here as syntax trees; they run nowhere but inside the sandboxed runs;
- the quote check (developer, 6 Oct 2026): a property quotes, word for word, the text it rests on;
- literal inputs: only plain literals ever go into a repro file a user may run;
- dedupe, and the representative input of each finding;
- the standalone repro file, and the failure it must end with;
- the runtime's out file, read as untrusted data.
"""

import ast
import builtins
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Literal

from tracefix.attack_inputs import Args, AttackTarget, DocExample, Source
from tracefix.attack_methods import AFTER, RECEIVER
from tracefix.attack_runtime import from_source, to_source
from tracefix.prompts.adversary import ExampleProposal, PropertyProposal, StrategyProposal
from tracefix.repro import FORBIDDEN_NAMES

MAX_EXPRESSION = 400
MAX_STRATEGY = 300
MAX_PATTERN = 200  # a regular expression in a strategy
MAX_CLAIM = 300
MIN_QUOTE = 12  # characters, after collapsing whitespace
MAX_EXPONENT = 64
# A repro file's line for a finding behind a warning (M11 S4): the project's "error" filters off.
DROP_ERROR_FILTERS = '_warnings.filters[:] = [f for f in _warnings.filters if f[0] != "error"]'
MAX_POWERS = 2
# Dropped around a quote: straight quote marks and backticks, and the curly ones (by code point).
QUOTE_MARKS = "\"'` " + "".join(map(chr, (0x201C, 0x201D, 0x2018, 0x2019)))
MAX_PROPERTIES_PER_TARGET = 8
MAX_EXAMPLES_PER_TARGET = 20
MAX_GENERATORS = 2
MAX_OTHER_INPUTS = 3
MAX_EVENT_LINE = 100_000
SAFE_BUILTINS = frozenset(
    {
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
    }
)
BUILTIN_EXCEPTIONS = frozenset(
    name
    for name, value in vars(builtins).items()
    if isinstance(value, type) and issubclass(value, BaseException)
)
# Attribute names that lead out of an expression to the process, the interpreter or the file
# system (verifier round 2: `calendar.sys.modules` reached `os` and the run's report file). The
# runtime also hides modules, so this is the second layer. (`compile` stays: `re.compile`.)
ESCAPE_NAMES = frozenset(
    {
        "sys",
        "os",
        "io",
        "builtins",
        "importlib",
        "subprocess",
        "shutil",
        "pathlib",
        "socket",
        "modules",
        "environ",
        "open",
        "exit",
        "exec",
        "eval",
        "globals",
        "locals",
        "vars",
        "getattr",
        "setattr",
        "delattr",
        "write",
        "write_text",
        "write_bytes",
        "unlink",
        "rmdir",
        "rename",
        "get_field",
        "format_field",
    }
)
# Frame, generator, coroutine, traceback and code attributes (`gi_frame.f_globals`...): the way
# from any generator back to a module's globals (verifier round 3).
ESCAPE_PREFIXES = ("gi_", "f_", "tb_", "cr_", "ag_", "co_")
STDLIB_MODULES = (
    "calendar",
    "cmath",
    "datetime",
    "decimal",
    "fractions",
    "math",
    "re",
    "statistics",
    "string",
    "unicodedata",
)
STRATEGY_FUNCTIONS = frozenset(
    {
        "binary",
        "booleans",
        "characters",
        "decimals",
        "dictionaries",
        "floats",
        "fractions",
        "from_regex",
        "frozensets",
        "integers",
        "just",
        "lists",
        "none",
        "one_of",
        "sampled_from",
        "sets",
        "text",
        "tuples",
    }
)
RESERVED = frozenset({"result", "result2", "st", "pytest"})
_ALLOWED: tuple[type[ast.AST], ...] = (
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Pow,  # only with a small constant exponent (checked below)
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.BitAnd,
    ast.BitOr,
    ast.BitXor,
    ast.RShift,
    ast.UnaryOp,
    ast.Not,
    ast.USub,
    ast.UAdd,
    ast.Invert,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Is,
    ast.IsNot,
    ast.In,
    ast.NotIn,
    ast.IfExp,
    ast.Call,
    ast.keyword,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Attribute,
    ast.Constant,
    ast.Subscript,
    ast.Slice,
    ast.Tuple,
    ast.List,
    ast.Dict,
    ast.Set,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.comprehension,
)
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)

PropertyKind = Literal["returns", "raises", "raises_only", "relation", "example"]


@dataclass(frozen=True)
class CheckedProperty:
    """A property that passed hygiene and the quote check (or a docstring example). Whether the
    project's tests contradict it is decided later, by a run."""

    id: str  # unique in the stage, e.g. "t1.p2" or "t1.doc1"
    target: str
    kind: PropertyKind
    name: str
    claim: str
    source: str
    quote: str
    when: str = ""
    check: str = ""
    expected: str = ""
    exceptions: tuple[str, ...] = ()
    transform: str = ""
    names: tuple[str, ...] = ()  # module names its expressions use
    stdlib: tuple[str, ...] = ()  # standard-library modules its expressions use
    example_args: Args = ()
    example_expected: str = ""
    compare: Literal["eq", "repr", "raises"] = "eq"
    origin: Literal["model", "docstring"] = "model"

    @property
    def constrains_result(self) -> bool:
        """It says something about the result (or the raise), not only "no other exception"
        (NOTES Q27: a property like that is too weak to make "nothing found" mean much)."""
        return self.kind != "raises_only" or bool(self.check)

    def spec(self) -> dict[str, Any]:
        """What the runtime gets."""
        if self.kind == "example":
            return {
                "id": self.id,
                "kind": "example",
                "args": dict(self.example_args),
                "example_expected": self.example_expected,
                "compare": self.compare,
            }
        return {
            "id": self.id,
            "kind": self.kind,
            "when": self.when,
            "check": self.check,
            "expected": self.expected,
            "transform": self.transform,
            "exceptions": list(self.exceptions),
            "names": list(self.names),
            "stdlib": list(self.stdlib),
            "huge_ok": speaks_of_large_values(self.quote),
        }


# Words in a property's quote that make huge inputs part of its promise (developer, 6 Oct 2026:
# otherwise a raise on a huge boundary value is a report-only note, not a finding).
LARGE_WORDS = re.compile(
    r"\b(large|larger|largest|huge|big|bigger|overflow\w*|arbitrar\w*|any size|unbounded|"
    r"very long|long input|any length|any integer|limit\w*|maximum|max)\b",
    re.IGNORECASE,
)


def speaks_of_large_values(quote: str) -> bool:
    return bool(LARGE_WORDS.search(quote))


# --- the quote check ------------------------------------------------------------------------------


def collapse(text: str) -> str:
    return " ".join(text.split())


def quote_found(quote: str, texts: Iterable[str]) -> bool:
    """The quote, with whitespace collapsed and surrounding quote marks dropped, is at least
    MIN_QUOTE characters long and appears exactly in one of the texts (whitespace collapsed)."""
    wanted = collapse(quote).strip(QUOTE_MARKS)
    if len(wanted) < MIN_QUOTE:
        return False
    return any(wanted in collapse(text) for text in texts if text)


# --- expressions ----------------------------------------------------------------------------------


def shadowed_stdlib(paths: Iterable[str]) -> frozenset[str]:
    """Standard-library module names a repo file could stand in for: a `name.py` or `name/` whose
    folder is not a package (so it may sit at the top of the import path)."""
    paths = list(paths)
    packages = {
        str(PurePosixPath(p).parent) for p in paths if PurePosixPath(p).name == "__init__.py"
    }
    found = set()
    for path in paths:
        parts = PurePosixPath(path).parts
        for depth, part in enumerate(parts):
            name = part.removesuffix(".py") if depth == len(parts) - 1 else part
            if name not in STDLIB_MODULES:
                continue
            parent = str(PurePosixPath(*parts[:depth])) if depth else "."
            if parent not in packages:
                found.add(name)
    return frozenset(found)


def expression_names(
    text: str, what: str, allowed: frozenset[str], target: str, method: str = ""
) -> set[str]:
    """The free names a hygiene-checked expression uses; ValueError with the reason if it breaks a
    rule: only plain expression syntax (no lambda, walrus, f-string, `**`, `<<`...), at most two
    generators per comprehension, no attribute starting with "_", no name that could fake or
    reach a result, only `allowed` names, and never the function under test itself (for a
    `method`, no attribute of that name on anything)."""
    if len(text) > MAX_EXPRESSION:
        raise ValueError(f"{what} is longer than {MAX_EXPRESSION} characters")
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except (SyntaxError, ValueError, RecursionError):
        raise ValueError(f"{what} is not a Python expression") from None
    local: set[str] = set()
    powers = 0
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ValueError(f"{what} uses {type(node).__name__}, which is not allowed")
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            # `10**24`, `1024**2 - 1` (real-bug trial), never a number too big to build.
            powers += 1
            exponent = node.right
            if (
                powers > MAX_POWERS
                or not isinstance(exponent, ast.Constant)
                or type(exponent.value) is not int
                or not 0 <= exponent.value <= MAX_EXPONENT
            ):
                raise ValueError(
                    f"{what} uses `**` other than with a constant exponent from 0 to "
                    f"{MAX_EXPONENT} (at most {MAX_POWERS} times)"
                )
        if isinstance(node, _COMPREHENSIONS) and len(node.generators) > MAX_GENERATORS:
            raise ValueError(f"{what} has a comprehension with more than {MAX_GENERATORS} loops")
        if isinstance(node, ast.comprehension):
            if node.is_async:
                raise ValueError(f"{what} uses an async comprehension")
            local |= {n.id for n in ast.walk(node.target) if isinstance(n, ast.Name)}
        if isinstance(node, ast.Attribute) and (
            node.attr.startswith(("_", *ESCAPE_PREFIXES))
            or node.attr in FORBIDDEN_NAMES
            or node.attr in ESCAPE_NAMES
        ):
            raise ValueError(f"{what} uses the attribute {node.attr}, which is not allowed")
        if method and isinstance(node, ast.Attribute) and node.attr == method:
            raise ValueError(f"{what} calls {method} itself: the verifier makes that call")
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and ("junit" in node.value.lower())
        ):
            raise ValueError(f"{what} mentions junit")
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    free = used - local
    if target in free:
        raise ValueError(f"{what} calls {target} itself: the verifier makes that call")
    bad = sorted(free & FORBIDDEN_NAMES) or sorted(free - allowed)
    if bad:
        raise ValueError(f"{what} uses names that are not available: {', '.join(bad)}")
    return free


def _constant(text: str) -> object:
    """The value of an expression that is only a constant, or a marker if it isn't one."""
    try:
        node = ast.parse(text.strip(), mode="eval").body
    except (SyntaxError, ValueError, RecursionError):
        return _NOT_CONSTANT
    return node.value if isinstance(node, ast.Constant) else _NOT_CONSTANT


_NOT_CONSTANT = object()


def _self_comparison(text: str) -> bool:
    """`result == result` and the like: a comparison of one expression with itself."""
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except (SyntaxError, ValueError, RecursionError):
        return False
    return any(
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and ast.dump(node.left) == ast.dump(node.comparators[0])
        for node in ast.walk(tree)
    )


# --- properties -----------------------------------------------------------------------------------


def find_target(function: str, targets: Sequence[AttackTarget]) -> AttackTarget:
    """The target a proposal names: by id ("t1"), else by a unique name (`Owner.name` too)."""
    for target in targets:
        if function == target.id:
            return target
    named = [t for t in targets if function in (t.name, t.qualname)]
    if len(named) == 1:
        return named[0]
    raise ValueError(f"{function!r} is not one of the functions under attack")


def _module_names(target: AttackTarget) -> frozenset[str]:
    """The module's names an expression may use: its public ones, and a method's own class
    (even a private one: the class is how its objects are written)."""
    return target.public_names() | ({target.owner} if target.owner else frozenset())


def base_names(target: AttackTarget, stdlib: frozenset[str]) -> frozenset[str]:
    params = {p.name for p in target.params}
    return frozenset(params | _module_names(target) | SAFE_BUILTINS | BUILTIN_EXCEPTIONS | stdlib)


Used = tuple[tuple[str, ...], tuple[str, ...]]


def _used(free: set[str], target: AttackTarget, stdlib: frozenset[str]) -> Used:
    params = {p.name for p in target.params}
    names = sorted((free & _module_names(target)) - params - SAFE_BUILTINS)
    modules = sorted((free & stdlib) - params - target.public_names())
    return tuple(names), tuple(modules)


def check_receiver(text: str, target: AttackTarget, stdlib: frozenset[str]) -> Used:
    """The code that builds the object a method is called on (its input `self`, M7.5): one
    expression with a property's hygiene whose outermost node is a call (a fresh object, never
    a shared one), over the module's names, safe builtins and standard-library modules only,
    never using the method under test. The module names and modules it uses; ValueError if it
    breaks a rule. It runs nowhere but inside the sandboxed runs."""
    if not target.has_receiver:
        raise ValueError(f"{target.qualname} is not called on an object: it takes no self")
    try:
        node = ast.parse(text.strip(), mode="eval").body
    except (SyntaxError, ValueError, RecursionError):
        raise ValueError("`self` is not a Python expression") from None
    if not isinstance(node, ast.Call):
        raise ValueError("`self` must be a call that builds the object, such as Owner(...)")
    allowed = frozenset(_module_names(target) | SAFE_BUILTINS | stdlib)
    free = expression_names(text, "`self`", allowed, target.name, target.name)
    return _used(free, target, stdlib)


def check_property(
    proposal: PropertyProposal,
    targets: Sequence[AttackTarget],
    evidence: Mapping[str, Mapping[Source, Sequence[str]]],
    stdlib: frozenset[str],
    pid: str,
) -> CheckedProperty:
    """The property as it will run, or ValueError with why it doesn't count. `evidence`: the
    quotable texts per target id; `stdlib`: the standard modules expressions may use."""
    target = find_target(proposal.function, targets)
    params = {p.name for p in target.params}
    objects = {RECEIVER, AFTER} if target.has_receiver else set()
    clash = sorted(params & (RESERVED | stdlib | objects))
    if clash:
        raise ValueError(
            f"{target.name} has parameters named like reserved names ({', '.join(clash)})"
        )
    method = target.name if target.owner else ""
    if len(proposal.claim) > MAX_CLAIM or not proposal.claim.strip():
        raise ValueError(f"the claim must be one sentence of at most {MAX_CLAIM} characters")
    if not quote_found(proposal.quote, evidence[target.id][proposal.source]):
        raise ValueError(
            f"the quote was not found word for word in the {proposal.source} text "
            f"(it must be at least {MIN_QUOTE} characters)"
        )
    allowed = base_names(target, stdlib)
    # A method's object: `self` as it was before the call (in `when` too), `self_after` the
    # object after the call (D3).
    after = allowed | objects
    with_result = after | {"result"}
    free: set[str] = set()
    when = "" if proposal.when.strip() in ("", "True") else proposal.when.strip()
    if when:
        if _constant(when) in (False, None, 0, ""):
            raise ValueError("`when` is never true")
        before = allowed | (objects - {AFTER})
        free |= expression_names(when, "`when`", before, target.name, method)
    check, expected = proposal.check.strip(), proposal.expected.strip()
    kind = proposal.kind
    exceptions = tuple(dict.fromkeys(e.strip() for e in proposal.exceptions))
    for name in exceptions:
        if name not in BUILTIN_EXCEPTIONS and name not in target.class_names():
            raise ValueError(f"{name} is not a builtin exception or a class of the module")
    free |= set(exceptions) & target.class_names()
    transform = ""
    if kind in ("returns", "raises_only", "relation") and check:
        if _constant(check) is not _NOT_CONSTANT:
            raise ValueError("`check` is a constant: it checks nothing")
        if _self_comparison(check):
            raise ValueError("`check` compares something with itself: it checks nothing")
        scope = with_result | ({"result2"} if kind == "relation" else set())
        used = expression_names(check, "`check`", frozenset(scope), target.name, method)
        # What the call did to its object is an outcome too (a method that returns None).
        if kind == "returns" and not used & {"result", AFTER} and not expected:
            raise ValueError("`check` never looks at the result")
        if kind == "relation" and "result2" not in used:
            raise ValueError("a relation's `check` must compare result2")
        free |= used - {"result", "result2"}
    if kind == "returns":
        if not check and not expected:
            raise ValueError("a `returns` property needs a check or an expected value")
        if expected:
            free |= expression_names(expected, "`expected`", after, target.name, method)
    elif kind == "raises":
        if not exceptions:
            raise ValueError("a `raises` property needs at least one exception")
    elif kind == "relation":
        if not check:
            raise ValueError("a relation needs a check")
        transform = proposal.transform.strip()
        free |= _transform_names(transform, target, with_result, method)
    names, modules = _used(free, target, stdlib)
    return CheckedProperty(
        pid,
        target.id,
        kind,
        proposal.name.strip()[:60] or pid,
        collapse(proposal.claim),
        proposal.source,
        collapse(proposal.quote),
        when,
        check if kind != "raises" else "",
        expected if kind == "returns" else "",
        exceptions,
        transform,
        names,
        modules,
    )


def _transform_names(
    text: str, target: AttackTarget, allowed: frozenset[str], method: str = ""
) -> set[str]:
    """A relation's transform: a dict literal from parameter names to expressions (a method's
    object is not one of them: the second call is on a fresh object built the same way)."""
    free = expression_names(text, "`transform`", allowed, target.name, method)
    node = ast.parse(text, mode="eval").body
    params = {p.name for p in target.params}
    if not isinstance(node, ast.Dict) or not node.keys:
        raise ValueError("`transform` must be a dict literal of new arguments")
    for key in node.keys:
        if not (isinstance(key, ast.Constant) and key.value in params):
            raise ValueError("`transform` keys must be parameter names")
    for value in node.values:
        if _quoted_expression(value, params | {"result"}):
            raise ValueError(
                '`transform` values are expressions, not strings: write -value, not "-value"'
            )
    return free - {"result"}


def _quoted_expression(node: ast.expr, names: set[str]) -> bool:
    """A string constant that is itself an expression over the parameters or the result, such
    as "-value" or "value * 2": the model meant the expression (real-bug trial: naturalsize was
    called with the text "-value"). A plain string argument such as "V" is not one."""
    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        return False
    try:
        tree = ast.parse(node.value.strip(), mode="eval")
    except (SyntaxError, ValueError, RecursionError):
        return False
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    return bool(used & names) and not isinstance(tree.body, ast.Name)


def same_property(a: CheckedProperty, b: CheckedProperty) -> bool:
    """Same target, kind and expressions (layout ignored): a repeat, counted once."""

    def code(p: CheckedProperty) -> tuple[str, ...]:
        parts = []
        for text in (p.when, p.check, p.expected, p.transform):
            try:
                parts.append(ast.dump(ast.parse(text, mode="eval")) if text else "")
            except (SyntaxError, ValueError, RecursionError):
                parts.append(text)
        return (p.target, p.kind, *parts, *sorted(p.exceptions))

    return code(a) == code(b)


def doc_property(example: DocExample, pid: str) -> CheckedProperty:
    """A docstring example as a single-input property (developer, 6 Oct 2026: they count)."""
    claim = f"the docstring's example holds: {collapse(example.quote)}"[:MAX_CLAIM]
    return CheckedProperty(
        pid,
        example.target,
        "example",
        f"docstring example {pid}",
        claim,
        "docstring",
        collapse(example.quote),
        example_args=example.args,
        example_expected=example.expected,
        compare=example.compare,
        origin="docstring",
    )


# --- strategies and examples ----------------------------------------------------------------------


def check_strategy(
    proposal: StrategyProposal, targets: Sequence[AttackTarget]
) -> tuple[str, str, str]:
    """(target id, parameter, strategy) if it is only `st.<allowed>(...)` calls over literals."""
    target = find_target(proposal.function, targets)
    if proposal.param not in {p.name for p in target.params}:
        raise ValueError(f"{target.name} has no parameter {proposal.param!r}")
    text = proposal.strategy.strip()
    if len(text) > MAX_STRATEGY:
        raise ValueError(f"the strategy is longer than {MAX_STRATEGY} characters")
    try:
        node = ast.parse(text, mode="eval").body
    except (SyntaxError, ValueError, RecursionError):
        raise ValueError("the strategy is not a Python expression") from None
    _strategy_node(node)
    return target.id, proposal.param, text


def _strategy_node(node: ast.expr, depth: int = 0) -> None:
    if depth > 6:
        raise ValueError("the strategy is nested too deeply")
    if not isinstance(node, ast.Call):
        raise ValueError("a strategy must be a call such as st.integers(...)")
    func = node.func
    if not (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "st"
        and func.attr in STRATEGY_FUNCTIONS
    ):
        raise ValueError(f"{ast.unparse(func)} is not an allowed strategy")
    for arg in [*node.args, *(k.value for k in node.keywords)]:
        if isinstance(arg, ast.Call):
            _strategy_node(arg, depth + 1)
            continue
        try:
            value = ast.literal_eval(arg)
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
            raise ValueError("strategy arguments must be literals or strategies") from None
        if isinstance(value, str) and len(value) > MAX_PATTERN:
            raise ValueError(f"a strategy argument is longer than {MAX_PATTERN} characters")


def literal_value(text: str) -> str:
    """The canonical source of a plain literal (as the runtime writes it), else ValueError."""
    value = from_source(text)
    source = to_source(value)
    if source is None:
        raise ValueError("not a plain literal")
    return source


def check_example(
    proposal: ExampleProposal, targets: Sequence[AttackTarget], stdlib: frozenset[str] = frozenset()
) -> tuple[str, Args]:
    """(target id, args) if every value is a plain literal for a real parameter; a method's
    `self` is the code that builds its object instead (`check_receiver`)."""
    target = find_target(proposal.function, targets)
    names = list(target.arg_names)
    given: dict[str, str] = {}
    for arg in proposal.args:
        if arg.param not in names or arg.param in given:
            raise ValueError(f"{target.name} has no parameter {arg.param!r} (or it is repeated)")
        if target.has_receiver and arg.param == RECEIVER:
            check_receiver(arg.value, target, stdlib)
            code = ast.unparse(ast.parse(arg.value.strip(), mode="eval").body)
            check_receiver(code, target, stdlib)  # the text kept (spaces added may lengthen it)
            source = to_source(code)
            if source is None:
                raise ValueError("the value for self is too long")
            given[arg.param] = source
            continue
        try:
            given[arg.param] = literal_value(arg.value)
        except ValueError:
            raise ValueError(f"the value for {arg.param} is not a plain literal") from None
    if not given:
        raise ValueError("the example gives no arguments")
    return target.id, tuple((n, given[n]) for n in names if n in given)


# --- dedupe and the representative input ----------------------------------------------------------

PHASE_RANK = {"doc": 0, "grid": 1, "evidence": 2, "model": 3, "boundary": 4, "search": 5}


@dataclass(frozen=True)
class Violation:
    """One violation the runtime reported (untrusted until confirmed)."""

    order: int  # its position in the runs' output
    target: str
    prop: str  # the property's id
    phase: str
    args: Args | None  # None: an input that can't be written as code
    outcome: Mapping[str, str] = field(hash=False)
    detail: str = ""
    expected: str | None = None
    ran: bool = False  # its call ran a line the fix added or changed

    @property
    def raised(self) -> bool:
        return self.outcome.get("kind") == "raised"

    @property
    def key(self) -> tuple[str, str, str]:
        """SPEC 2.6: findings are deduplicated by function and exception type, or by function
        and property for a wrong value."""
        if self.raised:
            return self.target, "raised", self.outcome.get("type", "")
        return self.target, "value", self.prop


@dataclass(frozen=True)
class Group:
    key: tuple[str, str, str]
    representative: Violation
    others: tuple[Violation, ...]  # up to MAX_OTHER_INPUTS other inputs, best first
    properties: tuple[str, ...]  # every property the representative input violates


def group_violations(violations: Sequence[Violation], counted: Iterable[str]) -> list[Group]:
    """Group by the dedupe key and pick each group's most convincing input: the one that breaks
    the most properties, then the earliest source (docstring example, grid, evidence, model
    example, boundary, search), then the shortest. Only violations of `counted` properties."""
    allowed = set(counted)
    usable = [v for v in violations if v.prop in allowed]
    broken: dict[tuple[str, Args | None], set[str]] = {}
    for v in usable:
        broken.setdefault((v.target, v.args), set()).add(v.prop)
    groups: dict[tuple[str, str, str], list[Violation]] = {}
    for v in usable:
        groups.setdefault(v.key, []).append(v)

    def rank(v: Violation) -> tuple[int, int, int, int, int, int]:
        size = sum(len(text) for _, text in v.args) if v.args is not None else 10**9
        return (
            v.args is None,
            not v.ran,  # through the fix first: a call that never reaches it may be pre-existing
            -len(broken[(v.target, v.args)]),
            PHASE_RANK.get(v.phase, 9),
            size,
            v.order,
        )

    out = []
    for key, members in groups.items():
        members.sort(key=rank)
        best = members[0]
        others: list[Violation] = []
        seen = {best.args}
        for v in members[1:]:
            if v.args not in seen and len(others) < MAX_OTHER_INPUTS:
                seen.add(v.args)
                others.append(v)
        violated = sorted(broken[(best.target, best.args)], key=lambda p: p != best.prop)
        out.append(Group(key, best, tuple(others), tuple(violated)))
    out.sort(key=lambda g: rank(g.representative))
    return _merged(out)


def _merged(groups: Sequence[Group]) -> list[Group]:
    """One finding per input and outcome: groups whose representatives are the same input with
    the same outcome (one bug that several properties notice) become the first of them, with the
    others' properties added to what it violates and their inputs to its other inputs (up to
    MAX_OTHER_INPUTS). A later round replays earlier violating inputs (plan P10), so a bug two
    properties notice shares an input; without one nothing merges."""
    kept: list[Group] = []
    for group in groups:
        v = group.representative
        same = next(
            (
                k
                for k in kept
                if k.representative.target == v.target
                and k.representative.args == v.args
                and _outcome_key(k.representative) == _outcome_key(v)
            ),
            None,
        )
        if same is None:
            kept.append(group)
            continue
        extra = tuple(p for p in group.properties if p not in same.properties)
        others = list(same.others)
        seen = {o.args for o in (same.representative, *others)}
        for o in (group.representative, *group.others):
            if o.args not in seen and len(others) < MAX_OTHER_INPUTS:
                seen.add(o.args)
                others.append(o)
        kept[kept.index(same)] = Group(
            same.key, same.representative, tuple(others), same.properties + extra
        )
    return kept


def _outcome_key(v: Violation) -> tuple[str, str, str]:
    detail = v.outcome.get("repr", "") if not v.raised else v.outcome.get("message", "")
    return v.outcome.get("kind", ""), v.outcome.get("type", ""), detail


# --- the standalone repro file --------------------------------------------------------------------


@dataclass(frozen=True)
class Expectation:
    """The failure a repro file must end with on head: one of `types` (empty: any test failure),
    with the crash site inside the file (True), outside it (False) or anywhere (None)."""

    types: frozenset[str]
    in_file: bool | None


@dataclass(frozen=True)
class ReproFile:
    code: str
    expect: Expectation


def _comment(text: str) -> str:
    """Text safe for a one-line comment."""
    flat = " ".join("".join(ch if ch.isprintable() else " " for ch in text).split())
    return flat[:MAX_CLAIM]


def _dotted_name(text: str) -> bool:
    """`a.b.c` with every part a Python identifier: nothing else goes into an import line."""
    return bool(text) and all(part.isidentifier() for part in text.split("."))


def _callee(target: AttackTarget, on: str) -> str:
    """What a repro file calls: the function, `Owner.name` for a class or static method, or
    `<on>.name` for a method called on the object `on`."""
    if target.has_receiver:
        return f"{on}.{target.name}"
    return f"{target.owner}.{target.name}" if target.owner else target.name


def _call(target: AttackTarget, args: Args, on: str = AFTER) -> str:
    """The call, with immutable arguments by name and mutable ones as fresh literals (so the
    check sees the input as it was); a method's on `on` (a property is read, not called)."""
    given = dict(args)
    if target.has_receiver:
        given.pop(RECEIVER, None)
    parts = []
    names = [p.name for p in target.params]
    skipped_positional = False
    for param in target.params:
        if param.name not in given:
            skipped_positional = skipped_positional or param.kind == "positional_only"
            continue
        value = given[param.name]
        # Anything holding a list, dict or set (even inside a tuple) goes in as a fresh literal.
        mutable = "[" in value or "{" in value or "set(" in value
        text = value if mutable else param.name
        if param.kind == "positional_only":
            if skipped_positional:
                raise ValueError("a positional-only argument after a missing one can't be passed")
            parts.append(text)
        else:
            parts.append(f"{param.name}={text}")
    unknown = set(given) - set(names)
    if unknown:
        raise ValueError(f"unknown parameters {sorted(unknown)}")
    if target.kind == "property":
        return _callee(target, on)
    return _awaited(target, f"{_callee(target, on)}({', '.join(parts)})")


def _awaited(target: AttackTarget, call: str) -> str:
    """An async target's call run to the end on a fresh event loop, as in the run."""
    return f"asyncio.run({call})" if target.is_async else call


def _names_self(prop: CheckedProperty) -> bool:
    """The property's checks read `self`, the object as it was before the call (its `when` is
    only a comment in the repro file)."""
    for text in (prop.check, prop.expected, prop.transform):
        try:
            tree = ast.parse(text, mode="eval") if text else None
        except (SyntaxError, ValueError, RecursionError):
            continue
        if tree is not None and any(
            isinstance(n, ast.Name) and n.id == RECEIVER for n in ast.walk(tree)
        ):
            return True
    return False


def render_finding(
    number: int,
    module: str,
    target: AttackTarget,
    prop: CheckedProperty,
    args: Args,
    outcome: Mapping[str, str],
    stdlib: frozenset[str] = frozenset(),
) -> ReproFile:
    """A standalone pytest file that fails while the finding holds, and the failure it must show.
    Only plain literals and hygiene-checked expressions go into it. A method's object is built
    from its code, checked again here (`stdlib`: the modules that code may use), and written in
    its canonical form; the call runs on it (`self_after`), and `self` is a copy taken before
    the call when the checks read it, as in the run."""
    params = tuple((n, v) for n, v in args if not (target.has_receiver and n == RECEIVER))
    for _, value in params:
        literal_value(value)  # raises for anything but a plain literal
    if not _dotted_name(module) or not _dotted_name(outcome.get("type", "") or "x"):
        raise ValueError("the module or exception name is not a plain dotted name")
    on = ""
    built_names: tuple[str, ...] = ()
    built_modules: tuple[str, ...] = ()
    if target.has_receiver:
        text = receiver_of(args, target)
        if text is None:
            raise ValueError("the input has no object to call the method on")
        built_names, built_modules = check_receiver(text, target, stdlib)
        on = ast.unparse(ast.parse(text.strip(), mode="eval").body)
    copy_self = target.has_receiver and _names_self(prop)
    call = _call(target, params)
    raised = outcome.get("kind") == "raised"
    modules = sorted({*prop.stdlib, *built_modules, *(["copy"] if copy_self else []),
                      *(["asyncio"] if target.is_async else [])})  # fmt: skip
    head = target.owner or target.name
    names = sorted((set(prop.names) | set(built_names)) - {target.name, head})
    what = f"raises {outcome.get('type', '')}" if raised else "returns a wrong value"
    lines = [
        f"# Break My Fix finding {number}, generated by Tracefix: {target.qualname} "
        f"{_comment(what)}.",
        f"# Property ({prop.source}): {_comment(prop.claim)}",
        f"# Quote: {_comment(prop.quote)}",
        "# Run it with pytest: it fails for as long as the code breaks this property.",
        "",
    ]
    needs_pytest = prop.kind == "raises" or (prop.kind == "example" and prop.compare == "raises")
    if prop.kind == "example" and prop.compare == "repr":
        modules = sorted({*modules, "contextlib", "doctest", "io"})
    imports = [f"import {m}" for m in modules] + (["import pytest"] if needs_pytest else [])
    warned = outcome.get("warned", "")
    if warned:  # under its own name: a parameter may be called `warnings`
        imports.append("import warnings as _warnings")
    if imports:
        lines += [*imports, ""]
    lines += [f"from {module} import {', '.join([head, *names])}", "", ""]
    lines.append(f"def test_break_my_fix_{number}() -> None:")
    if on:
        lines.append(f"    {AFTER} = {on}")
        if copy_self:
            lines.append(f"    {RECEIVER} = copy.deepcopy({AFTER})")
    lines += [f"    {name} = {value}" for name, value in params]
    if prop.when:
        lines.append(f"    # The property applies to this input: {_comment(prop.when)}")
    body, expect = _body(prop, target, params, call, outcome, on)
    # The attack judged the call without the run's starting "error" filters (M11 S4). When a test
    # starts, every "error" filter is the project's (pytest has reverted any the code set at
    # import), so the file takes away exactly those and keeps the rest: ignoring every warning
    # would change what code that records its own warnings returns (verifier round 2 of M11, B1).
    if warned:
        body = [
            f"# {_comment(warned)} is not the failure: the project's error filters are off, as "
            "in the attack.",
            "with _warnings.catch_warnings():",
            f"    {DROP_ERROR_FILTERS}",
            *(f"    {line}" for line in body),
        ]
    lines += [f"    {line}" for line in body]
    return ReproFile("\n".join(lines) + "\n", expect)


def _body(
    prop: CheckedProperty,
    target: AttackTarget,
    args: Args,
    call: str,
    outcome: Mapping[str, str],
    on: str = "",
) -> tuple[list[str], Expectation]:
    raised = outcome.get("kind") == "raised"
    crash = Expectation(frozenset({outcome.get("type", "")}), in_file=False)
    wrong = Expectation(frozenset({"AssertionError"}), in_file=True)
    missed = Expectation(frozenset({"Failed"}), None)  # pytest.raises: DID NOT RAISE
    if prop.kind == "example":
        if prop.compare == "raises":
            body = [
                "with pytest.raises(Exception) as caught:",
                f"    {call}",
                f"assert type(caught.value).__name__ == {prop.example_expected!r}",
            ]
            return body, (wrong if raised else missed)
        if prop.compare == "repr":
            # What doctest itself compares: the printed output, then the repr unless None.
            body = [
                "printed = io.StringIO()",
                "with contextlib.redirect_stdout(printed):",
                f"    result = {call}",
                'shown = printed.getvalue() + (repr(result) + "\\n" if result is not None else "")',
                f"want = {prop.example_expected + chr(10)!r}",
                "assert doctest.OutputChecker().check_output(want, shown, 0), shown",
            ]
            return body, (crash if raised else wrong)
        # Brackets: an expected value is written as an expression, and `==` must apply to all
        # of it (`29 if leap else 28`).
        body = [f"result = {call}", f"assert result == ({prop.example_expected})"]
        return body, (crash if raised else wrong)
    if prop.kind == "raises":
        body = [f"with pytest.raises(({', '.join(prop.exceptions)},)):", f"    {call}"]
        return body, (crash if raised else missed)
    if prop.kind == "relation":
        if any(p.kind == "positional_only" for p in target.params):
            raise ValueError("a relation on positional-only parameters can't be written as a call")
        first = ", ".join(f"{name!r}: {name}" for name, _ in args)
        # A method's second call runs on a fresh object built the same way (as in the run).
        again = f"{_callee(target, on)}(**{{{first}, **({prop.transform})}})"
        second = f"result2 = {_awaited(target, again)}"
        if prop.exceptions:  # as in the run: an allowed raise means the relation does not apply
            allowed = ", ".join(prop.exceptions)
            second_lines = ["try:", f"    {second}", f"except ({allowed},):", "    return"]
        else:
            second_lines = [second]
        body = [f"result = {call}", *second_lines, f"assert ({prop.check})"]
        return body, (crash if raised else Expectation(frozenset(), None))
    body = [f"result = {call}"]
    if prop.check:
        body.append(f"assert ({prop.check})")
    if prop.expected:
        body.append(f"assert result == ({prop.expected})")
    return body, (crash if raised else wrong)


# --- the runtime's out file -----------------------------------------------------------------------


def read_events(text: str | None) -> tuple[list[dict[str, Any]], int]:
    """The JSON-lines events of one run (untrusted: written inside the process under test), and
    how many lines were unreadable (too long, not JSON, not an event)."""
    if not text:
        return [], 0
    events: list[dict[str, Any]] = []
    bad = 0
    lines = text.splitlines()
    if not text.endswith("\n") and lines:
        lines.pop()  # a run killed mid-write: the last line is partial
    for line in lines:
        if not line.strip():
            continue
        if len(line) > MAX_EVENT_LINE:
            bad += 1
            continue
        try:
            event = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if isinstance(event, dict) and isinstance(event.get("event"), str):
            events.append(event)
        else:
            bad += 1
    return events, bad


def _short(value: object, limit: int = 4_000) -> str:
    return value[:limit] if isinstance(value, str) else ""


def outcome_of(value: object) -> dict[str, str] | None:
    """An outcome report ({kind, type, repr | module + message}), or None if malformed."""
    if not isinstance(value, dict) or value.get("kind") not in ("returned", "raised"):
        return None
    kind = _short(value.get("type"), 200)
    if not _dotted_name(kind):  # a type name is an identifier: anything else is forged
        return None
    out = {"kind": str(value["kind"]), "type": kind}
    for key in ("repr", "module", "message", "raised_by", "in_project", "errno", "winerror"):
        if key in value:
            out[key] = _short(value.get(key))
    warned = _short(value.get("warned"), 200)  # M11 S4: a name, for words and a comment only
    if _dotted_name(warned):
        out["warned"] = warned
    return out


def receiver_of(args: Args, target: AttackTarget) -> str | None:
    """The code that builds a method's object in an input (its `self`), or None."""
    if not target.has_receiver:
        return None
    source = dict(args).get(RECEIVER)
    try:
        text = from_source(source) if source is not None else None
    except ValueError:
        return None
    return text if isinstance(text, str) else None


def receiver_spec(
    target: AttackTarget, codes: Iterable[str], stdlib: frozenset[str]
) -> dict[str, Any]:
    """What the runtime needs to call a method (M7.5): its class and kind, and the module names
    and standard-library modules its objects' code uses (each code checked again here; one that
    fails is left out, so the runtime can't evaluate it). Nothing for a function."""
    if not target.owner:
        return {}
    names: set[str] = set()
    modules: set[str] = set()
    for code in codes:
        try:
            used, mods = check_receiver(code, target, stdlib)
        except ValueError:
            continue
        names.update(used)
        modules.update(mods)
    return {
        "owner": target.owner,
        "kind": target.kind,
        "receiver_names": sorted(names),
        "receiver_stdlib": sorted(modules),
    }


def args_of(
    value: object, target: AttackTarget, stdlib: frozenset[str] = frozenset()
) -> Args | None:
    """Validated literal arguments, in parameter order; None if any isn't a plain literal. For
    a method called on an object, `self` must be there and pass `check_receiver` (it comes back
    from a run: untrusted, and it will run again in probes and repro files)."""
    if not isinstance(value, dict):
        return None
    order = list(target.arg_names)
    try:
        given = {str(k): literal_value(v) for k, v in value.items() if isinstance(v, str)}
    except ValueError:
        return None
    if len(given) != len(value) or set(given) - set(order):
        return None
    args = tuple((name, given[name]) for name in order if name in given)
    if target.has_receiver:
        text = receiver_of(args, target)
        try:
            if text is None:
                return None
            check_receiver(text, target, stdlib)
        except ValueError:
            return None
    return args


def violation_of(
    event: Mapping[str, Any],
    order: int,
    targets: Mapping[str, AttackTarget],
    stdlib: frozenset[str] = frozenset(),
) -> Violation | None:
    """A violation event as Tracefix reads it, or None if it is malformed."""
    target = targets.get(str(event.get("target")))
    outcome = outcome_of(event.get("outcome"))
    if target is None or outcome is None or not isinstance(event.get("property"), str):
        return None
    args = args_of(event.get("args"), target, stdlib) if event.get("representable") else None
    expected = event.get("expected")
    return Violation(
        order,
        target.id,
        event["property"],
        _short(event.get("phase"), 20),
        args,
        outcome,
        _short(event.get("detail"), 2_000),
        expected[:2_000] if isinstance(expected, str) else None,
        event.get("ran") is True,
    )

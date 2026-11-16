"""Methods as targets (M7.5), the static side: read with `ast` only, nothing here runs any code.

- where a changed method is: its class at module level, the definition the class exposes, and
  its kind (a method, class method, static method or property getter), or why it isn't called;
- what the model and the Judge see of the class: its header, docstring, constructor and the
  headers of its other public methods;
- the object a call is made on, in a test or a docstring session: a name bound to a fresh
  `Owner(...)` whose first use is the call (a later use could see an object a call changed).
"""

import ast
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

TargetKind = Literal["function", "method", "classmethod", "staticmethod", "property"]
RECEIVER_KINDS = frozenset({"method", "property"})  # called on an object
RECEIVER = "self"  # the input holding the code that builds the object
AFTER = "self_after"  # in property expressions: the object after the call
CONSTRUCTORS = ("__init__", "__post_init__", "__new__")
NESTED_FUNCTION = "a nested function: it can't be imported, not attacked yet"
REDEFINED = "a property its class redefines later: not called"
ABSTRACT = "an abstract method: a subclass's version is what runs, not this body"
_ABSTRACT = frozenset({"abstractmethod", "abstractproperty"})
_PROPERTIES = frozenset({"property", "cached_property", "functools.cached_property"})
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
# A use under one of these may run more than once, on an object an earlier run changed.
_REPEATS = (ast.For, ast.AsyncFor, ast.While, ast.ListComp, ast.SetComp, ast.DictComp,
            ast.GeneratorExp, *_SCOPES)  # fmt: skip

Definition = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass(frozen=True)
class Located:
    """A changed method that can be called: its class, the definition the class exposes (for a
    property, the changed getter), its kind, and how often the class defines the name."""

    owner: ast.ClassDef
    node: Definition  # an async method is awaited on a fresh event loop (M11 early)
    kind: TargetKind
    defined: int


def _dotted(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        inner = _dotted(node.value)
        return f"{inner}.{node.attr}" if inner else ""
    return ""


def is_generator(node: Definition) -> bool:
    """True if the function's own body (not a nested function's) yields."""
    stack: list[ast.AST] = list(node.body)
    while stack:
        current = stack.pop()
        if isinstance(current, ast.Yield | ast.YieldFrom):
            return True
        if isinstance(current, _SCOPES):
            continue
        stack.extend(ast.iter_child_nodes(current))
    return False


def class_defs(owner: ast.ClassDef, name: str) -> list[Definition | ast.ClassDef]:
    """The definitions of `name` in the class body, in source order, counted as diffscope counts
    them (also inside an `if` or `try` in the body, not inside a nested class or function)."""
    found: list[Definition | ast.ClassDef] = []
    stack: list[ast.AST] = list(reversed(list(ast.iter_child_nodes(owner))))
    while stack:
        node = stack.pop()
        if isinstance(node, Definition | ast.ClassDef):
            if node.name == name:
                found.append(node)
            continue
        stack.extend(reversed(list(ast.iter_child_nodes(node))))
    return found


def _decorators(node: Definition) -> set[str]:
    return {_dotted(d.func if isinstance(d, ast.Call) else d) for d in node.decorator_list}


def accessor(node: Definition) -> str:
    """'setter' or 'deleter' for `@x.setter` / `@x.deleter`, 'getter' for `@x.getter`, else ''."""
    for d in node.decorator_list:
        if isinstance(d, ast.Attribute) and d.attr in ("setter", "deleter", "getter"):
            return d.attr
    return ""


def is_abstract(node: Definition) -> bool:
    """Marked `@abstractmethod` or `@abstractproperty`, `abc.` or not (M11 S5, NOTES 30)."""
    return any(name.rpartition(".")[2] in _ABSTRACT for name in _decorators(node))


def kind_of(node: Definition) -> TargetKind:
    names = _decorators(node)
    if "staticmethod" in names:
        return "staticmethod"
    if "classmethod" in names:
        return "classmethod"
    if names & _PROPERTIES or accessor(node) == "getter":
        return "property"
    return "method"


def _first_param(node: Definition) -> str | None:
    positional = [*node.args.posonlyargs, *node.args.args]
    return positional[0].arg if positional else None


def locate(tree: ast.Module, qualname: str, occurrence: int) -> Located | str:
    """The changed method `qualname` (`Owner.name`, its `occurrence`-th definition) of a class at
    module level, or why Break My Fix and the behaviour diff don't call it."""
    first, *rest = qualname.split(".")
    top = [n for n in tree.body if isinstance(n, Definition | ast.ClassDef) and n.name == first]
    if not top or not isinstance(top[-1], ast.ClassDef):
        return NESTED_FUNCTION if top else "not defined at module level"
    owner = top[-1]
    if len(rest) > 1:
        inner = class_defs(owner, rest[0])
        if inner and isinstance(inner[-1], ast.ClassDef):
            return "a method of a nested class: not called yet"
        return NESTED_FUNCTION
    name = rest[0]
    if name.startswith("__") and name.endswith("__"):
        return "a special method (such as __init__ or __eq__): not called yet"
    if name.startswith("__"):
        return "a name-mangled private method: not called yet"
    defs = [d for d in class_defs(owner, name) if isinstance(d, Definition)]
    if occurrence >= len(defs):
        return "not found in its class"
    changed = defs[occurrence]
    if accessor(changed) in ("setter", "deleter"):
        return "a property setter or deleter: not called yet"
    if kind_of(changed) == "property":
        if any(accessor(d) not in ("setter", "deleter") for d in defs[occurrence + 1 :]):
            return REDEFINED
        exposed: Definition = changed
    else:
        exposed = defs[-1]  # the binding the class exposes (an @overload stub is never it)
        if exposed is not changed and (accessor(exposed) or kind_of(exposed) == "property"):
            return REDEFINED
    kind = kind_of(exposed)
    if isinstance(exposed, ast.AsyncFunctionDef) and kind == "property":
        return "an async property: not called yet"
    if is_generator(exposed):
        return "generators are not attacked yet"
    first_param = _first_param(exposed)
    if kind in RECEIVER_KINDS and first_param != RECEIVER:
        return "its first parameter is not self: not called yet"
    if kind == "classmethod" and first_param is None:
        return "a class method without a parameter for the class: not called yet"
    return Located(owner, exposed, kind, len(defs))


def _named(key: ast.expr, loops: Mapping[str, tuple[str, ...]]) -> Iterable[str]:
    """The attribute names `key` can be: a string, or a loop's variable over listed strings."""
    if isinstance(key, ast.Constant) and isinstance(key.value, str):
        return (key.value,)
    return loops.get(key.id, ()) if isinstance(key, ast.Name) else ()


def _listed(values: ast.expr) -> tuple[str, ...]:
    if not isinstance(values, ast.List | ast.Tuple | ast.Set):
        return ()
    return tuple(
        e.value for e in values.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)
    )


def _removed(node: ast.AST, loops: Mapping[str, tuple[str, ...]]) -> Iterator[str]:
    """The attributes this code deletes from `self`: `del self.x`, `del self.__dict__[k]` and
    `delattr(self, k)`, with `k` a string or a loop's variable over listed strings."""
    if isinstance(node, ast.ClassDef):
        return  # `self` is another object in there
    if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
        loops = {**loops, node.target.id: _listed(node.iter)}
    if isinstance(node, ast.Delete):
        for target in node.targets:
            if isinstance(target, ast.Attribute) and _dotted(target.value) == RECEIVER:
                yield target.attr
            elif isinstance(target, ast.Subscript) and _dotted(target.value) == "self.__dict__":
                yield from _named(target.slice, loops)
    if (
        isinstance(node, ast.Call)
        and _dotted(node.func) == "delattr"
        and len(node.args) == 2
        and _dotted(node.args[0]) == RECEIVER
    ):
        yield from _named(node.args[1], loops)
    for child in ast.iter_child_nodes(node):
        yield from _removed(child, loops)


def deleted_attributes(tree: ast.Module, name: str) -> frozenset[str]:
    """What class `name` and its bases in the same file delete from `self` (M11 S5): only their
    code runs on such an object. A class or base in another file isn't read."""
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    found: set[str] = set()
    seen: set[str] = set()
    stack = [name]
    while stack:
        current = stack.pop()
        if current in seen or current not in classes:
            continue
        seen.add(current)
        stack.extend(_dotted(base) for base in classes[current].bases)
        for statement in classes[current].body:
            found.update(_removed(statement, {}))
    return frozenset(found)


def init_node(owner: ast.ClassDef) -> ast.FunctionDef | None:
    """The class's own `__init__` (the last definition), or None (inherited or generated)."""
    found = [d for d in class_defs(owner, "__init__") if isinstance(d, ast.FunctionDef)]
    return found[-1] if found else None


def method_callers(owner: ast.ClassDef, name: str) -> list[ast.FunctionDef]:
    """Public methods of the class that call `name` on the object or the class itself
    (`self.name(...)`, `cls.name(...)`, `Owner.name(...)`), in source order."""
    out = []
    for node in owner.body:
        if not isinstance(node, ast.FunctionDef) or node.name.startswith("_") or node.name == name:
            continue
        for call in (c for c in ast.walk(node) if isinstance(c, ast.Call)):
            func = call.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == name
                and isinstance(func.value, ast.Name)
                and func.value.id in ("self", "cls", owner.name)
            ):
                out.append(node)
                break
    return out


def _lines(text: str, first: int, last: int) -> str:
    return "\n".join(text.split("\n")[first - 1 : last])


def start_of(node: Definition | ast.ClassDef) -> int:
    return min([node.lineno, *(d.lineno for d in node.decorator_list)])


def def_header(text: str, node: Definition | ast.ClassDef) -> str:
    """Decorators and the `def`/`class` line(s), up to the body."""
    body_start = node.body[0].lineno if node.body else node.lineno + 1
    return _lines(text, start_of(node), max(body_start - 1, node.lineno))


def owner_context(text: str, owner: ast.ClassDef) -> str:
    """The class as the model and the Judge see it next to a method: its header and docstring,
    the statements of its body that aren't functions (fields, constants), its constructor in
    full, and one header line for each other public method."""
    parts = [def_header(text, owner)]
    for node in owner.body:
        if isinstance(node, Definition):
            if node.name in CONSTRUCTORS:
                parts.append(_lines(text, start_of(node), node.end_lineno or node.lineno))
            elif not node.name.startswith("_"):
                indent = " " * (node.col_offset + 4)
                parts.append(f"{def_header(text, node)}\n{indent}...")
        elif not isinstance(node, ast.ClassDef):
            parts.append(_lines(text, node.lineno, node.end_lineno or node.lineno))
    return "\n".join(parts)


def owner_call(node: ast.expr, is_owner: Callable[[ast.expr], bool]) -> ast.Call | None:
    """`node` if it is a call of the class itself (`Owner(...)`), else None."""
    return node if isinstance(node, ast.Call) and is_owner(node.func) else None


def _mentions(stmt: ast.stmt, names: set[str]) -> Iterator[tuple[ast.Name, bool]]:
    """Each mention of one of `names` in the statement, and whether it sits where it may run
    more than once (a loop, a comprehension) or not at all now (a nested function)."""
    stack: list[tuple[ast.AST, bool]] = [(stmt, False)]
    while stack:
        node, repeated = stack.pop()
        if isinstance(node, ast.Name) and node.id in names:
            yield node, repeated
        # A loop's own header counts too (conservative: its iterable runs once).
        inner = repeated or isinstance(node, _REPEATS)
        stack.extend((child, inner) for child in ast.iter_child_nodes(node))


def fresh_uses(
    statements: Sequence[ast.stmt], is_owner: Callable[[ast.expr], bool]
) -> dict[int, ast.Call]:
    """For each `x.attr` that is the first use of a name bound by `x = Owner(...)`, the call
    that built the object (keyed by the id of the `x.attr` node). Only statements at this level
    bind; the use must be the only mention of `x` in its statement and run at most once there.
    Any other mention (passing `x` on, a second use, a loop) ends the name's freshness."""
    pending: dict[str, ast.Call] = {}
    found: dict[int, ast.Call] = {}
    for stmt in statements:
        mentions: dict[str, list[tuple[ast.Name, bool]]] = {}
        for name_node, repeated in _mentions(stmt, set(pending)):
            mentions.setdefault(name_node.id, []).append((name_node, repeated))
        for name, seen in mentions.items():
            (name_node, repeated), *others = seen
            if not others and not repeated and isinstance(name_node.ctx, ast.Load):
                use = _attribute_on(stmt, name_node)
                if use is not None:
                    found[id(use)] = pending[name]
            del pending[name]
        if (
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
        ):
            built = owner_call(stmt.value, is_owner)
            if built is not None:
                pending[stmt.targets[0].id] = built
    return found


def _attribute_on(stmt: ast.stmt, name_node: ast.Name) -> ast.Attribute | None:
    for node in ast.walk(stmt):
        if isinstance(node, ast.Attribute) and node.value is name_node:
            return node
    return None


def uses(tree: ast.AST, name: str, kind: TargetKind) -> Iterator[tuple[ast.expr, ast.expr]]:
    """Each use of the target in `tree`, with the expression it is used on: for a method, class
    method or static method a call `<on>.name(...)` (the Call node); for a property a read
    `<on>.name` that is not itself called (the Attribute node)."""
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called.add(id(node.func))
            if kind != "property" and node.func.attr == name:
                yield node, node.func.value
    if kind == "property":
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == name
                and isinstance(node.ctx, ast.Load)
                and id(node) not in called
            ):
                yield node, node.value


def bodies(tree: ast.AST) -> Iterator[Sequence[ast.stmt]]:
    """The statement lists a fresh name can live in: the module's own statements and each
    function's body (a test file's helpers and tests)."""
    if isinstance(tree, ast.Module):
        yield tree.body
    for node in ast.walk(tree):
        if isinstance(node, Definition):
            yield node.body

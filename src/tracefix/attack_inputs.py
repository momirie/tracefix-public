"""Break My Fix's static inputs (SPEC 2.6, Decided in M6), read from git objects and `ast` only:
nothing here runs any code.

- targets: the changed module-level functions, plus the public callers of a changed private
  helper (where its documented contract lives);
- evidence: the texts the adversary is shown, by source, which the quote check searches;
- seeds: the fix's own comparisons and their neighbours (`year == 2100` -> 2200, 2000, ...),
  literals from the fix, the issue, the reproduction test, partly fixed repro attempts and Guard's
  surviving mutants;
- witnesses: literal calls to a target in the project's untouched tests and in the reproduction
  test, plus advisory ones in the tests the PR added or changed;
- docstring examples (`f(-5, 10) == 0`, `>>>` doctests).
"""

import ast
import fnmatch
import io
import re
import tokenize
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
from typing import Literal

from tracefix.attack_methods import (
    ABSTRACT,
    RECEIVER,
    RECEIVER_KINDS,
    Definition,
    Located,
    TargetKind,
    bodies,
    class_defs,
    def_header,
    fresh_uses,
    init_node,
    is_abstract,
    is_generator,
    kind_of,
    locate,
    method_callers,
    owner_call,
    owner_context,
    start_of,
    uses,
)
from tracefix.attack_runtime import MAX_OBJECT_CODE, from_source, to_source
from tracefix.diffscope import ChangeKind, DiffScope, FileChange, FileKind, classify
from tracefix.guard import GuardResult, MutantStatus, SourceFile, python_files, source_files
from tracefix.repro import ReproResult, ReproStatus, Verdict, called_name
from tracefix.runner import pytest_config
from tracefix.workspace import Workspace, blob_text

MAX_TARGETS = 6
MAX_CALLERS = 2  # public callers attacked for each changed private function
README_CHARS = 6_000
README_NAMES = ("README.md", "README.rst", "README.txt", "README")
MAX_ISSUE_VALUES = 20  # numbers, and quoted strings, taken from the issue (each)
MAX_CANDIDATES = 30  # evidence values per parameter
MAX_WITNESSES = 50  # per target
MAX_QUOTED = 40  # characters of a quoted string taken from the issue
SKIPPED_TEST_FILES = ("conftest.py", "__init__.py")
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")
_QUOTED = re.compile(
    rf"'([^'\n]{{1,{MAX_QUOTED}}})'|\"([^\"\n]{{1,{MAX_QUOTED}}})\"|`([^`\n]{{1,{MAX_QUOTED}}})`"
)

ParamKind = Literal["positional_only", "positional", "keyword_only"]
Args = tuple[tuple[str, str], ...]  # (parameter, literal source), in parameter order


@dataclass(frozen=True)
class Param:
    name: str
    kind: ParamKind
    annotation: str  # its source text, "" without one
    has_default: bool


@dataclass(frozen=True)
class OwnerTexts:
    """What a property about a method may quote from its class: the class's and its
    constructor's docstrings, the constructor's comments, the class and constructor headers."""

    docstrings: tuple[str, ...] = ()
    comments: str = ""
    headers: tuple[str, ...] = ()


@dataclass(frozen=True)
class AttackTarget:
    """One function or method Break My Fix and the behaviour diff call, as head's source
    describes it."""

    id: str  # "t1", "t2", ... in attack order
    path: str  # repo-relative source file
    name: str
    params: tuple[Param, ...]  # a method's object (or class) is not among them
    span: tuple[int, int]  # first and last line, decorators included
    header: str  # the def line(s): the "signature" a property may quote
    source: str  # the whole function, as shown to the adversary
    docstring: str
    comments: str  # the comments inside the function, one per line
    module_docstring: str
    module_names: tuple[tuple[str, str], ...]  # the module's public names, with a description
    module_candidates: tuple[str, ...]  # dotted names it may import under, likeliest first
    via: str = ""  # set for a public caller attacked on behalf of a changed private function
    owner: str = ""  # a method's class ("" for a function)
    kind: TargetKind = "function"
    owner_context: str = ""  # the class as the model and the Judge see it beside the method
    owner_texts: OwnerTexts = OwnerTexts()
    # The class's own __init__ (None: it has none). Read by nothing since verifier M7.5 round 1
    # (B1); kept so that decision can be reversed (DECISIONS, 12 Oct 2026).
    init_params: tuple[Param, ...] | None = None
    # `async def`: each call is awaited on a fresh event loop, in the run and in its repro file
    # (M11 early).
    is_async: bool = False

    @property
    def required(self) -> frozenset[str]:
        return frozenset(p.name for p in self.params if not p.has_default)

    @property
    def qualname(self) -> str:
        """`name`, or `Owner.name` for a method."""
        return f"{self.owner}.{self.name}" if self.owner else self.name

    @property
    def has_receiver(self) -> bool:
        """Called on an object: its inputs carry `self`, the code that builds a fresh one."""
        return self.kind in RECEIVER_KINDS

    @property
    def arg_names(self) -> tuple[str, ...]:
        """The names an input binds, in order: `self` first for a method called on an object."""
        names = tuple(p.name for p in self.params)
        return (RECEIVER, *names) if self.has_receiver else names

    def public_names(self) -> frozenset[str]:
        return frozenset(name for name, _ in self.module_names)

    def class_names(self) -> frozenset[str]:
        return frozenset(name for name, text in self.module_names if text.startswith("class "))


@dataclass(frozen=True)
class Skipped:
    path: str
    function: str
    reason: str


# --- targets --------------------------------------------------------------------------------------


def _top_level(tree: ast.Module) -> dict[str, list[ast.stmt]]:
    defs: dict[str, list[ast.stmt]] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            defs.setdefault(node.name, []).append(node)
    return defs


def params_of(node: Definition) -> tuple[Param, ...]:
    """The parameters a call can pass (not *args or **kwargs), with their kinds and defaults."""
    args = node.args
    ordered = [*args.posonlyargs, *args.args]
    with_default = len(ordered) - len(args.defaults)
    out = []
    for index, arg in enumerate(ordered):
        kind: ParamKind = "positional_only" if index < len(args.posonlyargs) else "positional"
        out.append(Param(arg.arg, kind, _annotation(arg), index >= with_default))
    for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        out.append(Param(arg.arg, "keyword_only", _annotation(arg), default is not None))
    return tuple(out)


def target_params(node: Definition, kind: TargetKind) -> tuple[Param, ...]:
    """The parameters a call passes: a method's, class method's or property's first parameter
    (the object or the class) is not one of them."""
    params = params_of(node)
    return params[1:] if kind in ("method", "classmethod", "property") else params


def _annotation(arg: ast.arg) -> str:
    return ast.unparse(arg.annotation) if arg.annotation is not None else ""


def _why_not(node: ast.stmt, allow_no_params: bool = False) -> str | None:
    """Why a module-level definition can't be called with inputs, or None if it can."""
    if isinstance(node, ast.ClassDef):
        return "it is a class"
    assert isinstance(node, Definition)
    if is_generator(node):
        return "generators are not attacked yet"
    if not params_of(node) and not allow_no_params:
        return "it takes no parameters to vary"
    return None


def _why_not_method(found: Located, allow_no_params: bool) -> str | None:
    """Why a located method isn't called: it is abstract (M11 S5), or it has nothing to vary (only
    a class or static method without parameters: an object's method varies with the object)."""
    if is_abstract(found.node):
        return ABSTRACT
    if found.kind in RECEIVER_KINDS or allow_no_params:
        return None
    return None if target_params(found.node, found.kind) else "it takes no parameters to vary"


def _comments(text: str) -> str:
    comments = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT:
                comments.append(token.string.lstrip("#").strip())
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return "\n".join(c for c in comments if c)


def _describe(node: ast.stmt) -> list[tuple[str, str]]:
    """(name, description) for each public name a module-level statement defines."""
    found: list[tuple[str, str]] = []
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        found.append((node.name, f"def {node.name}({ast.unparse(node.args)})"))
    elif isinstance(node, ast.ClassDef):
        bases = ", ".join(ast.unparse(b) for b in node.bases)
        found.append((node.name, f"class {node.name}({bases})" if bases else f"class {node.name}"))
    elif isinstance(node, ast.Assign | ast.AnnAssign):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = ast.unparse(node.value)[:80] if node.value is not None else "..."
        for target in targets:
            if isinstance(target, ast.Name):
                found.append((target.id, f"{target.id} = {value}"))
    elif isinstance(node, ast.ImportFrom):
        # Only class-like imported names (an exception such as ConfigError from another module):
        # an imported module or function (`os`, `system`) could reach I/O from a property. The
        # runtime checks the value again before a property may use it.
        for alias in node.names:
            local = alias.asname or alias.name
            if local[:1].isupper():
                found.append((local, f"class {local} (imported)"))
    return [(name, text) for name, text in found if not name.startswith("_") and name != "*"]


def module_names(tree: ast.Module) -> tuple[tuple[str, str], ...]:
    """The module's public names, each with a one-line description (the last definition wins)."""
    names: dict[str, str] = {}
    for node in tree.body:
        for name, text in _describe(node):
            names[name] = text
    return tuple(names.items())


def module_guess(path: str, head_files: frozenset[str]) -> str:
    """The dotted name the file most likely imports under: its path from the top of its package
    (the first folder up without an __init__.py)."""
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    folder = PurePosixPath(path).parent
    start = len(PurePosixPath(path).parent.parts)
    while folder.parts and str(folder / "__init__.py") in head_files:
        folder = folder.parent
        start -= 1
    return ".".join(parts[start:]) if parts[start:] else ".".join(parts)


def dotted_suffixes(path: str) -> tuple[str, ...]:
    """Every dotted name a file could import under: "src.svc.config", "svc.config", "config"."""
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return tuple(".".join(parts[i:]) for i in range(len(parts)))


def _target(
    tid: str,
    source: SourceFile,
    tree: ast.Module,
    node: Definition,
    head_files: frozenset[str],
    via: str = "",
    found: Located | None = None,
) -> AttackTarget:
    lines = source.head.split("\n")
    first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
    last = node.end_lineno or node.lineno
    body_start = node.body[0].lineno if node.body else node.lineno + 1
    header = "\n".join(lines[node.lineno - 1 : max(body_start - 1, node.lineno)])
    text = "\n".join(lines[first - 1 : last])
    guess = module_guess(source.path, head_files)
    target = AttackTarget(
        tid,
        source.path,
        node.name,
        params_of(node),
        (first, last),
        header,
        text,
        ast.get_docstring(node) or "",
        _comments(text),
        ast.get_docstring(tree) or "",
        module_names(tree),
        (guess,),
        via,
        is_async=isinstance(node, ast.AsyncFunctionDef),
    )
    if found is None:
        return target
    owner, init = found.owner, init_node(found.owner)
    docstrings = [ast.get_docstring(owner)]
    headers = [def_header(source.head, owner)]
    init_text = ""
    if init is not None:
        docstrings.append(ast.get_docstring(init))
        headers.append(def_header(source.head, init))
        init_text = "\n".join(lines[start_of(init) - 1 : init.end_lineno])
    texts = OwnerTexts(
        tuple(d for d in docstrings if d), _comments(init_text), tuple(h for h in headers if h)
    )
    return replace(
        target,
        params=target_params(node, found.kind),
        owner=owner.name,
        kind=found.kind,
        owner_context=owner_context(source.head, owner),
        owner_texts=texts,
        init_params=params_of(init)[1:] if init else None,
    )


def _callers(tree: ast.Module, name: str) -> list[ast.FunctionDef]:
    """Public module-level functions that call `name` directly, in file order."""
    found = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name.startswith("_") or node.name == name:
            continue
        if any(isinstance(c, ast.Call) and called_name(c) == name for c in ast.walk(node)):
            found.append(node)
    return found


@dataclass(frozen=True)
class _Pick:
    """A function or method chosen to attack, before it becomes an AttackTarget."""

    source: SourceFile
    node: Definition
    via: str = ""
    found: Located | None = None  # set for a method

    @property
    def qualname(self) -> str:
        return f"{self.found.owner.name}.{self.node.name}" if self.found else self.node.name


def _method(
    source: SourceFile, tree: ast.Module, qualname: str, occurrence: int, allow_no_params: bool
) -> _Pick | str:
    """A changed method to attack, or why not (M7.5)."""
    found = locate(tree, qualname, occurrence)
    if isinstance(found, str):
        return found
    why = _why_not_method(found, allow_no_params)
    return why if why is not None else _Pick(source, found.node, found=found)


def _occurrence(owner: ast.ClassDef, node: ast.FunctionDef) -> int:
    defs = [d for d in class_defs(owner, node.name) if not isinstance(d, ast.ClassDef)]
    return defs.index(node)


def _private_callers(
    pick: _Pick, trees: Mapping[str, ast.Module], allow_no_params: bool
) -> list[_Pick]:
    """Up to MAX_CALLERS public callers of a changed private function (module-level functions)
    or method (methods of its class calling it on `self`, `cls` or the class)."""
    tree = trees[pick.source.path]
    if pick.found is None:
        return [
            _Pick(pick.source, caller, f"a public caller of the changed {pick.node.name}")
            for caller in _callers(tree, pick.node.name)[:MAX_CALLERS]
            if _why_not(caller, allow_no_params) is None
        ]
    owner = pick.found.owner
    out = []
    for caller in method_callers(owner, pick.node.name)[:MAX_CALLERS]:
        found = _method(pick.source, tree, f"{owner.name}.{caller.name}",
                        _occurrence(owner, caller), allow_no_params)  # fmt: skip
        if isinstance(found, _Pick):
            out.append(replace(found, via=f"a public caller of the changed {pick.qualname}"))
    return out


def select_targets(
    ws: Workspace,
    scope: DiffScope,
    *,
    allow_no_params: bool = False,
    cut_is_skipped: bool = False,
) -> tuple[list[AttackTarget], list[Skipped], list[str]]:
    """The functions and methods to attack (at most MAX_TARGETS), the changed ones skipped and
    why, and notes. `allow_no_params`: a function without parameters is a target too (the
    behaviour diff calls it once on each side; Break My Fix has nothing to vary). A method
    called on an object always has its object to vary. `cut_is_skipped`: targets past the cap
    are listed as skipped, not only noted."""
    sources, notes = source_files(ws, scope)
    by_path = {s.path: s for s in sources}
    head_files = frozenset(ws.pristine[ws.head])
    trees = {s.path: ast.parse(s.head) for s in sources}
    picked: list[_Pick] = []
    private: list[_Pick] = []
    skipped: list[Skipped] = []
    for fn in scope.source_functions:
        source = by_path.get(fn.path)
        if fn.change is ChangeKind.REMOVED or source is None:
            continue
        tree = trees[fn.path]
        if "." in fn.qualname:
            found = _method(source, tree, fn.qualname, fn.occurrence, allow_no_params)
            if isinstance(found, str):
                skipped.append(Skipped(fn.path, fn.qualname, found))
                continue
            assert found.found is not None
            if found.found.defined > 1 and found.found.kind != "property":
                notes.append(
                    f"{fn.path}: {fn.qualname} is defined {found.found.defined} times in its "
                    "class; the attack calls the one the class exposes (the last)"
                )
            (private if found.node.name.startswith("_") else picked).append(found)
            continue
        nodes = _top_level(tree).get(fn.qualname, [])
        if not nodes:
            skipped.append(Skipped(fn.path, fn.qualname, "not a module-level function"))
            continue
        node = nodes[-1]  # the binding the module exports (Q10: an @overload stub is never it)
        why = _why_not(node, allow_no_params)
        if why is not None:
            skipped.append(Skipped(fn.path, fn.qualname, why))
            continue
        assert isinstance(node, Definition)
        if len(nodes) > 1:
            notes.append(
                f"{fn.path}: {fn.qualname} is defined {len(nodes)} times; the attack "
                "calls the one the module exports (the last)"
            )
        (private if fn.qualname.startswith("_") else picked).append(_Pick(source, node))
    picked.sort(key=lambda p: (p.source.path, p.node.lineno))  # file order, not name order
    private.sort(key=lambda p: (p.source.path, p.node.lineno))
    callers = [c for p in private for c in _private_callers(p, trees, allow_no_params)]
    ordered: list[_Pick] = []
    seen: set[tuple[str, str]] = set()
    for pick in [*picked, *private, *callers]:
        if (pick.source.path, pick.qualname) not in seen:
            seen.add((pick.source.path, pick.qualname))
            ordered.append(pick)
    if len(ordered) > MAX_TARGETS:
        notes.append(f"only the first {MAX_TARGETS} of {len(ordered)} functions are attacked")
        if cut_is_skipped:  # the behaviour diff can't vouch for what it never compared (B1)
            skipped += [
                Skipped(p.source.path, p.qualname, f"past the cap of {MAX_TARGETS} functions")
                for p in ordered[MAX_TARGETS:]
            ]
    targets = [
        _target(f"t{i}", p.source, trees[p.source.path], p.node, head_files, p.via, p.found)
        for i, p in enumerate(ordered[:MAX_TARGETS], 1)
    ]
    return targets, skipped, notes


def fixed_by_file(ws: Workspace, scope: DiffScope) -> dict[str, frozenset[int]]:
    """The fix's added or changed lines in every changed Python source file (head side)."""
    sources, _ = source_files(ws, scope)
    return {s.path: s.fixed for s in sources}


# --- evidence a property may quote ----------------------------------------------------------------

Source = Literal["issue", "docstring", "comment", "docs", "signature", "test"]


def readme(ws: Workspace) -> str:
    """The start of the repo's README at head, or ""."""
    for name in README_NAMES:
        text = blob_text(ws.repo, ws.head_sha, name) if name in ws.pristine[ws.head] else None
        if text:
            return text.replace("\r\n", "\n")[:README_CHARS]
    return ""


def evidence_texts(
    target: AttackTarget, issue: str, docs: str, tests: str
) -> dict[Source, tuple[str, ...]]:
    """The texts, by source, that a property about `target` may quote. Exactly what the adversary
    is shown, so a quote can only come from text the model really saw (for a method, also its
    class's docstrings, constructor comments and headers, shown beside it)."""
    owner = target.owner_texts
    return {
        "issue": (issue,),
        "docstring": (target.docstring, target.module_docstring, *owner.docstrings),
        "comment": (target.comments, *((owner.comments,) if owner.comments else ())),
        "docs": (docs,),
        "signature": (target.header, *owner.headers),
        "test": (tests,),
    }


# --- literals and calls ---------------------------------------------------------------------------


def literal_of(node: ast.expr) -> str | None:
    """The literal source of a plain-literal expression (as attack_runtime writes it), or None."""
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return None
    return to_source(value)


def bind_call(call: ast.Call, params: Sequence[Param]) -> Args | None:
    """The call's arguments by parameter name, if every one is a plain literal and every required
    parameter is given; else None."""
    if any(isinstance(a, ast.Starred) for a in call.args):
        return None
    positional = [p for p in params if p.kind != "keyword_only"]
    if len(call.args) > len(positional):
        return None
    bound: dict[str, str] = {}
    for param, arg in zip(positional, call.args, strict=False):
        source = literal_of(arg)
        if source is None:
            return None
        bound[param.name] = source
    names = {p.name: p for p in params}
    for keyword in call.keywords:
        named = names.get(keyword.arg or "")
        if named is None or named.kind == "positional_only" or named.name in bound:
            return None
        source = literal_of(keyword.value)
        if source is None:
            return None
        bound[named.name] = source
    if any(not p.has_default and p.name not in bound for p in params):
        return None
    return tuple((p.name, bound[p.name]) for p in params if p.name in bound)


Imports = tuple[dict[str, tuple[str, str]], dict[str, str]]


def imports_of(tree: ast.Module) -> Imports:
    """(local name -> (module, attribute)) for `from M import a as b`, and (local name -> module)
    for `import M`, `import M as a` and `from P import m as a` (m may be a module)."""
    names: dict[str, tuple[str, str]] = {}
    modules: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                names[alias.asname or alias.name] = (node.module, alias.name)
                modules[alias.asname or alias.name] = f"{node.module}.{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    modules[alias.asname] = alias.name
                else:
                    modules[alias.name.split(".")[0]] = alias.name.split(".")[0]
    return names, modules


def _dotted(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        inner = _dotted(node.value)
        return f"{inner}.{node.attr}" if inner else None
    return None


def refers_to(node: ast.expr, name: str, target: AttackTarget, imports: Imports) -> bool:
    """`node` reaches `name` in the target's module through the file's imports: `name` imported
    from its module, or `mod.name` / `pkg.mod.name` with the module imported. A same-named
    object from elsewhere never counts."""
    names, modules = imports
    suffixes = set(dotted_suffixes(target.path))
    if isinstance(node, ast.Name):
        found = names.get(node.id)
        return found is not None and found[1] == name and found[0] in suffixes
    if isinstance(node, ast.Attribute) and node.attr == name:
        owner = _dotted(node.value)
        if owner is None:
            return False
        first, _, rest = owner.partition(".")
        module = modules.get(first)
        return module is not None and (f"{module}.{rest}" if rest else module) in suffixes
    return False


def calls_target(call: ast.Call, target: AttackTarget, imports: Imports) -> bool:
    """The call reaches the function `target` through the file's imports: `f(...)` imported
    from its module, or `mod.f(...)` / `pkg.mod.f(...)` with the module imported."""
    return refers_to(call.func, target.name, target, imports)


def built_text(call: ast.Call, owner: str) -> str | None:
    """`Owner(1, b='x')`: a call that builds an object, written with the class's own name, if
    every argument is a plain literal (no `*` or `**`) and it is no longer than the run may use
    (verifier M7.5 round 2: a test's long object cut the diff short); else None."""
    if any(isinstance(a, ast.Starred) for a in call.args) or any(
        k.arg is None for k in call.keywords
    ):
        return None
    parts = [literal_of(a) for a in call.args]
    for keyword in call.keywords:
        value = literal_of(keyword.value)
        parts.append(None if value is None else f"{keyword.arg}={value}")
    if any(p is None for p in parts):
        return None
    text = f"{owner}({', '.join(p for p in parts if p is not None)})"
    return text if len(text) <= MAX_OBJECT_CODE else None


Owner = Callable[[ast.expr], bool]  # does this expression name the target's class?


def method_args(
    use: ast.expr,
    on: ast.expr,
    target: AttackTarget,
    is_owner: Owner,
    fresh: Mapping[int, ast.Call],
) -> Args | None:
    """The literal input of one use of a method target (`attack_methods.uses`): a class or
    static method must be used on the class itself; a method or property on an object built
    right there (`Owner(...).name`) or by the call `fresh` holds for this use (a name bound to
    one, first used here). None if any part is not a plain literal."""
    receiver: Args = ()
    if target.has_receiver:
        attribute = use.func if isinstance(use, ast.Call) else use
        built = owner_call(on, is_owner) if isinstance(on, ast.Call) else fresh.get(id(attribute))
        text = built_text(built, target.owner) if built is not None else None
        source = to_source(text) if text is not None else None
        if source is None:
            return None
        receiver = ((RECEIVER, source),)
    elif not is_owner(on):
        return None
    if not isinstance(use, ast.Call):
        return receiver
    args = bind_call(use, target.params)
    return None if args is None else (*receiver, *args)


def _method_calls(tree: ast.AST, target: AttackTarget, is_owner: Owner) -> list[Args]:
    fresh: dict[int, ast.Call] = {}
    for body in bodies(tree):
        fresh.update(fresh_uses(body, is_owner))
    found = []
    for use, on in uses(tree, target.name, target.kind):
        args = method_args(use, on, target, is_owner, fresh)
        if args is not None:
            found.append(((use.lineno, use.col_offset), args))
    found.sort(key=lambda f: f[0])
    return [args for _, args in found]


def target_calls(tree: ast.AST, target: AttackTarget, imports: Imports) -> list[Args]:
    """Literal calls to `target` inside `tree`, in source order (a method's with the object it
    is called on)."""
    if target.owner:
        return _method_calls(
            tree, target, lambda node: refers_to(node, target.owner, target, imports)
        )
    calls = [
        n for n in ast.walk(tree) if isinstance(n, ast.Call) and calls_target(n, target, imports)
    ]
    calls.sort(key=lambda c: (c.lineno, c.col_offset))
    return [args for args in (bind_call(c, target.params) for c in calls) if args is not None]


# --- witnesses ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class WitnessCall:
    target: str  # the target's id
    file: str  # the test file (repo-relative)
    test: str  # the test's qualified name in that file, e.g. "test_x" or "TestA.test_x"
    args: Args
    advisory: bool  # from a test the PR added or changed: noted, never decides
    repro: bool = False  # from the reproduction test (already proven to pass on head)

    @property
    def id(self) -> str:
        return f"{self.file}::{self.test.replace('.', '::')}"


def test_functions(
    tree: ast.Module,
) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """pytest's default test functions: module-level `test*`, and `test*` methods of `Test*`
    classes and of unittest.TestCase subclasses (by base name)."""
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test"
        ):
            yield node.name, node
        elif isinstance(node, ast.ClassDef):
            testcase = any(_dotted(b) in ("TestCase", "unittest.TestCase") for b in node.bases)
            if node.name.startswith("Test") or testcase:
                for item in node.body:
                    if isinstance(
                        item, ast.FunctionDef | ast.AsyncFunctionDef
                    ) and item.name.startswith("test"):
                        yield f"{node.name}.{item.name}", item


def _parse(text: str | None) -> ast.Module | None:
    if text is None:
        return None
    try:
        return ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return None


def head_test_files(ws: Workspace) -> list[str]:
    """Head's Python test files that pytest would collect, by the repo's `python_files`."""
    found = []
    for path in sorted(ws.pristine[ws.head]):
        name = PurePosixPath(path).name
        if not path.endswith(".py") or name in SKIPPED_TEST_FILES:
            continue
        if classify(path) is not FileKind.TEST:
            continue
        patterns = python_files(pytest_config(ws.head.resolve(), [path]))
        if any(fnmatch.fnmatch(path if "/" in p else name, p) for p in patterns):
            found.append(path)
    return found


@dataclass(frozen=True)
class HeadTestFile:
    path: str
    tree: ast.Module
    # (name, node, untouched): "test_x" or "TestK.test_x", and whether the PR left it alone.
    tests: tuple[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef, bool], ...]


def head_tests(ws: Workspace, scope: DiffScope) -> list[HeadTestFile]:
    """Head's test files that parse, each test with whether the PR left it untouched: its file
    unchanged, or the same code as the same-named test at base with the rest of the file the same;
    and no conftest, helper or data file the PR changed in its folder or above. Shared by Break My
    Fix's witnesses and the no-regression check."""
    changed = {f.path: f for f in scope.test_files}
    tests = head_test_files(ws)
    # Conftests, helpers and data the PR changed. A test file it deleted is not one: nothing
    # else runs it, and a test that imported it no longer collects, which shows on head.
    support = [p for p, f in changed.items() if p not in tests and not _deleted_test(ws, f)]
    found: list[HeadTestFile] = []
    for path in tests:
        tree = _parse(blob_text(ws.repo, ws.head_sha, path))
        if tree is None:
            continue
        before: dict[str, str] = {}
        change = changed.get(path)
        # Anything the PR changed around a test (module-level data in its file, a conftest or
        # helper in its folder or above) can change what it checks: none of its tests count.
        around = _under_changed_support(path, support)
        if change is not None:
            old = (
                None
                if change.status in "AC"
                else _parse(blob_text(ws.repo, ws.base_sha, change.old_path or path))
            )
            before = {name: ast.dump(node) for name, node in test_functions(old)} if old else {}
            around = around or old is None or _outside_tests(old) != _outside_tests(tree)
        found.append(
            HeadTestFile(
                path,
                tree,
                tuple(
                    (
                        name,
                        node,
                        not around and (change is None or before.get(name) == ast.dump(node)),
                    )
                    for name, node in test_functions(tree)
                ),
            )
        )
    return found


def witness_calls(
    ws: Workspace, scope: DiffScope, targets: Sequence[AttackTarget], repro: ReproResult | None
) -> list[WitnessCall]:
    """Literal calls to each target in head's tests: from tests the PR did not touch
    (`head_tests`) as witnesses; from tests it added or changed as advisory witnesses; and from a
    reproduction test that reproduced (proven on head)."""
    found: list[WitnessCall] = []
    for file in head_tests(ws, scope):
        imports = imports_of(file.tree)
        for name, node, untouched in file.tests:
            for target in targets:
                for args in target_calls(node, target, imports):
                    found.append(WitnessCall(target.id, file.path, name, args, not untouched))
    if repro is not None and repro.status is ReproStatus.REPRODUCED and repro.test_code:
        tree = _parse(repro.test_code)
        if tree is not None:
            imports = imports_of(tree)
            for name, node in test_functions(tree):
                for target in targets:
                    for args in target_calls(node, target, imports):
                        found.append(
                            WitnessCall(target.id, repro.test_path, name, args, False, repro=True)
                        )
    return _capped(found)


def _outside_tests(tree: ast.Module) -> str:
    """The module's code apart from its test functions (and test classes' test methods)."""
    tests = {id(node) for _, node in test_functions(tree)}
    kept = []
    for node in tree.body:
        if id(node) in tests:
            continue
        if isinstance(node, ast.ClassDef):
            body = [n for n in node.body if id(n) not in tests]
            node = ast.ClassDef(node.name, node.bases, node.keywords, body, node.decorator_list)
        kept.append(ast.dump(node))
    return "\n".join(kept)


def _deleted_test(ws: Workspace, change: FileChange) -> bool:
    """A test file the PR deleted: base's pytest would have collected it by `python_files`."""
    name = PurePosixPath(change.path).name
    if change.status != "D" or not name.endswith(".py") or name in SKIPPED_TEST_FILES:
        return False
    patterns = python_files(pytest_config(ws.base.resolve(), [change.path]))
    return any(fnmatch.fnmatch(change.path if "/" in p else name, p) for p in patterns)


def _under_changed_support(path: str, support: Sequence[str]) -> bool:
    """A test-layout file the PR changed (conftest, helper, data) sits in this test's folder or
    one above it."""
    folder = PurePosixPath(path).parent
    return any(
        folder == PurePosixPath(s).parent or PurePosixPath(s).parent in folder.parents
        for s in support
    )


def _capped(calls: Iterable[WitnessCall]) -> list[WitnessCall]:
    per: dict[str, int] = {}
    kept, seen = [], set()
    for call in calls:
        key = (call.target, call.args, call.advisory)
        if key in seen or per.get(call.target, 0) >= MAX_WITNESSES:
            continue
        seen.add(key)
        per[call.target] = per.get(call.target, 0) + 1
        kept.append(call)
    return kept


# --- docstring examples ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DocExample:
    target: str
    args: Args
    expected: str  # a literal (eq), the printed repr (repr) or an exception name (raises)
    compare: Literal["eq", "repr", "raises"]
    quote: str  # the example as written in the docstring


def _named_owner(target: AttackTarget) -> Owner:
    """In prose or a doctest (no imports to follow): the class by its name, `Owner` or
    `pkg.Owner`."""
    return lambda node: (_dotted(node) or "").rpartition(".")[2] == target.owner


def _use_of(
    node: ast.expr, target: AttackTarget, is_owner: Owner, fresh: Mapping[int, ast.Call]
) -> Args | None:
    """The input of `node` if `node` itself is a use of the method target."""
    for use, on in uses(node, target.name, target.kind):
        if use is node:
            return method_args(use, on, target, is_owner, fresh)
    return None


def _call_of(text: str, target: AttackTarget) -> Args | None:
    """The literal arguments of `text` if it is exactly a call to the target (a method's on an
    object built right there, or on the class)."""
    try:
        node = ast.parse(text.strip(), mode="eval").body
    except (SyntaxError, ValueError, RecursionError):
        return None
    if target.owner:
        return _use_of(node, target, _named_owner(target), {})
    if (
        not isinstance(node, ast.Call)
        or _dotted(node.func) not in (target.name, None)
        or (_dotted(node.func) or "").rpartition(".")[2] != target.name
    ):
        return None
    return bind_call(node, target.params)


def _example(
    lines: Sequence[str], index: int, target: AttackTarget, args: Args
) -> DocExample | None:
    """The docstring example whose `>>>` line is `lines[index]`, with its expected output."""
    output = []
    for later in lines[index + 1 :]:
        if not later.strip() or later.strip().startswith(">>>"):
            break
        output.append(later.strip())
    if not output:
        return None
    quote = "\n".join([lines[index].strip(), *output])
    if output[0].startswith("Traceback"):
        exception = output[-1].split(":", 1)[0].strip().rpartition(".")[2]
        return (
            DocExample(target.id, args, exception, "raises", quote)
            if exception.isidentifier()
            else None
        )
    return DocExample(target.id, args, output[0], "repr", quote) if len(output) == 1 else None


def _doctests(target: AttackTarget) -> Iterator[DocExample]:
    if target.owner:
        yield from _method_doctests(target)
        return
    lines = target.docstring.split("\n")
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith(">>> ") or "doctest:" in stripped:
            continue  # a directive (+ELLIPSIS, +SKIP...) changes what "the same output" means
        args = _call_of(stripped[4:], target)
        example = _example(lines, index, target, args) if args is not None else None
        if example is not None:
            yield example


def _sessions(lines: Sequence[str]) -> list[list[tuple[int, ast.stmt]]]:
    """A docstring's `>>>` lines as statements, in runs a name can stay fresh through: a line
    that doesn't parse alone, or a continuation line, ends a run (it may use any name)."""
    runs: list[list[tuple[int, ast.stmt]]] = [[]]
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("..."):
            runs.append([])
            continue
        if not stripped.startswith(">>> "):
            continue
        try:
            body = ast.parse(stripped[4:]).body
        except (SyntaxError, ValueError, RecursionError):
            body = []
        if len(body) == 1:
            runs[-1].append((index, body[0]))
        else:
            runs.append([])
    return runs


def _method_doctests(target: AttackTarget) -> Iterator[DocExample]:
    """A method's doctests: `>>> Owner(1).name(2)`, `>>> Owner.name(2)`, or `>>> x = Owner(1)`
    followed by `>>> x.name(2)` as the first use of `x`."""
    lines = target.docstring.split("\n")
    is_owner = _named_owner(target)
    for run in _sessions(lines):
        fresh = fresh_uses([stmt for _, stmt in run], is_owner)
        for index, stmt in run:
            if not isinstance(stmt, ast.Expr) or "doctest:" in lines[index]:
                continue
            args = _use_of(stmt.value, target, is_owner, fresh)
            example = _example(lines, index, target, args) if args is not None else None
            if example is not None:
                yield example


def _closing(text: str, start: int) -> int | None:
    """The index just after the `)` that closes the `(` at `start`, or None."""
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return index + 1
    return None


def _calls_in(text: str, target: AttackTarget) -> Iterator[tuple[int, int, Args]]:
    """(start, end, arguments) of every `name(literals)` call to the target written in `text`."""
    for match in re.finditer(rf"(?<![\w.]){re.escape(target.name)}\(", text):
        end = _closing(text, match.end() - 1)
        if end is None:
            continue
        args = _call_of(text[match.start() : end], target)
        if args is not None:
            yield match.start(), end, args


def _use_end(text: str, at: int, target: AttackTarget) -> int | None:
    """Where a use of the method target, written right after its class's name at `at`, ends:
    `(...).name(...)` on an object, `.name(...)` on the class, `(...).name` for a property."""
    if target.has_receiver:
        built = _closing(text, at) if text.startswith("(", at) else None
        if built is None:
            return None
        at = built
    attribute = f".{target.name}"
    if not text.startswith(attribute, at):
        return None
    at += len(attribute)
    following = text[at : at + 1]
    if target.kind == "property":
        return None if following == "(" or following.isalnum() or following == "_" else at
    return _closing(text, at) if following == "(" else None


def _method_calls_in(text: str, target: AttackTarget) -> Iterator[Args]:
    """The method target's uses with literal arguments written in a text (the issue): on an
    object built right there, or on the class."""
    for match in re.finditer(rf"(?<![\w.]){re.escape(target.owner)}(?!\w)", text):
        end = _use_end(text, match.end(), target)
        args = _call_of(text[match.start() : end], target) if end is not None else None
        if args is not None:
            yield args


def literal_calls(text: str, target: AttackTarget) -> list[Args]:
    """The target's calls with literal arguments written in a text (the issue), without repeats."""
    if target.owner:
        return list(dict.fromkeys(_method_calls_in(text, target)))
    return list(dict.fromkeys(args for _, _, args in _calls_in(text, target)))


def _inline(target: AttackTarget) -> Iterator[DocExample]:
    """`name(literals) == literal` written in the docstring's prose."""
    text = target.docstring
    for start, end, args in _calls_in(text, target):
        rest = re.match(r"\s*==\s*", text[end:])
        if rest is None:
            continue
        tail = text[end + rest.end() :].split("\n", 1)[0]
        for cut in [*(i for i, ch in enumerate(tail) if ch in ",;"), len(tail)]:
            literal = tail[:cut].strip().rstrip(".").strip("`").strip()
            try:
                value = from_source(literal) if literal else None
            except ValueError:
                continue
            source = to_source(value)
            if source is not None and literal:
                quote = text[start : end + rest.end()] + tail[:cut].rstrip().rstrip(".")
                yield DocExample(target.id, args, source, "eq", quote.strip())
                break


def doc_examples(target: AttackTarget) -> list[DocExample]:
    """The target's docstring examples, doctests first, without repeats."""
    found, seen = [], set()
    for example in [*_doctests(target), *_inline(target)]:
        if example.args not in seen:
            seen.add(example.args)
            found.append(example)
    return found


# --- seeds ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Example:
    phase: Literal["grid", "evidence"]
    args: Args  # may name only some parameters: the runtime completes it from a typical input


@dataclass(frozen=True)
class Seed:
    """A value worth trying for one parameter (the runtime keeps it only if its type fits)."""

    param: str
    value: str  # literal source
    compared: bool = False  # the fix compares this parameter with it (fits even without a hint)


def neighbours(value: object) -> list[object]:
    """Values next to a hard-coded one: what a fix for one value most likely still gets wrong."""
    if type(value) is bool:
        return [not value]
    if type(value) is int:
        assert isinstance(value, int)
        out: list[object] = [value + 1, value - 1]
        zeros = len(str(abs(value))) - len(str(abs(value)).rstrip("0")) if value else 0
        if zeros:
            step = 10**zeros
            out += [value + step, value - step]
        out.append(-value)
        return [v for v in dict.fromkeys(out) if v != value]
    if type(value) is float:
        assert isinstance(value, float)
        return [v for v in dict.fromkeys([value + 1, value - 1, -value, 0.0]) if v != value]
    if type(value) is str:
        assert isinstance(value, str)
        out = ["", value.strip(), value.upper(), value.lower(), f" {value} "]
        return [v for v in dict.fromkeys(out) if v != value]
    if type(value) is bytes:
        return [b""] if value != b"" else []
    return []


_EQUAL = (ast.Eq, ast.Is)
_ANY = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot, ast.In, ast.NotIn)


ATTRIBUTE = f"{RECEIVER}."  # a seed for the constructor parameter named like the attribute
EVERY_ATTRIBUTE = f"{RECEIVER}.*"  # an evidence value for every constructor parameter


def _operand(node: ast.expr, params: set[str], receiver: bool) -> str | None:
    """A parameter the fix compares (`year`), or with `receiver` a public attribute of the
    object (`self.limit`, named "self.limit")."""
    if isinstance(node, ast.Name) and node.id in params:
        return node.id
    if (
        receiver
        and isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == RECEIVER
        and not node.attr.startswith("_")
    ):
        return f"{ATTRIBUTE}{node.attr}"
    return None


def _compared(
    node: ast.Compare, params: set[str], receiver: bool = False
) -> list[tuple[str, object, bool]]:
    """(parameter, value, equality) for `param <op> literal` (either side), and each element of
    `param in (literals)`; with `receiver`, `self.attr` counts as the parameter "self.attr"."""
    if len(node.ops) != 1 or not isinstance(node.ops[0], _ANY):
        return []
    left, right, op = node.left, node.comparators[0], node.ops[0]
    if _operand(right, params, receiver) is not None and not isinstance(op, ast.In | ast.NotIn):
        left, right = right, left
    name = _operand(left, params, receiver)
    if name is None:
        return []
    if isinstance(op, ast.In | ast.NotIn) and isinstance(right, ast.Tuple | ast.List | ast.Set):
        values = [v for v in (_value(e) for e in right.elts) if v is not _NOTHING]
        return [(name, v, isinstance(op, ast.In)) for v in values]
    value = _value(right)
    return [] if value is _NOTHING else [(name, value, isinstance(op, _EQUAL))]


_NOTHING = object()


def _value(node: ast.expr) -> object:
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return _NOTHING
    return value if to_source(value) is not None else _NOTHING


def _function_node(text: str, target: AttackTarget) -> Definition | None:
    """The target's definition in `text` (the last one: the binding the module exports, or for a
    method the one its class exposes; for a property, its getter)."""
    tree = _parse(text)
    if tree is None:
        return None
    if target.owner:
        owners = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == target.owner]
        defs = [
            d
            for d in (class_defs(owners[-1], target.name) if owners else [])
            if isinstance(d, Definition) and (target.kind != "property" or kind_of(d) == "property")
        ]
        return defs[-1] if defs else None
    found = [n for n in tree.body if isinstance(n, Definition) and n.name == target.name]
    return found[-1] if found else None


def fix_seeds(
    target: AttackTarget, head: str, fixed: frozenset[int]
) -> tuple[list[Example], list[Seed]]:
    """The grid and the compared values from the fix's own comparisons in this function.

    Comparisons joined by `and` on a fixed line give one example (`{year: 2100, month: 2}`),
    then that example with one parameter at a time moved to a neighbour (2101, 2099, 2200, 2000,
    -2100 for 2100): a fix that special-cases one value is caught on the next one. Every compared
    value and its neighbours are also seeds for their parameter. For a method, `self.attr <op>
    literal` gives seeds for the constructor parameter named `attr` ("self.attr"), not grid
    inputs: the object is built by the run, which knows the constructor."""
    node = _function_node(head, target)
    if node is None:
        return [], []
    params = {p.name for p in target.params}
    receiver = target.has_receiver
    grid: list[Example] = []
    seeds: list[Seed] = []
    groups: list[list[tuple[str, object]]] = []
    in_and: set[int] = set()

    def equal_params(found: list[tuple[str, object, bool]]) -> list[tuple[str, object]]:
        return [(p, v) for p, v, equal in found if equal and not p.startswith(ATTRIBUTE)]

    for sub in ast.walk(node):
        if isinstance(sub, ast.BoolOp) and isinstance(sub.op, ast.And) and sub.lineno in fixed:
            group = []
            for part in sub.values:
                if isinstance(part, ast.Compare):
                    in_and.add(id(part))
                    group += equal_params(_compared(part, params, receiver))
            if group:
                groups.append(group)
    for compare in ast.walk(node):
        if not isinstance(compare, ast.Compare) or compare.lineno not in fixed:
            continue
        found = _compared(compare, params, receiver)
        for param, value, _ in found:
            for v in [value, *neighbours(value)]:
                source = to_source(v)
                if source is not None:
                    seeds.append(Seed(param, source, compared=True))
        if id(compare) not in in_and:
            groups += [[pair] for pair in equal_params(found)]
    for group in groups:
        base = dict(group)
        grid.append(Example("grid", _args(base, target)))
        for param, value in base.items():
            for near in neighbours(value):
                grid.append(Example("grid", _args({**base, param: near}, target)))
    return _unique(grid), list(dict.fromkeys(seeds))


def _args(values: Mapping[str, object], target: AttackTarget) -> Args:
    order = [p.name for p in target.params]
    return tuple((name, to_source(values[name]) or "None") for name in order if name in values)


def _unique(examples: Iterable[Example]) -> list[Example]:
    return list(dict.fromkeys(examples))


def _literal_tokens(text: str) -> list[str]:
    """Literal sources of the number and string tokens in a piece of code (it may not parse)."""
    found = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type in (tokenize.NUMBER, tokenize.STRING):
                try:
                    source = to_source(ast.literal_eval(token.string))
                except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
                    continue
                if source is not None:
                    found.append(source)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return found


def fix_literals(head: str, fixed: frozenset[int]) -> list[str]:
    """Literals written on the fix's lines of a file."""
    lines = head.split("\n")
    return _literal_tokens("\n".join(lines[n - 1] for n in sorted(fixed) if n <= len(lines)))


def issue_values(issue: str) -> list[str]:
    """Numbers and short quoted strings in the issue text, as literal sources."""
    numbers = [to_source(float(m) if "." in m else int(m)) for m in _NUMBER.findall(issue)]
    quoted = [to_source(next(g for g in m if g)) for m in _QUOTED.findall(issue)]
    kept = [n for n in numbers if n][:MAX_ISSUE_VALUES] + [q for q in quoted if q][
        :MAX_ISSUE_VALUES
    ]
    return list(dict.fromkeys(kept))


def partly_fixed_codes(repro: ReproResult | None) -> list[str]:
    """Test code of repro attempts that were partly fixed (NOTES Q13): the inputs the model
    believed broken that still fail on head."""
    if repro is None:
        return []
    return [a.test_code for a in repro.attempts if a.verdict is Verdict.PARTLY_FIXED]


def _test_calls(codes: Iterable[str], target: AttackTarget) -> list[Args]:
    found = []
    for code in codes:
        tree = _parse(code)
        if tree is not None:
            found += target_calls(tree, target, imports_of(tree))
    return found


@dataclass(frozen=True)
class Seeds:
    """Everything the attack tries for one target before the search."""

    examples: tuple[Example, ...]  # grid first, then evidence calls
    seeds: tuple[Seed, ...]


def seeds_for(
    target: AttackTarget,
    head: str,
    fixed: Mapping[str, frozenset[int]],
    issue: str,
    repro: ReproResult | None,
    survivors: Sequence[str] = (),
) -> Seeds:
    """The grid, the evidence calls and the evidence values for one target.

    `survivors`: replacement text of Guard's surviving mutants in this target's file (Q23)."""
    grid, compared = fix_seeds(target, head, fixed.get(target.path, frozenset()))
    calls = _test_calls([repro.test_code] if repro and repro.test_code else [], target)
    calls += _test_calls(partly_fixed_codes(repro), target)
    if target.owner:  # a method: the issue's own calls also show typical objects (M7.5)
        calls += literal_calls(issue, target)
    evidence = [Example("evidence", args) for args in calls]
    values = [*fix_literals(head, fixed.get(target.path, frozenset())), *issue_values(issue)]
    for code in [*(repro.test_code for repro in [repro] if repro and repro.test_code), *survivors]:
        values += _literal_tokens(code)
    seeds = list(compared)
    for param in target.params:
        unique = list(dict.fromkeys(values))[:MAX_CANDIDATES]
        seeds += [Seed(param.name, v) for v in unique]
    if target.has_receiver:  # every constructor parameter (the run keeps the ones that fit)
        seeds += [Seed(EVERY_ATTRIBUTE, v) for v in list(dict.fromkeys(values))[:MAX_CANDIDATES]]
    return Seeds(tuple(_unique([*grid, *evidence])), tuple(dict.fromkeys(seeds)))


def survivors_in(guard: GuardResult | None, path: str) -> list[str]:
    """Replacement text of Guard's surviving mutants in `path` (report only; never a verdict)."""
    if guard is None:
        return []
    results = [*guard.mutants, *guard.rule_mutants]
    return [
        r.mutant.replacement
        for r in results
        if r.status is MutantStatus.SURVIVED and r.mutant.path == path
    ]

"""M7.5: methods as targets, the static side (attack_methods, attack_inputs and attack_rules for
methods).

Read from `ast` only: no code from the snippets runs (rendered repro files are only compiled;
the end-to-end tests run them in watched copies).
"""

import ast
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from conftest import make_repo

from tracefix.attack_inputs import (
    AttackTarget,
    Param,
    doc_examples,
    evidence_texts,
    fix_seeds,
    imports_of,
    literal_calls,
    seeds_for,
    select_targets,
    target_calls,
)
from tracefix.attack_methods import ABSTRACT, Located, deleted_attributes, fresh_uses, locate
from tracefix.attack_rules import (
    MAX_EXPRESSION,
    args_of,
    check_example,
    check_property,
    check_receiver,
    render_finding,
)
from tracefix.diffscope import compute_scope
from tracefix.prompts.adversary import ArgValue, ExampleProposal, PropertyProposal
from tracefix.workspace import Workspace

CLASSES = '''\
"""Shapes."""
from functools import cached_property


class Box:
    """A box of `limit` items."""

    size_unit = "cm"

    def __init__(self, limit: int = 10) -> None:
        """`limit` is how many items fit."""
        self.limit = limit  # never negative

    def fits(self, n: int) -> bool:
        return n <= self.limit

    @classmethod
    def make(cls, limit: int) -> "Box":
        return cls(limit)

    @staticmethod
    def unit(n: int) -> str:
        return f"{n} cm"

    @property
    def area(self) -> int:
        return self.limit * 2

    @area.setter
    def area(self, value: int) -> None:
        self.limit = value // 2

    @cached_property
    def label(self) -> str:
        return str(self.limit)

    def __eq__(self, other: object) -> bool:
        return self is other

    def __hidden(self, n: int) -> int:
        return n

    def _check(self, n: int) -> None:
        if n < 0:
            raise ValueError(n)

    def put(self, n: int) -> int:
        self._check(n)
        return n

    def take(self, n: int) -> int:
        self._check(n)
        return -n

    def odd(this, n: int) -> int:
        return n

    class Inner:
        def deep(self, n: int) -> int:
            return n

    def outer(self, n: int) -> int:
        def inner(m: int) -> int:
            return m

        return inner(n)

    async def later(self, n: int) -> int:
        return n

    def many(self, n: int):
        yield n
'''


def found(qualname: str, occurrence: int = 0) -> Located | str:
    return locate(ast.parse(CLASSES), qualname, occurrence)


@pytest.mark.parametrize(
    ("qualname", "occurrence", "kind"),
    [
        ("Box.fits", 0, "method"),
        ("Box.make", 0, "classmethod"),
        ("Box.unit", 0, "staticmethod"),
        ("Box.area", 0, "property"),
        ("Box.label", 0, "property"),
        ("Box._check", 0, "method"),
        ("Box.later", 0, "method"),  # async: awaited (M11 early; "async methods" until then)
    ],
)
def test_each_kind_of_method_is_located(qualname: str, occurrence: int, kind: str) -> None:
    where = found(qualname, occurrence)
    assert isinstance(where, Located), where
    assert (where.owner.name, where.node.name, where.kind) == ("Box", qualname[4:], kind)


@pytest.mark.parametrize(
    ("qualname", "occurrence", "reason"),
    [
        ("Box.area", 1, "a property setter or deleter"),
        ("Box.__eq__", 0, "a special method"),
        ("Box.__init__", 0, "a special method"),
        ("Box.__hidden", 0, "a name-mangled private method"),
        ("Box.odd", 0, "its first parameter is not self"),
        ("Box.Inner.deep", 0, "a method of a nested class"),
        ("Box.outer.inner", 0, "a nested function"),
        ("Box.many", 0, "generators"),
        ("Box.missing", 0, "not found in its class"),
    ],
)
def test_what_is_not_called_says_why(qualname: str, occurrence: int, reason: str) -> None:
    where = found(qualname, occurrence)
    assert isinstance(where, str) and where.startswith(reason), where


def test_m11_async_methods_are_located_but_async_properties_and_generators_are_not() -> None:
    text = (
        "class A:\n    @property\n    async def soon(self) -> int:\n        return 1\n\n"
        "    async def ticks(self, n: int):\n        yield n\n\n"
        "    @staticmethod\n    async def later(n: int) -> int:\n        return n\n"
    )
    tree = ast.parse(text)
    assert locate(tree, "A.soon", 0) == "an async property: not called yet"
    assert locate(tree, "A.ticks", 0) == "generators are not attacked yet"
    later = locate(tree, "A.later", 0)
    assert isinstance(later, Located) and later.kind == "staticmethod"
    assert isinstance(later.node, ast.AsyncFunctionDef)


def test_a_property_the_class_redefines_later_is_not_called() -> None:
    text = (
        "class A:\n    @property\n    def x(self) -> int:\n        return 1\n\n"
        "    def x(self) -> int:\n        return 2\n"
    )
    assert locate(ast.parse(text), "A.x", 0) == "a property its class redefines later: not called"


def test_a_method_redefined_later_is_the_last_definition() -> None:
    text = (
        "class A:\n    def x(self, n: int) -> int:\n        return 1\n\n"
        "    def x(self, n: int) -> int:\n        return 2\n"
    )
    where = locate(ast.parse(text), "A.x", 0)
    assert isinstance(where, Located) and where.node.lineno == 5 and where.defined == 2


def box_target(
    name: str, kind: str, params: tuple[Param, ...] = (), **fields: object
) -> AttackTarget:
    target = AttackTarget(
        "t1", "pkg/mod.py", name, params, (1, 1), "", "", "", "", "", (), ("pkg.mod",),
        owner="Box", kind=kind,  # type: ignore[arg-type]
    )  # fmt: skip
    return replace(target, **fields)  # type: ignore[arg-type]


N = (Param("n", "positional", "int", False),)
FITS = box_target("fits", "method", N)
MAKE = box_target("make", "classmethod", (Param("limit", "positional", "int", False),))
AREA = box_target("area", "property")


def calls(test: str, target: AttackTarget) -> list[dict[str, str]]:
    tree = ast.parse(test)
    return [dict(a) for a in target_calls(tree, target, imports_of(tree))]


def test_a_test_vouches_for_an_object_it_builds_fresh_for_the_call() -> None:
    test = (
        "from pkg.mod import Box\n\n\n"
        "def test_direct():\n    assert Box(3).fits(4) is False\n\n\n"
        "def test_named():\n    box = Box(limit=5)\n    assert box.fits(n=2)\n"
    )
    assert calls(test, FITS) == [
        {"self": "'Box(3)'", "n": "4"},
        {"self": "'Box(limit=5)'", "n": "2"},
    ]


def test_an_object_too_long_for_the_run_is_no_witness() -> None:
    # Verifier round 2: one test's long object cut the method's whole diff short.
    def test(limit: str) -> str:
        return f"from pkg.mod import Box\n\n\ndef test_it():\n    assert Box({limit}).fits(4)\n"

    fits = "1" + "0" * (MAX_EXPRESSION - len("Box()") - 1)  # exactly at the limit
    assert calls(test(fits), FITS) == [{"self": repr(f"Box({fits})"), "n": "4"}]
    assert calls(test(fits + "0"), FITS) == []


@pytest.mark.parametrize(
    "body",
    [
        "box = Box(3)\n    box.put(1)\n    assert box.fits(4)",  # another use first
        "box = Box(3)\n    assert box.fits(1) == box.fits(2)",  # two uses in one check
        "box = Box(3)\n    for n in (1, 2):\n        assert box.fits(n)",  # a loop
        "box = Box(3)\n    assert all(box.fits(n) for n in (1, 2))",  # a comprehension
        "box = Box(3)\n    keep(box)\n    assert box.fits(4)",  # passed on first
        "if True:\n        box = Box(3)\n    assert box.fits(4)",  # bound in a block
        "box = Box(n)\n    assert box.fits(4)",  # not a literal object
        "box = make_box()\n    assert box.fits(4)",  # not built by the class
    ],
)
def test_an_object_used_before_or_not_built_here_is_no_witness(body: str) -> None:
    test = f"from pkg.mod import Box\n\n\ndef test_it(n=3):\n    {body}\n"
    assert calls(test, FITS) == []


def test_the_class_is_followed_through_the_imports() -> None:
    aliased = "from pkg.mod import Box as B\n\n\ndef test_it():\n    assert B(3).fits(4)\n"
    module = "import pkg.mod\n\n\ndef test_it():\n    assert pkg.mod.Box(3).fits(4)\n"
    other = "from elsewhere import Box\n\n\ndef test_it():\n    assert Box(3).fits(4)\n"
    assert calls(aliased, FITS) == [{"self": "'Box(3)'", "n": "4"}]  # written with its own name
    assert calls(module, FITS) == [{"self": "'Box(3)'", "n": "4"}]
    assert calls(other, FITS) == []


def test_class_methods_and_properties_in_tests() -> None:
    test = (
        "from pkg.mod import Box\n\n\ndef test_it():\n"
        "    assert Box.make(4).limit == 4\n    assert Box(3).area == 6\n    Box(3).area(1)\n"
    )
    assert calls(test, MAKE) == [{"limit": "4"}]
    assert calls(test, AREA) == [{"self": "'Box(3)'"}]  # a call of the value is no read


def test_fresh_names_end_at_rebinding_and_restart_at_a_new_object() -> None:
    body = ast.parse("box = Box(1)\nbox = Box(2)\nbox.fits(3)\n").body
    fresh = fresh_uses(body, lambda node: isinstance(node, ast.Name) and node.id == "Box")
    (built,) = fresh.values()
    assert ast.unparse(built) == "Box(2)"


def test_method_doctests_one_line_two_lines_and_a_broken_session() -> None:
    doc = """Whether `n` items fit.

    >>> Box(3).fits(4)
    False
    >>> box = Box(5)
    >>> box.fits(2)
    True
    >>> other = Box(1)
    >>> for n in range(2):
    ...     other.fits(n)
    >>> other.fits(9)
    False
    """
    found = [
        (dict(e.args), e.expected, e.compare) for e in doc_examples(replace(FITS, docstring=doc))
    ]
    assert found == [
        ({"self": "'Box(3)'", "n": "4"}, "False", "repr"),
        ({"self": "'Box(5)'", "n": "2"}, "True", "repr"),
    ]


def test_uses_written_in_the_issue() -> None:
    issue = (
        "Box(3).fits(4) says True, and `Box(limit=0).fits(n=1)` too. Box.make(2) works; "
        "Box(3).area is 6. Boxes(1).fits(2) and box.fits(1) are not ours."
    )
    assert literal_calls(issue, FITS) == [
        (("self", "'Box(3)'"), ("n", "4")),
        (("self", "'Box(limit=0)'"), ("n", "1")),
    ]
    assert literal_calls(issue, MAKE) == [(("limit", "2"),)]
    assert literal_calls(issue, AREA) == [(("self", "'Box(3)'"),)]


def test_an_attribute_the_fix_compares_seeds_the_constructor_not_the_grid() -> None:
    head = (
        "class Box:\n    def fits(self, n: int) -> bool:\n"
        "        if self.limit == 10 and n == 3:\n            return True\n"
        "        return n <= self.limit\n"
    )
    grid, seeds = fix_seeds(FITS, head, frozenset({3}))
    assert [dict(e.args) for e in grid] == [{"n": "3"}, {"n": "4"}, {"n": "2"}, {"n": "-3"}]
    attribute = [(s.value, s.compared) for s in seeds if s.param == "self.limit"]
    assert attribute == [("10", True), ("11", True), ("9", True), ("20", True), ("0", True),
                         ("-10", True)]  # fmt: skip
    every = seeds_for(FITS, head, {"pkg/mod.py": frozenset({3})}, "it breaks at 7", None)
    assert ("self.*", "7") in {(s.param, s.value) for s in every.seeds}
    assert ("self.*", "7") not in {
        (s.param, s.value) for s in seeds_for(MAKE, head, {}, "7", None).seeds
    }


def test_select_targets_reads_the_class_and_brings_in_callers_of_a_private_method(
    tmp_path: Path,
) -> None:
    changed = CLASSES.replace("raise ValueError(n)", "raise ValueError(n + 0)")
    changed = changed.replace("return n <= self.limit", "return n < self.limit + 1")
    repo = make_repo(
        tmp_path / "r", [{"pkg/__init__.py": "", "pkg/mod.py": CLASSES}, {"pkg/mod.py": changed}]
    )
    with Workspace(repo, "c0", "c1") as ws:
        targets, skipped, _ = select_targets(ws, compute_scope(ws.repo, ws.base_sha, ws.head_sha))
    assert not skipped
    assert [(t.qualname, t.via) for t in targets] == [
        ("Box.fits", ""),
        ("Box._check", ""),
        ("Box.put", "a public caller of the changed Box._check"),
        ("Box.take", "a public caller of the changed Box._check"),
    ]
    fits = targets[0]
    assert fits.init_params is not None and [p.name for p in fits.init_params] == ["limit"]
    assert 'size_unit = "cm"' in fits.owner_context and "def __init__" in fits.owner_context
    assert '    def make(cls, limit: int) -> "Box":\n        ...' in fits.owner_context
    assert "def _check" not in fits.owner_context  # private methods are not shown
    texts = evidence_texts(fits, "", "", "")
    assert "A box of `limit` items." in texts["docstring"]
    assert "`limit` is how many items fit." in texts["docstring"]
    assert "never negative" in texts["comment"]
    assert "class Box:" in texts["signature"]


# --- hygiene and repro files (attack_rules) -------------------------------------------------------

QUOTE = "never more than the limit"
SPOKEN = replace(
    FITS,
    docstring=f"Whether `n` items fit: {QUOTE}.",
    module_names=(("Box", "class Box"), ("helper", "def helper(n)")),
)
EVIDENCE: Any = {
    "t1": {
        "docstring": (SPOKEN.docstring,),
        "issue": (),
        "comment": (),
        "docs": (),
        "signature": (),
        "test": (),
    }
}


def proposal(**fields: Any) -> PropertyProposal:
    base = {
        "function": "t1",
        "name": "p",
        "kind": "returns",
        "claim": "A rule.",
        "source": "docstring",
        "quote": QUOTE,
        "when": "True",
        "check": "",
        "expected": "",
        "exceptions": [],
        "transform": "",
    }
    return PropertyProposal(**(base | fields))


def prop(target: AttackTarget = SPOKEN, **fields: Any) -> Any:
    return check_property(proposal(**fields), [target], EVIDENCE, frozenset({"math"}), "t1.p1")


@pytest.mark.parametrize(
    "text", ["Box(3)", "Box(limit=3)", "Box(math.floor(2.5))", "helper(Box(1))", " Box() "]
)
def test_an_objects_code_is_a_hygienic_call(text: str) -> None:
    names, modules = check_receiver(text, SPOKEN, frozenset({"math"}))
    assert set(names) <= {"Box", "helper"} and set(modules) <= {"math"}


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("Box", "must be a call"),
        ("[Box(1)][0]", "must be a call"),
        ("Box(3).fits(1)", "calls fits itself"),
        ("Box(3).__class__(4)", "attribute __class__"),
        ("open('x')", "not available"),
        ("Box(self)", "not available"),
        ("Box(result)", "not available"),
        ("Box(lambda: 1)", "Lambda"),
        ("Box(", "not a Python expression"),
    ],
)
def test_an_objects_code_that_breaks_a_rule_is_refused(text: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        check_receiver(text, SPOKEN, frozenset())


def test_a_class_or_static_method_takes_no_object() -> None:
    with pytest.raises(ValueError, match="not called on an object"):
        check_receiver("Box(1)", replace(MAKE, module_names=SPOKEN.module_names), frozenset())


def test_properties_see_self_before_the_call_and_self_after_after_it() -> None:
    assert prop(when="self.limit >= 0", check="result == (n <= self.limit)").names == ()
    assert prop(check="self_after.limit == self.limit").check  # an effect on the object counts
    assert prop(expected="n <= self.limit").expected
    with pytest.raises(ValueError, match="self_after"):
        prop(when="self_after.limit > 0", check="result")  # `when` runs before the call
    with pytest.raises(ValueError, match="never looks at the result"):
        prop(check="self.limit > 0")
    with pytest.raises(ValueError, match="calls fits itself"):
        prop(check="result == self.fits(n)")
    clash = replace(SPOKEN, params=(Param("self_after", "positional", "", False),))
    with pytest.raises(ValueError, match="reserved names"):
        prop(clash, check="result")


def test_a_function_still_has_no_self() -> None:
    with pytest.raises(ValueError, match="not available: self"):
        prop(replace(SPOKEN, owner="", kind="function"), check="result == self")


def test_the_model_gives_an_object_as_code_in_its_examples() -> None:
    example = ExampleProposal(
        function="t1",
        args=[ArgValue(param="n", value="4"), ArgValue(param="self", value="Box( 3 )")],
        why="small",
    )
    assert check_example(example, [SPOKEN]) == ("t1", (("self", "'Box(3)'"), ("n", "4")))
    bad = ExampleProposal(function="t1", args=[ArgValue(param="self", value="Box")], why="")
    with pytest.raises(ValueError, match="must be a call"):
        check_example(bad, [SPOKEN])
    with pytest.raises(ValueError, match="has no parameter 'self'"):
        check_example(bad.model_copy(update={"function": "Box.make"}), [MAKE])


def test_an_objects_code_is_checked_as_it_is_kept() -> None:
    # Verifier round 1, S1: 388 characters as given, over 400 once unparse adds the spaces.
    tight = "Box(" + ",".join(["1"] * 192) + ")"
    assert len(tight) <= MAX_EXPRESSION < len(ast.unparse(ast.parse(tight, mode="eval")))
    example = ExampleProposal(function="t1", args=[ArgValue(param="self", value=tight)], why="")
    with pytest.raises(ValueError, match="longer than 400"):
        check_example(example, [SPOKEN])


def test_an_input_back_from_a_run_needs_its_object_and_a_clean_one() -> None:
    assert args_of({"self": "'Box(3)'", "n": "4"}, SPOKEN) == (("self", "'Box(3)'"), ("n", "4"))
    assert args_of({"n": "4"}, SPOKEN) is None  # no object to call it on
    assert args_of({"self": "'__import__(1)'", "n": "4"}, SPOKEN) is None  # forged
    assert args_of({"self": "3", "n": "4"}, SPOKEN) is None  # not code
    assert args_of({"self": "'Box(3)'"}, MAKE) is None  # a class method has no object
    assert args_of({"limit": "4"}, MAKE) == (("limit", "4"),)


def test_a_method_finding_builds_its_object_and_calls_the_method_on_it() -> None:
    outcome = {"kind": "returned", "type": "bool"}
    p = prop(check="result == (n <= self.limit)")
    code = render_finding(1, "pkg.mod", SPOKEN, p, (("self", "'Box( 3 )'"), ("n", "4")), outcome)
    compile(code.code, "f.py", "exec")
    assert "import copy\n" in code.code and "from pkg.mod import Box\n" in code.code
    built = "    self_after = Box(3)\n    self = copy.deepcopy(self_after)\n    n = 4\n"
    assert built in code.code
    called = "    result = self_after.fits(n=n)\n    assert (result == (n <= self.limit))\n"
    assert called in code.code
    assert "generated by Tracefix: Box.fits returns a wrong value" in code.code
    args = (("self", "'Box(3)'"), ("n", "4"))
    after_only = render_finding(2, "pkg.mod", SPOKEN, prop(check="result or self_after.limit"),
                                args, outcome)  # fmt: skip
    assert "copy" not in after_only.code  # no copy unless a check reads `self`
    with pytest.raises(ValueError, match="no object"):
        render_finding(3, "pkg.mod", SPOKEN, p, (("n", "4"),), outcome)
    with pytest.raises(ValueError, match="not available"):
        render_finding(4, "pkg.mod", SPOKEN, p, (("self", "'open(1)'"), ("n", "4")), outcome)


def test_class_methods_properties_and_relations_render_too() -> None:
    make = replace(MAKE, module_names=SPOKEN.module_names, docstring=SPOKEN.docstring)
    p = prop(make, kind="raises_only")
    code = render_finding(1, "pkg.mod", make, p, (("limit", "-1"),),
                          {"kind": "raised", "type": "ValueError"}).code  # fmt: skip
    assert "from pkg.mod import Box\n" in code and "    result = Box.make(limit=limit)\n" in code
    compile(code, "f.py", "exec")
    area = replace(AREA, module_names=SPOKEN.module_names, docstring=SPOKEN.docstring)
    p = prop(area, when="self.limit >= 0", check="result == 2 * self_after.limit")
    code = render_finding(2, "pkg.mod", area, p, (("self", "'Box(3)'"),),
                          {"kind": "returned", "type": "int"}).code  # fmt: skip
    assert "    self_after = Box(3)\n" in code and "    result = self_after.area\n" in code
    compile(code, "f.py", "exec")
    relation = prop(kind="relation", check="result2 == result", transform="{'n': n}")
    code = render_finding(3, "pkg.mod", SPOKEN, relation, (("self", "'Box(3)'"), ("n", "4")),
                          {"kind": "returned", "type": "bool"}).code  # fmt: skip
    assert "    result2 = Box(3).fits(**{'n': n, **({'n': n})})\n" in code  # a fresh object
    compile(code, "f.py", "exec")


# --- M11 S5: abstract methods, and attributes a class deletes -------------------------------------

NOT_SELF = "its first parameter is not self: not called yet"
ABSTRACTS = """\
import abc
from abc import ABC, abstractmethod


class Reference(ABC):
    @abstractmethod
    def plain(self, x):
        return x

    @abc.abstractmethod
    def dotted(self, x):
        return x

    @staticmethod
    @abstractmethod
    def static(x):
        return x

    @classmethod
    @abstractmethod
    def built(cls, x):
        return x

    @property
    @abstractmethod
    def size(self):
        return 1

    @abc.abstractproperty
    def old_size(self):
        return 1

    @abc.abstractclassmethod
    def old_built(cls, x):
        return x

    @abc.abstractstaticmethod
    def old_static(x):
        return x

    @abstractmethod
    def _hook(self, x):
        return x

    def uses_hook(self, x):
        return self._hook(x)

    def concrete(self, x):
        return x


class Real(Reference):
    def plain(self, x):
        return x + 1
"""


def test_s5_abstract_methods_are_skipped_with_the_reason_and_an_override_is_not(
    tmp_path: Path,
) -> None:
    head = ABSTRACTS.replace("return x", "return (x)").replace("return 1", "return (1)")
    repo = make_repo(tmp_path / "r", [{"pkg/__init__.py": "", "pkg/mod.py": ABSTRACTS},
                                      {"pkg/mod.py": head}])  # fmt: skip
    with Workspace(repo, "c0", "c1") as ws:
        targets, skipped, _ = select_targets(ws, compute_scope(ws.repo, ws.base_sha, ws.head_sha))
    names = ("plain", "dotted", "static", "built", "size", "old_size", "_hook")
    reasons = {s.function: s.reason for s in skipped}
    assert {f"Reference.{n}": reasons[f"Reference.{n}"] for n in names} == {
        f"Reference.{n}": ABSTRACT for n in names
    }
    # The other old spellings never get this far: `locate` reads them as methods without `self`.
    assert reasons["Reference.old_built"] == reasons["Reference.old_static"] == NOT_SELF
    # An abstract private method brings in no public callers: only what is concrete is attacked.
    assert {t.qualname for t in targets} == {"Reference.concrete", "Real.plain"}


DELETES = """\
from somewhere import Outside


class Root:
    def tidy(self):
        del self.from_root


class Base(Root):
    def finalize(self):
        del self.single, self.pair
        del self.__dict__["in_dict"]
        delattr(self, "by_call")

    def looping(self):
        for key in ["in_loop", "in_loop_2"]:
            del self.__dict__[key]
        for name in ("by_call_loop",):
            delattr(self, name)

    def not_deletions(self, other, keys):
        del self.items[0]
        del self.table["in_table"]
        del other.elsewhere
        delattr(other, "elsewhere_too")
        for key in keys:
            del self.__dict__[key]
        for key in ["not_deleted"]:
            print(key)
        self.kept = None

    class Inner:
        def own(self):
            del self.nested


class Child(Base):
    def __init__(self):
        del self.from_child


class Stranger:
    def go(self):
        del self.from_stranger


class FromOutside(Outside, Base):
    pass
"""


@pytest.mark.parametrize(
    ("start", "attribute", "deleted"),
    [
        ("Base", "single", True),
        ("Base", "pair", True),
        ("Base", "in_dict", True),
        ("Base", "by_call", True),
        ("Base", "in_loop", True),
        ("Base", "in_loop_2", True),
        ("Base", "by_call_loop", True),
        ("Base", "from_root", True),  # its base's method runs on the object too
        ("Child", "from_child", True),
        ("Child", "single", True),
        ("Child", "from_root", True),
        ("FromOutside", "single", True),  # a base in another file is simply not read
        ("Base", "from_child", False),  # a subclass's code doesn't run on a Base
        ("Base", "items", False),
        ("Base", "table", False),
        ("Base", "in_table", False),
        ("Base", "elsewhere", False),
        ("Base", "elsewhere_too", False),
        ("Base", "not_deleted", False),
        ("Base", "kept", False),
        ("Base", "nested", False),
        ("Base", "from_stranger", False),
        ("Missing", "single", False),
    ],
)
def test_s5_attributes_a_class_deletes(start: str, attribute: str, deleted: bool) -> None:
    assert (attribute in deleted_attributes(ast.parse(DELETES), start)) is deleted

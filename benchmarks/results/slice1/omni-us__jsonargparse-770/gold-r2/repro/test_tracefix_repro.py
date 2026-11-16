import ast
import types
from typing import Union

from jsonargparse._stubs_resolver import StubsResolver


def test_self_referencing_stub_assign_does_not_recurse():
    resolver = StubsResolver()
    assign = ast.parse("T = Union[T, int]").body[0]
    resolver.get_module_stub_assigns = lambda module_path: {"T": assign}
    resolver.get_module_stub_imports = lambda module_path: {}
    module = types.SimpleNamespace(Union=Union)
    aliases = {}
    resolver.add_module_aliases(aliases, "fake_module_for_test", module, assign.value)
    assert "Union" in aliases

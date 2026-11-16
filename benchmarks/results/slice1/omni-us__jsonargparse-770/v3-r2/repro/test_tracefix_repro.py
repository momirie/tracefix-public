import importlib
import logging
import sys

from jsonargparse import _common, _stubs_resolver
from jsonargparse._parameter_resolvers import get_parameters_from_stubs


def test_stubs_resolver_py_files(tmp_path, monkeypatch):
    (tmp_path / "pyonly_mod_xyz.py").write_text(
        "def g(x: int, y: str = 'a'):\n    pass\n\ng.__signature__ = 1\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    monkeypatch.setitem(_common.parsing_settings, "stubs_resolver_allow_py_files", True)
    monkeypatch.setattr(_stubs_resolver, "stubs_resolver", None)
    try:
        mod = importlib.import_module("pyonly_mod_xyz")
        params = get_parameters_from_stubs(mod.g, None, logging.getLogger("t"))
        assert params is not None
        assert [p.name for p in params] == ["x", "y"]
        assert [p.annotation for p in params] == [int, str]
    finally:
        sys.modules.pop("pyonly_mod_xyz", None)
        _stubs_resolver.stubs_resolver = None

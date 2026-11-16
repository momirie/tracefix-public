import inspect
import logging

import jsonargparse._common as common
import jsonargparse._stubs_resolver as sr
from jsonargparse._parameter_resolvers import get_parameters_from_stubs


def test_stubs_resolver_finds_params_in_py_file(monkeypatch):
    from _pytest.pathlib import bestrelpath

    real_signature = inspect.signature

    def fake_signature(obj, *args, **kwargs):
        if obj is bestrelpath:
            raise ValueError("no signature")
        return real_signature(obj, *args, **kwargs)

    monkeypatch.setattr(inspect, "signature", fake_signature)
    monkeypatch.setitem(common.parsing_settings, "stubs_resolver_allow_py_files", True)
    monkeypatch.setattr(sr, "stubs_resolver", None)
    try:
        params = get_parameters_from_stubs(bestrelpath, None, logging.getLogger("test"))
    finally:
        sr.stubs_resolver = None
    assert params is not None
    assert [p.name for p in params] == ["directory", "dest"]

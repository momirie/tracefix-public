import pytest

from jsonargparse import set_parsing_settings
from jsonargparse._common import parsing_settings
from jsonargparse._parameter_resolvers import get_signature_parameters


def test_stubs_resolver_allow_py_files_setting(monkeypatch):
    import jsonargparse._stubs_resolver as sr

    monkeypatch.setitem(parsing_settings, "stubs_resolver_allow_py_files", False)
    monkeypatch.setattr(sr, "stubs_resolver", None)
    set_parsing_settings(stubs_resolver_allow_py_files=True)
    assert parsing_settings["stubs_resolver_allow_py_files"] is True
    import calendar

    params = get_signature_parameters(calendar.Calendar, "formatweekday")
    assert isinstance(params, list)

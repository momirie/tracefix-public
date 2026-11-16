import sys
import types

import pytest


def _make_module():
    src = '''
class NestedClass:
    """Parent class"""
    class Foo:
        """Nested class"""
        def foo(self):
            """Nested method"""
            pass


class Attribute:
    """Attribute"""
    #: Alias
    foo = NestedClass.Foo
    #: Attribute
    bar = 'bar'
'''
    return src


def test_alias_not_expanded(tmp_path):
    from sphinx.application import Sphinx

    srcdir = tmp_path / 'src'
    srcdir.mkdir()
    (srcdir / 'aliasmod.py').write_text(_make_module())
    (srcdir / 'conf.py').write_text(
        "import sys\nsys.path.insert(0, %r)\n"
        "extensions = ['autodocsumm']\nmaster_doc = 'index'\n" % str(srcdir))
    (srcdir / 'index.rst').write_text(
        'Test\n====\n\n.. autoclass:: aliasmod.Attribute\n'
        '   :members:\n   :autosummary:\n   :autosummary-no-titles:\n')
    out = tmp_path / 'out'
    app = Sphinx(str(srcdir), str(srcdir), str(out), str(tmp_path / 'dt'),
                 'text', status=None, warning=None)
    try:
        app.build()
    finally:
        sys.modules.pop('aliasmod', None)
    text = (out / 'index.txt').read_text()
    assert 'Nested method' not in text

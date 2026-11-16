import sys
import os
import pytest


def test_alias_not_expanded(tmp_path):
    from sphinx.application import Sphinx

    src = tmp_path / 'src'
    src.mkdir()
    (src / 'aliasmod.py').write_text(
        'class NestedClass:\n'
        '    """Parent class"""\n'
        '    class Foo:\n'
        '        """Nested class"""\n'
        '        def foo(self):\n'
        '            """Nested method foo"""\n'
        '        def barmethod(self):\n'
        '            """Nested method bar"""\n'
        '\n'
        'class Attribute:\n'
        '    """Attribute"""\n'
        '    #: Alias\n'
        '    foo = NestedClass.Foo\n'
        '    #: Attribute\n'
        '    bar = "bar"\n')
    (src / 'conf.py').write_text(
        'import sys, os\n'
        'sys.path.insert(0, os.path.abspath("."))\n'
        "extensions = ['autodocsumm']\n"
        "master_doc = 'index'\n"
        "autodoc_default_options = {'members': True, 'autosummary': True}\n")
    (src / 'index.rst').write_text(
        'Test\n====\n\n.. autoclass:: aliasmod.Attribute\n')
    sys.path.insert(0, str(src))
    try:
        out = tmp_path / 'out'
        app = Sphinx(str(src), str(src), str(out), str(tmp_path / 'dt'),
                     'text', status=None, warning=None, freshenv=True)
        app.build()
    finally:
        sys.path.remove(str(src))
        sys.modules.pop('aliasmod', None)
    text = (out / 'index.txt').read_text()
    assert 'Nested method' not in text
    assert 'barmethod' not in text

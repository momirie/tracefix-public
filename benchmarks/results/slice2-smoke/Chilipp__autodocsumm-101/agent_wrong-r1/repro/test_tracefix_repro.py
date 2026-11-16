import sys
import types

import pytest


def test_alias_nested_class_not_expanded(tmp_path):
    from sphinx.application import Sphinx

    src = tmp_path / 'src'
    src.mkdir()
    (src / 'aliasmod.py').write_text(
        'class NestedClass:\n'
        '    """Parent class"""\n'
        '    class Foo:\n'
        '        """Nested class"""\n'
        '        def foo(self):\n'
        '            """Nested method"""\n'
        '        def bar(self):\n'
        '            """Nested method"""\n'
        '\n'
        'class Attribute:\n'
        '    """Attribute"""\n'
        '    #: Alias\n'
        '    foo = NestedClass.Foo\n'
        '    #: Attribute\n'
        '    bar = "bar"\n'
    )
    (src / 'conf.py').write_text(
        'import sys\n'
        'sys.path.insert(0, %r)\n'
        "extensions = ['autodocsumm']\n"
        "master_doc = 'index'\n"
        "autodoc_default_options = {'autosummary': True, 'members': True}\n"
        % str(src)
    )
    (src / 'index.rst').write_text(
        'Test\n====\n\n.. autoclass:: aliasmod.Attribute\n'
    )
    sys.path.insert(0, str(src))
    try:
        out = tmp_path / 'out'
        app = Sphinx(str(src), str(src), str(out), str(tmp_path / 'dt'),
                     'text', status=None, warning=None, freshenv=True)
        app.build()
        text = (out / 'index.txt').read_text()
    finally:
        sys.path.remove(str(src))
        sys.modules.pop('aliasmod', None)
    assert 'Nested method' not in text

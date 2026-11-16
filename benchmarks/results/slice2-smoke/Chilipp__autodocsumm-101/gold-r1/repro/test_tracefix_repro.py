import os
import sys
import textwrap

import pytest


def test_alias_not_expanded(tmp_path):
    from sphinx.application import Sphinx

    src = tmp_path / 'src'
    src.mkdir()
    (src / 'aliasmod_repro.py').write_text(textwrap.dedent('''
        class NestedClass:
            """Parent class"""
            class Foo:
                """Nested class"""
                def foo(self):
                    """Nested method"""
                    pass

                def bar(self):
                    """Nested method"""
                    pass

        class Attribute:
            """Attribute"""
            #: Alias
            foo = NestedClass.Foo
            #: Attribute
            bar = 'bar'
    '''))
    (src / 'conf.py').write_text(textwrap.dedent('''
        import sys, os
        sys.path.insert(0, os.path.dirname(__file__))
        extensions = ['autodocsumm']
        master_doc = 'index'
        autodoc_default_options = {'autosummary': True, 'members': True}
    '''))
    (src / 'index.rst').write_text(textwrap.dedent('''
        Test
        ====

        .. autoclass:: aliasmod_repro.Attribute
            :members:
            :autosummary:
    '''))
    out = tmp_path / 'out'
    app = Sphinx(str(src), str(src), str(out), str(out / '.doctrees'),
                 'text', status=None, warning=None, freshenv=True)
    try:
        app.build()
    finally:
        sys.modules.pop('aliasmod_repro', None)
        if str(src) in sys.path:
            sys.path.remove(str(src))
    text = (out / 'index.txt').read_text()
    # the alias must not list the nested class's methods in an autosummary
    assert 'Nested method' not in text

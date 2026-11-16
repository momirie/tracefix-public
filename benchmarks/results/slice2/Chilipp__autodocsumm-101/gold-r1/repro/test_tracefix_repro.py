import sys
import textwrap

from sphinx.application import Sphinx


def test_alias_not_expanded(tmp_path):
    src = tmp_path / 'src'
    src.mkdir()
    (src / 'aliasmod_x.py').write_text(textwrap.dedent('''
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
        import sys
        sys.path.insert(0, %r)
        extensions = ['autodocsumm']
        master_doc = 'index'
        autodoc_default_options = {'autosummary': True, 'members': True}
    ''' % str(src)))
    (src / 'index.rst').write_text(
        'Test\n====\n\n.. autoclass:: aliasmod_x.Attribute\n')
    sys.path.insert(0, str(src))
    try:
        out = tmp_path / 'out'
        app = Sphinx(str(src), str(src), str(out), str(tmp_path / 'dt'),
                     'text', status=None, warning=None, freshenv=True)
        app.build()
    finally:
        sys.path.remove(str(src))
        sys.modules.pop('aliasmod_x', None)
    text = (out / 'index.txt').read_text()
    assert 'alias of' in text
    # the alias must not get its own summary of the nested class members
    assert text.count('Methods:') == 0
    assert 'Nested method' not in text

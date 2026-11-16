import sys
import textwrap

from sphinx.application import Sphinx


def test_alias_not_expanded(tmp_path):
    src = tmp_path / 'src'
    src.mkdir()
    (src / 'aliasmod.py').write_text(textwrap.dedent('''
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
        master_doc = 'index'
        extensions = ['autodocsumm']
        autodoc_default_options = {'autosummary': True, 'members': True}
    ''' % str(src)))
    (src / 'index.rst').write_text(
        'Test\n====\n\n.. autoclass:: aliasmod.Attribute\n   :members:\n   :undoc-members:\n')
    out = tmp_path / 'out'
    sys.path.insert(0, str(src))
    try:
        app = Sphinx(str(src), str(src), str(out), str(out / '.doctrees'),
                     'text', status=None, warning=None, freshenv=True)
        app.build()
    finally:
        sys.path.remove(str(src))
        sys.modules.pop('aliasmod', None)
    text = (out / 'index.txt').read_text()
    assert 'Nested method' not in text

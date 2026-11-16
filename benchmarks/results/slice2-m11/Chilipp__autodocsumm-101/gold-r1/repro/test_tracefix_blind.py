import sys
import textwrap


def test_alias_not_expanded(tmp_path):
    from sphinx.application import Sphinx

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

                def nestedbar(self):
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
    '''))
    (src / 'index.rst').write_text(
        'Test\n====\n\n.. autoclass:: aliasmod.Attribute\n'
        '   :members:\n   :autosummary:\n   :undoc-members:\n')
    sys.path.insert(0, str(src))
    try:
        out = tmp_path / 'out'
        app = Sphinx(str(src), str(src), str(out), str(out / '.doctrees'),
                     'html', status=None, warning=None, freshenv=True)
        app.build()
    finally:
        sys.path.remove(str(src))
        sys.modules.pop('aliasmod', None)
    text = (out / 'index.html').read_text()
    assert 'nestedbar' not in text

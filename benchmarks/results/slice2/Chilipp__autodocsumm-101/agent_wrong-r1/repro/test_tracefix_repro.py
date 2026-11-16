import sys


def test_alias_to_nested_class_not_expanded(tmp_path):
    from sphinx.application import Sphinx

    src = tmp_path / 'src'
    src.mkdir()
    (src / 'aliasmod3.py').write_text(
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
        '    bar = "bar"\n')
    (src / 'conf.py').write_text(
        'import sys, os\n'
        'sys.path.insert(0, os.path.abspath("."))\n'
        "extensions = ['autodocsumm']\n"
        "master_doc = 'index'\n"
        "autodoc_default_options = {'autosummary': True, 'members': True}\n")
    (src / 'index.rst').write_text(
        'Test\n====\n\n.. autoclass:: aliasmod3.Attribute\n')
    out = tmp_path / 'out'
    doctree = tmp_path / 'doctrees'
    app = Sphinx(str(src), str(src), str(out), str(doctree), 'html',
                 status=None, warning=None, freshenv=True)
    try:
        app.build()
    finally:
        sys.modules.pop('aliasmod3', None)
        sys.path[:] = [p for p in sys.path if p != str(src)]
    html = (out / 'index.html').read_text()
    # Attribute has no methods; a 'Methods' section would come from the
    # expanded nested class behind the alias
    assert 'Methods:' not in html
    assert 'Nested method' not in html

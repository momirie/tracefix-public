import sys
from pathlib import Path

from sphinx.testing.util import SphinxTestApp


def test_alias_not_expanded(tmp_path):
    src = tmp_path / 'src'
    src.mkdir()
    (src / 'aliasmod_repro.py').write_text(
        'class NestedClass:\n'
        '    """Parent class"""\n'
        '    class Foo:\n'
        '        """Nested class"""\n'
        '        def foo(self):\n'
        '            """Nested method foo"""\n'
        '        def bar(self):\n'
        '            """Nested method bar"""\n'
        '\n'
        'class Attribute:\n'
        '    """Attribute"""\n'
        '    #: Alias\n'
        '    foo = NestedClass.Foo\n'
        '    #: Attribute\n'
        '    bar = "bar"\n')
    (src / 'conf.py').write_text(
        "import sys\nsys.path.insert(0, %r)\n"
        "extensions = ['autodocsumm']\n"
        "master_doc = 'index'\n"
        "autodoc_default_options = {'autosummary': True, 'members': True}\n"
        % str(src))
    (src / 'index.rst').write_text(
        'Test\n====\n\n.. autoclass:: aliasmod_repro.Attribute\n')
    sys.path.insert(0, str(src))
    try:
        app = SphinxTestApp(srcdir=Path(str(src)))
        try:
            app.build()
            html = (Path(str(app.outdir)) / 'index.html').read_text()
        finally:
            app.cleanup()
    finally:
        sys.path.remove(str(src))
        sys.modules.pop('aliasmod_repro', None)
    assert 'Nested method foo' not in html
    assert 'Nested method bar' not in html

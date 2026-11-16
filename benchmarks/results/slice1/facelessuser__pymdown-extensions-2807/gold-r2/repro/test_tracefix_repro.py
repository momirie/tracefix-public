import markdown
from pymdownx.arithmatex import ArithmatexExtension


def test_inline_double_dollar_not_nested():
    md = markdown.Markdown(extensions=[ArithmatexExtension()])
    out = md.convert('hello $$x$$')
    assert out.count('<script') == 1
    assert out.count('class="arithmatex"') == 1
    assert out.count('MathJax_Preview') == 1


def test_inline_double_dollar_no_preview_not_nested():
    md = markdown.Markdown(extensions=[ArithmatexExtension()], extension_configs={'pymdownx.arithmatex': {'preview': False}})
    out = md.convert('hello $$x$$')
    assert out.count('<script') == 1
    assert out.count('class="arithmatex"') == 1

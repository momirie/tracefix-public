import markdown
from pymdownx.arithmatex import ArithmatexExtension


def test_inline_double_dollar_not_nested():
    md = markdown.Markdown(extensions=[ArithmatexExtension()])
    out = md.convert('hello $$x$$')
    expected = '<p>hello <span class="arithmatex"><span class="MathJax_Preview">x</span><script type="math/tex">x</script></span></p>'
    assert out == expected


def test_inline_double_dollar_not_nested_no_preview():
    md = markdown.Markdown(extensions=[ArithmatexExtension()], extension_configs={'pymdownx.arithmatex': {'preview': False}})
    out = md.convert('hello $$x$$')
    assert out.count('class="arithmatex"') == 1
    assert out.count('<script') == 1

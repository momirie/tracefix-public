from markdownify import markdownify as md


def test_comment_only_is_dropped():
    assert md("<!-- This is a comment -->") == ""


def test_comment_between_text_is_dropped():
    result = md("<p>Hello<!-- hidden note --> world</p>")
    assert "hidden note" not in result
    assert "Hello" in result and "world" in result

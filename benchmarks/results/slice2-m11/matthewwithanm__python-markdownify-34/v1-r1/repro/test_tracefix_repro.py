from markdownify import markdownify as md


def test_comments_are_excluded():
    assert md("<!-- This is a comment -->") == ""


def test_comment_inside_text_is_excluded():
    out = md("<p>Hello<!-- hidden note --> world</p>")
    assert "hidden note" not in out
    assert "Hello" in out and "world" in out

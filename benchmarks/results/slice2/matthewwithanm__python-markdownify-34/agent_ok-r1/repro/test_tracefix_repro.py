from markdownify import markdownify as md


def test_comments_excluded():
    assert md("<!-- This is a comment -->") == ""


def test_comment_inside_text_excluded():
    out = md("<p>Hello<!-- hidden --> world</p>")
    assert "hidden" not in out
    assert "Hello" in out and "world" in out

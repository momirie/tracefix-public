from markdownify import markdownify as md


def test_comments_are_excluded():
    assert md("<!-- This is a comment -->") == ""


def test_comment_inside_tag_is_excluded():
    assert "comment" not in md("<p>Hello <!-- a comment --> world</p>")

from datetime import datetime

from pre_commit_hooks.insert_license import try_update_year_range


def test_all_year_lines_updated_in_one_run(tmp_path):
    year = datetime.now().year
    old = year - 1
    lines = [
        "/* Copyright (c) 2012-%d Dummy             */\n" % old,
        "/*********************************************/\n",
        "/* @copyright Copyright (c) 2012-%d Dummy  */\n" % old,
    ]
    path = tmp_path / "f.php"
    path.write_text("".join(lines))
    content, updated = try_update_year_range(list(lines), str(path), 0, 3)
    assert updated
    assert "2012-%d" % year in content[0]
    assert "2012-%d" % year in content[2]

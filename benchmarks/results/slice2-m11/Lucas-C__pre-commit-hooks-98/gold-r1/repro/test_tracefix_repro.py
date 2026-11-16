from datetime import datetime

from pre_commit_hooks.insert_license import try_update_year_range


def test_all_license_lines_updated_in_one_run(tmp_path):
    year = datetime.now().year
    lines = [
        "/* Copyright (c) 2012-2023 Dummy             */\n",
        "/*********************************************/\n",
        "/* @copyright Copyright (c) 2012-2023 Dummy  */\n",
    ]
    path = tmp_path / "a.php"
    path.write_text("".join(lines))
    content, changed = try_update_year_range(list(lines), str(path), 0, 3)
    assert changed
    assert "2012-%d" % year in content[0]
    assert "2012-%d" % year in content[2]
    assert "2023" not in content[0]
    assert "2023" not in content[2]

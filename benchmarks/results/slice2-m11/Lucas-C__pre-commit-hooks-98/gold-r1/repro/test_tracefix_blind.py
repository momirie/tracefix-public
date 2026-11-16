from datetime import datetime

from pre_commit_hooks.insert_license import try_update_year_range


def test_all_year_lines_updated_in_one_run(tmp_path):
    year = datetime.now().year
    lines = [
        "/* Copyright (c) 2012-2023 Dummy             */\n",
        "/*********************************************/\n",
        "/* @copyright Copyright (c) 2012-2023 Dummy  */\n",
    ]
    result, updated = try_update_year_range(list(lines), str(tmp_path / "a.php"), 0, 3)
    assert updated
    assert str(year) in result[0]
    assert str(year) in result[2]
    assert "2023 " not in result[2]

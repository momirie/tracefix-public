from datetime import datetime

from pre_commit_hooks.insert_license import main


def test_all_year_lines_updated_in_one_run(tmp_path):
    year = datetime.now().year
    lic = tmp_path / "LICENSE.txt"
    lic.write_text(
        "Copyright (c) 2012-%d Dummy\n----\nCopyright (c) 2012-%d Dummy\n" % (year, year)
    )
    src = tmp_path / "a.py"
    src.write_text(
        "# Copyright (c) 2012-2020 Dummy\n# ----\n# Copyright (c) 2012-2020 Dummy\n\ncode = 1\n"
    )
    main(["--license-filepath", str(lic), "--use-current-year", str(src)])
    content = src.read_text()
    assert "2020" not in content
    assert content.count("2012-%d" % year) == 2

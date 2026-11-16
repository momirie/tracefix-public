from sqllineage.runner import LineageRunner


def test_ansi89_join_source_tables():
    runner = LineageRunner("select a.* from tab1 a, tab2 b")
    assert runner.target_tables == []
    names = sorted(str(t).split(".")[-1] for t in runner.source_tables)
    assert names == ["tab1", "tab2"]

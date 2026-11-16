from sqllineage.runner import LineageRunner


def test_ansi89_join_source_tables():
    runner = LineageRunner("select a.* from table1 a, table2 b")
    assert runner.target_tables == []
    assert sorted(str(t) for t in runner.source_tables) == ["<default>.table1", "<default>.table2"] or sorted(str(t).split(".")[-1] for t in runner.source_tables) == ["table1", "table2"]

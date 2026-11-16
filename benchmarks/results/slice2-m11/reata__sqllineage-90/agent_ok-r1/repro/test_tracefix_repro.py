from sqllineage.runner import LineageRunner


def test_ansi89_cartesian_product_source_tables():
    runner = LineageRunner("select a.* from table1 a, table2 b")
    sources = sorted(str(t) for t in runner.source_tables)
    assert sources == ["<default>.table1", "<default>.table2"] or sources == ["table1", "table2"] or [s.split('.')[-1] for s in sources] == ["table1", "table2"]
    assert runner.target_tables == []

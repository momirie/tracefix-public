from sqllineage.runner import LineageRunner


def test_ansi89_cartesian_product_does_not_raise():
    runner = LineageRunner("select a.* from table1 a, table2 b")
    assert len(runner.target_tables) == 0
    sources = {str(t) for t in runner.source_tables}
    assert sources == {"table1", "table2"}

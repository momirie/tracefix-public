from sqlglot import parse_one


def test_duckdb_cte_pivot_statement():
    sql = "WITH cities (country, name, year, population) AS (SELECT 'NL', 'Amsterdam', 2000, 1005 UNION ALL SELECT 'US', 'Seattle', 2010, 608) PIVOT cities ON year USING SUM(population)"
    expr = parse_one(sql, dialect="duckdb")
    out = expr.sql(dialect="duckdb")
    assert out.startswith("WITH cities")
    assert "PIVOT cities ON year USING SUM(population)" in out

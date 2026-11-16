from sqlglot import parse_one


def test_spark_unix_timestamp_no_args():
    expr = parse_one("SELECT UNIX_TIMESTAMP()", read="spark")
    assert expr is not None
    assert "UNIX_TIMESTAMP" in expr.sql(dialect="spark").upper()

from sqlglot import parse_one


def test_spark_unix_timestamp_no_args():
    expression = parse_one("SELECT unix_timestamp()", read="spark")
    assert expression is not None
    assert "UNIX_TIMESTAMP" in expression.sql(dialect="spark").upper()

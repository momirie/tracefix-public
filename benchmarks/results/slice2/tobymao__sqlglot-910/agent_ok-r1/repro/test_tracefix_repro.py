from sqlglot import parse_one


def test_spark_unix_timestamp_no_args_parses():
    result = parse_one("select unix_timestamp()", read="spark")
    assert result is not None
    sql = result.sql(dialect="spark")
    assert "UNIX_TIMESTAMP" in sql.upper()

from sqlglot import parse_one, exp


def test_spark_unix_timestamp_no_args():
    expression = parse_one("select unix_timestamp()", read="spark")
    assert expression.find(exp.StrToUnix) is not None

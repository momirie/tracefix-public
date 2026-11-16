from sqlglot import parse_one, exp


def test_spark_unix_timestamp_no_args():
    for dialect in ("spark", "hive"):
        expr = parse_one("select unix_timestamp()", read=dialect)
        node = expr.find(exp.StrToUnix)
        assert node is not None
        assert isinstance(node.this, exp.CurrentTimestamp)

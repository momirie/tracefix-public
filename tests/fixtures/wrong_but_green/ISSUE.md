# Histogram buckets are wrong for large values

`bucket_of(100000000000000015, 10)` returns `100000000000000020`, which isn't even the
bucket the value is in. Smaller values look fine.

# truncate() returns strings longer than max_len

`truncate()` returns strings longer than `max_len`. `truncate('hello world', 5)` gives
6 characters, and it overflows our fixed-width table column.

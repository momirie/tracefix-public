"""The docstring's rule checked for every position 1..1000 (a reference implementation)."""

from standings.ordinal import ordinal

SUFFIXES = {1: "st", 2: "nd", 3: "rd"}


def reference(n: int) -> str:
    suffix = "th" if n % 100 in (11, 12, 13) else SUFFIXES.get(n % 10, "th")
    return f"{n}{suffix}"


def test_every_position_up_to_1000() -> None:
    wrong = [n for n in range(1, 1001) if ordinal(n) != reference(n)]
    assert wrong == []

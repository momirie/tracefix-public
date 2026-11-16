from crm.contacts import dedupe_emails, merge_mailing_lists


def test_dedupe_keeps_first_occurrence_in_order() -> None:
    emails = ["ann@example.com", "bob@example.com", "ann@example.com"]
    assert dedupe_emails(emails) == ["ann@example.com", "bob@example.com"]


def test_dedupe_empty() -> None:
    assert dedupe_emails([]) == []


def test_dedupe_accepts_any_iterable() -> None:
    assert dedupe_emails(iter(["a@x.org", "a@x.org"])) == ["a@x.org"]


def test_dedupe_ignores_surrounding_whitespace() -> None:
    assert dedupe_emails(["bob@example.com", " bob@example.com "]) == ["bob@example.com"]


def test_merge_mailing_lists() -> None:
    newsletter = ["ann@example.com", "cat@example.com"]
    customers = ["cat@example.com", "dan@example.com"]
    assert merge_mailing_lists(newsletter, customers) == [
        "ann@example.com",
        "cat@example.com",
        "dan@example.com",
    ]

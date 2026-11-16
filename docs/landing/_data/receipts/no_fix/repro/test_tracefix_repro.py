from crm.contacts import dedupe_emails, merge_mailing_lists


def test_dedupe_case_insensitive() -> None:
    result = dedupe_emails(["Bob@Example.com", "bob@example.com"])
    assert len(result) == 1
    assert result[0].lower() == "bob@example.com"


def test_merge_lists_case_insensitive() -> None:
    result = merge_mailing_lists(["Bob@Example.com"], ["bob@example.com"])
    assert len(result) == 1

"""ISSUE: addresses differing only in case are imported twice."""

from crm.contacts import dedupe_emails


def test_case_insensitive_duplicates_are_merged() -> None:
    assert len(dedupe_emails(["Bob@Example.com", "bob@example.com"])) == 1

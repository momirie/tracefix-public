"""Helpers for importing contacts from spreadsheets and mailing-list exports."""

from collections.abc import Iterable
from itertools import chain


def dedupe_emails(emails: Iterable[str]) -> list[str]:
    """Remove duplicate addresses, keeping the first occurrence of each, in order."""
    seen: set[str] = set()
    unique: list[str] = []
    for raw in emails:
        email = raw.strip()
        if email in seen:
            continue
        seen.add(email)
        unique.append(email)
    return unique


def merge_mailing_lists(*lists: Iterable[str]) -> list[str]:
    """Combine several mailing lists into one import batch without duplicates."""
    return dedupe_emails(chain.from_iterable(lists))

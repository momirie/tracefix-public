"""The Talk page's holes (docs/landing/talk/): the contact address, its mailto links, and the
release gate that counts conversations, read from docs/landing/_data/gates.json.

The page offers a conversation only: no runs on a visitor's code (the developer, 2026-11-07).
Every way to reach the developer on the site (feedback, a wrong receipt, a fixture idea) is a
mailto link made here, so the address lives in one place. The page source types no number
(tests/test_site_talk.py).
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import site_benchmark

# The developer's choice (2026-11-07); it works once tracefix.dev is registered with mail.
EMAIL = "founder@tracefix.dev"
# How long the conversation is: the offer itself, not a measurement.
CALL = "twenty minutes"
# The release gate a website can move: conversations with people who review AI-written PRs.
TALK_GATE = 7

# Subject and body of each kind of message; the body is a template the sender fills in.
MESSAGES: dict[str, tuple[str, str]] = {
    "talk": (
        "Talk: reviewing AI-written fixes",
        "How I review fixes today:\n\nGood times for a call:\n",
    ),
    "receipt": ("Wrong receipt: ", "Receipt (page or file):\nWhat it says:\nWhat is true:\n"),
    "fixture": ("Fixture: ", "The bug:\nA fix that looks right but is not:\n"),
    "feedback": ("Feedback: ", ""),
}


def mailto(kind: str) -> str:
    """A mailto link for one kind of message, subject and body percent-encoded (RFC 6068)."""
    subject, body = MESSAGES[kind]
    query = f"subject={quote(subject, safe='')}"
    if body:
        query += f"&body={quote(body, safe='')}"
    return f"mailto:{EMAIL}?{query}"


def fields(data: Path | None = None) -> dict[str, str]:
    """The page's holes: the address, the links, and the gate as the data has it today."""
    gates, _, _ = site_benchmark.load(data)
    gate = next(g for g in gates["gates"] if g["number"] == TALK_GATE)
    latest = gates["columns"][2:-2][-1]
    return {
        "email": EMAIL,
        "call": CALL,
        "mailto_talk": site_benchmark.e(mailto("talk")),
        "mailto_receipt": site_benchmark.e(mailto("receipt")),
        "mailto_fixture": site_benchmark.e(mailto("fixture")),
        "mailto_feedback": site_benchmark.e(mailto("feedback")),
        "talk_gate": str(TALK_GATE),
        "talk_gate_title": site_benchmark.e(gate["title"]),
        "talk_gate_count": site_benchmark.e(gate["results"][latest]),
        "talk_gate_target": site_benchmark.e(gate["target"]),
        "gates_total": str(len(gates["gates"])),
        "gates_holding": str(gates["holding"]),
    }

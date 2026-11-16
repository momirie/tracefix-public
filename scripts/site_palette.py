"""The command palette's entries (every page): the pages, their sections and every receipt.

The palette (Ctrl or Cmd + K, or "/"; docs/landing/assets/site.js) searches this list, built into
each page as JSON by scripts/build_site.py. A link is relative to the site's root; the script adds
the page's own way back to it. tests/test_site_palette.py checks that every entry leads to a built
page and, where it names one, to an id on it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import site_receipts

Json = dict[str, Any]

# (link, name, what is there)
PAGES = (
    ("", "Home", "Watch Tracefix break a fix"),
    ("benchmark/", "Benchmark", "How often it is right on real fixes, and every miss"),
    ("receipts/", "Receipts", "What Tracefix hands back, for every fixture"),
    ("method/", "Method", "How it decides, and where it stops"),
    ("talk/", "Talk to me", "A conversation before anything ships"),
)
# (link, name, the page it is on)
SECTIONS = (
    ("#attack", "Replay the attack", "Home"),
    ("#try", "Try your own input", "Home"),
    ("#stands", "Where it stands", "Home"),
    ("#butterfly", "The Butterfly", "Home"),
    ("#hard-code", "The Hard-Code", "Home"),
    ("#lawyer", "The Lawyer", "Home"),
    ("#levels", "Evidence levels", "Home"),
    ("#install", "Install", "Home"),
    ("#faq", "Questions", "Home"),
    ("benchmark/#gates", "Release gates", "Benchmark"),
    ("benchmark/#results", "Results per slice", "Benchmark"),
    ("benchmark/#misses", "Every counted miss", "Benchmark"),
    ("benchmark/#method", "How it was measured", "Benchmark"),
    ("method/#rule", "The rule", "Method"),
    ("method/#run", "The run, stage by stage", "Method"),
    ("method/#ladder", "The ladder and the strict L4 gate", "Method"),
    ("method/#isolation", "Isolation and the tamper watch", "Method"),
    ("method/#loop", "In the pull request", "Method"),
    ("method/#forks", "Fork pull requests", "Method"),
    ("method/#sent", "What is sent to Anthropic", "Method"),
    ("talk/#ask", "What I would ask", "Talk to me"),
    ("talk/#feedback", "Report a wrong receipt", "Talk to me"),
)


def entries(receipts: Path | None = None, fixtures: Path | None = None) -> list[Json]:
    """Every entry in the order the empty palette lists them: g is the group, t the name, h the
    hint beside it, u the link from the site's root, lv a receipt's level."""
    out: list[Json] = [{"g": "Pages", "t": name, "h": hint, "u": url} for url, name, hint in PAGES]
    for name in site_receipts.cases(receipts):
        case = site_receipts.load(name, receipts, fixtures)
        out.append({
            "g": "Receipts", "t": name, "h": site_receipts.title(case),
            "u": f"receipts/{name}/", "lv": case.level,
        })  # fmt: skip
    out += [{"g": "Sections", "t": name, "h": page, "u": url} for url, name, page in SECTIONS]
    return out


def data(receipts: Path | None = None, fixtures: Path | None = None) -> str:
    """The entries as JSON for a <script> element: "<" escaped so no text can close it."""
    found = entries(receipts, fixtures)
    return json.dumps(found, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")

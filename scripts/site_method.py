"""The Method page's numbers (docs/landing/method/), read from Tracefix's own constants.

The page explains how Tracefix decides; every limit it names (runs in a row, inputs per function,
the kill rate, the model defaults, the budget) is the constant the code uses, so the page can't
drift from the code. The page source types no number (tests/test_site_method.py).

Two of its parts are made from the fixtures' receipts (moved from the home page, DECISIONS
2026-11-14 "Home page cut"): the fixture picker that walks a receipt up the ladder
(site_receipts.climb_fields), and the home replay's receipt as a pull request gets it: the check
run's fields and its first annotation (tracefix.action_report's own functions), the PR comment and
a receipt.json excerpt. Every string from a receipt is escaped.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

import site_home
import site_receipts

from tracefix import action_report, attack, behaviour_rules, guard, judge, ladder, llm, repro
from tracefix.ladder import ORDER
from tracefix.receipt import Receipt

Json = dict[str, Any]
# A receipt with no finding and no tampering: the check's conclusion per level is asked of it.
CLEAN = "good_fix"

WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
TIMES = {1: "once", 2: "twice"}


def word(n: int) -> str:
    """A small count as a word ("three"), a larger one in digits."""
    return WORDS[n] if 0 <= n < len(WORDS) else f"{n:,}"


def times(n: int) -> str:
    """How many times, as said: "once", "twice", "three times"."""
    return TIMES.get(n, f"{word(n)} times")


def e(text: object) -> str:
    """Text from a receipt, escaped for the page."""
    return escape(str(text), quote=True)


# What the excerpt keeps of receipt.json and of its first finding: what an agent reads first.
JSON_KEYS = ("level", "level_reasons")
FINDING_KEYS = ("call", "outcome", "property", "file", "path", "line")
PROPERTY_KEYS = ("source", "quote")


def check_by_level(receipt: Receipt) -> str:
    """The check's conclusion for every level, asked of action_report.conclusion itself (the
    Action's default settings: no min-level) with a clean receipt set to each level in turn."""
    rows = []
    for level in reversed(ORDER):
        says = action_report.conclusion(receipt.model_copy(update={"level": level}), "")
        rows.append(
            f"<li>{site_receipts.level_badge(level.value)}"
            f'<span class="ck-{e(says)}">{e(says)}</span></li>'
        )
    return "".join(rows)


def json_excerpt(receipt: Json) -> str:
    finding = receipt["findings"][0]
    picked = {k: finding[k] for k in FINDING_KEYS}
    picked["property"] = {k: finding["property"][k] for k in PROPERTY_KEYS}
    excerpt = {**{k: receipt[k] for k in JSON_KEYS}, "findings": [picked]}
    return json.dumps(excerpt, indent=2, ensure_ascii=False)


def loop_fields(case: site_receipts.Case, clean: site_receipts.Case) -> dict[str, str]:
    """The replay's receipt as a pull request gets it: the check run's fields and its first
    annotation (tracefix.action_report), receipt.md as the comment shows it, and a JSON excerpt.
    `clean` is a receipt with no finding and no tampering, for the conclusion per level."""
    receipt = Receipt.model_validate(case.receipt)
    report = action_report.Report(receipt)
    notes, _ = action_report.annotations_for(receipt)
    if not receipt.findings or not notes or notes[0].level != "failure":
        raise ValueError(f"{case.name}: its receipt has no finding with a failure annotation")
    note = notes[0]
    return {
        "check_name": e(action_report.CHECK_NAME),
        "check_conclusion": e(action_report.conclusion(receipt, "")),
        "check_title": e(action_report.check_title(report, "")),
        "note_path": e(note.path),
        "note_line": str(note.line),
        "note_level": e(note.level),
        "note_title": e(note.title),
        "note_message": e(note.message),
        "check_by_level": check_by_level(Receipt.model_validate(clean.receipt)),
        "comment_md": site_receipts.markdown(case.receipt_md, shift=1, html=True),
        "json_excerpt": e(json_excerpt(case.receipt)),
    }


def constant_fields() -> dict[str, str]:
    """The holes that name a limit, each from the constant the code reads."""
    return {
        "roles": word(len(llm.DEFAULT_MODELS)),
        "repro_attempts": word(repro.MAX_ATTEMPTS),
        "head_runs": times(repro.HEAD_PASS_REPEATS + 1),
        "min_mutants": word(guard.MIN_MUTANTS),
        "max_mutants": word(guard.MAX_MUTANTS),
        "kill_percent": f"{guard.KILL_PERCENT}%",
        "max_edit_lines": word(guard.MAX_EDIT_LINES),
        "min_compared": f"{behaviour_rules.MIN_COMPARED:,}",
        "max_lost": f"{behaviour_rules.MAX_LOST_SHARE:.0%}",
        "finding_runs": times(attack.FINDING_RERUNS + 1),
        "adversary_samples": word(attack.ADVERSARY_SAMPLES),
        "judge_samples": word(judge.JUDGE_SAMPLES),
        "strict_min_inputs": f"{ladder.L4_MIN_INPUTS:,}",
        "model_reproducer": llm.DEFAULT_MODELS["reproducer"],
        "model_mutator": llm.DEFAULT_MODELS["mutator"],
        "model_adversary": llm.DEFAULT_MODELS["adversary"],
        "model_judge": llm.DEFAULT_MODELS["judge"],
        "effort": llm.DEFAULT_EFFORT,
        "max_calls": f"{llm.DEFAULT_MAX_CALLS:,}",
        "token_budget": f"{llm.DEFAULT_TOKEN_BUDGET:,}",
    }


def fields(receipts: Path | None = None, fixtures: Path | None = None) -> dict[str, str]:
    """Every hole the page fills: the constants, the fixture picker and the pull request parts."""
    case = site_receipts.load(site_home.REPLAY, receipts, fixtures)
    clean = site_receipts.load(CLEAN, receipts, fixtures)
    return {
        **constant_fields(),
        **site_receipts.climb_fields(receipts, fixtures),
        **loop_fields(case, clean),
        "replay_case": site_home.REPLAY,
    }

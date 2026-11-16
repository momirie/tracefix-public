"""The Action's verdict and its words on GitHub (plan P4, P5): pure functions, no I/O.

The check run's conclusion comes from the receipt's level, status and tampering only, by a fixed
table (`conclusion`); nothing a model wrote can move it. The check's summary and the PR comment
show receipt.md re-rendered from the validated `Receipt` model, never a markdown file from an
artifact. Annotations come from the receipt's own places (finding, regression, flag and survivor
lines), as plain text on one line.

One PR comment is ours: it starts with MARKER, it was written by the token's own login, and it
ends with a state block holding the history of earlier verdicts. That block is read back by
`parse_history` into a strict model (commit ids hex, levels and statuses from fixed sets, times
in one shape, run ids numbers) and rendered by our code, so a forged comment can inject nothing
but those values.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tracefix.github_api import Comment
from tracefix.ladder import EvidenceLevel, rank
from tracefix.previous import WORDS as REPLAY_WORDS
from tracefix.previous import Replay, label
from tracefix.receipt import Receipt
from tracefix.receipt_md import LEVEL_WORDS, code, render, text
from tracefix.record import RunStatus

Conclusion = Literal["success", "failure", "neutral"]
AnnotationLevel = Literal["failure", "warning", "notice"]
CHECK_NAME = "Tracefix"
MARKER = "<!-- tracefix-receipt -->"
STATE_OPEN = "<!-- tracefix-state "
STATE_CLOSE = " -->"
BOT_LOGIN = "github-actions[bot]"  # the workflow token's comments
MAX_ANNOTATIONS = 50  # GitHub's limit per request; the check run is created in one request
MAX_MESSAGE_CHARS = 500
MAX_TITLE_CHARS = 100
MAX_HISTORY = 20
MAX_STATE_CHARS = 20_000
CHECK_RECEIPT_CHARS = 60_000  # the check summary's limit is 65,535 characters
COMMENT_RECEIPT_CHARS = 55_000  # a comment's is 65,536: room for the header and the history
SHORT_SHA = 7
_SHA_PATTERN = r"^[0-9a-f]{40}([0-9a-f]{24})?$"
_WHEN_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
_SAFE_PATH = re.compile(r"[A-Za-z0-9_.@+=,/ -]+")

Status = Literal["ok", "ENVIRONMENT_ERROR", "INVALID", "ERROR", "not_verified", "failed"]
STATUS_WORDS: dict[str, str] = {
    "ok": "ran",
    "ENVIRONMENT_ERROR": "environment error",
    "INVALID": "invalid (tampering)",
    "ERROR": "error",
    "not_verified": "not verified",
    "failed": "Tracefix failed",
}


@dataclass(frozen=True)
class Report:
    """What the run produced: a receipt, or why there is none."""

    receipt: Receipt | None
    why_not: str = ""  # why there is no receipt (a skip, exit 2, a crash)
    failed: bool = False  # Tracefix itself failed (exit 3, or verify did not finish)


@dataclass(frozen=True)
class Header:
    """The line above the receipt, from the run's own context (never from the receipt)."""

    head: str  # the commit verified ("" when there is none)
    run_url: str
    artifact: str  # the receipt artifact's name ("" when none was uploaded)
    issue_source: str  # e.g. "from #12" ("" when not verified)


# --- the conclusion -------------------------------------------------------------------------------


def conclusion(receipt: Receipt | None, min_level: str) -> Conclusion:
    """Plan P4's table: tampering, a COUNTEREXAMPLE or a level below `min-level` fail; L0 or no
    receipt is neutral (a failure when `min-level` is set); L1-L4 succeed."""
    if receipt is None:
        return "failure" if min_level else "neutral"
    if receipt.status is RunStatus.INVALID or receipt.tampering:
        return "failure"
    if receipt.level is EvidenceLevel.COUNTEREXAMPLE:
        return "failure"
    if min_level and rank(receipt.level) < rank(EvidenceLevel(min_level)):
        return "failure"
    return "neutral" if receipt.level is EvidenceLevel.L0 else "success"


def check_title(report: Report, min_level: str) -> str:
    receipt = report.receipt
    if receipt is None:
        what = "Tracefix failed" if report.failed else "Not verified"
        return plain(f"{what}: {report.why_not}", MAX_TITLE_CHARS)
    level = receipt.level
    if receipt.status is RunStatus.INVALID or receipt.tampering:
        return f"{level.value}: tampering detected"
    title = f"{level.value}: {LEVEL_WORDS[level]}"
    if min_level and rank(level) < rank(EvidenceLevel(min_level)):
        title += f" (below min-level {min_level})"
    return plain(title, MAX_TITLE_CHARS)


# --- annotations ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Annotation:
    path: str
    line: int
    level: AnnotationLevel
    title: str
    message: str

    def payload(self) -> dict[str, object]:
        return {
            "path": self.path,
            "start_line": self.line,
            "end_line": self.line,
            "annotation_level": self.level,
            "title": self.title,
            "message": self.message,
        }


def plain(value: str, limit: int) -> str:
    """Untrusted text as plain text on one line: whitespace runs made one space, every other
    control or format character escaped (`\\x1b`, `\\u202e`), at most `limit` characters."""
    flat = " ".join(value.split())
    shown = "".join(c if c.isprintable() else c.encode("unicode_escape").decode() for c in flat)
    return shown if len(shown) <= limit else shown[: limit - 3] + "..."


def repo_path(path: str | None) -> str | None:
    """A repo-relative POSIX path GitHub can place an annotation on, else None."""
    if not path or len(path) > 500 or not _SAFE_PATH.fullmatch(path):
        return None
    if any(part in ("", ".", "..") for part in path.split("/")):  # also a leading "/"
        return None
    return path


def _annotation(path: str | None, line: int | None, level: AnnotationLevel, title: str,
                message: str) -> Annotation | None:  # fmt: skip
    where = repo_path(path)
    if where is None:
        return None
    at = line if line is not None and line >= 1 else 1
    return Annotation(where, at, level, plain(title, MAX_TITLE_CHARS),
                      plain(message, MAX_MESSAGE_CHARS))  # fmt: skip


def _candidates(r: Receipt) -> list[Annotation | None]:
    """Every annotation the receipt has a place for, failures first (None: no usable place)."""
    out: list[Annotation | None] = []
    for f in r.findings:
        message = f"{f.call}: {f.outcome}"
        if f.base_outcome is not None:
            message += f" (before the fix: {f.base_outcome})"
        if f.property is not None:
            message += f"; breaks {f.property.name}: {f.property.quote}"
        elif f.expected is not None:
            message += f"; expected {f.expected}"
        if f.file:
            message += f"; reproduce with {f.file} from the receipt artifact"
        out.append(_annotation(f.path, f.line, "failure", f"Break My Fix: finding {f.number}",
                               message))  # fmt: skip
    for g in r.regressions:
        where = g.file if g.test is None else f"{g.file}::{g.test}"
        what = "no longer collects" if g.test is None else "passed before the fix, fails after it"
        out.append(_annotation(g.file, g.line, "failure", "Regression",
                               f"{where} {what} ({g.evidence})"))  # fmt: skip
    for flag in r.integrity_flags:
        out.append(_annotation(flag.file, flag.line, "failure",
                               f"Test integrity: {flag.kind}", flag.detail))  # fmt: skip
    previous = r.previous
    for old in previous.findings if previous else ():
        if old.result is Replay.FIXED or old.carried:  # a carried one's line is an older commit's
            continue
        assert previous is not None
        message = (f"{old.call} {REPLAY_WORDS[old.result]} on this commit ({old.detail}); "
                   f"line as of commit {previous.head_sha[:SHORT_SHA]}")  # fmt: skip
        name = label(old.number, old.carried)
        title = name[0].upper() + name[1:]
        out.append(_annotation(old.path, old.line, "warning", title, message))
    for s in r.survivors:
        out.append(_annotation(s.file, s.line, "notice", "A change no test noticed",
                               f"{s.description} ({s.words})"))  # fmt: skip
    return out


def annotations_for(r: Receipt) -> tuple[list[Annotation], int]:
    """At most MAX_ANNOTATIONS, failures first, and how many more the receipt holds (left out
    for the cap, or with no place GitHub accepts)."""
    found = _candidates(r)
    placed = [a for a in found if a is not None]
    return placed[:MAX_ANNOTATIONS], len(found) - min(len(placed), MAX_ANNOTATIONS)


# --- the check run and the header -----------------------------------------------------------------


def header_line(h: Header) -> str:
    parts = [f"Tracefix on commit {code(h.head[:SHORT_SHA])}" if h.head else "Tracefix"]
    if h.run_url.startswith(("https://", "http://")):
        parts.append(f"[workflow run]({h.run_url})")
    if h.artifact:
        parts.append(f"receipt artifact {code(h.artifact)}")
    if h.issue_source:
        parts.append(f"issue text {text(h.issue_source)}")
    return " · ".join(parts)


def _not_verified(report: Report) -> str:
    if report.failed:
        return (f"> [!WARNING]\n> Tracefix failed on this commit (a bug in Tracefix, not a verdict "
                f"on the fix): {text(report.why_not)}")  # fmt: skip
    return f"> [!NOTE]\n> Tracefix did not verify this commit: {text(report.why_not)}"


def check_summary(h: Header, report: Report, more: int) -> str:
    if report.receipt is None:
        return f"{header_line(h)}\n\n{_not_verified(report)}\n"
    page = render(report.receipt, max_chars=CHECK_RECEIPT_CHARS)
    tail = f"\n{more} more annotation(s) in receipt.json\n" if more else ""
    return f"{header_line(h)}\n\n{page}{tail}"


def check_run(h: Header, report: Report, min_level: str, notes: Sequence[Annotation],
              more: int, completed_at: str) -> dict[str, object]:  # fmt: skip
    """The check run's fields, created complete (no "in progress" step)."""
    return {
        "name": CHECK_NAME,
        "head_sha": h.head,
        "status": "completed",
        "conclusion": conclusion(report.receipt, min_level),
        "completed_at": completed_at,
        "details_url": h.run_url,
        "output": {
            "title": check_title(report, min_level),
            "summary": check_summary(h, report, more),
            "annotations": [a.payload() for a in notes],
        },
    }


# --- the PR comment and its history ---------------------------------------------------------------


class Entry(BaseModel):
    """One verdict in the comment's history: only fixed shapes."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    sha: Annotated[str, Field(pattern=_SHA_PATTERN)]
    level: EvidenceLevel | None
    status: Status
    when: Annotated[str, Field(pattern=_WHEN_PATTERN)]
    run: Annotated[int, Field(ge=0, le=10**15)]


class CommentState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    v: Literal[1] = 1
    history: Annotated[tuple[Entry, ...], Field(max_length=MAX_HISTORY)] = ()


def entry(sha: str, report: Report, when: str, run: int) -> Entry:
    receipt = report.receipt
    if receipt is not None:
        return Entry(sha=sha, level=receipt.level, status=receipt.status.value, when=when, run=run)
    return Entry(sha=sha, level=None, status="failed" if report.failed else "not_verified",
                 when=when, run=run)  # fmt: skip


def with_entry(history: Sequence[Entry], new: Entry) -> tuple[Entry, ...]:
    """Newest first; a run on the same commit replaces that commit's entry."""
    return (new, *(e for e in history if e.sha != new.sha))[:MAX_HISTORY]


def parse_history(body: str) -> tuple[Entry, ...]:
    """The history in a comment's last state block; anything malformed is no history at all."""
    start = body.rfind(STATE_OPEN)
    if start < 0:
        return ()
    end = body.find(STATE_CLOSE, start + len(STATE_OPEN))
    raw = body[start + len(STATE_OPEN) : end]
    if end < 0 or len(raw) > MAX_STATE_CHARS:
        return ()
    try:
        return CommentState.model_validate_json(raw, strict=True).history
    except (ValidationError, ValueError):
        return ()


def ours(comments: Sequence[Comment], login: str) -> Comment | None:
    """The newest comment with our marker on its first line, written by `login`; anyone else's
    comment carrying the marker is ignored."""
    mine = [c for c in comments if c.author == login and c.body.startswith(MARKER + "\n")]
    return max(mine, key=lambda c: c.id, default=None)


def _history_table(history: Sequence[Entry], run_url: Callable[[int], str]) -> list[str]:
    if not history:
        return []
    rows = [
        f"| {code(e.sha[:SHORT_SHA])} | {e.level.value if e.level else '-'} | "
        f"{STATUS_WORDS[e.status]} | {e.when} | [{e.run}]({run_url(e.run)}) |"
        for e in history
    ]
    return [
        "<details>",
        f"<summary>Earlier receipts on this pull request ({len(history)})</summary>",
        "",
        "| Commit | Level | Run status | When (UTC) | Workflow run |",
        "|---|---|---|---|---|",
        *rows,
        "",
        "</details>",
        "",
    ]


def comment_body(h: Header, report: Report, history: Sequence[Entry],
                 run_url: Callable[[int], str]) -> str:  # fmt: skip
    """The whole comment: marker, header, receipt (or why there is none), the earlier verdicts,
    and the state block. `history` is newest first and holds this run's entry."""
    if report.receipt is None:
        middle = _not_verified(report) + "\n"
    else:
        middle = render(report.receipt, max_chars=COMMENT_RECEIPT_CHARS)
    earlier = [e for e in history if e.sha != h.head]
    state = CommentState(history=tuple(history)).model_dump_json()
    lines = [MARKER, header_line(h), "", middle, *_history_table(earlier, run_url)]
    return "\n".join(lines) + f"{STATE_OPEN}{state}{STATE_CLOSE}\n"

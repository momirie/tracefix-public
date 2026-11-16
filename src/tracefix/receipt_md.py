"""receipt.md (SPEC 2.8, plan P13): the Fix Receipt for people, rendered from the Receipt only.

Everything shown comes from `receipt.Receipt`, so this page and receipt.json can't disagree. M9
posts the page as a PR comment, and much of its text comes from the issue, the repo or a model,
so every such string goes through `text` (Markdown and HTML escaped, one line, no mentions) or
`code` (a code span that no backtick inside can close). Every item is one line: that is what keeps
the page within its limits, at most 60 lines above the run log and 150 in all.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from tracefix.attack import Doubt
from tracefix.ladder import EvidenceLevel
from tracefix.previous import WORDS as REPLAY_WORDS
from tracefix.receipt import (
    UNOBSERVED_PREFIX,
    AttackTargetEntry,
    BehaviourChange,
    FindingEntry,
    IntegrityFlagEntry,
    PreviousInfo,
    Receipt,
    RegressionEntry,
    StageEntry,
    Survivor,
)
from tracefix.record import PREVIOUS, RunStatus

MAX_MAIN_LINES = 60  # above the run log
MAX_LINES = 150
MAX_COUNTEREXAMPLES = 5
MAX_CHANGES = 3
MAX_SURVIVORS = 3
MAX_FLAGS = 3
MAX_ALERTS = 2  # warnings, tampering
MAX_REPLAYED = 5  # findings of the last receipt on the "Since the last receipt" line
MAX_STAGE_COMMANDS = 3
MAX_REASONS = 6  # "Why this level" items above the run log
MAX_NOT_CHECKED = 10  # "Not checked" items above the run log (6 are the fixed scope limits)
MAX_TEXT = 500  # characters of one untrusted text, before escaping
MAX_CHARS = 60_000  # the whole page: GitHub refuses a comment over 65,536 characters
SNIPPET = 60  # characters of code shown in one item
ELLIPSIS = "..."
SHORT_SHA = 7
MORE = "in receipt.json"

# What each level means, in one line (SPEC 2.8's ladder).
LEVEL_WORDS: dict[EvidenceLevel, str] = {
    EvidenceLevel.COUNTEREXAMPLE: "concrete evidence against this fix",
    EvidenceLevel.L0: "no evidence for this fix",
    EvidenceLevel.L1: "the bug is reproduced and this fix removes it",
    EvidenceLevel.L2: "L1, and the tests notice the fix being undone",
    EvidenceLevel.L3: "L2, and every behaviour change is explained",
    EvidenceLevel.L4: "L3, and Break My Fix found no counterexample",
}
# The evidence numbers shown in each stage's table row (all of them are in receipt.json).
KEY_NUMBERS: dict[str, tuple[str, ...]] = {
    "environment": ("base_suite",),
    "import_check": ("modules",),
    "reproduce": ("attempts",),
    "guard": ("kill_rate", "mutants", "killed", "survived"),
    "regressions": ("compared", "regressions", "unconfirmed"),
    "fix_line_coverage": ("fix_lines",),
    "behaviour_diff": ("inputs_compared", "changes", "groups"),
    "break_my_fix": ("targets", "inputs_tried", "properties_counted", "findings"),
    "integrity": ("flags",),
    "blind": ("attempts", "report_only"),
    "previous": ("findings", "fixed"),
}
CHECK_WORDS = {
    "differs": "behaves differently from the fix on inputs no test checks",
    "no_difference_found": "no input tried behaved differently from the fix",
    "not_checked": "not compared with the fix",
}
# Why a counted finding may be a false alarm (M11 S5): fixed words, no text from the run.
DOUBT_WORDS: dict[Doubt, str] = {
    "refused": "this may be the code's own refusal: a `raise` in the project, same before the fix",
    "os_limit": "this may be the operating system's limit on how long a name can be",
    "finished_object": "the object's class deletes this attribute itself: it may be finished",
}

# --- escaping -------------------------------------------------------------------------------------

_PUNCTUATION = re.compile(r"([\\`*_\[\]|~$])")  # inline Markdown, tables, GitHub math
_MENTION = re.compile(r"([@#])(?=\w)")  # GitHub @mentions and #123 references
# GitHub links "x://" and "www." bare, "www." also right after "_" (no word boundary there).
_AUTOLINK = re.compile(r"(?<=:)(?=//)|(?<=[wW]{3}\.)")
_NUMBERED = re.compile(r"\d+(?=[.)])")


def _visible(value: str) -> str:
    """Control, format and separator characters (newlines, bidi overrides) as escapes."""
    return "".join(c if c.isprintable() else c.encode("unicode_escape").decode() for c in value)


def text(value: str) -> str:
    """Untrusted text as inert Markdown on one line: no markup, HTML, links (bare URLs too) or
    mentions."""
    flat = " ".join(value.split())
    flat = _visible(flat if len(flat) <= MAX_TEXT else flat[:MAX_TEXT] + ELLIPSIS)
    flat = _PUNCTUATION.sub(r"\\\1", flat)
    flat = flat.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    flat = _MENTION.sub("\\1\u200b", flat)
    flat = _AUTOLINK.sub("\u200b", flat)
    if flat[:1] in ("#", "+", "-", "="):  # would start a heading or list inside a list item
        return "\\" + flat
    numbered = _NUMBERED.match(flat)
    if numbered:
        return f"{flat[: numbered.end()]}\\{flat[numbered.end() :]}"
    return flat


def code(value: str, limit: int | None = None) -> str:
    """Untrusted text as one code span: its fence is longer than any backtick run inside."""
    # A cut saves room or isn't made: "..." in place of 3 characters or fewer would hide them for
    # nothing (an exception message's last `''` was cut that way).
    cut = limit is not None and len(value) > limit + len(ELLIPSIS)
    shown = value[:limit] + ELLIPSIS if cut else value
    shown = _visible(shown)
    longest = max((len(run) for run in re.findall(r"`+", shown)), default=0)
    fence = "`" * (longest + 1)
    pad = " " if longest or not shown or shown[0] == " " or shown[-1] == " " else ""
    return f"{fence}{pad}{shown}{pad}{fence}"


def _cell(value: str) -> str:
    """Our own identifier as a code span in a table cell (a `|` would split the cell)."""
    return code(value).replace("|", "\\|")


def _count(n: int, word: str) -> str:
    return f"{n:,} {word}" if n == 1 else f"{n:,} {word}s"


def _joined(items: Sequence[str], cap: int) -> str:
    """Items on one line, at most `cap` of them."""
    extra = len(items) - cap
    return "; ".join([*items[:cap], *([f"and {extra} more {MORE}"] if extra > 0 else [])])


def _more(shown: int, total: int) -> str:
    return f" ({shown} of {total}; the rest {MORE})" if total > shown else ""


# --- the top: level, summary, why, refs, alerts ---------------------------------------------------


def _head(r: Receipt) -> list[str]:
    lines = [f"## Fix Receipt: {r.level.value} ({LEVEL_WORDS[r.level]})", ""]
    if r.status is not RunStatus.OK:
        lines += [f"**Run stopped ({r.status.value}):** {text(r.status_reason)}", ""]
    if r.summary.by == "judge":
        model = r.llm.settings.models.get("judge", "the judge model")
        label = (
            f"**Summary** (advisory, written by the model {text(model)}; it never sets the level):"
        )
    else:
        label = "**Summary:**"
    lines += [f"{label} {text(r.summary.text)}", ""]
    lines += [f"**Why this level:** {_joined([text(x) for x in r.level_reasons], MAX_REASONS)}", ""]
    base = f"{code(r.base.ref)} ({code(r.base.sha[:SHORT_SHA])})"
    head = f"{code(r.head.ref)} ({code(r.head.sha[:SHORT_SHA])})"
    lines += [
        f"**Issue:** {text(r.issue.title)} · **Repo:** {text(r.repo.name)} · "
        f"**Base** {base} → **head** {head}\\",
        f"**Isolation:** {r.isolation.level} ({text(r.isolation.why)})",
        "",
    ]
    warnings = [*([r.isolation.warning] if r.isolation.warning else []), *r.warnings]
    lines += _alert("WARNING", [text(w) for w in warnings])
    tampering = [
        f"Tampering detected in **{text(t.stage)}**: {text(t.detail)}" for t in r.tampering
    ]
    lines += _alert("CAUTION", tampering)
    return lines


def _alert(kind: str, items: Sequence[str]) -> list[str]:
    if not items:
        return []
    shown = list(items[:MAX_ALERTS])
    if len(items) > MAX_ALERTS:
        shown[-1] += f" ({len(items) - MAX_ALERTS} more {MORE})"
    return [f"> [!{kind}]", *(f"> - {item}" for item in shown), ""]


# --- sections -------------------------------------------------------------------------------------


def _finding(f: FindingEntry) -> str:
    line = f"{code(f.call, SNIPPET)} → {code(f.outcome, SNIPPET)}"
    if f.base_outcome is not None:
        line += f" (before the fix: {code(f.base_outcome, SNIPPET)})"
    if f.property is not None:
        line += f"; breaks **{text(f.property.name)}**: “{text(f.property.quote)}”"
        line += f" ({text(f.property.source)})"
    elif f.expected is not None:
        line += f"; expected {code(f.expected, SNIPPET)}"
    if f.other_inputs:
        line += f"; {_count(f.other_inputs, 'more input')} break it the same way"
    if f.file is not None:
        line += f"; test: {code(f.file)}"
    if f.doubt is not None:
        line += f"; **Doubt (still counted):** {DOUBT_WORDS[f.doubt]}"
    return line


def _regression(g: RegressionEntry) -> str:
    where = g.file if g.test is None else f"{g.file}::{g.test}"
    what = "no longer collects" if g.test is None else "passed before the fix and fails after it"
    return f"Regression: {code(where)} {what} ({text(g.evidence)})"


def _since(r: Receipt) -> list[str]:
    """One line: what became of the last receipt's findings (only when they were replayed)."""
    stage = next((s for s in r.stages if s.name == PREVIOUS), None)
    p = r.previous
    if stage is None and p is None:
        return []
    if p is None or stage is None or stage.status not in ("replayed", "skipped") or not p.level:
        why = stage.reason if stage else "the run stopped before the replay"
        return [f"**Since the last receipt:** not replayed ({text(why)}){_open(p)}"]
    head = f"**Since the last receipt** ({code(p.head_sha[:SHORT_SHA])}, {p.level.value}):"
    if not p.findings:
        return [f"{head} it had no findings"]
    items = [f"{'earlier ' if f.carried else ''}finding {f.number} {code(f.call, SNIPPET)} "
             f"{REPLAY_WORDS[f.result]}" for f in p.findings]  # fmt: skip
    return [f"{head} {_joined(items, MAX_REPLAYED)}"]


def _open(p: PreviousInfo | None) -> str:
    if p is None:
        return ""
    if not p.still_open_known:
        return "; which earlier findings are still open is unknown"
    return f"; {len(p.still_open)} earlier finding(s) still open" if p.still_open else ""


def _counterexamples(r: Receipt) -> list[str]:
    items = [*(_finding(f) for f in r.findings), *(_regression(g) for g in r.regressions)]
    since = _since(r)
    if not items:
        return ["### Counterexamples", "None found.", *since, ""]
    heading = f"### Counterexamples{_more(MAX_COUNTEREXAMPLES, len(items))}"
    shown = items[:MAX_COUNTEREXAMPLES]
    numbered = [f"{i}. {item}" for i, item in enumerate(shown, start=1)]
    # A line right after a list item would join it: a blank line first.
    return [heading, *numbered, *(["", *since] if since else []), ""]


def _value(value: object) -> str:
    if isinstance(value, list):
        return str(len(value))
    return text(str(value))


def _key_numbers(s: StageEntry) -> str:
    keys = KEY_NUMBERS.get(s.name, ())
    shown = [
        f"{key.replace('_', ' ')} {_value(s.evidence[key])}"
        for key in keys
        if s.evidence.get(key) is not None
    ]
    return ", ".join(shown) or "none"


def _rule_kinds(r: Receipt) -> list[str]:
    """One line under the stages: Guard's rule mutants by kind (report only), if any ran."""
    stage = next((s for s in r.stages if s.name == "guard"), None)
    kinds = stage.evidence.get("rule_kinds") if stage else None
    if stage is None or not isinstance(kinds, list) or not kinds:
        return []
    line = f"**Rule mutants by kind (report only):** {text('; '.join(map(str, kinds)))}"
    absent = stage.evidence.get("rule_kinds_absent")
    if isinstance(absent, list) and absent:
        line += f"; no place for {text(', '.join(map(str, absent)))}"
    return [line, ""]


def _stages(r: Receipt) -> list[str]:
    rows = [
        f"| {_cell(s.name)} | {_cell('error' if s.error else s.status)} | {_key_numbers(s)} |"
        for s in r.stages
    ]
    table = ["### Stages", "| Stage | Status | Key numbers |", "|---|---|---|", *rows, ""]
    return [*table, *_rule_kinds(r)]


def _change(c: BehaviourChange) -> str:
    line = (
        f"{code(c.function)} ({code(c.kind)}, {_count(c.count, 'input')}): "
        f"{code(c.before, SNIPPET)} → {code(c.after, SNIPPET)}"
    )
    if c.explained:
        line += f"; explained by: {text('; '.join(c.explained))}"
    if c.contradicts:
        line += f"; contradicts: {text('; '.join(c.contradicts))}"
    for label in c.labels:
        line += f"; the Judge (advisory) calls it {text(label.label)}: {text(label.reason)}"
    return line


def _survivor(s: Survivor) -> str:
    where = code(f"{s.file}:{s.line}")
    edit = f"{code(s.original, SNIPPET)} → {code(s.replacement, SNIPPET)}"
    words = CHECK_WORDS.get(s.check, text(s.check))
    return f"{where}: {edit} made no test fail; {words} ({code(s.id)})"


def _flag(f: IntegrityFlagEntry) -> str:
    test = f" ({code(f.test)})" if f.test else ""
    line = (
        f"**{text(f.id)}** {code(f.kind)} in {code(f'{f.file}:{f.line}')}{test}: "
        f"{text(f.detail)} ({text(f.evidence)})"
    )
    if f.note is not None:
        line += f"; the Judge's note (advisory): {text(f.note)}"
    return line


def _section(title: str, items: Sequence[str], cap: int) -> list[str]:
    if not items:
        return []
    heading = f"### {title}{_more(cap, len(items))}"
    return [heading, *(f"- {item}" for item in items[:cap]), ""]


def _footer(r: Receipt) -> list[str]:
    cost = r.llm.cost_estimate
    usd = "unknown" if cost.usd is None else f"${cost.usd:.4f}"
    use = (
        f"**Model use:** {_count(r.llm.calls, 'call')}, {r.llm.input_tokens:,} input and "
        f"{r.llm.output_tokens:,} output tokens, cost {usd} ({text(cost.label)})"
    )
    if r.llm.problems:
        use += f"; {_count(len(r.llm.problems), 'failed model call')} (see the run log)"
    unobserved = [u for u in r.unchecked if u.startswith(UNOBSERVED_PREFIX)]
    shown = [text(u) for u in r.unchecked if not u.startswith(UNOBSERVED_PREFIX)]
    if unobserved:
        shown.append(f"{len(unobserved)} things the behaviour diff can't observe (run log)")
    return [f"- **Not checked:** {_joined(shown, MAX_NOT_CHECKED)}", f"- {use}"]


def _main(r: Receipt) -> list[str]:
    return [
        *_head(r),
        *_counterexamples(r),
        *_stages(r),
        *_section("Behaviour changes", [_change(c) for c in r.behaviour_changes], MAX_CHANGES),
        *_section("Changes no test noticed", [_survivor(s) for s in r.survivors], MAX_SURVIVORS),
        *_section("Integrity flags", [_flag(f) for f in r.integrity_flags], MAX_FLAGS),
        *_footer(r),
    ]


# --- the run log ----------------------------------------------------------------------------------


def _stage_log(s: StageEntry) -> list[str]:
    status = code("error" if s.error else s.status)
    lines = [f"- {code(s.name)}: {status}, {s.duration_s} s: {text(s.reason)}"]
    if s.error:
        lines.append(f"  - Tracefix's own code failed: {code(s.error, 200)}")
    lines += [f"  - {text(p.words)} ({text(p.role)}, {text(p.model)}): {code(p.detail, 200)}"
              for p in s.problems]  # fmt: skip
    lines += [f"  - {code(c, 200)}" for c in s.commands[:MAX_STAGE_COMMANDS]]
    if len(s.commands) > MAX_STAGE_COMMANDS:
        lines.append(f"  - {len(s.commands) - MAX_STAGE_COMMANDS} more command(s) {MORE}")
    return lines


def _target(t: AttackTargetEntry) -> str:
    line = f"{code(t.function)} ({code(t.path)}): "
    line += _count(t.inputs_tried, "input") if t.attacked else "not attacked"
    if t.reason:
        line += f" ({text(t.reason)})"
    if not t.finished:
        line += "; its attack did not finish"
    if t.via:
        line += f"; {text(t.via)}"
    return line


def _log_section(title: str, items: Sequence[str]) -> list[str]:
    return [f"#### {title}", *(f"- {item}" for item in items)] if items else []


def _log(r: Receipt) -> list[str]:
    counterexamples = [*(_finding(f) for f in r.findings), *(_regression(g) for g in r.regressions)]
    coverage = r.fix_line_coverage
    lines = ["#### Stages", *(line for s in r.stages for line in _stage_log(s))]
    lines += _log_section("More counterexamples", counterexamples[MAX_COUNTEREXAMPLES:])
    lines += _log_section("Found before the fix too", [_finding(f) for f in r.pre_existing])
    lines += _log_section("Break My Fix targets", [_target(t) for t in r.attack_targets or ()])
    lines += _log_section("More behaviour changes",
                          [_change(c) for c in r.behaviour_changes[MAX_CHANGES:]])  # fmt: skip
    lines += _log_section("More changes no test noticed",
                          [_survivor(s) for s in r.survivors[MAX_SURVIVORS:]])  # fmt: skip
    lines += _log_section("More integrity flags",
                          [_flag(f) for f in r.integrity_flags[MAX_FLAGS:]])  # fmt: skip
    if coverage is not None:
        sets = [f"{text(s.name)}: {s.ran} of {s.total} fix lines run" for s in coverage.sets]
        lines += _log_section("Fix lines run (report only)", [*sets, *map(text, coverage.notes)])
    lines += _log_section("Not checked", [text(u) for u in r.unchecked])
    lines += _log_section("Warnings", [text(w) for w in r.warnings])
    lines += _log_section("Notes", [text(n) for n in r.notes])
    s = r.llm.settings
    models = ", ".join(f"{text(role)} {text(model)}" for role, model in s.models.items())
    lines += _log_section("This receipt", [
        f"models: {models}; effort {text(s.effort)}; at most {s.max_calls} calls and "
        f"{s.token_budget:,} tokens",
        f"Tracefix {r.tracefix_version}, receipt schema {r.schema_version}, "
        f"created {r.created_at}, issue sha256 {code(r.issue.sha256)}",
    ])  # fmt: skip
    return lines


def _fit(lines: list[str], max_chars: int = MAX_CHARS) -> list[str]:
    """The page cut at a line to stay within `max_chars`, saying so (and still closing the run
    log), so it can always be posted as one comment."""
    out: list[str] = []
    size = 200  # room for the closing lines
    for line in lines:
        size += len(line) + 1
        if size > max_chars:
            break
        out.append(line)
    else:
        return lines
    out = out[: len(lines) - 4]  # never more lines than before
    more = len(lines) - len(out)
    if out and out[-1].startswith("<"):  # after "<summary>": a list item needs a blank line first
        out.append("")
    out.append(f"- {more} more line(s) {MORE} (receipt.md stays within {max_chars:,} characters)")
    return [*out, "", "</details>"] if "<details>" in out else out


def render(r: Receipt, max_chars: int = MAX_CHARS) -> str:
    """receipt.md: at most MAX_MAIN_LINES above the run log, MAX_LINES and `max_chars` in all
    (the Action passes less, to leave room for its own lines in the PR comment)."""
    main = _main(r)
    log = _log(r)
    room = MAX_LINES - len(main) - 6  # blank, <details>, <summary>, blank ... blank, </details>
    if len(log) > room:
        cut = len(log) - room + 1
        log = [*log[: room - 1], f"- {cut} more line(s) {MORE}"]
    return "\n".join(_fit([*main, "", "<details>", "<summary>Run log</summary>", "", *log, "",
                           "</details>"], max_chars)) + "\n"  # fmt: skip

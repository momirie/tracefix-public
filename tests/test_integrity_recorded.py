"""M5 acceptance: the integrity audit on every fixture, graded against expected.json.

The reproducer's answers are replayed from tests/recordings (integrity itself calls no model);
everything else is real: copies, pytest runs, the tamper watch. test_weakened must give exactly its
integrity `must_find`; every other case must give no flag at all (a flag is a COUNTEREXAMPLE, so
one on a good fix would be a false alarm). special_cased's hard-coded 2100 must be reported, never
flagged (Decided in M5 by the developer; Break My Fix finds its counterexample in M6).
"""

from pathlib import Path
from typing import Any

import make_fixtures
import pytest
from test_guard_recorded import expected, provider
from test_repro_recorded import issue_text

from tracefix.diffscope import compute_scope
from tracefix.integrity import IntegrityResult, IntegrityStatus, audit
from tracefix.llm import LLMClient
from tracefix.repro import ReproResult, ReproStatus, reproduce
from tracefix.workspace import Workspace

CASES = sorted(make_fixtures.CASES)
NO_REPRO = ReproResult(ReproStatus.NOT_REPRODUCED, "the pipeline stops before reproduction",
                       "tests/test_tracefix_repro.py", None, (), ())  # fmt: skip
# Report-only candidates a case must show (kind, file, literal), beside expected.json's flags.
MUST_REPORT = {"special_cased": ("special_case", "src/billing/calendar.py", 2100)}


def wanted(case: str) -> list[dict[str, Any]]:
    return [m for m in expected(case)["must_find"] if m["stage"] == "integrity"]


def summary(result: IntegrityResult) -> str:
    lines = [f"{result.status}: {result.reason}"]
    lines += [f"  flag {f.kind} {f.file}:{f.line} {f.detail!r}: {f.evidence}" for f in result.flags]
    lines += [f"  candidate {c.kind} {c.file}:{c.line} {c.detail!r}: {c.why_not_flag}"
              for c in result.candidates]  # fmt: skip
    return "\n".join(lines + [f"  note: {n}" for n in result.notes])


def test_one_case_expects_an_integrity_flag_and_special_cased_must_have_none() -> None:
    assert [c for c in CASES if wanted(c)] == ["test_weakened"]
    assert "integrity_flag" in expected("special_cased")["must_not_find"]


@pytest.mark.parametrize("case", CASES)
def test_integrity_matches_expected_json(case: str, built: dict[str, Path]) -> None:
    client = LLMClient(provider())
    with Workspace(built[case], "base", "head") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        repro = NO_REPRO if case == "env_broken" else reproduce(ws, scope, issue_text(case), client)
        result = audit(ws, scope, repro, issue_text(case))
        assert ws.copies == [ws.base, ws.head]
    assert not any(c.role != "reproducer" for c in client.calls)  # integrity asks no model
    if case in MUST_REPORT:
        reported = [(c.kind, c.file, c.literal) for c in result.candidates]
        assert MUST_REPORT[case] in reported, summary(result)
    must = wanted(case)
    if not must:
        assert result.flags == (), summary(result)
        assert result.status in (IntegrityStatus.CLEAN, IntegrityStatus.SKIPPED), summary(result)
        return
    assert result.status is IntegrityStatus.FLAGGED, summary(result)
    got = [(f.kind, f.file, f.detail if "detail" in m else f.literal)
           for f, m in zip(result.flags, must, strict=False)]  # fmt: skip
    want = [(m["kind"], m["file"], m.get("detail", m.get("literal"))) for m in must]
    assert got == want and len(result.flags) == len(must), summary(result)
    assert all(f.evidence for f in result.flags)

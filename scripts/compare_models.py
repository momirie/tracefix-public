"""Compare models for the reproducer role on fixtures 1-7. LIVE: calls the API (costs money).

    uv run python scripts/compare_models.py OUT_DIR claude-sonnet-5-5 claude-opus-5-5

For each model: one run per fixture, graded against expected.json. Responses are recorded under
OUT_DIR/<model>/ so a winning run can become the test recordings without paying again. Prints a
table and writes OUT_DIR/summary.json.
"""

import json
import sys
import tempfile
import time
from pathlib import Path

import make_fixtures

from tracefix.diffscope import compute_scope
from tracefix.llm import DEFAULT_MODELS, AnthropicProvider, LLMClient, RecordingProvider
from tracefix.repro import ReproStatus, reproduce
from tracefix.workspace import Workspace

CASES = [c for c in sorted(make_fixtures.CASES) if c != "env_broken"]


def expected(case: str) -> ReproStatus:
    data = json.loads((make_fixtures.FIXTURES_DIR / case / "expected.json").read_text("utf-8"))
    return ReproStatus(data["receipt"]["stages"]["reproduce"])


def run_model(model: str, repos: dict[str, Path], out: Path) -> dict[str, object]:
    rows = []
    for case in CASES:
        models = {**DEFAULT_MODELS, "reproducer": model}
        client = LLMClient(RecordingProvider(AnthropicProvider(), out / model), models=models)
        issue = (make_fixtures.FIXTURES_DIR / case / "ISSUE.md").read_text(encoding="utf-8")
        start = time.monotonic()
        with Workspace(repos[case], "base", "head") as ws:
            result = reproduce(ws, compute_scope(ws.repo, ws.base_sha, ws.head_sha), issue, client)
        rows.append({
            "case": case,
            "status": result.status.value,
            "expected": expected(case).value,
            "pass": result.status is expected(case),
            "attempts": len(result.attempts),
            "calls": len(client.calls),
            "input_tokens": sum(c.input_tokens for c in client.calls),
            "output_tokens": sum(c.output_tokens for c in client.calls),
            "cost_usd": client.cost_usd,
            "seconds": round(time.monotonic() - start, 1),
        })  # fmt: skip
        print(f"  {model} {case}: {rows[-1]['status']} (pass={rows[-1]['pass']})", flush=True)
    passed = sum(1 for r in rows if r["pass"])
    cost = sum(float(r["cost_usd"] or 0) for r in rows)  # type: ignore[arg-type]
    return {"model": model, "passed": passed, "total": len(rows), "cost_usd": round(cost, 4),
            "calls": sum(int(r["calls"]) for r in rows), "rows": rows}  # type: ignore[call-overload]  # fmt: skip


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    out = Path(argv[1])
    repos = make_fixtures.build_all(Path(tempfile.mkdtemp(prefix="tracefix-compare-")))
    summary = [run_model(model, repos, out) for model in argv[2:]]
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(f"\n{'model':<20} {'pass':>6} {'calls':>6} {'cost $':>8} {'$ per pass':>11}")
    for s in summary:
        per_pass = s["cost_usd"] / s["passed"] if s["passed"] else float("inf")  # type: ignore[operator]
        print(f"{s['model']:<20} {s['passed']}/{s['total']:<4} {s['calls']:>6} "
              f"{s['cost_usd']:>8.4f} {per_pass:>11.4f}")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

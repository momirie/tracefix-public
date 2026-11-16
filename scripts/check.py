"""Run every check CI runs, in the same order, and report each one. Use before pushing.

    uv run python scripts/check.py          # lint, format, types, dead code, CLI, tests
    uv run python scripts/check.py --fast   # everything except the test suite

Exits 0 only if every check passed. Every check runs even after one fails, so one run shows all.
The tests run with TRACEFIX_OLD_PYTHONS=required: the old-Python tests fail instead of skipping
when the project Pythons 3.9/3.10 (set up first, by scripts/old_pythons.py) are missing.
"""

import os
import subprocess
import sys
import time

# The Action's own files, and the example workflows the docs tell users to copy.
ACTIONS = ["action.yml", "report/action.yml"]
EXAMPLES = ["docs/examples/tracefix.yml", "docs/examples/tracefix-fork.yml"]
# Tracefix's code that runs inside the project's Python (3.9+): also checked at those versions.
RUNTIME = ["src/tracefix/attack_runtime.py", "src/tracefix/runtime_state.py"]
# The parallel pass: everything but the acceptance cases and the serial tests (their own phases).
MAIN_TESTS = "not serial and not acceptance"

CHECKS = [
    ("lint", ["ruff", "check", "."]),
    ("format", ["ruff", "format", "--check", "."]),
    ("types", ["mypy"]),  # the files listed in pyproject.toml
    ("types-3.10", ["mypy", "--strict", "--python-version", "3.10", *RUNTIME]),  # mypy's oldest
    ("syntax-3.9", ["vermin", "-t=3.9-", "--no-tips", "--violations", *RUNTIME]),
    ("deadcode", ["vulture"]),
    ("workflows", ["actionlint"]),
    ("examples", ["actionlint", *EXAMPLES]),
    ("actions-sec", ["zizmor", "--offline", ".github", *ACTIONS, *EXAMPLES]),
    ("cli", ["tracefix", "--help"]),
    ("tests-pythons", ["python", "scripts/old_pythons.py"]),  # 3.9/3.10 for the tests (uv)
    # Tests run in parallel (pytest-xdist), then the end-to-end acceptance cases with few workers,
    # then the few marked `serial` alone: those write where every run's tamper watch looks, so
    # beside other tests they would make them fail. The acceptance cases are load-sensitive: beside
    # the whole suite on every core, Break My Fix on method_good hit its 120 s safety limit
    # (docs/NOTES.md). `worksteal` lets an idle worker take queued tests while another runs a long
    # one (as CI does).
    ("tests", ["pytest", "-q", "-n", "auto", "--dist", "worksteal", "-m", MAIN_TESTS]),
    ("tests-acceptance", ["pytest", "-q", "-n", "4", "--dist", "worksteal", "-m", "acceptance"]),
    ("tests-serial", ["pytest", "-q", "-m", "serial"]),
]


def main(argv: list[str]) -> int:
    fast = "--fast" in argv
    results: list[tuple[str, bool, float]] = []
    for name, cmd in CHECKS:
        if fast and name.startswith("tests"):
            continue
        print(f"\n=== {name}: {' '.join(cmd)}", flush=True)
        start = time.monotonic()
        env = {**os.environ, "TRACEFIX_OLD_PYTHONS": "required"}
        ok = subprocess.run(cmd, env=env).returncode == 0
        results.append((name, ok, time.monotonic() - start))
    print("\n=== summary")
    for name, ok, seconds in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<16} {seconds:6.1f}s")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

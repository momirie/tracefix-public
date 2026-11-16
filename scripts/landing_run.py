"""Make the runs shown on the website, with the test suite's recorded model answers (no network,
no API key, $0): real fixture repos, real copies and pytest runs, the real receipts.

One case (default partial_fix): print `tracefix verify`'s output with the second each line
appeared. The home page's replay (docs/landing/_src/pages/index.html, section "how") is copied
from docs/landing-notes/run-partial_fix.log, made this way; then run scripts/build_site.py.

    uv run python scripts/landing_run.py OUT_DIR > docs/landing-notes/run-partial_fix.log 2>&1
    uv run python scripts/landing_run.py OUT_DIR --case good_fix  # another case

Every case (`--all`, about 17 minutes): each fixture's receipt folder and its terminal log go to
docs/landing/_data/receipts/<case>/ (receipt.json, receipt.md, findings/, run.log) for the
receipt gallery. The older-Python cases run with `--python`, as tests/test_pipeline_recorded.py
runs them: set them up first with `uv run python scripts/old_pythons.py`.

    uv run python scripts/landing_run.py --all [--case CASE ...]
"""

import argparse
import shutil
import sys
import tempfile
import time
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import TextIO

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "scripts")]

import make_fixtures  # noqa: E402
import old_pythons  # noqa: E402
from conftest import OLD_PYTHONS  # noqa: E402
from test_fixtures import load_expected  # noqa: E402
from test_guard_recorded import provider  # noqa: E402

from tracefix.cli import main as verify  # noqa: E402

RECEIPTS = ROOT / "docs" / "landing" / "_data" / "receipts"
SHOWN_OUT = "tracefix-receipt"  # how the logs show the temporary --out folder


class Stamped:
    """A text stream that prefixes each line with the seconds since `start`."""

    def __init__(self, stream: TextIO, start: float) -> None:
        self.stream, self.start, self.at_line_start = stream, start, True

    def write(self, text: str) -> int:
        for part in text.splitlines(keepends=True):
            if self.at_line_start:
                self.stream.write(f"[{time.monotonic() - self.start:7.1f}] ")
            self.stream.write(part)
            self.at_line_start = part.endswith("\n")
        self.stream.flush()
        return len(text)

    def flush(self) -> None:
        self.stream.flush()

    def isatty(self) -> bool:
        return False


def project_python(case: str) -> list[str]:
    """`--python` for a case its expected.json pins to an older Python; none otherwise."""
    version = load_expected(case).get("python")
    if version is None:
        return []
    python = old_pythons.python_in(OLD_PYTHONS / str(version))
    if not python.is_file():
        raise SystemExit(f"{case} needs Python {version}: run scripts/old_pythons.py first")
    return ["--python", str(python)]


def run_case(case: str, work: Path, log: TextIO) -> int:
    """Build `case` in `work` and verify it, writing the stamped output to `log`."""
    repo = make_fixtures.build_case(case, work / "fixture")
    issue = make_fixtures.FIXTURES_DIR / case / "ISSUE.md"
    argv = ["verify", "--repo", str(repo), "--base", "base", "--head", "head",
            "--issue", str(issue), "--out", str(work / "receipt")]  # fmt: skip
    argv += project_python(case)
    stamped = Stamped(log, time.monotonic())
    with redirect_stdout(stamped), redirect_stderr(stamped):
        return verify(argv, provider=provider())


def save_case(case: str, dest: Path) -> int:
    """Run `case` and keep its receipt folder and log in `dest/<case>/`, temporary paths masked."""
    with tempfile.TemporaryDirectory(prefix="tracefix-landing-") as tmp:
        work, log = Path(tmp), StringIO()
        code = run_case(case, work, log)
        target = dest / case
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(work / "receipt", target)
        text = log.getvalue().replace(str(work / "receipt"), SHOWN_OUT).replace(str(work), "")
        (target / "run.log").write_text(text, encoding="utf-8", newline="\n")
    return code


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("out", nargs="?", type=Path, help="one case: where to build and verify it")
    parser.add_argument("--case", action="append", choices=sorted(make_fixtures.ALL_CASES))
    parser.add_argument("--all", action="store_true", help=f"every case, saved in {RECEIPTS}")
    args = parser.parse_args(argv)
    if args.all == (args.out is not None):
        parser.error("give OUT_DIR (one case) or --all")
    if not args.all:
        [case] = args.case or ["partial_fix"]
        return run_case(case, args.out, sys.__stdout__)
    failed = []
    for case in args.case or sorted(make_fixtures.ALL_CASES):
        started = time.monotonic()
        code = save_case(case, RECEIPTS)
        print(f"{case}: exit {code} ({time.monotonic() - started:.0f}s)", file=sys.__stderr__)
        if code != 0:
            failed.append(case)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

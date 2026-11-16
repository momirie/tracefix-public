"""Command-line entry point (plan P15).

Usage: `tracefix verify --repo PATH --base REF --head REF --issue FILE|TEXT|-`

Exit 0 when a receipt was written, whatever its level (the GitHub Action maps levels to a check);
2 when there was nothing to verify (bad arguments, not a repo, an unknown ref, bad settings, no
strict isolation under --require-strict, no receipt in the --previous folder); 3 when Tracefix
itself failed (a bug in Tracefix).
"""

import argparse
import re
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path

from tracefix import __version__
from tracefix.attack import AttackResult
from tracefix.config import ConfigError, FileSettings, from_flags
from tracefix.llm import EFFORTS, AnthropicProvider, Provider
from tracefix.pipeline import Request, SetupError, Verified, verify
from tracefix.previous import PreviousError, load
from tracefix.receipt import BLIND_TEST_FILE, finding_file, repro_file
from tracefix.receipt_md import render
from tracefix.repro import BlindResult, ReproResult

EXIT_OK = 0
EXIT_NOTHING_TO_VERIFY = 2  # also argparse's own exit code for bad arguments
EXIT_INTERNAL_ERROR = 3
MAX_ISSUE_CHARS = 100_000
DEFAULT_OUT = "tracefix-receipt"
_FINDING_FILE = re.compile(r"(?:finding|previous)_\d+\.py")


class UsageError(Exception):
    """The arguments can't be used: nothing to verify (exit 2)."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tracefix",
        description="Verify a bug fix and produce a Fix Receipt.",
    )
    parser.add_argument("--version", action="version", version=f"tracefix {__version__}")
    subcommands = parser.add_subparsers(dest="command", required=True)

    verify_cmd = subcommands.add_parser(
        "verify", help="Verify a fix between two git refs and write a receipt."
    )
    verify_cmd.add_argument("--repo", required=True, help="Path to the git repository.")
    verify_cmd.add_argument("--base", required=True, help="Git ref before the fix (buggy).")
    verify_cmd.add_argument("--head", required=True, help="Git ref with the fix.")
    verify_cmd.add_argument(
        "--issue", required=True, help="Issue description: a file path, literal text, or - (stdin)."
    )
    verify_cmd.add_argument(
        "--out", default=DEFAULT_OUT, help=f"Folder for the receipt (default: ./{DEFAULT_OUT})."
    )
    verify_cmd.add_argument(
        "--json", action="store_true", help="Print the receipt JSON alone on stdout."
    )
    verify_cmd.add_argument(
        "--config", help="A settings file to use instead of tracefix.yml at the base commit."
    )
    verify_cmd.add_argument(
        "--model", action="append", default=[], metavar="ROLE=MODEL",
        help="The model for one role (reproducer, mutator, adversary, judge); repeatable.",
    )  # fmt: skip
    verify_cmd.add_argument("--effort", choices=EFFORTS, help="The models' effort level.")
    verify_cmd.add_argument("--max-tokens", type=int, help="Tokens per model answer.")
    verify_cmd.add_argument("--max-llm-calls", type=int, help="Model calls per run.")
    verify_cmd.add_argument("--token-budget", type=int, help="Tokens per run (input + output).")
    verify_cmd.add_argument(
        "--suite-timeout", type=int, metavar="SECONDS",
        help="Time limit of one run of the whole test suite.",
    )  # fmt: skip
    verify_cmd.add_argument(
        "--pytest-plugin", action="append", default=[], metavar="MODULE",
        help="A pytest plugin module to load in every run; repeatable.",
    )  # fmt: skip
    verify_cmd.add_argument(
        "--require-strict", action="store_true",
        help="Refuse to run (exit 2) unless the tests run at strict isolation (bubblewrap).",
    )  # fmt: skip
    verify_cmd.add_argument(
        "--python", metavar="PATH",
        help="The Python that runs the project's tests (3.9+, with pytest; default: Tracefix's).",
    )  # fmt: skip
    verify_cmd.add_argument(
        "--previous", metavar="DIR",
        help="An earlier receipt folder: its findings are run again on head (L4 needs them fixed).",
    )  # fmt: skip
    return parser


def read_issue(value: str) -> str:
    """The issue text: `-` reads stdin, an existing file is read (UTF-8), else the text itself."""
    try:
        if value == "-":
            text = sys.stdin.buffer.read().decode("utf-8-sig")
        elif Path(value).is_file():
            text = Path(value).read_bytes().decode("utf-8-sig")
        else:
            text = value
    except UnicodeDecodeError:
        raise UsageError("the issue is not UTF-8 text") from None
    except OSError as exc:
        raise UsageError(f"can't read the issue: {exc.strerror or exc}") from None
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        raise UsageError("the issue is empty")
    if len(text) > MAX_ISSUE_CHARS:
        raise UsageError(f"the issue is longer than {MAX_ISSUE_CHARS:,} characters")
    return text


def _models(values: Sequence[str]) -> dict[str, str] | None:
    models: dict[str, str] = {}
    for value in values:
        role, sep, model = value.partition("=")
        if not sep or not role or not model:
            raise UsageError(f"--model takes ROLE=MODEL, not {value!r}")
        if role in models:
            raise UsageError(f"--model is given twice for {role}")
        models[role] = model
    return models or None


def flag_settings(args: argparse.Namespace) -> FileSettings:
    try:
        return from_flags({
            "suite_timeout_seconds": args.suite_timeout,
            "max_llm_calls": args.max_llm_calls,
            "token_budget": args.token_budget,
            "max_tokens": args.max_tokens,
            "effort": args.effort,
            "models": _models(args.model),
            "pytest_plugins": args.pytest_plugin or None,
        })  # fmt: skip
    except ConfigError as exc:
        raise UsageError(str(exc)) from None


def _plain(text: str) -> str:
    """One line a console can always print: no control characters, ASCII only."""
    printable = "".join(c if c.isprintable() else "?" for c in text)
    return printable.encode("ascii", "backslashreplace").decode("ascii")


def _say(line: str) -> None:
    sys.stderr.write(_plain(line) + "\n")
    sys.stderr.flush()


def write_out(out: Path, verified: Verified) -> None:
    """receipt.json, receipt.md, repro/ and findings/ (this run's findings, and the earlier ones
    still open) in `out`. Only Tracefix's own files there are replaced: a finding file from an
    earlier run is removed, nothing else."""
    receipt, run = verified.receipt, verified.run
    files: dict[str, str] = {
        "receipt.json": receipt.model_dump_json(indent=2) + "\n",
        "receipt.md": render(receipt),
    }
    repro = run.result(ReproResult)
    if repro is not None and repro.test_code is not None:
        files[repro_file(repro)] = repro.test_code
    shadow = run.result(BlindResult)
    if shadow is not None and shadow.test_code is not None:
        files[BLIND_TEST_FILE] = shadow.test_code
    attack = run.result(AttackResult)
    for finding in attack.findings if attack else ():
        if finding.repro_code:
            files[finding_file(finding)] = finding.repro_code
    carried = run.still_open.findings if run.still_open else ()
    for entry, open_finding in zip(receipt.previous.still_open if receipt.previous else (), carried,
                          strict=True):  # fmt: skip
        files[entry.file] = open_finding.code
    try:
        (out / "findings").mkdir(parents=True, exist_ok=True)
        (out / "repro").mkdir(exist_ok=True)
        for old in (out / "findings").iterdir():
            if _FINDING_FILE.fullmatch(old.name) and old.is_file():
                old.unlink()
        for rel, text in files.items():
            (out / rel).write_text(text, encoding="utf-8", newline="\n")
    except OSError as exc:  # a bad --out, not a bug in Tracefix
        raise UsageError(f"can't write the receipt to {out}: {exc.strerror or exc}") from None


def run_verify(args: argparse.Namespace, provider: Provider) -> int:
    issue = read_issue(args.issue)
    try:  # read into memory first: --out may be the same folder
        previous = load(Path(args.previous)) if args.previous else None
    except PreviousError as exc:
        raise UsageError(str(exc)) from None
    request = Request(
        repo=Path(args.repo),
        base=args.base,
        head=args.head,
        issue=issue,
        config_file=Path(args.config) if args.config else None,
        flags=flag_settings(args),
        require_strict=args.require_strict,
        previous=previous,
        python=args.python,
    )
    verified = verify(request, provider, _say)
    out = Path(args.out)
    write_out(out, verified)
    receipt = verified.receipt
    if args.json:
        sys.stdout.buffer.write(receipt.model_dump_json(indent=2).encode("utf-8") + b"\n")
        sys.stdout.flush()
    else:
        print(_plain(f"Fix Receipt: {receipt.level.value} (run status: {receipt.status.value})"))
        by = "the Judge (advisory)" if receipt.summary.by == "judge" else "Tracefix"
        print(_plain(f"Summary by {by}: {receipt.summary.text}"))
        print(_plain(f"Written to {out / 'receipt.md'} and {out / 'receipt.json'}"))
    return EXIT_OK


def main(argv: Sequence[str] | None = None, *, provider: Provider | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_verify(args, provider or AnthropicProvider())
    except (UsageError, SetupError) as exc:
        _say(f"tracefix {args.command}: {exc}")
        return EXIT_NOTHING_TO_VERIFY
    except Exception as exc:  # the caller (the Action) needs exit 3, not Python's exit 1
        what = f"{type(exc).__name__}: {exc}"
        _say(f"tracefix {args.command}: internal error (a bug in Tracefix): {what}")
        for line in traceback.format_exc().splitlines():
            _say(line)
        return EXIT_INTERNAL_ERROR

"""Build the demo repo for M9's live acceptance (docs/plans/M9.md, "Live acceptance").

The demo is the partial_fix fixture as a project on GitHub, with Tracefix's example workflows:
- `main`: partial_fix's base, `.github/workflows/` from docs/examples/ pinned to `--pin`,
  `tracefix.yml` (`max_llm_calls: 20`, the spend guard) and `uv.lock`;
- `fix-port-unset`: plus partial_fix's head, the partial fix (PORT unset handled, blank not);
- `fix-port-complete`: plus the complete fix (unset or blank), pushed later onto
  `fix-port-unset` so the same pull request gets a second receipt.

Usage: python scripts/make_demo.py --out DIR --pin SHA [--no-lock]
Then: git -C DIR remote add origin <url>; git -C DIR push origin main fix-port-unset
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "partial_fix"
EXAMPLES = ROOT / "docs" / "examples"
WORKFLOWS = ("tracefix.yml", "tracefix-fork.yml")
PIN = re.compile(r"(momirie/tracefix(?:/report)?@)[0-9a-f]{40}")
SHA = re.compile(r"[0-9a-f]{40}")
BRANCHES = ("main", "fix-port-unset", "fix-port-complete")

DEV_GROUP = '\n[dependency-groups]\ndev = ["pytest>=8"]\n'
GITIGNORE = ".venv/\n__pycache__/\n.pytest_cache/\ntracefix-receipt/\n"
SETTINGS = """\
# Tracefix settings (docs/USAGE.md#settings), read from the base commit.
max_llm_calls: 20
"""
PARTIAL = "    if raw is None:\n        return DEFAULT_PORT\n"
COMPLETE = "    if raw is None or not raw.strip():\n        return DEFAULT_PORT\n"
BLANK_TEST = """

def test_parse_port_defaults_when_blank() -> None:
    assert parse_port("") == 8080
    assert parse_port("  ") == 8080
    assert load_settings({"PORT": ""}).port == 8080
"""


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "core.autocrlf=false", *args],
        cwd=repo, capture_output=True, text=True, check=True,
    )  # fmt: skip
    return result.stdout


def pinned(text: str, pin: str) -> str:
    """The example workflow with every Tracefix action pinned to `pin`."""
    new, count = PIN.subn(lambda m: m.group(1) + pin, text)
    if count == 0:
        raise ValueError("no `momirie/tracefix@<sha>` pin in the example")
    return new


def complete_fix(config: str, tests: str) -> tuple[str, str]:
    """partial_fix's head with blank PORT handled too, and a test for it."""
    if config.count(PARTIAL) != 1:
        raise ValueError("partial_fix's head no longer has the `raw is None` check")
    return config.replace(PARTIAL, COMPLETE), tests.rstrip("\n") + "\n" + BLANK_TEST


def _replace_tree(repo: Path, source: Path) -> None:
    """The fixture's files in place of the project's (`.git`, `.github` and the demo's own files
    are kept)."""
    for name in ("src", "tests", "README.md"):
        target = repo / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    for item in source.iterdir():
        if item.name in ("__pycache__", ".pytest_cache", "pyproject.toml"):
            continue
        if item.is_dir():
            shutil.copytree(item, repo / item.name, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(item, repo / item.name)


def _commit(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def build(out: Path, pin: str, *, lock: bool = True) -> None:
    if not SHA.fullmatch(pin):
        raise ValueError("--pin must be a full commit id (40 hex characters)")
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"{out} is not empty")
    out.mkdir(parents=True, exist_ok=True)
    git(out, "init", "-q", "--initial-branch=main")

    _replace_tree(out, FIXTURE / "base")
    pyproject = (FIXTURE / "base" / "pyproject.toml").read_text(encoding="utf-8")
    (out / "pyproject.toml").write_text(pyproject + DEV_GROUP, encoding="utf-8", newline="\n")
    (out / ".gitignore").write_text(GITIGNORE, encoding="utf-8", newline="\n")
    (out / "tracefix.yml").write_text(SETTINGS, encoding="utf-8", newline="\n")
    workflows = out / ".github" / "workflows"
    workflows.mkdir(parents=True)
    for name in WORKFLOWS:
        text = pinned((EXAMPLES / name).read_text(encoding="utf-8"), pin)
        (workflows / name).write_text(text, encoding="utf-8", newline="\n")
    if lock:
        subprocess.run(["uv", "lock", "--directory", str(out)], check=True)
    _commit(out, "Add settings loader and the Tracefix workflows")

    git(out, "switch", "-q", "-c", "fix-port-unset")
    _replace_tree(out, FIXTURE / "head")
    _commit(out, "Fix crash when PORT is unset")

    git(out, "switch", "-q", "-c", "fix-port-complete")
    config_path = out / "src" / "svc" / "config.py"
    tests_path = out / "tests" / "test_config.py"
    config, tests = complete_fix(
        config_path.read_text(encoding="utf-8"), tests_path.read_text(encoding="utf-8")
    )
    config_path.write_text(config, encoding="utf-8", newline="\n")
    tests_path.write_text(tests, encoding="utf-8", newline="\n")
    _commit(out, "Also fall back to the default port when PORT is blank")
    git(out, "switch", "-q", "main")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pin", required=True, help="the Tracefix commit the workflows use")
    parser.add_argument("--no-lock", action="store_true", help="skip `uv lock` (tests)")
    args = parser.parse_args(argv)
    try:
        build(args.out, args.pin, lock=not args.no_lock)
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"make_demo: {exc}", file=sys.stderr)
        return 2
    print(f"built {args.out}: branches {', '.join(BRANCHES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Build the ground-truth fixture repos from tests/fixtures/<case>/{base,head}/.

Each case becomes a real git repo with two commits: `base` (buggy) and `head` (the "fix").
Builds are reproducible: fixed author, committer and dates, no user/system git config,
LF line endings. Only base/ and head/ go into the repo; ISSUE.md, expected.json and
oracle/ stay outside so the answers never leak into what Tracefix reads.

Usage: python scripts/make_fixtures.py [--out build/fixtures] [case ...]
"""

import argparse
import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "tests" / "fixtures"
DEFAULT_OUT = ROOT / "build" / "fixtures"

# case -> (base commit message, head commit message)
CASES: dict[str, tuple[str, str]] = {
    "good_fix": (
        "Add pagination helpers",
        "Fix missing last page when item count is not a multiple of per_page",
    ),
    "partial_fix": (
        "Add settings loader",
        "Fix crash when PORT is not set",
    ),
    "wrong_but_green": (
        "Add histogram bucketing",
        "Fix wrong buckets for large values",
    ),
    "test_weakened": (
        "Add slugify",
        "Fix trailing dash in slugs",
    ),
    "special_cased": (
        "Add billing calendar",
        "Fix Feb 29 appearing in 2100 schedules",
    ),
    "unguarded_test": (
        "Add truncate helper",
        "Fix truncate exceeding max_len",
    ),
    "no_fix": (
        "Add contact import dedupe",
        "Fix duplicate contacts on import",
    ),
    "env_broken": (
        "Add weekly metrics report",
        "Fix week number off by one on Mondays",
    ),
    "method_partial": (
        "Add gateway listener",
        "Fix crash when no port is configured",
    ),
    "method_good": (
        "Add version bumping",
        "Fix minor bump keeping the patch number",
    ),
}
# Cases whose project needs an older Python than Tracefix's own (M10 part 2; the version is
# "python" in expected.json). Built like the others, but only tests/test_fixtures.py and the
# end-to-end acceptance test run them, with that version's venv (scripts/old_pythons.py).
OLD_PYTHON_CASES: dict[str, tuple[str, str]] = {
    "py39_partial": (
        "Add ordinal positions for league tables",
        "Fix 11st, 12nd and 13rd in the final table",
    ),
}
ALL_CASES = CASES | OLD_PYTHON_CASES

BASE_DATE = "2026-01-01T12:00:00+00:00"
HEAD_DATE = "2026-01-01T13:00:00+00:00"
SKIP_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
FIXTURE_EMAIL = "fixtures@tracefix.invalid"
# GIT_CONFIG_GLOBAL needs git 2.32; --initial-branch needs 2.28.
MIN_GIT_VERSION = (2, 32)


def tag_ref(name: str) -> str:
    """Fully qualified tag ref. Bare `head` is ambiguous: on case-insensitive filesystems
    (Windows, macOS) git matches it to .git/HEAD before the `head` tag."""
    return f"refs/tags/{name}"


def git_env(date: str) -> dict[str, str]:
    """Environment that makes git ignore user config and produce fixed commit metadata."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="Fixture Author",
        GIT_AUTHOR_EMAIL=FIXTURE_EMAIL,
        GIT_COMMITTER_NAME="Fixture Author",
        GIT_COMMITTER_EMAIL=FIXTURE_EMAIL,
        GIT_AUTHOR_DATE=date,
        GIT_COMMITTER_DATE=date,
    )
    return env


def git(repo: Path, *args: str, date: str = BASE_DATE) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=git_env(date),
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return result.stdout.strip()


@cache
def require_git_version() -> None:
    out = subprocess.run(
        ["git", "--version"], capture_output=True, text=True, timeout=30, check=True
    ).stdout
    numbers = out.split()[2].split(".")  # "git version 2.55.0.windows.5"
    found = (int(numbers[0]), int(numbers[1]))
    if found < MIN_GIT_VERSION:
        wanted = ".".join(map(str, MIN_GIT_VERSION))
        raise RuntimeError(f"git >= {wanted} is required to build fixtures, found {out.strip()}")


def is_fixture_build(repo: Path) -> bool:
    """True only for a repo this script built (its base commit has the fixture author)."""
    if not (repo / ".git").is_dir():
        return False
    try:
        author = git(repo, "log", "-1", "--format=%ae", tag_ref("base"))
    except subprocess.CalledProcessError:
        return False
    return author == FIXTURE_EMAIL


def copy_tree(src: Path, dest: Path) -> None:
    """Copy src into dest, normalising text to LF and skipping caches."""
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if any(part in SKIP_NAMES for part in rel.parts) or path.suffix == ".pyc":
            continue
        target = dest / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


def clear_worktree(repo: Path) -> None:
    for child in repo.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            rmtree(child)
        else:
            child.unlink()


def _make_writable(func: Callable[..., Any], path: str, _exc: object) -> None:
    # git marks object files read-only; Windows refuses to delete those without this.
    os.chmod(path, stat.S_IWRITE)
    func(path)


def rmtree(path: Path) -> None:
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_make_writable)
    else:
        shutil.rmtree(path, onerror=_make_writable)


def build_case(case: str, out_root: Path) -> Path:
    """Build one fixture repo at out_root/case and return its path."""
    if case not in ALL_CASES:
        raise ValueError(f"unknown fixture case: {case}")
    src = FIXTURES_DIR / case
    for part in ("base", "head"):
        if not (src / part).is_dir():
            raise FileNotFoundError(f"missing {src / part}")
    base_msg, head_msg = ALL_CASES[case]
    require_git_version()

    repo = out_root / case
    if repo.exists():
        if not is_fixture_build(repo):
            raise FileExistsError(f"{repo} exists and is not a fixture build; refusing to delete")
        rmtree(repo)
    repo.mkdir(parents=True)

    git(repo, "init", "--quiet", "--template=", "--initial-branch=main")
    git(repo, "config", "core.autocrlf", "false")
    git(repo, "config", "commit.gpgsign", "false")

    copy_tree(src / "base", repo)
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "--no-verify", "-m", base_msg, date=BASE_DATE)
    git(repo, "tag", "base")

    clear_worktree(repo)
    copy_tree(src / "head", repo)
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "--no-verify", "-m", head_msg, date=HEAD_DATE)
    git(repo, "tag", "head")
    return repo


def build_all(out_root: Path, cases: list[str] | None = None) -> dict[str, Path]:
    return {case: build_case(case, out_root) for case in (cases or list(ALL_CASES))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    parser.add_argument("cases", nargs="*", help="cases to build (default: all)")
    args = parser.parse_args(argv)
    for case, repo in build_all(args.out, args.cases or None).items():
        base = git(repo, "rev-parse", "--short", tag_ref("base"))
        head = git(repo, "rev-parse", "--short", tag_ref("head"))
        print(f"{case:<16} base={base} head={head}  {repo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

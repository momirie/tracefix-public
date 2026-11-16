"""Run scripts/check.py on a commit in a worktree of its own, so the working copy stays free.

    uv run python scripts/check_at.py              # HEAD
    uv run python scripts/check_at.py REF --fast   # any commit; check.py's flags pass through

The full check takes 30-45 minutes and tests the files on disk, so it can't run in the working
copy while it is being edited. This keeps one worktree beside the repo (`<repo>-check`), moves
it to the commit each time and runs check.py there, with that worktree's own environment (uv
syncs it from its uv.lock). Its `.venv` and `.old-pythons` are kept between runs, so only the
first run builds them. Exits with check.py's exit code.

Only one check at a time: the suite uses every core, and two at once make the load-sensitive
tests fail (docs/NOTES.md).
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKTREE = ROOT.with_name(ROOT.name + "-check")
KEEP = (".venv", ".old-pythons")  # kept by `git clean`: rebuilding them costs minutes


def git(*args: str, cwd: Path = ROOT) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def move_worktree(ref: str) -> str:
    """The worktree at `ref` (detached, its other files removed); the commit's id."""
    sha = git("rev-parse", "--verify", f"{ref}^{{commit}}")
    if not (WORKTREE / ".git").exists():
        git("worktree", "add", "--detach", str(WORKTREE), sha)
    else:
        git("checkout", "--detach", "--force", sha, cwd=WORKTREE)
        git("clean", "-fdx", *(f"--exclude={name}" for name in KEEP), cwd=WORKTREE)
    return sha


def main(argv: list[str]) -> int:
    flags = [a for a in argv if a.startswith("-")]
    refs = [a for a in argv if not a.startswith("-")]
    if len(refs) > 1:
        print("usage: check_at.py [REF] [check.py flags]", file=sys.stderr)
        return 2
    sha = move_worktree(refs[0] if refs else "HEAD")
    print(f"check.py on {sha[:12]} in {WORKTREE}", flush=True)
    # This process may run in the main checkout's environment: the worktree uses its own.
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    command = ["uv", "run", "--frozen", "python", "scripts/check.py", *flags]
    code = subprocess.run(command, cwd=WORKTREE, env=env).returncode
    print(f"\ncheck.py on {sha[:12]}: {'PASS' if code == 0 else 'FAIL'}", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

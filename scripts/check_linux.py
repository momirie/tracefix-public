"""Run every check CI runs in a Linux container (Docker), with strict isolation. Use before pushing.

    uv run python scripts/check_linux.py                  # Python 3.11, everything CI runs
    uv run python scripts/check_linux.py --python 3.13    # CI's other Linux version
    uv run python scripts/check_linux.py --fast           # everything except the test suite

The container gets what `git add -A` would commit (tracked and new files, not ignored ones such
as .venv), with LF line endings as CI's checkout has them. Your files and git index are not
touched. It runs scripts/check.py there with bubblewrap required (TRACEFIX_REQUIRE_STRICT=1), as
Linux CI does. Free (no CI minutes); needs Docker Desktop running. Exits with check.py's code.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The codespace's image (.devcontainer/devcontainer.json) plus bubblewrap and a pinned uv, so a
# pass here means what a pass in the codespace means.
BASE_IMAGE = "mcr.microsoft.com/devcontainers/python:1-3.11-bookworm"
UV_IMAGE = "ghcr.io/astral-sh/uv:0.12.21"
IMAGE = "tracefix-check-linux"
CACHE_VOLUME = "tracefix-check-linux-uv"  # uv's downloads and Pythons, kept between runs
DOCKERFILE = f"""\
FROM {BASE_IMAGE}
# The base image lists a Yarn source whose signing key expired (see .devcontainer/setup.sh).
RUN {{ grep -rl yarnpkg /etc/apt/sources.list.d/ || true; }} | xargs -r rm -f \\
    && apt-get update -q && apt-get install -y -q --no-install-recommends bubblewrap \\
    && rm -rf /var/lib/apt/lists/*
COPY --from={UV_IMAGE} /uv /uvx /usr/local/bin/
USER vscode
RUN mkdir -p /home/vscode/.cache/uv /home/vscode/tracefix
ENV TRACEFIX_REQUIRE_STRICT=1 UV_LINK_MODE=copy UV_PYTHON_INSTALL_DIR=/home/vscode/.cache/uv/py
WORKDIR /home/vscode/tracefix
"""
# The codespace's permissions (devcontainer.json says why each is needed): without them
# bubblewrap can't make its namespaces or mount a fresh /proc inside a container.
SANDBOX_FLAGS = [
    "--cap-add", "SYS_ADMIN",
    "--security-opt", "seccomp=unconfined",
    "--security-opt", "apparmor=unconfined",
    "--security-opt", "systempaths=unconfined",
]  # fmt: skip
# Inside: unpack the files from stdin into a one-commit repo (CI's checkout is a git repo too),
# install, show the Python and isolation level, then check.py with this script's own arguments.
# UV_PYTHON, not `uv sync --python`: that flag holds for one command, and the next `uv run` would
# rebuild the environment on the image's 3.11.
INSIDE = """\
set -euo pipefail
export UV_PYTHON="$PY"
tar -x
git init -q && git add -A
git -c user.name=check -c user.email=check@localhost commit -q -m snapshot
uv sync --locked
uv run python -c "import sys; from tracefix.sandbox import probe; print(sys.version, probe())"
uv run python scripts/check.py "$@"
"""


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> bytes:
    return subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True).stdout


def snapshot(repo: Path) -> bytes:
    """A tar of what `git add -A` would commit, made through a temporary index: git applies the
    repo's line-ending rules on the way in, and the real index is never written."""
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        git(repo, "read-tree", "HEAD", env=env)
        git(repo, "add", "-A", env=env)
        tree = git(repo, "write-tree", env=env).decode().strip()
    return git(repo, "-c", "core.autocrlf=false", "archive", "--format=tar", tree)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--python", choices=["3.11", "3.13"], default="3.11")
    parser.add_argument("--fast", action="store_true", help="skip the test suite")
    args = parser.parse_args(argv)
    if (
        shutil.which("docker") is None
        or subprocess.run(["docker", "info"], capture_output=True).returncode
    ):
        print("Docker isn't running: start Docker Desktop and try again.", file=sys.stderr)
        return 2
    print(f"=== image {IMAGE} (the first build takes a few minutes)", flush=True)
    subprocess.run(
        ["docker", "build", "-q", "-t", IMAGE, "-"], input=DOCKERFILE.encode(), check=True
    )
    files = snapshot(ROOT)
    print(f"=== {len(files) // 1024} KiB of files to Linux, Python {args.python}", flush=True)
    command = [
        "docker", "run", "--rm", "-i", *SANDBOX_FLAGS,
        "-v", f"{CACHE_VOLUME}:/home/vscode/.cache/uv", "-e", f"PY={args.python}",
        IMAGE, "bash", "-c", INSIDE, "bash", *(["--fast"] if args.fast else []),
    ]  # fmt: skip
    return subprocess.run(command, input=files).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

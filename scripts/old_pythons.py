"""Set up the project Pythons the tests run old-Python projects with (M10 part 2).

    uv run python scripts/old_pythons.py

Installs Python 3.9 and 3.10 with uv (free) and makes one venv for each in `.old-pythons/<v>`
with pytest and Hypothesis pinned in `tests/old_pythons/requirements-<v>.txt`. Run before the
test suite (scripts/check.py, check_linux.py and CI do), so the tests themselves stay offline.
A venv whose pins haven't changed is kept. Exits 1 if anything fails.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENVS = ROOT / ".old-pythons"
PINS = ROOT / "tests" / "old_pythons"
VERSIONS = ("3.9", "3.10")
STAMP = "tracefix-pins.txt"  # the pins a venv was made from


def python_in(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def _run(*command: str) -> bool:
    print("+", " ".join(command), flush=True)
    return subprocess.run(command).returncode == 0


def make(version: str) -> bool:
    """The venv for one version, with its pins; kept as it is when they haven't changed."""
    venv = VENVS / version
    pins = (PINS / f"requirements-{version}.txt").read_text(encoding="utf-8")
    stamp = venv / STAMP
    if python_in(venv).is_file() and stamp.is_file() and stamp.read_text("utf-8") == pins:
        print(f"{version}: up to date ({venv})")
        return True
    shutil.rmtree(venv, ignore_errors=True)
    ok = (
        _run("uv", "python", "install", version)
        and _run("uv", "venv", "--quiet", "--no-project", "--python", version, str(venv))
        and _run(
            "uv",
            "pip",
            "install",
            "--quiet",
            "--python",
            str(python_in(venv)),
            "-r",
            str(PINS / f"requirements-{version}.txt"),
        )
    )
    if ok:
        stamp.write_text(pins, encoding="utf-8")
    return ok


def main() -> int:
    results = [make(version) for version in VERSIONS]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())

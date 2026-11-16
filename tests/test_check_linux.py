"""scripts/check_linux.py: the files it sends to the container, and that it stays the codespace's
machine. Docker itself isn't needed (the default suite runs without it)."""

from __future__ import annotations

import io
import json
import re
import subprocess
import tarfile
from pathlib import Path

import check_linux

ROOT = Path(__file__).parent.parent


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return done.stdout


def _files(archive: bytes) -> dict[str, bytes]:
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        return {m.name: tar.extractfile(m).read() for m in tar if m.isfile()}  # type: ignore[union-attr]


def test_the_snapshot_is_what_git_add_would_commit_with_lf_endings(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "core.autocrlf", "true")  # as on Windows: CRLF in the working copy
    (repo / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    (repo / "kept.py").write_bytes(b"a = 1\r\n")
    (repo / "gone.py").write_bytes(b"x = 0\r\n")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
    (repo / "kept.py").write_bytes(b"a = 2\r\n")  # changed, not staged
    (repo / "gone.py").unlink()  # deleted, not staged
    (repo / "new.py").write_bytes(b"b = 3\r\n")  # untracked
    (repo / ".venv").mkdir()
    (repo / ".venv" / "big.bin").write_bytes(b"ignored")
    status = _git(repo, "status", "--porcelain")

    files = _files(check_linux.snapshot(repo))

    assert files == {".gitignore": b".venv/\n", "kept.py": b"a = 2\n", "new.py": b"b = 3\n"}
    assert _git(repo, "status", "--porcelain") == status  # the real index is untouched


def test_the_container_is_the_codespaces_machine() -> None:
    text = (ROOT / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8")
    config = json.loads(re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE))  # JSON with comments
    assert config["image"] == check_linux.BASE_IMAGE
    flags = check_linux.SANDBOX_FLAGS
    assert flags[::2] == ["--cap-add"] * len(config["capAdd"]) + ["--security-opt"] * len(
        config["securityOpt"]
    )
    assert flags[1::2] == config["capAdd"] + config["securityOpt"]
    assert config["containerEnv"]["TRACEFIX_REQUIRE_STRICT"] == "1"
    assert "TRACEFIX_REQUIRE_STRICT=1" in check_linux.DOCKERFILE


def test_uv_is_pinned_to_an_exact_version() -> None:
    assert re.fullmatch(r"ghcr\.io/astral-sh/uv:\d+\.\d+\.\d+", check_linux.UV_IMAGE)


def test_every_uv_command_inside_uses_the_chosen_python() -> None:
    """`uv sync --python X` holds for that command only: the next `uv run` rebuilt the
    environment on the image's 3.11, so a "3.13" check ran 3.11."""
    lines = check_linux.INSIDE.splitlines()
    first_uv = next(i for i, line in enumerate(lines) if line.startswith("uv "))
    assert 'export UV_PYTHON="$PY"' in lines[:first_uv]
    assert "--python" not in check_linux.INSIDE

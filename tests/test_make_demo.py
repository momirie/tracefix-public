"""scripts/make_demo.py: the demo repo for M9's live acceptance."""

import subprocess
import sys
from pathlib import Path

import make_demo
import pytest

PIN = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture
def demo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for who in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{who}_NAME", "Demo")
        monkeypatch.setenv(f"GIT_{who}_EMAIL", "demo@tracefix.invalid")
    out = tmp_path / "demo"
    make_demo.build(out, PIN, lock=False)
    return out


def _show(repo: Path, branch: str, path: str) -> str:
    return make_demo.git(repo, "show", f"{branch}:{path}")


def _pytest(repo: Path, branch: str, *args: str) -> subprocess.CompletedProcess[str]:
    make_demo.git(repo, "switch", "-q", branch)
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args]
    return subprocess.run(command, cwd=repo, capture_output=True, text=True, timeout=120)


def test_branches_build_on_each_other(demo: Path) -> None:
    log = make_demo.git(demo, "log", "--format=%s", "fix-port-complete").splitlines()
    assert log == [
        "Also fall back to the default port when PORT is blank",
        "Fix crash when PORT is unset",
        "Add settings loader and the Tracefix workflows",
    ]
    assert make_demo.git(demo, "branch", "--show-current").strip() == "main"


def test_main_holds_the_workflows_pinned_and_the_spend_guard(demo: Path) -> None:
    for name in make_demo.WORKFLOWS:
        text = _show(demo, "main", f".github/workflows/{name}")
        pins = make_demo.PIN.findall(text)
        assert pins, name
        assert f"momirie/tracefix@{PIN}" in text
        assert "a849030" not in text
    assert f"momirie/tracefix/report@{PIN}" in _show(
        demo, "main", ".github/workflows/tracefix-fork.yml"
    )
    assert "max_llm_calls: 20" in _show(demo, "main", "tracefix.yml")
    assert "[dependency-groups]" in _show(demo, "main", "pyproject.toml")


def test_the_partial_fix_is_the_fixture_head(demo: Path) -> None:
    head = make_demo.FIXTURE / "head" / "src" / "svc" / "config.py"
    assert _show(demo, "fix-port-unset", "src/svc/config.py") == head.read_text("utf-8")
    assert "ISSUE" not in make_demo.git(demo, "ls-tree", "-r", "--name-only", "fix-port-unset")


def test_both_fixes_pass_their_tests_but_the_partial_one_breaks_on_blank(demo: Path) -> None:
    complete = _pytest(demo, "fix-port-complete")
    assert complete.returncode == 0, complete.stdout
    partial = _pytest(demo, "fix-port-unset")  # green CI: the Sniper's whole point
    assert partial.returncode == 0, partial.stdout
    probe = (
        "import sys; sys.path.insert(0, 'src'); from svc.config import parse_port; parse_port('')"
    )
    crash = subprocess.run(
        [sys.executable, "-c", probe], cwd=demo, capture_output=True, text=True, timeout=60
    )
    assert crash.returncode != 0 and "ValueError" in crash.stderr


def test_bad_pins_and_changed_fixtures_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="full commit id"):
        make_demo.build(tmp_path / "x", "55db97b")
    with pytest.raises(ValueError, match="pin"):
        make_demo.pinned("uses: actions/checkout@v7\n", PIN)
    with pytest.raises(ValueError, match="raw is None"):
        make_demo.complete_fix("def parse_port(raw): ...\n", "")

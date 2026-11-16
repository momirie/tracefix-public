"""Ground-truth fixtures (M1): build every case and prove it behaves as expected.json says."""

import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

import make_fixtures
import pytest
from conftest import old_python

FIXTURES_DIR = make_fixtures.FIXTURES_DIR
CASES = sorted(make_fixtures.ALL_CASES)
LEVELS = ["COUNTEREXAMPLE", "L0", "L1", "L2", "L3", "L4"]
LEVEL_KINDS = {"exactly", "at_least", "at_most"}
STATUSES = {"ok", "ENVIRONMENT_ERROR"}
NOT_FIND = {"break_my_fix_finding", "integrity_flag", "suspicious_behaviour_change"}
STAGES = {"break_my_fix", "integrity", "behaviour_diff", "guard", "reproduce", "environment"}
EXIT_CODES = {"pass": 0, "fail": 1, "error": 2}
ANSWER_FILES = {"ISSUE.md", "expected.json", "oracle"}
PYTEST_TIMEOUT_S = 120
BASE = make_fixtures.tag_ref("base")
HEAD = make_fixtures.tag_ref("head")
ENV_ALLOWLIST = {
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC",
    "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "LANG", "LC_ALL",
}  # fmt: skip
CHECK_KEYS = {"tests", "ref", "expect"}

# Exact commit ids, so every OS and git version must build byte-identical history.
# After a deliberate fixture edit: run `uv run python scripts/make_fixtures.py` and update these.
PINNED_SHAS = {
    "env_broken": (
        "db9d6ce88f92030252a7a9081c3ce24ff4e48edb",
        "78b206d8c3b0d162ea2959b5dbf4c93c211e29f5",
    ),
    "good_fix": (
        "c8e4f112ba6c8bbbed32b9d2ee1671e41f15fafe",
        "d6954de59ef880c9790b864d37cb8b9846c6a5d8",
    ),
    "method_good": (
        "daec69a8f868c6f3f28ef768317c7ea8b08c6f3c",
        "4b38a3a6f7d2aec65af8f240aed27226576e6cce",
    ),
    "method_partial": (
        "0ac383ab93c563a41b03bee2691067b64878a4af",
        "4ae629c1e8991eb5e13a623327bbffa7f520e45c",
    ),
    "no_fix": (
        "b82706e0cd5a82d5c68f6ba2d5bdeebaf938fe5f",
        "242a3d9cf7f2430b68337e46778905132f8ee848",
    ),
    "partial_fix": (
        "878c55e7676bfcee76a04a572d52e5411a009ab3",
        "8c47ba4eec397549ce7f3d1b6ec8d9224511c655",
    ),
    "special_cased": (
        "9e0465b0bb1b4c839465cff36c62b3a5b405f537",
        "5678c1ff3d68dce79e54a06761f65dea0148af30",
    ),
    "test_weakened": (
        "0888218294713e32e1e9bdfb8fd4077c81712d22",
        "28e91c796929c7679690f6faf1628fb7edb592a7",
    ),
    "py39_partial": (
        "1c75aaf86966fa1d45a089dd76567c995e49bb10",
        "d0df1eb141db41df36ec438e553bdf558382eca7",
    ),
    "unguarded_test": (
        "47cc8c4606eeed586fbad0ff98e4077b8db2f38b",
        "9f620ef67ccea6631762cbad46129919542738a9",
    ),
    "wrong_but_green": (
        "3c7e67a54edfe8745cd3ca82b57110c269797179",
        "458c063fd5dff268a0900bffbb44c6ab77a9b223",
    ),
}


def load_expected(case: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES_DIR / case / "expected.json").read_text("utf-8"))
    return data


def all_checks() -> list[tuple[str, dict[str, str]]]:
    return [(case, check) for case in CASES for check in load_expected(case)["checks"]]


def check_id(item: tuple[str, dict[str, str]]) -> str:
    case, check = item
    return f"{case}:{check['tests']}@{check['ref']}->{check['expect']}"


def git_out(repo: Path, *args: str) -> str:
    return make_fixtures.git(repo, *args)


def export_ref(repo: Path, label: str, dest: Path) -> None:
    """Write the files of the `base`/`head` tag into dest (no .git), like a clean checkout."""
    tar_bytes = subprocess.run(
        ["git", "archive", "--format=tar", make_fixtures.tag_ref(label)],
        cwd=repo,
        env=make_fixtures.git_env(make_fixtures.BASE_DATE),
        capture_output=True,
        timeout=60,
        check=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        tar.extractall(dest, filter="data")


def fixture_env() -> dict[str, str]:
    """Allowlisted env for fixture runs (SPEC §4): no API keys, no PYTHON*/PYTEST_* leaks."""
    env = {k: v for k, v in os.environ.items() if k.upper() in ENV_ALLOWLIST}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return env


def case_python(case: str) -> str:
    """The Python a case's project runs on: its "python" venv, else Tracefix's own."""
    version = load_expected(case).get("python")
    return sys.executable if version is None else str(old_python(version))


def run_pytest(
    workdir: Path, target: str | None, python: str = sys.executable
) -> subprocess.CompletedProcess[str]:
    env = fixture_env()
    cmd = [python, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    if target is not None:
        cmd.append(target)
    return subprocess.run(
        cmd,
        cwd=workdir,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=PYTEST_TIMEOUT_S,
    )


# --- structure -------------------------------------------------------------------------------


def test_every_fixture_dir_is_registered() -> None:
    dirs = sorted(p.name for p in FIXTURES_DIR.iterdir() if p.is_dir() and p.name[0] not in "._")
    assert dirs == CASES


@pytest.mark.parametrize("case", CASES)
def test_case_layout(case: str) -> None:
    src = FIXTURES_DIR / case
    for part in ("base", "head", "oracle"):
        assert (src / part).is_dir(), f"missing {part}/"
    assert (src / "ISSUE.md").read_text("utf-8").strip(), "ISSUE.md is empty"
    assert (src / "oracle" / "test_repro.py").is_file()


@pytest.mark.parametrize("case", CASES)
def test_expected_json_schema(case: str) -> None:
    exp = load_expected(case)
    assert exp["schema"] == 1
    assert exp["case"] == case
    # An older project Python is declared exactly for the cases registered as needing one.
    assert ("python" in exp) == (case in make_fixtures.OLD_PYTHON_CASES)
    assert exp.get("python", "3.9") in {"3.9", "3.10"}
    assert isinstance(exp["summary"], str) and exp["summary"]

    receipt = exp["receipt"]
    assert receipt["status"] in STATUSES
    (kind, level), *rest = receipt["level"].items()
    assert not rest and kind in LEVEL_KINDS and level in LEVELS
    assert isinstance(receipt.get("stages", {}), dict)
    for finding in receipt["must_find"]:
        assert finding["stage"] in STAGES
    assert set(receipt["must_not_find"]) <= NOT_FIND

    assert exp["checks"], "no executable checks"
    for check in exp["checks"]:
        assert CHECK_KEYS <= set(check) <= CHECK_KEYS | {"match"}
        assert check["ref"] in {"base", "head"}
        assert check["expect"] in EXIT_CODES
        if check["expect"] != "pass":
            # A failure only counts if it fails for the intended reason.
            assert check.get("match"), f"{check_id((case, check))} needs a 'match' string"
        tests = check["tests"]
        if tests.startswith("oracle/"):
            assert (FIXTURES_DIR / case / tests).is_file(), f"missing {tests}"
        elif tests.startswith("head:"):
            assert (FIXTURES_DIR / case / "head" / tests.removeprefix("head:")).is_file()
        else:
            assert tests == "suite"


@pytest.mark.parametrize("case", CASES)
def test_repro_oracle_fails_on_base(case: str) -> None:
    exp = load_expected(case)
    if exp["receipt"]["status"] == "ENVIRONMENT_ERROR":
        pytest.skip("environment cannot run tests at all")
    wanted = {"tests": "oracle/test_repro.py", "ref": "base", "expect": "fail"}
    identities = [{k: c[k] for k in CHECK_KEYS} for c in exp["checks"]]
    assert wanted in identities, "every case must prove the bug exists on base"


@pytest.mark.parametrize("case", CASES)
def test_readme_row_matches_expected_level(case: str) -> None:
    readme = (FIXTURES_DIR / "README.md").read_text("utf-8")
    rows = [line for line in readme.splitlines() if line.startswith(f"| `{case}` |")]
    assert len(rows) == 1, f"README needs exactly one table row for {case}"
    receipt = load_expected(case)["receipt"]
    (kind, level), *_ = receipt["level"].items()
    words = {"exactly": "exactly", "at_least": "at least", "at_most": "at most"}
    expected_text = f"**{level}**" if receipt["status"] == "ok" else f"**{receipt['status']}**"
    assert expected_text in rows[0], f"README row for {case} does not say {expected_text}"
    if receipt["status"] == "ok":
        assert f"{words[kind]} **{level}**" in rows[0]


# --- built repos -----------------------------------------------------------------------------


def test_builds_are_reproducible(built: dict[str, Path], tmp_path: Path) -> None:
    again = make_fixtures.build_all(tmp_path)
    for case in CASES:
        for ref in (BASE, HEAD):
            assert git_out(built[case], "rev-parse", ref) == git_out(again[case], "rev-parse", ref)


@pytest.mark.parametrize("case", CASES)
def test_builds_match_pinned_shas(case: str, built: dict[str, Path]) -> None:
    actual = (git_out(built[case], "rev-parse", BASE), git_out(built[case], "rev-parse", HEAD))
    assert actual == PINNED_SHAS[case]


@pytest.mark.parametrize("case", CASES)
def test_history_shape(case: str, built: dict[str, Path]) -> None:
    repo = built[case]
    assert git_out(repo, "rev-parse", f"{HEAD}^") == git_out(repo, "rev-parse", BASE)
    assert git_out(repo, "rev-list", "--count", HEAD) == "2"
    assert git_out(repo, "diff", "--name-only", BASE, HEAD), "head changes nothing"
    assert git_out(repo, "status", "--porcelain") == ""
    for ref in (BASE, HEAD):
        top_level = set(git_out(repo, "ls-tree", "--name-only", ref).splitlines())
        assert not top_level & ANSWER_FILES, f"answer files leaked into {ref}"


def test_head_label_means_head_tag_even_when_base_is_checked_out(tmp_path: Path) -> None:
    # Regression: on case-insensitive filesystems bare `head` resolves to .git/HEAD.
    repo = make_fixtures.build_case("good_fix", tmp_path)
    git_out(repo, "checkout", "--quiet", BASE)
    head_tree = tmp_path / "head_tree"
    export_ref(repo, "head", head_tree)
    head_src = (FIXTURES_DIR / "good_fix" / "head" / "src" / "pager" / "pagination.py").read_bytes()
    exported = (head_tree / "src" / "pager" / "pagination.py").read_bytes()
    assert exported == head_src.replace(b"\r\n", b"\n")


def test_rebuild_refuses_to_delete_foreign_dir(tmp_path: Path) -> None:
    (tmp_path / "good_fix").mkdir()
    (tmp_path / "good_fix" / "precious.txt").write_text("keep me")
    with pytest.raises(FileExistsError):
        make_fixtures.build_case("good_fix", tmp_path)
    assert (tmp_path / "good_fix" / "precious.txt").exists()


def test_rebuild_refuses_to_delete_foreign_git_repo(tmp_path: Path) -> None:
    foreign = tmp_path / "good_fix"
    foreign.mkdir()
    git_out(foreign, "init", "--quiet")
    (foreign / "precious.txt").write_text("keep me")
    with pytest.raises(FileExistsError):
        make_fixtures.build_case("good_fix", tmp_path)
    assert (foreign / "precious.txt").exists()


def test_rebuild_replaces_own_previous_build(tmp_path: Path) -> None:
    first = git_out(make_fixtures.build_case("good_fix", tmp_path), "rev-parse", HEAD)
    second = git_out(make_fixtures.build_case("good_fix", tmp_path), "rev-parse", HEAD)
    assert first == second


# --- behaviour: the ground truth itself ------------------------------------------------------


@pytest.mark.parametrize("item", all_checks(), ids=check_id)
def test_fixture_check(
    item: tuple[str, dict[str, str]], built: dict[str, Path], tmp_path: Path
) -> None:
    case, check = item
    workdir = tmp_path / "tree"
    export_ref(built[case], check["ref"], workdir)

    tests = check["tests"]
    target: str | None = None
    if tests.startswith("oracle/"):
        target = f"tracefix_oracle_{Path(tests).name}"
        shutil.copyfile(FIXTURES_DIR / case / tests, workdir / target)
    elif tests.startswith("head:"):
        rel = tests.removeprefix("head:")
        target = rel
        (workdir / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(FIXTURES_DIR / case / "head" / rel, workdir / rel)

    result = run_pytest(workdir, target, case_python(case))
    output = result.stdout + result.stderr
    expected_code = EXIT_CODES[check["expect"]]
    assert result.returncode == expected_code, (
        f"{check_id(item)}: pytest exited {result.returncode}, expected {expected_code}\n"
        f"{output[-5000:]}"
    )
    if "match" in check:
        assert check["match"] in output, (
            f"{check_id(item)}: failed for the wrong reason; {check['match']!r} not in output\n"
            f"{output[-5000:]}"
        )


@pytest.mark.parametrize("case", sorted(make_fixtures.OLD_PYTHON_CASES))
def test_old_python_case_cannot_run_on_tracefix_python(
    case: str, built: dict[str, Path], tmp_path: Path
) -> None:
    """Its suite doesn't even import on Tracefix's own Python, so an end-to-end run that
    reaches its known answer must have run every stage with --python."""
    workdir = tmp_path / "tree"
    export_ref(built[case], "base", workdir)
    result = run_pytest(workdir, None)
    assert result.returncode == EXIT_CODES["error"], result.stdout[-3000:]
    assert "ImportError: cannot import name 'Iterable' from 'collections'" in result.stdout

"""The Action's YAML (plan P1, P2): action.yml, report/action.yml and the example workflows. These
files hold no logic, but they decide where the secrets go and what reaches a shell, so their rules
are checked here: pins, no `${{` inside a script, the key and token placement, the step order, the
outputs, and the fork flow's shape. Also the release workflow: who may upload to PyPI, and what."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from tracefix import action

ROOT = Path(__file__).parent.parent
ACTION = ROOT / "action.yml"
REPORT = ROOT / "report" / "action.yml"
TRUSTED = ROOT / "docs" / "examples" / "tracefix.yml"
FORK = ROOT / "docs" / "examples" / "tracefix-fork.yml"
WORKFLOWS = ROOT / ".github" / "workflows"
CI, CI_WINDOWS, TESTS = WORKFLOWS / "ci.yml", WORKFLOWS / "ci-windows.yml", WORKFLOWS / "tests.yml"
RELEASE = WORKFLOWS / "release.yml"
ALL = [ACTION, REPORT, TRUSTED, FORK, CI, CI_WINDOWS, TESTS, RELEASE]
KEY = "${{ inputs.anthropic-api-key }}"
HAS_KEY = "${{ inputs.anthropic-api-key != '' }}"
TOKEN = "${{ inputs.github-token }}"
SECRET_KEY = "${{ secrets.ANTHROPIC_API_KEY }}"
WSL_LAUNCHERS = ("system32", "windowsapps")


def _bash() -> str | None:
    """A bash that runs scripts. On Windows a bare "bash" may be WSL's launcher (System32 or
    WindowsApps), which fails when WSL's only distro is Docker Desktop's: Git's bash instead."""
    found = shutil.which("bash")
    if os.name != "nt" or (found and Path(found).parent.name.lower() not in WSL_LAUNCHERS):
        return found
    git = shutil.which("git")
    if git is None:
        return None
    root = Path(git).resolve().parent.parent  # <Git>\cmd\git.exe
    for candidate in (root / "bin" / "bash.exe", root / "usr" / "bin" / "bash.exe"):
        if candidate.is_file():
            return str(candidate)
    return None


BASH = _bash()
USES = re.compile(r"^\s*(?:-\s+)?uses:\s*(\S+)(.*)$")
PINNED = re.compile(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}")
# A reusable workflow in this repo, called from a job: read from the running commit, so not pinned.
LOCAL_WORKFLOW = re.compile(r"\./\.github/workflows/[\w-]+\.yml")
OUTPUT_REF = re.compile(r"^\$\{\{ steps\.([\w-]+)\.outputs\.([\w-]+) \}\}$")


def load(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def steps(path: Path) -> list[dict[str, Any]]:
    return list(load(path)["runs"]["steps"])


def step(path: Path, step_id: str) -> dict[str, Any]:
    (found,) = [s for s in steps(path) if s.get("id") == step_id]
    return found


def all_steps(path: Path) -> list[dict[str, Any]]:
    data = load(path)
    if "runs" in data:
        return list(data["runs"]["steps"])
    found: list[dict[str, Any]] = []
    for job in data["jobs"].values():
        called = job.get("uses", "")
        found += (
            all_steps(ROOT / called) if LOCAL_WORKFLOW.fullmatch(called) else job.get("steps", [])
        )
    return found


def expressions(value: object) -> list[str]:
    """Every string anywhere in `value` (a step, a job, a whole file)."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in expressions(item)]
    if isinstance(value, list):
        return [text for item in value for text in expressions(item)]
    return []


@pytest.mark.parametrize("path", ALL, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_every_action_used_is_pinned_to_a_commit_with_its_version(path: Path) -> None:
    lines = [m for line in path.read_text(encoding="utf-8").splitlines() if (m := USES.match(line))]
    assert lines
    for match in lines:
        ref, comment = match.group(1), match.group(2).strip()
        if LOCAL_WORKFLOW.fullmatch(ref):
            assert (ROOT / ref).is_file(), ref
            continue
        assert PINNED.fullmatch(ref), ref
        assert comment.startswith("#") and len(comment) > 2, f"{ref}: say which version it is"


@pytest.mark.parametrize("path", ALL, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_expression_is_pasted_into_a_script(path: Path) -> None:
    runs = [s["run"] for s in all_steps(path) if "run" in s]
    assert runs
    for script in runs:
        assert "${{" not in script, script


def test_the_api_key_is_only_in_the_verify_step() -> None:
    for s in steps(ACTION):
        texts = expressions(s)
        holds_key = [t for t in texts if "anthropic-api-key" in t]
        if s.get("id") == "verify":
            assert s["env"] == {"PY": "${{ steps.python.outputs.path }}",
                                "PROJECT_PYTHON": "${{ steps.python.outputs.project }}",
                                "ANTHROPIC_API_KEY": KEY}  # fmt: skip
        elif s.get("id") == "prepare":
            assert holds_key == [HAS_KEY]  # only whether there is one: "true" or "false"
            assert s["env"]["INPUT_HAS_API_KEY"] == HAS_KEY
        else:
            assert holds_key == [], s
    assert "anthropic-api-key" not in REPORT.read_text(encoding="utf-8")
    assert "secrets." not in REPORT.read_text(encoding="utf-8")


def test_the_token_is_only_in_prepare_and_report() -> None:
    for path in (ACTION, REPORT):
        for s in steps(path):
            holds_token = [t for t in expressions(s) if "github-token" in t]
            if s.get("id") in ("prepare", "report"):
                assert holds_token == [TOKEN] and s["env"]["INPUT_GITHUB_TOKEN"] == TOKEN
            else:
                assert holds_token == [], s
            assert "github.token" not in str(s.get("env", {}))


def test_the_steps_run_in_order_and_verify_only_when_prepare_found_work() -> None:
    names = [s.get("id") or s.get("uses", "").split("@")[0] or s["name"] for s in steps(ACTION)]
    assert names == [
        "Install bubblewrap (strict isolation, Linux)",
        "astral-sh/setup-uv",
        "python",
        "prepare",
        "verify",
        "actions/upload-artifact",
        "report",
    ]
    assert step(ACTION, "verify")["if"] == "steps.prepare.outputs.skip == 'false'"
    condition = step(ACTION, "report")["if"]
    assert "!cancelled()" in condition and "steps.prepare.outcome == 'success'" in condition
    (upload,) = [s for s in steps(ACTION) if s.get("uses", "").startswith("actions/upload")]
    assert "!cancelled()" in upload["if"]
    assert upload["with"]["overwrite"] is True
    assert upload["with"]["path"] == "${{ steps.prepare.outputs.receipt-dir }}"
    assert upload["with"]["name"] == "${{ steps.prepare.outputs.artifact-name }}"


def test_python_steps_run_the_action_module_with_the_chosen_interpreter() -> None:
    for name in action.STEPS:
        s = step(ACTION, name)
        assert s["run"] == f'"$PY" -P -m tracefix.action {name}'
        assert s["env"]["PY"] == "${{ steps.python.outputs.path }}"
        assert s["shell"] == "bash"


def test_every_input_reaches_the_python_steps_that_read_it() -> None:
    declared = set(load(ACTION)["inputs"])
    passed_on = declared - {"anthropic-api-key", "python", "github-token"}
    for name in ("prepare", "report"):
        env = step(ACTION, name)["env"]
        for input_name in passed_on:
            variable = "INPUT_" + input_name.upper().replace("-", "_")
            assert env[variable] == f"${{{{ inputs.{input_name} }}}}", (name, variable)
    report_inputs = set(load(REPORT)["inputs"])
    env = step(REPORT, "report")["env"]
    assert {v.removeprefix("INPUT_").lower().replace("_", "-") for v in env} == report_inputs


def test_the_skip_and_crash_paths_still_reach_the_report() -> None:
    """A skip in the fork flow (report: false) still uploads its state, so job 2 can post it."""
    (upload,) = [s for s in steps(ACTION) if s.get("uses", "").startswith("actions/upload")]
    assert "steps.prepare.outputs.skip == 'false' || inputs.report != 'true'" in upload["if"]
    assert "inputs.report == 'true'" in step(ACTION, "report")["if"]


@pytest.mark.parametrize("path", [ACTION, REPORT], ids=["action", "report"])
def test_outputs_map_to_outputs_the_steps_really_write(path: Path) -> None:
    written = {**action.OUTPUTS, "python": frozenset({"path", "project"})}
    ids = {s.get("id") for s in steps(path)}
    for name, output in load(path)["outputs"].items():
        match = OUTPUT_REF.fullmatch(output["value"])
        assert match, output["value"]
        step_id, key = match.groups()
        assert step_id in ids and key in written[step_id], (name, step_id, key)
    if path == ACTION:
        assert set(load(path)["outputs"]) == action.OUTPUTS["report"]


def test_the_report_action_reads_the_artifact_the_action_uploads() -> None:
    (download,) = [s for s in steps(REPORT) if s.get("uses", "").startswith("actions/download")]
    expected = action.ARTIFACT_PREFIX + "${{ github.event.pull_request.number }}"
    assert download["with"]["name"] == expected
    assert download["with"]["path"] == "${{ runner.temp }}/tracefix/" + action.RECEIPT
    script = step(REPORT, "report")["run"]
    assert "--no-project" in script and "python -P -m tracefix.action report" in script
    # Tracefix's dependencies pinned by its own lock in the job with the write token (M9 S6).
    assert "uv export --frozen --no-dev" in script and '--with-requirements "$pinned"' in script
    assert script.index("uv export") < script.index("uv run")


def test_no_uv_cache_where_untrusted_code_could_write_one() -> None:
    for path in (ACTION, REPORT):
        (uv,) = [s for s in steps(path) if s.get("uses", "").startswith("astral-sh/setup-uv")]
        assert uv["with"]["enable-cache"] is False
    fork_uv = [s for s in all_steps(FORK) if s.get("uses", "").startswith("astral-sh/setup-uv")]
    assert [s["with"]["enable-cache"] for s in fork_uv] == [False]


def test_the_examples_pin_the_same_commits_as_the_action_and_ci() -> None:
    def pins(path: Path) -> dict[str, str]:
        found = [m.group(1) for line in path.read_text(encoding="utf-8").splitlines()
                 if (m := USES.match(line))]  # fmt: skip
        return dict(ref.split("@") for ref in found if not ref.startswith(("momirie/", "./")))

    known = {**pins(CI), **pins(TESTS), **pins(ACTION), **pins(REPORT)}
    for path in (TRUSTED, FORK):
        for name, sha in pins(path).items():
            assert known[name] == sha, (path.name, name)


def test_the_trusted_example_checks_out_full_history_without_a_stored_token() -> None:
    workflow = load(TRUSTED)
    assert list(workflow[True]) == ["pull_request"]  # YAML 1.1 reads `on` as True
    assert workflow["permissions"] == {}
    (job,) = workflow["jobs"].values()
    assert job["permissions"] == {
        "contents": "read", "checks": "write", "pull-requests": "write",
        "issues": "read", "actions": "read",
    }  # fmt: skip
    checkout = job["steps"][0]
    assert checkout["with"] == {"fetch-depth": 0, "persist-credentials": False}
    (tracefix,) = [s for s in job["steps"] if s.get("uses", "").startswith("momirie/tracefix@")]
    assert tracefix["with"] == {"anthropic-api-key": SECRET_KEY}


def test_the_fork_example_keeps_pull_request_code_and_write_access_apart() -> None:
    workflow = load(FORK)
    assert workflow[True] == {"pull_request_target": {"types": ["labeled"]}}
    assert workflow["permissions"] == {}
    verify, report = workflow["jobs"]["verify"], workflow["jobs"]["report"]
    assert verify["if"] == "github.event.label.name == 'tracefix'"
    assert "github.event.label.name == 'tracefix'" in report["if"]
    # Job 1: the model key and a read-only token; the base branch only, never the PR's code.
    assert set(verify["permissions"].values()) == {"read"}
    checkout = verify["steps"][0]
    assert checkout["uses"].startswith("actions/checkout@")
    assert "ref" not in checkout["with"] and checkout["with"]["persist-credentials"] is False
    (tracefix,) = [s for s in verify["steps"] if s.get("uses", "").startswith("momirie/tracefix@")]
    assert tracefix["with"] == {
        "anthropic-api-key": SECRET_KEY, "trust": "untrusted", "report": False,
    }  # fmt: skip
    assert "github.event.pull_request.head" not in FORK.read_text(encoding="utf-8")
    # Job 2: write access, no secret, no checkout, no project code: only the report action.
    assert report["needs"] == "verify"
    assert report["permissions"] == {"checks": "write", "pull-requests": "write"}
    (only,) = report["steps"]
    assert only["uses"].startswith("momirie/tracefix/report@") and "with" not in only
    assert "secrets." not in str(report)


@pytest.mark.skipif(BASH is None, reason="needs bash to run the step's script")
@pytest.mark.parametrize("runner", ["github-hosted", "self-hosted", ""])
def test_the_kernel_setting_changes_only_on_githubs_own_runners(
    tmp_path: Path, runner: str
) -> None:
    """A self-hosted machine would keep it after the job (verifier M9 S5)."""
    (script,) = [s["run"] for s in steps(ACTION) if s.get("name", "").startswith("Install bubble")]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in {"bwrap": "exit 1", "sudo": 'echo "SUDO $*"'}.items():
        (bin_dir / name).write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8", newline="\n")
        (bin_dir / name).chmod(0o755)
    command = f'export PATH="$PWD/bin:$PATH"; RUNNER_ENVIRONMENT="{runner}"\n{script}'
    assert BASH is not None
    result = subprocess.run([BASH, "-c", command], cwd=tmp_path, capture_output=True, text=True,
                            timeout=60)  # fmt: skip
    assert result.returncode == 0, result.stderr
    changed = "SUDO sysctl -w kernel.apparmor_restrict_unprivileged_userns=0" in result.stdout
    assert changed is (runner == "github-hosted"), result.stdout


@pytest.mark.parametrize("path", [CI, CI_WINDOWS], ids=lambda p: p.name)
def test_ci_jobs_cover_every_test_group_once(path: Path) -> None:
    """pytest-split runs group `group` of `splits`: a group missing from a matrix would silently
    leave its share of the tests unrun, and a group past `splits` would fail."""
    job = load(path)["jobs"]["check"]
    assert job["uses"] == "./.github/workflows/tests.yml"
    splits = job["with"]["splits"]
    assert job["with"]["group"] == "${{ matrix.group }}"
    assert job["strategy"]["matrix"]["group"] == list(range(1, splits + 1))
    assert job["strategy"]["fail-fast"] is False


def test_ci_runs_linux_on_a_pinned_image_and_windows_only_on_demand() -> None:
    """Linux's bubblewrap setup is checked on 24.04 only (NOTES), so the image is pinned; Windows
    runs on a label or by hand, never on every push."""
    for path in (CI, CI_WINDOWS, TESTS):
        assert "-latest" not in path.read_text(encoding="utf-8").replace("windows-latest", "")
    assert load(CI)["jobs"]["check"]["with"]["os"] == "ubuntu-24.04"
    windows = load(CI_WINDOWS)
    assert windows[True] == {"pull_request": {"types": ["labeled"]}, "workflow_dispatch": None}
    assert "github.event.label.name == 'ci-windows'" in windows["jobs"]["check"]["if"]
    assert windows["jobs"]["check"]["with"]["os"] == "windows-latest"


def test_the_shared_test_job_runs_the_serial_tests_once_and_balances_the_rest() -> None:
    """The parallel pass leaves out the acceptance cases, which run next in their own step with
    few workers (load-sensitive: docs/NOTES.md), each group its share; then the serial tests.
    Every pass reads, and may record, the caller's durations file."""
    workflow = load(TESTS)
    (job,) = workflow["jobs"].values()
    runs = [s for s in job["steps"] if "pytest" in s.get("run", "")]
    parallel, acceptance, serial = runs
    assert '-m "not serial and not acceptance"' in parallel["run"]
    assert "-n auto" in parallel["run"]
    assert "-m acceptance" in acceptance["run"] and '-n "$WORKERS"' in acceptance["run"]
    assert acceptance["env"]["WORKERS"] == "${{ inputs.acceptance-workers }}"
    assert workflow[True]["workflow_call"]["inputs"]["acceptance-workers"]["default"] == 2
    for step in (parallel, acceptance):
        assert '--group "$GROUP"' in step["run"] and '--splits "$SPLITS"' in step["run"]
        assert "--splitting-algorithm least_duration" in step["run"]
        assert "--dist worksteal" in step["run"]
        assert "if" not in step  # every group runs its share
    assert serial["run"].startswith("uv run pytest -q -m serial ")
    assert serial["if"] == "inputs.group == 1"
    for step in runs:
        assert '--durations-path "$DURATIONS" --store-durations' in step["run"]
        assert step["env"]["DURATIONS"] == "${{ inputs.durations }}"


def test_linux_keeps_the_defaults_and_windows_gets_room_and_its_own_test_times() -> None:
    """Windows' 2-core runners: a longer hang guard, one end-to-end case at a time, and test times
    measured on Windows (the laptop's left its groups 24 to 40 minutes apart)."""
    inputs = load(TESTS)[True]["workflow_call"]["inputs"]
    assert load(TESTS)["jobs"]["test"]["timeout-minutes"] == "${{ inputs.timeout }}"
    assert inputs["timeout"]["default"] == 40
    assert inputs["durations"]["default"] == ".test_durations"
    assert inputs["store-durations"]["default"] is False
    linux = load(CI)["jobs"]["check"]["with"]
    assert not {"timeout", "acceptance-workers", "durations", "store-durations"} & set(linux)
    windows = load(CI_WINDOWS)["jobs"]["check"]["with"]
    assert windows["timeout"] == 60 and windows["acceptance-workers"] == 1
    assert windows["durations"] == ".test_durations_windows" and windows["store-durations"] is True


def test_each_windows_job_uploads_its_times_and_one_job_merges_them() -> None:
    (upload,) = [s for s in all_steps(TESTS) if "upload-artifact" in s.get("uses", "")]
    assert upload["if"] == "always() && inputs.store-durations"
    assert upload["with"]["name"].startswith("durations-")
    assert upload["with"]["path"] == "${{ inputs.durations }}"
    assert upload["with"]["include-hidden-files"] is True  # ".test_durations_windows"
    merge = load(CI_WINDOWS)["jobs"]["durations"]
    assert merge["needs"] == "check" and merge["if"].startswith("always()")
    download, run, out = (s for s in merge["steps"] if "checkout" not in s.get("uses", ""))
    assert download["with"]["pattern"] == "durations-*"
    script = run["run"].split()
    assert script[:3] == ["python3", "scripts/merge_durations.py", ".test_durations_windows"]
    assert (ROOT / script[1]).is_file()
    assert script[3] == f"{download['with']['path']}/*/.test_durations_windows"
    assert out["with"]["path"] == script[-1] and out["with"]["include-hidden-files"] is True


def test_the_vermin_step_runs_in_bash_on_every_os() -> None:
    """PowerShell, Windows' default shell, mangles `-t=3.9-`: vermin then checks against 3.0
    and fails (PR #39's Windows run)."""
    (step,) = [s for s in all_steps(TESTS) if "vermin" in s.get("run", "")]
    assert "-t=3.9-" in step["run"] and step["shell"] == "bash"


@pytest.mark.parametrize("name", [".test_durations", ".test_durations_windows"])
def test_the_committed_test_times_are_durations_files(name: str) -> None:
    import merge_durations

    assert len(merge_durations.load(ROOT / name)) > 1000


def test_ci_runs_on_ready_pull_requests_and_by_hand_only() -> None:
    """No run on push to main (the PR's run tested what merges) and none on draft PRs."""
    ci = load(CI)
    types = ["opened", "synchronize", "reopened", "ready_for_review"]
    assert ci[True] == {"pull_request": {"types": types}, "workflow_dispatch": None}
    assert ci["jobs"]["changes"]["if"] == "${{ !github.event.pull_request.draft }}"
    assert ci["jobs"]["all-checks"]["if"] == "always()"


@pytest.mark.skipif(BASH is None, reason="needs bash to run the job's script")
@pytest.mark.parametrize(
    ("changes", "code", "check", "draft", "passes"),
    [
        ("success", "true", "success", "false", True),
        ("success", "false", "skipped", "false", True),  # docs-only
        ("success", "true", "failure", "false", False),
        ("success", "true", "cancelled", "false", False),
        ("success", "true", "skipped", "false", False),  # code changed but tests didn't run
        ("failure", "", "skipped", "false", False),
        ("skipped", "", "skipped", "true", False),  # draft: never green without tests
        ("skipped", "", "skipped", "false", False),
    ],
)
def test_all_checks_is_green_only_when_tests_passed_or_the_change_was_docs_only(
    changes: str, code: str, check: str, draft: str, passes: bool
) -> None:
    (script,) = [s["run"] for s in load(CI)["jobs"]["all-checks"]["steps"]]
    assert BASH is not None
    env = {"CHANGES": changes, "CODE": code, "CHECK": check, "DRAFT": draft, "PATH": ""}
    result = subprocess.run([BASH, "-c", script], env=env, capture_output=True, text=True,
                            timeout=60)  # fmt: skip
    assert (result.returncode == 0) is passes, result.stdout
    assert ("Draft PR" in result.stdout) is (draft == "true")


HYPOTHESIS_CHECK = "import sys, hypothesis; sys.exit(hypothesis.__version_info__[:2] < (6, 141))"


@pytest.mark.parametrize(("version", "upgraded"), [
    (None, True), ((6, 119, 3), True), ((6, 140, 9), True), ((6, 141, 0), False),
    ((7, 0, 0), False),
])  # fmt: skip
def test_the_action_installs_hypothesis_when_missing_or_older_than_6_141(
    tmp_path: Path, version: tuple[int, int, int] | None, upgraded: bool
) -> None:
    """NOTES #35 (developer, 22 Oct 2026): SWE-rebench-like environments ship Hypothesis 6.119.3,
    which an "is it importable" check let through, leaving Break My Fix inconclusive."""
    assert f"'{HYPOTHESIS_CHECK}'" in step(ACTION, "python")["run"]
    if version is not None:
        (tmp_path / "hypothesis").mkdir()
        (tmp_path / "hypothesis" / "__init__.py").write_text(
            f"__version_info__ = {version!r}\n", encoding="utf-8"
        )
    hide = "" if version is not None else "import sys; sys.modules['hypothesis'] = None; "
    env = {**os.environ, "PYTHONPATH": str(tmp_path)}
    done = subprocess.run([sys.executable, "-c", hide + HYPOTHESIS_CHECK], env=env,
                          capture_output=True, check=False)  # fmt: skip
    assert (done.returncode != 0) is upgraded, done.stderr


def test_tracefix_runs_from_its_own_locked_env_and_the_project_python_runs_the_tests() -> None:
    """Two environments (SPEC §4, M10 part 2): Tracefix in uv's own Python 3.11 with its uv.lock's
    versions; the project's Python (3.9+) gets only Hypothesis, and only when it has none or one
    older than 6.141."""
    script = step(ACTION, "python")["run"]
    assert "sys.version_info < (3, 9)" in script
    assert "uv export --frozen --no-dev" in script and '--project "$GITHUB_ACTION_PATH"' in script
    assert "--python-preference only-managed --python 3.11" in script
    assert '-r "$pinned"' in script and '--no-deps "$GITHUB_ACTION_PATH"' in script
    assert script.index("uv export") < script.index('-r "$pinned"') < script.index("--no-deps")
    assert script.count('"hypothesis>=6.141"') == 1
    assert f"if ! \"$project\" -I -c '{HYPOTHESIS_CHECK}'" in script
    # The project's interpreter never starts without -I: the checkout's own files (a planted
    # sys.py or hypothesis.py in the working folder) can't run before Tracefix's checks.
    starts = [line for line in script.splitlines() if '"$project" -' in line]
    assert len(starts) == 4 and all('"$project" -I -c' in line for line in starts)
    # What Tracefix gets is the interpreter's own sys.executable: a native path on every runner.
    assert "project=$(\"$project\" -I -c 'import sys; print(sys.executable)')" in script
    assert script.index("print(sys.executable)") < script.index(HYPOTHESIS_CHECK)
    assert 'echo "path=$py"' in script and 'echo "project=$project"' in script


def test_the_marketplace_badge_uses_githubs_names_and_keeps_red_for_findings() -> None:
    """GitHub draws the listing's badge from a Feather icon name and one of nine colours; any
    other value makes the listing fail. Red stays a finding's colour (docs/brand/GUIDELINES.md)."""
    branding = load(ACTION)["branding"]
    assert set(branding) == {"icon", "color"}
    colours = {"white", "black", "yellow", "blue", "green", "orange", "red", "purple", "gray-dark"}
    assert branding["color"] in colours - {"red"}
    assert re.fullmatch(r"[a-z]+(-[a-z]+)*", branding["icon"])
    # The Feather icons GitHub leaves out.
    assert branding["icon"] not in {
        "coffee", "columns", "divide-circle", "divide-square", "divide", "frown", "hexagon",
        "key", "meh", "mouse-pointer", "smile", "tool", "x-octagon",
    }  # fmt: skip
    assert "branding" not in load(REPORT)  # only the root action is listed


def test_a_release_uploads_from_a_published_release_only_and_stores_no_secret() -> None:
    """PyPI trusts the workflow's identity (OIDC), so there is no token to leak. Only the upload
    job may ask for that identity; it waits for the `pypi` environment's approval and runs no
    project code: no checkout, and its one script is the upload. A run by hand is a rehearsal:
    it builds and checks, and the upload job is skipped. A pre-release is never built."""
    release = load(RELEASE)
    assert release[True] == {"release": {"types": ["published"]}, "workflow_dispatch": None}
    assert release["permissions"] == {}
    assert "secrets." not in RELEASE.read_text(encoding="utf-8")
    assert set(release["jobs"]) == {"build", "publish"}
    build, publish = release["jobs"]["build"], release["jobs"]["publish"]
    assert build["permissions"] == {"contents": "read"}
    assert build["if"] == "${{ !github.event.release.prerelease }}"
    assert "environment" not in build
    assert (publish["needs"], publish["environment"]) == ("build", "pypi")
    assert publish["if"] == "github.event_name == 'release'"
    assert publish["permissions"] == {"id-token": "write"}
    assert not any("checkout" in step.get("uses", "") for step in publish["steps"])
    scripts = [step["run"] for step in publish["steps"] if "run" in step]
    assert scripts == ["uv publish --trusted-publishing always"]
    # The upload gets exactly what the build job checked: the same artifact, by name.
    (up,) = [s for s in build["steps"] if "upload-artifact" in s.get("uses", "")]
    (down,) = [s for s in publish["steps"] if "download-artifact" in s.get("uses", "")]
    assert up["with"]["name"] == down["with"]["name"]
    assert up["with"]["path"] == down["with"]["path"] == "dist/"
    # The build's last word is the upload: every check runs before it.
    assert build["steps"][-1] is up
    # The two checks about the release itself make no sense in a rehearsal; the package check
    # always runs.
    by_name = {step["name"]: step for step in build["steps"] if "name" in step}
    assert set(by_name) == {TAG_STEP, MAIN_STEP, PACKAGE_STEP}
    assert by_name[TAG_STEP]["if"] == by_name[MAIN_STEP]["if"] == "github.event_name == 'release'"
    assert "if" not in by_name[PACKAGE_STEP]
    # Every script stops at its first failing command, wherever it runs.
    assert release["defaults"] == {"run": {"shell": "bash"}}
    assert all(step["run"].startswith("set -euo pipefail\n") for step in by_name.values())


def test_a_release_is_built_without_a_cache_and_with_the_pins_ci_uses() -> None:
    def pins(path: Path) -> dict[str, str]:
        found = [m.group(1) for line in path.read_text(encoding="utf-8").splitlines()
                 if (m := USES.match(line))]  # fmt: skip
        return dict(ref.split("@") for ref in found if not ref.startswith("./"))

    known = {**pins(CI), **pins(CI_WINDOWS), **pins(TESTS), **pins(ACTION), **pins(REPORT)}
    for name, sha in pins(RELEASE).items():
        assert known[name] == sha, name
    setups = [s for s in all_steps(RELEASE) if "setup-uv" in s.get("uses", "")]
    assert len(setups) == 2
    assert all(s["with"] == {"enable-cache": False} for s in setups)


def test_the_source_package_is_limited_to_the_package() -> None:
    """Hatchling's default packs the whole repository into the source package. The list is
    anchored to the repository's root: a bare "README.md" also matches every README below it."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    sdist = project["tool"]["hatch"]["build"]["targets"]["sdist"]
    assert sdist == {"include": ["/src/tracefix", "/README.md", "/LICENSE"]}


TAG_STEP = "The tag is the version in pyproject.toml"
MAIN_STEP = "The released commit is on main"
PACKAGE_STEP = "The packages hold only the package"
SDIST_FILES = [
    "src/tracefix/__init__.py",
    "src/tracefix/prompts/judge.py",
    "README.md",
    "LICENSE",
    "pyproject.toml",
    "PKG-INFO",
    ".gitignore",
]
WHEEL_FILES = [
    "tracefix/__init__.py",
    "tracefix/prompts/judge.py",
    "tracefix-1.2.3.dist-info/METADATA",
    "tracefix-1.2.3.dist-info/licenses/LICENSE",
]


def _release_script(name: str) -> str:
    (step,) = [s for s in load(RELEASE)["jobs"]["build"]["steps"] if s.get("name") == name]
    return str(step["run"])


def _sdist(folder: Path, names: list[str], name: str = "tracefix-1.2.3.tar.gz") -> None:
    """A stand-in for `uv build`'s source package: dist/<name> holding `names`."""
    (folder / "dist").mkdir(exist_ok=True)
    (folder / "empty").write_bytes(b"")
    with tarfile.open(folder / "dist" / name, "w:gz") as tar:
        for member in names:
            tar.add(folder / "empty", arcname=f"tracefix-1.2.3/{member}")


def _wheel(folder: Path, names: list[str]) -> None:
    """A stand-in for `uv build`'s wheel: dist/tracefix-1.2.3-py3-none-any.whl holding `names`."""
    (folder / "dist").mkdir(exist_ok=True)
    with zipfile.ZipFile(folder / "dist" / "tracefix-1.2.3-py3-none-any.whl", "w") as wheel:
        for member in names:
            wheel.writestr(member, "")


def _check_packages(folder: Path) -> subprocess.CompletedProcess[str]:
    assert BASH is not None
    return subprocess.run([BASH, "-c", _release_script(PACKAGE_STEP)], cwd=folder,
                          capture_output=True, text=True, timeout=60)  # fmt: skip


@pytest.mark.skipif(BASH is None, reason="needs bash to run the step's script")
def test_the_release_accepts_the_packages_a_build_makes(tmp_path: Path) -> None:
    _sdist(tmp_path, SDIST_FILES)
    _wheel(tmp_path, WHEEL_FILES)
    (tmp_path / "dist" / ".gitignore").write_text("*\n")  # uv build leaves one; never uploaded
    result = _check_packages(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "::error::" not in result.stdout


@pytest.mark.skipif(BASH is None, reason="needs bash to run the step's script")
@pytest.mark.parametrize(
    "extra",
    [
        "founder/pricing-strategy.md",
        "docs/journal/2026-11-13.md",
        "tests/fixtures/README.md",  # what a bare "README.md" in the include list lets in
        "CLAUDE.md",
        "src/other/__init__.py",
        "LICENSE.bak",
        "src/tracefix/../../founder/notes.md",
    ],
)
def test_the_release_refuses_a_source_package_with_anything_else_in_it(
    tmp_path: Path, extra: str
) -> None:
    _sdist(tmp_path, [*SDIST_FILES, extra])
    _wheel(tmp_path, WHEEL_FILES)
    result = _check_packages(tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "::error::" in result.stdout and "source package" in result.stdout


@pytest.mark.skipif(BASH is None, reason="needs bash to run the step's script")
@pytest.mark.parametrize("extra", ["tests/test_x.py", "founder/notes.md", "tracefix/../x.py"])
def test_the_release_refuses_a_wheel_with_anything_else_in_it(tmp_path: Path, extra: str) -> None:
    _sdist(tmp_path, SDIST_FILES)
    _wheel(tmp_path, [*WHEEL_FILES, extra])
    result = _check_packages(tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "::error::" in result.stdout and "wheel" in result.stdout


@pytest.mark.skipif(BASH is None, reason="needs bash to run the step's script")
@pytest.mark.parametrize(
    "broken",
    ["no sdist", "no wheel", "nothing", "two sdists", "a stray file", "corrupt sdist",
     "corrupt wheel", "empty sdist"],
)  # fmt: skip
def test_the_release_stops_when_the_packages_cannot_be_checked(tmp_path: Path, broken: str) -> None:
    """The check fails closed: a package that is missing, doubled or unreadable is never "no
    unexpected files" (verifier, 2026-11-13: `|| true` let a failing tar through)."""
    dist = tmp_path / "dist"
    dist.mkdir()
    if broken not in {"no sdist", "nothing"}:
        _sdist(tmp_path, [] if broken == "empty sdist" else SDIST_FILES)
    if broken not in {"no wheel", "nothing"}:
        _wheel(tmp_path, WHEEL_FILES)
    if broken == "two sdists":
        # tar reads a second file name as a member to look for in the first archive.
        _sdist(tmp_path, [*SDIST_FILES, "founder/pricing-strategy.md"], "a-0.tar.gz")
    if broken == "a stray file":
        (dist / "notes.txt").write_text("x")
    if broken == "corrupt sdist":
        (dist / "tracefix-1.2.3.tar.gz").write_bytes(b"not a tarball")
    if broken == "corrupt wheel":
        (dist / "tracefix-1.2.3-py3-none-any.whl").write_bytes(b"not a zip file")
    result = _check_packages(tmp_path)
    assert result.returncode != 0, result.stdout + result.stderr


@pytest.mark.skipif(BASH is None, reason="needs bash to run the step's script")
@pytest.mark.parametrize(
    ("tag", "version", "passes"),
    [
        ("v1.2.3", "1.2.3", True),
        ("1.2.3", "1.2.3", False),
        ("v1.2.4", "1.2.3", False),
        ("v1.2.3-rc1", "1.2.3", False),
        ("", "1.2.3", False),
        ("v", "", False),  # uv printed nothing
        ("v", None, False),  # uv failed
    ],
)
def test_the_release_refuses_a_tag_that_is_not_the_package_version(
    tmp_path: Path, tag: str, version: str | None, passes: bool
) -> None:
    (step,) = [s for s in load(RELEASE)["jobs"]["build"]["steps"] if s.get("name") == TAG_STEP]
    assert step["env"] == {"TAG": "${{ github.event.release.tag_name }}"}
    # `uv version --short` prints the project's version; here a shell function stands in for uv.
    stand_in = "uv() { return 2; }\n" if version is None else f"uv() {{ echo '{version}'; }}\n"
    assert BASH is not None
    result = subprocess.run([BASH, "-c", stand_in + step["run"]], cwd=tmp_path,
                            env={"TAG": tag, "PATH": ""}, capture_output=True, text=True,
                            timeout=60)  # fmt: skip
    assert (result.returncode == 0) is passes, result.stdout + result.stderr


@pytest.mark.skipif(BASH is None, reason="needs bash to run the step's script")
@pytest.mark.parametrize(("where", "passes"), [("main", True), ("older", True), ("side", False)])
def test_the_release_refuses_a_commit_that_is_not_on_main(
    tmp_path: Path, where: str, passes: bool
) -> None:
    """A tag can be put on any commit; only main's commits went through review and CI."""

    def git(*args: str) -> str:
        done = subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
            cwd=tmp_path, check=True, capture_output=True, text=True, timeout=60,
        )  # fmt: skip
        return done.stdout.strip()

    git("init", "-q", "-b", "main")
    git("commit", "-q", "--allow-empty", "-m", "one")
    older = git("rev-parse", "HEAD")
    git("commit", "-q", "--allow-empty", "-m", "two")
    main = git("rev-parse", "HEAD")
    git("update-ref", "refs/remotes/origin/main", main)
    git("checkout", "-q", "-b", "side")
    git("commit", "-q", "--allow-empty", "-m", "not reviewed")
    sha = {"main": main, "older": older, "side": git("rev-parse", "HEAD")}[where]
    assert BASH is not None
    result = subprocess.run([BASH, "-c", _release_script(MAIN_STEP)], cwd=tmp_path,
                            env={**os.environ, "GITHUB_SHA": sha}, capture_output=True, text=True,
                            timeout=60)  # fmt: skip
    assert (result.returncode == 0) is passes, result.stdout + result.stderr

"""Run pytest in a worktree: allowlisted env, timeout, reruns on failure, structured result.

Verdicts later in the pipeline come from these exit codes, never from a model.
"""

import os
import re
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Literal
from xml.etree.ElementTree import Element, ParseError

import defusedxml.ElementTree as SafeElementTree
from defusedxml import DefusedXmlException

from tracefix import sandbox
from tracefix.proctree import ProcessTree
from tracefix.sandbox import Level

DEFAULT_TIMEOUT_S = 300
DEFAULT_RERUNS = 3
OUTPUT_LIMIT = 100_000  # bytes kept from the end of each attempt's output
OUT_FILE = "tracefix-out.jsonl"  # where Tracefix's own in-run code reports (Probe)
OUT_LIMIT = 2_000_000  # bytes read from the start of it; honest output stays far below
ENV_ALLOWLIST = {
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
    "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "LANG", "LC_ALL", "LC_CTYPE",
    "APPDATA", "LOCALAPPDATA", "PROGRAMDATA",
}  # fmt: skip
_MISSING_MODULE = re.compile(r"(ModuleNotFoundError|ImportError): No module named '([^']+)'")
_ERROR_LINE = re.compile(r"^E\s+(\w+(?:Error|Exception))\b", re.MULTILINE)
# Last line of pytest's long traceback: "<path>:<line>: <ExceptionType>"
_CRASH_LINE = re.compile(r"^(.+?):(\d+): ([A-Za-z_][\w.]*)\s*$", re.MULTILINE)
_MESSAGE_TYPE = re.compile(r"^([A-Za-z_][\w.]*)(?::|$)")
_E_LINE = re.compile(r"^E\s+(\S.*)$", re.MULTILINE)  # pytest's explanation lines
MAX_DETAIL = 300
# How pytest starts on a Python without -P (3.9, 3.10): `-c` puts "" (the current folder, the
# copy) first on sys.path, so it is taken off before pytest is imported, which then runs as
# `-m pytest` would. A repo's pytest.py still can't replace the test runner.
BOOTSTRAP = (
    "import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; "
    "runpy.run_module('pytest', run_name='__main__', alter_sys=True)"
)


class Outcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"  # tests failed on every attempt, the same tests each time
    FLAKY = "flaky"  # failed, then a rerun ended differently (passed, other tests, error)
    ERROR = "error"  # collection, internal or usage error (pytest exit 2, 3, 4)
    TIMEOUT = "timeout"
    NO_TESTS = "no_tests"


@dataclass(frozen=True)
class Attempt:
    exit_code: int | None  # None when the run was killed for timing out
    duration_s: float
    failed: tuple[str, ...]  # "classname::name" of failing/erroring tests, from JUnit XML
    output: str  # combined stdout+stderr, last OUTPUT_LIMIT bytes
    tests: int = 0  # test cases in the JUnit report
    skipped: int = 0  # skipped or xfailed
    failures: tuple["FailureInfo", ...] = ()
    report_ok: bool = True  # the JUnit report existed and parsed
    passed: tuple[str, ...] = ()  # "classname::name" of tests that ran and passed
    # What the run wrote to TRACEFIX_OUT (runs with a Probe only; None if nothing). Written inside
    # the process under test, so it is untrusted: callers parse it defensively.
    out: str | None = None


@dataclass(frozen=True)
class Probe:
    """Tracefix's own code for a run (e.g. Break My Fix's attack harness): `modules` (name ->
    source) are written into the run's scratch folder and importable from there, `plugins` (some
    of those names) are loaded with -p, and `env` is added to the run's environment. The run gets
    TRACEFIX_OUT, a file in the scratch folder, and its content comes back as Attempt.out."""

    modules: Mapping[str, str] = field(default_factory=dict)
    plugins: tuple[str, ...] = ()
    env: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class FailureInfo:
    """One failing test case, from pytest's JUnit report."""

    test: str  # "classname::name"
    kind: Literal["failure", "error"]  # error = setup/teardown/collection problem
    exc_type: str | None  # e.g. "AssertionError"
    location: str | None  # crash site "path:line", "/" separators
    message: str = ""  # first line of the failure message, e.g. "AssertionError: assert 2 == 1"
    # An error with no crash line (e.g. pytest's "collection failure"): the last "E   " line of
    # its report, e.g. "ModuleNotFoundError: No module named 'x'". Not part of the signature.
    detail: str = ""

    @property
    def signature(self) -> tuple[str, str, str | None, str | None]:
        return (self.test, self.kind, self.exc_type, self.location)


@dataclass(frozen=True)
class JUnitDetails:
    tests: int
    skipped: int
    failures: tuple[FailureInfo, ...]
    readable: bool = True
    passed: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunResult:
    outcome: Outcome
    command: tuple[str, ...]  # the pytest command, without the sandbox wrapper
    attempts: tuple[Attempt, ...]
    isolation: Level = "basic"  # how the runs were confined (sandbox.py)

    @property
    def first(self) -> Attempt:
        return self.attempts[0]

    @property
    def duration_s(self) -> float:
        return sum(a.duration_s for a in self.attempts)


def safe_env() -> dict[str, str]:
    """Allowlisted environment (SPEC §4): no API keys, no PYTHON*/PYTEST_* settings leak in."""
    env = {k: v for k, v in os.environ.items() if k.upper() in ENV_ALLOWLIST}
    env["PYTHONDONTWRITEBYTECODE"] = "1"  # keep __pycache__ out of the worktree
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONHASHSEED"] = "0"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["COLUMNS"] = "80"  # same output layout on every machine (feedback text names recordings)
    return env


def outcome_for(exit_code: int | None) -> Outcome:
    if exit_code is None:
        return Outcome.TIMEOUT
    return {0: Outcome.PASSED, 1: Outcome.FAILED, 5: Outcome.NO_TESTS}.get(exit_code, Outcome.ERROR)


def _parse_report(junit_xml: Path) -> Element:
    """The report's root element. It is written inside the process under test, so it is parsed
    as untrusted XML: entity declarations and external references are refused."""
    root = SafeElementTree.parse(junit_xml, forbid_dtd=True).getroot()
    if root is None:
        raise ParseError("empty report")
    return root


def failed_tests(junit_xml: Path) -> tuple[str, ...]:
    """Test ids with a <failure> or <error> in pytest's JUnit report; () if unreadable."""
    try:
        root = _parse_report(junit_xml)
    except (OSError, ParseError, DefusedXmlException):
        return ()
    failed = []
    for case in root.iter("testcase"):
        if case.find("failure") is not None or case.find("error") is not None:
            failed.append(f"{case.get('classname', '')}::{case.get('name', '')}")
    return tuple(failed)


def _failure_info(test: str, kind: Literal["failure", "error"], node: Element) -> FailureInfo:
    message = node.get("message", "").splitlines()[0] if node.get("message") else ""
    crashes = _CRASH_LINE.findall(node.text or "")
    if crashes:
        path, line, exc_type = crashes[-1]
        location = f"{path.replace(chr(92), '/')}:{line}"
        return FailureInfo(test, kind, exc_type, location, message)
    typed = _MESSAGE_TYPE.match(message)
    explained = _E_LINE.findall(node.text or "") if kind == "error" else []
    detail = explained[-1].strip()[:MAX_DETAIL] if explained else ""
    return FailureInfo(test, kind, typed.group(1) if typed else None, None, message, detail)


def junit_details(junit_xml: Path) -> JUnitDetails:
    """Counts and failure details from pytest's JUnit report; empty if unreadable."""
    try:
        root = _parse_report(junit_xml)
    except (OSError, ParseError, DefusedXmlException):
        return JUnitDetails(0, 0, (), readable=False)
    tests = skipped = 0
    failures = []
    passed = []
    for case in root.iter("testcase"):
        tests += 1
        test = f"{case.get('classname', '')}::{case.get('name', '')}"
        if case.find("skipped") is not None:
            skipped += 1
        for kind in ("failure", "error"):
            node = case.find(kind)
            if node is not None:
                failures.append(_failure_info(test, kind, node))
                break
        else:
            if case.find("skipped") is None:
                passed.append(test)
    return JUnitDetails(tests, skipped, tuple(failures), passed=tuple(passed))


def _read_tail(path: Path) -> str:
    """The last OUTPUT_LIMIT bytes of a file, decoded; "" if it can't be read."""
    try:
        with path.open("rb") as f:
            f.seek(max(0, path.stat().st_size - OUTPUT_LIMIT))
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _read_out(path: Path) -> str | None:
    """The first OUT_LIMIT bytes of the run's TRACEFIX_OUT file, or None if there is none. Only a
    plain file is read: the process under test could have put a link or a FIFO there."""
    try:
        if path.is_symlink() or not path.is_file():
            return None
        with path.open("rb") as f:
            return f.read(OUT_LIMIT).decode("utf-8", errors="replace")
    except OSError:
        return None


def _install_probe(probe: Probe, scratch: Path, env: dict[str, str]) -> list[str]:
    """Write the probe's modules into the scratch folder and set its env; returns pytest args."""
    for name, source in probe.modules.items():
        env.update(sandbox.write_module(scratch, name, source))
    env.update(probe.env)
    env["TRACEFIX_OUT"] = str(scratch / OUT_FILE)
    return [arg for plugin in probe.plugins for arg in ("-p", plugin)]


@dataclass(frozen=True)
class Loaded:
    """What every attempt of a run loads besides the tests: the copy's package folders (put
    ahead of site-packages by the paths plugin), Tracefix's own probe, and the project's pytest
    plugins (-p, in this order, after the paths plugin and the network block)."""

    import_roots: tuple[Path, ...] = ()
    probe: Probe | None = None
    plugins: tuple[str, ...] = ()


def _attempt(
    base_command: Sequence[str],
    targets: Sequence[str],
    cwd: Path,
    timeout_s: float,
    level: Level,
    loaded: Loaded,
) -> Attempt:
    # Output goes to a file, not a pipe: a leftover child holding the pipe open can't make
    # a finished run look hung, and output is kept whatever happens.
    with tempfile.TemporaryDirectory(prefix="tracefix-run-", ignore_cleanup_errors=True) as tmp:
        scratch = Path(tmp).resolve()
        junit = scratch / "report.xml"
        log = scratch / "output.log"
        env = {**safe_env(), **sandbox.run_env(scratch)}
        extra = _config_args(cwd.resolve(), targets, scratch)
        if loaded.import_roots:
            paths_env, paths_args = sandbox.install_paths(scratch, loaded.import_roots)
            env.update(paths_env)
            extra += paths_args
        if level == "basic":
            net_env, net_args = sandbox.install_netblock(scratch)
            env.update(net_env)
            extra += net_args
        if loaded.probe is not None:
            extra += _install_probe(loaded.probe, scratch, env)
        extra += [arg for plugin in loaded.plugins for arg in ("-p", plugin)]
        command = sandbox.wrap(
            level, [*base_command, *extra, f"--junitxml={junit}"], cwd.resolve(), scratch
        )
        start = time.monotonic()
        with log.open("wb") as out:
            tree = ProcessTree(command, cwd=cwd, env=env, stdout=out)
            try:
                exit_code = tree.wait(timeout_s)
            finally:
                tree.kill_all()  # also after a normal exit: nothing a test started survives
        duration = time.monotonic() - start
        details = junit_details(junit)
        reported = _read_out(scratch / OUT_FILE) if loaded.probe is not None else None
        return Attempt(
            exit_code, round(duration, 3), failed_tests(junit), _read_tail(log),
            details.tests, details.skipped, details.failures, details.readable, details.passed,
            reported,
        )  # fmt: skip


# Where pytest reads its configuration from, in its own order of preference: (file, marker the
# file must contain, or None if the file always counts).
_CONFIG_FILES = (
    ("pytest.ini", None), (".pytest.ini", None), ("pyproject.toml", "[tool.pytest"),
    ("tox.ini", "[pytest]"), ("setup.cfg", "[tool:pytest]"),
)  # fmt: skip


def _start_dir(cwd: Path, targets: Sequence[str]) -> Path:
    """The folder pytest starts its config search from: the targets' common folder, in the copy."""
    dirs = []
    for target in targets:
        path = (cwd / target.split("::", 1)[0]).resolve()
        dirs.append(path if path.is_dir() else path.parent)
    if not dirs:
        return cwd
    common = Path(os.path.commonpath(dirs))
    return common if common.is_relative_to(cwd) else cwd


def _config_in(folder: Path) -> Path | None:
    for name, marker in _CONFIG_FILES:
        path = folder / name
        if path.is_file() and (
            marker is None or marker in path.read_text(encoding="utf-8", errors="replace")
        ):
            return path
    return None


def pytest_config(cwd: Path, targets: Sequence[str]) -> Path | None:
    """The config file pytest uses for these targets in the copy at cwd, or None. pytest's own
    search (from the targets' folder upwards) is followed, but it stops at the top of the copy:
    beyond it, a planted pytest.ini/conftest.py could change every later run."""
    folder = _start_dir(cwd, targets)
    while True:
        config = _config_in(folder)
        if config is not None:
            return config
        if folder == cwd:
            return None
        folder = folder.parent


def _config_args(cwd: Path, targets: Sequence[str], scratch: Path) -> list[str]:
    """Pin pytest's config file, rootdir and conftest search to the copy (see pytest_config)."""
    config = pytest_config(cwd, targets)
    if config is not None:
        return ["-c", str(config), f"--rootdir={config.parent}", f"--confcutdir={cwd}"]
    empty = scratch / "tracefix-empty.ini"
    empty.write_text("[pytest]\n", encoding="utf-8")
    return ["-c", str(empty), f"--rootdir={cwd}", f"--confcutdir={cwd}"]


def _outcome(attempt: Attempt) -> Outcome:
    """Outcome from the exit code, cross-checked with the report: a run whose exit code and
    JUnit report disagree (or that wrote no report) is an error, never a pass or a failure."""
    outcome = outcome_for(attempt.exit_code)
    if outcome is Outcome.PASSED and not (attempt.report_ok and attempt.tests > 0):
        return Outcome.ERROR
    if outcome is Outcome.FAILED and not (attempt.report_ok and attempt.failures):
        return Outcome.ERROR
    return outcome


def run_pytest(
    worktree: Path,
    targets: Sequence[str] = (),
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    reruns: int = DEFAULT_RERUNS,
    python: str = sys.executable,
    safe_path: bool = True,
    isolation: Level | None = None,
    probe: Probe | None = None,
    pytest_args: Sequence[str] = (),
    import_roots: Sequence[Path] = (),
    plugins: Sequence[str] = (),
) -> RunResult:
    """Run pytest in worktree. On test failures, rerun up to `reruns` times to detect flakiness.

    `timeout_s` applies to each attempt. Only real test failures (exit 1) are rerun. Runs are
    confined at `isolation` (default: the strongest level available here, see sandbox.py).
    `probe` adds Tracefix's own code to every attempt (see Probe). `pytest_args` go before
    the targets. `import_roots` (folders in worktree) and `plugins`: see Loaded. `safe_path`:
    `python` has -P (3.11+); else pytest starts through BOOTSTRAP.
    """
    level = isolation or sandbox.sandbox_level()
    # -P: the worktree is not put on sys.path first, so a repo file named pytest.py (or a
    # folder named like a pytest dependency) cannot replace the real test runner.
    # --tb=long on the command line beats a repo's addopts, so crash locations are always reported.
    # -rN: no short summary (its truncation depends on the terminal width, which differs by OS).
    start = ("-P", "-m", "pytest") if safe_path else ("-c", BOOTSTRAP)
    command = (python, *start, "-q", "-p", "no:cacheprovider", "--tb=long", "-rN", "--color=no",
               *pytest_args, *targets)  # fmt: skip
    loaded = Loaded(tuple(import_roots), probe, tuple(plugins))
    attempts = [_attempt(command, targets, worktree, timeout_s, level, loaded)]
    outcome = _outcome(attempts[0])
    if outcome is not Outcome.FAILED:
        return RunResult(outcome, command, tuple(attempts), level)
    for _ in range(reruns):
        rerun = _attempt(command, targets, worktree, timeout_s, level, loaded)
        attempts.append(rerun)
        if _outcome(rerun) is not Outcome.FAILED or rerun.failed != attempts[0].failed:
            return RunResult(Outcome.FLAKY, command, tuple(attempts), level)
    return RunResult(Outcome.FAILED, command, tuple(attempts), level)


class EnvStatus(StrEnum):
    OK = "ok"
    ENVIRONMENT_ERROR = "ENVIRONMENT_ERROR"


@dataclass(frozen=True)
class EnvironmentCheck:
    status: EnvStatus
    reason: str
    error: str | None  # e.g. "ModuleNotFoundError"
    module: str | None  # the missing module, when there is one
    run: RunResult


def check_environment(
    base: Path,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    run_suite: Callable[..., RunResult] = run_pytest,
) -> EnvironmentCheck:
    """Run the base suite before any change. If it can't even run, stop with ENVIRONMENT_ERROR.

    Test failures are fine here (the bug may make tests fail); errors and timeouts are not.
    `run_suite` lets the pipeline run it watched (isolation.check_environment), with the
    project's Python.
    """
    run = run_suite(base, timeout_s=timeout_s, reruns=0)
    if run.outcome is Outcome.TIMEOUT:
        reason = f"the base test suite did not finish within {timeout_s:g}s"
        return EnvironmentCheck(EnvStatus.ENVIRONMENT_ERROR, reason, "Timeout", None, run)
    if run.outcome is not Outcome.ERROR:
        return EnvironmentCheck(EnvStatus.OK, f"base suite {run.outcome}", None, None, run)
    output = run.first.output
    missing = _MISSING_MODULE.search(output)
    if missing:
        error, module = missing.group(1), missing.group(2)
        reason = f"the base test suite cannot import {module!r} ({error})"
        return EnvironmentCheck(EnvStatus.ENVIRONMENT_ERROR, reason, error, module, run)
    other = _ERROR_LINE.search(output)
    error = other.group(1) if other else None
    reason = f"the base test suite could not run (pytest exit {run.first.exit_code})"
    return EnvironmentCheck(EnvStatus.ENVIRONMENT_ERROR, reason, error, None, run)

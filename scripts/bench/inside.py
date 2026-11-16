"""The benchmark's steps inside one task's box (M10 plan P5), run by the project's interpreter.

The host copies this one file into the box and runs it as a plain script:

    python -s inside.py COMMAND REQUEST.json RESULT.json

It imports only the standard library and `tracefix`, never the `bench` package, so it is a single
file to copy. It runs with Tracefix's interpreter: the project's own on 3.11+, else one of its own
(bench.box); then every request names the project's interpreter (`python`), and every run uses
it. The host writes the request and reads the result back strictly (bench.prepare): this process
shares the box with the project's code, so its output is untrusted data like any other.

Commands:
- probe: the interpreter, the isolation level, the installed pytest plugins;
- commits: tf-base on the checkout's HEAD (the base commit, or SWE-rebench's own setup commit
  right on it) plus a setup commit when needed, tf-<kind> per patch, and tf-<kind>-t with
  the hidden tests only when the request has them (prepare's box, never a run box: plan P5),
  built with a temporary index (the checkout's files are never touched); a kind in `reset`
  (an agent's patch, which may change the tests) gets those files back from base first;
- suite: the base suite under Tracefix's runner, watched (its time sets the suite timeout);
- hidden: the hidden tests on `*-t` commits, watched; JUnit ids of what passed and failed;
- verify: `tracefix verify` on one commit, with recorded (or recording) model answers,
  (adversary_live) the adversary's live and the other roles' recorded, or (anchored) every role's
  recorded and live only on a request with no recorded answer;
- replay: an earlier receipt's findings on another commit (`--previous`'s replay);
- functions: the source functions one commit changes against another (tracefix.diffscope).
"""

from __future__ import annotations

import importlib.metadata
import json
import re
import subprocess
import sys
import tempfile
import traceback
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from tracefix import cli, diffscope, interpreter, isolation, previous, runner, sandbox
from tracefix.llm import (
    AnthropicProvider,
    LLMRequest,
    LLMResponse,
    MissingRecording,
    Provider,
    RecordedProvider,
    RecordingProvider,
)
from tracefix.workspace import RunSettings, Workspace, WorkspaceError, git, git_bytes

Json = dict[str, Any]

KIND = re.compile(r"^[a-z0-9][a-z0-9_-]{0,30}$")  # tag names are built from it
SETUP_SUFFIXES = (".py", ".so", ".pyd")  # ignored files a package needs at import time
MAX_SETUP_FILES = 1_000
MAX_SETUP_BYTES = 100 * 1024 * 1024
# A fixed author and date: the same task and patches give the same commit ids on every run.
COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "tracefix-bench", "GIT_AUTHOR_EMAIL": "bench@tracefix.invalid",
    "GIT_COMMITTER_NAME": "tracefix-bench", "GIT_COMMITTER_EMAIL": "bench@tracefix.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
}  # fmt: skip
# SWE-rebench's images may sit one commit past the base: its eval agent's environment setup.
SETUP_COMMIT_EMAIL = "SWEBenchEvalAgent@nebius.com"
SETUP_COMMIT_SUBJECT = "Environment setup changes"
PROBE_MARKER = "TRACEFIX-PROBE "
PROBE_TIMEOUT_S = 120
# Runs in the project's interpreter (3.9+: `EntryPoint.dist` is 3.10+, so each distribution's
# own entry points are read): its version and its pytest plugins, as `probe` lists them here.
PROJECT_PROBE = """\
import json, sys
from importlib import metadata
plugins = []
for dist in metadata.distributions():
    for ep in dist.entry_points:
        if ep.group == "pytest11":
            plugins.append({"name": ep.name, "module": ep.module,
                            "dist": dist.metadata["Name"] or ""})
found = {"python": ".".join(str(n) for n in sys.version_info[:3]), "plugins": plugins}
print("TRACEFIX-PROBE " + json.dumps(found))
"""


def _project(request: Json) -> str | None:
    """The project's interpreter, when it isn't this one."""
    python = request.get("python")
    return python if isinstance(python, str) else None


def probe(request: Json) -> Json:
    """The isolation level, and the project's Python and pytest plugins. A project interpreter
    Tracefix's check refuses gives its reason (`unusable`) and nothing else."""
    level, why = sandbox.probe()
    python = _project(request)
    if python is None:
        version = ".".join(str(n) for n in sys.version_info[:3])
        plugins = [
            {"name": ep.name, "module": ep.module, "dist": ep.dist.name if ep.dist else ""}
            for ep in importlib.metadata.entry_points(group="pytest11")
        ]
    else:
        checked = interpreter.check(python, level)
        if checked.interpreter is None:
            return {"python": "", "level": level, "why": why, "plugins": [],
                    "unusable": checked.reason}  # fmt: skip
        found = _probe_project(python)
        version, plugins = found["python"], found["plugins"]
    return {
        "python": version,
        "level": level,
        "why": why,
        "plugins": sorted(plugins, key=lambda p: (p["module"], p["name"])),
    }


def _probe_project(python: str) -> Json:
    """PROJECT_PROBE's answer (checked by the host, like every result)."""
    with tempfile.TemporaryDirectory(prefix="tfbench-probe-") as tmp:
        done = subprocess.run([python, "-I", "-c", PROJECT_PROBE], cwd=tmp, env=runner.safe_env(),
                              stdin=subprocess.DEVNULL, capture_output=True, check=True,
                              timeout=PROBE_TIMEOUT_S)  # fmt: skip
    lines = done.stdout.decode("utf-8", "replace").splitlines()
    line = next(x for x in lines if x.startswith(PROBE_MARKER))
    found: Json = json.loads(line.removeprefix(PROBE_MARKER))
    return found


# --- commits ------------------------------------------------------------------------------------


def _lines(repo: Path, *args: str) -> list[str]:
    return [p for p in git_bytes(repo, *args).decode("utf-8", "surrogateescape").split("\0") if p]


def setup_files(repo: Path) -> list[str]:
    """Ignored files the copies need: a .py/.so/.pyd beside a tracked __init__.py (e.g.
    setuptools-scm's _version.py, a built extension), outside __pycache__."""
    tracked = set(_lines(repo, "ls-files", "-z"))
    ignored = _lines(repo, "ls-files", "-z", "--others", "--ignored", "--exclude-standard")
    found = []
    for path in ignored:
        pure = PurePosixPath(path)
        init = (pure.parent / "__init__.py").as_posix()
        if pure.suffix in SETUP_SUFFIXES and "__pycache__" not in pure.parts and init in tracked:
            found.append(path)
    return sorted(found)


def image_setup_files(repo: Path, base: str) -> list[str] | None:
    """The files of SWE-rebench's own setup commit when HEAD is one, right on `base` (its
    eval agent's author and subject, `base` its only parent): its hidden tests ran there.
    None when HEAD is any other commit; [] when HEAD is `base`."""
    head = git(repo, "rev-parse", "HEAD").strip()
    if head == base:
        return []
    shown = git(repo, "show", "-s", "--format=%P%n%ae%n%s", "HEAD").strip().splitlines()
    if shown != [base, SETUP_COMMIT_EMAIL, SETUP_COMMIT_SUBJECT]:
        return None
    return _lines(repo, "diff", "-z", "--name-only", "--no-renames", base, "HEAD")


def changed_files(repo: Path) -> list[str]:
    """What the image's checkout changes or adds to HEAD (not ignored files)."""
    changed = _lines(repo, "diff", "-z", "--name-only", "HEAD")
    added = _lines(repo, "ls-files", "-z", "--others", "--exclude-standard")
    return sorted({*changed, *added})


class _Index:
    """A temporary git index, so commits are built without touching the checkout."""

    def __init__(self, repo: Path, folder: Path) -> None:
        self.repo = repo
        self.env = {"GIT_INDEX_FILE": str(folder / "index"), **COMMIT_ENV}

    def git(self, *args: str) -> str:
        out = git_bytes(self.repo, *args, extra_env=self.env)
        return out.decode("utf-8", "replace").strip()

    def applies(self, patch: Path) -> bool:
        check = ("apply", "--cached", "--check", str(patch))
        return git_run_ok(self.repo, check, self.env)

    def commit(self, parent: str, message: str) -> str:
        tree = self.git("write-tree")
        if tree == self.git("rev-parse", f"{parent}^{{tree}}"):
            return parent
        return self.git("commit-tree", tree, "-p", parent, "-m", message)


def git_run_ok(repo: Path, args: tuple[str, ...], env: dict[str, str]) -> bool:
    try:
        git_bytes(repo, *args, extra_env=env)
    except WorkspaceError:
        return False
    return True


def _tag(repo: Path, name: str, sha: str) -> None:
    git(repo, "update-ref", f"refs/tags/{name}", sha)


def _size(repo: Path, paths: list[str]) -> int:
    return sum((repo / p).stat().st_size for p in paths if (repo / p).is_file())


def _patched(
    index: _Index,
    parent: str,
    patch: Path,
    message: str,
    reset: tuple[str, list[str]] | None = None,
) -> str | None:
    """`patch` applied on `parent`; with `reset` (a commit and paths), those paths are first
    put back as that commit has them (a path it lacks is removed)."""
    index.git("read-tree", parent)
    if reset is not None and reset[1]:
        index.git("reset", "-q", reset[0], "--", *reset[1])
    if not index.applies(patch):
        return None
    index.git("apply", "--cached", str(patch))
    return index.commit(parent, message)


def commits(request: Json) -> Json:
    repo = Path(request["repo"])
    head = git(repo, "rev-parse", "HEAD").strip()
    image = image_setup_files(repo, request["base_commit"])
    if image is None:
        return {"error": "not_at_base"}
    setup, changed = setup_files(repo), changed_files(repo)
    both = sorted({*setup, *changed, *image})
    if len(both) > MAX_SETUP_FILES or _size(repo, both) > MAX_SETUP_BYTES:
        return {"error": "setup_too_large"}
    with tempfile.TemporaryDirectory(prefix="tfbench-") as tmp:
        folder = Path(tmp)
        index = _Index(repo, folder)
        index.git("read-tree", "HEAD")
        if changed:
            index.git("add", "-A", "--", *changed)
        if setup:
            index.git("add", "-f", "--", *setup)
        base = index.commit(head, "tracefix-bench: setup (ignored and changed files)")
        _tag(repo, "tf-base", base)
        made: Json = {"base": base}
        with_tests: Json = {}
        tests: Path | None = None
        if request["test_patch"] is not None:
            tests = folder / "tests.patch"
            tests.write_bytes(request["test_patch"].encode("utf-8", "surrogatepass"))
            with_tests["base"] = _patched(index, base, tests, "tracefix-bench: hidden tests")
        reset: dict[str, list[str]] = request.get("reset") or {}
        for kind, text in request["patches"].items():
            if not KIND.match(kind) or kind == "base":
                raise ValueError(f"bad patch kind {kind!r}")
            patch = folder / f"{kind}.patch"
            patch.write_bytes(text.encode("utf-8", "surrogatepass"))
            made[kind] = _patched(index, base, patch, f"tracefix-bench: {kind}")
            if tests is not None:
                with_tests[kind] = None
                if made[kind] is not None:
                    again = (base, reset[kind]) if kind in reset else None
                    with_tests[kind] = _patched(index, made[kind], tests,
                                                "tracefix-bench: tests", again)  # fmt: skip
    for kind, sha in made.items():
        if sha is not None and kind != "base":
            _tag(repo, f"tf-{kind}", sha)
    for kind, sha in with_tests.items():
        if sha is not None:
            _tag(repo, f"tf-{kind}-t", sha)
    changed = sorted({*changed, *image})  # the record lists the setup commit's files too
    return {"setup": setup, "changed": changed, "commits": made, "with_tests": with_tests}


# --- runs ---------------------------------------------------------------------------------------


def _settings(request: Json) -> RunSettings:
    """The runs' settings; with the project's interpreter, as Tracefix's check describes it
    (probe refused an unusable one before any run)."""
    python = _project(request)
    found = interpreter.current()
    if python is not None:
        checked = interpreter.check(python, sandbox.probe()[0])
        if checked.interpreter is None:
            raise RuntimeError(checked.reason)
        found = checked.interpreter
    return RunSettings(float(request["timeout"]), tuple(request["plugins"]), found)


def suite(request: Json) -> Json:
    with Workspace(Path(request["repo"]), "tf-base", "tf-base", _settings(request)) as ws:
        try:
            check = isolation.check_environment(ws)
        except isolation.TamperingDetected as exc:
            print(exc, file=sys.stderr)  # the step log only: the host never parses it
            return {"status": "tampering"}
    run = check.run
    return {
        "status": check.status.value,
        "error": check.error,
        "module": check.module,
        "outcome": run.outcome.value,
        "seconds": run.first.duration_s,
        "tests": run.first.tests,
        "isolation": run.isolation,
    }


def _rootdir(copy: Path, files: list[str]) -> str:
    """The folder pytest's JUnit names are relative to, as the runner pins it (`--rootdir`)."""
    config = runner.pytest_config(copy, files)
    return "." if config is None else config.parent.relative_to(copy).as_posix() or "."


def hidden(request: Json) -> Json:
    files: list[str] = request["files"]
    found: Json = {}
    for kind, ref in request["refs"].items():
        with Workspace(Path(request["repo"]), "tf-base", ref, _settings(request)) as ws:
            rootdir = _rootdir(ws.head, files)
            try:
                run = isolation.run_checked(ws, ws.head, files, reruns=int(request["reruns"]))
            except isolation.TamperingDetected as exc:
                print(exc, file=sys.stderr)  # the step log only: the host never parses it
                found[kind] = {"outcome": "tampering"}
                continue
        first = run.first
        found[kind] = {
            "outcome": run.outcome.value,
            "rootdir": rootdir,
            "passed": list(first.passed),
            "failed": list(first.failed),
            "tests": first.tests,
            "seconds": run.duration_s,
            "isolation": run.isolation,
        }
    return found


class AnchoredLive:
    """Every role's calls are replayed, and go live (recorded) only when no answer was recorded
    for that very request: only what changed since the anchor's run costs money."""

    def __init__(self, live: Provider, recordings: Path) -> None:
        self.live = RecordingProvider(live, recordings)
        self.recorded = RecordedProvider(recordings)

    def send(self, request: LLMRequest) -> LLMResponse:
        try:
            return self.recorded.send(request)
        except MissingRecording:
            return self.live.send(request)


class AdversaryLive(AnchoredLive):
    """The same, except that the adversary's calls always go live (recorded)."""

    def send(self, request: LLMRequest) -> LLMResponse:
        if request.role == "adversary":
            return self.live.send(request)
        return super().send(request)


def provider(
    mode: str, recordings: Path, live: Callable[[], Provider] = AnthropicProvider
) -> Provider:
    """The verify's model answers by mode (bench.prepare.Mode); `live` makes the API client."""
    if mode == "live":
        return RecordingProvider(live(), recordings)
    if mode == "adversary_live":
        return AdversaryLive(live(), recordings)
    if mode == "anchored":
        return AnchoredLive(live(), recordings)
    if mode == "replay":
        return RecordedProvider(recordings)
    raise ValueError(f"unknown mode {mode!r}")


def verify(request: Json) -> Json:
    """When live, the API key is only in this process's environment: Tracefix's runs never pass
    it on (runner.safe_env)."""
    answers = provider(request["mode"], Path(request["recordings"]))
    with tempfile.TemporaryDirectory(prefix="tfbench-verify-") as tmp:
        issue, config = Path(tmp) / "ISSUE.md", Path(tmp) / "tracefix.yml"
        issue.write_text(request["issue"], encoding="utf-8")
        config.write_text(request["config"], encoding="utf-8")
        argv = ["verify", "--repo", request["repo"], "--base", "tf-base",
                "--head", request["head"], "--issue", str(issue), "--config", str(config),
                "--out", request["out"]]  # fmt: skip
        python = _project(request)
        if python is not None:
            argv += ["--python", python]
        return {"exit_code": cli.main(argv, provider=answers)}


def touched(repo: Path, old: str, new: str) -> list[Json]:
    """The source code `new` changes against `old`, by Tracefix's own diff parse: each changed
    function or method, and each file with code changed outside every function (or that
    doesn't parse) as `function` None. Test files and non-Python files are left out."""
    a = git(repo, "rev-parse", f"{old}^{{commit}}").strip()
    b = git(repo, "rev-parse", f"{new}^{{commit}}").strip()
    scope = diffscope.compute_scope(repo, a, b)
    found: set[tuple[str, str | None]] = {(f.path, f.qualname) for f in scope.source_functions}
    outside = (*scope.module_level, *scope.unparseable)
    found |= {(p, None) for p in outside if diffscope.classify(p) is diffscope.FileKind.SOURCE}
    ordered = sorted(found, key=lambda t: (t[0], t[1] or ""))
    return [{"path": path, "function": name} for path, name in ordered]


def functions(request: Json) -> Json:
    """`touched` for each named pair of refs (bench.prepare.changed_functions)."""
    repo = Path(request["repo"])
    return {name: touched(repo, old, new) for name, (old, new) in request["pairs"].items()}


def replay(request: Json) -> Json:
    earlier = previous.load(Path(request["previous"]))
    with Workspace(Path(request["repo"]), "tf-base", request["head"], _settings(request)) as ws:
        result = previous.replay(ws, earlier)
    return {
        "status": result.status.value,
        "isolation": result.isolation,
        "findings": [
            {"number": f.number, "carried": f.carried, "result": f.result.value}
            for f in result.findings
        ],
    }


COMMANDS: dict[str, Callable[[Json], Json]] = {
    "probe": probe, "commits": commits, "suite": suite, "hidden": hidden, "verify": verify,
    "replay": replay, "functions": functions,
}  # fmt: skip


def main(argv: list[str]) -> int:
    command, request_path, result_path = argv
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    try:
        result = {"ok": True, "result": COMMANDS[command](request)}
    except Exception as exc:  # the host records it as a harness error
        traceback.print_exc()
        result = {"ok": False, "error": type(exc).__name__}
    Path(result_path).write_text(json.dumps(result), encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

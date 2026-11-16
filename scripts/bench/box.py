"""Where one task runs (M10 plan P5): a container from the task's image, or a local clone.

`DockerBox` drives the `docker` CLI (no Docker SDK). Files go in and out with `docker cp`, never
bind mounts: those are slow on Windows, and a mount would give the box a path into this PC. The
container gets the codespace's extra permissions (.devcontainer/devcontainer.json), so
bubblewrap works inside it and receipts say strict. All project and model-written code then runs
inside bubblewrap, inside Docker Desktop's Linux VM, never directly on Windows.

A project on Python 3.11+ gets Tracefix's wheel in its own environment, as slice 1 did. An older
one (M10 part 2 plan C4) keeps its environment as it is, apart from Hypothesis when it has none
or one too old for Tracefix:
Tracefix goes into an environment of its own (uv's Python 3.11, uv.lock's versions, the same steps
as the GitHub Action), inside.py runs with that, and every run gets `--python` naming the project's
interpreter.

`LocalBox` runs the same steps on a local clone with this interpreter (and, when given, a project
interpreter of its own). The tests use it, so the default suite needs no Docker.

Paths inside a box are strings (POSIX in a container); `put` and `get` copy one file or folder,
and the destination must not exist yet (`docker cp` would otherwise copy *into* it).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from tracefix.interpreter import MIN_HYPOTHESIS

OUTPUT_LIMIT = 100_000  # characters kept from the end of a command's output
START_TIMEOUT_S = 3_600  # `docker run` pulls the image first (~8 GB: minutes)
COMMAND_TIMEOUT_S = 600  # apt, pip and docker cp
LABEL = "tracefix-bench=1"  # every container the harness starts, for cleaning up by hand
MEMORY = "8g"
PIDS = "4096"
# The codespace's permissions: without them bubblewrap can't make its namespaces or mount a
# fresh /proc inside a container (scripts/check_linux.py uses the same).
SANDBOX_FLAGS = (
    "--cap-add", "SYS_ADMIN",
    "--security-opt", "seccomp=unconfined",
    "--security-opt", "apparmor=unconfined",
    "--security-opt", "systempaths=unconfined",
)  # fmt: skip
CONDA_PYTHON = "/opt/conda/envs/testbed/bin/python"  # SWE-rebench's images; else `python`
APT_BUBBLEWRAP = (
    "apt-get update -qq && DEBIAN_FRONTEND=noninteractive "
    "apt-get install -y -qq --no-install-recommends bubblewrap"
)
MAX_PACKAGES = 5_000
SECRETS = frozenset({"ANTHROPIC_API_KEY"})  # LocalBox passes it on only when asked to
# Option stubs (scripts/bench/stubs) for plugins prepare never loads: distribution -> module.
STUBS = Path(__file__).with_name("stubs")
STUB_MODULES = {"pytest-cov": "tracefix_stub_cov", "pytest-xdist": "tracefix_stub_xdist"}
PURELIB = "import sysconfig; print(sysconfig.get_paths()['purelib'])"
SITE_PATH = re.compile(r"^/[\w./+-]{1,400}$")
OWN_ENV_BELOW = (3, 11)  # a project Python below this gets Tracefix in an environment of its own
UV_VERSION = "0.12.21"  # pinned: the uv that builds Tracefix's own environment in a box
PINS = "requirements.txt"  # beside the wheel: uv.lock's versions (`uv export`), for that env
VERSION = "import sys; print('%d.%d' % sys.version_info[:2])"
# Every distribution the interpreter sees, as `pip list --format=json` prints them (a uv venv
# has no pip).
DISTRIBUTIONS = (
    "import json; from importlib import metadata as m; "
    "print(json.dumps([{'name': d.metadata['Name'], 'version': d.version} "
    "for d in m.distributions()]))"
)
HYPOTHESIS = "hypothesis>=" + ".".join(map(str, MIN_HYPOTHESIS))
# Exits 0 only when the interpreter has a Hypothesis Tracefix's in-run code is tested with
# (an older one leaves Break My Fix and the behaviour diff inconclusive: interpreter.py).
HAS_HYPOTHESIS = (
    f"import sys, hypothesis; sys.exit(hypothesis.__version_info__[:2] < {MIN_HYPOTHESIS!r})"
)

Docker = Callable[[Sequence[str], float], "subprocess.CompletedProcess[bytes]"]


class BoxError(Exception):
    """The box could not be started, reached or set up; `str(exc)` is in our own words."""


@dataclass(frozen=True)
class Exec:
    code: int | None  # None: killed at the timeout
    output: str  # stdout and stderr, the last OUTPUT_LIMIT characters
    seconds: float


@dataclass(frozen=True)
class Installed:
    """The project environment's distributions (normalised name -> version), before and after
    Tracefix was installed into it, and the option stubs installed beside them (modules)."""

    before: Mapping[str, str]
    after: Mapping[str, str]
    stubs: tuple[str, ...] = ()

    def changes(self) -> list[str]:
        names = sorted({*self.before, *self.after})
        out = []
        for name in names:
            old, new = self.before.get(name), self.after.get(name)
            if old != new:
                out.append(f"{name} {old or '-'} -> {new or '-'}")
        return out


class Box(Protocol):
    repo: str  # the task's checkout, as the box's processes see it
    python: str  # the interpreter Tracefix (and inside.py) runs with
    project_python: str | None  # the project's own, when it isn't `python` (runs get --python)
    home: str  # the harness's own folder (inside.py, requests, results, receipts)

    def path(self, *parts: str) -> str: ...
    def run(
        self, argv: Sequence[str], *, timeout: float, env_names: Sequence[str] = ()
    ) -> Exec: ...
    def put(self, local: Path, remote: str) -> None: ...
    def get(self, remote: str, local: Path) -> None: ...
    def install(self, wheel: Path) -> Installed: ...
    def close(self) -> None: ...


def normalise(name: str) -> str:
    """A distribution name as packaging compares them (PEP 503)."""
    return "-".join(name.lower().replace("_", "-").replace(".", "-").split("-"))


def packages(pip_list_json: str) -> dict[str, str]:
    """`pip list --format=json`'s output as {name: version}; BoxError if it isn't that."""
    try:
        items = json.loads(pip_list_json)
    except ValueError as exc:
        raise BoxError("pip list printed no JSON") from exc
    if not isinstance(items, list) or len(items) > MAX_PACKAGES:
        raise BoxError("pip list printed something else")
    found = {}
    for item in items:
        name = item.get("name") if isinstance(item, dict) else None
        version = item.get("version") if isinstance(item, dict) else None
        if not isinstance(name, str) or not isinstance(version, str):
            raise BoxError("pip list printed something else")
        found[normalise(name)] = version
    return found


def version(printed: str) -> tuple[int, int]:
    """VERSION's output as (major, minor); BoxError if it isn't that."""
    match = re.fullmatch(r"(\d{1,2})\.(\d{1,3})", printed.strip())
    if match is None:
        raise BoxError("the project's Python printed no version")
    return int(match[1]), int(match[2])


def _tail(data: bytes | str | None) -> str:
    text = data.decode("utf-8", "replace") if isinstance(data, bytes) else data or ""
    return text[-OUTPUT_LIMIT:]


def own_group() -> dict[str, Any]:
    """Popen options for a process group of its own. The terminal sends Ctrl+C to every process
    in its group: a `docker exec` that quit at once left its box working while the pool
    recorded a failed run (NOTES 38). Ctrl+C is then the pool's alone (`run.run_all`)."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def run_docker(args: Sequence[str], timeout: float) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["docker", *args], stdin=subprocess.DEVNULL, capture_output=True,
                          timeout=timeout, **own_group())  # fmt: skip


def container_name(instance_id: str) -> str:
    return "tfbench-" + instance_id.lower().replace("__", "-").replace(".", "-")


def remove_image(image: str, docker: Docker = run_docker) -> bool:
    """Free the image's disk (~8 GB each). False when docker refused, e.g. while another
    container still uses it: the image then stays, which is harmless."""
    try:
        return docker(["rmi", image], COMMAND_TIMEOUT_S).returncode == 0
    except subprocess.TimeoutExpired:
        return False


class DockerBox:
    repo = "/testbed"
    home = "/opt/tfbench"

    def __init__(self, image: str, name: str, docker: Docker = run_docker) -> None:
        self.image = image
        self.name = name
        self.python = CONDA_PYTHON
        self.project_python: str | None = None
        self._docker = docker
        self._alive = False

    def _call(self, args: Sequence[str], timeout: float = COMMAND_TIMEOUT_S) -> str:
        try:
            done = self._docker(args, timeout)
        except subprocess.TimeoutExpired as exc:
            raise BoxError(f"docker {args[0]} timed out") from exc
        if done.returncode != 0:
            raise BoxError(f"docker {args[0]} failed (exit {done.returncode})")
        return _tail(done.stdout)

    def start(self) -> None:
        """A fresh container (one left by an interrupted run under the same name is removed)."""
        with contextlib.suppress(subprocess.TimeoutExpired):
            self._docker(["rm", "-f", self.name], COMMAND_TIMEOUT_S)
        self._call(
            ["run", "-d", "--init", "--name", self.name, "--label", LABEL, *SANDBOX_FLAGS,
             "--memory", MEMORY, "--pids-limit", PIDS, "--entrypoint", "sleep",
             self.image, "infinity"],
            START_TIMEOUT_S,
        )  # fmt: skip
        self._alive = True
        self._call(["exec", self.name, "mkdir", "-p", self.home])
        found = self._call(["exec", self.name, "sh", "-c", f"test -x {CONDA_PYTHON} && echo yes"])
        if found.strip() != "yes":
            self.python = self._call(["exec", self.name, "sh", "-c", "command -v python"]).strip()
        if not self.python.startswith("/"):
            raise BoxError("the image has no python")

    def path(self, *parts: str) -> str:
        return "/".join([self.home, *parts])

    def run(self, argv: Sequence[str], *, timeout: float, env_names: Sequence[str] = ()) -> Exec:
        """One command in the container. A name in `env_names` passes that variable from this
        process's environment (`docker exec -e NAME`): its value is never on a command line.
        At the timeout the whole container is removed, so nothing it started keeps running."""
        env = [arg for name in env_names for arg in ("-e", name)]
        start = time.monotonic()
        try:
            done = self._docker(["exec", *env, "-w", "/", self.name, *argv], timeout)
        except subprocess.TimeoutExpired as exc:
            self.close()
            return Exec(None, _tail(exc.output), round(time.monotonic() - start, 3))
        output = _tail(done.stdout) + _tail(done.stderr)
        return Exec(done.returncode, output[-OUTPUT_LIMIT:], round(time.monotonic() - start, 3))

    def put(self, local: Path, remote: str) -> None:
        self._call(["cp", str(local), f"{self.name}:{remote}"])

    def get(self, remote: str, local: Path) -> None:
        if local.exists():
            raise BoxError(f"{local} exists already")
        self._call(["cp", f"{self.name}:{remote}", str(local)])

    @property
    def project(self) -> str:
        return self.project_python or self.python

    def _packages(self) -> dict[str, str]:
        return packages(self._call(["exec", self.name, self.project, "-m", "pip", "list",
                                    "--format=json", "--disable-pip-version-check"]))  # fmt: skip

    def _pip(self, *args: str) -> Exec:
        """pip install into the project's environment."""
        return self.run([self.project, "-m", "pip", "install", "--no-input", "--quiet",
                         "--disable-pip-version-check", "--root-user-action=ignore", *args],
                        timeout=COMMAND_TIMEOUT_S)  # fmt: skip

    def install(self, wheel: Path) -> Installed:
        """bubblewrap (when apt can get it: without it runs are basic, and receipts say so),
        then Tracefix: into the project's environment (3.11+), or into one of its own beside it
        (older), recording what changed in the project's."""
        self.run(["sh", "-c", APT_BUBBLEWRAP], timeout=COMMAND_TIMEOUT_S)
        before = self._packages()
        remote = self.path(wheel.name)
        self.put(wheel, remote)
        if version(self._call(["exec", self.name, self.python, "-c", VERSION])) < OWN_ENV_BELOW:
            self._own_env(wheel.with_name(PINS), remote)
        elif self._pip(remote).code != 0:
            raise BoxError("pip could not install Tracefix into the project's environment")
        return Installed(before, self._packages(), self._install_stubs(before))

    def _own_env(self, pins: Path, wheel: str) -> None:
        """uv (pinned, into a folder of its own: the project's environment is untouched), uv's
        Python 3.11 under the harness's folder, uv.lock's versions, then the wheel alone; and
        Hypothesis into the project's environment only when it has none or one older than
        MIN_HYPOTHESIS (pip then upgrades it)."""
        if not pins.is_file():
            raise BoxError(f"{PINS} is missing beside the wheel")
        uv, env, remote_pins = self.path("uv", "bin", "uv"), self.path("env"), self.path(PINS)
        self.put(pins, remote_pins)
        py = f"{env}/bin/python"
        if self._pip("--target", self.path("uv"), f"uv=={UV_VERSION}").code != 0:
            raise BoxError("pip could not install uv for Tracefix's own environment")
        steps = (
            (["env",f"UV_PYTHON_INSTALL_DIR={self.path('pythons')}", uv, "venv", "--quiet",
              "--no-project", "--python-preference", "only-managed", "--python", "3.11", env],
             "Python 3.11"),
            ([uv, "pip", "install", "--quiet", "--python", py, "-r", remote_pins],
             "Tracefix's dependencies"),
            ([uv, "pip", "install", "--quiet", "--python", py, "--no-deps", wheel], "Tracefix"),
        )  # fmt: skip
        for argv, what in steps:
            if self.run(argv, timeout=COMMAND_TIMEOUT_S).code != 0:
                raise BoxError(f"could not install {what} for Tracefix's own environment")
        has = self.run([self.python, "-I", "-c", HAS_HYPOTHESIS], timeout=COMMAND_TIMEOUT_S)
        if has.code != 0 and self._pip(HYPOTHESIS).code != 0:
            raise BoxError("pip could not install Hypothesis into the project's environment")
        self.python, self.project_python = py, self.python

    def _install_stubs(self, before: Mapping[str, str]) -> tuple[str, ...]:
        """The option stub of each never-loaded plugin the project has, into its site-packages
        (where Tracefix's runs import from, also under bubblewrap)."""
        stubs = tuple(module for dist, module in STUB_MODULES.items() if dist in before)
        if not stubs:
            return ()
        site = self._call(["exec", self.name, self.project, "-c", PURELIB]).strip()
        if not SITE_PATH.fullmatch(site) or ".." in site.split("/"):
            raise BoxError("the project's site-packages folder is not a plain path")
        for module in stubs:
            self.put(STUBS / f"{module}.py", f"{site}/{module}.py")
        return stubs

    def close(self) -> None:
        if self._alive:
            self._alive = False
            with contextlib.suppress(subprocess.TimeoutExpired):
                self._docker(["rm", "-f", self.name], COMMAND_TIMEOUT_S)


def _installed_here() -> dict[str, str]:
    from importlib.metadata import distributions

    return {normalise(d.metadata["Name"]): d.version for d in distributions()}


class LocalBox:
    """The same steps on a local clone of `source` (checked out at `checkout`), run by this
    interpreter, in `work`; the project's tests with `project_python` when given (an older
    Python's environment, as a box below 3.11 has). Tracefix is already installed here, so
    `install` changes nothing."""

    def __init__(
        self, source: Path, checkout: str, work: Path, project_python: str | None = None
    ) -> None:
        self.python = sys.executable
        self.project_python = project_python
        self.repo = str(work / "testbed")
        self.home = str(work / "home")
        Path(self.home).mkdir(parents=True)
        # autocrlf off: a Windows user's global setting would rewrite every file's line endings
        # in the clone, and the setup commit would then hold them all.
        clone = ["clone", "--quiet", "--no-hardlinks", "--config", "core.autocrlf=false"]
        for args in ([*clone, str(source), self.repo],
                     ["-C", self.repo, "checkout", "--quiet", "--detach", checkout]):  # fmt: skip
            subprocess.run(["git", "-c", "core.autocrlf=false", *args], check=True,
                           capture_output=True)  # fmt: skip

    def path(self, *parts: str) -> str:
        return str(Path(self.home, *parts))

    def run(self, argv: Sequence[str], *, timeout: float, env_names: Sequence[str] = ()) -> Exec:
        env = {k: v for k, v in os.environ.items() if k not in SECRETS or k in env_names}
        start = time.monotonic()
        try:
            done = subprocess.run(list(argv), stdin=subprocess.DEVNULL, capture_output=True,
                                  timeout=timeout, env=env)  # fmt: skip
        except subprocess.TimeoutExpired as exc:
            return Exec(None, _tail(exc.output), round(time.monotonic() - start, 3))
        output = _tail(done.stdout) + _tail(done.stderr)
        return Exec(done.returncode, output[-OUTPUT_LIMIT:], round(time.monotonic() - start, 3))

    def put(self, local: Path, remote: str) -> None:
        _copy(local, Path(remote))

    def get(self, remote: str, local: Path) -> None:
        if local.exists():
            raise BoxError(f"{local} exists already")
        if not Path(remote).exists():
            raise BoxError(f"{remote} doesn't exist")
        _copy(Path(remote), local)

    def install(self, wheel: Path) -> Installed:
        """Nothing is installed: this interpreter is Tracefix's own, and an option stub written
        into its site-packages would set off every tamper watch that looks there. A project
        interpreter must already have Hypothesis (scripts/old_pythons.py installs it)."""
        if self.project_python is None:
            here = _installed_here()
            return Installed(here, here)
        listed = self.run([self.project_python, "-I", "-c", DISTRIBUTIONS], timeout=60)
        if listed.code != 0:
            raise BoxError("the project's Python could not list its distributions")
        found = packages(listed.output)
        return Installed(found, found)

    def close(self) -> None:
        pass


def _copy(source: Path, dest: Path) -> None:
    """A file replaces what is there (as `docker cp` does); a folder must be new."""
    if source.is_dir():
        if dest.exists():
            raise BoxError(f"{dest} exists already")
        shutil.copytree(source, dest)
    else:
        shutil.copyfile(source, dest)

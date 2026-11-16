"""How a pytest process is confined (SPEC 4, Decided in M3.5).

- strict: Linux with bubblewrap. Read-only system, only the copy under test and the run's scratch
  folder writable, other copies, temp files and $HOME hidden, no network.
- basic: everywhere else. The run gets its own HOME/TMP, an allowlisted environment (runner) and a
  best-effort in-process network block. Tamper detection (isolation.py) applies to both levels.
"""

import functools
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

Level = Literal["strict", "basic"]
PROBE_TIMEOUT_S = 20
NETBLOCK_MODULE = "tracefix_netblock"
PATHS_MODULE = "tracefix_paths"
BASIC_WARNING = (
    "Generated tests ran with basic isolation only (no bubblewrap sandbox): tampering inside the "
    "watched folders is detected, but code could still read or write elsewhere on this machine, "
    "and a process that escaped could influence a later run. For untrusted changes run Tracefix "
    "in GitHub Actions or on Linux with bubblewrap."
)

# Loaded into each basic-level pytest run with -p. Refuses connections to anything but loopback
# and Unix sockets, like the network namespace of a strict run. Code inside the process can undo
# it: this is a seat belt, not a wall.
NETBLOCK_SOURCE = """\
import socket

_LOCAL = ("127.", "::1", "localhost", "0:0:0:0:0:0:0:1")


def _allowed(address):
    if not isinstance(address, tuple):
        return True  # AF_UNIX path or similar
    host = str(address[0]) if address else ""
    return host.startswith(_LOCAL)


def _refuse():
    raise OSError("network access is disabled by Tracefix")


_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex
_getaddrinfo = socket.getaddrinfo


def connect(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6) and not _allowed(address):
        _refuse()
    return _connect(self, address)


def connect_ex(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6) and not _allowed(address):
        _refuse()
    return _connect_ex(self, address)


def getaddrinfo(host, *args, **kwargs):
    if host is not None and not _allowed((host,)):
        raise socket.gaierror("network access is disabled by Tracefix")
    return _getaddrinfo(host, *args, **kwargs)


def _lookup(original):
    def lookup(host, *args, **kwargs):
        if not _allowed((host,)):
            raise socket.gaierror("network access is disabled by Tracefix")
        return original(host, *args, **kwargs)
    return lookup


_sendto = socket.socket.sendto
_sendmsg = getattr(socket.socket, "sendmsg", None)


def sendto(self, data, *args):
    address = args[-1] if args else None
    if self.family in (socket.AF_INET, socket.AF_INET6) and not _allowed(address):
        _refuse()
    return _sendto(self, data, *args)


def sendmsg(self, buffers, ancdata=(), flags=0, address=None):
    if address is not None and self.family in (socket.AF_INET, socket.AF_INET6):
        if not _allowed(address):
            _refuse()
    extra = [address] if address is not None else []
    return _sendmsg(self, buffers, ancdata, flags, *extra)


socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
socket.socket.sendto = sendto
if _sendmsg is not None:
    socket.socket.sendmsg = sendmsg
socket.getaddrinfo = getaddrinfo
for _name in ("gethostbyname", "gethostbyname_ex", "gethostbyaddr"):
    setattr(socket, _name, _lookup(getattr(socket, _name)))
"""


def _install_root(executable: Path) -> Path:
    """The install folder of a python executable: the parent of its bin/ (Scripts/) folder."""
    folder = executable.parent
    return folder.parent if folder.name in ("bin", "Scripts") else folder


def _symlink_hops(path: Path, limit: int = 20) -> list[Path]:
    """`path` and every path its symlink chain passes through, as written (unresolved)."""
    hops = [path]
    for _ in range(limit):
        if not path.is_symlink():
            break
        raw = os.readlink(path)
        raw = raw.removeprefix("\\\\?\\")  # Windows: absolute targets as extended-length paths
        target = Path(raw)
        path = target if target.is_absolute() else path.parent / target
        hops.append(path)
    return hops


def _venv_home(prefix: Path) -> Path | None:
    """The `home = ...` folder from a venv's pyvenv.cfg (the base python's bin folder)."""
    cfg = prefix / "pyvenv.cfg"
    try:
        for line in cfg.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "home" and value.strip():
                return Path(value.strip())
    except OSError:
        pass
    return None


def executable_dirs(executable: Path) -> set[Path]:
    """Folders a python executable needs: the install folder of every hop of its link chain and
    of its target, and for a venv the base install its pyvenv.cfg names, as written and resolved.
    uv links a venv's python through version-alias folders (e.g. cpython-3.11-... ->
    cpython-3.11.13-...) that pyvenv.cfg names, so every hop must stay visible."""
    dirs = {_install_root(hop) for hop in _symlink_hops(executable)}
    dirs.add(_install_root(executable.resolve()))
    home = _venv_home(_install_root(executable))
    if home is not None:
        dirs.update({home.parent, home.resolve().parent})
    return dirs


def _interpreter_dirs(executable: Path | None = None) -> list[Path]:
    """Folders the interpreters need inside the sandbox: Tracefix's own (venv and base install,
    both as written and resolved) and, when it is another one, the run's `executable`'s."""
    dirs: set[Path] = set()
    for prefix in (sys.prefix, sys.exec_prefix, sys.base_prefix):
        dirs.update({Path(prefix), Path(prefix).resolve()})
    dirs |= executable_dirs(Path(sys.executable))
    if executable is not None and executable.is_absolute():
        dirs |= executable_dirs(executable)
    return sorted(d for d in dirs if d.exists() and d != Path("/"))


def _hidden() -> list[Path]:
    """Folders a run never sees as they are: /tmp (a fresh tmpfs), the temp folder and $HOME."""
    return [Path("/tmp"), Path(tempfile.gettempdir()).resolve(), Path.home().resolve()]


def _under(folder: Path, roots: list[Path]) -> bool:
    return any(folder.is_relative_to(root) for root in roots)


def bwrap_prefix(writable: list[Path], executable: Path | None = None) -> list[str]:
    """The bubblewrap command that runs a process with only `writable` folders writable;
    `executable`: the python it runs, when it isn't Tracefix's own (see _interpreter_dirs)."""
    args = ["bwrap", "--die-with-parent", "--new-session", "--unshare-all", "--ro-bind", "/", "/",
            "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp"]  # fmt: skip
    hidden = _hidden()
    for folder in hidden[1:]:
        if folder != Path("/") and not folder.is_relative_to("/tmp") and folder.is_dir():
            args += ["--tmpfs", str(folder)]
    for folder in _interpreter_dirs(executable):  # back in view if under a hidden folder
        if folder.is_symlink() and not _under(folder, hidden):
            # Already visible through "/" with its target (also in the list), and bubblewrap
            # can't mount onto a symlink: uv's version-alias folder (cpython-3.11 ->
            # cpython-3.11.16) outside $HOME made the probe fail, so runs fell back to basic.
            continue
        args += ["--ro-bind", str(folder), str(folder)]
    for folder in writable:
        args += ["--bind", str(folder), str(folder)]
    return args


@functools.cache
def probe() -> tuple[Level, str]:
    """(level, why): strict if bubblewrap works here (checked once), else basic, with the reason
    (e.g. bubblewrap's own error message), so a fallback can always be explained."""
    if os.environ.get("TRACEFIX_ISOLATION") == "basic":
        return "basic", "TRACEFIX_ISOLATION=basic"
    if sys.platform != "linux":
        return "basic", f"bubblewrap needs Linux (this is {sys.platform})"
    if shutil.which("bwrap") is None:
        return "basic", "bubblewrap (bwrap) is not installed"
    folder = tempfile.mkdtemp(prefix="tracefix-probe-")
    command = [*bwrap_prefix([Path(folder)]), "--chdir", folder, sys.executable, "-c", "pass"]
    try:
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=PROBE_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "basic", f"bubblewrap probe could not run: {exc}"
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    if result.returncode != 0:
        output = (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()
        return "basic", f"bubblewrap probe failed (exit {result.returncode}): {output[-500:]}"
    return "strict", "bubblewrap works"


def sandbox_level() -> Level:
    """strict if bubblewrap works here, else basic (see probe() for why)."""
    return probe()[0]


def run_env(scratch: Path) -> dict[str, str]:
    """Per-run HOME and temp folders inside the run's scratch folder, so well-behaved code never
    touches the real ones; no user site-packages."""
    home = scratch / "home"
    tmp = scratch / "tmp"
    home.mkdir(exist_ok=True)
    tmp.mkdir(exist_ok=True)
    return {
        "HOME": str(home), "USERPROFILE": str(home), "APPDATA": str(home),
        "LOCALAPPDATA": str(home), "TMP": str(tmp), "TEMP": str(tmp), "TMPDIR": str(tmp),
        "PYTHONNOUSERSITE": "1",
        # .pyc files come only from this run's own empty folder: one planted in any __pycache__
        # (venv, interpreter install, the copy) is never loaded.
        "PYTHONPYCACHEPREFIX": str(scratch / "pycache"),
    }  # fmt: skip


# Hypothesis seeds its draws with constants it reads from the run's own source files, but not
# from test files (a path with a "tests" folder). Tracefix's modules live in one, so the draws
# follow the project's code only, never Tracefix's own strings (which also kept the recorded
# Judge requests changing with every edit to the runtime: verifier round 7).
MODULES_DIR = "tests"


def write_module(scratch: Path, name: str, source: str) -> dict[str, str]:
    """Write Tracefix's own module `name` into the run's scratch folder, importable from there:
    returns the env vars that put the folder on the run's import path."""
    if not name.isidentifier():
        raise ValueError(f"not a module name: {name!r}")
    folder = scratch / MODULES_DIR
    folder.mkdir(exist_ok=True)
    (folder / f"{name}.py").write_text(source, encoding="utf-8")
    return {"PYTHONPATH": str(folder)}


def install_netblock(scratch: Path) -> tuple[dict[str, str], list[str]]:
    """Write the network-block plugin into the run's scratch folder: (env vars, pytest args)."""
    return write_module(scratch, NETBLOCK_MODULE, NETBLOCK_SOURCE), ["-p", NETBLOCK_MODULE]


# Loaded into every run with -p (before any other plugin) when the copy has package folders
# (Workspace.import_roots). It puts them into sys.path just before the first site-packages
# folder: the copy's code wins over an installed or editable copy of the project (often the
# user's working copy), while the standard library and the already imported pytest can't be
# shadowed. Never through PYTHONPATH, which would put them first (see runner's -P).
PATHS_SOURCE = """\
import os
import sys

_SITE = ("site-packages", "dist-packages")


def _first_site(path):
    for i, entry in enumerate(path):
        if os.path.basename(os.path.normpath(entry)).lower() in _SITE:
            return i
    return len(path)


_at = _first_site(sys.path)
sys.path[_at:_at] = [root for root in ROOTS if root not in sys.path[:_at]]
"""


def install_paths(scratch: Path, roots: Sequence[Path]) -> tuple[dict[str, str], list[str]]:
    """Write the paths plugin for these folders into the run's scratch folder: (env, args)."""
    source = f"ROOTS = {[str(root) for root in roots]!r}\n{PATHS_SOURCE}"
    return write_module(scratch, PATHS_MODULE, source), ["-p", PATHS_MODULE]


def wrap(level: Level, command: list[str], cwd: Path, scratch: Path) -> list[str]:
    """The full command for one pytest run at this isolation level."""
    if level == "strict":
        executable = Path(command[0])
        return [*bwrap_prefix([cwd, scratch], executable), "--chdir", str(cwd), *command]
    return command

"""The project's Python (`--python`, M10 part 2): which interpreter runs the project's tests.

Tracefix itself needs 3.11+; the project's tests may run with another interpreter (3.9+), the
one the project's dependencies are installed in. Before any stage, `check` runs it once with a
fixed script (-I, the allowlisted environment, a timeout, at the runs' isolation level) and
reads back its version, its folders and its pytest and Hypothesis versions. That report is
written by the project's environment, so it is parsed strictly, with size caps. Without
`--python`, `current()` describes Tracefix's own interpreter and nothing is run.
"""

import json
import re
import shutil
import sys
import sysconfig
import tempfile
import time
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from tracefix import sandbox
from tracefix.proctree import ProcessTree
from tracefix.runner import Attempt, Outcome, RunResult, safe_env
from tracefix.sandbox import Level

MIN_PYTHON = (3, 9)
MIN_PYTEST = (7, 0)
# The oldest Hypothesis Tracefix's in-run code is tested with (the newest one Python 3.9 gets).
MIN_HYPOTHESIS = (6, 141)
CHECK_TIMEOUT_S = 60
MARKER = "TRACEFIX-INTERPRETER "
MAX_REPORT = 256 * 1024  # bytes of output read
MAX_DIRS = 200
MAX_PATH = 4096
_VERSION = re.compile(r"(\d{1,4})\.(\d{1,4})(?:[.\w+-]{0,60})")

# Runs inside the project's interpreter. Old syntax only (no f-strings), so even a Python 2 can
# say which version it is instead of failing to parse.
SCRIPT = """\
import json, os, sys
info = {"version": list(sys.version_info[:3])}
if sys.version_info >= (3, 9):
    import sysconfig
    from importlib import metadata
    names = ("stdlib", "platstdlib", "purelib", "platlib")
    paths = sysconfig.get_paths()
    base = sysconfig.get_paths(vars={"base": sys.base_prefix, "platbase": sys.base_exec_prefix})
    info["prefixes"] = [sys.prefix, sys.exec_prefix, sys.base_prefix, sys.base_exec_prefix]
    info["dirs"] = [paths[n] for n in names] + [base[n] for n in names]
    # Absolute entries only: an editable install's import hook name is not a folder.
    info["dirs"] += [p for p in sys.path if p and os.path.isabs(p)]
    for name in ("pytest", "hypothesis"):
        try:
            info[name] = metadata.version(name)
        except Exception:
            info[name] = None
sys.stdout.write("TRACEFIX-INTERPRETER " + json.dumps(info) + "\\n")
"""


@dataclass(frozen=True)
class Interpreter:
    """A Python that runs the project's tests."""

    executable: str  # as given (absolute, not resolved: a venv's python is often a link)
    version: tuple[int, int, int]
    prefixes: tuple[Path, ...] = ()  # sys.prefix, exec_prefix and their base installs
    code_dirs: tuple[Path, ...] = ()  # stdlib, site-packages and sys.path folders
    pytest: str | None = None
    hypothesis: str | None = None
    own: bool = False  # Tracefix's own interpreter (no --python)

    @property
    def label(self) -> str:
        return ".".join(map(str, self.version))

    @property
    def safe_path(self) -> bool:
        """Whether it has -P (3.11+); older ones start pytest through runner.BOOTSTRAP."""
        return self.version >= (3, 11)

    def hypothesis_problem(self) -> str | None:
        """Why Break My Fix and the behaviour diff can't run in this environment, or None."""
        if self.hypothesis is None:
            return ("Hypothesis is not installed in the project's Python (--python): install it "
                    "there (python -m pip install hypothesis)")  # fmt: skip
        if version_of(self.hypothesis) < MIN_HYPOTHESIS:
            least = ".".join(map(str, MIN_HYPOTHESIS))
            return (f"the project's Python has Hypothesis {self.hypothesis}, older than {least}, "
                    "the oldest Tracefix is tested with: upgrade it there "
                    "(python -m pip install -U hypothesis)")  # fmt: skip
        return None


@dataclass(frozen=True)
class InterpreterCheck:
    """The check's answer: an interpreter, or why the project's tests can't run with it."""

    interpreter: Interpreter | None
    reason: str  # "" when the interpreter can be used
    run: RunResult  # the check run itself (its command and output), for the receipt


def _distribution(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _code_dirs() -> tuple[Path, ...]:
    names = ("stdlib", "platstdlib", "purelib", "platlib")
    base = {"base": sys.base_prefix, "platbase": sys.base_exec_prefix}
    dirs = [sysconfig.get_paths()[n] for n in names]
    dirs += [sysconfig.get_paths(vars=base)[n] for n in names]
    return tuple(Path(d) for d in [*dirs, *(p for p in sys.path if p)])


def current() -> Interpreter:
    """Tracefix's own interpreter, which runs the tests when no --python is given."""
    prefixes = (sys.prefix, sys.exec_prefix, sys.base_prefix, sys.base_exec_prefix)
    return Interpreter(sys.executable, (sys.version_info.major, sys.version_info.minor,
                                        sys.version_info.micro),
                       tuple(Path(p) for p in prefixes), _code_dirs(),
                       _distribution("pytest"), _distribution("hypothesis"), own=True)  # fmt: skip


def version_of(text: str) -> tuple[int, int]:
    """(major, minor) of a version string like "8.4.2" or "7.0.0rc1"; (0, 0) if unreadable."""
    found = _VERSION.fullmatch(text)
    return (int(found.group(1)), int(found.group(2))) if found else (0, 0)


def find(given: str) -> Path | None:
    """The interpreter named by --python: a path, or a command on PATH. Made absolute but never
    resolved (resolving a venv's python link would leave the venv)."""
    path = Path(given)
    if path.is_file():
        return path.absolute()
    found = shutil.which(given)
    return Path(found).absolute() if found else None


def _folder(value: object) -> bool:
    """An absolute folder on this machine (the check runs here), below a filesystem root. A
    relative one would be resolved against Tracefix's own working folder (on Windows `/Users`
    is one: it takes the current drive), and a bare root such as `C:\\` would watch a whole
    drive. POSIX `/` stays: isolation treats it as a shared prefix (`SHARED_PREFIXES`)."""
    if not (isinstance(value, str) and 0 < len(value) <= MAX_PATH):
        return False
    path = Path(value)
    return path.is_absolute() and (len(path.parts) > 1 or value == "/")


def _strings(value: object, limit: int) -> list[str] | None:
    if not isinstance(value, list) or len(value) > limit:
        return None
    if not all(_folder(v) for v in value):
        return None
    return value


def _optional_version(value: object) -> str | None:
    """A distribution version as reported: kept only if it reads as one."""
    if isinstance(value, str) and _VERSION.fullmatch(value):
        return value
    return None


def parse_report(output: str, executable: str) -> Interpreter | None:
    """The interpreter from the check's output, or None if the report is missing or malformed.
    The last marked line counts; anything that doesn't fit the expected shape is refused."""
    lines = [line for line in output.splitlines() if line.startswith(MARKER)]
    if not lines:
        return None
    try:
        data = json.loads(lines[-1][len(MARKER) :])
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    version = data.get("version")
    if not (isinstance(version, list) and len(version) == 3
            and all(type(v) is int and 0 <= v < 10_000 for v in version)):  # fmt: skip
        return None
    major, minor, micro = version
    if (major, minor) < MIN_PYTHON:
        return Interpreter(executable, (major, minor, micro))
    prefixes = _strings(data.get("prefixes"), 4)
    dirs = _strings(data.get("dirs"), MAX_DIRS)
    if prefixes is None or len(prefixes) != 4 or dirs is None:
        return None
    return Interpreter(executable, (major, minor, micro), tuple(Path(p) for p in prefixes),
                       tuple(Path(d) for d in dirs), _optional_version(data.get("pytest")),
                       _optional_version(data.get("hypothesis")))  # fmt: skip


def refusal(found: Interpreter | None) -> str:
    """Why the project's tests can't run with this interpreter, in fixed words (no machine
    paths: the receipt may be posted publicly); "" if they can."""
    if found is None:
        return ("the project's Python (--python) did not report its version and folders: is it "
                "a working Python 3.9 or later?")  # fmt: skip
    least = ".".join(map(str, MIN_PYTHON))
    if found.version[:2] < MIN_PYTHON:
        return f"the project's Python is {found.label}; Tracefix runs projects on {least} or later"
    if found.pytest is None:
        return ("pytest is not installed in the project's Python (--python): install it there "
                "(python -m pip install pytest)")  # fmt: skip
    if version_of(found.pytest) < MIN_PYTEST:
        least_pytest = ".".join(map(str, MIN_PYTEST))
        return (f"the project's Python has pytest {found.pytest}; Tracefix needs pytest "
                f"{least_pytest} or later there")  # fmt: skip
    return ""


def _read(path: Path) -> str:
    try:
        with path.open("rb") as f:
            return f.read(MAX_REPORT).decode("utf-8", errors="replace")
    except OSError:
        return ""


def check(given: str, level: Level, timeout_s: float = CHECK_TIMEOUT_S) -> InterpreterCheck:
    """Run the project's interpreter once and describe it (see the module docstring). The run's
    command names the script, which is fixed text, instead of quoting it."""
    executable = find(given)
    if executable is None:
        reason = "the project's Python (--python) was not found"
        return InterpreterCheck(None, reason, RunResult(Outcome.ERROR, ("python",), (), level))
    command = (str(executable), "-I", "-c", SCRIPT)
    shown = ("python", "-I", "-c", "<Tracefix's interpreter check>")
    with tempfile.TemporaryDirectory(prefix="tracefix-python-", ignore_cleanup_errors=True) as tmp:
        scratch = Path(tmp).resolve()
        log = scratch / "output.log"
        env = {**safe_env(), **sandbox.run_env(scratch)}
        start = time.monotonic()
        with log.open("wb") as out:
            try:
                tree = ProcessTree(sandbox.wrap(level, list(command), scratch, scratch),
                                   cwd=scratch, env=env, stdout=out)  # fmt: skip
            except OSError as exc:  # not a program (e.g. a text file, no execute permission)
                reason = (f"the project's Python (--python) could not be started "
                          f"({type(exc).__name__})")  # fmt: skip
                return InterpreterCheck(None, reason, RunResult(Outcome.ERROR, shown, (), level))
            try:
                exit_code = tree.wait(timeout_s)
            finally:
                tree.kill_all()
        output = _read(log)
    attempt = Attempt(exit_code, round(time.monotonic() - start, 3), (), output[-10_000:])
    found = parse_report(output, str(executable)) if exit_code == 0 else None
    reason = refusal(found)
    if exit_code is None:
        reason = f"the project's Python (--python) did not answer within {timeout_s:g}s"
    run = RunResult(Outcome.ERROR if reason else Outcome.PASSED, shown, (attempt,), level)
    return InterpreterCheck(None if reason else found, reason, run)

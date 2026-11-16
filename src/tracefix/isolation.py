"""Tamper detection around every run of repo or generated code (SPEC 4, Decided in M3.5).

Every copy (base, head and any extra copy) is compared with its state right after export
(Workspace.pristine), plus the files Tracefix itself placed or removed for the run, both before
the run (drift since the last run) and after it. Tracefix's own environment, the user's
repository and the copies' parent folders are watched by metadata. Afterwards:
- the copies that were not running must be unchanged;
- in the copy under test, changed or deleted files and new code/config files are tampering;
  other new files (logs, caches, a conftest's session file) are leftovers: deleted, not blamed;
- everything else watched must be unchanged; new start-up files (.pth, sitecustomize) are deleted.
Tampering raises TamperingDetected, which a stage turns into "invalid: tampering detected",
never into a pass/fail verdict.
"""

import os
import site
import stat
import sys
import sysconfig
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tracefix.interpreter import Interpreter
from tracefix.runner import EnvironmentCheck, RunResult, run_pytest
from tracefix.runner import check_environment as runner_check_environment
from tracefix.snapshots import (
    Keep,
    Snapshot,
    changed,
    content_snapshot,
    exact_metadata,
    metadata_snapshot,
)
from tracefix.workspace import Workspace, rmtree

# New files with these endings in the copy under test can change what the code does.
CODE_OR_CONFIG_SUFFIXES = (".py", ".pyc", ".pyd", ".so", ".pth", ".ini", ".cfg", ".toml")
STARTUP_NAMES = ("sitecustomize.py", "usercustomize.py")
CODE_OR_CONFIG_NAMES = ("conftest.py", *STARTUP_NAMES)
# Folders in the user's repo whose churn is noise (caches, tools, other environments).
NOISY_DIRS = {"__pycache__", "node_modules", ".venv", "venv", ".tox", ".nox", ".mypy_cache",
              ".pytest_cache", ".ruff_cache", ".idea", ".vscode", ".hypothesis"}  # fmt: skip
CONFIRM_DELAY_S = 0.1
MAX_LISTED = 5


class TamperingDetected(Exception):
    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        shown = "; ".join(problems[:MAX_LISTED])
        more = f" (+{len(problems) - MAX_LISTED} more)" if len(problems) > MAX_LISTED else ""
        super().__init__(f"tampering detected: {shown}{more}")


def _startup_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name.endswith(".pth") or name in STARTUP_NAMES


def _code_or_config(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name.endswith(CODE_OR_CONFIG_SUFFIXES) or name in CODE_OR_CONFIG_NAMES


def _not_noisy(rel: str) -> bool:
    return rel.rsplit("/", 1)[-1] not in NOISY_DIRS


def _repo_dirs(rel: str) -> bool:
    """In the user's repo: skip caches, and inside .git only descend into hooks/."""
    if rel == ".git" or rel == ".git/hooks" or rel.startswith(".git/hooks/"):
        return True
    return not rel.startswith(".git") and _not_noisy(rel)


def _repo_files(rel: str) -> bool:
    return not rel.startswith(".git/") or rel == ".git/config" or rel.startswith(".git/hooks/")


@dataclass(frozen=True)
class Watched:
    """A folder outside the copies that a run must not change."""

    label: str
    root: Path
    keep_dir: Keep = field(default=lambda _p: True)
    keep_file: Keep = field(default=lambda _p: True)
    by_content: bool = False  # hash contents instead of comparing timestamps

    def snapshot(self) -> Snapshot:
        if self.by_content:
            return content_snapshot(self.root, self.keep_dir, self.keep_file)
        return metadata_snapshot(self.root, self.keep_dir, self.keep_file)


# Content snapshots of the interpreter are slow (~0.7 s warm), so each run's "after" is the next
# run's "before". A change made between runs then shows up at the next check.
_CONTENT_CACHE: dict[tuple[str, Path], Snapshot] = {}


def _source(rel: str) -> bool:
    return rel.endswith((".py", ".pth"))


def _binary(rel: str) -> bool:
    return rel.endswith((".pyd", ".dll", ".so", ".dylib"))


def _no_pycache(rel: str) -> bool:
    # Runs read .pyc files only from their own PYTHONPYCACHEPREFIX, and Tracefix from a private
    # prefix (see _private_pycache), so __pycache__ folders are inert, and other Python
    # processes write there all the time.
    return rel.rsplit("/", 1)[-1] != "__pycache__"


_PRIVATE_PYCACHE: list[Path] = []


def _private_pycache() -> Path:
    """Tracefix's own .pyc folder, so a .pyc planted in a shared __pycache__ never runs inside
    Tracefix (which holds the API key). Created once, watched like the environment."""
    if not _PRIVATE_PYCACHE:
        folder = Path(tempfile.mkdtemp(prefix="tracefix-pycache-")).resolve()
        _PRIVATE_PYCACHE.append(folder)
        sys.pycache_prefix = str(folder)
    return _PRIVATE_PYCACHE[0]


def _no_subdirs(_rel: str) -> bool:
    return False


# A distribution's Python lives in the system's own prefix, which it shares with everything else
# installed there (a GitHub runner's /usr holds hundreds of thousands of files, so walking it took
# minutes per run). There only Python's own folders are watched; any other prefix is a dedicated
# install and is watched whole.
SHARED_PREFIXES = frozenset({Path("/"), Path("/usr"), Path("/usr/local")})


def interpreter_roots(prefixes: Sequence[Path], python_dirs: Sequence[Path]) -> set[Path]:
    """The interpreter folders to watch: each prefix (venv, base install) unless it is a shared
    system prefix, then the Python folders (stdlib, site-packages, sys.path entries) inside a
    shared one. Folders outside every prefix (the project, PYTHONPATH) are not the interpreter's."""
    shared = [p for p in prefixes if p in SHARED_PREFIXES]
    roots = {p for p in prefixes if p not in SHARED_PREFIXES}
    roots.update(
        d for d in python_dirs
        if d not in SHARED_PREFIXES and any(d.is_relative_to(p) for p in shared)
    )  # fmt: skip
    return roots


def _python_dirs() -> list[Path]:
    """Where this interpreter and its base install load code from."""
    names = ("stdlib", "platstdlib", "purelib", "platlib")
    dirs = [sysconfig.get_paths()[n] for n in names]
    base_vars = {"base": sys.base_prefix, "platbase": sys.base_exec_prefix}
    dirs += [sysconfig.get_paths(vars=base_vars)[n] for n in names]
    dirs += [p for p in sys.path if p]
    return [Path(d).resolve() for d in dirs]


def _project_roots(python: Interpreter) -> set[Path]:
    """The project's Python environment (--python), when it isn't Tracefix's own."""
    if python.own:
        return set()
    prefixes = [p.resolve() for p in python.prefixes]
    roots = interpreter_roots(prefixes, [d.resolve() for d in python.code_dirs])
    stdlib = python.code_dirs[:1]  # the check reports stdlib first
    return (roots | {d.resolve() for d in stdlib}) - SHARED_PREFIXES


def watched_folders(ws: Workspace) -> list[Watched]:
    """Tracefix's environment, the project's Python environment (when it is another one), the
    user's repository and the folders around the copies."""
    import tracefix

    env = "Tracefix's environment"
    # Windows can't tell a same-size edit with its mtime set back from no edit at all, so there
    # Python sources are compared by content; elsewhere ctime gives that away.
    sources_by_content = os.name == "nt"
    folders = [Watched(env, Path(tracefix.__file__).parent.resolve(), by_content=True),
               Watched(env, _private_pycache())]  # fmt: skip
    prefixes = [Path(p).resolve() for p in (sys.prefix, sys.base_prefix)]
    roots = interpreter_roots(prefixes, _python_dirs())
    roots |= {Path(p).resolve() for p in (sysconfig.get_paths()["stdlib"],
                                          site.getusersitepackages())}  # fmt: skip
    labels = dict.fromkeys(_project_roots(ws.settings.python), "the project's Python environment")
    labels.update(dict.fromkeys(roots - SHARED_PREFIXES, env))  # a shared folder: Tracefix's
    for root in sorted(labels):
        if any(root != r and root.is_relative_to(r) for r in labels):
            continue  # inside another watched root
        label = labels[root]
        folders.append(Watched(label, root, _no_pycache, _source, by_content=sources_by_content))
        folders.append(Watched(label, root, _no_pycache, _binary))
    folders.append(Watched("your repository", ws.repo, _repo_dirs, _repo_files))
    for parent in {ws.root, *(copy.parent for copy in ws.copies)}:
        # Around the copies (pytest looks for config in parent folders): only direct entries.
        folders.append(Watched("a folder around the copies", parent, _no_subdirs))
    return [f for f in folders if f.root.is_dir()]


def _confirmed(folder: Watched, before: Snapshot, paths: list[str]) -> list[str]:
    """Re-check differences with a fresh lstat: on Windows a directory listing can report a
    file's old timestamps for a moment after a write, which would be a false alarm."""
    if not paths or os.name != "nt" or folder.by_content:
        return paths
    time.sleep(CONFIRM_DELAY_S)
    return [p for p in paths if exact_metadata(folder.root / p) != before.get(p)]


def _remove(root: Path, paths: list[str]) -> list[str]:
    """Delete paths, deepest first. Never raises: returns what could not be removed."""
    failed = []
    for rel in sorted(paths, key=len, reverse=True):
        target = root / rel
        try:
            if target.is_dir() and not target.is_symlink():
                rmtree(target)
            else:
                if not os.access(target, os.W_OK) and not target.is_symlink():
                    target.chmod(stat.S_IWRITE | stat.S_IREAD)  # read-only files on Windows
                target.unlink(missing_ok=True)
        except OSError as exc:
            failed.append(f"could not remove {target}: {exc.strerror or exc}")
    return failed


@dataclass
class Watch:
    """What one run may and may not change, and the state it must start from."""

    ws: Workspace
    under_test: Path
    copies: dict[Path, Snapshot]
    folders: list[tuple[Watched, Snapshot]]
    bytecode_flag: bool

    @classmethod
    def start(cls, ws: Workspace, under_test: Path, placed: Sequence[str] = ()) -> "Watch":
        """Raise TamperingDetected if a copy drifted from its exported state since the last
        run (e.g. a process that outlived a previous run); else snapshot everything else."""
        flag, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # our imports aren't noise
        copies: dict[Path, Snapshot] = {}
        drift: list[str] = []
        for copy in ws.copies:
            now = content_snapshot(copy)
            expected = dict(ws.pristine[copy])
            if copy == under_test:
                for p in placed:  # written for this run, or removed for it if absent now
                    if p not in now:
                        expected.pop(p, None)
                    elif now[p][0] in ("file", "large"):  # large: over the hash cap
                        expected[p] = now[p]
                    else:  # a link or special file: Tracefix only ever places plain files
                        drift.append(f"the copy under test: placed file {p} is not a plain file")
            drift += [f"{_label(copy, under_test)} changed between runs: {p}"
                      for p in changed(expected, now)]  # fmt: skip
            copies[copy] = expected
        if drift:
            sys.dont_write_bytecode = flag
            raise TamperingDetected(drift)
        folders = [(f, _CONTENT_CACHE.get((f.label, f.root)) or f.snapshot()) if f.by_content
                   else (f, f.snapshot()) for f in watched_folders(ws)]  # fmt: skip
        return cls(ws, under_test, copies, folders, flag)

    def finish(self) -> list[str]:
        """Check everything; delete leftovers and planted start-up files. Returns the problems."""
        try:
            return self._problems()
        finally:
            sys.dont_write_bytecode = self.bytecode_flag

    def _problems(self) -> list[str]:
        problems: list[str] = []
        for copy, expected in self.copies.items():
            diff = changed(expected, content_snapshot(copy))
            label = _label(copy, self.under_test)
            if copy != self.under_test:
                problems += [f"{label}: {p}" for p in diff]
                continue
            leftovers = [p for p in diff if p not in expected and not _code_or_config(p)]
            problems += [f"{label}: {p}" for p in diff if p not in leftovers]
            # New files go either way: harmless leftovers silently, planted code/config after
            # being reported, so the copy never keeps them.
            problems += _remove(copy, [p for p in diff if p not in expected])
        for folder, before in self.folders:
            after = folder.snapshot()
            diff = _confirmed(folder, before, changed(before, after))
            if folder.by_content:
                # Reuse this snapshot only if nothing changed: after a detection (and the
                # deletion of planted files) the folder no longer matches it.
                key = (folder.label, folder.root)
                if diff:
                    _CONTENT_CACHE.pop(key, None)
                else:
                    _CONTENT_CACHE[key] = after
            problems += [f"{folder.label}: {folder.root / p}" for p in diff]
            problems += _remove(folder.root, [p for p in diff
                                              if p not in before and _startup_file(p)])  # fmt: skip
        return problems


def _label(copy: Path, under_test: Path) -> str:
    return "the copy under test" if copy == under_test else "the other copy"


def run_checked(
    ws: Workspace, tree: Path, targets: Sequence[str], placed: Sequence[str] = (), **kwargs: Any
) -> RunResult:
    """run_pytest in one copy, watched. `placed` are files Tracefix wrote into the copy for this
    run (e.g. the repro test, a mutated source file), or removed from it if they are absent now
    (e.g. a file the fix added, for Guard's revert). Raises TamperingDetected if anything outside
    the rules changed;
    harmless leftovers in the copy under test are removed either way.

    The workspace's run settings apply to every run: its package folders in `tree` go ahead of
    installed packages, its pytest plugins are loaded, the project's Python runs the tests, and
    the suite timeout is the default."""
    kwargs.setdefault("timeout_s", ws.settings.suite_timeout_s)
    kwargs.setdefault("python", ws.settings.python.executable)
    kwargs.setdefault("safe_path", ws.settings.python.safe_path)
    roots = [tree / root for root in ws.import_roots if (tree / root).is_dir()]
    watch = Watch.start(ws, tree, placed)
    result = run_pytest(tree, targets, import_roots=roots, plugins=ws.settings.pytest_plugins,
                        **kwargs)  # fmt: skip
    problems = watch.finish()
    if problems:
        raise TamperingDetected(problems)
    return result


def check_environment(ws: Workspace, tree: Path | None = None, **kwargs: Any) -> EnvironmentCheck:
    """The base-suite environment check (or `tree`'s: the pipeline runs head's only to word an
    error), watched like every other run: its leftovers are removed, and tampering raises
    TamperingDetected instead of passing unseen."""

    def watched(tree: Path, **run_args: Any) -> RunResult:
        return run_checked(ws, tree, (), **run_args)

    kwargs.setdefault("timeout_s", ws.settings.suite_timeout_s)
    return runner_check_environment(tree or ws.base, run_suite=watched, **kwargs)

"""Plain copies of the base and head commits, each in its own random temp folder.

Refs are resolved to exact commit ids before anything else happens, and every later stage
works with those ids only. The user's working copy is never touched, and the copies contain no
`.git` link back to it: code run in a copy cannot reach the user's repository through git.
"""

import functools
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import warnings
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any

from tracefix.interpreter import Interpreter, current
from tracefix.runner import DEFAULT_TIMEOUT_S
from tracefix.snapshots import Snapshot, content_snapshot, size_checked_only

GIT_TIMEOUT_S = 120
MIN_SHA_PREFIX = 7
_HEX = re.compile(r"[0-9a-fA-F]+")
# Where git itself looks up a short name, most specific first (gitrevisions(7)).
_NAME_PREFIXES = ("", "refs/", "refs/tags/", "refs/heads/", "refs/remotes/")
_GIT_ENV_ALLOWLIST = {
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
    "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "LANG", "LC_ALL", "LC_CTYPE",
}  # fmt: skip
CLEANUP_ATTEMPTS = 3


class WorkspaceError(Exception):
    """A ref or repo problem that stops the run before any test executes."""


def git_env() -> dict[str, str]:
    """A minimal environment for git: no GIT_* overrides (e.g. GIT_DIR), no API keys, and no
    global or system config, so results don't depend on the machine's git setup."""
    env = {k: v for k, v in os.environ.items() if k.upper() in _GIT_ENV_ALLOWLIST}
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_LFS_SKIP_SMUDGE"] = "1"  # never download LFS content during checkout
    return env


def _subcommand(args: tuple[str, ...]) -> str:
    """The git subcommand in args, skipping options like `-c key=value`."""
    return next((a for a in args if not a.startswith("-") and "=" not in a), "")


@functools.cache
def user_safe_directories() -> tuple[str, ...]:
    """The user's own `safe.directory` entries from their global and system git config.

    Isolating git from that config would otherwise also drop the user's trust in repos owned
    by another account (common in CI containers). Repo-local config is never read here, so a
    repo cannot mark itself as safe.
    """
    found: list[str] = []
    for scope in ("--system", "--global"):
        try:
            result = subprocess.run(
                ["git", "config", scope, "--get-all", "safe.directory"],
                cwd=tempfile.gettempdir(),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=GIT_TIMEOUT_S,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            found.extend(line for line in result.stdout.splitlines() if line)
    return tuple(found)


def _base_command() -> list[str]:
    command = ["git", "-c", "core.longpaths=true"]
    for directory in user_safe_directories():
        command += ["-c", f"safe.directory={directory}"]
    return command


def git_run(
    repo: Path, *args: str, extra_env: Mapping[str, str] | None = None
) -> "subprocess.CompletedProcess[bytes]":
    """Run git in repo with git_env() plus `extra_env` (kept out of argv); any exit code is
    returned. Raises WorkspaceError only when git could not run at all."""
    try:
        return subprocess.run(
            [*_base_command(), *args],
            cwd=repo,
            env={**git_env(), **(extra_env or {})},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=GIT_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceError(f"git {_subcommand(args)} could not run: {exc}") from exc


def git_bytes(repo: Path, *args: str, extra_env: Mapping[str, str] | None = None) -> bytes:
    """Run git in repo and return raw stdout; raise WorkspaceError on failure."""
    result = git_run(repo, *args, extra_env=extra_env)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise WorkspaceError(f"git {_subcommand(args)} failed: {stderr}")
    return result.stdout


def git(repo: Path, *args: str) -> str:
    """Run git in repo and return stdout as text; raise WorkspaceError on failure."""
    return git_bytes(repo, *args).decode("utf-8", errors="replace")


def blob_text(repo: Path, sha: str, path: str) -> str | None:
    """A file's text at a commit, from git objects; None if it isn't there or isn't UTF-8."""
    try:
        return git_bytes(repo, "show", f"{sha}:{path}").decode("utf-8")
    except (WorkspaceError, UnicodeDecodeError):
        return None


def require_repo(repo: Path) -> None:
    """repo must be the top folder of a git work tree, not a folder inside some other repo."""
    if not repo.is_dir():
        raise WorkspaceError(f"repo path is not a directory: {repo}")
    try:
        top = git(repo, "rev-parse", "--show-toplevel").strip()
    except WorkspaceError as exc:
        if "dubious ownership" in str(exc):
            raise WorkspaceError(
                f"git does not trust {repo} because another account owns it; if you trust it, "
                f"run: git config --global --add safe.directory {repo.as_posix()}"
            ) from exc
        raise WorkspaceError(f"not a git repository: {repo}") from exc
    if not top or not os.path.samefile(top, repo):
        raise WorkspaceError(f"not a git repository: {repo} (it is inside {top or 'a git dir'})")


def _object_type(repo: Path, sha: str) -> str:
    return git(repo, "cat-file", "-t", sha).strip()


def _peeled_refs(repo: Path) -> dict[str, str]:
    """Every ref name -> the object it finally points to (annotated tags peeled)."""
    out = git(repo, "for-each-ref", "--format=%(refname)%00%(objectname)%00%(*objectname)")
    refs: dict[str, str] = {}
    for line in out.splitlines():
        name, obj, peeled = line.split("\0")
        refs[name] = peeled or obj
    return refs


def _name_matches(repo: Path, ref: str) -> dict[str, str]:
    """Ref names that `ref` could mean, compared case-sensitively (unlike the filesystem)."""
    if ref == "HEAD":
        return {"HEAD": git(repo, "rev-parse", "--verify", "HEAD^{object}").strip()}
    refs = _peeled_refs(repo)
    found = {prefix + ref: refs[prefix + ref] for prefix in _NAME_PREFIXES if prefix + ref in refs}
    if f"refs/remotes/{ref}/HEAD" in refs:
        found[f"refs/remotes/{ref}/HEAD"] = refs[f"refs/remotes/{ref}/HEAD"]
    return found


def _sha_matches(repo: Path, ref: str) -> dict[str, str]:
    """Commits whose id starts with `ref`, if it looks like an abbreviated id."""
    if len(ref) < MIN_SHA_PREFIX or not _HEX.fullmatch(ref):
        return {}
    out = git(repo, "rev-parse", "--disambiguate=" + ref.lower())
    commits = [sha for sha in out.split() if _object_type(repo, sha) == "commit"]
    return {f"commit {sha}": sha for sha in commits}


def resolve_ref(repo: Path, ref: str) -> str:
    """Return the full commit id `ref` names, or raise WorkspaceError.

    Rejects names that could mean two different commits, e.g. a tag and a branch, or a name
    and an abbreviated commit id. Bare `head` never means `.git/HEAD`.
    """
    if not ref or ref.startswith("-") or any(c.isspace() or ord(c) < 32 for c in ref):
        raise WorkspaceError(f"invalid ref: {ref!r}")
    candidates = {**_name_matches(repo, ref), **_sha_matches(repo, ref)}
    if not candidates:
        raise WorkspaceError(f"unknown ref: {ref!r}")
    if len(set(candidates.values())) > 1:
        names = ", ".join(sorted(candidates))
        raise WorkspaceError(f"ambiguous ref {ref!r}: it could mean {names}")
    sha = next(iter(candidates.values()))
    kind = _object_type(repo, sha)
    if kind != "commit":
        raise WorkspaceError(f"ref {ref!r} points to a {kind}, not a commit")
    return sha


def _make_writable(func: Callable[..., Any], path: str, _exc: object) -> None:
    # git marks object files read-only; Windows refuses to delete those without this.
    os.chmod(path, stat.S_IWRITE)
    func(path)


def rmtree(path: Path) -> None:
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_make_writable)
    else:
        shutil.rmtree(path, onerror=_make_writable)


# Path components that must never come out of a tree we export (git refuses most already).
_FORBIDDEN_PARTS = {"", ".", "..", ".git"}
SUBMODULE_MODE = b"160000"
EXEC_MODE = b"100755"


def safe_relpath(path: str) -> str | None:
    """The path if it is a safe relative path inside a copy, else None."""
    if path.startswith("/") or "\\" in path or re.match(r"^[A-Za-z]:", path):
        return None
    parts = path.split("/")
    if any(p.lower() in _FORBIDDEN_PARTS or p.lower().startswith(".git ") for p in parts):
        return None
    return path


def _read_blobs(repo: Path, oids: list[bytes]) -> list[bytes]:
    """Contents of many blobs from one `git cat-file --batch` call, in order."""
    if not oids:
        return []
    try:
        result = subprocess.run(
            [*_base_command(), "cat-file", "--batch"],
            cwd=repo,
            env=git_env(),
            input=b"\n".join(oids) + b"\n",
            capture_output=True,
            timeout=GIT_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceError(f"git cat-file could not run: {exc}") from exc
    if result.returncode != 0:
        raise WorkspaceError(f"git cat-file failed: {result.stderr.decode(errors='replace')}")
    out, pos, blobs = result.stdout, 0, []
    for _ in oids:
        header_end = out.index(b"\n", pos)
        _oid, kind, size = out[pos:header_end].split(b" ")
        if kind != b"blob":
            raise WorkspaceError(f"expected a blob, got {kind.decode()}")
        start = header_end + 1
        blobs.append(out[start : start + int(size)])
        pos = start + int(size) + 1  # content is followed by a newline
    return blobs


def export_commit(repo: Path, sha: str, dest: Path) -> list[str]:
    """Write every file of commit `sha` into `dest`, reading git objects directly.

    No checkout, so no hooks, filters or .gitattributes (export-ignore/export-subst) apply and
    no .git link is created. Executable bits are kept; symlinks become plain files holding the
    link text (like git's core.symlinks=false). Returns what was skipped (submodules, unsafe or
    unwritable paths), as "path (reason)".
    """
    dest.mkdir(parents=True)
    root = dest.resolve()
    listing = git_bytes(repo, "ls-tree", "-r", "-z", "--full-tree", sha)
    files: list[tuple[str, bytes, bytes]] = []
    skipped = []
    for record in listing.split(b"\0"):
        if not record:
            continue
        meta, raw_path = record.split(b"\t", 1)
        mode, _kind, oid = meta.split(b" ")
        path = os.fsdecode(raw_path)
        if mode == SUBMODULE_MODE:
            skipped.append(f"{path} (submodule)")
        elif safe_relpath(path) is None:
            skipped.append(f"{path} (unsafe path)")
        else:
            files.append((path, mode, oid))
    contents = _read_blobs(repo, [oid for _, _, oid in files])
    for (path, mode, _oid), content in zip(files, contents, strict=True):
        target = root / path
        if not target.resolve().is_relative_to(root):
            skipped.append(f"{path} (outside the copy)")
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            if mode == EXEC_MODE and os.name == "posix":
                target.chmod(0o755)
        except OSError as exc:
            skipped.append(f"{path} (cannot be written here: {exc.strerror})")
    return skipped


@dataclass(frozen=True)
class RunSettings:
    """How every run in the copies is made (from config.Settings); isolation.run_checked
    applies them, so no stage has to remember to."""

    suite_timeout_s: float = DEFAULT_TIMEOUT_S  # one run of the whole suite or of test files
    pytest_plugins: tuple[str, ...] = ()  # module names loaded with -p (autoload stays off)
    python: Interpreter = field(default_factory=current)  # the project's Python (--python)


MAX_IMPORT_ROOTS = 20
# Folders that never hold the project's own packages: environments, caches, build output.
_NOT_SOURCE = {"__pycache__", "node_modules", "site-packages", "dist-packages", "venv", "env",
               "build", "dist"}  # fmt: skip
# Files at a project's top that are scripts, not its code: importing one runs it.
SCRIPT_NAMES = {"setup.py", "conftest.py", "noxfile.py", "fabfile.py"}


def _skipped_folder(folders: list[str], files: set[str]) -> bool:
    """Hidden, environment, cache or build folders, a virtualenv (it holds pyvenv.cfg), or the
    test layout (SPEC 2.2: a `tests` folder anywhere)."""
    for i, name in enumerate(folders):
        if name.startswith(".") or name in _NOT_SOURCE or name == "tests":
            return True
        if "/".join([*folders[: i + 1], "pyvenv.cfg"]) in files:
            return True
    return False


def is_script_or_test(name: str) -> bool:
    """A file name that is never the project's importable code: a test module, a conftest or a
    build/task script (importing it runs it)."""
    return name in SCRIPT_NAMES or name.startswith("test_") or name.endswith("_test.py")


def _module_root(parts: list[str], files: set[str]) -> str | None:
    """The copy itself or `src` when it directly holds a top-level module (the single-module
    layouts, e.g. `slug.py` or `src/slug.py`), else None."""
    folder = "/".join(parts[:-1])
    if folder not in ("", "src") or not parts[-1].endswith(".py") or is_script_or_test(parts[-1]):
        return None
    if parts[-1] == "__init__.py" or f"{folder}/__init__.py".lstrip("/") in files:
        return None
    return folder or "."


def package_roots(paths: Iterable[str]) -> list[str]:
    """The folders that hold a copy's top-level packages, from its file list: a folder with an
    __init__.py whose parent has none gives that parent ("." for the copy itself), and the copy
    or `src` when it holds a top-level module. Shallowest first. Namespace packages (no
    __init__.py) give none."""
    files = set(paths)
    roots = set()
    for path in files:
        parts = path.split("/")
        module_root = _module_root(parts, files)
        if module_root is not None:
            roots.add(module_root)
        if parts[-1] != "__init__.py" or len(parts) < 2:
            continue
        folders = parts[:-1]
        parent = "/".join(folders[:-1])
        if _skipped_folder(folders, files) or f"{parent}/__init__.py".lstrip("/") in files:
            continue
        roots.add(parent or ".")
    return sorted(roots, key=lambda r: (0 if r == "." else r.count("/") + 1, r))


class Workspace:
    """Plain copies of the base and head commits, for running code in.

    `base` and `head` (and any extra copy) are all named `repo`, each inside its own
    `tracefix-<random>` temp folder, so a path says nothing about which one it is. `root` is
    Tracefix's own scratch folder. Use as a context manager; everything is removed on exit, even
    after an error.
    """

    def __init__(
        self, repo: Path, base_ref: str, head_ref: str, settings: RunSettings | None = None
    ) -> None:
        self.repo = repo.resolve()
        self.settings = settings or RunSettings()
        self.base_ref = base_ref
        self.head_ref = head_ref
        self.base_sha = ""
        self.head_sha = ""
        self.root = Path()
        self.base = Path()
        self.head = Path()
        self.skipped: list[str] = []  # files not copied, e.g. "base: vendor/lib (submodule)"
        self.leftovers: list[Path] = []  # paths cleanup could not remove (also warned)
        self.copies: list[Path] = []  # base, head, then any extra copies (add_copy)
        self.pristine: dict[Path, Snapshot] = {}  # each copy's state right after export
        self.notes: list[str] = []  # limits of the tamper watch here, for the receipt
        # Folders (relative, "." for the copy) holding base's and head's top-level packages: each
        # run puts them, in the copy under test, ahead of site-packages (sandbox.PATHS_SOURCE).
        self.import_roots: tuple[str, ...] = ()
        self._folders: list[Path] = []

    def __enter__(self) -> "Workspace":
        require_repo(self.repo)
        self.base_sha = resolve_ref(self.repo, self.base_ref)
        self.head_sha = resolve_ref(self.repo, self.head_ref)
        try:
            self.root = self._new_folder()
            self.base = self._export("base", self.base_sha)
            self.head = self._export("head", self.head_sha)
            both = [*self.pristine[self.base], *self.pristine[self.head]]
            roots = package_roots(both)
            self.import_roots = tuple(roots[:MAX_IMPORT_ROOTS])
            if len(roots) > MAX_IMPORT_ROOTS:
                self.notes.append(
                    f"only the {MAX_IMPORT_ROOTS} shallowest of {len(roots)} package folders "
                    "were put ahead of installed packages"
                )
        except BaseException:
            self.cleanup()
            raise
        return self

    def _export(self, side: str, sha: str) -> Path:
        copy = self._new_folder() / "repo"
        skipped = export_commit(self.repo, sha, copy)
        self.pristine[copy] = content_snapshot(copy)
        self.copies.append(copy)
        if side in ("base", "head"):  # an extra copy of the same commit would only repeat these
            self.skipped += [f"{side}: {s}" for s in skipped]
            self.notes += [f"{side}: {p} is too large to hash, so a rewrite of it is checked by "
                           "size and timestamp only"
                           for p in size_checked_only(self.pristine[copy])]  # fmt: skip
        return copy

    def add_copy(self, sha: str) -> Path:
        """One more plain copy of commit `sha` (e.g. head, for Guard to swap files in), exported
        and recorded like base and head, so the tamper watch covers it in every run."""
        return self._export("extra", sha)

    def in_head(self, path: str) -> bool:
        """The path is a safe relative path that the export actually wrote into head's copy. Diff
        paths come from the repo, so nothing is ever written anywhere else."""
        return safe_relpath(path) is not None and path in self.pristine[self.head]

    def remove_copy(self, copy: Path) -> None:
        """Forget an extra copy and delete it, so later runs neither watch nor inherit it.
        Never raises (a folder that can't be deleted is warned about, like in cleanup)."""
        if copy in (self.base, self.head) or copy not in self.copies:
            return
        self.copies.remove(copy)
        self.pristine.pop(copy, None)
        self._remove(copy.parent)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.cleanup()

    def _new_folder(self) -> Path:
        folder = Path(tempfile.mkdtemp(prefix="tracefix-")).resolve()
        self._folders.append(folder)
        return folder

    def _remove(self, path: Path) -> None:
        """Delete a folder, retrying briefly (Windows holds files of just-killed processes)."""
        for attempt in range(CLEANUP_ATTEMPTS):
            try:
                rmtree(path)
                return
            except FileNotFoundError:
                return
            except OSError as exc:
                if attempt == CLEANUP_ATTEMPTS - 1:
                    self.leftovers.append(path)
                    warnings.warn(f"tracefix could not remove {path}: {exc}", stacklevel=3)
                else:
                    time.sleep(0.5)

    def cleanup(self) -> None:
        """Remove the copies and the scratch folder. Never raises, so an error from the stage
        that was running is never hidden. Safe to call twice."""
        for folder in self._folders:
            if folder.exists():
                self._remove(folder)

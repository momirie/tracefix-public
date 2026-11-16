"""Extra copies of a commit that a stage changes between runs (Guard's mutants and revert,
Integrity's old tests and removed branches).

Files are written into a copy only through `swapped`, which never follows a link and puts the
copy back after a clean run. `variant_copy` exports the copy, checks at the end that it is exactly
the commit again (anything left over is tampering), and always removes it, so later stages never
watch or inherit it. Runs themselves still go through `isolation.run_checked`.
"""

import os
import stat
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, suppress
from pathlib import Path, PurePosixPath

from tracefix.isolation import TamperingDetected
from tracefix.snapshots import changed, content_snapshot, is_link_stat
from tracefix.workspace import Workspace, safe_relpath

# Windows has no O_NOFOLLOW (it is 0 there): the last path part is then checked just before
# it is opened (plain_target), and the run's whole process tree is already dead by then.
_WRITE_FLAGS = (os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_BINARY", 0))  # fmt: skip


def _is_link(path: Path) -> bool:
    """A symlink, or a Windows junction (which Python reports as a folder)."""
    try:
        return is_link_stat(os.lstat(path))
    except FileNotFoundError:
        return False


def plain_target(tree: Path, rel: str) -> Path:
    """tree/rel, if writing there stays inside the copy: a safe relative path, no link on the
    way, and not something other than a plain file. Copies never contain links, so one is
    tampering."""
    if safe_relpath(rel) is None:
        raise TamperingDetected([f"refusing to write {rel!r}: not a safe path inside the copy"])
    folder = tree
    for part in PurePosixPath(rel).parts[:-1]:
        folder = folder / part
        if _is_link(folder) or (folder.exists() and not folder.is_dir()):
            raise TamperingDetected([f"the copy under test: {rel} goes through a link"])
    target = tree / rel
    if _is_link(target) or (target.exists() and not target.is_file()):
        raise TamperingDetected([f"the copy under test: {rel} is not a plain file"])
    return target


def write(target: Path, content: bytes, mode: int = 0o644) -> None:
    fd = os.open(target, _WRITE_FLAGS, mode)
    try:
        view = memoryview(content)
        while view:
            view = view[os.write(fd, view) :]
    finally:
        os.close(fd)


def _make_folders(folder: Path, tree: Path) -> list[Path]:
    """Create folder and its missing parents inside tree; return the ones created, deepest last."""
    missing = []
    while folder != tree and not folder.exists():
        missing.append(folder)
        folder = folder.parent
    for path in reversed(missing):
        path.mkdir()
    return list(reversed(missing))


@contextmanager
def swapped(tree: Path, files: Mapping[str, bytes | None]) -> Iterator[None]:
    """Write (or delete, for None) files in the copy, and put the old ones back after a clean
    run: contents, modes, and no folder that wasn't there.

    Writes never follow links. After an exception (e.g. tampering detected) nothing is put back:
    the copy is no longer trusted, and it is checked and dropped at the end of the stage."""
    saved: dict[str, tuple[bytes, int] | None] = {}
    created: list[Path] = []
    for rel, content in files.items():
        target = plain_target(tree, rel)
        saved[rel] = (target.read_bytes(), target.stat().st_mode) if target.is_file() else None
        if content is None:
            target.unlink(missing_ok=True)
        else:
            created += _make_folders(target.parent, tree)
            write(target, content)
    yield
    for rel, old in saved.items():
        target = plain_target(tree, rel)
        try:
            if old is None:
                target.unlink(missing_ok=True)
            else:
                write(target, old[0])
                os.chmod(target, stat.S_IMODE(old[1]))
        except OSError as exc:  # e.g. a folder made read-only: modes aren't snapshotted
            problem = f"the copy under test: could not put {rel} back: {exc.strerror or exc}"
            raise TamperingDetected([problem]) from exc
    for folder in sorted(created, key=lambda p: len(p.parts), reverse=True):
        with suppress(OSError):  # not empty: the next run's watch reports what is left in it
            folder.rmdir()


@contextmanager
def variant_copy(ws: Workspace, sha: str, name: str) -> Iterator[Path]:
    """A new plain copy of `sha` (`name` says which commit, e.g. "head", in tampering reasons).

    When the block ends normally the copy must be exactly the commit again, else
    TamperingDetected. The copy is removed in every case."""
    tree = ws.add_copy(sha)
    try:
        yield tree
        drift = changed(ws.pristine[tree], content_snapshot(tree))
        if drift:
            raise TamperingDetected([f"the variant copy is not back to {name}: {p}" for p in drift])
    finally:
        ws.remove_copy(tree)

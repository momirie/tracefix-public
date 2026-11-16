"""File-tree snapshots for tamper detection: what is in a folder, cheaply and without hanging.

Only files, links and special files are recorded, never folders (a folder's timestamp changes
for harmless reasons). Regular files are hashed in chunks up to a size cap; FIFOs, sockets and
devices are recorded by type without being opened; unreadable entries are recorded as such.
Links and Windows junctions are recorded by target and never followed. A file swapped for
something else between listing and hashing is opened without following links or blocking, so
the snapshot always finishes.
"""

import errno
import hashlib
import os
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

HASH_CAP_BYTES = 64 * 1024 * 1024  # bigger files: size + timestamps only
CHUNK_BYTES = 1024 * 1024
# No following links, no blocking on a FIFO, no newline translation (flags missing here are 0).
_OPEN_FLAGS = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
               | getattr(os, "O_BINARY", 0))  # fmt: skip
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)

Snapshot = dict[str, tuple[Any, ...]]
Keep = Callable[[str], bool]  # relative path -> include it?


def _walk(root: Path, keep_dir: Keep, base: Path) -> list[os.DirEntry[str]]:
    """Every non-folder entry under root, not following links; folders pruned by keep_dir."""
    found: list[os.DirEntry[str]] = []
    try:
        with os.scandir(root) as it:
            entries = list(it)
    except OSError:
        return found  # missing, vanished or unreadable folder: nothing to record
    for entry in entries:
        try:
            is_dir = entry.is_dir(follow_symlinks=False) and not _is_link(entry)
        except OSError:
            is_dir = False  # recorded below as unreadable
        if is_dir:
            if keep_dir(Path(entry.path).relative_to(base).as_posix()):
                found += _walk(Path(entry.path), keep_dir, base)
        else:
            found.append(entry)
    return found


def is_link_stat(st: os.stat_result) -> bool:
    """A symlink, or a Windows junction (which Python reports as a folder, though it points
    elsewhere), from an lstat result. The one definition of a link, for the tamper watch
    and for Guard's writes."""
    attributes: int = getattr(st, "st_file_attributes", 0)
    return stat.S_ISLNK(st.st_mode) or bool(attributes & _REPARSE_POINT)


def _is_link(entry: os.DirEntry[str]) -> bool:
    return is_link_stat(entry.stat(follow_symlinks=False))


def _rel(root: Path, entry: os.DirEntry[str]) -> str:
    return Path(entry.path).relative_to(root).as_posix()


def _digest(path: str) -> str:
    """sha256 of a regular file's first HASH_CAP_BYTES bytes. Raises OSError if path is no
    longer a regular file (swapped since it was listed: a link, FIFO or device)."""
    fd = os.open(path, _OPEN_FLAGS)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(0, "no longer a regular file")
        sha = hashlib.sha256()
        remaining = HASH_CAP_BYTES  # a file growing during the read can't keep us reading
        while remaining > 0 and (chunk := os.read(fd, min(CHUNK_BYTES, remaining))):
            sha.update(chunk)
            remaining -= len(chunk)
        return sha.hexdigest()
    finally:
        os.close(fd)


def _large_state(st: os.stat_result) -> tuple[Any, ...]:
    # On POSIX ctime changes with every write and cannot be set back by the writer; Windows has
    # no such time, so there these files are checked by size and mtime only (size_checked_only).
    if os.name == "nt":
        return ("large", st.st_size, st.st_mtime_ns)
    return ("large", st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _content_state(entry: os.DirEntry[str]) -> tuple[Any, ...] | None:
    try:
        st = entry.stat(follow_symlinks=False)
        if _is_link(entry):
            return ("link", os.readlink(entry.path))
        if not stat.S_ISREG(st.st_mode):
            return ("special", stat.S_IFMT(st.st_mode))  # FIFO, socket, device: never opened
        if st.st_size > HASH_CAP_BYTES:
            return _large_state(st)
        try:
            return ("file", st.st_mode & 0o777, st.st_size, _digest(entry.path))
        except FileNotFoundError:
            raise
        except OSError as exc:
            return ("file", st.st_mode & 0o777, st.st_size, f"unreadable: {exc.errno}")
    except FileNotFoundError:
        return None  # vanished during the walk
    except OSError as exc:
        return ("unreadable", exc.errno)  # e.g. inside a folder that can't be entered


def content_snapshot(
    root: Path, keep_dir: Keep = lambda _p: True, keep_file: Keep = lambda _p: True
) -> Snapshot:
    """{relative path: state} with file contents hashed: for the copies, and for interpreter
    sources where timestamps can be set back (Windows has no unforgeable change time)."""
    snap: Snapshot = {}
    for entry in _walk(root, keep_dir, root):
        if not keep_file(_rel(root, entry)):
            continue
        state = _content_state(entry)
        if state is not None:
            snap[_rel(root, entry)] = state
    return snap


def metadata_snapshot(
    root: Path, keep_dir: Keep = lambda _p: True, keep_file: Keep = lambda _p: True
) -> Snapshot:
    """{relative path: (size, mtime_ns, ctime_ns)}: fast, for big trees. On Linux ctime changes
    with every write and cannot be set back by the writer."""
    snap: Snapshot = {}
    for entry in _walk(root, keep_dir, root):
        rel = _rel(root, entry)
        if not keep_file(rel):
            continue
        try:
            st = entry.stat(follow_symlinks=False)
        except FileNotFoundError:
            continue
        except OSError as exc:
            snap[rel] = ("unreadable", exc.errno)
            continue
        snap[rel] = (st.st_size, st.st_mtime_ns, st.st_ctime_ns)
    return snap


def exact_metadata(path: Path) -> tuple[Any, ...] | None:
    """The same state from a fresh lstat (no directory-listing cache); None if gone."""
    try:
        st = os.lstat(path)
    except OSError as exc:
        if exc.errno in (errno.ENOENT, errno.ENOTDIR):
            return None
        return ("unreadable", exc.errno)
    return (st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def size_checked_only(snap: Snapshot) -> list[str]:
    """Files in a content snapshot whose contents were not hashed and whose rewrite could go
    unseen (over HASH_CAP_BYTES on Windows), for a note in the stage result."""
    return sorted(p for p, state in snap.items() if state[0] == "large" and len(state) == 3)


def changed(before: Snapshot, after: Snapshot) -> list[str]:
    return sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))

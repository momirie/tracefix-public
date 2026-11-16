"""Snapshots must never hang, crash or walk out of their root, whatever a watched process does.

Regressions for the snapshot review findings (NOTES questions 19-22, fixed in M4).
"""

import hashlib
import os
import stat
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import tracefix.snapshots as snapshots
from tracefix.snapshots import content_snapshot, metadata_snapshot

posix_only = pytest.mark.skipif(os.name != "posix", reason="POSIX file types and permissions")
windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows junctions")
not_root = pytest.mark.skipif(
    os.name == "posix" and os.geteuid() == 0, reason="root ignores permissions"
)
FINISH_S = 10


def finishes(fn: Callable[[], Any]) -> Any:
    """fn's result; fails (instead of hanging the suite) if it takes longer than FINISH_S."""
    result: list[Any] = []
    worker = threading.Thread(target=lambda: result.append(fn()), daemon=True)
    worker.start()
    worker.join(FINISH_S)
    assert not worker.is_alive(), f"did not finish within {FINISH_S}s"
    assert result, "raised instead of returning (see the thread's traceback above)"
    return result[0]


def listed(folder: Path, name: str) -> os.DirEntry[str]:
    """The directory entry for folder/name, with its stat cached, as the walk sees it."""
    entry = next(e for e in os.scandir(folder) if e.name == name)
    entry.stat(follow_symlinks=False)
    return entry


@posix_only
def test_q19_a_file_swapped_for_a_fifo_after_listing_does_not_hang(tmp_path: Path) -> None:
    (tmp_path / "f").write_bytes(b"x")
    entry = listed(tmp_path, "f")
    (tmp_path / "f").unlink()
    os.mkfifo(tmp_path / "f")  # opening a FIFO for reading blocks until a writer appears
    state = finishes(lambda: snapshots._content_state(entry))
    # Whatever is recorded, it must differ from the original file's state, so the swap is seen.
    assert state is not None and hashlib.sha256(b"x").hexdigest() not in state


@posix_only
def test_q19_a_file_swapped_for_a_link_after_listing_is_not_followed(tmp_path: Path) -> None:
    (tmp_path / "f").write_bytes(b"x")
    entry = listed(tmp_path, "f")
    (tmp_path / "f").unlink()
    (tmp_path / "f").symlink_to("/dev/zero")  # reading through it would never end
    state = finishes(lambda: snapshots._content_state(entry))
    assert state is not None and "unreadable" in str(state[-1])


def test_q19_a_file_that_grows_after_listing_is_read_only_up_to_the_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(snapshots, "HASH_CAP_BYTES", 10)
    monkeypatch.setattr(snapshots, "CHUNK_BYTES", 4)
    (tmp_path / "f").write_bytes(b"0123")
    entry = listed(tmp_path, "f")
    with (tmp_path / "f").open("ab") as f:
        f.write(b"456789" + b"z" * 1000)
    state = snapshots._content_state(entry)
    assert state is not None
    assert state[-1] == hashlib.sha256(b"0123456789").hexdigest()


@posix_only
@not_root
def test_q20_a_folder_that_cannot_be_entered_is_recorded_not_fatal(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "f").write_bytes(b"x")
    (tmp_path / "ok").write_bytes(b"y")
    sub.chmod(0o644)  # listable (r) but not traversable (no x): every stat inside fails
    try:
        content = content_snapshot(tmp_path)
        metadata = metadata_snapshot(tmp_path)
    finally:
        sub.chmod(0o755)
    assert content["sub/f"][0] == "unreadable" and content["ok"][0] == "file"
    assert metadata["sub/f"][0] == "unreadable" and "ok" in metadata


@posix_only
def test_q21_a_large_file_rewritten_with_its_mtime_set_back_is_seen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(snapshots, "HASH_CAP_BYTES", 10)
    big = tmp_path / "big.bin"
    big.write_bytes(b"a" * 100)
    before = content_snapshot(tmp_path)
    st = big.stat()
    # File times tick every few ms; a watched run starts many ticks after its snapshot, so the
    # rewrite does too (a fast codespace once did all three steps within one tick; NOTES).
    time.sleep(0.05)
    big.write_bytes(b"b" * 100)
    os.utime(big, ns=(st.st_atime_ns, st.st_mtime_ns))
    after = content_snapshot(tmp_path)
    assert before["big.bin"][0] == "large" and before != after


def test_q21_large_files_are_listed_where_they_are_only_size_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(snapshots, "HASH_CAP_BYTES", 10)
    (tmp_path / "big.bin").write_bytes(b"a" * 100)
    (tmp_path / "small.txt").write_bytes(b"a")
    unchecked = snapshots.size_checked_only(content_snapshot(tmp_path))
    assert unchecked == (["big.bin"] if os.name == "nt" else [])


@windows_only
def test_q22_a_junction_is_recorded_as_a_link_and_never_walked(tmp_path: Path) -> None:
    import _winapi

    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "f").write_bytes(b"x")
    _winapi.CreateJunction(str(tmp_path), str(tmp_path / "sub" / "loop"))  # points at the root
    try:
        content = finishes(lambda: content_snapshot(tmp_path))
        metadata = finishes(lambda: metadata_snapshot(tmp_path))
    finally:
        os.rmdir(tmp_path / "sub" / "loop")  # removes the junction, not its target
    assert sorted(content) == ["sub/f", "sub/loop"] and content["sub/loop"][0] == "link"
    assert sorted(metadata) == ["sub/f", "sub/loop"]


def test_special_files_are_still_recorded_by_type(tmp_path: Path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("no FIFOs here")
    os.mkfifo(tmp_path / "pipe")
    state = finishes(lambda: content_snapshot(tmp_path))["pipe"]
    assert state == ("special", stat.S_IFIFO)

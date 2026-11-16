"""Start a subprocess so that it and everything it starts can be killed together.

Windows: the process starts suspended, joins a Job Object, then resumes, so even its first
child is inside the job. POSIX: the process leads a new session (process group).
Daemons that deliberately leave the group (setsid) on POSIX are out of reach.
"""

import contextlib
import os
import signal
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import IO

KILL_WAIT_S = 10

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _CREATE_SUSPENDED = 0x00000004
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    _PROCESS_SET_QUOTA = 0x0100
    _PROCESS_TERMINATE = 0x0001
    _PROCESS_SUSPEND_RESUME = 0x0800

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_ulonglong)
            for name in ("read_ops", "write_ops", "other_ops", "read", "write", "other")
        ]

    class _BasicLimits(ctypes.Structure):
        _fields_ = [
            ("per_process_user_time", ctypes.c_int64),
            ("per_job_user_time", ctypes.c_int64),
            ("limit_flags", wintypes.DWORD),
            ("min_working_set", ctypes.c_size_t),
            ("max_working_set", ctypes.c_size_t),
            ("active_process_limit", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority_class", wintypes.DWORD),
            ("scheduling_class", wintypes.DWORD),
        ]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("basic", _BasicLimits),
            ("io", _IoCounters),
            ("process_memory_limit", ctypes.c_size_t),
            ("job_memory_limit", ctypes.c_size_t),
            ("peak_process_memory", ctypes.c_size_t),
            ("peak_job_memory", ctypes.c_size_t),
        ]

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    _k32.CreateJobObjectW.restype = wintypes.HANDLE
    _k32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
    ]  # fmt: skip
    _k32.SetInformationJobObject.restype = wintypes.BOOL
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _k32.AssignProcessToJobObject.restype = wintypes.BOOL
    _k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _k32.TerminateJobObject.restype = wintypes.BOOL
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.CloseHandle.restype = wintypes.BOOL
    _JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1

    class _Accounting(ctypes.Structure):
        _fields_ = [
            ("total_user_time", ctypes.c_int64),
            ("total_kernel_time", ctypes.c_int64),
            ("period_user_time", ctypes.c_int64),
            ("period_kernel_time", ctypes.c_int64),
            ("page_faults", wintypes.DWORD),
            ("total_processes", wintypes.DWORD),
            ("active_processes", wintypes.DWORD),
            ("terminated_processes", wintypes.DWORD),
        ]

    _k32.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p
    ]  # fmt: skip
    _k32.QueryInformationJobObject.restype = wintypes.BOOL

    def _wait_until_empty(job: int, timeout_s: float) -> None:
        """TerminateJobObject returns before processes are gone; wait until none are left, so
        their file handles are closed before anyone inspects or deletes the files."""
        info = _Accounting()
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            ok = _k32.QueryInformationJobObject(
                job, _JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION, ctypes.byref(info),
                ctypes.sizeof(info), None,
            )  # fmt: skip
            if not ok or info.active_processes == 0:
                return
            time.sleep(0.05)

    _ntdll = ctypes.WinDLL("ntdll")
    _ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
    _ntdll.NtResumeProcess.restype = ctypes.c_long

    def _new_job() -> int | None:
        job = _k32.CreateJobObjectW(None, None)
        if not job:
            return None
        limits = _ExtendedLimits()
        limits.basic.limit_flags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = _k32.SetInformationJobObject(
            job, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(limits), ctypes.sizeof(limits)
        )
        if not ok:
            _k32.CloseHandle(job)
            return None
        return int(job)

    def _start_in_job(pid: int) -> int | None:
        """Put the suspended process `pid` into a new job and resume it. Returns the job, or
        None if no job could be made (the process still runs). Raises OSError if the process
        can't be resumed, so it never sits suspended until a false timeout."""
        access = _PROCESS_SET_QUOTA | _PROCESS_TERMINATE | _PROCESS_SUSPEND_RESUME
        handle = _k32.OpenProcess(access, False, pid)
        if not handle:
            raise OSError(ctypes.get_last_error(), "cannot open the new process to resume it")
        job: int | None = None
        try:
            job = _new_job()
            if job is not None and not _k32.AssignProcessToJobObject(job, handle):
                _k32.CloseHandle(job)
                job = None
        finally:
            status = _ntdll.NtResumeProcess(handle)  # always resume, job or not
            _k32.CloseHandle(handle)
        if status != 0:
            if job is not None:
                _k32.CloseHandle(job)  # kill-on-close ends the process
            raise OSError(f"cannot resume the new process (NTSTATUS {status & 0xFFFFFFFF:#x})")
        return job


class ProcessTree:
    """A running command plus every process it starts."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        stdout: IO[bytes],
    ) -> None:
        self._job: int | None = None
        if sys.platform == "win32":
            self.proc = subprocess.Popen(
                command,
                cwd=cwd,
                env=dict(env),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | _CREATE_SUSPENDED,
            )
            try:
                self._job = _start_in_job(self.proc.pid)
            except OSError:
                self.proc.kill()
                self.proc.wait(timeout=KILL_WAIT_S)
                raise
        else:
            self.proc = subprocess.Popen(
                command,
                cwd=cwd,
                env=dict(env),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

    def wait(self, timeout_s: float) -> int | None:
        """The exit code, or None if the main process is still running after timeout_s."""
        try:
            return self.proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return None

    def kill_all(self) -> None:
        """Kill the main process and every descendant still running. Safe to call twice."""
        if sys.platform == "win32":
            if self._job is not None:
                _k32.TerminateJobObject(self._job, 1)
                _wait_until_empty(self._job, KILL_WAIT_S)
                _k32.CloseHandle(self._job)
                self._job = None
            else:  # No job (creation failed): best effort by parent process id.
                with contextlib.suppress(OSError, subprocess.SubprocessError):
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(self.proc.pid)],
                        capture_output=True,
                        timeout=KILL_WAIT_S,
                        check=False,
                    )
        else:
            # After a normal exit pytest is already reaped; its group lives on while any member
            # does. If the group is empty and the id was reused in between, this could hit an
            # unrelated group: a tiny window, accepted.
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(self.proc.pid, signal.SIGKILL)
        with contextlib.suppress(OSError):
            self.proc.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            self.proc.wait(timeout=KILL_WAIT_S)

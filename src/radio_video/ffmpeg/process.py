from __future__ import annotations

import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

# Keeps console windows from flashing when the GUI starts FFmpeg processes on Windows.
if sys.platform == "win32":
    CREATION_FLAGS = subprocess.CREATE_NO_WINDOW
else:
    CREATION_FLAGS = 0


class ProcessGroup:
    """Ties a process and every process it starts to one lifetime.

    Package managers such as Chocolatey and Scoop install ``ffmpeg.exe`` as a shim that starts
    the real executable as a child process, so killing the direct child is not enough. On
    Windows the process is assigned to a Job Object: children started later join the job
    automatically, ``terminate()`` kills all of them, and the job kills any survivors when it
    is closed, including when this application exits unexpectedly. On other platforms this
    class does nothing and callers kill the direct child themselves.
    """

    def __init__(self) -> None:
        self._handle: int | None = None

    @property
    def attached(self) -> bool:
        return self._handle is not None

    def attach(self, pid: int) -> bool:
        if pid <= 0 or self._handle is not None:
            return False
        if sys.platform == "win32":
            handle = _windows.create_kill_on_close_job()
            if handle is None:
                return False
            if not _windows.assign_process(handle, pid):
                _windows.close_handle(handle)
                return False
            self._handle = handle
            return True
        return False

    def terminate(self) -> None:
        if sys.platform == "win32" and self._handle is not None:
            _windows.terminate_job(self._handle)

    def close(self) -> None:
        if sys.platform == "win32" and self._handle is not None:
            _windows.close_handle(self._handle)
        self._handle = None


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimitInformation),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class _Windows:
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
        JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
        PROCESS_SET_QUOTA = 0x0100
        PROCESS_TERMINATE = 0x0001

        def __init__(self) -> None:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self._create_job = kernel32.CreateJobObjectW
            self._create_job.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
            self._create_job.restype = wintypes.HANDLE
            self._set_info = kernel32.SetInformationJobObject
            self._set_info.argtypes = [
                wintypes.HANDLE,
                ctypes.c_int,
                wintypes.LPVOID,
                wintypes.DWORD,
            ]
            self._set_info.restype = wintypes.BOOL
            self._open_process = kernel32.OpenProcess
            self._open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            self._open_process.restype = wintypes.HANDLE
            self._assign = kernel32.AssignProcessToJobObject
            self._assign.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            self._assign.restype = wintypes.BOOL
            self._terminate = kernel32.TerminateJobObject
            self._terminate.argtypes = [wintypes.HANDLE, wintypes.UINT]
            self._terminate.restype = wintypes.BOOL
            self._close = kernel32.CloseHandle
            self._close.argtypes = [wintypes.HANDLE]
            self._close.restype = wintypes.BOOL

        def create_kill_on_close_job(self) -> int | None:
            handle = self._create_job(None, None)
            if not handle:
                logger.warning("CreateJobObject failed: %d", ctypes.get_last_error())
                return None
            info = _ExtendedLimitInformation()
            info.BasicLimitInformation.LimitFlags = self.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            ok = self._set_info(
                handle,
                self.JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
            if not ok:
                logger.warning("SetInformationJobObject failed: %d", ctypes.get_last_error())
                self.close_handle(handle)
                return None
            return int(handle)

        def assign_process(self, job: int, pid: int) -> bool:
            process = self._open_process(
                self.PROCESS_SET_QUOTA | self.PROCESS_TERMINATE, False, pid
            )
            if not process:
                logger.warning("OpenProcess(%d) failed: %d", pid, ctypes.get_last_error())
                return False
            try:
                if not self._assign(job, process):
                    logger.warning(
                        "AssignProcessToJobObject(%d) failed: %d", pid, ctypes.get_last_error()
                    )
                    return False
                return True
            finally:
                self._close(process)

        def terminate_job(self, job: int) -> None:
            if not self._terminate(job, 1):
                logger.warning("TerminateJobObject failed: %d", ctypes.get_last_error())

        def close_handle(self, handle: int) -> None:
            self._close(handle)

    _windows = _Windows()

"""Job Objects Windows via ctypes : lancement suspendu, assignation, reprise (règle 3).

Seul module de `src/deskgate` (avec `instance`) qui importe `ctypes`, et seul à importer
`subprocess`. `JOB_OBJECT_LIMIT_BREAKAWAY_OK` n'est volontairement jamais posé : un
plugin ne doit pas pouvoir sortir du Job.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
from collections.abc import Mapping, Sequence
from ctypes import wintypes

JobObjectBasicAccountingInformation = 1
JobObjectExtendedLimitInformation = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x200
CREATE_SUSPENDED = 0x00000004
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
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


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", wintypes.LARGE_INTEGER),
        ("TotalKernelTime", wintypes.LARGE_INTEGER),
        ("ThisPeriodTotalUserTime", wintypes.LARGE_INTEGER),
        ("ThisPeriodTotalKernelTime", wintypes.LARGE_INTEGER),
        ("TotalPageFaultCount", wintypes.DWORD),
        ("TotalProcesses", wintypes.DWORD),
        ("ActiveProcesses", wintypes.DWORD),
        ("TotalTerminatedProcesses", wintypes.DWORD),
    ]


k32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")

k32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
k32.CreateJobObjectW.restype = wintypes.HANDLE
k32.SetInformationJobObject.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    wintypes.LPVOID,
    wintypes.DWORD,
]
k32.SetInformationJobObject.restype = wintypes.BOOL
k32.QueryInformationJobObject.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
k32.QueryInformationJobObject.restype = wintypes.BOOL
k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
k32.AssignProcessToJobObject.restype = wintypes.BOOL
k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
k32.TerminateJobObject.restype = wintypes.BOOL
k32.CloseHandle.argtypes = [wintypes.HANDLE]
k32.CloseHandle.restype = wintypes.BOOL
ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
ntdll.NtResumeProcess.restype = wintypes.LONG


class JobHandle:
    """Poignée d'un Job Object ; `close` est idempotent."""

    def __init__(self, handle: int) -> None:
        self._handle: int | None = handle

    @property
    def handle(self) -> int:
        if self._handle is None:
            raise ValueError("Job Object déjà fermé")
        return self._handle

    def terminate(self, exit_code: int = 1) -> None:
        """Tue tout l'arbre du Job ; sans effet si la poignée est fermée."""
        if self._handle is None:
            return
        if not k32.TerminateJobObject(self._handle, exit_code):
            raise ctypes.WinError(ctypes.get_last_error())

    def active_processes(self) -> int:
        info = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
        if not k32.QueryInformationJobObject(
            self.handle,
            JobObjectBasicAccountingInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
            None,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(info.ActiveProcesses)

    def close(self) -> None:
        if self._handle is None:
            return
        handle, self._handle = self._handle, None
        k32.CloseHandle(handle)


def create_job(memory_mb: int | None = None) -> JobHandle:
    """Crée un Job KILL_ON_JOB_CLOSE (jamais BREAKAWAY_OK), avec plafond mémoire optionnel."""
    raw = k32.CreateJobObjectW(None, None)
    if not raw:
        raise ctypes.WinError(ctypes.get_last_error())
    job = JobHandle(int(raw))
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if memory_mb is not None:
        flags |= JOB_OBJECT_LIMIT_JOB_MEMORY
        info.JobMemoryLimit = memory_mb * 1024 * 1024
    info.BasicLimitInformation.LimitFlags = flags
    if not k32.SetInformationJobObject(
        job.handle, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)
    ):
        err = ctypes.WinError(ctypes.get_last_error())
        job.close()
        raise err
    return job


def spawn_in_job(
    job: JobHandle,
    argv: Sequence[str],
    *,
    cwd: str,
    log_path: str,
    env: Mapping[str, str],
) -> subprocess.Popen[bytes]:
    """Lance `argv` suspendu, l'assigne au Job, puis le reprend. Sans shell, sans tube."""
    if not argv or not os.path.isabs(argv[0]) or not os.path.isabs(cwd):
        raise ValueError("chemin absolu attendu")
    with open(log_path, "ab") as log:  # fermé juste après Popen : la poignée est dupliquée
        p = subprocess.Popen(  # noqa: S603  argv en liste, sans shell (règle 2)
            list(argv),
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_SUSPENDED | CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
    # Attribut privé mais présent en 3.11 comme en 3.14 (pas d'API publique pour la poignée).
    handle = wintypes.HANDLE(int(getattr(p, "_handle")))  # noqa: B009
    try:
        if not k32.AssignProcessToJobObject(job.handle, handle):
            raise ctypes.WinError(ctypes.get_last_error())
        if ntdll.NtResumeProcess(handle) != 0:
            raise OSError("NtResumeProcess a échoué")
    except BaseException:
        p.kill()
        p.wait()
        raise
    return p

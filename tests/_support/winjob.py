"""Aide de test : Job Object Windows via ctypes (spike D-13(c)).

Le module définitif `jobobject` arrive en phase 2 ; celui-ci ne sert qu'aux tests.
"""

from __future__ import annotations

import ctypes
import subprocess
from ctypes import wintypes
from typing import Any

JobObjectExtendedLimitInformation = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
CREATE_SUSPENDED = 0x00000004
CREATE_NO_WINDOW = 0x08000000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259


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
k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
k32.AssignProcessToJobObject.restype = wintypes.BOOL
k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
k32.TerminateJobObject.restype = wintypes.BOOL
k32.CloseHandle.argtypes = [wintypes.HANDLE]
k32.CloseHandle.restype = wintypes.BOOL
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.OpenProcess.restype = wintypes.HANDLE
k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
k32.GetExitCodeProcess.restype = wintypes.BOOL
ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
ntdll.NtResumeProcess.restype = wintypes.LONG


def create_kill_on_close_job() -> int:
    """Crée un Job Object qui tue ses processus à la fermeture de sa dernière poignée."""
    job = k32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not k32.SetInformationJobObject(
        job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(job)


def spawn_in_job(job: int, argv: list[str], **kw: Any) -> subprocess.Popen[Any]:
    """Lance `argv` suspendu, l'assigne au job, puis le reprend (jamais `shell=True`)."""
    p = subprocess.Popen(argv, creationflags=CREATE_SUSPENDED | CREATE_NO_WINDOW, **kw)
    handle = wintypes.HANDLE(int(p._handle))  # type: ignore[attr-defined]
    if not k32.AssignProcessToJobObject(job, handle):
        raise ctypes.WinError(ctypes.get_last_error())
    if ntdll.NtResumeProcess(handle) != 0:
        raise OSError("NtResumeProcess a échoué")
    return p


def is_alive(pid: int) -> bool:
    """Vrai si le processus `pid` existe et n'est pas terminé."""
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False
    try:
        code = wintypes.DWORD()
        if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE
    finally:
        k32.CloseHandle(h)

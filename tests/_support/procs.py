"""Aides de test : vivacité d'un processus."""

from __future__ import annotations

import time

import psutil


def is_alive(pid: int) -> bool:
    if not psutil.pid_exists(pid):
        return False
    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def wait_dead(pid: int, timeout: float = 5.0) -> bool:
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        if not is_alive(pid):
            return True
        time.sleep(0.1)
    return not is_alive(pid)

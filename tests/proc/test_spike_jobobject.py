"""Spike D-13(c) : un petit-enfant orphelin meurt avec son Job Object."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.proc,
    pytest.mark.skipif(sys.platform != "win32", reason="Job Object Windows"),
]

PARENT = """\
import os, subprocess, sys
p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
with open(sys.argv[1], "w") as f:
    f.write(str(p.pid))
os._exit(0)
"""


def _wait_dead(pid: int, delai: float = 5.0) -> bool:
    from _support.winjob import is_alive

    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if not is_alive(pid):
            return True
        time.sleep(0.1)
    return not is_alive(pid)


def _scenario(tmp_path: Path, tuer: str) -> None:
    from _support.winjob import (
        create_kill_on_close_job,
        is_alive,
        k32,
        spawn_in_job,
    )

    parent = tmp_path / "parent.py"
    parent.write_text(PARENT, encoding="utf-8")
    pidfile = tmp_path / "pid.txt"
    job = create_kill_on_close_job()
    pid = 0
    closed = False
    try:
        p = spawn_in_job(job, [sys.executable, str(parent), str(pidfile)])
        p.wait(30)
        pid = int(pidfile.read_text(encoding="utf-8"))
        assert is_alive(pid)  # l'orphelin survit à son parent
        if tuer == "terminate":
            assert k32.TerminateJobObject(job, 1)
        else:
            assert k32.CloseHandle(job)
            closed = True
        assert _wait_dead(pid)
    finally:
        if pid and is_alive(pid):
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        if not closed:
            k32.CloseHandle(job)


@pytest.mark.timeout(90)
def test_terminate_job_tue_orphelin(tmp_path: Path) -> None:
    _scenario(tmp_path, "terminate")


@pytest.mark.timeout(90)
def test_close_handle_tue_orphelin(tmp_path: Path) -> None:
    _scenario(tmp_path, "close")

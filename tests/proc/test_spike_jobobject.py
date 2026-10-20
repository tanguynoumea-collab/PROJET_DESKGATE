"""Spike D-13(c) : un petit-enfant orphelin meurt avec son Job Object."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from _support.procs import is_alive, wait_dead
from deskgate.core.env import build_env
from deskgate.jobobject import create_job, spawn_in_job

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


def _scenario(tmp_path: Path, tuer: str) -> None:
    parent = tmp_path / "parent.py"
    parent.write_text(PARENT, encoding="utf-8")
    pidfile = tmp_path / "pid.txt"
    job = create_job()
    pid = 0
    try:
        p = spawn_in_job(
            job,
            [sys.executable, str(parent), str(pidfile)],
            cwd=str(tmp_path),
            log_path=str(tmp_path / "job.log"),
            env=build_env(os.environ),
        )
        p.wait(30)
        pid = int(pidfile.read_text(encoding="utf-8"))
        assert is_alive(pid)  # l'orphelin survit à son parent
        if tuer == "terminate":
            job.terminate()
        else:
            job.close()
        assert wait_dead(pid)
    finally:
        if pid and is_alive(pid):
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        job.close()


@pytest.mark.timeout(90)
def test_terminate_job_tue_orphelin(tmp_path: Path) -> None:
    _scenario(tmp_path, "terminate")


@pytest.mark.timeout(90)
def test_close_handle_tue_orphelin(tmp_path: Path) -> None:
    _scenario(tmp_path, "close")

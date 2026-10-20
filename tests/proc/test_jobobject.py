"""Job Object de production avec de vrais sous-processus."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from _support.procs import is_alive, wait_dead
from deskgate.core.env import build_env
from deskgate.jobobject import JobHandle, create_job, spawn_in_job

pytestmark = [
    pytest.mark.proc,
    pytest.mark.skipif(sys.platform != "win32", reason="Job Object Windows"),
    pytest.mark.timeout(60),
]


def _run(job: JobHandle, tmp_path: Path, code: str) -> subprocess.Popen[bytes]:
    script = tmp_path / "enfant.py"
    script.write_text(code, encoding="utf-8")
    return spawn_in_job(
        job,
        [sys.executable, str(script), str(tmp_path / "pid.txt")],
        cwd=str(tmp_path),
        log_path=str(tmp_path / "job.log"),
        env=build_env(os.environ),
    )


def _vide(job: JobHandle, delai: float = 5.0) -> bool:
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if job.active_processes() == 0:
            return True
        time.sleep(0.05)
    return job.active_processes() == 0


def test_sortie_utf8_dans_le_log(tmp_path: Path) -> None:
    job = create_job()
    try:
        p = _run(job, tmp_path, "print('é')\n")
        assert p.wait(30) == 0
        assert "é" in (tmp_path / "job.log").read_text(encoding="utf-8")
        assert _vide(job)
    finally:
        job.close()


def test_env_liste_blanche(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_X", "s")
    job = create_job()
    try:
        code = "import os\nprint(os.environ.get('SECRET_X'), os.environ.get('PYTHONUTF8'))\n"
        p = _run(job, tmp_path, code)
        assert p.wait(30) == 0
        assert (tmp_path / "job.log").read_text(encoding="utf-8").strip() == "None 1"
    finally:
        job.close()


PARENT = """\
import os, subprocess, sys
p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
with open(sys.argv[1], "w") as f:
    f.write(str(p.pid))
os._exit(0)
"""


def test_terminate_tue_le_petit_enfant(tmp_path: Path) -> None:
    job = create_job()
    pid = 0
    try:
        p = _run(job, tmp_path, PARENT)
        p.wait(30)
        pid = int((tmp_path / "pid.txt").read_text(encoding="utf-8"))
        assert is_alive(pid)
        assert job.active_processes() > 0
        job.terminate()
        assert wait_dead(pid)
        assert _vide(job)
        assert p.wait(5) == 0  # le parent était déjà sorti
    finally:
        job.close()
        if pid and is_alive(pid):
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)


def test_plafond_memoire(tmp_path: Path) -> None:
    job = create_job(memory_mb=100)
    try:
        code = "b = bytearray(400 * 1024 * 1024)\nb[::4096] = bytes(len(b[::4096]))\n"
        p = _run(job, tmp_path, code)
        assert p.wait(30) != 0
    finally:
        job.close()


def test_executable_inexistant(tmp_path: Path) -> None:
    job = create_job()
    with pytest.raises(OSError):
        spawn_in_job(
            job,
            [str(tmp_path / "absent.exe")],
            cwd=str(tmp_path),
            log_path=str(tmp_path / "job.log"),
            env=build_env(os.environ),
        )
    job.close()
    job.close()


def test_chemin_relatif_refuse(tmp_path: Path) -> None:
    job = create_job()
    try:
        with pytest.raises(ValueError, match="absolu"):
            spawn_in_job(job, ["python"], cwd=str(tmp_path), log_path=str(tmp_path / "l"), env={})
    finally:
        job.close()

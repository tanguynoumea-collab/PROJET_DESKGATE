"""Journal fichier du runner : ouvert après le mutex, masqué, présent sous pythonw."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest
from tests.e2e.conftest import (
    CALLBACK_URL,
    FAKE_CAPS,
    api,
    kill_tree,
    runner_env,
    start_runner,
    wait_health,
    wait_status,
    write_config,
)

from deskgate.locations import log_path

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows seul"),
]

MARQUEUR = "démarré (pid"


def _fermer(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is None:
        kill_tree(proc)
    for stream in (proc.stdout, proc.stderr):
        if stream is not None:
            stream.close()


def _journal(data_home: Path) -> str:
    return log_path(data_home).read_text(encoding="utf-8", errors="replace")


@pytest.mark.timeout(60)
def test_journal_cree_et_signature_masquee(
    data_home: Path, instance_name: str, free_port: int
) -> None:
    write_config(data_home, free_port, capabilities=FAKE_CAPS)
    proc = start_runner(runner_env(data_home, instance_name))
    try:
        wait_health(free_port, proc)
        status, body = api(
            free_port,
            "POST",
            "/jobs",
            {"capability": "demo.fail", "params": {}, "callback": {"url": CALLBACK_URL}},
        )
        assert status == 202, body
        wait_status(free_port, str(body["job_id"]), {"failed"})
        time.sleep(2)  # laisse le sender tenter le rappel vers le port 9
        texte = _journal(data_home)
        assert MARQUEUR in texte
        assert "Écoute sur http://127.0.0.1:" in texte
        assert "E2E-SECRET-SIG" not in texte
    finally:
        _fermer(proc)


@pytest.mark.timeout(60)
def test_second_runner_n_ecrit_pas(data_home: Path, instance_name: str, free_port: int) -> None:
    write_config(data_home, free_port, capabilities=FAKE_CAPS)
    env = runner_env(data_home, instance_name)
    premier = start_runner(env)
    second: subprocess.Popen[bytes] | None = None
    try:
        wait_health(free_port, premier)
        second = start_runner(env)
        assert second.wait(15) == 3
        assert _journal(data_home).count(MARQUEUR) == 1
    finally:
        if second is not None:
            _fermer(second)
        _fermer(premier)


@pytest.mark.timeout(60)
def test_runner_sous_pythonw(data_home: Path, instance_name: str, free_port: int) -> None:
    pyw = Path(sys.executable).with_name("pythonw.exe")
    if not pyw.exists():
        pytest.fail(f"pythonw.exe introuvable : {pyw}")
    write_config(data_home, free_port, capabilities=FAKE_CAPS)
    proc = subprocess.Popen(
        [str(pyw), "-m", "deskgate", "serve"],
        env=runner_env(data_home, instance_name),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    try:
        wait_health(free_port, proc)
        assert MARQUEUR in _journal(data_home)
    finally:
        _fermer(proc)

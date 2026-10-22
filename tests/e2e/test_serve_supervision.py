"""Supervision en processus réel : recréation de l'engine et abandon en code 6 (ARC-001)."""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from tests.e2e.conftest import (
    FAKE_CAPS,
    api,
    kill_tree,
    runner_env,
    wait_health,
    wait_status,
    write_config,
)

from _support.fake_n8n import OK, FakeN8n
from deskgate.locations import log_path, startup_log_path

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows seul"),
]

PILOTE = Path(__file__).resolve().parents[1] / "_support" / "serve_with_fault.py"


@contextlib.contextmanager
def _pilote(
    data_home: Path, instance_name: str, port: int, mode: str
) -> Iterator[subprocess.Popen[bytes]]:
    write_config(data_home, port, capabilities=FAKE_CAPS, callback={"max_backoff_s": 2})
    proc = subprocess.Popen(
        [sys.executable, str(PILOTE)],
        env={**runner_env(data_home, instance_name), "DESKGATE_TEST_FAULT": mode},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    try:
        yield proc
    finally:
        if proc.poll() is None:
            kill_tree(proc)
        for stream in (proc.stdout, proc.stderr):
            if stream is not None:
                stream.close()


@pytest.mark.timeout(90)
def test_engine_mort_recree_et_rappel_interrupted(
    data_home: Path, instance_name: str, free_port: int, fake_n8n: FakeN8n
) -> None:
    fake_n8n.default = OK
    with _pilote(data_home, instance_name, free_port, "running:1") as proc:
        wait_health(free_port, proc)
        status, resp = api(
            free_port,
            "POST",
            "/jobs",
            {
                "capability": "demo.sleep",
                "params": {"n": 60},
                "callback": {"url": fake_n8n.url()},
            },
        )
        assert status == 202, resp
        recues = fake_n8n.wait_requests(1, timeout=20)
        corps = json.loads(recues[0].body)
        assert corps["status"] == "interrupted"
        assert corps["error"]["code"] == "runner_restarted"
        assert proc.poll() is None
        status, resp = api(
            free_port,
            "POST",
            "/jobs",
            {
                "capability": "demo.sleep",
                "params": {"n": 0.05},
                "callback": {"url": fake_n8n.url()},
            },
        )
        assert status == 202, resp
        wait_status(free_port, str(resp["job_id"]), {"succeeded"})
        texte = log_path(data_home).read_text(encoding="utf-8", errors="replace")
        assert "Thread engine recréé" in texte


@pytest.mark.timeout(90)
def test_pannes_repetees_sortie_code_6(data_home: Path, instance_name: str, free_port: int) -> None:
    with _pilote(data_home, instance_name, free_port, "always") as proc:
        wait_health(free_port, proc)
        assert proc.wait(timeout=45) == 6
        texte = log_path(data_home).read_text(encoding="utf-8", errors="replace")
        assert "abandon" in texte
        assert "engine" in texte
        assert "code 6" in startup_log_path(data_home).read_text(encoding="utf-8", errors="replace")

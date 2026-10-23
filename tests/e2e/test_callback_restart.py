"""Rappel durable à travers un arrêt brutal du runner (CB-01, CB-02, CB-03)."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from tests.e2e.conftest import (
    FAKE_CAPS,
    api,
    kill_tree,
    runner_env,
    start_runner,
    wait_callback_state,
    wait_health,
    wait_status,
    write_config,
)

from _support.fake_n8n import FINISHED, OK, SERVER_ERROR, SIG, FakeN8n, hang

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows seul"),
]

CLES = {"job_id", "capability", "status", "duration_s", "summary", "data", "artifacts", "error"}


def _close(p: subprocess.Popen[bytes]) -> None:
    for stream in (p.stdout, p.stderr):
        if stream is not None:
            stream.close()


@contextmanager
def _runners(
    data_home: Path, instance_name: str, port: int
) -> Iterator[list[subprocess.Popen[bytes]]]:
    """Lance un premier runner ; la liste reçoit les suivants. Tout est tué en sortie."""
    write_config(data_home, port, capabilities=FAKE_CAPS, callback={"max_backoff_s": 2})
    env = runner_env(data_home, instance_name)
    procs: list[subprocess.Popen[bytes]] = []
    try:
        procs.append(start_runner(env))
        wait_health(port, procs[0])
        yield procs
    finally:
        for p in procs:
            if p.poll() is None:
                kill_tree(p)
            _close(p)


def _restart(procs: list[subprocess.Popen[bytes]], data_home: Path, name: str, port: int) -> None:
    kill_tree(procs[-1])
    procs.append(start_runner(runner_env(data_home, name)))
    wait_health(port, procs[-1])


def _submit(port: int, fake: FakeN8n, params: dict[str, object]) -> str:
    status, resp = api(
        port,
        "POST",
        "/jobs",
        {"capability": "demo.sleep", "params": params, "callback": {"url": fake.url()}},
    )
    assert status == 202, resp
    return str(resp["job_id"])


@pytest.mark.timeout(90)
def test_reprise_apres_redemarrage(
    data_home: Path, instance_name: str, free_port: int, fake_n8n: FakeN8n
) -> None:
    fake_n8n.default = SERVER_ERROR
    with _runners(data_home, instance_name, free_port) as procs:
        job_id = _submit(free_port, fake_n8n, {"n": 0.05})
        fake_n8n.wait_requests(1, timeout=20)
        kill_tree(procs[0])
        fake_n8n.default = OK
        procs.append(start_runner(runner_env(data_home, instance_name)))
        wait_health(free_port, procs[-1])
        row = wait_callback_state(data_home, job_id, {"delivered"}, timeout=40)
        assert row["attempts"] >= 2
        for rec in list(fake_n8n.requests):
            assert rec.requestline == f"POST /webhook-waiting/42?signature={SIG} HTTP/1.1"


@pytest.mark.timeout(90)
def test_envoi_interrompu(
    data_home: Path, instance_name: str, free_port: int, fake_n8n: FakeN8n
) -> None:
    fake_n8n.script(hang(60), FINISHED)
    fake_n8n.default = OK
    with _runners(data_home, instance_name, free_port) as procs:
        job_id = _submit(free_port, fake_n8n, {"n": 0.05})
        fake_n8n.wait_requests(1, timeout=20)
        kill_tree(procs[0])
        conn = sqlite3.connect(data_home / "deskgate.db", timeout=5)
        try:
            conn.row_factory = sqlite3.Row
            ligne = conn.execute("SELECT * FROM callbacks WHERE job_id=?", (job_id,)).fetchone()
        finally:
            conn.close()
        assert ligne["attempts"] == 1
        assert ligne["maybe_delivered"] == 1
        procs.append(start_runner(runner_env(data_home, instance_name)))
        wait_health(free_port, procs[-1])
        row = wait_callback_state(data_home, job_id, {"delivered_duplicate"}, timeout=40)
        assert row["attempts"] == 2


@pytest.mark.timeout(90)
def test_rappel_interrupted(
    data_home: Path, instance_name: str, free_port: int, fake_n8n: FakeN8n
) -> None:
    fake_n8n.default = OK
    with _runners(data_home, instance_name, free_port) as procs:
        job_id = _submit(free_port, fake_n8n, {"n": 60})
        wait_status(free_port, job_id, {"running"})
        _restart(procs, data_home, instance_name, free_port)
        recues = fake_n8n.wait_requests(1, timeout=20)
        corps = json.loads(recues[0].body)
        assert set(corps) == CLES
        assert corps["status"] == "interrupted"
        assert corps["error"]["code"] == "runner_restarted"
        wait_callback_state(data_home, job_id, {"delivered"})
        conn = sqlite3.connect(data_home / "deskgate.db", timeout=5)
        try:
            url = conn.execute("SELECT callback_url FROM jobs WHERE id=?", (job_id,)).fetchone()[0]
        finally:
            conn.close()
        assert url == ""

"""Rappel réel vers un faux n8n par HTTP (CB-01, CB-03)."""

from __future__ import annotations

import json
import sqlite3
import sys
import time

import pytest
from tests.e2e.conftest import Runner, api, wait_callback_state, wait_status

from _support.fake_n8n import OK, RUNNING, SIG, FakeN8n

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows seul"),
]

CLES = {"job_id", "capability", "status", "duration_s", "summary", "artifacts", "error"}


def _submit(
    r: Runner, fake: FakeN8n, capability: str, params: dict[str, object], **extra: object
) -> str:
    body: dict[str, object] = {
        "capability": capability,
        "params": params,
        "callback": {"url": fake.url()},
        **extra,
    }
    status, resp = api(r.port, "POST", "/jobs", body)
    assert status == 202, resp
    return str(resp["job_id"])


@pytest.mark.timeout(90)
def test_tache_courte_rappel_livre(cb_runner: Runner, fake_n8n: FakeN8n) -> None:
    job_id = _submit(cb_runner, fake_n8n, "demo.sleep", {"n": 0.05})
    recues = fake_n8n.wait_requests(1, timeout=15)
    assert recues[0].requestline == f"POST /webhook-waiting/42?signature={SIG} HTTP/1.1"
    corps = json.loads(recues[0].body)
    assert set(corps) == CLES
    assert corps["status"] == "succeeded"
    assert corps["job_id"] == job_id
    assert isinstance(corps["duration_s"], float)
    wait_callback_state(cb_runner.home, job_id, {"delivered"})
    conn = sqlite3.connect(cb_runner.home / "deskgate.db")
    try:
        url = conn.execute("SELECT callback_url FROM jobs WHERE id=?", (job_id,)).fetchone()[0]
    finally:
        conn.close()
    assert url == ""


@pytest.mark.timeout(90)
@pytest.mark.parametrize("cas", ["failed", "timeout", "cancelled"])
def test_statuts_terminaux(cb_runner: Runner, fake_n8n: FakeN8n, cas: str) -> None:
    if cas == "failed":
        job_id = _submit(cb_runner, fake_n8n, "demo.fail", {})
    elif cas == "timeout":
        job_id = _submit(cb_runner, fake_n8n, "demo.sleep", {"n": 30}, timeout=1)
    else:
        job_id = _submit(cb_runner, fake_n8n, "demo.sleep", {"n": 30})
        wait_status(cb_runner.port, job_id, {"running"})
        api(cb_runner.port, "POST", f"/jobs/{job_id}/cancel")
    recues = fake_n8n.wait_requests(1, timeout=30)
    corps = json.loads(recues[0].body)
    assert corps["status"] == cas
    assert corps["job_id"] == job_id
    assert corps["error"] is not None
    assert corps["error"]["code"]
    wait_callback_state(cb_runner.home, job_id, {"delivered"})


@pytest.mark.timeout(90)
def test_reessai_court_puis_livre(cb_runner: Runner, fake_n8n: FakeN8n) -> None:
    fake_n8n.script(RUNNING)
    fake_n8n.default = OK
    debut = time.monotonic()
    job_id = _submit(cb_runner, fake_n8n, "demo.sleep", {"n": 0.05})
    fake_n8n.wait_requests(2, timeout=20)
    assert time.monotonic() - debut < 20
    ligne = wait_callback_state(cb_runner.home, job_id, {"delivered"})
    assert ligne["attempts"] == 2

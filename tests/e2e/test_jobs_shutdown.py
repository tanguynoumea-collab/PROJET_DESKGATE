"""Arrêt propre par CTRL_BREAK : le lifespan arrête l'engine (Pitfall 1)."""

from __future__ import annotations

import signal
import sys

import pytest
from tests._support.procs import wait_dead
from tests.e2e.conftest import (
    CALLBACK_URL,
    Runner,
    api,
    kill_tree,
    start_runner,
    wait_health,
    wait_status,
)
from tests.e2e.test_jobs_restart import wait_pids

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows seul"),
]


@pytest.mark.timeout(90)
def test_ctrl_break_arrete_engine_et_plugin(jobs_runner: Runner) -> None:
    status, resp = api(
        jobs_runner.port,
        "POST",
        "/jobs",
        {
            "capability": "demo.spawn_orphan",
            "params": {"sleep": 120},
            "callback": {"url": CALLBACK_URL},
        },
    )
    assert status == 202
    job_id = resp["job_id"]
    wait_status(jobs_runner.port, job_id, {"running"})
    orphan, plugin = wait_pids(jobs_runner.home.parent / "bim" / "travail" / job_id)

    proc = jobs_runner.proc
    proc.send_signal(signal.CTRL_BREAK_EVENT)
    proc.wait(20)
    assert proc.stderr is not None
    assert "Engine arrêté." in proc.stderr.read().decode("utf-8", "replace")
    assert wait_dead(plugin, 10)
    assert wait_dead(orphan, 10)

    second = start_runner(jobs_runner.env)
    try:
        wait_health(jobs_runner.port, second)
        job = wait_status(jobs_runner.port, job_id, {"interrupted"}, timeout=10)
        assert job["error"]["code"] == "runner_restarted"
    finally:
        kill_tree(second)
        for stream in (second.stdout, second.stderr):
            if stream is not None:
                stream.close()

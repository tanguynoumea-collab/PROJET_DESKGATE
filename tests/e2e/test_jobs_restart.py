"""Test obligatoire : running -> interrupted au redémarrage après taskkill /F /T (JOB-06)."""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

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

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows seul"),
]


def wait_pids(work_dir: Path, timeout: float = 15.0) -> tuple[int, int]:
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        o, p = work_dir / "orphan.pid", work_dir / "plugin.pid"
        if o.is_file() and p.is_file():
            try:
                return int(o.read_text()), int(p.read_text())
            except ValueError:
                pass
        time.sleep(0.1)
    pytest.fail("PID du plugin et de l'orphelin non écrits")


@pytest.mark.timeout(90)
def test_running_devient_interrupted_apres_taskkill(jobs_runner: Runner) -> None:
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
    work_dir = jobs_runner.home.parent / "bim" / "travail" / job_id
    orphan, plugin = wait_pids(work_dir)

    kill_tree(jobs_runner.proc)
    assert wait_dead(plugin, 10)
    assert wait_dead(orphan, 10)

    second = start_runner(jobs_runner.env)
    try:
        wait_health(jobs_runner.port, second)
        job = wait_status(jobs_runner.port, job_id, {"interrupted"}, timeout=10)
        assert job["error"]["code"] == "runner_restarted"
        assert job["finished_at"] is not None

        conn = sqlite3.connect(jobs_runner.home / "deskgate.db")
        try:
            rows = conn.execute("SELECT state FROM callbacks WHERE job_id=?", (job_id,)).fetchall()
            assert rows == [("pending",)]
            audit = conn.execute(
                "SELECT count(*) FROM audit WHERE event=?", ("job.interrupted",)
            ).fetchone()
            assert audit[0] >= 1
        finally:
            conn.close()
        assert work_dir.is_dir()

        status, resp = api(
            jobs_runner.port,
            "POST",
            "/jobs",
            {"capability": "demo.sleep", "params": {"n": 0.2}, "callback": {"url": CALLBACK_URL}},
        )
        assert status == 202
        wait_status(jobs_runner.port, resp["job_id"], {"succeeded"})
    finally:
        kill_tree(second)
        for stream in (second.stdout, second.stderr):
            if stream is not None:
                stream.close()

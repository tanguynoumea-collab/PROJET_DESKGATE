"""Preuve réelle sous plafond du Job Object : `memory_limit` classé par l'engine."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

import deskgate_sdk.run as sdk_run
from _support.jobs import get, make_config, run_until_terminal, submit
from deskgate import store
from deskgate.core.env import build_env
from deskgate.engine import Engine
from deskgate.jobobject import create_job, spawn_in_job

pytestmark = [
    pytest.mark.proc,
    pytest.mark.skipif(sys.platform != "win32", reason="Job Object Windows"),
    pytest.mark.timeout(60),
]

CAPS: dict[str, dict[str, object]] = {
    "demo.hog": {"entry": "deskgate_fakes:hog", "memory_mb": 200},
}


def _run(tmp_path: Path, params: dict[str, object]) -> store.JobRow:
    cfg = make_config(tmp_path, CAPS)
    db = tmp_path / "home" / "deskgate.db"
    store.open_db(db).close()
    engine = Engine(
        db_path=db,
        config=cfg,
        worker_script=Path(sdk_run.__file__).resolve(),
        poll=0.05,
        grace=1.0,
    )
    try:
        job_id = submit(db, cfg, "demo.hog", params)
        run_until_terminal(engine, db, job_id, timeout=50)
        return get(db, job_id)
    finally:
        engine.stop()


def test_memory_error_donne_memory_limit(tmp_path: Path) -> None:
    row = _run(tmp_path, {})
    assert (row.status, row.error_code) == ("failed", "memory_limit")


def test_sortie_brutale_donne_memory_limit(tmp_path: Path) -> None:
    row = _run(tmp_path, {"crash": True})
    assert (row.status, row.error_code) == ("failed", "memory_limit")


def test_arret_avant_le_plafond_reussit(tmp_path: Path) -> None:
    row = _run(tmp_path, {"stop_mb": 20})
    assert row.status == "succeeded"


def test_peak_memory_du_job_reel(tmp_path: Path) -> None:
    script = tmp_path / "alloc.py"
    script.write_text(
        "import time\nb = bytearray(50 * 2**20)\nfor i in range(0, len(b), 4096):\n"
        "    b[i] = 1\ntime.sleep(1)\n",
        encoding="utf-8",
    )
    job = create_job()
    try:
        proc = spawn_in_job(
            job,
            [sys.executable, str(script)],
            cwd=str(tmp_path),
            log_path=str(tmp_path / "job.log"),
            env=build_env(os.environ),
        )
        time.sleep(0.7)
        assert job.peak_memory() >= 50 * 2**20
        proc.wait(10)
    finally:
        job.terminate()
        job.close()

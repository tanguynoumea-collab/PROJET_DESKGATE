"""JOB-04 : annulation coopérative puis forcée, avec de vrais sous-processus."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import psutil
import pytest

from _support.jobs import get, run_until_terminal, submit
from deskgate import store
from deskgate.core.config import RunnerConfig
from deskgate.engine import Engine

pytestmark = [
    pytest.mark.proc,
    pytest.mark.skipif(sys.platform != "win32", reason="Job Object Windows"),
    pytest.mark.timeout(60),
]

Env = tuple[Engine, Path, RunnerConfig]


def _attendre_running(engine: Engine, db: Path, job_id: str) -> None:
    limite = time.monotonic() + 15
    while time.monotonic() < limite:
        engine.tick()
        if get(db, job_id).status == "running" and engine.running_job_id == job_id:
            return
        time.sleep(0.05)
    raise AssertionError("la tâche n'a pas démarré")


def _demander_annulation(db: Path, job_id: str) -> None:
    conn = store.connect(db)
    try:
        store.request_cancel(conn, job_id)
    finally:
        conn.close()


def test_annulation_cooperative(real_engine: Env) -> None:
    engine, db, cfg = real_engine
    job_id = submit(db, cfg, "demo.sleep", {"n": 30})
    _attendre_running(engine, db, job_id)
    debut = time.monotonic()
    _demander_annulation(db, job_id)
    row = run_until_terminal(engine, db, job_id, timeout=10)
    assert row.status == "cancelled"
    assert time.monotonic() - debut < 3
    assert (Path(row.work_dir) / "cancel.flag").exists()


def test_annulation_forcee_apres_grace(real_engine: Env) -> None:
    engine, db, cfg = real_engine
    job_id = submit(db, cfg, "demo.sleep", {"n": 30, "ignore_cancel": True})
    _attendre_running(engine, db, job_id)
    debut = time.monotonic()
    _demander_annulation(db, job_id)
    row = run_until_terminal(engine, db, job_id, timeout=10)
    duree = time.monotonic() - debut
    assert row.status == "cancelled"
    assert 1.0 <= duree < 5.0
    assert engine.running_job_id is None
    limite = time.monotonic() + 5
    while time.monotonic() < limite and psutil.Process().children(recursive=True):
        time.sleep(0.1)
    assert psutil.Process().children(recursive=True) == []


def test_annulation_tache_en_file(real_engine: Env) -> None:
    engine, db, cfg = real_engine
    premiere = submit(db, cfg, "demo.sleep", {"n": 30})
    seconde = submit(db, cfg, "demo.sleep", {"n": 30})
    _attendre_running(engine, db, premiere)
    _demander_annulation(db, seconde)
    row = get(db, seconde)
    assert row.status == "cancelled"
    assert not Path(row.work_dir).exists()
    _demander_annulation(db, premiere)
    run_until_terminal(engine, db, premiere, timeout=10)
    assert not Path(get(db, seconde).work_dir).exists()

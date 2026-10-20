"""JOB-05 : arrêt de l'arbre de processus au délai, orphelin compris."""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

from _support.jobs import get, run_until_terminal, submit
from _support.procs import wait_dead
from deskgate.core.config import RunnerConfig
from deskgate.engine import Engine

pytestmark = [
    pytest.mark.proc,
    pytest.mark.skipif(sys.platform != "win32", reason="Job Object Windows"),
    pytest.mark.timeout(60),
]

Env = tuple[Engine, Path, RunnerConfig]


def _pid(work: Path, name: str) -> int:
    return int((work / name).read_text(encoding="utf-8").strip())


def test_delai_tue_l_arbre(real_engine: Env) -> None:
    engine, db, cfg = real_engine
    job_id = submit(db, cfg, "demo.spawn_orphan", {"sleep": 60}, timeout_s=2)
    row = run_until_terminal(engine, db, job_id)
    assert row.status == "timeout"
    assert row.error_code == "timeout"
    work = Path(row.work_dir)
    orphan, plugin = _pid(work, "orphan.pid"), _pid(work, "plugin.pid")
    assert plugin != os.getpid()
    assert wait_dead(orphan, 5)
    assert wait_dead(plugin, 5)
    assert row.started_at is not None
    assert row.finished_at is not None
    duree = datetime.fromisoformat(row.finished_at) - datetime.fromisoformat(row.started_at)
    assert duree.total_seconds() < 6


def test_sortie_normale_orphelin_tue(real_engine: Env) -> None:
    engine, db, cfg = real_engine
    job_id = submit(db, cfg, "demo.spawn_orphan", {"sleep": 0})
    row = run_until_terminal(engine, db, job_id)
    assert row.status == "succeeded", row.error_message
    work = Path(row.work_dir)
    assert wait_dead(_pid(work, "orphan.pid"), 5)
    assert wait_dead(_pid(work, "plugin.pid"), 5)


def test_plugin_hors_processus_du_runner(real_engine: Env) -> None:
    engine, db, cfg = real_engine
    job_id = submit(db, cfg, "demo.spawn_orphan", {"sleep": 30}, timeout_s=30)
    limite = time.monotonic() + 20
    work: Path | None = None
    while time.monotonic() < limite:
        engine.tick()
        row = get(db, job_id)
        candidat = Path(row.work_dir) / "plugin.pid"
        if candidat.exists() and candidat.read_text(encoding="utf-8").strip():
            work = candidat.parent
            break
        time.sleep(0.05)
    assert work is not None
    plugin, orphan = _pid(work, "plugin.pid"), _pid(work, "orphan.pid")
    assert plugin != os.getpid()
    engine.stop()
    assert wait_dead(plugin, 5)
    assert wait_dead(orphan, 5)

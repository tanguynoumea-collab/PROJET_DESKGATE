"""Engine et erreurs SQLite transitoires : verrou réel, verdict différé, seuil fatal."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from _support.jobs import FakeClock, FakeLauncher, get, make_config, submit
from deskgate import store
from deskgate.core.config import RunnerConfig
from deskgate.engine import Engine

pytestmark = pytest.mark.fs

WORKER = Path("C:/fake/run.py")


def fast_connect(path: Path) -> store.Connection:
    conn = store.connect(path)
    conn.execute("PRAGMA busy_timeout=50")
    return conn


@contextmanager
def blocker(db: Path) -> Iterator[store.Connection]:
    """Seconde connexion qui tient le verrou d'écriture."""
    conn = store.connect(db)
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    finally:
        try:
            conn.execute("ROLLBACK")
        finally:
            conn.close()


class Env:
    def __init__(self, tmp_path: Path, **kw: object) -> None:
        self.db = tmp_path / "d.db"
        store.open_db(self.db).close()
        self.cfg: RunnerConfig = make_config(tmp_path)
        self.launcher = FakeLauncher()
        self.engine = Engine(
            db_path=self.db,
            config=self.cfg,
            worker_script=WORKER,
            launcher=self.launcher,
            clock=FakeClock(),
            poll=0.01,
            grace=2.0,
            base_env={"PATH": "x"},
            connect=fast_connect,
            backoff=lambda n: 0.0,
            **kw,  # type: ignore[arg-type]
        )

    def submit(self, cap: str = "demo.sleep") -> str:
        return submit(self.db, self.cfg, cap)

    def callback_state(self, job_id: str) -> str | None:
        conn = store.connect(self.db)
        try:
            row = conn.execute("SELECT state FROM callbacks WHERE job_id=?", (job_id,)).fetchone()
        finally:
            conn.close()
        return None if row is None else row[0]


def test_verrou_pendant_le_suivi_ne_tue_pas_le_job(tmp_path: Path) -> None:
    env = Env(tmp_path)
    try:
        job_id = env.submit()
        env.engine.tick()
        assert env.engine.running_job_id == job_id
        job, proc = env.launcher.jobs[0], env.launcher.procs[0]
        events = Path(env.launcher.specs[0].cwd, "events.jsonl")
        events.write_text(
            '{"type":"progress","pct":50,"message":"mi-parcours"}\n', encoding="utf-8"
        )
        with blocker(env.db), pytest.raises(store.OperationalError):
            env.engine.tick()
        assert job.terminated == 0
        assert env.engine.running_job_id == job_id
        assert get(env.db, job_id).status == "running"
        proc.exit_code = 0
        Path(env.launcher.specs[0].cwd, "result.json").write_text(
            '{"protocol":1,"ok":true,"summary":{},"data":{},"artifacts":[]}', encoding="utf-8"
        )
        env.engine.tick()
        assert get(env.db, job_id).status == "succeeded"
        assert env.callback_state(job_id) == "pending"
    finally:
        env.engine.stop()


def test_verrou_a_la_reclamation(tmp_path: Path) -> None:
    env = Env(tmp_path)
    try:
        job_id = env.submit()
        with blocker(env.db), pytest.raises(store.OperationalError):
            env.engine.tick()
        assert get(env.db, job_id).status == "queued"
        env.engine.tick()
        assert get(env.db, job_id).status == "running"
    finally:
        env.engine.stop()


def test_conclusion_differee(tmp_path: Path) -> None:
    env = Env(tmp_path)
    try:
        first = env.submit()
        second = env.submit()
        env.engine.tick()
        env.launcher.procs[0].exit_code = 3
        with blocker(env.db), pytest.raises(store.OperationalError):
            env.engine.tick()
        assert env.engine._unsettled is not None
        assert env.engine.running_job_id is None
        assert get(env.db, first).status == "running"
        env.engine.tick()  # verrou levé : le verdict d'origine est écrit, rien n'est réclamé
        row = get(env.db, first)
        assert row.status == "failed"
        assert row.error_code is not None
        assert env.engine._unsettled is None
        assert get(env.db, second).status == "queued"
        assert env.callback_state(first) == "pending"
        env.engine.tick()
        assert get(env.db, second).status == "running"
    finally:
        env.engine.stop()


def test_echec_au_lancement_differe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = Env(tmp_path)
    try:
        job_id = env.submit("capacite.absente")
        real_finish = store.finish
        state = {"n": 0}

        def finish_once_locked(*a: object, **k: object) -> None:
            if state["n"] == 0:
                state["n"] += 1
                raise store.OperationalError("database is locked")
            real_finish(*a, **k)  # type: ignore[arg-type]

        monkeypatch.setattr(store, "finish", finish_once_locked)
        with pytest.raises(store.OperationalError):
            env.engine.tick()
        assert env.engine._unsettled is not None
        assert get(env.db, job_id).status == "running"
        env.engine.tick()
        row = get(env.db, job_id)
        assert row.status == "failed"
        assert env.engine._unsettled is None
        assert env.engine.running_job_id is None
    finally:
        env.engine.stop()


def test_cinq_erreurs_consecutives_fatales(tmp_path: Path) -> None:
    env = Env(tmp_path)
    fatal: list[int] = []
    env.engine.on_fatal = lambda: fatal.append(1)
    env.submit()
    with blocker(env.db):
        thread = threading.Thread(target=env.engine.run)
        thread.start()
        thread.join(10)
        assert not thread.is_alive()
    assert env.engine.failed is True
    assert fatal == [1]


def test_quatre_erreurs_puis_succes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = Env(tmp_path)
    fatal: list[int] = []
    env.engine.on_fatal = lambda: fatal.append(1)
    real_tick = env.engine.tick
    seen = {"n": 0}

    def flaky() -> None:
        seen["n"] += 1
        if seen["n"] <= 4:
            raise store.OperationalError("database is locked")
        real_tick()
        if seen["n"] >= 7:
            env.engine._stop.set()

    monkeypatch.setattr(env.engine, "tick", flaky)
    thread = threading.Thread(target=env.engine.run)
    thread.start()
    thread.join(10)
    assert not thread.is_alive()
    assert env.engine.failed is False
    assert fatal == []


def test_erreur_non_transitoire_fatale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = Env(tmp_path)
    fatal: list[int] = []
    env.engine.on_fatal = lambda: fatal.append(1)

    def boom() -> None:
        raise RuntimeError("bug")

    monkeypatch.setattr(env.engine, "tick", boom)
    thread = threading.Thread(target=env.engine.run)
    thread.start()
    thread.join(10)
    assert not thread.is_alive()
    assert env.engine.failed is True
    assert fatal == [1]


def test_stop_ferme_la_connexion(tmp_path: Path) -> None:
    env = Env(tmp_path)
    env.engine.tick()
    assert env.engine._conn is not None
    env.engine.stop()
    assert env.engine._conn is None
    env.engine.stop()

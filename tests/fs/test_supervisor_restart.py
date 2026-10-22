"""Superviseur : recréation réelle de l'engine et du sender sur base WAL."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from _support.jobs import FakeClock, FakeLauncher, get, make_config, submit
from deskgate import store
from deskgate.core.config import RunnerConfig
from deskgate.engine import Engine
from deskgate.supervisor import Holder, Restartable, Supervisor

pytestmark = pytest.mark.fs

WORKER = Path("C:/fake/run.py")


class DummySender:
    """Doublure minimale d'un sender : compte les appels."""

    def __init__(self) -> None:
        self.failed = False
        self.on_fatal: Callable[[], None] | None = None
        self.started = 0
        self.stopped = 0
        self.woken = 0

    def start(self) -> None:
        self.started += 1

    def stop(self, timeout: float = 5.0) -> None:
        self.stopped += 1

    def wake(self) -> None:
        self.woken += 1


class Env:
    def __init__(self, tmp_path: Path) -> None:
        self.db = tmp_path / "d.db"
        store.open_db(self.db).close()
        self.cfg: RunnerConfig = make_config(tmp_path)
        self.launcher = FakeLauncher()
        self.clock = FakeClock(0.0)
        self.gave_up = 0
        self.recover_error: Exception | None = None
        self.engines: list[Engine] = []
        self.senders: list[DummySender] = []
        first = self.new_engine()
        sender = self.new_sender()
        self.holder = Holder(engine=first, sender=sender)
        self.sup = Supervisor(
            holder=self.holder,
            make_engine=self.new_engine,
            make_sender=self.new_sender,
            recover=self.recover,
            on_give_up=self._give_up,
            clock=self.clock,
            period=0.05,
        )
        self.sup.attach()

    def new_engine(self) -> Engine:
        engine = Engine(
            db_path=self.db,
            config=self.cfg,
            worker_script=WORKER,
            launcher=self.launcher,
            clock=FakeClock(),
            poll=0.05,
            grace=2.0,
            base_env={"PATH": "x"},
        )
        self.engines.append(engine)
        return engine

    def new_sender(self) -> DummySender:
        sender = DummySender()
        self.senders.append(sender)
        return sender

    def recover(self) -> list[str]:
        if self.recover_error is not None:
            raise self.recover_error
        conn = store.connect(self.db)
        try:
            return store.recover_interrupted(conn)
        finally:
            conn.close()

    def _give_up(self) -> None:
        self.gave_up += 1

    def callback_state(self, job_id: str) -> str | None:
        conn = store.connect(self.db)
        try:
            row = conn.execute("SELECT state FROM callbacks WHERE job_id=?", (job_id,)).fetchone()
        finally:
            conn.close()
        return None if row is None else row[0]

    def close(self) -> None:
        self.sup.stop()
        self.holder.engine.stop()
        for engine in self.engines:
            engine.stop()


@pytest.fixture
def env(tmp_path: Path) -> Iterator[Env]:
    e = Env(tmp_path)
    try:
        yield e
    finally:
        e.close()


def wait_until(cond: Callable[[], bool], timeout: float = 5.0) -> bool:
    limit = time.monotonic() + timeout
    while time.monotonic() < limit:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def fail_engine(env: Env) -> None:
    env.holder.engine.failed = True


def test_engine_mort_recree(env: Env) -> None:
    job_id = submit(env.db, env.cfg, "demo.sleep")
    engine1 = env.holder.engine
    assert isinstance(engine1, Engine)
    engine1.tick()
    assert get(env.db, job_id).status == "running"
    engine1.failed = True
    env.sup.check()
    job = env.launcher.jobs[0]
    assert job.terminated >= 1
    assert job.closed >= 1
    row = get(env.db, job_id)
    assert row.status == "interrupted"
    assert row.error_code == "runner_restarted"
    assert env.callback_state(job_id) == "pending"
    new = env.holder.engine
    assert new is not engine1
    assert isinstance(new, Engine)
    assert new._thread is not None and new._thread.is_alive()
    assert new.on_fatal == env.sup.notify
    assert env.holder.sender.woken >= 1  # type: ignore[attr-defined]


def test_sender_mort_recree(env: Env) -> None:
    engine = env.holder.engine
    old = env.holder.sender
    assert isinstance(old, DummySender)
    old.failed = True
    env.sup.check()
    new = env.holder.sender
    assert new is not old
    assert isinstance(new, DummySender)
    assert old.stopped == 1
    assert new.started == 1
    assert new.on_fatal == env.sup.notify
    assert env.holder.engine is engine


def test_budget_epuise(env: Env) -> None:
    for t in (0.0, 1.0, 2.0):
        env.clock.t = t
        fail_engine(env)
        env.sup.check()
    assert len(env.engines) == 4
    env.clock.t = 3.0
    fail_engine(env)
    env.sup.check()
    assert env.sup.gave_up is True
    assert env.gave_up == 1
    assert len(env.engines) == 4
    env.sup.check()
    assert env.gave_up == 1


def test_budget_glissant(env: Env) -> None:
    for t in (0.0, 0.0, 0.0):
        env.clock.t = t
        fail_engine(env)
        env.sup.check()
    env.clock.t = 601.0
    fail_engine(env)
    env.sup.check()
    assert env.sup.gave_up is False
    assert len(env.engines) == 5


def test_recover_qui_leve(env: Env) -> None:
    env.recover_error = RuntimeError("base verrouillée")
    first = env.holder.engine
    fail_engine(env)
    env.sup.check()
    assert env.holder.engine is first
    assert len(env.engines) == 1
    assert env.sup.last_cause == "engine (recovery impossible)"
    for _ in range(4):
        env.sup.check()
    assert env.sup.gave_up is True
    assert env.gave_up == 1


def test_thread_superviseur_reveille_par_on_fatal(env: Env) -> None:
    engine1 = env.holder.engine
    assert isinstance(engine1, Engine)

    def boom() -> None:
        raise RuntimeError("panne simulée")

    engine1.tick = boom  # type: ignore[method-assign]
    env.sup.start()
    engine1.start()
    assert wait_until(lambda: env.holder.engine is not engine1)
    new = env.holder.engine
    assert isinstance(new, Engine)
    assert new._thread is not None and new._thread.is_alive()


def test_stop_bloque_les_recreations(env: Env) -> None:
    env.sup.start()
    env.sup.stop()
    fail_engine(env)
    before = env.holder.engine
    env.sup.notify()
    time.sleep(1.5)
    assert env.holder.engine is before
    assert len(env.engines) == 1


def test_protocol_satisfait(env: Env) -> None:
    engine: Restartable = env.holder.engine
    assert engine.failed is False

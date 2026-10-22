"""État des threads (D-07) : fonctions pures, Engine.status et Sender.status."""

from __future__ import annotations

from pathlib import Path

import pytest

from _support.jobs import FakeClock, FakeLauncher, make_config
from _support.sender_helpers import FakeWall, make_sender
from deskgate import store
from deskgate.core.health import overall, stale_threshold, thread_state
from deskgate.engine import Engine

WORKER = Path("C:/fake/run.py")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("poll", "floor", "attendu"),
    [(0.5, 30.0, 30.0), (5.0, 30.0, 50.0), (1.0, 60.0, 60.0)],
)
def test_stale_threshold(poll: float, floor: float, attendu: float) -> None:
    assert stale_threshold(poll, floor) == attendu


@pytest.mark.unit
def test_failed_l_emporte() -> None:
    assert thread_state(failed=True, age_s=0, threshold_s=30) == "failed"


@pytest.mark.unit
def test_jamais_demarre_est_ok() -> None:
    assert thread_state(failed=False, age_s=None, threshold_s=30) == "ok"


@pytest.mark.unit
def test_bornes() -> None:
    assert thread_state(failed=False, age_s=30.0, threshold_s=30) == "ok"
    assert thread_state(failed=False, age_s=30.01, threshold_s=30) == "stale"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("etats", "attendu"),
    [
        ({"engine": "ok", "sender": "ok"}, "ok"),
        ({"engine": "stale", "sender": "ok"}, "degraded"),
        ({"engine": "ok", "sender": "failed"}, "degraded"),
    ],
)
def test_overall(etats: dict[str, str], attendu: str) -> None:
    assert overall(etats) == attendu  # type: ignore[arg-type]


def _engine(tmp_path: Path, clock: FakeClock) -> Engine:
    db = tmp_path / "d.db"
    store.open_db(db).close()
    return Engine(
        db_path=db,
        config=make_config(tmp_path),
        worker_script=WORKER,
        launcher=FakeLauncher(),
        clock=clock,
        poll=0.5,
        grace=2.0,
        base_env={"PATH": "x"},
    )


@pytest.mark.fs
def test_engine_status(tmp_path: Path) -> None:
    clock = FakeClock()
    engine = _engine(tmp_path, clock)
    try:
        engine.tick()
        assert engine.status() == "ok"
        clock.advance(31)
        assert engine.status() == "stale"
        engine.failed = True
        assert engine.status() == "failed"
    finally:
        engine.stop()


@pytest.mark.fs
def test_engine_demarre_sans_tour(tmp_path: Path) -> None:
    clock = FakeClock()
    engine = _engine(tmp_path, clock)
    try:
        engine._started_at = clock()
        clock.advance(29)
        assert engine.status() == "ok"
        clock.advance(2)
        assert engine.status() == "stale"
    finally:
        engine.stop()


@pytest.mark.fs
def test_sender_status(tmp_path: Path) -> None:
    db = tmp_path / "d.db"
    store.open_db(db).close()
    wall = FakeWall()
    sender = make_sender(db, make_config(tmp_path), wall)
    try:
        sender.tick()
        wall.advance(59)
        assert sender.status() == "ok"
        wall.advance(2)
        assert sender.status() == "stale"
    finally:
        sender.stop()

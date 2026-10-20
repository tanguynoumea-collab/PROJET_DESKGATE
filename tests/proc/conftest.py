"""Fixture partagée : engine réel (vrai launcher, Job Object, vrai worker SDK)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import deskgate_sdk.run as sdk_run
from deskgate import store
from deskgate.core.config import RunnerConfig
from deskgate.engine import Engine
from _support.jobs import make_config


@pytest.fixture
def real_engine(tmp_path: Path) -> Iterator[tuple[Engine, Path, RunnerConfig]]:
    cfg = make_config(tmp_path)
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
        yield engine, db, cfg
    finally:
        engine.stop()

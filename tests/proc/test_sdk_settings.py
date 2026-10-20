"""SDK : ctx.settings et error_code, avec un vrai worker."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

import deskgate_sdk.run as sdk_run
from _support.jobs import make_config, run_until_terminal, submit
from deskgate import store
from deskgate.engine import Engine

pytestmark = [
    pytest.mark.proc,
    pytest.mark.skipif(sys.platform != "win32", reason="Job Object Windows"),
    pytest.mark.timeout(60),
]


@pytest.fixture
def env(tmp_path: Path) -> Iterator[tuple[Engine, Path, object]]:
    cfg = make_config(
        tmp_path,
        caps={
            "demo.settings_echo": {
                "entry": "deskgate_fakes:settings_echo",
                "settings": {"cle": "v", "n": 2},
            },
            "demo.fail_code": {"entry": "deskgate_fakes:fail_code"},
        },
    )
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


def test_settings_visibles(env: tuple[Engine, Path, object]) -> None:
    engine, db, cfg = env
    job = submit(db, cfg, "demo.settings_echo")  # type: ignore[arg-type]
    row = run_until_terminal(engine, db, job)
    assert row.status == "succeeded"
    assert row.result_json is not None
    assert '"cle"' in row.result_json
    assert '"n"' in row.result_json


def test_error_code(env: tuple[Engine, Path, object]) -> None:
    engine, db, cfg = env
    job = submit(db, cfg, "demo.fail_code")  # type: ignore[arg-type]
    row = run_until_terminal(engine, db, job)
    assert row.status == "failed"
    assert row.error_code == "plugin_error"
    assert (row.error_message or "").startswith("demo_code : ")

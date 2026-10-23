"""Purge de `data` des tâches terminées au rappel final (DS-SCAL-1) : périmètre, audit, schéma."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from tests._support.jobs import get, make_config
from tests._support.sender_helpers import (
    T0,
    FakeWall,
    audit_details,
    make_terminal,
    read_one,
)

from deskgate import store
from deskgate.core.config import RunnerConfig
from deskgate.core.jobspec import new_job_id
from deskgate.jobs import job_view

pytestmark = pytest.mark.fs

CUTOFF = T0 + timedelta(days=1)
URL = "http://n8n/x?signature=S"


def _job(
    db: Path,
    cfg: RunnerConfig,
    wall: FakeWall,
    status: str = "succeeded",
    data: object = None,
    *,
    result_json: str | None = None,
    final: bool = True,
) -> str:
    if data is not None:
        result_json = json.dumps(
            {"summary": {"n": 1}, "data": data, "artifacts": [{"kind": "k", "path": "p"}]}
        )
    job_id = make_terminal(db, cfg, status, url=URL, wall=wall, result_json=result_json)
    if final:
        conn = store.connect(db)
        try:
            with store.tx(conn):
                conn.execute("UPDATE callbacks SET state='delivered' WHERE job_id=?", (job_id,))
        finally:
            conn.close()
    return job_id


def _purge(db: Path, cutoff: datetime = CUTOFF) -> int:
    conn = store.connect(db)
    try:
        return store.purge_data(conn, older_than=cutoff, now=cutoff)
    finally:
        conn.close()


def _result(db: Path, job_id: str) -> str | None:
    value = read_one(db, "SELECT result_json FROM jobs WHERE id=?", job_id)[0]
    return None if value is None else str(value)


@pytest.fixture
def env(tmp_path: Path) -> tuple[Path, RunnerConfig, FakeWall]:
    return tmp_path / "d.db", make_config(tmp_path), FakeWall()


def test_purge_remplace_data_ancien_final(env: tuple[Path, RunnerConfig, FakeWall]) -> None:
    db, cfg, wall = env
    job_id = _job(db, cfg, wall, data={"values": list(range(1000))})
    assert _purge(db) == 1
    result = json.loads(str(_result(db, job_id)))
    assert result["data"] == {"purged": True}
    assert result["summary"] == {"n": 1}
    assert result["artifacts"] == [{"kind": "k", "path": "p"}]


@pytest.mark.parametrize("status", ["succeeded", "failed", "timeout"])
def test_purge_statuts_terminaux(env: tuple[Path, RunnerConfig, FakeWall], status: str) -> None:
    db, cfg, wall = env
    _job(db, cfg, wall, status, data={"v": 1})
    assert _purge(db) == 1


def test_purge_ignore_recent(env: tuple[Path, RunnerConfig, FakeWall]) -> None:
    db, cfg, wall = env
    job_id = _job(db, cfg, wall, data={"v": 1})
    before = _result(db, job_id)
    assert _purge(db, T0 - timedelta(seconds=1)) == 0
    assert _result(db, job_id) == before


def test_purge_ignore_rappel_non_final(env: tuple[Path, RunnerConfig, FakeWall]) -> None:
    db, cfg, wall = env
    job_id = _job(db, cfg, wall, data={"v": 1}, final=False)
    before = _result(db, job_id)
    assert _purge(db) == 0
    assert _result(db, job_id) == before


def test_purge_ignore_non_terminal(tmp_path: Path) -> None:
    db = tmp_path / "d.db"
    conn = store.open_db(db)
    try:
        store.insert_job(
            conn,
            job_id=new_job_id(),
            capability="demo.sleep",
            params_json="{}",
            timeout_s=60,
            resource="default",
            idempotency_key=None,
            callback_url="http://x/y",
            work_dir="C:/w/q",
            now=T0,
        )
    finally:
        conn.close()
    assert _purge(db) == 0


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"purged": True},
        {"path": "/data/travail/x/data.json", "truncated": True},
        {"truncated": True},
        {"truncated": True, "error": "data_write_failed"},
    ],
)
def test_purge_ignore_vide_purge_et_repli(
    env: tuple[Path, RunnerConfig, FakeWall], data: dict[str, object]
) -> None:
    db, cfg, wall = env
    job_id = _job(db, cfg, wall, data=data)
    before = _result(db, job_id)
    assert _purge(db) == 0
    assert _result(db, job_id) == before


def test_purge_ignore_sans_resultat(env: tuple[Path, RunnerConfig, FakeWall]) -> None:
    db, cfg, wall = env
    job_id = _job(db, cfg, wall, "interrupted")
    assert _result(db, job_id) is None
    assert _purge(db) == 0


def test_purge_json_invalide_ne_bloque_pas(env: tuple[Path, RunnerConfig, FakeWall]) -> None:
    db, cfg, wall = env
    bad = _job(db, cfg, wall, result_json="{")
    _job(db, cfg, wall, data={"v": 1})
    assert _purge(db) == 1
    assert _result(db, bad) == "{"


def test_purge_idempotente_et_auditee(env: tuple[Path, RunnerConfig, FakeWall]) -> None:
    db, cfg, wall = env
    _job(db, cfg, wall, data={"values": [1, 2, 3]})
    snap_cb = "SELECT * FROM callbacks ORDER BY job_id"
    snap_audit = (
        "SELECT id, ts, event, job_id, detail_json FROM audit "
        "WHERE event != 'data.purged' ORDER BY id"
    )

    def snapshot() -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
        conn = store.connect(db)
        try:
            return (
                [tuple(r) for r in conn.execute(snap_cb)],
                [tuple(r) for r in conn.execute(snap_audit)],
            )
        finally:
            conn.close()

    before = snapshot()
    assert _purge(db) == 1
    assert audit_details(db, "data.purged") == [{"count": 1, "older_than": store.iso(CUTOFF)}]
    assert snapshot() == before
    assert _purge(db) == 0
    assert len(audit_details(db, "data.purged")) == 1
    assert "values" not in json.dumps(audit_details(db, "data.purged"))


def test_purge_schema_inchange(env: tuple[Path, RunnerConfig, FakeWall]) -> None:
    db, cfg, wall = env
    _job(db, cfg, wall, data={"v": 1})
    _purge(db)
    assert read_one(db, "PRAGMA user_version")[0] == 2 == store.SCHEMA_VERSION


def test_get_apres_purge(env: tuple[Path, RunnerConfig, FakeWall]) -> None:
    db, cfg, wall = env
    job_id = _job(db, cfg, wall, data={"v": 1})
    _purge(db)
    assert job_view(get(db, job_id))["data"] == {"purged": True}

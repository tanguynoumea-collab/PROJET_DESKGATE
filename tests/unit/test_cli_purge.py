"""Commande `deskgate purge` (DS-SCAL-1) : sortie, codes de retour, base absente."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from tests._support.jobs import make_config
from tests._support.sender_helpers import FakeWall, make_terminal
from typer.testing import CliRunner

from deskgate import store
from deskgate.cli import app

pytestmark = pytest.mark.unit


def _seed(tmp_path: Path, data_home: Path) -> Path:
    db = data_home / "deskgate.db"
    job_id = make_terminal(
        db,
        make_config(tmp_path),
        "succeeded",
        url="http://n8n/x?signature=S",
        wall=FakeWall(),
        result_json=json.dumps({"summary": {}, "data": {"v": 1}, "artifacts": []}),
    )
    conn = store.connect(db)
    try:
        with store.tx(conn):
            conn.execute("UPDATE callbacks SET state='delivered' WHERE job_id=?", (job_id,))
    finally:
        conn.close()
    return db


def test_purge_base_absente(data_home: Path) -> None:
    result = CliRunner().invoke(app, ["purge"])
    assert result.exit_code == 1
    assert "Base introuvable" in result.stderr
    assert not (data_home / "deskgate.db").exists()


def test_purge_affiche_le_nombre(tmp_path: Path, data_home: Path) -> None:
    _seed(tmp_path, data_home)
    first = CliRunner().invoke(app, ["purge", "--older-than-days", "0"])
    assert first.exit_code == 0
    assert first.stdout.startswith("1 tâche(s) purgée(s)")
    second = CliRunner().invoke(app, ["purge", "--older-than-days", "0"])
    assert second.exit_code == 0
    assert second.stdout.startswith("0 tâche(s) purgée(s)")


def test_purge_defaut_30_jours(
    tmp_path: Path, data_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(tmp_path, data_home)
    seen: list[datetime] = []
    original = store.purge_data

    def spy(conn: sqlite3.Connection, *, older_than: datetime, now: datetime | None = None) -> int:
        seen.append(older_than)
        return original(conn, older_than=older_than, now=now)

    monkeypatch.setattr(store, "purge_data", spy)
    assert CliRunner().invoke(app, ["purge"]).exit_code == 0
    expected = datetime.now(UTC) - timedelta(days=30)
    assert abs((seen[0] - expected).total_seconds()) < 60


def test_purge_jours_negatifs_refuses(data_home: Path) -> None:
    result = CliRunner().invoke(app, ["purge", "--older-than-days", "-1"])
    assert result.exit_code == 2


def test_purge_base_occupee(
    tmp_path: Path, data_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(tmp_path, data_home)

    def busy(conn: sqlite3.Connection, **_: object) -> int:
        raise store.OperationalError("database is locked")

    monkeypatch.setattr(store, "purge_data", busy)
    result = CliRunner().invoke(app, ["purge"])
    assert result.exit_code == 1
    assert "Base occupée" in result.stderr


def test_purge_base_trop_recente(data_home: Path) -> None:
    raw = sqlite3.connect(data_home / "deskgate.db")
    raw.execute("PRAGMA user_version = 99")
    raw.close()
    result = CliRunner().invoke(app, ["purge"])
    assert result.exit_code == 2
    assert "mettez Deskgate à jour" in result.stderr


def test_purge_base_non_initialisee(data_home: Path) -> None:
    (data_home / "deskgate.db").write_bytes(b"")
    result = CliRunner().invoke(app, ["purge"])
    assert result.exit_code == 2
    assert "non initialisée" in result.stderr


def test_aide_liste_purge() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert "purge" in result.stdout

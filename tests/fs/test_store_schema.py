"""Migrations 1 et 2, transactions et audit en ajout seul."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from deskgate import store

pytestmark = pytest.mark.fs


def test_base_neuve_migree(tmp_path: Path) -> None:
    conn = store.open_db(tmp_path / "sous" / "d.db")
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        names = {r["name"] for r in rows}
        assert {"jobs", "callbacks", "audit"} <= names
    finally:
        conn.close()


def test_migrate_idempotent(tmp_path: Path) -> None:
    conn = store.open_db(tmp_path / "d.db")
    try:
        assert store.migrate(conn) == 2
    finally:
        conn.close()


def test_base_trop_recente(tmp_path: Path) -> None:
    path = tmp_path / "d.db"
    raw = sqlite3.connect(path)
    raw.execute("PRAGMA user_version = 3")
    raw.close()
    with pytest.raises(store.SchemaTooNew) as err:
        store.open_db(path)
    assert "3" in str(err.value)
    assert "2" in str(err.value)


def test_audit_ajout_seul(tmp_path: Path) -> None:
    conn = store.open_db(tmp_path / "d.db")
    try:
        conn.execute("INSERT INTO audit(ts, event) VALUES ('t', 'e')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE audit SET event='x'")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM audit")
    finally:
        conn.close()


def test_statut_invalide_refuse(tmp_path: Path) -> None:
    conn = store.open_db(tmp_path / "d.db")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO jobs(id, capability, params_json, status, timeout_s, resource, "
                "callback_url, work_dir, created_at) "
                "VALUES ('a','c','{}','bogus',1,'r','u','w','t')"
            )
    finally:
        conn.close()


def test_tx_rollback_sur_exception(tmp_path: Path) -> None:
    conn = store.open_db(tmp_path / "d.db")
    try:
        with pytest.raises(RuntimeError), store.tx(conn):
            conn.execute("INSERT INTO audit(ts, event) VALUES ('t', 'e')")
            raise RuntimeError("boum")
        assert conn.execute("SELECT count(*) FROM audit").fetchone()[0] == 0
    finally:
        conn.close()


def test_migration_1_vers_2(tmp_path: Path) -> None:
    path = tmp_path / "d.db"
    raw = sqlite3.connect(path, isolation_level=None)
    for statement in store.MIGRATION_1:
        raw.execute(statement)
    raw.execute("PRAGMA user_version = 1")
    raw.execute(
        "INSERT INTO jobs(id, capability, params_json, timeout_s, resource, callback_url, "
        "work_dir, created_at) VALUES ('a','c','{}',1,'r','u','w','t')"
    )
    raw.execute("INSERT INTO callbacks(job_id, next_attempt_at, not_before) VALUES ('a','t','t')")
    raw.close()
    conn = store.open_db(path)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(callbacks)")}
        assert "maybe_delivered" in columns
        assert conn.execute("SELECT maybe_delivered FROM callbacks").fetchone()[0] == 0
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE callbacks SET maybe_delivered=2")
    finally:
        conn.close()

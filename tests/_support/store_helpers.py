"""Aides communes aux tests du stockage."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from deskgate import store

CALLBACK_URL = "http://localhost:5678/webhook-waiting/1?signature=SECRETSIG"


def make_db(tmp_path: Path) -> sqlite3.Connection:
    return store.open_db(tmp_path / "d.db")


def submit(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    capability: str = "demo.sleep",
    key: str | None = None,
) -> None:
    store.insert_job(
        conn,
        job_id=job_id,
        capability=capability,
        params_json='{"secret_param": "PARAMVAL"}',
        timeout_s=60,
        resource="default",
        idempotency_key=key,
        callback_url=CALLBACK_URL,
        work_dir=f"C:/w/{job_id}",
    )


def succeed(conn: sqlite3.Connection, job_id: str) -> None:
    store.finish(
        conn,
        job_id,
        from_status="running",
        to_status="succeeded",
        result_json="{}",
        error_code=None,
        error_message=None,
    )


def count(conn: sqlite3.Connection, table: str, where: str = "1=1") -> int:
    sql = f"SELECT count(*) FROM {table} WHERE {where}"  # noqa: S608
    return int(conn.execute(sql).fetchone()[0])

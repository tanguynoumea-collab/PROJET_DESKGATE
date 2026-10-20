"""Aides des tests du sender : horloge murale fausse, tâches terminales, lectures de base."""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx2

from deskgate import store
from deskgate.core.config import CallbackConfig, RunnerConfig
from deskgate.core.jobspec import new_job_id
from deskgate.sender import Sender

T0 = datetime(2026, 10, 20, 12, tzinfo=UTC)


class FakeWall:
    """Horloge murale appelable, avancée à la main."""

    def __init__(self, t0: datetime = T0) -> None:
        self.t = t0

    def __call__(self) -> datetime:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += timedelta(seconds=seconds)

    def set(self, t: datetime) -> None:
        self.t = t


def callback_config(
    cfg: RunnerConfig, *, max_window_s: int = 3600, max_backoff_s: int = 300
) -> RunnerConfig:
    return cfg.model_copy(
        update={"callback": CallbackConfig(max_window_s=max_window_s, max_backoff_s=max_backoff_s)}
    )


def make_sender(
    db: Path,
    cfg: RunnerConfig,
    wall: FakeWall,
    *,
    client: httpx2.Client | None = None,
    seed: int = 0,
) -> Sender:
    return Sender(db_path=db, config=cfg, client=client, wall=wall, rng=random.Random(seed))  # noqa: S311


def make_terminal(
    db: Path,
    cfg: RunnerConfig,
    status: str,
    *,
    url: str,
    wall: FakeWall,
    result_json: str | None = None,
) -> str:
    """Insère une tâche et l'amène dans `status` à l'instant `wall()`."""
    job_id = new_job_id()
    now = wall()
    conn = store.open_db(db)
    try:
        store.insert_job(
            conn,
            job_id=job_id,
            capability="demo.sleep",
            params_json="{}",
            timeout_s=60,
            resource="default",
            idempotency_key=None,
            callback_url=url,
            work_dir=f"C:/w/{job_id}",
            now=now,
        )
        if status == "cancelled":
            store.request_cancel(conn, job_id, now)
            return job_id
        claimed = store.claim_next(conn, now)
        assert claimed is not None and claimed.id == job_id
        if status == "interrupted":
            store.recover_interrupted(conn, now)
            return job_id
        failed = status in ("failed", "timeout")
        store.finish(
            conn,
            job_id,
            from_status="running",
            to_status=status,
            result_json=result_json,
            error_code="boom" if failed else None,
            error_message="échec simulé" if failed else None,
            now=now,
        )
    finally:
        conn.close()
    return job_id


def read_one(db: Path, sql: str, *args: object) -> sqlite3.Row:
    conn = store.connect(db)
    try:
        row = conn.execute(sql, args).fetchone()
    finally:
        conn.close()
    assert row is not None
    return row


def callback_row(db: Path, job_id: str) -> sqlite3.Row:
    return read_one(db, "SELECT * FROM callbacks WHERE job_id=?", job_id)


def job_callback_url(db: Path, job_id: str) -> str:
    return str(read_one(db, "SELECT callback_url FROM jobs WHERE id=?", job_id)[0])


def audit_details(db: Path, event: str) -> list[dict[str, object]]:
    conn = store.connect(db)
    try:
        rows = conn.execute("SELECT detail_json FROM audit WHERE event=? ORDER BY id", (event,))
        return [json.loads(r["detail_json"]) for r in rows.fetchall()]
    finally:
        conn.close()


def all_audit_text(db: Path) -> str:
    conn = store.connect(db)
    try:
        return "\n".join(str(r[0]) for r in conn.execute("SELECT detail_json FROM audit"))
    finally:
        conn.close()


def next_attempt(db: Path, job_id: str) -> datetime:
    return datetime.fromisoformat(str(callback_row(db, job_id)["next_attempt_at"]))


def advance_to_next(wall: FakeWall, db: Path, job_id: str) -> None:
    """Avance l'horloge jusqu'à `next_attempt_at` lu en base."""
    wall.set(max(wall.t, next_attempt(db, job_id)))

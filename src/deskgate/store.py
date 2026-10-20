"""Accès à la base SQLite : seul module qui importe `sqlite3`.

Une connexion par thread ou par requête, jamais partagée ; toute écriture en BEGIN IMMEDIATE.
Les statuts sont écrits en littéraux SQL (mêmes valeurs que le noyau d'états).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

Connection = sqlite3.Connection  # alias : les autres modules n'importent pas sqlite3

CALLBACK_DELAY_S = 2


class StoreError(Exception):
    """Erreur de la couche de stockage."""


class SchemaTooNew(StoreError):
    """La base est plus récente que ce runner."""

    def __init__(self, found: int) -> None:
        super().__init__(
            f"Base de données en version {found}, ce runner gère la version "
            f"{SCHEMA_VERSION} : mettez Deskgate à jour."
        )
        self.found = found


class StaleTransition(StoreError):
    """La tâche n'était plus dans l'état attendu."""

    def __init__(self, job_id: str) -> None:
        super().__init__(f"Transition obsolète pour la tâche {job_id}.")
        self.job_id = job_id


class IdempotencyConflict(StoreError):
    """Une tâche non terminale porte déjà cette clé d'idempotence."""

    def __init__(self, existing_job_id: str) -> None:
        super().__init__(f"Clé d'idempotence déjà utilisée par la tâche {existing_job_id}.")
        self.existing_job_id = existing_job_id


MIGRATION_1: tuple[str, ...] = (
    """CREATE TABLE jobs (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE,
  capability TEXT NOT NULL,
  params_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued','running','succeeded','failed','timeout','cancelled','interrupted')),
  cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0,1)),
  timeout_s INTEGER NOT NULL CHECK (timeout_s > 0),
  progress_pct REAL, progress_message TEXT,
  result_json TEXT,
  error_code TEXT, error_message TEXT,
  resource TEXT NOT NULL,
  idempotency_key TEXT,
  callback_url TEXT NOT NULL,
  work_dir TEXT NOT NULL,
  created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT
) STRICT""",
    """CREATE UNIQUE INDEX jobs_idem ON jobs(capability, idempotency_key)
  WHERE status IN ('queued','running')""",
    "CREATE INDEX jobs_status_seq ON jobs(status, seq)",
    """CREATE TABLE callbacks (
  job_id TEXT NOT NULL UNIQUE REFERENCES jobs(id),
  state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN
    ('pending','delivered','delivered_duplicate','abandoned_stale','abandoned_rejected','abandoned_exhausted')),
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TEXT NOT NULL, not_before TEXT NOT NULL,
  last_status INTEGER, last_error_redacted TEXT
) STRICT""",
    """CREATE TABLE audit (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL,
  event TEXT NOT NULL, job_id TEXT, detail_json TEXT) STRICT""",
    """CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit
BEGIN SELECT RAISE(ABORT,'audit en ajout seul'); END""",
    """CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit
BEGIN SELECT RAISE(ABORT,'audit en ajout seul'); END""",
)

MIGRATIONS: tuple[tuple[str, ...], ...] = (MIGRATION_1,)


def iso(dt: datetime) -> str:
    """UTC, millisecondes, suffixe Z : 2026-10-20T12:00:00.123Z."""
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _now(now: datetime | None) -> datetime:
    return now if now is not None else datetime.now(UTC)


def connect(path: Path) -> sqlite3.Connection:
    """Ouvre une connexion (sans transaction implicite)."""
    conn = sqlite3.connect(path, isolation_level=None, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def tx(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Transaction BEGIN IMMEDIATE ; ROLLBACK sur toute exception."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def migrate(conn: sqlite3.Connection) -> int:
    """Applique les migrations manquantes ; renvoie la version finale."""
    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if version > SCHEMA_VERSION:
        raise SchemaTooNew(version)
    for number in range(version, len(MIGRATIONS)):
        with tx(conn):
            for statement in MIGRATIONS[number]:
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {number + 1}")
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def open_db(path: Path) -> sqlite3.Connection:
    """Crée le dossier parent, ouvre la base en WAL et la migre."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        migrate(conn)
    except BaseException:
        conn.close()
        raise
    return conn


@dataclass(frozen=True)
class JobRow:
    seq: int
    id: str
    capability: str
    params_json: str
    status: str
    cancel_requested: bool
    timeout_s: int
    progress_pct: float | None
    progress_message: str | None
    result_json: str | None
    error_code: str | None
    error_message: str | None
    resource: str
    idempotency_key: str | None
    callback_url: str
    work_dir: str
    created_at: str
    started_at: str | None
    finished_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> JobRow:
        return cls(
            seq=row["seq"],
            id=row["id"],
            capability=row["capability"],
            params_json=row["params_json"],
            status=row["status"],
            cancel_requested=bool(row["cancel_requested"]),
            timeout_s=row["timeout_s"],
            progress_pct=row["progress_pct"],
            progress_message=row["progress_message"],
            result_json=row["result_json"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            resource=row["resource"],
            idempotency_key=row["idempotency_key"],
            callback_url=row["callback_url"],
            work_dir=row["work_dir"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )


def _audit(
    conn: sqlite3.Connection, event: str, job_id: str, detail: dict[str, Any], now: datetime
) -> None:
    conn.execute(
        "INSERT INTO audit(ts, event, job_id, detail_json) VALUES (?, ?, ?, ?)",
        (iso(now), event, job_id, json.dumps(detail, ensure_ascii=False)),
    )


def _callback_and_audit(
    conn: sqlite3.Connection,
    job_id: str,
    to_status: str,
    error_code: str | None,
    now: datetime,
) -> None:
    conn.execute(
        "INSERT INTO callbacks(job_id, state, next_attempt_at, not_before) "
        "VALUES (?, 'pending', ?, ?)",
        (job_id, iso(now), iso(now + timedelta(seconds=CALLBACK_DELAY_S))),
    )
    _audit(conn, f"job.{to_status}", job_id, {"status": to_status, "error_code": error_code}, now)


def _terminal(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    from_status: str,
    to_status: str,
    result_json: str | None,
    error_code: str | None,
    error_message: str | None,
    now: datetime,
) -> None:
    """Écriture terminale (D-11) : à appeler DANS une transaction ouverte."""
    cur = conn.execute(
        "UPDATE jobs SET status=?, finished_at=?, result_json=?, error_code=?, error_message=? "
        "WHERE id=? AND status=?",
        (to_status, iso(now), result_json, error_code, error_message, job_id, from_status),
    )
    if cur.rowcount != 1:
        raise StaleTransition(job_id)
    _callback_and_audit(conn, job_id, to_status, error_code, now)


def insert_job(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    capability: str,
    params_json: str,
    timeout_s: int,
    resource: str,
    idempotency_key: str | None,
    callback_url: str,
    work_dir: str,
    now: datetime | None = None,
) -> None:
    """Insère une tâche `queued` ; refuse une clé d'idempotence déjà active."""
    moment = _now(now)
    try:
        with tx(conn):
            if idempotency_key is not None:
                found = conn.execute(
                    "SELECT id FROM jobs WHERE capability=? AND idempotency_key=? "
                    "AND status IN ('queued','running')",
                    (capability, idempotency_key),
                ).fetchone()
                if found is not None:
                    raise IdempotencyConflict(found["id"])
            conn.execute(
                "INSERT INTO jobs(id, capability, params_json, timeout_s, resource, "
                "idempotency_key, callback_url, work_dir, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    capability,
                    params_json,
                    timeout_s,
                    resource,
                    idempotency_key,
                    callback_url,
                    work_dir,
                    iso(moment),
                ),
            )
            _audit(conn, "job.submitted", job_id, {"capability": capability}, moment)
    except sqlite3.IntegrityError as exc:
        if "jobs.capability" in str(exc) or "jobs.idempotency_key" in str(exc):
            row = conn.execute(
                "SELECT id FROM jobs WHERE capability=? AND idempotency_key=? "
                "AND status IN ('queued','running')",
                (capability, idempotency_key),
            ).fetchone()
            if row is not None:
                raise IdempotencyConflict(row["id"]) from exc
        raise


def get_job(conn: sqlite3.Connection, job_id: str) -> JobRow | None:
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return None if row is None else JobRow.from_row(row)


def claim_next(conn: sqlite3.Connection, now: datetime | None = None) -> JobRow | None:
    """Réclame atomiquement la plus ancienne tâche queued si aucune ne tourne."""
    moment = _now(now)
    with tx(conn):
        rows = conn.execute(
            "UPDATE jobs SET status='running', started_at=? "
            "WHERE id = (SELECT id FROM jobs WHERE status='queued' ORDER BY seq LIMIT 1) "
            "AND NOT EXISTS (SELECT 1 FROM jobs WHERE status='running') "
            "RETURNING *",
            (iso(moment),),
        ).fetchall()
        if not rows:
            return None
        job = JobRow.from_row(rows[0])
        _audit(conn, "job.started", job.id, {"capability": job.capability}, moment)
    return job


def update_progress(
    conn: sqlite3.Connection, job_id: str, pct: float | None, message: str | None
) -> None:
    with tx(conn):
        conn.execute(
            "UPDATE jobs SET progress_pct=?, progress_message=? WHERE id=? AND status='running'",
            (pct, message, job_id),
        )


def is_cancel_requested(conn: sqlite3.Connection, job_id: str) -> bool:
    row = conn.execute("SELECT cancel_requested FROM jobs WHERE id=?", (job_id,)).fetchone()
    return row is not None and bool(row["cancel_requested"])


def finish(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    from_status: str,
    to_status: str,
    result_json: str | None,
    error_code: str | None,
    error_message: str | None,
    now: datetime | None = None,
) -> None:
    """Transition terminale : statut, rappel pending et audit en une transaction."""
    moment = _now(now)
    with tx(conn):
        _terminal(
            conn,
            job_id,
            from_status=from_status,
            to_status=to_status,
            result_json=result_json,
            error_code=error_code,
            error_message=error_message,
            now=moment,
        )


def request_cancel(
    conn: sqlite3.Connection, job_id: str, now: datetime | None = None
) -> JobRow | None:
    """Annulation atomique : queued -> cancelled ; running -> drapeau ; sinon inchangé."""
    moment = _now(now)
    with tx(conn):
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            return None
        job = JobRow.from_row(row)
        if job.status == "queued":
            _terminal(
                conn,
                job_id,
                from_status="queued",
                to_status="cancelled",
                result_json=None,
                error_code="cancelled",
                error_message="Tâche annulée.",
                now=moment,
            )
        elif job.status == "running" and not job.cancel_requested:
            conn.execute("UPDATE jobs SET cancel_requested=1 WHERE id=?", (job_id,))
            _audit(conn, "job.cancel_requested", job_id, {}, moment)
        fresh = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return None if fresh is None else JobRow.from_row(fresh)


def recover_interrupted(conn: sqlite3.Connection, now: datetime | None = None) -> list[str]:
    """Au démarrage : toute tâche running devient interrupted (sans lire le disque)."""
    moment = _now(now)
    with tx(conn):
        rows = conn.execute(
            "UPDATE jobs SET status='interrupted', finished_at=?, error_code='runner_restarted', "
            "error_message=? WHERE status='running' RETURNING id",
            (iso(moment), "Runner redémarré pendant l'exécution."),
        ).fetchall()
        ids = [r["id"] for r in rows]
        for job_id in ids:
            _callback_and_audit(conn, job_id, "interrupted", "runner_restarted", moment)
    return ids

"""Accès à la base SQLite : seul module qui importe `sqlite3`.

Une connexion par thread ou par requête, jamais partagée ; toute écriture en BEGIN IMMEDIATE.
Les statuts sont écrits en littéraux SQL (mêmes valeurs que le noyau d'états).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from deskgate.core.payload import duration_s
from deskgate.core.redact import redact_params, redact_signature

SCHEMA_VERSION = 2

Connection = sqlite3.Connection  # alias : les autres modules n'importent pas sqlite3

CALLBACK_DELAY_S = 2
AUDIT_PARAMS_MAX = 4096
CALLBACK_FINAL_STATES = frozenset(
    {
        "delivered",
        "delivered_duplicate",
        "abandoned_stale",
        "abandoned_rejected",
        "abandoned_exhausted",
    }
)
ABANDON_REASONS = {
    "abandoned_stale": "stale",
    "abandoned_rejected": "rejected",
    "abandoned_exhausted": "exhausted",
}


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

MIGRATION_2: tuple[str, ...] = (
    "ALTER TABLE callbacks ADD COLUMN maybe_delivered INTEGER NOT NULL DEFAULT 0 "
    "CHECK (maybe_delivered IN (0,1))",
)

MIGRATIONS: tuple[tuple[str, ...], ...] = (MIGRATION_1, MIGRATION_2)


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
    callback_url: str = field(repr=False)
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
    conn: sqlite3.Connection, event: str, job_id: str | None, detail: dict[str, Any], now: datetime
) -> None:
    conn.execute(
        "INSERT INTO audit(ts, event, job_id, detail_json) VALUES (?, ?, ?, ?)",
        (iso(now), event, job_id, json.dumps(detail, ensure_ascii=False)),
    )


def _audit_params(params_json: str) -> Any:
    """Paramètres masqués ; remplacés par un marqueur s'ils dépassent AUDIT_PARAMS_MAX."""
    masked = redact_params(json.loads(params_json))
    size = len(json.dumps(masked, ensure_ascii=False))
    if size > AUDIT_PARAMS_MAX:
        return {"truncated": True, "size": size}
    return masked


def _callback_and_audit(
    conn: sqlite3.Connection,
    job_id: str,
    to_status: str,
    error_code: str | None,
    now: datetime,
    started_at: str | None,
) -> None:
    conn.execute(
        "INSERT INTO callbacks(job_id, state, next_attempt_at, not_before) "
        "VALUES (?, 'pending', ?, ?)",
        (job_id, iso(now), iso(now + timedelta(seconds=CALLBACK_DELAY_S))),
    )
    finished_at = iso(now)
    detail = {
        "status": to_status,
        "error_code": error_code,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_s": duration_s(started_at, finished_at),
    }
    _audit(conn, f"job.{to_status}", job_id, detail, now)


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
        "WHERE id=? AND status=? RETURNING started_at",
        (to_status, iso(now), result_json, error_code, error_message, job_id, from_status),
    )
    rows = cur.fetchall()
    if len(rows) != 1:
        raise StaleTransition(job_id)
    _callback_and_audit(conn, job_id, to_status, error_code, now, rows[0]["started_at"])


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
            _audit(
                conn,
                "job.submitted",
                job_id,
                {
                    "capability": capability,
                    "client": "bearer",
                    "params": _audit_params(params_json),
                    "timeout_s": timeout_s,
                    "has_idempotency_key": idempotency_key is not None,
                },
                moment,
            )
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
            "error_message=? WHERE status='running' RETURNING id, started_at",
            (iso(moment), "Runner redémarré pendant l'exécution."),
        ).fetchall()
        ids = [r["id"] for r in rows]
        for r in rows:
            _callback_and_audit(
                conn, r["id"], "interrupted", "runner_restarted", moment, r["started_at"]
            )
    return ids


def record_refusal(
    conn: sqlite3.Connection,
    *,
    code: str,
    capability: str | None,
    job_id: str | None = None,
    now: datetime | None = None,
) -> None:
    """Audit d'une soumission refusée (sans création de tâche)."""
    with tx(conn):
        _audit(conn, "job.refused", job_id, {"code": code, "capability": capability}, _now(now))


@dataclass(frozen=True)
class CallbackClaim:
    """Rappel réclamé : l'essai est déjà inscrit en base (écriture préalable)."""

    job_id: str
    attempt: int
    last_status: int | None
    maybe_delivered_before: bool
    deadline: datetime
    capability: str
    status: str
    started_at: str | None
    finished_at: str | None
    result_json: str | None
    error_code: str | None
    error_message: str | None
    callback_url: str = field(repr=False)


def _close_callback(
    conn: sqlite3.Connection,
    job_id: str,
    state: str,
    reason: str | None,
    attempts: int,
    now: datetime,
) -> None:
    """État final du rappel : purge de la resumeUrl et audit. Dans une transaction ouverte."""
    conn.execute("UPDATE callbacks SET state=? WHERE job_id=?", (state, job_id))
    conn.execute("UPDATE jobs SET callback_url='' WHERE id=?", (job_id,))
    if state.startswith("delivered"):
        _audit(conn, "callback.delivered", job_id, {"attempts": attempts, "state": state}, now)
    else:
        _audit(conn, "callback.abandoned", job_id, {"reason": reason, "attempts": attempts}, now)


def claim_due_callback(
    conn: sqlite3.Connection, now: datetime, *, max_window_s: int
) -> CallbackClaim | None:
    """Réclame le rappel échu le plus ancien ; écrit attempts+1 et maybe_delivered=1 avant l'envoi.

    Un rappel au-delà de finished_at + max_window_s est abandonné sans envoi.
    """
    stamp = iso(now)
    with tx(conn):
        while True:
            row = conn.execute(
                "SELECT c.job_id, c.attempts, c.last_status, c.maybe_delivered, j.capability, "
                "j.status, j.started_at, j.finished_at, j.result_json, j.error_code, "
                "j.error_message, j.callback_url, c.not_before "
                "FROM callbacks c JOIN jobs j ON j.id = c.job_id "
                "WHERE c.state = 'pending' AND c.next_attempt_at <= :now AND c.not_before <= :now "
                "ORDER BY c.next_attempt_at, c.rowid LIMIT 1",
                {"now": stamp},
            ).fetchone()
            if row is None:
                return None
            deadline = datetime.fromisoformat(row["finished_at"] or row["not_before"]) + timedelta(
                seconds=max_window_s
            )
            if now >= deadline:
                _close_callback(
                    conn, row["job_id"], "abandoned_exhausted", "exhausted", row["attempts"], now
                )
                continue
            conn.execute(
                "UPDATE callbacks SET attempts = attempts + 1, maybe_delivered = 1 "
                "WHERE job_id = ?",
                (row["job_id"],),
            )
            return CallbackClaim(
                job_id=row["job_id"],
                attempt=row["attempts"] + 1,
                last_status=row["last_status"],
                maybe_delivered_before=bool(row["maybe_delivered"]),
                deadline=deadline,
                capability=row["capability"],
                status=row["status"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                result_json=row["result_json"],
                error_code=row["error_code"],
                error_message=row["error_message"],
                callback_url=row["callback_url"],
            )


def record_callback_result(
    conn: sqlite3.Connection,
    claim: CallbackClaim,
    *,
    state: str,
    decision: str,
    http_status: int | None,
    error: str | None,
    next_attempt_at: datetime | None,
    now: datetime,
    reason: str | None = None,
) -> None:
    """Enregistre l'issue d'un essai ; une réponse 4xx restaure le bit maybe_delivered."""
    restore = http_status is not None and 400 <= http_status < 500
    maybe_delivered = int(claim.maybe_delivered_before) if restore else 1
    if error:
        err: str | None = redact_signature(error)
    elif http_status is not None and not 200 <= http_status < 300:
        err = f"http_{http_status}"
    else:
        err = None
    with tx(conn):
        cur = conn.execute(
            "UPDATE callbacks SET state=?, last_status=?, last_error_redacted=?, "
            "maybe_delivered=?, next_attempt_at=COALESCE(?, next_attempt_at) "
            "WHERE job_id=? AND state='pending'",
            (
                state,
                http_status,
                err,
                maybe_delivered,
                iso(next_attempt_at) if next_attempt_at is not None else None,
                claim.job_id,
            ),
        )
        if cur.rowcount != 1:
            raise StaleTransition(claim.job_id)
        _audit(
            conn,
            "callback.attempt",
            claim.job_id,
            {
                "attempt": claim.attempt,
                "http_status": http_status,
                "error": err if error else None,
                "decision": decision,
            },
            now,
        )
        if state in CALLBACK_FINAL_STATES:
            _close_callback(
                conn,
                claim.job_id,
                state,
                reason or ABANDON_REASONS.get(state),
                claim.attempt,
                now,
            )


def abandon_callback(
    conn: sqlite3.Connection, job_id: str, *, state: str, reason: str, now: datetime
) -> None:
    """Abandon sans envoi (hôte refusé, etc.) : sans effet si le rappel n'est plus pending."""
    with tx(conn):
        row = conn.execute(
            "SELECT attempts FROM callbacks WHERE job_id=? AND state='pending'", (job_id,)
        ).fetchone()
        if row is not None:
            _close_callback(conn, job_id, state, reason, row["attempts"], now)

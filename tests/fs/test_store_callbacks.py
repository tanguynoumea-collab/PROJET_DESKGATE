"""Outbox durable : amorçage, écriture préalable, restauration, fenêtre, purge."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from _support.store_helpers import make_db, submit
from deskgate import store

pytestmark = pytest.mark.fs

T0 = datetime(2026, 10, 20, 12, tzinfo=UTC)
WINDOW = 86400


def s(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def done(conn: sqlite3.Connection, at: datetime = T0) -> None:
    job = store.claim_next(conn, at)
    assert job is not None
    store.finish(
        conn,
        job.id,
        from_status="running",
        to_status="succeeded",
        result_json="{}",
        error_code=None,
        error_message=None,
        now=at,
    )


def ready(tmp_path: Path) -> sqlite3.Connection:
    conn = make_db(tmp_path)
    submit(conn, "a")
    done(conn)
    return conn


def claim(conn: sqlite3.Connection, at: datetime) -> store.CallbackClaim:
    got = store.claim_due_callback(conn, at, max_window_s=WINDOW)
    assert got is not None
    return got


def result(
    conn: sqlite3.Connection,
    c: store.CallbackClaim,
    *,
    state: str = "pending",
    decision: str = "retry_backoff",
    http_status: int | None = None,
    error: str | None = None,
    nxt: datetime | None = None,
    reason: str | None = None,
) -> None:
    store.record_callback_result(
        conn,
        c,
        state=state,
        decision=decision,
        http_status=http_status,
        error=error,
        next_attempt_at=nxt,
        now=s(2),
        reason=reason,
    )


def row(conn: sqlite3.Connection, job_id: str = "a") -> sqlite3.Row:
    r = conn.execute("SELECT * FROM callbacks WHERE job_id=?", (job_id,)).fetchone()
    assert r is not None
    return r


def audit(conn: sqlite3.Connection, event: str) -> list[dict[str, object]]:
    rows = conn.execute("SELECT detail_json FROM audit WHERE event=? ORDER BY id", (event,))
    return [json.loads(r["detail_json"]) for r in rows]


def purged(conn: sqlite3.Connection, job_id: str = "a") -> bool:
    r = conn.execute("SELECT callback_url FROM jobs WHERE id=?", (job_id,)).fetchone()
    return bool(r[0] == "")


def test_amorcage_et_ecriture_prealable(tmp_path: Path) -> None:
    conn = ready(tmp_path)
    assert store.claim_due_callback(conn, s(1.9), max_window_s=WINDOW) is None
    c = claim(conn, s(2))
    assert (c.attempt, c.last_status, c.maybe_delivered_before) == (1, None, False)
    assert c.deadline == s(WINDOW)
    other = store.connect(tmp_path / "d.db")
    try:
        r = row(other)
        assert (r["attempts"], r["maybe_delivered"]) == (1, 1)
    finally:
        other.close()
    assert "SECRETSIG" not in repr(c)


def test_retry_5xx_et_prochain_essai(tmp_path: Path) -> None:
    conn = ready(tmp_path)
    c = claim(conn, s(2))
    result(conn, c, http_status=500, nxt=s(6))
    r = row(conn)
    assert (r["last_status"], r["last_error_redacted"], r["maybe_delivered"]) == (
        500,
        "http_500",
        1,
    )
    assert store.claim_due_callback(conn, s(5), max_window_s=WINDOW) is None
    c2 = claim(conn, s(6))
    assert (c2.attempt, c2.last_status) == (2, 500)


@pytest.mark.parametrize(
    ("status", "error", "expected"),
    [(409, None, 0), (404, None, 0), (503, None, 1), (None, "ReadTimeout", 1)],
)
def test_restauration_du_bit(
    tmp_path: Path, status: int | None, error: str | None, expected: int
) -> None:
    conn = ready(tmp_path)
    c = claim(conn, s(2))
    assert c.maybe_delivered_before is False
    result(conn, c, http_status=status, error=error, nxt=s(10))
    r = row(conn)
    assert r["maybe_delivered"] == expected
    if error:
        assert r["last_error_redacted"] == error


def test_erreur_masquee(tmp_path: Path) -> None:
    conn = ready(tmp_path)
    c = claim(conn, s(2))
    result(conn, c, error="RuntimeError signature=SECRETSIG", nxt=s(10))
    assert "SECRETSIG" not in row(conn)["last_error_redacted"]
    for r in conn.execute("SELECT detail_json FROM audit"):
        assert "SECRETSIG" not in (r["detail_json"] or "")


def test_final_livre_purge_et_audit(tmp_path: Path) -> None:
    conn = ready(tmp_path)
    c = claim(conn, s(2))
    result(conn, c, state="delivered", decision="delivered", http_status=200)
    assert row(conn)["state"] == "delivered"
    assert purged(conn)
    assert audit(conn, "callback.attempt") == [
        {"attempt": 1, "http_status": 200, "error": None, "decision": "delivered"}
    ]
    assert audit(conn, "callback.delivered") == [{"attempts": 1, "state": "delivered"}]
    with pytest.raises(store.StaleTransition):
        result(conn, c, state="delivered", decision="delivered", http_status=200)


def test_final_abandonne_raison(tmp_path: Path) -> None:
    conn = ready(tmp_path)
    c = claim(conn, s(2))
    result(conn, c, state="abandoned_stale", decision="abandon", http_status=404)
    assert audit(conn, "callback.abandoned") == [{"reason": "stale", "attempts": 1}]


def test_final_abandonne_raison_explicite(tmp_path: Path) -> None:
    conn = ready(tmp_path)
    c = claim(conn, s(2))
    result(conn, c, state="abandoned_rejected", decision="abandon", reason="host_not_allowed")
    assert audit(conn, "callback.abandoned")[0]["reason"] == "host_not_allowed"


def test_fenetre_sans_dernier_envoi(tmp_path: Path) -> None:
    conn = ready(tmp_path)
    assert store.claim_due_callback(conn, s(60), max_window_s=60) is None
    assert row(conn)["state"] == "abandoned_exhausted"
    assert audit(conn, "callback.abandoned") == [{"reason": "exhausted", "attempts": 0}]
    assert purged(conn)


def test_fenetre_puis_suivante(tmp_path: Path) -> None:
    conn = ready(tmp_path)
    submit(conn, "b")
    done(conn, s(50))
    got = store.claim_due_callback(conn, s(60), max_window_s=60)
    assert got is not None
    assert got.job_id == "b"
    assert row(conn, "a")["state"] == "abandoned_exhausted"


def test_abandon_direct(tmp_path: Path) -> None:
    conn = ready(tmp_path)
    store.abandon_callback(
        conn, "a", state="abandoned_rejected", reason="host_not_allowed", now=s(3)
    )
    assert row(conn)["state"] == "abandoned_rejected"
    assert purged(conn)
    assert audit(conn, "callback.abandoned")[0]["reason"] == "host_not_allowed"
    store.abandon_callback(conn, "a", state="abandoned_stale", reason="stale", now=s(4))
    assert len(audit(conn, "callback.abandoned")) == 1


def test_ordre_next_attempt_puis_rowid(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    for name in ("a", "b", "c"):
        submit(conn, name)
        done(conn)
    conn.execute("UPDATE callbacks SET next_attempt_at=? WHERE job_id='c'", (store.iso(s(-5)),))
    order = []
    for _ in range(3):
        c = claim(conn, s(10))
        order.append(c.job_id)
        result(conn, c, state="delivered", decision="delivered", http_status=200)
    assert order == ["c", "a", "b"]


def test_audit_callback_sans_secret(tmp_path: Path) -> None:
    conn = ready(tmp_path)
    c = claim(conn, s(2))
    result(conn, c, state="delivered", decision="delivered", http_status=200)
    for r in conn.execute("SELECT detail_json FROM audit WHERE event LIKE 'callback.%'"):
        assert "webhook-waiting" not in r["detail_json"]
        assert "SECRETSIG" not in r["detail_json"]

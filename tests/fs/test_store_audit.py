"""Audit enrichi (SEC-06) : soumission, fin, refus ; aucun secret."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from _support.store_helpers import CALLBACK_URL, make_db, submit

from deskgate import store

pytestmark = pytest.mark.fs

T0 = datetime(2026, 10, 20, 12, tzinfo=UTC)


def _detail(conn: sqlite3.Connection, event: str) -> dict[str, object]:
    row = conn.execute(
        "SELECT detail_json FROM audit WHERE event=? ORDER BY id DESC LIMIT 1", (event,)
    ).fetchone()
    assert row is not None
    return dict(json.loads(row["detail_json"]))


def test_submitted_complet_et_masque(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    submit(conn, "a")
    detail = _detail(conn, "job.submitted")
    assert set(detail) == {"capability", "client", "params", "timeout_s", "has_idempotency_key"}
    assert detail["params"] == {"secret_param": "***"}
    for row in conn.execute("SELECT detail_json FROM audit"):
        text = row["detail_json"] or ""
        assert "PARAMVAL" not in text
        assert "SECRETSIG" not in text
        assert CALLBACK_URL not in text


def test_params_trop_gros_tronques(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    big = json.dumps({"note": "x" * 5000})
    store.insert_job(
        conn,
        job_id="a",
        capability="c",
        params_json=big,
        timeout_s=1,
        resource="default",
        idempotency_key=None,
        callback_url=CALLBACK_URL,
        work_dir="w",
    )
    params = _detail(conn, "job.submitted")["params"]
    assert isinstance(params, dict)
    assert params["truncated"] is True
    assert params["size"] > store.AUDIT_PARAMS_MAX


def test_succeeded_porte_duree(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    submit(conn, "a")
    store.claim_next(conn, T0)
    store.finish(
        conn,
        "a",
        from_status="running",
        to_status="succeeded",
        result_json="{}",
        error_code=None,
        error_message=None,
        now=T0 + timedelta(seconds=1.5),
    )
    detail = _detail(conn, "job.succeeded")
    assert detail["duration_s"] == 1.5
    assert detail["started_at"] == store.iso(T0)
    assert detail["finished_at"] == store.iso(T0 + timedelta(seconds=1.5))


def test_cancelled_depuis_queued_sans_duree(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    submit(conn, "a")
    store.request_cancel(conn, "a", T0)
    detail = _detail(conn, "job.cancelled")
    assert detail["duration_s"] is None
    assert detail["started_at"] is None


def test_interrupted_porte_debut(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    submit(conn, "a")
    store.claim_next(conn, T0)
    store.recover_interrupted(conn, T0 + timedelta(seconds=3))
    detail = _detail(conn, "job.interrupted")
    assert detail["started_at"] == store.iso(T0)
    assert detail["duration_s"] == 3.0


def test_refus_audite(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    store.record_refusal(conn, code="capability_not_found", capability="x", now=T0)
    row = conn.execute("SELECT job_id, detail_json FROM audit WHERE event='job.refused'").fetchone()
    assert row["job_id"] is None
    assert json.loads(row["detail_json"]) == {"code": "capability_not_found", "capability": "x"}


def test_repr_sans_secret(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    submit(conn, "a")
    job = store.get_job(conn, "a")
    assert job is not None
    text = repr(job)
    assert "signature" not in text
    assert "webhook-waiting" not in text

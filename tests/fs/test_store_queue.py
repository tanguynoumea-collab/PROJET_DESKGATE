"""File : ordre, exclusivité, idempotence, fin transactionnelle."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from _support.store_helpers import CALLBACK_URL, count, make_db, submit, succeed
from deskgate import store

pytestmark = pytest.mark.fs


def test_ordre_et_exclusivite(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    for n in ("a", "b", "c"):
        submit(conn, n)
    first = store.claim_next(conn)
    assert first is not None
    assert first.id == "a"
    assert first.status == "running"
    assert first.started_at is not None
    assert store.claim_next(conn) is None
    succeed(conn, "a")
    second = store.claim_next(conn)
    assert second is not None
    assert second.id == "b"


def test_six_threads_un_seul_gagnant(tmp_path: Path) -> None:
    path = tmp_path / "d.db"
    conn = store.open_db(path)
    submit(conn, "a")
    submit(conn, "b")
    barrier = threading.Barrier(6)
    results: list[object] = []
    lock = threading.Lock()

    def work() -> None:
        c = store.connect(path)
        try:
            barrier.wait()
            r = store.claim_next(c)
            with lock:
                results.append(r)
        finally:
            c.close()

    threads = [threading.Thread(target=work) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len([r for r in results if r is not None]) == 1
    assert count(conn, "jobs", "status='running'") == 1
    conn.close()


def test_idempotence(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    submit(conn, "a", key="k")
    with pytest.raises(store.IdempotencyConflict) as err:
        submit(conn, "b", key="k")
    assert err.value.existing_job_id == "a"
    submit(conn, "c", key="k", capability="autre")
    submit(conn, "d")
    submit(conn, "e")
    claimed = store.claim_next(conn)
    assert claimed is not None
    succeed(conn, "a")
    submit(conn, "f", key="k")


def test_finish_ecrit_tout_et_stale(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    submit(conn, "a")
    store.claim_next(conn)
    now = datetime(2026, 10, 20, 12, 0, 0, tzinfo=UTC)
    store.finish(
        conn,
        "a",
        from_status="running",
        to_status="failed",
        result_json='{"x":1}',
        error_code="nonzero_exit",
        error_message="échec",
        now=now,
    )
    job = store.get_job(conn, "a")
    assert job is not None
    assert (job.status, job.result_json, job.error_code, job.error_message) == (
        "failed",
        '{"x":1}',
        "nonzero_exit",
        "échec",
    )
    assert job.finished_at == "2026-10-20T12:00:00.000Z"
    cb = conn.execute("SELECT * FROM callbacks WHERE job_id='a'").fetchone()
    assert cb["state"] == "pending"
    assert cb["not_before"] == store.iso(now + timedelta(seconds=2))
    assert count(conn, "audit", "event='job.failed'") == 1
    with pytest.raises(store.StaleTransition):
        succeed(conn, "a")
    assert count(conn, "callbacks") == 1
    assert count(conn, "audit", "event='job.succeeded'") == 0


def test_update_progress_seulement_running(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    submit(conn, "a")
    store.update_progress(conn, "a", 10.0, "x")
    job = store.get_job(conn, "a")
    assert job is not None
    assert job.progress_pct is None
    store.claim_next(conn)
    store.update_progress(conn, "a", 40.0, "étape")
    job = store.get_job(conn, "a")
    assert job is not None
    assert (job.progress_pct, job.progress_message) == (40.0, "étape")


def test_audit_sans_secret(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    submit(conn, "a")
    store.claim_next(conn)
    succeed(conn, "a")
    rows = conn.execute("SELECT detail_json FROM audit").fetchall()
    assert rows
    for row in rows:
        detail = row["detail_json"] or ""
        assert CALLBACK_URL not in detail
        assert "SECRETSIG" not in detail
        assert "PARAMVAL" not in detail

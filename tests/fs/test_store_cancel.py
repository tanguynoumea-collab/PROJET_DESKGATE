"""Annulation atomique."""

from __future__ import annotations

from pathlib import Path

import pytest

from _support.store_helpers import count, make_db, submit
from deskgate import store

pytestmark = pytest.mark.fs


def test_cancel_queued(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    submit(conn, "a")
    job = store.request_cancel(conn, "a")
    assert job is not None
    assert job.status == "cancelled"
    assert job.error_code == "cancelled"
    assert count(conn, "callbacks", "state='pending'") == 1
    assert count(conn, "audit", "event='job.cancelled'") == 1


def test_cancel_running_puis_idempotent(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    submit(conn, "a")
    store.claim_next(conn)
    job = store.request_cancel(conn, "a")
    assert job is not None
    assert job.status == "running"
    assert job.cancel_requested is True
    assert store.is_cancel_requested(conn, "a")
    assert count(conn, "audit", "event='job.cancel_requested'") == 1
    store.request_cancel(conn, "a")
    assert count(conn, "audit", "event='job.cancel_requested'") == 1


def test_cancel_terminale_et_inconnue(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    submit(conn, "a")
    store.request_cancel(conn, "a")
    before = count(conn, "audit")
    job = store.request_cancel(conn, "a")
    assert job is not None
    assert job.status == "cancelled"
    assert count(conn, "audit") == before
    assert store.request_cancel(conn, "zzz") is None

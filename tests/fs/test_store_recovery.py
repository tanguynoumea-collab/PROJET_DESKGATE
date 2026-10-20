"""Recovery au démarrage."""

from __future__ import annotations

from pathlib import Path

import pytest

from _support.store_helpers import count, make_db, submit, succeed
from deskgate import store

pytestmark = pytest.mark.fs


def test_recover_interrupted(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    submit(conn, "done")
    store.claim_next(conn)
    succeed(conn, "done")
    submit(conn, "run")
    store.claim_next(conn)
    submit(conn, "wait")
    cb_before = count(conn, "callbacks")
    assert store.recover_interrupted(conn) == ["run"]
    run = store.get_job(conn, "run")
    assert run is not None
    assert run.status == "interrupted"
    assert run.error_code == "runner_restarted"
    assert count(conn, "callbacks") == cb_before + 1
    assert count(conn, "callbacks", "job_id='run' AND state='pending'") == 1
    assert count(conn, "audit", "event='job.interrupted'") == 1
    wait = store.get_job(conn, "wait")
    assert wait is not None
    assert wait.status == "queued"
    done = store.get_job(conn, "done")
    assert done is not None
    assert done.status == "succeeded"
    assert store.recover_interrupted(conn) == []

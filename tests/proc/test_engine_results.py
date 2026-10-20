"""Verdicts et artefacts de l'engine avec de vrais sous-processus dans un Job Object."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest
from _support.jobs import get, make_config, run_until_terminal, submit

import deskgate_sdk.run as sdk_run
from deskgate import store
from deskgate.core.config import RunnerConfig
from deskgate.engine import Engine

pytestmark = [
    pytest.mark.proc,
    pytest.mark.skipif(sys.platform != "win32", reason="Job Object Windows"),
    pytest.mark.timeout(60),
]

Env = tuple[Engine, Path, RunnerConfig]


def test_artifact_ok(real_engine: Env) -> None:
    engine, db, cfg = real_engine
    job_id = submit(db, cfg, "demo.artifact_ok")
    row = run_until_terminal(engine, db, job_id)
    assert row.status == "succeeded", row.error_message
    work = Path(row.work_dir)
    assert work.parent.name == "travail"
    for name in ("input.json", "job.log", "result.json", "sortie.txt"):
        assert (work / name).exists(), name
    assert row.result_json is not None
    result = json.loads(row.result_json)
    assert result["artifacts"] == [{"kind": "txt", "path": f"/data/travail/{job_id}/sortie.txt"}]


def test_sleep_progress_et_journal(real_engine: Env) -> None:
    engine, db, cfg = real_engine
    job_id = submit(db, cfg, "demo.sleep", {"n": 0.3})
    row = run_until_terminal(engine, db, job_id)
    assert row.status == "succeeded"
    assert row.progress_pct
    log = (Path(row.work_dir) / "job.log").read_text(encoding="utf-8", errors="replace")
    assert "début du sommeil" in log


def test_artifact_outside(real_engine: Env) -> None:
    engine, db, cfg = real_engine
    row = run_until_terminal(engine, db, submit(db, cfg, "demo.artifact_outside"))
    assert row.status == "failed"
    assert row.error_code == "artifact_outside_roots"


@pytest.mark.parametrize(
    ("mode", "code"),
    [
        ("garbage", "invalid_result"),
        ("missing", "missing_result"),
        ("huge", "result_too_large"),
        ("not_dict", "plugin_error"),
    ],
)
def test_bad_result(real_engine: Env, mode: str, code: str) -> None:
    engine, db, cfg = real_engine
    row = run_until_terminal(engine, db, submit(db, cfg, "demo.bad_result", {"mode": mode}))
    assert row.status == "failed"
    assert row.error_code == code


def test_fail(real_engine: Env) -> None:
    engine, db, cfg = real_engine
    row = run_until_terminal(engine, db, submit(db, cfg, "demo.fail"))
    assert row.status == "failed"
    assert row.error_code == "plugin_error"
    assert row.error_message is not None
    assert "ValueError" in row.error_message
    log = (Path(row.work_dir) / "job.log").read_text(encoding="utf-8", errors="replace")
    assert "ValueError" in log


def test_exit_code(real_engine: Env) -> None:
    engine, db, cfg = real_engine
    row = run_until_terminal(engine, db, submit(db, cfg, "demo.exit_code", {"code": 3}))
    assert row.status == "failed"
    assert row.error_code == "nonzero_exit"


def test_chatty(real_engine: Env) -> None:
    engine, db, cfg = real_engine
    row = run_until_terminal(engine, db, submit(db, cfg, "demo.chatty", {"mb": 4}))
    assert row.status == "succeeded", row.error_message
    assert (Path(row.work_dir) / "job.log").stat().st_size >= 8 * 1024 * 1024


def test_spawn_failed_puis_suite(tmp_path: Path) -> None:
    cfg = make_config(
        tmp_path,
        caps={
            "demo.absent": {
                "entry": "deskgate_fakes:sleep",
                "python": str(tmp_path / "absent" / "python.exe"),
            },
            "demo.sleep": {"entry": "deskgate_fakes:sleep"},
        },
    )
    db = tmp_path / "home" / "deskgate.db"
    store.open_db(db).close()
    engine = Engine(
        db_path=db,
        config=cfg,
        worker_script=Path(sdk_run.__file__).resolve(),
        poll=0.05,
        grace=1.0,
    )
    try:
        row = run_until_terminal(engine, db, submit(db, cfg, "demo.absent"))
        assert row.status == "failed"
        assert row.error_code == "spawn_failed"
        row2 = run_until_terminal(engine, db, submit(db, cfg, "demo.sleep", {"n": 0.1}))
        assert row2.status == "succeeded"
    finally:
        engine.stop()


def test_une_a_la_fois_dans_l_ordre(real_engine: Env) -> None:
    engine, db, cfg = real_engine
    a = submit(db, cfg, "demo.sleep", {"n": 0.2})
    b = submit(db, cfg, "demo.sleep", {"n": 0.2})
    run_until_terminal(engine, db, a)
    rb = run_until_terminal(engine, db, b)
    ra = get(db, a)
    assert ra.finished_at is not None
    assert rb.started_at is not None
    fin_a = datetime.fromisoformat(ra.finished_at)
    debut_b = datetime.fromisoformat(rb.started_at)
    assert debut_b >= fin_a

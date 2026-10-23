"""Worker deskgate_sdk/run.py lancé en vrai sous-processus dans un Job Object."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest

import deskgate_sdk.run as sdk_run
from deskgate.core.env import build_env
from deskgate.core.worker_protocol import ResultError, ResultOk, parse_event, parse_result
from deskgate.jobobject import create_job, spawn_in_job

pytestmark = [
    pytest.mark.proc,
    pytest.mark.skipif(sys.platform != "win32", reason="Job Object Windows"),
    pytest.mark.timeout(60),
]

FAKES = Path(__file__).resolve().parents[1] / "fake_plugins"
RUN_PY = Path(sdk_run.__file__).resolve()


def _lancer(tmp_path: Path, fn: str, params: dict[str, Any]) -> tuple[Any, Any]:
    work = tmp_path / "work"
    work.mkdir()
    (work / "input.json").write_text(
        json.dumps(
            {
                "protocol": 1,
                "job_id": "a1b2c3d4e5f6",
                "capability": "demo",
                "entry": f"deskgate_fakes:{fn}",
                "params": params,
                "work_dir": str(work),
                "sys_path": [str(FAKES)],
            }
        ),
        encoding="utf-8",
    )
    job = create_job()
    p = spawn_in_job(
        job,
        [sys.executable, "-X", "utf8", str(RUN_PY), "--input", str(work / "input.json")],
        cwd=str(work),
        log_path=str(work / "job.log"),
        env=build_env(os.environ),
    )
    return job, p


def _resultat(work: Path) -> ResultOk | ResultError:
    etat, res = parse_result((work / "result.json").read_bytes())
    assert res is not None, etat
    return res


def test_succes_evenements_et_log(tmp_path: Path) -> None:
    job, p = _lancer(tmp_path, "sleep", {"n": 0.2})
    try:
        assert p.wait(30) == 0
    finally:
        job.terminate()
        job.close()
    work = tmp_path / "work"
    res = _resultat(work)
    assert isinstance(res, ResultOk)
    lignes = (work / "events.jsonl").read_bytes().splitlines()
    assert any(getattr(parse_event(x), "type", None) == "progress" for x in lignes)
    assert "début du sommeil" in (work / "job.log").read_text(encoding="utf-8")


def test_exception_du_plugin(tmp_path: Path) -> None:
    job, p = _lancer(tmp_path, "fail", {})
    try:
        assert p.wait(30) == 1
    finally:
        job.terminate()
        job.close()
    work = tmp_path / "work"
    res = _resultat(work)
    assert isinstance(res, ResultError)
    assert res.error.type == "ValueError"
    assert "ValueError" in (work / "job.log").read_text(encoding="utf-8")


def test_resultat_nan_refuse_par_le_sdk(tmp_path: Path) -> None:
    job, p = _lancer(tmp_path, "nan_result", {})
    try:
        assert p.wait(30) == 1
    finally:
        job.terminate()
        job.close()
    work = tmp_path / "work"
    res = _resultat(work)
    assert isinstance(res, ResultError)
    assert res.error.type == "ValueError"
    assert b"NaN" not in (work / "result.json").read_bytes()


def test_progression_nan_refusee(tmp_path: Path) -> None:
    job, p = _lancer(tmp_path, "nan_progress", {})
    try:
        assert p.wait(30) == 1
    finally:
        job.terminate()
        job.close()
    work = tmp_path / "work"
    res = _resultat(work)
    assert isinstance(res, ResultError)
    assert res.error.type == "ValueError"
    events = work / "events.jsonl"
    assert b"NaN" not in (events.read_bytes() if events.exists() else b"")


def test_resultat_non_dict(tmp_path: Path) -> None:
    job, p = _lancer(tmp_path, "bad_result", {"mode": "not_dict"})
    try:
        assert p.wait(30) == 1
    finally:
        job.terminate()
        job.close()
    res = _resultat(tmp_path / "work")
    assert isinstance(res, ResultError)
    assert res.error.type == "TypeError"


def test_annulation_par_cancel_flag(tmp_path: Path) -> None:
    job, p = _lancer(tmp_path, "sleep", {"n": 30})
    work = tmp_path / "work"
    try:
        time.sleep(1.0)
        (work / "cancel.flag").write_text("", encoding="utf-8")
        debut = time.monotonic()
        assert p.wait(10) == 0
        assert time.monotonic() - debut < 3
    finally:
        job.terminate()
        job.close()
    res = _resultat(work)
    assert isinstance(res, ResultOk)
    assert res.summary["cancelled"] is True


def test_aucune_variable_deskgate_vue_par_le_plugin(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DESKGATE_TOKEN", "secret")
    job, p = _lancer(tmp_path, "sleep", {"n": 0.1, "report_env": True})
    try:
        assert p.wait(30) == 0
    finally:
        job.terminate()
        job.close()
    res = _resultat(tmp_path / "work")
    assert isinstance(res, ResultOk)
    assert res.summary["deskgate_env"] == []
    assert res.summary["pythonutf8"] == "1"

"""CB-04 : un résumé trop gros est déporté dans summary.json avant la transaction terminale."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from _support.jobs import FakeClock, FakeLauncher, get, make_config, run_until_terminal, submit
from deskgate import store
from deskgate.core.worker_protocol import RESULT_MAX_BYTES
from deskgate.engine import Engine, LaunchSpec

pytestmark = pytest.mark.fs

WORKER = Path("C:/fake/run.py")


class Env:
    def __init__(self, tmp_path: Path, before_launch=None, **engine_kw: object) -> None:  # type: ignore[no-untyped-def]
        self.db = tmp_path / "d.db"
        store.open_db(self.db).close()
        self.cfg = make_config(tmp_path)
        self.result: object = None
        self.before = before_launch
        self.launcher = FakeLauncher(self._launch)
        self.engine = Engine(
            db_path=self.db,
            config=self.cfg,
            worker_script=WORKER,
            launcher=self.launcher,
            clock=FakeClock(),
            poll=5.0,
            grace=2.0,
            base_env={"PATH": "x"},
            **engine_kw,  # type: ignore[arg-type]
        )

    def _launch(self, spec: LaunchSpec) -> None:
        if self.before is not None:
            self.before(spec)
        Path(spec.cwd, "result.json").write_text(
            json.dumps(self.result, separators=(",", ":")), encoding="utf-8"
        )

    def run(self) -> store.JobRow:
        job_id = submit(self.db, self.cfg, "demo.sleep")
        self.engine.tick()
        self.launcher.procs[0].exit_code = 0
        return run_until_terminal(self.engine, self.db, job_id)

    def work_dir(self, job_id: str) -> Path:
        return Path(get(self.db, job_id).work_dir)


def _result(summary: object) -> dict[str, object]:
    return {"protocol": 1, "ok": True, "summary": summary, "data": {}, "artifacts": []}


def test_petit_plafond_deporte_le_resume(tmp_path: Path) -> None:
    env = Env(tmp_path, callback_max_bytes=2048)
    env.result = _result({"text": "x" * 10_000})
    row = env.run()
    assert row.status == "succeeded"
    assert row.result_json is not None
    result = json.loads(row.result_json)
    assert result["summary"] == {"path": f"/data/travail/{row.id}/summary.json", "truncated": True}
    work = Path(row.work_dir)
    assert json.loads((work / "summary.json").read_text(encoding="utf-8")) == {"text": "x" * 10_000}
    assert not (work / "summary.json.tmp").exists()
    assert result["data"] == {}
    assert result["artifacts"] == []


def test_petit_resume_inchange(tmp_path: Path) -> None:
    env = Env(tmp_path)
    env.result = _result({"n": 1})
    row = env.run()
    assert row.result_json is not None
    assert json.loads(row.result_json)["summary"] == {"n": 1}
    assert not (Path(row.work_dir) / "summary.json").exists()


def test_borne_reelle_un_mio(tmp_path: Path) -> None:
    env = Env(tmp_path)
    env.result = _result({"text": "x" * (RESULT_MAX_BYTES - 100)})
    row = env.run()
    assert row.status == "succeeded"
    assert row.result_json is not None
    assert json.loads(row.result_json)["summary"]["truncated"] is True


def test_echec_ecriture_garde_succeeded(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    def block(spec: LaunchSpec) -> None:
        Path(spec.cwd, "summary.json").mkdir()

    env = Env(tmp_path, before_launch=block, callback_max_bytes=2048)
    env.result = _result({"text": "SECRET-CONTENU" * 1000})
    with caplog.at_level(logging.WARNING, logger="deskgate.engine"):
        row = env.run()
    assert row.status == "succeeded"
    assert row.result_json is not None
    assert json.loads(row.result_json)["summary"] == {
        "truncated": True,
        "error": "summary_write_failed",
    }
    assert "summary.json" in caplog.text
    assert "SECRET-CONTENU" not in caplog.text

"""Tours de l'engine sans processus réel : faux launcher, horloge et horloge murale injectées."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from _support.jobs import (
    FakeClock,
    FakeJob,
    FakeLauncher,
    FakeProc,
    get,
    make_config,
    submit,
)
from deskgate import store
from deskgate.core.config import RunnerConfig
from deskgate.core.worker_protocol import WorkerInput
from deskgate.engine import Engine, LaunchSpec

pytestmark = pytest.mark.fs

WORKER = Path("C:/fake/run.py")
GRACE = 2.0


class Env:
    def __init__(self, tmp_path: Path, launcher: FakeLauncher | None = None) -> None:
        self.db = tmp_path / "d.db"
        store.open_db(self.db).close()
        self.cfg: RunnerConfig = make_config(tmp_path)
        self.launcher = launcher or FakeLauncher()
        self.clock = FakeClock()
        self.engine = Engine(
            db_path=self.db,
            config=self.cfg,
            worker_script=WORKER,
            launcher=self.launcher,
            clock=self.clock,
            poll=5.0,
            grace=GRACE,
            base_env={"PATH": "x", "DESKGATE_SECRET": "nope"},
        )

    def submit(self, cap: str = "demo.sleep", **kw: object) -> str:
        return submit(self.db, self.cfg, cap, **kw)  # type: ignore[arg-type]

    def row(self, job_id: str) -> store.JobRow:
        return get(self.db, job_id)

    def finish_proc(self, index: int = 0, code: int = 0) -> None:
        self.launcher.procs[index].exit_code = code


def write_result(spec: LaunchSpec, obj: object) -> None:
    Path(spec.cwd, "result.json").write_text(json.dumps(obj), encoding="utf-8")


def ok_result(artifacts: list[dict[str, str]] | None = None) -> dict[str, object]:
    return {
        "protocol": 1,
        "ok": True,
        "summary": {"n": 1},
        "data": {},
        "artifacts": artifacts or [],
    }


def test_ordre_et_lancement(tmp_path: Path) -> None:
    env = Env(tmp_path, FakeLauncher(lambda s: write_result(s, ok_result())))
    a = env.submit(params={"n": 1})
    b = env.submit()
    env.engine.tick()
    assert env.row(a).status == "running"
    assert env.row(b).status == "queued"
    assert env.engine.running_job_id == a
    assert len(env.launcher.specs) == 1
    spec = env.launcher.specs[0]
    work_dir = env.row(a).work_dir
    cap = env.cfg.capabilities["demo.sleep"]
    assert spec.argv == [
        cap.python,
        "-X",
        "utf8",
        str(WORKER),
        "--input",
        str(Path(work_dir) / "input.json"),
    ]
    assert Path(spec.cwd) == Path(work_dir)
    assert Path(spec.log_path) == Path(work_dir) / "job.log"
    assert "DESKGATE_SECRET" not in spec.env
    raw = Path(work_dir, "input.json").read_text(encoding="utf-8")
    parsed = WorkerInput.model_validate_json(raw)
    assert parsed.entry == "deskgate_fakes:sleep"
    assert parsed.params == {"n": 1}
    assert parsed.sys_path == list(cap.pythonpath)
    assert Path(parsed.work_dir).is_absolute()
    assert "SECRET-SIG" not in raw
    assert "callback" not in raw

    env.finish_proc()
    env.engine.tick()
    done = env.row(a)
    assert done.status == "succeeded"
    assert json.loads(done.result_json or "{}")["summary"] == {"n": 1}
    job = env.launcher.jobs[0]
    assert job.terminated == 1
    assert job.closed == 1
    assert env.engine.running_job_id is None
    env.engine.tick()
    assert env.row(b).status == "running"


def test_progression_ligne_incomplete(tmp_path: Path) -> None:
    env = Env(tmp_path)
    a = env.submit()
    env.engine.tick()
    events = Path(env.row(a).work_dir, "events.jsonl")
    events.write_bytes(b'{"type": "progress", "pct": 40, "message": "m"}\n{"type": "progr')
    env.engine.tick()
    row = env.row(a)
    assert row.progress_pct == 40.0
    assert row.progress_message == "m"
    with open(events, "ab") as f:
        f.write(b'ess", "pct": 70}\n')
    env.engine.tick()
    assert env.row(a).progress_pct == 70.0


def test_artefact_valide_en_chemin_conteneur(tmp_path: Path) -> None:
    def on_launch(spec: LaunchSpec) -> None:
        Path(spec.cwd, "sortie.txt").write_text("x", encoding="utf-8")
        write_result(spec, ok_result([{"kind": "txt", "path": "sortie.txt"}]))

    env = Env(tmp_path, FakeLauncher(on_launch))
    a = env.submit()
    env.engine.tick()
    env.finish_proc()
    env.engine.tick()
    row = env.row(a)
    assert row.status == "succeeded", row.error_message
    artifacts = json.loads(row.result_json or "{}")["artifacts"]
    assert artifacts == [{"kind": "txt", "path": f"/data/travail/{a}/sortie.txt"}]


def test_artefact_hors_racines(tmp_path: Path) -> None:
    env = Env(
        tmp_path,
        FakeLauncher(
            lambda s: write_result(s, ok_result([{"kind": "x", "path": "C:/Windows/win.ini"}]))
        ),
    )
    a = env.submit()
    env.engine.tick()
    env.finish_proc()
    env.engine.tick()
    row = env.row(a)
    assert row.status == "failed"
    assert row.error_code == "artifact_outside_roots"
    assert row.result_json is None


def test_result_absent(tmp_path: Path) -> None:
    env = Env(tmp_path)
    a = env.submit()
    env.engine.tick()
    env.finish_proc()
    env.engine.tick()
    assert env.row(a).error_code == "missing_result"


def test_erreur_du_plugin(tmp_path: Path) -> None:
    err = {"protocol": 1, "ok": False, "error": {"type": "ValueError", "message": "boum"}}
    env = Env(tmp_path, FakeLauncher(lambda s: write_result(s, err)))
    a = env.submit()
    env.engine.tick()
    env.finish_proc(code=1)
    env.engine.tick()
    row = env.row(a)
    assert row.status == "failed"
    assert row.error_code == "plugin_error"
    assert "ValueError" in (row.error_message or "")


def test_result_trop_gros(tmp_path: Path) -> None:
    def on_launch(spec: LaunchSpec) -> None:
        Path(spec.cwd, "result.json").write_bytes(b" " * (1_048_576 + 10))

    env = Env(tmp_path, FakeLauncher(on_launch))
    a = env.submit()
    env.engine.tick()
    env.finish_proc()
    env.engine.tick()
    assert env.row(a).error_code == "result_too_large"


def test_echec_de_lancement_puis_suivante(tmp_path: Path) -> None:
    calls: list[int] = []

    def on_launch(spec: LaunchSpec) -> None:
        calls.append(1)
        if len(calls) == 1:
            raise OSError("introuvable")

    env = Env(tmp_path, FakeLauncher(on_launch))
    a = env.submit()
    b = env.submit()
    env.engine.tick()
    row = env.row(a)
    assert row.status == "failed"
    assert row.error_code == "spawn_failed"
    assert "OSError" in (row.error_message or "")
    assert env.row(b).status == "queued"
    env.engine.tick()
    assert env.row(b).status == "running"


def test_capacite_retiree(tmp_path: Path) -> None:
    env = Env(tmp_path)
    a = env.submit()
    env.engine._config = make_config(tmp_path, caps={})
    env.engine.tick()
    row = env.row(a)
    assert row.status == "failed"
    assert row.error_code == "spawn_failed"
    assert not env.launcher.specs


def test_exception_de_suivi(tmp_path: Path) -> None:
    env = Env(tmp_path)
    a = env.submit()
    b = env.submit()
    env.engine.tick()

    def boom() -> int | None:
        raise RuntimeError("poll cassé")

    env.launcher.procs[0].poll = boom  # type: ignore[method-assign]
    env.engine.tick()
    row = env.row(a)
    assert row.status == "failed"
    assert row.error_code == "engine_error"
    assert env.launcher.jobs[0].terminated == 1
    assert env.launcher.jobs[0].closed == 1
    env.engine.tick()
    assert env.row(b).status == "running"


def test_echeance(tmp_path: Path) -> None:
    env = Env(tmp_path)
    a = env.submit(timeout_s=30)
    env.engine.tick()
    env.clock.advance(29)
    env.engine.tick()
    assert env.row(a).status == "running"
    env.clock.advance(1)
    env.engine.tick()
    row = env.row(a)
    assert row.status == "timeout"
    assert row.error_code == "timeout"
    assert env.launcher.jobs[0].terminated == 1
    assert env.launcher.jobs[0].closed == 1


def test_annulation_avec_grace(tmp_path: Path) -> None:
    env = Env(tmp_path)
    a = env.submit()
    env.engine.tick()
    conn = store.connect(env.db)
    store.request_cancel(conn, a)
    conn.close()
    env.engine.tick()
    assert Path(env.row(a).work_dir, "cancel.flag").exists()
    env.clock.advance(GRACE - 0.1)
    env.engine.tick()
    assert env.row(a).status == "running"
    env.clock.advance(0.2)
    env.engine.tick()
    row = env.row(a)
    assert row.status == "cancelled"
    assert env.launcher.jobs[0].terminated == 1


def test_annulation_cooperative(tmp_path: Path) -> None:
    env = Env(tmp_path, FakeLauncher(lambda s: write_result(s, ok_result())))
    a = env.submit()
    env.engine.tick()
    conn = store.connect(env.db)
    store.request_cancel(conn, a)
    conn.close()
    env.engine.tick()
    env.finish_proc()
    env.engine.tick()
    assert env.row(a).status == "cancelled"
    assert env.launcher.jobs[0].terminated == 1


def test_annulation_puis_echeance_pendant_la_grace(tmp_path: Path) -> None:
    env = Env(tmp_path)
    a = env.submit(timeout_s=10)
    env.engine.tick()
    conn = store.connect(env.db)
    store.request_cancel(conn, a)
    conn.close()
    env.engine.tick()
    env.clock.advance(11)  # échéance dépassée ; la grâce (2 s) l'est aussi
    env.engine.tick()
    row = env.row(a)
    assert row.status == "cancelled"
    assert row.error_code == "cancelled"


@pytest.mark.timeout(30)
def test_reveil_immediat(tmp_path: Path) -> None:
    env = Env(tmp_path)
    env.engine.start()
    try:
        time.sleep(0.2)
        a = env.submit()
        env.engine.wake()
        limit = time.monotonic() + 1.0
        while time.monotonic() < limit and env.row(a).status != "running":
            time.sleep(0.02)
        assert env.row(a).status == "running"
    finally:
        env.engine.stop()


@pytest.mark.timeout(30)
def test_arret_laisse_running(tmp_path: Path) -> None:
    env = Env(tmp_path)
    a = env.submit()
    env.engine.start()
    env.engine.wake()
    limit = time.monotonic() + 3.0
    while time.monotonic() < limit and env.row(a).status != "running":
        time.sleep(0.02)
    assert env.row(a).status == "running"
    t0 = time.monotonic()
    env.engine.stop()
    assert time.monotonic() - t0 < 5.0
    assert env.engine._thread is not None
    assert not env.engine._thread.is_alive()
    assert env.launcher.jobs[0].terminated >= 1
    assert env.row(a).status == "running"


@pytest.mark.timeout(30)
def test_erreur_fatale_appelle_on_fatal(tmp_path: Path) -> None:
    env = Env(tmp_path)
    fatal: list[bool] = []
    env.engine.on_fatal = lambda: fatal.append(True)

    def boom() -> None:
        raise store.StoreError("base cassée")

    env.engine.tick = boom  # type: ignore[method-assign]
    env.engine.wake()
    env.engine.run()
    assert fatal == [True]
    assert env.engine.failed


def test_fakes_coherents() -> None:
    proc = FakeProc()
    job = FakeJob(proc)
    job.terminate()
    assert proc.poll() == 1

"""Thread `engine` : une tâche à la fois, lancée dans un Job Object, observée à chaque tour.

L'engine est le seul écrivain des transitions `running -> *` (la recovery au démarrage écrit
`running -> interrupted`). `tick()` fait un tour complet et se teste sans thread, avec un
launcher et des horloges injectés ; `run()` n'est que la boucle de réveil autour de `tick()`.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import Protocol

from deskgate import store
from deskgate.core.config import RunnerConfig
from deskgate.core.env import build_env
from deskgate.core.outcome import (
    ENGINE_ERROR,
    PLUGIN_ERROR,
    SPAWN_FAILED,
    Verdict,
    kill_verdict,
    verdict,
)
from deskgate.core.paths import PathDenied, Resolver, default_resolver, validate_artifact_path
from deskgate.core.states import (
    CANCELLED,
    FAILED,
    RUNNING,
    SUCCEEDED,
    Observation,
    step,
)
from deskgate.core.worker_protocol import (
    PROTOCOL,
    RESULT_MAX_BYTES,
    ProgressEvent,
    ResultError,
    ResultOk,
    WorkerInput,
    parse_event,
    parse_result,
)
from deskgate.jobobject import create_job, spawn_in_job

logger = logging.getLogger("deskgate.engine")

EVENTS_READ_MAX = 1_048_576
WAIT_AFTER_KILL_S = 5.0


@dataclass(frozen=True)
class LaunchSpec:
    argv: list[str]
    cwd: str
    log_path: str
    env: dict[str, str]
    memory_mb: int | None


class ProcLike(Protocol):
    pid: int

    def poll(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...


class JobLike(Protocol):
    def terminate(self, exit_code: int = 1) -> None: ...

    def active_processes(self) -> int: ...

    def close(self) -> None: ...


Launcher = Callable[[LaunchSpec], tuple[JobLike, ProcLike]]


def default_launcher(spec: LaunchSpec) -> tuple[JobLike, ProcLike]:
    """Crée le Job Object puis lance le worker dedans ; en cas d'échec, ferme le Job."""
    job = create_job(spec.memory_mb)
    try:
        proc = spawn_in_job(job, spec.argv, cwd=spec.cwd, log_path=spec.log_path, env=spec.env)
    except BaseException:
        job.close()
        raise
    return job, proc


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class _Running:
    job_id: str
    work_dir: Path
    job: JobLike
    proc: ProcLike
    deadline: float
    cancel_sent_at: float | None = None
    events_off: int = 0


class Engine:
    def __init__(
        self,
        *,
        db_path: Path,
        config: RunnerConfig,
        worker_script: Path,
        launcher: Launcher = default_launcher,
        clock: Callable[[], float] = time.monotonic,
        wall: Callable[[], datetime] = _utcnow,
        poll: float = 0.5,
        grace: float = 10.0,
        base_env: Mapping[str, str] | None = None,
        resolver: Resolver = default_resolver,
    ) -> None:
        self._db_path = db_path
        self._config = config
        self._worker_script = worker_script
        self._launcher = launcher
        self._clock = clock
        self._wall = wall
        self._poll = poll
        self._grace = grace
        self._base_env = base_env
        self._resolver = resolver
        self._conn: store.Connection | None = None
        self._cur: _Running | None = None
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self.on_fatal: Callable[[], None] | None = None
        self.failed = False
        self.last_tick_at: float | None = None

    @property
    def running_job_id(self) -> str | None:
        cur = self._cur
        return None if cur is None else cur.job_id

    # ------------------------------------------------------------------ tour

    def _connection(self) -> store.Connection:
        if self._conn is None:
            self._conn = store.connect(self._db_path)
        return self._conn

    def tick(self) -> None:
        """Un tour : réclamer si rien ne tourne, puis observer la tâche en cours."""
        self.last_tick_at = self._clock()
        conn = self._connection()
        if self._cur is None:
            row = store.claim_next(conn, self._wall())
            if row is not None:
                self._launch(conn, row)
        if self._cur is not None:
            self._observe(conn)

    # -------------------------------------------------------------- lancement

    def _fail(self, conn: store.Connection, job_id: str, code: str, message: str) -> None:
        try:
            store.finish(
                conn,
                job_id,
                from_status=RUNNING,
                to_status=FAILED,
                result_json=None,
                error_code=code,
                error_message=message,
                now=self._wall(),
            )
        except store.StaleTransition:
            logger.warning("Transition obsolète pour la tâche %s (échec %s).", job_id, code)

    def _launch(self, conn: store.Connection, row: store.JobRow) -> None:
        try:
            self._launch_inner(conn, row)
        except Exception:
            logger.exception("Erreur interne au lancement de la tâche %s.", row.id)
            self._cur = None
            self._fail(conn, row.id, ENGINE_ERROR, "Erreur interne de l'engine.")

    def _launch_inner(self, conn: store.Connection, row: store.JobRow) -> None:
        cap = self._config.capabilities.get(row.capability)
        if cap is None:
            self._fail(conn, row.id, SPAWN_FAILED, "Capacité absente de la configuration.")
            return
        work_dir = Path(row.work_dir)
        try:
            work_dir.mkdir(parents=True, exist_ok=False)
            payload = WorkerInput(
                protocol=PROTOCOL,
                job_id=row.id,
                capability=row.capability,
                entry=cap.entry,
                params=_params(row.params_json),
                work_dir=str(work_dir.resolve()).replace("\\", "/"),
                sys_path=list(cap.pythonpath),
            )
            input_path = work_dir / "input.json"
            input_path.write_text(payload.model_dump_json(), encoding="utf-8")
            spec = LaunchSpec(
                argv=[
                    cap.python,
                    "-X",
                    "utf8",
                    str(self._worker_script),
                    "--input",
                    str(input_path),
                ],
                cwd=str(work_dir),
                log_path=str(work_dir / "job.log"),
                env=build_env(self._base_env if self._base_env is not None else os.environ),
                memory_mb=cap.memory_mb,
            )
            job, proc = self._launcher(spec)
        except (OSError, ValueError) as exc:
            logger.warning(
                "Lancement impossible pour la tâche %s : %s.", row.id, type(exc).__name__
            )
            self._fail(
                conn,
                row.id,
                SPAWN_FAILED,
                f"Lancement du plugin impossible : {type(exc).__name__}.",
            )
            return
        self._cur = _Running(
            job_id=row.id,
            work_dir=work_dir,
            job=job,
            proc=proc,
            deadline=self._clock() + row.timeout_s,
        )

    # ------------------------------------------------------------ observation

    def _observe(self, conn: store.Connection) -> None:
        cur = self._cur
        if cur is None:
            return
        try:
            self._observe_inner(conn, cur)
        except Exception:
            if self._cur is None:  # la conclusion elle-même a échoué : erreur d'infrastructure
                raise
            logger.exception("Erreur interne pendant le suivi de la tâche %s.", cur.job_id)
            with contextlib.suppress(Exception):
                cur.job.terminate(1)
            try:
                self._fail(conn, cur.job_id, ENGINE_ERROR, "Erreur interne de l'engine.")
            finally:
                self._release(cur)

    def _release(self, cur: _Running) -> None:
        try:
            cur.job.close()
        finally:
            if self._cur is cur:
                self._cur = None

    def _observe_inner(self, conn: store.Connection, cur: _Running) -> None:
        rc = cur.proc.poll()
        cancel = store.is_cancel_requested(conn, cur.job_id)
        self._read_progress(conn, cur)
        decision = step(
            Observation(rc, cancel, cur.cancel_sent_at, cur.deadline), self._clock(), self._grace
        )
        if decision.action == "wait":
            return
        if decision.action == "write_cancel_flag":
            (cur.work_dir / "cancel.flag").write_bytes(b"")
            cur.cancel_sent_at = self._clock()
            return
        if decision.action == "kill":
            self._reap(cur)
            if decision.status is None:
                raise RuntimeError("décision d'arrêt sans statut")
            self._conclude(conn, cur, kill_verdict(decision.status), None)
            return
        # "exited" : nettoyage systématique des orphelins, puis verdict.
        self._reap(cur)
        if decision.status == CANCELLED:
            self._conclude(conn, cur, kill_verdict(CANCELLED), None)
            return
        if rc is None:
            raise RuntimeError("sortie sans code de retour")
        outcome, result_json = self._evaluate(cur, rc)
        self._conclude(conn, cur, outcome, result_json)

    def _reap(self, cur: _Running) -> None:
        cur.job.terminate(1)
        try:
            cur.proc.wait(WAIT_AFTER_KILL_S)
        except Exception:
            logger.warning("Le processus de la tâche %s n'a pas rendu la main à temps.", cur.job_id)

    def _read_progress(self, conn: store.Connection, cur: _Running) -> None:
        try:
            with open(cur.work_dir / "events.jsonl", "rb") as f:
                f.seek(cur.events_off)
                data = f.read(EVENTS_READ_MAX)
        except FileNotFoundError:
            return
        end = data.rfind(b"\n")
        if end < 0:
            return
        cur.events_off += end + 1
        last: ProgressEvent | None = None
        for line in data[: end + 1].splitlines():
            event = parse_event(line)
            if isinstance(event, ProgressEvent):
                last = event
        if last is not None:
            store.update_progress(conn, cur.job_id, last.pct, last.message)

    def _evaluate(self, cur: _Running, rc: int) -> tuple[Verdict, str | None]:
        try:
            with open(cur.work_dir / "result.json", "rb") as f:
                raw: bytes | None = f.read(RESULT_MAX_BYTES + 1)
        except FileNotFoundError:
            raw = None
        state, parsed = parse_result(raw)
        artifacts: list[dict[str, str]] = []
        artifacts_ok = True
        if isinstance(parsed, ResultOk):
            for art in parsed.artifacts:
                host = _artifact_host_path(cur.work_dir, art.path)
                try:
                    container = validate_artifact_path(
                        host,
                        self._config.mappings(),
                        self._config.paths.allowed_roots,
                        self._resolver,
                    )
                except PathDenied:
                    artifacts_ok = False
                    break
                artifacts.append({"kind": art.kind, "path": container})
        outcome = verdict(exit_code=rc, result_state=state, artifacts_ok=artifacts_ok)
        if isinstance(parsed, ResultError) and outcome.error_code == PLUGIN_ERROR:
            message = f"{parsed.error.type} : {parsed.error.message}"[:2000]
            outcome = Verdict(outcome.status, outcome.error_code, message)
        result_json: str | None = None
        if outcome.status == SUCCEEDED and isinstance(parsed, ResultOk):
            result_json = json.dumps(
                {"summary": parsed.summary, "data": parsed.data, "artifacts": artifacts},
                ensure_ascii=False,
            )
        return outcome, result_json

    def _conclude(
        self,
        conn: store.Connection,
        cur: _Running,
        outcome: Verdict,
        result_json: str | None,
    ) -> None:
        try:
            store.finish(
                conn,
                cur.job_id,
                from_status=RUNNING,
                to_status=outcome.status,
                result_json=result_json,
                error_code=outcome.error_code,
                error_message=outcome.error_message,
                now=self._wall(),
            )
        except store.StaleTransition:
            logger.warning("Transition obsolète pour la tâche %s.", cur.job_id)
        finally:
            self._release(cur)

    # ------------------------------------------------- boucle, réveil, arrêt

    def wake(self) -> None:
        self._wake.set()

    def run(self) -> None:
        try:
            while not self._stop.is_set():
                self._wake.wait(self._poll)
                self._wake.clear()  # avant la lecture de la base : aucun réveil perdu
                if self._stop.is_set():
                    break
                self.tick()
        except BaseException:
            logger.exception("Thread engine arrêté sur erreur.")
            self.failed = True
            if self.on_fatal is not None:
                self.on_fatal()
        finally:
            if self._conn is not None:
                with contextlib.suppress(Exception):
                    self._conn.close()
                self._conn = None

    def start(self) -> None:
        thread = threading.Thread(target=self.run, name="deskgate-engine", daemon=True)
        self._thread = thread
        thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Arrête la boucle et tue le Job en cours ; la ligne reste `running` (recovery).

        Idempotent : appelé par le lifespan puis par le `finally` de `serve`.
        """
        already = self._stop.is_set()
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
        cur = self._cur
        if cur is not None:
            with contextlib.suppress(Exception):
                cur.job.terminate(1)
            with contextlib.suppress(Exception):
                cur.job.close()
        if not already:
            logger.info("Engine arrêté.")


def _params(params_json: str) -> dict[str, object]:
    data = json.loads(params_json)
    if not isinstance(data, dict):
        raise ValueError("params doit être un objet JSON")
    return data


def _artifact_host_path(work_dir: Path, raw: str) -> str:
    if PureWindowsPath(raw).drive:
        return raw
    base = str(work_dir).replace("\\", "/")
    relative = raw.lstrip("/\\")
    return f"{base}/{relative}"

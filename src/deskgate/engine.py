"""Thread `engine` : une tâche à la fois, lancée dans un Job Object, observée à chaque tour.

L'engine est le seul écrivain des transitions `running -> *` (la recovery au démarrage écrit
`running -> interrupted`). `tick()` fait un tour complet et se teste sans thread, avec un
launcher et des horloges injectés ; `run()` n'est que la boucle de réveil autour de `tick()`.

Politique d'erreur : une erreur SQLite transitoire (`OperationalError` : verrou, occupation, E/S)
est journalisée, la connexion rouverte et le tour rejoué avec back-off sans toucher au Job en
cours, un verdict non écrit étant rejoué au tour suivant ; au-delà de `MAX_DB_ERRORS` erreurs
consécutives, ou sur toute autre erreur interne, le thread meurt (`failed`, `on_fatal`) et le
superviseur du runner conclut la tâche en `interrupted` puis recrée le thread. Limite connue : un
thread bloqué (et non mort) n'est pas recréé ; /health le signale en `stale`.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import Protocol

from deskgate import store
from deskgate.core.config import RunnerConfig
from deskgate.core.env import build_env, mcp_env_var
from deskgate.core.outcome import (
    ENGINE_ERROR,
    MEMORY_LIMIT,
    PLUGIN_ERROR,
    SPAWN_FAILED,
    Verdict,
    kill_verdict,
    memory_exhausted,
    verdict,
)
from deskgate.core.paths import (
    PathDenied,
    Resolver,
    convert_mcp_arguments,
    convert_path_params,
    default_resolver,
    host_to_container,
    validate_artifact_path,
)
from deskgate.core.payload import CALLBACK_MAX_BYTES, build_callback, encode
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
MAX_DB_ERRORS = 5


def _default_backoff(errors: int) -> float:
    return float(min(30, 2**errors))


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

    def peak_memory(self) -> int: ...

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
    capability: str
    work_dir: Path
    job: JobLike
    proc: ProcLike
    deadline: float
    cancel_sent_at: float | None = None
    events_off: int = 0
    memory_mb: int | None = None


@dataclass(frozen=True)
class _Unsettled:
    """Verdict calculé mais non écrit (base occupée) : rejoué au tour suivant."""

    job_id: str
    outcome: Verdict
    result_json: str | None


MCP_ENTRY = "deskgate.workers.mcp_call:run"


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
        callback_max_bytes: int = CALLBACK_MAX_BYTES,
        runner_python: str | None = None,
        connect: Callable[[Path], store.Connection] = store.connect,
        backoff: Callable[[int], float] = _default_backoff,
        max_db_errors: int = MAX_DB_ERRORS,
    ) -> None:
        self._connect = connect
        self._backoff = backoff
        self._max_db_errors = max_db_errors
        self._unsettled: _Unsettled | None = None
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
        self._runner_python = runner_python or sys.executable
        self._callback_max_bytes = callback_max_bytes
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
            self._conn = self._connect(self._db_path)
        return self._conn

    def _drop_connection(self) -> None:
        if self._conn is not None:
            with contextlib.suppress(Exception):
                self._conn.close()
            self._conn = None

    def tick(self) -> None:
        """Un tour : réclamer si rien ne tourne, puis observer la tâche en cours."""
        self.last_tick_at = self._clock()
        conn = self._connection()
        if self._unsettled is not None:
            self._settle(conn)
            return
        if self._cur is None:
            row = store.claim_next(conn, self._wall())
            if row is not None:
                self._launch(conn, row)
        if self._cur is not None:
            self._observe(conn)

    # -------------------------------------------------------------- lancement

    def _store_verdict(
        self, conn: store.Connection, job_id: str, outcome: Verdict, result_json: str | None
    ) -> None:
        try:
            store.finish(
                conn,
                job_id,
                from_status=RUNNING,
                to_status=outcome.status,
                result_json=result_json,
                error_code=outcome.error_code,
                error_message=outcome.error_message,
                now=self._wall(),
            )
        except store.StaleTransition:
            logger.warning("Transition obsolète pour la tâche %s.", job_id)
        except store.OperationalError:
            self._unsettled = _Unsettled(job_id, outcome, result_json)
            logger.warning(
                "Verdict de la tâche %s non écrit (base occupée) : nouvel essai au prochain tour.",
                job_id,
            )
            raise

    def _settle(self, conn: store.Connection) -> None:
        pending = self._unsettled
        if pending is None:
            return
        try:
            store.finish(
                conn,
                pending.job_id,
                from_status=RUNNING,
                to_status=pending.outcome.status,
                result_json=pending.result_json,
                error_code=pending.outcome.error_code,
                error_message=pending.outcome.error_message,
                now=self._wall(),
            )
        except store.StaleTransition:
            logger.warning("Transition obsolète pour la tâche %s.", pending.job_id)
        self._unsettled = None

    def _fail(self, conn: store.Connection, job_id: str, code: str, message: str) -> None:
        self._store_verdict(conn, job_id, Verdict(FAILED, code, message), None)

    def _launch(self, conn: store.Connection, row: store.JobRow) -> None:
        try:
            self._launch_inner(conn, row)
        except store.OperationalError:
            raise
        except Exception:
            logger.exception("Erreur interne au lancement de la tâche %s.", row.id)
            self._cur = None
            self._fail(conn, row.id, ENGINE_ERROR, "Erreur interne de l'engine.")

    def _launch_inner(self, conn: store.Connection, row: store.JobRow) -> None:
        cap = self._config.capabilities.get(row.capability)
        if cap is None:
            self._fail(conn, row.id, SPAWN_FAILED, "Capacité absente de la configuration.")
            return
        try:
            # Revalidation au lancement : une jonction a pu changer depuis la soumission.
            raw = _params(row.params_json)
            if cap.kind == "mcp":
                params = convert_mcp_arguments(
                    raw,
                    self._config.mcp_path_arguments(),
                    self._config.mappings(),
                    self._config.paths.allowed_roots,
                    self._resolver,
                )
            else:
                params = convert_path_params(
                    raw,
                    cap.path_params,
                    self._config.mappings(),
                    self._config.paths.allowed_roots,
                    self._resolver,
                )
        except PathDenied as exc:
            self._fail(conn, row.id, exc.code, exc.message)
            return
        python: str
        entry: str
        sys_path: list[str]
        settings: dict[str, object]
        extra_env: dict[str, str]
        if cap.kind == "mcp":
            servers = self._config.mcp_servers
            python = self._runner_python
            entry = MCP_ENTRY
            sys_path = []
            settings = {
                "servers": {
                    name: {
                        "command": s.command,
                        "args": list(s.args),
                        "allowed_tools": list(s.allowed_tools),
                        "env_keys": sorted(s.env),
                    }
                    for name, s in servers.items()
                }
            }
            # Valeurs d'env : mémoire et environnement du worker seulement, jamais sur disque.
            # D-13 : seules les variables du serveur visé par params.server.
            target = params.get("server")
            srv = servers.get(target) if isinstance(target, str) else None
            extra_env = (
                {mcp_env_var(target, key): value for key, value in srv.env.items()}
                if srv is not None and isinstance(target, str)
                else {}
            )
        else:
            if cap.python is None or cap.entry is None:
                raise ValueError("capacité python incomplète")
            python, entry = cap.python, cap.entry
            sys_path = list(cap.pythonpath)
            settings = dict(cap.settings)
            extra_env = {}
        work_dir = Path(row.work_dir)
        try:
            work_dir.mkdir(parents=True, exist_ok=False)
            payload = WorkerInput(
                protocol=PROTOCOL,
                job_id=row.id,
                capability=row.capability,
                entry=entry,
                params=params,
                work_dir=str(work_dir.resolve()).replace("\\", "/"),
                sys_path=sys_path,
                settings=settings,
            )
            input_path = work_dir / "input.json"
            input_path.write_text(payload.model_dump_json(), encoding="utf-8")
            spec = LaunchSpec(
                argv=[
                    python,
                    "-X",
                    "utf8",
                    str(self._worker_script),
                    "--input",
                    str(input_path),
                ],
                cwd=str(work_dir),
                log_path=str(work_dir / "job.log"),
                env=build_env(
                    self._base_env if self._base_env is not None else os.environ, extra_env
                ),
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
            capability=row.capability,
            work_dir=work_dir,
            job=job,
            proc=proc,
            deadline=self._clock() + row.timeout_s,
            memory_mb=cap.memory_mb,
        )

    # ------------------------------------------------------------ observation

    def _observe(self, conn: store.Connection) -> None:
        cur = self._cur
        if cur is None:
            return
        try:
            self._observe_inner(conn, cur)
        except store.OperationalError:
            raise
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
        # "exited" : pic mémoire lu avant de tuer le Job, nettoyage des orphelins, puis verdict.
        peak = self._peak(cur)
        self._reap(cur)
        if decision.status == CANCELLED:
            self._conclude(conn, cur, kill_verdict(CANCELLED), None)
            return
        if rc is None:
            raise RuntimeError("sortie sans code de retour")
        outcome, result_json = self._evaluate(cur, rc, peak)
        self._conclude(conn, cur, outcome, result_json)

    def _peak(self, cur: _Running) -> int | None:
        if cur.memory_mb is None:
            return None
        try:
            return cur.job.peak_memory()
        except Exception as exc:
            logger.warning(
                "Pic mémoire illisible pour la tâche %s : %s.", cur.job_id, type(exc).__name__
            )
            return None

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

    def _evaluate(
        self, cur: _Running, rc: int, peak: int | None = None
    ) -> tuple[Verdict, str | None]:
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
        outcome = verdict(
            exit_code=rc,
            result_state=state,
            artifacts_ok=artifacts_ok,
            memory_limit_mb=cur.memory_mb if memory_exhausted(peak, cur.memory_mb) else None,
        )
        if isinstance(parsed, ResultError) and outcome.error_code == PLUGIN_ERROR:
            message = f"{parsed.error.type} : {parsed.error.message}"[:2000]
            outcome = Verdict(outcome.status, outcome.error_code, message)
        elif isinstance(parsed, ResultError) and outcome.error_code == MEMORY_LIMIT:
            message = f"{outcome.error_message} (plugin : {parsed.error.type})"[:2000]
            outcome = Verdict(outcome.status, outcome.error_code, message)
        result_json: str | None = None
        if outcome.status == SUCCEEDED and isinstance(parsed, ResultOk):
            result_json = json.dumps(
                {"summary": parsed.summary, "data": parsed.data, "artifacts": artifacts},
                ensure_ascii=False,
            )
            result_json = self._cap_summary(cur, parsed.summary, result_json)
        return outcome, result_json

    def _cap_summary(self, cur: _Running, summary: object, result_json: str) -> str:
        """Déporte le résumé dans summary.json si le corps du rappel dépasserait le plafond."""
        body = build_callback(
            job_id=cur.job_id,
            capability=cur.capability,
            status=SUCCEEDED,
            started_at=None,
            finished_at=None,
            result_json=result_json,
            error_code=None,
            error_message=None,
            max_bytes=None,
        )
        if len(encode(body)) <= self._callback_max_bytes:
            return result_json
        result = json.loads(result_json)
        try:
            result["summary"] = {"path": self._write_summary(cur, summary), "truncated": True}
        except OSError as exc:
            logger.warning(
                "Écriture de summary.json impossible pour la tâche %s : %s.",
                cur.job_id,
                type(exc).__name__,
            )
            result["summary"] = {"truncated": True, "error": "summary_write_failed"}
        return json.dumps(result, ensure_ascii=False)

    def _write_summary(self, cur: _Running, summary: object) -> str:
        tmp = cur.work_dir / "summary.json.tmp"
        try:
            with open(tmp, "wb") as f:
                f.write(json.dumps(summary, ensure_ascii=False).encode("utf-8"))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, cur.work_dir / "summary.json")
        except OSError:
            with contextlib.suppress(OSError):
                tmp.unlink()
            raise
        host = str(cur.work_dir).replace("\\", "/") + "/summary.json"
        try:
            return host_to_container(host, self._config.mappings())
        except PathDenied:
            logger.warning(
                "Aucun mapping ne couvre le dossier de la tâche %s : chemin hôte transmis.",
                cur.job_id,
            )
            return host

    def _conclude(
        self,
        conn: store.Connection,
        cur: _Running,
        outcome: Verdict,
        result_json: str | None,
    ) -> None:
        try:
            self._store_verdict(conn, cur.job_id, outcome, result_json)
        finally:
            self._release(cur)

    # ------------------------------------------------- boucle, réveil, arrêt

    def wake(self) -> None:
        self._wake.set()

    def run(self) -> None:
        errors = 0
        try:
            while not self._stop.is_set():
                self._wake.wait(self._poll)
                self._wake.clear()  # avant la lecture de la base : aucun réveil perdu
                if self._stop.is_set():
                    break
                try:
                    self.tick()
                    errors = 0
                except store.OperationalError:
                    errors += 1
                    self._drop_connection()
                    if errors >= self._max_db_errors:
                        logger.exception(
                            "Base indisponible : %d erreurs consécutives, thread engine arrêté.",
                            errors,
                        )
                        raise
                    if errors == 1:
                        logger.warning(
                            "Base occupée ou indisponible : nouvel essai (%d/%d).",
                            errors,
                            self._max_db_errors,
                            exc_info=True,
                        )
                    else:
                        logger.warning(
                            "Base occupée ou indisponible : nouvel essai (%d/%d).",
                            errors,
                            self._max_db_errors,
                        )
                    self._stop.wait(self._backoff(errors))
        except BaseException:
            logger.exception("Thread engine arrêté sur erreur.")
            self.failed = True
            if self.on_fatal is not None:
                self.on_fatal()
        finally:
            self._drop_connection()

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
        if thread is None or not thread.is_alive():
            self._drop_connection()
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

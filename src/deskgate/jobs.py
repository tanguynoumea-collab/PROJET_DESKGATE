"""Service des tâches : soumission, lecture, annulation, journaux.

Une connexion SQLite par appel (les routes sont synchrones, exécutées dans un thread).
La resumeUrl (`callback_url`) est stockée brute et n'est jamais renvoyée (règle 6, D-13).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any

from deskgate import store
from deskgate.core.callback_policy import CallbackUrlError, check_callback_url
from deskgate.core.config import RunnerConfig
from deskgate.core.errors import (
    CALLBACK_HOST_NOT_ALLOWED,
    CAPABILITY_NOT_FOUND,
    IDEMPOTENCY_CONFLICT,
)
from deskgate.core.jobspec import (
    JobRequestError,
    SubmitRequest,
    is_valid_job_id,
    new_job_id,
    resolve_timeout,
    work_dir_for,
)
from deskgate.core.payload import duration_s
from deskgate.core.redact import redact_signature
from deskgate.core.states import TERMINAL
from deskgate.store import IdempotencyConflict, JobRow

LOG_LIMIT_DEFAULT = 65_536
LOG_LIMIT_MAX = 1_048_576

logger = logging.getLogger("deskgate.jobs")


def job_view(row: JobRow) -> dict[str, Any]:
    """Vue publique d'une tâche : sans callback, paramètres ni chemin hôte."""
    result: dict[str, Any] = json.loads(row.result_json) if row.result_json else {}
    progress: dict[str, Any] | None = None
    if row.progress_pct is not None or row.progress_message is not None:
        progress = {"pct": row.progress_pct, "message": row.progress_message}
    error: dict[str, str | None] | None = None
    if row.error_code is not None:
        error = {"code": row.error_code, "message": row.error_message}
    return {
        "job_id": row.id,
        "capability": row.capability,
        "status": row.status,
        "cancel_requested": row.cancel_requested,
        "progress": progress,
        "summary": result.get("summary", {}),
        "artifacts": result.get("artifacts", []),
        "error": error,
        "created_at": row.created_at,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "duration_s": duration_s(row.started_at, row.finished_at),
    }


class JobsService:
    def __init__(
        self,
        *,
        db_path: Path,
        config: RunnerConfig,
        wake: Callable[[], None] = lambda: None,
    ) -> None:
        self._db = db_path
        self._config = config
        self._wake = wake

    def _refuse(self, code: str, capability: str | None, job_id: str | None = None) -> None:
        """Audit d'un refus ; ne fait jamais échouer la réponse."""
        try:
            with closing(store.connect(self._db)) as conn:
                store.record_refusal(conn, code=code, capability=capability, job_id=job_id)
        except Exception as exc:
            logger.warning("Audit du refus impossible : %s.", type(exc).__name__)

    def audit_refusal(self, code: str, capability: str | None = None) -> None:
        self._refuse(code, capability)

    def submit(self, req: SubmitRequest) -> str:
        cap = self._config.capabilities.get(req.capability)
        if cap is None:
            self._refuse(CAPABILITY_NOT_FOUND, req.capability)
            raise JobRequestError(CAPABILITY_NOT_FOUND, "Capacité inconnue.", 404)
        try:
            timeout_s = resolve_timeout(req.timeout, cap.timeout_max)
        except JobRequestError as exc:
            self._refuse(exc.code, req.capability)
            raise
        try:
            check_callback_url(req.callback.url, self._config.callback_allowed_hosts)
        except CallbackUrlError as exc:
            self._refuse(CALLBACK_HOST_NOT_ALLOWED, req.capability)
            raise JobRequestError(CALLBACK_HOST_NOT_ALLOWED, exc.message, 422) from None
        job_id = new_job_id()
        try:
            with closing(store.connect(self._db)) as conn:
                store.insert_job(
                    conn,
                    job_id=job_id,
                    capability=req.capability,
                    params_json=json.dumps(req.params, ensure_ascii=False),
                    timeout_s=timeout_s,
                    resource=cap.resource,
                    idempotency_key=req.idempotency_key,
                    callback_url=req.callback.url,
                    work_dir=work_dir_for(self._config.effective_work_root(), job_id),
                )
        except IdempotencyConflict as exc:
            self._refuse(IDEMPOTENCY_CONFLICT, req.capability, job_id=exc.existing_job_id)
            raise JobRequestError(
                IDEMPOTENCY_CONFLICT,
                "Une tâche avec cette clé d'idempotence est déjà en file ou en cours.",
                409,
                job_id=exc.existing_job_id,
            ) from None
        self._wake()
        return job_id

    def get(self, job_id: str) -> dict[str, Any] | None:
        if not is_valid_job_id(job_id):
            return None
        with closing(store.connect(self._db)) as conn:
            row = store.get_job(conn, job_id)
        return None if row is None else job_view(row)

    def cancel(self, job_id: str) -> dict[str, Any] | None:
        if not is_valid_job_id(job_id):
            return None
        with closing(store.connect(self._db)) as conn:
            row = store.request_cancel(conn, job_id)
        if row is None:
            return None
        if row.status == "running":
            self._wake()
        return job_view(row)

    def read_logs(
        self,
        job_id: str,
        *,
        offset: int | None = None,
        limit: int = LOG_LIMIT_DEFAULT,
        tail: int | None = None,
    ) -> dict[str, Any] | None:
        if not is_valid_job_id(job_id):
            return None
        with closing(store.connect(self._db)) as conn:
            row = store.get_job(conn, job_id)
        if row is None:
            return None
        limit = max(1, min(limit, LOG_LIMIT_MAX))
        path = Path(row.work_dir) / "job.log"
        try:
            size = path.stat().st_size
        except OSError:
            return {"text": "", "offset": 0, "next_offset": 0, "size": 0, "complete": False}
        start = max(0, size - tail) if tail is not None else (offset or 0)
        length = tail if tail is not None else limit
        with path.open("rb") as fh:
            fh.seek(start)
            data = fh.read(max(0, length))
        next_offset = start + len(data)
        return {
            "text": redact_signature(data.decode("utf-8", errors="replace")),
            "offset": start,
            "next_offset": next_offset,
            "size": size,
            "complete": row.status in TERMINAL and next_offset >= size,
        }

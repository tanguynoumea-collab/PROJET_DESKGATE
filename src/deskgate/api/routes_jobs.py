"""Routes des tâches : fines, déléguées à `JobsService` (routes synchrones, exécutées en thread)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from starlette.responses import JSONResponse

from deskgate.core.errors import INVALID_REQUEST, JOB_NOT_FOUND
from deskgate.core.jobspec import JobRequestError, SubmitRequest
from deskgate.jobs import LOG_LIMIT_DEFAULT, LOG_LIMIT_MAX, JobsService

router = APIRouter()


def _service(request: Request) -> JobsService:
    service: JobsService = request.app.state.jobs
    return service


def _found(result: dict[str, Any] | None) -> dict[str, Any]:
    if result is None:
        raise JobRequestError(JOB_NOT_FOUND, "Tâche introuvable.", 404)
    return result


@router.post("/jobs", status_code=202)
def submit_job(body: SubmitRequest, request: Request) -> JSONResponse:
    job_id = _service(request).submit(body)
    return JSONResponse({"job_id": job_id, "status": "queued"}, status_code=202)


@router.get("/jobs/{job_id}")
def get_job(job_id: str, request: Request) -> dict[str, Any]:
    return _found(_service(request).get(job_id))


@router.get("/jobs/{job_id}/logs")
def get_logs(
    job_id: str,
    request: Request,
    offset: int | None = Query(None, ge=0),
    limit: int = Query(LOG_LIMIT_DEFAULT, ge=1, le=LOG_LIMIT_MAX),
    tail: int | None = Query(None, ge=1, le=LOG_LIMIT_MAX),
) -> dict[str, Any]:
    if offset is not None and tail is not None:
        raise JobRequestError(
            INVALID_REQUEST, "Requête invalide : offset et tail sont exclusifs.", 422
        )
    return _found(_service(request).read_logs(job_id, offset=offset, limit=limit, tail=tail))


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, request: Request) -> dict[str, Any]:
    return _found(_service(request).cancel(job_id))

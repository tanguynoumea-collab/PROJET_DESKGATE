"""Gestionnaires d'erreurs au format D-08, messages en français."""

from __future__ import annotations

import logging
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from deskgate.core.errors import (
    HTTP_MESSAGES_FR,
    INTERNAL_ERROR,
    INVALID_REQUEST,
    error_body,
    http_code,
)
from deskgate.core.jobspec import JobRequestError

_log = logging.getLogger("deskgate.api")

_FR = {
    "missing": "champ obligatoire absent",
    "int_parsing": "entier attendu",
    "int_type": "entier attendu",
    "string_type": "chaîne attendue",
    "bool_parsing": "booléen attendu",
    "bool_type": "booléen attendu",
    "json_invalid": "JSON invalide",
    "extra_forbidden": "champ inconnu",
}


def _fr(error_type: str) -> str:
    return _FR.get(error_type, "valeur invalide")


async def _http_exception(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(StarletteHTTPException, exc)
    return JSONResponse(
        error_body(http_code(exc.status_code), HTTP_MESSAGES_FR.get(exc.status_code, "Erreur.")),
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
    )


async def _validation(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(RequestValidationError, exc)
    jobs = getattr(request.app.state, "jobs", None)
    if request.method == "POST" and request.url.path == "/jobs" and jobs is not None:
        try:
            await run_in_threadpool(jobs.audit_refusal, INVALID_REQUEST)
        except Exception as audit_exc:
            _log.warning("Audit du refus impossible : %s.", type(audit_exc).__name__)
    # Ni `input` ni `msg` (anglais, peut contenir la valeur fautive) ne sont repris.
    details = "; ".join(
        f"{'.'.join(str(p) for p in e['loc'])} : {_fr(e['type'])}" for e in exc.errors()
    )
    return JSONResponse(
        error_body(INVALID_REQUEST, f"Requête invalide : {details}"), status_code=422
    )


async def _job_request(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(JobRequestError, exc)
    return JSONResponse(error_body(exc.code, exc.message, **exc.extra), status_code=exc.status)


async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
    _log.error("Erreur interne non gérée", exc_info=exc)
    return JSONResponse(error_body(INTERNAL_ERROR, HTTP_MESSAGES_FR[500]), status_code=500)


def install_handlers(app: FastAPI) -> None:
    """Enregistre les gestionnaires 4xx/5xx au format D-08."""
    app.add_exception_handler(StarletteHTTPException, _http_exception)
    app.add_exception_handler(RequestValidationError, _validation)
    app.add_exception_handler(JobRequestError, _job_request)
    app.add_exception_handler(Exception, _unexpected)

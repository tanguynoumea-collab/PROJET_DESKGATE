"""Codes d'erreur stables et forme du corps d'erreur (D-08)."""

from __future__ import annotations

UNAUTHORIZED = "unauthorized"
HOST_NOT_ALLOWED = "host_not_allowed"
PATH_OUTSIDE_ROOTS = "path_outside_roots"
PATH_INVALID = "path_invalid"
INVALID_CONFIG = "invalid_config"
INVALID_REQUEST = "invalid_request"
INTERNAL_ERROR = "internal_error"
CAPABILITY_NOT_FOUND = "capability_not_found"
JOB_NOT_FOUND = "job_not_found"
IDEMPOTENCY_CONFLICT = "idempotency_conflict"
TIMEOUT_TOO_LARGE = "timeout_too_large"
CALLBACK_HOST_NOT_ALLOWED = "callback_host_not_allowed"

HTTP_MESSAGES_FR: dict[int, str] = {
    400: "Requête invalide.",
    401: "Jeton d'authentification absent ou invalide.",
    403: "Accès refusé.",
    404: "Ressource introuvable.",
    405: "Méthode non autorisée.",
    409: "Conflit.",
    422: "Requête invalide.",
    500: "Erreur interne du runner.",
}


def error_body(code: str, message: str, **extra: str) -> dict[str, dict[str, str]]:
    """Corps JSON d'erreur : `{"error": {"code": ..., "message": ...}}` (+ clés `extra`)."""
    return {"error": {"code": code, "message": message, **extra}}


def http_code(status: int) -> str:
    """Code stable pour une erreur HTTP générique."""
    return f"http_{status}"

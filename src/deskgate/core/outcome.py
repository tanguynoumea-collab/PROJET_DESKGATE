"""Verdict terminal pur d'une tâche et codes d'erreur stables."""

from __future__ import annotations

from dataclasses import dataclass

from deskgate.core.states import CANCELLED, FAILED, SUCCEEDED, TIMEOUT
from deskgate.core.worker_protocol import ResultState

NONZERO_EXIT = "nonzero_exit"
MISSING_RESULT = "missing_result"
INVALID_RESULT = "invalid_result"
RESULT_TOO_LARGE = "result_too_large"
ARTIFACT_OUTSIDE_ROOTS = "artifact_outside_roots"
PLUGIN_ERROR = "plugin_error"
SPAWN_FAILED = "spawn_failed"
ENGINE_ERROR = "engine_error"
RUNNER_RESTARTED = "runner_restarted"
TIMEOUT_CODE = "timeout"
CANCELLED_CODE = "cancelled"

RESTART_MESSAGE = "Runner redémarré pendant l'exécution."


@dataclass(frozen=True)
class Verdict:
    status: str
    error_code: str | None
    error_message: str | None


def _failed(code: str, message: str) -> Verdict:
    return Verdict(FAILED, code, message)


def verdict(*, exit_code: int, result_state: ResultState, artifacts_ok: bool) -> Verdict:
    """Verdict d'un processus sorti sans annulation."""
    if result_state == "plugin_error":
        return _failed(PLUGIN_ERROR, "Le plugin a signalé une erreur.")
    if result_state == "too_large":
        return _failed(RESULT_TOO_LARGE, "result.json dépasse la taille maximale.")
    if result_state == "invalid":
        return _failed(INVALID_RESULT, "result.json invalide.")
    if result_state == "missing" and exit_code == 0:
        return _failed(MISSING_RESULT, "result.json absent.")
    if exit_code != 0:
        return _failed(NONZERO_EXIT, f"Le plugin s'est terminé avec le code {exit_code}.")
    if not artifacts_ok:
        return _failed(ARTIFACT_OUTSIDE_ROOTS, "Artefact hors des racines autorisées.")
    return Verdict(SUCCEEDED, None, None)


def kill_verdict(status: str) -> Verdict:
    """Verdict d'une tâche tuée par l'engine (délai ou annulation)."""
    if status == TIMEOUT:
        return Verdict(TIMEOUT, TIMEOUT_CODE, "Délai maximum dépassé.")
    if status == CANCELLED:
        return Verdict(CANCELLED, CANCELLED_CODE, "Tâche annulée.")
    raise ValueError(f"Statut d'arrêt inattendu : {status}")

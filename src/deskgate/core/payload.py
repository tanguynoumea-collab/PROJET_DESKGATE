"""Corps du rappel n8n, construit à l'envoi depuis la ligne jobs (D-06).

Module pur : stdlib seulement. Le champ `data` du plugin n'est jamais transmis.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

CALLBACK_MAX_BYTES = 1_048_576


def duration_s(started_at: str | None, finished_at: str | None) -> float | None:
    """Durée en secondes ; `None` si la tâche n'a jamais démarré ou n'est pas terminée."""
    if started_at is None or finished_at is None:
        return None
    delta = datetime.fromisoformat(finished_at) - datetime.fromisoformat(started_at)
    return round(delta.total_seconds(), 3)


def encode(body: Mapping[str, Any]) -> bytes:
    """JSON compact en UTF-8 non échappé ; lève ValueError sur un flottant non fini."""
    return json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode(
        "utf-8"
    )


def minimal(body: Mapping[str, Any]) -> dict[str, Any]:
    """Copie du corps dont le résumé est remplacé par le marqueur de troncature."""
    return {**body, "summary": {"truncated": True}}


def build_callback(
    *,
    job_id: str,
    capability: str,
    status: str,
    started_at: str | None,
    finished_at: str | None,
    result_json: str | None,
    error_code: str | None,
    error_message: str | None,
    max_bytes: int | None = CALLBACK_MAX_BYTES,
) -> dict[str, Any]:
    """Construit le corps du rappel ; dernier recours : résumé tronqué si trop gros."""
    result = json.loads(result_json) if result_json else {}
    error = None if error_code is None else {"code": error_code, "message": error_message}
    body: dict[str, Any] = {
        "job_id": job_id,
        "capability": capability,
        "status": status,
        "duration_s": duration_s(started_at, finished_at),
        "summary": result.get("summary", {}),
        "artifacts": result.get("artifacts", []),
        "error": error,
    }
    if max_bytes is not None and len(encode(body)) > max_bytes:
        body = minimal(body)
    return body

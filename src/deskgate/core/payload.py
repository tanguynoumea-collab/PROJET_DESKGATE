"""Corps du rappel n8n, construit à l'envoi depuis la ligne jobs.

Module pur : stdlib seulement. Contrat (decision-ds-1, 2026-10-23) : le corps porte `summary`,
`data` et `artifacts` du résultat du plugin, tels que l'engine les a figés dans `result_json` ;
au-delà de `CALLBACK_MAX_BYTES` l'engine a déjà déporté `data` (puis `summary`) dans `data.json`
(`summary.json`) et la clé porte `{"path": ..., "truncated": true}`. `data` n'est pas masqué :
un plugin n'y met jamais de secret.
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


def result_parts(result_json: str | None) -> tuple[dict[str, Any], dict[str, Any], list[Any]]:
    """summary, data, artifacts d'un result_json de l'engine ; source unique du rappel et de GET."""
    result = json.loads(result_json) if result_json else {}
    return result.get("summary", {}), result.get("data", {}), result.get("artifacts", [])


def minimal(body: Mapping[str, Any]) -> dict[str, Any]:
    """Copie du corps dont summary et data sont remplacés par le marqueur de troncature."""
    return {**body, "summary": {"truncated": True}, "data": {"truncated": True}}


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
    """Construit le corps du rappel ; dernier recours : summary et data tronqués si trop gros."""
    summary, data, artifacts = result_parts(result_json)
    error = None if error_code is None else {"code": error_code, "message": error_message}
    body: dict[str, Any] = {
        "job_id": job_id,
        "capability": capability,
        "status": status,
        "duration_s": duration_s(started_at, finished_at),
        "summary": summary,
        "data": data,
        "artifacts": artifacts,
        "error": error,
    }
    if max_bytes is not None and len(encode(body)) > max_bytes:
        body = minimal(body)
    return body

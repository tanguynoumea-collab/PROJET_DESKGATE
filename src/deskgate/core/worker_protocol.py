"""Contrat de fichiers runner <-> worker (input.json, events.jsonl, result.json).

Les fichiers sont le transport (D-09). Le SDK côté plugin duplique ``CONTRACT`` en littéral.
"""

from __future__ import annotations

import json
import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

PROTOCOL = 1
RESULT_MAX_BYTES = 1_048_576

ResultState = Literal["valid", "plugin_error", "missing", "invalid", "too_large"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkerInput(_Strict):
    protocol: Literal[1]
    job_id: str
    capability: str
    entry: str
    params: dict[str, Any]
    work_dir: str
    sys_path: list[str]
    settings: dict[str, Any] = Field(default_factory=dict)


class ProgressEvent(_Strict):
    type: Literal["progress"]
    pct: float = Field(ge=0, le=100)
    message: str = ""


class ArtifactEvent(_Strict):
    type: Literal["artifact"]
    kind: str = Field(min_length=1, max_length=64)
    path: str = Field(min_length=1, max_length=1024)


class ResultArtifact(_Strict):
    kind: str = Field(min_length=1, max_length=64)
    path: str = Field(min_length=1, max_length=1024)


class ResultOk(_Strict):
    protocol: Literal[1]
    ok: Literal[True]
    summary: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ResultArtifact] = Field(default_factory=list)


class WorkerError(_Strict):
    type: str
    message: str


class ResultError(_Strict):
    protocol: Literal[1]
    ok: Literal[False]
    error: WorkerError


def _no_constant(name: str) -> object:
    raise ValueError(f"constante JSON non standard : {name}")


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("flottant JSON hors limites")
    return value


def _loads_strict(raw: bytes) -> object:
    """JSON strict (RFC 8259) : NaN, Infinity et flottants hors limites (1e999) refusés."""
    return json.loads(raw, parse_constant=_no_constant, parse_float=_finite_float)


def parse_event(line: bytes) -> ProgressEvent | ArtifactEvent | None:
    """Analyse une ligne de events.jsonl ; ``None`` si JSON ou modèle invalide."""
    try:
        data = _loads_strict(line)
    except (ValueError, RecursionError):
        return None
    if not isinstance(data, dict):
        return None
    kind = data.get("type")
    try:
        if kind == "progress":
            return ProgressEvent.model_validate(data)
        if kind == "artifact":
            return ArtifactEvent.model_validate(data)
    except ValidationError:
        return None
    return None


def parse_result(
    raw: bytes | None, max_bytes: int = RESULT_MAX_BYTES
) -> tuple[ResultState, ResultOk | ResultError | None]:
    """Analyse les octets de result.json (aucun accès disque)."""
    if raw is None:
        return "missing", None
    if len(raw) > max_bytes:
        return "too_large", None
    try:
        data = _loads_strict(raw)
    except (ValueError, RecursionError):
        return "invalid", None
    if not isinstance(data, dict):
        return "invalid", None
    try:
        if data.get("ok") is False:
            return "plugin_error", ResultError.model_validate(data)
        return "valid", ResultOk.model_validate(data)
    except ValidationError:
        return "invalid", None


CONTRACT: dict[str, Any] = {
    "protocol": PROTOCOL,
    "files": {
        "input": "input.json",
        "events": "events.jsonl",
        "result": "result.json",
        "cancel": "cancel.flag",
        "log": "job.log",
    },
    "input_keys": sorted(WorkerInput.model_fields),
    "event_types": ["artifact", "progress"],
    "result_ok_keys": sorted(ResultOk.model_fields),
    "result_error_keys": sorted(ResultError.model_fields),
}

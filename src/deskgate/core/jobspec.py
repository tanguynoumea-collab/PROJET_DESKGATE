"""Contrat de soumission `POST /jobs` : modèle strict, délai effectif, identifiant de tâche.

La resumeUrl est un secret (règle 6) : jamais renvoyée ni journalisée. Aucun message d'erreur
de ce module ne contient la valeur de l'URL.
"""

from __future__ import annotations

import re
import secrets
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from deskgate.core.errors import TIMEOUT_TOO_LARGE

DEFAULT_TIMEOUT_S = 7200
MAX_TIMEOUT_S = 43200
JOB_ID_RE = re.compile(r"^[0-9a-f]{12}$")


class JobRequestError(Exception):
    """Refus d'une demande de tâche, avec un code stable et un statut HTTP."""

    def __init__(self, code: str, message: str, status: int, **extra: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra


class CallbackSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    url: Annotated[str, StringConstraints(pattern=r"^https?://", max_length=2048)]


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    params: dict[str, Any] = Field(default_factory=dict)
    callback: CallbackSpec
    idempotency_key: Annotated[str, StringConstraints(min_length=1, max_length=128)] | None = None
    timeout: Annotated[int, Field(ge=1)] | None = None


def resolve_timeout(requested: int | None, timeout_max: int) -> int:
    """Délai effectif : `min(7200, timeout_max)` par défaut ; refus au-delà de `timeout_max`."""
    if requested is None:
        return min(DEFAULT_TIMEOUT_S, timeout_max)
    if requested > timeout_max:
        raise JobRequestError(
            TIMEOUT_TOO_LARGE,
            f"Délai demandé ({requested} s) supérieur au maximum de la capacité ({timeout_max} s).",
            422,
        )
    return requested


def new_job_id() -> str:
    return secrets.token_hex(6)


def is_valid_job_id(value: str) -> bool:
    return JOB_ID_RE.fullmatch(value) is not None


def work_dir_for(work_root: str, job_id: str) -> str:
    if not is_valid_job_id(job_id):
        raise ValueError("identifiant de tâche invalide")
    return f"{work_root}/{job_id}"

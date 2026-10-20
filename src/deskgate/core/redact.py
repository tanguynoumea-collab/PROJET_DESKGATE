"""Masquage des secrets.

Seule fonction de masquage du projet (logging, API et audit). Formes de la signature masquées :
`signature=`, `signature%3D` (URL encodée) et `"signature": "…"` (JSON, avec ou sans espaces).
"""

from __future__ import annotations

import logging
import re
from typing import Any

_SIGNATURE_RE = re.compile(r"(signature(?:=|%3[dD]))[^&\s#\"']+", re.IGNORECASE)
_SIGNATURE_JSON_RE = re.compile(r"(\"signature\"\s*:\s*\")[^\"]*(\")", re.IGNORECASE)
_SECRET_KEY_RE = re.compile(
    r"token|secret|password|passwd|authorization|api[_-]?key|signature", re.IGNORECASE
)
MASK = "***"


def redact_signature(text: str) -> str:
    """Remplace la valeur du paramètre `signature` (resumeUrl n8n) par `***`."""
    return _SIGNATURE_JSON_RE.sub(r"\1***\2", _SIGNATURE_RE.sub(r"\1***", text))


def redact_params(obj: Any) -> Any:
    """Copie de `obj` où les valeurs de clés secrètes et les signatures sont masquées."""
    if isinstance(obj, dict):
        return {
            k: MASK if isinstance(k, str) and _SECRET_KEY_RE.search(k) else redact_params(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [redact_params(v) for v in obj]
    if isinstance(obj, str):
        return redact_signature(obj)
    return obj


class RedactingFormatter(logging.Formatter):
    """Masque la signature dans la chaîne finale (message et traceback)."""

    def format(self, record: logging.LogRecord) -> str:
        return redact_signature(super().format(record))


class RedactingFilter(logging.Filter):
    """À poser sur les handlers : couvre caplog et les loggers tiers."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_signature(record.getMessage())
        record.args = None
        return True

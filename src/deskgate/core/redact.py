"""Masquage des secrets.

Seule fonction de masquage du projet (utilisée par le logging, l'API et l'audit en phase 3).
"""

from __future__ import annotations

import re

_SIGNATURE_RE = re.compile(r"(signature=)[^&\s#\"']+", re.IGNORECASE)


def redact_signature(text: str) -> str:
    """Remplace la valeur du paramètre `signature` (resumeUrl n8n) par `***`."""
    return _SIGNATURE_RE.sub(r"\1***", text)

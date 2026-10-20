"""Politique pure du rappel n8n : classement des réponses, délai croissant, contrôle d'URL.

Module pur (stdlib seulement) : aucun réseau, aucune base. Le sender et la soumission l'appellent.
"""

from __future__ import annotations

import json
import random
import re
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit

DELIVERED = "delivered"
DELIVERED_DUPLICATE = "delivered_duplicate"
ABANDONED_STALE = "abandoned_stale"
ABANDONED_REJECTED = "abandoned_rejected"
ABANDONED_EXHAUSTED = "abandoned_exhausted"
RETRY_SHORT = "retry_short"
RETRY_BACKOFF = "retry_backoff"
RETRY_MINIMAL = "retry_minimal"
FINAL = frozenset({DELIVERED, DELIVERED_DUPLICATE, ABANDONED_STALE, ABANDONED_REJECTED})
SHORT_CAP_S = 30.0
BODY_READ_MAX = 4096


@dataclass(frozen=True)
class Decision:
    kind: str
    reason: str = ""


def _message(body: bytes | str | None) -> str:
    if not body:
        return ""
    if isinstance(body, bytes):
        text = body[:BODY_READ_MAX].decode("utf-8", "replace")
    else:
        text = body[:BODY_READ_MAX]
    try:
        data = json.loads(text)
        msg = data.get("message") if isinstance(data, dict) else None
    except ValueError:
        msg = None
    return (msg if isinstance(msg, str) else text[:200]).lower()


def classify(
    status: int | None,
    body: bytes | str | None,
    *,
    maybe_delivered: bool,
    prev_status: int | None = None,
) -> Decision:
    """Classe une réponse de n8n 2.43.8 (ou une erreur réseau si `status` est None)."""
    if status is None:
        return Decision(RETRY_BACKOFF, "network")
    if 200 <= status < 300:
        return Decision(DELIVERED)
    if status == 409:
        msg = _message(body)
        if "finished" in msg:
            kind = DELIVERED_DUPLICATE if maybe_delivered else ABANDONED_STALE
            return Decision(kind, "finished")
        if "running already" in msg or "about to resume" in msg:
            return Decision(RETRY_SHORT, "running")
        return Decision(RETRY_SHORT, "unknown_409")
    if status in (401, 403, 404):
        if prev_status != status:  # deux constats consécutifs identiques
            return Decision(RETRY_SHORT, f"confirm_{status}")
        kind = ABANDONED_STALE if status == 404 else ABANDONED_REJECTED
        return Decision(kind, f"http_{status}")
    if status == 413:  # un seul renvoi minimal
        return Decision(RETRY_BACKOFF if prev_status == 413 else RETRY_MINIMAL, "too_large")
    return Decision(RETRY_BACKOFF, f"http_{status}")


def next_delay(
    attempts: int, *, max_backoff_s: float, rng: random.Random, short: bool = False
) -> float:
    """Délai avant la prochaine tentative : 2 s, 4 s, 8 s… gigue ±25 %, plafonné."""
    base = 2.0 * (1.5 if short else 2.0) ** min(max(attempts - 1, 0), 30)
    cap = SHORT_CAP_S if short else float(max_backoff_s)
    return max(0.0, min(cap, base * rng.uniform(0.75, 1.25)))


class CallbackUrlError(ValueError):
    """URL de rappel refusée ; le message ne contient jamais l'URL."""

    def __init__(self, reason: str, host: str | None = None) -> None:
        self.reason = reason
        self.host = host
        if reason == "host_not_allowed":
            self.message = (
                f"Hôte de rappel « {host} » non autorisé : "
                "ajoutez-le à callback_allowed_hosts dans runner.toml."
            )
        else:
            self.message = (
                "URL de rappel refusée : schéma http ou https, sans identifiants, "
                "caractères ASCII visibles seulement."
            )
        super().__init__(self.message)


def check_callback_url(url: str, allowed_hosts: Iterable[str]) -> str:
    """Vérifie l'URL de rappel ; renvoie son nom d'hôte en minuscules."""
    if re.fullmatch(r"[\x21-\x7e]+", url) is None or "\\" in url:
        raise CallbackUrlError("invalid_chars")
    try:
        parts = urlsplit(url)
    except ValueError:
        raise CallbackUrlError("invalid_chars") from None
    if parts.scheme.lower() not in ("http", "https"):
        raise CallbackUrlError("scheme")
    if "@" in parts.netloc:
        raise CallbackUrlError("userinfo")
    host = parts.hostname or ""
    if not host:
        raise CallbackUrlError("no_host")
    try:
        _ = parts.port
    except ValueError:
        raise CallbackUrlError("port") from None
    if host not in {h.lower() for h in allowed_hosts}:
        raise CallbackUrlError("host_not_allowed", host)
    return host

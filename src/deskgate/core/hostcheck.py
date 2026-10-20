"""Contrôle de l'en-tête Host (anti-DNS-rebinding, D-07)."""

from __future__ import annotations

import re

ALLOWED_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "localhost", "host.docker.internal"})

_HOST_RE = re.compile(r"[A-Za-z0-9.\-]+(:\d{1,5})?")


def is_allowed_host(raw: str | None, allowed: frozenset[str] = ALLOWED_HOSTS) -> bool:
    """Vrai si `raw` (valeur brute de l'en-tête Host) désigne un hôte autorisé.

    Forme stricte `hôte[:port]` en ASCII ; `localhost.` et IPv6 sont refusés.
    """
    if not raw or _HOST_RE.fullmatch(raw) is None:
        return False
    host, sep, port = raw.partition(":")
    if sep and int(port) > 65535:
        return False
    return host.lower() in allowed

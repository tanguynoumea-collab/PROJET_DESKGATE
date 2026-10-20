"""Jeton d'authentification : hachage SHA-256, vérification en temps constant.

Aucune journalisation ici : le jeton en clair ne doit jamais quitter ce module.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets


def hash_token(token: str) -> str:
    """Empreinte SHA-256 du jeton, en hexadécimal minuscule."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(presented: str, expected_sha256: str) -> bool:
    """Vrai si l'empreinte du jeton présenté égale l'empreinte attendue (temps constant)."""
    if not presented:
        return False
    return hmac.compare_digest(hash_token(presented), expected_sha256)


def generate_token() -> str:
    """Jeton aléatoire de 256 bits, sûr dans une URL."""
    return secrets.token_urlsafe(32)

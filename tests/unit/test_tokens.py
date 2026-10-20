"""Tests du jeton : hachage, vérification en temps constant, génération."""

from __future__ import annotations

import hashlib

import pytest

from deskgate.core.tokens import generate_token, hash_token, verify_token

pytestmark = pytest.mark.unit


def test_hash_token_est_sha256_hex() -> None:
    assert hash_token("abc") == hashlib.sha256(b"abc").hexdigest()


def test_verify_token_bon_jeton() -> None:
    assert verify_token("abc", hash_token("abc")) is True


def test_verify_token_mauvais_jeton() -> None:
    assert verify_token("abd", hash_token("abc")) is False


def test_verify_token_vide() -> None:
    assert verify_token("", hash_token("abc")) is False


def test_verify_token_empreinte_majuscule_refusee() -> None:
    assert verify_token("abc", hash_token("abc").upper()) is False


def test_verify_token_non_ascii_ne_leve_pas() -> None:
    assert verify_token("é", hash_token("abc")) is False


def test_generate_token_longueur_et_unicite() -> None:
    a, b = generate_token(), generate_token()
    assert len(a) >= 43
    assert a != b

"""build_env : liste blanche, PYTHONUTF8 imposé."""

from __future__ import annotations

import pytest

from deskgate.core.env import build_env

pytestmark = pytest.mark.unit


def test_liste_blanche_sans_secret() -> None:
    base = {"SYSTEMROOT": "C:\\Windows", "PATH": "x", "SECRET_X": "s", "DESKGATE_HOME": "h"}
    env = build_env(base)
    assert env["SYSTEMROOT"] == "C:\\Windows"
    assert env["PATH"] == "x"
    assert env["PYTHONUTF8"] == "1"
    assert "SECRET_X" not in env
    assert "DESKGATE_HOME" not in env


def test_extra_ajoute_mais_ne_retire_pas_utf8() -> None:
    env = build_env({"PATH": "x"}, extra={"OMP_NUM_THREADS": "2", "PYTHONUTF8": "0"})
    assert env["OMP_NUM_THREADS"] == "2"
    assert env["PYTHONUTF8"] == "1"


def test_casse_insensible() -> None:
    assert build_env({"SystemRoot": "C:\\Windows"})["SYSTEMROOT"] == "C:\\Windows"

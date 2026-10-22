"""Les docstrings de module énoncent la politique d'erreur de l'engine et du sender."""

from __future__ import annotations

import pytest

import deskgate.engine
import deskgate.sender

pytestmark = pytest.mark.unit


def test_politique_d_erreur_documentee() -> None:
    assert "Politique d'erreur :" in (deskgate.engine.__doc__ or "")
    assert "Politique d'erreur :" in (deskgate.sender.__doc__ or "")
    assert "interrupted" in (deskgate.engine.__doc__ or "")

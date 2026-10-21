# SPDX-License-Identifier: MIT
"""Paramètres de ifc.clash (params.py) : chargé par chemin, sans IfcOpenShell."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[1] / "src" / "deskgate_bim" / "params.py"
BASE = {"ifc_a": "x.ifc", "selector_a": "IfcWall", "mode": "hard", "tolerance": 0.002}


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dg_params", SRC)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dg_params"] = mod
    spec.loader.exec_module(mod)
    return mod


m = _load()


def test_defauts() -> None:
    p = m.parse_params(BASE)
    assert p.max_clashes is None and p.include_openings is False


def test_max_clashes_zero_refuse() -> None:
    with pytest.raises(m.ClashError) as exc:
        m.parse_params({**BASE, "max_clashes": 0})
    assert exc.value.error_code == "invalid_params"


def test_include_openings_non_booleen() -> None:
    with pytest.raises(m.ClashError) as exc:
        m.parse_params({**BASE, "include_openings": "oui"})
    assert exc.value.error_code == "invalid_params"


def test_parametre_inconnu() -> None:
    with pytest.raises(m.ClashError, match="paramètre inconnu"):
        m.parse_params({**BASE, "bidule": 1})

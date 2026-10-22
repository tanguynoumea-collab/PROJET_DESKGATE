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
    """Charge params.py et naming.py sous un paquet factice (import relatif), sans ifcopenshell."""
    pkg = ModuleType("dg_pkg")
    pkg.__path__ = [str(SRC.parent)]
    sys.modules["dg_pkg"] = pkg
    for name in ("naming", "params"):
        spec = importlib.util.spec_from_file_location(f"dg_pkg.{name}", SRC.parent / f"{name}.py")
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"dg_pkg.{name}"] = mod
        spec.loader.exec_module(mod)
    return sys.modules["dg_pkg.params"]


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


def test_titre_par_defaut() -> None:
    p = m.parse_params(BASE)
    assert p.title_template is None
    assert p.mappings.building is None and p.mappings.storey is None
    assert p.mappings.trade is None and p.mappings.type is None


def test_gabarit_et_tables_acceptes() -> None:
    p = m.parse_params(
        {
            **BASE,
            "title_template": "{building}/{type_a} x {type_b}",
            "mappings": {"building": {"Jura": "BaJ"}},
        }
    )
    assert p.mappings.building == {"Jura": "BaJ"}


def test_gabarit_champ_inconnu() -> None:
    with pytest.raises(m.ClashError) as exc:
        m.parse_params({**BASE, "title_template": "{floor}"})
    assert exc.value.error_code == "invalid_params"
    assert "champ inconnu « floor »" in str(exc.value)


def test_charte_refusee() -> None:
    with pytest.raises(m.ClashError, match="paramètre inconnu : charter"):
        m.parse_params({**BASE, "charter": {}})


def test_table_inconnue() -> None:
    with pytest.raises(m.ClashError, match=r"paramètre inconnu : mappings\.level"):
        m.parse_params({**BASE, "mappings": {"level": {}}})


def test_table_valeur_trop_longue() -> None:
    with pytest.raises(m.ClashError) as exc:
        m.parse_params({**BASE, "mappings": {"type": {"x": "A" * 129}}})
    assert exc.value.error_code == "invalid_params"


def test_table_cle_vide() -> None:
    with pytest.raises(m.ClashError) as exc:
        m.parse_params({**BASE, "mappings": {"type": {"": "A"}}})
    assert exc.value.error_code == "invalid_params"

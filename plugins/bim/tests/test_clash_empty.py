# SPDX-License-Identifier: MIT
"""CAP-03 : sélection vide, classe inconnue ou sans géométrie = succès à 0 conflit averti."""

from __future__ import annotations

from typing import Any

import pytest

from _support.clash_env import ClashEnv

pytestmark = [pytest.mark.bim, pytest.mark.proc]

POUTRE: dict[str, Any] = {
    "ifc_a": "/data/depot/poutre_tuyau.ifc",
    "selector_a": "IfcSlab",
    "selector_b": "IfcPipeSegment",
    "mode": "clearance",
    "clearance": 0.10,
}


def test_aucune_dalle(clash_env: ClashEnv) -> None:
    clash_env.place("poutre_tuyau.ifc")
    row, res = clash_env.run(POUTRE)
    assert row.status == "succeeded", row.error_message
    assert res["summary"]["clashes"] == 0
    assert res["summary"]["warnings"] == ["selection_a_empty"]
    assert res["data"]["groups"] == []


def test_classe_inconnue(clash_env: ClashEnv) -> None:
    clash_env.place("poutre_tuyau.ifc")
    row, res = clash_env.run({**POUTRE, "selector_a": "IfcNotAClass"})
    assert row.status == "succeeded", row.error_message
    assert "selection_a_empty" in res["summary"]["warnings"]
    assert "IfcNotAClass" in res["summary"]["warning_details"][0]["message"]


def test_selection_b_vide(clash_env: ClashEnv) -> None:
    clash_env.place("poutre_tuyau.ifc")
    row, res = clash_env.run({**POUTRE, "selector_a": "IfcBeam", "selector_b": "IfcSlab"})
    assert row.status == "succeeded", row.error_message
    assert res["summary"]["warnings"] == ["selection_b_empty"]


def test_element_sans_geometrie(clash_env: ClashEnv) -> None:
    clash_env.place("mur_gaine.ifc")
    row, res = clash_env.run(
        {
            "ifc_a": "/data/depot/mur_gaine.ifc",
            "selector_a": "IfcWall, Name=Mur_sans_geom",
            "selector_b": "IfcDuctSegment",
            "mode": "hard",
            "tolerance": 0.002,
        }
    )
    assert row.status == "succeeded", row.error_message
    assert res["summary"]["warnings"] == ["selection_a_empty"]
    msg = res["summary"]["warning_details"][0]["message"]
    assert "1 élément(s) trouvé(s), 0 avec géométrie" in msg

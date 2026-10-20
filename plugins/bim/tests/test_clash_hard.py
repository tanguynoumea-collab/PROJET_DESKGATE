# SPDX-License-Identifier: MIT
"""ifc.clash en mode hard : Engine réel, IFC synthétiques, tolérance en mètres."""

from __future__ import annotations

from typing import Any

import pytest

from _support.clash_env import ClashEnv

pytestmark = [pytest.mark.bim, pytest.mark.proc]

BASE: dict[str, Any] = {
    "selector_a": "IfcWall",
    "selector_b": "IfcDuctSegment",
    "mode": "hard",
    "tolerance": 0.002,
}


def pairs(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for g in result["data"]["groups"] for c in g["clashes"]]


def test_mur_traverse_par_une_gaine(clash_env: ClashEnv) -> None:
    clash_env.place("mur_gaine.ifc")
    row, res = clash_env.run({**BASE, "ifc_a": "/data/depot/mur_gaine.ifc"})
    assert row.status == "succeeded", row.error_message
    g = clash_env.guids["mur_gaine.ifc"]
    ps = pairs(res)
    assert len(res["data"]["groups"]) == 1 and len(ps) == 1
    assert ps[0]["type"] == "pierce"
    assert ps[0]["distance"] == pytest.approx(0.2, abs=1e-3)
    assert ps[0]["a_global_id"] == g["Mur1"] and ps[0]["b_global_id"] == g["Gaine1"]
    assert g["Poteau_loin"] not in {ps[0]["a_global_id"], ps[0]["b_global_id"]}
    s = res["summary"]
    assert s["clashes"] == 1 and s["groups"] == 1 and s["truncated"] is False
    assert s["unit"] == "m" and s["tolerance"] == 0.002 and s["mode"] == "hard"
    assert s["ifcopenshell"] and s["warnings"] == []
    assert res["artifacts"] == [
        {"kind": "clashes", "path": f"/data/travail/{clash_env.last_job_id}/clashes.json"}
    ]
    assert (clash_env.work_dir / "clashes.json").is_file()


def test_tolerance_1mm(clash_env: ClashEnv) -> None:
    clash_env.place("gaine_1mm.ifc")
    p = {**BASE, "ifc_a": "/data/depot/gaine_1mm.ifc"}
    row, res = clash_env.run({**p, "tolerance": 0.0005})
    assert row.status == "succeeded", row.error_message
    ps = pairs(res)
    assert len(ps) == 1 and ps[0]["type"] == "protrusion"
    assert ps[0]["distance"] == pytest.approx(0.001, abs=1e-3)
    row, res = clash_env.run({**p, "tolerance": 0.002})
    assert row.status == "succeeded" and pairs(res) == []


def test_maquette_en_millimetres(clash_env: ClashEnv) -> None:
    clash_env.place("mur_gaine_mm.ifc")
    row, res = clash_env.run({**BASE, "ifc_a": "/data/depot/mur_gaine_mm.ifc"})
    assert row.status == "succeeded", row.error_message
    ps = pairs(res)
    assert len(ps) == 1 and ps[0]["type"] == "pierce"
    assert ps[0]["distance"] == pytest.approx(0.2, abs=1e-3)


def test_deux_fichiers(clash_env: ClashEnv) -> None:
    clash_env.place("murs.ifc", "gaines.ifc")
    row, res = clash_env.run(
        {**BASE, "ifc_a": "/data/depot/murs.ifc", "ifc_b": "/data/depot/gaines.ifc"}
    )
    assert row.status == "succeeded", row.error_message
    ps = pairs(res)
    assert len(ps) == 1 and ps[0]["type"] == "pierce"
    assert ps[0]["a_global_id"] == clash_env.guids["murs.ifc"]["Mur1"]
    assert ps[0]["b_global_id"] == clash_env.guids["gaines.ifc"]["Gaine1"]


def test_auto_clash_une_seule_paire(clash_env: ClashEnv) -> None:
    clash_env.place("mur_gaine.ifc")
    row, res = clash_env.run(
        {
            "ifc_a": "/data/depot/mur_gaine.ifc",
            "selector_a": "IfcWall, IfcDuctSegment",
            "mode": "hard",
            "tolerance": 0.002,
        }
    )
    assert row.status == "succeeded", row.error_message
    ps = pairs(res)
    assert len(ps) == 1
    assert ps[0]["a_global_id"] < ps[0]["b_global_id"]


def test_nom_de_fichier_accentue(clash_env: ClashEnv) -> None:
    clash_env.place("Maquette_é.ifc")
    row, res = clash_env.run({**BASE, "ifc_a": "/data/depot/Maquette_é.ifc"})
    assert row.status == "succeeded", row.error_message
    assert len(pairs(res)) == 1

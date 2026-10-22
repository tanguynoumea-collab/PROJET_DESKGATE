# SPDX-License-Identifier: MIT
"""Titres des sujets BCF (CAP-06 révisée) : gabarit et tables du job, IFC synthétiques."""

from __future__ import annotations

import json
from typing import Any

import pytest

from _support.clash_env import ClashEnv

pytestmark = [pytest.mark.bim, pytest.mark.proc]

PIC = "{building}/{storey}/{trade_a}-{trade_b}/{type_a} x {type_b}"
TABLES: dict[str, Any] = {
    "building": {"Jura": "BaJ", "Tour": "BaT"},
    "storey": {"J_10_P00": "P00", "J_11_P01": "P01", "L0": "P00"},
    "trade": {"PIC-CVC-etages": "CVC", "PIC-ARC-etages": "ARC"},
    "type": {"IfcDuctSegment": "Gaine", "IfcWall": "Mur", "IfcCovering/CEILING": "Faux-plafond"},
}
BASE: dict[str, Any] = {
    "mode": "hard",
    "tolerance": 0.002,
    "group_radius": 0.5,
    "bcf": True,
    "created_at": "2026-10-21T10:00:00Z",
}
ETAGES: dict[str, Any] = {
    **BASE,
    "ifc_a": "/data/depot/PIC-CVC-etages.ifc",
    "selector_a": "IfcDuctSegment",
    "ifc_b": "/data/depot/PIC-ARC-etages.ifc",
    "selector_b": "IfcWall",
}


@pytest.fixture
def settings(plugin_envs: dict[str, Any]) -> dict[str, Any]:
    return {"bcf_executable": str(plugin_envs["bcf_exe"])}


def doc(env: ClashEnv) -> dict[str, Any]:
    return json.loads((env.work_dir / "bcf-input.json").read_text(encoding="utf-8"))


def titres(env: ClashEnv) -> list[str]:
    return [t["title"] for t in doc(env)["topics"]]


def lance(
    env: ClashEnv, settings: dict[str, Any], params: dict[str, Any]
) -> tuple[Any, dict[str, Any]]:
    row, res = env.run(params, settings=settings)
    assert row.status == "succeeded", row.error_message
    return row, res


def codes(res: dict[str, Any]) -> list[str]:
    return [d["code"] for d in res["summary"]["warning_details"]]


def test_titres_gabarit_et_tables(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("PIC-CVC-etages.ifc", "PIC-ARC-etages.ifc")
    _, res = lance(clash_env, settings, {**ETAGES, "title_template": PIC, "mappings": TABLES})
    assert titres(clash_env) == [
        "BaJ/P00/CVC-ARC/Gaine x Mur",
        "BaJ/P01/CVC-ARC/Gaine x Mur",
    ]
    assert "mapping_missing" not in codes(res) and "naming_incomplete" not in codes(res)


def test_titres_defaut_sans_gabarit(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("PIC-CVC-etages.ifc", "PIC-ARC-etages.ifc")
    _, res = lance(clash_env, settings, ETAGES)
    assert titres(clash_env) == ["IfcDuctSegment x IfcWall", "IfcDuctSegment x IfcWall"]
    assert "mapping_missing" not in codes(res)


def test_titres_gabarit_sans_tables(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("PIC-CVC-etages.ifc", "PIC-ARC-etages.ifc")
    _, res = lance(clash_env, settings, {**ETAGES, "title_template": PIC})
    assert titres(clash_env) == [
        "Jura/J_10_P00/PIC-CVC-etages-PIC-ARC-etages/IfcDuctSegment x IfcWall",
        "Jura/J_11_P01/PIC-CVC-etages-PIC-ARC-etages/IfcDuctSegment x IfcWall",
    ]
    assert "mapping_missing" not in codes(res)


def test_valeur_absente_de_la_table(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("PIC-CVC-etages.ifc", "PIC-ARC-etages.ifc")
    tables = {**TABLES, "storey": {"J_10_P00": "P00", "L0": "P00"}}
    _, res = lance(clash_env, settings, {**ETAGES, "title_template": PIC, "mappings": tables})
    assert "BaJ/J_11_P01/CVC-ARC/Gaine x Mur" in titres(clash_env)
    assert codes(res).count("mapping_missing") == 1
    (detail,) = [d for d in res["summary"]["warning_details"] if d["code"] == "mapping_missing"]
    assert "storey : J_11_P01" in detail["message"]


def test_gabarit_invalide(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("PIC-CVC-etages.ifc", "PIC-ARC-etages.ifc")
    row, _ = clash_env.run({**ETAGES, "title_template": "{floor}"}, settings=settings)
    assert row.status == "failed"
    assert row.error_message is not None
    assert row.error_message.startswith("invalid_params : ") and "floor" in row.error_message


def test_guid_stable_si_les_tables_changent(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("PIC-CVC-etages.ifc", "PIC-ARC-etages.ifc")

    def empreinte() -> dict[str, Any]:
        return {t["guid"]: (t["guids_a"], t["guids_b"]) for t in doc(clash_env)["topics"]}

    lance(clash_env, settings, ETAGES)
    sans = empreinte()
    lance(clash_env, settings, {**ETAGES, "title_template": PIC, "mappings": TABLES})
    avec = empreinte()
    assert sans == avec and len(sans) == 2


def test_deux_batiments(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("deux_batiments.ifc")
    params = {
        **BASE,
        "ifc_a": "/data/depot/deux_batiments.ifc",
        "selector_a": "IfcDuctSegment",
        "selector_b": "IfcWall",
        "title_template": "{building}/{storey}/{type_a} x {type_b}",
        "mappings": TABLES,
    }
    lance(clash_env, settings, params)
    assert titres(clash_env) == ["BaJ/P00/Gaine x Mur", "BaT/P00/Gaine x Mur"]


def test_ifc2x3_par_type(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("ifc2x3_types.ifc")
    params = {
        **BASE,
        "ifc_a": "/data/depot/ifc2x3_types.ifc",
        "selector_a": "IfcFlowSegment",
        "selector_b": "IfcCovering",
    }
    lance(clash_env, settings, params)
    assert titres(clash_env) == ["T x IfcCovering"]
    lance(clash_env, settings, {**params, "mappings": TABLES})
    assert titres(clash_env) == ["Gaine x Faux-plafond"]


def test_un_seul_bcf_trie(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("PIC-CVC-etages.ifc", "PIC-ARC-etages.ifc")
    _, res = lance(clash_env, settings, {**ETAGES, "title_template": PIC, "mappings": TABLES})
    assert [a["kind"] for a in res["artifacts"]].count("bcf") == 1
    liste = titres(clash_env)
    assert liste == sorted(liste)

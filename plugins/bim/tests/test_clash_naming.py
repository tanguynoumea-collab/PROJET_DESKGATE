# SPDX-License-Identifier: MIT
"""Titres des sujets BCF (CAP-06) : Engine réel, IFC synthétiques, charte en paramètre."""

from __future__ import annotations

import json
from typing import Any

import pytest

from _support.clash_env import ClashEnv

pytestmark = [pytest.mark.bim, pytest.mark.proc]

CHARTE: dict[str, Any] = {
    "buildings": {"Jura": "BaJ", "Tour": "BaT"},
    "levels": {"J_10_P00": "P00", "J_11_P01": "P01", "L0": "P00"},
    "trades": {"a": "CVC", "b": "ARC"},
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


def test_titres_avec_charte(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("PIC-CVC-etages.ifc", "PIC-ARC-etages.ifc")
    _, res = lance(clash_env, settings, {**ETAGES, "charter": CHARTE})
    assert titres(clash_env) == [
        "BaJ/P00/CVC-ARC/Gaine x Mur",
        "BaJ/P01/CVC-ARC/Gaine x Mur",
    ]
    assert "charter_missing" not in res["summary"]["warnings"]


def test_titres_sans_charte(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("PIC-CVC-etages.ifc", "PIC-ARC-etages.ifc")
    _, res = lance(clash_env, settings, ETAGES)
    assert titres(clash_env) == [
        "Jura/J_10_P00/CVC-ARC/Gaine x Mur",
        "Jura/J_11_P01/CVC-ARC/Gaine x Mur",
    ]
    assert "charter_missing" in res["summary"]["warnings"]
    (detail,) = [d for d in res["summary"]["warning_details"] if d["code"] == "charter_missing"]
    for mot in ("Jura", "J_10_P00", "repéré"):
        assert mot in detail["message"]


def test_guid_stable_si_la_charte_change(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("PIC-CVC-etages.ifc", "PIC-ARC-etages.ifc")
    lance(clash_env, settings, ETAGES)
    sans = sorted(t["guid"] for t in doc(clash_env)["topics"])
    lance(clash_env, settings, {**ETAGES, "charter": CHARTE})
    avec = sorted(t["guid"] for t in doc(clash_env)["topics"])
    assert sans == avec and len(sans) == 2


def test_deux_batiments(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("deux_batiments.ifc")
    params = {
        **BASE,
        "ifc_a": "/data/depot/deux_batiments.ifc",
        "selector_a": "IfcDuctSegment",
        "selector_b": "IfcWall",
        "charter": CHARTE,
    }
    lance(clash_env, settings, params)
    assert titres(clash_env) == [
        "BaJ/P00/CVC-ARC/Gaine x Mur",
        "BaT/P00/CVC-ARC/Gaine x Mur",
    ]


def test_ifc2x3_par_type(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("ifc2x3_types.ifc")
    params = {
        **BASE,
        "ifc_a": "/data/depot/ifc2x3_types.ifc",
        "selector_a": "IfcFlowSegment",
        "selector_b": "IfcCovering",
    }
    lance(clash_env, settings, params)
    (titre,) = titres(clash_env)
    assert titre.endswith("/Gaine x Faux-plafond")


def test_un_seul_bcf_trie(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("PIC-CVC-etages.ifc", "PIC-ARC-etages.ifc")
    _, res = lance(clash_env, settings, {**ETAGES, "charter": CHARTE})
    assert [a["kind"] for a in res["artifacts"]].count("bcf") == 1
    liste = titres(clash_env)
    assert liste == sorted(liste)

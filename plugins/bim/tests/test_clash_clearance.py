# SPDX-License-Identifier: MIT
"""ifc.clash en mode clearance : distance minimale en mètres."""

from __future__ import annotations

from typing import Any

import pytest

from _support.clash_env import ClashEnv

pytestmark = [pytest.mark.bim, pytest.mark.proc]

BASE: dict[str, Any] = {
    "ifc_a": "/data/depot/poutre_tuyau.ifc",
    "selector_a": "IfcBeam",
    "selector_b": "IfcPipeSegment",
    "mode": "clearance",
}


def pairs(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for g in result["data"]["groups"] for c in g["clashes"]]


def test_poutre_a_5_cm_du_tuyau(clash_env: ClashEnv) -> None:
    clash_env.place("poutre_tuyau.ifc")
    row, res = clash_env.run({**BASE, "clearance": 0.10})
    assert row.status == "succeeded", row.error_message
    ps = pairs(res)
    assert len(ps) == 1 and ps[0]["type"] == "clearance"
    assert ps[0]["distance"] == pytest.approx(0.05, abs=1e-3)
    g = clash_env.guids["poutre_tuyau.ifc"]
    assert ps[0]["a_global_id"] == g["Poutre1"] and ps[0]["b_global_id"] == g["Tuyau1"]
    # Question ouverte 4 : p1 est sur la poutre A après normalisation, p2 sur le tuyau B.
    assert ps[0]["p1"] == pytest.approx([12, 0.1, 0.15], abs=1e-3)
    assert ps[0]["p2"] == pytest.approx([12, 0.1, 0.1], abs=1e-3)
    assert res["summary"]["clearance"] == 0.10 and "tolerance" not in res["summary"]


def test_clearance_inferieure_a_la_distance(clash_env: ClashEnv) -> None:
    clash_env.place("poutre_tuyau.ifc")
    row, res = clash_env.run({**BASE, "clearance": 0.03})
    assert row.status == "succeeded", row.error_message
    assert pairs(res) == [] and res["summary"]["clashes"] == 0


def test_mode_hard_ne_voit_pas_les_5_cm(clash_env: ClashEnv) -> None:
    clash_env.place("poutre_tuyau.ifc")
    row, res = clash_env.run({**BASE, "mode": "hard", "tolerance": 0.002})
    assert row.status == "succeeded", row.error_message
    assert pairs(res) == []

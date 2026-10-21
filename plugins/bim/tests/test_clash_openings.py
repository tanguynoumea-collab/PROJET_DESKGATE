# SPDX-License-Identifier: MIT
"""Réservations (IfcOpeningElement) exclues par défaut de ifc.clash (D-11)."""

from __future__ import annotations

from typing import Any

import pytest

from _support.clash_env import ClashEnv

pytestmark = [pytest.mark.bim, pytest.mark.proc]

BASE: dict[str, Any] = {
    "ifc_a": "/data/depot/reservation.ifc",
    "selector_a": "IfcDuctSegment",
    "selector_b": "IfcWall, IfcOpeningElement",
    "mode": "hard",
    "tolerance": 0.002,
}


def pairs(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for g in result["data"]["groups"] for c in g["clashes"]]


def test_reservations_exclues_par_defaut(clash_env: ClashEnv) -> None:
    clash_env.place("reservation.ifc")
    row, res = clash_env.run(BASE)
    assert row.status == "succeeded", row.error_message
    g = clash_env.guids["reservation.ifc"]
    assert res["data"]["counts"]["clashes"] == 1
    ps = pairs(res)
    assert len(ps) == 1
    assert {ps[0]["a_global_id"], ps[0]["b_global_id"]} == {g["Gaine1"], g["Mur1"]}
    assert res["data"]["counts"]["openings_excluded"] == 1


def test_include_openings(clash_env: ClashEnv) -> None:
    clash_env.place("reservation.ifc")
    row, res = clash_env.run({**BASE, "include_openings": True})
    assert row.status == "succeeded", row.error_message
    assert res["data"]["counts"]["clashes"] == 2
    assert res["data"]["counts"]["openings_excluded"] == 0


def test_selection_reservations_seules_vide(clash_env: ClashEnv) -> None:
    clash_env.place("reservation.ifc")
    row, res = clash_env.run({**BASE, "selector_b": "IfcOpeningElement"})
    assert row.status == "succeeded", row.error_message
    assert "selection_b_empty" in res["summary"]["warnings"]
    detail = next(d for d in res["summary"]["warning_details"] if d["code"] == "selection_b_empty")
    assert "include_openings" in detail["message"]

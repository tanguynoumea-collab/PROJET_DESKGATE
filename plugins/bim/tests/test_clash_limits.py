# SPDX-License-Identifier: MIT
"""Regroupement, plafonds, déterminisme et progression de ifc.clash de bout en bout."""

from __future__ import annotations

import json
from typing import Any

import pytest

from _support.clash_env import ClashEnv

pytestmark = [pytest.mark.bim, pytest.mark.proc]

CINQ: dict[str, Any] = {
    "ifc_a": "/data/depot/cinq_gaines.ifc",
    "selector_a": "IfcWall",
    "selector_b": "IfcDuctSegment",
    "mode": "hard",
    "tolerance": 0.002,
}


@pytest.mark.parametrize(("rayon", "tailles"), [(1.0, [1] * 5), (10.0, [5]), (0, [1] * 5)])
def test_regroupement(clash_env: ClashEnv, rayon: float, tailles: list[int]) -> None:
    clash_env.place("cinq_gaines.ifc")
    row, res = clash_env.run({**CINQ, "group_radius": rayon})
    assert row.status == "succeeded", row.error_message
    assert [g["count"] for g in res["data"]["groups"]] == tailles
    assert res["summary"]["clashes"] == 5


def test_max_clashes(clash_env: ClashEnv) -> None:
    clash_env.place("cinq_gaines.ifc")
    row, res = clash_env.run({**CINQ, "max_clashes": 2})
    assert row.status == "succeeded", row.error_message
    assert res["data"]["counts"]["clashes"] == 5
    assert res["data"]["counts"]["returned"] == 2
    assert res["data"]["truncated"] is True and res["summary"]["truncated"] is True
    assert "clashes_truncated" in res["summary"]["warnings"]


def test_data_trop_grosse(clash_env: ClashEnv) -> None:
    clash_env.place("cinq_gaines.ifc")
    row, res = clash_env.run(CINQ, settings={"data_max_bytes": 200})
    assert row.status == "succeeded", row.error_message
    for r in (res["data"], res["summary"]):
        assert r["pairs_omitted"] is True and r["truncated"] is False
    assert "data_pairs_omitted" in res["summary"]["warnings"]
    complet = json.loads((clash_env.work_dir / "clashes.json").read_text(encoding="utf-8"))
    assert sum(len(g["clashes"]) for g in complet["groups"]) == 5


def test_groupes_omis(clash_env: ClashEnv) -> None:
    clash_env.place("cinq_gaines.ifc")
    row, res = clash_env.run({**CINQ, "group_radius": 0}, settings={"data_max_bytes": 1})
    assert row.status == "succeeded", row.error_message
    assert res["data"]["groups"] == []
    assert res["data"]["groups_omitted"] is True and res["summary"]["groups_omitted"] is True
    assert res["data"]["counts"]["groups"] == 5
    assert "data_groups_omitted" in res["summary"]["warnings"]
    complet = json.loads((clash_env.work_dir / "clashes.json").read_text(encoding="utf-8"))
    assert len(complet["groups"]) == 5


@pytest.mark.parametrize("limite", [300, 600, 1200])
def test_taille_bornee(clash_env: ClashEnv, limite: int) -> None:
    clash_env.place("cinq_gaines.ifc")
    row, res = clash_env.run({**CINQ, "group_radius": 0}, settings={"data_max_bytes": limite})
    assert row.status == "succeeded", row.error_message
    assert len(json.dumps(res["data"], ensure_ascii=False)) <= limite or res["data"]["groups"] == []


MILLE: dict[str, Any] = {
    "ifc_a": "/data/depot/mille_conflits.ifc",
    "selector_a": "IfcSlab",
    "selector_b": "IfcDuctSegment",
    "mode": "hard",
    "tolerance": 0.002,
    "group_radius": 0,
}


def test_sans_plafond_par_defaut(clash_env: ClashEnv) -> None:
    clash_env.place("mille_conflits.ifc")
    row, res = clash_env.run(MILLE)
    assert row.status == "succeeded", row.error_message
    counts = res["data"]["counts"]
    assert counts["clashes"] == 1024 == counts["returned"]
    assert res["data"]["truncated"] is False and res["summary"]["truncated"] is False
    assert "clashes_truncated" not in res["summary"]["warnings"]
    row, res = clash_env.run({**MILLE, "max_clashes": 1000})
    assert row.status == "succeeded", row.error_message
    assert res["data"]["truncated"] is True
    assert res["data"]["counts"]["returned"] == 1000


def test_deterministe(clash_env: ClashEnv) -> None:
    clash_env.place("cinq_gaines.ifc")
    row1, res1 = clash_env.run({**CINQ, "group_radius": 3.0})
    bytes1 = (clash_env.work_dir / "clashes.json").read_bytes()
    row2, res2 = clash_env.run({**CINQ, "group_radius": 3.0})
    bytes2 = (clash_env.work_dir / "clashes.json").read_bytes()
    assert row1.status == row2.status == "succeeded"
    assert res1["data"] == res2["data"]
    assert [g["id"] for g in res1["data"]["groups"]] == [g["id"] for g in res2["data"]["groups"]]
    assert bytes1 == bytes2


def test_progression(clash_env: ClashEnv) -> None:
    clash_env.place("cinq_gaines.ifc")
    row, _ = clash_env.run(CINQ)
    assert row.status == "succeeded", row.error_message
    lines = (clash_env.work_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    pcts = [e["pct"] for e in map(json.loads, lines) if e["type"] == "progress"]
    assert 3 <= len(pcts) <= 210
    assert pcts == sorted(pcts) and pcts[-1] == 100

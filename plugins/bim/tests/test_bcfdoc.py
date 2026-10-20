# SPDX-License-Identifier: MIT
"""Document bcf-write-v1 (bcfdoc.py) : chargé par chemin, validé contre le contrat JSON."""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from jsonschema import Draft202012Validator

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[1] / "src" / "deskgate_bim" / "bcfdoc.py"
SCHEMA = Path(__file__).resolve().parents[3] / "docs" / "contrats" / "bcf-write-v1.json"
GUID_A = "0AAAAAAAAAAAAAAAAAAAAA"
GUID_B = "0BBBBBBBBBBBBBBBBBBBBB"
GUID_C = "0CCCCCCCCCCCCCCCCCCCCC"
GUID_D = "0DDDDDDDDDDDDDDDDDDDDD"
GROUP_ID = "5b6e8d1e-6a0c-5f3c-8a46-0e1d9a3c7b21"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dg_bcfdoc", SRC)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dg_bcfdoc"] = mod
    spec.loader.exec_module(mod)
    return mod


m = _load()
VALIDATOR = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))


def pair(a: str, b: str, p1: list[float], p2: list[float], na: str = "Mur1", nb: str = "Gaine1"):
    return {
        "a_global_id": a,
        "b_global_id": b,
        "a_ifc_class": "IfcWall",
        "b_ifc_class": "IfcDuctSegment",
        "a_name": na,
        "b_name": nb,
        "type": "pierce",
        "distance": 0.2,
        "p1": p1,
        "p2": p2,
    }


def group(pairs: list[dict[str, Any]], centre: list[float]) -> dict[str, Any]:
    return {"id": GROUP_ID, "centre": centre, "count": len(pairs), "clashes": pairs}


def doc(groups: list[dict[str, Any]], **kw: Any) -> dict[str, Any]:
    args: dict[str, Any] = {
        "project": "P",
        "author": "deskgate",
        "created_at": "2026-10-21T10:00:00Z",
        "context": {},
        "mode": "hard",
        "threshold": 0.002,
    }
    args.update(kw)
    return m.build_doc(groups, **args)


def test_document_valide_contre_le_contrat() -> None:
    g = group([pair(GUID_A, GUID_B, [0, 0, 0], [0, 0.2, 0])], [0, 0.1, 0])
    d = doc([g], context={GROUP_ID: [GUID_C]})
    assert list(VALIDATOR.iter_errors(d)) == []
    assert d["schema_version"] == 1 and d["colors"] == m.DEFAULT_COLORS


def test_un_sujet_par_groupe_et_champs_du_sujet() -> None:
    g = group([pair(GUID_A, GUID_B, [0, 0, 0], [0, 0.2, 0])], [0, 0.1, 0])
    (t,) = doc([g])["topics"]
    assert t["guid"] == GROUP_ID and t["type"] == "Clash" and t["status"] == "Open"
    assert t["title"] == "Mur1 x Gaine1"
    assert (
        "hard" in t["description"] and "0.002" in t["description"] and "1 paire" in t["description"]
    )
    assert t["camera"]["type"] == "perspective" and t["camera"]["target"] == [0, 0.1, 0]


def test_guids_tries_uniques_et_titre_avec_surplus() -> None:
    pairs = [
        pair(GUID_B, GUID_D, [0, 0, 0], [0, 0, 0]),
        pair(GUID_A, GUID_D, [0, 0, 0], [0, 0, 0]),
        pair(GUID_A, GUID_C, [0, 0, 0], [0, 0, 0]),
    ]
    (t,) = doc([group(pairs, [0, 0, 0])])["topics"]
    assert t["guids_a"] == [GUID_A, GUID_B]
    assert t["guids_b"] == [GUID_C, GUID_D]
    assert t["title"].endswith("(+2)")


def test_titre_replie_sur_la_classe_ifc_si_nom_vide() -> None:
    g = group([pair(GUID_A, GUID_B, [0, 0, 0], [0, 0, 0], na="", nb="")], [0, 0, 0])
    assert doc([g])["topics"][0]["title"] == "IfcWall x IfcDuctSegment"


def test_rayon_de_camera() -> None:
    near = group([pair(GUID_A, GUID_B, [0, 0, 0], [0, 0, 0])], [0, 0, 0])
    assert doc([near])["topics"][0]["camera"]["radius"] == 1.0
    far = group(
        [pair(GUID_A, GUID_B, [0, 0, 0], [0, 0, 0]), pair(GUID_C, GUID_D, [10, 0, 0], [10, 0, 0])],
        [0, 0, 0],
    )
    assert doc([far])["topics"][0]["camera"]["radius"] == pytest.approx(10.5)


def test_contexte_ne_contient_pas_le_conflit() -> None:
    g = group([pair(GUID_A, GUID_B, [0, 0, 0], [0, 0, 0])], [0, 0, 0])
    t = doc([g], context={GROUP_ID: [GUID_C, GUID_D]})["topics"][0]
    assert t["context_guids"] == [GUID_C, GUID_D]
    assert not set(t["context_guids"]) & (set(t["guids_a"]) | set(t["guids_b"]))
    assert doc([g])["topics"][0]["context_guids"] == []


def test_determinisme() -> None:
    g = group([pair(GUID_A, GUID_B, [0, 0, 0], [0, 0.2, 0])], [0, 0.1, 0])
    assert json.dumps(doc([g]), sort_keys=True) == json.dumps(doc([g]), sort_keys=True)


def test_bcfdoc_stdlib_seule() -> None:
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    mods: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    assert mods <= set(sys.stdlib_module_names)

# SPDX-License-Identifier: MIT
"""Nommage des sujets BCF (naming.py) : chargé par chemin, sans IfcOpenShell."""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[1] / "src" / "deskgate_bim" / "naming.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dg_naming", SRC)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dg_naming"] = mod
    spec.loader.exec_module(mod)
    return mod


n = _load()


def test_build_title_nominal():
    assert (
        n.build_title("BaJ", "P01", "CVC", "ARC", "Gaine", "Faux-plafond")
        == "BaJ/P01/CVC-ARC/Gaine x Faux-plafond"
    )


def test_build_title_assainit_et_tronque():
    assert n.build_title("Ba/J", "P\n01", "", "ARC", "a", "b") == "Ba-J/P 01/?-ARC/a x b"
    assert len(n.build_title("B", "E", "T", "U", "x" * 600, "y")) == 512


def test_build_title_sans_suffixe():
    assert "(+" not in n.build_title("B", "E", "T", "U", "a", "b")


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, "?"), ("", "?"), ("   ", "?"), ("a/b\\c", "a-b-c"), (" a \t\n b ", "a b")],
)
def test_sanitize(value, expected):
    assert n.sanitize(value) == expected


def test_lookup_exact_puis_casse():
    m = {" Jura ": "BaJ", "Tour": "BaT"}
    assert n.lookup(m, "Jura") == "BaJ"
    assert n.lookup(m, "tour") == "BaT"
    assert n.lookup(m, None) is None
    assert n.lookup(m, "autre") is None


def _info(cls, predefined=None, type_class=None, supertypes=()):
    return {
        "ifc_class": cls,
        "predefined": predefined,
        "type_class": type_class,
        "supertypes": list(supertypes),
    }


def test_element_label_ifc2x3_par_type():
    info = _info(
        "IfcFlowSegment",
        None,
        "IfcDuctSegment",
        ["IfcDistributionFlowElement", "IfcDistributionElement", "IfcElement"],
    )
    assert n.element_label(info, {}) == ("Gaine", False)


def test_element_label_plafond():
    info = _info("IfcCovering", "CEILING", "IfcCovering", ["IfcBuildingElement", "IfcElement"])
    assert n.element_label(info, {}) == ("Faux-plafond", False)


def test_element_label_ifc4_flexible():
    assert n.element_label(_info("IfcDuctSegment", "FLEXIBLESEGMENT"), {}) == (
        "Gaine flexible",
        False,
    )


def test_element_label_charte_prioritaire():
    info = _info("IfcCovering", "CEILING", "IfcCovering", ["IfcBuildingElement", "IfcElement"])
    assert n.element_label(info, {"ifccovering/ceiling": "Plafond"}) == ("Plafond", False)
    assert n.element_label(info, {"IfcCovering": "Habillage"}) == ("Habillage", False)


def test_element_label_super_type():
    info = _info("IfcWallStandardCase", None, None, ["IfcWall", "IfcBuildingElement"])
    assert n.element_label(info, {}) == ("Mur", False)


def test_element_label_inconnu():
    assert n.element_label(_info("IfcFooBar"), {}) == ("IfcFooBar", True)


LEVELS = [(382.9, "J_11_P01"), (378.0, "J_10_P00"), (386.4, "J_12_P02")]


@pytest.mark.parametrize(
    ("z", "expected"),
    [(382.8999, "J_11_P01"), (380.0, "J_10_P00"), (370.0, "J_10_P00"), (500.0, "J_12_P02")],
)
def test_bracket_storey(z, expected):
    assert n.bracket_storey(LEVELS, z) == expected


def test_bracket_storey_vide():
    assert n.bracket_storey([], 1.0) is None


def _pair(a, b, ca="IfcA", cb="IfcB"):
    return {"a_global_id": a, "b_global_id": b, "a_ifc_class": ca, "b_ifc_class": cb}


def test_pick_principal_majorite():
    pairs = [_pair("a1", "b1"), _pair("a2", "b2"), _pair("a3", "b3")]
    labels = {"a1": "Gaine", "b1": "Mur", "a2": "Gaine", "b2": "Dalle", "a3": "Gaine", "b3": "Mur"}
    assert n.pick_principal(pairs, labels) == ("Gaine", "Mur", "a1")


def test_pick_principal_egalite_premiere_occurrence():
    pairs = [_pair("a1", "b1"), _pair("a2", "b2")]
    labels = {"a1": "Gaine", "b1": "Dalle", "a2": "Gaine", "b2": "Mur"}
    assert n.pick_principal(pairs, labels) == ("Gaine", "Dalle", "a1")


def test_pick_principal_repli_classe():
    assert n.pick_principal([_pair("a1", "b1", "IfcX", "IfcY")], {}) == ("IfcX", "IfcY", "a1")


def test_trade_code_charte():
    assert n.trade_code("CVC", "x") == ("CVC", None)


def test_trade_code_nom_de_fichier():
    code, note = n.trade_code(None, "PIC-EXE-AW-CVC-MNQ-BaJ-SUP-30701-IFC4")
    assert code == "CVC" and note is not None and "repéré" in note
    assert n.trade_code(None, "PIC_REV_HRS_ARC_MNQ_BaJ_SUP_30400")[0] == "ARC"
    assert n.trade_code("", "PIC-ARC")[0] == "ARC"


def test_trade_code_tronque():
    code, note = n.trade_code(None, "maquette_essai_longue")
    assert code == "maquette_ess" and note is not None and "tronqué" in note


def test_missing_message():
    assert n.missing_message(["niveau : J_11_P01", "bâtiment : Jura", "niveau : J_11_P01"]) == (
        "Valeurs absentes de la charte (valeur brute dans le titre) : "
        "bâtiment : Jura ; niveau : J_11_P01."
    )
    assert len(n.missing_message([f"v{i}" * 50 for i in range(500)])) <= 2000


def test_fallback_message():
    assert n.fallback_message(["IfcB", "IfcA", "IfcB"]) == (
        "Libellé inconnu, classe IFC brute dans le titre : IfcA, IfcB."
    )


def test_naming_stdlib_seule():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert mods <= set(sys.stdlib_module_names) | {"__future__"}

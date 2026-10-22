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


PIC = "{building}/{storey}/{trade_a}-{trade_b}/{type_a} x {type_b}"
CHAMPS = "building, storey, trade_a, trade_b, type_a, type_b"


def test_template_fields_ordre():
    assert n.template_fields(PIC) == [
        "building",
        "storey",
        "trade_a",
        "trade_b",
        "type_a",
        "type_b",
    ]


def test_template_fields_sans_doublon():
    assert n.template_fields("{type_a}/{type_a}") == ["type_a"]


def test_template_fields_inconnu():
    with pytest.raises(ValueError) as exc:
        n.template_fields("{floor}/{type_a}")
    assert "floor" in str(exc.value) and CHAMPS in str(exc.value)
    assert "champ inconnu" in str(exc.value)


@pytest.mark.parametrize("bad", ["{type_a} x {type_b", "type}", "{{type_a}"])
def test_template_fields_accolade(bad):
    with pytest.raises(ValueError, match="accolade non appariée"):
        n.template_fields(bad)


def test_template_fields_aucun_champ():
    with pytest.raises(ValueError, match="aucun champ"):
        n.template_fields("Conflit")


def test_render_title_nominal():
    values = {
        "building": "BaJ",
        "storey": "P01",
        "trade_a": "CVC",
        "trade_b": "ARC",
        "type_a": "Gaine",
        "type_b": "Faux-plafond",
    }
    assert n.render_title(PIC, values) == "BaJ/P01/CVC-ARC/Gaine x Faux-plafond"


def test_render_title_assainit_et_tronque():
    assert n.render_title("{building}/{storey}", {"building": "Ba/J", "storey": "P\n01"}) == (
        "Ba-J/P 01"
    )
    assert len(n.render_title("{type_a}", {"type_a": "x" * 600})) == 512


def test_render_title_repete_et_vide():
    assert n.render_title("{type_a}+{type_a}", {"type_a": "G"}) == "G+G"
    assert n.render_title("{type_a}", {}) == "?"


def test_resolve():
    assert n.resolve(None, ["Jura"], "Jura") == ("Jura", False)
    assert n.resolve({"Jura": "BaJ"}, ["Jura"], "Jura") == ("BaJ", False)
    assert n.resolve({"jura": "BaJ"}, ["Jura"], "Jura") == ("BaJ", False)
    assert n.resolve({"Tour": "BaT"}, ["Jura"], "Jura") == ("Jura", True)


def test_type_candidates():
    info = {
        "ifc_class": "IfcFlowSegment",
        "predefined": "RIGIDSEGMENT",
        "type_class": "IfcDuctSegment",
        "type_name": "T",
        "type_ifc_class": "IfcDuctSegmentType",
        "supertypes": ["IfcDistributionFlowElement"],
    }
    assert n.type_candidates(info)[:6] == [
        "IfcDuctSegmentType:T",
        "T",
        "IfcDuctSegment/RIGIDSEGMENT",
        "IfcDuctSegment",
        "IfcFlowSegment/RIGIDSEGMENT",
        "IfcFlowSegment",
    ]


def test_type_raw():
    assert n.type_raw({"type_name": "T", "ifc_class": "IfcX"}) == "T"
    assert n.type_raw({"type_name": None, "ifc_class": "IfcX"}) == "IfcX"


def test_pas_de_valeur_metier_dans_la_source():
    text = SRC.read_text(encoding="utf-8")
    for banned in ("LABELS", "TRADE_CODES", "Charter", '"Gaine"', '"CVC"', '"BaJ"'):
        assert banned not in text
    assert not hasattr(n, "LABELS") and not hasattr(n, "TRADE_CODES")
    assert n.DEFAULT_TEMPLATE == "{type_a} x {type_b}"


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


def test_missing_message():
    assert n.missing_message(["storey : J_11_P01", "type : IfcFoo", "storey : J_11_P01"]) == (
        "Valeurs absentes des tables de correspondance (valeur brute dans le titre) : "
        "storey : J_11_P01 ; type : IfcFoo."
    )
    assert len(n.missing_message([f"v{i}" * 50 for i in range(500)])) <= 2000


def test_incomplete_message():
    assert n.incomplete_message(["storey", "building", "storey"]) == (
        "Champs du titre introuvables dans les maquettes (« ? » dans le titre) : "
        "building, storey."
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

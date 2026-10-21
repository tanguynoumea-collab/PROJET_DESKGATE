# SPDX-License-Identifier: MIT
"""Post-traitement pur (grouping.py) : chargé par chemin, sans IfcOpenShell."""

from __future__ import annotations

import ast
import importlib.util
import itertools
import math
import random
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[1] / "src" / "deskgate_bim" / "grouping.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dg_grouping", SRC)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dg_grouping"] = mod
    spec.loader.exec_module(mod)
    return mod


g = _load()


def clash(a: str, b: str, x: float = 0.0, d: float = 0.2) -> dict:
    return {
        "a_global_id": a,
        "b_global_id": b,
        "a_ifc_class": "Cls" + a[0],
        "b_ifc_class": "Cls" + b[0],
        "a_name": "n" + a,
        "b_name": "n" + b,
        "type": "pierce",
        "p1": [x, 0.0, 0.0],
        "p2": [x, 0.0, 0.2],
        "distance": d,
    }


def test_normalise_echange_si_inverse():
    c = clash("B1", "A1")
    out = g.normalise(c, {"A1"}, {"B1"})
    assert (out["a_global_id"], out["b_global_id"]) == ("A1", "B1")
    assert out["a_ifc_class"] == "ClsA" and out["b_ifc_class"] == "ClsB"
    assert out["a_name"] == "nA1" and out["b_name"] == "nB1"
    assert out["p1"] == [0.0, 0.0, 0.2] and out["p2"] == [0.0, 0.0, 0.0]


def test_normalise_aligne_inchange():
    c = clash("A1", "B1")
    before = dict(c)
    assert g.normalise(c, {"A1"}, {"B1"}) == before


def test_normalise_auto_clash_ordre_lexicographique():
    out = g.normalise(clash("Z", "A"), {"A", "Z"}, {"A", "Z"})
    assert (out["a_global_id"], out["b_global_id"]) == ("A", "Z")
    out2 = g.normalise(clash("A", "Z"), {"A", "Z"}, {"A", "Z"})
    assert (out2["a_global_id"], out2["b_global_id"]) == ("A", "Z")


def test_prepare_filtre_auto_paire_et_doublons():
    raw = [clash("A1", "A1"), clash("A1", "B1"), clash("B1", "A1")]
    out = g.prepare(raw, {"A1"}, {"B1"})
    assert len(out) == 1 and out[0]["a_global_id"] == "A1"


def test_prepare_independant_de_l_ordre_et_de_l_orientation():
    pairs = [("A3", "B1"), ("A1", "B2"), ("A2", "B2"), ("A1", "B1")]
    sel_a, sel_b = {"A1", "A2", "A3"}, {"B1", "B2"}
    ref = None
    for perm in itertools.permutations(pairs):
        for flip in (False, True):
            raw = [clash(b, a, i) if flip else clash(a, b, i) for i, (a, b) in enumerate(perm)]
            raw = [dict(c, p1=[0.0, 0.0, 0.0], p2=[0.0, 0.0, 0.0]) for c in raw]
            out = g.prepare(raw, sel_a, sel_b)
            keys = [(c["a_global_id"], c["b_global_id"]) for c in out]
            assert keys == sorted(keys)
            ref = ref or out
            assert out == ref


@pytest.mark.parametrize(("radius", "attendu"), [(0, 5), (1.0, 5), (10.0, 1)])
def test_group_clashes_rayon(radius: float, attendu: int):
    cl = [clash(f"A{i}", "B", x=i * 2.0) for i in range(5)]
    groups = g.group_clashes(g.prepare(cl, {f"A{i}" for i in range(5)}, {"B"}), radius)
    assert len(groups) == attendu
    flat = [c["a_global_id"] for grp in groups for c in grp]
    assert flat == sorted(flat)


def test_build_groups_structure():
    cl = g.prepare([clash("A1", "B1"), clash("A2", "B1", x=1.0)], {"A1", "A2"}, {"B1"})
    groups = g.build_groups(cl, 10.0, "hard", 0.002)
    assert len(groups) == 1 and groups[0]["count"] == 2
    assert groups[0]["centre"] == [0.5, 0.0, 0.1]


def test_group_guid_stable_et_sensible():
    m = [clash("A1", "B1"), clash("A2", "B2")]
    base = g.group_guid(m, "hard", 0.002)
    assert base == g.group_guid(list(reversed(m)), "hard", 0.002)
    assert base != g.group_guid(m, "clearance", 0.002)
    assert base != g.group_guid(m, "hard", 0.003)
    assert base == g.group_guid(m, "hard", 0.002)


def test_grouping_stdlib_seule():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert mods <= set(sys.stdlib_module_names) | {"__future__"}


def _reference_group_clashes(clashes: list[dict], radius: float) -> list[list[dict]]:
    """Algorithme linéaire d'origine, figé comme référence (D-13)."""
    if radius <= 0:
        return [[c] for c in clashes]
    groups: list[tuple[list[float], list[dict]]] = []
    for c in clashes:
        m = g.midpoint(c)
        for centre, members in groups:
            if math.dist(centre, m) <= radius:
                members.append(c)
                break
        else:
            groups.append((m, [c]))
    return [members for _, members in groups]


@pytest.mark.parametrize("radius", [0.5, 2.0, 7.3])
def test_grille_equivalente(radius: float):
    rng = random.Random(0)
    cl = []
    for i in range(5000):
        c = clash(f"A{i:05d}", f"B{i:05d}")
        c["p1"] = [rng.uniform(0, 50) for _ in range(3)]
        c["p2"] = [rng.uniform(0, 50) for _ in range(3)]
        cl.append(c)
    cl.sort(key=g.sort_key)

    def ids(groups: list[list[dict]]) -> list[list[tuple[str, str]]]:
        return [[(c["a_global_id"], c["b_global_id"]) for c in m] for m in groups]

    assert ids(g.group_clashes(cl, radius)) == ids(_reference_group_clashes(cl, radius))
    assert g.group_clashes(cl[:50], 0) == _reference_group_clashes(cl[:50], 0)


def test_group_guid_fige():
    m = [clash("A1", "B1"), clash("A2", "B2")]
    assert g.group_guid(m, "hard", 0.002) == g.group_guid(m, "hard", 0.002)
    assert g.NS.hex == "6f1c2b7e3b1e5d0a9a532f0f8e5d7a10"

# SPDX-License-Identifier: MIT
"""Post-traitement pur des conflits : normalisation a/b, tri, regroupement, GUID (stdlib seule)."""

from __future__ import annotations

import itertools
import math
import uuid
from collections.abc import Iterable
from typing import Any

# Constante du projet : ne plus jamais la changer (les GUID de groupe en dépendent).
NS = uuid.UUID("6f1c2b7e-3b1e-5d0a-9a53-2f0f8e5d7a10")

_SWAPPED = ("global_id", "ifc_class", "name")


def _swap(c: dict[str, Any]) -> None:
    for k in _SWAPPED:
        c["a_" + k], c["b_" + k] = c["b_" + k], c["a_" + k]
    c["p1"], c["p2"] = c["p2"], c["p1"]


def normalise(c: dict[str, Any], sel_a: set[str], sel_b: set[str]) -> dict[str, Any]:
    """Aligne a sur la sélection A et b sur la sélection B ; ordre des GlobalId si ambigu."""
    a, b = c["a_global_id"], c["b_global_id"]
    in_a_first = a in sel_a
    swap = (not in_a_first and b in sel_a) or (in_a_first == (b in sel_a) and a > b)
    if swap:
        _swap(c)
    return c


def midpoint(c: dict[str, Any]) -> list[float]:
    return [(a + b) / 2 for a, b in zip(c["p1"], c["p2"], strict=True)]


def sort_key(c: dict[str, Any]) -> tuple[str, str]:
    return (c["a_global_id"], c["b_global_id"])


def prepare(
    clashes: Iterable[dict[str, Any]], sel_a: set[str], sel_b: set[str]
) -> list[dict[str, Any]]:
    """Copie, filtre a == b, dédoublonne, normalise, arrondit et trie de façon déterministe."""
    out: dict[frozenset[str], dict[str, Any]] = {}
    for raw in clashes:
        if raw["a_global_id"] == raw["b_global_id"]:
            continue
        c = dict(raw)
        c["p1"], c["p2"] = list(c["p1"]), list(c["p2"])
        key = frozenset((c["a_global_id"], c["b_global_id"]))
        if key in out:
            continue
        normalise(c, sel_a, sel_b)
        c["distance"] = round(float(c["distance"]), 6)
        c["p1"] = [round(float(x), 6) for x in c["p1"]]
        c["p2"] = [round(float(x), 6) for x in c["p2"]]
        out[key] = c
    return sorted(out.values(), key=sort_key)


def group_clashes(clashes: list[dict[str, Any]], radius: float) -> list[list[dict[str, Any]]]:
    """Regroupe par proximité des milieux (premier membre = centre) ; `clashes` déjà triés.

    Grille spatiale de pas `radius` ; mêmes groupes que la recherche linéaire (premier groupe,
    dans l'ordre de création, dont le centre est à au plus `radius`).
    """
    if radius <= 0:
        return [[c] for c in clashes]
    centres: list[list[float]] = []
    members_of: list[list[dict[str, Any]]] = []
    cells: dict[tuple[int, int, int], list[int]] = {}

    def key(p: list[float]) -> tuple[int, int, int]:
        return (math.floor(p[0] / radius), math.floor(p[1] / radius), math.floor(p[2] / radius))

    for c in clashes:
        m = midpoint(c)
        kx, ky, kz = key(m)
        best = -1
        for dx, dy, dz in itertools.product(range(-2, 3), repeat=3):
            for gi in cells.get((kx + dx, ky + dy, kz + dz), ()):
                if (best < 0 or gi < best) and math.dist(centres[gi], m) <= radius:
                    best = gi
        if best >= 0:
            members_of[best].append(c)
        else:
            cells.setdefault((kx, ky, kz), []).append(len(centres))
            centres.append(m)
            members_of.append([c])
    return members_of


def group_guid(members: list[dict[str, Any]], mode: str, threshold: float) -> str:
    sig = (
        "|".join(sorted(f"{c['a_global_id']}:{c['b_global_id']}" for c in members))
        + f"#{mode}#{threshold:.6f}"
    )
    return str(uuid.uuid5(NS, sig))


def build_groups(
    clashes: list[dict[str, Any]], radius: float, mode: str, threshold: float
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for members in group_clashes(clashes, radius):
        mids = [midpoint(c) for c in members]
        centre = [round(sum(axis) / len(mids), 6) for axis in zip(*mids, strict=True)]
        result.append(
            {
                "id": group_guid(members, mode, threshold),
                "centre": centre,
                "count": len(members),
                "clashes": members,
            }
        )
    return result

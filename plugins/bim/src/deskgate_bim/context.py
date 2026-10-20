# SPDX-License-Identifier: MIT
"""Contexte gris des points de vue BCF : éléments voisins d'un groupe de conflits."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import ifcopenshell.geom
import ifcopenshell.ifcopenshell_wrapper as wrapper


def _elements(ifc_file: Any) -> list[Any]:
    return [e for e in ifc_file.by_type("IfcElement") if getattr(e, "Representation", None)]


def _build_tree(ifc_files: Iterable[Any], threads: int) -> Any:
    """Arbre BREP natif (seul backend dont select_box accepte une entité : spike 04-07)."""
    settings = ifcopenshell.geom.settings()
    settings.set("iterator-output", wrapper.NATIVE)
    tree = ifcopenshell.geom.tree(backend="opencascade.brep")
    for f in ifc_files:
        els = _elements(f)
        if els:
            tree.add_iterator(ifcopenshell.geom.iterator(settings, f, threads, include=els))
    return tree


def context_guids(
    ifc_files: list[Any],
    groups: list[dict[str, Any]],
    *,
    radius: float,
    max_context: int,
    exclude_per_group: dict[str, set[str]] | None = None,
    threads: int = 1,
    warn: Callable[[str, str], None] | None = None,
) -> dict[str, list[str]]:
    """GlobalId voisins de chaque groupe (hors conflit), triés et bornés par `max_context`."""
    empty: dict[str, list[str]] = {g["id"]: [] for g in groups}
    if max_context <= 0 or not groups:
        return empty
    try:
        tree = _build_tree(ifc_files, threads)
        out: dict[str, list[str]] = {}
        for g in groups:
            own = {c[k] for c in g["clashes"] for k in ("a_global_id", "b_global_id")}
            excluded = own | (exclude_per_group or {}).get(g["id"], set())
            found: set[str] = set()
            for guid in sorted(own):
                for f in ifc_files:
                    try:
                        el = f.by_guid(guid)
                    except RuntimeError:
                        continue
                    for near in tree.select_box(el, extend=float(radius)):
                        if near.is_a("IfcElement"):
                            found.add(near.GlobalId)
                    break
            out[g["id"]] = sorted(found - excluded)[:max_context]
        return out
    except MemoryError:
        raise
    except Exception as exc:
        if warn is not None:
            warn("context_unavailable", f"Contexte gris indisponible : {exc}")
        return empty

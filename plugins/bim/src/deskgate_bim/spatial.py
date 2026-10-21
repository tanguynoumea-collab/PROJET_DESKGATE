# SPDX-License-Identifier: MIT
"""Lecture IFC pour le nommage des sujets : étages, bâtiment, type effectif, titres."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

import ifcopenshell.ifcopenshell_wrapper as wrapper
import ifcopenshell.util.element
import ifcopenshell.util.placement
import ifcopenshell.util.unit

from .naming import (
    bracket_storey,
    build_title,
    element_label,
    lookup,
    pick_principal,
    trade_code,
)

_UNDEFINED = {None, "NOTDEFINED", "USERDEFINED"}
_GENERIC_TYPES = {
    "IfcDistributionElementType",
    "IfcBuildingElementProxyType",
    "IfcTypeObject",
    "IfcTypeProduct",
    "IfcElementType",
}
_MAX_HOPS = 20


def storey_levels(f: Any) -> list[tuple[float, str]]:
    """Cotes monde (m) des étages, depuis le placement (jamais `Elevation`)."""
    scale = ifcopenshell.util.unit.calculate_unit_scale(f)
    levels: list[tuple[float, str]] = []
    for s in f.by_type("IfcBuildingStorey"):
        z = 0.0
        if s.ObjectPlacement is not None:
            z = float(ifcopenshell.util.placement.get_local_placement(s.ObjectPlacement)[2][3])
        levels.append((round(z * scale, 6), str(s.Name or s.LongName or "?")))
    return sorted(levels)


def building_name(element: Any) -> str | None:
    """Nom de l'IfcBuilding atteint par remontée conteneur puis agrégats."""
    node = ifcopenshell.util.element.get_container(element)
    for _ in range(_MAX_HOPS):
        if node is None:
            return None
        if node.is_a("IfcBuilding"):
            return str(node.Name or node.LongName or "") or None
        node = ifcopenshell.util.element.get_aggregate(node)
    return None


def _predefined(entity: Any) -> str | None:
    value = getattr(entity, "PredefinedType", None) if entity is not None else None
    return None if value in _UNDEFINED else str(value)


def _supertypes(f: Any, ifc_class: str) -> list[str]:
    schema = wrapper.schema_by_name(f.schema_identifier)
    try:
        decl = schema.declaration_by_name(ifc_class).supertype()
    except RuntimeError:
        return []
    out: list[str] = []
    while decl is not None:
        out.append(decl.name())
        decl = decl.supertype()
    return out


def element_info(element: Any) -> dict[str, Any]:
    """Classe, prédéfini effectif (élément puis type), classe du type et surclasses."""
    ifc_class = element.is_a()
    typ = ifcopenshell.util.element.get_type(element)
    predefined = _predefined(element) or _predefined(typ)
    type_class = None
    if typ is not None and typ.is_a() not in _GENERIC_TYPES:
        type_class = typ.is_a().removesuffix("Type")
    supers = [c for c in _supertypes(element.file, ifc_class) if c != ifc_class]
    return {
        "ifc_class": ifc_class,
        "predefined": predefined,
        "type_class": type_class,
        "supertypes": supers,
    }


def topic_titles(
    files: Mapping[str, Any],
    ifc_a: str,
    ifc_b: str | None,
    groups: list[dict[str, Any]],
    charter: Mapping[str, Any],
) -> tuple[dict[str, str], list[str], list[str]]:
    """(titre par id de groupe, entrées absentes de la charte, classes en repli)."""
    fa = files[ifc_a]
    fb = files[ifc_b or ifc_a]
    levels = storey_levels(fa) or storey_levels(fb)
    overrides = charter.get("labels") or {}
    missing: list[str] = []
    fallbacks: list[str] = []
    cache: dict[tuple[str, str], tuple[str, Any]] = {}

    def label(side: str, f: Any, guid: str, ifc_class: str) -> str:
        key = (side, guid)
        if key not in cache:
            try:
                el = f.by_guid(guid)
            except RuntimeError:
                el = None
            if el is None:
                cache[key] = (ifc_class, None)
                fallbacks.append(ifc_class)
            else:
                text, fell_back = element_label(element_info(el), overrides)
                if fell_back:
                    fallbacks.append(text)
                cache[key] = (text, el)
        return cache[key][0]

    trades = charter.get("trades") or {}
    trade_a, note_a = trade_code(trades.get("a"), Path(ifc_a).stem)
    trade_b, note_b = trade_code(trades.get("b"), Path(ifc_b or ifc_a).stem)
    if note_a:
        missing.append(f"technique A : {note_a}")
    if note_b:
        missing.append(f"technique B : {note_b}")

    titles: dict[str, str] = {}
    for g in groups:
        pairs = g["clashes"]
        labels: dict[str, str] = {}
        for c in pairs:
            labels[c["a_global_id"]] = label("a", fa, c["a_global_id"], c["a_ifc_class"])
            labels[c["b_global_id"]] = label("b", fb, c["b_global_id"], c["b_ifc_class"])
        lib_a, lib_b, a_guid = pick_principal(pairs, labels)
        storey = bracket_storey(levels, g["centre"][2])
        if storey is None:
            storey_code = "?"
            missing.append("niveau : aucun étage dans les maquettes")
        else:
            found = lookup(charter.get("levels") or {}, storey)
            storey_code = found or storey
            if not found:
                missing.append(f"niveau : {storey}")
        element = cache.get(("a", a_guid), (None, None))[1]
        name = building_name(element) if element is not None else None
        if name is None:
            building_code = "?"
            missing.append("bâtiment : introuvable")
        else:
            found = lookup(charter.get("buildings") or {}, name)
            building_code = found or name
            if not found:
                missing.append(f"bâtiment : {name}")
        titles[g["id"]] = build_title(building_code, storey_code, trade_a, trade_b, lib_a, lib_b)
    return titles, missing, fallbacks


def project_refs(files: Mapping[str, Any], paths: Sequence[str]) -> list[dict[str, str]]:
    """Références Header/File des maquettes : nom de fichier seul et GlobalId de l'IfcProject."""
    refs: list[dict[str, str]] = []
    for path in dict.fromkeys(paths):
        f = files.get(path)
        if f is None:
            continue
        projects = f.by_type("IfcProject")
        if not projects:
            continue
        guid = getattr(projects[0], "GlobalId", None)
        if not isinstance(guid, str) or len(guid) != 22:
            continue
        refs.append({"filename": PurePosixPath(path.replace("\\", "/")).name, "ifc_project": guid})
    return refs

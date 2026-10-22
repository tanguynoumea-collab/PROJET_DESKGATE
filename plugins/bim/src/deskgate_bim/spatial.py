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
    TABLE_OF,
    bracket_storey,
    pick_principal,
    render_title,
    resolve,
    template_fields,
    type_candidates,
    type_raw,
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
        "type_name": str(typ.Name) if typ is not None and getattr(typ, "Name", None) else None,
        "type_ifc_class": typ.is_a() if typ is not None else None,
        "supertypes": supers,
    }


def topic_titles(
    files: Mapping[str, Any],
    ifc_a: str,
    ifc_b: str | None,
    groups: list[dict[str, Any]],
    template: str,
    mappings: Mapping[str, Mapping[str, str] | None],
) -> tuple[dict[str, str], list[str], list[str]]:
    """(titre par id de groupe, entrées absentes des tables, champs introuvables)."""
    fa = files[ifc_a]
    fb = files[ifc_b or ifc_a]
    levels = storey_levels(fa) or storey_levels(fb)
    used = set(template_fields(template))
    tables = {TABLE_OF[f] for f in used}
    missing: list[str] = []
    incomplete: list[str] = []
    cache: dict[tuple[str, str], tuple[str, Any]] = {}
    type_table = mappings.get("type")

    def note(table: str, raw: str, absent: bool) -> None:
        if absent and table in tables:
            missing.append(f"{table} : {raw}")

    def label(side: str, f: Any, guid: str, ifc_class: str) -> str:
        key = (side, guid)
        if key not in cache:
            try:
                el = f.by_guid(guid)
            except RuntimeError:
                el = None
            if el is None:
                cache[key] = (ifc_class, None)
                note("type", ifc_class, type_table is not None)
            else:
                info = element_info(el)
                raw = type_raw(info)
                shown, absent = resolve(type_table, type_candidates(info), raw)
                note("type", raw, absent)
                cache[key] = (shown, el)
        return cache[key][0]

    def trade(path: str) -> str:
        stem = Path(path).stem
        shown, absent = resolve(mappings.get("trade"), [stem, Path(path).name], stem)
        note("trade", stem, absent)
        return shown

    trade_a = trade(ifc_a)
    trade_b = trade(ifc_b or ifc_a)

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
            storey_shown = "?"
            if "storey" in used:
                incomplete.append("storey")
        else:
            storey_shown, absent = resolve(mappings.get("storey"), [storey], storey)
            note("storey", storey, absent)
        element = cache.get(("a", a_guid), (None, None))[1]
        name = building_name(element) if element is not None else None
        if name is None:
            building_shown = "?"
            if "building" in used:
                incomplete.append("building")
        else:
            building_shown, absent = resolve(mappings.get("building"), [name], name)
            note("building", name, absent)
        titles[g["id"]] = render_title(
            template,
            {
                "building": building_shown,
                "storey": storey_shown,
                "trade_a": trade_a,
                "trade_b": trade_b,
                "type_a": lib_a,
                "type_b": lib_b,
            },
        )
    return titles, missing, incomplete


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

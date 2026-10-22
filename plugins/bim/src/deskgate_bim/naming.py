# SPDX-License-Identifier: MIT
"""Nommage générique des sujets BCF (D-04 à D-07, D-16, D-17) : fonctions pures, stdlib seule."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

TITLE_MAX = 512
MESSAGE_MAX = 2000

FIELDS: tuple[str, ...] = ("building", "storey", "trade_a", "trade_b", "type_a", "type_b")
TABLE_OF: dict[str, str] = {
    "building": "building",
    "storey": "storey",
    "trade_a": "trade",
    "trade_b": "trade",
    "type_a": "type",
    "type_b": "type",
}
TABLES: tuple[str, ...] = ("building", "storey", "trade", "type")
DEFAULT_TEMPLATE = "{type_a} x {type_b}"
_PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
_ADMITTED = "building, storey, trade_a, trade_b, type_a, type_b"


def sanitize(value: str | None) -> str:
    """Rend une valeur utilisable dans un titre : pas de « / », espaces normalisées."""
    if value is None:
        return "?"
    text = re.sub(r"\s+", " ", value.replace("/", "-").replace("\\", "-")).strip()
    return text or "?"


def lookup(mapping: Mapping[str, str], key: str | None) -> str | None:
    """Recherche exacte puis insensible à la casse (première clé dans l'ordre du dict)."""
    if key is None:
        return None
    wanted = key.strip()
    for k, v in mapping.items():
        if k.strip() == wanted:
            return v
    folded = wanted.casefold()
    for k, v in mapping.items():
        if k.strip().casefold() == folded:
            return v
    return None


def template_fields(template: str) -> list[str]:
    """Champs du gabarit dans l'ordre d'apparition ; ValueError si le gabarit est invalide."""
    names = _PLACEHOLDER.findall(template)
    for name in names:
        if name not in FIELDS:
            raise ValueError(
                f"gabarit de titre : champ inconnu « {name} » (champs admis : {_ADMITTED})"
            )
    if "{" in _PLACEHOLDER.sub("", template) or "}" in _PLACEHOLDER.sub("", template):
        raise ValueError("gabarit de titre : accolade non appariée")
    if not names:
        raise ValueError(f"gabarit de titre : aucun champ (champs admis : {_ADMITTED})")
    return list(dict.fromkeys(names))


def render_title(template: str, values: Mapping[str, str]) -> str:
    """Remplace chaque {champ} par sa valeur assainie ; tronque à TITLE_MAX."""
    text = _PLACEHOLDER.sub(lambda m: sanitize(values.get(m.group(1))), template)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:TITLE_MAX] or "?"


def resolve(
    table: Mapping[str, str] | None, candidates: Sequence[str], raw: str
) -> tuple[str, bool]:
    """Valeur affichée d'après la table ; (brute, True) si la table ne la connaît pas."""
    if table is None:
        return raw, False
    for candidate in candidates:
        found = lookup(table, candidate)
        if found:
            return found, False
    return raw, True


def type_candidates(info: Mapping[str, Any]) -> list[str]:
    """Clés de recherche d'un type d'objet, de la plus précise à la plus générale."""
    keys: list[str] = []
    name = info.get("type_name")
    if name:
        keys.append(f"{info.get('type_ifc_class')}:{name}")
        keys.append(str(name))
    predefined = info.get("predefined")
    classes: list[str] = []
    for cls in [info.get("type_class"), info.get("ifc_class"), *(info.get("supertypes") or [])]:
        if cls and cls not in classes:
            classes.append(cls)
    for cls in classes:
        if predefined:
            keys.append(f"{cls}/{predefined}")
        keys.append(cls)
    return list(dict.fromkeys(keys))


def type_raw(info: Mapping[str, Any]) -> str:
    """Valeur brute du type : nom du type d'objet, sinon classe IFC."""
    return str(info.get("type_name") or info["ifc_class"])


def bracket_storey(levels: Sequence[tuple[float, str]], z: float, tol: float = 0.01) -> str | None:
    """Nom de l'étage de cote maximale <= z + tol ; sous le plus bas : le plus bas."""
    if not levels:
        return None
    ordered = sorted(levels, key=lambda lv: (lv[0], lv[1]))
    chosen = ordered[0][1]
    for elevation, name in ordered:
        if elevation <= z + tol:
            chosen = name
        else:
            break
    return chosen


def pick_principal(
    pairs: Sequence[Mapping[str, Any]], labels: Mapping[str, str]
) -> tuple[str, str, str]:
    """Couple de libellés le plus fréquent (égalité : première occurrence) et son GlobalId A."""
    counts: Counter[tuple[str, str]] = Counter()
    first: dict[tuple[str, str], tuple[int, str]] = {}
    for index, pair in enumerate(pairs):
        lib_a = labels.get(pair["a_global_id"]) or pair["a_ifc_class"]
        lib_b = labels.get(pair["b_global_id"]) or pair["b_ifc_class"]
        key = (lib_a, lib_b)
        counts[key] += 1
        first.setdefault(key, (index, pair["a_global_id"]))
    best = min(counts, key=lambda k: (-counts[k], first[k][0]))
    return best[0], best[1], first[best][1]


def missing_message(entries: Iterable[str]) -> str:
    """Avertissement listant les valeurs absentes des tables de correspondance."""
    text = (
        "Valeurs absentes des tables de correspondance (valeur brute dans le titre) : "
        + " ; ".join(sorted(set(entries)))
        + "."
    )
    return text[:MESSAGE_MAX]


def incomplete_message(fields: Iterable[str]) -> str:
    """Avertissement listant les champs du titre introuvables dans les maquettes."""
    text = (
        "Champs du titre introuvables dans les maquettes (« ? » dans le titre) : "
        + ", ".join(sorted(set(fields)))
        + "."
    )
    return text[:MESSAGE_MAX]

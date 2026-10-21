# SPDX-License-Identifier: MIT
"""Nommage des sujets BCF (D-04 à D-09, D-16) : fonctions pures, stdlib seule."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

TITLE_MAX = 512
FILENAME_FALLBACK_MAX = 12
MESSAGE_MAX = 2000

TRADE_CODES: tuple[str, ...] = (
    "ARC",
    "STR",
    "CVC",
    "CHA",
    "VEN",
    "CLI",
    "PLB",
    "SAN",
    "ELE",
    "SPK",
    "FAC",
    "VRD",
)

# Clé « Classe » ou « Classe/TYPEPREDEFINI » -> libellé français.
LABELS: dict[str, str] = {
    "IfcDuctSegment": "Gaine",
    "IfcDuctSegment/FLEXIBLESEGMENT": "Gaine flexible",
    "IfcPipeSegment": "Canalisation",
    "IfcDuctFitting": "Raccord de gaine",
    "IfcDuctFitting/BEND": "Coude de gaine",
    "IfcPipeFitting": "Raccord de tuyauterie",
    "IfcAirTerminal": "Bouche d'air",
    "IfcValve": "Vanne",
    "IfcDamper": "Clapet",
    "IfcDamper/FIREDAMPER": "Clapet coupe-feu",
    "IfcLightFixture": "Luminaire",
    "IfcCableCarrierSegment": "Chemin de câbles",
    "IfcCovering/INSULATION": "Isolant",
    "IfcCovering/CEILING": "Faux-plafond",
    "IfcCovering/FLOORING": "Revêtement de sol",
    "IfcCovering": "Revêtement",
    "IfcWall": "Mur",
    "IfcSlab": "Dalle",
    "IfcBeam": "Poutre",
    "IfcColumn": "Poteau",
    "IfcMember": "Ossature",
    "IfcPlate": "Panneau",
    "IfcPlate/CURTAIN_PANEL": "Panneau de façade",
    "IfcDoor": "Porte",
    "IfcWindow": "Fenêtre",
    "IfcStair": "Escalier",
    "IfcRailing": "Garde-corps",
    "IfcRoof": "Toiture",
    "IfcBuildingElementProxy": "Objet générique",
    "IfcFlowSegment": "Conduit",
    "IfcFlowFitting": "Raccord",
    "IfcFlowTerminal": "Terminal",
    "IfcFlowController": "Régulation",
    "IfcFlowTreatmentDevice": "Traitement",
    "IfcEnergyConversionDevice": "Équipement de production",
    "IfcFlowMovingDevice": "Ventilateur ou pompe",
    "IfcDistributionElement": "Équipement",
    "IfcOpeningElement": "Réservation",
}


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


def element_label(info: Mapping[str, Any], overrides: Mapping[str, str]) -> tuple[str, bool]:
    """Libellé d'un élément : charte, puis table intégrée, sinon classe brute.

    Renvoie (libellé, repli) où repli vaut True si la classe IFC brute est utilisée.
    """
    classes: list[str] = []
    for cls in [info.get("type_class"), info.get("ifc_class"), *(info.get("supertypes") or [])]:
        if cls and cls not in classes:
            classes.append(cls)
    predefined = info.get("predefined")
    keys: list[str] = []
    for cls in classes:
        if predefined:
            keys.append(f"{cls}/{predefined}")
        keys.append(cls)
    for source in (overrides, LABELS):
        for key in keys:
            found = lookup(source, key)
            if found:
                return sanitize(found), False
    return str(info["ifc_class"]), True


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


def trade_code(charter_value: str | None, filename_stem: str) -> tuple[str, str | None]:
    """Technique : charte, sinon code connu du nom de fichier, sinon nom tronqué (+ note)."""
    if charter_value and charter_value.strip():
        return sanitize(charter_value), None
    for token in re.split(r"[^A-Za-z0-9]+", filename_stem):
        code = token.upper()
        if code in TRADE_CODES:
            return code, f"code « {code} » repéré dans le nom de fichier « {filename_stem} »"
    return (
        sanitize(filename_stem)[:FILENAME_FALLBACK_MAX],
        f"nom de fichier tronqué « {filename_stem} »",
    )


def build_title(
    building: str, storey: str, trade_a: str, trade_b: str, label_a: str, label_b: str
) -> str:
    """Titre `<bâtiment>/<étage>/<techniques>/<sujet>`, sans suffixe de comptage."""
    title = "/".join(
        [
            sanitize(building),
            sanitize(storey),
            f"{sanitize(trade_a)}-{sanitize(trade_b)}",
            f"{sanitize(label_a)} x {sanitize(label_b)}",
        ]
    )
    return title[:TITLE_MAX]


def missing_message(entries: Iterable[str]) -> str:
    """Avertissement listant les valeurs absentes de la charte."""
    text = (
        "Valeurs absentes de la charte (valeur brute dans le titre) : "
        + " ; ".join(sorted(set(entries)))
        + "."
    )
    return text[:MESSAGE_MAX]


def fallback_message(classes: Iterable[str]) -> str:
    """Avertissement listant les classes IFC utilisées faute de libellé."""
    text = (
        "Libellé inconnu, classe IFC brute dans le titre : " + ", ".join(sorted(set(classes))) + "."
    )
    return text[:MESSAGE_MAX]

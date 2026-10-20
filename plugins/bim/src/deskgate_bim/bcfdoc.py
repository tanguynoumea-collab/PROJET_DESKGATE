# SPDX-License-Identifier: MIT
"""Document du contrat bcf-write-v1 construit depuis les groupes de conflits (stdlib seule)."""

from __future__ import annotations

import math
from typing import Any

DEFAULT_COLORS: dict[str, str] = {"a": "FFE53935", "b": "FF1E88E5", "context": "40B0B0B0"}
TITLE_MAX = 512
DESCRIPTION_MAX = 4000


def _label(pair: dict[str, Any], side: str) -> str:
    name = str(pair.get(f"{side}_name") or "").strip()
    return name or str(pair.get(f"{side}_ifc_class") or side.upper())


def _midpoint(pair: dict[str, Any]) -> list[float]:
    return [(a + b) / 2 for a, b in zip(pair["p1"], pair["p2"], strict=True)]


def _title(pairs: list[dict[str, Any]]) -> str:
    first = pairs[0]
    title = f"{_label(first, 'a')} x {_label(first, 'b')}"
    if len(pairs) > 1:
        title += f" (+{len(pairs) - 1})"
    return title[:TITLE_MAX]


def _description(pairs: list[dict[str, Any]], mode: str, threshold: float) -> str:
    n = len(pairs)
    text = (
        f"Conflit détecté en mode {mode} (seuil {threshold:g} m) : "
        f"{n} paire{'s' if n > 1 else ''} d'éléments."
    )
    return text[:DESCRIPTION_MAX]


def _radius(group: dict[str, Any]) -> float:
    centre = group["centre"]
    far = max(
        (math.dist(centre, _midpoint(c)) for c in group["clashes"]),
        default=0.0,
    )
    return max(1.0, round(far + 0.5, 6))


def build_doc(
    groups: list[dict[str, Any]],
    *,
    project: str,
    author: str,
    created_at: str,
    context: dict[str, list[str]],
    mode: str,
    threshold: float,
    colors: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Un sujet par groupe ; les GUID de sujet sont ceux des groupes (UUID v5, déterministes)."""
    topics: list[dict[str, Any]] = []
    for g in groups:
        pairs = g["clashes"]
        topics.append(
            {
                "guid": g["id"],
                "title": _title(pairs),
                "description": _description(pairs, mode, threshold),
                "type": "Clash",
                "status": "Open",
                "guids_a": sorted({c["a_global_id"] for c in pairs}),
                "guids_b": sorted({c["b_global_id"] for c in pairs}),
                "context_guids": list(context.get(g["id"], [])),
                "camera": {
                    "type": "perspective",
                    "target": list(g["centre"]),
                    "radius": _radius(g),
                },
            }
        )
    return {
        "schema_version": 1,
        "project": project,
        "author": author,
        "created_at": created_at,
        "colors": dict(colors or DEFAULT_COLORS),
        "topics": topics,
    }

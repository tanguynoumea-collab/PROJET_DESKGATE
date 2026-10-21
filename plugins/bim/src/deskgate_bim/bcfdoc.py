# SPDX-License-Identifier: MIT
"""Document du contrat bcf-write-v2 construit depuis les groupes de conflits (stdlib seule)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
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
    return f"{_label(first, 'a')} x {_label(first, 'b')}"[:TITLE_MAX]


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


def _unit(v: Sequence[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v] if n else list(v)


def _cross(a: Sequence[float], b: Sequence[float]) -> list[float]:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def camera_pose(
    target: Sequence[float], radius: float, direction: Sequence[float] | None = None
) -> dict[str, Any]:
    """Pose de caméra perspective en coordonnées monde (même calcul que le writer v1)."""
    d = _unit(list(direction) if direction else [-1.0, 1.0, -0.8])
    r = max(radius, 1.0)
    pos = [t - c * 3 * r for t, c in zip(target, d, strict=True)]
    right = _cross([0.0, 0.0, 1.0], d)
    n = math.sqrt(sum(x * x for x in right)) or 1.0
    right = [x / n for x in right]
    up = _cross(d, right)
    return {
        "type": "perspective",
        "position": [round(x, 6) for x in pos],
        "direction": [round(x, 6) for x in d],
        "up": [round(x, 6) for x in up],
        "field_of_view": 60.0,
    }


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
    titles: Mapping[str, str] | None = None,
    header_files: Sequence[Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Un sujet par groupe ; les GUID de sujet sont ceux des groupes (UUID v5, déterministes)."""
    topics: list[dict[str, Any]] = []
    for g in groups:
        pairs = g["clashes"]
        topics.append(
            {
                "guid": g["id"],
                "title": ((titles or {}).get(g["id"]) or _title(pairs))[:TITLE_MAX],
                "description": _description(pairs, mode, threshold),
                "type": "Clash",
                "status": "Open",
                "guids_a": sorted({c["a_global_id"] for c in pairs}),
                "guids_b": sorted({c["b_global_id"] for c in pairs}),
                "context_guids": list(context.get(g["id"], [])),
                "camera": camera_pose(g["centre"], _radius(g)),
            }
        )
    topics.sort(key=lambda t: (t["title"], t["guid"]))
    doc: dict[str, Any] = {
        "schema_version": 2,
        "project": project,
        "author": author,
        "created_at": created_at,
        "colors": dict(colors or DEFAULT_COLORS),
        "topics": topics,
    }
    if header_files is not None:
        doc["header_files"] = [
            {"filename": h["filename"], "ifc_project": h["ifc_project"]} for h in header_files
        ]
    return doc

# SPDX-License-Identifier: GPL-3.0-or-later
"""Écriture d'un BCF 2.1 à deux points de vue par sujet (seul module qui importe `bcf`).

Vue 1 « only » : tout masqué, exceptions = objets du conflit, colorés A et B.
Vue 2 « context » : tout visible, contexte coloré, objets du conflit colorés.
Aucune sélection n'est enregistrée (D-08). Les GUID sont déterministes.
"""

from __future__ import annotations

import contextlib
import datetime
import math
import os
import uuid
from pathlib import Path
from typing import Any

import bcf.v2.model as mdl
from bcf.v2.bcfxml import BcfXml
from bcf.v2.visinfo import VisualizationInfoHandler
from xsdata.models.datatype import XmlDateTime


def _comps(guids: list[str]) -> list[mdl.Component]:
    return [mdl.Component(ifc_guid=g) for g in sorted(set(guids))]


def _cross(a: list[float], b: list[float]) -> list[float]:
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _camera(cam: dict[str, Any]) -> dict[str, Any]:
    """Caméra regardant la cible ; recul = 3 x rayon ; direction par défaut (-1, 1, -0.8)."""
    d = cam.get("direction") or [-1.0, 1.0, -0.8]
    n = math.sqrt(sum(c * c for c in d))
    d = [c / n for c in d]
    r = max(float(cam["radius"]), 1.0)
    t = cam["target"]
    pos = [t[i] - d[i] * 3 * r for i in range(3)]
    right = _cross([0, 0, 1], d)
    rn = math.sqrt(sum(c * c for c in right)) or 1.0
    right = [c / rn for c in right]
    up = _cross(d, right)
    p = mdl.Point(x=pos[0], y=pos[1], z=pos[2])
    dd = mdl.Direction(x=d[0], y=d[1], z=d[2])
    uu = mdl.Direction(x=up[0], y=up[1], z=up[2])
    if cam.get("type") == "orthogonal":
        return {
            "orthogonal_camera": mdl.OrthogonalCamera(
                camera_view_point=p,
                camera_direction=dd,
                camera_up_vector=uu,
                view_to_world_scale=2.0 * r,
            )
        }
    return {
        "perspective_camera": mdl.PerspectiveCamera(
            camera_view_point=p, camera_direction=dd, camera_up_vector=uu, field_of_view=60.0
        )
    }


def _only(t: dict[str, Any], c: dict[str, str]) -> mdl.Components:
    return mdl.Components(
        visibility=mdl.ComponentVisibility(
            default_visibility=False,
            exceptions=mdl.ComponentVisibilityExceptions(
                component=_comps(t["guids_a"] + t["guids_b"])
            ),
        ),
        coloring=mdl.ComponentColoring(
            color=[
                mdl.ComponentColoringColor(color=c["a"], component=_comps(t["guids_a"])),
                mdl.ComponentColoringColor(color=c["b"], component=_comps(t["guids_b"])),
            ]
        ),
    )


def _context(t: dict[str, Any], c: dict[str, str]) -> mdl.Components:
    skip = set(t["guids_a"]) | set(t["guids_b"])
    ctx = sorted({g for g in t.get("context_guids", []) if g not in skip})
    col = []
    if ctx:
        col.append(mdl.ComponentColoringColor(color=c["context"], component=_comps(ctx)))
    col.append(mdl.ComponentColoringColor(color=c["a"], component=_comps(t["guids_a"])))
    col.append(mdl.ComponentColoringColor(color=c["b"], component=_comps(t["guids_b"])))
    return mdl.Components(
        visibility=mdl.ComponentVisibility(default_visibility=True),
        coloring=mdl.ComponentColoring(color=col),
    )


def _build(doc: dict[str, Any], target: Path) -> None:
    created = XmlDateTime.from_datetime(datetime.datetime.fromisoformat(doc["created_at"]))
    bcf = BcfXml.create_new(doc["project"])
    bcf.project_info.project.project_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, "deskgate:" + doc["project"])
    )
    for t in doc["topics"]:
        th = bcf.add_topic(
            t["title"],
            t.get("description", ""),
            doc["author"],
            t.get("type", ""),
            t.get("status", ""),
        )
        del bcf.topics[th.guid]  # GUID déterministe : guid ET dossier du zip
        th.topic.guid = t["guid"]
        th.topic.creation_date = created
        th._topic_dir = Path(t["guid"])
        bcf.topics[t["guid"]] = th
        for i, (make, label) in enumerate(((_only, "only"), (_context, "context")), 1):
            g = str(uuid.uuid5(uuid.UUID(t["guid"]), f"viewpoint-{i}-{label}"))
            th.add_visinfo_handler(
                VisualizationInfoHandler(
                    mdl.VisualizationInfo(
                        guid=g, components=make(t, doc["colors"]), **_camera(t["camera"])
                    )
                )
            )
    bcf.save(target)


def write(doc: dict[str, Any], out: Path) -> None:
    """Écrit le BCF dans un fichier temporaire voisin puis le renomme."""
    tmp = out.with_name(out.stem + ".tmp.bcf")
    try:
        _build(doc, tmp)
        os.replace(tmp, out)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise

# SPDX-License-Identifier: GPL-3.0-or-later
"""Relit un .bcf avec BcfXml.load et imprime un résumé JSON sur stdout (env bcf)."""

import json
import sys
from pathlib import Path

from bcf.v2.bcfxml import BcfXml


def _guids(components) -> list[str]:
    return sorted(c.ifc_guid for c in components or [])


def _viewpoint(vh) -> dict:
    vi = vh.visualization_info
    comps = vi.components
    vis = comps.visibility if comps else None
    colors: dict[str, list[str]] = {}
    if comps and comps.coloring:
        for col in comps.coloring.color:
            colors.setdefault(col.color.upper(), []).extend(_guids(col.component))
    camera = None
    if vi.perspective_camera is not None:
        camera = "perspective"
    elif vi.orthogonal_camera is not None:
        camera = "orthogonal"
    exc = vis.exceptions.component if vis and vis.exceptions else []
    sel = comps.selection if comps else None
    return {
        "guid": vi.guid,
        "camera": camera,
        "default_visibility": vis.default_visibility if vis else None,
        "exceptions": _guids(exc),
        "colors": {k: sorted(v) for k, v in sorted(colors.items())},
        "has_selection": bool(sel and sel.component),
    }


def main() -> None:
    bcf = BcfXml.load(Path(sys.argv[1]))
    topics = []
    for guid, th in sorted(bcf.topics.items()):
        vps = sorted((_viewpoint(v) for v in th.viewpoints.values()), key=lambda d: d["guid"])
        topics.append({"guid": guid, "title": th.topic.title, "viewpoints": vps})
    out = {
        "version": bcf.version.version_id,
        "project": bcf.project_info.project.name,
        "topics": topics,
    }
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


main()

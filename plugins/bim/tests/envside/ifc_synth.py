# SPDX-License-Identifier: MIT
# pyright: basic, reportMissingImports=false
"""Scènes IFC synthétiques à résultats connus (D-09). Exécuté dans l'env bim : `python -I`.

Usage : `python -I ifc_synth.py <dossier_sortie>` ; imprime {"fichier": {"nom": "GlobalId"}}.
L'API attend des mètres et convertit vers l'unité du projet : ne jamais pré-multiplier.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import ifcopenshell
import ifcopenshell.api


def new_model(unit: str = "METRE"):
    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    proj = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="P")
    if unit == "MILLIMETRE":
        u = ifcopenshell.api.run("unit.add_si_unit", f, unit_type="LENGTHUNIT", prefix="MILLI")
        ifcopenshell.api.run("unit.assign_unit", f, units=[u])
    else:
        ifcopenshell.api.run("unit.assign_unit", f)
    ctx = ifcopenshell.api.run("context.add_context", f, context_type="Model")
    body = ifcopenshell.api.run(
        "context.add_context",
        f,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=ctx,
    )
    site = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcSite", name="S")
    bld = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuilding", name="B")
    st = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="L0")
    for child, parent in ((site, proj), (bld, site), (st, bld)):
        ifcopenshell.api.run("aggregate.assign_object", f, products=[child], relating_object=parent)
    f._bld = bld  # pyright: ignore[reportAttributeAccessIssue]
    return f, body, st


def storey(f, name: str):
    st = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name=name)
    ifcopenshell.api.run("aggregate.assign_object", f, products=[st], relating_object=f._bld)
    return st


def box(f, body, st, cls, name, origin, size, geometry=True):
    el = ifcopenshell.api.run("root.create_entity", f, ifc_class=cls, name=name)
    if geometry:
        x, y, z = origin
        dx, dy, dz = size
        v = [
            (x, y, z),
            (x + dx, y, z),
            (x + dx, y + dy, z),
            (x, y + dy, z),
            (x, y, z + dz),
            (x + dx, y, z + dz),
            (x + dx, y + dy, z + dz),
            (x, y + dy, z + dz),
        ]
        faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        rep = ifcopenshell.api.run(
            "geometry.add_mesh_representation", f, context=body, vertices=[v], faces=[faces]
        )
        ifcopenshell.api.run("geometry.assign_representation", f, product=el, representation=rep)
    ifcopenshell.api.run("spatial.assign_container", f, products=[el], relating_structure=st)
    return el


def mur_gaine(unit="METRE", gaine_y=-1.0, gaine_len=2.0, gaine_origin=(1, -1, 1), extra=True):
    f, body, st = new_model(unit)
    els = [
        box(f, body, st, "IfcWall", "Mur1", (0, 0, 0), (4, 0.2, 3)),
        box(f, body, st, "IfcDuctSegment", "Gaine1", gaine_origin, (0.3, gaine_len, 0.3)),
    ]
    if extra:
        els.append(box(f, body, st, "IfcColumn", "Poteau_loin", (30, 30, 30), (0.3, 0.3, 3)))
        els.append(
            box(f, body, st, "IfcWall", "Mur_sans_geom", (0, 0, 0), (1, 1, 1), geometry=False)
        )
    return f, els


def main(out: Path) -> dict[str, dict[str, str]]:
    out.mkdir(parents=True, exist_ok=True)
    guids: dict[str, dict[str, str]] = {}

    def save(name: str, f, els) -> None:
        f.write(str(out / name))
        guids[name] = {e.Name: e.GlobalId for e in els}

    f, els = mur_gaine()
    save("mur_gaine.ifc", f, els)
    save("Maquette_é.ifc", *mur_gaine())
    save("mur_gaine_mm.ifc", *mur_gaine("MILLIMETRE"))
    save("gaine_1mm.ifc", *mur_gaine(gaine_origin=(1, 0.199, 1)))

    f, body, st = new_model()
    els = [
        box(f, body, st, "IfcBeam", "Poutre1", (10, 0, 0.15), (2, 0.1, 0.1)),
        box(f, body, st, "IfcPipeSegment", "Tuyau1", (10, 0, 0), (2, 0.1, 0.1)),
    ]
    save("poutre_tuyau.ifc", f, els)

    f, body, st = new_model()
    els = [box(f, body, st, "IfcWall", "Mur1", (0, 0, 0), (10, 0.2, 3))]
    for i in range(5):
        els.append(
            box(f, body, st, "IfcDuctSegment", f"Gaine{i}", (i * 2 + 0.5, -1, 1), (0.3, 2, 0.3))
        )
    save("cinq_gaines.ifc", f, els)

    f, body, st = new_model()
    save("murs.ifc", f, [box(f, body, st, "IfcWall", "Mur1", (0, 0, 0), (4, 0.2, 3))])
    f, body, st = new_model()
    save(
        "gaines.ifc",
        f,
        [box(f, body, st, "IfcDuctSegment", "Gaine1", (1, -1, 1), (0.3, 2, 0.3))],
    )

    f, body, st = new_model()
    l1 = storey(f, "L1")
    els = [
        box(f, body, st, "IfcWall", "Mur1", (0, 0, 0), (4, 0.2, 3)),
        box(f, body, st, "IfcDuctSegment", "Gaine1", (1, -1, 1), (0.3, 2, 0.3)),
        box(f, body, st, "IfcSlab", "Dalle_proche", (0, -1, -0.2), (4, 2, 0.2)),
        box(f, body, l1, "IfcColumn", "Poteau_loin", (50, 50, 3), (0.3, 0.3, 3)),
    ]
    save("contexte.ifc", f, els)

    (out / "pas_un_ifc.ifc").write_text("pas un ifc", encoding="utf-8")
    return guids


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # pyright: ignore[reportAttributeAccessIssue]
    print(json.dumps(main(Path(sys.argv[1])), ensure_ascii=False))

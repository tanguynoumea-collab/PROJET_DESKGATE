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
import numpy


def _owner_2x3(f) -> None:
    """IFC2X3 impose un OwnerHistory : utilisateur et application fictifs."""
    import ifcopenshell.api.owner.settings as settings

    person = ifcopenshell.api.run("owner.add_person", f, identification="t", family_name="T")
    org = ifcopenshell.api.run("owner.add_organisation", f, identification="o", name="O")
    user = ifcopenshell.api.run(
        "owner.add_person_and_organisation", f, person=person, organisation=org
    )
    app = ifcopenshell.api.run(
        "owner.add_application",
        f,
        application_developer=org,
        version="1",
        application_full_name="synth",
        application_identifier="synth",
    )
    settings.get_user = lambda _file: user
    settings.get_application = lambda _file: app


def new_model(
    unit: str = "METRE", version: str = "IFC4", building: str = "B", storey_name: str = "L0"
):
    f = ifcopenshell.api.run("project.create_file", version=version)
    if version == "IFC2X3":
        _owner_2x3(f)
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
    bld = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuilding", name=building)
    st = ifcopenshell.api.run(
        "root.create_entity", f, ifc_class="IfcBuildingStorey", name=storey_name
    )
    for child, parent in ((site, proj), (bld, site), (st, bld)):
        ifcopenshell.api.run("aggregate.assign_object", f, products=[child], relating_object=parent)
    f._bld = bld  # pyright: ignore[reportAttributeAccessIssue]
    return f, body, st


def storey(f, name: str, building=None):
    st = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name=name)
    parent = building if building is not None else f._bld
    ifcopenshell.api.run("aggregate.assign_object", f, products=[st], relating_object=parent)
    return st


def add_building(f, name: str, storey_name: str = "L0"):
    """Second bâtiment sous le site de la maquette ; renvoie (bâtiment, étage)."""
    site = f.by_type("IfcSite")[0]
    bld = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuilding", name=name)
    ifcopenshell.api.run("aggregate.assign_object", f, products=[bld], relating_object=site)
    return bld, storey(f, storey_name, bld)


def place_storey(f, st, z: float) -> None:
    """Pose l'étage à la cote z (mètres) : placement et propriété Elevation."""
    m = numpy.eye(4)
    m[2, 3] = z
    ifcopenshell.api.run("geometry.edit_object_placement", f, product=st, matrix=m)
    st.Elevation = z


def box_brep(f, body, v, faces):
    """Représentation IfcFacetedBrep (IFC2X3, quand le maillage n'est pas accepté)."""
    pts = [f.createIfcCartesianPoint(tuple(float(c) for c in p)) for p in v]
    fcs = []
    for face in faces:
        loop = f.createIfcPolyLoop([pts[i] for i in face])
        fcs.append(f.createIfcFace([f.createIfcFaceOuterBound(loop, True)]))
    brep = f.createIfcFacetedBrep(f.createIfcClosedShell(fcs))
    return f.createIfcShapeRepresentation(body, "Body", "Brep", [brep])


def box(f, body, st, cls, name, origin, size, geometry=True, contain=True):
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
        if f.schema == "IFC2X3":
            rep = box_brep(f, body, v, faces)
        else:
            rep = ifcopenshell.api.run(
                "geometry.add_mesh_representation", f, context=body, vertices=[v], faces=[faces]
            )
        ifcopenshell.api.run("geometry.assign_representation", f, product=el, representation=rep)
    if contain:
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


def etages(f):
    """Deux étages J_10_P00 (z = 0) et J_11_P01 (z = 3) ; renvoie (p00, p01)."""
    p00 = f.by_type("IfcBuildingStorey")[0]
    p00.Name = "J_10_P00"
    p01 = storey(f, "J_11_P01")
    place_storey(f, p00, 0.0)
    place_storey(f, p01, 3.0)
    return p00, p01


def scenes_51(out: Path, save) -> None:
    """Scènes de la phase 5.1 (nommage, réservations, volume)."""
    # 1. CVC par étages
    f, body, st = new_model(building="Jura", storey_name="J_10_P00")
    p00, p01 = etages(f)
    els = [
        box(f, body, p00, "IfcDuctSegment", "Gaine_P00", (1, -1, 1), (0.3, 2, 0.3)),
        box(f, body, p01, "IfcDuctSegment", "Gaine_P01", (1, -1, 4), (0.3, 2, 0.3)),
    ]
    save("PIC-CVC-etages.ifc", f, els)

    # 2. ARC par étages (Mur_P01 rattaché à P00 : l'étage vient de la cote du point)
    f, body, st = new_model(building="Jura", storey_name="J_10_P00")
    p00, p01 = etages(f)
    els = [
        box(f, body, p00, "IfcWall", "Mur_P00", (0, 0, 0), (4, 0.2, 3)),
        box(f, body, p00, "IfcWall", "Mur_P01", (0, 0, 3), (4, 0.2, 3)),
    ]
    save("PIC-ARC-etages.ifc", f, els)

    # 3. Deux bâtiments dans un seul fichier
    f, body, st = new_model(building="Jura", storey_name="L0")
    _tour, st_t = add_building(f, "Tour")
    els = [
        box(f, body, st, "IfcWall", "Mur_J", (0, 0, 0), (4, 0.2, 3)),
        box(f, body, st, "IfcDuctSegment", "Gaine_J", (1, -1, 1), (0.3, 2, 0.3)),
        box(f, body, st_t, "IfcWall", "Mur_T", (100, 0, 0), (4, 0.2, 3)),
        box(f, body, st_t, "IfcDuctSegment", "Gaine_T", (101, -1, 1), (0.3, 2, 0.3)),
    ]
    save("deux_batiments.ifc", f, els)

    # 4. IFC2X3 : objet typé et faux-plafond
    f, body, st = new_model(version="IFC2X3")
    gaine = box(f, body, st, "IfcFlowSegment", "Gaine_2x3", (1, -1, 1), (0.3, 2, 0.3))
    typ = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDuctSegmentType", name="T")
    typ.PredefinedType = "RIGIDSEGMENT"
    ifcopenshell.api.run("type.assign_type", f, related_objects=[gaine], relating_type=typ)
    plafond = box(f, body, st, "IfcCovering", "Plafond_2x3", (0, -2, 1.1), (4, 4, 0.05))
    plafond.PredefinedType = "CEILING"
    save("ifc2x3_types.ifc", f, [gaine, plafond])

    # 5. Réservation dans un mur traversé par une gaine
    f, body, st = new_model()
    els = [
        box(f, body, st, "IfcWall", "Mur1", (0, 0, 0), (4, 0.2, 3)),
        box(
            f,
            body,
            st,
            "IfcOpeningElement",
            "Reservation1",
            (1.5, -0.05, 1),
            (1, 0.3, 1),
            contain=False,
        ),
        box(f, body, st, "IfcDuctSegment", "Gaine1", (1.8, -1, 1.3), (0.3, 2, 0.3)),
    ]
    save("reservation.ifc", f, els)

    # 6. Plus de 1000 conflits : dalle x 1024 gaines
    f, body, st = new_model()
    els = [box(f, body, st, "IfcSlab", "Dalle", (0, 0, 0), (33, 33, 0.2))]
    for i in range(32):
        for j in range(32):
            els.append(
                box(
                    f,
                    body,
                    st,
                    "IfcDuctSegment",
                    f"G_{i}_{j}",
                    (i + 0.5, j + 0.5, -0.4),
                    (0.1, 0.1, 1.0),
                )
            )
    save("mille_conflits.ifc", f, els)


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

    scenes_51(out, save)

    (out / "pas_un_ifc.ifc").write_text("pas un ifc", encoding="utf-8")
    return guids


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # pyright: ignore[reportAttributeAccessIssue]
    print(json.dumps(main(Path(sys.argv[1])), ensure_ascii=False))

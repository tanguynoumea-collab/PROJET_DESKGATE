# SPDX-License-Identifier: MIT
"""Header/File du BCF (verdict BIMcollab Zoom V4) : Engine réel, caméras en coordonnées monde."""

from __future__ import annotations

import json
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

import pytest

from _support.clash_env import ClashEnv

pytestmark = [pytest.mark.bim, pytest.mark.proc]

BASE: dict[str, Any] = {
    "mode": "hard",
    "tolerance": 0.002,
    "bcf": True,
    "created_at": "2026-10-21T10:00:00Z",
}
DEUX: dict[str, Any] = {
    **BASE,
    "ifc_a": "/data/depot/PIC-CVC-etages.ifc",
    "selector_a": "IfcDuctSegment",
    "ifc_b": "/data/depot/PIC-ARC-etages.ifc",
    "selector_b": "IfcWall",
}


@pytest.fixture
def settings(plugin_envs: dict[str, Any]) -> dict[str, Any]:
    return {"bcf_executable": str(plugin_envs["bcf_exe"])}


def _project_guid(python: Path, ifc: Path) -> str:
    code = (
        "import sys, ifcopenshell; "
        "print(ifcopenshell.open(sys.argv[1]).by_type('IfcProject')[0].GlobalId)"
    )
    r = subprocess.run(
        [str(python), "-B", "-I", "-c", code, str(ifc)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip()


def _markups(env: ClashEnv) -> list[tuple[str, ET.Element]]:
    with zipfile.ZipFile(env.work_dir / "conflits.bcf") as z:
        return [
            (n.split("/")[0], ET.fromstring(z.read(n)))  # noqa: S314
            for n in sorted(z.namelist())
            if n.endswith("/markup.bcf")
        ]


def _files(markup: ET.Element) -> list[tuple[str, str | None]]:
    header = markup.find("Header")
    assert header is not None
    return [
        (f.findtext("Filename", ""), f.attrib.get("IfcProject")) for f in header.findall("File")
    ]


def test_header_deux_maquettes(
    clash_env: ClashEnv, settings: dict[str, Any], plugin_envs: dict[str, Any]
) -> None:
    clash_env.place("PIC-CVC-etages.ifc", "PIC-ARC-etages.ifc")
    row, _ = clash_env.run(DEUX, settings=settings)
    assert row.status == "succeeded", row.error_message
    attendu = [
        (nom, _project_guid(plugin_envs["bim"], clash_env.depot / nom))
        for nom in ("PIC-CVC-etages.ifc", "PIC-ARC-etages.ifc")
    ]
    markups = _markups(clash_env)
    assert markups
    for _, markup in markups:
        assert _files(markup) == attendu


def test_header_une_maquette(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("mur_gaine.ifc")
    row, _ = clash_env.run(
        {
            **BASE,
            "ifc_a": "/data/depot/mur_gaine.ifc",
            "selector_a": "IfcWall",
            "selector_b": "IfcDuctSegment",
        },
        settings=settings,
    )
    assert row.status == "succeeded", row.error_message
    markups = _markups(clash_env)
    assert markups
    for _, markup in markups:
        (fichier,) = _files(markup)
        assert fichier[0] == "mur_gaine.ifc" and fichier[1] and len(fichier[1]) == 22


def test_camera_monde(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("mur_gaine.ifc")
    row, _ = clash_env.run(
        {
            **BASE,
            "ifc_a": "/data/depot/mur_gaine.ifc",
            "selector_a": "IfcWall",
            "selector_b": "IfcDuctSegment",
        },
        settings=settings,
    )
    assert row.status == "succeeded", row.error_message
    doc = json.loads((clash_env.work_dir / "bcf-input.json").read_text(encoding="utf-8"))
    (topic,) = doc["topics"]
    with zipfile.ZipFile(clash_env.work_dir / "conflits.bcf") as z:
        racine = ET.fromstring(z.read(f"{topic['guid']}/viewpoint.bcfv"))  # noqa: S314
    point = racine.find("PerspectiveCamera/CameraViewPoint")
    assert point is not None
    xyz = [float(point.findtext(c, "nan")) for c in ("X", "Y", "Z")]
    assert xyz == pytest.approx(topic["camera"]["position"], abs=1e-9)

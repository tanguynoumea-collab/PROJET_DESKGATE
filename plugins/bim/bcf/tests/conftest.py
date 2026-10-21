"""Fixtures des tests deskgate-bcf : document valide et lanceur du CLI."""

from __future__ import annotations

import copy
import json
import struct
import subprocess
import uuid
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

GID = "0123456789ABCDEFabcdef"


def _gid(n: int) -> str:
    """GlobalId de 22 caractères, distinct par n."""
    return (f"{n:02d}" + GID)[:22]


def png_bytes(w: int = 4, h: int = 3, rgb: tuple[int, int, int] = (229, 57, 53)) -> bytes:
    """PNG valide (type couleur 2) construit en stdlib."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


@pytest.fixture
def png() -> Callable[..., bytes]:
    return png_bytes


@pytest.fixture
def doc_valide() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "project": "Essai",
        "author": "deskgate",
        "created_at": "2026-10-21T10:00:00Z",
        "colors": {"a": "FFE53935", "b": "FF1E88E5", "context": "40B0B0B0"},
        "topics": [
            {
                "guid": str(uuid.uuid5(uuid.NAMESPACE_URL, "sujet-1")),
                "title": "Gaine x Mur",
                "description": "hard, 2 paires",
                "type": "Clash",
                "status": "Open",
                "guids_a": [_gid(1), _gid(2)],
                "guids_b": [_gid(3)],
                "context_guids": [_gid(4), _gid(5), _gid(6), _gid(1)],
                "camera": {"type": "perspective", "target": [1.0, 2.0, 3.0], "radius": 1.5},
            },
            {
                "guid": str(uuid.uuid5(uuid.NAMESPACE_URL, "sujet-2")),
                "title": "Poutre x Conduit",
                "guids_a": [_gid(7)],
                "guids_b": [_gid(8)],
                "camera": {"type": "orthogonal", "target": [0.0, 0.0, 0.0], "radius": 2.0},
            },
        ],
    }


@pytest.fixture
def doc_v2(doc_valide: dict[str, Any], tmp_path: Path) -> dict[str, Any]:
    doc = copy.deepcopy(doc_valide)
    doc["schema_version"] = 2
    doc["header_files"] = [
        {"filename": "CVC.ifc", "ifc_project": "1AAAAAAAAAAAAAAAAAAAAA"},
        {"filename": "ARC.ifc", "ifc_project": "1BBBBBBBBBBBBBBBBBBBBB"},
    ]
    doc["topics"][0]["camera"] = {
        "type": "perspective",
        "position": [10.0, 20.0, 30.0],
        "direction": [0.0, 1.0, 0.0],
        "up": [0.0, 0.0, 1.0],
        "field_of_view": 60.0,
    }
    doc["topics"][1]["camera"] = {
        "type": "orthogonal",
        "position": [0.0, 0.0, 10.0],
        "direction": [0.0, 0.0, -1.0],
        "up": [0.0, 1.0, 0.0],
        "view_to_world_scale": 4.0,
    }
    (tmp_path / "snapshots").mkdir()
    (tmp_path / "snapshots" / "s1-1.png").write_bytes(png_bytes(rgb=(229, 57, 53)))
    (tmp_path / "snapshots" / "s1-2.png").write_bytes(png_bytes(rgb=(30, 136, 229)))
    doc["topics"][0]["snapshots"] = {
        "only": "snapshots/s1-1.png",
        "context": "snapshots/s1-2.png",
    }
    return doc


@pytest.fixture
def ecrire(
    plugin_envs: dict[str, Path], tmp_path: Path
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def _ecrire(
        doc: Any,
        nom: str = "out.bcf",
        sortie: Path | None = None,
        brut: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        src = tmp_path / "in.json"
        src.write_text(
            brut if brut is not None else json.dumps(copy.deepcopy(doc)), encoding="utf-8"
        )
        out = sortie if sortie is not None else tmp_path / nom
        return subprocess.run(
            [str(plugin_envs["bcf_exe"]), "write", "--input", str(src), "--output", str(out)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            check=False,
        )

    return _ecrire

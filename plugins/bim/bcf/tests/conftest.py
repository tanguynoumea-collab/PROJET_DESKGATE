"""Fixtures des tests deskgate-bcf : document valide et lanceur du CLI."""

from __future__ import annotations

import copy
import json
import subprocess
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

GID = "0123456789ABCDEFabcdef"


def _gid(n: int) -> str:
    """GlobalId de 22 caractères, distinct par n."""
    return (f"{n:02d}" + GID)[:22]


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

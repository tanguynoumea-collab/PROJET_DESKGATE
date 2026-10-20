"""Le contrat bcf-write-v1 et ses deux copies sont identiques octet par octet."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from _support.plugin_envs import REPO

pytestmark = pytest.mark.unit

SOURCE = REPO / "docs" / "contrats" / "bcf-write-v1.json"
COPIES = [
    REPO / "plugins" / "bim" / "src" / "deskgate_bim" / "contracts" / "bcf-write-v1.json",
    REPO / "plugins" / "bim" / "bcf" / "src" / "deskgate_bcf" / "schemas" / "bcf-write-v1.json",
]


@pytest.mark.parametrize("copie", COPIES, ids=lambda p: p.parent.parent.name)
def test_copie_identique(copie: Path) -> None:
    assert copie.read_bytes() == SOURCE.read_bytes()


def test_schema_version_1() -> None:
    schema = json.loads(SOURCE.read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == 1

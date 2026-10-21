"""Les contrats bcf-write-v1 et v2 et leurs copies sont identiques octet par octet."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from _support.plugin_envs import REPO

pytestmark = pytest.mark.unit

VERSIONS = ("v1", "v2")


def _source(version: str) -> Path:
    return REPO / "docs" / "contrats" / f"bcf-write-{version}.json"


def _copies(version: str) -> list[Path]:
    nom = f"bcf-write-{version}.json"
    return [
        REPO / "plugins" / "bim" / "src" / "deskgate_bim" / "contracts" / nom,
        REPO / "plugins" / "bim" / "bcf" / "src" / "deskgate_bcf" / "schemas" / nom,
    ]


COUPLES = [(v, c) for v in VERSIONS for c in _copies(v)]


@pytest.mark.parametrize(
    ("version", "copie"), COUPLES, ids=lambda x: x if isinstance(x, str) else x.parent.parent.name
)
def test_copie_identique(version: str, copie: Path) -> None:
    assert copie.read_bytes() == _source(version).read_bytes()


def test_schema_version_1() -> None:
    schema = json.loads(_source("v1").read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == 1


def test_schema_version_2() -> None:
    schema = json.loads(_source("v2").read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == 2
    assert schema["properties"]["topics"]["maxItems"] == 100000
    assert "snapshots" in schema["$defs"]["topic"]["properties"]
    assert "header_files" in schema["properties"]
    assert "origin_offset" not in json.dumps(schema)

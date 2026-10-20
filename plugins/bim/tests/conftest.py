# SPDX-License-Identifier: MIT
"""Fixtures des tests de deskgate-bim : scènes IFC synthétiques et Engine réel."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from _support.clash_env import ClashEnv
from _support.plugin_envs import run_json

SYNTH = Path(__file__).resolve().parent / "envside" / "ifc_synth.py"


@pytest.fixture(scope="session")
def scenes(
    plugin_envs: dict[str, Path], tmp_path_factory: pytest.TempPathFactory
) -> tuple[Path, dict[str, dict[str, str]]]:
    """Scènes générées une seule fois par session (Pitfall 13) : (dossier, GlobalId par nom)."""
    dossier = tmp_path_factory.mktemp("scenes")
    guids = run_json(plugin_envs["bim"], SYNTH, str(dossier))
    assert isinstance(guids, dict)
    return dossier, guids


@pytest.fixture
def clash_env(
    tmp_path: Path,
    plugin_envs: dict[str, Path],
    scenes: tuple[Path, dict[str, dict[str, str]]],
) -> Iterator[ClashEnv]:
    yield ClashEnv(tmp_path, plugin_envs, scenes)

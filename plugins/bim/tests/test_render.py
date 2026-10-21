# SPDX-License-Identifier: MIT
"""Rendu logiciel des points de vue : couleurs, découpage au plan proche, déterminisme."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from _support.plugin_envs import run_json

pytestmark = [pytest.mark.bim]

PROBE = Path(__file__).resolve().parent / "envside" / "render_probe.py"


@pytest.fixture(scope="module")
def probe(plugin_envs: dict[str, Any]) -> dict[str, Any]:
    out = run_json(plugin_envs["bim"], PROBE)
    assert isinstance(out, dict)
    return out


def test_png_et_taille(probe: dict[str, Any]) -> None:
    assert probe["sig"] == "89504e470d0a1a0a"
    assert probe["size"] == [800, 450]


def test_vue_objets_rouge_et_bleu(probe: dict[str, Any]) -> None:
    assert probe["red"] > 0 and probe["blue"] > 0


def test_vue_contexte_gris_transparent(probe: dict[str, Any]) -> None:
    assert probe["grey"] > 0
    assert probe["red2"] > 0 and probe["blue2"] > 0


def test_plancher_decoupe_au_plan_proche(probe: dict[str, Any]) -> None:
    assert probe["floor_ratio"] > 0.10


def test_deterministe(probe: dict[str, Any]) -> None:
    assert probe["sha_1"] == probe["sha_1_bis"]


def test_taille_invalide(probe: dict[str, Any]) -> None:
    assert probe["bad_size_error"] is True

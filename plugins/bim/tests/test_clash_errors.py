# SPDX-License-Identifier: MIT
"""Erreurs classées de ifc.clash : le code devient `plugin_error`, le message débute par le code."""

from __future__ import annotations

from typing import Any

import pytest

from _support.clash_env import ClashEnv

pytestmark = [pytest.mark.bim, pytest.mark.proc]

OK: dict[str, Any] = {
    "ifc_a": "/data/depot/mur_gaine.ifc",
    "selector_a": "IfcWall",
    "selector_b": "IfcDuctSegment",
    "mode": "hard",
    "tolerance": 0.002,
}


def failed(env: ClashEnv, params: dict[str, Any]) -> str:
    env.place("mur_gaine.ifc", "pas_un_ifc.ifc")
    row, _ = env.run(params)
    assert row.status == "failed", row.result_json
    assert row.error_code == "plugin_error"
    assert row.error_message is not None
    return row.error_message


def test_selecteur_invalide(clash_env: ClashEnv) -> None:
    msg = failed(clash_env, {**OK, "selector_a": "IfcWall, Name=/[/"})
    assert msg.startswith("invalid_selector : ")


def test_fichier_illisible(clash_env: ClashEnv) -> None:
    msg = failed(clash_env, {**OK, "ifc_a": "/data/depot/pas_un_ifc.ifc"})
    assert msg.startswith("ifc_unreadable : ")


def test_fichier_absent(clash_env: ClashEnv) -> None:
    msg = failed(clash_env, {**OK, "ifc_a": "/data/depot/absent.ifc"})
    assert msg.startswith("ifc_not_found : ")


def test_mode_inconnu(clash_env: ClashEnv) -> None:
    assert failed(clash_env, {**OK, "mode": "touch"}).startswith("invalid_params : ")


def test_hard_sans_tolerance(clash_env: ClashEnv) -> None:
    params = {k: v for k, v in OK.items() if k != "tolerance"}
    msg = failed(clash_env, params)
    assert msg.startswith("invalid_params : ") and "tolerance" in msg


def test_parametre_inconnu(clash_env: ClashEnv) -> None:
    msg = failed(clash_env, {**OK, "foo": 1})
    assert msg.startswith("invalid_params : ") and "foo" in msg


def test_chemin_hors_racine(clash_env: ClashEnv) -> None:
    clash_env.place("mur_gaine.ifc")
    row, _ = clash_env.run({**OK, "ifc_a": "/data/../hors.ifc"})
    assert row.status == "failed"
    assert row.error_code in {"path_outside_roots", "path_invalid"}
    assert not (clash_env.work_dir / "job.log").exists()

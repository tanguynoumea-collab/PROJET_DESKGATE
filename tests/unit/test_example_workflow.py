"""Contrôle statique du workflow d'exemple n8n (D-06)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

FICHIER = Path(__file__).resolve().parents[2] / "n8n" / "examples" / "ifc-clash.json"
PARAMS = FICHIER.with_name("ifc-clash-params.json")


@pytest.fixture(scope="module")
def texte() -> str:
    return FICHIER.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def wf(texte: str) -> dict[str, Any]:
    return json.loads(texte)


def _noeud(wf: dict[str, Any], nom: str) -> dict[str, Any]:
    return next(n for n in wf["nodes"] if n["name"] == nom)


def _par_type(wf: dict[str, Any], suffixe: str) -> dict[str, Any]:
    return next(n for n in wf["nodes"] if n["type"].endswith("." + suffixe))


def test_structure(wf: dict[str, Any]) -> None:
    assert wf["id"] == "DeskgateClash0001"
    assert len(wf["nodes"]) == 8
    ids = [n["id"] for n in wf["nodes"]]
    assert len(set(ids)) == 8
    noms = {n["name"] for n in wf["nodes"]}
    for source, sorties in wf["connections"].items():
        assert source in noms
        for branche in sorties["main"]:
            for lien in branche:
                assert lien["node"] in noms


def test_types_presents(wf: dict[str, Any]) -> None:
    types = {n["type"].split(".")[-1] for n in wf["nodes"]}
    assert {"manualTrigger", "webhook", "set", "httpRequest", "wait", "if"} <= types
    webhook = _par_type(wf, "webhook")
    assert webhook["parameters"]["path"] == "deskgate-ifc-clash"
    assert webhook["parameters"]["httpMethod"] == "POST"


def test_http_request(wf: dict[str, Any]) -> None:
    http = _par_type(wf, "httpRequest")
    assert http["parameters"]["url"] == "http://host.docker.internal:8765/jobs"
    assert http["parameters"]["method"] == "POST"
    assert http["credentials"]["httpHeaderAuth"]["id"] == "DeskgateToken0001"
    assert "$execution.resumeUrl" in http["parameters"]["jsonBody"]


def test_wait_borne(wf: dict[str, Any]) -> None:
    wait = _par_type(wf, "wait")
    p = wait["parameters"]
    assert wait["typeVersion"] == 1.1
    assert p["resume"] == "webhook"
    assert p["limitWaitTime"] is True
    facteur = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400}[p["resumeUnit"]]
    assert p["resumeAmount"] * facteur > 14400


def test_condition_sur_body(wf: dict[str, Any], texte: str) -> None:
    cond = _par_type(wf, "if")["parameters"]["conditions"]["conditions"][0]
    assert "$json.body?.status" in cond["leftValue"]
    assert cond["rightValue"] == "succeeded"
    assert "{{ $json.status" not in texte


def test_parametres_par_defaut(wf: dict[str, Any]) -> None:
    sortie = _noeud(wf, "Parametres")["parameters"]["jsonOutput"]
    marque = "$json.body?.params ?? "
    debut = sortie.index(marque) + len(marque)
    fin = sortie.rindex(", timeout:")
    objet = json.loads(sortie[debut:fin])
    canonique = json.loads(PARAMS.read_text(encoding="utf-8"))
    assert objet == canonique
    assert (
        canonique["title_template"] == "{building}/{storey}/{trade_a}-{trade_b}/{type_a} x {type_b}"
    )
    assert len(canonique["mappings"]["type"]) == 38
    assert len(canonique["mappings"]["storey"]) == 9
    assert canonique["mappings"]["type"]["IfcCovering/CEILING"] == "Faux-plafond"
    assert "charter" not in sortie
    assert "max_clashes" not in sortie
    assert sortie.count("}}") == 1


def test_aucun_jeton(texte: str) -> None:
    assert "Bearer" not in texte
    assert re.search(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])", texte) is None

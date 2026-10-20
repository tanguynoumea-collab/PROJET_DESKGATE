"""Codes de sortie et messages de deskgate-bcf write."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.bim]


def test_succes_sans_stdout_ni_temporaire(ecrire, doc_valide, tmp_path):
    r = ecrire(doc_valide)
    assert r.returncode == 0, r.stderr
    assert r.stdout == ""
    assert (tmp_path / "out.bcf").is_file()
    assert not list(tmp_path.glob("*.tmp.bcf"))


def test_json_invalide(ecrire):
    r = ecrire(None, brut="{pas du json")
    assert r.returncode == 2
    assert r.stdout == ""
    assert "JSON invalide" in r.stderr


def test_entree_illisible(plugin_envs, tmp_path):
    r = subprocess.run(
        [
            str(plugin_envs["bcf_exe"]),
            "write",
            "--input",
            str(tmp_path / "absent.json"),
            "--output",
            str(tmp_path / "o.bcf"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert r.returncode == 2
    assert r.stdout == ""
    assert "illisible" in r.stderr


def test_schema_version_inconnue(ecrire, doc_valide):
    doc_valide["schema_version"] = 2
    r = ecrire(doc_valide)
    assert r.returncode == 2
    assert r.stdout == ""
    assert "schema_version" in r.stderr


def test_topics_vide(ecrire, doc_valide):
    doc_valide["topics"] = []
    r = ecrire(doc_valide)
    assert r.returncode == 2
    assert r.stdout == ""
    assert "non conforme" in r.stderr


def test_guid_ifc_trop_court(ecrire, doc_valide):
    doc_valide["topics"][0]["guids_a"][0] = "0" * 21
    r = ecrire(doc_valide)
    assert r.returncode == 2
    assert r.stdout == ""
    assert "topics/0/guids_a/0" in r.stderr


def test_couleur_six_caracteres(ecrire, doc_valide):
    doc_valide["colors"]["a"] = "E53935"
    r = ecrire(doc_valide)
    assert r.returncode == 2
    assert r.stdout == ""
    assert "colors/a" in r.stderr


def test_dossier_de_sortie_absent(ecrire, doc_valide, tmp_path: Path):
    r = ecrire(doc_valide, sortie=tmp_path / "absent" / "out.bcf")
    assert r.returncode == 3
    assert r.stdout == ""
    assert "introuvable" in r.stderr


def test_racine_non_objet(ecrire):
    r = ecrire(None, brut=json.dumps([1, 2]))
    assert r.returncode == 2
    assert "schema_version" in r.stderr

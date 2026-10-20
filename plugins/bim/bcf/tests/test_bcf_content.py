"""Contenu du BCF écrit : relecture bcf-client, vues, couleurs, sélection, déterminisme."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from _support.plugin_envs import run_json

pytestmark = [pytest.mark.bim]

SONDE = Path(__file__).parent / "envside" / "read_bcf.py"
ROUGE, BLEU, CONTEXTE = "FFE53935", "FF1E88E5", "40B0B0B0"


def _tag(e: ET.Element) -> str:
    return e.tag.rsplit("}", 1)[-1]


def _vues(z: zipfile.ZipFile, guid: str) -> dict[str, ET.Element]:
    noms = sorted(n for n in z.namelist() if n.startswith(guid + "/") and n.endswith(".bcfv"))
    return {n: ET.fromstring(z.read(n)) for n in noms}  # noqa: S314


def _guids(parent: ET.Element) -> list[str]:
    return sorted(c.get("IfcGuid", "") for c in parent if _tag(c) == "Component")


def _exceptions(root: ET.Element) -> list[str]:
    for e in root.iter():
        if _tag(e) == "Exceptions":
            return _guids(e)
    return []


def _couleurs(root: ET.Element) -> dict[str, list[str]]:
    res: dict[str, list[str]] = {}
    for e in root.iter():
        if _tag(e) == "Color" and e.get("Color"):
            res[(e.get("Color") or "").upper()] = _guids(e)
    return res


def _visibilite(root: ET.Element) -> str | None:
    for e in root.iter():
        if _tag(e) == "Visibility":
            return e.get("DefaultVisibility")
    raise AssertionError("Visibility absent")


def test_relecture_bcf_client(ecrire, doc_valide, plugin_envs, tmp_path):
    assert ecrire(doc_valide).returncode == 0
    res = run_json(plugin_envs["bcf"], SONDE, str(tmp_path / "out.bcf"))
    assert isinstance(res, dict)
    assert res["version"] == "2.1"
    assert len(res["topics"]) == 2
    par_guid = {t["guid"]: t for t in res["topics"]}
    assert sorted(par_guid) == sorted(t["guid"] for t in doc_valide["topics"])
    cams = []
    for t in doc_valide["topics"]:
        vps = par_guid[t["guid"]]["viewpoints"]
        assert len(vps) == 2
        assert not any(v["has_selection"] for v in vps)
        cams.append({v["camera"] for v in vps})
    assert cams == [{"perspective"}, {"orthogonal"}]


def test_deux_vues_et_couleurs(ecrire, doc_valide, tmp_path):
    assert ecrire(doc_valide).returncode == 0
    t = doc_valide["topics"][0]
    ab = sorted(t["guids_a"] + t["guids_b"])
    with zipfile.ZipFile(tmp_path / "out.bcf") as z:
        assert 'VersionId="2.1"' in z.read("bcf.version").decode("utf-8")
        assert f"{t['guid']}/markup.bcf" in z.namelist()
        vues = _vues(z, t["guid"])
        assert len(vues) == 2
        for n in z.namelist():
            if n.endswith((".bcfv", ".bcf")):
                racine = ET.fromstring(z.read(n))  # noqa: S314
                assert "Selection" not in {_tag(e) for e in racine.iter()}
    only = next(r for r in vues.values() if _visibilite(r) == "false")
    ctx = next(r for r in vues.values() if _visibilite(r) == "true")
    assert _exceptions(only) == ab
    assert _couleurs(only) == {ROUGE: sorted(t["guids_a"]), BLEU: sorted(t["guids_b"])}
    restants = sorted(g for g in t["context_guids"] if g not in ab)
    assert len(restants) == 3
    assert _couleurs(ctx) == {
        CONTEXTE: restants,
        ROUGE: sorted(t["guids_a"]),
        BLEU: sorted(t["guids_b"]),
    }


def test_determinisme_des_membres(ecrire, doc_valide, tmp_path):
    assert ecrire(doc_valide, nom="a.bcf").returncode == 0
    assert ecrire(doc_valide, nom="b.bcf").returncode == 0
    with zipfile.ZipFile(tmp_path / "a.bcf") as za, zipfile.ZipFile(tmp_path / "b.bcf") as zb:
        assert sorted(za.namelist()) == sorted(zb.namelist())
        for n in za.namelist():
            assert za.read(n) == zb.read(n), n

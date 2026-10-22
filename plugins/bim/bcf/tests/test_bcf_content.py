"""Contenu du BCF écrit : relecture bcf-client, vues, couleurs, sélection, déterminisme."""

from __future__ import annotations

import uuid
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
    g1 = str(uuid.uuid5(uuid.UUID(t["guid"]), "viewpoint-1-only"))
    only = vues[f"{t['guid']}/{g1}.bcfv"]
    ctx = vues[f"{t['guid']}/{_g2(t)}.bcfv"]
    assert _visibilite(only) == "false"
    assert _visibilite(ctx) == "false"
    assert _exceptions(only) == ab
    assert _couleurs(only) == {ROUGE: sorted(t["guids_a"]), BLEU: sorted(t["guids_b"])}
    restants = sorted(g for g in t["context_guids"] if g not in ab)
    assert len(restants) == 3
    assert _couleurs(ctx) == {
        CONTEXTE: restants,
        ROUGE: sorted(t["guids_a"]),
        BLEU: sorted(t["guids_b"]),
    }
    assert _exceptions(ctx) == sorted(set(ab) | set(restants))


def test_vue2_sans_contexte(ecrire, doc_valide, tmp_path):
    t = doc_valide["topics"][0]
    t["context_guids"] = []
    assert ecrire(doc_valide).returncode == 0
    ab = sorted(t["guids_a"] + t["guids_b"])
    with zipfile.ZipFile(tmp_path / "out.bcf") as z:
        ctx = ET.fromstring(z.read(f"{t['guid']}/{_g2(t)}.bcfv"))  # noqa: S314
    assert _visibilite(ctx) == "false"
    assert _exceptions(ctx) == ab
    assert CONTEXTE not in _couleurs(ctx)


def test_determinisme_des_membres(ecrire, doc_valide, tmp_path):
    assert ecrire(doc_valide, nom="a.bcf").returncode == 0
    assert ecrire(doc_valide, nom="b.bcf").returncode == 0
    with zipfile.ZipFile(tmp_path / "a.bcf") as za, zipfile.ZipFile(tmp_path / "b.bcf") as zb:
        assert sorted(za.namelist()) == sorted(zb.namelist())
        for n in za.namelist():
            assert za.read(n) == zb.read(n), n


def _markup(z: zipfile.ZipFile, guid: str) -> ET.Element:
    return ET.fromstring(z.read(f"{guid}/markup.bcf"))  # noqa: S314


def _g2(topic: dict) -> str:
    return str(uuid.uuid5(uuid.UUID(topic["guid"]), "viewpoint-2-context"))


def test_v2_snapshots_dans_le_zip(ecrire, doc_v2, tmp_path):
    assert ecrire(doc_v2).returncode == 0
    t = doc_v2["topics"][0]
    g, g2 = t["guid"], _g2(t)
    with zipfile.ZipFile(tmp_path / "out.bcf") as z:
        noms = set(z.namelist())
        for n in ("viewpoint.bcfv", "snapshot.png", f"{g2}.bcfv", f"{g2}.png"):
            assert f"{g}/{n}" in noms, n
        assert z.read(f"{g}/snapshot.png") == (tmp_path / "snapshots" / "s1-1.png").read_bytes()
        assert z.read(f"{g}/{g2}.png") == (tmp_path / "snapshots" / "s1-2.png").read_bytes()
        vps = [e for e in _markup(z, g).iter() if _tag(e) == "Viewpoints"]
        assert len(vps) == 2
        assert all(any(_tag(c) == "Snapshot" for c in v) for v in vps)
        index = [next(c.text for c in v if _tag(c) == "Index") for v in vps]
        assert sorted(index) == ["0", "1"]


def test_v2_sujet_sans_snapshot(ecrire, doc_v2, tmp_path):
    assert ecrire(doc_v2).returncode == 0
    g = doc_v2["topics"][1]["guid"]
    with zipfile.ZipFile(tmp_path / "out.bcf") as z:
        assert not [n for n in z.namelist() if n.startswith(g + "/") and n.endswith(".png")]
        assert f"{g}/viewpoint.bcfv" in z.namelist()
        m = _markup(z, g)
        assert "Snapshot" not in {_tag(e) for e in m.iter()}
        assert len([e for e in m if _tag(e) == "Comment"]) == 2


def test_v2_commentaires(ecrire, doc_v2, tmp_path):
    assert ecrire(doc_v2).returncode == 0
    with zipfile.ZipFile(tmp_path / "out.bcf") as z:
        for t in doc_v2["topics"]:
            m = _markup(z, t["guid"])
            vp_guids = {e.get("Guid") for e in m.iter() if _tag(e) == "Viewpoints"}
            comments = [e for e in m if _tag(e) == "Comment"]
            assert len(comments) == 2
            for c in comments:
                ref = next(e for e in c if _tag(e) == "Viewpoint")
                assert ref.get("Guid") in vp_guids


def test_v2_header(ecrire, doc_v2, tmp_path):
    assert ecrire(doc_v2).returncode == 0
    with zipfile.ZipFile(tmp_path / "out.bcf") as z:
        for t in doc_v2["topics"]:
            files = [e for e in _markup(z, t["guid"]).iter() if _tag(e) == "File"]
            assert [f.get("IfcProject") for f in files] == [
                "1AAAAAAAAAAAAAAAAAAAAA",
                "1BBBBBBBBBBBBBBBBBBBBB",
            ]
            fn = [next(c.text for c in f if _tag(c) == "Filename") for f in files]
            assert fn == ["CVC.ifc", "ARC.ifc"]


def test_v2_sans_header_files(ecrire, doc_v2, tmp_path):
    del doc_v2["header_files"]
    assert ecrire(doc_v2).returncode == 0
    with zipfile.ZipFile(tmp_path / "out.bcf") as z:
        for t in doc_v2["topics"]:
            assert "Header" not in {_tag(e) for e in _markup(z, t["guid"]).iter()}


def test_v2_camera_monde(ecrire, doc_v2, tmp_path):
    assert ecrire(doc_v2).returncode == 0
    t = doc_v2["topics"][0]
    with zipfile.ZipFile(tmp_path / "out.bcf") as z:
        racine = ET.fromstring(z.read(f"{t['guid']}/viewpoint.bcfv"))  # noqa: S314
    pt = next(e for e in racine.iter() if _tag(e) == "CameraViewPoint")
    xyz = [float(next(c.text for c in pt if _tag(c) == k)) for k in ("X", "Y", "Z")]
    assert xyz == pytest.approx([10.0, 20.0, 30.0], abs=1e-9)


def test_v2_determinisme(ecrire, doc_v2, tmp_path):
    assert ecrire(doc_v2, nom="a.bcf").returncode == 0
    assert ecrire(doc_v2, nom="b.bcf").returncode == 0
    with zipfile.ZipFile(tmp_path / "a.bcf") as za, zipfile.ZipFile(tmp_path / "b.bcf") as zb:
        assert sorted(za.namelist()) == sorted(zb.namelist())
        for n in za.namelist():
            assert za.read(n) == zb.read(n), n


def test_v2_relecture_bcf_client(ecrire, doc_v2, plugin_envs, tmp_path):
    assert ecrire(doc_v2).returncode == 0
    res = run_json(plugin_envs["bcf"], SONDE, str(tmp_path / "out.bcf"))
    assert isinstance(res, dict)
    par_guid = {t["guid"]: t for t in res["topics"]}
    t1 = par_guid[doc_v2["topics"][0]["guid"]]
    assert len(t1["viewpoints"]) == 2
    assert not any(v["has_selection"] for v in t1["viewpoints"])
    vue0 = next(v for v in t1["viewpoints"] if v["index"] == 0)
    assert vue0["snapshot"] == "snapshot.png"
    assert vue0["file"] == "viewpoint.bcfv"
    assert len(t1["comments"]) == 2

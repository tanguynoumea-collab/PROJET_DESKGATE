# SPDX-License-Identifier: MIT
"""ifc.clash avec bcf: true : Engine réel -> deskgate-bcf en sous-processus -> BcfXml.load."""

from __future__ import annotations

import uuid
import zipfile
from pathlib import Path
from typing import Any

import pytest

from _support.clash_env import ClashEnv
from _support.plugin_envs import run_json

pytestmark = [pytest.mark.bim, pytest.mark.proc]

REPO = Path(__file__).resolve().parents[3]
READ_BCF = REPO / "plugins" / "bim" / "bcf" / "tests" / "envside" / "read_bcf.py"
CREATED = "2026-10-21T10:00:00Z"
BASE: dict[str, Any] = {
    "selector_a": "IfcWall",
    "selector_b": "IfcDuctSegment",
    "mode": "hard",
    "tolerance": 0.002,
    "bcf": True,
    "created_at": CREATED,
}
CONTEXT_COLOR = "40B0B0B0"
PNG = bytes.fromhex("89504e470d0a1a0a")


@pytest.fixture
def settings(plugin_envs: dict[str, Any]) -> dict[str, Any]:
    return {"bcf_executable": str(plugin_envs["bcf_exe"])}


def read(plugin_envs: dict[str, Any], env: ClashEnv) -> dict[str, Any]:
    out = run_json(plugin_envs["bcf"], READ_BCF, str(env.work_dir / "conflits.bcf"))
    assert isinstance(out, dict)
    return out


def views(topic: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    g2 = str(uuid.uuid5(uuid.UUID(topic["guid"]), "viewpoint-2-context"))
    objets = [v for v in topic["viewpoints"] if v["guid"] != g2]
    contexte = [v for v in topic["viewpoints"] if v["guid"] == g2]
    assert len(objets) == 1 and len(contexte) == 1
    return objets[0], contexte[0]


def colored(view: dict[str, Any], color: str) -> list[str]:
    return view["colors"].get(color, [])


def test_bcf_mur_gaine_de_bout_en_bout(
    clash_env: ClashEnv, settings: dict[str, Any], plugin_envs: dict[str, Any]
) -> None:
    clash_env.place("mur_gaine.ifc")
    row, res = clash_env.run({**BASE, "ifc_a": "/data/depot/mur_gaine.ifc"}, settings=settings)
    assert row.status == "succeeded", row.error_message
    assert res["artifacts"] == [
        {"kind": "clashes", "path": f"/data/travail/{clash_env.last_job_id}/clashes.json"},
        {"kind": "bcf", "path": f"/data/travail/{clash_env.last_job_id}/conflits.bcf"},
    ]
    assert res["summary"]["bcf"] is True and res["summary"]["bcf_topics"] == 1
    g = clash_env.guids["mur_gaine.ifc"]
    bcf = read(plugin_envs, clash_env)
    assert bcf["version"] == "2.1"
    (topic,) = bcf["topics"]
    assert topic["guid"] == res["data"]["groups"][0]["id"]
    assert len(topic["viewpoints"]) == 2
    objets, contexte = views(topic)
    assert objets["exceptions"] == sorted([g["Mur1"], g["Gaine1"]])
    assert objets["has_selection"] is False and contexte["has_selection"] is False
    assert colored(objets, "FFE53935") == [g["Mur1"]]
    assert colored(objets, "FF1E88E5") == [g["Gaine1"]]
    membres = _members(clash_env.work_dir / "conflits.bcf")
    g2 = str(uuid.uuid5(uuid.UUID(topic["guid"]), "viewpoint-2-context"))
    for nom in (f"{topic['guid']}/viewpoint.bcfv", f"{topic['guid']}/snapshot.png"):
        assert nom in membres
    assert membres[f"{topic['guid']}/snapshot.png"].startswith(PNG)
    assert membres[f"{topic['guid']}/{g2}.png"].startswith(PNG)
    assert membres[f"{topic['guid']}/markup.bcf"].count(b"<Comment ") == 2
    assert "snapshots_unavailable" not in res["summary"]["warnings"]


def test_cinq_gaines_rayon_1_puis_10(
    clash_env: ClashEnv, settings: dict[str, Any], plugin_envs: dict[str, Any]
) -> None:
    clash_env.place("cinq_gaines.ifc")
    p = {**BASE, "ifc_a": "/data/depot/cinq_gaines.ifc"}
    row, res = clash_env.run({**p, "group_radius": 1.0}, settings=settings)
    assert row.status == "succeeded", row.error_message
    assert res["summary"]["bcf_topics"] == 5
    assert len(read(plugin_envs, clash_env)["topics"]) == 5
    row, res = clash_env.run({**p, "group_radius": 10.0}, settings=settings)
    assert row.status == "succeeded", row.error_message
    (topic,) = read(plugin_envs, clash_env)["topics"]
    objets, _ = views(topic)
    gaines = [v for k, v in clash_env.guids["cinq_gaines.ifc"].items() if k.startswith("Gaine")]
    assert set(gaines) <= set(objets["exceptions"])


def test_contexte_gris_voisins_seulement(
    clash_env: ClashEnv, settings: dict[str, Any], plugin_envs: dict[str, Any]
) -> None:
    clash_env.place("contexte.ifc")
    p = {**BASE, "ifc_a": "/data/depot/contexte.ifc"}
    row, _ = clash_env.run(p, settings=settings)
    assert row.status == "succeeded", row.error_message
    g = clash_env.guids["contexte.ifc"]
    (topic,) = read(plugin_envs, clash_env)["topics"]
    _, contexte = views(topic)
    gris = colored(contexte, CONTEXT_COLOR)
    assert g["Dalle_proche"] in gris
    assert g["Poteau_loin"] not in gris and g["Mur1"] not in gris and g["Gaine1"] not in gris
    assert colored(contexte, "FFE53935") == [g["Mur1"]]
    # D-18 : la vue 2 ne montre que conflit + contexte coloré (rien sans couleur)
    assert contexte["default_visibility"] is False
    visibles = set(colored(contexte, CONTEXT_COLOR)) | set(colored(contexte, "FFE53935"))
    visibles |= set(colored(contexte, "FF1E88E5"))
    assert set(contexte["exceptions"]) == visibles
    row, _ = clash_env.run({**p, "max_context": 0}, settings=settings)
    assert row.status == "succeeded", row.error_message
    (topic,) = read(plugin_envs, clash_env)["topics"]
    _, contexte = views(topic)
    assert colored(contexte, CONTEXT_COLOR) == []


def _members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


def test_deux_executions_identiques(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("mur_gaine.ifc")
    p = {**BASE, "ifc_a": "/data/depot/mur_gaine.ifc"}
    row, _ = clash_env.run(p, settings=settings)
    assert row.status == "succeeded", row.error_message
    first = _members(clash_env.work_dir / "conflits.bcf")
    row, _ = clash_env.run(p, settings=settings)
    assert row.status == "succeeded", row.error_message
    second = _members(clash_env.work_dir / "conflits.bcf")
    assert first.keys() == second.keys()
    assert first == second


def test_sans_images(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("mur_gaine.ifc")
    p = {**BASE, "ifc_a": "/data/depot/mur_gaine.ifc", "snapshots": False}
    row, _ = clash_env.run(p, settings=settings)
    assert row.status == "succeeded", row.error_message
    noms = _members(clash_env.work_dir / "conflits.bcf").keys()
    assert not [n for n in noms if n.endswith(".png")]
    assert len([n for n in noms if n.endswith(".bcfv")]) == 2


def test_rendu_impossible(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("mur_gaine.ifc")
    p = {**BASE, "ifc_a": "/data/depot/mur_gaine.ifc"}
    row, res = clash_env.run(p, settings={**settings, "snapshot_size": [0, 0]})
    assert row.status == "succeeded", row.error_message
    assert "snapshots_unavailable" in res["summary"]["warnings"]
    noms = _members(clash_env.work_dir / "conflits.bcf").keys()
    assert not [n for n in noms if n.endswith(".png")]


@pytest.mark.parametrize("bad", [{}, {"bcf_executable": "C:/inexistant/deskgate-bcf.exe"}])
def test_bcf_unavailable(clash_env: ClashEnv, bad: dict[str, Any]) -> None:
    clash_env.place("mur_gaine.ifc")
    row, _ = clash_env.run({**BASE, "ifc_a": "/data/depot/mur_gaine.ifc"}, settings=bad)
    assert row.status == "failed"
    assert (row.error_message or "").startswith("bcf_unavailable")


def test_aucun_conflit_pas_de_bcf(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("poutre_tuyau.ifc")
    p = {**BASE, "ifc_a": "/data/depot/poutre_tuyau.ifc", "selector_a": "IfcBeam"}
    p["selector_b"] = "IfcPipeSegment"
    row, res = clash_env.run(p, settings=settings)
    assert row.status == "succeeded", row.error_message
    assert all(a["kind"] != "bcf" for a in res["artifacts"])
    assert "bcf_skipped_no_clash" in res["summary"]["warnings"]
    assert res["summary"]["bcf"] is False
    assert not (clash_env.work_dir / "conflits.bcf").exists()


def test_bcf_faux_par_defaut(clash_env: ClashEnv, settings: dict[str, Any]) -> None:
    clash_env.place("mur_gaine.ifc")
    p = {k: v for k, v in BASE.items() if k not in {"bcf", "created_at"}}
    row, res = clash_env.run({**p, "ifc_a": "/data/depot/mur_gaine.ifc"}, settings=settings)
    assert row.status == "succeeded", row.error_message
    assert res["summary"]["bcf"] is False
    assert not (clash_env.work_dir / "bcf-input.json").exists()
    assert not (clash_env.work_dir / "conflits.bcf").exists()

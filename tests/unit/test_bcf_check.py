# SPDX-License-Identifier: MIT
"""Contrôle de scripts/recette/bcf_check.py sur de petits BCF construits en stdlib."""

from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "recette" / "bcf_check.py"
PNG = bytes.fromhex("89504e470d0a1a0a") + b"x"
TOPIC = "11111111-1111-1111-1111-111111111111"
G1 = "aaaaaaaa-0000-0000-0000-000000000001"
G2 = "aaaaaaaa-0000-0000-0000-000000000002"
TITLE = "BaJ/P01/CVC-ARC/Gaine x Mur"


def _module() -> Any:
    spec = importlib.util.spec_from_file_location("bcf_check", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _markup(title: str, header: bool, comments: int) -> str:
    head = (
        '<Header><File IfcProject="0123456789012345678901" Filename="a.ifc"/></Header>'
        if header
        else ""
    )
    com = "".join(
        f'<Comment Guid="c{i}"><Viewpoint Guid="{G1}"/></Comment>' for i in range(comments)
    )
    return (
        f"<Markup>{head}<Topic Guid='{TOPIC}'><Title>{title}</Title></Topic>"
        f"<Viewpoints Guid='{G1}'><Viewpoint>viewpoint.bcfv</Viewpoint>"
        "<Snapshot>snapshot.png</Snapshot><Index>0</Index></Viewpoints>"
        f"<Viewpoints Guid='{G2}'><Viewpoint>{G2}.bcfv</Viewpoint>"
        f"<Snapshot>{G2}.png</Snapshot><Index>1</Index></Viewpoints>{com}</Markup>"
    )


def _view2(vis: str, exc: tuple[str, ...], col: tuple[tuple[str, tuple[str, ...]], ...]) -> str:
    e = "".join(f'<Component IfcGuid="{g}"/>' for g in exc)
    c = "".join(
        f'<Color Color="{k}">' + "".join(f'<Component IfcGuid="{g}"/>' for g in v) + "</Color>"
        for k, v in col
    )
    return (
        f'<VisualizationInfo><Components><Visibility DefaultVisibility="{vis}">'
        f"<Exceptions>{e}</Exceptions></Visibility><Coloring>{c}</Coloring>"
        "</Components></VisualizationInfo>"
    )


def _build(
    tmp: Path,
    *,
    title: str = TITLE,
    header: bool = True,
    comments: int = 2,
    png2: bool = True,
    truncated: bool = False,
    cls: str = "IfcWall",
    vis2: str = "false",
    exc2: tuple[str, ...] = ("A", "B", "C"),
    col2: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("40B0B0B0", ("C",)),
        ("FFE53935", ("A",)),
        ("FF1E88E5", ("B",)),
    ),
) -> tuple[Path, Path]:
    bcf = tmp / "c.bcf"
    with zipfile.ZipFile(bcf, "w") as z:
        z.writestr(f"{TOPIC}/markup.bcf", _markup(title, header, comments))
        z.writestr(f"{TOPIC}/viewpoint.bcfv", "<v/>")
        z.writestr(f"{TOPIC}/{G2}.bcfv", _view2(vis2, exc2, col2))
        z.writestr(f"{TOPIC}/snapshot.png", PNG)
        if png2:
            z.writestr(f"{TOPIC}/{G2}.png", PNG)
    clashes = tmp / "clashes.json"
    pair = {"a_ifc_class": cls, "b_ifc_class": "IfcDuctSegment"}
    clashes.write_text(
        json.dumps(
            {
                "counts": {"clashes": 1, "returned": 1, "groups": 1},
                "truncated": truncated,
                "groups": [{"clashes": [pair]}],
            }
        ),
        encoding="utf-8",
    )
    return bcf, clashes


PIC = "{building}/{storey}/{trade_a}-{trade_b}/{type_a} x {type_b}"
ALLOWED = {"building": {"BaJ", "BaT"}, "trade_a": {"CVC"}, "trade_b": {"ARC"}}


def _run(
    bcf: Path,
    clashes: Path,
    template: str = PIC,
    allowed: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    return _module().check(bcf, clashes, template, ALLOWED if allowed is None else allowed)


def test_conforme(tmp_path: Path) -> None:
    res = _run(*_build(tmp_path))
    assert res["verdict"] is True and res["failures"] == []
    assert res["titles_matching"] == res["titles_allowed"] == res["topics"] == 1
    assert res["values_by_field"]["storey"] == {"P01": 1}


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"png2": False}, "PNG manquant"),
        ({"header": False}, "Header/File"),
        ({"comments": 1}, "commentaires"),
        ({"title": "BaJ/P01/CVC-ARC/Gaine x Mur (+2)"}, "titre non conforme"),
        ({"title": "Gaine x Mur"}, "hors gabarit"),
        ({"truncated": True}, "tronqué"),
        ({"cls": "IfcOpeningElement"}, "IfcOpeningElement"),
    ],
)
def test_defauts(tmp_path: Path, kwargs: dict[str, Any], message: str) -> None:
    res = _run(*_build(tmp_path, **kwargs))
    assert res["verdict"] is False
    assert any(message in f for f in res["failures"])


def test_valeur_non_admise(tmp_path: Path) -> None:
    res = _run(*_build(tmp_path, title="Jura/J_11_P01/CVC-ARC/Gaine x Mur"))
    assert res["verdict"] is False
    assert res["titles_matching"] == 1 and res["titles_allowed"] == 0
    assert any("building" in f for f in res["failures"])


def test_gabarit_simple_sans_tables(tmp_path: Path) -> None:
    res = _run(*_build(tmp_path, title="Gaine x Mur"), "{type_a} x {type_b}", {})
    assert res["verdict"] is True
    assert res["titles_matching"] == 1


def test_gabarit_champ_inconnu(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        _run(*_build(tmp_path), "{inconnu}/{type_a}", {})


def test_champ_repete_identique(tmp_path: Path) -> None:
    ok = _run(*_build(tmp_path, title="Gaine/Gaine"), "{type_a}/{type_a}", {})
    assert ok["verdict"] is True
    ko = _run(*_build(tmp_path, title="Gaine/Mur"), "{type_a}/{type_a}", {})
    assert ko["verdict"] is False


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"vis2": "true"}, "visibilité par défaut vraie"),
        ({"exc2": ("A", "B", "C", "D")}, "1 élément(s) visible(s) non coloré(s)"),
        (
            {"col2": (("FFB0B0B0", ("C",)), ("FFE53935", ("A",)), ("FF1E88E5", ("B",)))},
            "contexte non transparent",
        ),
    ],
)
def test_vue2_defauts(tmp_path: Path, kwargs: dict[str, Any], message: str) -> None:
    res = _run(*_build(tmp_path, **kwargs))
    assert res["verdict"] is False
    assert any(message in f for f in res["failures"])


def test_vue2_sans_contexte(tmp_path: Path) -> None:
    res = _run(
        *_build(
            tmp_path,
            exc2=("A", "B"),
            col2=(("FFE53935", ("A",)), ("FF1E88E5", ("B",))),
        )
    )
    assert res["verdict"] is True

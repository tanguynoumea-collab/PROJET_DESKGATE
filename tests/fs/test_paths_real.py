"""Attaques de chemins sur un vrai disque : jonctions, flux alternatifs, noms réservés."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from deskgate.core.paths import (
    Mapping,
    PathDenied,
    is_under,
    resolve_within_roots,
    validate_artifact_path,
    validate_container_path,
)

pytestmark = [
    pytest.mark.fs,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows seul"),
]

Junction = Callable[[Path, Path], Path]


@pytest.fixture
def arbre(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "a.txt").write_text("a", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("s", encoding="utf-8")
    return tmp_path


def _cfg(root: Path) -> tuple[list[Mapping], list[str]]:
    return [Mapping("/data", root.as_posix())], [root.as_posix()]


def test_fichier_reel_accepte(arbre: Path) -> None:
    m, r = _cfg(arbre / "root")
    res = validate_container_path("/data/sub/a.txt", m, r)
    assert is_under(res, (arbre / "root").resolve().as_posix())


def test_fichier_inexistant_accepte(arbre: Path) -> None:
    m, r = _cfg(arbre / "root")
    assert validate_container_path("/data/sub/nouveau.txt", m, r).endswith("/sub/nouveau.txt")


def test_junction_vers_exterieur_refusee(arbre: Path, junction: Junction) -> None:
    m, r = _cfg(arbre / "root")
    junction(arbre / "root" / "jun", arbre / "outside")
    with pytest.raises(PathDenied) as info:
        validate_container_path("/data/jun/secret.txt", m, r)
    assert info.value.code == "path_outside_roots"


def test_junction_fichier_inexistant_refusee(arbre: Path, junction: Junction) -> None:
    m, r = _cfg(arbre / "root")
    junction(arbre / "root" / "jun", arbre / "outside")
    with pytest.raises(PathDenied) as info:
        validate_container_path("/data/jun/new.txt", m, r)
    assert info.value.code == "path_outside_roots"


def test_racine_qui_est_une_junction(tmp_path: Path, junction: Junction) -> None:
    real = tmp_path / "real"
    real.mkdir()
    rootj = junction(tmp_path / "rootj", real)
    m, r = _cfg(rootj)
    assert validate_container_path("/data/x.txt", m, r).endswith("/real/x.txt")


def test_ads_reel_refuse(arbre: Path) -> None:
    f = arbre / "root" / "f.txt"
    f.write_text("x", encoding="utf-8")
    with open(f"{f}:flux", "w", encoding="utf-8") as flux:
        flux.write("cache")
    m, r = _cfg(arbre / "root")
    with pytest.raises(PathDenied) as info:
        validate_container_path("/data/f.txt:flux", m, r)
    assert info.value.code == "path_invalid"


@pytest.mark.parametrize("raw", ["/data/CON", "/data/sub/nul.txt"])
def test_nom_reserve_refuse(arbre: Path, raw: str) -> None:
    m, r = _cfg(arbre / "root")
    with pytest.raises(PathDenied) as info:
        validate_container_path(raw, m, r)
    assert info.value.code == "path_invalid"


def test_casse_differente_acceptee(arbre: Path) -> None:
    root = arbre / "root"
    m, r = _cfg(root)
    validate_container_path("/data/SUB/A.TXT", m, r)
    haut = root.as_posix().upper() + "/sub/a.txt"
    assert validate_artifact_path(haut, m, r).lower() == "/data/sub/a.txt"


def test_prefixe_frere_refuse(arbre: Path) -> None:
    root = arbre / "root"
    frere = arbre / (root.name + "2")
    frere.mkdir()
    (frere / "x.txt").write_text("x", encoding="utf-8")
    with pytest.raises(PathDenied) as info:
        resolve_within_roots((frere / "x.txt").as_posix(), [root.as_posix()])
    assert info.value.code == "path_outside_roots"


def test_symlink_vers_exterieur_refuse(arbre: Path, symlink_ok: bool) -> None:
    assert symlink_ok
    root = arbre / "root"
    m, r = _cfg(root)
    lien = root / "lien"
    os.symlink(arbre / "outside", lien, target_is_directory=True)
    try:
        with pytest.raises(PathDenied) as info:
            validate_container_path("/data/lien/secret.txt", m, r)
        assert info.value.code == "path_outside_roots"
    finally:
        os.rmdir(lien)

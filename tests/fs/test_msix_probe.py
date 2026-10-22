"""LIV-001 : détection du contexte empaqueté (sonde d'écriture, identité de paquet)."""

from __future__ import annotations

from pathlib import Path

import pytest

from deskgate import scheduler
from deskgate.scheduler import detect_packaged_context, probe_virtualized

pytestmark = pytest.mark.fs


def _leftovers(root: Path) -> list[Path]:
    return list(root.rglob("deskgate-probe-*"))


def test_package_full_name_hors_paquet() -> None:
    assert scheduler.package_full_name() is None


def test_sonde_sans_redirection(tmp_path: Path) -> None:
    assert probe_virtualized(tmp_path) is None
    assert _leftovers(tmp_path) == []


def test_sonde_redirigee(tmp_path: Path) -> None:
    copies: list[Path] = []

    def write(marker: Path, data: bytes) -> None:
        target = tmp_path / "Packages" / "App_x" / "LocalCache" / "Local"
        target.mkdir(parents=True)
        copy = target / marker.name
        copy.write_bytes(data)
        copies.append(copy)

    found = probe_virtualized(tmp_path, write=write)
    assert found == copies[0]
    assert not copies[0].exists()
    assert _leftovers(tmp_path) == []


def test_sonde_ecriture_impossible(tmp_path: Path) -> None:
    def write(marker: Path, data: bytes) -> None:
        raise PermissionError("refusé")

    assert probe_virtualized(tmp_path, write=write) is None
    assert _leftovers(tmp_path) == []


def test_detect_identite() -> None:
    def probe(_: Path) -> Path | None:
        raise AssertionError("sonde non attendue")

    reason = detect_packaged_context({}, identity=lambda: "Pkg_1.0_x64__abc", probe=probe)
    assert reason is not None
    assert "Pkg_1.0_x64__abc" in reason


def test_detect_sonde() -> None:
    copy = Path("C:/U/AppData/Local/Packages/Claude_pzs/LocalCache/Local/f")
    reason = detect_packaged_context(
        {"LOCALAPPDATA": "C:/U/AppData/Local"}, identity=lambda: None, probe=lambda _: copy
    )
    assert reason is not None
    assert "Claude_pzs" in reason


def test_detect_home_dans_un_paquet() -> None:
    env = {"DESKGATE_HOME": r"C:\U\AppData\Local\Packages\X\LocalCache\Local\Deskgate"}
    assert detect_packaged_context(env, identity=lambda: None, probe=lambda _: None)


def test_detect_rien() -> None:
    assert detect_packaged_context({}, identity=lambda: None, probe=lambda _: None) is None

    def probe(_: Path) -> Path | None:
        raise AssertionError("sans LOCALAPPDATA la sonde n'est pas appelée")

    assert detect_packaged_context({}, identity=lambda: None, probe=probe) is None

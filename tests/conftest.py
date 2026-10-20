"""Fixtures communes de la suite de tests Deskgate."""

from __future__ import annotations

import os
import socket
import subprocess
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest


@pytest.fixture
def instance_name() -> str:
    """Nom de mutex unique par test, pour ne jamais entrer en collision avec un vrai runner."""
    return f"Local\\DeskgateTest-{uuid.uuid4().hex}"


@pytest.fixture
def data_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Dossier de données isolé : crée `tmp_path/home` et pose `DESKGATE_HOME`."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("DESKGATE_HOME", str(home))
    return home


@pytest.fixture
def free_port() -> int:
    """Port TCP libre sur 127.0.0.1 (le socket de sondage est fermé avant le retour)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def junction(tmp_path: Path) -> Iterator[Callable[[Path, Path], Path]]:
    """Fabrique de jonctions NTFS (`mklink /J`, sans droits administrateur).

    Les jonctions sont retirées par `os.rmdir` à la fin, avant tout `rmtree`,
    pour ne jamais supprimer le contenu de la cible.
    """
    created: list[Path] = []

    def make(link: Path, target: Path) -> Path:
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True,
            capture_output=True,
        )
        created.append(link)
        return link

    yield make
    for link in created:
        if link.exists() or link.is_symlink():
            os.rmdir(link)


@pytest.fixture
def symlink_ok(tmp_path: Path) -> bool:
    """Vérifie que les liens symboliques sont permis ; sinon saute le test (WinError 1314)."""
    cible = tmp_path / "symlink-cible"
    lien = tmp_path / "symlink-lien"
    cible.mkdir()
    try:
        os.symlink(cible, lien, target_is_directory=True)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("Privilège de lien symbolique absent (mode développeur désactivé)")
        raise
    os.rmdir(lien)
    return True

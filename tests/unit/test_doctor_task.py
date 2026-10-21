"""Tests de la vérification de la tâche par `deskgate doctor` (XML relu et falsifié)."""

from __future__ import annotations

from pathlib import Path

import pytest

from deskgate import doctor

from .test_scheduler_xml import NORMALISE

pytestmark = pytest.mark.unit

FACTICE = r"C:\venv\Scripts\pythonw.exe"


def _xml(tmp_path: Path, name: str = "pythonw.exe") -> str:
    exe = tmp_path / name
    exe.write_bytes(b"")
    assert FACTICE in NORMALISE
    return NORMALISE.replace(FACTICE, str(exe))


def _check(xml: str | None) -> list[doctor.Check]:
    return doctor.check_task(query=lambda _name: xml)


def _echecs(checks: list[doctor.Check]) -> list[str]:
    return [c.message for c in checks if c.level == "echec"]


def test_tache_absente() -> None:
    checks = _check(None)
    assert [c.level for c in checks] == ["echec"]
    assert "task install" in checks[0].message


def test_xml_conforme(tmp_path: Path) -> None:
    checks = _check(_xml(tmp_path))
    assert [c.level for c in checks] == ["ok"]


@pytest.mark.parametrize(
    ("ancien", "nouveau", "mot"),
    [
        ("PT0S", "PT72H", "durée"),
        (
            "<DisallowStartIfOnBatteries>false",
            "<DisallowStartIfOnBatteries>true",
            "batterie",
        ),
        (
            "<LogonType>InteractiveToken</LogonType>",
            "<LogonType>InteractiveToken</LogonType><RunLevel>HighestAvailable</RunLevel>",
            "élévation",
        ),
        ("InteractiveToken", "Password", "session"),
        ("<LogonTrigger>", "<BootTrigger>", "ouverture de session"),
    ],
)
def test_falsifications(tmp_path: Path, ancien: str, nouveau: str, mot: str) -> None:
    xml = _xml(tmp_path)
    assert ancien in xml
    xml = xml.replace(ancien, nouveau)
    if ancien == "<LogonTrigger>":
        xml = xml.replace("</LogonTrigger>", "</BootTrigger>")
    echecs = _echecs(_check(xml))
    assert any(mot in m for m in echecs), echecs


def test_redemarrage_retire_est_un_avertissement(tmp_path: Path) -> None:
    xml = _xml(tmp_path)
    debut = xml.index("<RestartOnFailure>")
    fin = xml.index("</RestartOnFailure>") + len("</RestartOnFailure>")
    checks = _check(xml[:debut] + xml[fin:])
    assert _echecs(checks) == []
    assert any(c.level == "avertissement" for c in checks)


def test_commande_inexistante(tmp_path: Path) -> None:
    xml = _xml(tmp_path).replace("pythonw.exe", "absent.exe")
    assert any("introuvable" in m for m in _echecs(_check(xml)))


def test_commande_autre_que_pythonw(tmp_path: Path) -> None:
    checks = _check(_xml(tmp_path, "python.exe"))
    assert _echecs(checks) == []
    assert any(c.level == "avertissement" and "console visible" in c.message for c in checks)


def test_arguments_differents(tmp_path: Path) -> None:
    xml = _xml(tmp_path).replace("-m deskgate serve", "-m autre")
    assert any("arguments" in m for m in _echecs(_check(xml)))

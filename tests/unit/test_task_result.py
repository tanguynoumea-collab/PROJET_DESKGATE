"""Classification et lecture du dernier résultat de la tâche planifiée."""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from deskgate import scheduler
from deskgate.scheduler import classify_task_result
from deskgate.scheduler import last_task_result as real_last_task_result

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("code", "kind", "level"),
    [
        (0, "ok", "ok"),
        (0x41301, "running", "ok"),
        (0x41303, "never", "ok"),
        (0x8007010B, "virtualized", "echec"),
        (2147942667, "virtualized", "echec"),
        (2, "runner_exit", "avertissement"),
        (3, "runner_exit", "avertissement"),
        (4, "runner_exit", "avertissement"),
        (5, "runner_exit", "avertissement"),
        (6, "runner_exit", "avertissement"),
        (0x41306, "failure", "avertissement"),
        (0x80070002, "failure", "avertissement"),
        (None, "unreadable", "avertissement"),
    ],
)
def test_classification(code: int | None, kind: str, level: str) -> None:
    r = classify_task_result(code)
    assert (r.kind, r.level) == (kind, level)


def test_messages() -> None:
    assert "MSIX" in classify_task_result(0x8007010B).message
    assert "terminal normal" in classify_task_result(0x8007010B).message
    assert "échec répété" in classify_task_result(6).message
    assert "configuration invalide" in classify_task_result(2).message
    assert "0x00041306" in classify_task_result(0x41306).message
    assert "0x80070002" in classify_task_result(0x80070002).message


@pytest.mark.parametrize("nom", ["a'b", "a b", "", "x;y"])
def test_nom_refuse_sans_processus(nom: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def espion(*a: Any, **k: Any) -> None:
        raise AssertionError("processus lancé")

    monkeypatch.setattr(scheduler.subprocess, "run", espion)
    assert real_last_task_result(nom) is None


def _faux(stdout: str) -> Any:
    def run(*a: Any, **k: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(a, 0, stdout, "")

    return run


@pytest.mark.parametrize(
    ("sortie", "attendu"),
    [
        ("2147942667\r\n", 2147942667),
        ("-2147024629", 2147942667),
        ("", None),
        ("erreur localisée", None),
    ],
)
def test_lecture(sortie: str, attendu: int | None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler.subprocess, "run", _faux(sortie))
    assert real_last_task_result("Deskgate") == attendu


@pytest.mark.parametrize("exc", [subprocess.TimeoutExpired("x", 1), OSError("x")])
def test_erreurs_donnent_none(exc: Exception, monkeypatch: pytest.MonkeyPatch) -> None:
    def run(*a: Any, **k: Any) -> None:
        raise exc

    monkeypatch.setattr(scheduler.subprocess, "run", run)
    assert real_last_task_result("Deskgate") is None

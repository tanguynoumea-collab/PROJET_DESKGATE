"""Décision, budget glissant et code de sortie du superviseur : fonctions pures."""

from __future__ import annotations

import ast
import pathlib

import pytest

import deskgate.supervisor as supervisor_module
from deskgate.supervisor import (
    EXIT_THREAD_FAILED,
    MAX_RECOVER_FAILURES,
    RECOVER_BACKOFF_CAP_S,
    Decision,
    decide,
    exit_code,
    recent,
    recover_delay,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("eng", "snd", "rec", "restart_e", "restart_s", "give_up"),
    [
        (False, False, 0, False, False, False),
        (True, False, 0, True, False, False),
        (False, True, 2, False, True, False),
        (True, True, 1, True, True, False),
        (True, False, 3, False, False, True),
        (True, True, 2, False, False, True),
    ],
)
def test_decide(
    eng: bool, snd: bool, rec: int, restart_e: bool, restart_s: bool, give_up: bool
) -> None:
    d = decide(engine_failed=eng, sender_failed=snd, recent_restarts=rec)
    assert d == Decision(restart_e, restart_s, give_up)


def test_recent() -> None:
    assert recent([0.0, 100.0, 650.0], now=699.0) == [100.0, 650.0]


def test_recent_borne_exclusive() -> None:
    assert recent([100.0], now=700.0, window=600.0) == []


def test_exit_code() -> None:
    assert exit_code(gave_up=False) == 0
    assert exit_code(gave_up=True) == 6 == EXIT_THREAD_FAILED


def test_supervisor_sans_sqlite_ni_ctypes() -> None:
    src = pathlib.Path(__file__).resolve().parents[2] / "src" / "deskgate" / "supervisor.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    names = {
        a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    assert not ({"sqlite3", "ctypes", "subprocess"} & names)


@pytest.mark.parametrize(
    ("n", "delay"),
    [(0, 0.0), (1, 2.0), (2, 4.0), (3, 8.0), (4, 16.0), (5, 30.0), (10, 30.0)],
)
def test_recover_delay(n: int, delay: float) -> None:
    assert recover_delay(n) == delay


def test_recover_delay_plafond_personnalise() -> None:
    assert recover_delay(3, cap=5.0) == 5.0


@pytest.mark.parametrize(
    ("eng", "snd", "failures", "expected"),
    [
        (True, False, 10, Decision(False, False, True)),
        (True, False, 9, Decision(True, False, False)),
        (False, True, 10, Decision(False, True, False)),
    ],
)
def test_decide_echecs_de_recover(eng: bool, snd: bool, failures: int, expected: Decision) -> None:
    d = decide(engine_failed=eng, sender_failed=snd, recent_restarts=0, recover_failures=failures)
    assert d == expected


def test_constantes_de_recover() -> None:
    assert MAX_RECOVER_FAILURES == 10
    assert RECOVER_BACKOFF_CAP_S == 30.0


def test_docstring_verdict_differe() -> None:
    doc = supervisor_module.__doc__ or ""
    assert "verdict différé" in doc
    assert "interrupted" in doc

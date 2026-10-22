"""Décision, budget glissant et code de sortie du superviseur : fonctions pures."""

from __future__ import annotations

import ast
import pathlib

import pytest

from deskgate.supervisor import EXIT_THREAD_FAILED, Decision, decide, exit_code, recent

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

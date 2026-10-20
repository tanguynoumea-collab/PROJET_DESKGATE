"""Décision d'un tour d'engine : table déterministe, sans attente réelle."""

from __future__ import annotations

import pytest

from deskgate.core.states import (
    CANCELLED,
    FAILED,
    INTERRUPTED,
    QUEUED,
    RUNNING,
    STATUSES,
    SUCCEEDED,
    TERMINAL,
    TIMEOUT,
    Decision,
    Observation,
    step,
)

pytestmark = pytest.mark.unit

GRACE = 10.0


def _obs(
    exit_code: int | None = None,
    cancel: bool = False,
    sent: float | None = None,
    deadline: float = 100.0,
) -> Observation:
    return Observation(
        exit_code=exit_code, cancel_requested=cancel, cancel_sent_at=sent, deadline=deadline
    )


CASES = [
    pytest.param(_obs(0, deadline=5.0), 6.0, Decision("exited", None), id="sortie-avant-echeance"),
    pytest.param(_obs(1, cancel=True), 1.0, Decision("exited", CANCELLED), id="sortie-annulee"),
    pytest.param(_obs(None, cancel=True), 1.0, Decision("write_cancel_flag"), id="ecrire-drapeau"),
    pytest.param(
        _obs(None, cancel=True, deadline=5.0), 5.0, Decision("write_cancel_flag"), id="annul-gagne"
    ),
    pytest.param(_obs(None, True, 10.0), 19.9, Decision("wait"), id="grace-en-cours"),
    pytest.param(_obs(None, True, 10.0), 20.0, Decision("kill", CANCELLED), id="grace-ecoulee"),
    pytest.param(_obs(None, True, 10.0, 12.0), 15.0, Decision("wait"), id="echeance-ignoree"),
    pytest.param(_obs(None, deadline=50.0), 50.0, Decision("kill", TIMEOUT), id="timeout"),
    pytest.param(_obs(None, deadline=50.0), 49.9, Decision("wait"), id="attente"),
]


@pytest.mark.parametrize(("obs", "now", "expected"), CASES)
def test_step_table(obs: Observation, now: float, expected: Decision) -> None:
    assert step(obs, now, GRACE) == expected


def test_statuses() -> None:
    assert STATUSES == (QUEUED, RUNNING, SUCCEEDED, FAILED, TIMEOUT, CANCELLED, INTERRUPTED)
    assert TERMINAL == {SUCCEEDED, FAILED, TIMEOUT, CANCELLED, INTERRUPTED}
    assert QUEUED not in TERMINAL
    assert RUNNING not in TERMINAL

"""Verdict terminal pur."""

from __future__ import annotations

import pytest

from deskgate.core.outcome import (
    RESTART_MESSAGE,
    Verdict,
    kill_verdict,
    memory_exhausted,
    verdict,
)
from deskgate.core.worker_protocol import ResultState

pytestmark = pytest.mark.unit

CASES: list[tuple[int, ResultState, bool, str, str | None]] = [
    (0, "valid", True, "succeeded", None),
    (0, "valid", False, "failed", "artifact_outside_roots"),
    (1, "valid", True, "failed", "nonzero_exit"),
    (1, "plugin_error", True, "failed", "plugin_error"),
    (0, "missing", True, "failed", "missing_result"),
    (3, "missing", True, "failed", "nonzero_exit"),
    (0, "invalid", True, "failed", "invalid_result"),
    (0, "too_large", True, "failed", "result_too_large"),
]


@pytest.mark.parametrize(("code", "state", "ok", "status", "error"), CASES)
def test_verdict(code: int, state: ResultState, ok: bool, status: str, error: str | None) -> None:
    v = verdict(exit_code=code, result_state=state, artifacts_ok=ok)
    assert v.status == status
    assert v.error_code == error
    assert (v.error_message is None) == (error is None)


def test_nonzero_message_mentions_code() -> None:
    v = verdict(exit_code=3, result_state="missing", artifacts_ok=True)
    assert v.error_message == "Le plugin s'est terminé avec le code 3."


def test_kill_verdicts() -> None:
    assert kill_verdict("timeout") == Verdict("timeout", "timeout", "Délai maximum dépassé.")
    assert kill_verdict("cancelled") == Verdict("cancelled", "cancelled", "Tâche annulée.")


def test_kill_verdict_rejects_other() -> None:
    with pytest.raises(ValueError):
        kill_verdict("failed")


def test_restart_message() -> None:
    assert RESTART_MESSAGE == "Runner redémarré pendant l'exécution."


MO = 2**20


def test_memory_exhausted_seuil() -> None:
    assert not memory_exhausted(None, 200)
    assert not memory_exhausted(190 * MO, None)
    assert memory_exhausted(190 * MO, 200)
    assert not memory_exhausted(150 * MO, 200)


@pytest.mark.parametrize(
    ("exit_code", "state"),
    [(3221225477, "missing"), (1, "plugin_error"), (1, "invalid"), (1, "valid")],
)
def test_verdict_memory_limit(exit_code: int, state: ResultState) -> None:
    v = verdict(exit_code=exit_code, result_state=state, artifacts_ok=True, memory_limit_mb=200)
    assert (v.status, v.error_code) == ("failed", "memory_limit")
    assert v.error_message is not None
    assert "200 Mo" in v.error_message
    assert "memory_mb" in v.error_message


def test_verdict_memory_limit_ne_requalifie_pas_un_succes() -> None:
    v = verdict(exit_code=0, result_state="valid", artifacts_ok=True, memory_limit_mb=200)
    assert v.status == "succeeded"

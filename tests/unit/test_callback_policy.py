"""Politique de rappel : table de décision n8n 2.43.8 et délai croissant."""

from __future__ import annotations

import random

import pytest

from deskgate.core.callback_policy import (
    ABANDONED_REJECTED,
    ABANDONED_STALE,
    DELIVERED,
    DELIVERED_DUPLICATE,
    FINAL,
    RETRY_BACKOFF,
    RETRY_MINIMAL,
    RETRY_SHORT,
    classify,
    next_delay,
)

pytestmark = pytest.mark.unit


def _rng(seed: int) -> random.Random:
    return random.Random(seed)  # noqa: S311


RUNNING = b'{"code":409,"message":"The execution \\"42\\" is running already."}'
RESUME = b'{"message":"The execution \\"42\\" is about to resume."}'
FINISHED = b'{"message":"The execution \\"42 has finished already."}'
FINISHED_ERR = b'{"message":"The execution \\"42\\" has finished with error."}'


@pytest.mark.parametrize(
    ("status", "body", "maybe", "prev", "kind", "reason"),
    [
        (200, b'{"message":"Workflow was started"}', False, None, DELIVERED, ""),
        (204, None, False, None, DELIVERED, ""),
        (409, RUNNING, False, None, RETRY_SHORT, "running"),
        (409, RESUME, False, None, RETRY_SHORT, "running"),
        (409, FINISHED, True, None, DELIVERED_DUPLICATE, "finished"),
        (409, FINISHED, False, None, ABANDONED_STALE, "finished"),
        (409, FINISHED_ERR, True, None, DELIVERED_DUPLICATE, "finished"),
        (409, FINISHED_ERR, False, None, ABANDONED_STALE, "finished"),
        (409, b"<html>conflit</html>", False, None, RETRY_SHORT, "unknown_409"),
        (409, None, False, None, RETRY_SHORT, "unknown_409"),
        (404, None, False, None, RETRY_SHORT, "confirm_404"),
        (404, None, False, 404, ABANDONED_STALE, "http_404"),
        (404, None, False, 500, RETRY_SHORT, "confirm_404"),
        (401, None, False, 401, ABANDONED_REJECTED, "http_401"),
        (403, None, False, 403, ABANDONED_REJECTED, "http_403"),
        (401, None, False, 404, RETRY_SHORT, "confirm_401"),
        (413, None, False, None, RETRY_MINIMAL, "too_large"),
        (413, None, False, 413, RETRY_BACKOFF, "too_large"),
        (500, None, False, None, RETRY_BACKOFF, "http_500"),
        (502, None, False, None, RETRY_BACKOFF, "http_502"),
        (408, None, False, None, RETRY_BACKOFF, "http_408"),
        (429, None, False, None, RETRY_BACKOFF, "http_429"),
        (400, None, False, None, RETRY_BACKOFF, "http_400"),
        (307, None, False, None, RETRY_BACKOFF, "http_307"),
        (None, None, False, None, RETRY_BACKOFF, "network"),
        (409, b'{"message":"IS RUNNING ALREADY"}', False, None, RETRY_SHORT, "running"),
    ],
)
def test_classify(
    status: int | None,
    body: bytes | None,
    maybe: bool,
    prev: int | None,
    kind: str,
    reason: str,
) -> None:
    decision = classify(status, body, maybe_delivered=maybe, prev_status=prev)
    assert decision.kind == kind
    assert decision.reason == reason


def test_classify_lit_seulement_4096_octets() -> None:
    body = b"x" * 5000 + b"is running already"
    assert classify(409, body, maybe_delivered=False).reason == "unknown_409"


def test_classify_corps_texte() -> None:
    assert classify(409, "has finished already", maybe_delivered=True).kind == DELIVERED_DUPLICATE


def test_final() -> None:
    assert {DELIVERED, DELIVERED_DUPLICATE, ABANDONED_STALE, ABANDONED_REJECTED} == FINAL


@pytest.mark.parametrize(
    ("attempts", "low", "high"),
    [(1, 1.5, 2.5), (2, 3, 5), (3, 6, 10), (4, 12, 20), (0, 1.5, 2.5)],
)
def test_next_delay_croit(attempts: int, low: float, high: float) -> None:
    for seed in range(20):
        d = next_delay(attempts, max_backoff_s=300, rng=_rng(seed))
        assert low <= d <= high


def test_next_delay_plafonne() -> None:
    for seed in range(20):
        assert next_delay(20, max_backoff_s=300, rng=_rng(seed)) <= 300


@pytest.mark.parametrize(
    ("attempts", "low", "high"),
    [(1, 1.5, 2.5), (2, 2.25, 3.75), (3, 3.375, 5.625)],
)
def test_next_delay_court(attempts: int, low: float, high: float) -> None:
    for seed in range(20):
        d = next_delay(attempts, max_backoff_s=300, rng=_rng(seed), short=True)
        assert low <= d <= high


def test_next_delay_court_plafonne() -> None:
    for seed in range(20):
        d = next_delay(30, max_backoff_s=300, rng=_rng(seed), short=True)
        assert 0 <= d <= 30

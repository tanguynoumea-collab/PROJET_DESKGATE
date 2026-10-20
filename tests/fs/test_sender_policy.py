"""Sender : politique de réponse de bout en bout sur le faux n8n (CB-03, SEC-06)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from _support.fake_n8n import (
    DROP,
    FINISHED,
    FINISHED_ERROR,
    INVALID_TOKEN,
    NOT_FOUND,
    OK,
    RUNNING,
    SERVER_ERROR,
    SIG,
    FakeN8n,
    Step,
)
from _support.jobs import make_config
from _support.sender_helpers import (
    FakeWall,
    advance_to_next,
    all_audit_text,
    audit_details,
    callback_config,
    callback_row,
    make_sender,
    make_terminal,
    next_attempt,
)
from deskgate.core.config import RunnerConfig
from deskgate.sender import Sender

pytestmark = pytest.mark.fs

FORBIDDEN_403 = Step(403, b"{}")
HTML_409 = Step(409, b"<html>?</html>")

SCENARIOS = [
    ("ok", [OK], "delivered", 1),
    ("running_puis_ok", [RUNNING, OK], "delivered", 2),
    ("coupure_puis_termine", [DROP, RUNNING, FINISHED], "delivered_duplicate", 3),
    ("running_puis_termine", [RUNNING, FINISHED], "abandoned_stale", 2),
    ("termine_en_erreur", [FINISHED_ERROR], "abandoned_stale", 1),
    ("404_deux_fois", [NOT_FOUND, NOT_FOUND], "abandoned_stale", 2),
    ("404_puis_ok", [NOT_FOUND, OK], "delivered", 2),
    ("401_deux_fois", [INVALID_TOKEN, INVALID_TOKEN], "abandoned_rejected", 2),
    ("403_deux_fois", [FORBIDDEN_403, FORBIDDEN_403], "abandoned_rejected", 2),
]


def _setup(tmp_path: Path, fake_n8n: FakeN8n) -> tuple[Path, FakeWall, str, RunnerConfig, Sender]:
    db = tmp_path / "d.db"
    cfg = callback_config(make_config(tmp_path))
    wall = FakeWall()
    job_id = make_terminal(db, cfg, "succeeded", url=fake_n8n.url(), wall=wall)
    wall.advance(2)
    return db, wall, job_id, cfg, make_sender(db, cfg, wall)


def _drive(db: Path, wall: FakeWall, job_id: str, sender: Sender, limit: int = 10) -> None:
    for _ in range(limit):
        assert sender.tick() is True
        if callback_row(db, job_id)["state"] != "pending":
            return
        advance_to_next(wall, db, job_id)
    raise AssertionError("état non final")


def _assert_no_secret(db: Path, job_id: str, caplog: pytest.LogCaptureFixture) -> None:
    for detail in audit_details(db, "callback.attempt"):
        assert set(detail) == {"attempt", "http_status", "error", "decision"}
    text = all_audit_text(db) + str(callback_row(db, job_id)["last_error_redacted"])
    assert SIG not in text
    assert "webhook-waiting" not in text
    for rec in caplog.records:
        if rec.name.startswith("deskgate.sender"):
            message = rec.getMessage()
            assert SIG not in message
            assert "a+b/c" not in message
            assert "webhook-waiting" not in message


@pytest.mark.parametrize(
    ("name", "script", "final", "attempts"), SCENARIOS, ids=[s[0] for s in SCENARIOS]
)
def test_scenario_de_reponse(
    tmp_path: Path,
    fake_n8n: FakeN8n,
    caplog: pytest.LogCaptureFixture,
    name: str,
    script: list[Step],
    final: str,
    attempts: int,
) -> None:
    caplog.set_level(logging.DEBUG, logger="deskgate")
    caplog.set_level(logging.DEBUG, logger="httpx2")
    db, wall, job_id, _cfg, sender = _setup(tmp_path, fake_n8n)
    fake_n8n.script(*script)
    _drive(db, wall, job_id, sender)
    row = callback_row(db, job_id)
    assert row["state"] == final
    assert row["attempts"] == attempts
    assert len(fake_n8n.requests) == attempts
    if final == "delivered":
        assert audit_details(db, "callback.delivered")[-1]["state"] == "delivered"
    _assert_no_secret(db, job_id, caplog)


def test_livraison_directe_audit(tmp_path: Path, fake_n8n: FakeN8n) -> None:
    db, wall, job_id, _cfg, sender = _setup(tmp_path, fake_n8n)
    _drive(db, wall, job_id, sender)
    assert audit_details(db, "callback.delivered") == [{"attempts": 1, "state": "delivered"}]


def test_reessai_court_apres_409_en_cours(tmp_path: Path, fake_n8n: FakeN8n) -> None:
    db, wall, job_id, _cfg, sender = _setup(tmp_path, fake_n8n)
    fake_n8n.script(RUNNING, OK)
    assert sender.tick() is True
    assert (next_attempt(db, job_id) - wall.t).total_seconds() <= 2.5


def test_409_illisible_reste_pending_court(
    tmp_path: Path, fake_n8n: FakeN8n, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="deskgate")
    db, wall, job_id, _cfg, sender = _setup(tmp_path, fake_n8n)
    fake_n8n.script(HTML_409)
    assert sender.tick() is True
    assert callback_row(db, job_id)["state"] == "pending"
    assert (next_attempt(db, job_id) - wall.t).total_seconds() <= 2.5
    _assert_no_secret(db, job_id, caplog)


def test_500_reste_pending(
    tmp_path: Path, fake_n8n: FakeN8n, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="deskgate")
    db, _wall, job_id, _cfg, sender = _setup(tmp_path, fake_n8n)
    fake_n8n.script(SERVER_ERROR)
    assert sender.tick() is True
    assert callback_row(db, job_id)["state"] == "pending"
    _assert_no_secret(db, job_id, caplog)

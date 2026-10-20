"""Sender : envoi de la resumeUrl telle quelle pour chaque statut terminal (CB-01, SEC-05)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from _support.fake_n8n import SIG, FakeN8n, Step
from _support.jobs import make_config
from _support.sender_helpers import (
    FakeWall,
    advance_to_next,
    audit_details,
    callback_config,
    callback_row,
    job_callback_url,
    make_sender,
    make_terminal,
)
from deskgate import store

pytestmark = pytest.mark.fs

KEYS = ["job_id", "capability", "status", "duration_s", "summary", "artifacts", "error"]
RESULT = json.dumps(
    {"summary": {"n": 1}, "data": {"secret": "DATA-XYZ"}, "artifacts": []}, ensure_ascii=False
)


@pytest.mark.parametrize("status", ["succeeded", "failed", "timeout", "cancelled", "interrupted"])
def test_statut_terminal_livre_exactement(tmp_path: Path, fake_n8n: FakeN8n, status: str) -> None:
    db = tmp_path / "d.db"
    cfg = callback_config(make_config(tmp_path))
    wall = FakeWall()
    job_id = make_terminal(
        db,
        cfg,
        status,
        url=fake_n8n.url(),
        wall=wall,
        result_json=RESULT if status == "succeeded" else None,
    )
    sender = make_sender(db, cfg, wall)
    assert sender.tick() is False
    assert fake_n8n.requests == []
    wall.advance(2)
    assert sender.tick() is True
    assert len(fake_n8n.requests) == 1
    req = fake_n8n.requests[0]
    assert req.requestline == f"POST /webhook-waiting/42?signature={SIG} HTTP/1.1"
    assert req.headers["content-type"] == "application/json"
    body = json.loads(req.body)
    assert list(body) == KEYS
    assert body["status"] == status
    assert body["job_id"] == job_id
    if status == "cancelled":
        assert body["duration_s"] is None
    assert "DATA-XYZ" not in req.body.decode("utf-8")
    assert callback_row(db, job_id)["state"] == "delivered"
    assert job_callback_url(db, job_id) == ""
    assert sender.tick() is False


def test_amorcage_de_deux_secondes(tmp_path: Path, fake_n8n: FakeN8n) -> None:
    db = tmp_path / "d.db"
    cfg = callback_config(make_config(tmp_path))
    wall = FakeWall()
    job_id = make_terminal(db, cfg, "succeeded", url=fake_n8n.url(), wall=wall)
    sender = make_sender(db, cfg, wall)
    wall.advance(1.9)
    assert sender.tick() is False
    assert fake_n8n.requests == []
    wall.advance(0.1)
    assert sender.tick() is True
    assert callback_row(db, job_id)["state"] == "delivered"


def test_413_puis_renvoi_minimal(tmp_path: Path, fake_n8n: FakeN8n) -> None:
    db = tmp_path / "d.db"
    cfg = callback_config(make_config(tmp_path))
    wall = FakeWall()
    job_id = make_terminal(db, cfg, "succeeded", url=fake_n8n.url(), wall=wall, result_json=RESULT)
    fake_n8n.script(Step(413, b"{}"))
    sender = make_sender(db, cfg, wall)
    wall.advance(2)
    assert sender.tick() is True
    assert json.loads(fake_n8n.requests[0].body)["summary"] == {"n": 1}
    assert callback_row(db, job_id)["state"] == "pending"
    advance_to_next(wall, db, job_id)
    assert sender.tick() is True
    assert json.loads(fake_n8n.requests[1].body)["summary"] == {"truncated": True}
    assert callback_row(db, job_id)["state"] == "delivered"


def test_hote_reverifie_a_l_envoi(tmp_path: Path, fake_n8n: FakeN8n) -> None:
    db = tmp_path / "d.db"
    cfg = callback_config(make_config(tmp_path))
    wall = FakeWall()
    job_id = make_terminal(db, cfg, "succeeded", url=fake_n8n.url(), wall=wall)
    conn = store.connect(db)
    try:
        conn.execute(
            "UPDATE jobs SET callback_url='http://evil.example/webhook-waiting/42?signature=X' "
            "WHERE id=?",
            (job_id,),
        )
    finally:
        conn.close()
    sender = make_sender(db, cfg, wall)
    wall.advance(2)
    assert sender.tick() is True
    assert fake_n8n.requests == []
    assert callback_row(db, job_id)["state"] == "abandoned_rejected"
    abandoned = audit_details(db, "callback.abandoned")
    assert abandoned[0]["reason"] == "host_not_allowed"


def test_thread_livre_puis_arret_idempotent(tmp_path: Path, fake_n8n: FakeN8n) -> None:
    db = tmp_path / "d.db"
    cfg = callback_config(make_config(tmp_path))
    wall = FakeWall()
    job_id = make_terminal(db, cfg, "succeeded", url=fake_n8n.url(), wall=wall)
    wall.advance(2)
    sender = make_sender(db, cfg, wall)
    sender.start()
    try:
        sender.wake()
        fake_n8n.wait_requests(1)
    finally:
        sender.stop()
        sender.stop()
    assert sender.failed is False
    assert callback_row(db, job_id)["state"] == "delivered"

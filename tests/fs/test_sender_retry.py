"""Sender : réessais durables, plafond, fenêtre, reprise par un nouveau Sender (CB-02)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import httpx2
import pytest

from _support.fake_n8n import DROP, OK, SERVER_ERROR, FakeN8n
from _support.jobs import make_config
from _support.sender_helpers import (
    T0,
    FakeWall,
    advance_to_next,
    audit_details,
    callback_config,
    callback_row,
    make_sender,
    make_terminal,
    next_attempt,
    read_one,
)
from deskgate.core.config import RunnerConfig

pytestmark = pytest.mark.fs


def _setup(
    tmp_path: Path, fake_n8n: FakeN8n, **kw: int
) -> tuple[Path, FakeWall, str, RunnerConfig]:
    db = tmp_path / "d.db"
    cfg = callback_config(make_config(tmp_path), **kw)
    wall = FakeWall()
    job_id = make_terminal(db, cfg, "succeeded", url=fake_n8n.url(), wall=wall)
    wall.advance(2)
    return db, wall, job_id, cfg


def test_delais_croissants_en_echec(tmp_path: Path, fake_n8n: FakeN8n) -> None:
    db, wall, job_id, cfg = _setup(tmp_path, fake_n8n)
    fake_n8n.default = SERVER_ERROR
    sender = make_sender(db, cfg, wall)
    bornes = [(1.5, 2.5), (3.0, 5.0), (6.0, 10.0)]
    for i, (lo, hi) in enumerate(bornes, start=1):
        assert sender.tick() is True
        delay = (next_attempt(db, job_id) - wall.t).total_seconds()
        assert lo <= delay <= hi, (i, delay)
        assert sender.tick() is False  # avant l'échéance
        advance_to_next(wall, db, job_id)
    row = callback_row(db, job_id)
    assert row["state"] == "pending"
    assert row["last_status"] == 500
    # trois essais réellement envoyés ; le 4e est dû mais pas encore tenté
    assert row["attempts"] == 3
    assert len(fake_n8n.requests) == 3


def test_plafond_du_delai(tmp_path: Path, fake_n8n: FakeN8n) -> None:
    db, wall, job_id, cfg = _setup(tmp_path, fake_n8n, max_backoff_s=5)
    fake_n8n.default = SERVER_ERROR
    sender = make_sender(db, cfg, wall)
    for _ in range(6):
        assert sender.tick() is True
        assert (next_attempt(db, job_id) - wall.t).total_seconds() <= 5.0
        advance_to_next(wall, db, job_id)
    assert callback_row(db, job_id)["attempts"] == 6


def test_fenetre_aucun_envoi_apres(tmp_path: Path, fake_n8n: FakeN8n) -> None:
    db, wall, job_id, cfg = _setup(tmp_path, fake_n8n, max_window_s=3600, max_backoff_s=300)
    fake_n8n.default = SERVER_ERROR
    sender = make_sender(db, cfg, wall)
    limit = T0 + timedelta(seconds=3600)
    for _ in range(200):
        if callback_row(db, job_id)["state"] != "pending":
            break
        assert wall.t < limit
        sender.tick()
        if callback_row(db, job_id)["state"] == "pending":
            advance_to_next(wall, db, job_id)
    row = callback_row(db, job_id)
    assert row["state"] == "abandoned_exhausted"
    assert audit_details(db, "callback.abandoned")[0]["reason"] == "exhausted"
    before = len(fake_n8n.requests)
    wall.set(limit)
    assert sender.tick() is False
    wall.set(limit + timedelta(seconds=500))
    assert sender.tick() is False
    assert len(fake_n8n.requests) == before


def test_survie_au_redemarrage(tmp_path: Path, fake_n8n: FakeN8n) -> None:
    db, wall, job_id, cfg = _setup(tmp_path, fake_n8n)
    fake_n8n.default = SERVER_ERROR
    first = make_sender(db, cfg, wall)
    for _ in range(2):
        assert first.tick() is True
        advance_to_next(wall, db, job_id)
    assert callback_row(db, job_id)["attempts"] == 2
    fake_n8n.default = OK
    second = make_sender(db, cfg, wall)
    assert second.tick() is True
    row = callback_row(db, job_id)
    assert row["attempts"] == 3
    assert row["state"] == "delivered"


def test_ecriture_prealable_pendant_la_requete(tmp_path: Path, fake_n8n: FakeN8n) -> None:
    db, wall, job_id, cfg = _setup(tmp_path, fake_n8n)
    seen: list[tuple[int, int]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        row = read_one(db, "SELECT attempts, maybe_delivered FROM callbacks WHERE job_id=?", job_id)
        seen.append((row["attempts"], row["maybe_delivered"]))
        return httpx2.Response(200)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    sender = make_sender(db, cfg, wall, client=client)
    assert sender.tick() is True
    assert seen == [(1, 1)]
    assert callback_row(db, job_id)["state"] == "delivered"


def test_coupure_reseau(tmp_path: Path, fake_n8n: FakeN8n) -> None:
    db, wall, job_id, cfg = _setup(tmp_path, fake_n8n)
    fake_n8n.default = DROP
    sender = make_sender(db, cfg, wall)
    assert sender.tick() is True
    row = callback_row(db, job_id)
    assert row["last_error_redacted"] == "RemoteProtocolError"
    assert row["maybe_delivered"] == 1
    assert row["state"] == "pending"

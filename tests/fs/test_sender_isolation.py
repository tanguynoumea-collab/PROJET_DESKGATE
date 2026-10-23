"""Sender : une erreur propre à un rappel n'arrête ni les autres ni le thread (DS-ARCH-2)."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import httpx2
import pytest

from _support.fake_n8n import SIG, FakeN8n
from _support.jobs import make_config
from _support.sender_helpers import (
    FakeWall,
    all_audit_text,
    audit_details,
    callback_config,
    callback_row,
    make_sender,
    make_terminal,
    next_attempt,
)
from deskgate import store
from deskgate.core.config import RunnerConfig
from deskgate.sender import Sender

pytestmark = pytest.mark.fs

GOOD = '{"summary":{"n":2},"data":{},"artifacts":[]}'


def _deux(
    tmp_path: Path, fake_n8n: FakeN8n, *, first_result_json: str = "{", **kw: int
) -> tuple[Path, RunnerConfig, FakeWall, str, str]:
    db = tmp_path / "d.db"
    cfg = callback_config(make_config(tmp_path), **kw)
    wall = FakeWall()
    j1 = make_terminal(
        db, cfg, "succeeded", url=fake_n8n.url("1"), wall=wall, result_json=first_result_json
    )
    j2 = make_terminal(db, cfg, "succeeded", url=fake_n8n.url("2"), wall=wall, result_json=GOOD)
    wall.advance(2)
    return db, cfg, wall, j1, j2


class _Boum(httpx2.Client):
    def stream(self, method: str, url: Any, **kw: Any) -> Any:  # type: ignore[override]
        raise RuntimeError(f"boum {url}")


def test_ligne_empoisonnee_n_arrete_pas_les_autres(tmp_path: Path, fake_n8n: FakeN8n) -> None:
    db, cfg, wall, j1, j2 = _deux(tmp_path, fake_n8n)
    sender = make_sender(db, cfg, wall)
    assert sender.tick() is True
    row = callback_row(db, j1)
    assert row["state"] == "pending"
    assert row["last_error_redacted"] == "JSONDecodeError"
    assert row["attempts"] == 1
    assert next_attempt(db, j1) > wall.t
    attempts = audit_details(db, "callback.attempt")
    assert attempts[0]["decision"] == "internal_error"
    assert attempts[0]["http_status"] is None
    assert sender.tick() is True
    assert callback_row(db, j2)["state"].startswith("delivered")
    assert len(fake_n8n.requests) == 1
    assert sender.failed is False


def test_client_qui_leve_isole_la_ligne(tmp_path: Path, fake_n8n: FakeN8n) -> None:
    db, cfg, wall, j1, _ = _deux(tmp_path, fake_n8n, first_result_json=GOOD)
    client = _Boum()
    try:
        sender = make_sender(db, cfg, wall, client=client)
        assert sender.tick() is True
    finally:
        client.close()
    row = callback_row(db, j1)
    assert row["last_error_redacted"] == "RuntimeError"
    assert row["state"] == "pending"
    text = all_audit_text(db) + str(row["last_error_redacted"])
    assert "signature=" not in text
    assert SIG not in text
    assert fake_n8n.url("1") not in text


def test_erreur_de_base_propagee(
    tmp_path: Path, fake_n8n: FakeN8n, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, cfg, wall, _, _ = _deux(tmp_path, fake_n8n, first_result_json=GOOD)

    def fake(*a: object, **k: object) -> None:
        raise store.OperationalError("database is locked")

    monkeypatch.setattr(store, "record_callback_result", fake)
    sender = make_sender(db, cfg, wall)
    try:
        with pytest.raises(store.OperationalError):
            sender.tick()
    finally:
        sender._drop_connection()
        sender._client.close()


def test_stale_transition_propagee(
    tmp_path: Path, fake_n8n: FakeN8n, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, cfg, wall, j1, _ = _deux(tmp_path, fake_n8n, first_result_json=GOOD)

    def fake(*a: object, **k: object) -> None:
        raise store.StaleTransition(j1)

    monkeypatch.setattr(store, "record_callback_result", fake)
    sender = make_sender(db, cfg, wall)
    try:
        with pytest.raises(store.StaleTransition):
            sender.tick()
    finally:
        sender._drop_connection()
        sender._client.close()
    assert audit_details(db, "callback.attempt") == []


def test_ligne_empoisonnee_abandonnee_hors_fenetre(tmp_path: Path, fake_n8n: FakeN8n) -> None:
    db, cfg, wall, j1, _ = _deux(tmp_path, fake_n8n, max_window_s=60)
    wall.advance(57)  # 59 s sur 60 : le délai d'essai dépasse la fenêtre
    sender = make_sender(db, cfg, wall)
    assert sender.tick() is True
    assert callback_row(db, j1)["state"] == "abandoned_exhausted"


def test_run_ne_passe_pas_failed(tmp_path: Path, fake_n8n: FakeN8n) -> None:
    db, cfg, wall, _, _ = _deux(tmp_path, fake_n8n)
    sender = Sender(
        db_path=db,
        config=cfg,
        wall=wall,
        rng=random.Random(0),  # noqa: S311
        poll=0.05,
    )
    sender.start()
    try:
        fake_n8n.wait_requests(1)
    finally:
        sender.stop()
    assert sender.failed is False

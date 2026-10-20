"""SEC-06 : chaque refus de soumission est audité, sans jamais contenir l'URL de rappel."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from _support.jobs import make_config
from deskgate import store
from deskgate.api import create_app
from deskgate.core.tokens import hash_token
from deskgate.jobs import JobsService

pytestmark = pytest.mark.fs

TOKEN = "jeton-de-test-secret-0123456789"  # noqa: S105
AUTH = {"Authorization": f"Bearer {TOKEN}"}
URL = "http://localhost:5678/webhook-waiting/1?signature=SECRET-SIG"


class Env:
    def __init__(self, tmp_path: Path) -> None:
        self.db = tmp_path / "d.db"
        store.open_db(self.db).close()
        cfg = make_config(tmp_path)
        service = JobsService(db_path=self.db, config=cfg)
        app = create_app(token_sha256=hash_token(TOKEN), version="x", jobs=service)
        self.client = TestClient(app, base_url="http://127.0.0.1:8765")

    def post(self, **kw: object) -> int:
        body: dict[str, object] = {"capability": "demo.sleep", "callback": {"url": URL}}
        body.update(kw)
        return self.client.post("/jobs", json=body, headers=AUTH).status_code

    def audit(self, event: str) -> list[dict[str, object]]:
        conn = store.connect(self.db)
        try:
            rows = conn.execute(
                "SELECT detail_json FROM audit WHERE event=? ORDER BY id", (event,)
            ).fetchall()
        finally:
            conn.close()
        return [json.loads(r[0]) for r in rows]

    def all_audit_text(self) -> str:
        conn = store.connect(self.db)
        try:
            return " ".join(r[0] for r in conn.execute("SELECT detail_json FROM audit"))
        finally:
            conn.close()


def test_refus_audites_avec_code(tmp_path: Path) -> None:
    env = Env(tmp_path)
    assert env.post(capability="demo.inconnue") == 404
    assert env.post(timeout=999999) == 422
    assert (
        env.post(callback={"url": "http://evil.example/webhook-waiting/1?signature=SECRET-SIG"})
        == 422
    )
    assert env.post(idempotency_key="k") == 202
    assert env.post(idempotency_key="k") == 409
    resp = env.client.post("/jobs", json={"capability": "demo.sleep"}, headers=AUTH)
    assert resp.status_code == 422
    codes = [d["code"] for d in env.audit("job.refused")]
    assert codes == [
        "capability_not_found",
        "timeout_too_large",
        "callback_host_not_allowed",
        "idempotency_conflict",
        "invalid_request",
    ]
    submitted = env.audit("job.submitted")
    assert len(submitted) == 1
    assert submitted[0]["client"] == "bearer"
    assert "timeout_s" in submitted[0]
    text = env.all_audit_text()
    assert "SECRET-SIG" not in text
    assert "webhook-waiting" not in text


def test_conflit_porte_le_job_id(tmp_path: Path) -> None:
    env = Env(tmp_path)
    assert env.post(idempotency_key="k") == 202
    conn = store.connect(env.db)
    try:
        first = conn.execute("SELECT id FROM jobs").fetchone()[0]
    finally:
        conn.close()
    assert env.post(idempotency_key="k") == 409
    conn = store.connect(env.db)
    try:
        row = conn.execute("SELECT job_id FROM audit WHERE event='job.refused'").fetchone()
    finally:
        conn.close()
    assert row[0] == first

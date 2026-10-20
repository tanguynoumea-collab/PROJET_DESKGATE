"""Service et routes /jobs sur une vraie base SQLite (TestClient, sans engine)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from _support.jobs import make_config
from deskgate import store
from deskgate.api import create_app
from deskgate.core.jobspec import JobRequestError, SubmitRequest
from deskgate.core.tokens import hash_token
from deskgate.jobs import JobsService, job_view

pytestmark = pytest.mark.fs

TOKEN = "jeton-de-test-secret-0123456789"  # noqa: S105
AUTH = {"Authorization": f"Bearer {TOKEN}"}
URL = "http://n8n:5678/webhook-waiting/1?signature=SECRET-SIG"
BASE = "http://127.0.0.1:8765"


class Env:
    def __init__(self, tmp_path: Path) -> None:
        self.db = tmp_path / "d.db"
        store.open_db(self.db).close()
        self.cfg = make_config(tmp_path)
        self.wakes = 0
        self.service = JobsService(db_path=self.db, config=self.cfg, wake=self._wake)

    def _wake(self) -> None:
        self.wakes += 1

    def req(self, **kw: object) -> SubmitRequest:
        data: dict[str, object] = {"capability": "demo.sleep", "callback": {"url": URL}}
        data.update(kw)
        return SubmitRequest.model_validate(data)


@pytest.fixture
def env(tmp_path: Path) -> Env:
    return Env(tmp_path)


@pytest.fixture
def client(env: Env) -> TestClient:
    app = create_app(token_sha256=hash_token(TOKEN), version="x", jobs=env.service)
    return TestClient(app, base_url=BASE)


def _write_log(env: Env, job_id: str, text: str) -> None:
    log_dir = Path(env.cfg.effective_work_root()) / job_id
    log_dir.mkdir(parents=True)
    (log_dir / "job.log").write_text(text, encoding="utf-8")


def _row(env: Env, job_id: str) -> store.JobRow:
    conn = store.connect(env.db)
    try:
        row = store.get_job(conn, job_id)
    finally:
        conn.close()
    assert row is not None
    return row


def test_submit_insere_queued_et_reveille(env: Env) -> None:
    job_id = env.service.submit(env.req())
    row = _row(env, job_id)
    assert len(job_id) == 12
    assert row.status == "queued"
    assert row.timeout_s == 600
    assert row.resource == "default"
    assert row.work_dir == f"{env.cfg.effective_work_root()}/{job_id}"
    assert env.wakes == 1


def test_submit_refus(env: Env) -> None:
    with pytest.raises(JobRequestError) as e1:
        env.service.submit(env.req(capability="inconnue"))
    assert (e1.value.code, e1.value.status) == ("capability_not_found", 404)
    with pytest.raises(JobRequestError) as e2:
        env.service.submit(env.req(timeout=601))
    assert (e2.value.code, e2.value.status) == ("timeout_too_large", 422)
    assert env.wakes == 0


def test_submit_conflit_idempotence(env: Env) -> None:
    first = env.service.submit(env.req(idempotency_key="k"))
    with pytest.raises(JobRequestError) as exc:
        env.service.submit(env.req(idempotency_key="k"))
    assert exc.value.status == 409
    assert exc.value.extra == {"job_id": first}


def test_job_view_forme_et_secret(env: Env) -> None:
    job_id = env.service.submit(env.req(params={"p": 1}))
    view = job_view(_row(env, job_id))
    assert set(view) == {
        "job_id",
        "capability",
        "status",
        "cancel_requested",
        "progress",
        "summary",
        "artifacts",
        "error",
        "created_at",
        "started_at",
        "finished_at",
        "duration_s",
    }
    assert view["progress"] is None
    assert view["error"] is None
    assert view["duration_s"] is None
    dumped = json.dumps(view)
    for forbidden in ("SECRET-SIG", "signature", "params", "travail"):
        assert forbidden not in dumped


def test_logs_service(env: Env) -> None:
    job_id = env.service.submit(env.req())
    empty = env.service.read_logs(job_id)
    assert empty == {"text": "", "offset": 0, "next_offset": 0, "size": 0, "complete": False}
    _write_log(env, job_id, "0123456789 signature=abc fin")
    part = env.service.read_logs(job_id, offset=2, limit=4)
    assert part is not None
    assert part["text"] == "2345"
    assert part["next_offset"] == 6
    assert part["complete"] is False
    tail = env.service.read_logs(job_id, tail=3)
    assert tail is not None
    assert tail["text"] == "fin"
    full = env.service.read_logs(job_id)
    assert full is not None
    assert "signature=***" in full["text"]
    assert "abc" not in full["text"]
    assert full["complete"] is False  # tâche non terminale


def test_logs_complete_sur_terminale(env: Env) -> None:
    job_id = env.service.submit(env.req())
    _write_log(env, job_id, "abc")
    env.service.cancel(job_id)
    res = env.service.read_logs(job_id)
    assert res is not None
    assert res["complete"] is True


def test_id_malforme_donne_none(env: Env) -> None:
    assert env.service.get("../x") is None
    assert env.service.cancel("zzz") is None
    assert env.service.read_logs("zzz") is None


def test_post_sans_jeton(client: TestClient) -> None:
    assert client.post("/jobs", json={}).status_code == 401


def test_post_202_et_get(client: TestClient) -> None:
    r = client.post(
        "/jobs", json={"capability": "demo.sleep", "callback": {"url": URL}}, headers=AUTH
    )
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "queued"
    got = client.get(f"/jobs/{body['job_id']}", headers=AUTH)
    assert got.status_code == 200
    assert got.json()["status"] == "queued"
    assert "SECRET-SIG" not in got.text
    assert "n8n:5678" not in got.text


_CB = {"url": URL}


@pytest.mark.parametrize(
    ("payload", "status", "code"),
    [
        ({"capability": "demo.sleep"}, 422, "invalid_request"),
        (
            {"capability": "demo.sleep", "callback": {"url": URL, "headers": {"a": "b"}}},
            422,
            "invalid_request",
        ),
        ({"capability": "nope", "callback": _CB}, 404, "capability_not_found"),
        ({"capability": "demo.sleep", "callback": _CB, "timeout": 601}, 422, "timeout_too_large"),
    ],
)
def test_post_erreurs(
    client: TestClient, payload: dict[str, object], status: int, code: str
) -> None:
    r = client.post("/jobs", json=payload, headers=AUTH)
    assert r.status_code == status
    assert r.json()["error"]["code"] == code
    assert "SECRET-SIG" not in r.text


def test_post_idempotence_409(client: TestClient) -> None:
    payload = {"capability": "demo.sleep", "callback": _CB, "idempotency_key": "k"}
    first = client.post("/jobs", json=payload, headers=AUTH)
    second = client.post("/jobs", json=payload, headers=AUTH)
    assert second.status_code == 409
    err = second.json()["error"]
    assert err["code"] == "idempotency_conflict"
    assert err["job_id"] == first.json()["job_id"]


def test_get_inconnu_404(client: TestClient) -> None:
    r = client.get("/jobs/zzz", headers=AUTH)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "job_not_found"


def test_logs_route(client: TestClient, env: Env) -> None:
    job_id = env.service.submit(env.req())
    _write_log(env, job_id, "0123456789")
    r = client.get(f"/jobs/{job_id}/logs?offset=0&limit=10", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["text"] == "0123456789"
    assert client.get(f"/jobs/{job_id}/logs?offset=1&tail=2", headers=AUTH).status_code == 422
    assert client.get(f"/jobs/{job_id}/logs?limit=2000000", headers=AUTH).status_code == 422


def test_cancel_idempotent(client: TestClient, env: Env) -> None:
    job_id = env.service.submit(env.req())
    one = client.post(f"/jobs/{job_id}/cancel", headers=AUTH)
    two = client.post(f"/jobs/{job_id}/cancel", headers=AUTH)
    assert one.status_code == two.status_code == 200
    assert one.json()["status"] == "cancelled"
    assert one.json() == two.json()
    assert client.post("/jobs/unknown/cancel", headers=AUTH).status_code == 404


def test_sans_jobs_pas_de_route() -> None:
    app = create_app(token_sha256=hash_token(TOKEN), version="x")
    c = TestClient(app, base_url=BASE)
    assert c.get("/jobs/abc", headers=AUTH).status_code == 404


def test_on_shutdown_appele_une_fois() -> None:
    calls: list[int] = []
    app = create_app(
        token_sha256=hash_token(TOKEN), version="x", on_shutdown=lambda: calls.append(1)
    )
    with TestClient(app, base_url=BASE):
        assert calls == []
    assert calls == [1]

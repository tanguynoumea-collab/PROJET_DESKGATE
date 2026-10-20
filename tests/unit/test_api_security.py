"""Sécurité de l'API : Host avant jeton, jeton sur toute route sauf /health, erreurs D-08."""

from __future__ import annotations

import logging

import httpx2
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from deskgate.api import create_app
from deskgate.core.tokens import hash_token

pytestmark = pytest.mark.unit

TOKEN = "jeton-de-test-secret-0123456789"  # noqa: S105
VERSION = "0.1.0.dev0"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class Echo(BaseModel):
    n: int


def _build(warnings: tuple[str, ...] = ()) -> TestClient:
    app = create_app(token_sha256=hash_token(TOKEN), version=VERSION, warnings=warnings)

    def echo(body: Echo) -> dict[str, int]:
        return {"n": body.n}

    def boom() -> None:
        raise RuntimeError("boom")

    app.add_api_route("/_test/echo", echo, methods=["POST"])
    app.add_api_route("/_test/boom", boom, methods=["GET"])
    return TestClient(app, base_url="http://127.0.0.1:8765", raise_server_exceptions=False)


@pytest.fixture
def client() -> TestClient:
    return _build()


def _assert_erreur(r: httpx2.Response, status: int, code: str) -> None:
    assert r.status_code == status
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == code


def test_health_sans_jeton(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": VERSION, "warnings": []}


def test_health_porte_les_avertissements() -> None:
    r = _build(("listen_non_loopback",)).get("/health")
    assert r.json()["warnings"] == ["listen_non_loopback"]


def test_health_host_hostile(client: TestClient) -> None:
    _assert_erreur(client.get("/health", headers={"host": "evil.com"}), 400, "host_not_allowed")


def test_route_sans_jeton(client: TestClient) -> None:
    r = client.get("/jobs")
    _assert_erreur(r, 401, "unauthorized")
    assert r.headers["www-authenticate"] == "Bearer"


def test_mauvais_jeton(client: TestClient) -> None:
    r = client.get("/jobs", headers={"Authorization": "Bearer faux"})
    _assert_erreur(r, 401, "unauthorized")


def test_schema_autre_que_bearer(client: TestClient) -> None:
    r = client.get("/jobs", headers={"Authorization": f"Basic {TOKEN}"})
    _assert_erreur(r, 401, "unauthorized")


def test_schema_bearer_insensible_a_la_casse(client: TestClient) -> None:
    r = client.get("/jobs", headers={"Authorization": f"bearer {TOKEN}"})
    _assert_erreur(r, 404, "http_404")


def test_host_verifie_avant_auth(client: TestClient) -> None:
    _assert_erreur(client.get("/jobs", headers={"host": "evil.com"}), 400, "host_not_allowed")


@pytest.mark.parametrize("host", ["host.docker.internal:8765", "LocalHost"])
def test_hotes_autorises_passent(client: TestClient, host: str) -> None:
    r = client.get("/jobs", headers={**AUTH, "host": host})
    _assert_erreur(r, 404, "http_404")


def test_validation_422_en_francais(client: TestClient) -> None:
    r = client.post("/_test/echo", json={"n": "valeur-fautive"}, headers=AUTH)
    _assert_erreur(r, 422, "invalid_request")
    message = r.json()["error"]["message"]
    assert "body.n" in message
    assert "entier attendu" in message
    assert "valeur-fautive" not in message


def test_erreur_500_sans_trace(client: TestClient) -> None:
    r = client.get("/_test/boom", headers=AUTH)
    _assert_erreur(r, 500, "internal_error")
    assert "boom" not in r.text
    assert "Traceback" not in r.text


def test_methode_non_autorisee(client: TestClient) -> None:
    _assert_erreur(client.post("/health"), 405, "http_405")


def test_health_slash_final_protege(client: TestClient) -> None:
    _assert_erreur(client.get("/health/"), 401, "unauthorized")


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_documentation_desactivee(client: TestClient, path: str) -> None:
    _assert_erreur(client.get(path, headers=AUTH), 404, "http_404")


def test_jeton_absent_des_journaux(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    client.get("/jobs", headers=AUTH)
    client.get("/_test/boom", headers=AUTH)
    assert TOKEN not in caplog.text

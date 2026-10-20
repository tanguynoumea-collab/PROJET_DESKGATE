"""Faux n8n : contrat 2.43.8 et préservation de la query par httpx2 (D-05)."""

from __future__ import annotations

import httpx2
import pytest

from _support.fake_n8n import FINISHED, RUNNING, SIG, FakeN8n

pytestmark = pytest.mark.fs

JSON = {"Content-Type": "application/json"}


def test_query_brute_preservee(fake_n8n: FakeN8n) -> None:
    with httpx2.Client(trust_env=False) as client:
        r = client.post(fake_n8n.url(), content=b"{}", headers=JSON)
    assert r.status_code == 200
    assert fake_n8n.requests[0].requestline == (
        f"POST /webhook-waiting/42?signature={SIG} HTTP/1.1"
    )


def test_script_puis_defaut(fake_n8n: FakeN8n) -> None:
    fake_n8n.script(RUNNING, FINISHED)
    with httpx2.Client(trust_env=False) as client:
        reponses = [client.post(fake_n8n.url(), content=b"{}", headers=JSON) for _ in range(3)]
    assert [r.status_code for r in reponses] == [409, 409, 200]
    assert reponses[1].json()["message"] == 'The execution "42 has finished already.'


def test_invalid_token(fake_n8n: FakeN8n) -> None:
    from _support.fake_n8n import INVALID_TOKEN

    fake_n8n.script(INVALID_TOKEN)
    with httpx2.Client(trust_env=False) as client:
        r = client.post(fake_n8n.url(), content=b"{}", headers=JSON)
    assert r.status_code == 401
    assert r.headers["content-type"] == "application/json; charset=utf-8"
    assert r.content == b'{"error":"Invalid token"}'


def test_coupure(fake_n8n: FakeN8n) -> None:
    from _support.fake_n8n import DROP

    fake_n8n.script(DROP)
    with httpx2.Client(trust_env=False) as client, pytest.raises(httpx2.RemoteProtocolError):
        client.post(fake_n8n.url(), content=b"{}", headers=JSON)
    assert len(fake_n8n.wait_requests(1)) == 1

"""Tests du corps du rappel (core/payload)."""

from __future__ import annotations

import json

import pytest

from deskgate.core.payload import (
    CALLBACK_MAX_BYTES,
    build_callback,
    duration_s,
    encode,
    minimal,
    result_parts,
)

pytestmark = pytest.mark.unit

CLES = ["job_id", "capability", "status", "duration_s", "summary", "data", "artifacts", "error"]
DEBUT = "2026-10-20T12:00:00.000Z"
FIN = "2026-10-20T12:00:01.234Z"
RESULTAT = (
    '{"summary":{"n":1},"data":{"valeur":"D"},"artifacts":[{"kind":"file","path":"/data/x.txt"}]}'
)


def _corps(status: str = "succeeded", **kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "job_id": "j1",
        "capability": "demo.run",
        "status": status,
        "started_at": DEBUT,
        "finished_at": FIN,
        "result_json": None,
        "error_code": None,
        "error_message": None,
    }
    base.update(kw)
    return build_callback(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize("status", ["succeeded", "failed", "timeout", "cancelled", "interrupted"])
def test_cles_exactes_pour_les_cinq_statuts(status: str) -> None:
    assert list(_corps(status)) == CLES


def test_succes_avec_data() -> None:
    body = _corps(result_json=RESULTAT)
    assert body["summary"] == {"n": 1}
    assert body["data"] == {"valeur": "D"}
    assert body["artifacts"] == [{"kind": "file", "path": "/data/x.txt"}]
    assert body["error"] is None
    assert b'"D"' in encode(body)


def test_echec() -> None:
    body = _corps("failed", error_code="plugin_error", error_message="boum")
    assert body["summary"] == {}
    assert body["data"] == {}
    assert body["artifacts"] == []
    assert body["error"] == {"code": "plugin_error", "message": "boum"}


def test_duree() -> None:
    assert duration_s(DEBUT, FIN) == 1.234
    assert duration_s(None, FIN) is None
    assert duration_s(DEBUT, None) is None
    assert _corps("cancelled", started_at=None)["duration_s"] is None


def test_marqueur_de_debordement_transmis() -> None:
    marqueur = {"path": "/data/travail/abc/summary.json", "truncated": True}
    result = json.dumps({"summary": marqueur, "data": {}, "artifacts": []})
    assert _corps(result_json=result)["summary"] == marqueur


def test_encode_compact_utf8() -> None:
    raw = encode(_corps(result_json='{"summary":{"m":"é"}}'))
    assert b'"job_id":"' in raw
    assert b'": "' not in raw
    assert "é".encode() in raw


def test_plafond_defensif() -> None:
    result = json.dumps({"summary": {"x": "a" * 5000}})
    body = _corps(result_json=result, max_bytes=1000)
    assert body["summary"] == {"truncated": True}
    assert len(encode(body)) <= 1000
    assert _corps(result_json=result, max_bytes=None)["summary"] == {"x": "a" * 5000}


def test_plafond_defensif_data() -> None:
    result = json.dumps({"summary": {}, "data": {"x": "a" * 2_000_000}})
    body = _corps(result_json=result)
    assert body["data"] == {"truncated": True}
    assert len(encode(body)) <= CALLBACK_MAX_BYTES


def test_result_parts() -> None:
    assert result_parts(None) == ({}, {}, [])
    assert result_parts('{"summary":{"a":1}}') == ({"a": 1}, {}, [])


def test_plafond_par_defaut() -> None:
    assert CALLBACK_MAX_BYTES == 1_048_576


def test_minimal_copie() -> None:
    body = _corps(result_json=RESULTAT)
    petit = minimal(body)
    assert body["summary"] == {"n": 1}
    assert petit["summary"] == {"truncated": True}
    assert petit["data"] == {"truncated": True}
    assert body["data"] == {"valeur": "D"}
    assert {k: v for k, v in petit.items() if k not in ("summary", "data")} == {
        k: v for k, v in body.items() if k not in ("summary", "data")
    }


def test_encode_refuse_non_fini() -> None:
    with pytest.raises(ValueError):
        encode({"summary": {"d": float("nan")}})
    with pytest.raises(ValueError):
        encode({"x": float("inf")})

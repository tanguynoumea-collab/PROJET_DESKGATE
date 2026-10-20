"""Contrat de fichiers runner <-> worker."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from deskgate.core.worker_protocol import (
    CONTRACT,
    RESULT_MAX_BYTES,
    ArtifactEvent,
    ProgressEvent,
    ResultError,
    ResultOk,
    WorkerInput,
    parse_event,
    parse_result,
)

pytestmark = pytest.mark.unit


def test_progress_event() -> None:
    ev = parse_event(b'{"type":"progress","pct":40,"message":"x"}')
    assert ev == ProgressEvent(type="progress", pct=40.0, message="x")


@pytest.mark.parametrize(
    "line",
    [
        b'{"type":"progress","pct":140}',
        b'{"type":"progress","pct":-1}',
        b"pas du json",
        b'{"type":"inconnu"}',
        b"[1]",
        b"",
    ],
)
def test_event_rejected(line: bytes) -> None:
    assert parse_event(line) is None


def test_artifact_event() -> None:
    ev = parse_event(b'{"type":"artifact","kind":"txt","path":"C:/BIM/a.txt"}')
    assert ev == ArtifactEvent(type="artifact", kind="txt", path="C:/BIM/a.txt")


def test_result_ok_defaults() -> None:
    state, res = parse_result(b'{"protocol":1,"ok":true,"summary":{"n":1}}')
    assert state == "valid"
    assert isinstance(res, ResultOk)
    assert res.summary == {"n": 1}
    assert res.data == {}
    assert res.artifacts == []


def test_result_error() -> None:
    raw = b'{"protocol":1,"ok":false,"error":{"type":"ValueError","message":"m"}}'
    state, res = parse_result(raw)
    assert state == "plugin_error"
    assert isinstance(res, ResultError)
    assert res.error.message == "m"


def test_result_missing_too_large_invalid() -> None:
    assert parse_result(None) == ("missing", None)
    assert parse_result(b"x" * (RESULT_MAX_BYTES + 1)) == ("too_large", None)
    assert parse_result(b"{") == ("invalid", None)
    assert parse_result(b'{"protocol":2,"ok":true}') == ("invalid", None)
    assert parse_result(b'{"protocol":1,"ok":true,"extra":1}') == ("invalid", None)


def test_worker_input_forbids_unknown_key() -> None:
    base = {
        "protocol": 1,
        "job_id": "a",
        "capability": "c",
        "entry": "m:f",
        "params": {},
        "work_dir": "w",
        "sys_path": [],
    }
    WorkerInput.model_validate(base)
    with pytest.raises(ValidationError):
        WorkerInput.model_validate({**base, "autre": 1})


def test_contract() -> None:
    assert CONTRACT["protocol"] == 1
    assert CONTRACT["input_keys"] == sorted(CONTRACT["input_keys"])
    assert CONTRACT["event_types"] == ["artifact", "progress"]
    assert CONTRACT["files"]["cancel"] == "cancel.flag"
    assert CONTRACT["result_ok_keys"] == ["artifacts", "data", "ok", "protocol", "summary"]
    assert CONTRACT["result_error_keys"] == ["error", "ok", "protocol"]

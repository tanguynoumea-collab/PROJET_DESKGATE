"""Contrat de soumission : validation stricte, délai effectif, identifiant."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from deskgate.core.errors import error_body
from deskgate.core.jobspec import (
    JobRequestError,
    SubmitRequest,
    is_valid_job_id,
    new_job_id,
    resolve_timeout,
    work_dir_for,
)

pytestmark = pytest.mark.unit

URL = "http://localhost:5678/webhook-waiting/1?signature=abc"


def _body(**over: Any) -> dict[str, Any]:
    return {"capability": "demo.sleep", "callback": {"url": URL}, **over}


def test_minimal_request() -> None:
    req = SubmitRequest.model_validate(_body())
    assert req.params == {}
    assert req.idempotency_key is None
    assert req.timeout is None
    assert req.callback.url == URL


def test_callback_required() -> None:
    with pytest.raises(ValidationError):
        SubmitRequest.model_validate({"capability": "demo.sleep"})


@pytest.mark.parametrize("url", ["ftp://x", "http://h/" + "a" * 2048])
def test_callback_url_invalid(url: str) -> None:
    with pytest.raises(ValidationError):
        SubmitRequest.model_validate(_body(callback={"url": url}))


def test_callback_headers_refused() -> None:
    with pytest.raises(ValidationError):
        SubmitRequest.model_validate(_body(callback={"url": URL, "headers": {"X": "y"}}))


@pytest.mark.parametrize(
    "over",
    [
        {"bogus": 1},
        {"params": [1]},
        {"timeout": 0},
        {"idempotency_key": ""},
        {"idempotency_key": "k" * 129},
    ],
)
def test_invalid_fields(over: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SubmitRequest.model_validate(_body(**over))


def test_validation_error_does_not_leak_url() -> None:
    with pytest.raises(ValidationError) as info:
        SubmitRequest.model_validate(_body(callback={"url": URL, "headers": {}}))
    assert "signature=abc" not in str(info.value.errors(include_input=False))


def test_resolve_timeout() -> None:
    assert resolve_timeout(None, 600) == 600
    assert resolve_timeout(None, 43200) == 7200
    assert resolve_timeout(1800, 3600) == 1800
    with pytest.raises(JobRequestError) as info:
        resolve_timeout(3601, 3600)
    assert info.value.code == "timeout_too_large"
    assert info.value.status == 422


def test_job_id() -> None:
    jid = new_job_id()
    assert len(jid) == 12
    assert is_valid_job_id(jid)
    assert not is_valid_job_id("ABCDEF123456")
    assert not is_valid_job_id("../../etc")


def test_work_dir_for() -> None:
    assert work_dir_for("C:/BIM/travail", "a1b2c3d4e5f6") == "C:/BIM/travail/a1b2c3d4e5f6"
    with pytest.raises(ValueError, match="invalide"):
        work_dir_for("C:/BIM/travail", "../x")


def test_error_body_extra() -> None:
    body = error_body("idempotency_conflict", "m", job_id="a1b2c3d4e5f6")
    assert body["error"]["job_id"] == "a1b2c3d4e5f6"
    assert set(error_body("c", "m")["error"]) == {"code", "message"}

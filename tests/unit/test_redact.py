"""Tests du masquage de la signature n8n."""

from __future__ import annotations

import logging
import sys

import pytest

from deskgate.core.errors import error_body, http_code
from deskgate.core.redact import (
    RedactingFilter,
    RedactingFormatter,
    redact_params,
    redact_signature,
)

pytestmark = pytest.mark.unit


def test_signature_masquee() -> None:
    src = "https://n/webhook-waiting/1?signature=abc123&x=1"
    assert redact_signature(src) == "https://n/webhook-waiting/1?signature=***&x=1"


def test_signature_majuscules_masquee() -> None:
    assert redact_signature("SIGNATURE=abc") == "SIGNATURE=***"


def test_texte_sans_signature_inchange() -> None:
    assert redact_signature("rien à masquer ?x=1") == "rien à masquer ?x=1"


def test_signature_url_encodee() -> None:
    out = redact_signature("u=http%3A%2F%2Fh%2Fw%3Fsignature%3DSEC2%26x")
    assert "SEC2" not in out
    assert "signature%3D***" in out


@pytest.mark.parametrize("src", ['{"signature": "SEC5", "a": 1}', '{"signature":"SEC5","a":1}'])
def test_signature_json(src: str) -> None:
    out = redact_signature(src)
    assert "SEC5" not in out
    assert '"signature"' in out
    assert "***" in out


def test_redact_params() -> None:
    entree = {
        "secret_param": "PARAMVAL",
        "api_key": "K",
        "Authorization": "Bearer t",
        "nested": {"token": "T"},
        "list": ["http://h/w?signature=S6"],
        "n": 3,
    }
    out = redact_params(entree)
    assert out["secret_param"] == out["api_key"] == out["Authorization"] == "***"  # noqa: S105
    assert out["nested"] == {"token": "***"}
    assert "S6" not in str(out)
    assert out["n"] == 3
    assert entree["secret_param"] == "PARAMVAL"  # noqa: S105
    assert entree["list"] == ["http://h/w?signature=S6"]


def _record(secret: str, exc: bool = False) -> logging.LogRecord:
    exc_info = None
    if exc:
        try:
            raise RuntimeError(f"échec signature={secret}")
        except RuntimeError:
            exc_info = sys.exc_info()
    return logging.LogRecord(
        "t", logging.ERROR, __file__, 1, "appel %s", (f"http://h/w?signature={secret}",), exc_info
    )


def test_formatter_masque_message_et_traceback() -> None:
    out = RedactingFormatter("%(message)s").format(_record("SEC3", exc=True))
    assert "SEC3" not in out
    assert "signature=***" in out
    assert "Traceback" in out


def test_filter_masque_et_vide_les_args() -> None:
    rec = _record("SEC4")
    assert RedactingFilter().filter(rec) is True
    assert "SEC4" not in rec.getMessage()
    assert rec.args is None


def test_error_body_et_http_code() -> None:
    assert error_body("unauthorized", "x") == {"error": {"code": "unauthorized", "message": "x"}}
    assert http_code(404) == "http_404"

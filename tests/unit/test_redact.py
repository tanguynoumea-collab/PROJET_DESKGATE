"""Tests du masquage de la signature n8n."""

from __future__ import annotations

import pytest

from deskgate.core.errors import error_body, http_code
from deskgate.core.redact import redact_signature

pytestmark = pytest.mark.unit


def test_signature_masquee() -> None:
    src = "https://n/webhook-waiting/1?signature=abc123&x=1"
    assert redact_signature(src) == "https://n/webhook-waiting/1?signature=***&x=1"


def test_signature_majuscules_masquee() -> None:
    assert redact_signature("SIGNATURE=abc") == "SIGNATURE=***"


def test_texte_sans_signature_inchange() -> None:
    assert redact_signature("rien à masquer ?x=1") == "rien à masquer ?x=1"


def test_error_body_et_http_code() -> None:
    assert error_body("unauthorized", "x") == {"error": {"code": "unauthorized", "message": "x"}}
    assert http_code(404) == "http_404"

"""Contrôle de l'URL de rappel : hôtes exacts, évasions refusées, aucune fuite de l'URL."""

from __future__ import annotations

import pytest

from deskgate.core.callback_policy import CallbackUrlError, check_callback_url

pytestmark = pytest.mark.unit

ALLOWED = ["localhost", "127.0.0.1"]


@pytest.mark.parametrize(
    ("url", "host"),
    [
        ("http://localhost:5678/webhook-waiting/1?signature=a+b/c=d%2B", "localhost"),
        ("http://127.0.0.1:5678/webhook-waiting/42?signature=x", "127.0.0.1"),
        ("https://LOCALHOST/x", "localhost"),
        ("http://localhost/x", "localhost"),
    ],
)
def test_acceptees(url: str, host: str) -> None:
    assert check_callback_url(url, ALLOWED) == host


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("http://localhost@evil.com/", "userinfo"),
        ("http://user:pw@localhost/", "userinfo"),
        ("http://evil.com\\@localhost/", "invalid_chars"),
        ("http://localhost\t.evil.com/", "invalid_chars"),
        (" http://localhost/", "invalid_chars"),
        ("http://localhost.evil.com/", "host_not_allowed"),
        ("http://127.1/", "host_not_allowed"),
        ("http://localhost./", "host_not_allowed"),
        ("ftp://localhost/", "scheme"),
        ("http:///x", "no_host"),
        ("http://localhost:99999/", "port"),
        ("http://évil/", "invalid_chars"),
    ],
)
def test_refusees(url: str, reason: str) -> None:
    with pytest.raises(CallbackUrlError) as info:
        check_callback_url(url, ALLOWED)
    assert info.value.reason == reason


def test_message_sans_url() -> None:
    url = "http://evil.com/w?signature=SECRET-XYZ"
    with pytest.raises(CallbackUrlError) as info:
        check_callback_url(url, ALLOWED)
    exc = info.value
    assert exc.reason == "host_not_allowed"
    assert exc.host == "evil.com"
    assert "SECRET-XYZ" not in str(exc)
    assert "SECRET-XYZ" not in exc.message
    assert "evil.com" in exc.message
    assert "callback_allowed_hosts" in exc.message


def test_hotes_compares_en_minuscules() -> None:
    assert check_callback_url("http://localhost/", ["LocalHost"]) == "localhost"

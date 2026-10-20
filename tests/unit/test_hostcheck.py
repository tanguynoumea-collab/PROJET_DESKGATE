"""Tests du contrôle de l'en-tête Host (D-07)."""

from __future__ import annotations

import pytest

from deskgate.core.hostcheck import is_allowed_host

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "raw",
    [
        "127.0.0.1",
        "127.0.0.1:8765",
        "localhost",
        "LocalHost:8765",
        "host.docker.internal",
        "host.docker.internal:8765",
    ],
)
def test_hotes_autorises(raw: str) -> None:
    assert is_allowed_host(raw) is True


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "evil.com",
        "127.0.0.1.evil.com",
        "localhost.",
        "[::1]",
        "[::1]:8765",
        "localhost:99999x",
        "localhost:123456",
        "localhost:70000",
        "127.0.0.1 ",
        "user@localhost",
        "192.168.1.10",
    ],
)
def test_hotes_refuses(raw: str | None) -> None:
    assert is_allowed_host(raw) is False

"""Spike D-13(b) : le bind exclusif empêche un second binder sur le même port."""

from __future__ import annotations

import socket
import sys

import pytest

from deskgate.instance import bind_exclusive, describe_bind_error

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(sys.platform != "win32", reason="WinError : Windows uniquement"),
]


def test_bind_non_heritable() -> None:
    a = bind_exclusive("127.0.0.1", 0)
    try:
        assert a.get_inheritable() is False
    finally:
        a.close()


def test_second_bind_echoue() -> None:
    a = bind_exclusive("127.0.0.1", 0)
    try:
        a.listen()
        port = a.getsockname()[1]
        with pytest.raises(OSError) as e:
            bind_exclusive("127.0.0.1", port)
        assert e.value.winerror == 10048  # type: ignore[attr-defined]
        b = socket.socket()
        try:
            b.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            with pytest.raises(OSError) as e2:
                b.bind(("127.0.0.1", port))
            assert e2.value.winerror == 10013  # type: ignore[attr-defined]
        finally:
            b.close()
    finally:
        a.close()


def test_messages_bind() -> None:
    m1 = describe_bind_error(OSError(None, "x", None, 10048), "127.0.0.1", 8765)
    assert "déjà utilisé" in m1
    m2 = describe_bind_error(OSError(None, "x", None, 10013), "127.0.0.1", 8765)
    assert "accès refusé" in m2.lower()
    assert "excludedportrange" in m2
    m3 = describe_bind_error(OSError(None, "x", None, 99999), "127.0.0.1", 8765)
    assert "99999" in m3

"""Le contrat dupliqué du SDK est égal à celui du cœur."""

from __future__ import annotations

import pytest

from deskgate.core import worker_protocol
from deskgate_sdk import run

pytestmark = pytest.mark.unit


def test_contrat_identique() -> None:
    assert run.CONTRACT == worker_protocol.CONTRACT


def test_protocole_identique() -> None:
    assert run.PROTOCOL == worker_protocol.PROTOCOL == 1

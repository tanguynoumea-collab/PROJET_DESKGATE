"""Codes de sortie de serve() : alignés et distincts."""

from __future__ import annotations

import pytest

from deskgate import runtime

pytestmark = pytest.mark.unit


def test_exit_codes_alignes() -> None:
    assert runtime.EXIT_THREAD_FAILED == 6
    codes = [
        runtime.EXIT_INVALID_CONFIG,
        runtime.EXIT_ALREADY_RUNNING,
        runtime.EXIT_BIND_FAILED,
        runtime.EXIT_DB_ERROR,
        runtime.EXIT_THREAD_FAILED,
    ]
    assert codes == [2, 3, 4, 5, 6]

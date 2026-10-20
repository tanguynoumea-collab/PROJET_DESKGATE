"""Fixture de session : interpréteurs des environnements uv des plugins."""

from __future__ import annotations

from pathlib import Path

import pytest

from _support.plugin_envs import plugin_envs_paths


@pytest.fixture(scope="session")
def plugin_envs() -> dict[str, Path]:
    return plugin_envs_paths()

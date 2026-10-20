"""Emplacements D-01 et validité du gabarit runner.example.toml."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import pytest

from deskgate.core.config import parse_config
from deskgate.locations import config_path, db_path, default_home, resolve_home

pytestmark = pytest.mark.unit


def test_default_home_has_no_double_level() -> None:
    home = default_home()
    assert home.name == "Deskgate"
    assert home.parent.name != "Deskgate"


def test_resolve_home_env_overrides() -> None:
    assert resolve_home({"DESKGATE_HOME": "X:/h"}) == Path("X:/h")
    assert resolve_home({}) == default_home()


def test_config_and_db_paths() -> None:
    home = Path("X:/h")
    assert config_path(home) == home / "runner.toml"
    assert config_path(home, Path("Y:/c.toml")) == Path("Y:/c.toml")
    assert db_path(home) == home / "deskgate.db"


def test_example_template_is_valid() -> None:
    text = (resources.files("deskgate") / "runner.example.toml").read_text(encoding="utf-8")
    cfg = parse_config(text, "runner.example.toml")
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8765
    assert cfg.paths.allowed_roots
    assert cfg.callback.max_window_s == 86400
    assert cfg.callback_allowed_hosts == ["localhost", "127.0.0.1"]
    assert any(m.container == "/data" and m.host == "C:/BIM" for m in cfg.mappings())

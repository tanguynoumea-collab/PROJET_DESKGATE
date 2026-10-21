"""`deskgate --version` (prescrit par AGENTS.md)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from deskgate import __version__
from deskgate.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout == f"deskgate {__version__}\n"


def test_aide_liste_serve() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "serve" in result.stdout

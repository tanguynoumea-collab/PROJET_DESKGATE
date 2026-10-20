"""CLI Typer et ordre de démarrage (échec de configuration avant toute écriture disque)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from deskgate import runtime
from deskgate.cli import app
from deskgate.core.tokens import hash_token

pytestmark = pytest.mark.unit


def test_dev_token_imprime_jeton_et_hash() -> None:
    result = CliRunner().invoke(app, ["dev-token"])
    assert result.exit_code == 0
    lignes = result.stdout.strip().splitlines()
    assert len(lignes) == 2
    jeton = lignes[0]
    assert len(jeton) >= 43
    assert lignes[1] == f'token_sha256 = "{hash_token(jeton)}"'


def test_aide_liste_serve_et_cache_dev_token() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "serve" in result.stdout
    assert "dev-token" not in result.stdout


def test_serve_config_absente_code_2(
    tmp_path: Path, data_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = runtime.serve(tmp_path / "absent.toml")
    assert code == runtime.EXIT_INVALID_CONFIG == 2
    assert capsys.readouterr().err.strip()
    assert not (data_home / "deskgate.db").exists()

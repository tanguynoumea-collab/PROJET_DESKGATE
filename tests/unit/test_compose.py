"""Contrôle statique du compose n8n par `docker compose config` (rien n'est démarré)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.docker

RACINE = Path(__file__).resolve().parents[2]
COMPOSE = RACINE / "n8n" / "docker-compose.yml"
ENV_EXEMPLE = RACINE / "n8n" / ".env.example"
SECRETS = ("POSTGRES_PASSWORD", "N8N_ENCRYPTION_KEY", "POSTGRES_USER", "POSTGRES_DB")


def _docker() -> str:
    docker = shutil.which("docker")
    if docker is None:
        pytest.fail("docker introuvable : Docker Desktop requis pour ce test")
    return docker


def _config(env_file: Path) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k not in SECRETS}
    return subprocess.run(
        [
            _docker(),
            "compose",
            "-f",
            str(COMPOSE),
            "--env-file",
            str(env_file),
            "config",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
        timeout=60,
    )


@pytest.fixture(scope="module")
def config() -> dict[str, Any]:
    res = _config(ENV_EXEMPLE)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def test_images_epinglees(config: dict[str, Any]) -> None:
    services = config["services"]
    assert services["n8n"]["image"] == (
        "docker.n8n.io/n8nio/n8n:2.43.8"
        "@sha256:a18edcf018198b33b5488fb47ededafe11e0b10d28f65b9535b7c447c9ce3b2c"
    )
    assert (
        "17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24"
        in services["postgres"]["image"]
    )


def test_ports_locaux_seulement(config: dict[str, Any]) -> None:
    ports = config["services"]["n8n"]["ports"]
    assert len(ports) == 1
    assert ports[0]["target"] == 5678
    assert str(ports[0]["published"]) == "5679"
    assert ports[0]["host_ip"] == "127.0.0.1"
    assert not config["services"]["postgres"].get("ports")


def test_volume_data(config: dict[str, Any]) -> None:
    volumes = config["services"]["n8n"]["volumes"]
    data = [v for v in volumes if v["target"] == "/data"]
    assert len(data) == 1
    assert data[0]["source"].rstrip("/\\").endswith("BIM")


def test_environnement_n8n(config: dict[str, Any]) -> None:
    env = config["services"]["n8n"]["environment"]
    assert env["N8N_WEBHOOK_URL"] == "http://127.0.0.1:5679/"
    assert env["DB_TYPE"] == "postgresdb"
    assert "N8N_RUNNERS_ENABLED" not in env


def test_texte_sans_latest_ni_runners() -> None:
    texte = COMPOSE.read_text(encoding="utf-8")
    assert "latest" not in texte
    assert "N8N_RUNNERS_ENABLED" not in texte


def test_secrets_manquants_font_echouer_config(tmp_path: Path) -> None:
    vide = tmp_path / "vide.env"
    vide.write_text("N8N_HOST_PORT=5679\n", encoding="utf-8")
    res = _config(vide)
    assert res.returncode != 0

"""Preuves de bout en bout RUN-01..04 : `deskgate serve` réel en sous-processus."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from tests.e2e.conftest import (
    TOKEN,
    Runner,
    kill_tree,
    runner_env,
    start_runner,
    wait_health,
    write_config,
)

from deskgate.instance import acquire_mutex

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows seul"),
]


def _get(port: int, path: str, token: str | None = None) -> tuple[int, dict[str, Any]]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:  # noqa: S310 (http local)
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _serve(env: dict[str, str], timeout: float = 60) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "deskgate", "serve"],
        env=env,
        capture_output=True,
        timeout=timeout,
    )


@pytest.mark.timeout(90)
def test_health_sans_jeton(runner: Runner) -> None:
    status, body = _get(runner.port, "/health")
    assert status == 200
    assert set(body) == {"status", "version", "warnings", "engine", "sender"}
    assert body["warnings"] == []
    assert body["engine"] == body["sender"] == "ok"
    texte = json.dumps(body)
    assert str(runner.home) not in texte
    assert "token" not in texte
    assert ":\\" not in texte
    assert ":/" not in texte


@pytest.mark.timeout(90)
def test_route_protegee_sans_jeton(runner: Runner) -> None:
    status, body = _get(runner.port, "/inconnue")
    assert status == 401
    assert body["error"]["code"] == "unauthorized"
    status, body = _get(runner.port, "/inconnue", TOKEN)
    assert status == 404
    assert body["error"]["code"] == "http_404"


@pytest.mark.timeout(90)
def test_ecoute_loopback_seulement(runner: Runner) -> None:
    lan = socket.gethostbyname(socket.gethostname())
    if lan.startswith("127."):
        pytest.skip("Aucune IP LAN disponible")
    with pytest.raises(OSError):
        socket.create_connection((lan, runner.port), timeout=2)
    socket.create_connection(("127.0.0.1", runner.port), timeout=2).close()


@pytest.mark.timeout(90)
def test_config_invalide_code_2(data_home: Path, instance_name: str, free_port: int) -> None:
    write_config(data_home, free_port, token_sha256='"SECRETVALUE"', bogus=1)  # noqa: S106
    res = _serve(runner_env(data_home, instance_name))
    err = res.stderr.decode("utf-8", "replace")
    assert res.returncode == 2
    assert "Configuration invalide" in err
    assert "bogus" in err
    assert "token_sha256" in err
    assert "SECRETVALUE" not in err
    assert not (data_home / "deskgate.db").exists()


@pytest.mark.timeout(90)
def test_config_non_loopback_refusee(data_home: Path, instance_name: str, free_port: int) -> None:
    write_config(data_home, free_port, host='"192.168.1.10"')
    res = _serve(runner_env(data_home, instance_name))
    assert res.returncode == 2
    assert "allow_non_loopback" in res.stderr.decode("utf-8", "replace")
    assert not (data_home / "deskgate.db").exists()


@pytest.mark.timeout(90)
def test_second_runner_code_3(runner: Runner) -> None:
    db = runner.home / "deskgate.db"
    before = db.stat().st_mtime_ns

    # -wal/-shm : fichiers annexes que l'engine du premier runner crée à son rythme.
    def lister() -> list[str]:
        return sorted(
            p.name for p in runner.home.iterdir() if not p.name.endswith(("-wal", "-shm"))
        )

    fichiers = lister()
    res = _serve(runner.env, timeout=30)
    assert res.returncode == 3
    assert "déjà en cours" in res.stderr.decode("utf-8", "replace")
    assert db.stat().st_mtime_ns == before
    assert lister() == fichiers
    status, _ = _get(runner.port, "/health")
    assert status == 200


@pytest.mark.timeout(90)
def test_second_runner_sans_base_existante(
    data_home: Path, instance_name: str, free_port: int
) -> None:
    write_config(data_home, free_port)
    assert acquire_mutex(instance_name) is not None
    res = _serve(runner_env(data_home, instance_name))
    assert res.returncode == 3
    assert not (data_home / "deskgate.db").exists()


@pytest.mark.timeout(90)
def test_redemarrage_apres_kill(runner: Runner) -> None:
    kill_tree(runner.proc)
    second = start_runner(runner.env)
    try:
        wait_health(runner.port, second)
    finally:
        kill_tree(second)
        for stream in (second.stdout, second.stderr):
            if stream is not None:
                stream.close()

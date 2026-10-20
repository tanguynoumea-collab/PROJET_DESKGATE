"""Aides e2e : lancement de `deskgate serve` en sous-processus, toujours tué en arbre."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from tests._support.jobs import FAKE_PLUGINS

from deskgate.core.tokens import hash_token

TOKEN = "jeton-de-test-e2e"  # noqa: S105 (jeton factice de test)
CALLBACK_URL = "http://localhost:5678/webhook-waiting/42?signature=E2E-SECRET-SIG"
FAKE_CAPS: dict[str, dict[str, object]] = {
    "demo.sleep": {"entry": "deskgate_fakes:sleep", "timeout_max": 600},
    "demo.spawn_orphan": {"entry": "deskgate_fakes:spawn_orphan", "timeout_max": 600},
    "demo.artifact_ok": {"entry": "deskgate_fakes:artifact_ok", "timeout_max": 600},
}


def write_config(
    home: Path,
    port: int,
    *,
    capabilities: Mapping[str, Mapping[str, object]] | None = None,
    **overrides: object,
) -> Path:
    """Écrit `runner.toml` ; `overrides` remplace des clés de premier niveau (TOML brut)."""
    root = home.parent / "bim"
    root.mkdir(exist_ok=True)
    posix = root.as_posix()
    top: dict[str, object] = {
        "host": '"127.0.0.1"',
        "port": port,
        "token_sha256": f'"{hash_token(TOKEN)}"',
    }
    top.update(overrides)
    lines = [f"{k} = {v}" for k, v in top.items()]
    lines += [
        "",
        "[paths]",
        f"allowed_roots = ['{posix}']",
        "",
        "[[paths.mapping]]",
        'container = "/data"',
        f"host = '{posix}'",
        "",
    ]
    for cap_id, options in (capabilities or {}).items():
        lines += [
            f'[capabilities."{cap_id}"]',
            'kind = "python"',
            f"python = '{Path(sys.executable).as_posix()}'",
            f"entry = '{options['entry']}'",
            f"timeout_max = {options['timeout_max']}",
            f"pythonpath = ['{FAKE_PLUGINS.as_posix()}']",
            "",
        ]
    home.mkdir(parents=True, exist_ok=True)
    path = home / "runner.toml"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def runner_env(data_home: Path, instance_name: str) -> dict[str, str]:
    env = os.environ.copy()
    env["DESKGATE_HOME"] = str(data_home)
    env["DESKGATE_INSTANCE_NAME"] = instance_name
    env["PYTHONUTF8"] = "1"
    return env


def start_runner(env: dict[str, str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [sys.executable, "-m", "deskgate", "serve"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )


def kill_tree(p: subprocess.Popen[bytes]) -> None:
    """Tue l'arbre entier (le lanceur de venv crée un processus enfant)."""
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
    p.wait(10)


def wait_health(
    port: int, proc: subprocess.Popen[bytes] | None = None, timeout: float = 15.0
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc is not None and proc.poll() is not None:
            break
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as r:
                if r.status == 200:
                    return json.loads(r.read())
        except OSError:
            pass
        time.sleep(0.2)
    detail = ""
    if proc is not None:
        if proc.poll() is None:
            kill_tree(proc)
        if proc.stderr is not None:
            detail = proc.stderr.read().decode("utf-8", "replace")
    pytest.fail(f"Le runner ne répond pas sur /health : {detail}")


@dataclass
class Runner:
    proc: subprocess.Popen[bytes]
    port: int
    home: Path
    env: dict[str, str]


@pytest.fixture
def runner(data_home: Path, instance_name: str, free_port: int) -> Iterator[Runner]:
    write_config(data_home, free_port)
    env = runner_env(data_home, instance_name)
    proc = start_runner(env)
    r = Runner(proc, free_port, data_home, env)
    try:
        wait_health(free_port, proc)
        yield r
    finally:
        kill_tree(r.proc)
        for stream in (proc.stdout, proc.stderr):
            if stream is not None:
                stream.close()


def api(
    port: int, method: str, path: str, body: object | None = None, token: str | None = TOKEN
) -> tuple[int, dict[str, Any]]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310 (http local)
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def wait_status(
    port: int, job_id: str, statuses: set[str], timeout: float = 30.0
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        _, last = api(port, "GET", f"/jobs/{job_id}")
        if last.get("status") in statuses:
            return last
        time.sleep(0.1)
    pytest.fail(f"Tâche {job_id} : statut {last.get('status')!r}, attendu {statuses}")


@pytest.fixture
def jobs_runner(data_home: Path, instance_name: str, free_port: int) -> Iterator[Runner]:
    write_config(data_home, free_port, capabilities=FAKE_CAPS)
    env = runner_env(data_home, instance_name)
    proc = start_runner(env)
    r = Runner(proc, free_port, data_home, env)
    try:
        wait_health(free_port, proc)
        yield r
    finally:
        kill_tree(r.proc)
        for stream in (proc.stdout, proc.stderr):
            if stream is not None:
                stream.close()

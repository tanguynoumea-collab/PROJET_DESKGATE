"""mcp.call : délai d'appel et serveurs injoignables, sans ExceptionGroup brut."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from _support.jobs import run_until_terminal, submit
from _support.mcp_env import mcp_config, mcp_engine

pytestmark = [pytest.mark.proc, pytest.mark.mcp]

PY = sys.executable.replace("\\", "/")


def _failed(
    tmp_path: Path, server: dict[str, object], params: dict[str, object]
) -> tuple[str, float]:
    cfg = mcp_config(tmp_path, servers={"srv": server})
    engine, db = mcp_engine(tmp_path, cfg)
    try:
        t0 = time.monotonic()
        job_id = submit(db, cfg, "mcp.call", {"server": "srv", **params})
        row = run_until_terminal(engine, db, job_id, timeout=45)
        dt = time.monotonic() - t0
    finally:
        engine.stop()
    assert row.status == "failed", (row.status, row.error_message)
    msg = row.error_message or ""
    assert "ExceptionGroup" not in msg
    return msg, dt


@pytest.mark.timeout(60)
def test_call_timeout(tmp_path: Path) -> None:
    from _support.mcp_env import MINI

    server = {"command": PY, "args": [str(MINI).replace("\\", "/")], "allowed_tools": ["sleep"]}
    msg, dt = _failed(
        tmp_path,
        server,
        {"tool": "sleep", "arguments": {"seconds": 5}, "call_timeout_s": 1},
    )
    assert msg.startswith("call_timeout : ")
    assert dt < 4 + 6  # marge de démarrage Python/mcp ; le délai d'appel lui-même est de 1 s


@pytest.mark.timeout(60)
def test_commande_inexistante(tmp_path: Path) -> None:
    server = {"command": "C:/inexistant/python.exe", "args": [], "allowed_tools": ["echo"]}
    msg, _ = _failed(tmp_path, server, {"tool": "echo", "arguments": {}, "call_timeout_s": 5})
    assert msg.startswith("server_unreachable : ")


@pytest.mark.timeout(60)
def test_serveur_sort_tout_de_suite(tmp_path: Path) -> None:
    server = {"command": PY, "args": ["-c", "pass"], "allowed_tools": ["echo"]}
    msg, _ = _failed(tmp_path, server, {"tool": "echo", "arguments": {}, "call_timeout_s": 5})
    assert msg.startswith("server_unreachable : ")


@pytest.mark.timeout(60)
def test_serveur_pollue_stdout(tmp_path: Path) -> None:
    server = {
        "command": PY,
        "args": ["-c", "print('x'); import time; time.sleep(30)"],
        "allowed_tools": ["echo"],
    }
    msg, _ = _failed(tmp_path, server, {"tool": "echo", "arguments": {}, "call_timeout_s": 2})
    assert msg.startswith("server_unreachable : ")

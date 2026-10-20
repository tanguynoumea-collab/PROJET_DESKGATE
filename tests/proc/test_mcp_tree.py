"""mcp.call : l'arrêt de la tâche tue le serveur MCP et son petit-enfant."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from _support.jobs import get, run_until_terminal, submit
from _support.mcp_env import mcp_config, mcp_engine
from _support.procs import wait_dead
from deskgate import store

pytestmark = [pytest.mark.proc, pytest.mark.mcp]


def _pids(pid_file: Path) -> tuple[int, int]:
    a, b = pid_file.read_text(encoding="utf-8").split()
    return int(a), int(b)


def _wait_file(engine: object, pid_file: Path) -> None:
    limit = time.monotonic() + 20
    while time.monotonic() < limit:
        engine.tick()  # type: ignore[attr-defined]
        if pid_file.exists() and pid_file.read_text(encoding="utf-8").count(" ") == 1:
            return
        time.sleep(0.05)
    raise AssertionError("fichier de PID absent")


@pytest.mark.timeout(90)
def test_delai_de_tache_tue_l_arbre(tmp_path: Path) -> None:
    cfg = mcp_config(tmp_path)
    engine, db = mcp_engine(tmp_path, cfg)
    pid_file = tmp_path / "pids.txt"
    try:
        job_id = submit(
            db,
            cfg,
            "mcp.call",
            {
                "server": "mini",
                "tool": "spawn_orphan",
                "arguments": {"pid_file": str(pid_file).replace("\\", "/"), "sleep": 60},
                "call_timeout_s": 120,
            },
            timeout_s=8,
        )
        row = run_until_terminal(engine, db, job_id, timeout=60)
    finally:
        engine.stop()
    assert row.status == "timeout", (row.status, row.error_message)
    server_pid, grand_pid = _pids(pid_file)
    assert wait_dead(server_pid, 10)
    assert wait_dead(grand_pid, 10)


@pytest.mark.timeout(90)
def test_annulation_tue_l_arbre(tmp_path: Path) -> None:
    cfg = mcp_config(tmp_path)
    engine, db = mcp_engine(tmp_path, cfg)
    pid_file = tmp_path / "pids.txt"
    try:
        job_id = submit(
            db,
            cfg,
            "mcp.call",
            {
                "server": "mini",
                "tool": "spawn_orphan",
                "arguments": {"pid_file": str(pid_file).replace("\\", "/"), "sleep": 60},
                "call_timeout_s": 120,
            },
        )
        _wait_file(engine, pid_file)
        conn = store.open_db(db)
        try:
            store.request_cancel(conn, job_id)
        finally:
            conn.close()
        row = run_until_terminal(engine, db, job_id, timeout=30)
    finally:
        engine.stop()
    assert row.status == "cancelled", (row.status, row.error_message)
    server_pid, grand_pid = _pids(pid_file)
    assert wait_dead(server_pid, 10)
    assert wait_dead(grand_pid, 10)


@pytest.mark.timeout(90)
def test_sortie_normale_tue_l_arbre(tmp_path: Path) -> None:
    cfg = mcp_config(tmp_path)
    engine, db = mcp_engine(tmp_path, cfg)
    pid_file = tmp_path / "pids.txt"
    try:
        job_id = submit(
            db,
            cfg,
            "mcp.call",
            {
                "server": "mini",
                "tool": "spawn_orphan",
                "arguments": {"pid_file": str(pid_file).replace("\\", "/"), "sleep": 0},
            },
        )
        row = run_until_terminal(engine, db, job_id, timeout=45)
    finally:
        engine.stop()
    assert row.status == "succeeded", (row.status, row.error_message)
    assert get(db, job_id).status == "succeeded"
    server_pid, grand_pid = _pids(pid_file)
    assert wait_dead(server_pid, 10)
    assert wait_dead(grand_pid, 10)

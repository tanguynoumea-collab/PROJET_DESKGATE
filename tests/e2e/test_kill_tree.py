"""Non-régression : `kill_tree` ne rend la main qu'une fois tout l'arbre du runner mort."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import psutil
import pytest
from tests.e2e.conftest import kill_tree, runner_env, start_runner, wait_health, write_config

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows seul"),
]


@pytest.mark.timeout(60)
def test_kill_tree_attend_tout_l_arbre(data_home: Path, instance_name: str, free_port: int) -> None:
    write_config(data_home, free_port)
    proc = start_runner(runner_env(data_home, instance_name))
    try:
        wait_health(free_port, proc)
        pids = [proc.pid, *(c.pid for c in psutil.Process(proc.pid).children(recursive=True))]
        kill_tree(proc)
    finally:
        for flux in (proc.stdout, proc.stderr):
            if flux is not None:
                flux.close()
    assert [pid for pid in pids if psutil.pid_exists(pid)] == []
    con = sqlite3.connect(data_home / "deskgate.db", timeout=5)
    try:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert con.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0
    finally:
        con.close()

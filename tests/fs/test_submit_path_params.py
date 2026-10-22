"""Soumission : refus 422 des chemins déclarés hors racines, audité."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from _support.jobs import make_config
from deskgate import store
from deskgate.core.jobspec import JobRequestError, SubmitRequest
from deskgate.jobs import JobsService

pytestmark = pytest.mark.fs

URL = "http://localhost:5678/webhook-waiting/1?signature=SECRET-SIG"


class Env:
    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "bim"
        self.db = tmp_path / "d.db"
        store.open_db(self.db).close()
        cfg = make_config(tmp_path, {"demo.p": {"path_params": ["ifc_a"]}})
        self.service = JobsService(db_path=self.db, config=cfg)

    def submit(self, value: object) -> str:
        req = SubmitRequest.model_validate(
            {"capability": "demo.p", "params": {"ifc_a": value}, "callback": {"url": URL}}
        )
        return self.service.submit(req)

    def count(self, table: str) -> int:
        conn = store.connect(self.db)
        try:
            return int(conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0])  # noqa: S608
        finally:
            conn.close()

    def refusals(self) -> list[dict[str, object]]:
        conn = store.connect(self.db)
        try:
            rows = conn.execute(
                "SELECT detail_json FROM audit WHERE event='job.refused'"
            ).fetchall()
        finally:
            conn.close()
        return [json.loads(r[0]) for r in rows]


def test_dotdot_refuse(tmp_path: Path) -> None:
    env = Env(tmp_path)
    with pytest.raises(JobRequestError) as e:
        env.submit("/data/../x")
    assert e.value.status == 422
    assert e.value.code in {"path_outside_roots", "path_invalid"}
    assert env.count("jobs") == 0
    assert any(r.get("code") == e.value.code for r in env.refusals())


def test_type_invalide(tmp_path: Path) -> None:
    env = Env(tmp_path)
    with pytest.raises(JobRequestError) as e:
        env.submit(3)
    assert (e.value.status, e.value.code) == (422, "path_invalid")


def test_chemin_valide_accepte(tmp_path: Path) -> None:
    env = Env(tmp_path)
    assert env.submit("/data/a.ifc")
    assert env.count("jobs") == 1


def test_jonction_hors_racine(tmp_path: Path, junction: Callable[[Path, Path], Path]) -> None:
    env = Env(tmp_path)
    outside = tmp_path / "dehors"
    outside.mkdir()
    junction(env.root / "lien", outside)
    with pytest.raises(JobRequestError) as e:
        env.submit("/data/lien/a.ifc")
    assert (e.value.status, e.value.code) == (422, "path_outside_roots")


class McpEnv(Env):
    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "bim"
        self.db = tmp_path / "d.db"
        store.open_db(self.db).close()
        server = {
            "command": "C:/Python/python.exe",
            "allowed_tools": ["read_file", "echo"],
            "path_arguments": {"read_file": ["path"]},
        }
        cfg = make_config(tmp_path, {"mcp.call": {"kind": "mcp"}}, mcp_servers={"srv": server})
        self.service = JobsService(db_path=self.db, config=cfg)

    def submit_mcp(self, tool: str, arguments: dict[str, object]) -> str:
        req = SubmitRequest.model_validate(
            {
                "capability": "mcp.call",
                "params": {"server": "srv", "tool": tool, "arguments": arguments},
                "callback": {"url": URL},
            }
        )
        return self.service.submit(req)


def test_mcp_dotdot_refuse(tmp_path: Path) -> None:
    env = McpEnv(tmp_path)
    with pytest.raises(JobRequestError) as e:
        env.submit_mcp("read_file", {"path": "/data/../hors.txt"})
    assert e.value.status == 422
    assert e.value.code in {"path_outside_roots", "path_invalid"}
    assert env.count("jobs") == 0
    assert any(r.get("code") == e.value.code for r in env.refusals())


def test_mcp_jonction_hors_racine(tmp_path: Path, junction: Callable[[Path, Path], Path]) -> None:
    env = McpEnv(tmp_path)
    outside = tmp_path / "dehors"
    outside.mkdir()
    junction(env.root / "lien", outside)
    with pytest.raises(JobRequestError) as e:
        env.submit_mcp("read_file", {"path": "/data/lien/secret.txt"})
    assert (e.value.status, e.value.code) == (422, "path_outside_roots")
    assert env.count("jobs") == 0


def test_mcp_chemin_valide_accepte(tmp_path: Path) -> None:
    env = McpEnv(tmp_path)
    assert env.submit_mcp("read_file", {"path": "/data/depot/a.txt"})
    conn = store.connect(env.db)
    try:
        raw = conn.execute("SELECT params_json FROM jobs").fetchone()[0]
    finally:
        conn.close()
    assert json.loads(raw)["arguments"] == {"path": "/data/depot/a.txt"}


def test_mcp_argument_non_declare_opaque(tmp_path: Path) -> None:
    env = McpEnv(tmp_path)
    assert env.submit_mcp("echo", {"text": "/data/../x"})

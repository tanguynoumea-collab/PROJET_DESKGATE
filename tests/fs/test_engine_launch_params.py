"""Lancement : conversion des chemins, settings, exécuteur mcp (faux launcher)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from _support.jobs import FakeLauncher, get, make_config, submit
from deskgate import store
from deskgate.engine import Engine, LaunchSpec

pytestmark = pytest.mark.fs

SECRET = "valeur-secrete-42"  # noqa: S105
RUNNER_PY = "C:/runner/python.exe"


class Env:
    def __init__(self, tmp_path: Path, caps: dict[str, dict[str, object]], **kw: object) -> None:
        self.root = tmp_path / "bim"
        self.db = tmp_path / "d.db"
        store.open_db(self.db).close()
        self.inputs: list[dict[str, object]] = []
        self.cfg = make_config(tmp_path, caps, **kw)  # type: ignore[arg-type]
        self.launcher = FakeLauncher(self._on_launch)
        self.engine = Engine(
            db_path=self.db,
            config=self.cfg,
            worker_script=Path("C:/fake/run.py"),
            launcher=self.launcher,
            poll=5.0,
            base_env={"PATH": "x"},
            runner_python=RUNNER_PY,
        )

    def _on_launch(self, spec: LaunchSpec) -> None:
        self.inputs.append(json.loads(Path(spec.cwd, "input.json").read_text(encoding="utf-8")))


def test_chemin_converti_base_intacte(tmp_path: Path) -> None:
    env = Env(tmp_path, {"demo.p": {"path_params": ["ifc_a"]}})
    job = submit(env.db, env.cfg, "demo.p", {"ifc_a": "/data/depot/a.ifc"})
    env.engine.tick()
    root = str(env.root).replace("\\", "/")
    assert env.inputs[0]["params"] == {"ifc_a": f"{root}/depot/a.ifc"}
    assert json.loads(get(env.db, job).params_json) == {"ifc_a": "/data/depot/a.ifc"}


def test_chemin_hors_racine_echec(tmp_path: Path) -> None:
    env = Env(tmp_path, {"demo.p": {"path_params": ["ifc_a"]}})
    job = submit(env.db, env.cfg, "demo.p", {"ifc_a": "/data/../hors.ifc"})
    env.engine.tick()
    row = get(env.db, job)
    assert row.status == "failed"
    assert row.error_code in {"path_outside_roots", "path_invalid"}
    assert env.launcher.specs == []
    assert not (Path(row.work_dir) / "input.json").exists()


def test_settings_transmis(tmp_path: Path) -> None:
    settings = {"bcf_executable": "C:/x.exe", "threads": 2}
    env = Env(tmp_path, {"demo.s": {"settings": settings}})
    submit(env.db, env.cfg, "demo.s")
    env.engine.tick()
    assert env.inputs[0]["settings"] == settings


def test_kind_mcp(tmp_path: Path) -> None:
    server = {
        "command": "C:/Python/python.exe",
        "args": ["s.py"],
        "env": {"LANG": SECRET},
        "allowed_tools": ["echo"],
    }
    env = Env(
        tmp_path,
        {"mcp.call": {"kind": "mcp"}},
        mcp_servers={"demo": server},
    )
    job = submit(env.db, env.cfg, "mcp.call", {"server": "demo", "tool": "echo", "arguments": {}})
    env.engine.tick()
    spec = env.launcher.specs[0]
    assert spec.argv[0] == RUNNER_PY
    inp = env.inputs[0]
    assert inp["entry"] == "deskgate.workers.mcp_call:run"
    assert inp["sys_path"] == []
    assert inp["settings"] == {
        "servers": {
            "demo": {
                "command": "C:/Python/python.exe",
                "args": ["s.py"],
                "allowed_tools": ["echo"],
                "env_keys": ["LANG"],
            }
        }
    }
    text = Path(get(env.db, job).work_dir, "input.json").read_text(encoding="utf-8")
    assert SECRET not in text
    assert spec.env["DESKGATE_MCPENV__DEMO__LANG"] == SECRET


_SRV_PATH = {
    "command": "C:/Python/python.exe",
    "allowed_tools": ["read_file", "echo"],
    "path_arguments": {"read_file": ["path"]},
}


def _call(server: str, tool: str, arguments: dict[str, object]) -> dict[str, object]:
    return {"server": server, "tool": tool, "arguments": arguments}


def test_mcp_chemin_converti_au_lancement(tmp_path: Path) -> None:
    env = Env(tmp_path, {"mcp.call": {"kind": "mcp"}}, mcp_servers={"srv": _SRV_PATH})
    job = submit(
        env.db, env.cfg, "mcp.call", _call("srv", "read_file", {"path": "/data/depot/a.txt"})
    )
    env.engine.tick()
    root = str(env.root).replace("\\", "/")
    assert env.inputs[0]["params"] == _call("srv", "read_file", {"path": f"{root}/depot/a.txt"})
    stored = json.loads(get(env.db, job).params_json)
    assert stored["arguments"] == {"path": "/data/depot/a.txt"}


def test_mcp_revalidation_au_lancement(tmp_path: Path) -> None:
    env = Env(tmp_path, {"mcp.call": {"kind": "mcp"}}, mcp_servers={"srv": _SRV_PATH})
    job = submit(
        env.db, env.cfg, "mcp.call", _call("srv", "read_file", {"path": "/data/../hors.txt"})
    )
    env.engine.tick()
    row = get(env.db, job)
    assert row.status == "failed"
    assert row.error_code in {"path_outside_roots", "path_invalid"}
    assert env.launcher.specs == []


def _two_servers(tmp_path: Path) -> Env:
    servers = {
        "a": {"command": "C:/p.exe", "env": {"CLE_A": "va"}, "allowed_tools": ["echo"]},
        "b": {"command": "C:/p.exe", "env": {"CLE_B": "vb"}, "allowed_tools": ["echo"]},
    }
    return Env(tmp_path, {"mcp.call": {"kind": "mcp"}}, mcp_servers=servers)


def test_mcp_env_du_seul_serveur_vise(tmp_path: Path) -> None:
    env = _two_servers(tmp_path)
    submit(env.db, env.cfg, "mcp.call", _call("a", "echo", {}))
    env.engine.tick()
    spec_env = env.launcher.specs[0].env
    assert spec_env["DESKGATE_MCPENV__A__CLE_A"] == "va"
    assert not [k for k in spec_env if k.startswith("DESKGATE_MCPENV__B__")]


def test_mcp_serveur_inconnu_aucun_env(tmp_path: Path) -> None:
    env = _two_servers(tmp_path)
    submit(env.db, env.cfg, "mcp.call", _call("zz", "echo", {}))
    env.engine.tick()
    assert not [k for k in env.launcher.specs[0].env if k.startswith("DESKGATE_MCPENV__")]

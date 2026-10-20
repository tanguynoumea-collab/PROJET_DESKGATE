"""Aides des tests mcp.call : configuration et Engine réel."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path

import deskgate_sdk.run as sdk_run
from _support.jobs import make_config
from deskgate import store
from deskgate.core.config import RunnerConfig
from deskgate.engine import Engine

MINI = Path(__file__).resolve().parents[1] / "mcp_fake" / "mini_server.py"
SECRET = "valeur-secrete-mcp-42"  # noqa: S105  valeur de test
ALL_TOOLS = ("echo", "add", "sleep", "erreur", "spawn_orphan", "env")


def mcp_config(
    tmp_path: Path,
    *,
    servers: Mapping[str, Mapping[str, object]] | None = None,
    allowed: tuple[str, ...] = ALL_TOOLS,
) -> RunnerConfig:
    default: dict[str, Mapping[str, object]] = {
        "mini": {
            "command": sys.executable.replace("\\", "/"),
            "args": [str(MINI).replace("\\", "/")],
            "env": {"MINI_SECRET": SECRET},
            "allowed_tools": list(allowed),
        }
    }
    return make_config(
        tmp_path,
        caps={"mcp.call": {"kind": "mcp", "timeout_max": 600}},
        mcp_servers=servers or default,
    )


def mcp_engine(tmp_path: Path, cfg: RunnerConfig) -> tuple[Engine, Path]:
    db = tmp_path / "home" / "deskgate.db"
    store.open_db(db).close()
    engine = Engine(
        db_path=db,
        config=cfg,
        worker_script=Path(sdk_run.__file__).resolve(),
        poll=0.05,
        grace=1.0,
    )
    return engine, db

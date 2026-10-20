"""Banc d'essai ifc.clash : Engine réel, scènes IFC synthétiques copiées dans /data/depot."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import deskgate_sdk.run as sdk_run
from _support.jobs import make_config, run_until_terminal, submit
from deskgate import store
from deskgate.engine import Engine


class ClashEnv:
    def __init__(
        self,
        tmp_path: Path,
        plugin_envs: dict[str, Path],
        scenes: tuple[Path, dict[str, dict[str, str]]],
    ) -> None:
        self.tmp_path = tmp_path
        self.python = plugin_envs["bim"]
        self.scenes_dir, self.guids = scenes
        self.depot = tmp_path / "bim" / "depot"
        self.depot.mkdir(parents=True, exist_ok=True)
        self.db = tmp_path / "home" / "deskgate.db"
        self.last_job_id = ""
        self.work_dir = tmp_path

    def place(self, *names: str) -> None:
        for name in names:
            shutil.copy(self.scenes_dir / name, self.depot / name)

    def run(
        self,
        params: dict[str, Any],
        *,
        settings: dict[str, Any] | None = None,
        memory_mb: int | None = None,
        timeout_s: int = 120,
    ) -> tuple[store.JobRow, dict[str, Any]]:
        caps: dict[str, dict[str, object]] = {
            "ifc.clash": {
                "python": str(self.python),
                "entry": "deskgate_bim.clash:run",
                "pythonpath": [],
                "timeout_max": 3600,
                "path_params": ["ifc_a", "ifc_b"],
                "settings": settings or {},
                **({"memory_mb": memory_mb} if memory_mb else {}),
            }
        }
        cfg = make_config(self.tmp_path, caps)
        store.open_db(self.db).close()
        engine = Engine(
            db_path=self.db,
            config=cfg,
            worker_script=Path(sdk_run.__file__).resolve(),
            poll=0.05,
            grace=1.0,
        )
        try:
            job_id = submit(self.db, cfg, "ifc.clash", params, timeout_s=timeout_s)
            row = run_until_terminal(engine, self.db, job_id, timeout=180)
        finally:
            engine.stop()
        self.last_job_id = job_id
        self.work_dir = Path(row.work_dir)
        return row, json.loads(row.result_json or "{}")

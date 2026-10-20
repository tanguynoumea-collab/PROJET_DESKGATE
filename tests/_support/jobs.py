"""Aides partagées des tests de l'engine : configuration, soumission, faux launcher, horloge."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path

from deskgate import store
from deskgate.core.config import RunnerConfig, parse_config
from deskgate.core.jobspec import new_job_id, work_dir_for
from deskgate.engine import Engine, LaunchSpec

FAKE_PLUGINS = Path(__file__).resolve().parents[1] / "fake_plugins"
CALLBACK_URL = "http://localhost:5678/webhook-waiting/1?signature=SECRET-SIG"
DEFAULT_CAPS = (
    "sleep",
    "spawn_orphan",
    "bad_result",
    "chatty",
    "artifact_outside",
    "artifact_ok",
    "exit_code",
    "fail",
    "settings_echo",
    "fail_code",
)


def _slash(p: str | Path) -> str:
    return str(p).replace("\\", "/")


def _toml_value(v: object) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int | float):
        return repr(v)
    if isinstance(v, str):
        return f"'{v}'" if "'" not in v else json.dumps(v)
    if isinstance(v, list):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f'"{k}" = {_toml_value(x)}' for k, x in v.items()) + " }"
    raise TypeError(type(v).__name__)


def make_config(
    tmp_path: Path,
    caps: Mapping[str, Mapping[str, object]] | None = None,
    *,
    mcp_servers: Mapping[str, Mapping[str, object]] | None = None,
    **top: object,
) -> RunnerConfig:
    """Configuration de test : racine `tmp_path/bim`, mapping `/data`, capacités `demo.*`."""
    root = tmp_path / "bim"
    root.mkdir(exist_ok=True)
    lines = [f'token_sha256 = "{"a" * 64}"']
    for key, value in top.items():
        lines.append(f"{key} = {json.dumps(value)}")
    lines += [
        "",
        "[paths]",
        f"allowed_roots = ['{_slash(root)}']",
        "",
        "[[paths.mapping]]",
        'container = "/data"',
        f"host = '{_slash(root)}'",
    ]
    if caps is None:
        caps = {f"demo.{name}": {"entry": f"deskgate_fakes:{name}"} for name in DEFAULT_CAPS}
    for cap_id, options in caps.items():
        if options.get("kind") == "mcp":
            merged: dict[str, object] = {"kind": "mcp", "timeout_max": 600}
        else:
            merged = {
                "kind": "python",
                "python": _slash(sys.executable),
                "entry": "deskgate_fakes:sleep",
                "timeout_max": 600,
                "pythonpath": [_slash(FAKE_PLUGINS)],
            }
        merged.update(options)
        lines += ["", f'[capabilities."{cap_id}"]']
        for key, value in merged.items():
            if key in ("settings", "path_params"):
                lines.append(f"{key} = {_toml_value(value)}")
            elif isinstance(value, list):
                items = ", ".join(f"'{_slash(v)}'" for v in value)
                lines.append(f"{key} = [{items}]")
            elif isinstance(value, str):
                shown = _slash(value) if key == "python" else value
                lines.append(f"{key} = '{shown}'")
            else:
                lines.append(f"{key} = {json.dumps(value)}")
    for name, server in (mcp_servers or {}).items():
        lines += ["", f'[mcp_servers."{name}"]']
        lines += [f"{key} = {_toml_value(value)}" for key, value in server.items()]
    return parse_config("\n".join(lines) + "\n", "test")


def submit(
    db: Path,
    cfg: RunnerConfig,
    capability: str,
    params: dict[str, object] | None = None,
    *,
    timeout_s: int = 60,
    idempotency_key: str | None = None,
) -> str:
    job_id = new_job_id()
    conn = store.open_db(db)
    try:
        store.insert_job(
            conn,
            job_id=job_id,
            capability=capability,
            params_json=json.dumps(params or {}),
            timeout_s=timeout_s,
            resource="default",
            idempotency_key=idempotency_key,
            callback_url=CALLBACK_URL,
            work_dir=work_dir_for(cfg.effective_work_root(), job_id),
        )
    finally:
        conn.close()
    return job_id


def get(db: Path, job_id: str) -> store.JobRow:
    conn = store.connect(db)
    try:
        row = store.get_job(conn, job_id)
    finally:
        conn.close()
    assert row is not None
    return row


def run_until_terminal(
    engine: Engine, db: Path, job_id: str, timeout: float = 30.0
) -> store.JobRow:
    limit = time.monotonic() + timeout
    while time.monotonic() < limit:
        engine.tick()
        row = get(db, job_id)
        if row.status not in ("queued", "running"):
            return row
        time.sleep(0.05)
    raise AssertionError(f"tâche {job_id} non terminale après {timeout} s")


class FakeClock:
    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class FakeProc:
    def __init__(self, pid: int = 4242) -> None:
        self.pid = pid
        self.exit_code: int | None = None

    def poll(self) -> int | None:
        return self.exit_code

    def wait(self, timeout: float | None = None) -> int:
        return 0 if self.exit_code is None else self.exit_code


class FakeJob:
    def __init__(self, proc: FakeProc | None = None) -> None:
        self.proc = proc
        self.terminated = 0
        self.closed = 0
        self.active = 0

    def terminate(self, exit_code: int = 1) -> None:
        self.terminated += 1
        if self.proc is not None and self.proc.exit_code is None:
            self.proc.exit_code = exit_code

    def active_processes(self) -> int:
        return self.active

    def close(self) -> None:
        self.closed += 1


class FakeLauncher:
    def __init__(self, on_launch: Callable[[LaunchSpec], None] | None = None) -> None:
        self.on_launch = on_launch
        self.specs: list[LaunchSpec] = []
        self.jobs: list[FakeJob] = []
        self.procs: list[FakeProc] = []

    def __call__(self, spec: LaunchSpec) -> tuple[FakeJob, FakeProc]:
        self.specs.append(spec)
        if self.on_launch is not None:
            self.on_launch(spec)
        proc = FakeProc(pid=4242 + len(self.procs))
        job = FakeJob(proc)
        self.procs.append(proc)
        self.jobs.append(job)
        return job, proc

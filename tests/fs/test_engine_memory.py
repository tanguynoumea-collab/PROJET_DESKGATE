"""Classement `memory_limit` par l'engine à partir du pic mémoire du Job (faux launcher)."""

from __future__ import annotations

from pathlib import Path

import pytest

from _support.jobs import make_config
from deskgate.core.config import RunnerConfig
from fs.test_engine_tick import Env

pytestmark = pytest.mark.fs

MO = 2**20
CRASH = 3221225477


def _env(tmp_path: Path, caps: dict[str, dict[str, object]]) -> Env:
    env = Env(tmp_path)
    cfg: RunnerConfig = make_config(tmp_path, caps)
    env.cfg = cfg
    env.engine._config = cfg
    return env


def _run(env: Env, cap: str, *, peak: int, error: bool = False) -> tuple[str, str | None]:
    job_id = env.submit(cap)
    env.engine.tick()
    job = env.launcher.jobs[-1]
    job.peak = peak
    job.peak_error = error
    env.finish_proc(len(env.launcher.procs) - 1, CRASH)
    env.engine.tick()
    row = env.row(job_id)
    return row.status, row.error_code


def test_pic_au_plafond_donne_memory_limit(tmp_path: Path) -> None:
    env = _env(tmp_path, {"demo.m": {"memory_mb": 200}})
    assert _run(env, "demo.m", peak=199 * MO) == ("failed", "memory_limit")


def test_pic_bas_reste_nonzero_exit(tmp_path: Path) -> None:
    env = _env(tmp_path, {"demo.m": {"memory_mb": 200}})
    assert _run(env, "demo.m", peak=10 * MO) == ("failed", "nonzero_exit")


def test_pic_illisible_reste_nonzero_exit(tmp_path: Path) -> None:
    env = _env(tmp_path, {"demo.m": {"memory_mb": 200}})
    assert _run(env, "demo.m", peak=199 * MO, error=True) == ("failed", "nonzero_exit")


def test_sans_memory_mb_reste_nonzero_exit(tmp_path: Path) -> None:
    env = _env(tmp_path, {"demo.m": {}})
    assert _run(env, "demo.m", peak=900 * MO) == ("failed", "nonzero_exit")

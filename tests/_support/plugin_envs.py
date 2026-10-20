"""Environnements uv des plugins BIM pour les tests : jamais l'environnement de dev (Pitfall 11)."""

from __future__ import annotations

import functools
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PACKAGES = (("deskgate-bim", "bim"), ("deskgate-bcf", "bcf"))


@functools.cache
def _build() -> dict[str, Path]:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv absent du PATH : environnements de plugins impossibles")
    tag = f"py{sys.version_info.major}{sys.version_info.minor}"
    cache = REPO / ".cache" / "plugin-envs" / tag
    base = getattr(sys, "_base_executable", sys.executable)
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper() not in {"VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"}
    }
    env["UV_PYTHON_DOWNLOADS"] = "never"  # Pitfall 12 : jamais de téléchargement d'interpréteur
    out: dict[str, Path] = {}
    for pkg, key in PACKAGES:
        target = cache / key
        r = subprocess.run(
            [uv, "sync", "--locked", "--package", pkg, "--no-dev", "--python", base],
            cwd=REPO,
            env={**env, "UV_PROJECT_ENVIRONMENT": str(target)},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
            check=False,
        )
        if r.returncode != 0:
            pytest.fail(f"uv sync {pkg} a échoué (code {r.returncode}) :\n{r.stderr[-4000:]}")
        out[key] = target / "Scripts" / "python.exe"
    out["bcf_exe"] = cache / "bcf" / "Scripts" / "deskgate-bcf.exe"
    return out


def plugin_envs_paths() -> dict[str, Path]:
    return _build()


def run_json(python: Path, script: Path, *args: str, timeout: float = 300) -> object:
    """Exécute `python -I script args` (sans PYTHONPATH ni dossier courant) et décode le JSON."""
    r = subprocess.run(
        [str(python), "-I", str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )
    assert r.returncode == 0, r.stderr[-4000:]
    return json.loads(r.stdout)

"""L'environnement deskgate-bim ne voit ni bcf-client ni deskgate_bcf ni scikit-learn."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.bim


def _run(python: Path, code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(python), "-I", "-c", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=False,
    )


def test_env_bim_sans_bcf(plugin_envs: dict[str, Path]) -> None:
    code = (
        "import ifcclash.ifcclash, deskgate_bim, sys, importlib.util as u\n"
        "assert 'bcf' not in sys.modules and 'sklearn' not in sys.modules\n"
        "assert u.find_spec('bcf') is None and u.find_spec('deskgate_bcf') is None\n"
    )
    r = _run(plugin_envs["bim"], code)
    assert r.returncode == 0, r.stderr[-4000:]


def test_env_bim_plafonne_les_threads(plugin_envs: dict[str, Path]) -> None:
    code = "import os, deskgate_bim\nassert os.environ['OPENBLAS_NUM_THREADS'] == '1'\n"
    r = _run(plugin_envs["bim"], code)
    assert r.returncode == 0, r.stderr[-4000:]

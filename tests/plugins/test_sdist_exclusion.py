"""Le sdist MIT n'embarque jamais le code GPL ; deskgate-bcf porte LICENSE et NOTICE."""

from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

from _support.plugin_envs import REPO

pytestmark = pytest.mark.bim


def _build(args: list[str], out: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv absent du PATH")
    env = {**os.environ, "UV_PYTHON_DOWNLOADS": "never"}
    r = subprocess.run(
        [uv, "build", *args, "--out-dir", str(out)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        check=False,
    )
    assert r.returncode == 0, r.stderr[-4000:]


def _membres(sdist: Path) -> list[str]:
    with tarfile.open(sdist) as t:
        return t.getnames()


def test_sdist_bim_sans_bcf(tmp_path: Path) -> None:
    _build(["--sdist", "--package", "deskgate-bim"], tmp_path)
    noms = _membres(next(tmp_path.glob("*.tar.gz")))
    assert noms
    assert not [n for n in noms if "/bcf/" in n or n.endswith("/bcf")], noms


def test_sdist_racine_sans_plugins(tmp_path: Path) -> None:
    _build(["--sdist", "--package", "deskgate"], tmp_path)
    noms = _membres(next(tmp_path.glob("*.tar.gz")))
    assert noms
    assert not [n for n in noms if "/plugins/" in n], noms


def test_deskgate_bcf_licence_et_notice(tmp_path: Path) -> None:
    _build(["--package", "deskgate-bcf"], tmp_path)
    noms = _membres(next(tmp_path.glob("*.tar.gz")))
    assert any(n.endswith("/LICENSE") for n in noms)
    assert any(n.endswith("/NOTICE") for n in noms)
    with zipfile.ZipFile(next(tmp_path.glob("*.whl"))) as z:
        meta = next(n for n in z.namelist() if n.endswith("METADATA"))
        assert "License-Expression: GPL-3.0-or-later" in z.read(meta).decode("utf-8")

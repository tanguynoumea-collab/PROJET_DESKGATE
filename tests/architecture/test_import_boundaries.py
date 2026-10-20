"""Frontières d'import : noyau pur, cœur sans BIM, frontière GPL, aucun `shell=True`."""

from __future__ import annotations

import ast
import pathlib
import sys
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.unit

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "deskgate"
FORBIDDEN_IN_CORE = {
    "sqlite3",
    "subprocess",
    "httpx2",
    "httpx",
    "fastapi",
    "starlette",
    "ctypes",
    "uvicorn",
}
FORBIDDEN_BIM = {"deskgate_bim", "ifcopenshell", "ifcclash", "bcf", "deskgate_bcf"}


def _imports(path: pathlib.Path) -> Iterator[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            yield from (a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            yield n.module.split(".")[0]


@pytest.mark.parametrize("py", sorted((SRC / "core").rglob("*.py")), ids=lambda p: p.name)
def test_core_est_pur(py: pathlib.Path) -> None:
    assert not (set(_imports(py)) & FORBIDDEN_IN_CORE)


def test_coeur_sans_bim() -> None:
    offenders = [py for py in SRC.rglob("*.py") if set(_imports(py)) & FORBIDDEN_BIM]
    assert not offenders, offenders


def test_frontiere_gpl() -> None:
    root = SRC.parents[1]
    allowed = root / "plugins" / "bim" / "bcf"
    offenders = []
    for py in root.rglob("*.py"):
        rel = py.relative_to(root).parts
        if any(part.startswith(".") for part in rel) or allowed in py.parents:
            continue
        if {"bcf", "deskgate_bcf"} & set(_imports(py)):
            offenders.append(py)
    assert not offenders, offenders


def test_aucun_shell_true() -> None:
    offenders = []
    for py in SRC.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if (
                isinstance(n, ast.keyword)
                and n.arg == "shell"
                and isinstance(n.value, ast.Constant)
                and n.value.value is True
            ):
                offenders.append(py)
    assert not offenders, offenders


def _importeurs(module: str) -> set[str]:
    return {py.name for py in SRC.rglob("*.py") if module in set(_imports(py))}


def test_ctypes_seulement_dans_jobobject() -> None:
    assert _importeurs("ctypes") <= {"jobobject.py", "instance.py"}


def test_sqlite3_seulement_dans_store() -> None:
    assert _importeurs("sqlite3") <= {"store.py"}


def test_subprocess_seulement_dans_jobobject() -> None:
    assert _importeurs("subprocess") <= {"jobobject.py"}


SDK = SRC.parent / "deskgate_sdk"


@pytest.mark.parametrize("py", sorted(SDK.glob("*.py")), ids=lambda p: p.name)
def test_sdk_stdlib_seulement(py: pathlib.Path) -> None:
    assert set(_imports(py)) <= set(sys.stdlib_module_names) | {"__future__"}

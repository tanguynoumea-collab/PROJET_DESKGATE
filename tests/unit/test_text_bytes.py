"""Aucun retour chariot isolé dans les documents racine ni dans les chaînes des sources.

Verrouille la cause commune de LIVR-N2-002 (AGENTS.md) et MNT-N2-001 (runtime.py) : un « \r »
introduit par un échappement non brut. « \r\n » reste permis.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
CR_ISOLE = re.compile(rb"\r(?!\n)")
CR_ISOLE_TXT = re.compile(r"\r(?!\n)")
DOCS = [
    "AGENTS.md",
    "ARCHITECTURE.md",
    "README.md",
    "CLAUDE.md",
    "ROADMAP.md",
    "n8n/README.md",
    "plugins/bim/README.md",
    "scripts/recette/README.md",
]
IGNORES = {"__pycache__", "build", "dist", "node_modules"}


@pytest.mark.parametrize("doc", DOCS)
def test_agents_md_sans_retour_chariot_isole(doc: str) -> None:
    chemin = ROOT / doc
    if not chemin.exists():
        pytest.skip(f"{doc} absent")
    data = chemin.read_bytes()
    m = CR_ISOLE.search(data)
    ligne = data[: m.start()].count(b"\n") + 1 if m else 0
    assert m is None, f"{doc}:{ligne} contient un CR isolé"


def test_agents_md_ligne_code_6_cite_runner_log() -> None:
    lignes = (ROOT / "AGENTS.md").read_text(encoding="utf-8").splitlines()
    cible = [ln for ln in lignes if "Tâche planifiée en code 6" in ln]
    assert cible
    assert all("`logs\\runner.log`" in ln for ln in cible)


def test_sources_sans_retour_chariot_isole() -> None:
    fautifs: list[str] = []
    for base in ("src", "plugins", "scripts"):
        for p in (ROOT / base).rglob("*.py"):
            rel = p.relative_to(ROOT)
            if any(part.startswith(".") or part in IGNORES for part in rel.parts):
                continue
            tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
            for n in ast.walk(tree):
                if (
                    isinstance(n, ast.Constant)
                    and isinstance(n.value, str)
                    and CR_ISOLE_TXT.search(n.value)
                ):
                    fautifs.append(f"{rel}:{n.lineno}")
    assert fautifs == []

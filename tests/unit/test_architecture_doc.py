"""`ARCHITECTURE.md` sépare le livré v0.1 de la cible (DS-MAINT-1).

Chaque référence `fichier:ligne` de la section livrée doit exister.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
TITRE = "## État livré en v0.1"
ABSENT = "### Absent en v0.1 (cible)"
REF = re.compile(
    r"`(?P<path>[A-Za-z0-9_./-]+\.(?:py|toml|md|yml|yaml|json)):(?P<start>\d+)(?:-(?P<end>\d+))?`"
    r"(?P<anchor> \(`(?P<sym>[^`]+)`\))?"
)
MARQUES_CIBLE = ("cible v0.2", "cible v0.3", "cible v0.4", "cible (non planifiée)")


def _texte() -> str:
    return (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")


def _section(text: str) -> str:
    lignes = text.splitlines()
    assert TITRE in lignes, f"ARCHITECTURE.md ne contient pas la ligne « {TITRE} »"
    debut = lignes.index(TITRE) + 1
    fin = len(lignes)
    for i in range(debut, len(lignes)):
        if lignes[i].startswith("## "):
            fin = i
            break
    return "\n".join(lignes[debut:fin])


def _livre(section: str) -> str:
    return section.split(ABSENT)[0]


def _absent(section: str) -> str:
    assert ABSENT in section, f"la sous-section « {ABSENT} » est absente"
    return section.split(ABSENT, 1)[1]


def _puces(part: str) -> list[str]:
    puces: list[str] = []
    for ligne in part.splitlines():
        if ligne.startswith("- "):
            puces.append(ligne)
        elif ligne.startswith(" ") and ligne.strip() and puces:
            puces[-1] += "\n" + ligne
    return puces


def test_livre_section_en_tete() -> None:
    text = _texte()
    lignes = text.splitlines()
    assert TITRE in lignes, f"la section « {TITRE} » est absente"
    assert lignes.index(TITRE) < lignes.index("## 0. Périmètre")


def test_livre_references_existent() -> None:
    section = _livre(_section(_texte()))
    refs = list(REF.finditer(section))
    assert len(refs) >= 15, f"{len(refs)} références seulement, 15 attendues"
    for m in refs:
        ref = m.group(0)
        fichier = ROOT / m["path"]
        assert fichier.is_file(), f"référence {ref} : fichier absent"
        lignes = fichier.read_text(encoding="utf-8").splitlines()
        debut = int(m["start"])
        fin = int(m["end"] or debut)
        assert 1 <= debut <= fin <= len(lignes), f"référence {ref} : ligne hors du fichier"
        if m["sym"] is None:
            continue
        zone = "\n".join(lignes[max(0, debut - 3) : fin + 2])
        assert m["sym"] in zone, (
            f"référence {ref} : le symbole {m['sym']!r} est absent de ces lignes (±2)"
        )


def test_livre_chaque_puce_reference() -> None:
    puces = _puces(_livre(_section(_texte())))
    assert puces, "la partie livrée n'a aucune puce"
    for puce in puces:
        assert REF.search(puce), f"puce sans référence fichier:ligne : {puce.splitlines()[0]}"


def test_reference_sans_symbole_refusee() -> None:
    section = _section(_texte())
    for m in REF.finditer(section):
        assert m["anchor"], f"référence {m.group(0)} sans symbole « (`…`) »"


def test_livre_sans_cible() -> None:
    livre = _livre(_section(_texte()))
    for interdit in (
        "/capabilities",
        "/ui",
        "plugin.yaml",
        "mcp_servers.toml",
        "par ressource",
        "`cli`",
    ):
        assert interdit not in livre, f"la partie livrée mentionne {interdit!r}, qui est une cible"


def test_absent_marque_cible() -> None:
    absent = _absent(_section(_texte()))
    for attendu in (
        "/capabilities",
        "/ui",
        "`cli`",
        "plugin.yaml",
        "n8n-nodes-deskgate",
        "Streamable HTTP",
    ):
        assert attendu in absent, f"la sous-section Absent ne mentionne pas {attendu!r}"
    for puce in _puces(absent):
        assert any(m in puce for m in MARQUES_CIBLE), (
            f"puce Absent sans version cible : {puce.splitlines()[0]}"
        )


def test_livre_contrat_data() -> None:
    livre = _livre(_section(_texte()))
    for attendu in (
        "data.json",
        "summary.json",
        "deskgate purge",
        '{"purged": true}',
        "NaN",
        "internal_error",
    ):
        assert attendu in livre, f"la partie livrée ne documente pas {attendu!r}"


def test_cible_reste_du_document() -> None:
    text = _texte()
    section = TITRE + "\n" + _section(text)
    reste = text.replace(section, "")
    assert "OpenAPI générée" not in reste
    for ligne in reste.splitlines():
        if any(k in ligne for k in ("/capabilities", "/ui", "plugin.yaml", "n8n-nodes-deskgate")):
            assert "cible" in ligne or "v0.2" in ligne or "v0.3" in ligne, (
                f"ligne de cible non marquée : {ligne.strip()}"
            )


def test_readme_sans_ligne_de_commande() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "ligne de commande, MCP" not in readme


def test_contrat_marqueurs_documente() -> None:
    arch = " ".join(_texte().split())
    n8n = " ".join((ROOT / "n8n" / "README.md").read_text(encoding="utf-8").split())
    changelog = " ".join((ROOT / "CHANGELOG.md").read_text(encoding="utf-8").split())
    assert '"artifact": "mcp_result"' in arch
    assert "sauf une valeur déjà réduite à un marqueur de repli" in arch
    assert '"artifact": "mcp_result"' in n8n and "renvoi minimal" in n8n
    assert "DS2-2" in changelog
    for nom, texte in (("ARCHITECTURE.md", arch), ("CHANGELOG.md", changelog)):
        assert "le renvoi minimal marque" not in texte, f"{nom} : ancien contrat du renvoi minimal"

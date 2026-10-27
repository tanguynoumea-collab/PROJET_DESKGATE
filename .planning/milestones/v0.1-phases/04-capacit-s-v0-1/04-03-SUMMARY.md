---
phase: 04-capacit-s-v0-1
plan: 03
subsystem: bim-bcf
tags: [bcf, gpl, cli, jsonschema, bcf-client]
requires: [04-01]
provides:
  - deskgate-bcf write --input in.json --output out.bcf (codes 0/2/3, stdout vide)
  - writer.write(doc, out) : BCF 2.1 à deux points de vue par sujet, sans sélection
  - sonde de relecture tests/envside/read_bcf.py (BcfXml.load)
affects: [04-07]
tech-stack:
  added: []
  patterns: [écriture atomique par fichier .tmp.bcf puis os.replace, GUID de vues en UUID v5, stderr forcé en UTF-8]
key-files:
  created:
    - plugins/bim/bcf/src/deskgate_bcf/writer.py
    - plugins/bim/bcf/src/deskgate_bcf/cli.py
    - plugins/bim/bcf/tests/envside/read_bcf.py
    - plugins/bim/bcf/tests/conftest.py
    - plugins/bim/bcf/tests/test_bcf_cli.py
    - plugins/bim/bcf/tests/test_bcf_content.py
  modified: []
key-decisions:
  - "stderr du CLI reconfiguré en UTF-8 : les appelants (tests, ifc.clash) le décodent ainsi, la page de code Windows donnerait des octets cp1252"
  - "Le helper d'écriture des tests est une fixture (ecrire) et non un import de conftest, à cause de --import-mode=importlib"
requirements-completed: [CAP-05]
duration: 30min
completed: 2026-10-20
---

# Phase 4 Plan 03 : deskgate-bcf Summary

CLI GPL `deskgate-bcf write` : valide un JSON `bcf-write-v1` (jsonschema 2020-12) et écrit un BCF 2.1 relu par `BcfXml.load`, deux points de vue par sujet (objets seuls, puis contexte `40B0B0B0`), ARGB, aucune sélection, GUID déterministes.

## Réalisé

- `writer.py` : code vérifié de la recherche, GUID dédoublonnés et triés (XML stables), écriture dans `<nom>.tmp.bcf` puis `os.replace`, nettoyage du temporaire en cas d'erreur.
- `cli.py` : sous-commande `write`, codes 0 / 2 (JSON illisible, invalide, `schema_version` inconnue, non conforme, usage argparse) / 3 (dossier de sortie absent, écriture impossible), messages français sur stderr, rien sur stdout.
- 12 tests (marqueur `bim`) lancés via `deskgate-bcf.exe` de l'env bcf : relecture BcfXml.load, vues, couleurs, absence de `Selection`, membres identiques sur deux écritures, tous les cas d'erreur.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] stderr en cp1252 sous Windows**
- **Found during:** Tâche 1 (vérification)
- **Issue :** les messages accentués sortaient en cp1252, non décodables en UTF-8 par l'appelant (UnicodeDecodeError).
- **Fix :** `sys.stderr.reconfigure(encoding="utf-8")` dans `_err`.
- **Files modified :** cli.py
- **Commit :** 7e3355e

**2. [Rule 3 - Blocking] Helper `ecrire` en fixture**
- **Issue :** `--import-mode=importlib` interdit `from conftest import ecrire`.
- **Fix :** `ecrire` est une fixture qui renvoie la fonction ; même comportement.
- **Commit :** 4888ba8

Incident local : un `uv sync --package deskgate-bcf` lancé sans `UV_PROJECT_ENVIRONMENT` a installé bcf-client dans le `.venv` de dev (2 tests de licence ont échoué) ; rétabli par `uv sync --locked`. Aucun fichier du dépôt concerné.

## Vérifications

`uv run pytest -m "not e2e"` : 532 passés, 1 ignoré (lien symbolique) ; ruff check, ruff format, pyright verts.

## Known Stubs

Aucun.

## Notes pour les plans suivants

CAP-02 reste en attente : la forme BCF est prouvée, `ifc.clash` (04-07) doit encore produire le JSON et appeler `deskgate-bcf.exe` par chemin absolu.

## Self-Check: PASSED

Fichiers créés présents ; commits 7e3355e et 4888ba8 présents.

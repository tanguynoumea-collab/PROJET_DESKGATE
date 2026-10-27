---
phase: 04-capacit-s-v0-1
plan: 01
subsystem: infra
tags: [uv-workspace, gpl-boundary, json-schema, licences, sdist]
requires: []
provides:
  - workspace uv à trois paquets (deskgate, deskgate-bim MIT, deskgate-bcf GPL-3.0-or-later)
  - contrat docs/contrats/bcf-write-v1.json et ses deux copies identiques
  - fixture plugin_envs (environnements uv des plugins)
  - garde-fous CI de la frontière GPL (AST, licences, sdist, égalité du contrat)
affects: [04-02, 04-03, 04-04, 04-05, 04-07]
tech-stack:
  added: [mcp>=2.3, ifcopenshell 0.9.0.post1 (plugin), ifcclash 0.9.0 (plugin), bcf-client 0.9.0 (plugin GPL), jsonschema]
  patterns: [environnements uv de plugins dans .cache/plugin-envs, contrat JSON dupliqué sans import croisé]
key-files:
  created:
    - docs/contrats/bcf-write-v1.json
    - docs/contrats/README.md
    - plugins/bim/pyproject.toml
    - plugins/bim/bcf/pyproject.toml
    - plugins/bim/bcf/LICENSE
    - plugins/bim/bcf/NOTICE
    - tests/_support/plugin_envs.py
    - tests/plugins/
  modified: [pyproject.toml, uv.lock, .gitignore, tests/architecture/test_import_boundaries.py]
key-decisions:
  - "Échec de uv sync d'un plugin = pytest.fail (pas de skip silencieux)"
duration: 25min
completed: 2026-10-20
---

# Phase 4 Plan 01: Workspace uv et frontière GPL Summary

Workspace uv à trois paquets avec contrat JSON `bcf-write-v1` figé en trois copies identiques, et garde-fous CI de la frontière GPL (AST, licences par environnement, sdist) en place avant tout code GPL.

## Tâches

| Tâche | Commit | Contenu |
|---|---|---|
| 1 | 9874bf5 | Workspace, pyproject des plugins, LICENSE/NOTICE, contrat et copies, `mcp` du coeur |
| 2 | a2d75fa | `plugin_envs`, sonde de licences, tests contrat, sdist, env bim sans bcf |
| 3 | fb603fb | Tests AST : pas d'export BCF d'ifcclash, plugin autonome, `mcp` seulement dans le worker |

## Vérification

- `uv lock --check` et `uv sync --locked` verts ; l'env de dev ne contient ni ifcopenshell ni bcf-client.
- `pytest -m "not e2e"` : 491 passés, 1 sauté (lien symbolique, privilège absent) ; ruff et pyright verts.
- Environnements de plugins construits dans `.cache/plugin-envs/py314/{bim,bcf}`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Échappement du motif `created_at` du contrat**
- **Found during:** Tâche 2 (test_schema_version_1)
- **Issue:** `\.` écrit à la place de `\\.` dans le JSON (invalide), copié dans les trois fichiers ; détecté par le test de chargement.
- **Fix:** `\\.` rétabli dans les trois copies.
- **Commit:** a2d75fa

**2. [Rule 3 - Lint] Ordre d'imports ruff** : `_support` est traité comme première partie ; imports réordonnés (`ruff check --fix`).

## Known Stubs

Aucun. `deskgate_bcf.cli` (cible du script `deskgate-bcf`) est créé par 04-03, comme prévu au plan.

## Notes

- Requirement CAP-05 : seule la partie frontière est couverte ici ; laissé en attente.

## Self-Check: PASSED

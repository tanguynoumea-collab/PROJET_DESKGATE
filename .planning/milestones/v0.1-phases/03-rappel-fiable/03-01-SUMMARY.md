---
phase: 03-rappel-fiable
plan: 01
subsystem: callback-foundations
tags: [httpx2, config, fake-n8n, tests]
requires: []
provides:
  - httpx2 en dépendance d'exécution (uv.lock régénéré)
  - CallbackConfig, RunnerConfig.callback, hôtes par défaut localhost et 127.0.0.1
  - CALLBACK_HOST_NOT_ALLOWED
  - tests/_support/fake_n8n.py et fixture fake_n8n
affects: [03-05, 03-06, 03-07, 03-08]
tech-stack:
  added: [httpx2 (runtime)]
  patterns: [faux serveur stdlib dans un thread, règle d'architecture par import]
key-files:
  created: [tests/_support/fake_n8n.py, tests/fs/test_fake_n8n.py]
  modified: [pyproject.toml, uv.lock, src/deskgate/core/config.py, src/deskgate/core/errors.py, src/deskgate/runner.example.toml, tests/conftest.py, tests/unit/test_config.py, tests/unit/test_locations.py, tests/architecture/test_import_boundaries.py]
decisions:
  - "Field(default=...) nommé pour les entiers de CallbackConfig (pyright refuse le défaut positionnel)"
metrics:
  tasks: 2
  completed: 2026-10-20
---

# Phase 3 Plan 01: Fondations du rappel Summary

httpx2 en dépendance d'exécution, table `[callback]` validée, hôtes de rappel par défaut, et faux n8n 2.43.8 prouvant que httpx2 envoie la query de la resumeUrl octet pour octet.

## Tâches

1. Dépendance, configuration, code d'erreur, règle d'architecture : `8f3792c`
2. Faux n8n, fixture, tests fs : `20fb0db`

## Vérification

`uv sync --locked`, `pytest -m "unit or fs"` (292 réussis, 1 sauté : privilège de lien symbolique), ruff check, ruff format --check et pyright : verts.

## Deviations from Plan

**1. [Rule 1 - Bug] pyright : défaut positionnel de Field**
- **Found during:** Tâche 2 (vérification pyright)
- **Fix:** `Field(default=86400, ...)` et `Field(default=300, ...)`, plus `cast` pour le serveur du gestionnaire du faux n8n.
- **Commit:** 20fb0db

## Known Stubs

Aucun.

## Self-Check: PASSED

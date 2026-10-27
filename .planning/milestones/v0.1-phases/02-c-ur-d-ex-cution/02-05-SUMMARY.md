---
phase: 02-c-ur-d-ex-cution
plan: 05
subsystem: worker-sdk
tags: [worker, sdk, stdlib, job-object, fake-plugins]
requires: ["02-02", "02-04"]
provides:
  - "deskgate_sdk.run : worker mono-fichier stdlib (Ctx, main, CONTRACT dupliqué)"
  - "tests/fake_plugins/deskgate_fakes.py : 8 faux plugins"
affects: ["02-06", "02-08", "02-09"]
tech-stack:
  added: []
  patterns: ["contrat de fichiers dupliqué en littéral", "écriture atomique .tmp + fsync + os.replace avec réessais"]
key-files:
  created:
    - src/deskgate_sdk/__init__.py
    - src/deskgate_sdk/run.py
    - tests/fake_plugins/deskgate_fakes.py
    - tests/unit/test_sdk_contract.py
    - tests/proc/test_sdk_worker.py
  modified:
    - pyproject.toml
    - tests/architecture/test_import_boundaries.py
key-decisions:
  - "Le worker retourne 1 sur exception et écrit result.json ok:false ; ctx.log va sur stderr (job.log)"
requirements-completed: []
duration: 10min
completed: 2026-10-20
---

# Phase 2 Plan 05 : Worker SDK Summary

Worker `deskgate_sdk/run.py` (stdlib seule, lancé par chemin) empaqueté dans la même wheel, contrat dupliqué vérifié égal à `core.worker_protocol.CONTRACT`, et faux plugins de test validés en vrai sous-processus dans un Job Object.

## Tâches

1. Worker, empaquetage, contrat et test AST stdlib : `a09512d`
2. Faux plugins et tests `proc` du worker : `b5755b9`

## Vérifications

- `uv run pytest -m "not e2e"` : 258 passés, 1 ignoré (lien symbolique sans privilège, préexistant)
- ruff check / format, pyright : propres ; `uv sync --locked` OK ; la wheel contient `deskgate_sdk/run.py`
- uv.lock inchangé (aucune dépendance ajoutée)

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

Requirements JOB-07 et JOB-09 laissés en attente : ils se complètent avec le plan 02-09.

## Self-Check: PASSED

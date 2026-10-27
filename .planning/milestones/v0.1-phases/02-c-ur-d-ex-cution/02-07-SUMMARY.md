---
phase: 02-c-ur-d-ex-cution
plan: 07
subsystem: api
tags: [api, jobs, fastapi, lifespan, logs]
requires: ["02-01", "02-02", "02-03"]
provides:
  - "deskgate.jobs : JobsService(submit, get, cancel, read_logs), job_view"
  - "api.routes_jobs : POST /jobs (202), GET /jobs/{id}, GET /jobs/{id}/logs, POST /jobs/{id}/cancel"
  - "create_app(..., jobs=None, on_shutdown=None) avec lifespan d'arrêt"
affects: ["02-08", "02-09"]
tech-stack:
  added: []
  patterns: ["routes def synchrones, une connexion SQLite par appel", "réveil de l'engine injecté (wake)", "JobRequestError rendu au format D-08 par un gestionnaire"]
key-files:
  created:
    - src/deskgate/jobs.py
    - src/deskgate/api/routes_jobs.py
    - tests/fs/test_routes_jobs.py
  modified:
    - src/deskgate/api/app.py
    - src/deskgate/api/handlers.py
key-decisions:
  - "Sans `jobs`, create_app n'enregistre aucune route /jobs : les tests de phase 1 restent inchangés"
  - "on_shutdown s'exécute après le yield du lifespan, seule voie exécutée sur CTRL_BREAK"
  - "Les tests réutilisent make_config de tests/_support/jobs.py (non modifié)"
requirements-completed: []
duration: 15min
completed: 2026-10-20
---

# Phase 2 Plan 07 : API des tâches Summary

`JobsService` et quatre routes /jobs (202 immédiat, suivi, journaux par offset ou tail avec masquage de `signature=`, annulation idempotente), erreurs D-08 (404, 409 avec job_id, 422), `callback.url` jamais renvoyée, et `create_app` branché sur un lifespan d'arrêt.

## Tâches

Les deux tâches (service, puis routes et lifespan) ont été validées par le même fichier de tests : un seul commit.

1. Service, routes, gestionnaire d'erreurs, lifespan : `0ffbdf1`

## Vérifications

- `tests/fs/test_routes_jobs.py` : 19 tests verts ; suite `not e2e` : 295 passés, 1 ignoré (lien symbolique, privilège absent) ; e2e serve : 8 verts
- ruff (check et format) et pyright : propres

## Deviations from Plan

None - plan executed exactly as written (commit unique pour les deux tâches).

## Requirements

JOB-01, JOB-03, JOB-04, JOB-08 laissés Pending : ils se complètent avec le plan 02-09 (branchement de bout en bout).

## Known Stubs

None.

## Self-Check: PASSED

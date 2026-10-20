---
phase: 02-c-ur-d-ex-cution
plan: 04
subsystem: process
tags: [ctypes, job-object, env-allowlist, subprocess]
requires: []
provides:
  - "jobobject : JobHandle (terminate, active_processes, close idempotent), create_job(memory_mb), spawn_in_job"
  - "core/env : ENV_ALLOWLIST, build_env (pur, PYTHONUTF8=1 imposé)"
  - "tests/_support/procs : is_alive, wait_dead"
  - "Tests AST : ctypes, sqlite3 et subprocess confinés"
affects: [02-05, 02-06]
tech-stack:
  added: []
  patterns: ["lancement suspendu, assignation, NtResumeProcess", "sortie vers job.log sans tube"]
key-files:
  created:
    - src/deskgate/jobobject.py
    - src/deskgate/core/env.py
    - tests/_support/procs.py
    - tests/unit/test_env.py
    - tests/proc/test_jobobject.py
  modified:
    - tests/proc/test_spike_jobobject.py
    - tests/architecture/test_import_boundaries.py
  removed:
    - tests/_support/winjob.py
key-decisions:
  - "ActiveProcesses lu avec une attente bornée (5 s) après une sortie normale : le décompte est en retard de quelques ms (lanceur de venv)"
requirements-completed: []
duration: 15min
completed: 2026-10-20
---

# Phase 2 Plan 04: Job Object de production Summary

`spawn_in_job` (suspendu, assigné à un Job KILL_ON_JOB_CLOSE sans BREAKAWAY_OK, repris par NtResumeProcess, sans shell, sortie dans `job.log`) et `build_env` en liste blanche avec `PYTHONUTF8=1`, validés avec de vrais sous-processus (orphelin tué, plafond mémoire, UTF-8, secret absent).

## Tâches

1. build_env et module jobobject : commit 8ac8423
2. winjob retiré, procs.py, frontières AST : commit 3b0b93c

## Vérification

pytest hors e2e : 249 réussis, 1 ignoré (lien symbolique sans privilège) ; ruff, ruff format et pyright propres.

## Deviations from Plan

**1. [Rule 1 - Bug] ActiveProcesses non nul juste après la sortie du parent**
- **Found during:** tâche 1 (test UTF-8)
- **Issue :** `active_processes()` renvoyait 1 immédiatement après `p.wait()`.
- **Fix :** test avec attente bornée jusqu'à 0 (`_vide`).
- **Commit :** 8ac8423

**2. Test du petit-enfant** : le plan attendait `p.wait(5) == 1` ; le parent étant déjà sorti (code 0), le test vérifie 0.

## Requirements

JOB-05, JOB-07 : brique posée, exigences complètes seulement avec le plan 02-09 ; laissées en attente.

## Known Stubs

None.

## Self-Check: PASSED

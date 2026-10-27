---
phase: 02-c-ur-d-ex-cution
plan: 08
subsystem: tests
tags: [engine, proc, job-object, timeout, cancel, artifacts]
requires: ["02-05", "02-06"]
provides:
  - "tests/proc/conftest.py : fixture real_engine (vrai launcher, Job Object, worker SDK)"
  - "Preuves réelles JOB-04, JOB-05, JOB-07, JOB-09 : verdicts, délai avec orphelin, annulation"
affects: ["02-09"]
tech-stack:
  added: []
  patterns: ["engine piloté par tick() dans le test, poll=0.05 et grace=1.0", "mort de processus attendue par wait_dead, jamais par sleep fixe"]
key-files:
  created:
    - tests/proc/conftest.py
    - tests/proc/test_engine_results.py
    - tests/proc/test_engine_timeout.py
    - tests/proc/test_engine_cancel.py
  modified: []
key-decisions:
  - "Aucun écart de l'engine révélé : src/deskgate/engine.py inchangé"
requirements-completed: []
duration: 15min
completed: 2026-10-20
---

# Phase 2 Plan 08 : Engine avec vrais sous-processus Summary

L'engine est prouvé avec de vrais sous-processus dans un Job Object : verdicts et artefacts (chemin conteneur `/data/travail/<id>/sortie.txt`), délai qui tue le plugin et son petit-enfant orphelin, annulation coopérative puis forcée après la grâce, annulation d'une tâche en file sans création de work_dir.

## Tâches

1. Fixture `real_engine` et tests de résultats (12 tests : artifact_ok, progression et journal, artifact_outside, bad_result x4, fail, exit_code, chatty 4 Mio, spawn_failed puis tâche suivante, ordre et exclusivité) : `d8d93d8`
2. Délai (arbre tué, orphelin laissé par une sortie normale tué, plugin hors du processus du runner) et annulation (coopérative < 3 s, forcée 1 à 5 s, en file) : `3dcdb0d` (inclut le tri d'imports ruff des fichiers de la tâche 1)

## Vérifications

- `uv run pytest -m "not e2e"` : 313 passés, 1 ignoré (lien symbolique, privilège absent) ; `proc` vert
- ruff (check et format) et pyright : propres
- Aucun processus Python résiduel de Deskgate après la suite (seuls des processus Jarvis, étrangers au plan)

## Deviations from Plan

None - plan executed exactly as written. Aucun correctif de `engine.py` n'a été nécessaire.

## Requirements

JOB-04, JOB-05, JOB-07, JOB-09 laissés Pending : ils se complètent avec le plan 02-09 (branchement de bout en bout).

## Known Stubs

None.

## Self-Check: PASSED

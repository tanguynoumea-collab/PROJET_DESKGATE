---
phase: 02-c-ur-d-ex-cution
plan: 02
subsystem: core
tags: [pure-core, states, outcome, worker-protocol, pydantic]
requires: []
provides:
  - "core/states : statuts, TERMINAL, Observation, Decision, step()"
  - "core/outcome : Verdict, verdict(), kill_verdict(), codes d'erreur stables, RESTART_MESSAGE"
  - "core/worker_protocol : WorkerInput, ProgressEvent, ArtifactEvent, ResultOk, ResultError, parse_event, parse_result, CONTRACT"
affects: [02-05, 02-06]
tech-stack:
  added: []
  patterns: ["fonctions pures testées par table, sans sleep", "modèles Pydantic extra=forbid"]
key-files:
  created:
    - src/deskgate/core/states.py
    - src/deskgate/core/outcome.py
    - src/deskgate/core/worker_protocol.py
    - tests/unit/test_states.py
    - tests/unit/test_outcome.py
    - tests/unit/test_worker_protocol.py
  modified: []
key-decisions:
  - "step : ordre sortie, annulation, échéance ; l'annulation l'emporte pendant la grâce"
  - "verdict : priorité plugin_error, too_large, invalid, missing (nonzero_exit si code ≠ 0), code ≠ 0, artefacts"
requirements-completed: []
duration: 10min
completed: 2026-10-20
---

# Phase 2 Plan 02: Noyau pur d'exécution Summary

Décision d'un tour d'engine (`step`), verdict terminal (`verdict`, `kill_verdict`) et contrat de fichiers runner/worker (`CONTRACT`, `parse_event`, `parse_result`) en fonctions pures, courses délai/fin et annulation/grâce figées par tests paramétrés.

## Tâches

1. step() et verdict() par table : RED b5100e9, GREEN eacf8dd
2. Contrat worker_protocol : RED 253a16e, GREEN 82c963b

## Vérification

pytest complet : 228 réussis, 1 ignoré (lien symbolique sans privilège) ; ruff, ruff format et pyright propres ; tests d'architecture (noyau pur) verts.

## Deviations from Plan

None - plan executed exactly as written. (Un correctif de lint SIM300 dans un test, intégré au commit GREEN de la tâche 2.)

## Requirements

JOB-04, JOB-05, JOB-07 : noyau posé, exigences complètes seulement avec le plan 02-09 ; laissées en attente.

## Known Stubs

None.

## Self-Check: PASSED

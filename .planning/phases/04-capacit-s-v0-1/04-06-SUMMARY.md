---
phase: 04-capacit-s-v0-1
plan: 06
subsystem: engine
tags: [job-object, memory, outcome, windows]
requires:
  - phase: 04-02
    provides: engine avec JobLike et _Running
provides:
  - "memory_limit : échec au plafond mémoire classé par l'engine"
  - "JobHandle.peak_memory() (PeakJobMemoryUsed)"
affects: [04-07]
tech-stack:
  added: []
  patterns: ["pic mémoire lu avant l'arrêt du Job, verdict pur requalifié"]
key-files:
  created: [tests/fs/test_engine_memory.py, tests/proc/test_engine_memory.py]
  modified:
    - src/deskgate/core/outcome.py
    - src/deskgate/jobobject.py
    - src/deskgate/engine.py
    - tests/_support/jobs.py
    - tests/fake_plugins/deskgate_fakes.py
    - tests/unit/test_outcome.py
key-decisions:
  - "Le pic n'est lu que si la capacité déclare memory_mb ; toute erreur de lecture donne None (verdict inchangé)"
patterns-established:
  - "verdict(memory_limit_mb=...) n'est appelé avec une valeur que si memory_exhausted() est vrai"
requirements-completed: [CAP-01]
duration: 20min
completed: 2026-10-20
---

# Phase 4 Plan 06: Classement memory_limit Summary

**L'engine lit PeakJobMemoryUsed du Job avant de le tuer et classe en `memory_limit` (message français avec le plafond) tout échec survenu à au moins 95 % de `memory_mb`.**

## Accomplishments
- `core/outcome.py` : `MEMORY_LIMIT`, `memory_exhausted`, `verdict(..., memory_limit_mb=None)` ; les succès ne sont jamais requalifiés.
- `JobHandle.peak_memory()` ; `JobLike.peak_memory`, `_Running.memory_mb`, `Engine._peak` (tolérant aux erreurs).
- Tests unit, fs (faux Job : pic haut, bas, illisible, sans memory_mb) et proc (vrai Job à 200 Mo : MemoryError, sortie brutale 3221225477, arrêt avant plafond, pic réel ≥ 50 Mio).

## Task Commits
1. Tâche 1 : 1427800 (feat)
2. Tâche 2 : 4b2771e (test)

## Deviations from Plan
None - plan exécuté comme écrit. Le plafond de 200 Mo suffit au démarrage de l'interpréteur (pas besoin de 300 Mo). CAP-01 était déjà Complete : inchangé.

## Verification
`pytest -m "not e2e"` : 598 passed, 1 skipped ; `pytest -m e2e` : 26 passed ; ruff check, ruff format --check, pyright verts.

## Known Stubs
None.

## Self-Check: PASSED

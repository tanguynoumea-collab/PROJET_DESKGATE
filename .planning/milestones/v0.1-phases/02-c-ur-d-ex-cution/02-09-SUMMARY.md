---
phase: 02-c-ur-d-ex-cution
plan: 09
subsystem: runtime
tags: [serve, recovery, engine, lifespan, e2e, taskkill, ctrl-break]
requires: ["02-06", "02-07", "02-08"]
provides:
  - "deskgate serve : config, mutex, socket, base (migration), recovery, engine, Uvicorn"
  - "Preuves e2e par HTTP réel : flux nominal, redémarrage après taskkill /F /T, arrêt propre CTRL_BREAK"
affects: []
tech-stack:
  added: []
  patterns: ["arrêt de l'engine par le lifespan (voie CTRL_BREAK) et par le finally (KeyboardInterrupt)", "engine.stop idempotent"]
key-files:
  created:
    - tests/e2e/test_jobs_flow.py
    - tests/e2e/test_jobs_restart.py
    - tests/e2e/test_jobs_shutdown.py
  modified:
    - src/deskgate/runtime.py
    - src/deskgate/engine.py
    - tests/e2e/conftest.py
    - tests/e2e/test_serve.py
key-decisions:
  - "Le battement de l'engine n'est pas exposé dans /health en phase 2 (discrétion)"
  - "JOB-06 : transition interrupted et ligne callbacks pending prouvées ; l'envoi du rappel est la phase 3 (décision utilisateur)"
requirements-completed: [JOB-01, JOB-02, JOB-03, JOB-04, JOB-05, JOB-06, JOB-07, JOB-08, JOB-09]
duration: 40min
completed: 2026-10-20
---

# Phase 2 Plan 09 : Assemblage de serve et preuves e2e Summary

`deskgate serve` démarre désormais recovery, thread engine et API des tâches, et un runner réel en sous-processus prouve le flux nominal, le passage `running` vers `interrupted` après `taskkill /F /T` (plugin et petit-enfant morts) et l'arrêt propre par CTRL_BREAK via le lifespan.

## Tâches

1. Câblage de `runtime.serve` (commits `a1d36a7`, correctif d'imports `style(02-09)`) : `open_db` (code 5 si `SchemaTooNew`), `recover_interrupted` avant `engine.start()`, `Engine`, `JobsService(wake=engine.wake)`, `create_app(..., on_shutdown=engine.stop)`, `on_fatal` qui lève `should_exit`. `Engine.stop` est idempotent et journalise « Engine arrêté. ».
2. et 3. Aides e2e (`api`, `wait_status`, `jobs_runner`, `FAKE_CAPS`, `write_config(capabilities=...)`) et trois fichiers de tests (commit `df43de0`) : 6 + 1 + 1 tests.

## Deviations from Plan

**1. [Rule 1 - Bug] test_serve.py de phase 1 devenu obsolète**
- `GET /jobs` renvoie désormais 405 (la route existe) ; le test de route protégée utilise `/inconnue` (401 sans jeton, 404 avec).
- `test_second_runner_code_3` comparait la liste des fichiers du dossier de données ; l'engine du premier runner crée `-wal`/`-shm` à son rythme. La comparaison ignore ces fichiers annexes (la contrainte « mtime de la base inchangé » est conservée).
- Fichiers : `tests/e2e/test_serve.py`. Commit `a1d36a7`.

Aucun autre écart.

## Requirements

JOB-01 à JOB-09 marqués complets (JOB-05/07 par 02-08, JOB-02/09 aussi par e2e). JOB-06 : l'envoi du rappel est couvert en phase 3 ; ici sont prouvées la transition `interrupted` (`runner_restarted`), la ligne `callbacks` `pending` unique et l'audit `job.interrupted`.

## Gate D-12 (résultats)

- `uv sync --locked` : 0
- `uv run ruff check` : All checks passed
- `uv run ruff format --check` : 78 files already formatted
- `uv run pyright` : 0 errors, 0 warnings
- `uv run pytest -m "not e2e" -q` : 313 passed, 1 skipped (lien symbolique, mode développeur désactivé), 16 deselected
- `uv run pytest -m e2e -q` : 16 passed
- `uv build --all-packages` : 0 (sdist et wheel de deskgate construits)

Aucun processus Deskgate ou fake plugin résiduel après les tests (seuls des processus JARVIS étrangers tournent).

## Known Stubs

Aucun.

## Self-Check: PASSED

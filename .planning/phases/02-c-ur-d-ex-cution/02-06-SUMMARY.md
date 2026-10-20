---
phase: 02-c-ur-d-ex-cution
plan: 06
subsystem: engine
tags: [engine, thread, job-object, tick, cancel, timeout]
requires: ["02-01", "02-02", "02-03", "02-04"]
provides:
  - "deskgate.engine : Engine(tick, run, start, stop, wake), LaunchSpec, Launcher, default_launcher"
  - "tests/_support/jobs.py : make_config, submit, get, run_until_terminal, FakeClock, FakeLauncher, FakeJob, FakeProc"
affects: ["02-07", "02-08", "02-09"]
tech-stack:
  added: []
  patterns: ["tour d'engine pur et testable (launcher et horloges injectés)", "décision par core.states.step, effets confinés à store/jobobject/engine"]
key-files:
  created:
    - src/deskgate/engine.py
    - tests/_support/jobs.py
    - tests/fs/test_engine_tick.py
  modified:
    - src/deskgate/store.py
key-decisions:
  - "store.Connection : alias de sqlite3.Connection, pour typer sans importer sqlite3 hors de store.py (test d'architecture)"
  - "stop() ne conclut jamais la tâche : la ligne reste running, la recovery fait le travail (un seul chemin)"
  - "Le battement last_tick_at existe mais n'est pas exposé dans /health en phase 2 (reporté à la phase 3)"
requirements-completed: []
duration: 25min
completed: 2026-10-20
---

# Phase 2 Plan 06 : Engine Summary

Thread `engine` à tour unique `tick()` (réclamation, lancement par le launcher, observation `poll` puis annulation puis échéance via `step()`, verdict, artefacts revalidés) avec boucle à réveil `run/start/stop/wake`, testé sans processus réel par 18 tests `fs`.

## Tâches

Les deux tâches (tick, puis annulation/échéance/boucle/arrêt) ont été écrites ensemble et validées par le même jeu de tests : un seul commit.

1. Tick, annulation, échéance, boucle, réveil, arrêt, aides de test : `891005b`

## Comportements vérifiés

- Ordre de soumission, une tâche à la fois, argv `[python, -X, utf8, worker, --input, input.json]`, environnement en liste blanche, `input.json` sans `callback_url`
- Progression lue par offset (ligne incomplète différée), une écriture par tour
- Artefact en chemin conteneur ; hors racines donne `artifact_outside_roots`
- `missing_result`, `plugin_error` (type dans le message), `result_too_large`, `spawn_failed` (OSError, capacité retirée), `engine_error` (exception de suivi, l'engine continue)
- Échéance puis `timeout` ; annulation avec grâce (`cancelled`), coopérative, annulation prioritaire sur échéance
- Réveil sous 1 s avec `poll=5.0` ; `stop()` laisse `running` ; erreur hors tâche : `on_fatal`

## Vérifications

- `uv run pytest -m "not e2e"` : 276 passés, 1 ignoré (lien symbolique sans privilège, préexistant)
- ruff check/format et pyright propres

## Deviations from Plan

**1. [Rule 3 - Blocage] Alias `store.Connection`**
- **Found during:** tâche 1
- **Issue :** l'engine doit typer la connexion mais le test d'architecture et le critère d'acceptation interdisent `import sqlite3` hors de `store.py`
- **Fix :** `Connection = sqlite3.Connection` dans `store.py`
- **Commit :** 891005b

## Known Stubs

None.

Requirements JOB-02, JOB-04, JOB-05, JOB-07, JOB-09 laissés en attente : ils se complètent avec le plan 02-09 (bout en bout).

## Self-Check: PASSED

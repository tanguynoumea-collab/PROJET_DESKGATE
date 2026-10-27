---
phase: 01-fondations-testables
plan: 05
subsystem: runtime
tags: [uvicorn, typer, mutex, socket-exclusif, e2e]
requires:
  - phase: 01-01
    provides: outillage uv, ruff, pyright, pytest
  - phase: 01-03
    provides: create_app, instance (mutex, bind exclusif)
  - phase: 01-04
    provides: load_config, locations
provides:
  - store.open_db (squelette WAL, seul importeur de sqlite3)
  - runtime.serve (ordre D-04, codes de sortie 2/3/4)
  - CLI Typer deskgate serve, deskgate dev-token (caché), python -m deskgate
  - tests e2e RUN-01..04 (sous-processus réels)
affects: [phase 2]
key-files:
  created:
    - src/deskgate/store.py
    - src/deskgate/runtime.py
    - src/deskgate/cli.py
    - src/deskgate/__main__.py
    - tests/unit/test_cli.py
    - tests/e2e/conftest.py
    - tests/e2e/test_serve.py
key-decisions:
  - "Uvicorn reçoit le socket pré-lié (server.run(sockets=[sock])), jamais host/port"
requirements-completed: [RUN-01, RUN-02, RUN-03, RUN-04]
duration: 25min
completed: 2026-10-20
---

# Phase 1 Plan 05 : Assemblage du runner Summary

`deskgate serve` démarre dans l'ordre configuration, mutex, socket exclusif, base, Uvicorn (socket pré-lié, thread principal), avec les codes de sortie 2 (configuration), 3 (instance déjà active), 4 (bind) ; huit tests e2e en sous-processus réels le prouvent.

## Commits
- dccf7a0 test(01-05): CLI et ordre de démarrage (RED)
- 41a7c1d feat(01-05): deskgate serve et dev-token (GREEN)
- 7afcb1e test(01-05): tests de bout en bout de deskgate serve

## Deviations from Plan
- [Rule 3] Ajout de `# noqa: S105/S106/S310` ciblés dans `tests/e2e` (jeton factice, http local) : la règle S de ruff n'était ignorée dans `tests/` que pour S101/S603/S607. Aucun changement de configuration ruff.
- Le test `test_ecoute_loopback_seulement` s'est exécuté (non skippé) : une IP LAN est disponible.

## Gate D-12 (Python 3.14.4 via UV_PYTHON)
- `uv sync --locked` : exit 0 (36 paquets résolus, 35 vérifiés)
- `uv run ruff check` : All checks passed
- `uv run ruff format --check` : 43 files already formatted
- `uv run pyright` : 0 errors, 0 warnings
- `uv run pytest -m "not e2e"` : 159 passed, 1 skipped (lien symbolique, privilège absent), 8 deselected
- `uv build --all-packages` : sdist et wheel `deskgate-0.1.0.dev0` construits
- `uv run pytest -m e2e` : 8 passed (~21 s)

Processus : tous les runners e2e tués par `taskkill /F /T` ; aucun processus deskgate résiduel (les python.exe restants appartiennent à PROJET JARVIS).

## Known Stubs
Aucun. Le commentaire « phase 2 : recovery, engine, sender » dans `runtime.py` est un emplacement documenté prévu par le plan.

## Self-Check: PASSED

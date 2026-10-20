---
phase: 01-fondations-testables
plan: 01
subsystem: infra
tags: [uv, ruff, pyright, pytest, ctypes, mutex, socket, job-object, ci]
requires: []
provides:
  - Outillage de gate D-12 (uv, ruff, pyright, pytest, build, CI windows-latest)
  - src/deskgate/instance.py (acquire_mutex, bind_exclusive, describe_bind_error)
  - Fixtures de test et tests AST de frontière
  - Helper de test tests/_support/winjob.py
affects: [01-02, 01-03, 01-04, 01-05, phase-2]
tech-stack:
  added: [fastapi, uvicorn, pydantic, platformdirs, typer, pytest, pytest-timeout, httpx2, psutil, ruff, pyright, hatchling]
  patterns: [noyau pur vérifié par AST, mutex nommé puis bind exclusif, tests proc avec taskkill /T]
key-files:
  created: [pyproject.toml, uv.lock, .gitignore, .github/workflows/ci.yml, src/deskgate/__init__.py, src/deskgate/core/__init__.py, src/deskgate/instance.py, tests/conftest.py, tests/_support/winjob.py, tests/architecture/test_import_boundaries.py, tests/unit/test_instance_socket.py, tests/proc/test_mutex.py, tests/proc/test_spike_jobobject.py]
  modified: []
key-decisions:
  - "ruff exclut .planning, .arthemis, .claude et docs : ruff 0.17 formate le Markdown et réécrirait les fichiers GSD"
patterns-established:
  - "Fixtures instance_name/data_home/free_port/junction/symlink_ok pour isoler les tests d'un vrai runner"
requirements-completed: [RUN-01, RUN-03]
duration: 25min
completed: 2026-10-20
---

# Phase 1 Plan 01: Outillage et fondations d'instance unique Summary

Squelette uv/CI avec gate D-12 vert, module `instance` (mutex nommé + bind exclusif, messages FR par winerror) et spike Job Object porté en tests pytest.

## Tâches

| Tâche | Commit | Contenu |
|---|---|---|
| 1 | ba65f61 | pyproject, uv.lock, CI, squelette, fixtures, tests AST |
| 2 | 80a69a9 | instance.py, tests unit (10048/10013) et proc (mutex, taskkill /F /T) |
| 3 | 5b941f4 | winjob.py, tests test_terminate_job_tue_orphelin / test_close_handle_tue_orphelin |

## Résultats des spikes

Spike D-13(b) et D-13(c) : verts (Python 3.14.4 via UV_PYTHON ; tests non exécutés sous 3.11 ici, la CI couvre 3.11 et 3.13).
Spike D-13(a) (`host.docker.internal`) : hors de ce plan (Docker non démarré), reste différé.

## Vérification

`uv sync --locked`, `ruff check`, `ruff format --check`, `pyright` (0 erreur), `pytest -m "not e2e"` (11 réussis), `uv build --all-packages` : tous verts.

## Deviations from Plan

**1. [Rule 3 - Blocage] ruff reformatait le Markdown de .planning**
- **Found during:** Tâche 1 (`uv run ruff format`)
- **Issue:** ruff 0.17 formate les `.md` ; trois fichiers `.planning/` ont été modifiés.
- **Fix:** fichiers restaurés par `git checkout`, `extend-exclude = [".planning", ".arthemis", ".claude", "docs"]` ajouté à `[tool.ruff]`.
- **Commit:** ba65f61

**2. [Rule 1 - Bug] Séquence d'échappement `\D` dans la fixture `instance_name`** corrigée en `\\D` avant le commit.

Hors ces points : plan exécuté tel quel. La CI n'a pas été exécutée (pas de dépôt distant consulté) ; les entrées de `setup-uv@v10` n'ont pas été revérifiées.

## Known Stubs

Aucun. `deskgate.cli` est déclaré dans `[project.scripts]` mais absent jusqu'au plan 01-05 (prévu).

## Self-Check: PASSED

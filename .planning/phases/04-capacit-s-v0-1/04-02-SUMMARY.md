---
phase: 04-capacit-s-v0-1
plan: 02
subsystem: core
tags: [config, settings, path-params, mcp, sdk]
requires: []
provides:
  - Capability.settings et path_params (ctx.settings côté plugin)
  - convert_path_params (conversion et validation des chemins déclarés)
  - kind = "mcp", [mcp_servers.*], lancement du worker deskgate.workers.mcp_call:run
  - type d'erreur plugin depuis l'attribut error_code
affects: [04-03, 04-04, 04-05]
tech-stack:
  added: []
  patterns: [secrets MCP par l'environnement du worker seulement, revalidation des chemins au lancement]
key-files:
  created:
    - tests/unit/test_config_capabilities.py
    - tests/unit/test_path_params.py
    - tests/fs/test_engine_launch_params.py
    - tests/fs/test_submit_path_params.py
    - tests/proc/test_sdk_settings.py
  modified:
    - src/deskgate/core/config.py
    - src/deskgate/core/paths.py
    - src/deskgate/core/env.py
    - src/deskgate/core/worker_protocol.py
    - src/deskgate_sdk/run.py
    - src/deskgate/engine.py
    - src/deskgate/jobs.py
    - tests/_support/jobs.py
    - tests/fake_plugins/deskgate_fakes.py
    - tests/unit/test_worker_protocol.py
key-decisions:
  - "La base garde les chemins d'origine ; l'engine reconvertit et revalide au lancement"
  - "Les valeurs d'env des serveurs MCP ne figurent jamais dans input.json (env_keys seulement)"
duration: 25min
completed: 2026-10-20
---

# Phase 4 Plan 02: Réglages, chemins déclarés et exécuteur mcp Summary

Trois mécanismes génériques sans nom BIM : `settings` vers `ctx.settings`, `path_params` convertis et validés à la soumission (422 audité) puis au lancement, et `kind = "mcp"` lançant `deskgate.workers.mcp_call:run` avec les secrets uniquement dans l'environnement du worker.

## Tâches

| Tâche | Commit | Contenu |
|---|---|---|
| 1 | 7447b23 | Config (settings, path_params, kind mcp, McpServer), `convert_path_params`, `mcp_env_var`, `WorkerInput.settings`, SDK |
| 2 | 70c1b34 | Engine (conversion, settings, branche mcp, `runner_python`), `JobsService.submit`, support de tests, faux plugins, tests fs/proc |

## Vérification

- `pytest -m "not e2e"` : 520 passés, 1 sauté (lien symbolique, privilège absent) ; `pytest -m e2e` : 26 passés.
- ruff check, ruff format --check, pyright : verts.

## Deviations from Plan

None - plan exécuté tel qu'écrit. (Le worker `deskgate.workers.mcp_call` reste à créer en 04-05 ; l'engine ne fait que le désigner.)

## Known Stubs

Aucun.

## Notes

- CAP-01 et CAP-04 : seuls les mécanismes du cœur sont livrés ; les capacités elles-mêmes arrivent dans les plans suivants, requirements laissés en attente.

## Self-Check: PASSED

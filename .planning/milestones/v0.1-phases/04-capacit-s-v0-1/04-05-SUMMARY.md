---
phase: 04-capacit-s-v0-1
plan: 05
subsystem: mcp-worker
tags: [mcp, mcp.call, job-object, stdio, anyio]
requires: [04-01, 04-02]
provides:
  - deskgate.workers.mcp_call:run, client MCP stdio (SDK mcp 2.x), seul module de src/deskgate qui importe mcp
  - tests/mcp_fake/mini_server.py, serveur MCP de test (echo, add, sleep, erreur, spawn_orphan, env)
  - tests/_support/mcp_env.py (mcp_config, mcp_engine)
affects: [04-06, 04-07]
tech-stack:
  added: []
  patterns: [MCPError intercepté dans le corps du client, aplatissement des ExceptionGroup, surveillant d'annulation coopérative, valeurs d'env par l'environnement du worker]
key-files:
  created:
    - src/deskgate/workers/__init__.py
    - src/deskgate/workers/mcp_call.py
    - tests/mcp_fake/mini_server.py
    - tests/_support/mcp_env.py
    - tests/proc/test_mcp_call.py
    - tests/proc/test_mcp_errors.py
    - tests/proc/test_mcp_tree.py
  modified: []
key-decisions:
  - "Erreurs classées : invalid_params, server_not_declared, tool_not_allowed, server_unreachable, call_timeout, mcp_error, tool_error"
  - "Résultat : summary {server, tool, is_error} ; data {structured_content, content} ; au-delà de 900 000 octets, artefact mcp-result.json et data {truncated: true}"
requirements-completed: [CAP-04]
duration: 25min
completed: 2026-10-20
---

# Phase 4 Plan 05 : mcp.call Summary

Worker `mcp.call` : client stdio du SDK `mcp` 2.x qui n'appelle que des serveurs et outils déclarés dans `runner.toml`, dans le Job Object de la tâche, prouvé par l'Engine réel et un mini-serveur MCP.

## Réalisé

- **Tâche 1** (a28903f) : worker, mini-serveur, aides de test. Le lancement `kind = "mcp"` existait déjà (04-02) ; `engine.py` n'est pas touché.
- **Tâche 2** et **tâche 3** (0342003) : 14 tests `proc`/`mcp` verts (7 appel et secrets, 4 erreurs, 3 arbre) :
  - echo, add, `is_error` donnant `failed`/`plugin_error` (`tool_error : ...`) ;
  - serveur ou outil non déclaré, `arguments` invalides ;
  - délai d'appel (`call_timeout`), commande inexistante, sortie immédiate, stdout pollué : tous `server_unreachable`, jamais d'`ExceptionGroup` ;
  - serveur MCP et petit-enfant morts après délai de tâche (`timeout`), annulation (`cancelled`) et sortie normale.
- Le serveur ne voit aucune variable `DESKGATE_*` ; la valeur d'env atteint le serveur et n'apparaît dans aucun fichier du dossier de tâche autre que `result.json` (qui contient la valeur renvoyée par l'outil `env` du test, par construction).

## Deviations from Plan

Aucune sur le code. Ajustements mineurs :
- `# noqa: S105` sur la constante de test `SECRET` (règle ruff sur mot de passe en dur, valeur fictive).
- Le contrôle « aucun fichier ne contient SECRET » exclut `result.json`, car l'outil de test `env` renvoie la valeur demandée ; tout le reste du dossier (input.json, events.jsonl, job.log, etc.) est contrôlé.
- Le Job imbriqué du SDK `mcp` n'a pas empêché l'arrêt de l'arbre : aucun contournement nécessaire.

## Known Stubs

Aucun.

## Vérification

`uv run pytest -m "not e2e"` : 584 passed, 1 skipped (lien symbolique, privilège absent). ruff check, ruff format --check, pyright verts. Aucun processus résiduel.

CAP-04 : requirement complet (appel sans LLM, refus des non déclarés, `is_error` en `failed`, arbre arrêté, secrets hors disque).

## Self-Check: PASSED

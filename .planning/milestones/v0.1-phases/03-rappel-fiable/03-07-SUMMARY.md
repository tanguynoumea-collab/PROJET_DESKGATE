---
phase: 03-rappel-fiable
plan: 07
subsystem: runtime
tags: [callback, sender, logging, redaction, e2e]
requires: ["03-05", "03-06"]
provides:
  - "deskgate serve démarre et arrête le thread sender (lifespan composé)"
  - "configure_logging : handler partagé masqué sur deskgate et la racine, httpx2/httpcore2 à WARNING, DESKGATE_LOG_LEVEL"
  - "tests/e2e : cb_runner, wait_callback_state, write_config(callback=), start_runner(log_path=)"
affects: [03-08]
tech-stack:
  added: []
  patterns: [arrêt composé engine puis sender via on_shutdown, faux n8n réel pour l'e2e]
key-files:
  created:
    - tests/unit/test_logging.py
    - tests/e2e/test_callback_flow.py
  modified:
    - src/deskgate/runtime.py
    - tests/e2e/conftest.py
decisions:
  - "Aucun compteur de rappels ni battement du sender exposé dans /health en v0.1 (discrétion)"
  - "CB-01, CB-03 et SEC-05 restent Pending : interrupted et le balayage complet de la signature relèvent de 03-08"
metrics:
  tasks: 2
  completed: 2026-10-20
---

# Phase 3 Plan 07: Sender câblé et rappel réel Summary

Le runner réel (`deskgate serve`) envoie maintenant les rappels : thread sender démarré après l'engine, arrêté avec lui par le lifespan, journaux masqués sur tous les handlers, et rappel prouvé par HTTP réel contre le faux n8n pour succeeded (< 100 ms), failed, timeout, cancelled, plus un réessai 409 puis 200.

## Tâches

1. Sender dans deskgate serve et journaux masqués : `02e1083`
2. Aides e2e et rappel réel pour quatre statuts : `aa70b07`

## Vérification

`pytest -m "not e2e"` : 468 réussis, 1 sauté (privilège de lien symbolique). `pytest -m e2e` : 21 réussis (dont 5 de `test_callback_flow.py`). `ruff check`, `ruff format --check`, `pyright` verts. Aucun processus `deskgate serve` résiduel.

## Deviations from Plan

None - plan exécuté tel qu'écrit. Le paramètre `log_path` de `start_runner` est livré mais non encore utilisé (réservé au balayage de 03-08).

## Known Stubs

None.

## Self-Check: PASSED

---
phase: 03-rappel-fiable
plan: 08
subsystem: tests-e2e
tags: [callback, durability, redaction, audit, e2e]
requires: ["03-07"]
provides:
  - "Preuve e2e de la reprise du rappel après taskkill /F /T (CB-02)"
  - "Preuve e2e du statut interrupted rappelé avec runner_restarted (CB-01)"
  - "Balayage complet de la signature et audit du parcours (SEC-05, SEC-06)"
affects: []
tech-stack:
  added: []
  patterns: ["runner relancé à la main et tué en arbre dans finally", "balayage par SQL, jamais en octets bruts sur la base"]
key-files:
  created:
    - tests/e2e/test_callback_restart.py
    - tests/e2e/test_callback_secret.py
  modified: []
decisions:
  - "CB-01..05, SEC-05 et SEC-06 marqués Complete : chacun est couvert par un test automatisé après ce plan"
metrics:
  tasks: 2
  completed: 2026-10-20
---

# Phase 3 Plan 08: Rappel durable et signature absente partout Summary

Le rappel survit à un arrêt brutal du runner (reprise, envoi interrompu relu en doublon 409, statut `interrupted` rappelé avec `runner_restarted`), et la signature `SWEEPq7...` est absente de toutes les réponses d'API, du journal INFO du runner, des fichiers de tâche et des colonnes d'audit, de callbacks et de jobs.

## Tâches

1. Rappel durable à travers un arrêt brutal : `6f4fce9` (3 tests)
2. Balayage de la signature et audit du parcours : `7e005e2` (2 tests)

## Gate D-12 (complet, vert)

| Commande | Résultat |
|---|---|
| `uv sync --locked` | OK (35 paquets vérifiés) |
| `uv run ruff check` | All checks passed |
| `uv run ruff format --check` | 98 fichiers déjà formatés |
| `uv run pyright` | 0 erreur, 0 avertissement |
| `uv run pytest -m "not e2e" -q` | 468 réussis, 1 sauté (privilège de lien symbolique), 26 désélectionnés |
| `uv build --all-packages` | sdist et wheel construits |
| `uv run pytest -m e2e -q` | 26 réussis (142 s) |

Aucun processus `deskgate serve` résiduel après les exécutions.

## Deviations from Plan

None - plan exécuté tel qu'écrit. Le parcours du balayage est factorisé dans un helper `_parcours` partagé par les deux tests du fichier secret (le second parcours court prévu par le plan).

## Known Stubs

None.

## Self-Check: PASSED

---
phase: 03-rappel-fiable
plan: 02
subsystem: callback-policy
tags: [callback, policy, tdd, n8n]
requires: []
provides:
  - "core/callback_policy.py : Decision, classify, next_delay, check_callback_url, CallbackUrlError, FINAL"
affects: [03-05, 03-06]
tech-stack:
  added: []
  patterns: [module pur de core/, rng injecté pour le déterminisme]
key-files:
  created: [src/deskgate/core/callback_policy.py, tests/unit/test_callback_policy.py, tests/unit/test_callback_url.py]
  modified: []
decisions:
  - "401/403/404 n'abandonnent qu'au deuxième constat identique ; 413 un seul renvoi minimal"
metrics:
  tasks: 2
  completed: 2026-10-20
---

# Phase 3 Plan 02: Politique pure du rappel Summary

Table de décision exacte de n8n 2.43.8 (`classify`), délai croissant avec gigue injectable (`next_delay`) et contrôle strict de l'hôte de rappel (`check_callback_url`), le tout en stdlib pure.

## Tâches

1. classify et next_delay : tests `9c08bae`, implémentation `038c892`
2. check_callback_url : tests `cf1d999` (implémentation dans `038c892`)

## Vérification

`pytest -m unit` (283 réussis), tests d'architecture, ruff check, ruff format, pyright : verts.

## Deviations from Plan

**1. [Process] check_callback_url écrit avec le GREEN de la tâche 1**
- Le code de la tâche 2 a été committé avec `038c892` ; les tests de la tâche 2 (`cf1d999`) passent donc dès leur commit, sans phase RED séparée.

**2. [Rule 3 - Blocking] ruff S311 / SIM300 / E501 dans les tests**
- Assistant `_rng(seed)` avec `noqa: S311`, comparaison inversée, docstring raccourcie.

## Known Stubs

Aucun.

## Self-Check: PASSED

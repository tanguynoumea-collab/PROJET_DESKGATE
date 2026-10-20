---
phase: 03-rappel-fiable
plan: 04
subsystem: store-outbox-audit
tags: [sqlite, outbox, audit, migration]
requires: ["03-03"]
provides:
  - "store.py : schéma 2 (callbacks.maybe_delivered), CallbackClaim, claim_due_callback, record_callback_result, abandon_callback, record_refusal"
  - "audit enrichi : job.submitted, job.<terminal>, job.refused, callback.attempt/delivered/abandoned"
affects: [03-05, 03-06, 03-07]
tech-stack:
  added: []
  patterns: [écriture préalable pessimiste avant l'envoi, purge de la resumeUrl à l'état final]
key-files:
  created: [tests/fs/test_store_audit.py, tests/fs/test_store_callbacks.py]
  modified: [src/deskgate/store.py, tests/fs/test_store_schema.py]
decisions:
  - "CB-02, CB-03, SEC-05 et SEC-06 restent Pending : backoff, classification HTTP, journaux et API viennent de 03-05 à 03-07"
metrics:
  tasks: 2
  completed: 2026-10-20
---

# Phase 3 Plan 04: Outbox durable et audit complet Summary

Store étendu : migration 2 (`maybe_delivered`), réclamation du rappel avec écriture préalable (attempts+1 et bit à 1 validés avant l'envoi), restauration du bit sur 4xx, abandon par fenêtre de 24 h sans dernier envoi, purge de `callback_url` à l'état final, audit de soumission, fin et refus, `repr(JobRow)` sans resumeUrl.

## Tâches

1. Migration 2, repr sans secret, audit enrichi : `247168d`
2. Outbox (claim, résultat, abandon) : `eb1677a`

## Vérification

`pytest -m "unit or fs"` (393 réussis, 1 sauté : privilège de lien symbolique), tests d'architecture, ruff check, ruff format --check, pyright : verts. 15 tests dans test_store_callbacks.py.

## Deviations from Plan

**1. [Process] Tests et implémentation committés ensemble par tâche** (pas de commit RED séparé pour la tâche 2).

**2. [Process] Commit 247168d laissait un import inutilisé** (`redact_signature`, employé à la tâche 2) et un tri d'imports de test ; corrigés dans eb1677a.

## Known Stubs

Aucun.

## Self-Check: PASSED

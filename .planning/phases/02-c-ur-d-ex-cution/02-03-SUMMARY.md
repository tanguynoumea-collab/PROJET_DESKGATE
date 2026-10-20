---
phase: 02-c-ur-d-ex-cution
plan: 03
subsystem: store
tags: [sqlite, queue, outbox, audit, migration]
requires: []
provides:
  - "store : connect, tx, migrate, open_db, iso, insert_job, get_job, claim_next, update_progress, finish, request_cancel, is_cancel_requested, recover_interrupted, JobRow, SchemaTooNew, StaleTransition, IdempotencyConflict"
affects: [02-05, 02-06, 02-07]
tech-stack:
  added: []
  patterns: ["isolation_level=None + BEGIN IMMEDIATE explicite", "écriture terminale unique _terminal() partagée par finish, request_cancel, recover_interrupted"]
key-files:
  created:
    - tests/_support/store_helpers.py
    - tests/fs/test_store_schema.py
    - tests/fs/test_store_queue.py
    - tests/fs/test_store_cancel.py
    - tests/fs/test_store_recovery.py
  modified:
    - src/deskgate/store.py
key-decisions:
  - "Aides de test placées dans tests/_support (pythonpath=tests) et non dans tests/fs"
  - "Les deux commits regroupent store.py dans le commit de la tâche 1 (module écrit d'un bloc)"
requirements-completed: []
duration: 15min
completed: 2026-10-20
---

# Phase 2 Plan 03 : Stockage SQLite Summary

Migration 1 complète (jobs, callbacks, audit STRICT, user_version 1) et file atomique : soumission idempotente, réclamation `UPDATE … RETURNING` avec `NOT EXISTS running`, fin/annulation/recovery transactionnelles avec rappel `pending` et audit sans secret.

## Réalisation

- `open_db` conserve son nom et crée le dossier parent ; migre en WAL ; refuse une base plus récente (`SchemaTooNew`).
- Audit en ajout seul par déclencheurs ; aucune trace de `callback_url` ni `params` dans `detail_json` (testé).
- Six threads concurrents : un seul gagnant (Barrier).

## Verification

`pytest -m "unit or fs"` : 232 passés, 1 ignoré (lien symbolique) ; e2e `test_serve` et architecture verts ; ruff et pyright à zéro erreur.

## Deviations from Plan

- [Rule 3] Les aides de test sont dans `tests/_support/store_helpers.py` : un module nu dans `tests/fs` n'était pas importable (`--import-mode=importlib`).
- Les exigences JOB-02/04/06/08 restent « Pending » : elles ne seront complètes qu'avec le plan 02-09.

## Known Stubs

Aucun.

## Self-Check: PASSED

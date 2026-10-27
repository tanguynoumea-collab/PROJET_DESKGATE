---
phase: 02-c-ur-d-ex-cution
plan: 01
subsystem: core
tags: [pydantic, config, jobspec, errors]
requires: []
provides:
  - "Capability étendue (pythonpath, memory_mb, timeout_max ≤ 43200, entry module:fonction)"
  - "RunnerConfig.work_root et effective_work_root()"
  - "core/jobspec : SubmitRequest, CallbackSpec, JobRequestError, resolve_timeout, new_job_id, is_valid_job_id, work_dir_for"
  - "Codes d'erreur capability_not_found, job_not_found, idempotency_conflict, timeout_too_large ; error_body(**extra)"
affects: [02-06, 02-07]
tech-stack:
  added: []
  patterns: ["noyau pur : pydantic, re, secrets seulement"]
key-files:
  created:
    - src/deskgate/core/jobspec.py
    - tests/unit/test_jobspec.py
  modified:
    - src/deskgate/core/config.py
    - src/deskgate/core/errors.py
    - src/deskgate/runner.example.toml
    - tests/unit/test_config.py
key-decisions:
  - "work_root validé par un field_validator lisant info.data['paths'] : le message cite work_root et racine"
  - "callback.headers refusé par extra=forbid (phase 2)"
requirements-completed: []
duration: 15min
completed: 2026-10-20
---

# Phase 2 Plan 01: Contrats de soumission Summary

Configuration des capacités et du dossier de travail étendue (python absolu, entry module:fonction, plafond 43200 s), modèle `POST /jobs` strict, délai effectif min(7200, timeout_max) et job_id de 12 caractères hexadécimaux.

## Tâches

1. Configuration (capacités, work_root) : commit 14051cd
2. Contrat jobspec et codes d'erreur : commit dabd78e

## Vérification

pytest complet : 190 réussis, 1 ignoré (lien symbolique sans privilège) ; ruff et pyright sans erreur ; tests d'architecture (noyau pur) verts.

## Deviations from Plan

None - plan executed exactly as written. (Un test existant utilisait `entry = "pkg.mod"` : mis à jour comme prévu.)

## Requirements

JOB-01, JOB-08, JOB-09 : contrats posés, mais les exigences ne sont complètes qu'avec le plan 02-09 ; laissées en attente.

## Known Stubs

None.

## Self-Check: PASSED

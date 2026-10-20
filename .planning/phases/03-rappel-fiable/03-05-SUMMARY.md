---
phase: 03-rappel-fiable
plan: 05
subsystem: engine-jobs-submission
tags: [summary-cap, callback-host, audit-refusals]
requires: ["03-01", "03-02", "03-03", "03-04"]
provides:
  - "Engine(callback_max_bytes) : résumé déporté dans summary.json (écriture atomique) avant la transaction terminale"
  - "JobsService.submit : contrôle d'hôte de rappel (422 callback_host_not_allowed) et audit job.refused de chaque refus"
  - "JobsService.audit_refusal, utilisé par le gestionnaire 422 de POST /jobs (invalid_request)"
  - "job_view.duration_s calculé par payload.duration_s (même fonction que le rappel)"
affects: [03-06, 03-07]
tech-stack:
  added: []
  patterns: [mesure du corps réel du rappel avant la conclusion, audit de refus sans effet sur la réponse]
key-files:
  created: [tests/fs/test_engine_summary_cap.py, tests/fs/test_audit_events.py]
  modified: [src/deskgate/engine.py, src/deskgate/jobs.py, src/deskgate/api/handlers.py, tests/fs/test_routes_jobs.py]
decisions:
  - "CB-04 complet (résumé déporté, rappel ne porte que le chemin). CB-05, SEC-05 et SEC-06 restent Pending : contrôle d'hôte à l'envoi, journaux et API viennent de 03-06 et 03-07"
metrics:
  tasks: 2
  completed: 2026-10-20
---

# Phase 3 Plan 05: Plafond du résumé, hôte de rappel et audit des refus Summary

L'engine mesure le corps réel du rappel et, au-delà du plafond (1 Mio par défaut, injectable), écrit le résumé dans `summary.json` (tmp, fsync, `os.replace`) avant la transaction terminale ; `POST /jobs` refuse un hôte non autorisé en 422 sans l'URL et inscrit chaque refus en `job.refused`.

## Tâches

1. Plafond du résumé et summary.json atomique : `5779adb`
2. Hôte autorisé à la soumission et audit des refus : `60bbcde`

## Vérification

`pytest -m "not e2e"` (438 réussis, 1 sauté : privilège de lien symbolique), ruff check, ruff format --check, pyright : verts. Tests : 4 dans test_engine_summary_cap.py (petit plafond, résumé inchangé, borne réelle 1 Mio, échec d'écriture), 6 ajoutés dans test_routes_jobs.py, 2 dans test_audit_events.py.

## Deviations from Plan

**1. [Process] Tests et implémentation committés ensemble par tâche** (pas de commit RED séparé).

**2. [Rule 3 - Blocage] Renommage du paramètre de test `on_launch_extra` en `before_launch`** : la règle ruff S610 (faux positif Django « extra ») bloquait le lint.

Les tests de `test_routes_jobs.py` utilisent `Env` avec `callback_allowed_hosts` incluant `n8n`, comme prévu au plan.

## Known Stubs

Aucun.

## Self-Check: PASSED

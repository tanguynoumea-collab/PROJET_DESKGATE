---
phase: 03-rappel-fiable
plan: 03
subsystem: callback-payload-redaction
tags: [callback, payload, redaction, tdd]
requires: []
provides:
  - "core/payload.py : CALLBACK_MAX_BYTES, duration_s, build_callback, encode, minimal"
  - "core/redact.py : redact_signature étendu, redact_params, RedactingFormatter, RedactingFilter"
affects: [03-04, 03-05, 03-06, 03-07]
tech-stack:
  added: []
  patterns: [modules purs de core/, masquage unique]
key-files:
  created: [src/deskgate/core/payload.py, tests/unit/test_payload.py]
  modified: [src/deskgate/core/redact.py, tests/unit/test_redact.py]
decisions:
  - "CB-01, CB-04 et SEC-05 restent Pending : le câblage (sender, engine, logging) vient des plans suivants"
metrics:
  tasks: 2
  completed: 2026-10-20
---

# Phase 3 Plan 03: Corps du rappel et masquage unique Summary

Corps du rappel pur à 7 clés pour les 5 statuts terminaux (data jamais transmis, plafond défensif avec marqueur de troncature) et masquage de la signature sous ses trois formes, pour chaînes, paramètres et journaux.

## Tâches

1. core/payload : `b132f5b`
2. core/redact étendu : `7ea1f59`

## Vérification

`pytest -m "unit or fs"` (370 réussis, 1 sauté : privilège de lien symbolique), tests d'architecture, ruff check, ruff format --check, pyright : verts.

## Deviations from Plan

**1. [Process] Tests et implémentation committés ensemble par tâche**
- Pas de commit RED séparé ; les tests ont été écrits avant l'implémentation mais committés avec elle.

**2. [Rule 3 - Blocking] ruff S105 dans test_redact**
- `noqa: S105` sur deux assertions comparant des valeurs de clé nommée « secret ».

## Known Stubs

Aucun.

## Self-Check: PASSED

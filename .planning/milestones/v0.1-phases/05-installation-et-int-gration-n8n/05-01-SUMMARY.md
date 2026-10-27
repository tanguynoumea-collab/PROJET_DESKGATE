---
phase: 05-installation-et-int-gration-n8n
plan: 01
subsystem: installation
tags: [planificateur, schtasks, xml, windows]
requires: []
provides:
  - "deskgate.scheduler : TaskSpec, build_task_xml, parse_task_xml, read_settings, audit_settings, enveloppe schtasks"
  - "marqueurs pytest scheduler et docker"
affects: [05-03, 05-04, 05-05]
tech-stack:
  added: []
  patterns: ["XML par ElementTree, jamais par concaténation", "seuls les codes de retour de schtasks sont lus"]
key-files:
  created:
    - src/deskgate/scheduler.py
    - tests/unit/test_scheduler_xml.py
    - tests/proc/test_scheduler_real.py
  modified:
    - pyproject.toml
    - tests/architecture/test_import_boundaries.py
decisions:
  - "scheduler.py autorisé à importer ctypes et subprocess dans les tests d'architecture"
metrics:
  duration: 20min
  completed: 2026-10-21
requirements-completed: [INS-02]
---

# Phase 5 Plan 01 : module du Planificateur Summary

Module `deskgate.scheduler` : XML UTF-16 de la tâche (D-03), relecture tolérante au XML normalisé par Windows, audit des réglages et enveloppe `schtasks.exe` sans shell, éprouvée sur une vraie tâche jetable sans élévation.

## Réalisé

- Tâche 1 (1eebd1c) : génération et relecture du XML, audit (échec / avertissement), marqueurs `scheduler` et `docker`. 14 tests unitaires.
- Tâche 2 (b446601) : create/query/run/end/delete ; test réel `DeskgateTest-<uuid>` créé, lancé (fichier marqueur écrit), relu, supprimé en `finally`. 3 tests, aucune tâche résiduelle.
- e633b60 : liste d'autorisation des tests d'architecture.

## Écarts par rapport au plan

**1. [Rule 3 - Blocage] Tests d'architecture** : `test_ctypes_seulement_dans_jobobject` et `test_subprocess_seulement_dans_jobobject` échouaient à cause de `scheduler.py` ; ajout de `scheduler.py` aux ensembles autorisés. Commit e633b60.

**2. [Rule 1] Ruff SIM112** : variable d'environnement `SYSTEMROOT` en majuscules (Windows insensible à la casse).

## Known Stubs

Aucun.

## Self-Check: PASSED

Fichiers présents, commits 1eebd1c, b446601, e633b60 ; ruff, pyright et tests verts ; 0 tâche DeskgateTest- résiduelle.

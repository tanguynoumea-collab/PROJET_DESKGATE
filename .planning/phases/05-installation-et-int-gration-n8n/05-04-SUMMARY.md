---
phase: 05-installation-et-int-gration-n8n
plan: 04
subsystem: installation
tags: [doctor, cli, diagnostic, planificateur]
requires: ["05-01", "05-03"]
provides:
  - "deskgate.doctor : Check, check_config, check_dirs, check_token, check_task, check_port, check_plugins, check_home_env, run_all, exit_code"
  - "commande deskgate doctor [--config]"
affects: [05-06]
tech-stack:
  added: []
  patterns: ["une vérification = un Check (niveau + message français)", "tâche relue via query injectable pour les tests"]
key-files:
  created: [src/deskgate/doctor.py, tests/unit/test_doctor.py, tests/unit/test_doctor_task.py]
  modified: [src/deskgate/cli.py]
key-decisions:
  - "check_task complet écrit dès la tâche 1 (le minimal du plan aurait été jeté aussitôt)"
requirements-completed: [INS-01, INS-02]
duration: 20min
completed: 2026-10-21
---

# Phase 5 Plan 04 : deskgate doctor Summary

`deskgate doctor` vérifie configuration, dossiers, jeton, tâche du Planificateur relue (réglages D-03), port (runner joignable, libre, ou occupé par un autre programme) et environnements de plugins, avec sortie 1 au moindre échec.

## Réalisé
- Tâche 1 (c9b294b) : `doctor.py` et commande `doctor`. Configuration invalide : arrêt des vérifications dépendantes, rappel que les erreurs d'avant le mutex ne sont visibles qu'en console. Avertissement si `DESKGATE_HOME` défini. 13 tests (vrai serveur HTTP local, vrai socket en écoute).
- Tâche 2 (116e39d) : 11 tests de `check_task` sur XML normalisé conforme et falsifié (PT72H, batterie, RunLevel, LogonType, déclencheur, redémarrage retiré, commande absente, autre que pythonw, arguments).

## Vérification
ruff, pyright verts ; 428 tests `unit` et `architecture` réussis ; `deskgate doctor --help` sort en 0 (avec un pipe vers `head`, Rich plante sur la console Windows : artefact de l'environnement, hors périmètre).

## Écarts par rapport au plan
- `check_task` complet implémenté en tâche 1 au lieu de la version minimale ; la tâche 2 n'a ajouté que les tests.
- Les suites e2e/proc n'ont pas été relancées (non touchées).

## Known Stubs
Aucun.

## Self-Check: PASSED

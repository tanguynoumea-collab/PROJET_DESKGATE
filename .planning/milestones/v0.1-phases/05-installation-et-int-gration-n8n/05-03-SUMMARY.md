---
phase: 05-installation-et-int-gration-n8n
plan: 03
subsystem: installation
tags: [init, cli, planificateur, jeton]
requires: ["05-01", "05-02"]
provides:
  - "deskgate.installer : load_template, normalize_root, render_config, ensure_dirs, init_config, task_spec, install_task"
  - "commande deskgate init et sous-application deskgate task (install, remove, status, run, end)"
affects: [05-06]
tech-stack:
  added: []
  patterns: ["logique sans Typer dans installer.py", "stdout réservé au jeton, guidage sur stderr"]
key-files:
  created: [src/deskgate/installer.py, tests/unit/test_init.py, tests/unit/test_cli_task.py]
  modified: [src/deskgate/cli.py]
key-decisions:
  - "cli.py appelle scheduler.<fonction> (attribut de module) pour que les tests puissent substituer le Planificateur"
requirements-completed: [INS-01, INS-02]
duration: 25min
completed: 2026-10-21
---

# Phase 5 Plan 03 : deskgate init et deskgate task Summary

`deskgate init` écrit `runner.toml` depuis le gabarit commenté (hash SHA-256 du jeton, racine personnalisable), crée les dossiers, affiche le jeton seul sur stdout et installe la tâche du Planificateur avec accord ; `deskgate task` la pilote.

## Réalisé
- Tâche 1 (3451410) : `installer.py` et `init` ; relance sans effet, `--force` avec sauvegarde `runner.toml.bak-<horodatage>`, racine UNC refusée (code 2), refus de la tâche sous `DESKGATE_HOME` (code 1), `--yes`, `--no-task`, confirmation sur stderr. 8 tests.
- Tâche 2 (5b5797b) : `task install | remove | status | run | end`, garde `_confirm_task` partagée avec `init`. 9 tests.

## Vérification
ruff, format et pyright verts ; 397 tests `unit` et `architecture` réussis ; aucun dossier `%LOCALAPPDATA%\Deskgate` créé. La suite complète (e2e/proc) n'a pas été relancée en entier ici (dépassement du délai de l'outil) ; ces tests n'ont pas été touchés.

## Écarts par rapport au plan
- Le test de refus interactif vérifie que la première ligne de stdout est le jeton : `CliRunner` recopie la saisie simulée (« n ») dans stdout, ce qui n'arrive pas sur un vrai terminal où la question et l'écho vont sur stderr/console.
- `task status` cite « limite de durée » (message d'audit de 05-01) et non le nom de balise `ExecutionTimeLimit`.
- INS-01 et INS-02 étaient déjà cochés par les plans précédents ; rien à modifier.

## Known Stubs
Aucun.

## Self-Check: PASSED

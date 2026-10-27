---
phase: 05-installation-et-int-gration-n8n
plan: 02
subsystem: runtime
tags: [logging, pythonw, cli, planificateur]
requires: []
provides:
  - "attach_file_log(home) : journal rotatif logs/runner.log, masqué, ouvert après le mutex"
  - "deskgate --version"
affects: [05-installation, tâche planifiée]
tech-stack:
  added: []
  patterns: ["journal fichier additif au flux stderr, stderr None toléré"]
key-files:
  created: [tests/unit/test_cli_version.py, tests/e2e/test_serve_logfile.py]
  modified: [src/deskgate/runtime.py, src/deskgate/locations.py, src/deskgate/cli.py, tests/unit/test_logging.py]
key-decisions:
  - "Échec d'ouverture du journal fichier : message en français, le runner continue"
requirements-completed: [INS-01, INS-02]
duration: 20min
completed: 2026-10-21
---

# Phase 5 Plan 02 : Journal fichier et --version Summary

Journal rotatif 5 x 2 Mio dans `<données>/logs/runner.log`, ouvert uniquement après l'acquisition du mutex, avec le même masquage de la signature que stderr ; fonctionne sous `pythonw.exe` (stderr `None`) ; `deskgate --version` ajouté.

## Réalisations
- `locations.py` : `logs_dir`, `log_path` (sans création de dossier).
- `runtime.py` : `configure_logging` n'ajoute plus de StreamHandler si `sys.stderr is None` ; `attach_file_log` ajoute un `RotatingFileHandler` au logger `deskgate` et à la racine ; appelé dans `serve()` entre le mutex et `bind_exclusive`, suivi de la ligne « démarré (pid ... ) ».
- `cli.py` : option `--version` (callback eager).
- Tests : 2 cas de journal (unitaires), 2 cas `--version`, 3 e2e (journal + signature masquée, second runner muet code 3, lancement réel sous `pythonw.exe`).

## Vérification
- Unitaires hors e2e : 636 réussis, 1 ignoré (lien symbolique, privilège absent) ; e2e : 29 réussis ; ruff et pyright verts.

## Commits
- 49b71fe : feat(05-02) journal fichier et --version
- 407f39d : test(05-02) e2e du journal

## Deviations from Plan
Aucune. Les tests d'architecture n'ont pas été modifiés.

## Known Stubs
Aucun.

## Self-Check: PASSED

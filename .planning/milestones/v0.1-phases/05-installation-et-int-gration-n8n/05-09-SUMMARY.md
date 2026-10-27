---
phase: 05-installation-et-int-gration-n8n
plan: 09
subsystem: documentation
tags: [documentation, installation, agents, architecture]
requires: ["05-08"]
provides:
  - "AGENTS.md : procédure exécutée sur la machine (init, task, doctor, n8n, mise à jour, dépannage)"
  - "ARCHITECTURE.md §2 (démarrage réel) et §9 (compose du dépôt, exemple)"
  - "README.md : section Installation réelle"
affects: []
key-files:
  modified: [AGENTS.md, ARCHITECTURE.md, README.md]
decisions:
  - "Pièges de l'environnement documentés : MSIX, UTF-16 de PowerShell 5.1, tube sur doctor, --out explicite"
metrics:
  duration: 10min
  completed: 2026-10-21
requirements-completed: [INS-01, INS-02, INS-03, INS-04, INS-05]
---

# Phase 5 Plan 09 : documentation d'après l'installation réelle

AGENTS.md devient la procédure exécutée en phase 5 ; ARCHITECTURE.md et README.md décrivent le démarrage par `pythonw.exe -m deskgate serve` et le compose n8n du dépôt.

## Réalisé

- **Tâche 1** (86eea4d) : AGENTS.md : statut « éprouvée en v0.1 », `deskgate --version`, `init` (`--root`, `--force`, `--no-task`, `--yes`), `task install|status|run|end|remove`, `doctor`, journal `logs\runner.log`, absence de relance automatique, blocs de capacité avec `memory_mb`, n8n (`.env`, port 5679, INS-05, `n8n_setup.py`, n8n existant), test par webhook, section « Mettre à jour », dépannage étendu. Pièges ajoutés : installation depuis une application MSIX (`0x8007010B`, `LocalCache`), redirection UTF-16 de PowerShell 5.1 (`cmd /c`), `doctor` non relié à un tube, `--out` explicite pour `recette.py`.
- **Tâche 2** (678f0ba) : ARCHITECTURE.md §2 (schtasks /XML, pythonw, journal après le mutex, `RestartOnFailure` limité aux échecs de démarrage, recovery `interrupted`) et §9 (compose épinglé, 5679, `/data`, `$json.body?.status`) ; README.md « Installation » sans « (cible) ».

## Vérification

`ruff check` et `ruff format --check` verts. Greps d'acceptation satisfaits (aucun chemin personnel, aucun « (cible) »). Documentation seule : pyright, pytest et `uv build` non relancés, car un calcul de recette tournait en arrière-plan sur le runner ; aucun code modifié.

## Deviations from Plan

Aucune, hormis la non-exécution de la gate complète (voir ci-dessus).

## Known Stubs

Aucun.

## Self-Check: PASSED

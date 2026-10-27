---
phase: 01-fondations-testables
plan: 02
subsystem: security
tags: [paths, windows, junction, ads, reserved-names, tdd]
requires: [01-01]
provides:
  - src/deskgate/core/paths.py (Mapping, PathDenied, conversion par segments, contrôle lexical, resolver injecté)
affects: [01-04, phase-2]
tech-stack:
  added: []
  patterns: [contrôle lexical sur chaînes avant résolution, comparaison par segments insensible à la casse, resolver injecté]
key-files:
  created: [src/deskgate/core/paths.py, tests/unit/test_paths_mapping.py, tests/unit/test_paths_attacks.py, tests/fs/test_paths_real.py]
  modified: []
key-decisions:
  - "validate_artifact_path convertit le chemin hôte lexical (pas le chemin résolu) : une racine qui est une jonction reste convertible vers /data"
requirements-completed: [SEC-03, SEC-04]
duration: 15min
completed: 2026-10-20
---

# Phase 1 Plan 02: Validation et conversion des chemins Summary

`core/paths.py` : conversion `/data` et `C:/BIM` par segments, contrôle lexical écrit à la main (`..`, UNC, `\\?\`, `\\.\`, `C:foo`, noms réservés dont `COM¹`, flux alternatifs, point ou espace final, caractères de contrôle), puis résolution par resolver injecté et recontrôle sous les racines résolues.

## Tâches

| Tâche | Commit | Contenu |
|---|---|---|
| 1 RED | bd9ec37 | table d'attaques (39 cas) et tests de correspondance |
| 1 GREEN | 00e28f3 | `core/paths.py` |
| 2 | 4010ede | 10 tests `fs` sur vrai disque |

## Vérification

`pytest -m "unit or fs"` : 71 réussis, 1 sauté. `tests/architecture` vert (core pur), `ruff check`, `ruff format --check`, `pyright` : 0 erreur. Aucun `xfail`.

## Notes de sécurité

- Symlink : `test_symlink_vers_exterieur_refuse` sauté localement (WinError 1314, mode développeur absent), skip explicite via la fixture `symlink_ok` ; à confirmer en CI `windows-latest`.
- Noms 8.3 non testables (volume sans noms courts) ; `~` volontairement non rejeté.
- Risques acceptés et documentés : TOCTOU (jonction substituée entre contrôle et usage), liens physiques (PITFALLS M12).
- Tests exécutés sous Python 3.14.4 seulement (3.11 non exécuté ici).

## Deviations from Plan

**1. [Rule 1 - Bug] Ordre des contrôles lexicaux** : le plan listait les caractères interdits (`?`) avant le préfixe `//`, ce qui classait `\\?\C:\BIM\x` en `path_invalid` alors que la table attend `path_outside_roots`. Contrôle des caractères de contrôle `[\x00-\x1f]` d'abord, préfixe `//` ensuite, puis `<>"|?*`.

Hors ce point : plan exécuté tel quel. Le trailer de commit utilise `Claude Sonnet 5.5` (consigne de rattribution du système), alors que le prompt mentionnait Opus 5.5.

## Known Stubs

Aucun.

## Self-Check: PASSED

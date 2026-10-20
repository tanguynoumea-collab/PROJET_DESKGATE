---
phase: 01-fondations-testables
plan: 04
subsystem: config
tags: [pydantic, tomllib, platformdirs, config, loopback]
requires:
  - phase: 01-02
    provides: core.paths (normalize_host_path, split_container_path, is_under, Mapping)
provides:
  - RunnerConfig, Paths, PathMapping, Capability, ConfigError, parse_config, load_config
  - locations.default_home, resolve_home, config_path, db_path
  - runner.example.toml (gabarit commenté en français, valide)
affects: [01-05 runtime]
tech-stack:
  added: []
  patterns: [modèles Pydantic stricts extra=forbid, erreurs traduites sans include_input]
key-files:
  created:
    - src/deskgate/core/config.py
    - src/deskgate/locations.py
    - src/deskgate/runner.example.toml
    - tests/unit/test_config.py
    - tests/unit/test_locations.py
key-decisions:
  - "Hôte d'écoute : IPv4 littérale uniquement ; non loopback exige allow_non_loopback = true"
  - "PydanticCustomError avec gabarit {msg} pour satisfaire pyright (LiteralString)"
requirements-completed: [RUN-01, SEC-01]
duration: 15min
completed: 2026-10-20
---

# Phase 1 Plan 04: Configuration runner.toml Summary

Configuration typée stricte (Pydantic, `extra="forbid"`) avec erreurs françaises citant le chemin complet de la clé sans jamais afficher la valeur, refus des hôtes non loopback sans option explicite, et dossier de données `%LOCALAPPDATA%\Deskgate` (D-01).

## Tâches

1. Tâche 1 (TDD) : `core/config.py` et 24 tests. Commits `77d5f96` (RED), `7fe1500` (GREEN).
2. Tâche 2 (TDD) : `locations.py`, gabarit `runner.example.toml`, tests. Commit `ab1aa47`.

## Vérification

`pytest -m unit` : 142 réussis ; `tests/architecture` : 10 réussis ; ruff, ruff format et pyright propres.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocage] PydanticCustomError et pyright**
- **Issue:** pyright refuse un `str` non littéral comme gabarit de message.
- **Fix:** gabarit `"{msg}"` avec contexte `{"msg": exc.message}` ; le message final est identique.
- **Commit:** 7fe1500

Sinon, plan exécuté comme écrit.

## Exigences

- SEC-01 : le jeton n'existe dans la configuration validée que sous forme de SHA-256 (`token_sha256`, format contrôlé) ; marquée complète.
- RUN-01 : déjà complète. RUN-02 : le refus de démarrer sur configuration invalide dépend du `runtime.py` du plan 01-05 ; non marquée ici.

## Known Stubs

Aucun. (Le jeton nul du gabarit est volontaire : aucun jeton ne lui correspond.)

## Self-Check: PASSED

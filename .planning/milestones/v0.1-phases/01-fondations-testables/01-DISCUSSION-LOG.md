# Phase 1: Fondations testables - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-20
**Phase:** 1-Fondations testables
**Areas discussed:** Emplacement des données, Écoute hors loopback, Format d'erreur

---

## Emplacement des données

| Option | Description | Selected |
|--------|-------------|----------|
| %LOCALAPPDATA%\Deskgate | Hors OneDrive et hors C:\BIM, surcharge par --config ou DESKGATE_HOME | ✓ |
| Dossier du dépôt / d'installation | Mélange données et code, casse avec uv tool install | |

**User's choice:** %LOCALAPPDATA%\Deskgate

---

## Écoute hors 127.0.0.1

| Option | Description | Selected |
|--------|-------------|----------|
| Clé de config + avertissement | `allow_non_loopback = true` requis, avertissement au démarrage et dans /health | ✓ |
| Aucune option en v0.1 | 127.0.0.1 en dur | |

**User's choice:** Clé de config + avertissement

---

## Format des erreurs de l'API

| Option | Description | Selected |
|--------|-------------|----------|
| JSON stable code + message FR | `{ "error": { "code", "message" } }` | ✓ |
| Format FastAPI par défaut | `{ "detail": … }` | |

**User's choice:** JSON stable code + message FR

---

## Claude's Discretion

Commande de développement pour le jeton, contenu de /health, gabarit de runner.toml, découpage des plans.

## Deferred Ideas

Aucune.

## Décisions reprises sans les reposer

Conseil d'approche (`.arthemis/reports/llm-council-1.md`) : noyau pur et tests AST, mutex puis socket
`SO_EXCLUSIVEADDRUSE` hors lifespan, config par `tomllib` + Pydantic, SHA-256 pour le jeton, marqueurs
de tests, spikes en tête de phase.

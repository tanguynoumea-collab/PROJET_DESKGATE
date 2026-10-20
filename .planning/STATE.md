---
gsd_state_version: 1.0
milestone: v0.1
milestone_name: "Runner minimal"
status: planning
stopped_at: feuille de route créée, conseil d'approche tenu
last_updated: "2026-10-20T11:12:46.630Z"
last_activity: 2026-10-20 — feuille de route créée, conseil d'approche tenu
progress:
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-20)

**Core value:** n8n délègue une tâche longue au PC Windows et reprend fiablement quand elle se termine, quel que soit le résultat (succès, échec, délai dépassé, annulation, redémarrage du runner).
**Current focus:** Phase 1 : Fondations testables

## Current Position

Phase: 1 of 5 (Fondations testables)
Plan: 0 of 0 in current phase
Status: Ready to plan
Last activity: 2026-10-20 — feuille de route créée, conseil d'approche tenu

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: -
- Total execution time: -

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Init]: Outbox de rappels écrite dans la même transaction que l'état terminal
- [Init]: Threads + Popen + Job Object (`ctypes`) ; asyncio pour le HTTP seulement
- [Init]: `httpx2` pour le rappel ; `bcf-client` isolé dans `deskgate-bcf` (GPL-3)
- [Phase 1]: Architecture d'implémentation : .arthemis/reports/llm-council-1.md (noyau pur core/ + tests AST, thread engine + thread sender, mutex puis socket SO_EXCLUSIVEADDRUSE hors lifespan, fichiers = transport, outbox callbacks sans payload) — Conseil d'approche cycle 1
- [Phase 2]: Capacités v0.1 déclarées dans runner.toml [capabilities.<id>] (kind, python, entry, timeout_max, resource), validées par Pydantic ; aucun nom BIM dans src/deskgate — Règle 1 de CLAUDE.md ; validé par l'utilisateur
- [Phase 2]: Migration 1 complète en phase 2 (tables callbacks et audit) ; la phase 3 livre envoi, politique, plafond, masquage et contenu complet de l'audit — La recovery JOB-06 insère le rappel dans la transaction terminale ; validé par l'utilisateur
- [Phase 3]: Rappel garanti au moins une fois ; n8n ne reprend qu'une fois, un doublon reçoit 409 tracé delivered_duplicate (remplace « une fois et une seule ») — Exactement-une-fois impossible côté runner ; validé par l'utilisateur

### Pending Todos

None yet.

### Blockers/Concerns

- Spikes de recherche : phase 1 (Job Object, host.docker.internal, bind exclusif), phase 3 (409 n8n, encodage signature), phase 4 (mcp dans Job Object, `bcf-client`, multiprocessing `ifcclash`), phase 5 (Planificateur sans élévation)
- Relecture juridique de la frontière GPL avant distribution d'un binaire

## Session Continuity

Last session: 2026-10-20
Stopped at: feuille de route créée, conseil d'approche tenu
Resume file: None

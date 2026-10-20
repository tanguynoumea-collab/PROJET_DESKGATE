---
gsd_state_version: 1.0
milestone: v0.1
milestone_name: Runner minimal
status: executing
stopped_at: Completed 04-03-PLAN.md
last_updated: "2026-10-20T15:49:21.452Z"
last_activity: 2026-10-20
progress:
  total_phases: 5
  completed_phases: 3
  total_plans: 29
  completed_plans: 25
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-20)

**Core value:** n8n délègue une tâche longue au PC Windows et reprend fiablement quand elle se termine, quel que soit le résultat (succès, échec, délai dépassé, annulation, redémarrage du runner).
**Current focus:** Phase 4 — Capacités v0.1

## Current Position

Phase: 4 (Capacités v0.1) — EXECUTING
Plan: 4 of 7
Status: Ready to execute
Last activity: 2026-10-20

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
| Phase 01 P01 | 25min | 3 tasks | 13 files |
| Phase 01 P02 | 15min | 2 tasks | 4 files |
| Phase 01 P03 | 20min | 2 tasks | 13 files |
| Phase 01 P04 | 15min | 2 tasks | 5 files |
| Phase 01 P05 | 25min | 2 tasks | 7 files |
| Phase 02 P01 | 15min | 2 tasks | 6 files |
| Phase 02 P02 | 10min | 2 tasks | 6 files |
| Phase 02 P03 | 15min | 2 tasks | 6 files |
| Phase 02 P04 | 15min | 2 tasks | 8 files |
| Phase 02 P05 | 10min | 2 tasks | 7 files |
| Phase 02 P06 | 25min | 2 tasks | 4 files |
| Phase 02 P07 | 15min | 2 tasks | 5 files |
| Phase 02 P08 | 15min | 2 tasks | 4 files |
| Phase 02 P09 | 40min | 3 tasks | 7 files |
| Phase 03 P01 | 20min | 2 tasks | 11 files |
| Phase 03 P02 | 10min | 2 tasks | 3 files |
| Phase 03 P03 | 10min | 2 tasks | 4 files |
| Phase 03 P04 | 25min | 2 tasks | 5 files |
| Phase 03 P05 | 25min | 2 tasks | 7 files |
| Phase 03 P06 | 25min | 2 tasks | 5 files |
| Phase 03 P07 | 20min | 2 tasks | 4 files |
| Phase 03 P08 | 25min | 2 tasks | 2 files |
| Phase 04 P01 | 25min | 3 tasks | 25 files |
| Phase 04 P02 | 25min | 2 tasks | 15 files |
| Phase 04 P03 | 30min | 2 tasks | 6 files |

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
- [Phase 01]: ruff exclut .planning/.arthemis/.claude/docs (ruff 0.17 formate le Markdown)
- [Phase 01]: validate_artifact_path convertit le chemin hôte lexical, pas le résolu
- [Phase 01]: Handlers API : cast() à la place de assert (ruff S101)
- [Phase 02]: stop() de l'engine ne conclut jamais la tâche : recovery au redémarrage
- [Phase 3]: Migration 2 additive : colonne callbacks.maybe_delivered (posée avant chaque envoi) pour distinguer delivered_duplicate d'abandoned_stale ; 401/404 exigent deux constats consécutifs avant abandon ; pas de dernier envoi après 24 h ; 413 : un renvoi minimal puis backoff ; jobs.callback_url purgée à l'état final du rappel — Recherche phase 3 (code n8n 2.43.8) ; questions ouvertes tranchées par ARTHEMIS, aucun utilisateur réel
- [Phase 03]: CB-04 complet ; CB-05, SEC-05, SEC-06 restent Pending (03-06, 03-07)
- [Phase 03]: 03-07 : compteur de rappels et battement du sender non exposés dans /health en v0.1
- [Phase 4]: Valeurs env des serveurs MCP transmises au worker par son environnement, jamais écrites dans input.json ; path_params déclarés par capacité, convertis et validés par le runner ; Capability.settings vers ctx.settings ; kind mcp ; rendu visuel BCF dans BIMcollab = vérification humaine différée (phase 5) — Recherche phase 4 ; input.json lisible par n8n via /data/travail
- [Phase 04]: Echec de uv sync d'un plugin = pytest.fail, pas de skip silencieux
- [Phase 04]: Chemins déclarés reconvertis et revalidés au lancement ; secrets MCP hors input.json
- [Phase 04]: deskgate-bcf : stderr forcé en UTF-8 (page de code Windows)

### Pending Todos

None yet.

### Blockers/Concerns

- Spikes de recherche : phase 1 (Job Object, host.docker.internal, bind exclusif), phase 3 (409 n8n, encodage signature), phase 4 (mcp dans Job Object, `bcf-client`, multiprocessing `ifcclash`), phase 5 (Planificateur sans élévation)
- Relecture juridique de la frontière GPL avant distribution d'un binaire

## Session Continuity

Last session: 2026-10-20T15:49:21.448Z
Stopped at: Completed 04-03-PLAN.md
Resume file: None

# Phase 2: Cœur d'exécution - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-10-20
**Phase:** 2-Cœur d'exécution
**Areas discussed:** Délais, Grâce d'annulation, Dossier de travail

## Délais

| Option | Description | Selected |
|--------|-------------|----------|
| Défaut 1 h, plafond 4 h | timeout_max par capacité, plafond 4 h | |
| Défaut 2 h, plafond 12 h | Plus permissif pour les calculs de nuit | ✓ |
| Aucun plafond global | Seul timeout_max compte | |

## Grâce d'annulation

| Option | Description | Selected |
|--------|-------------|----------|
| 10 secondes | ctx.cancelled() puis TerminateJobObject | ✓ |
| 30 secondes | Plus de marge | |
| Immédiat | Sans sauvegarde partielle | |

## Dossier de travail

| Option | Description | Selected |
|--------|-------------|----------|
| Conservé | Pas de purge en v0.1 | ✓ |
| Purgé après N jours | Nettoyage au démarrage | |

## Décisions reprises sans les reposer

Conseil d'approche et STATE.md : capacités dans runner.toml, migration 1 complète en phase 2, engine unique, fichiers = transport, recovery sans lecture disque.

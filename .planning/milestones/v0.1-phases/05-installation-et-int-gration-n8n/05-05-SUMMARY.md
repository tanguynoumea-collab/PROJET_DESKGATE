---
phase: 05-installation-et-int-gration-n8n
plan: 05
subsystem: n8n
tags: [docker-compose, n8n, workflow, postgres]
requires: ["05-01"]
provides:
  - "n8n/docker-compose.yml : n8n 2.43.8 et Postgres 17 épinglés par digest, 127.0.0.1:5679, C:/BIM sur /data"
  - "n8n/examples/ifc-clash.json : workflow DeskgateClash0001 (manuel + webhook, Wait borné)"
  - "n8n/README.md : procédure de démarrage, d'import CLI et d'import manuel"
affects: [05-07]
tech-stack:
  added: []
  patterns: ["secrets obligatoires par ${VAR:?}", "test par docker compose config, sans démarrer"]
key-files:
  created:
    - n8n/docker-compose.yml
    - n8n/.env.example
    - n8n/.gitignore
    - n8n/examples/ifc-clash.json
    - n8n/README.md
    - tests/unit/test_compose.py
    - tests/unit/test_example_workflow.py
  modified: []
decisions:
  - "Fuseau par défaut du compose : UTC (GENERIC_TIMEZONE), à la place de Europe/Zurich"
metrics:
  duration: 15min
  completed: 2026-10-21
requirements-completed: [INS-03]
---

# Phase 5 Plan 05 : compose n8n et workflow d'exemple Summary

Compose n8n 2.43.8 + Postgres 17 épinglés par digest, publié sur 127.0.0.1:5679, et workflow d'exemple `ifc.clash` sans jeton (identifiant référencé par id fixe), contrôlés statiquement.

## Réalisé

- Tâche 1 (b953b3f, c91824f) : compose, `.env.example`, `n8n/.gitignore`, 6 tests `docker compose config` (marqueur docker). Les secrets manquants font échouer `config`.
- Tâche 2 (e27e42a) : workflow à 8 nœuds, README (démarrage, import CLI, lancement, lecture du résultat, n8n existant, arrêt), 7 tests statiques.

Aucun conteneur démarré, le n8n de l'utilisateur (5678) n'a pas été touché.

## Écarts par rapport au plan

**1. [Rule 1] Commentaire du compose** : le mot « latest » dans l'en-tête faisait échouer le test d'absence de « latest » ; reformulé (« jamais de tag flottant »).

**2. [Rule 1] Ruff RUF100** : `noqa: S603` inutile retiré (c91824f).

## Exigences

- INS-03 : livrée (compose épinglé, validé).
- INS-04 : laissée en attente. Seule la partie statique est livrée ici ; l'import et l'exécution réels sur n8n relèvent des plans suivants (05-07).

## Known Stubs

Aucun.

## Self-Check: PASSED

Fichiers présents ; commits b953b3f, c91824f, e27e42a ; ruff, format et pyright verts ; tests docker (6) et workflow (7) verts.

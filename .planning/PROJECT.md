# Deskgate

## What This Is

Deskgate est une passerelle locale open source (MIT) entre n8n et les outils lourds d'un PC Windows :
n8n (dans Docker) soumet une tâche, Deskgate l'exécute dans la session Windows de l'utilisateur via
un plugin déclaré (fonction Python ou outil MCP en v0.1 ; ligne de commande en cible), puis rappelle
n8n avec le résultat. Il est destiné aux coordinateurs et BIM managers qui construisent des pipelines n8n avec
des calculs IfcOpenShell longs ou des logiciels installés, en commençant par son auteur.

## Core Value

n8n délègue une tâche longue au PC Windows et reprend fiablement quand elle se termine, quel que
soit le résultat (succès, échec, délai dépassé, annulation, redémarrage du runner).

## Current State

v0.1.0 publiée le 2026-10-26 (tag `v0.1.0`), vérifiée sur la machine de l'auteur le 2026-10-27 :
runner lancé par la tâche planifiée à l'ouverture de session, `ifc.clash` et `mcp.call` depuis n8n 2.43.8 et
2.42.5, rappel garanti. Milestone GSD v0.1 « Runner minimal » archivé (`milestones/v0.1-ROADMAP.md`).
Point ouvert : verrous SQLite au repos (backlog 999.11).

## Requirements

### Validated

- ✓ Runner sur 127.0.0.1, configuration typée `runner.toml`, jeton Bearer haché, contrôle Host, instance unique, `/health`, chemins `/data` ↔ `C:/BIM` avec refus hors racines — Validated in Phase 1: Fondations testables
- ✓ File SQLite persistante, `POST/GET /jobs`, `/logs`, `/cancel`, exécution une à la fois dans un Job Object, délai avec arbre tué, `interrupted` après arrêt brutal, idempotence minimale — Validated in Phase 2: Cœur d'exécution
- ✓ Rappel vers la `resumeUrl` (au moins une fois, outbox durable, politique n8n 2.43.8, plafond 1 Mio, hôtes autorisés, signature masquée partout, audit complet) — Validated in Phase 3: Rappel fiable
- ✓ `ifc.clash` (hard/clearance, groupes, GlobalId, BCF 2.1 via `deskgate-bcf` GPL-3 en sous-processus) et `mcp.call` (serveur stdio déclaré, dans le Job Object) — Validated in Phase 4: Capacités v0.1
- ✓ Résultat `data` d'un plugin (dont `mcp.call`) transmis à n8n dans le rappel et `GET /jobs/{id}` (≤ 1 Mio, repli `data.json`), rappels isolés par ligne, `NaN`/`Infinity` refusés, `deskgate purge`, `ARCHITECTURE.md` livré/cible — Validated in Phase 5.4: corrections audit senior 1 (certifié par dev-senior, rapports 1-2 à 1-4) — v0.1

- ✓ BCF exploitable dans BIMcollab Zoom (deux points de vue avec image, contexte gris transparent), titres des sujets par gabarit et tables du job, aucun conflit perdu, réservations exclues — Validated in Phase 5.1 — v0.1
- ✓ `deskgate init` (refus en contexte MSIX), tâche planifiée à l'ouverture de session, `doctor`, compose n8n 2.43.8 épinglé et workflow d'exemple ; calcul réel repris dans n8n et arrêt brutal → `interrupted` — Validated in Phases 5, 5.2, 5.3 — v0.1

### Active

- [ ] Objectifs du prochain milestone à définir par `/gsd:new-milestone` ; candidats : verrous SQLite au
  repos (999.11), backlog 999.1 à 999.10, v0.2 de la feuille de route produit (droits par plugin, exécuteur
  `cli`, manifestes).

### Out of Scope

- Workflows n8n complets (coordination, audit, évolution), ingestion, registre des maquettes, base
  et déduplication des conflits, tri IA, Hermes, superviseur, tableau de bord — projet d'intégration
  distinct ; Deskgate n'est qu'une passerelle.
- Exposition de Deskgate comme serveur MCP — aucun usage : un agent passe par un workflow n8n
  exposé par *MCP Server Trigger* ou par l'API HTTP.
- DAG, planification, enchaînement d'étapes dans Deskgate — rôle de n8n.
- Plugin BIMcollab Zoom — inutile pour ce projet.
- Runner partagé multi-utilisateurs, exécution distante, macOS / Linux natif.
- `odm.audit_loi` — backlog, après une version fonctionnelle.

## Context

- Cadrage complet dans `docs/passation/` (vision, décisions D1-D13, architecture, pipelines cibles,
  points ouverts), `ARCHITECTURE.md`, `ROADMAP.md` (v0.1 → v0.4), `CLAUDE.md` (règles du dépôt),
  `AGENTS.md` (installation par une IA).
- Recherche de l'existant (`.arthemis/reports/existant-cycle-1.md`) : aucun projet MIT/Apache ne
  couvre le besoin ; Windmill le plus proche mais workers Windows payants et AGPL ; on construit.
  File de tâches écrite sur SQLite (Huey en plan B) ; SDK `mcp` officiel pour l'exécuteur MCP.
- Vérifications techniques (`.arthemis/reports/verifs-techniques-cycle-1.md`) : un nœud n8n
  communautaire peut se mettre en attente comme *Wait* ; Docker Desktop relaie
  `host.docker.internal` vers le loopback Windows ; `N8N_PAYLOAD_SIZE_MAX` = 16 Mio ; la
  `resumeUrl` porte un jeton `?signature=` ; IfcOpenShell 0.9.0.post1 + uv OK en 3.11 et 3.14 ;
  Job Object (création suspendue, assignation, reprise) tue les petits-enfants que psutil manque.
- Plugins BIM écrits de zéro sur l'écosystème IfcOpenShell (LGPL-3) : `ifcclash`, `ifctester`,
  `ifcdiff`, `ifc5d`, `ifcpatch`, `ifccsv`, IfcConvert. `bcf-client` est GPL-3 : isolé dans
  `deskgate-bcf`.
- Machine de l'auteur : Windows 11 Pro, uv 0.12.17, Docker 29.8.2 (Docker Desktop, WSL en NAT).
- Langue de travail : français (documents, interface, messages, commits).
- État après v0.1 : runner Python 3.14 installé par `uv tool install`, deux n8n (2.43.8 du dépôt sur 5679,
  2.42.5 de l'auteur sur 5678). Après un redémarrage, Docker Desktop ne démarre pas seul : n8n reste éteint
  tant qu'il n'est pas lancé. Pythons gérés par uv cassés (décision uv-pythons en attente, contournement
  `UV_PYTHON`).

## Constraints

- **Tenancy**: mono-tenant, un runner par PC : pas de multi-utilisateurs (D7, D9)
- **Authentification**: jetons Bearer hachés, un jeton en v0.1, droits par plugin en v0.2 : tout conteneur local peut joindre le runner
- **Données personnelles**: aucune collectée : l'audit local contient chemins et paramètres de tâches
- **Facturation**: sans objet : projet open source MIT
- **Stade**: v0.1.0 publiée, un utilisateur (l'auteur) : schéma SQLite 2, migrations additives uniquement
- **Environnements**: un seul, le PC local (runner Windows natif + n8n Docker Desktop) : pas de déploiement distant
- **Plateforme**: Windows 10/11 natif, dans la session utilisateur — pour piloter des logiciels graphiques (un service Windows ne voit pas le bureau)
- **Pile**: Python ≥ 3.11, uv, FastAPI + Uvicorn, SQLite (WAL), SDK `mcp` — même écosystème que les plugins IfcOpenShell
- **Réseau**: écoute sur 127.0.0.1 uniquement — sécurité ; suffisant avec Docker Desktop
- **Licence**: MIT, sauf `plugins/bim/bcf/` (GPL-3, appelé en sous-processus) ; aucun code GPL/AGPL ailleurs
- **Sécurité**: aucune commande libre, pas de `shell=True`, plugins en sous-processus dans un Job Object
- **n8n**: version épinglée 2.43.8 — reproductibilité
- **Cœur générique**: `src/deskgate` n'importe jamais le BIM — les plugins BIM sont un paquet séparé

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Construire plutôt que contribuer | Aucun existant open source ne couvre session Windows + rappel + manifeste + jetons | ✓ Good (v0.1 livrée) |
| File de tâches maison sur SQLite | Concurrence par ressource, `interrupted`, idempotence non couverts par Huey/RQ | ✓ Good ; ⚠️ verrous au repos à comprendre (999.11) |
| Arrêt par Job Object Windows | psutil rate les petits-enfants orphelins (testé) | ✓ Good |
| Lancement par le Planificateur de tâches | Un service Windows ne peut pas piloter d'interface | ✓ Good (constaté au redémarrage, 05-D1) |
| `resumeUrl` appelée telle quelle et masquée | Jeton `signature` vérifié par n8n, secret | ✓ Good |
| Rappel plafonné à 1 Mio, reste en `summary.json` | Petits rappels, gros résultats en artefacts | ✓ Good (étendu à `data.json`, v0.1) |
| Pas de serveur MCP Deskgate | Sans usage pour une passerelle n8n | ✓ Good |
| Plugins BIM dans ce dépôt, de zéro sur IfcOpenShell | Tests réels du runner ; ancien `bim-assistant` non repris | ✓ Good |
| `bcf-client` isolé dans `deskgate-bcf` (GPL-3), appelé en sous-processus | Utiliser la lib officielle sans contaminer le MIT | ✓ Good |
| Nœud n8n v0.3 en un seul nœud (soumission + attente) | Vérifié faisable dans le code de n8n 2.43.8 | — Pending |
| Licence MIT | Cohérence avec l'écosystème de l'auteur | ✓ Good |
| `data` du plugin exposé à n8n (≤ 1 Mio, repli fichier) | Le résultat de `mcp.call` n'atteignait pas n8n (DS-ARCH-1) | ✓ Good (v0.1) |
| ACC-01 jugé sur un calcul réel complet, pas sur la durée | Décision de l'auteur du 2026-10-21 : la coordination la plus fiable | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-27 after v0.1 milestone*

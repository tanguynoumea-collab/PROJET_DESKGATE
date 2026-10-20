# Deskgate

## What This Is

Deskgate est une passerelle locale open source (MIT) entre n8n et les outils lourds d'un PC Windows :
n8n (dans Docker) soumet une tâche, Deskgate l'exécute dans la session Windows de l'utilisateur via
un plugin déclaré (fonction Python, ligne de commande ou outil MCP), puis rappelle n8n avec le
résultat. Il est destiné aux coordinateurs et BIM managers qui construisent des pipelines n8n avec
des calculs IfcOpenShell longs ou des logiciels installés, en commençant par son auteur.

## Core Value

n8n délègue une tâche longue au PC Windows et reprend fiablement quand elle se termine, quel que
soit le résultat (succès, échec, délai dépassé, annulation, redémarrage du runner).

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Runner FastAPI sur 127.0.0.1, jeton obligatoire, file SQLite persistante
- [ ] Soumission asynchrone (`POST /jobs` → 202) et rappel vers la `resumeUrl` n8n avec réessais
- [ ] Délai maximum et arrêt de tout l'arbre de processus (Job Object Windows)
- [ ] Correspondance des chemins `/data` ↔ `C:/BIM` et refus hors racines
- [ ] Tâches `running` passées `interrupted` au redémarrage, avec rappel
- [ ] Capacités v0.1 : `ifc.clash` et `mcp.call` (outil d'un serveur MCP stdio)
- [ ] Paquet `deskgate-bcf` (GPL-3, sur `bcf-client`) appelé en sous-processus pour écrire le BCF 2.1
- [ ] `deskgate init` et démarrage à l'ouverture de session (Planificateur de tâches)
- [ ] `docker-compose` n8n 2.43.8 épinglé + workflow d'exemple HTTP Request + Wait

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

## Constraints

- **Tenancy**: mono-tenant, un runner par PC : pas de multi-utilisateurs (D7, D9)
- **Authentification**: jetons Bearer hachés, un jeton en v0.1, droits par plugin en v0.2 : tout conteneur local peut joindre le runner
- **Données personnelles**: aucune collectée : l'audit local contient chemins et paramètres de tâches
- **Facturation**: sans objet : projet open source MIT
- **Stade**: nouveau projet, aucun utilisateur : rien à migrer
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
| Construire plutôt que contribuer | Aucun existant open source ne couvre session Windows + rappel + manifeste + jetons | — Pending |
| File de tâches maison sur SQLite | Concurrence par ressource, `interrupted`, idempotence non couverts par Huey/RQ | — Pending |
| Arrêt par Job Object Windows | psutil rate les petits-enfants orphelins (testé) | — Pending |
| Lancement par le Planificateur de tâches | Un service Windows ne peut pas piloter d'interface | — Pending |
| `resumeUrl` appelée telle quelle et masquée | Jeton `signature` vérifié par n8n, secret | — Pending |
| Rappel plafonné à 1 Mio, reste en `summary.json` | Petits rappels, gros résultats en artefacts | — Pending |
| Pas de serveur MCP Deskgate | Sans usage pour une passerelle n8n | — Pending |
| Plugins BIM dans ce dépôt, de zéro sur IfcOpenShell | Tests réels du runner ; ancien `bim-assistant` non repris | — Pending |
| `bcf-client` isolé dans `deskgate-bcf` (GPL-3), appelé en sous-processus | Utiliser la lib officielle sans contaminer le MIT | — Pending |
| Nœud n8n v0.3 en un seul nœud (soumission + attente) | Vérifié faisable dans le code de n8n 2.43.8 | — Pending |
| Licence MIT | Cohérence avec l'écosystème de l'auteur | — Pending |

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
*Last updated: 2026-10-20 after initialization*

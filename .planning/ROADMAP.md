# Roadmap: Deskgate

## Overview

Milestone v0.1 : un runner minimal, prouvé de bout en bout sur une détection de conflits IFC réelle. Le noyau générique (sécurité, file SQLite, Job Object, rappel durable) est validé avec un faux plugin avant d'y brancher `ifc.clash` et `mcp.call`, puis intégré à n8n depuis la tâche planifiée. La feuille de route produit (v0.1 à v0.4) reste dans `ROADMAP.md` à la racine.

## Milestones

- 🚧 **v0.1 Runner minimal** — Phases 1-5 (in progress)

## Phases

- [x] **Phase 1: Fondations testables** - Runner local sécurisé : configuration, jeton, contrôle Host, chemins, instance unique, `/health`
 (completed 2026-10-20)
- [x] **Phase 2: Cœur d'exécution** - File SQLite, exécution en Job Object, API des tâches, délai, annulation, reprise après redémarrage
 (completed 2026-10-20)
- [x] **Phase 3: Rappel fiable** - Outbox de rappels, politique par réponse n8n, plafond de taille, masquage de la signature, audit
 (completed 2026-10-20)
- [x] **Phase 4: Capacités v0.1** - `ifc.clash`, `deskgate-bcf` (BCF 2.1) et `mcp.call`
 (completed 2026-10-20)
- [x] **Phase 5: Installation et intégration n8n** - `deskgate init`, tâche planifiée, docker-compose n8n, workflow d'exemple, acceptation (completed 2026-10-22)

## Phase Details

### Phase 1: Fondations testables
**Goal**: Un runner démarre localement avec une configuration valide, n'accepte que des requêtes authentifiées venant d'hôtes attendus et ne peut lire ou écrire que dans les racines autorisées.
**Depends on**: Nothing (first phase)
**Requirements:** RUN-01, RUN-02, RUN-03, RUN-04, SEC-01, SEC-02, SEC-03, SEC-04
**Success Criteria** (what must be TRUE):
  1. `deskgate serve` écoute sur 127.0.0.1 uniquement et refuse de démarrer sur une autre interface sans option explicite
  2. Un `runner.toml` invalide fait échouer le démarrage avec un message clair en français ; un second runner lancé en parallèle s'arrête sans toucher à la base
  3. `GET /health` répond sans jeton et sans détail sensible ; toute autre route renvoie 401 sans jeton Bearer valide et 4xx si l'en-tête `Host` n'est pas `127.0.0.1`, `localhost` ou `host.docker.internal`
  4. Un chemin `/data/...` devient `C:/BIM/...` (et inversement) ; les chemins hors racines (`..`, lien symbolique, jonction, UNC, `C:/BIM2`, nom réservé, flux alternatif) sont refusés par des tests d'attaque
**Plans:** 5/5 plans complete
Plans:
- [x] 01-01-PLAN.md — Outillage uv/CI, tests AST de frontière, mutex et socket exclusif, spike Job Object (vague 1)
- [x] 01-02-PLAN.md — Chemins : conversion /data ↔ C:/BIM et table d'attaques (vague 2)
- [x] 01-03-PLAN.md — Jeton, contrôle Host, erreurs D-08, /health (vague 2)
- [x] 01-04-PLAN.md — Configuration runner.toml typée, emplacement des données, gabarit (vague 3)
- [x] 01-05-PLAN.md — deskgate serve (ordre D-04), dev-token, tests e2e, gate complet (vague 4)
**Note de recherche**: prérequis à vérifier tôt : `host.docker.internal` joint bien le loopback ; type de boucle Uvicorn (`asyncio`).

### Phase 2: Cœur d'exécution
**Goal**: n8n peut soumettre une tâche, la suivre, l'annuler, et le runner l'exécute une à la fois dans un Job Object avec délai maximum, sans jamais perdre l'état après un arrêt brutal.
**Depends on**: Phase 1
**Requirements:** JOB-01, JOB-02, JOB-03, JOB-04, JOB-05, JOB-06, JOB-07, JOB-08, JOB-09
**Success Criteria** (what must be TRUE):
  1. `POST /jobs` renvoie immédiatement `202 { job_id, status: "queued" }` ; les tâches s'exécutent une à la fois dans l'ordre de soumission et survivent à un redémarrage (SQLite)
  2. `GET /jobs/{id}` et `/logs` renvoient état, progression, résumé, artefacts et journaux ; chaque tâche a son dossier `C:/BIM/travail/<job_id>/` et déclare ses artefacts
  3. Un faux plugin qui dépasse son délai est arrêté avec tout son arbre (petit-enfant orphelin compris) et passe `timeout` ; l'annulation (en file ou en cours) est idempotente
  4. Après `taskkill /F` du runner pendant une tâche, le redémarrage la passe `interrupted` (rappel couvert en phase 3)
  5. Une soumission avec une `idempotency_key` identique à une tâche non terminale est refusée ; le plugin tourne dans un sous-processus sans shell, jamais dans le processus du runner
**Plans:** 9/9 plans complete
Plans:
- [x] 02-01-PLAN.md — Config des capacités et work_root, contrat de soumission, codes d'erreur (vague 1)
- [x] 02-02-PLAN.md — Noyau pur : step(), verdict, protocole worker (vague 1)
- [x] 02-03-PLAN.md — Store : migration 1, file, outbox, annulation, recovery (vague 1)
- [x] 02-04-PLAN.md — jobobject (ctypes), env en liste blanche, frontières AST (vague 1)
- [x] 02-05-PLAN.md — deskgate_sdk (worker stdlib) et faux plugins (vague 2)
- [x] 02-06-PLAN.md — Engine : tick, annulation, échéance, réveil, arrêt (vague 2)
- [x] 02-07-PLAN.md — JobsService et routes /jobs, lifespan d'arrêt (vague 2)
- [x] 02-08-PLAN.md — Engine prouvé avec de vrais sous-processus (vague 3)
- [x] 02-09-PLAN.md — Câblage deskgate serve et e2e (flux, taskkill, CTRL_BREAK) (vague 4)

### Phase 3: Rappel fiable
**Goal**: n8n reprend toujours, une fois et une seule, avec le bon statut, quel que soit l'état terminal de la tâche ou l'arrêt du runner, sans fuite de la signature.
**Depends on**: Phase 2
**Requirements:** CB-01, CB-02, CB-03, CB-04, CB-05, SEC-05, SEC-06
**Success Criteria** (what must be TRUE):
  1. À chaque état terminal (`succeeded`, `failed`, `timeout`, `cancelled`, `interrupted`), un faux serveur n8n reçoit `{ job_id, capability, status, duration_s, summary, artifacts, error }` sur la `resumeUrl` telle quelle, y compris pour une tâche de moins de 100 ms
  2. Un rappel non livré est réessayé avec délai croissant et reprend après un redémarrage du runner ; les réponses sont distinguées (livré, Wait pas encore en attente, exécution terminée ou inconnue, signature refusée) avec abandon tracé quand il faut
  3. Un résumé de plus de 1 Mio est écrit dans `summary.json` et le rappel n'en porte que le chemin ; un hôte de rappel non autorisé est refusé
  4. La `signature` n'apparaît dans aucun journal, aucune réponse d'API ni l'audit ; chaque soumission, refus, fin de tâche et rappel figure dans l'audit local
**Plans:** 8/8 plans complete

Plans:
- [x] 03-01-PLAN.md — httpx2 en dépendance, configuration [callback], hôtes par défaut, faux n8n 2.43.8 (vague 0)
- [x] 03-02-PLAN.md — Politique pure : classify, next_delay, check_callback_url (TDD)
- [x] 03-03-PLAN.md — Corps du rappel pur (core/payload) et masquage unique étendu (core/redact)
- [x] 03-04-PLAN.md — Store : migration 2 (maybe_delivered), outbox durable, purge, audit enrichi
- [x] 03-05-PLAN.md — Plafond 1 Mio et summary.json dans l'engine ; hôte autorisé et audit des refus à la soumission
- [x] 03-06-PLAN.md — Thread sender : envoi de la resumeUrl telle quelle, réessais, politique de réponse
- [x] 03-07-PLAN.md — Câblage du sender dans deskgate serve, journaux masqués, rappel e2e pour 4 statuts
- [x] 03-08-PLAN.md — E2E : reprise après taskkill, envoi interrompu, statut interrupted, balayage de la signature, gate
**Note de recherche**: spike court : textes exacts des 409 de n8n 2.43.8 ; `httpx2` ne réencode pas la signature (hôte seulement réécrit, query intacte).

### Phase 4: Capacités v0.1
**Goal**: Le runner réalise un vrai travail : détecter des conflits IFC avec export BCF 2.1 et appeler un outil MCP stdio, sans contaminer le code MIT avec du GPL.
**Depends on**: Phase 3
**Requirements:** CAP-01, CAP-02, CAP-03, CAP-04, CAP-05
**Success Criteria** (what must be TRUE):
  1. `ifc.clash` sur deux sélections IFC réelles renvoie un JSON groupé avec les GlobalId de chaque paire, en modes `hard` et `clearance` (tolérance explicite) ; une sélection vide donne un succès à 0 conflit avec avertissement
  2. Sur demande, `ifc.clash` produit un BCF 2.1 ouvrable, avec deux points de vue par sujet (objets seuls ; contexte gris transparent), couleurs ARGB, sans sélection enregistrée
  3. `mcp.call` appelle un outil d'un serveur MCP stdio déclaré, sans LLM, dans le Job Object de la tâche, et renvoie son résultat ; l'arrêt de la tâche tue le serveur MCP
  4. `deskgate-bcf` (GPL-3) écrit le BCF depuis un JSON versionné en sous-processus ; un test CI échoue si un autre paquet importe `bcf-client` ou `deskgate-bcf`
**Plans**: 7 plans

Plans:
- [x] 04-01-PLAN.md — Workspace uv, squelettes deskgate-bim / deskgate-bcf, contrat bcf-write-v1, garde-fous GPL (AST, licences, sdist)
- [x] 04-02-PLAN.md — Cœur générique : settings, path_params, kind mcp et mcp_servers, ctx.settings, codes d'erreur des plugins
- [x] 04-03-PLAN.md — deskgate-bcf (GPL-3) : écriture BCF 2.1 à deux vues depuis le JSON du contrat, codes 0/2/3
- [x] 04-04-PLAN.md — ifc.clash : DeskgateClasher, modes hard/clearance, regroupement déterministe, sélection vide, erreurs classées
- [x] 04-05-PLAN.md — mcp.call : worker MCP stdio dans le Job Object, mini-serveur de test, arrêt de l'arbre, secrets hors disque
- [x] 04-06-PLAN.md — Classement memory_limit par le pic mémoire du Job Object
- [x] 04-07-PLAN.md — Sortie BCF d'ifc.clash (contexte gris, appel de deskgate-bcf), bout en bout, documentation

**Note de recherche**: spikes nécessaires : SDK `mcp` 2.x dans un Job Object ; API bas niveau de `bcf-client` ; multiprocessing de `ifcclash` sous Windows.

### Phase 5: Installation et intégration n8n
**Goal**: Sur la machine cible, un utilisateur installe Deskgate, lance n8n épinglé et voit un calcul long déclenché depuis n8n reprendre avec son résultat, même après un arrêt brutal du runner.
**Depends on**: Phase 4
**Requirements:** INS-01, INS-02, INS-03, INS-04, INS-05, ACC-01, ACC-02
**Success Criteria** (what must be TRUE):
  1. `deskgate init` crée `runner.toml`, `C:\BIM` (`depot`, `travail`, `livrables`) et un jeton affiché une seule fois ; avec l'accord de l'utilisateur, il installe une tâche du Planificateur lancée à l'ouverture de session, sans limite de durée et même sur batterie
  2. `n8n/docker-compose.yml` lance n8n 2.43.8 avec Postgres et `C:\BIM` monté sur `/data` ; depuis le conteneur, `http://host.docker.internal:8765/health` répond
  3. Le workflow d'exemple importé (HTTP Request, Wait, test du `status`) déclenche `ifc.clash` et reprend sur le rappel
  4. Acceptation : un calcul de plus de 10 minutes, runner démarré par la tâche planifiée, reprend dans n8n avec le résumé et le chemin du BCF
  5. Acceptation : un arrêt brutal du runner pendant une tâche produit, au redémarrage, un rappel `interrupted` reçu par n8n
**Plans:** 9/9 plans complete
Plans:
- [x] 05-01-PLAN.md — Module scheduler : XML de tâche D-03, relecture, enveloppe schtasks, marqueurs (vague 1)
- [x] 05-02-PLAN.md — Journal fichier après le mutex (pythonw) et deskgate --version (vague 1)
- [x] 05-03-PLAN.md — deskgate init et deskgate task install|remove|status|run|end (vague 2)
- [x] 05-05-PLAN.md — Compose n8n 2.43.8 + Postgres, workflow d'exemple ifc-clash.json, tests statiques (vague 2)
- [x] 05-04-PLAN.md — deskgate doctor (configuration, dossiers, jeton, tâche, port, plugins) (vague 3)
- [x] 05-06-PLAN.md — Installation sur la machine : outil uv, init --yes, plugins, maquettes, runner lancé par la tâche (vague 4)
- [x] 05-07-PLAN.md — Scripts de recette, compose démarré, import, INS-05, calcul court INS-04 sur 2.43.8 (vague 5)
- [x] 05-08-PLAN.md — Acceptation ACC-01 (calcul long) et ACC-02 (arrêt brutal), 05-ACCEPTANCE.md (vague 6)
- [x] 05-09-PLAN.md — AGENTS.md, ARCHITECTURE.md, README d'après l'installation réelle (vague 7)
**Note de recherche**: spikes nécessaires : Planificateur de tâches sans élévation (XML `schtasks`, repli `HKCU\Run`) ; `gui-scripts` sous uv ; sortie du Wait à l'échéance.

## Progress

| Phase | Plans terminés | Statut | Terminée |
|-------|----------------|--------|----------|
| 1. Fondations testables | 0/5 | Complete    | 2026-10-20 |
| 2. Cœur d'exécution | 0/9 | Complete    | 2026-10-20 |
| 3. Rappel fiable | 0/0 | Complete    | 2026-10-20 |
| 4. Capacités v0.1 | 0/0 | Complete    | 2026-10-20 |
| 5. Installation et intégration n8n | 6/9 | Complete    | 2026-10-22 |

### Phase 05.1: BCF exploitable dans BIMcollab et nommage des sujets (INSERTED)

**Goal:** Le BCF d'`ifc.clash` s'ouvre dans BIMcollab Zoom avec ses deux points de vue par sujet, chaque sujet est titré selon la convention de tri du projet, et aucun conflit n'est perdu ni inventé par les réservations.
**Requirements**: CAP-02, CAP-06, CAP-07
**Success Criteria** (what must be TRUE):
  1. Le BCF du calcul réel CVC × ARC, ouvert dans BIMcollab Zoom avec les deux maquettes, montre pour chaque sujet ses deux points de vue (objets seuls ; contexte gris transparent, aucun élément visible dans ses couleurs d'origine, D-18), cadrés sur le conflit (04-D1)
  2. Les sujets sont titrés d'après un gabarit et des tables de correspondance fournis par le job (champs building, storey, trade_a, trade_b, type_a, type_b) ; aucune valeur métier dans le plugin ; une valeur absente d'une table reste brute avec un avertissement (révisé le 2026-10-22)
  3. Sur les maquettes réelles, `clashes.json` et le BCF contiennent tous les conflits par défaut, ou la troncature est explicite et signalée ; les réservations sont exclues par défaut
  4. Le workflow d'exemple n8n passe la charte du projet pilote (gabarit + tables) et les réglages de coordination fiable
**Depends on:** Phase 5
**Plans:** 13/13 plans complete

Plans:
- [x] 05.1-01-PLAN.md — Pillow et uv.lock, contrat bcf-write-v2 (3 copies), scènes IFC synthétiques
- [x] 05.1-02-PLAN.md — deskgate-bcf v2 : snapshots, commentaires, viewpoint.bcfv/snapshot.png, Index, Header/File (verdict Zoom V4/V5)
- [x] 05.1-03-PLAN.md — naming.py en TDD : table de libellés, étage par cote, technique, titre
- [x] 05.1-04-PLAN.md — Volume et réservations : défaut sans plafond, drapeaux distincts, IfcOpeningElement exclus, grille
- [x] 05.1-05-PLAN.md — Charte du job, spatial.py, titres des sujets, document BCF v2 trié
- [x] 05.1-06-PLAN.md — Rendu 3D logiciel (Pillow) des deux points de vue, snapshots dans ifc.clash
- [x] 05.1-07-PLAN.md — Header/File des maquettes, exemple n8n et documentation, script de mise à jour des plugins
- [x] 05.1-08-PLAN.md — Recette réelle CVC x ARC depuis n8n, contrôle du BCF, ACCEPTANCE (Zoom différé)
- [x] 05.1-09-PLAN.md — (écart) Nommage générique dans le plugin : title_template + mappings, LABELS/TRADE_CODES/Charter retirés
- [x] 05.1-10-PLAN.md — (écart) Charte PIC dans l'exemple n8n (ifc-clash-params.json), README, AGENTS.md, bcf_check par gabarit
- [x] 05.1-11-PLAN.md — (écart) Trois BCF de test de la vue 2 (A isolé, B maquette grise, C voisinage large) pour Zoom
- [x] 05.1-12-PLAN.md — (écart, bloquant B1) Choix de l'approche de la vue 2 dans Zoom, généralisation, règle D-18 dans bcf_check
- [x] 05.1-13-PLAN.md — (écart) Recette 2 réelle depuis n8n, ACCEPTANCE, Zoom différé 05.1-D2 (solde 04-D1)

## Backlog

### Phase 999.1: Rappel : source unique des etats, plafond 1 Mio unique, index des rappels dus (MNT-002, ARC-005, DON-002) (BACKLOG)

**Goal:** [Captured for future planning]
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.2: Base : retention et purge, sauvegarde avant migration (DON-001, DON-003) (BACKLOG)

**Goal:** [Captured for future planning]
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.3: Installation et CI : contraintes du lock, versions des plugins, test obligatoire saute (LIV-002, LIV-004, TST-001) (BACKLOG)

**Goal:** [Captured for future planning]
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.4: Plugin BIM : decoupage de clash, typage, test IfcElement (MNT-001, MNT-003, MNT-005, MNT-009, ARC-003, TST-002) (BACKLOG)

**Goal:** [Captured for future planning]
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.5: Noyau : test AST, champ data, mcp_call, typage doctor, events.jsonl (ARC-002, ARC-004, MNT-006, MNT-008, FIA-004) (BACKLOG)

**Goal:** [Captured for future planning]
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

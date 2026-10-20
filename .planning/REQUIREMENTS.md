# Requirements: Deskgate

**Defined:** 2026-10-20
**Core Value:** n8n délègue une tâche longue au PC Windows et reprend fiablement quand elle se termine, quel que soit le résultat (succès, échec, délai dépassé, annulation, redémarrage du runner).

## v1 Requirements

Milestone v0.1 : runner minimal prouvé sur une détection de conflits réelle. Chaque exigence correspond à une phase du ROADMAP.

### Runner

- [x] **RUN-01**: L'utilisateur démarre le runner (`deskgate serve`) et il n'écoute que sur 127.0.0.1 ; il refuse de démarrer sur une autre interface sans option explicite
- [ ] **RUN-02**: Le runner lit sa configuration typée dans `runner.toml` (port, racines autorisées, correspondance des chemins, jeton, délais) et refuse de démarrer sur une configuration invalide avec un message clair en français
- [x] **RUN-03**: Un second runner lancé pendant que le premier tourne s'arrête sans toucher à la base ni aux tâches
- [x] **RUN-04**: `GET /health` répond sans jeton, sans détail sensible

### Sécurité

- [x] **SEC-01**: Toute route sauf `/health` refuse une requête sans jeton Bearer valide (401) ; le jeton est stocké haché
- [x] **SEC-02**: Le runner refuse une requête dont l'en-tête `Host` n'est pas `127.0.0.1`, `localhost` ou `host.docker.internal`
- [x] **SEC-03**: Un chemin `/data/...` est converti en `C:/BIM/...` (et inversement pour les artefacts renvoyés)
- [x] **SEC-04**: Un chemin hors des racines autorisées est refusé, y compris via `..`, lien symbolique, jonction, chemin UNC, préfixe de segment (`C:/BIM2`), nom réservé ou flux alternatif
- [ ] **SEC-05**: La `signature` de la `resumeUrl` n'apparaît dans aucun journal, aucune réponse d'API ni l'audit
- [ ] **SEC-06**: Chaque soumission, refus, fin de tâche et rappel est inscrit dans un journal d'audit local (client, capacité, paramètres sans secrets, début, fin, statut, durée)

### Tâches

- [ ] **JOB-01**: n8n soumet une tâche par `POST /jobs` et reçoit immédiatement `202 { job_id, status: "queued" }`
- [ ] **JOB-02**: Les tâches sont persistées dans SQLite et exécutées une à la fois, dans l'ordre de soumission
- [ ] **JOB-03**: `GET /jobs/{id}` renvoie l'état, la progression, le résumé et les artefacts ; `GET /jobs/{id}/logs` renvoie les journaux
- [ ] **JOB-04**: `POST /jobs/{id}/cancel` annule une tâche en file ou en cours (annulation coopérative, puis arrêt forcé) ; l'appel est idempotent
- [ ] **JOB-05**: Une tâche qui dépasse son délai maximum est arrêtée avec tout son arbre de processus (petits-enfants orphelins compris) et passe `timeout`
- [ ] **JOB-06**: Au redémarrage du runner, chaque tâche `running` passe `interrupted` et son rappel est envoyé
- [ ] **JOB-07**: Un plugin s'exécute dans un sous-processus placé dans un Job Object Windows, jamais dans le processus du runner, sans shell
- [ ] **JOB-08**: Une soumission avec une `idempotency_key` identique à une tâche non terminale est refusée (pas de double calcul)
- [ ] **JOB-09**: Chaque tâche dispose d'un dossier de travail `C:/BIM/travail/<job_id>/` et déclare ses artefacts produits

### Rappel

- [ ] **CB-01**: À chaque état terminal (`succeeded`, `failed`, `timeout`, `cancelled`, `interrupted`), le runner appelle la `resumeUrl` telle quelle avec `{ job_id, capability, status, duration_s, summary, artifacts, error }`
- [ ] **CB-02**: Un rappel non livré est réessayé avec délai croissant, y compris après un redémarrage du runner (aucun résultat perdu)
- [ ] **CB-03**: Le runner distingue les réponses de n8n : livré, Wait pas encore en attente (réessai court), exécution déjà terminée ou inconnue (abandon tracé), refus de signature (abandon tracé)
- [ ] **CB-04**: Un résumé trop volumineux pour le rappel (> 1 Mio) est écrit dans `summary.json` et le rappel n'en porte que le chemin
- [ ] **CB-05**: Le rappel n'est envoyé qu'à un hôte autorisé dans `runner.toml`

### Capacités

- [ ] **CAP-01**: La capacité `ifc.clash` détecte les conflits entre deux sélections IFC en modes `hard` et `clearance` (tolérance explicite), regroupe les résultats et renvoie un JSON avec les GlobalId de chaque paire
- [ ] **CAP-02**: `ifc.clash` produit sur demande un BCF 2.1 avec deux points de vue par sujet (objets du conflit seuls ; contexte gris transparent), couleurs ARGB, sans sélection enregistrée
- [ ] **CAP-03**: `ifc.clash` traite une sélection vide comme un succès à 0 conflit avec avertissement
- [ ] **CAP-04**: La capacité `mcp.call` appelle un outil d'un serveur MCP stdio déclaré dans la configuration, sans LLM, dans le Job Object de la tâche, et renvoie son résultat
- [ ] **CAP-05**: Le paquet `deskgate-bcf` (GPL-3) écrit un BCF 2.1 à partir d'un fichier JSON versionné, appelé en sous-processus ; aucun autre paquet n'importe `bcf-client` ni `deskgate-bcf` (vérifié par un test)

### Installation et intégration

- [ ] **INS-01**: `deskgate init` crée `runner.toml`, le dossier `C:\BIM` (`depot`, `travail`, `livrables`) et le jeton, affiché une seule fois
- [ ] **INS-02**: `deskgate init` installe, avec l'accord de l'utilisateur, une tâche du Planificateur qui lance le runner à l'ouverture de session, sans limite de durée et même sur batterie
- [ ] **INS-03**: `n8n/docker-compose.yml` lance n8n 2.43.8 épinglé avec Postgres et `C:\BIM` monté sur `/data`
- [ ] **INS-04**: Un workflow d'exemple importable (HTTP Request → Wait → test du `status`) déclenche `ifc.clash` et reprend sur le rappel
- [ ] **INS-05**: Depuis le conteneur n8n, `http://host.docker.internal:8765/health` répond (vérifié sur la machine cible)

### Acceptation

- [ ] **ACC-01**: Un calcul de plus de 10 minutes lancé depuis n8n, avec le runner démarré par la tâche planifiée, reprend dans n8n avec le résumé et le chemin du BCF
- [ ] **ACC-02**: Un arrêt brutal du runner pendant une tâche produit, au redémarrage, un rappel `interrupted` reçu par n8n

### Socle ARTHEMIS

- [ ] **SOC-01**: Le gate du profil (`profil.gate[]`) passe vert sur toutes les cibles, journal dans `.arthemis/reports/gate-<date>.log`
- [ ] **SOC-02**: Les tests sont 100 % verts ; aucun test retiré ni ignoré sans décision datée dans `.arthemis/events.jsonl`
- [ ] **SOC-03**: Chaque finding critique du cycle est corrigé et re-vérifié ; aucun item `corrige_non_certifie` dans `items_ouverts[]`
- [ ] **AUD-01**: Le council du profil (saas-team-council) a tourné ; rapport dans `audits/` ; triage daté dans `checkpoints.triage`
- [ ] **AUD-02**: Les findings reportés sont au backlog GSD ou dans `items_ouverts[]` ; aucun finding bloquant ni critique ouvert
- [ ] **AUD-03**: dev-senior a relu le projet ; rapport dans `.arthemis/reports/dev-senior-1-<n>.md` ; zéro bloquant
- [ ] **PUB-01**: La version est bumpée dans `pyproject.toml` ; CHANGELOG généré depuis les SUMMARY du milestone
- [ ] **PUB-02**: Le go publication est daté et commité dans `checkpoints.go_publication` ; aucun item `uat` ou `action_humaine` qui retient la publication n'est ouvert
- [ ] **PUB-03**: Le tag `v0.1.0` est posé sur le commit livré, poussé, inscrit dans `livraisons[]` et dans la ligne `**Version produit :**` de MILESTONES.md
- [ ] **PUB-04**: Vérification 11a sur la machine cible : runner démarré par la tâche planifiée, `/health` répond, parcours n8n de bout en bout passe ; `exploitation.verification_11a` renseigné
- [ ] **PUB-05**: Plan de retour arrière écrit dans `exploitation.plan_retour_arriere` avant le go (désinstallation, sort de la base, retrait de la tâche planifiée)

## v2 Requirements

Milestones ultérieurs (voir `ROADMAP.md` à la racine). Non planifiés dans ce milestone.

### v0.2 — Plugins génériques et droits

- **PLG-01**: Manifeste `plugin.yaml` validé ; exécuteurs `python` (environnement uv isolé), `cli` (gabarit sans shell), `mcp` (stdio et Streamable HTTP)
- **PLG-02**: `deskgate plugin add | remove | list`, `deskgate doctor`
- **PLG-03**: Ressources et concurrence (`gui-session`, `cpu-heavy`, `light`)
- **PLG-04**: Jetons multiples, droits par plugin, `deskgate token create | revoke`
- **PLG-05**: Idempotence complète (réutilisation du résultat)
- **PLG-06**: Plugins `ifc.audit`, `ifc.diff`, `ifc.quantities`, `ifc.validate`, `ifc.info` ; `ifc.clash` en manifeste, modes `touch` et `duplicate`
- **PLG-07**: `deskgate-bcf` : lecture `.bcf` → JSON, BCF 3.0, plugins `bcf.write` / `bcf.read`
- **PLG-08**: Téléchargement d'artefacts `GET /jobs/{id}/artifacts/{name}`

### v0.3 — Nœud n8n et interface

- **N8N-01**: Nœud `n8n-nodes-deskgate` : soumission et attente dans un seul nœud, capacités dynamiques, champs depuis le schéma
- **UI-01**: Interface `/ui` : catalogue, test, tâches, journaux, jetons, audit, diagnostic
- **PLG-09**: Plugins `ifc.patch`, `ifc.convert`, `ifc.table`

### v0.4 — Reproductibilité et publication

- **REP-01**: `pipeline.lock` et `deskgate plugin install --from pipeline.lock`
- **REP-02**: `AGENTS.md` éprouvé sur un PC vierge ; publication GitHub, PyPI, npm

## Out of Scope

| Feature | Reason |
|---------|--------|
| Workflows complets, ingestion, registre des maquettes, déduplication des conflits, tri IA | Projet d'intégration distinct ; Deskgate n'est qu'une passerelle |
| Hermes, superviseur, tableau de bord | Contexte d'usage, hors produit |
| Deskgate comme serveur MCP | Aucun usage : n8n *MCP Server Trigger* ou API HTTP suffisent |
| DAG, planification, enchaînement | Rôle de n8n |
| Réessai automatique des tâches échouées | Décision de l'orchestrateur ; seul le rappel est réessayé |
| Poussée de progression vers n8n | La `resumeUrl` ne permet qu'une reprise |
| Téléversement HTTP de fichiers IFC | On transmet des chemins dans le dossier partagé |
| Plugin BIMcollab Zoom | Inutile pour ce projet |
| `odm.audit_loi` | Backlog, après une version fonctionnelle |
| Multi-utilisateurs, exécution distante, macOS / Linux | Un runner par PC, Windows cible |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| RUN-01 | Phase 1 | Complete |
| RUN-02 | Phase 1 | Pending |
| RUN-03 | Phase 1 | Complete |
| RUN-04 | Phase 1 | Complete |
| SEC-01 | Phase 1 | Complete |
| SEC-02 | Phase 1 | Complete |
| SEC-03 | Phase 1 | Complete |
| SEC-04 | Phase 1 | Complete |
| JOB-01 | Phase 2 | Pending |
| JOB-02 | Phase 2 | Pending |
| JOB-03 | Phase 2 | Pending |
| JOB-04 | Phase 2 | Pending |
| JOB-05 | Phase 2 | Pending |
| JOB-06 | Phase 2 | Pending |
| JOB-07 | Phase 2 | Pending |
| JOB-08 | Phase 2 | Pending |
| JOB-09 | Phase 2 | Pending |
| CB-01 | Phase 3 | Pending |
| CB-02 | Phase 3 | Pending |
| CB-03 | Phase 3 | Pending |
| CB-04 | Phase 3 | Pending |
| CB-05 | Phase 3 | Pending |
| SEC-05 | Phase 3 | Pending |
| SEC-06 | Phase 3 | Pending |
| CAP-01 | Phase 4 | Pending |
| CAP-02 | Phase 4 | Pending |
| CAP-03 | Phase 4 | Pending |
| CAP-04 | Phase 4 | Pending |
| CAP-05 | Phase 4 | Pending |
| INS-01 | Phase 5 | Pending |
| INS-02 | Phase 5 | Pending |
| INS-03 | Phase 5 | Pending |
| INS-04 | Phase 5 | Pending |
| INS-05 | Phase 5 | Pending |
| ACC-01 | Phase 5 | Pending |
| ACC-02 | Phase 5 | Pending |
| SOC-01 | Phase 5 | Pending |
| SOC-02 | Phase 5 | Pending |
| SOC-03 | Phase 5 | Pending |
| AUD-01 | Phase 5 | Pending |
| AUD-02 | Phase 5 | Pending |
| AUD-03 | Phase 5 | Pending |
| PUB-01 | Phase 5 | Pending |
| PUB-02 | Phase 5 | Pending |
| PUB-03 | Phase 5 | Pending |
| PUB-04 | Phase 5 | Pending |
| PUB-05 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 47 total (dont 11 de socle ARTHEMIS, cochés par requirements mark-complete, hors ligne Requirements du ROADMAP)
- Mapped to phases: 47
- Unmapped: 0 ✓

---
*Requirements defined: 2026-10-20*
*Last updated: 2026-10-20 after roadmap creation (traceability, count fixed to 36)*

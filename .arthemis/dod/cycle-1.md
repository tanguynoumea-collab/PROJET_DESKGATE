# Definition of Done : deskgate, cycle 1 (milestone GSD v0.1, version cible 0.1.0)

> Instanciée le 2026-10-20 à l'entrée en IMPLEMENTATION, gelée à la clôture. Modèle : `arthemis-orchestrator/assets/dod_template.md`.

## Marqueurs (les seuls admis)

- `- [ ]` : à faire. `- [x] … (preuve: <sha|chemin|REQ>)` : fait. `- [~] renoncé le <AAAA-MM-JJ> : <motif>` : renoncé, jamais fait.

## Socle commun

- [ ] Toutes les phases 1 à 5 ont un SUMMARY par PLAN, VERIFICATION `passed` ou `human_needed` soldé, aucun UAT pending (preuve : liste des SUMMARY et statuts)
- [ ] Aucun `*-UAT.md` ni `*-HUMAN-UAT.md` en `testing`, `partial` ou `diagnosed` ; aucun `result: pending` (preuve : grep collé)
- [x] Aucune VERIFICATION en `gaps_found` sans phase de gaps exécutée (preuve: aucune VERIFICATION en gaps_found ; écarts de 5.4 fermés par les plans 06 à 09, 9a7305c)
- [x] Gate du profil vert : chaque commande de `profil.gate[]` exécutée, code 0, journal dans `.arthemis/reports/gate-1-<phase>.log` (preuve: .arthemis/reports/gate-1-05.4.log, 93f7d0c)
- [x] Tests 100 % verts ; aucun test retiré ou ignoré sans décision datée (les skip explicites de liens symboliques sans mode développeur sont déclarés) (preuve: .arthemis/reports/gate-1-05.4.log, 1053 passés, 2 skips de liens symboliques déclarés, 33 e2e)
- [x] Aucun secret introduit dans le code ou le dépôt (preuve: git grep des motifs de clés privées, jetons ghp_/sk-/AKIA et mots de passe en clair : aucun résultat (2026-10-26))
- [x] Aucun item `finding` en `corrige_non_certifie` (preuve: state.json du 2026-10-26, items_ouverts sans finding)
- [ ] REQUIREMENTS.md : chaque exigence du milestone `[x]` ou Dropped daté (preuve : table Traceability)

## Socle web_saas (adapté : runner local mono-tenant)

- [x] Les 8 portes du GATE vertes ou NON COUVERTES avec motif et item `porte_non_couverte` (installation figée · types · lint · tests · build · E2E · migrations · budgets) (preuve: .arthemis/reports/gate-1-05.4.log, 7 portes vertes et migrations couvertes ; budgets sans objet (runner local, aucun bundle client))
- [x] Toute route HTTP a la garde du jeton et du contrôle Host, sauf `/health` publique assumée (preuve: api/app.py:46-47 BearerAuthMiddleware et HostCheckMiddleware sur toute l'app ; routes /jobs (POST, GET, logs, cancel) et /health seule publique)
- [x] Tout appel réseau sortant (rappel, MCP HTTP) a un timeout (preuve: sender.py:65 httpx2.Timeout(30, connect=5) ; mcp_call.py:94 read_timeout_seconds ; doctor.py:88 timeout)
- [x] Toute nouvelle clé de configuration est documentée dans le gabarit commenté de `runner.toml` ; aucun secret dans les journaux (preuve: tests/unit/test_runner_example.py vert au gate ; phase 5.4 sans nouvelle clé (purge en option de CLI) ; signature masquée (tests/unit/test_callback_url.py))
- [x] Frontière GPL : aucun paquet hors `plugins/bim/bcf/` n'importe `bcf` ni `deskgate_bcf` ; `core/` n'importe ni `sqlite3`, `subprocess`, `httpx2`, `fastapi`, `ctypes` (preuve: tests/architecture/test_import_boundaries.py, 29 tests verts au gate)
- [x] Plan de retour arrière écrit dans `exploitation.plan_retour_arriere` (désinstallation, base conservée, tâche planifiée retirée) (preuve: state.json extension.web_saas.exploitation.plan_retour_arriere, 2026-10-26)

## Par exigence du milestone

- [x] **RUN-01** : L'utilisateur démarre le runner (`deskgate serve`) et il n'écoute que sur 127.0.0.1 ; il refuse de démarrer sur une autre interface sans option explicite (preuve: REQ RUN-01 Complete, phase 1, 01-VERIFICATION.md)
- [x] **RUN-02** : Le runner lit sa configuration typée dans `runner.toml` (port, racines autorisées, correspondance des chemins, jeton, délais) et refuse de démarrer sur une configuration invalide avec un message clair en français (preuve: REQ RUN-02 Complete, phase 1, 01-VERIFICATION.md)
- [x] **RUN-03** : Un second runner lancé pendant que le premier tourne s'arrête sans toucher à la base ni aux tâches (preuve: REQ RUN-03 Complete, phase 1, 01-VERIFICATION.md)
- [x] **RUN-04** : `GET /health` répond sans jeton, sans détail sensible (preuve: REQ RUN-04 Complete, phase 1, 01-VERIFICATION.md)
- [x] **SEC-01** : Toute route sauf `/health` refuse une requête sans jeton Bearer valide (401) ; le jeton est stocké haché (preuve: REQ SEC-01 Complete, phase 1, 01-VERIFICATION.md)
- [x] **SEC-02** : Le runner refuse une requête dont l'en-tête `Host` n'est pas `127.0.0.1`, `localhost` ou `host.docker.internal` (preuve: REQ SEC-02 Complete, phase 1, 01-VERIFICATION.md)
- [x] **SEC-03** : Un chemin `/data/...` est converti en `C:/BIM/...` (et inversement pour les artefacts renvoyés) (preuve: REQ SEC-03 Complete, phase 1, 01-VERIFICATION.md)
- [x] **SEC-04** : Un chemin hors des racines autorisées est refusé, y compris via `..`, lien symbolique, jonction, chemin UNC, préfixe de segment (`C:/BIM2`), nom réservé ou flux alternatif (preuve: REQ SEC-04 Complete, phase 1, 01-VERIFICATION.md)
- [x] **SEC-05** : La `signature` de la `resumeUrl` n'apparaît dans aucun journal, aucune réponse d'API ni l'audit (preuve: REQ SEC-05 Complete, phase 3, 03-VERIFICATION.md)
- [x] **SEC-06** : Chaque soumission, refus, fin de tâche et rappel est inscrit dans un journal d'audit local (client, capacité, paramètres sans secrets, début, fin, statut, durée) (preuve: REQ SEC-06 Complete, phase 3, 03-VERIFICATION.md)
- [x] **JOB-01** : n8n soumet une tâche par `POST /jobs` et reçoit immédiatement `202 { job_id, status: "queued" }` (preuve: REQ JOB-01 Complete, phase 2, 02-VERIFICATION.md)
- [x] **JOB-02** : Les tâches sont persistées dans SQLite et exécutées une à la fois, dans l'ordre de soumission (preuve: REQ JOB-02 Complete, phase 2, 02-VERIFICATION.md)
- [x] **JOB-03** : `GET /jobs/{id}` renvoie l'état, la progression, le résumé et les artefacts ; `GET /jobs/{id}/logs` renvoie les journaux (preuve: REQ JOB-03 Complete, phase 2, 02-VERIFICATION.md)
- [x] **JOB-04** : `POST /jobs/{id}/cancel` annule une tâche en file ou en cours (annulation coopérative, puis arrêt forcé) ; l'appel est idempotent (preuve: REQ JOB-04 Complete, phase 2, 02-VERIFICATION.md)
- [x] **JOB-05** : Une tâche qui dépasse son délai maximum est arrêtée avec tout son arbre de processus (petits-enfants orphelins compris) et passe `timeout` (preuve: REQ JOB-05 Complete, phase 2, 02-VERIFICATION.md)
- [x] **JOB-06** : Au redémarrage du runner, chaque tâche `running` passe `interrupted` et son rappel est envoyé (preuve: REQ JOB-06 Complete, phase 2, 02-VERIFICATION.md)
- [x] **JOB-07** : Un plugin s'exécute dans un sous-processus placé dans un Job Object Windows, jamais dans le processus du runner, sans shell (preuve: REQ JOB-07 Complete, phase 2, 02-VERIFICATION.md)
- [x] **JOB-08** : Une soumission avec une `idempotency_key` identique à une tâche non terminale est refusée (pas de double calcul) (preuve: REQ JOB-08 Complete, phase 2, 02-VERIFICATION.md)
- [x] **JOB-09** : Chaque tâche dispose d'un dossier de travail `C:/BIM/travail/<job_id>/` et déclare ses artefacts produits (preuve: REQ JOB-09 Complete, phase 2, 02-VERIFICATION.md)
- [x] **CB-01** : À chaque état terminal (`succeeded`, `failed`, `timeout`, `cancelled`, `interrupted`), le runner appelle la `resumeUrl` telle quelle avec `{ job_id, capability, status, duration_s, summary, artifacts, error }` (preuve: REQ CB-01 Complete, phase 3, 03-VERIFICATION.md)
- [x] **CB-02** : Un rappel non livré est réessayé avec délai croissant, y compris après un redémarrage du runner (aucun résultat perdu) (preuve: REQ CB-02 Complete, phase 3, 03-VERIFICATION.md)
- [x] **CB-03** : Le runner distingue les réponses de n8n : livré, Wait pas encore en attente (réessai court), exécution déjà terminée ou inconnue (abandon tracé), refus de signature (abandon tracé) (preuve: REQ CB-03 Complete, phase 3, 03-VERIFICATION.md)
- [x] **CB-04** : Un résumé trop volumineux pour le rappel (> 1 Mio) est écrit dans `summary.json` et le rappel n'en porte que le chemin (preuve: REQ CB-04 Complete, phase 3, 03-VERIFICATION.md)
- [x] **CB-05** : Le rappel n'est envoyé qu'à un hôte autorisé dans `runner.toml` (preuve: REQ CB-05 Complete, phase 3, 03-VERIFICATION.md)
- [x] **CAP-01** : La capacité `ifc.clash` détecte les conflits entre deux sélections IFC en modes `hard` et `clearance` (tolérance explicite), regroupe les résultats et renvoie un JSON avec les GlobalId de chaque paire (preuve: REQ CAP-01 Complete, phase 4, 04-VERIFICATION.md)
- [x] **CAP-02** : `ifc.clash` produit sur demande un BCF 2.1 avec deux points de vue par sujet (objets du conflit seuls ; contexte gris transparent), couleurs ARGB, sans sélection enregistrée (preuve: REQ CAP-02 Complete, phase 5.1, 05.1-VERIFICATION.md)
- [x] **CAP-03** : `ifc.clash` traite une sélection vide comme un succès à 0 conflit avec avertissement (preuve: REQ CAP-03 Complete, phase 4, 04-VERIFICATION.md)
- [x] **CAP-04** : La capacité `mcp.call` appelle un outil d'un serveur MCP stdio déclaré dans la configuration, sans LLM, dans le Job Object de la tâche, et renvoie son résultat (preuve: REQ CAP-04 Complete, phase 4, 04-VERIFICATION.md)
- [x] **CAP-05** : Le paquet `deskgate-bcf` (GPL-3) écrit un BCF 2.1 à partir d'un fichier JSON versionné, appelé en sous-processus ; aucun autre paquet n'importe `bcf-client` ni `deskgate-bcf` (vérifié par un test) (preuve: REQ CAP-05 Complete, phase 4, 04-VERIFICATION.md)
- [x] **CAP-06** : Chaque sujet BCF d'`ifc.clash` est titré d'après un gabarit et des tables de correspondance fournis par le job (champs génériques : bâtiment, étage du point de conflit, maquettes, types d'objets) ; aucune valeur métier n'est codée dans le plugin ; une valeur absente d'une table reste brute et produit un avertissement (révisé le 2026-10-22) (preuve: REQ CAP-06 Complete, phase 5.1, 05.1-VERIFICATION.md ; ligne ajoutée le 2026-10-26, exigence créée en 5.1)
- [x] **CAP-07** : `ifc.clash` ne perd aucun conflit en silence (troncature explicite et signalée, défaut sans perte sur des maquettes réelles) et exclut par défaut les réservations (`IfcOpeningElement`) des sélections (preuve: REQ CAP-07 Complete, phase 5.1, 05.1-VERIFICATION.md ; ligne ajoutée le 2026-10-26, exigence créée en 5.1)
- [x] **INS-01** : `deskgate init` crée `runner.toml`, le dossier `C:\BIM` (`depot`, `travail`, `livrables`) et le jeton, affiché une seule fois (preuve: REQ INS-01 Complete, phase 5, 05-VERIFICATION.md)
- [x] **INS-02** : `deskgate init` installe, avec l'accord de l'utilisateur, une tâche du Planificateur qui lance le runner à l'ouverture de session, sans limite de durée et même sur batterie (preuve: REQ INS-02 Complete, phase 5, 05-VERIFICATION.md)
- [x] **INS-03** : `n8n/docker-compose.yml` lance n8n 2.43.8 épinglé avec Postgres et `C:\BIM` monté sur `/data` (preuve: REQ INS-03 Complete, phase 5, 05-VERIFICATION.md)
- [x] **INS-04** : Un workflow d'exemple importable (HTTP Request → Wait → test du `status`) déclenche `ifc.clash` et reprend sur le rappel (preuve: REQ INS-04 Complete, phase 5, 05-VERIFICATION.md)
- [x] **INS-05** : Depuis le conteneur n8n, `http://host.docker.internal:8765/health` répond (vérifié sur la machine cible) (preuve: REQ INS-05 Complete, phase 5, 05-VERIFICATION.md)
- [x] **ACC-01** : Un calcul de plus de 10 minutes lancé depuis n8n, avec le runner démarré par la tâche planifiée, reprend dans n8n avec le résumé et le chemin du BCF (preuve: 05-ACCEPTANCE.md et 05-VERIFICATION.md, job 1ec19b03b33d 486 s complet, critère revu le 2026-10-21 (STATE.md Phase 5) ; certifie acc01-duree)
- [x] **ACC-02** : Un arrêt brutal du runner pendant une tâche produit, au redémarrage, un rappel `interrupted` reçu par n8n (preuve: REQ ACC-02 Complete, phase 5, 05-VERIFICATION.md)
- [x] **SOC-01** : gate du profil vert (preuve: .arthemis/reports/gate-1-05.4.log, verdict vert, 93f7d0c)
- [x] **SOC-02** : tests 100 % verts, aucun test retiré sans décision datée (preuve: .arthemis/reports/gate-1-05.4.log, 1053 passés + 33 e2e, 2 skips de liens symboliques déclarés)
- [x] **SOC-03** : findings critiques corrigés et re-vérifiés (preuve: state.json, aucun item finding ni corrige_non_certifie ; certifications .arthemis/reports/dev-senior-1-2..1-4)
- [x] **AUD-01** : saas-team-council passé, triage daté (preuve: audits/saas-council-2026-10-22.md, checkpoints.triage du 2026-10-22)
- [x] **AUD-02** : findings reportés au backlog, aucun bloquant ouvert (preuve: backlog 999.1 à 999.10 du ROADMAP ; aucun bloquant ouvert dans state.json)
- [x] **AUD-03** : dev-senior a relu, zéro bloquant (preuve: .arthemis/reports/dev-senior-1-1.md, findings certifiés fermés (dev-senior-1-4-recertification.md))
- [ ] **PUB-01** : version bumpée dans pyproject.toml, CHANGELOG depuis les SUMMARY (preuve: <sha>)
- [ ] **PUB-02** : go publication daté dans checkpoints.go_publication (preuve: <sha>)
- [ ] **PUB-03** : tag v0.1.0 posé, poussé, inscrit dans livraisons[] (preuve: <sha>)
- [ ] **PUB-04** : vérification 11a sur la machine cible : runner démarré par la tâche planifiée, /health, parcours n8n (preuve: <rapport>)
- [x] **PUB-05** : plan de retour arrière écrit avant le go (preuve: state.json extension.web_saas.exploitation.plan_retour_arriere, 2026-10-26)

## Clôture

À la CLOTURE_MILESTONE, ARTHEMIS relit ce fichier ligne par ligne, puis le gèle.

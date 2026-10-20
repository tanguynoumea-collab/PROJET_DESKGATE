# Definition of Done : deskgate, cycle 1 (milestone GSD v0.1, version cible 0.1.0)

> Instanciée le 2026-10-20 à l'entrée en IMPLEMENTATION, gelée à la clôture. Modèle : `arthemis-orchestrator/assets/dod_template.md`.

## Marqueurs (les seuls admis)

- `- [ ]` : à faire. `- [x] … (preuve: <sha|chemin|REQ>)` : fait. `- [~] renoncé le <AAAA-MM-JJ> : <motif>` : renoncé, jamais fait.

## Socle commun

- [ ] Toutes les phases 1 à 5 ont un SUMMARY par PLAN, VERIFICATION `passed` ou `human_needed` soldé, aucun UAT pending (preuve : liste des SUMMARY et statuts)
- [ ] Aucun `*-UAT.md` ni `*-HUMAN-UAT.md` en `testing`, `partial` ou `diagnosed` ; aucun `result: pending` (preuve : grep collé)
- [ ] Aucune VERIFICATION en `gaps_found` sans phase de gaps exécutée (preuve : sha)
- [ ] Gate du profil vert : chaque commande de `profil.gate[]` exécutée, code 0, journal dans `.arthemis/reports/gate-1-<phase>.log` (preuve : chemin)
- [ ] Tests 100 % verts ; aucun test retiré ou ignoré sans décision datée (les skip explicites de liens symboliques sans mode développeur sont déclarés) (preuve : journal de gate)
- [ ] Aucun secret introduit dans le code ou le dépôt (preuve : grep collé)
- [ ] Aucun item `finding` en `corrige_non_certifie` (preuve : extrait de state.json)
- [ ] REQUIREMENTS.md : chaque exigence du milestone `[x]` ou Dropped daté (preuve : table Traceability)

## Socle web_saas (adapté : runner local mono-tenant)

- [ ] Les 8 portes du GATE vertes ou NON COUVERTES avec motif et item `porte_non_couverte` (installation figée · types · lint · tests · build · E2E · migrations · budgets) (preuve : journal de gate)
- [ ] Toute route HTTP a la garde du jeton et du contrôle Host, sauf `/health` publique assumée (preuve : liste collée)
- [ ] Tout appel réseau sortant (rappel, MCP HTTP) a un timeout (preuve : grep collé)
- [ ] Toute nouvelle clé de configuration est documentée dans le gabarit commenté de `runner.toml` ; aucun secret dans les journaux (preuve : diff collé)
- [ ] Frontière GPL : aucun paquet hors `plugins/bim/bcf/` n'importe `bcf` ni `deskgate_bcf` ; `core/` n'importe ni `sqlite3`, `subprocess`, `httpx2`, `fastapi`, `ctypes` (preuve : tests AST)
- [ ] Plan de retour arrière écrit dans `exploitation.plan_retour_arriere` (désinstallation, base conservée, tâche planifiée retirée) (preuve : extrait de state.json)

## Par exigence du milestone

- [ ] **RUN-01** : L'utilisateur démarre le runner (`deskgate serve`) et il n'écoute que sur 127.0.0.1 ; il refuse de démarrer sur une autre interface sans option explicite (preuve: <REQ|sha>)
- [ ] **RUN-02** : Le runner lit sa configuration typée dans `runner.toml` (port, racines autorisées, correspondance des chemins, jeton, délais) et refuse de démarrer sur une configuration invalide avec un message clair en français (preuve: <REQ|sha>)
- [ ] **RUN-03** : Un second runner lancé pendant que le premier tourne s'arrête sans toucher à la base ni aux tâches (preuve: <REQ|sha>)
- [ ] **RUN-04** : `GET /health` répond sans jeton, sans détail sensible (preuve: <REQ|sha>)
- [ ] **SEC-01** : Toute route sauf `/health` refuse une requête sans jeton Bearer valide (401) ; le jeton est stocké haché (preuve: <REQ|sha>)
- [ ] **SEC-02** : Le runner refuse une requête dont l'en-tête `Host` n'est pas `127.0.0.1`, `localhost` ou `host.docker.internal` (preuve: <REQ|sha>)
- [ ] **SEC-03** : Un chemin `/data/...` est converti en `C:/BIM/...` (et inversement pour les artefacts renvoyés) (preuve: <REQ|sha>)
- [ ] **SEC-04** : Un chemin hors des racines autorisées est refusé, y compris via `..`, lien symbolique, jonction, chemin UNC, préfixe de segment (`C:/BIM2`), nom réservé ou flux alternatif (preuve: <REQ|sha>)
- [ ] **SEC-05** : La `signature` de la `resumeUrl` n'apparaît dans aucun journal, aucune réponse d'API ni l'audit (preuve: <REQ|sha>)
- [ ] **SEC-06** : Chaque soumission, refus, fin de tâche et rappel est inscrit dans un journal d'audit local (client, capacité, paramètres sans secrets, début, fin, statut, durée) (preuve: <REQ|sha>)
- [ ] **JOB-01** : n8n soumet une tâche par `POST /jobs` et reçoit immédiatement `202 { job_id, status: "queued" }` (preuve: <REQ|sha>)
- [ ] **JOB-02** : Les tâches sont persistées dans SQLite et exécutées une à la fois, dans l'ordre de soumission (preuve: <REQ|sha>)
- [ ] **JOB-03** : `GET /jobs/{id}` renvoie l'état, la progression, le résumé et les artefacts ; `GET /jobs/{id}/logs` renvoie les journaux (preuve: <REQ|sha>)
- [ ] **JOB-04** : `POST /jobs/{id}/cancel` annule une tâche en file ou en cours (annulation coopérative, puis arrêt forcé) ; l'appel est idempotent (preuve: <REQ|sha>)
- [ ] **JOB-05** : Une tâche qui dépasse son délai maximum est arrêtée avec tout son arbre de processus (petits-enfants orphelins compris) et passe `timeout` (preuve: <REQ|sha>)
- [ ] **JOB-06** : Au redémarrage du runner, chaque tâche `running` passe `interrupted` et son rappel est envoyé (preuve: <REQ|sha>)
- [ ] **JOB-07** : Un plugin s'exécute dans un sous-processus placé dans un Job Object Windows, jamais dans le processus du runner, sans shell (preuve: <REQ|sha>)
- [ ] **JOB-08** : Une soumission avec une `idempotency_key` identique à une tâche non terminale est refusée (pas de double calcul) (preuve: <REQ|sha>)
- [ ] **JOB-09** : Chaque tâche dispose d'un dossier de travail `C:/BIM/travail/<job_id>/` et déclare ses artefacts produits (preuve: <REQ|sha>)
- [ ] **CB-01** : À chaque état terminal (`succeeded`, `failed`, `timeout`, `cancelled`, `interrupted`), le runner appelle la `resumeUrl` telle quelle avec `{ job_id, capability, status, duration_s, summary, artifacts, error }` (preuve: <REQ|sha>)
- [ ] **CB-02** : Un rappel non livré est réessayé avec délai croissant, y compris après un redémarrage du runner (aucun résultat perdu) (preuve: <REQ|sha>)
- [ ] **CB-03** : Le runner distingue les réponses de n8n : livré, Wait pas encore en attente (réessai court), exécution déjà terminée ou inconnue (abandon tracé), refus de signature (abandon tracé) (preuve: <REQ|sha>)
- [ ] **CB-04** : Un résumé trop volumineux pour le rappel (> 1 Mio) est écrit dans `summary.json` et le rappel n'en porte que le chemin (preuve: <REQ|sha>)
- [ ] **CB-05** : Le rappel n'est envoyé qu'à un hôte autorisé dans `runner.toml` (preuve: <REQ|sha>)
- [ ] **CAP-01** : La capacité `ifc.clash` détecte les conflits entre deux sélections IFC en modes `hard` et `clearance` (tolérance explicite), regroupe les résultats et renvoie un JSON avec les GlobalId de chaque paire (preuve: <REQ|sha>)
- [ ] **CAP-02** : `ifc.clash` produit sur demande un BCF 2.1 avec deux points de vue par sujet (objets du conflit seuls ; contexte gris transparent), couleurs ARGB, sans sélection enregistrée (preuve: <REQ|sha>)
- [ ] **CAP-03** : `ifc.clash` traite une sélection vide comme un succès à 0 conflit avec avertissement (preuve: <REQ|sha>)
- [ ] **CAP-04** : La capacité `mcp.call` appelle un outil d'un serveur MCP stdio déclaré dans la configuration, sans LLM, dans le Job Object de la tâche, et renvoie son résultat (preuve: <REQ|sha>)
- [ ] **CAP-05** : Le paquet `deskgate-bcf` (GPL-3) écrit un BCF 2.1 à partir d'un fichier JSON versionné, appelé en sous-processus ; aucun autre paquet n'importe `bcf-client` ni `deskgate-bcf` (vérifié par un test) (preuve: <REQ|sha>)
- [ ] **INS-01** : `deskgate init` crée `runner.toml`, le dossier `C:\BIM` (`depot`, `travail`, `livrables`) et le jeton, affiché une seule fois (preuve: <REQ|sha>)
- [ ] **INS-02** : `deskgate init` installe, avec l'accord de l'utilisateur, une tâche du Planificateur qui lance le runner à l'ouverture de session, sans limite de durée et même sur batterie (preuve: <REQ|sha>)
- [ ] **INS-03** : `n8n/docker-compose.yml` lance n8n 2.43.8 épinglé avec Postgres et `C:\BIM` monté sur `/data` (preuve: <REQ|sha>)
- [ ] **INS-04** : Un workflow d'exemple importable (HTTP Request → Wait → test du `status`) déclenche `ifc.clash` et reprend sur le rappel (preuve: <REQ|sha>)
- [ ] **INS-05** : Depuis le conteneur n8n, `http://host.docker.internal:8765/health` répond (vérifié sur la machine cible) (preuve: <REQ|sha>)
- [ ] **ACC-01** : Un calcul de plus de 10 minutes lancé depuis n8n, avec le runner démarré par la tâche planifiée, reprend dans n8n avec le résumé et le chemin du BCF (preuve: <REQ|sha>)
- [ ] **ACC-02** : Un arrêt brutal du runner pendant une tâche produit, au redémarrage, un rappel `interrupted` reçu par n8n (preuve: <REQ|sha>)
- [ ] **SOC-01** : gate du profil vert (preuve: <chemin du journal>)
- [ ] **SOC-02** : tests 100 % verts, aucun test retiré sans décision datée (preuve: <chemin>)
- [ ] **SOC-03** : findings critiques corrigés et re-vérifiés (preuve: <extrait>)
- [ ] **AUD-01** : saas-team-council passé, triage daté (preuve: <rapport>)
- [ ] **AUD-02** : findings reportés au backlog, aucun bloquant ouvert (preuve: <extrait>)
- [ ] **AUD-03** : dev-senior a relu, zéro bloquant (preuve: <rapport>)
- [ ] **PUB-01** : version bumpée dans pyproject.toml, CHANGELOG depuis les SUMMARY (preuve: <sha>)
- [ ] **PUB-02** : go publication daté dans checkpoints.go_publication (preuve: <sha>)
- [ ] **PUB-03** : tag v0.1.0 posé, poussé, inscrit dans livraisons[] (preuve: <sha>)
- [ ] **PUB-04** : vérification 11a sur la machine cible : runner démarré par la tâche planifiée, /health, parcours n8n (preuve: <rapport>)
- [ ] **PUB-05** : plan de retour arrière écrit avant le go (preuve: <extrait>)

## Clôture

À la CLOTURE_MILESTONE, ARTHEMIS relit ce fichier ligne par ligne, puis le gèle.

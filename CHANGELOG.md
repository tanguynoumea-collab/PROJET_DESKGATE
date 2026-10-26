# Journal des changements

Format : sections par version, la plus récente en tête. Les changements de comportement visibles par un plugin ou
par n8n sont signalés « Changement de comportement ».

## [0.1.0] - 2026-10-26

Première version publiée. Deskgate est une passerelle locale entre n8n (dans Docker) et les outils lourds d'un PC
Windows : n8n soumet une tâche, le runner exécute un plugin dans la session Windows, puis rappelle n8n avec le
résultat, quel que soit le dénouement.

### Ajouté

- **Runner local** : `deskgate serve` n'écoute que sur 127.0.0.1, lit une configuration typée dans `runner.toml`
  (port, racines autorisées, correspondance `/data` ↔ `C:/BIM`, jeton, délais) et refuse de démarrer sur une
  configuration invalide, avec un message en français. Un second runner s'arrête sans toucher à la base.
- **API pour n8n** : `POST /jobs` (réponse immédiate `202`), `GET /jobs/{id}`, `GET /jobs/{id}/logs`,
  `POST /jobs/{id}/cancel` (idempotent), et `GET /health` public sans détail sensible.
- **Exécution fiable** : tâches persistées dans SQLite et exécutées une à la fois, dans l'ordre ; chaque plugin tourne
  dans un sous-processus placé dans un Job Object Windows, sans shell ; délai maximum avec arrêt de tout l'arbre de
  processus ; dossier de travail par tâche ; doublon d'`idempotency_key` refusé pendant que la première tâche tourne.
- **Rappel garanti** : à chaque état terminal (`succeeded`, `failed`, `timeout`, `cancelled`, `interrupted`), le
  runner appelle la `resumeUrl` telle quelle, avec réessais à délai croissant qui survivent à un redémarrage ; les
  réponses de n8n sont distinguées (livré, Wait pas encore prêt, exécution terminée, signature refusée). Après un
  arrêt brutal, chaque tâche en cours passe `interrupted` et son rappel part au redémarrage.
- **Résultat complet pour n8n** : le rappel et `GET /jobs/{id}` portent `summary`, `data` et `artifacts`. Au-delà de
  1 Mio, `data` puis `summary` sont écrits dans `data.json` / `summary.json` du dossier de la tâche et le rappel n'en
  porte que le chemin ; ces marqueurs survivent au renvoi réduit après un refus 413 (DS-ARCH-1, DS2-2).
- **Capacité `ifc.clash`** : détection de conflits IFC (modes `hard` et `clearance`, tolérance explicite),
  regroupement, GlobalId de chaque paire, aucune perte silencieuse (troncature signalée), réservations exclues par
  défaut ; BCF 2.1 sur demande, deux points de vue par sujet avec image (conflit seul, puis contexte gris
  transparent), lisible dans BIMcollab Zoom ; titres des sujets d'après un gabarit et des tables fournis par le job.
- **Capacité `mcp.call`** : appel d'un outil d'un serveur MCP stdio déclaré dans `runner.toml`, sans LLM, dans le Job
  Object de la tâche ; arguments de chemin déclarés et validés ; variables d'environnement limitées au serveur visé ;
  réponse de plus de 900 000 octets déportée dans `mcp-result.json`.
- **Installation** : `deskgate init` crée `runner.toml`, `C:\BIM` (`depot`, `travail`, `livrables`) et le jeton
  (affiché une fois, stocké haché), et installe avec accord une tâche du Planificateur qui lance le runner à
  l'ouverture de session. `deskgate doctor` diagnostique l'installation, `deskgate task …` pilote la tâche.
- **Rétention** : `deskgate purge [--older-than-days N]` retire `data` des tâches anciennes dont le rappel est final
  (résumé, artefacts, audit et rappels conservés) (DS-SCAL-1, DS3-2).
- **n8n** : `n8n/docker-compose.yml` (n8n 2.43.8 épinglé, Postgres, `C:\BIM` monté sur `/data`) et un workflow
  d'exemple importable (soumettre, attendre le rappel, tester le statut).

### Sécurité

- Jeton Bearer obligatoire sur toutes les routes sauf `/health`, contrôle de l'en-tête `Host`, rappel envoyé
  seulement à un hôte autorisé ; tout chemin reçu est validé contre les racines autorisées (`..`, liens, jonctions,
  UNC, préfixes, noms réservés, flux alternatifs) ; la `signature` de la `resumeUrl` n'apparaît dans aucun journal,
  aucune réponse ni l'audit ; journal d'audit local de chaque soumission, refus, fin de tâche et rappel.
- `deskgate init` et `deskgate task install` refusent de tourner depuis une application empaquetée (MSIX), dont les
  écritures seraient invisibles pour la tâche planifiée.

### Notes pour les auteurs de plugins

- **NaN et Infinity refusés** : un `result.json` ou un événement contenant `NaN`, `Infinity` ou un flottant hors
  limites est refusé (`failed/invalid_result`) ; le SDK n'écrit plus de flottant non fini. Remplacer ces valeurs par
  `null` ou une chaîne (DS-ARCH-3).
- **Marqueurs de repli** : `data` peut valoir `{"path": "…", "truncated": true}`,
  `{"truncated": true, "artifact": "mcp_result"}`, `{"truncated": true, "error": "…"}`, `{"truncated": true}` ou,
  après une purge, `{"purged": true}`. Un champ métier `truncated` à côté d'autres clés n'est pas un marqueur.

### Données

- Base SQLite locale (`%LOCALAPPDATA%\Deskgate`, schéma 2) créée à l'installation ; aucune migration à appliquer
  pour cette première version.

### Documentation

- `ARCHITECTURE.md` sépare l'« État livré en v0.1 » (références au code vérifiées par test) de la cible v0.2+ ;
  `AGENTS.md` décrit l'installation, la mise à jour et le dépannage.

### Reporté

- Backlog 999.1 à 999.10 : findings mineurs des audits (source unique des états du rappel, rétention complète et
  purge des dossiers de tâche, CI et plugins, découpage du plugin BIM, noyau, documentation, diagnostic, `NaN` dans
  les paramètres de `POST /jobs`, verrou de doc lexical, mémoire et verrou de la purge).
- Vérification 05-D1 (démarrage du runner à l'ouverture de session) : à jouer avec la vérification après
  installation.

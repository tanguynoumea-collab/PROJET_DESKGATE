# Deskgate — règles du dépôt pour Claude Code

Lire aussi [`AGENTS.md`](AGENTS.md) (installation) et [`ARCHITECTURE.md`](ARCHITECTURE.md) (référence
technique). Le cycle de développement est piloté par ARTHEMIS (profil `web_saas`, état dans
`.arthemis/state.json`) et GSD (`.planning/`, écrit uniquement par les commandes GSD).

## Langue

Français partout : documents, interface, messages d'erreur, journaux, commits (sujet en français).
Identifiants de code, noms de routes et de champs JSON : anglais.

## Ce que Deskgate est, et n'est pas

- Une **passerelle** : n8n soumet une tâche, Deskgate exécute un plugin dans la session Windows,
  puis rappelle n8n. Une tâche = un appel d'un plugin.
- **Pas** un orchestrateur : aucun DAG, aucune planification, aucun enchaînement d'étapes.
- **Pas** un serveur MCP : Deskgate *appelle* des outils MCP (exécuteur `mcp`), il n'en expose pas.
- Workflows complets, Hermes, tableau de bord : hors de ce dépôt.

## Règles non négociables

1. **Le cœur ne connaît rien au BIM.** `src/deskgate/` n'importe jamais `deskgate_bim` ni
   IfcOpenShell. Les plugins BIM vivent dans `plugins/bim/`, paquet séparé.
2. **Aucune exécution de commande libre.** Pas de `shell=True`, pas de chaîne de commande construite
   par concaténation. L'exécuteur `cli` n'utilise que l'exécutable et le gabarit du manifeste.
3. **Un plugin ne tourne jamais dans le processus du runner** : sous-processus, dans un Job Object
   (créé suspendu, assigné, repris ; breakaway interdit).
4. **Chemins** : tout chemin reçu est converti puis validé contre `allowed_roots` (résolution des
   `..`, liens et jonctions) avant usage. On transmet des chemins, jamais les fichiers.
5. **Écoute sur `127.0.0.1` uniquement** ; jeton obligatoire sur toutes les routes sauf `/health`.
6. **Secrets** : jamais dans les manifestes, les journaux ni l'audit. La `resumeUrl` n8n est un
   secret (paramètre `signature`) : appelée telle quelle, masquée partout ailleurs.
7. **Rappel** : petit (≤ 1 Mio) ; les gros résultats vont dans des fichiers artefacts.
8. **Déterminisme** : un plugin de calcul donne les mêmes sorties pour les mêmes entrées.
9. **Licences** : le code du dépôt est MIT. Ne jamais intégrer de code GPL ou AGPL (Bonsai, xeokit,
   BIMserver, Windmill…) ; IfcOpenShell (LGPL-3) s'utilise comme bibliothèque.
10. **Frontière GPL** : seul `plugins/bim/bcf/` (`deskgate-bcf`, GPL-3) importe `bcf-client`.
    Aucun autre paquet ne l'importe ni n'importe `deskgate-bcf` : on l'appelle en sous-processus,
    avec des fichiers JSON. N'appeler l'export BCF d'`ifcclash` et le rapporteur BCF d'`ifctester`
    que depuis `deskgate-bcf`.

## Pile

- Python ≥ 3.11, `uv` pour les environnements, FastAPI + Uvicorn, SQLite (WAL), SDK `mcp` officiel,
  `pywin32` ou `ctypes` pour les Job Objects.
- n8n épinglé en `2.43.8` dans `n8n/docker-compose.yml`. Ne pas passer sur `latest`.
- Nœud n8n : TypeScript, paquet `n8n-nodes-deskgate`.

## Tests

- `pytest` pour le runner ; chaque exécuteur a des tests avec de vrais sous-processus Windows.
- Tests obligatoires sur : refus de chemin hors racine (`..`, lien, jonction), arrêt de l'arbre de
  processus au délai, passage `running` → `interrupted` au redémarrage, masquage de la signature,
  refus d'un jeton sans droit.
- Les plugins BIM ont leurs propres tests sur de petits fichiers IFC d'exemple dans `plugins/bim/tests/`.

## Commits

Format ARTHEMIS : `type(scope): sujet` ≤ 72 caractères, sujet en français. `.arthemis/**` jamais
mêlé au code ni à `.planning/`.

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Deskgate**

Deskgate est une passerelle locale open source (MIT) entre n8n et les outils lourds d'un PC Windows :
n8n (dans Docker) soumet une tâche, Deskgate l'exécute dans la session Windows de l'utilisateur via
un plugin déclaré (fonction Python, ligne de commande ou outil MCP), puis rappelle n8n avec le
résultat. Il est destiné aux coordinateurs et BIM managers qui construisent des pipelines n8n avec
des calculs IfcOpenShell longs ou des logiciels installés, en commençant par son auteur.

**Core Value:** n8n délègue une tâche longue au PC Windows et reprend fiablement quand elle se termine, quel que
soit le résultat (succès, échec, délai dépassé, annulation, redémarrage du runner).

### Constraints

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
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Trois faits qui changent la conception
## Pile recommandée
### Noyau du runner (`deskgate`, MIT)
| Technologie | Version | Rôle | Pourquoi | Confiance |
|---|---|---|---|---|
| Python | >= 3.11 ; **cible de dev/test 3.12 ou 3.13** | Langage | 3.11 est le plancher d'`httpx2`, `pydantic-settings`, `platformdirs` et `bcf-client` (source). 3.14 testé OK avec IfcOpenShell. | HAUTE |
| FastAPI | `>=0.151,<0.152` (0.151.0) | API HTTP | Contrainte. Épingler la mineure : FastAPI casse parfois en 0.x. Ne pas installer l'extra `[standard]` (tire `fastapi-cli`, `uvicorn[standard]`, jinja2 : inutiles). | HAUTE |
| Starlette | 1.9.0 (transitif) | ASGI | Tiré par FastAPI. Ne pas l'importer directement sauf pour `TrustedHostMiddleware` (contrôle de l'en-tête `Host`, anti-DNS-rebinding exigé par les vérifications). | HAUTE |
| Uvicorn | `>=0.54,<0.55` (0.54.0), **sans** extra `standard` | Serveur ASGI | Sous Windows `uvloop` n'existe pas ; `httptools`/`watchfiles` inutiles. h11 pur Python suffit pour un trafic local. Lancer par `uvicorn.Server(Config(app, host="127.0.0.1", port=8765, log_config=None))` depuis `deskgate serve` : contrôle du host et du logging. | HAUTE |
| Pydantic | `>=2.14,<3` (2.14.1) | Modèles, validation, schémas JSON | Contrainte de fait (FastAPI, `mcp` exige >= 2.12). Un seul modèle sert API, file, rappel, manifeste v0.2 (`model_json_schema()` alimente `input_schema`). | HAUTE |
| pydantic-settings | `>=2.16` (2.16.0) | Lecture de `runner.toml` | `TomlConfigSettingsSource` lit TOML avec `tomllib` : validation typée de la config, variables d'environnement `DESKGATE_*` en surcouche. | MOYENNE (API de source TOML à confirmer au premier usage) |
| `tomllib` (stdlib) | 3.11+ | Lecture TOML | Standard ; **ne pas installer `tomli`** (inutile dès 3.11). | HAUTE |
| tomli-w | `>=1.2,<2` (1.2.0) | Écriture TOML | Seulement pour `deskgate init` / `config set` si on réécrit le fichier. Ne conserve pas les commentaires : `deskgate init` doit produire `runner.toml` depuis un **gabarit texte commenté**, et n'utiliser tomli-w que pour de petites mises à jour. | HAUTE (version), MOYENNE (usage) |
| SQLite via `sqlite3` stdlib | SQLite 3.45 (Python 3.11 Windows) à 3.50 (3.14) | File, audit, jetons | Voir « Motifs SQLite » ci-dessous. `RETURNING` (>= 3.35) et `STRICT` (>= 3.37) disponibles dès 3.11. [test] | HAUTE |
| anyio | `>=4.15` (4.15.1, transitif) | Concurrence asynchrone | Déjà imposé par Starlette/`mcp` ; `anyio.to_thread`, `anyio.open_process`, groupes de tâches pour l'ordonnanceur. | HAUTE |
| httpx2 | `>=2.15,<3` (2.15.1) | Rappel vers la `resumeUrl` | Voir « Rappel HTTP ». Pas de `httpx` ni `httpx-retries` (celui-ci dépend de `httpx`). | HAUTE (existence/version), MOYENNE (stabilité : projet jeune) |
| `mcp` (SDK officiel) | `>=2.3,<3` (2.3.0, 2026-10-02) | Exécuteur `mcp` côté client | Voir « SDK `mcp` ». | HAUTE |
| Typer | `>=0.27,<0.28` (0.27.3) | CLI `deskgate` | Voir « CLI ». | HAUTE |
| platformdirs | `>=4.13` (4.13.5) | Dossier de données (`%LOCALAPPDATA%\Deskgate`) | Ne pas coder les chemins en dur. | HAUTE |
| keyring | `>=25.7` (25.7.0) | Secrets de plugins (gestionnaire d'identifiants Windows) | Exigé par `ARCHITECTURE.md` §8 ; backend Windows Credential Locker intégré. Reporter à la v0.2 (droits par plugin), pas nécessaire en v0.1. | MOYENNE |
| structlog | 26.1.0 | Journaux structurés | **Optionnel.** Le `logging` stdlib + un `Filter` de masquage de la `signature` suffit en v0.1 ; structlog seulement si le journal JSON devient un besoin. Ne pas l'ajouter par défaut. | MOYENNE |
### Motifs SQLite (file de tâches maison)
- **Un seul écrivain logique** : toutes les écritures passent par `BEGIN IMMEDIATE` (évite les `SQLITE_BUSY` d'upgrade de verrou). Lecteurs concurrents libres grâce au WAL.
- **Réclamer une tâche** de façon atomique : `UPDATE jobs SET status='running', started_at=? WHERE id=(SELECT id FROM jobs WHERE status='queued' AND resource=? ORDER BY created_at LIMIT 1) RETURNING *` ; la concurrence par ressource se compte par `SELECT count(*) ... status='running' AND resource=?` dans la même transaction.
- **Idempotence** : index unique partiel sur `(capability, idempotency_key)` pour les tâches `succeeded`.
- **Rappel durable (outbox)** : table `callbacks` (job_id, tentatives, `next_attempt_at`, dernier statut). Un redémarrage reprend les rappels dus : c'est la valeur centrale du produit (« reprend fiablement »), donc **les réessais vivent en base, pas en mémoire**.
- **Redémarrage** : au démarrage, `UPDATE jobs SET status='interrupted' WHERE status='running'` puis insertion des rappels correspondants, dans la même transaction.
- Fichier de base **local au PC** (`%LOCALAPPDATA%`), jamais sur un partage réseau ni sur le dossier monté dans Docker (WAL ne fonctionne pas sur partage réseau).
- Migrations : un entier `PRAGMA user_version` et des scripts SQL numérotés ; pas d'ORM, pas d'Alembic (surdimensionné).
- Pas de SQLAlchemy / SQLModel : le schéma tient en cinq tables et le SQL brut est plus lisible et testable.
### SDK `mcp` 2.x : API cliente vérifiée
- Signature : `Client(server | Transport | StdioServerParameters | str, *, read_timeout_seconds: float | None, mode='auto', ...)` ; `call_tool(name, arguments=None, read_timeout_seconds=None, progress_callback=None, *, meta=None)`. Une chaîne URL donne du Streamable HTTP.
- `StdioServerParameters(command, args, env, cwd, encoding, encoding_error_handler)`. **`env` : l'enfant n'hérite pas de l'environnement complet** (liste blanche minimale), donc passer explicitement `SYSTEMROOT`, `PATH`, `USERPROFILE`, etc. sinon les serveurs Node/Python échouent sous Windows. `errlog=` de `stdio_client` redirige le stderr du serveur vers un fichier de la tâche (sinon il part dans le stderr du runner).
- Champs en `snake_case` (`is_error`, `structured_content`, `input_schema`), erreurs `MCPError` (ex-`McpError`), délai dépassé = `MCPError` avec `code == REQUEST_TIMEOUT` (-32001), timeouts en `float` secondes (plus de `timedelta`).
- Un `httpx2.AsyncClient` construit à la main **retombe sur 5 s de timeout** : toujours fixer `timeout=httpx2.Timeout(30, read=300)` (ou plus).
- Streamable HTTP : un statut HTTP non 2xx devient `MCPError` par requête, plus de `HTTPStatusError`.
- `mode='auto'` négocie l'ère de protocole (2026-07-28 ou héritée) : les serveurs MCP tiers encore en 1.x restent joignables. **Cas à tester en v0.1** avec un serveur 1.x réel.
- Le SDK sous Windows place lui-même le serveur stdio dans un Job Object (module `mcp.os.win32`) : bon pour la mort avec le runner, mais **ce n'est pas notre Job** (pas de plafond mémoire, pas d'arrêt par tâche).
- Les « Tasks » MCP expérimentales ont été **retirées de la spécification et du SDK** (migration §Tasks) : les rapports du cycle 1 les mentionnaient comme piste v0.4 ; ce n'est plus le cas, `submit`/`status` maison reste le bon modèle.
### Rappel HTTP (`httpx2`)
- **`httpx2.AsyncClient` unique**, créé dans le `lifespan` FastAPI, `timeout=httpx2.Timeout(10, read=30)`, `follow_redirects=False`, aucun `trust_env` surprenant (désactiver les proxys d'environnement : `trust_env=False`) car l'URL est locale (`localhost:5678`).
- **Réessais écrits à la main, pilotés par la table `callbacks`** : délai `min(5 * 2**n, 300)` s avec gigue, au plus ~8 tentatives (~1 h), réessai sur erreur réseau / 5xx / 408 / 429, **pas** de réessai sur 4xx (401 = signature invalide, 404 = exécution n8n terminée ou supprimée, 413 = trop gros : voir §3 des vérifications). Abandon tracé dans l'audit.
- Pourquoi pas `tenacity` : le réessai doit survivre à un redémarrage du runner et se voir dans l'UI ; un décorateur en mémoire ne le permet pas. Pourquoi pas `httpx-retries` : dépend de `httpx` (pas `httpx2`) et ne couvre que la couche transport en mémoire.
- Passer la `resumeUrl` **telle quelle** : `client.post(url_str, json=payload)` ; jamais `httpx2.URL(...).copy_with(...)`, ni reconstruction. Masquer `signature=` dans tout `repr`/log (filtre `logging` + exceptions : les messages d'erreur d'`httpx2` contiennent l'URL).
- Corps JSON sérialisé une fois, taille mesurée avant envoi (seuil 1 Mio, repli `summary.json`).
### Job Objects Windows
### CLI
### Empaquetage et distribution
| Outil | Version | Usage | Notes |
|---|---|---|---|
| uv | 0.13.3 (publié 2026-10-20) ; la machine a 0.12.17 | Installation (`uv tool install deskgate`), environnements de plugins, verrouillage | `uv tool install` crée un venv isolé et une exécutable `deskgate.exe` dans le dossier des outils (`uv tool update-shell` pour le `PATH`). Mise à jour : `uv tool upgrade deskgate`. |
| hatchling | 1.32.4 | Backend de build | Un `pyproject.toml` par paquet ; espace de travail uv (`[tool.uv.workspace]`) avec `deskgate`, `plugins/bim` (`deskgate-bim`), `plugins/bim/bcf` (`deskgate-bcf`). |
| ruff | 0.17.1 | Lint + format | Dev uniquement. |
- **Entrée `gui-scripts` pour le démarrage sans console** : déclarer en plus `[project.gui-scripts] deskgatew = "deskgate.cli:serve_main"`. Sous Windows, uv génère un lanceur `pythonw` pour les `gui-scripts` (corrigé en amont ; **non vérifié pour `uv tool install` : tester**) et `sys.stdout`/`sys.stderr` valent alors `None` : rediriger tout vers un fichier journal dès le premier import, sinon `print` et Uvicorn plantent. Confiance BASSE-MOYENNE : prévoir un spike.
- Les plugins : un `uv venv --python X.Y` + `uv pip install -r requirements.txt` par plugin, avec `UV_CACHE_DIR` partagé (vérifications §5). IfcOpenShell **épinglé** à `0.9.0.post1`.
- `deskgate-bcf` : installé comme outil indépendant (`uv tool install ./plugins/bim/bcf`) ou dans son propre venv de plugin ; il expose l'exécutable `deskgate-bcf.exe`, appelé par chemin absolu résolu à l'installation (jamais par recherche dans le `PATH` à l'exécution).
### Planificateur de tâches Windows (`deskgate init`)
- `<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>` (sinon la tâche est tuée au bout de **72 h** par défaut) ;
- `<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>` et `<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>` (portables) ;
- `<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>` ;
- `<LogonTrigger>` avec `<UserId>` = utilisateur courant (`DOMAINE\nom` via `getpass`/`os.environ`), `<Principal>` : `LogonType=InteractiveToken`, `RunLevel=LeastPrivilege` ;
- `<RestartOnFailure>` (intervalle 1 min, 3 essais) ;
- l'action pointe l'exécutable `deskgatew.exe serve` ou `uv tool run` : chemin absolu résolu à l'installation, `WorkingDirectory` explicite.
### Tests
| Outil | Version | Usage |
|---|---|---|
| pytest | 9.1.1 | Exécution des tests |
| anyio (plugin pytest intégré) | 4.15.1 | Tests asynchrones (`@pytest.mark.anyio`, fixture `anyio_backend = "asyncio"`) : pas de dépendance en plus. `pytest-asyncio` 1.4.0 est un équivalent acceptable ; **choisir l'un des deux, pas les deux**. |
| `fastapi.testclient.TestClient` | via Starlette 1.9 | Tests de routes ; accepte `httpx2`. Pour des tests où l'ordonnanceur tourne vraiment : `with TestClient(app)` déclenche le `lifespan`. |
| pytest-httpx | 0.36.2 | **À vérifier** : cible `httpx`, pas `httpx2`. Pour le rappel, préférer un **vrai serveur HTTP local éphémère** (stdlib `http.server` dans un thread, ou une app Starlette minimale sur port 0) : test de réessai, de 401/413 et de masquage de `signature` plus réalistes qu'un mock. |
| psutil | 7.2.2 | Dans les tests uniquement : vérifier qu'aucun PID n'a survécu. |
### Plugins BIM : `ifcclash` et `deskgate-bcf`
- Résultat JSON : par ensemble, `clashes` = dictionnaire de `ClashResult` (`a_global_id`, `b_global_id`, `a_ifc_class`, `b_ifc_class`, `a_name`, `b_name`, `type`, `p1`, `p2`, `distance`, `smart_group` si regroupé). C'est **ce JSON** que `ifc.clash` lit pour produire `summary` et pour alimenter `deskgate-bcf`.
- Les clés `tolerance`/`check_all`/`allow_touching`/`clearance` sont lues par `assert` : un jeu incomplet donne un `AssertionError` brut ; valider l'entrée avec Pydantic avant d'appeler.
- `smart_group_clashes(clash_sets, max_clustering_distance)` : regroupement OPTICS, **requiert scikit-learn** (extra `ifcclash[advanced]`) ; arrivée tardive, optionnelle.
- L'export BCF intégré d'`ifcclash` est volontairement pauvre (un point de vue, `author="IfcClash"`, pas de couleurs ni de deuxième vue, `get_viewpoint_snapshot` renvoie `None`) : **ne pas l'utiliser**. Les conventions du dépôt (deux points de vue par sujet, contexte gris transparent, couleurs ARGB) se font dans `deskgate-bcf`.
- Exécuter dans un **sous-processus du venv du plugin** (règle 3). Plafond de threads : variables d'environnement transmises (`OMP_NUM_THREADS`, `NUMEXPR_NUM_THREADS`).
- Chaque ouverture `ifcopenshell.open` d'un gros IFC est coûteuse en RAM : `memory_mb` du Job Object est un vrai filet de sécurité ici.
- `add_topic(title, description, author, topic_type="", topic_status="")` ; `TopicHandler.add_viewpoint(element)` et `add_viewpoint_from_point_and_guids(position, *guids)` ; `VisualizationInfoHandler` expose `set_selected_elements`, `set_visible_elements`, `set_hidden_elements`, `set_visibility` et les constructeurs `build_camera_from_vectors(position, dir, up)`, `build_components(*guids)`. `BcfXml.load(Path)` lit un BCF existant (utile à `bcf.read`).
- `save()` attend un `Path` ; l'écriture se fait dans un zip en mémoire (`InMemoryZipFile`) : pas de fichier partiel sur disque en cas de plantage.
- Dépendances : `xsdata>=24.4`, `numpy`, `ifcopenshell`, `requests` ; Python >= 3.10 (le dépôt amont a abandonné 3.10 ; ne pas compter dessus).
- Les couleurs ARGB, la caméra et le second point de vue passent par les modèles xsdata (`bcf.v2.model`) : **API de bas niveau, peu documentée** ; prévoir de la lire en phase `deskgate-bcf` plutôt que de la supposer. Confiance MOYENNE.
- **Contrat de `deskgate-bcf`** (JSON en entrée/sortie, aucun import croisé) : entrée `{project, author, topics:[{title, description, type, status, guids:[...], point:[x,y,z], camera:{...}, colors:{...}, comments:[]}]}` → `.bcf` ; sens inverse `.bcf` → JSON. À figer dans un schéma Pydantic **dupliqué** des deux côtés (le côté MIT ne doit pas importer le paquet GPL, même pour un modèle partagé) ou dans un JSON Schema versionné dans `docs/`.
## Alternatives écartées
| Catégorie | Retenu | Alternative | Pourquoi pas |
|---|---|---|---|
| Client HTTP | `httpx2` | `httpx` 0.28.1 | Dernière version décembre 2024, projet au ralenti ; `mcp` 2.x ne le tire plus. |
| Client HTTP | `httpx2` | `aiohttp`, `requests` | Deux clients de plus ; `requests` est bloquant. |
| Réessais | Table `callbacks` + boucle maison | `tenacity` 9.2.1, `httpx-retries` 0.6.0 | Pas durables au redémarrage ; `httpx-retries` cible `httpx`. |
| SQLite | `sqlite3` + `to_thread` | `aiosqlite` 0.22.1 | Couche sans gain réel (voir plus haut). Acceptable si préféré. |
| SQLite | SQL brut | SQLAlchemy, SQLModel, Alembic | Cinq tables, pas de besoin d'ORM. |
| File | Maison | Huey (plan B), RQ, Celery, Dramatiq | Voir `existant-cycle-1.md`. |
| Job Objects | `ctypes` | `pywin32` | Dépendance native, piège d'empaquetage, aucun gain pour ce besoin (arrive en transitif via `mcp`, non importé). |
| Arbre de processus | Job Object | `psutil.children(recursive=True)` | Rate les orphelins [test]. |
| Démarrage | `schtasks /XML` | COM `Schedule.Service`, `pywin32`, `pyinstaller`+service, dossier `Startup` | COM : dépendance et complexité ; service : session 0 ; dossier Startup : pas de relance ni de limite de durée. |
| CLI | Typer | Click, argparse | Click/argparse : plus de code pour la même ergonomie. |
| Config | `tomllib` + pydantic-settings | `tomli`, `dynaconf`, YAML | `tomli` redondant en 3.11+. |
| Tests async | plugin `anyio` | `pytest-asyncio` 1.4.0 | Équivalent ; un seul des deux. |
| MCP | `mcp` 2.3 | `mcp` 1.28.x, `fastmcp` (projet tiers) | 1.x en fin de vie ; l'exécuteur ne fait que *consommer* des serveurs. |
| Journalisation | `logging` + filtre | structlog, loguru | Optionnel ; filtre de masquage indispensable de toute façon. |
## Installation
# Développement (monorepo uv)
# Dépendances du cœur
# Dev
# Environnement d'un plugin BIM (épinglé)
# Paquet GPL isolé
# Utilisateur final
## Questions ouvertes
- **Serveurs MCP stdio persistants** : lancer un processus par appel (simple, isolé, coût de démarrage par tâche) ou garder un serveur par `mcp_servers.toml` (rapide, mais état partagé et jobs multiples). Par défaut un par tâche ; revoir si un serveur coûte > 5 s à démarrer.
- **Licence de `bcf-client`** : suivre la prochaine publication (classifier corrigé en LGPL attendu). Si LGPL confirmé, `deskgate-bcf` pourrait redevenir MIT et être importable ; décision à prendre par l'auteur, pas avant.
- **Planificateur** : confirmer sans élévation sur Windows 10/11 compte standard ; confirmer le comportement `gui-scripts` sous `uv tool install`.
- **`pydantic-settings` TOML** : confirmer l'API de `TomlConfigSettingsSource` (non vérifiée dans Context7) ou lire `tomllib` + `model_validate` à la main (équivalent, sans dépendance).
- **`pytest-httpx` / `httpx2`** : compatibilité non vérifiée ; contournée par un vrai serveur local de test.
## Sources
- PyPI JSON (2026-10-20) : fastapi 0.151.0, uvicorn 0.54.0, starlette 1.9.0, pydantic 2.14.1, pydantic-settings 2.16.0, mcp 2.3.0 (2026-10-02), httpx 0.28.1 (2024-12-06), httpx2 2.15.1, typer 0.27.3, click 8.5.0, tomli-w 1.2.0, aiosqlite 0.22.1, pywin32 312, psutil 7.2.2, pytest 9.1.1, pytest-asyncio 1.4.0, anyio 4.15.1, uv 0.13.3, ifcopenshell 0.9.0.post1, ifcclash / ifctester / ifcdiff / bcf-client 0.9.0 : https://pypi.org/project/<nom>/
- Guide de migration MCP Python SDK v1 vers v2 : https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/docs/migration.md ; transports : https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/docs/client/transports.md (Context7 `/modelcontextprotocol/python-sdk`, versions v2.0.0 et v2.3.0)
- `httpx2` : https://github.com/pydantic/httpx2
- Code `ifcclash` et `bcf-client` : https://github.com/IfcOpenShell/IfcOpenShell/tree/v0.9.0/src/ifcclash , `.../src/bcf` ; commits de correction de licence du 2026-09-29 (`462f7a62`, `4c9c45e1`) dans `src/bcf/pyproject.toml`
- Vérifications locales (exécution) : serveur et client `mcp` 2.3.0 en stdio sous Python 3.11 ; SQLite 3.45.1 (Python 3.11) et 3.50.4 (3.14) ; roues IfcOpenShell (rapport `verifs-techniques-cycle-1.md`)
- Job Objects : https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects ; schéma XML du Planificateur de tâches : https://learn.microsoft.com/en-us/windows/win32/taskschd/taskschedulerschema-logontrigger-triggergroup-element (recherche web seule pour le comportement non élevé : BASSE confiance)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->

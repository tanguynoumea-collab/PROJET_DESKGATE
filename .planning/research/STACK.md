# Pile technique

**Projet :** Deskgate (passerelle locale n8n vers outils Windows)
**Recherché le :** 2026-10-20
**Confiance globale :** MOYENNE-HAUTE (versions vérifiées sur PyPI le jour même ; API `mcp` 2.x et `ifcclash`/`bcf-client` vérifiées par lecture du code et exécution locale ; Planificateur de tâches non testé)

Les décisions de `ARCHITECTURE.md` et `CLAUDE.md` sont des contraintes (FastAPI + Uvicorn, SQLite WAL, SDK `mcp`, Job Object, uv, MIT, frontière GPL). Cette recherche ne les remet pas en cause ; elle fixe les versions et les choix de détail. Niveaux de preuve : [PyPI] = API JSON PyPI du 2026-10-20 ; [code] = source lu ; [test] = exécuté ici ; [doc] = documentation officielle ; [web] = recherche web seule.

## Trois faits qui changent la conception

1. **Le SDK `mcp` est passé en 2.x** (2.0.0 puis 2.3.0 le 2026-10-02). L'API cliente a changé : classe `Client` de haut niveau, `snake_case`, `MCPError`, timeouts en `float`, `httpx` remplacé par `httpx2`. Tout exemple trouvé en ligne (1.x : `ClientSession`, `streamablehttp_client`, `McpError`, `inputSchema`) est obsolète. [doc + test]
2. **`httpx` est en sommeil** (0.28.1, décembre 2024) ; **Pydantic reprend le flambeau sous le nom `httpx2`** (2.15.1, `import httpx2`, Python >= 3.11). `mcp` 2.x, Starlette 1.9 et FastAPI 0.151 l'adoptent. Choisir `httpx2` évite deux clients HTTP dans l'arbre. [PyPI + doc]
3. **Licence de `bcf-client` : contradiction amont.** Le wheel PyPI 0.9.0 porte le classifier GPL-3 ; mais les en-têtes de tous les fichiers sont LGPL-3+, et deux commits amont du 2026-09-29 (`bcf: fix license classifier`, « le classifier est périmé ») corrigent en LGPL-3.0-or-later. La prochaine publication sera donc annoncée LGPL. **On garde l'isolation `deskgate-bcf` (GPL-3, sous-processus)** : décision validée, peu coûteuse, et juridiquement prudente tant que le wheel publié dit GPL. À réévaluer quand un wheel corrigé sort. [PyPI + code]

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

Pas de `pywin32` en dépendance directe : voir Job Objects. Remarque : `mcp` 2.x tire `pywin32>=311` sous Windows de lui-même ; on ne l'importe quand même pas (cf. règle ctypes).

### Motifs SQLite (file de tâches maison)

**Choix : `sqlite3` synchrone de la stdlib, appelé depuis `anyio.to_thread.run_sync`, pas `aiosqlite`.** Pourquoi : `aiosqlite` (0.22.1) n'est qu'un fil par connexion et une file de messages au-dessus de `sqlite3` ; il ajoute une dépendance et une couche d'indirection sans rendre SQLite plus rapide, et complique les transactions explicites (`BEGIN IMMEDIATE`) et les tests. Une petite classe `Db` (une connexion par appel court, ou un pool de 1 écrivain + lecteurs) suffit ; le volume est de quelques tâches par minute. Confiance MOYENNE (choix de conception, pas une vérité d'écosystème) ; `aiosqlite` reste acceptable si l'équipe préfère `await` partout.

Réglages à l'ouverture de **chaque** connexion :

```python
con = sqlite3.connect(path, timeout=5.0, isolation_level=None)  # transactions explicites
con.execute("PRAGMA journal_mode=WAL")      # persistant dans le fichier
con.execute("PRAGMA synchronous=NORMAL")    # sûr en WAL, sans fsync à chaque commit
con.execute("PRAGMA busy_timeout=5000")
con.execute("PRAGMA foreign_keys=ON")
```

- **Un seul écrivain logique** : toutes les écritures passent par `BEGIN IMMEDIATE` (évite les `SQLITE_BUSY` d'upgrade de verrou). Lecteurs concurrents libres grâce au WAL.
- **Réclamer une tâche** de façon atomique : `UPDATE jobs SET status='running', started_at=? WHERE id=(SELECT id FROM jobs WHERE status='queued' AND resource=? ORDER BY created_at LIMIT 1) RETURNING *` ; la concurrence par ressource se compte par `SELECT count(*) ... status='running' AND resource=?` dans la même transaction.
- **Idempotence** : index unique partiel sur `(capability, idempotency_key)` pour les tâches `succeeded`.
- **Rappel durable (outbox)** : table `callbacks` (job_id, tentatives, `next_attempt_at`, dernier statut). Un redémarrage reprend les rappels dus : c'est la valeur centrale du produit (« reprend fiablement »), donc **les réessais vivent en base, pas en mémoire**.
- **Redémarrage** : au démarrage, `UPDATE jobs SET status='interrupted' WHERE status='running'` puis insertion des rappels correspondants, dans la même transaction.
- Fichier de base **local au PC** (`%LOCALAPPDATA%`), jamais sur un partage réseau ni sur le dossier monté dans Docker (WAL ne fonctionne pas sur partage réseau).
- Migrations : un entier `PRAGMA user_version` et des scripts SQL numérotés ; pas d'ORM, pas d'Alembic (surdimensionné).
- Pas de SQLAlchemy / SQLModel : le schéma tient en cinq tables et le SQL brut est plus lisible et testable.

### SDK `mcp` 2.x : API cliente vérifiée

Version : `mcp>=2.3,<3` (2.3.0 publiée le 2026-10-02 ; Python >= 3.10 ; dépend de `httpx2`, `mcp-types==2.3.0`, `anyio`, `pydantic>=2.12`, `opentelemetry-api`, `pywin32` sous Windows). La 1.x (1.28.x) est en maintenance : **ne pas l'utiliser pour du neuf**. Épingler `<3`, la 2.x vient de sortir et a encore bougé entre 2.0 et 2.3.

Vérifié par exécution (Python 3.11, venv jetable, serveur `MCPServer` stdio local) [test] :

```python
import sys
from mcp import Client, StdioServerParameters

params = StdioServerParameters(command=sys.executable, args=["srv.py"], env={...}, cwd="C:/BIM/travail/<job>")
async with Client(params) as c:                       # stdio : le sous-processus est lancé à l'entrée
    r = await c.call_tool("add", {"a": 2, "b": 3}, read_timeout_seconds=1800)
    r.is_error, r.structured_content, r.content       # False, {'result': 5}, [TextContent(...)]
```

Streamable HTTP :

```python
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

async with httpx2.AsyncClient(headers={"Authorization": "Bearer ..."},
                              timeout=httpx2.Timeout(30.0, read=300.0)) as http:
    async with Client(streamable_http_client(url, http_client=http)) as c:
        tools = (await c.list_tools()).tools
```

Points à retenir (doc de migration v2.3.0 + inspection des signatures) :
- Signature : `Client(server | Transport | StdioServerParameters | str, *, read_timeout_seconds: float | None, mode='auto', ...)` ; `call_tool(name, arguments=None, read_timeout_seconds=None, progress_callback=None, *, meta=None)`. Une chaîne URL donne du Streamable HTTP.
- `StdioServerParameters(command, args, env, cwd, encoding, encoding_error_handler)`. **`env` : l'enfant n'hérite pas de l'environnement complet** (liste blanche minimale), donc passer explicitement `SYSTEMROOT`, `PATH`, `USERPROFILE`, etc. sinon les serveurs Node/Python échouent sous Windows. `errlog=` de `stdio_client` redirige le stderr du serveur vers un fichier de la tâche (sinon il part dans le stderr du runner).
- Champs en `snake_case` (`is_error`, `structured_content`, `input_schema`), erreurs `MCPError` (ex-`McpError`), délai dépassé = `MCPError` avec `code == REQUEST_TIMEOUT` (-32001), timeouts en `float` secondes (plus de `timedelta`).
- Un `httpx2.AsyncClient` construit à la main **retombe sur 5 s de timeout** : toujours fixer `timeout=httpx2.Timeout(30, read=300)` (ou plus).
- Streamable HTTP : un statut HTTP non 2xx devient `MCPError` par requête, plus de `HTTPStatusError`.
- `mode='auto'` négocie l'ère de protocole (2026-07-28 ou héritée) : les serveurs MCP tiers encore en 1.x restent joignables. **Cas à tester en v0.1** avec un serveur 1.x réel.
- Le SDK sous Windows place lui-même le serveur stdio dans un Job Object (module `mcp.os.win32`) : bon pour la mort avec le runner, mais **ce n'est pas notre Job** (pas de plafond mémoire, pas d'arrêt par tâche).
- Les « Tasks » MCP expérimentales ont été **retirées de la spécification et du SDK** (migration §Tasks) : les rapports du cycle 1 les mentionnaient comme piste v0.4 ; ce n'est plus le cas, `submit`/`status` maison reste le bon modèle.

**Recommandation d'architecture (confiance MOYENNE, à valider en phase exécuteur MCP) :** exécuter l'exécuteur `mcp` comme **sous-processus de travail** (`python -m deskgate.executors.mcp_worker`) lancé dans le Job Object de la tâche, qui ouvre le `Client` et écrit le résultat en JSON. Cela respecte la règle 3 (rien d'externe dans le processus du runner), cantonne les plantages et les fuites du SDK, et le Job de la tâche contient alors le serveur MCP stdio et ses petits-enfants. Coût : un démarrage Python (~0,3 s) par appel ; acceptable pour des tâches longues. Pour les serveurs stdio de longue durée partagés entre appels, voir la question ouverte plus bas.

### Rappel HTTP (`httpx2`)

- **`httpx2.AsyncClient` unique**, créé dans le `lifespan` FastAPI, `timeout=httpx2.Timeout(10, read=30)`, `follow_redirects=False`, aucun `trust_env` surprenant (désactiver les proxys d'environnement : `trust_env=False`) car l'URL est locale (`localhost:5678`).
- **Réessais écrits à la main, pilotés par la table `callbacks`** : délai `min(5 * 2**n, 300)` s avec gigue, au plus ~8 tentatives (~1 h), réessai sur erreur réseau / 5xx / 408 / 429, **pas** de réessai sur 4xx (401 = signature invalide, 404 = exécution n8n terminée ou supprimée, 413 = trop gros : voir §3 des vérifications). Abandon tracé dans l'audit.
- Pourquoi pas `tenacity` : le réessai doit survivre à un redémarrage du runner et se voir dans l'UI ; un décorateur en mémoire ne le permet pas. Pourquoi pas `httpx-retries` : dépend de `httpx` (pas `httpx2`) et ne couvre que la couche transport en mémoire.
- Passer la `resumeUrl` **telle quelle** : `client.post(url_str, json=payload)` ; jamais `httpx2.URL(...).copy_with(...)`, ni reconstruction. Masquer `signature=` dans tout `repr`/log (filtre `logging` + exceptions : les messages d'erreur d'`httpx2` contiennent l'URL).
- Corps JSON sérialisé une fois, taille mesurée avant envoi (seuil 1 Mio, repli `summary.json`).

### Job Objects Windows

**Choix : `ctypes` pur (module `executors/jobobject.py`), pas `pywin32`.** Vérifié par la démonstration du cycle 1 (psutil rate les petits-enfants, le Job Object les tue) [test]. Raisons : zéro dépendance native, contrôle exact de `CREATE_SUSPENDED` + assignation + reprise (que `pywin32` n'améliore pas : `subprocess.Popen` n'expose pas le handle de thread de toute façon), signatures `kernel32` courtes et stables depuis Windows 8. `pywin32` (312) arrive de toute façon en transitif via `mcp` mais son chargement (`pythoncom`, post-install DLL) est un piège d'empaquetage ; ne pas l'importer.

Recette (déjà validée) :
1. `CreateJobObjectW`, `SetInformationJobObject(JobObjectExtendedLimitInformation)` avec `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (+ `JOB_OBJECT_LIMIT_JOB_MEMORY` si `memory_mb`) ; **jamais** `BREAKAWAY_OK` ni `SILENT_BREAKAWAY_OK`.
2. `subprocess.Popen(argv, creationflags=CREATE_SUSPENDED | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW, shell=False)`.
3. `AssignProcessToJobObject(int(p._handle))`, puis `NtResumeProcess` (ntdll).
4. Arrêt : `CTRL_BREAK_EVENT` (grâce 10 s) puis `TerminateJobObject` puis contrôle `JobObjectBasicAccountingInformation.ActiveProcesses == 0`.
5. Déclarer `argtypes`/`restype` de chaque fonction (`ctypes.WinDLL("kernel32", use_last_error=True)`) : sans cela, les handles 64 bits sont tronqués.

`psutil` 7.2.2 : seulement diagnostic et nettoyage ciblé `cleanup.extra_process_names` des plugins `gui-session`. Pas d'arrêt d'arbre par psutil.

Prudence `CREATE_NEW_PROCESS_GROUP` : il désactive Ctrl+C dans l'enfant mais permet `CTRL_BREAK_EVENT` ; à combiner avec `CREATE_NO_WINDOW` pour les plugins sans interface, pas pour les `gui-session`.

### CLI

**Typer `0.27.x`** (au-dessus de Click 8.5.0, qui reste une dépendance). Raisons : sous-commandes typées (`deskgate init | serve | doctor | plugin add | token create`) avec les mêmes annotations que Pydantic/FastAPI, aide générée (`--help`), complétion. Typer tire `rich` (aide colorée) : accepter ; la taille n'est pas un enjeu pour un outil de bureau. Écrire les sorties de `doctor` en texte simple (compatibles redirection). Click nu seulement si on voulait zéro dépendance : pas le cas ici. Confiance HAUTE.

Importer paresseusement `fastapi`/`uvicorn`/`mcp` dans la commande `serve` pour que `deskgate --help`, `init` et `doctor` démarrent vite.

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

**Choix : `schtasks.exe /Create /XML <fichier> /TN Deskgate /F`, appelé par `subprocess.run([...], shell=False)`, avec un fichier XML généré par Python. Pas de COM (`Schedule.Service` via pywin32 / comtypes).** Raisons : aucune dépendance, comportement identique à ce qu'un utilisateur voit (`schtasks /Query /TN Deskgate /XML`), `deskgate doctor` et la désinstallation (`schtasks /Delete`) tiennent en une ligne, et l'option en ligne `/SC ONLOGON /TR` n'expose pas les réglages qui comptent ici. Le XML est indispensable parce que les réglages par défaut de `schtasks /Create` sont dangereux pour un runner longue durée :

- `<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>` (sinon la tâche est tuée au bout de **72 h** par défaut) ;
- `<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>` et `<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>` (portables) ;
- `<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>` ;
- `<LogonTrigger>` avec `<UserId>` = utilisateur courant (`DOMAINE\nom` via `getpass`/`os.environ`), `<Principal>` : `LogonType=InteractiveToken`, `RunLevel=LeastPrivilege` ;
- `<RestartOnFailure>` (intervalle 1 min, 3 essais) ;
- l'action pointe l'exécutable `deskgatew.exe serve` ou `uv tool run` : chemin absolu résolu à l'installation, `WorkingDirectory` explicite.

Le fichier XML s'écrit en **UTF-16 avec BOM** (`schtasks` le refuse en UTF-8 selon les cas). Un utilisateur standard peut enregistrer une tâche à l'ouverture de **sa propre** session sans élévation (RunLevel limité) : confiance MOYENNE, **non testé ici** (la création d'une tâche modifie le système) ; premier spike de la phase « démarrage » : `schtasks /Create /XML` sur un compte standard, puis fermeture/réouverture de session, puis `schtasks /Query /V`. Ajouter `deskgate service start|stop|status` autour de `schtasks /Run|/End`.

### Tests

| Outil | Version | Usage |
|---|---|---|
| pytest | 9.1.1 | Exécution des tests |
| anyio (plugin pytest intégré) | 4.15.1 | Tests asynchrones (`@pytest.mark.anyio`, fixture `anyio_backend = "asyncio"`) : pas de dépendance en plus. `pytest-asyncio` 1.4.0 est un équivalent acceptable ; **choisir l'un des deux, pas les deux**. |
| `fastapi.testclient.TestClient` | via Starlette 1.9 | Tests de routes ; accepte `httpx2`. Pour des tests où l'ordonnanceur tourne vraiment : `with TestClient(app)` déclenche le `lifespan`. |
| pytest-httpx | 0.36.2 | **À vérifier** : cible `httpx`, pas `httpx2`. Pour le rappel, préférer un **vrai serveur HTTP local éphémère** (stdlib `http.server` dans un thread, ou une app Starlette minimale sur port 0) : test de réessai, de 401/413 et de masquage de `signature` plus réalistes qu'un mock. |
| psutil | 7.2.2 | Dans les tests uniquement : vérifier qu'aucun PID n'a survécu. |

Principes Windows : `tmp_path` pour tous les fichiers ; **tester avec de vrais sous-processus** (règle du dépôt) : un petit script `spawn_grandchild.py` (intermédiaire qui lance un petit-enfant orphelin puis se termine), un plugin qui dort ; assertions sur `ActiveProcesses` et sur `psutil.pid_exists`. Marqueur `@pytest.mark.skipif(sys.platform != "win32")` sur les tests de Job Object ; marqueur `slow` pour les tests IfcOpenShell. Fermer les connexions SQLite et attendre la libération des fichiers avant `tmp_path` teardown (Windows refuse de supprimer un fichier ouvert, y compris `-wal`/`-shm`). Tests de chemins : créer jonctions par `mklink /J` via `subprocess` (les liens symboliques exigent le mode développeur).

### Plugins BIM : `ifcclash` et `deskgate-bcf`

**IfcOpenShell et satellites : 0.9.0 / 0.9.0.post1** (tous publiés le 2026-09-29 à 2026-10-15) ; `ifcclash` 0.9.0 (LGPL-3+), `ifctester` 0.9.0, `ifcdiff` 0.9.0, `bcf-client` 0.9.0 [PyPI]. Les paquets satellites ne déclarent que `ifcopenshell` en dépendance : **`ifcclash` n'impose pas `bcf-client`** (import paresseux dans `export_bcfxml`), ce qui garde le plugin `ifc.clash` MIT propre. Pour `ifctester`, en revanche, `bcf-client` est une dépendance déclarée : `ifc.audit` (v0.2) **l'installera** dans son venv même sans l'importer ; la règle « n'appeler le rapporteur BCF d'`ifctester` que depuis `deskgate-bcf` » du CLAUDE.md reste applicable, mais cette dépendance transitive est à documenter dans `plugins/bim/NOTICE`.

**API `ifcclash` 0.9.0** (code lu, `ifcclash/ifcclash.py`) [code] :

```python
import logging
from ifcclash.ifcclash import Clasher, ClashSettings

s = ClashSettings()
s.logger = logging.getLogger("clash")      # obligatoire (None par défaut)
s.output = str(work_dir / "clashes.json")  # ".bcf" déclencherait l'export bcf-client : NE PAS l'utiliser dans le cœur MIT
c = Clasher(s)
c.clash_sets = [{
    "name": "CVC vs STR",
    "mode": "intersection",                 # "intersection" | "collision" | "clearance"
    "a": [{"file": "C:/BIM/CVC.ifc", "selector": "IfcFlowSegment", "mode": "i"}],
    "b": [{"file": "C:/BIM/STR.ifc", "selector": "IfcBeam", "mode": "i"}],
    "tolerance": 0.002, "check_all": True,  # intersection : tolerance + check_all requis
    # collision : allow_touching ; clearance : clearance + check_all
}]
c.clash()                                   # géométrie OpenCascade, trianglebvh
c.export()                                  # export_json : liste de ClashSet avec "clashes"
```

- Résultat JSON : par ensemble, `clashes` = dictionnaire de `ClashResult` (`a_global_id`, `b_global_id`, `a_ifc_class`, `b_ifc_class`, `a_name`, `b_name`, `type`, `p1`, `p2`, `distance`, `smart_group` si regroupé). C'est **ce JSON** que `ifc.clash` lit pour produire `summary` et pour alimenter `deskgate-bcf`.
- Les clés `tolerance`/`check_all`/`allow_touching`/`clearance` sont lues par `assert` : un jeu incomplet donne un `AssertionError` brut ; valider l'entrée avec Pydantic avant d'appeler.
- `smart_group_clashes(clash_sets, max_clustering_distance)` : regroupement OPTICS, **requiert scikit-learn** (extra `ifcclash[advanced]`) ; arrivée tardive, optionnelle.
- L'export BCF intégré d'`ifcclash` est volontairement pauvre (un point de vue, `author="IfcClash"`, pas de couleurs ni de deuxième vue, `get_viewpoint_snapshot` renvoie `None`) : **ne pas l'utiliser**. Les conventions du dépôt (deux points de vue par sujet, contexte gris transparent, couleurs ARGB) se font dans `deskgate-bcf`.
- Exécuter dans un **sous-processus du venv du plugin** (règle 3). Plafond de threads : variables d'environnement transmises (`OMP_NUM_THREADS`, `NUMEXPR_NUM_THREADS`).
- Chaque ouverture `ifcopenshell.open` d'un gros IFC est coûteuse en RAM : `memory_mb` du Job Object est un vrai filet de sécurité ici.

**API `bcf-client` 0.9.0, BCF 2.1** (wheel inspecté, module `bcf.v2`) [code] :

```python
from pathlib import Path
import numpy as np
from bcf.v2.bcfxml import BcfXml                  # BCF 2.1 ; bcf.v3.* pour BCF 3.0

bcf = BcfXml.create_new("Projet X")               # project_name
topic = bcf.add_topic(title, description, author, topic_type="Clash", topic_status="Open")
vp = topic.add_viewpoint_from_point_and_guids(np.array([x, y, z]), guid_a, guid_b)
topic.comments.append(...)                         # mdl.Comment (bcf.v2.model)
bcf.save(Path("C:/BIM/travail/<id>/conflits.bcf"))
```

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

```bash
# Développement (monorepo uv)
uv sync

# Dépendances du cœur
uv add "fastapi>=0.151,<0.152" "uvicorn>=0.54,<0.55" "pydantic>=2.14,<3" "pydantic-settings>=2.16" \
       "httpx2>=2.15,<3" "mcp>=2.3,<3" "typer>=0.27,<0.28" "platformdirs>=4.13" "tomli-w>=1.2,<2"
# Dev
uv add --dev "pytest>=9.1" "psutil>=7.2" "ruff>=0.17"

# Environnement d'un plugin BIM (épinglé)
uv pip install "ifcopenshell==0.9.0.post1" "ifcclash==0.9.0"

# Paquet GPL isolé
uv pip install "bcf-client==0.9.0" "ifcopenshell==0.9.0.post1"

# Utilisateur final
uv tool install deskgate
deskgate init
```

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

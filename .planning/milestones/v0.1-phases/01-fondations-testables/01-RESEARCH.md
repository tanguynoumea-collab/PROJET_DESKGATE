# Phase 1: Fondations testables - Recherche

**Recherché le :** 2026-10-20
**Domaine :** runner Windows local (FastAPI/Uvicorn), instance unique, socket exclusif, validation de chemins Windows, configuration typée, outillage uv/CI
**Confiance globale :** HAUTE (tout ce qui est marqué [exp] a été exécuté sur cette machine : Windows 11 Pro 10.0.26200, Python 3.11.9 et 3.14.4, FastAPI 0.151.0, Starlette 1.9.0, Uvicorn 0.54.0, Pydantic 2.14.1). Exceptions explicites : spike Docker (non exécuté), liens symboliques (non testables ici), noms courts 8.3 (désactivés sur ce volume).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `runner.toml`, la base `deskgate.db` et les journaux du runner vivent dans `%LOCALAPPDATA%\Deskgate` (via `platformdirs`), jamais sous OneDrive, `Documents` ni `C:\BIM`. Surcharge possible par `--config <chemin>` ou la variable `DESKGATE_HOME`.
- **D-02:** Défaut `host = "127.0.0.1"`, port `8765`. Toute autre adresse n'est acceptée que si `allow_non_loopback = true` dans `runner.toml` ; dans ce cas, avertissement en français au démarrage et champ d'avertissement dans `/health`. `0.0.0.0` n'est jamais un défaut.
- **D-03:** Le socket est créé et lié à la main avec `SO_EXCLUSIVEADDRUSE`, puis passé à `uvicorn.Server(config).serve(sockets=[sock])`. Rien d'important dans le `lifespan` d'Uvicorn (il s'exécute avant le bind).
- **D-04:** Ordre de démarrage strict : mutex nommé `Local\Deskgate` (`CreateMutexW`) → socket lié (`SO_EXCLUSIVEADDRUSE`) → ouverture de la base → (recovery et threads en phase 2) → Uvicorn. Un second runner sort à l'étape du mutex, avec un message clair, sans ouvrir la base (RUN-03).
- **D-05:** `tomllib` + `RunnerConfig.model_validate` (Pydantic 2) ; pas de pydantic-settings. Une configuration invalide arrête le démarrage avec un message en français qui cite la clé fautive. Clés connues dès la phase 1 : `host`, `port`, `allow_non_loopback`, `token_sha256`, `[paths] allowed_roots`, `[[paths.mapping]] container/host`, `callback_allowed_hosts` (lu, utilisé en phase 3), `[capabilities.<id>]` (lu, utilisé en phase 2 ; voir STATE.md, décision phase 2). Inconnu → erreur (pas de clé ignorée en silence).
- **D-06:** Un seul jeton en v0.1. `runner.toml` ne contient que `token_sha256` (SHA-256 hex) ; comparaison par `hmac.compare_digest`. Le jeton en clair n'est jamais écrit ni journalisé. Toute route sauf `/health` exige `Authorization: Bearer <jeton>` (401 sinon).
- **D-07:** En-tête `Host` accepté : `127.0.0.1`, `localhost`, `host.docker.internal` (avec ou sans port). Sinon 400 avec erreur stable. Protège contre le DNS rebinding.
- **D-08:** Toutes les erreurs de l'API ont la forme `{ "error": { "code": "<code_stable_anglais>", "message": "<message en français>" } }`. Codes stables (ex. `unauthorized`, `host_not_allowed`, `path_outside_roots`, `invalid_config`). Les erreurs de validation FastAPI sont réécrites dans ce format.
- **D-09:** `core/paths.py` pur : conversion `/data/...` ↔ `C:/BIM/...` selon `[[paths.mapping]]`, contrôles lexicaux (UNC, `\\?\`, noms réservés `CON`/`NUL`/…, flux alternatifs `:`, préfixe de segment `C:/BIM2`, `..`), résolution des liens et jonctions par un `resolver` injecté (le vrai : `Path.resolve(strict=…)`). Comparaison insensible à la casse, par segments.
- **D-10:** Noyau pur `src/deskgate/core/` (`paths`, `config`, `tokens`, `redact`, `hostcheck`, `errors`) ; coquille `api`, `cli`, `store` (squelette), `instance` (mutex + socket). Test AST : `core/` n'importe jamais `sqlite3`, `subprocess`, `httpx2`, `fastapi`, `ctypes`. Test AST de frontière GPL : aucun paquet hors `plugins/bim/bcf/` n'importe `bcf` ni `deskgate_bcf` (vide mais actif dès la phase 1).
- **D-11:** Marqueurs pytest `unit`, `fs`, `proc`, `e2e`. Tests `fs` avec vraies jonctions (`mklink /J`, sans admin) ; liens symboliques en `skipif` explicite si le mode développeur manque. CI GitHub Actions `windows-latest`.
- **D-12:** Outillage de gate (`profil.gate[]` d'ARTHEMIS) à mettre en place dans cette phase : `uv sync --locked`, `uv run ruff check`, `uv run ruff format --check`, `uv run pyright`, `uv run pytest -m "not e2e"`, `uv build --all-packages`, `uv run pytest -m e2e`. Workspace uv (paquet `deskgate` ; `plugins/bim` et `plugins/bim/bcf` déclarés plus tard).
- **D-13:** Avant le code : (a) `host.docker.internal` → service sur 127.0.0.1 depuis un conteneur jetable (Docker 29.8.2 présent) ; (b) bind `SO_EXCLUSIVEADDRUSE` : un second bind échoue ; (c) Job Object ctypes avec petit-enfant orphelin porté en test pytest (le module `jobobject` définitif est livré en phase 2). Résultats consignés dans le RESEARCH ou le SUMMARY de la phase.

### Claude's Discretion

- Commande de développement pour générer un jeton et son hash avant `deskgate init` (phase 5).
- Contenu exact de `/health` (statut, version, avertissement d'écoute ; aucun chemin, aucun secret).
- Gabarit commenté de `runner.toml` et ses valeurs par défaut.
- Découpage des plans et vagues.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope. (Hors phase : file de tâches, exécution, Job Object en production, rappel, audit, capacités, `deskgate init` ; le schéma SQLite complet est livré en phase 2.)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Support de la recherche |
|----|-------------|-------------------------|
| RUN-01 | `deskgate serve` n'écoute que sur 127.0.0.1 ; refuse une autre interface sans option explicite | §Socket exclusif (bind manuel, `SO_EXCLUSIVEADDRUSE` vérifié), validateur Pydantic `host` + `allow_non_loopback`, `Server.run(sockets=[sock])` |
| RUN-02 | Config typée `runner.toml`, refus d'une config invalide avec message FR | §Configuration (tomllib + `extra="forbid"`, traduction FR des `ValidationError.errors()`, prototype exécuté) |
| RUN-03 | Second runner s'arrête sans toucher la base | §Instance unique (mutex `Local\` vérifié, libéré à la mort du processus ; ordre mutex → socket → base) |
| RUN-04 | `GET /health` sans jeton, sans détail sensible | §Middlewares ASGI (exemption `/health` exacte ; contenu minimal) |
| SEC-01 | 401 sans Bearer valide ; jeton haché | §Middlewares ASGI (SHA-256 + `compare_digest`, prototype exécuté : 401 aussi sur routes inconnues) |
| SEC-02 | Refus d'un `Host` hors liste | §Middlewares ASGI (Host custom, pas `TrustedHostMiddleware` : texte brut non conforme à D-08) |
| SEC-03 | `/data/...` ↔ `C:/BIM/...` | §Chemins (conversion par segments, prototype exécuté) |
| SEC-04 | Refus hors racines (`..`, lien, jonction, UNC, `C:/BIM2`, nom réservé, ADS) | §Chemins (table d'attaques exécutée sur vrai FS, 3.11 et 3.14) |
</phase_requirements>

## Résumé

Le plan d'implémentation du conseil (noyau pur, coquille impérative, démarrage mutex → socket → base → Uvicorn) est confirmé par l'expérience sur cette machine. Les points d'API d'Uvicorn 0.54 sont vérifiés dans le code source installé : `Server.run(sockets=[sock])` exécute `asyncio.run(..., loop_factory=ProactorEventLoop)` sous Windows, ne touche pas aux options du socket passé (pas de `SO_REUSEADDR`), n'écrit pas le message « Uvicorn running on », ferme lui-même le socket à l'arrêt, et exécute le `lifespan` AVANT `create_server` (donc avant `listen()`). Le prototype complet (mutex, bind exclusif, FastAPI, Uvicorn) a démarré, répondu sur `/health`, refusé un second runner (code 3 au mutex, code 4 si le mutex est contourné : WinError 10048) et redémarré immédiatement après un `taskkill /F /T`.

Les pièges les plus coûteux, tous vérifiés : (1) `SO_EXCLUSIVEADDRUSE` et `SO_REUSEADDR` ne peuvent pas être posés ensemble (WinError 10022) et un binder `SO_REUSEADDR` ordinaire peut coexister avec un autre `SO_REUSEADDR` : le mutex est donc indispensable, le bind exclusif n'est que la deuxième barrière ; (2) les helpers de chemins de la bibliothèque standard (`is_reserved`, `isabs`, `splitroot`) changent de comportement entre 3.11 et 3.14 : le contrôle lexical doit être écrit à la main, sur des chaînes, indépendamment de la version ; (3) `Path.resolve()` conserve le préfixe `\\?\` en sortie et accepte `\\.\C:\Windows`, `C:foo` (relatif au répertoire courant du lecteur) et supprime silencieusement les points/espaces finaux : ces entrées doivent être refusées AVANT la résolution ; (4) sur cette machine, `mklink /D` échoue sans privilège (WinError 1314) alors que `mklink /J` réussit : les tests de lien symbolique doivent être en `skipif` ; (5) `platformdirs.user_data_dir("Deskgate")` donne `...\Local\Deskgate\Deskgate` sauf avec `appauthor=False` ; (6) `TrustedHostMiddleware` renvoie du texte brut, pas le format D-08 : middleware ASGI pur à écrire.

Le spike Docker (D-13a) n'a PAS été exécuté : Docker Desktop n'est pas démarré (le tuyau `dockerDesktopLinuxEngine` est absent) et la consigne interdit de le lancer. Il reste à faire en tête de phase par un humain ou un exécuteur avec Docker démarré (procédure ci-dessous). Les spikes (b) et (c) sont faits et fournis sous forme de code prêt à devenir test pytest.

**Recommandation principale :** construire d'abord le noyau pur (`paths`, `config`, `tokens`, `hostcheck`, `errors`, `redact`) avec ses tests `unit`/`fs`, puis la coquille `instance` (mutex + socket) et l'`api` (deux middlewares ASGI purs + handlers d'erreur), enfin `cli.serve` et le test `e2e` ; mettre l'outillage (workspace uv, ruff, pyright, pytest, CI) en vague 0 car tout le reste en dépend.

## Standard Stack

### Core
| Bibliothèque | Version (vérifiée) | Rôle | Pourquoi |
|--------------|--------------------|------|----------|
| Python | `>=3.11` ; dev local 3.14.4 et 3.11.9 installés, CI sur 3.11 et 3.13 | Langage | Plancher imposé par STACK.md. 3.12 et 3.13 absents localement (voir Environnement) |
| FastAPI | `>=0.151,<0.152` (0.151.0) [exp] | API | Contrainte du projet |
| Starlette | 1.9.0 (transitif) [exp] | ASGI | `JSONResponse`, types ASGI, `StarletteHTTPException` |
| Uvicorn | `>=0.54,<0.55` (0.54.0) [exp], sans `[standard]` | Serveur | `Server(Config(...)).run(sockets=[sock])` |
| Pydantic | `>=2.14,<3` (2.14.1) [exp] | Config | `model_validate`, `extra="forbid"` |
| `tomllib` | stdlib | Lecture TOML | Décision D-05 |
| platformdirs | `>=4.13` (4.13.5, 2026-10-19) | Dossier de données | **Toujours `appauthor=False`** |
| Typer | `>=0.27,<0.28` (0.27.3) | CLI `deskgate serve` | STACK.md |
| hatchling | `>=1.32` (1.32.4) | Backend de build | Vérifié : `uv build --all-packages` OK |

### Supporting (dev)
| Bibliothèque | Version | Rôle |
|--------------|---------|------|
| pytest | `>=9.1,<10` (9.1.1) | Tests |
| httpx2 | `>=2.15,<3` (2.15.1) | **Requis par `starlette.testclient` 1.9** (il importe `httpx2`, retombe sur `httpx`) et pour les tests e2e (client HTTP) |
| psutil | `>=7.2` (7.2.2) | Tests uniquement : vérifier l'absence de PID survivants (phase 2 surtout) |
| ruff | `>=0.17,<0.18` (0.17.1, 2026-10-15) | Lint + format |
| pyright | `>=1.1.414` (1.1.414, 2026-09-10) | Vérification de types ; le paquet PyPI exige Node (v24.14.1 présent ici ; `windows-latest` l'a) |
| pytest-timeout | 2.4.0 (2025-05-05) | Recommandé pour les tests `e2e` et `proc` (un test bloqué ne doit pas geler la CI) ; optionnel |

### Alternatives écartées
| Au lieu de | Alternative | Raison |
|------------|-------------|--------|
| Middleware Host custom | `TrustedHostMiddleware` | Renvoie `PlainTextResponse("Invalid host header")` [exp, code lu] : ne respecte pas D-08 |
| Dépendance FastAPI pour l'auth | Middleware ASGI | Une dépendance ne protège pas les routes inconnues (404 sans jeton = fuite d'information) ; le middleware renvoie 401 partout [exp] |
| `pydantic-settings` | `tomllib` + `model_validate` | Décidé (D-05) |
| `msvcrt.locking` / port comme verrou | Mutex nommé | Décidé (D-04) |

**Installation (racine du dépôt, jamais globale) :**
```bash
uv sync            # crée .venv et uv.lock ; en CI : uv sync --locked
```

**Vérification des versions :** `pypi.org/pypi/<paquet>/json` interrogé le 2026-10-20 (valeurs ci-dessus). `astral-sh/setup-uv` dernière version : `v10.3.0` ; `actions/checkout` : `v7.0.1` (via `gh api`).

## Architecture Patterns

### Structure recommandée du dépôt
```
pyproject.toml            # paquet `deskgate` + [tool.uv.workspace] members = [] (ajouter plugins plus tard)
uv.lock                   # commité
.python-version           # optionnel (ex. 3.13) : épingle l'interpréteur de dev
.github/workflows/ci.yml
src/deskgate/
├── __init__.py           # __version__ via importlib.metadata
├── cli.py                # Typer : serve ; reconfigure stdout/stderr en UTF-8
├── core/                 # PUR : aucun import sqlite3/subprocess/httpx2/fastapi/ctypes
│   ├── paths.py  config.py  tokens.py  redact.py  hostcheck.py  errors.py
├── api/                  # app.py (create_app), middleware.py, handlers.py, routes_health.py
├── instance.py           # acquire_mutex(), bind_exclusive() ; SEUL module avec ctypes (hors jobobject plus tard)
├── store.py              # squelette : seul futur importeur de sqlite3 (phase 1 : open_db(path) minimal)
└── runtime.py            # orchestre l'ordre D-04
tests/
├── unit/  fs/  proc/  e2e/  architecture/   # un répertoire par marqueur ; conftest.py à la racine
```
`tests/` ne doit PAS contenir d'`__init__.py` conflictuels : utiliser `--import-mode=importlib` si deux fichiers de même nom existent dans des sous-dossiers (sinon, noms uniques).

### Pattern 1 : démarrage D-04 (vérifié de bout en bout [exp])
**Quoi :** `runtime.serve(config)` exécute dans l'ordre : charger/valider la config (échec → exit 2 + message FR) → `acquire_mutex()` (échec → exit 3) → `bind_exclusive()` (échec → exit 4, message selon `winerror`) → `store.open_db()` → `uvicorn.Server(Config(app, log_config=None, ...)).run(sockets=[sock])` dans le **thread principal**.
**Détails vérifiés dans uvicorn 0.54 :**
- `Server.run(sockets)` = `asyncio_run(self.serve(sockets=sockets), loop_factory=config.get_loop_factory())` ; `asyncio_loop_factory` renvoie `asyncio.ProactorEventLoop` sous win32 (sauf `use_subprocess`). Le prototype a affiché `loop = ProactorEventLoop` depuis le lifespan.
- `startup()` : `await lifespan.startup()` PUIS `loop.create_server(create_protocol, sock=sock, ...)` : le lifespan précède l'écoute (confirme D-03). Entre le `bind` et le `listen`, aucune connexion n'est acceptée : acceptable.
- Uvicorn ne pose PAS `SO_REUSEADDR` sur un socket fourni (il ne le fait que dans `Config.bind_socket()`, chemin non utilisé), et n'écrit pas « Uvicorn running on ... » dans ce cas : **journaliser soi-même** « Écoute sur http://127.0.0.1:8765 ».
- `shutdown()` ferme le socket fourni : ne pas le réutiliser ni le fermer deux fois sans `try`.
- `capture_signals` n'installe les handlers (`SIGINT`, `SIGTERM`, `SIGBREAK`) que dans le thread principal : lancer `server.run` dans le thread principal ; les threads de fond de la phase 2 sont daemon.
- `Config.fd` ne convient pas ici : le code utilise `socket.fromfd(fd, AF_UNIX, ...)`. Utiliser `sockets=[sock]`.
- `log_config=None` : Uvicorn ne reconfigure pas `logging` (le filtre de masquage `redact` des phases suivantes reste sous notre contrôle).

```python
# Source : prototype scratchpad/serve_proto.py exécuté (Python 3.11 et 3.14) ; code uvicorn 0.54.0 server.py
sock = bind_exclusive(cfg.host, cfg.port)          # après acquire_mutex()
server = uvicorn.Server(uvicorn.Config(app, log_config=None, lifespan="on"))
server.run(sockets=[sock])                          # Proactor sous Windows
```

### Pattern 2 : mutex nommé (ctypes) [exp]
```python
# Source : scratchpad/mutex1.py exécuté
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
k32.CreateMutexW.restype = wintypes.HANDLE
def acquire_mutex(name=r"Local\Deskgate"):
    ctypes.set_last_error(0)                       # indispensable avant l'appel
    h = k32.CreateMutexW(None, True, name)
    err = ctypes.get_last_error()                  # lire IMMÉDIATEMENT
    if not h or err == 183:                        # ERROR_ALREADY_EXISTS (183) ; 5 = ACCESS_DENIED aussi => occupé
        return None
    return h                                       # garder la référence jusqu'à la sortie (ne jamais fermer)
```
Vérifié : un second processus reçoit `ERROR_ALREADY_EXISTS` (183) ; après `taskkill /F` du détenteur, le mutex est libéré et un nouveau processus l'acquiert. Pas besoin de `ReleaseMutex`/`CloseHandle` : la mort du processus suffit.
**Le nom doit être paramétrable** (argument de fonction, ou variable `DESKGATE_INSTANCE_NAME`) : un test e2e ne doit pas entrer en collision avec un vrai runner qui tourne sur la machine du développeur. Défaut : `Local\Deskgate`.

### Pattern 3 : socket exclusif [exp]
```python
# Source : scratchpad/sock1.py exécuté
def bind_exclusive(host: str, port: int) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)   # NE PAS poser SO_REUSEADDR (WinError 10022)
    try:
        s.bind((host, port))
    except OSError:
        s.close(); raise
    return s                                                       # non héritable par défaut (get_inheritable() == False)
```
Résultats mesurés (détenteur A = bind exclusif sur 127.0.0.1) :

| Second bind | Résultat |
|---|---|
| exclusif, même adresse | WinError **10048** (WSAEADDRINUSE) |
| ordinaire, même adresse | 10048 |
| `SO_REUSEADDR`, même adresse | WinError **10013** (WSAEACCES) |
| exclusif + `SO_REUSEADDR` (même socket) | `setsockopt` échoue : WinError **10022** |
| joker `0.0.0.0` exclusif | 10048 |
| joker `0.0.0.0` ordinaire | **OK** (adresse plus spécifique prioritaire : les connexions vers 127.0.0.1 vont à A) |
| détenteur A = `SO_REUSEADDR` (mode Uvicorn par défaut), second exclusif | 10048 |
| détenteur A = `SO_REUSEADDR`, second `SO_REUSEADDR` | **OK : deux runners coexisteraient** |
| rebind exclusif après fermeture d'une connexion (TIME_WAIT) | OK |
| `port=0` + exclusif | OK (port éphémère ; utile pour les tests e2e) |
Conséquences : mutex obligatoire (le bind seul ne suffit pas si un autre outil utilise `SO_REUSEADDR`) ; les messages d'`OSError` sont **localisés** (français ici) : tester `exc.winerror` (10048 → « port déjà utilisé » ; 10013 → « accès refusé / port réservé (Hyper-V, voir `netsh interface ipv4 show excludedportrange protocol=tcp`) ») et jamais le texte.

### Pattern 4 : middlewares ASGI purs + handlers D-08 [exp]
**Ordre :** `app.add_middleware(...)` — le DERNIER ajouté est le plus EXTERNE. Ajouter d'abord `BearerAuthMiddleware`, puis `HostCheckMiddleware` : Host s'exécute en premier (400 avant 401 : vérifié). `ServerErrorMiddleware` de Starlette reste plus externe encore et appelle le handler `Exception`.
- Les réponses produites dans un middleware ne passent pas par les `exception_handler` : construire le `JSONResponse` D-08 directement (fonction `error_response(status, code, message)` dans `core/errors.py` côté données, `api/` côté `JSONResponse`).
- `/health` : exemption par égalité exacte du chemin (`scope["path"] == "/health"`). `/health/` (slash final) reste protégé (401) : comportement voulu, à garder simple.
- Auth avant routage : une route inconnue sans jeton donne 401, avec jeton 404 `{"error":{"code":"http_404",...}}` (pas de fuite sur l'existence des routes).
- Handlers à enregistrer : `StarletteHTTPException` (couvre 404/405 et les `HTTPException` FastAPI) → `code = f"http_{status}"` ou table de codes stables ; `RequestValidationError` → 422 `invalid_request` avec message FR construit depuis `exc.errors()` (loc → chemin) ; `Exception` → 500 `internal_error` (message générique, jamais la trace). Vérifié : sortie JSON `application/json` partout.
- Désactiver `docs_url`, `redoc_url`, `openapi_url` (surface inutile en v0.1 ; la 404 est au format D-08).
- Parsing du `Host` : regex stricte `^[A-Za-z0-9.\-]+(:\d{1,5})?$` (hôte ASCII) puis `.lower()` ; `localhost.` (point final) est refusé (choix de prudence). IPv6 `[::1]` non accepté (hors liste D-07). Alternative : `starlette._utils.parse_host_header` existe mais est privé : ne pas en dépendre.
- Authentification : hacher le jeton présenté (`hashlib.sha256`) puis `hmac.compare_digest` sur les deux hex de même longueur ; schéma `Bearer` insensible à la casse ; ajouter `WWW-Authenticate: Bearer` au 401. Ne jamais journaliser l'en-tête `Authorization`.
- Logique pure à placer dans `core/` : `hostcheck.is_allowed_host(raw, allowed) -> bool`, `tokens.hash_token(str) -> str`, `tokens.verify(presented, expected_sha256) -> bool`, `errors.ErrorBody`. Les middlewares n'ont plus qu'à adapter (testables en `unit` sans serveur).

### Pattern 5 : configuration (tomllib + Pydantic) [exp]
```python
# Source : scratchpad/cfg_proto.py exécuté (3.11)
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
class RunnerConfig(Strict):
    host: str = "127.0.0.1"
    port: int = Field(8765, ge=1, le=65535)
    allow_non_loopback: bool = False
    token_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    paths: Paths                      # allowed_roots: list[str] = Field(min_length=1) ; mapping: list[Mapping]
    callback_allowed_hosts: list[str] = []
    capabilities: dict[str, Capability] = {}   # Capability(extra=forbid): kind Literal["python"], python, entry, timeout_max>0, resource
```
- `extra="forbid"` s'applique aux sous-tables (`paths.mapping.0.prot`, `capabilities.fake.bogus`) : la clé fautive est citée par `".".join(str(p) for p in e["loc"])`.
- Traduction FR : table `type → message` (`extra_forbidden`, `missing`, `int_parsing`, `bool_parsing`, `string_type`, `greater_than_equal`, `less_than_equal`, `string_pattern_mismatch`, `too_short`, `literal_error`, `value_error`), repli sur `e["msg"]`. **Utiliser `exc.errors(include_input=False, include_url=False, include_context=False)`** : sans `include_input=False`, la valeur fautive (donc un `token_sha256` mal formé) pourrait être affichée.
- Les erreurs de `@model_validator(mode="after")` ont `loc == ()` et un préfixe « Value error, » : préférer un `@field_validator("host")` (loc = `host`) levant `ValueError("...")` et retirer le préfixe, ou `PydanticCustomError("host_non_loopback", "...")`.
- Erreur de syntaxe TOML : `tomllib.TOMLDecodeError` (message anglais avec « at line L, column C ») : l'encapsuler : « `runner.toml` illisible (ligne L, colonne C) ».
- Valider `host` avec `ipaddress.ip_address(host).is_loopback` ; un nom d'hôte (`localhost`) → soit résolu en `127.0.0.1`, soit refusé avec message (recommandation : n'accepter qu'une adresse IP littérale).
- Valider aussi : `token_sha256` ∈ `^[0-9a-f]{64}$` ; `allowed_roots` = chemins hôte absolus `X:/...` sans UNC (réutiliser `paths.lexical_check`) ; `mapping.container` = `/segment[...]` ; `mapping.host` doit être sous une racine autorisée ; `callback_allowed_hosts` = liste de noms (non utilisés en phase 1).
- Piège TOML : `allowed_roots = ["C:\BIM"]` est une erreur TOML (échappement invalide) : documenter dans le gabarit l'usage de `'C:/BIM'` ou `'C:\BIM'` (chaîne littérale) ; accepter `/` comme séparateur.
- Piège de portée TOML : une clé ajoutée sous `[[paths.mapping]]` appartient à ce tableau (c'était `paths.mapping.0.prot` dans le test) : le message d'erreur citant le chemin complet aide l'utilisateur.
- Lecture du fichier : `Path.read_bytes()` puis `tomllib.loads(bytes.decode("utf-8"))` ou `tomllib.load(open(..., "rb"))` ; `UnicodeDecodeError`/`FileNotFoundError`/`PermissionError` → messages FR distincts (fichier absent : indiquer le chemin attendu et qu'`init` arrive en phase 5 ; fournir le gabarit).
- Emplacement (D-01) : `platformdirs.user_data_dir("Deskgate", appauthor=False, roaming=False)` → `C:\Users\<u>\AppData\Local\Deskgate` [exp]. Sans `appauthor=False` : `...\Local\Deskgate\Deskgate` (piège). Priorité : `--config` > `DESKGATE_HOME` > défaut. Ne pas créer le dossier avant que la config soit valide (aucune écriture avant le mutex).

### Pattern 6 : chemins D-09 (noyau pur + résolveur injecté) [exp]
Prototype exécuté (`scratchpad/paths_proto.py`) sur un vrai arbre avec une jonction créée par `mklink /J`, résultats identiques sur 3.11.9 et 3.14.4. Algorithme recommandé :

1. **Lexical (chaîne uniquement, sans pathlib)** : rejeter vide/non-`str` ; caractères `[\x00-\x1f<>"|?*]` ; remplacer `\` par `/` ; préfixe `//` (couvre `\\srv\x`, `\\?\...`, `\\.\...`, `\\?\UNC\...`) → `path_outside_roots` ; forme conteneur : doit commencer par `/` ; forme hôte : `^[A-Za-z]:/` obligatoire (rejette `C:foo`, relatif au lecteur) ; segments : `..` refusé (avant toute conversion), segment vide ou `.` refusé, `:` dans un segment refusé (ADS, `::$DATA`, lecteur relatif), segment terminé par espace ou point refusé (Windows les supprime silencieusement : `sub.` → `sub` [exp]), nom réservé refusé (partie avant le premier `.`, espaces finaux retirés, insensible à la casse : `CON PRN AUX NUL CONIN$ CONOUT$ COM1-9 LPT1-9` et variantes `COM¹ COM² COM³ LPT¹...`).
2. **Correspondance par segments** (jamais `startswith`) : `/data` ↔ `C:/BIM` ; `/data2/x` et `/datax/x` ne correspondent pas ; comparaison sur `segment.lower()` ; `/data` et `/data/` valides (la racine elle-même).
3. **Contrôle lexical sous les racines**, puis **résolution** par `resolver(host_path)` (réel : `str(Path(p).resolve(strict=False))`), **retirer le préfixe `\\?\`** de la sortie (`resolve()` le conserve quand l'entrée l'avait [exp]), refuser tout UNC résolu, relancer le contrôle lexical sur le chemin résolu, vérifier qu'il est sous une racine **elle-même résolue** (une racine peut être une jonction) ; renvoyer le chemin résolu (c'est celui-ci qui sert à l'usage et à l'audit).
4. **Sens inverse (artefacts)** : hôte → conteneur par préfixe de segments sur la racine du mapping, après la même validation ; un artefact hors racines est une erreur, pas un chemin renvoyé tel quel.
5. Le validateur renvoie une erreur typée `PathDenied(code, message)` ; l'API la traduit en 4xx D-08 (`path_outside_roots`, `path_invalid`) — l'exposition HTTP viendra avec les routes de phase 2 ; en phase 1, la fonction est testée en direct.

**Comportements Windows mesurés** (3.11.9 et 3.14.4, sauf mention) :
- `Path.resolve()` suit les jonctions (strict ou non, y compris vers un fichier inexistant : `jun/new.txt` → `outside\new.txt`) ; `os.path.realpath` identique ; `realpath(strict=True)` sur un fichier absent lève `FileNotFoundError`. Utiliser `strict=False` (les chemins de sortie n'existent pas encore) : c'est l'ancêtre existant qui est résolu.
- `Path.is_junction()` existe en 3.12+ (absent en 3.11) : ne pas s'y appuyer, la résolution suffit.
- `resolve()` accepte `\\.\C:\Windows` → `C:\Windows`, `\\localhost\C$\Windows` (UNC loopback, existe) : **lexical avant résolution, impératif**.
- Casse : `resolve(strict=True)` d'un chemin en majuscules renvoie la casse réelle du disque ; sous `strict=False` la casse reste celle de l'entrée : comparer en `lower()`.
- `PureWindowsPath.is_reserved()` : 3.11 ne signale pas ADS/points finaux, 3.14 les signale (et `\\?\...`) ; déprécié en 3.13 ; `ntpath.isreserved` existe dès 3.13 seulement ; `ntpath.isabs("/data/x")` : True en 3.11, False en 3.14 ; `ntpath.splitroot` absent en 3.11. **Ne rien déléguer à ces fonctions.**
- Noms courts 8.3 (`LONGDI~1`) : non testables ici (la génération est désactivée sur ce volume : `dir /x` vide). `resolve()` sur un chemin existant passe par l'API Win32 qui renvoie le nom long ; risque résiduel documenté ; ne pas rejeter `~` (faux positifs).
- Liens symboliques : `mklink /D` a échoué (« privilèges insuffisants ») : mode développeur absent sur cette machine ; la jonction (`mklink /J`, via `cmd /c`) fonctionne sans élévation. Détection de capacité dans le test : `try: os.symlink(...) except OSError as e: if e.winerror == 1314: skip`.
- TOCTOU (jonction substituée entre contrôle et usage) et liens physiques (hardlinks, non détectables) : risques acceptés et documentés (PITFALLS M12).

### Anti-patterns à éviter
- **`str.startswith` pour « sous la racine »** (`C:/BIM2`). Utiliser la comparaison par segments.
- **Faire confiance à `Path.resolve()` pour valider** : il ne rejette ni UNC, ni appareil, ni ADS, ni `C:foo`.
- **`TrustedHostMiddleware`** (réponse texte brut, hors D-08).
- **Dépendance FastAPI pour l'auth** (routes inconnues non protégées).
- **Poser `SO_REUSEADDR` en plus de `SO_EXCLUSIVEADDRUSE`** (erreur 10022) ou laisser Uvicorn lier lui-même (`host=`/`port=` : il pose `SO_REUSEADDR`).
- **Mettre quoi que ce soit d'important dans le `lifespan`** (D-03).
- **Lire `OSError.strerror`** (localisé) au lieu de `winerror`.
- **Imprimer sur stdout avec l'encodage par défaut** (cp1252 ici : `UnicodeEncodeError` sur `U+202E` pendant les tests) : dans `cli.py`, `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` (idem stderr) au tout début ; sous `pythonw`, `sys.stdout` peut valoir `None` (STACK.md) : tester `is not None`.
- **Importer `ctypes` dans `core/`** (test AST) : `instance.py` porte `ctypes`.

## Don't Hand-Roll

| Problème | Ne pas construire | Utiliser | Pourquoi |
|----------|-------------------|----------|----------|
| Dossier de données Windows | Concaténation de `%LOCALAPPDATA%` | `platformdirs.user_data_dir("Deskgate", appauthor=False)` | Cas limites de redirection, mais **vérifier `appauthor`** |
| Validation de la config | Parseur de clés maison | Pydantic `extra="forbid"` + `ValidationError.errors()` | Chemins de clés exacts, types, bornes |
| Comparaison de jeton | `==` | `hmac.compare_digest` sur SHA-256 hex | Temps constant |
| Mutex / instance unique | Fichier verrou, port comme verrou | `CreateMutexW` nommé (ctypes, ~10 lignes) | Libéré à la mort du processus, sans fichier orphelin |
| Boucle d'événements sous Windows | `WindowsSelectorEventLoopPolicy` | Défaut Uvicorn (Proactor) | Vérifié dans le code d'Uvicorn |
| Génération de jeton (dev) | Chaîne maison | `secrets.token_urlsafe(32)` + `hashlib.sha256` | 256 bits d'entropie, argon2 inutile |
| Contrôle lexical des chemins | `Path.is_reserved`, `is_relative_to` | Fonction maison sur chaînes (c'est le cœur du sujet) | Comportement stdlib variable entre 3.11/3.13/3.14 ; ici le code maison est la solution, avec sa batterie de tests d'attaque |

**Point clé :** pour la sécurité des chemins, la stdlib ne suffit pas et change selon la version ; la défense est la combinaison lexical (chaînes) + résolution réelle + recontrôle, testée par une table d'attaques paramétrée.

## Runtime State Inventory

Non applicable : phase de création (greenfield), aucun renommage ni migration. Rien à inventorier.

## Pièges courants

### Piège 1 : le binder `SO_REUSEADDR` coexiste
**Ce qui casse :** deux runners lancés via une voie qui laisse Uvicorn lier le port réussissent tous les deux. **Pourquoi :** `Config.bind_socket` pose `SO_REUSEADDR` [exp : second `REUSEADDR` OK]. **Éviter :** mutex d'abord, bind exclusif manuel. **Signal :** deux `runner_started` ; test `proc` « deux lancements ».

### Piège 2 : tests entrant en collision avec un vrai runner
**Ce qui casse :** un e2e prend le mutex `Local\Deskgate` ou le port 8765 d'un runner réel et échoue, ou pire, passe en tuant le mauvais processus. **Éviter :** nom de mutex et dossier de données paramétrables (`DESKGATE_HOME`, `DESKGATE_INSTANCE_NAME`), port 0 (éphémère, bind exclusif OK) ou port libre détecté, config générée par la fixture dans `tmp_path`.

### Piège 3 : le lanceur de venv double les processus
**Ce qui casse :** `venv\Scripts\python.exe` (et `deskgate.exe` d'un `uv tool install`) est un lanceur qui crée un processus Python enfant [exp : parent 87116, enfant 60376] ; `taskkill /F /PID <lanceur>` laisse l'enfant vivant, et c'est l'enfant qui détient le mutex et le port. **Éviter :** dans les tests e2e, tuer avec `taskkill /F /T /PID` (arbre) ou `psutil` (`Process.children(recursive=True)`), et lancer avec `sys.executable` de l'environnement de test ; le lire avec précaution.

### Piège 4 : codes d'erreur Windows localisés
**Ce qui casse :** détection d'erreur par texte (« address already in use »). **Éviter :** `winerror` (10048, 10013, 10022 ; mutex : 183).

### Piège 5 : `get_last_error` entre deux appels
**Ce qui casse :** `ctypes.get_last_error()` lu après une autre opération renvoie 0 ou une autre erreur. **Éviter :** `WinDLL(..., use_last_error=True)`, `set_last_error(0)` avant, lecture immédiate après.

### Piège 6 : sortie console cp1252
Voir anti-patterns : reconfigurer stdout/stderr en UTF-8 ; messages FR avec accents passent, caractères exotiques plantent.

### Piège 7 : message Pydantic fuyant une valeur secrète
`ValidationError` affiche `input_value` par défaut ; toujours `include_input=False`. Test : une config avec `token_sha256 = "SECRETVALUE"` ne doit pas voir `SECRETVALUE` dans la sortie.

### Piège 8 : `appauthor` de platformdirs
`user_data_dir("Deskgate")` → `...\Deskgate\Deskgate` [exp]. Test unitaire sur le suffixe du chemin (avec `LOCALAPPDATA` simulé).

### Piège 9 : jonction créée en test et nettoyage
`shutil.rmtree` sur un dossier contenant une jonction peut supprimer le contenu de la cible selon la version ; supprimer la jonction avec `os.rmdir`/`os.unlink` d'abord (fixture `junction(tmp_path, target)` avec finaliseur), ne jamais créer une jonction vers un répertoire réel important.

### Piège 10 : vérification Host et conteneur
`host.docker.internal` DOIT être dans la liste (PITFALLS m2) ; le test unitaire le prouve, le spike Docker le confirme sur la machine cible (voir Open Questions).

## Code Examples

### Test AST (frontières du noyau et GPL) 
```python
# tests/architecture/test_import_boundaries.py
import ast, pathlib, pytest
SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "deskgate"
FORBIDDEN_IN_CORE = {"sqlite3", "subprocess", "httpx2", "httpx", "fastapi", "starlette", "ctypes", "uvicorn"}

def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            yield from (a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            yield n.module.split(".")[0]

@pytest.mark.unit
@pytest.mark.parametrize("py", sorted((SRC / "core").rglob("*.py")), ids=lambda p: p.name)
def test_core_est_pur(py):
    assert not (set(_imports(py)) & FORBIDDEN_IN_CORE)

@pytest.mark.unit
def test_frontiere_gpl():
    root = SRC.parents[1]
    allowed = root / "plugins" / "bim" / "bcf"
    offenders = []
    for py in root.rglob("*.py"):
        if ".venv" in py.parts or allowed in py.parents:
            continue
        if {"bcf", "deskgate_bcf"} & set(_imports(py)):
            offenders.append(py)
    assert not offenders
```
(`importlib`/`__import__` dynamiques ne sont pas détectés : limite assumée ; ajouter une recherche textuelle de `"bcf"` dans `import_module(` si souhaité.) Étendre `FORBIDDEN_IN_CORE` avec `deskgate_bim` pour la règle 1 de CLAUDE.md (le cœur ne connaît pas le BIM) : test séparé sur tout `src/deskgate`.

### Spike D-13(b) devenu test `proc`/`unit` (bind exclusif)
```python
# Source : scratchpad/sock1.py exécuté
@pytest.mark.unit   # socket local, pas de sous-processus : classer "fs"/"unit" au choix du plan
def test_second_bind_echoue():
    a = bind_exclusive("127.0.0.1", 0); a.listen()
    port = a.getsockname()[1]
    with pytest.raises(OSError) as e:
        bind_exclusive("127.0.0.1", port)
    assert e.value.winerror == 10048
    b = socket.socket(); b.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    with pytest.raises(OSError) as e2:
        b.bind(("127.0.0.1", port))
    assert e2.value.winerror == 10013
```
Les tests qui dépendent de WinError doivent être `skipif(sys.platform != "win32")` (le projet est Windows seul ; CI `windows-latest`).

### Spike D-13(c) : Job Object ctypes + petit-enfant orphelin (forme du test pytest)
Code complet exécuté (`scratchpad/jobspike.py`, résultat identique en 3.11 et 3.14) :
```python
# Structures : JOBOBJECT_EXTENDED_LIMIT_INFORMATION (classe 9), LimitFlags = 0x2000 (KILL_ON_JOB_CLOSE)
def spawn_in_job(job, argv, **kw):
    p = subprocess.Popen(argv, creationflags=CREATE_SUSPENDED | CREATE_NO_WINDOW, **kw)
    assert k32.AssignProcessToJobObject(job, wintypes.HANDLE(int(p._handle)))
    assert ntdll.NtResumeProcess(wintypes.HANDLE(int(p._handle))) == 0
    return p
# enfant : lance un petit-enfant `sleep 120` qui écrit son PID dans PIDFILE puis `os._exit(0)` (orphelin)
# 1) attendre la sortie du parent ; lire le PID ; alive(pid) == True           (l'orphelin survit à son parent)
# 2) TerminateJobObject(job, 1)        -> alive(pid) == False
# 3) autre job : CloseHandle(job)       -> alive(pid) == False  (KILL_ON_JOB_CLOSE)
alive = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION) + GetExitCodeProcess == STILL_ACTIVE (259)
```
Sortie observée : `orphan alive: True` → après `TerminateJobObject` : `False` ; second scénario : `True` → après `CloseHandle(job2)` : `False`. Fonctionne aussi quand `sys.executable` est le lanceur de venv. Les `argtypes` explicites (HANDLE, LPVOID) sont nécessaires : sans eux, les poignées 64 bits sont tronquées. Le module définitif reste en phase 2 ; en phase 1 le test vit dans `tests/proc/test_spike_jobobject.py` avec le helper dans `tests/_support/` (ne pas l'importer depuis `src`). `int(p._handle)` marche en 3.11 et 3.14 (attribut privé : à isoler dans `spawn_in_job`).

### Auth + Host + erreurs : voir le prototype exécuté
Fichiers de référence (scratchpad) : `api_proto.py` (middlewares + handlers), `api_test.py` (16 cas : health sans jeton 200, mauvais Host 400, `host.docker.internal:8765` 200, `LocalHost` 200, 401 jeton absent/faux, 422 reformaté, route inconnue 401/404, 405, 500, Host avant auth, docs désactivées, `/health/` 401, `localhost.` 400). Ces 16 cas sont la base de `tests/unit/test_api_security.py` (avec `TestClient(app, base_url="http://127.0.0.1:8765", raise_server_exceptions=False)` ; `TestClient` exige `httpx2`).

### Workflow GitHub Actions (windows-latest)
```yaml
# .github/workflows/ci.yml
name: ci
on: { push: { branches: [main] }, pull_request: {} }
jobs:
  gate:
    runs-on: windows-latest
    strategy:
      fail-fast: false
      matrix: { python: ["3.11", "3.13"] }
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v10          # v10.3.0 au 2026-10-20
        with: { python-version: "${{ matrix.python }}", enable-cache: true }
      - run: uv sync --locked
      - run: uv run ruff check
      - run: uv run ruff format --check
      - run: uv run pyright
      - run: uv run pytest -m "not e2e"
      - run: uv build --all-packages
      - run: uv run pytest -m e2e
```
(Épingler `setup-uv` par tag majeur ; vérifier les entrées `python-version` et `enable-cache` dans la doc de la version retenue au moment de l'écriture : non revérifié ici, MOYENNE.)

### `pyproject.toml` racine (validé : `uv lock`, `uv sync --locked`, ruff, pyright, pytest, `uv build --all-packages` exécutés)
```toml
[project]
name = "deskgate"
version = "0.1.0.dev0"
requires-python = ">=3.11"
license = "MIT"
dependencies = ["fastapi>=0.151,<0.152", "uvicorn>=0.54,<0.55", "pydantic>=2.14,<3", "platformdirs>=4.13", "typer>=0.27,<0.28"]
[project.scripts]
deskgate = "deskgate.cli:app"
[build-system]
requires = ["hatchling>=1.32"]
build-backend = "hatchling.build"
[tool.hatch.build.targets.wheel]
packages = ["src/deskgate"]
[tool.uv]
default-groups = ["dev"]
[tool.uv.workspace]
members = []                       # "plugins/bim", "plugins/bim/bcf" ajoutés quand les répertoires existent
[dependency-groups]
dev = ["pytest>=9.1,<10", "httpx2>=2.15,<3", "psutil>=7.2", "ruff>=0.17,<0.18", "pyright>=1.1.414"]
[tool.ruff]
line-length = 100
target-version = "py311"
src = ["src", "tests"]
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "S", "SIM", "RUF"]
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "S603", "S607"]
[tool.pyright]
include = ["src", "tests"]
pythonVersion = "3.11"
typeCheckingMode = "standard"
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["--strict-markers", "--strict-config", "-ra"]
markers = [
  "unit: noyau pur, sans disque, serveur ni sous-processus",
  "fs: vrai système de fichiers (jonctions, ADS, noms réservés)",
  "proc: vrais sous-processus Windows",
  "e2e: deskgate serve en sous-processus",
]
```
Remarques : `--strict-markers` fait échouer tout marqueur non déclaré ; `members = []` est accepté par uv 0.12.17 (le workspace est vide jusqu'aux phases suivantes ; ajouter un membre dont le répertoire n'existe pas provoque une erreur) ; `ctypes.WinDLL` est inconnu de pyright sur d'autres plateformes mais le projet est Windows seul (laisser `pythonPlatform` par défaut sous Windows ; en CI c'est `windows-latest`). Un finding ruff trivial est apparu sur le squelette (formatage) : `ruff format` d'abord. La règle `S` (bandit) signalera `subprocess` et `assert` : ignorées dans `tests/`, à justifier ligne à ligne dans `src/`.

## État de l'art

| Ancien | Actuel | Impact |
|--------|--------|--------|
| `uvicorn.run(host, port)` | `Server(Config).run(sockets=[sock])` | contrôle du bind (D-03) ; Uvicorn ne journalise pas l'URL dans ce cas |
| `loop = asyncio.get_event_loop(); policy` | `Config.get_loop_factory()` (≥ 0.36) | Proactor sous Windows par défaut |
| `starlette.testclient` sur `httpx` | `httpx2` (1.9) | `httpx2` obligatoire en dev |
| `Path.is_reserved` | `os.path.isreserved` (3.13+) | non portable 3.11 : code maison |

## Open Questions

1. **Spike D-13(a) `host.docker.internal` → 127.0.0.1 : non exécuté.**
   - Connu : Docker 29.8.2, contexte `desktop-linux` ; Docker Desktop **n'est pas démarré** (moteur `dockerDesktopLinuxEngine` injoignable). La recherche antérieure (`verifs-techniques-cycle-1.md` §2) conclut avec confiance élevée que cela fonctionne avec Docker Desktop (relais côté Windows) mais « pas prouvé sur cette machine ».
   - Manque : preuve empirique.
   - Recommandation : tâche de vague 0 (non bloquante pour le code) : démarrer Docker Desktop, puis `py -3.14 -m http.server 8799 --bind 127.0.0.1` et `docker run --rm alpine wget -qO- http://host.docker.internal:8799/` (alpine/busybox `wget` : n'a pas besoin de curl ; vérifier la présence de l'image, sinon `curlimages/curl`) ; consigner le code et l'IP source vue par le serveur dans le SUMMARY. Repli si échec : option `allow_non_loopback` sur l'IP vEthernet (déjà prévue par D-02), à traiter en phase 5. Marquer ce point « action humaine différable » (il ne retient pas le code de la phase 1, mais SEC-02 vaut pour la machine cible en phase 5, INS-05).
2. **Liens symboliques :** non testables sur cette machine (WinError 1314). Le test `skipif` est prévu ; la CI `windows-latest` crée des liens symboliques normalement (les runners GitHub ont les privilèges), à confirmer au premier passage de la CI (MOYENNE).
3. **Noms 8.3 :** non vérifiables (volume sans noms courts). Risque résiduel faible ; à noter dans la doc de sécurité.
4. **Python 3.12/3.13 absents localement :** les expériences couvrent 3.11 et 3.14 (3.13 est entre les deux pour les API concernées). `uv python install 3.13` n'a pas abouti pendant la recherche (le lien du répertoire géré uv est cassé : voir Environnement) ; la CI couvre 3.11 et 3.13.
5. **Contenu de `/health` (discrétion) :** recommandation `{"status":"ok","version":"<__version__>","warnings":[...]}` où `warnings` contient `"listen_non_loopback"` quand `allow_non_loopback` est vrai ; aucun chemin, aucun nom de capacité, aucun secret.
6. **Commande de jeton de dev (discrétion) :** recommandation d'une sous-commande Typer cachée `deskgate dev-token` imprimant le jeton (une fois) et la ligne `token_sha256 = "..."` ; remplacée par `deskgate init` en phase 5 (INS-01). Alternative sans code : une ligne `python -c` dans le gabarit commenté.
7. **Forme des chemins acceptés (SEC-03) :** l'API n'accepte que la forme conteneur `/data/...` (D-09) ; les chemins hôte `C:/BIM/...` en entrée sont refusés (`path_invalid`) sauf usage interne (dossier de travail, artefacts). À confirmer par le planificateur si un cas d'usage exige la forme hôte en entrée.

## Environment Availability

| Dépendance | Requis par | Disponible | Version | Repli |
|------------|-----------|------------|---------|-------|
| Python 3.11 | tests | oui | 3.11.9 | — |
| Python 3.14 | tests/dev | oui | 3.14.4 | — |
| Python 3.12 / 3.13 | cible dev (STACK.md) | non (local) | — | CI matrice 3.11 + 3.13 |
| uv | workspace, gate | oui | 0.12.17 (dernier : 0.13.3) | — |
| uv — Pythons gérés | `uv venv --python 3.13` | **cassé** : le lien `...\AppData\Roaming\uv\python\cpython-3.13-windows-x86_64-none` est introuvable ; le téléchargement tenté pendant la recherche a échoué avec « Missing expected target directory for Python minor version link » | — | `UV_PYTHON` vers le Python système (`C:\Users\Tanguy\AppData\Local\Python\pythoncore-3.14-64\python.exe`) |
| Node.js | pyright (PyPI) | oui | v24.14.1 | — |
| Docker Desktop | spike D-13(a), INS-05 | **non démarré** | CLI 29.8.2 | spike différé (action humaine) |
| Mode développeur / privilège symlink | tests `fs` symlink | non | — | `skipif` explicite ; jonctions OK |
| Windows 11 Pro 10.0.26200 | tout | oui | — | — |
| gh CLI | consultation des versions | oui | — | — |

**Bloquant sans repli :** aucun pour le code.
**Avec repli :** Docker (spike différé), Python 3.12/3.13 (CI), symlinks (skipif).

## Validation Architecture

### Test Framework
| Propriété | Valeur |
|-----------|--------|
| Framework | pytest 9.1.1 (+ `starlette.testclient` via httpx2 2.15.1) |
| Fichier de config | `pyproject.toml` `[tool.pytest.ini_options]` (marqueurs enregistrés, `--strict-markers`) |
| Commande rapide | `uv run pytest -m "unit" -q -x` (< 5 s attendu) |
| Commande de gate complète | `uv run pytest -m "not e2e"` puis `uv run pytest -m e2e` |
| Autres vérifications du gate | `uv run ruff check`, `uv run ruff format --check`, `uv run pyright`, `uv build --all-packages` |
| Clés d'environnement des tests | `DESKGATE_HOME` (tmp), `DESKGATE_INSTANCE_NAME` (mutex unique par test), port 0/libre |

Marqueurs : `unit` (aucun disque, aucun serveur réel, aucun sous-processus ; horloge et résolveur injectés ; `TestClient` autorisé car en mémoire), `fs` (vrai disque : jonctions, ADS, `CON`), `proc` (sous-processus réels : mutex, Job Object, deux runners), `e2e` (`deskgate serve` en sous-processus + client HTTP). Convention : chaque fichier de test porte `pytestmark = pytest.mark.<x>` ; les tests d'architecture (AST) sont `unit`.

### Exigences → tests
| Req | Comportement | Type | Commande automatisée | Fichier |
|-----|--------------|------|----------------------|---------|
| RUN-01 | La config refuse `host` non loopback sans `allow_non_loopback` ; le défaut est `127.0.0.1:8765` ; `allow_non_loopback=true` accepté (avec avertissement) | unit | `pytest tests/unit/test_config.py -k "loopback"` | Wave 0 |
| RUN-01 | `deskgate serve` écoute sur 127.0.0.1 uniquement : connexion sur l'IP LAN refusée, sur 127.0.0.1 acceptée ; `Server.run` reçoit un socket exclusif | e2e | `pytest -m e2e tests/e2e/test_serve.py::test_ecoute_loopback_seulement` | Wave 0 |
| RUN-01 | `bind_exclusive` : second bind échoue (10048), `SO_REUSEADDR` échoue (10013) | unit | `pytest tests/unit/test_instance_socket.py` | Wave 0 |
| RUN-02 | Config valide chargée ; clé inconnue (y compris imbriquée), clé manquante, port hors bornes, TOML invalide, jeton mal formé → échec, message FR citant la clé, sans fuite de valeur | unit | `pytest tests/unit/test_config.py` | Wave 0 |
| RUN-02 | `deskgate serve` avec config invalide : code de sortie 2, message FR sur stderr, aucune base créée | e2e | `pytest -m e2e -k config_invalide` | Wave 0 |
| RUN-03 | Mutex : second `acquire` échoue tant que le premier tient ; libéré à la mort du processus | proc | `pytest -m proc tests/proc/test_mutex.py` | Wave 0 |
| RUN-03 | Deuxième `deskgate serve` : code 3, message FR, le fichier `deskgate.db` n'est pas créé/modifié (mtime + absence) | e2e | `pytest -m e2e -k second_runner` | Wave 0 |
| RUN-03 | Redémarrage après `taskkill /F /T` : le premier relance sans erreur de port | e2e | `pytest -m e2e -k redemarrage_apres_kill` | Wave 0 |
| RUN-04 | `/health` 200 sans jeton ; ne contient ni chemin ni secret ; porte `warnings` si non loopback | unit (TestClient) + e2e | `pytest tests/unit/test_api_security.py -k health` | Wave 0 |
| SEC-01 | 401 sans/avec mauvais jeton sur toute route (y compris inconnue) ; 200 avec bon jeton ; `compare_digest` utilisé ; jeton clair absent des journaux | unit | `pytest tests/unit/test_api_security.py tests/unit/test_tokens.py` | Wave 0 |
| SEC-02 | 400 `host_not_allowed` pour Host hors liste ; 200 pour `127.0.0.1`, `localhost`, `host.docker.internal` avec/sans port ; Host vérifié avant l'auth | unit | `pytest tests/unit/test_hostcheck.py tests/unit/test_api_security.py -k host` | Wave 0 |
| SEC-03 | `/data/x/y.ifc` → `C:/BIM/x/y.ifc` ; retour hôte → conteneur ; `/data2/x`, `/datax` refusés | unit (résolveur injecté) | `pytest tests/unit/test_paths_mapping.py` | Wave 0 |
| SEC-04 | Table d'attaques lexicales (`..`, UNC, `\\?\`, `\\.\`, `C:foo`, `C:/BIM2`, `CON`, `nul.txt`, `COM1`, `COM¹`, ADS, `::$DATA`, point/espace final, NUL) sans disque | unit | `pytest tests/unit/test_paths_attacks.py` | Wave 0 |
| SEC-04 | Vraies jonctions (`mklink /J` vers l'extérieur), fichier inexistant sous jonction, ADS réel, casse, lien symbolique (skipif) | fs | `pytest -m fs tests/fs/test_paths_real.py` | Wave 0 |
| D-10 | `core/` pur ; frontière GPL | unit | `pytest tests/architecture` | Wave 0 |
| D-13 | Spikes (b) et (c) en tests | proc | `pytest -m proc tests/proc/test_spike_jobobject.py tests/unit/test_instance_socket.py` | Wave 0 |
| D-13(a) | `host.docker.internal` depuis un conteneur | manuel (Docker requis) | procédure Open Questions §1 | manuel : justification : Docker Desktop non scriptable en CI `windows-latest` |
| D-12 | Gate complet vert localement et en CI | CI | commandes du gate | Wave 0 |

### Fréquence d'échantillonnage
- **Par commit de tâche :** `uv run pytest -m unit -q -x` + `uv run ruff check`.
- **Par fusion de vague :** `uv run pytest -m "not e2e"` + pyright.
- **Gate de phase :** tout le gate D-12, e2e compris, avant `/gsd:verify-work`.

### Lacunes de la vague 0
- [ ] `pyproject.toml`, `uv.lock`, `src/deskgate/` squelette, `.github/workflows/ci.yml` (D-12)
- [ ] `tests/conftest.py` : fixtures `instance_name` (mutex unique), `data_home` (tmp + `DESKGATE_HOME`), `free_port`, `junction(link, target)` avec nettoyage, `symlink_ok` (skipif WinError 1314), `runner_process` (démarre `deskgate serve`, attend `/health`, tue l'arbre `taskkill /F /T`)
- [ ] Fichiers de test listés ci-dessus
- [ ] Spike D-13(a) manuel (Docker) consigné dans le SUMMARY

## Sources

### Primaires (HAUTE)
- Code source installé : `uvicorn 0.54.0` (`server.py`, `config.py`, `loops/asyncio.py`), `starlette 1.9.0` (`middleware/trustedhost.py`, `_utils.py`, `testclient.py`) : lus et exécutés
- Expériences exécutées le 2026-10-20 (scratchpad) : `sock1.py`, `mutex1.py`, `path1.py`, `path2.py`, `paths_proto.py`, `api_proto.py`/`api_test.py`, `cfg_proto.py`, `serve_proto.py`, `jobspike.py`, projet uv complet (`uv lock/sync/build`, ruff, pyright, pytest)
- PyPI JSON (versions et dates) ; `gh api` pour `astral-sh/setup-uv` et `actions/checkout`
- `.arthemis/reports/llm-council-1.md`, `.arthemis/reports/verifs-techniques-cycle-1.md` §2 et §6, `.planning/research/PITFALLS.md` (M12, M14, M16, m1, m2, P3)

### Secondaires (MOYENNE)
- Documentation Win32 (CreateMutexW, SO_EXCLUSIVEADDRUSE, Job Objects) connue mais non rouverte : le comportement a été **mesuré** plutôt que cité
- Entrées `astral-sh/setup-uv` (`python-version`, `enable-cache`) : de mémoire, à revérifier à l'écriture du workflow

### Tertiaires (BASSE)
- Comportement des liens symboliques et des noms 8.3 sur `windows-latest` : non vérifié

## Metadata

**Confiance :**
- Pile standard : HAUTE (versions lues sur PyPI, projet uv construit et exécuté)
- Architecture (démarrage, middlewares, config) : HAUTE (prototype exécuté de bout en bout)
- Chemins : HAUTE pour jonctions/UNC/ADS/réservés/préfixes ; MOYENNE pour symlinks et 8.3 (non testés ici)
- Spike Docker : AUCUNE preuve (non exécuté)
- Pièges : HAUTE

**Date de recherche :** 2026-10-20
**Valide jusqu'à :** 2026-11-20 (Uvicorn/FastAPI changent vite ; épinglés par mineure)

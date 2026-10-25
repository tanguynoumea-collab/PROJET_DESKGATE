# Architecture de Deskgate

Deskgate est une **passerelle locale** entre un orchestrateur (n8n en priorité) et les outils
lourds d'un PC Windows : calculs longs (IfcOpenShell), logiciels installés, serveurs MCP en stdio.
n8n soumet une tâche, Deskgate l'exécute dans la session Windows de l'utilisateur, puis rappelle
n8n avec le résultat.

Ce document est la référence technique. Les décisions de fond et leur justification sont dans
[`docs/passation/02-DECISIONS.md`](docs/passation/02-DECISIONS.md) ; les vérifications qui fondent
les choix ci-dessous sont dans [`.arthemis/reports/`](.arthemis/reports/).

## État livré en v0.1

Ce qui suit décrit le code livré ; le reste du document décrit aussi la cible, marquée « cible vX ».
Chaque puce cite le code (`fichier:ligne` (`symbole`)) ; `tests/unit/test_architecture_doc.py` vérifie ces
références.

- API : cinq routes. `/health` n'exige pas de jeton (`src/deskgate/api/routes_health.py:14` (`@router.get("/health")`)) ;
  `POST /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/logs` et `POST /jobs/{id}/cancel` l'exigent
  (`src/deskgate/api/routes_jobs.py:28` (`@router.post("/jobs"`), 
  `src/deskgate/api/routes_jobs.py:34` (`@router.get("/jobs/{job_id}")`), `src/deskgate/api/routes_jobs.py:39` (`/logs`),
  `src/deskgate/api/routes_jobs.py:54` (`/cancel`)). OpenAPI et pages de documentation sont désactivées
  (`src/deskgate/api/app.py:36` (`openapi_url=None`)).
- Écoute sur `127.0.0.1` par défaut (`src/deskgate/core/config.py:202` (`host: str = "127.0.0.1"`)) ; un seul jeton,
  stocké haché dans `runner.toml` (`src/deskgate/core/config.py:204` (`token_sha256`)).
- Deux types d'exécution : `python` et `mcp` (`src/deskgate/core/config.py:119` (`Literal["python", "mcp"]`)). Les
  serveurs MCP sont lancés en stdio ; ils sont déclarés dans la table `[mcp_servers]` de `runner.toml`
  (`src/deskgate/core/config.py:168` (`class McpServer`), `src/deskgate/core/config.py:209` (`mcp_servers:`)).
- Une seule tâche `running` à la fois pour tout le runner
  (`src/deskgate/store.py:371` (`NOT EXISTS (SELECT 1 FROM jobs WHERE status='running')`)) ; la colonne `resource` est
  enregistrée mais jamais lue pour ordonnancer (`src/deskgate/store.py:90` (`resource TEXT NOT NULL`)).
- Idempotence : une clé est refusée (409) tant qu'une tâche `queued` ou `running` la porte
  (`src/deskgate/store.py:96-97` (`jobs_idem`)) ; le résultat d'une tâche réussie n'est pas réutilisé.
- Base SQLite : tables `jobs`, `callbacks` et `audit` ; l'audit est en ajout seul
  (`src/deskgate/store.py:109` (`audit_no_update`)). Au redémarrage, les tâches `running` passent `interrupted`
  (`src/deskgate/store.py:451` (`def recover_interrupted`)).
- Isolation : le sous-processus du plugin est créé suspendu dans un Job Object
  (`src/deskgate/jobobject.py:195` (`CREATE_SUSPENDED`)). L'annulation est d'abord coopérative
  (`src/deskgate/engine.py:451` (`cancel.flag`)), puis `TerminateJobObject` tue l'arbre
  (`src/deskgate/jobobject.py:120` (`TerminateJobObject`)).
- Frontière worker en JSON strict : `NaN`, `Infinity` et `1e999` sont refusés, la tâche finit
  `failed/invalid_result` (`src/deskgate/core/worker_protocol.py:82` (`def _loads_strict`)).
- Rappel : le corps porte `job_id`, `capability`, `status`, `duration_s`, `summary`, `data`, `artifacts` et `error`
  (`src/deskgate/core/payload.py:38` (`def result_parts`),
  `src/deskgate/core/payload.py:67` (`def build_callback`)). Plafond de 1 Mio (`src/deskgate/core/payload.py:18` (`CALLBACK_MAX_BYTES`)) : au-delà,
  `data` puis `summary` sont déportés dans `data.json` puis `summary.json` du dossier de la tâche, la clé valant
  `{"path": "…", "truncated": true}` (`src/deskgate/engine.py:555` (`def _cap_result`)). Après un 413, le renvoi minimal
  remplace `summary` et `data` par `{"truncated": true}`, sauf une valeur déjà réduite à un marqueur de repli, transmise
  telle quelle avec son chemin (`src/deskgate/core/payload.py:62` (`def minimal`)). `mcp.call` déporte une réponse
  > 900 000 octets dans `mcp-result.json` ; `data` vaut alors `{"truncated": true, "artifact": "mcp_result"}` et le
  chemin est celui de l'entrée `artifacts` de ce type (`src/deskgate/workers/mcp_call.py:128` (`"artifact": "mcp_result"`)).
  `data` n'est pas masqué. `GET /jobs/{id}` porte le même `data` (`src/deskgate/jobs.py:50` (`def job_view`)).
- Sender : une erreur propre à un rappel (corps illisible…) est un essai en échec `internal_error` de cette ligne
  (`src/deskgate/sender.py:155` (`def _record_internal_error`)) ; seules les erreurs de base comptent pour l'arrêt du
  thread (`src/deskgate/sender.py:53` (`MAX_CONSECUTIVE_ERRORS`)).
- Superviseur : il recrée un thread mort, puis sort en code 6 au-delà du budget
  (`src/deskgate/supervisor.py:32` (`EXIT_THREAD_FAILED = 6`)).
- CLI : `deskgate init`, `serve`, `doctor`, `task …` et `purge`
  (`src/deskgate/cli.py:54` (`def serve`), `src/deskgate/cli.py:76` (`def doctor`),
  `src/deskgate/cli.py:147` (`def init`), `src/deskgate/cli.py:205` (`task_app`)). `deskgate purge --older-than-days N`
  remplace `data` par `{"purged": true}` pour les tâches au rappel final, sans migration
  (`src/deskgate/cli.py:88` (`def purge`), `src/deskgate/store.py:643` (`def purge_data`)).
- BCF : `deskgate-bcf` n'offre que la sous-commande `write`
  (`plugins/bim/bcf/src/deskgate_bcf/cli.py:50` (`sub.add_parser("write"`)).

### Absent en v0.1 (cible)

- Routes `/capabilities` et `/capabilities/{id}` : cible v0.2.
- Interface locale `/ui` : cible v0.3.
- Exécuteur `cli` : cible v0.2.
- Manifestes `plugin.yaml` et `deskgate plugin add` : cible v0.2.
- Jetons multiples et droits par plugin : cible v0.2.
- Ressources et concurrence par ressource : cible v0.2.
- Réutilisation idempotente d'un résultat : cible v0.2.
- MCP en Streamable HTTP : cible v0.2.
- Lecture `.bcf` et capacités `bcf.read` / `bcf.write` : cible v0.2.
- Nœud `n8n-nodes-deskgate` : cible v0.3.
- Plugins d'exemple : cible v0.4.
- `/jobs/{id}/artifacts/{name}` et OpenAPI publiée : cible (non planifiée).

## 0. Périmètre

| Dans ce dépôt | Hors de ce dépôt (projet d'intégration) |
|---|---|
| Le runner (API, file, exécuteurs, sécurité ; interface locale : cible v0.3) | Les workflows n8n complets (coordination, audit, évolution) |
| Le nœud communautaire `n8n-nodes-deskgate` (cible v0.3) | Ingestion, registre des maquettes, base et déduplication des conflits |
| Les plugins BIM `deskgate-bim` (calcul et logiciels) | Tri et synthèse par IA, Hermes Agent, superviseur, tableau de bord |
| Des plugins d'exemple (Python, CLI, MCP ; cible v0.4, en v0.1 : `tests/fake_plugins/`, `tests/mcp_fake/`) et des workflows n8n de démonstration | Toute exposition de Deskgate comme serveur MCP |

Deskgate **ne planifie pas et n'enchaîne pas** : pas de DAG, pas de déclencheur, pas de reprise
d'étapes. Une tâche = un appel d'un plugin. L'enchaînement est le rôle de n8n.

## 1. Vue d'ensemble

Schéma cible (v0.3). Livré en v0.1 : voir « État livré en v0.1 ».

```
┌──────────── Docker Desktop (WSL2) ─────────────┐
│  n8n 2.43.8 (+ n8n-nodes-deskgate, cible v0.3) │
│  Postgres                                      │
└───────────────┬───────────────▲────────────────┘
   POST /jobs   │               │ rappel : POST resumeUrl (signée)
   http://host.docker.internal:8765
┌───────────────▼───────────────┴──── Windows natif, session utilisateur ───┐
│  Deskgate (Python ≥ 3.11)                                                 │
│   ├─ API HTTP (FastAPI)  : /health /jobs  (/capabilities : cible v0.2)    │
│   ├─ Interface web       : /ui (cible v0.3)                               │
│   ├─ File de tâches      : SQLite, une tâche à la fois (v0.1)             │
│   ├─ Exécuteurs          : python │ mcp ; cli : cible v0.2 (Job Object)    │
│   ├─ Registre de plugins : plugin.yaml + env. uv (cible v0.2)             │
│   └─ Sécurité            : jeton haché, audit, chemins (droits : cible v0.2)│
│                                                                           │
│  Plugins (dossiers séparés, un environnement uv chacun)                    │
│   ifc.clash  ifc.audit  ifc.diff  ifc.quantities  …                       │
└───────────────────────────────────────────────────────────────────────────┘
        Dossier partagé :  C:\BIM\   ⇄   /data  (monté dans les conteneurs)
```

## 2. Le runner

- **Python ≥ 3.11**, FastAPI + Uvicorn, paquet `deskgate`, commande `deskgate`.
- **Écoute sur `127.0.0.1:8765` uniquement.** Docker Desktop relaie `host.docker.internal` vers le
  loopback de Windows : aucune règle de pare-feu ni `.wslconfig` n'est nécessaire
  (vérification technique §2, à confirmer sur la machine au début de la v0.1). Refus de démarrer sur
  une autre interface sans option explicite. Variante documentée : Docker Engine installé
  directement dans WSL2 en mode NAT impose d'écouter sur l'interface vEthernet.
- Conséquence : **tout conteneur local peut joindre le runner**. Le jeton est donc obligatoire sur
  toutes les routes sauf `/health`, même en local.
- **Persistance SQLite** (mode WAL) : tâches, rappels et audit (tables `jobs`, `callbacks`, `audit`) ; journaux de
  tâche en fichiers ; jetons hachés multiples et état des plugins : cible v0.2. Au redémarrage, les tâches `running` passent `interrupted` et leur rappel est envoyé.
- **Démarrage** : tâche du Planificateur de tâches Windows créée par `schtasks /Create /XML`, sans
  élévation : ouverture de session, `InteractiveToken`, `LeastPrivilege`, `ExecutionTimeLimit=PT0S`,
  batterie autorisée, `IgnoreNew`. L'action est `pythonw.exe -m deskgate serve` du venv de l'outil (pas de
  console, pas de `gui-scripts`) ; le journal `logs\runner.log` est ouvert après le mutex.
  `RestartOnFailure` ne couvre que les échecs de démarrage : il ne relance ni un runner tué, ni un runner
  sorti avec un code non nul (constaté en phase 5.2). Dans le processus, un superviseur recrée un thread
  engine ou sender mort après avoir conclu la tâche courante en `interrupted` ; au-delà de 3 recréations
  effectives en 10 min, ou de 10 échecs consécutifs de la conclusion des tâches (base verrouillée :
  nouvel essai après 2, 4, 8, 16 puis 30 s), le runner sort avec le code 6. Les échecs de démarrage sont écrits dans `logs\startup.log`
  (même sous `pythonw`). Un runner tué reste arrêté jusqu'à `deskgate task run` ou la prochaine ouverture
  de session ; la recovery `interrupted` rend cette relance sûre (constaté : runner tué, relancé, rappel
  `interrupted` reçu par n8n). Pas de service Windows : un
  service ne voit pas le bureau et ne peut pas piloter de logiciel graphique.
- **Configuration** : `runner.toml` (port, racines autorisées, correspondance des chemins,
  capacités et serveurs MCP, un jeton `token_sha256` ; concurrence par ressource et dossier des plugins :
  cible v0.2).

## 3. File de tâches et ordonnancement

File **écrite pour Deskgate** au-dessus de SQLite, pas de bibliothèque de file : aucune ne gère à la
fois la concurrence par ressource, l'état `interrupted`, l'annulation et l'idempotence par clé, et
celles qui ont un mode multi-processus sont fragiles sous Windows (rapport de l'existant). Huey
reste le plan B.

- Cycle de vie : `queued → running → succeeded | failed | timeout | cancelled | interrupted`.
- Cible v0.2 : chaque plugin déclare une **ressource** ; chaque ressource a une **concurrence maximale** :
  `gui-session` = 1, `cpu-heavy` = 1 (défaut), `light` = N. En v0.1 : une tâche à la fois.
- **Idempotence** : en v0.1, une clé est refusée (409) tant qu'une tâche `queued`/`running` la porte. Cible v0.2 :
  renvoi du résultat d'une tâche réussie sans recalcul (désactivable par le client).
- Plafonds : la mémoire d'une tâche est plafonnée par son Job Object (`memory_mb` de la capacité dans
  `runner.toml`) ; le nombre de threads est un réglage du plugin (`settings.threads` de la capacité, lu par
  `ifc.clash`). Plafond transmis aux plugins par variables d'environnement (`OMP_NUM_THREADS`…) : cible (non
  planifiée).

## 4. Exécution des plugins

### Types d'exécution

| Type | Ce que le runner exécute |
|---|---|
| `python` | `module:fonction(params, ctx) -> dict`, dans l'environnement uv du plugin, **dans un sous-processus** (jamais dans le processus du runner) |
| `cli` (cible v0.2) | Un exécutable et un **gabarit d'arguments déclaré** ; pas de shell, pas de concaténation libre |
| `mcp` | Un outil d'un serveur MCP, appelé avec le SDK `mcp` officiel, sans LLM : stdio, serveurs déclarés dans `[mcp_servers]` de `runner.toml` ; Streamable HTTP : cible v0.2 |

### Isolation et arrêt

- Chaque tâche tourne dans un **Job Object Windows** : processus créé suspendu
  (`CREATE_SUSPENDED`), assigné au job, puis repris. La sortie du job (`breakaway`) n'est jamais
  autorisée. Au délai maximum ou à l'annulation (coopérative d'abord : `cancel.flag`, délai de grâce), `TerminateJobObject` tue tout l'arbre, y compris
  les petits-enfants orphelins que `psutil` ne voit pas.
- Limite connue : un logiciel lancé via COM (Revit, Excel) n'appartient pas au job. Un plugin qui
  pilote un logiciel par COM doit le fermer lui-même et le déclarer dans son manifeste.
- Chaque tâche a un `work_dir` : `C:/BIM/travail/<job_id>/`.

### Contexte passé au plugin (`ctx`)

`job_id`, `work_dir`, `log(msg)`, `progress(pct, msg)`, `artifact(path, kind)`, `cancelled()`.
Les chemins déclarés (`path_params` d'une capacité python, `path_arguments` d'un outil MCP) sont
déjà convertis au format Windows et validés contre les racines autorisées.

### Sortie d'un plugin

```json
{ "summary":   { "...": "petit résumé lisible" },
  "data":      { "...": "sortie structurée du plugin" },
  "artifacts": [ { "kind": "bcf", "path": "C:/BIM/travail/a1b2/conflits.bcf" } ] }
```

`data` est transmis à n8n (rappel) et à `GET /jobs/{id}` tel quel, sans masquage : un plugin n'y met jamais de
secret. `output_schema` : cible v0.2. Les valeurs `NaN`, `Infinity` et les flottants hors limites sont refusés
(tâche `failed/invalid_result`). `mcp.call` déporte une réponse > 900 000 octets dans l'artefact
`mcp_result` (`mcp-result.json`) et `data` vaut `{"truncated": true, "artifact": "mcp_result"}` : le chemin se lit dans
l'entrée `artifacts` de ce type. Au-delà de 1 Mio de corps, l'engine applique son propre repli (`data.json`).

## 5. Manifeste `plugin.yaml` (cible v0.2)

```yaml
id: ifc.clash
version: 0.1.0
title: Détection de conflits IFC
description: Détection IfcOpenShell entre deux sélections, regroupement, BCF 2.1 optionnel
kind: python                      # python | cli | mcp
category: BIM / Coordination

python:
  entry: deskgate_bim.clash:run
  requirements: requirements.txt  # environnement uv dédié
# cli:
#   executable: "C:/Program Files/Outil/outil.exe"
#   args: ["--input", "{ifc}", "--out", "{work_dir}/result.json"]
# mcp:
#   server: nom                     # référence vers mcp_servers.toml
#   tool: outil

input_schema:  { ... }            # JSON Schema : validation, champs du nœud n8n, formulaire de test
output_schema: { ... }
timeout: 3600
resource: cpu-heavy               # gui-session | cpu-heavy | light
requires_session: false           # true : la session Windows doit être ouverte et déverrouillée
spawns_com: false                 # true : le plugin pilote un logiciel par COM (voir §4)
requires:
  - { type: python, version: ">=3.11" }
idempotent: true
```

En v0.1, les capacités sont déclarées dans `runner.toml` (`[capabilities.<id>]` : `kind`, `python`,
`entry`, `timeout_max`, `resource`), validées par Pydantic ; le cœur ne contient aucun nom BIM. Le
format `plugin.yaml` arrive en v0.2.

## 6. Protocole HTTP

Toutes les routes sauf `/health` exigent `Authorization: Bearer <jeton>`. OpenAPI non publiée en v0.1
(`openapi_url=None`).

| Méthode | Route | Rôle | v0.1 |
|---|---|---|---|
| GET | `/health` | État du runner, sans détail sensible | livré |
| GET | `/capabilities` | Plugins autorisés pour ce jeton, schémas et disponibilité | cible v0.2 |
| GET | `/capabilities/{id}` | Détail d'un plugin | cible v0.2 |
| POST | `/jobs` | Soumettre une tâche → `202 { job_id, status: "queued" }` | livré |
| GET | `/jobs/{id}` | État, progression, résumé, données, artefacts | livré |
| GET | `/jobs/{id}/logs` | Journaux de la tâche | livré |
| POST | `/jobs/{id}/cancel` | Annulation | livré |
| GET | `/jobs/{id}/artifacts/{name}` | Téléchargement d'un artefact | cible (non planifiée) |

```json
POST /jobs
{ "capability": "ifc.clash",
  "params": { "ifc_a": "/data/depot/CVC_S42.ifc", "selector_a": "IfcFlowSegment" },
  "callback": { "url": "http://host.docker.internal:5678/webhook-waiting/123?signature=…" },
  "idempotency_key": "...",
  "timeout": 1800 }
```

`callback.url` reçoit `{{ $execution.resumeUrl }}` tel quel ; `callback` n'accepte que `url` (toute autre clé :
422). En-têtes personnalisés du rappel (`callback.headers`) : cible (non planifiée).

### Rappel

```json
{ "job_id": "a1b2c3d4", "capability": "ifc.clash", "status": "succeeded",
  "duration_s": 742, "summary": {}, "data": {}, "artifacts": [], "error": null }
```

- `status` ∈ `succeeded | failed | timeout | cancelled | interrupted`.
- L'URL de reprise n8n porte un jeton `?signature=…` : le runner l'appelle **telle quelle**, sans
  jamais la reconstruire (sinon 401), et la **masque** dans l'audit et les journaux.
- n8n accepte 16 Mio par défaut (`N8N_PAYLOAD_SIZE_MAX`). Le runner plafonne le rappel à **1 Mio** : au-delà,
  `data` est écrit dans `data.json` du dossier de la tâche et la clé vaut `{"path": "…/data.json", "truncated": true}` ;
  si le corps dépasse encore, `summary` suit le même chemin (`summary.json`). Après un 413, le renvoi minimal remplace
  `summary` et `data` par `{"truncated": true}`, sauf une valeur déjà réduite à un marqueur de repli, transmise telle
  quelle : n8n garde le chemin de `data.json` / `summary.json`.
- Marqueurs `truncated` : `{"path": "…", "truncated": true}` (fichier `data.json` ou `summary.json` écrit par l'engine) ;
  `{"truncated": true, "artifact": "mcp_result"}` (réponse `mcp.call`, chemin dans `artifacts`) ;
  `{"truncated": true, "error": "data_write_failed"}` ou `"summary_write_failed"` (écriture impossible, rien à lire) ;
  `{"truncated": true}` seul (renvoi minimal d'une valeur non déportée : lire `GET /jobs/{id}`).
- Une erreur propre à un rappel (corps illisible…) est un essai en échec de cette ligne (`internal_error`) : elle ne
  bloque pas les autres rappels.
- Rétention : `deskgate purge --older-than-days N` remplace `data` par `{"purged": true}` pour les tâches au rappel
  final ; le fichier de base ne rétrécit pas.
- Réessais avec délai croissant si n8n ne répond pas ; abandon tracé dans l'audit.

## 7. Chemins et dossier partagé

```toml
[paths]
allowed_roots = ["C:/BIM"]
[[paths.mapping]]
container = "/data"
host = "C:/BIM"
```

Conversion `/data/...` ↔ `C:/BIM/...` dans les deux sens (entrées et artefacts). Tout chemin hors
des racines est refusé, y compris via `..`, liens symboliques ou jonctions. On transmet des chemins,
jamais les fichiers.

Exécuteur `mcp` : seuls les arguments de premier niveau déclarés dans
`[mcp_servers.<nom>].path_arguments` (par outil) sont convertis et validés, à la soumission (422) et
au lancement ; les autres arguments sont transmis tels quels, sans heuristique. N'autorisez pas un
outil de fichiers sans déclarer ses arguments de chemin. Une fois le chemin validé, le serveur MCP
reçoit un chemin hôte absolu ; un lien créé ensuite sous la racine reste hors de portée du runner
(même limite que pour les plugins).

## 8. Sécurité (un runner par PC)

- Écoute locale, jeton obligatoire, **jetons par client** stockés hachés, chacun avec la liste des
  plugins autorisés et des quotas éventuels (cible v0.2 ; v0.1 : un jeton, client `bearer`).
- **Journal d'audit** : client, plugin, paramètres (sans secrets ni signature de rappel), début,
  fin, statut, durée, refus.
- **Aucune commande libre** : seules les capacités déclarées sont appelables.
- Secrets : en v0.1, les valeurs `env` d'un serveur MCP sont lues dans `runner.toml` et passées au worker par
  variables d'environnement (`DESKGATE_MCPENV__<SERVEUR>__<CLÉ>`), jamais par `input.json`, les journaux ni
  l'audit. Gestionnaire d'identifiants Windows (`keyring`) pour les secrets des plugins : cible v0.2.
- Un plugin s'installe uniquement sur action explicite (`deskgate plugin add`, cible v0.2).

## 9. Intégration n8n

- **Version épinglée : `n8nio/n8n:2.43.8`** (digest noté dans le rapport de vérifications).
  Le compose du dépôt (`n8n/docker-compose.yml`) épingle n8n 2.43.8 et Postgres par digest, publie
  `127.0.0.1:5679`, monte le dossier partagé sur `/data` et fixe `N8N_WEBHOOK_URL`.
- **v0.1** : nœuds natifs `HTTP Request` (POST `/jobs`, `callback.url = {{$execution.resumeUrl}}`)
  puis `Wait` (« On Webhook Call »). Exemple `n8n/examples/ifc-clash.json` : déclencheurs manuel et
  webhook, nœud If sur `$json.body?.status` ; à l'échéance du Wait, n8n continue avec l'item d'entrée
  (sans `body`), qui prend la branche « Echec ou delai ».
- **v0.3** : nœud communautaire `n8n-nodes-deskgate`, **un seul nœud** qui soumet et attend : un
  nœud communautaire peut se mettre en attente comme `Wait` (webhook `restartWebhook: true`,
  `putExecutionToWait`, méthode `webhook()`), vérifié dans le code de n8n 2.43.8. Liste des
  capacités chargée depuis `/capabilities` (cible v0.3), champs générés depuis `input_schema`, sortie = JSON du
  rappel.

## 10. Interface locale (v0.3)

Servie par le runner sur `http://127.0.0.1:8765/ui` (cible v0.3), en français : catalogue par type puis par
catégorie, statut et prérequis, bouton **Tester** ; tâches, progression, journaux, artefacts ;
jetons et droits ; audit ; diagnostic (`deskgate doctor`).

## 11. Plugins BIM (`deskgate-bim`)

Écrits **de zéro, dans ce dépôt, en parallèle du runner**, sur les bibliothèques IfcOpenShell
existantes (LGPL-3, utilisées comme bibliothèques), dans un paquet séparé (MIT, sauf `deskgate-bcf`) : le cœur `deskgate`
n'importe jamais `deskgate_bim` et ne connaît rien au BIM.

| Plugin | Type | Ressource | Base | Arrivée |
|---|---|---|---|---|
| `ifc.clash` | python | cpu-heavy | `ifcclash` (détection) + `deskgate-bcf` en sous-processus | v0.1 (en dur), v0.2 (manifeste) |
| `ifc.audit` | python | cpu-heavy | `ifctester` (IDS) | v0.2 |
| `ifc.diff` | python | cpu-heavy | `ifcdiff` | v0.2 |
| `ifc.quantities` | python | cpu-heavy | `ifc5d.qto`, `ifcopenshell.util.shape` | v0.2 |
| `ifc.validate` | python | light | `ifcopenshell.validate` (conformité au schéma) | v0.2 |
| `ifc.info` | python | light | `ifcopenshell.util` (`selector`, `element`, `pset`) : en-tête, inventaire, propriétés | v0.2 |
| `ifc.patch` | python | cpu-heavy | `ifcpatch` (recette en paramètre, liste blanche) | v0.3 |
| `ifc.convert` | cli | cpu-heavy | IfcConvert (exécutable) : glTF, OBJ, SVG, STEP… | v0.3 |
| `ifc.table` | python | light | `ifccsv` (export / réimport CSV, XLSX, ODS) | v0.3 |
| `ifc.draw`, `ifc.cost`, `ifc.fm`, `ifc.4d`, `ifc.sql` | python | — | `ifcopenshell.draw`, `ifc5d`, `ifcfm`, `ifc4d`, `ifcpatch` (Ifc2Sql) | backlog |
| `odm.audit_loi` | à définir | — | ODM | backlog, après une version fonctionnelle |

Écartés : Bonsai, ifcsverchok, intégration Blender (GPL, extensions Blender).

IfcOpenShell 0.9.0.post1 dispose de roues Windows pour Python 3.10 à 3.15 ; installation et import
vérifiés avec `uv` en 3.11 et 3.14.

### Module BCF (`deskgate-bcf`, sous GPL-3)

La bibliothèque BCF de l'écosystème, `bcf-client`, est sous **GPL-3**. On l'utilise telle quelle, et
**seul le module qui l'importe est sous GPL-3** :

- paquet séparé `plugins/bim/bcf/` (`deskgate-bcf`), avec son propre `LICENSE` GPL-3 ; il importe
  `bcf-client` (BCF 2.1 et 3.0 : sujets, commentaires, points de vue, captures, extensions) ;
- il est exposé comme **programme en ligne de commande** `deskgate-bcf` : il reçoit un fichier JSON
  (sujets, GUID, caméras, couleurs) et écrit le `.bcf` (v0.1 : sous-commande `write` seule) ; lire un `.bcf` et
  rendre du JSON : cible v0.2 ;
- les plugins MIT (`ifc.clash`, `ifc.audit`) **ne l'importent jamais** : ils l'appellent en
  sous-processus, avec des fichiers JSON comme seul échange. Deux programmes distincts, chacun sous
  sa licence ;
- il est aussi déclaré comme plugin `bcf.write` / `bcf.read` (type `cli`, cible v0.2), ce qui permet de
  produire ou relire un BCF depuis n8n et sert de cas de test de l'exécuteur `cli`.

Le runner (`deskgate`) et les autres plugins restent MIT. L'export BCF intégré d'`ifcclash` (qui
importe `bcf-client`) n'est utilisé que depuis `deskgate-bcf`.

Conventions héritées du projet d'origine, appliquées par défaut par `ifc.clash` : deux points de vue
par sujet, (1) objets du conflit seuls, (2) contexte gris transparent ; pas de sélection
enregistrée ; couleurs ARGB.

## 12. Structure du dépôt

```
deskgate/
├─ AGENTS.md  CLAUDE.md  README.md  ARCHITECTURE.md  ROADMAP.md  CHANGELOG.md  LICENSE
├─ pyproject.toml               paquet deskgate
├─ src/
│  ├─ deskgate/
│  │  ├─ store.py  engine.py  sender.py  jobs.py  jobobject.py  scheduler.py
│  │  ├─ runtime.py  supervisor.py  instance.py  installer.py  doctor.py  locations.py
│  │  ├─ cli.py        deskgate init | serve | doctor | task … | purge
│  │  ├─ api/          routes FastAPI (/health, /jobs)
│  │  ├─ core/         configuration, protocole worker, corps du rappel, chemins
│  │  └─ workers/      processus de travail des types python et mcp
│  └─ deskgate_sdk/    SDK des plugins python (contexte, résultat)
├─ plugins/
│  └─ bim/          paquet deskgate-bim (MIT, pyproject propre) + un dossier par plugin
│     └─ bcf/       paquet deskgate-bcf (GPL-3, LICENSE propre), CLI deskgate-bcf
├─ n8n/
│  ├─ docker-compose.yml   n8n 2.43.8 épinglé + Postgres + montage C:\BIM
│  └─ examples/     workflows à importer
├─ docs/            contrats et cadrage d'origine (docs/passation/)
└─ tests/
```

Cible : `n8n/node/` (`n8n-nodes-deskgate`, cible v0.3), `plugins/examples/` (cible v0.4).

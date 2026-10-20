# Architecture de Deskgate

Deskgate est une **passerelle locale** entre un orchestrateur (n8n en priorité) et les outils
lourds d'un PC Windows : calculs longs (IfcOpenShell), logiciels installés, serveurs MCP en stdio.
n8n soumet une tâche, Deskgate l'exécute dans la session Windows de l'utilisateur, puis rappelle
n8n avec le résultat.

Ce document est la référence technique. Les décisions de fond et leur justification sont dans
[`docs/passation/02-DECISIONS.md`](docs/passation/02-DECISIONS.md) ; les vérifications qui fondent
les choix ci-dessous sont dans [`.arthemis/reports/`](.arthemis/reports/).

## 0. Périmètre

| Dans ce dépôt | Hors de ce dépôt (projet d'intégration) |
|---|---|
| Le runner (API, file, exécuteurs, sécurité, interface locale) | Les workflows n8n complets (coordination, audit, évolution) |
| Le nœud communautaire `n8n-nodes-deskgate` | Ingestion, registre des maquettes, base et déduplication des conflits |
| Les plugins BIM `deskgate-bim` (calcul et logiciels) | Tri et synthèse par IA, Hermes Agent, superviseur, tableau de bord |
| Des plugins d'exemple (Python, CLI, MCP) et des workflows n8n de démonstration | Toute exposition de Deskgate comme serveur MCP |

Deskgate **ne planifie pas et n'enchaîne pas** : pas de DAG, pas de déclencheur, pas de reprise
d'étapes. Une tâche = un appel d'un plugin. L'enchaînement est le rôle de n8n.

## 1. Vue d'ensemble

```
┌──────────── Docker Desktop (WSL2) ─────────────┐
│  n8n 2.43.8 (+ nœud n8n-nodes-deskgate)        │
│  Postgres                                      │
└───────────────┬───────────────▲────────────────┘
   POST /jobs   │               │ rappel : POST resumeUrl (signée)
   http://host.docker.internal:8765
┌───────────────▼───────────────┴──── Windows natif, session utilisateur ───┐
│  Deskgate (Python ≥ 3.11)                                                 │
│   ├─ API HTTP (FastAPI)  : /health /capabilities /jobs /artifacts         │
│   ├─ Interface web       : /ui (catalogue, tâches, jetons, audit)         │
│   ├─ File de tâches      : SQLite, ordonnanceur par ressource             │
│   ├─ Exécuteurs          : python │ cli │ mcp   (sous-processus + Job Object)│
│   ├─ Registre de plugins : manifestes plugin.yaml + environnements uv     │
│   └─ Sécurité            : jetons hachés, droits par plugin, audit, chemins│
│                                                                           │
│  Plugins (dossiers séparés, un environnement uv chacun)                    │
│   ifc.clash  ifc.audit  ifc.diff  ifc.quantities  zoom.nightshift  …      │
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
- **Persistance SQLite** (mode WAL) : tâches, journaux de tâche, audit, jetons hachés, état des
  plugins. Au redémarrage, les tâches `running` passent `interrupted` et leur rappel est envoyé.
- **Démarrage** : tâche du Planificateur de tâches Windows à l'ouverture de session, installée par
  `deskgate init`. Pas de service Windows : un service ne voit pas le bureau et ne peut pas piloter
  de logiciel graphique.
- **Configuration** : `runner.toml` (port, racines autorisées, correspondance des chemins,
  concurrence par ressource, dossier des plugins, jetons en v0.1).

## 3. File de tâches et ordonnancement

File **écrite pour Deskgate** au-dessus de SQLite, pas de bibliothèque de file : aucune ne gère à la
fois la concurrence par ressource, l'état `interrupted`, l'annulation et l'idempotence par clé, et
celles qui ont un mode multi-processus sont fragiles sous Windows (rapport de l'existant). Huey
reste le plan B.

- Cycle de vie : `queued → running → succeeded | failed | timeout | cancelled | interrupted`.
- Chaque plugin déclare une **ressource** ; chaque ressource a une **concurrence maximale** :
  `gui-session` = 1, `cpu-heavy` = 1 (défaut), `light` = N.
- **Idempotence** : si une tâche réussie a la même `idempotency_key`, son résultat est renvoyé
  sans recalcul (désactivable par le client).
- Plafond de mémoire et de threads transmis aux plugins par variables d'environnement.

## 4. Exécution des plugins

### Trois types

| Type | Ce que le runner exécute |
|---|---|
| `python` | `module:fonction(params, ctx) -> dict`, dans l'environnement uv du plugin, **dans un sous-processus** (jamais dans le processus du runner) |
| `cli` | Un exécutable et un **gabarit d'arguments déclaré** ; pas de shell, pas de concaténation libre |
| `mcp` | Un outil d'un serveur MCP (stdio lancé par le runner, ou Streamable HTTP), appelé avec le SDK `mcp` officiel, sans LLM |

### Isolation et arrêt

- Chaque tâche tourne dans un **Job Object Windows** : processus créé suspendu
  (`CREATE_SUSPENDED`), assigné au job, puis repris. La sortie du job (`breakaway`) n'est jamais
  autorisée. Au délai maximum ou à l'annulation, `TerminateJobObject` tue tout l'arbre, y compris
  les petits-enfants orphelins que `psutil` ne voit pas.
- Limite connue : un logiciel lancé via COM (Revit, Excel) n'appartient pas au job. Un plugin qui
  pilote un logiciel par COM doit le fermer lui-même et le déclarer dans son manifeste.
- Chaque tâche a un `work_dir` : `C:/BIM/travail/<job_id>/`.

### Contexte passé au plugin (`ctx`)

`job_id`, `work_dir`, `log(msg)`, `progress(pct, msg)`, `artifact(path, kind)`, `cancelled()`.
Les chemins reçus sont déjà convertis au format Windows et validés contre les racines autorisées.

### Sortie d'un plugin

```json
{ "summary":   { "...": "petit résumé lisible" },
  "data":      { "...": "conforme à output_schema" },
  "artifacts": [ { "kind": "bcf", "path": "C:/BIM/travail/a1b2/conflits.bcf" } ] }
```

## 5. Manifeste `plugin.yaml` (v0.2)

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

En v0.1, les capacités sont codées en dur ; le format de manifeste arrive en v0.2.

## 6. Protocole HTTP

Toutes les routes sauf `/health` exigent `Authorization: Bearer <jeton>`. OpenAPI générée.

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/health` | État du runner, sans détail sensible |
| GET | `/capabilities` | Plugins autorisés pour ce jeton, schémas et disponibilité |
| GET | `/capabilities/{id}` | Détail d'un plugin |
| POST | `/jobs` | Soumettre une tâche → `202 { job_id, status: "queued" }` |
| GET | `/jobs/{id}` | État, progression, résumé, artefacts |
| GET | `/jobs/{id}/logs` | Journaux de la tâche |
| POST | `/jobs/{id}/cancel` | Annulation |
| GET | `/jobs/{id}/artifacts/{name}` | Téléchargement d'un artefact |

```json
POST /jobs
{ "capability": "ifc.clash",
  "params": { "ifc_a": "/data/depot/CVC_S42.ifc", "selector_a": "IfcFlowSegment" },
  "callback": { "url": "<resumeUrl n8n>", "headers": {} },
  "idempotency_key": "...",
  "timeout": 1800 }
```

### Rappel

```json
{ "job_id": "a1b2c3d4", "capability": "ifc.clash", "status": "succeeded",
  "duration_s": 742, "summary": {}, "artifacts": [], "error": null }
```

- `status` ∈ `succeeded | failed | timeout | cancelled | interrupted`.
- L'URL de reprise n8n porte un jeton `?signature=…` : le runner l'appelle **telle quelle**, sans
  jamais la reconstruire (sinon 401), et la **masque** dans l'audit et les journaux.
- n8n accepte 16 Mio par défaut (`N8N_PAYLOAD_SIZE_MAX`). Le runner plafonne le rappel à **1 Mio** ;
  au-delà, `summary` est écrit dans `summary.json` et le rappel ne porte que son chemin.
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

## 8. Sécurité (un runner par PC)

- Écoute locale, jeton obligatoire, **jetons par client** stockés hachés, chacun avec la liste des
  plugins autorisés (v0.2) et des quotas éventuels.
- **Journal d'audit** : client, plugin, paramètres (sans secrets ni signature de rappel), début,
  fin, statut, durée, refus.
- **Aucune commande libre** : seules les capacités déclarées sont appelables.
- Secrets des plugins dans le gestionnaire d'identifiants Windows ou des variables
  d'environnement, jamais dans les manifestes ni les journaux.
- Un plugin s'installe uniquement sur action explicite (`deskgate plugin add`).

## 9. Intégration n8n

- **Version épinglée : `n8nio/n8n:2.43.8`** (digest noté dans le rapport de vérifications).
- **v0.1** : nœuds natifs `HTTP Request` (POST `/jobs`, `callback.url = {{$execution.resumeUrl}}`)
  puis `Wait` (« On Webhook Call »). Workflows d'exemple fournis.
- **v0.3** : nœud communautaire `n8n-nodes-deskgate`, **un seul nœud** qui soumet et attend : un
  nœud communautaire peut se mettre en attente comme `Wait` (webhook `restartWebhook: true`,
  `putExecutionToWait`, méthode `webhook()`), vérifié dans le code de n8n 2.43.8. Liste des
  capacités chargée depuis `/capabilities`, champs générés depuis `input_schema`, sortie = JSON du
  rappel.

## 10. Interface locale (v0.3)

Servie par le runner sur `http://127.0.0.1:8765/ui`, en français : catalogue par type puis par
catégorie, statut et prérequis, bouton **Tester** ; tâches, progression, journaux, artefacts ;
jetons et droits ; audit ; diagnostic (`deskgate doctor`).

## 11. Plugins BIM (`deskgate-bim`)

Développés **dans ce dépôt, en parallèle du runner**, mais dans un paquet séparé : le cœur
`deskgate` n'importe jamais `deskgate_bim` et ne connaît rien au BIM.

| Plugin | Type | Base | Arrivée |
|---|---|---|---|
| `ifc.clash` | python | IfcOpenShell (détection, regroupement, BCF 2.1) | v0.1 (en dur), v0.2 (manifeste) |
| `ifc.audit` | python | IfcOpenShell + `ifctester` (IDS) | v0.2 |
| `ifc.diff` | python | `ifcdiff` | v0.2 |
| `ifc.quantities` | python | IfcOpenShell (géométrie, quantités) | v0.2 |
| `zoom.nightshift` | cli | BIMcollab Zoom Nightshift (`requires_session`) | v0.3 |
| `odm.audit_loi` | à définir | ODM | backlog, après une version fonctionnelle |

IfcOpenShell 0.9.0.post1 dispose de roues Windows pour Python 3.10 à 3.15 ; installation et import
vérifiés avec `uv` en 3.11 et 3.14.

## 12. Structure du dépôt

```
deskgate/
├─ AGENTS.md  CLAUDE.md  README.md  ARCHITECTURE.md  ROADMAP.md  LICENSE
├─ pyproject.toml               paquet deskgate
├─ src/deskgate/
│  ├─ api/          routes FastAPI
│  ├─ queue/        file SQLite, ordonnanceur par ressource
│  ├─ executors/    python.py  cli.py  mcp.py  jobobject.py
│  ├─ plugins/      registre, manifeste, environnements uv, doctor
│  ├─ security/     jetons, droits, audit, chemins
│  ├─ ui/           interface web (v0.3)
│  └─ cli.py        deskgate init | serve | doctor | plugin … | token …
├─ plugins/
│  ├─ examples/     plugins minimaux python, cli, mcp
│  └─ bim/          paquet deskgate-bim (pyproject propre) + un dossier par plugin
├─ n8n/
│  ├─ docker-compose.yml   n8n 2.43.8 épinglé + Postgres + montage C:\BIM
│  ├─ examples/     workflows à importer
│  └─ node/         n8n-nodes-deskgate (v0.3)
├─ docs/passation/  cadrage d'origine
└─ tests/
```

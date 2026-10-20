# 03 — Architecture

Conception issue du cadrage. C'est une base de travail : les détails (noms de routes, champs)
peuvent évoluer pendant la v0.1, les principes non (voir `02-DECISIONS.md`).

## Vue d'ensemble

```
┌──────────── Docker (Linux / WSL2) ─────────────┐
│  n8n  (+ nœud communautaire « Deskgate »)      │      Hermes Agent / Claude
│  Postgres                                      │            │ (MCP, v0.4)
└───────────────┬────────────────────────────────┘            │
                │ HTTP  http://host.docker.internal:8765      │
┌───────────────▼──── Windows natif, session utilisateur ─────▼──────────┐
│  Deskgate                                                              │
│   ├─ API HTTP (FastAPI)  : /capabilities, /jobs, /artifacts, /health    │
│   ├─ Interface web       : catalogue, tâches, journaux, jetons          │
│   ├─ File de tâches      : SQLite persistante, ordonnanceur par ressource│
│   ├─ Exécuteurs          : python │ cli │ mcp                            │
│   ├─ Registre de plugins : manifestes + environnements uv isolés        │
│   └─ Sécurité            : jetons, droits par plugin, journal d'audit   │
│                                                                        │
│  Plugins (paquets séparés)  → IfcOpenShell, ODM, Zoom, Revit…          │
└────────────────────────────────────────────────────────────────────────┘
          Dossier partagé :  C:\BIM\   ⇄   /data  (dans les conteneurs)
```

## 1. Le runner

- **Langage** : Python ≥ 3.11 (même écosystème que les plugins BIM).
- **API** : FastAPI + Uvicorn, écoute **par défaut sur `127.0.0.1`**. Pour que Docker le joigne,
  écouter aussi sur l'interface utilisée par `host.docker.internal` (à vérifier sur Docker
  Desktop / WSL2, voir points ouverts), **jamais sur `0.0.0.0` sans avertissement explicite**.
- **Persistance** : SQLite (tâches, journal d'audit, jetons hachés, état des plugins).
  Au redémarrage : les tâches `running` deviennent `interrupted`, et un rappel d'erreur est
  envoyé à n8n.
- **Démarrage** : Planificateur de tâches Windows, à l'ouverture de session (installé par
  `deskgate init`).
- **Configuration** : un fichier `runner.toml` (port, racines de chemins autorisées,
  correspondance des chemins, limites de ressources, dossier des plugins).

## 2. Les plugins

### Trois types

| Type | Ce que le runner exécute | Exemple |
|---|---|---|
| `python` | Une fonction `module:fonction(params, ctx) -> dict`, dans l'environnement isolé du plugin, **dans un sous-processus** (jamais dans le processus du runner) | `ifc.clash` (moteur `bim-assistant`) |
| `cli` | Un exécutable avec des arguments construits à partir d'un **gabarit déclaré** (pas de shell, pas de concaténation libre) | un convertisseur, un script PowerShell déclaré |
| `mcp` | Un outil d'un serveur MCP (stdio lancé par le runner, ou HTTP), appelé sans LLM | `odm.audit_loi` |

### Manifeste (`plugin.yaml`) — proposition

```yaml
id: ifc.clash                     # identifiant unique, espace de noms par point
version: 0.1.0
title: Détection de conflits IFC
description: Détection IfcOpenShell entre deux sélections, regroupement, BCF 2.1 optionnel
kind: python                      # python | cli | mcp
category: BIM / Coordination      # pour le classement dans l'interface

python:
  entry: bim_plugins.clash:run
  requirements: requirements.txt  # environnement uv dédié

# cli:
#   executable: "C:/Program Files/Outil/outil.exe"
#   args: ["--input", "{ifc}", "--out", "{work_dir}/result.json"]
# mcp:
#   server: odm                     # référence vers mcp_servers.toml
#   tool: audit_loi

input_schema:                     # JSON Schema → validation + formulaire n8n + interface
  type: object
  required: [ifc_a, selector_a]
  properties:
    ifc_a:      { type: string, format: path }
    selector_a: { type: string }
    ifc_b:      { type: string, format: path }
    selector_b: { type: string }
    mode:       { type: string, enum: [hard, clearance, touch, duplicate], default: hard }
    bcf:        { type: boolean, default: false }

output_schema: { ... }            # forme du result.json

timeout: 3600                     # secondes, tâche tuée au-delà (arbre de processus)
resource: cpu-heavy               # file de concurrence (voir §4)
requires_session: false           # true = a besoin de la session Windows ouverte (GUI)
requires:                         # vérifiés par `deskgate doctor`
  - { type: python, version: ">=3.11" }
  # - { type: executable, path: "C:/Program Files/ODM/odm.exe", version: ">=2.1" }
idempotent: true                  # autorise la réutilisation d'un résultat (clé d'idempotence)
```

### Contexte passé au plugin (`ctx`)

- `job_id`, `work_dir` (dossier de travail propre à la tâche), `log(msg)`,
  `progress(pct, msg)`, `artifact(path, kind)` pour déclarer un fichier produit,
  `cancelled()` pour vérifier une annulation.
- Les chemins reçus sont **déjà convertis** au format Windows et **validés** contre les racines
  autorisées.

### Sortie d'un plugin

```json
{ "summary": { "...": "petit résumé lisible" },
  "data":    { "...": "conforme à output_schema" },
  "artifacts": [ { "kind": "bcf", "path": "C:/BIM/travail/a1b2/conflits.bcf" } ] }
```
Gros résultats → fichier artefact ; le JSON de rappel reste petit.

### Registre et environnements

- `deskgate plugin add <git|dossier>` : copie ou clone, lit le manifeste, crée l'environnement uv
  (`uv venv` + installation des dépendances), vérifie les prérequis.
- Un plugin dont un prérequis manque est **indisponible**, avec la raison affichée ; il
  n'apparaît pas comme utilisable dans n8n.
- Serveurs MCP déclarés dans `mcp_servers.toml`, au même format que la configuration MCP de
  Claude (`command`, `args`, `env`, ou `url`).

## 3. Protocole de tâches (API HTTP)

Toutes les routes exigent `Authorization: Bearer <jeton>`. Documentation OpenAPI générée.

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/health` | État du runner (sans jeton, sans détail sensible) |
| GET | `/capabilities` | Plugins **autorisés pour ce jeton**, avec schémas et disponibilité |
| GET | `/capabilities/{id}` | Détail d'un plugin |
| POST | `/jobs` | Soumettre une tâche → `202 { job_id, status: "queued" }` |
| GET | `/jobs/{id}` | État, progression, résumé, artefacts |
| GET | `/jobs/{id}/logs` | Journaux de la tâche |
| POST | `/jobs/{id}/cancel` | Annulation |
| GET | `/jobs/{id}/artifacts/{name}` | Télécharger un artefact (si le client ne voit pas le dossier partagé) |

Corps de `POST /jobs` :
```json
{ "capability": "ifc.clash",
  "params": { "ifc_a": "/data/depot/CVC_S42.ifc", "selector_a": "IfcFlowSegment", "...": "..." },
  "callback": { "url": "<resumeUrl n8n>", "headers": { } },
  "idempotency_key": "sha256-du-fichier+capability+params",
  "timeout": 1800 }
```

Corps du rappel (vers l'URL de reprise) :
```json
{ "job_id": "a1b2c3d4", "capability": "ifc.clash", "status": "succeeded",
  "duration_s": 742, "summary": { }, "artifacts": [ ], "error": null }
```
`status` ∈ `succeeded | failed | timeout | cancelled | interrupted`. Le rappel est **réessayé**
(avec délai croissant) si n8n ne répond pas.

Cycle de vie : `queued → running → succeeded | failed | timeout | cancelled | interrupted`.

## 4. Ordonnancement et ressources

- Chaque plugin déclare une **ressource** ; chaque ressource a une **concurrence maximale**
  configurée dans `runner.toml` :
  - `gui-session` : **1** (un seul pilotage de logiciel à la fois — Zoom, Revit, ODM graphique) ;
  - `cpu-heavy` : 1 par défaut (calculs IFC, mémoire) ;
  - `light` : N (appels courts).
- Plafond mémoire / nombre de threads transmis aux plugins (ex. variable d'environnement).
- **Idempotence** : si une tâche réussie avec la même clé existe, on renvoie son résultat
  au lieu de recalculer (désactivable par le client).

## 5. Chemins et dossier partagé

- `runner.toml` déclare les **racines autorisées** et la **correspondance** :
  ```toml
  [paths]
  allowed_roots = ["C:/BIM"]
  [[paths.mapping]]
  container = "/data"
  host = "C:/BIM"
  ```
- Le runner convertit `/data/...` ↔ `C:/BIM/...` dans les deux sens (entrées et artefacts
  renvoyés), et **refuse tout chemin hors des racines** (y compris via `..` ou liens).
- Chaque tâche a son `work_dir` : `C:/BIM/travail/<job_id>/`.

## 6. Sécurité (modèle : un runner par PC)

- Écoute locale uniquement ; refus de démarrer sur une interface publique sans option explicite.
- **Jetons par client**, stockés hachés ; chaque jeton a la **liste des plugins autorisés**
  (et éventuellement des quotas).
- **Journal d'audit** : client, plugin, paramètres (sans secrets), début, fin, statut, durée.
- **Pas de commande libre** : `cli` n'exécute que l'exécutable et le gabarit d'arguments du
  manifeste, sans shell.
- Secrets des plugins (clés d'API, mots de passe) dans le gestionnaire d'identifiants Windows
  ou des variables d'environnement, jamais dans les manifestes ni les journaux.
- Un plugin s'installe uniquement sur action explicite de l'utilisateur (`deskgate plugin add`).

## 7. Intégration n8n

### v0.1 (sans nœud dédié)
`HTTP Request` (POST `/jobs`, `callback.url = {{$execution.resumeUrl}}`) → `Wait`
(« On Webhook Call »). Fournir des workflows d'exemple à importer.

### v0.3 — nœud communautaire `n8n-nodes-deskgate`
- Identifiants : URL du runner + jeton.
- Champ « Capacité » : liste chargée dynamiquement (`/capabilities`), groupée par type.
- Champs de paramètres générés depuis `input_schema` (piste : *resource mapper* de n8n).
- Comportement : soumettre puis **attendre le rappel**. À vérifier : un nœud communautaire
  peut-il mettre l'exécution en attente comme le nœud *Wait* (`putExecutionToWait`) et recevoir
  le webhook ? Sinon : nœud « Soumettre » + nœud *Wait* préconfiguré, ou attente active par
  `GET /jobs/{id}` (moins bon).
- Sortie du nœud : le JSON de rappel (`summary`, `artifacts`…), pour enchaîner les nœuds.

## 8. Exposition MCP (v0.4)

Le runner expose aussi ses capacités comme **outils MCP** (HTTP) : Hermes ou Claude peuvent
appeler un plugin sans passer par n8n. Mêmes jetons, mêmes droits, même journal. Pour les tâches
longues : outil `submit` + outil `status`, ou notifications de progression MCP.

## 9. Interface visuelle

Servie par le runner (`http://127.0.0.1:8765/ui`), en français :
- **Catalogue** : plugins groupés par type (Python / CLI / MCP) puis par catégorie ; statut,
  version, prérequis, schéma ; bouton **Tester** (formulaire généré depuis le schéma).
- **Tâches** : en file, en cours, terminées ; progression, journaux, artefacts, relance.
- **Clients et droits** : création/révocation de jetons, plugins autorisés par jeton, quotas.
- **Audit** : historique filtrable.
- **Diagnostic** : résultat de `deskgate doctor`.

## 10. Structure de dépôt proposée

```
deskgate/
├─ AGENTS.md / CLAUDE.md        procédure d'installation pour une IA + règles du dépôt
├─ README.md                    installation humaine en 3 commandes
├─ ARCHITECTURE.md  ROADMAP.md
├─ src/deskgate/
│  ├─ api/          routes FastAPI
│  ├─ queue/        file SQLite, ordonnanceur par ressource
│  ├─ executors/    python.py  cli.py  mcp.py
│  ├─ plugins/      registre, manifeste, environnements uv, doctor
│  ├─ security/     jetons, droits, audit, chemins
│  ├─ ui/           interface web
│  └─ cli.py        `deskgate init | doctor | plugin add | serve | token ...`
├─ n8n/
│  ├─ examples/     workflows à importer (HTTP Request + Wait)
│  └─ node/         n8n-nodes-deskgate (v0.3)
├─ examples/plugins/  plugin Python, CLI et MCP minimaux
└─ tests/
```

Plugins BIM dans un **dépôt séparé** (ex. `deskgate-bim`) : `ifc.clash`, `ifc.audit`,
`ifc.diff`, `ifc.quantities`, `odm.audit_loi`, `zoom.nightshift`…

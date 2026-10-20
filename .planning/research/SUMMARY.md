# Synthèse de la recherche projet

**Projet :** Deskgate
**Domaine :** passerelle locale Windows entre n8n (Docker Desktop) et des outils lourds (IfcOpenShell, CLI, MCP stdio)
**Recherché le :** 2026-10-20
**Confiance :** MOYENNE-HAUTE (versions PyPI du jour, code n8n 2.43.8 et `ifcclash` lus, Job Object testé ;
Planificateur de tâches, `CTRL_BREAK`, SDK `mcp` dans un Job Object non prouvés)

## Résumé exécutif

Runner Python mono-tenant dans la session Windows : `POST /jobs` → 202, exécution en sous-processus dans
un Job Object, rappel de la `resumeUrl` du Wait n8n. La valeur centrale (« n8n reprend fiablement quel
que soit le résultat ») repose sur deux mécanismes à concevoir dès le premier schéma : une **outbox de
rappels écrite dans la même transaction que l'état terminal**, et une **récupération au démarrage**
(`running` → `interrupted` + rappel).

Noyau sans import BIM, validé de bout en bout avec un faux plugin (sleep, petit-enfant orphelin) avant
d'y brancher `ifc.clash` et `mcp.call`. Worker et supervision en **threads** (Popen + Job Object),
asyncio pour le HTTP seulement ; pont API/worker uniquement par SQLite ; échange avec le processus
worker par fichiers (`input.json`, `events.jsonl`, `result.json`, sentinelle d'annulation, `job.log`).

Frontière de licence tranchée : `ifcclash` n'importe `bcf-client` que paresseusement et ne le déclare
pas ; `ifc.clash` (MIT) n'utilise que la détection et un JSON ; `deskgate-bcf` (GPL-3, sous-processus)
écrit tout le BCF.

## Pile recommandée (détail : STACK.md)

- Python ≥ 3.11 (dev/test 3.12 ou 3.13).
- FastAPI `>=0.151,<0.152`, Uvicorn `>=0.54,<0.55` sans extra `standard`, lancé par programme, un worker,
  sans reload, `loop="asyncio"`.
- Pydantic 2.14, `tomllib` + `model_validate` (ou pydantic-settings) pour `runner.toml`, `tomli-w`.
- `sqlite3` stdlib + threads, SQL brut, `PRAGMA user_version`, WAL, `synchronous=FULL`,
  `BEGIN IMMEDIATE`, une connexion par thread. Pas d'ORM ni d'`aiosqlite`.
- `ctypes` pour les Job Objects (pas `pywin32`).
- `httpx2` 2.15 (pas `httpx`, en sommeil) pour le rappel ; `follow_redirects=False`, `trust_env=False`.
- SDK `mcp` `>=2.3,<3` : API 2.x (`Client`, `MCPError`, snake_case) ; exemples 1.x obsolètes ; les
  « Tasks » MCP ont été retirées.
- Typer 0.27, platformdirs, uv 0.13 + hatchling (workspace), pytest + plugin anyio, ruff.
- `ifcopenshell==0.9.0.post1`, `ifcclash==0.9.0` ; `bcf-client==0.9.0` uniquement dans `deskgate-bcf`.
- Planificateur : `schtasks /Create /XML` (XML UTF-16 généré), pas de COM.

Licence de `bcf-client` contradictoire en amont (wheel GPL-3, en-têtes et commits LGPL-3+) : l'isolation
reste la règle, à réévaluer à la prochaine publication.

## Fonctionnalités (détail : FEATURES.md)

**v0.1 indispensables :** `POST/GET /jobs`, `/logs`, `/cancel` idempotent, `/health` ; états terminaux
`succeeded|failed|timeout|cancelled|interrupted` ; file SQLite (une tâche à la fois) ; délai + arbre tué ;
rappel au moins une fois, réessais durables, plafond de taille avec `summary.json`, rappel pour tous les
états terminaux ; chemins `/data` ↔ `C:/BIM` ; jeton haché ; audit minimal ; `deskgate init` + démarrage
à l'ouverture de session ; `ifc.clash` (`hard`, `clearance`, sélecteurs, tolérance, regroupement, JSON
avec GlobalId, BCF 2.1 à deux points de vue via `deskgate-bcf`) ; `mcp.call` stdio ; docker-compose n8n
2.43.8 + workflow d'exemple ; `idempotency_key` minimal (refus de doublon non terminal).

**Reporté :** v0.2 manifestes, exécuteurs `cli`/`python` en venv uv, ressources, jetons multiples,
idempotence complète, `doctor`, BCF 3.0 et lecture, téléchargement d'artefacts, modes `touch` /
`duplicate` ; v0.3 nœud n8n, `/ui` ; v0.4 `pipeline.lock`, publication.

**Anti-fonctionnalités :** DAG, planification, serveur MCP, `shell=True`, réessai automatique des tâches
échouées, poussée de progression vers n8n, téléversement HTTP d'IFC.

## Architecture (détail : ARCHITECTURE.md)

Un processus. `api` (routes `def` synchrones) écrit dans `store` ; threads `scheduler`, `supervisor` par
tâche, `callback-sender`, par transitions atomiques (`UPDATE ... WHERE status IN (...)` + `rowcount`).
Exécuteurs → `LaunchSpec` (argv, env en liste blanche, cwd) ; un seul code lance, surveille, tue.
Composants : `security` (jeton, contrôle `Host`, `paths`), `store` + `recovery`, `scheduler` +
`supervisor` + `jobobject`, `callback` (outbox), `executors` + `deskgate_sdk`, `plugins/bim` et
`plugins/bim/bcf` liés par un contrat JSON. Schéma v0.1 : `resource`, `idempotency_key` (index unique
partiel), tables `callbacks` et `audit`, `user_version`.

## Pièges critiques (détail : PITFALLS.md)

1. **Rappel avant la mise en attente du Wait (P1)** : 409 ambigu. Politique par réponse : 2xx livré ;
   401 abandon ; 409 « running/about to resume » réessai court ; 409 « finished » ou 404 terminal
   (`callback_stale`) ; 5xx/réseau réessai plafonné. Délai d'amorçage ~2 s ; test avec tâche < 100 ms.
2. **Résultat perdu sans outbox (P2)** : table `callbacks` dans la transaction terminale, reprise au
   démarrage, durée des réessais ≥ échéance du Wait.
3. **Deux instances (P3)** : bind du port puis verrou, `recovery` après le verrou.
4. **Planificateur et veille (P4, P5)** : `ExecutionTimeLimit=PT0S`, batterie, `IgnoreNew`, LogonTrigger
   interactif, `RunLevel` limité, relu par `doctor` ; délai en temps actif ; `SetThreadExecutionState`.
5. **Annulation (P7)** : coopérative par sentinelle ; `CTRL_BREAK` jamais requis ; `TerminateJobObject`
   en garde-fou ; sorties vers fichiers.
6. **Chemins et secrets (M12, M20, M21)** : tests d'attaque (`..`, jonction, UNC, `C:\BIM2`, `CON`, flux
   alternatif, préfixe de segment) ; filtre global de `signature=` dans les journaux ; hôtes de rappel
   autorisés.

## Implications pour la feuille de route (v0.1)

1. **Fondations testables** : squelette, `runner.toml`, `/health`, jeton + contrôle `Host` + refus hors
   loopback, `paths`, `jobobject`, `store` + machine d'états + `recovery`, verrou d'instance. Prérequis :
   test `host.docker.internal` et type de boucle Uvicorn.
2. **Cœur d'exécution** : scheduler, superviseur, exécuteur python minimal + `deskgate_sdk`, API des
   tâches, délai, annulation, idempotence minimale ; faux plugin ; test `taskkill /F` + redémarrage.
3. **Rappel fiable** : outbox, politique par code, amorçage, plafond + `summary.json`, masquage,
   hôtes autorisés ; faux serveur n8n local.
4. **Capacités** : `mcp.call` (worker dans le Job), `deskgate-bcf` (JSON → BCF 2.1), `ifc.clash` ; test
   CI d'imports (pas de `bcf` hors `plugins/bim/bcf/`), `NOTICE`.
5. **Installation et intégration n8n** : `deskgate init` (XML de tâche), environnement `ifc.clash`,
   docker-compose, workflow HTTP Request + Wait (Limit Wait Time + test de `status`) ; acceptation
   depuis la tâche planifiée.

Recherche de phase : phase 4 (mcp dans un Job, API bas niveau `bcf-client`, multiprocessing `ifcclash`),
phase 5 (Planificateur sans élévation, `gui-scripts` sous uv, sortie du Wait à l'échéance), phase 3
courte (textes 409, non-réencodage de la signature par `httpx2`).

## Contradictions tranchées

- Client HTTP : `httpx2`, jamais `httpx` en même temps.
- SQLite : `synchronous=FULL`.
- Accès SQLite : une connexion par thread, `BEGIN IMMEDIATE`, pas d'`aiosqlite`.
- Idempotence : minimum en v0.1 (index unique partiel, refus de doublon), complète en v0.2.
- Démarrage : XML `schtasks` principal, repli `HKCU\Run` documenté.
- Licence `ifcclash` : risque levé (import paresseux) ; reste le test CI d'imports et le `NOTICE`.

## Lacunes

`mcp.call` dans un Job Object (spike phase 4) ; Planificateur sans élévation (spike phase 5) ; sortie du
Wait à l'échéance ; réécriture d'hôte de `callback.url` (à trancher en phase 3 : hôte seulement, query
intacte) ; `duplicate` et GUID BCF déterministe (basse confiance, hors chemin critique) ; relecture
juridique de la frontière GPL avant distribution d'un binaire ; veille et `time.monotonic`.

---
*Recherche terminée : 2026-10-20 — prête pour la feuille de route*

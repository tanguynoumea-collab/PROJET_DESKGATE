# Architecture Patterns

**Domaine :** passerelle locale Windows (n8n vers outils lourds), runner Python à file SQLite
**Recherché le :** 2026-10-20
**Portée :** ce document ne redessine pas `ARCHITECTURE.md` (racine, validé). Il le met à l'épreuve, fixe les frontières de composants, les flux de données et l'ordre de construction pour atteindre l'acceptation v0.1 de façon incrémentale.
**Confiance globale :** MOYENNE. Le modèle de concurrence (threads + Popen + Job Object) repose sur des faits Windows/Python connus et sur le test Job Object déjà réalisé (rapport de vérifications §6). Les points marqués [à prouver] n'ont pas été exécutés dans cette recherche.

## Réponse courte à la question de concurrence

**Décision : le worker et la supervision des sous-processus sont des threads, pas de la coroutine asyncio.** FastAPI/Uvicorn garde la boucle asyncio (ProactorEventLoop) uniquement pour le HTTP.

Pourquoi :

1. La séquence imposée par la règle n°3 (`CREATE_SUSPENDED`, `AssignProcessToJobObject`, `NtResumeProcess`) a besoin du handle de processus d'un `subprocess.Popen`. `asyncio.create_subprocess_exec` accepte `creationflags`, mais n'expose le `Popen` que par un attribut privé du transport : fragile, à éviter.
2. Un job dure de quelques secondes à plus d'une heure. Le bloquer dans `Popen.wait(timeout)` dans un thread dédié est le modèle le plus simple et le plus robuste. Aucune coroutine n'est bloquée, la boucle HTTP reste réactive.
3. Uvicorn sous Windows : en processus unique, sans `--reload` ni `workers > 1`, il utilise `ProactorEventLoop` (défaut Python depuis 3.8), qui gère les sous-processus. Il bascule sur `SelectorEventLoop` seulement avec reload/workers multiples, cas où `asyncio` ne sait plus lancer de sous-processus. Conséquence : **lancer Uvicorn en processus unique, sans reload en production, `loop="asyncio"` explicite**. Même sans asyncio pour les sous-processus, cela évite une surprise future (exécuteur MCP, httpx). [MOYENNE : lu dans mon souvenir du code uvicorn, à confirmer par un test d'une ligne : `asyncio.get_running_loop()` dans une route.]
4. SQLite est synchrone (`sqlite3` standard). Une connexion par thread, WAL, `busy_timeout` : pas de pilote asynchrone nécessaire.

Répartition :

| Contexte d'exécution | Contenu | Règle |
|---|---|---|
| Boucle asyncio (thread principal, Uvicorn) | Routes FastAPI, authentification, validation de requête | **Aucun appel bloquant.** Les routes qui touchent SQLite sont des `def` synchrones (Starlette les exécute dans son pool de threads) ou appellent `anyio.to_thread.run_sync`. |
| Thread `scheduler` (1, démon) | Boucle : réveil par `threading.Event` ou sondage 1 s, sélection des tâches `queued` éligibles par ressource, démarrage des superviseurs | Seul écrivain des transitions `queued -> running`. |
| Threads `supervisor` (1 par tâche `running`) | `Popen` + Job Object, attente avec délai, lecture des événements, transition terminale | Seul écrivain de la transition `running -> terminal` pour sa tâche. |
| Thread `callback-sender` (1) | Lit la table `callbacks` (outbox), POST via `httpx` synchrone, réessais à délai croissant | Voir §Rappel : l'état est en base, pas en mémoire. |

Le pont API vers worker passe **uniquement par SQLite** (INSERT d'une tâche, UPDATE `cancel_requested`) plus un `threading.Event` de réveil. Pas de file en mémoire : l'état doit survivre au redémarrage.

## Architecture recommandée

```
            HTTP (127.0.0.1:8765, jeton Bearer, contrôle Host)
                          |
                  [ api ]  FastAPI, boucle asyncio
                          |  (lecture / écriture SQLite uniquement)
                          v
   +------------------ [ store ] SQLite WAL ------------------+
   | jobs | job_events/logs | callbacks (outbox) | audit | tokens |
   +---^-----------^-------------------^----------------------+
       |           |                   |
 [ scheduler ] [ supervisor xN ]  [ callback-sender ]
   thread        threads             thread
       |           |
       |     [ jobobject ] ctypes (Job + suspend/assign/resume/terminate)
       |           |
       |     [ executors ] python | cli | mcp  (construisent la ligne de commande)
       |           |
       |           v   Popen CREATE_SUSPENDED, dans le Job Object
       |     processus worker (hors runner)
       |       python : deskgate_sdk (ctx) -> plugin dans son venv uv
       |       cli    : exécutable + gabarit
       |       mcp    : python -m deskgate_mcp_worker (SDK mcp) -> serveur stdio
       |           |
       |           +--> work_dir/<job_id>/ : events.jsonl, result.json, cancel.flag, job.log
       |
 [ paths ] conversion /data <-> C:/BIM et validation (appelée par api ET executors)
 [ plugins.registry ] capacités (codées en dur v0.1, manifeste v0.2)
```

### Limites de composants

| Composant (paquet) | Responsabilité | Parle à | Ne doit jamais |
|---|---|---|---|
| `security.tokens` / middleware `api` | Vérifie le jeton (comparaison à temps constant, hachage), en-tête `Host` (anti-rebinding), refus de démarrer hors loopback | `api`, `store` | Être contourné par `/ui` plus tard (même middleware) |
| `security.paths` | `to_host(path)`, `to_container(path)`, `validate(path)` : résolution `..`, liens, jonctions (`os.path.realpath` puis test de préfixe sur chemin normalisé et insensible à la casse) | `api` (à la soumission), `executors` (artefacts) | Dépendre de FastAPI ou de SQLite : module pur, testable seul |
| `api` | Validation d'entrée, création de tâche `queued`, lecture d'état, annulation (pose du drapeau), téléchargement d'artefact | `store`, `plugins.registry`, `security` | Lancer un processus, attendre un job, faire un appel réseau sortant |
| `store` (`queue/db.py`) | Schéma, migrations, connexions par thread, transitions atomiques (`UPDATE ... WHERE status = ?`, vérifier `rowcount`) | Tous | Contenir de la logique d'ordonnancement |
| `queue.scheduler` | Choix de la prochaine tâche éligible selon `resource` et concurrence max, démarrage du superviseur | `store`, `executors` | Exécuter une tâche lui-même |
| `executors.jobobject` | Création du Job (`KILL_ON_JOB_CLOSE`, jamais de breakaway), `spawn_suspended`, `terminate`, `active_processes` | `executors.*` | Connaître la notion de plugin ou de tâche |
| `executors.{python,cli,mcp}` | Construit `argv`, environnement, répertoire de travail ; retourne un descripteur de lancement | `supervisor` | Appeler `Popen` directement (passe par `jobobject`) |
| `queue.supervisor` | Cycle de vie d'une tâche : lancer, tailler les événements, délai, annulation douce puis dure, lire `result.json`, écrire l'état terminal et l'entrée `callbacks` **dans la même transaction** | `store`, `jobobject`, `executors` | Faire l'appel HTTP de rappel |
| `callback` | Outbox : envoi, plafond 1 Mio, débordement `summary.json`, réessais, masquage de `signature` | `store`, réseau sortant | Reconstruire l'URL ; journaliser l'URL brute |
| `recovery` | À l'amorçage : `running -> interrupted` + insertion des rappels ; nettoyage des `work_dir` orphelins | `store` | S'exécuter après l'ouverture du port HTTP |
| `plugins.registry` | v0.1 : table codée en dur `ifc.clash`, `mcp.call` ; v0.2 : manifestes | `api`, `executors` | Importer `deskgate_bim` |
| `deskgate_sdk` (paquet minuscule, MIT, sans dépendance) | Côté plugin : `ctx.log/progress/artifact/cancelled`, écriture de `events.jsonl` et `result.json` | Processus worker uniquement | Importer le cœur `deskgate` |
| `cli` (`deskgate init/serve/doctor`) | Configuration, génération du jeton, enregistrement de la tâche planifiée | `runner.toml`, `schtasks`/XML | Contenir de la logique métier |
| `plugins/bim` (`deskgate-bim`) | `ifc.clash` : détection `ifcclash`, regroupement, écrit un JSON d'entrée pour `deskgate-bcf` | `deskgate_sdk`, sous-processus `deskgate-bcf` | Importer `deskgate-bcf` ou `bcf-client` |
| `plugins/bim/bcf` (`deskgate-bcf`, GPL-3) | CLI : JSON vers `.bcf` | Fichiers JSON uniquement | Être importé par quiconque |

### Protocole entre superviseur et processus worker (fichiers, pas de pipes)

Choix opiniâtre : **échange par fichiers dans `work_dir/<job_id>/`**.

| Fichier | Sens | Contenu |
|---|---|---|
| `input.json` | runner vers worker | `params` convertis et validés, `job_id`, `work_dir`, limites |
| `events.jsonl` | worker vers runner | lignes `{"t":"log"|"progress"|"artifact", ...}` ; le superviseur lit à partir d'un offset |
| `result.json` | worker vers runner | `summary`, `data`, `artifacts` ; écrit en `result.json.tmp` puis `os.replace` (atomique) |
| `cancel.flag` | runner vers worker | présence = `ctx.cancelled()` vrai |
| `job.log` | stdout+stderr du worker | redirigés vers ce fichier ; pas de pipe |

Raisons : stdout/stderr en pipe peut bloquer un worker bavard si personne ne lit (interblocage classique) et il faut alors un thread lecteur par flux ; un fichier n'a pas ce problème, survit à un crash du runner (diagnostic de `interrupted`) et sert directement à `GET /jobs/{id}/logs`. Fonctionne à l'identique pour `cli` (stdout/stderr vers `job.log`, résultat via le fichier déclaré dans le gabarit) et `mcp`.

Pour `mcp.call` : le runner **ne lance pas le serveur MCP lui-même**. Il lance un petit worker Python (`deskgate_mcp_worker`, qui utilise le SDK `mcp` et son client stdio) **dans le Job Object**. Le serveur MCP stdio devient alors un descendant du worker et meurt avec le job. Cela évite d'avoir à greffer un Job Object sur la création de processus interne du SDK. [à prouver en phase 3 ; vérifier que le SDK `mcp` installé ne pose pas `CREATE_BREAKAWAY_FROM_JOB` : il n'aurait aucun effet sans `BREAKAWAY_OK`, selon le test §6.]

## Flux de données

### Soumission (chemin heureux)

1. n8n : `POST /jobs {capability, params, callback.url, idempotency_key, timeout}` avec Bearer.
2. `api` : jeton OK, `registry.get(capability)` OK, validation JSON Schema, `paths` convertit et valide chaque chemin d'entrée (refus 400 sinon), `timeout` plafonné au max du plugin.
3. `store` : INSERT `jobs(status='queued', callback_url=<brut>, ...)`. Réponse `202 {job_id, status:'queued'}`. L'URL de rappel est stockée brute (nécessaire pour l'appeler) mais jamais exposée par aucune route ni journalisée.
4. `scheduler` (réveillé) : une tâche éligible, `UPDATE ... SET status='running' WHERE id=? AND status='queued'`, crée `work_dir`, écrit `input.json`, démarre un thread `supervisor`.
5. `supervisor` : `jobobject.spawn_suspended(argv, env, cwd, stdout=job.log)`, puis assign, puis resume. Boucle toutes les ~0,5 s : lit `events.jsonl` (progression stockée), vérifie `cancel_requested`, vérifie l'échéance (`time.monotonic`).
6. Fin normale : lit `result.json`, valide les chemins d'artefacts (mêmes règles), conversion vers `/data/...`, transition `succeeded` + INSERT `callbacks(job_id, payload)` **dans une seule transaction**, puis `TerminateJobObject` pour nettoyer les orphelins éventuels, fermeture du handle.
7. `callback-sender` : prend les lignes `callbacks` dues, POST, marque `delivered` ou reprogramme.

### Délai maximum et annulation

`supervisor` : poser `cancel.flag`, `CTRL_BREAK_EVENT` si le processus est dans un nouveau groupe, grâce 10 s, puis `TerminateJobObject`, contrôle `ActiveProcesses == 0`, état `timeout` ou `cancelled`. L'état final est choisi par le superviseur seul, donc pas de course entre API et worker : l'API ne fait que poser `cancel_requested=1` (et `UPDATE` direct `queued -> cancelled` pour une tâche pas encore démarrée, protégé par `WHERE status='queued'`).

### Redémarrage

`recovery` s'exécute **avant** l'ouverture du port et **avant** le démarrage du scheduler : `UPDATE jobs SET status='interrupted' WHERE status='running'` plus INSERT `callbacks` pour chacune. Les `queued` restent `queued` et repartent. Les processus enfants sont déjà morts : `KILL_ON_JOB_CLOSE` a fermé le Job à la mort du runner. (Arrêt propre par `deskgate serve` Ctrl+C : même chemin, les superviseurs sont arrêtés, jobs marqués `interrupted` explicitement, car l'absence de crash ne dispense pas du rappel.)

### Rappel (outbox)

Table `callbacks(id, job_id, payload_json, attempt, next_at, state)`. Le rappel est **durable** : il est écrit dans la transaction de fin de tâche, donc un crash entre la fin du calcul et l'envoi ne perd rien. Sender : `next_at <= now`, POST du JSON, 2xx = livré, 413 = rappel d'erreur minimal sans réessai, 401/404 = abandon tracé (exécution n8n disparue, ne pas boucler), réseau/5xx = backoff exponentiel plafonné (ex. 5 s, 15 s, 1 min, 5 min, 15 min, puis toutes les 15 min jusqu'à une borne en heures). Au redémarrage du runner, les rappels `pending` reprennent. La borne doit être cohérente avec la « Limit Wait Time » du Wait n8n (rapport §1).

## Schéma SQLite minimal (v0.1)

| Table | Colonnes clés |
|---|---|
| `jobs` | `id` (hex 8+), `capability`, `params_json`, `status`, `resource`, `idempotency_key` (UNIQUE partiel), `callback_url`, `timeout_s`, `cancel_requested`, `progress_pct`, `progress_msg`, `result_json`, `error`, `created_at`, `started_at`, `finished_at` |
| `job_logs` | `job_id`, `seq`, `ts`, `level`, `msg` (ou lecture directe de `job.log`) |
| `callbacks` | voir ci-dessus |
| `audit` | `ts`, `client`, `capability`, `params_sanitized`, `status`, `detail` (créée dès v0.1 : coût nul, évite une migration) |
| `meta` | `schema_version` |

Dès la v0.1, **créer les colonnes `resource` et `idempotency_key`** même si le scheduler n'applique qu'une concurrence globale de 1 : la v0.2 n'exigera alors qu'un changement de logique, pas de schéma. Le pragma `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`, `foreign_keys=ON`.

## Patterns à suivre

### Pattern 1 : transition d'état atomique par UPDATE conditionnel
**Quoi :** chaque changement d'état est un `UPDATE ... WHERE id=? AND status IN (...)` dont on contrôle `rowcount`.
**Quand :** toujours (scheduler, superviseur, API d'annulation, recovery).
**Exemple :**
```python
def transition(db, job_id, frm, to, **cols):
    cur = db.execute(
        "UPDATE jobs SET status=?, finished_at=? WHERE id=? AND status IN (%s)"
        % ",".join("?" * len(frm)), (to, now(), job_id, *frm))
    return cur.rowcount == 1   # False = quelqu'un d'autre a gagné la course
```

### Pattern 2 : fin de tâche et rappel dans une transaction
**Quoi :** état terminal + INSERT dans `callbacks` dans le même `BEGIN IMMEDIATE`.
**Pourquoi :** c'est ce qui rend la valeur centrale (« n8n reprend toujours ») vraie même en cas de crash.

### Pattern 3 : Job Object par ctypes, avec signatures déclarées
**Quoi :** `ctypes.WinDLL("kernel32", use_last_error=True)`, déclarer `argtypes`/`restype` de chaque fonction (en particulier `HANDLE` en 64 bits : sans cela, troncature des handles sous Python 64 bits).
**Exemple :**
```python
p = subprocess.Popen(argv, creationflags=CREATE_SUSPENDED | CREATE_NEW_PROCESS_GROUP,
                     stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                     env=env, cwd=cwd, close_fds=True)
assign(job, int(p._handle))      # _handle : privé mais stable, déjà validé par le test
nt_resume_process(int(p._handle))
```
Contrôler le retour d'`AssignProcessToJobObject` : en cas d'échec, tuer le processus suspendu et marquer `failed`, ne **jamais** reprendre un processus hors job.

### Pattern 4 : exécuteurs = constructeurs de lancement, pas lanceurs
Un exécuteur retourne `LaunchSpec(argv, env, cwd, grace)`. Un seul code (`supervisor` + `jobobject`) lance, surveille et tue. Ajouter un type de plugin ne touche jamais au code d'arrêt.

### Pattern 5 : une seule horloge, monotone
Le délai utilise `time.monotonic()` (insensible à la veille ou au changement d'heure). Les horodatages affichés utilisent l'horloge murale.

## Anti-patterns à éviter

### Anti-pattern 1 : exécuter le job dans une coroutine ou un thread du processus API
**Pourquoi c'est mauvais :** viole la règle n°3 ; un plugin IfcOpenShell qui plante ou consomme toute la mémoire emporte l'API.
**À la place :** sous-processus uniquement.

### Anti-pattern 2 : pipes stdout/stderr non drainés
**Pourquoi :** interblocage du worker bavard. **À la place :** redirection vers fichier.

### Anti-pattern 3 : reconstruire ou normaliser la `resumeUrl`
**Pourquoi :** 401 (jeton `signature`). **À la place :** passer la chaîne brute à `httpx` (`httpx.URL(raw)` ne réencode pas la query ; à vérifier par test avec une signature contenant `+`, `/`, `=`), et masquer par remplacement de la valeur de `signature` pour toute trace.

### Anti-pattern 4 : état en mémoire pour la file ou les rappels
**Pourquoi :** perdu au redémarrage, contredit l'état `interrupted`. **À la place :** tout en SQLite.

### Anti-pattern 5 : ouvrir le port avant la recovery
**Pourquoi :** une requête `GET /jobs/{id}` verrait `running` pour une tâche morte. **À la place :** recovery dans le `lifespan` avant le démarrage du scheduler, et le port n'est servi qu'après `startup` (garanti par le lifespan ASGI).

### Anti-pattern 6 : `psutil` comme mécanisme d'arrêt
Prouvé insuffisant (rapport §6). Diagnostic seulement.

## Pièges de concurrence spécifiques à ce montage

| Piège | Détail | Parade |
|---|---|---|
| Écritures SQLite concurrentes | WAL autorise 1 écrivain ; plusieurs threads provoquent `database is locked` | `busy_timeout`, transactions courtes, `BEGIN IMMEDIATE`, une connexion par thread (jamais partagée) |
| Fuite de handle de job | Handle non fermé = `KILL_ON_JOB_CLOSE` jamais déclenché ou, à l'inverse, fermeture trop tôt qui tue un job vivant | Le superviseur possède le handle pour toute la vie de la tâche (try/finally) |
| Course terminal : fin normale vs délai | `result.json` apparaît au moment où le délai expire | Priorité : si le processus est sorti avec code 0 et `result.json` valide avant l'échéance, `succeeded` ; sinon `timeout` ; transition conditionnelle |
| Héritage de handles | Les handles hérités par l'enfant (base SQLite, socket du port) | `close_fds=True` (défaut) ; ne pas utiliser `bInheritHandles` à la légère |
| Arrêt d'Uvicorn | Ctrl+C ou tâche planifiée arrêtée pendant des jobs | `lifespan` shutdown : signaler les superviseurs, marquer `interrupted`, attendre le sender un court instant |
| Boucle bloquée par un `def` async oublié | Une route `async def` qui appelle `sqlite3` bloque tout | Convention : routes `def`, test de latence de `/health` pendant un job |
| Instance double | Deux runners ouverts (reconnexion de session, lancement manuel) | Verrou : le bind du port 8765 échoue tout seul ; ajouter un mutex nommé Windows pour un message clair |

## Plan de construction incrémental vers l'acceptation v0.1

Principe : chaque étape livre une chose démontrable par un test avec de vrais sous-processus, et l'acceptation de la v0.1 est atteinte en **tranche verticale** dès l'étape 5, puis durcie. Les deux pistes (runner, BIM) se rejoignent à l'étape 6.

| # | Étape | Contenu | Preuve de sortie | Dépend de |
|---|---|---|---|---|
| 0 | Prérequis machine | Test `host.docker.internal` vers `127.0.0.1` (2 min, rapport §2) ; test d'une ligne : type de boucle sous Uvicorn | Test passé ou plan B écrit | — |
| 1 | Squelette et sécurité d'entrée | Paquet `deskgate`, `runner.toml`, `/health`, middleware jeton + contrôle `Host`, refus de bind hors loopback | Tests : sans jeton 401, `Host` étranger refusé | 0 |
| 2 | `paths` | Conversion bidirectionnelle, validation (`..`, lien symbolique, jonction, casse, chemins UNC, `C:\BIM2` vs `C:\BIM`) | Tests dédiés obligatoires (CLAUDE.md) | — (parallélisable avec 1) |
| 3 | `jobobject` autonome | `spawn_suspended`, `terminate`, `active_processes` ; port du test orphelin du rapport §6 en test pytest | Test : petit-enfant tué ; mort brutale du parent tue l'arbre | — (parallélisable) |
| 4 | `store` + machine d'états | Schéma, transitions atomiques, `recovery` (`running -> interrupted` + outbox) | Test : insérer `running`, redémarrer le store, état `interrupted` + rappel en file | 1 |
| 5 | Supervision de bout en bout avec un faux plugin | `scheduler` (concurrence 1), `supervisor`, exécuteur `python` minimal + `deskgate_sdk`, `POST/GET /jobs`, `/logs`, `/cancel`, délai | Test : tâche `sleep` 3 s réussit ; tâche qui lance un petit-fils orphelin et dépasse son délai : arbre mort, état `timeout` | 2, 3, 4 |
| 6 | `callback` outbox | Envoi, plafond 1 Mio + `summary.json`, réessais, masquage, 413/401 | Tests avec faux serveur n8n local : signature non réencodée, absente des journaux, reprise après redémarrage du sender | 4 |
| 7 | Exécuteur `mcp.call` | Worker `deskgate_mcp_worker`, serveur MCP stdio d'exemple | Test : appel d'outil réussi ; timeout tue serveur et worker | 5 |
| 8 | Piste BIM : `deskgate-bcf` puis `ifc.clash` | CLI GPL JSON vers `.bcf` ; `ifc.clash` appelle la CLI en sous-processus ; environnement uv dédié | Test sur petit IFC de `plugins/bim/tests/` ; vérifier qu'aucun import croisé n'existe (test d'analyse statique des imports) | 5 (pour l'intégration), indépendant pour le développement |
| 9 | `deskgate init` + Planificateur | Génération du jeton et de `runner.toml`, tâche à l'ouverture de session | Redémarrage de session : le runner répond | 1 |
| 10 | `n8n/docker-compose.yml` + workflow HTTP Request + Wait | n8n 2.43.8 épinglé, Postgres, montage `C:\BIM`, `N8N_WEBHOOK_URL` ; Wait avec « Limit Wait Time » | **Acceptation v0.1** : calcul de plus de 10 min, reprise sur rappel, `interrupted` après arrêt du runner en cours de tâche, arbre tué au délai | 6, 8, 9 |

Remarques d'ordonnancement :

- Les étapes 2 et 3 sont des modules purs, sans dépendance : les démarrer tôt retire les deux plus gros risques Windows (chemins, Job Object) avant l'intégration.
- L'étape 5 avec un faux plugin (`sleep`, `spawn_orphan`) valide **le cœur de la valeur** (délai, arbre, `interrupted`) sans aucun IfcOpenShell. `ifc.clash` n'est alors qu'un plugin de plus.
- Le test « mort brutale du runner pendant une tâche » (taskkill /F sur le runner, puis démarrage) est la validation réelle de `interrupted` : il se fait à l'étape 5/6, pas à la toute fin.
- Ne pas construire le manifeste en v0.1 : la table `registry` codée en dur doit toutefois renvoyer une structure identique à celle que le manifeste produira (`resource`, `timeout`, `input_schema`, `kind`), pour que la v0.2 remplace la source, non le consommateur.
- Prévoir dès l'étape 5 le **découpage en `LaunchSpec`** : la v0.2 ajoute `cli` et `python` à environnement uv sans toucher au superviseur.

### Phasage suggéré pour la feuille de route

1. **Fondations testables** : étapes 1 à 4 (sécurité d'entrée, chemins, Job Object, store et recovery).
2. **Cœur d'exécution** : étape 5 (scheduler, superviseur, API des tâches).
3. **Rappel fiable** : étape 6.
4. **Capacités v0.1** : étapes 7 et 8 (`mcp.call`, `deskgate-bcf`, `ifc.clash`).
5. **Installation et intégration n8n** : étapes 9 et 10, acceptation v0.1.

## Considérations de montée en charge

Mono-tenant : un PC, un utilisateur. Le dimensionnement est borné par la machine, pas par des utilisateurs.

| Préoccupation | v0.1 (concurrence 1) | v0.2 (par ressource) | Au-delà |
|---|---|---|---|
| Threads | 1 superviseur | `light` N superviseurs ; SQLite WAL suffit | Sans objet |
| Taille de la base | Purge des tâches terminées anciennes (option `retention_days`) | Idem | Idem |
| Journaux | Fichier `job.log` par tâche, plafonné | Idem | Idem |
| Espace disque `work_dir` | Nettoyage des `work_dir` des tâches anciennes après rétention, sans toucher aux artefacts référencés | Idem | Idem |

## Risques de l'architecture mis à l'épreuve (pour les phases)

1. **Tâche planifiée Windows** [à prouver] : vérifier à l'étape 9 les réglages par défaut qui tuent silencieusement le runner : « arrêter la tâche si elle s'exécute plus de 3 jours », « ne démarrer que sur secteur », « ne pas lancer de nouvelle instance ». Générer l'XML de la tâche (via `schtasks /Create /XML`) avec `ExecutionTimeLimit=PT0S`, `DisallowStartIfOnBatteries=false`, `StopIfGoingOnBatteries=false`, déclencheur `LogonTrigger` limité à l'utilisateur courant, `MultipleInstancesPolicy=IgnoreNew`. Cela fait appel à des connaissances de formation : à valider contre la documentation Microsoft du schéma de tâche. Confiance MOYENNE.
2. **Jobs imbriqués** : une tâche du Planificateur tourne dans son propre Job Object. Windows 8 et suivants autorisent l'imbrication, donc l'assignation d'un enfant à un Job propre fonctionne ; à confirmer dans les tests d'étape 9 (lancer l'acceptation depuis la tâche planifiée, non depuis un terminal).
3. **`mcp.call` et Job Object** : voir §Protocole. Si le SDK `mcp` crée son propre Job Object côté Windows pour le serveur, vérifier qu'il n'entre pas en conflit avec l'imbrication (acceptable sous Windows 8+).
4. **Sessions verrouillées** (`requires_session`) : non pertinent en v0.1 (`ifc.clash` est `cpu-heavy` sans interface), à traiter dans les phases `gui-session` de la v0.2.
5. **`ifcclash` et BCF** : l'export BCF intégré d'`ifcclash` importe `bcf-client` (GPL). `ifc.clash` doit uniquement utiliser la partie détection et sérialiser les résultats en JSON ; vérifier à l'étape 8 que l'import de `ifcclash.ifcclash` n'entraîne pas l'import de `bcf` à l'exécution dans l'environnement du plugin MIT (sinon installer `bcf-client` dans un environnement séparé, uniquement celui de `deskgate-bcf`). **Risque de frontière de licence à vérifier** : c'est la seule zone où la règle n°10 peut être violée indirectement. Confiance BASSE sur le détail d'import, à lire dans le code d'`ifcclash` 0.9.

## Sources

- Rapport interne `.arthemis/reports/verifs-techniques-cycle-1.md` §1, §2, §3, §6 (HAUTE pour le Job Object, testé ; HAUTE pour la reprise n8n, lu dans le code 2.43.8).
- `ARCHITECTURE.md`, `ROADMAP.md`, `CLAUDE.md`, `.planning/PROJECT.md` du dépôt (architecture validée, entrées de cette recherche).
- Connaissances générales de Python/Windows (`subprocess`, `asyncio` ProactorEventLoop, comportement d'Uvicorn avec reload, schéma XML du Planificateur de tâches) : **non revérifiées par recherche externe dans cette session** (aucun accès à des sources en ligne utilisé). Confiance MOYENNE ; chaque point est assorti d'un test de validation à l'étape correspondante.

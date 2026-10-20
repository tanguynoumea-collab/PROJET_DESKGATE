# Conseil d'approche — cycle 1 (milestone v0.1)

Date : 2026-10-20. Question : comment implémenter les 5 phases de `.planning/ROADMAP.md` (le QUOI est
figé). Conseil : 5 membres indépendants (Pragmatique, Red-teamer, Rigoriste, Premiers principes,
Généraliste), 5 relectures à l'aveugle, synthèse par ARTHEMIS.

Classement agrégé (position moyenne) : Rigoriste 1,0 · Premiers principes 2,6 · Red-teamer 3,2 ·
Pragmatique 3,4 · Généraliste 4,8. Les cinq relecteurs placent le Rigoriste premier.

## Architecture retenue

### 1. Noyau pur, coquille impérative, frontière vérifiée

- `src/deskgate/core/` : fonctions pures, testables sans disque, serveur ni sous-processus.
  - `states` : table des transitions et `step(job, observation, now) -> (transition, actions)`.
    L'observation regroupe code de sortie, validité de `result.json`, `cancel_requested`, échéance.
  - `outcome` : verdict terminal. Règle écrite et testée : sortie avant l'échéance sans annulation →
    on évalue le résultat (`succeeded` exige code 0 **et** `result.json` valide **et** artefacts
    revalidés) ; annulation demandée avant la sortie → `cancelled` même si le résultat est valide ;
    sinon `timeout`. Le worker ne décide jamais de son statut.
  - `callback_policy` : `classify(status, body) -> Delivered | RetryShort | RetryBackoff |
    Abandon(raison)` et `next_attempt(attempts, now, rng)`.
  - `payload` : construction du rappel depuis la ligne `jobs`, plafond 1 Mio, débordement vers
    `summary.json`.
  - `paths` : conversion et contrôles lexicaux (UNC, `CON`, flux alternatif, préfixe de segment
    `C:/BIM2`) ; résolution des liens et jonctions par un `resolver` injecté.
  - `redact` : **une seule** fonction de masquage de `signature=`, utilisée par le filtre `logging`,
    les sérialiseurs d'API et l'audit.
  - `config` : `tomllib` + `RunnerConfig.model_validate` (pas de pydantic-settings), messages en
    français.
  - `tokens` : SHA-256 + `hmac.compare_digest` (jeton aléatoire 256 bits : argon2 inutile).
  - `worker_protocol` : modèles Pydantic d'`input.json`, `events.jsonl`, `result.json`.
- Coquille : `store` (seul module qui importe `sqlite3`), `jobobject` (ctypes, derrière
  `spawn_in_job()`), `engine`, `sender`, `api`, `cli`.
- **Tests AST** : `core/` n'importe jamais `sqlite3`, `subprocess`, `httpx2`, `fastapi`, `ctypes` ;
  aucun paquet hors `plugins/bim/bcf/` n'importe `bcf` ni `deskgate_bcf`. Écrits dès la phase 1.

### 2. Concurrence

- asyncio sert uniquement à Uvicorn. Routes `def` synchrones.
- **Un thread `engine`** : sondage toutes les 0,5 s (`Popen.poll()`), démarre la prochaine tâche
  `queued`, lit les événements, applique `step()`. Il est le seul à écrire les transitions
  `running → *`. Concurrence N (v0.2) = une condition dans `step()`.
- **Un thread `sender`** pour l'outbox (un POST lent ne retarde pas un délai), avec un
  `httpx2.Client` **synchrone** qui lui appartient.
- Une connexion SQLite par thread de fond, connexion par requête côté API ; WAL,
  `synchronous=FULL`, `busy_timeout=5000`, toute écriture en `BEGIN IMMEDIATE`, réessai unique sur
  `SQLITE_BUSY` concentré dans `store`.
- Robustesse de l'engine : `try/except` par tâche dans le tick (→ `failed` + audit), taille maximale
  lue pour `result.json`, battement exposé dans `/health` ; si le thread meurt, le runner s'arrête
  volontairement (la tâche planifiée le relance, la recovery rend l'arrêt sans danger).

### 3. Démarrage et instance unique (corrige RUN-03)

Ordre strict, **hors du `lifespan` d'Uvicorn** (il s'exécute avant le bind) :
1. mutex nommé `Local\Deskgate` (`CreateMutexW`) — un second runner sort ici sans ouvrir la base ;
2. socket créé et lié à la main avec `SO_EXCLUSIVEADDRUSE` sur `127.0.0.1` ;
3. ouverture de la base (`%LOCALAPPDATA%\Deskgate`, jamais sous OneDrive ni `C:\BIM`), migrations
   par `PRAGMA user_version` ;
4. recovery ;
5. threads `engine` et `sender` ;
6. `uvicorn.Server(config).serve(sockets=[sock])`.

### 4. Protocole runner ↔ worker : les fichiers sont un transport, jamais un état

- `work_dir` : `input.json`, `events.jsonl`, `result.json`, `cancel.flag`, `job.log`.
- Seul l'engine ingère ces fichiers en base, après validation.
- `events.jsonl` lu par offset jusqu'au dernier `\n` ; ligne invalide journalisée et ignorée.
- `result.json` écrit en `.tmp` puis `os.replace` par le worker ; lu par le runner **seulement après
  la sortie du processus et `TerminateJobObject`** (sinon `PermissionError` sous Windows) ; taille
  plafonnée ; artefacts repassés par `paths`.
- `cancel.flag` est une projection de `jobs.cancel_requested`, écrite par l'engine.
- Annulation : sentinelle, délai de grâce, `TerminateJobObject`. **Pas de `CTRL_BREAK`.**
- `TerminateJobObject` systématique en fin de tâche, même normale (orphelins).
- Environnement en liste blanche avec `PYTHONUTF8=1` ; `job.log` lu en octets, décodé
  `errors="replace"`.
- Recovery : `running → interrupted` **sans lire le disque**. Limite documentée : un `result.json`
  valide écrit juste avant le crash est perdu.
- Job Object : `KILL_ON_JOB_CLOSE`, jamais `BREAKAWAY_OK` ; création suspendue, assignation,
  `NtResumeProcess` (voie testée), alternative `CreateProcessW` + `PROC_THREAD_ATTRIBUTE_JOB_LIST`
  gardée derrière `spawn_in_job()`.
- `mcp.call` : worker `python -m deskgate.workers.mcp_call` dans le Job ; le serveur stdio est son
  descendant.

### 5. Schéma SQLite (migration 1, complète dès la phase 2)

- `jobs` (`STRICT`, `CHECK` sur les statuts) : `capability`, `params_json`, `status`,
  `cancel_requested`, progression, `result_json`, `error`, `resource`, `idempotency_key`,
  `callback_url` (brute, jamais exposée par l'API — test), horodatages UTC.
- Index unique partiel `(capability, idempotency_key) WHERE status IN ('queued','running')` (JOB-08 ;
  conflit → 409 avec le `job_id` existant). L'index sur `succeeded` est la v0.2.
- `callbacks` : `job_id UNIQUE`, `state` (`pending | delivered | delivered_duplicate |
  abandoned_stale | abandoned_rejected | abandoned_exhausted`), `attempts`, `next_attempt_at`,
  `not_before` (création + 2 s), `last_status`, `last_error_redacted`. **Pas de `payload_json`** :
  le corps est dérivé de `jobs` à l'envoi.
- `audit` (ajout seul), `tokens` (hachés). Pas de table de journaux : `job.log` fait foi.
- Fin de tâche : écrire `summary.json` si nécessaire, puis **une** transaction : `UPDATE jobs ...
  WHERE id=? AND status='running'` (contrôle de `rowcount`) + `INSERT callbacks` + `INSERT audit`.
  Même règle pour `queued → cancelled` et `running → interrupted`.
- L'échéance d'exécution reste en mémoire (monotone) : après redémarrage la tâche est `interrupted`.

### 6. Tests sous Windows

Marqueurs pytest : `unit` (noyau pur, horloge et aléa injectés), `fs` (vraies jonctions `mklink /J`,
ADS, `CON`, UNC ; liens symboliques en `skipif` explicite sans mode développeur), `proc` (faux plugins
`sleep`, `spawn_orphan` qui écrit le PID du petit-enfant, `result.json` invalide, sortie bavarde ;
vérification de mort par `OpenProcess`), `e2e` (`deskgate serve` en sous-processus sur port libre,
faux n8n en `http.server` qui enregistre la query brute et rejoue les textes 409 de 2.43.8,
`taskkill /F` puis redémarrage, tâche < 100 ms). CI `windows-latest` pour `unit`, `fs`, `proc` ;
acceptation IFC/Docker manuelle (phase 5).

### 7. Ordre de construction

- **Phase 1** : spikes d'abord (demi-journée chacun) : Job Object avec petit-enfant porté en pytest ;
  `host.docker.internal` → `127.0.0.1` avec un conteneur jetable ; comportement du bind
  (`SO_EXCLUSIVEADDRUSE`). Puis noyau pur, config, chemins, jeton et `Host`, mutex, socket, `/health`,
  tests AST.
- **Phase 2** : migration 1 complète (dont `callbacks` et `audit`), engine, faux plugin de bout en
  bout, API des tâches, annulation, délai, recovery, test `taskkill /F`.
- **Phase 3** : spikes courts d'abord (textes 409 du vrai n8n 2.43.8 enregistrés comme fixtures ;
  non-réencodage de la signature par `httpx2`), puis sender, politique, plafond, masquage, hôtes
  autorisés (contrôlés aussi à `POST /jobs`, 422).
- **Phase 4** : contrat JSON de `deskgate-bcf` versionné dans `docs/` d'abord ; spike `mcp` dans le
  Job ; `mcp.call` ; `deskgate-bcf` et `ifc.clash` en parallèle sur le contrat.
- **Phase 5** : spike Planificateur sans élévation, puis `init`, docker-compose, workflow, acceptation
  **depuis la tâche planifiée**.

## Alternatives écartées

| Proposition | Membre | Pourquoi écartée |
|---|---|---|
| Un thread superviseur par tâche + scheduler | Rigoriste, Pragmatique, Généraliste | Plus d'écrivains concurrents sans gain à concurrence 1 ; `step()` pur rend le nombre de threads indifférent, et un engine unique se teste avec une horloge injectée |
| Outbox fusionnée dans `jobs` (`cb_state`) | Premiers principes | Mélange deux concepts ; la table séparée `job_id UNIQUE` sans `payload_json` donne la même atomicité (une transaction) sans copie |
| `payload_json` figé dans `callbacks` | Pragmatique, Généraliste | Seconde copie du résultat qui peut diverger |
| Écrivain SQLite unique alimenté par une file | (évoqué) | File en mémoire = second état ; repli possible car seul `store` touche `sqlite3` |
| « Bind du port comme verrou » | recherche (P3) | Faux sous Windows avec `SO_REUSEADDR` ; le `lifespan` précède le bind |
| docker-compose dès la phase 1 | Red-teamer | Élargit la phase 1 ; un conteneur jetable suffit au spike réseau, les fixtures 409 sont capturées en phase 3 |
| Recovery qui relit `result.json` | (implicite) | Ferait de la recovery un second superviseur |
| `CTRL_BREAK_EVENT` pour l'annulation | recherche | Perdu sans console partagée, peut frapper le runner |
| pydantic-settings | recherche | API de source TOML incertaine ; `tomllib` + `model_validate` suffit |

## Points remontés à l'utilisateur (contestent le cadrage)

1. **Capacités « codées en dur » dans le cœur** (Red-teamer) : coder `ifc.clash` (nom, schéma,
   interpréteur du venv IfcOpenShell) dans `src/deskgate` met du BIM dans le cœur, contraire à la
   règle 1 de `CLAUDE.md`. Proposition : une section `[capabilities.<id>]` dans `runner.toml`
   (`kind = "python"`, `python`, `entry`, `timeout_max`, `resource`), validée par Pydantic — un
   mini-manifeste, pas le format `plugin.yaml` de la v0.2. Le faux plugin de test est déclaré de la
   même façon. **Recommandé.**
2. **« Une fois et une seule »** (critère de la phase 3) est impossible côté runner : la garantie est
   « au moins une fois » ; n8n rend la reprise unique (un second envoi reçoit 409 « terminée », tracé
   `delivered_duplicate`). Reformulation proposée du critère.
3. **Schéma de l'outbox et de l'audit en phase 2** : la table `callbacks` et l'INSERT transactionnel
   (nécessaires à JOB-06), ainsi que la table `audit`, sont créés en phase 2 ; la phase 3 livre
   l'envoi, la politique, le plafond, le masquage et le contenu complet de l'audit (SEC-06 reste en
   phase 3).

## Lacunes à mesurer (non tranchées par le conseil)

- `time.monotonic` pendant la veille sous Windows 11 : à mesurer avant de figer le « temps actif » ;
  la veille est une limite documentée en v0.1.
- Textes exacts des 409 de n8n 2.43.8 et sortie du Wait à l'échéance.
- SDK `mcp` dans un Job Object imbriqué.
- Planificateur sans élévation sur compte standard.

# Phase 2: Cœur d'exécution - Research

**Researched:** 2026-10-20
**Domain:** file de tâches SQLite + exécution de sous-processus dans un Job Object Windows (ctypes) + API FastAPI de tâches
**Confidence:** HIGH (tous les points risqués ont été vérifiés par exécution locale, Windows 11, Python 3.11.9 et 3.14.4, SQLite 3.45.1 et 3.50.4)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Délais**
- **D-01:** Délai par défaut d'une tâche : **2 h** (7200 s) si la requête n'en donne pas. Plafond global absolu : **12 h** (43200 s). Chaque capacité déclare `timeout_max` dans `[capabilities.<id>]` (≤ 12 h). Une requête qui demande plus que le `timeout_max` de sa capacité est refusée (422, code `timeout_too_large`).
- **D-02:** L'échéance est mesurée en mémoire avec `time.monotonic()` ; non persistée (après redémarrage, la tâche est `interrupted`). La veille est une limite documentée en v0.1.

**Annulation**
- **D-03:** Annulation coopérative : `jobs.cancel_requested = 1`, l'engine écrit `cancel.flag` dans le `work_dir`, le plugin le voit via `ctx.cancelled()`. **Délai de grâce : 10 s**, puis `TerminateJobObject`. Pas de `CTRL_BREAK`. Une tâche `queued` annulée passe directement `cancelled`. L'appel est idempotent (sur tâche terminale : 200 avec l'état actuel, pas d'erreur).

**Dossier de travail**
- **D-04:** `C:/BIM/travail/<job_id>/` (racine `travail` configurable sous une racine autorisée) est **conservé** après la fin de la tâche ; aucune purge automatique en v0.1. Contenu : `input.json`, `events.jsonl`, `result.json`, `cancel.flag`, `job.log`, artefacts.

**Capacités (décision du conseil, validée)**
- **D-05:** Les capacités sont lues dans `runner.toml` `[capabilities.<id>]` (`kind = "python"`, `python` = interpréteur, `entry` = `module:fonction`, `timeout_max`, `resource`). Le cœur ne contient aucun nom BIM. Les faux plugins de test sont déclarés de la même façon (config de test).
- **D-06:** Une capacité inconnue à la soumission → 404 `capability_not_found`. Les paramètres (`params`) sont validés comme objet JSON ; leur schéma propre arrive en v0.2 (manifeste). Tout paramètre de type chemin reste à la charge du plugin en v0.1, mais les artefacts déclarés sont revalidés par `core/paths` (hors racines → tâche `failed`).

**Architecture d'exécution (conseil d'approche, `.arthemis/reports/llm-council-1.md`)**
- **D-07:** Un thread `engine` (sondage 0,5 s, `Popen.poll()`), seul écrivain des transitions `running → *`, applique une fonction pure `core/states.step(job, observation, now)`. Verdict pur `core/outcome` : sortie avant échéance sans annulation → `succeeded` seulement si code 0 **et** `result.json` valide **et** artefacts revalidés, sinon `failed` ; annulation demandée avant la sortie → `cancelled` ; échéance → `timeout`.
- **D-08:** Lancement unique `spawn_in_job()` (module `jobobject`, ctypes) : création suspendue, assignation, `NtResumeProcess`, `KILL_ON_JOB_CLOSE`, jamais `BREAKAWAY_OK`, sans shell, env en liste blanche avec `PYTHONUTF8=1`, sorties redirigées dans `job.log` (pas de pipe). `TerminateJobObject` systématique en fin de tâche.
- **D-09:** Fichiers = transport, jamais état. `events.jsonl` lu par offset jusqu'au dernier `\n` ; `result.json` (écrit `.tmp` puis `os.replace` par le worker) lu seulement après sortie du processus et `TerminateJobObject`, taille plafonnée. Petit SDK `deskgate_sdk` côté worker (`ctx.log`, `ctx.progress`, `ctx.artifact`, `ctx.cancelled`, écriture atomique du résultat) ; le contrat (`worker_protocol`) est dupliqué, pas importé du cœur, avec un test d'égalité.
- **D-10:** Schéma SQLite **migration 1 complète** (décision validée) : `jobs` (STRICT, CHECK des statuts, `capability`, `params_json`, `status`, `cancel_requested`, progression, `result_json`, `error`, `resource`, `idempotency_key`, `callback_url` brute jamais exposée, `work_dir`, horodatages UTC), index unique partiel `(capability, idempotency_key) WHERE status IN ('queued','running')` (conflit → 409 avec le `job_id` existant), `callbacks` (`job_id UNIQUE`, `state`, `attempts`, `next_attempt_at`, `not_before`, `last_status`, `last_error_redacted` ; pas de `payload_json`), `audit` (ajout seul), `PRAGMA user_version = 1`, WAL, `synchronous=FULL`, `busy_timeout=5000`, `BEGIN IMMEDIATE`. Seul `store` importe `sqlite3`.
- **D-11:** Toute transition terminale (y compris `queued → cancelled` et `running → interrupted`) se fait en **une** transaction : `UPDATE jobs ... WHERE status=...` (contrôle de `rowcount`) + `INSERT callbacks` (état `pending`) + `INSERT audit`. Le rappel n'est **pas envoyé** en phase 2 (pas de sender) ; la ligne existe.
- **D-12:** Recovery au démarrage, après le mutex et avant l'API : `running → interrupted` sans lire le disque (limite documentée : un `result.json` écrit juste avant le crash est perdu).
- **D-13:** `callback.url` est requis dans `POST /jobs`, stocké brut, jamais renvoyé par l'API (test). Le contrôle des hôtes autorisés (CB-05) et le masquage complet arrivent en phase 3.

### Claude's Discretion
- Forme exacte des réponses `GET /jobs/{id}` (dans le respect de D-08 de la phase 1 pour les erreurs).
- Format de `job_id` (UUID4 hex court ou ULID).
- Découpage des plans et vagues ; noms des faux plugins (`sleep`, `spawn_orphan`, `bad_result`, `chatty`, `artifact_outside`).

### Deferred Ideas (OUT OF SCOPE)
- Purge automatique des `work_dir` (après N jours) — idée pour une version ultérieure.

Hors phase (rappel du domaine) : envoi du rappel HTTP, politique de réponse n8n, plafond de taille, masquage complet de la `signature` et contenu complet de l'audit (phase 3) ; `ifc.clash`, `deskgate-bcf`, `mcp.call` (phase 4) ; `deskgate init` (phase 5).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| JOB-01 | `POST /jobs` → `202 { job_id, status: "queued" }` | §API (formes), §Pattern 5 (service de soumission), job_id 12 hex, 404/409/422 |
| JOB-02 | Persistance SQLite, une tâche à la fois, ordre de soumission | §Pattern 2 (SQL vérifié : `seq AUTOINCREMENT`, claim `UPDATE…RETURNING` avec `NOT EXISTS running`), §Pattern 3 (engine) |
| JOB-03 | `GET /jobs/{id}` + `/logs` | §API (forme de la réponse, `/logs` par offset/tail), lecture de `job.log` pendant l'écriture vérifiée |
| JOB-04 | `POST /jobs/{id}/cancel` idempotent, coopératif puis arrêt forcé | §Pattern 2 (`request_cancel` en une transaction), §Pattern 4 (`step()` : grâce, course), `cancel.flag` |
| JOB-05 | Délai maximum : arrêt de l'arbre (orphelins) → `timeout` | Expériences 1 et 6 (TerminateJobObject tue l'orphelin ; `ActiveProcesses`), §Pattern 4 |
| JOB-06 | Redémarrage : `running` → `interrupted` + rappel inséré | Expérience 6 (taskkill /F /T), §Pattern 2 (`recover_interrupted`, une transaction), §Pattern 6 (ordre de démarrage) |
| JOB-07 | Sous-processus dans un Job Object, jamais dans le runner, sans shell | §Pattern 1 (`spawn_in_job` vérifié 3.11/3.14, Job imbriqué, venv), test AST `shell=True` déjà en place |
| JOB-08 | `idempotency_key` identique à une tâche non terminale → 409 | §Pattern 2 (index partiel vérifié, NULL multiples permis, clé libérée à l'état terminal) |
| JOB-09 | Dossier de travail par tâche, artefacts déclarés | §Pattern 5 (`work_root`, arborescence, revalidation `core/paths`), §Code Examples (worker) |
</phase_requirements>

## Summary

Tout ce qui était incertain a été éprouvé par de petites expériences locales (hors dépôt, dans le scratchpad), sur Python 3.11.9 et 3.14.4. Résultats clés : (1) la recette `CREATE_SUSPENDED` + `Popen._handle` + `AssignProcessToJobObject` + `NtResumeProcess` fonctionne telle quelle avec sortie redirigée vers un fichier, env en liste blanche, interpréteur de venv (lanceur-relais compris) et **dans un Job imbriqué** (le processus de test tourne déjà dans un Job : `IsProcessInJob` = vrai) ; (2) `taskkill /F /T` du runner **tue bien le petit-enfant orphelin** (le job a `KILL_ON_JOB_CLOSE`, sa poignée se ferme à la mort du runner), y compris lorsque le plugin est déjà mort et que `taskkill /T` ne peut plus suivre l'arbre ; (3) un worker de **un seul fichier, bibliothèque standard**, lancé **par chemin** par l'interpréteur du plugin, fonctionne dans un venv qui ne contient pas deskgate ; (4) l'arrêt propre du thread engine doit être branché sur le **`lifespan` d'Uvicorn (arrêt)** et non sur un `finally` après `server.run()`, car Uvicorn ré-émet le signal capturé (`signal.raise_signal`) avant le retour de `run()` et le processus est alors abandonné (code 3 observé en `CTRL_BREAK`).

La file SQLite se construit avec `isolation_level=None` + `BEGIN IMMEDIATE`/`COMMIT` explicites, valable de 3.11 à 3.14 (pas besoin de l'attribut `autocommit` de 3.12). `STRICT`, l'index unique partiel, `UPDATE … RETURNING`, `AUTOINCREMENT` en `STRICT` et les déclencheurs d'audit « ajout seul » sont vérifiés sur SQLite 3.45.1 et 3.50.4. Une connexion par requête coûte 1,3 ms ; une transaction `FULL` 2,6 ms : aucune raison de partager une connexion entre threads.

**Primary recommendation :** construire en 4 vagues — (1) `store` migration 1 + noyau pur (`states`, `outcome`, `worker_protocol`) + `jobobject` en parallèle ; (2) `deskgate_sdk` (worker mono-fichier stdlib) + faux plugins + `engine` testable par `tick()` ; (3) routes `/jobs` + câblage `runtime.serve` (recovery, thread, arrêt via lifespan) ; (4) e2e (`taskkill /F /T`, redémarrage, annulation, arrêt propre). Trois extensions mineures de config (`work_root`, `Capability.pythonpath`, `Capability.memory_mb` + `timeout_max ≤ 43200`) sont à planifier.

## Project Constraints (from CLAUDE.md)

- Français partout (documents, messages d'erreur, journaux, commits en français) ; identifiants de code, routes, champs JSON en anglais.
- Règle 1 : `src/deskgate/` n'importe jamais `deskgate_bim` ni IfcOpenShell (test AST existant) ; le cœur n'a aucun nom BIM.
- Règle 2 : pas de `shell=True`, pas de commande par concaténation (test AST existant `test_aucun_shell_true`).
- Règle 3 : un plugin ne tourne jamais dans le processus du runner ; Job Object créé suspendu, assigné, repris ; breakaway interdit.
- Règle 4 : tout chemin reçu converti puis validé contre `allowed_roots` (`..`, liens, jonctions) ; artefacts revalidés.
- Règle 5 : écoute `127.0.0.1`, jeton sur toutes les routes sauf `/health` (les nouvelles routes `/jobs` héritent du middleware Bearer sans rien faire).
- Règle 6 : secrets jamais dans journaux/audit ; `callback.url` (resumeUrl n8n) est un secret : stocké brut, jamais renvoyé, jamais dans `audit`/`job.log`.
- Règle 8 : déterminisme ; règle 9 : MIT, aucun code GPL.
- Tests obligatoires : arrêt de l'arbre au délai, `running` → `interrupted` au redémarrage.
- Commits `type(scope): sujet` ≤ 72 car., français ; `.arthemis/**` jamais mêlé au code ni à `.planning/`.
- Workflow GSD : modifications du dépôt uniquement via une commande GSD (le présent fichier est écrit par l'agent de recherche GSD).
- Skill de projet `gsd-file-manuelle` : toute étape humaine est classée bloquante (B1/B2/B3) ou différable au moment du plan. Pour cette phase, aucune action humaine n'est nécessaire (tout est automatisable) ; les vérifications visuelles n'existent pas. Le planificateur n'a donc a priori aucun `checkpoint` à créer.
- Pile : Python ≥ 3.11 (cibles 3.11 plancher, 3.14 dans le venv du dépôt), `ctypes` pour les Job Objects (pas `pywin32`), SQLite sans ORM.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `sqlite3` (stdlib) | SQLite 3.45.1 (Python 3.11.9) à 3.50.4 (3.14.4) | File, callbacks, audit | `STRICT`, `RETURNING`, index partiel vérifiés sur les deux |
| `ctypes` (stdlib) | — | Job Objects, `NtResumeProcess` | Décision projet (pas `pywin32`) ; recette validée phase 1 puis ici |
| `subprocess` (stdlib) | — | `Popen` avec `CREATE_SUSPENDED` | Voir Pattern 1 |
| `threading` (stdlib) | — | Thread `engine`, `Event` de réveil | D-07 |
| FastAPI / Uvicorn / Pydantic | 0.151.0 / 0.54.0 / 2.14 (déjà installés dans le venv, versions lues sur place) | Routes `/jobs`, modèles de requête | Déjà la pile du dépôt |
| `secrets` / `json` / `os` (stdlib) | — | `job_id`, JSON, `os.replace` | Rien à ajouter |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `psutil` | ≥ 7.2 (groupe dev, déjà présent) | Tests : aucun PID survivant | Tests `proc`/`e2e` seulement |
| `pytest-timeout` | ≥ 2.4 (déjà présent) | Garde-fou des tests de processus | `@pytest.mark.timeout(…)` sur tout test `proc`/`e2e` |
| `httpx2` | ≥ 2.15 (dev) | `TestClient` | Tests d'API |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `deskgate_sdk` = fichier lancé par chemin | Paquet `deskgate-sdk` installé dans chaque venv de plugin | Coût d'installation par venv, deux versions à synchroniser ; à reconsidérer en v0.2 (manifeste) |
| `ctypes` | `pywin32` | Déjà écarté (STACK.md) |
| Sondage 0,5 s | `WaitForMultipleObjects` / IOCP du Job | Complexité inutile à concurrence 1 ; le sondage suffit (D-07) |

**Installation :** aucune dépendance nouvelle (tout est stdlib ou déjà déclaré). Seul changement de packaging : `[tool.hatch.build.targets.wheel] packages = ["src/deskgate", "src/deskgate_sdk"]`.

**Vérification des versions :** versions lues dans le venv du dépôt (`uvicorn 0.54.0`, `fastapi 0.151.0`, `starlette 1.9.0`) ; aucune bibliothèque tierce n'est ajoutée par cette phase.

## Architecture Patterns

### Recommended Project Structure
```
src/
├── deskgate/
│   ├── core/
│   │   ├── states.py          # statuts, table des transitions, step(job, obs, now) pur
│   │   ├── outcome.py         # verdict terminal pur
│   │   ├── worker_protocol.py # modèles Pydantic d'input.json, events.jsonl, result.json (+ CONTRACT)
│   │   ├── jobspec.py         # (optionnel) validation de la requête, résolution du timeout, job_id
│   │   └── env.py             # (optionnel) build_env(allowlist, base) pur
│   ├── jobobject.py           # ctypes : create_job, spawn_in_job, terminate, active_processes, close
│   ├── store.py               # SEUL module sqlite3 : connect, migrate, submit, claim_next, finish, request_cancel, recover…
│   ├── engine.py              # Engine(store, cfg, spawner, clock, grace, poll) : tick(), run(), stop(), wake()
│   ├── jobs.py                # service : submit/get/cancel/read_logs (appelé par les routes)
│   └── api/routes_jobs.py     # routes minces
└── deskgate_sdk/
    ├── __init__.py            # vide (ou version)
    └── run.py                 # worker stdlib seule, exécutable PAR CHEMIN (python run.py --input …)
tests/
├── fake_plugins/deskgate_fakes.py   # sleep, spawn_orphan, bad_result, chatty, artifact_outside, exit_code
├── unit/ (states, outcome, worker_protocol, routes_jobs, sdk_contract)
├── fs/   (store, engine avec faux spawner)
├── proc/ (jobobject, engine réel avec faux plugins)
└── e2e/  (test_jobs.py : soumission-suivi-annulation, taskkill, redémarrage)
```

### Pattern 1: `spawn_in_job()` (vérifié 3.11.9 et 3.14.4)
**What :** création suspendue → assignation → reprise, sortie vers un fichier, env en liste blanche.
**Résultats d'expérience (HIGH) :**
- `Popen(creationflags=CREATE_SUSPENDED|CREATE_NO_WINDOW|CREATE_NEW_PROCESS_GROUP, stdin=DEVNULL, stdout=<fichier>, stderr=STDOUT, env=<liste blanche>, cwd=<work_dir>)` fonctionne ; le fichier ouvert par le parent peut être fermé juste après `Popen` (la poignée est dupliquée) ; le contenu UTF-8 (`é`) arrive intact avec `PYTHONUTF8=1`.
- `Popen` ferme la poignée du thread principal : seul `NtResumeProcess(poignée_processus)` reprend (voie déjà testée en phase 1, reconfirmée). `Popen._handle` existe en 3.11 et 3.14 (attribut privé : l'encadrer d'un `getattr`/`# type: ignore`).
- **Job imbriqué** : le processus de test (et donc pytest) est déjà dans un Job (`IsProcessInJob(GetCurrentProcess(), NULL)` = vrai) et `AssignProcessToJobObject` d'un nouveau job réussit (Windows ≥ 8). Même chose pour un runner lancé par le Planificateur. Si l'assignation échoue malgré tout : tuer le processus suspendu, tâche `failed` avec `error_code = "spawn_failed"`.
- Interpréteur d'un **venv** (lanceur-relais `Scripts\python.exe` qui lance le vrai Python) : l'exécution et le code de sortie sont corrects ; après sortie normale `ActiveProcesses` = 0.
- **Plafond mémoire** : `JOB_OBJECT_LIMIT_JOB_MEMORY` (0x200) + `JobMemoryLimit` (octets) : une allocation de 400 Mio sous un plafond de 100 Mio lève `MemoryError` dans le plugin (code 1). Plafond global du job (tous descendants), à préférer à `PROCESS_MEMORY`.
- `QueryInformationJobObject(JobObjectBasicAccountingInformation = 1)` → `ActiveProcesses` : après sortie du parent avec un orphelin vivant, vaut > 0 ; après `TerminateJobObject` vaut 0 en ~2 ms. **Mais `Popen.poll()` vaut encore `None` juste après `TerminateJobObject`** : appeler `p.wait(timeout=5)` avant de lire `result.json` ou de conclure. Le code de sortie est celui passé à `TerminateJobObject` (1).
- Le compte `ActiveProcesses` initial peut dépasser le nombre de processus attendus (lanceurs) : les tests comparent à **0** après terminaison, jamais à un compte exact.
- Piège constaté : chemins **absolus** partout (mon premier essai avait un script relatif avec `cwd` différent : « can't open file »). `spawn_in_job` reçoit `cwd`/`argv` absolus.
- Poignée du Job : `CreateJobObjectW(None, None)` (non héritable). Fermer la poignée en fin de tâche (après `TerminateJobObject`) ; `KILL_ON_JOB_CLOSE` couvre la mort du runner.
**Env en liste blanche (fonctionne) :** `SYSTEMROOT, SYSTEMDRIVE, WINDIR, PATH, PATHEXT, COMSPEC, TEMP, TMP, USERPROFILE, LOCALAPPDATA, APPDATA, PROGRAMDATA, PROGRAMFILES, PROGRAMFILES(X86), COMPUTERNAME, USERNAME, NUMBER_OF_PROCESSORS, PROCESSOR_ARCHITECTURE, HOMEDRIVE, HOMEPATH` + `PYTHONUTF8=1` (un secret `SECRET_X` posé dans l'environnement du parent n'est **pas** vu par l'enfant : vérifié). `os.environ` met les clés en majuscules sous Windows, donc la recherche par nom majuscule suffit. `SYSTEMROOT` est indispensable (sans lui, Python/sockets échouent). Prévoir un paramètre `extra_env` (threads, mémoire : phase 4).
**Interface :** `JobHandle(int)` avec `terminate(code=1)`, `active_processes()`, `close()` ; `create_job(memory_mb: int | None = None)`, `spawn_in_job(job, argv, *, cwd, log_path, env) -> Popen`. Seul module avec `ctypes` (hors `core/`, test AST déjà en place).

### Pattern 2: SQLite — transactions, claim, transition terminale (vérifié 3.11.9 / 3.14.4)
**Connexion :** `sqlite3.connect(path, isolation_level=None, timeout=5.0)` (+ `PRAGMA synchronous=FULL; busy_timeout=5000; foreign_keys=ON` **à chaque connexion** ; `journal_mode=WAL` persistant, posé une fois dans `migrate`). `isolation_level=None` = pas de transaction implicite : on écrit `BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK` explicitement. Fonctionne à l'identique en 3.11 et 3.14 (en 3.14 `conn.autocommit` vaut `-1`, mode hérité : ne pas y toucher). Un `contextmanager` `store.tx(conn)` (BEGIN IMMEDIATE, COMMIT, ROLLBACK sur exception) évite les oublis.
**Threads :** `check_same_thread` laissé à `True` (la lecture depuis un autre thread lève `ProgrammingError`, vérifié). API : une connexion **par requête** (1,3 ms ouverture + pragmas, 2,6 ms par transaction `FULL`, mesurés) via une dépendance FastAPI `def` ; engine : sa propre connexion ouverte dans son thread.
**Pièges vérifiés :** (a) `RETURNING` : faire `.fetchall()` avant `COMMIT` ; (b) une transaction `DEFERRED` qui lit puis écrit échoue **immédiatement** (`database is locked`, 0,00 s) quand un autre écrivain est passé, d'où `BEGIN IMMEDIATE` systématique ; (c) 6 threads qui réclament en même temps : un seul gagne.
**Schéma proposé (migration 1)** — `seq` donne l'ordre de soumission, `id` l'identifiant public :
```sql
CREATE TABLE jobs (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE,
  capability TEXT NOT NULL,
  params_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued','running','succeeded','failed','timeout','cancelled','interrupted')),
  cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0,1)),
  timeout_s INTEGER NOT NULL CHECK (timeout_s > 0),
  progress_pct REAL, progress_message TEXT,
  result_json TEXT,                 -- résumé + artefacts validés (chemins conteneur)
  error_code TEXT, error_message TEXT,
  resource TEXT NOT NULL,
  idempotency_key TEXT,
  callback_url TEXT NOT NULL,       -- brute, jamais exposée
  work_dir TEXT NOT NULL,
  created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT   -- UTC ISO-8601 « …Z »
) STRICT;
CREATE UNIQUE INDEX jobs_idem ON jobs(capability, idempotency_key)
  WHERE status IN ('queued','running');          -- NULL multiples permis (vérifié)
CREATE INDEX jobs_status_seq ON jobs(status, seq);
CREATE TABLE callbacks (
  job_id TEXT NOT NULL UNIQUE REFERENCES jobs(id),
  state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN
    ('pending','delivered','delivered_duplicate','abandoned_stale','abandoned_rejected','abandoned_exhausted')),
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TEXT NOT NULL, not_before TEXT NOT NULL,
  last_status INTEGER, last_error_redacted TEXT
) STRICT;
CREATE TABLE audit (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, event TEXT NOT NULL,
  job_id TEXT, detail_json TEXT) STRICT;
CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT,'audit en ajout seul'); END;
CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT,'audit en ajout seul'); END;
PRAGMA user_version = 1;
```
(`STRICT` + `AUTOINCREMENT` + déclencheurs `RAISE(ABORT)` vérifiés : `UPDATE`/`DELETE` sur `audit` lèvent `IntegrityError`.) `migrate(conn)` : lit `user_version`, applique les scripts de `MIGRATIONS[v:]` chacun dans `BEGIN IMMEDIATE … PRAGMA user_version=N … COMMIT` (le `PRAGMA user_version` dans la transaction est vérifié) ; base plus récente que le code → refus de démarrer avec un message français.
**Claim (une seule instruction, vérifié) :**
```sql
UPDATE jobs SET status='running', started_at=?
 WHERE id = (SELECT id FROM jobs WHERE status='queued' ORDER BY seq LIMIT 1)
   AND NOT EXISTS (SELECT 1 FROM jobs WHERE status='running')
RETURNING *;
```
Concurrence par ressource (v0.2) : remplacer le `NOT EXISTS` par un compte par `resource`. Phase 2 : concurrence globale 1 (D-02/JOB-02).
**Soumission (JOB-08) :** dans **une** `BEGIN IMMEDIATE` : `SELECT id … WHERE capability=? AND idempotency_key=? AND status IN ('queued','running')` → si trouvé, 409 avec ce `job_id` ; sinon `INSERT` (l'index partiel est le filet de sécurité). Après l'état terminal, la même clé est de nouveau acceptée (vérifié).
**Transition terminale (D-11) :** `finish(job_id, from_status, to_status, …)` : `UPDATE jobs SET status=?, finished_at=?, result_json=?, error_code=?, error_message=? WHERE id=? AND status=?` → `if cur.rowcount != 1: ROLLBACK` + `INSERT INTO callbacks(job_id, state, next_attempt_at, not_before) VALUES (?, 'pending', now, now+2 s)` + `INSERT INTO audit(...)`, tout dans la même transaction. Même fonction pour `queued → cancelled`, `running → *`, `running → interrupted`.
**Annulation (JOB-04) :** `request_cancel(job_id)` en **une** `BEGIN IMMEDIATE` : lire le statut ; `queued` → transition terminale `cancelled` directe ; `running` → `UPDATE … SET cancel_requested=1` (+ audit) ; terminal → ne rien faire, renvoyer l'état. L'atomicité évite la course « la tâche vient d'être réclamée par l'engine ».
**Recovery (D-12) :** `UPDATE jobs SET status='interrupted', finished_at=?, error_code='runner_restarted', error_message='…' WHERE status='running' RETURNING id` puis, **dans la même transaction**, un `INSERT callbacks` + `INSERT audit` par id. Les tâches `queued` restent `queued` et seront exécutées au démarrage de l'engine.

### Pattern 3: Thread engine (et réveil)
- **Boucle fine, `tick()` public.** `Engine.tick(now_mono)` fait un tour complet (réclamer si rien ne tourne, observer, appliquer `step()`) : testable **sans thread** avec un faux spawner et une horloge injectée ; `run()` n'est que `while not stop: wake.wait(poll); wake.clear(); tick()`.
- **Réveil :** l'API fait `engine.wake()` (`threading.Event.set()`) après le `COMMIT` d'une soumission ou d'une demande d'annulation. L'engine fait `wait(0.5)`, puis `clear()` **avant** de lire la base : un `set()` perdu est impossible (la lecture suit le commit), un `set()` arrivé pendant le tour laisse l'événement levé pour le tour suivant.
- **Réglages injectables :** `poll=0.5`, `grace=10.0`, `clock=time.monotonic`, `wall=utcnow`, `spawner=spawn_in_job` ; les tests `proc` utilisent `poll=0.05`, `grace=1.0`.
- **Tour (état en mémoire : `Running{job, proc, jobobj, deadline, cancel_sent_at, events_off}`) :**
  1. rien ne tourne → `claim_next()` ; créer `work_dir`, écrire `input.json`, `spawn_in_job` ; échec de lancement → `finish(failed, spawn_failed)` ; `deadline = clock() + timeout_s`.
  2. observer **dans cet ordre** : `rc = proc.poll()` d'abord, puis l'échéance, puis `cancel_requested` relu en base.
  3. lire `events.jsonl` par offset (progression → colonne `progress_*` ; **au plus une écriture par tour**) ; si `cancel_requested` et pas encore envoyé → écrire `cancel.flag`, `cancel_sent_at = now`.
  4. `step(job, obs, now)` décide ; actions possibles : `WriteCancelFlag`, `TerminateJob`, `Finalize(status, error)`.
  5. Avant d'évaluer un résultat : `TerminateJobObject` (orphelins), `proc.wait(5)`, puis lire `result.json` (plafonné, p. ex. 1 Mio + 1 octet, JSON strict), revalider les artefacts, `finish()`, fermer la poignée du Job.
- **Robustesse :** `try/except` **par tâche** dans le tour (exception → `failed` + audit, le thread continue) ; si le thread meurt malgré tout : `server.should_exit = True` (le runner s'arrête, la Planificateur le relance, la recovery rend cela sans danger). Battement exposé dans `/health` : facultatif en phase 2.
- **Arrêt propre :** voir Pitfall 1 (hook `lifespan`). `stop()` = `Event.set()` + `TerminateJobObject` de la tâche en cours (le statut reste `running` en base : la recovery au prochain démarrage fait le travail, un seul chemin de code). Thread `daemon=True` (sécurité si le processus sort sans `lifespan`).

### Pattern 4: `core/states.step()` et `core/outcome` (purs)
```python
@dataclass(frozen=True)
class Observation:
    exit_code: int | None          # None = processus vivant
    cancel_requested: bool
    cancel_sent_at: float | None   # monotone, None si pas encore envoyé
    deadline: float                # monotone
    result: ResultCheck | None     # None tant que non lu ; sinon valid/invalid/absent + artefacts ok

def step(job: JobView, obs: Observation, now: float, grace: float) -> Decision: ...
```
Règles à écrire **et tester** (table) :
| Situation observée dans le tour | Décision |
|---|---|
| processus sorti, `cancel_requested` | `cancelled` (même si le résultat est valide ; D-07) |
| processus sorti, pas d'annulation (même si `now > deadline` dans ce même tour) | verdict par `outcome` : code 0 **et** résultat valide **et** artefacts valides → `succeeded`, sinon `failed` |
| vivant, `cancel_requested`, drapeau pas encore écrit | `WriteCancelFlag` |
| vivant, `cancel_sent_at` et `now - cancel_sent_at ≥ grace` | `TerminateJob`, puis `cancelled` |
| vivant, pas d'annulation, `now ≥ deadline` | `TerminateJob`, puis `timeout` |
| vivant, annulation demandée **et** échéance atteinte pendant la grâce | `cancelled` l'emporte (annulation demandée avant) |
**Choix déterministes (à figer dans les tests de course) :** l'ordre d'observation est `poll()` puis échéance : « délai atteint en même temps que la fin normale » donne `succeeded` si le processus est déjà sorti à l'instant du `poll()`, sinon `timeout`. Une sortie observée pendant la grâce → `cancelled` sans `TerminateJobObject` supplémentaire autre que le nettoyage systématique.
`outcome` : fonction pure `(exit_code, result_state, artifacts_ok, cancel_requested, timed_out) -> (status, error_code)`. Codes d'erreur stables proposés : `nonzero_exit`, `missing_result`, `invalid_result`, `result_too_large`, `artifact_outside_roots`, `plugin_error` (le worker a écrit `ok:false`), `spawn_failed`, `engine_error`, `runner_restarted`, `timeout`, `cancelled`.

### Pattern 5: Soumission, dossier de travail, formes d'API
**Dossier de travail (JOB-09, D-04) :** racine `work_root` (nouvelle clé `RunnerConfig.work_root: str | None`, défaut `<allowed_roots[0]>/travail`, **doit être sous une racine autorisée**, validée par `normalize_host_path`/`is_under`) ; `work_dir = <work_root>/<job_id>/`, créé par l'engine au lancement (`mkdir(parents=True, exist_ok=False)`), jamais purgé. Le `job_id` n'est que de l'hex minuscule : aucun risque de traversée. Au `GET /jobs/{id}/logs` et partout, le `job_id` de l'URL est validé par motif `^[0-9a-f]{12}$` avant tout accès disque (sinon 404 `job_not_found`).
**`job_id` :** `secrets.token_hex(6)` (12 hex ; 48 bits ; unicité garantie par `UNIQUE`, un `IntegrityError` rare → nouveau tirage). Pas d'ULID : l'ordre vient de `seq`.
**`POST /jobs` (corps)** — modèle Pydantic, `extra="forbid"` :
```json
{ "capability": "demo.sleep", "params": {"n": 5},
  "callback": {"url": "http://localhost:5678/webhook-waiting/12?signature=…"},
  "idempotency_key": "wf12-exec345", "timeout": 1800 }
```
`params` : objet JSON (défaut `{}`) ; `idempotency_key` : 1 à 128 caractères ; `timeout` : entier ≥ 1, absent → `min(7200, timeout_max_capacité)` (voir Open Questions 1) ; `callback.url` : requis, chaîne `http(s)://…`, ≤ 2048 caractères, **non renvoyée**.
Réponses : `202 {"job_id","status":"queued"}` ; 404 `capability_not_found` ; 409 `idempotency_conflict` avec `{"error":{"code","message","job_id":"<existant>"}}` (étendre `error_body(code, message, **extra)` ; le test phase 1 qui impose `set(error) == {code,message}` ne vise que ses routes de test) ; 422 `invalid_request` (format D-08 existant) ou `timeout_too_large`.
**`GET /jobs/{id}` (200) — forme recommandée :**
```json
{ "job_id": "a1b2c3d4e5f6", "capability": "demo.sleep", "status": "running",
  "cancel_requested": false,
  "progress": {"pct": 40.0, "message": "étape 2"},
  "summary": {}, "artifacts": [{"kind": "bcf", "path": "/data/travail/a1b2c3d4e5f6/conflits.bcf"}],
  "error": null,
  "created_at": "2026-10-20T12:00:00.123Z", "started_at": "…", "finished_at": null, "duration_s": null }
```
`error` = `{"code","message"}` ou `null`. Jamais `callback_url`, `params_json`, `work_dir` hôte brut (test par inspection du JSON complet : la valeur de `callback.url` n'apparaît nulle part dans la réponse). Les chemins d'artefacts sont renvoyés **au format conteneur** (`host_to_container`).
**`GET /jobs/{id}/logs` :** paramètres `offset` (octets, défaut 0), `limit` (octets, défaut 65536, max 1048576) ou `tail` (octets finaux, exclusif avec `offset`) ; réponse `200 {"text": "...", "offset": 0, "next_offset": 1234, "size": 1234, "complete": true}` où `complete` = `status` terminal **et** `next_offset == size`. Lecture binaire du `job.log`, décodage `errors="replace"`, passage dans `redact_signature` (fonction unique du projet). Fichier absent (tâche `queued`) → `text: ""`, `size: 0`. Lecture pendant l'écriture du plugin vérifiée (partage Windows par défaut de Python).
**`POST /jobs/{id}/cancel` :** 200 avec la même forme que `GET /jobs/{id}` (idempotent, y compris sur tâche terminale) ; 404 `job_not_found`.

### Pattern 6: Démarrage et arrêt (`runtime.serve`)
Ordre : config → mutex → socket → `open_db` + `migrate` → **recovery** → construire `Engine`, `jobs` service, `create_app(..., services=…, on_shutdown=engine.stop)` → `engine.start()` (thread) → `server.run(sockets=[sock])`. `create_app` garde sa signature actuelle comme valeur par défaut (les tests phase 1 appellent `create_app(token_sha256=…, version=…)` sans services) : n'inclure `routes_jobs` que si `services` est fourni.

### Anti-Patterns to Avoid
- **Brancher l'arrêt de l'engine après `server.run()`** : non exécuté sur `CTRL_BREAK`/`SIGTERM` (voir Pitfall 1).
- **Lire `result.json` avant la fin du processus ou ouvrir un fichier du worker en écriture exclusive** : `os.replace` du worker échoue (PermissionError, expérience 5).
- **Une connexion SQLite partagée entre threads (`check_same_thread=False`)** ; **transactions `DEFERRED`** qui lisent puis écrivent.
- **`os.environ.copy()` pour le plugin** (fuite de secrets, variables `DESKGATE_*`).
- **Écrire le statut terminal hors transaction** ou en deux étapes (perte du rappel).
- **Journaliser/audit `callback_url` ou `params`** (règle 6) : l'audit de phase 2 ne contient que `event`, `job_id`, un `detail_json` minimal (statut, code d'erreur).
- **Compter sur `taskkill /T` pour l'arbre du plugin** : il ne suit pas les orphelins ; seul le Job le fait.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Arrêt d'un arbre de processus | Parcours `psutil.children()` | `TerminateJobObject` | Rate les orphelins (vérifié : l'orphelin meurt avec le Job) |
| Réclamation atomique de la prochaine tâche | `SELECT` puis `UPDATE` en deux temps | `UPDATE … WHERE id=(SELECT …) AND NOT EXISTS(…) RETURNING *` | Atomique, vérifié à 6 threads concurrents |
| Unicité des clés d'idempotence | Verrou applicatif | Index unique partiel + contrôle dans la même transaction | Garanti par SQLite |
| Migrations | Alembic / ORM | `PRAGMA user_version` + scripts SQL numérotés | Décision STACK.md |
| Écriture atomique du résultat | Écriture directe de `result.json` | `.tmp` + `fsync` + `os.replace` avec réessais courts | Le lecteur ne voit jamais un fichier partiel ; réessais car antivirus/lecteur (PermissionError) |
| Masquage de `signature` | Nouvelle regex | `deskgate.core.redact.redact_signature` | Fonction unique du projet |
| Conversion/validation de chemins d'artefacts | Nouveau code | `core.paths.validate_artifact_path` | Déjà testé (jonctions, ADS, UNC) |
| Journaux d'une tâche | Table `job_logs`, tube (pipe) | Redirection vers `job.log` | Pas de blocage de tube, pas de second état |
| Format d'erreur HTTP | Nouveau gestionnaire | `error_body` / `install_handlers` (D-08 phase 1) | Cohérence ; étendre `error_body` avec champs optionnels |

**Key insight :** tout ce qui est « décidé » vit dans `core/` (fonctions pures testées avec horloge injectée) ; tout ce qui est « effet » est confiné à `store`, `jobobject`, `engine`, ce qui rend les courses (délai/fin normale, annulation/grâce) testables sans dormir.

## Runtime State Inventory

Non applicable (phase de construction, pas de renommage ni de migration de données existantes : « Stade : nouveau projet, aucun utilisateur »). La base de phase 1 ne contient que le squelette (aucune table) : `migrate` part de `user_version = 0`.

## Common Pitfalls

### Pitfall 1: l'arrêt de l'engine n'est pas exécuté après `server.run()`
**What goes wrong :** avec `CTRL_BREAK` (ou `SIGTERM`), `uvicorn.Server.run()` ré-émet le signal capturé (`signal.raise_signal`) à la sortie de `capture_signals`, puis le gestionnaire par défaut tue le processus : un `finally` placé après `server.run(...)` ne s'exécute **pas**.
**Vérifié (expérience 4) :** processus de test `uvicorn.Server.run` + thread + `try/finally` : après `CTRL_BREAK`, code de sortie 3, fichiers laissés par le `lifespan` (arrêt) et l'arrêt du thread **présents**, marqueur du `finally` **absent**. `Process.terminate()` (TerminateProcess) : rien ne s'exécute (cas du crash, couvert par la recovery).
**How to avoid :** passer à `create_app` un `lifespan` (asynccontextmanager) dont la partie après `yield` appelle `engine.stop()` ; garder `daemon=True` sur le thread ; le `finally` après `run()` reste utile pour `KeyboardInterrupt` mais ne doit pas être la seule voie.
**Warning signs :** test e2e « arrêt propre » où le plugin survit ou où `engine_stopped` n'est jamais écrit.

### Pitfall 2: `os.replace` du worker contre un lecteur
**What goes wrong :** `PermissionError [WinError 5]` si un autre processus (le runner, un antivirus) tient `result.json` ouvert (vérifié : lecteur Python ouvert → `os.replace` refusé ; destination absente → OK).
**How to avoid :** le runner n'ouvre `result.json` **qu'après** la sortie du processus ; le worker réessaie `os.replace` (10 essais, 50 ms croissant) ; l'ordre `fsync` puis `replace`.

### Pitfall 3: `Popen.poll()` encore `None` juste après `TerminateJobObject`
**What goes wrong :** lecture de `result.json`/statut avant la fin réelle du processus. Vérifié : `poll()` = `None` immédiatement, puis `wait` renvoie 1.
**How to avoid :** toujours `proc.wait(timeout=5)` après `TerminateJobObject`, et attendre `ActiveProcesses == 0` (boucle ≤ 5 s, pas de `sleep` fixe) dans les tests.

### Pitfall 4: `finally` croisés et fuite de poignées
**What goes wrong :** poignée de Job non fermée si `spawn_in_job` échoue après `Popen` (processus suspendu orphelin) ; `ResourceWarning` pour des `Popen` non attendus.
**How to avoid :** dans `spawn_in_job`, `except BaseException: p.kill(); p.wait(); raise` (déjà dans le prototype validé) ; `JobHandle.close()` appelé en `finally` côté engine.

### Pitfall 5: chemins relatifs et `cwd`
**What goes wrong :** « can't open file » (reproduit). **How to avoid :** `input.json`, script du worker, `cwd` : tous absolus ; `work_dir` passé en absolu dans `input.json`.

### Pitfall 6: sortie bavarde sans lecteur
**What goes wrong :** avec un tube, un plugin qui écrit beaucoup bloque. **How to avoid :** pas de tube (D-08) → redirection fichier ; test `chatty` (plusieurs Mio sur stdout et stderr) qui doit finir. Le fichier n'est pas plafonné en v0.1 (limite documentée, voir Open Questions 5).

### Pitfall 7: `ctx.log` dupliqué
**What goes wrong :** deux sources de journaux (`events.jsonl` et `job.log`) et un runner qui recopie. **How to avoid :** `ctx.log(msg)` écrit une ligne horodatée sur **stderr** (donc dans `job.log`, source unique de `/logs`) ; `events.jsonl` ne porte que `progress` et `artifact`.

### Pitfall 8: plugin qui ne rend pas la main sur l'annulation
**What goes wrong :** calcul natif (IfcOpenShell) qui ignore `cancel.flag`. **How to avoid :** grâce de 10 s puis `TerminateJobObject` (D-03) ; test `sleep` avec `ignore_cancel=true`.

### Pitfall 9: `Popen._handle` privé
**How to avoid :** isoler dans `jobobject` ; si l'attribut disparaît, repli `OpenProcess(PROCESS_SET_QUOTA|PROCESS_TERMINATE|PROCESS_SUSPEND_RESUME|SYNCHRONIZE, False, pid)` (non éprouvé ici ; le test `test_spawn_in_job` détecte toute casse).

### Pitfall 10: erreur 409 et test de format D-08 existant
**What goes wrong :** ajouter `job_id` dans `error` fait échouer un test qui impose `{code, message}` pour **toutes** les erreurs. **How to avoid :** vérifier `tests/unit/test_api_security.py` (la contrainte vise ses routes de test) ; mettre à jour le test si besoin et le consigner.

## Code Examples

### `spawn_in_job` (prototype exécuté sur 3.11 et 3.14)
```python
# Source : expériences locales 2026-10-20 (scratchpad exp1/exp2/exp6), promotion de tests/_support/winjob.py
def spawn_in_job(job: int, argv: list[str], *, cwd: str, log_path: str, env: dict[str, str]):
    with open(log_path, "ab") as log:           # fermé juste après Popen : la poignée est dupliquée
        p = subprocess.Popen(
            argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            creationflags=CREATE_SUSPENDED | CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
            close_fds=True)
    h = wintypes.HANDLE(int(p._handle))          # type: ignore[attr-defined]
    try:
        if not k32.AssignProcessToJobObject(job, h):
            raise ctypes.WinError(ctypes.get_last_error())
        if ntdll.NtResumeProcess(h) != 0:
            raise OSError("NtResumeProcess a échoué")
    except BaseException:
        p.kill(); p.wait(); raise
    return p
# create_job(memory_mb): LimitFlags = KILL_ON_JOB_CLOSE (0x2000) | JOB_MEMORY (0x200) si plafond ;
#   info.JobMemoryLimit = memory_mb * 1024 * 1024 ; SetInformationJobObject(job, 9, byref(info), sizeof(info))
# active_processes(job): QueryInformationJobObject(job, 1, byref(JOBOBJECT_BASIC_ACCOUNTING_INFORMATION)) -> .ActiveProcesses
```
Structure à ajouter à celle de `winjob.py` : `JOBOBJECT_BASIC_ACCOUNTING_INFORMATION` = `TotalUserTime, TotalKernelTime, ThisPeriodTotalUserTime, ThisPeriodTotalKernelTime (LARGE_INTEGER ×4), TotalPageFaultCount, TotalProcesses, ActiveProcesses, TotalTerminatedProcesses (DWORD ×4)`. Déclarer `argtypes`/`restype` de `QueryInformationJobObject` comme les autres appels.

### Worker `deskgate_sdk/run.py` (mono-fichier, stdlib seule ; exécuté PAR CHEMIN)
```python
# Lancé par : <python du plugin> <chemin>/deskgate_sdk/run.py --input <work_dir>/input.json
# Source : prototype exécuté dans un venv 3.11 SANS deskgate (expérience 2) : succès, erreur, événements lus par offset
import importlib, json, os, sys, time, traceback
PROTOCOL = 1

def _replace(src, dst):                      # os.replace avec réessais (PermissionError : antivirus, lecteur)
    for i in range(10):
        try: os.replace(src, dst); return
        except PermissionError: time.sleep(0.05 * (i + 1))
    os.replace(src, dst)

def _write_atomic(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False); f.flush(); os.fsync(f.fileno())
    _replace(tmp, path)

class Ctx:                                    # ctx.log -> stderr (job.log) ; progress/artifact -> events.jsonl
    def __init__(self, inp):
        self.job_id, self.work_dir = inp["job_id"], inp["work_dir"]
        self._events = open(os.path.join(self.work_dir, "events.jsonl"), "ab", buffering=0)
        self._flag = os.path.join(self.work_dir, "cancel.flag"); self.artifacts = []
    def _emit(self, **ev): self._events.write((json.dumps(ev, ensure_ascii=False) + "\n").encode("utf-8"))
    def log(self, msg): print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)
    def progress(self, pct, msg=""): self._emit(type="progress", pct=float(pct), message=str(msg))
    def artifact(self, path, kind): self.artifacts.append({"kind": kind, "path": str(path)}); self._emit(type="artifact", kind=kind, path=str(path))
    def cancelled(self): return os.path.exists(self._flag)

def main(argv):
    sys.path.pop(0)                           # retire le dossier du script (pas de masquage de modules, sans option -P)
    with open(argv[argv.index("--input") + 1], encoding="utf-8") as f: inp = json.load(f)
    ctx, res = Ctx(inp), os.path.join(inp["work_dir"], "result.json")
    try:
        for p in reversed(inp.get("sys_path", [])): sys.path.insert(0, p)
        mod, _, fn = inp["entry"].partition(":")
        out = getattr(importlib.import_module(mod), fn)(inp["params"], ctx)
        if not isinstance(out, dict): raise TypeError("le plugin doit renvoyer un dict")
        _write_atomic(res, {"protocol": PROTOCOL, "ok": True, "summary": out.get("summary", {}),
                            "data": out.get("data", {}), "artifacts": out.get("artifacts") or ctx.artifacts})
        return 0
    except BaseException as exc:
        traceback.print_exc()
        _write_atomic(res, {"protocol": PROTOCOL, "ok": False,
                            "error": {"type": type(exc).__name__, "message": str(exc)[:2000]}})
        return 1
if __name__ == "__main__": sys.exit(main(sys.argv))
```
Le prototype d'expérience traitait `ctx.log` dans `events.jsonl` ; la version recommandée ci-dessus l'envoie sur stderr (Pitfall 7). **Emplacement du chemin :** côté runner, `Path(deskgate_sdk.__file__).parent / "run.py"` (le runner importe `deskgate_sdk` : même wheel, donc toujours présent). Ligne de commande : `[cap.python, "-X", "utf8", <run.py>, "--input", <input.json>]` (aucun `-P`, qui n'existe qu'à partir de 3.11 : le `sys.path.pop(0)` fait le travail et supporte un venv de plugin plus ancien). `input.json` : `{protocol, job_id, capability, entry, params, work_dir, sys_path}`.

### Lecture incrémentale de `events.jsonl` (vérifiée, lecteur ouvert pendant que le worker écrit)
```python
def read_events(path: Path, offset: int) -> tuple[list[dict], int]:
    try:
        with open(path, "rb") as f:               # le partage par défaut de Python autorise lecture + écriture simultanées
            f.seek(offset); data = f.read(1_048_576)
    except FileNotFoundError:
        return [], offset
    end = data.rfind(b"\n")
    if end < 0: return [], offset                  # ligne encore incomplète : on attend
    events = []
    for line in data[: end + 1].splitlines():
        try: events.append(json.loads(line))
        except json.JSONDecodeError: log.warning("ligne d'événement invalide ignorée")
    return events, offset + end + 1
```
(Vérifié : le lecteur voit `b'{"a":1}\n{"b"'` puis le reste ; il ne consomme que jusqu'au dernier `\n`.) Valider chaque événement avec `worker_protocol` (Pydantic) ; ignorer sinon.

### Arrêt propre branché sur le `lifespan` (vérifié : s'exécute sur CTRL_BREAK)
```python
@contextlib.asynccontextmanager
async def lifespan(app):
    yield
    on_shutdown()          # engine.stop() : Event.set(), TerminateJobObject de la tâche en cours, join(5)
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
```

### Transaction terminale (D-11)
```python
def finish(conn, job_id, from_status, to_status, *, result_json, error, now):
    with tx(conn):                                         # BEGIN IMMEDIATE ... COMMIT / ROLLBACK
        cur = conn.execute(
            "UPDATE jobs SET status=?, finished_at=?, result_json=?, error_code=?, error_message=? "
            "WHERE id=? AND status=?", (to_status, now, result_json, error.code, error.message, job_id, from_status))
        if cur.rowcount != 1:
            raise StaleTransition(job_id)                  # ROLLBACK par tx() ; rien d'autre écrit
        conn.execute("INSERT INTO callbacks(job_id, next_attempt_at, not_before) VALUES (?,?,?)", (job_id, now, now_plus_2s))
        conn.execute("INSERT INTO audit(ts, event, job_id, detail_json) VALUES (?,?,?,?)", (now, f"job.{to_status}", job_id, "{}"))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `CTRL_BREAK_EVENT` pour arrêter poliment | Sentinelle `cancel.flag` + grâce + `TerminateJobObject` | Décision D-03, pitfall P7 | Aucun signal console |
| `isolation_level` implicite / `autocommit` (3.12+) | `isolation_level=None` + `BEGIN IMMEDIATE` explicites | Vérifié 3.11 → 3.14 | Un seul code pour toutes les versions |
| Job non imbriqué (Windows < 8) | Jobs imbriqués natifs (≥ Windows 8) | Windows 8 | Un runner lancé dans un Job (Planificateur, pytest) peut créer le sien |
| `python -m paquet` dans le venv du plugin | Worker mono-fichier lancé par chemin | Choix v0.1 | Aucun besoin d'installer deskgate dans le venv du plugin |

**Deprecated/outdated :** `tests/_support/winjob.py` (aide de spike, à remplacer par `deskgate.jobobject` ; conserver uniquement `is_alive` côté tests, par exemple dans `tests/_support/procs.py`, ou utiliser `psutil.pid_exists`/`psutil.Process.is_running`).

## Open Questions

1. **Délai par défaut quand `timeout_max` de la capacité est inférieur à 7200 s**
   - Connu : D-01 fixe 2 h par défaut, plafond par capacité.
   - Flou : le défaut dépasserait le plafond.
   - Recommandation : `timeout = min(7200, capability.timeout_max)` ; consigner dans le plan (discrétion du planificateur).
2. **`callback.headers`** (présent dans l'exemple d'`ARCHITECTURE.md` §6)
   - Connu : D-13 ne parle que de `callback.url` ; aucun emplacement de stockage en migration 1.
   - Flou : un client qui envoie `headers` recevrait 422 avec `extra="forbid"`.
   - Recommandation : accepter uniquement `url` en phase 2 (422 sinon, message français) ; les en-têtes (potentiels secrets) arrivent en phase 3 avec leur stockage et leur masquage.
3. **Extensions de config** (modèles Pydantic stricts existants dans `core/config.py`)
   - `RunnerConfig.work_root` (défaut sous la première racine), `Capability.pythonpath: list[str] = []` (dossiers préfixés à `sys.path` par le worker, **indispensable** pour les faux plugins de test et utile pour un plugin non installé), `Capability.memory_mb: int | None`, et `Capability.timeout_max` borné à `le=43200` (D-01). Recommandation : les ajouter en première vague avec leurs tests de configuration et mettre à jour `runner.example.toml`.
4. **Surveillance de l'engine dans `/health`**
   - Recommandation : facultatif ; si le temps manque, laisser à la phase 3.
5. **Taille de `job.log`**
   - Connu : aucune purge ni plafond en v0.1 (D-04) ; un plugin bavard peut remplir le disque.
   - Recommandation : documenter la limite ; la route `/logs` plafonne la lecture, pas l'écriture.
6. **Plugin interpréteur absent ou invalide**
   - Recommandation : détecté au lancement (`spawn_failed`) plutôt qu'à la soumission ; une vérification `Path(python).is_file()` à la soumission est un plus, non requis.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 (venv du dépôt) | Tests, runner | ✓ | 3.14.4 | — |
| Python 3.11 (`py -3.11`) | Plancher du projet | ✓ | 3.11.9 | — |
| SQLite (stdlib) | store | ✓ | 3.45.1 (3.11) / 3.50.4 (3.14) | — |
| Windows 11 (Job Objects imbriqués, `taskkill`) | `jobobject`, e2e | ✓ | 10.0.26200 | — |
| `taskkill` | e2e `kill_tree` | ✓ | système | — |
| psutil, pytest-timeout, httpx2 | Tests | ✓ | groupe `dev` (installés) | — |
| uv | Environnements | ✓ | 0.12.17 (venv créé par uv) | — |
| Docker / n8n / IfcOpenShell | — | non requis | — | Hors phase (faux plugins) |

**Missing dependencies with no fallback :** aucune.
**Missing dependencies with fallback :** aucune. Note : un venv de plugin « sans deskgate » a été créé avec `py -3.11 -m venv` (aucun `uv python install`) : la même technique convient pour un test `proc` d'un plugin hors venv du runner (facultatif : le chemin d'exécution est identique).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1 + pytest-timeout ≥ 2.4 + `fastapi.testclient` (httpx2) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (marqueurs `unit`, `fs`, `proc`, `e2e` déjà déclarés, `--strict-markers`) |
| Quick run command | `uv run pytest -m unit -q -x` |
| Full suite command | `uv run pytest -m "not e2e" -q` puis `uv run pytest -m e2e -q` (+ `uv run ruff check`, `uv run pyright`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| JOB-01 | `POST /jobs` → 202 `{job_id,status:"queued"}` ; 404 capacité inconnue ; 422 `timeout_too_large` / corps invalide ; `callback.url` absente → 422 | unit (TestClient + store sur fichier temporaire) | `uv run pytest tests/unit/test_routes_jobs.py -x` | ❌ Wave 0 |
| JOB-02 | Ordre de soumission, une tâche à la fois, claim atomique (6 threads → 1 gagnant) | fs | `uv run pytest tests/fs/test_store_queue.py -x` | ❌ Wave 0 |
| JOB-02 | Engine enchaîne deux tâches dans l'ordre (faux spawner, horloge injectée) | fs | `uv run pytest tests/fs/test_engine_tick.py -x` | ❌ Wave 0 |
| JOB-03 | `GET /jobs/{id}` (forme, `callback_url` absente de tout le JSON) ; `/logs` offset/tail/`complete` ; `job_id` invalide → 404 | unit | `uv run pytest tests/unit/test_routes_jobs.py -x` | ❌ Wave 0 |
| JOB-04 | Cancel `queued` → `cancelled` immédiat + callback + audit ; idempotence sur terminal ; cancel `running` : `cancel.flag` puis `cancelled` | fs + proc | `uv run pytest tests/fs/test_store_cancel.py tests/proc/test_engine_cancel.py -x` | ❌ Wave 0 |
| JOB-04 | Plugin ignorant l'annulation : `TerminateJobObject` après la grâce (`grace=1.0`) ; annulation pendant la grâce ; course cancel/fin normale | unit (`step`) + proc | `uv run pytest tests/unit/test_states.py tests/proc/test_engine_cancel.py -x` | ❌ Wave 0 |
| JOB-05 | Délai dépassé → `timeout` et orphelin (`spawn_orphan`) mort (`ActiveProcesses==0`, PID absent) | proc | `uv run pytest tests/proc/test_engine_timeout.py -x` | ❌ Wave 0 |
| JOB-05 | Course délai / fin normale (table de `step`, ordre `poll` puis échéance) | unit | `uv run pytest tests/unit/test_states.py tests/unit/test_outcome.py -x` | ❌ Wave 0 |
| JOB-06 | `recover_interrupted` : `running → interrupted` + 1 ligne `callbacks` `pending` + audit, une transaction ; `queued` inchangé | fs | `uv run pytest tests/fs/test_store_recovery.py -x` | ❌ Wave 0 |
| JOB-06 | `taskkill /F /T` du runner pendant une tâche à petit-enfant → redémarrage → `interrupted`, aucun PID survivant, `work_dir` conservé | e2e | `uv run pytest tests/e2e/test_jobs_restart.py -x` | ❌ Wave 0 |
| JOB-07 | `spawn_in_job` : suspendu puis repris, env liste blanche (secret absent, `PYTHONUTF8=1`), sortie dans `job.log` sans tube, Job imbriqué, plafond mémoire, `ActiveProcesses` | proc | `uv run pytest tests/proc/test_jobobject.py -x` | ❌ Wave 0 (remplace `test_spike_jobobject.py`) |
| JOB-07 | Aucun `shell=True`, `core/` sans `ctypes`/`sqlite3`/`subprocess`, `deskgate_sdk` stdlib seule | unit (AST) | `uv run pytest tests/architecture -x` | ✅ à étendre |
| JOB-08 | Même `(capability, idempotency_key)` non terminale → 409 + `job_id` existant ; clé réutilisable après état terminal ; clés NULL multiples | unit + fs | `uv run pytest tests/unit/test_routes_jobs.py tests/fs/test_store_queue.py -x` | ❌ Wave 0 |
| JOB-09 | `work_dir` créé sous `work_root`, contient `input.json`/`job.log` ; artefact valide renvoyé en chemin conteneur ; `artifact_outside` → `failed` ; `bad_result` → `failed` ; `chatty` ne bloque pas | proc | `uv run pytest tests/proc/test_engine_results.py -x` | ❌ Wave 0 |
| (transverse) | Contrat `worker_protocol` du cœur = contrat dupliqué du SDK | unit | `uv run pytest tests/unit/test_sdk_contract.py -x` | ❌ Wave 0 |
| (transverse) | Arrêt propre `CTRL_BREAK` : engine arrêté, plugin tué, redémarrage → `interrupted` | e2e | `uv run pytest tests/e2e/test_jobs_shutdown.py -x` | ❌ Wave 0 (recommandé) |
| (transverse) | Soumission → suivi → annulation par HTTP réel sur port libre | e2e | `uv run pytest tests/e2e/test_jobs_flow.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit :** `uv run pytest -m unit -q -x` + `uv run ruff check`
- **Per wave merge :** `uv run pytest -m "not e2e" -q` + `uv run pyright`
- **Phase gate :** suite complète (e2e compris) verte avant `/gsd:verify-work`
- Tous les tests `proc`/`e2e` portent `@pytest.mark.timeout(…)` (30 à 90 s) ; les paramètres `poll=0.05`, `grace=1.0`, `timeout=2` rendent chaque test `proc` < 10 s.

### Wave 0 Gaps
- [ ] `tests/fake_plugins/deskgate_fakes.py` — `sleep` (`n`, `ignore_cancel`), `spawn_orphan` (petit-enfant `sleep 120`, PID écrit dans `work_dir`), `bad_result` (résultat invalide / absent / non-dict), `chatty` (plusieurs Mio sur stdout et stderr), `artifact_outside` (chemin hors racines), `exit_code`
- [ ] `tests/e2e/conftest.py` : `write_config` étendu pour émettre `[capabilities.<id>]` (`python = sys.executable`, `pythonpath = [tests/fake_plugins]`) et `work_root` ; fixture de soumission HTTP
- [ ] `tests/_support/` : remplacer `winjob.py` par `procs.py` (`is_alive`, `wait_dead`) après promotion ; adapter `tests/proc/test_spike_jobobject.py` (importer `deskgate.jobobject`)
- [ ] Fixtures partagées : base temporaire + `Engine` à horloge injectée (`tests/fs/conftest.py`)
- [ ] Extension du test AST : `deskgate_sdk/*` n'importe que la bibliothèque standard (liste blanche), `jobobject` seul module `ctypes`, `store` seul module `sqlite3`
- [ ] Aucune installation de framework : pytest et plugins déjà déclarés

## Sources

### Primary (HIGH confidence)
- Expériences locales (scratchpad, 2026-10-20), Windows 11 10.0.26200, Python 3.11.9 et 3.14.4 : `exp1` (spawn/env/mémoire/accounting, Job imbriqué), `exp2` (worker mono-fichier dans un venv 3.11 sans deskgate, lecture par offset), `exp3` + `exp9` (SQLite : STRICT, index partiel, RETURNING, BEGIN IMMEDIATE, threads, DEFERRED, AUTOINCREMENT, déclencheurs), `exp4` (Uvicorn : arrêt, `CTRL_BREAK`), `exp5` (`os.replace` et lecteur), `exp6` (`taskkill /F /T` du runner : orphelin tué, avec runner en Python de base et en venv), `exp7` (coûts de connexion/transaction), `exp8` (`TerminateJobObject`, `poll`/`wait`)
- Code source installé : `.venv/Lib/site-packages/uvicorn/server.py` (`HANDLED_SIGNALS`, `capture_signals`, `raise_signal` après arrêt)
- Dépôt : `src/deskgate/**`, `tests/**`, `ARCHITECTURE.md` §3, §4, §6, §7, `.arthemis/reports/llm-council-1.md`, `.planning/research/PITFALLS.md` (P2, P7, M1, M2), `.planning/phases/02-c-ur-d-ex-cution/02-CONTEXT.md`
- Documentation Microsoft (déjà citée dans STACK.md) : https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects (Jobs imbriqués, `KILL_ON_JOB_CLOSE`)

### Secondary (MEDIUM confidence)
- Aucune source web n'a été nécessaire : tous les comportements décisifs ont été reproduits localement.

### Tertiary (LOW confidence)
- Repli `OpenProcess` à la place de `Popen._handle` (Pitfall 9) : non éprouvé.
- Comportement de `time.monotonic` pendant la veille Windows (D-02) : limite documentée, non mesurée ici.

## Metadata

**Confidence breakdown:**
- Standard stack : HIGH — tout en stdlib ou déjà installé, versions lues dans le venv
- Architecture : HIGH — chaque brique risquée (Job imbriqué, claim SQLite, worker dans venv, arrêt Uvicorn, orphelin au `taskkill`) vérifiée par exécution
- Pitfalls : HIGH pour ceux reproduits (1, 2, 3, 5), MEDIUM pour 9 et 10 (prévention par raisonnement)
- Formes d'API : MEDIUM — recommandations de conception (discrétion du planificateur), non vérifiées contre le nœud n8n (phase 5)

**Research date:** 2026-10-20
**Valid until:** 2026-11-19 (30 jours ; pile stable). À réviser si Uvicorn ou FastAPI changent de mineure (le comportement de signal de l'arrêt est celui de uvicorn 0.54.0).

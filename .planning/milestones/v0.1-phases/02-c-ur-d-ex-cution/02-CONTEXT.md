# Phase 2: Cœur d'exécution - Context

**Gathered:** 2026-10-20
**Status:** Ready for planning

<domain>
## Phase Boundary

n8n peut soumettre une tâche (`POST /jobs` → 202), la suivre (`GET /jobs/{id}`, `/logs`), l'annuler
(`POST /jobs/{id}/cancel`). Le runner l'exécute une à la fois, dans l'ordre de soumission, dans un
sous-processus placé dans un Job Object, avec délai maximum, et ne perd jamais l'état après un arrêt
brutal (`running` → `interrupted` au redémarrage). Validé avec de faux plugins, sans IfcOpenShell.
Exigences : JOB-01 à JOB-09.

Hors phase : envoi du rappel HTTP, politique de réponse n8n, plafond de taille, masquage complet de
la `signature` et contenu complet de l'audit (phase 3) ; `ifc.clash`, `deskgate-bcf`, `mcp.call`
(phase 4) ; `deskgate init` (phase 5).

</domain>

<decisions>
## Implementation Decisions

### Délais
- **D-01:** Délai par défaut d'une tâche : **2 h** (7200 s) si la requête n'en donne pas. Plafond
  global absolu : **12 h** (43200 s). Chaque capacité déclare `timeout_max` dans
  `[capabilities.<id>]` (≤ 12 h). Une requête qui demande plus que le `timeout_max` de sa capacité
  est refusée (422, code `timeout_too_large`).
- **D-02:** L'échéance est mesurée en mémoire avec `time.monotonic()` ; non persistée (après
  redémarrage, la tâche est `interrupted`). La veille est une limite documentée en v0.1.

### Annulation
- **D-03:** Annulation coopérative : `jobs.cancel_requested = 1`, l'engine écrit `cancel.flag` dans
  le `work_dir`, le plugin le voit via `ctx.cancelled()`. **Délai de grâce : 10 s**, puis
  `TerminateJobObject`. Pas de `CTRL_BREAK`. Une tâche `queued` annulée passe directement
  `cancelled`. L'appel est idempotent (sur tâche terminale : 200 avec l'état actuel, pas d'erreur).

### Dossier de travail
- **D-04:** `C:/BIM/travail/<job_id>/` (racine `travail` configurable sous une racine autorisée)
  est **conservé** après la fin de la tâche ; aucune purge automatique en v0.1.
  Contenu : `input.json`, `events.jsonl`, `result.json`, `cancel.flag`, `job.log`, artefacts.

### Capacités (décision du conseil, validée)
- **D-05:** Les capacités sont lues dans `runner.toml` `[capabilities.<id>]` (`kind = "python"`,
  `python` = interpréteur, `entry` = `module:fonction`, `timeout_max`, `resource`). Le cœur ne
  contient aucun nom BIM. Les faux plugins de test sont déclarés de la même façon (config de test).
- **D-06:** Une capacité inconnue à la soumission → 404 `capability_not_found`. Les paramètres
  (`params`) sont validés comme objet JSON ; leur schéma propre arrive en v0.2 (manifeste). Tout
  paramètre de type chemin reste à la charge du plugin en v0.1, mais les artefacts déclarés sont
  revalidés par `core/paths` (hors racines → tâche `failed`).

### Architecture d'exécution (conseil d'approche, `.arthemis/reports/llm-council-1.md`)
- **D-07:** Un thread `engine` (sondage 0,5 s, `Popen.poll()`), seul écrivain des transitions
  `running → *`, applique une fonction pure `core/states.step(job, observation, now)`. Verdict pur
  `core/outcome` : sortie avant échéance sans annulation → `succeeded` seulement si code 0 **et**
  `result.json` valide **et** artefacts revalidés, sinon `failed` ; annulation demandée avant la
  sortie → `cancelled` ; échéance → `timeout`.
- **D-08:** Lancement unique `spawn_in_job()` (module `jobobject`, ctypes) : création suspendue,
  assignation, `NtResumeProcess`, `KILL_ON_JOB_CLOSE`, jamais `BREAKAWAY_OK`, sans shell, env en
  liste blanche avec `PYTHONUTF8=1`, sorties redirigées dans `job.log` (pas de pipe).
  `TerminateJobObject` systématique en fin de tâche.
- **D-09:** Fichiers = transport, jamais état. `events.jsonl` lu par offset jusqu'au dernier `\n` ;
  `result.json` (écrit `.tmp` puis `os.replace` par le worker) lu seulement après sortie du
  processus et `TerminateJobObject`, taille plafonnée. Petit SDK `deskgate_sdk` côté worker
  (`ctx.log`, `ctx.progress`, `ctx.artifact`, `ctx.cancelled`, écriture atomique du résultat) ; le
  contrat (`worker_protocol`) est dupliqué, pas importé du cœur, avec un test d'égalité.
- **D-10:** Schéma SQLite **migration 1 complète** (décision validée) : `jobs` (STRICT, CHECK des
  statuts, `capability`, `params_json`, `status`, `cancel_requested`, progression, `result_json`,
  `error`, `resource`, `idempotency_key`, `callback_url` brute jamais exposée, `work_dir`,
  horodatages UTC), index unique partiel `(capability, idempotency_key) WHERE status IN
  ('queued','running')` (conflit → 409 avec le `job_id` existant), `callbacks` (`job_id UNIQUE`,
  `state`, `attempts`, `next_attempt_at`, `not_before`, `last_status`, `last_error_redacted` ; pas de
  `payload_json`), `audit` (ajout seul), `PRAGMA user_version = 1`, WAL, `synchronous=FULL`,
  `busy_timeout=5000`, `BEGIN IMMEDIATE`. Seul `store` importe `sqlite3`.
- **D-11:** Toute transition terminale (y compris `queued → cancelled` et `running →
  interrupted`) se fait en **une** transaction : `UPDATE jobs ... WHERE status=...` (contrôle de
  `rowcount`) + `INSERT callbacks` (état `pending`) + `INSERT audit`. Le rappel n'est **pas envoyé**
  en phase 2 (pas de sender) ; la ligne existe.
- **D-12:** Recovery au démarrage, après le mutex et avant l'API : `running → interrupted` sans lire
  le disque (limite documentée : un `result.json` écrit juste avant le crash est perdu).
- **D-13:** `callback.url` est requis dans `POST /jobs`, stocké brut, jamais renvoyé par l'API
  (test). Le contrôle des hôtes autorisés (CB-05) et le masquage complet arrivent en phase 3.

### Claude's Discretion
- Forme exacte des réponses `GET /jobs/{id}` (dans le respect de D-08 de la phase 1 pour les erreurs).
- Format de `job_id` (UUID4 hex court ou ULID).
- Découpage des plans et vagues ; noms des faux plugins (`sleep`, `spawn_orphan`, `bad_result`,
  `chatty`, `artifact_outside`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Conception
- `.arthemis/reports/llm-council-1.md` — architecture d'implémentation retenue (§2 concurrence, §4 protocole, §5 schéma)
- `ARCHITECTURE.md` §3 (file), §4 (exécution), §6 (protocole HTTP), §7 (chemins)
- `CLAUDE.md` — règles non négociables

### Phase précédente
- `.planning/phases/01-fondations-testables/01-CONTEXT.md` — décisions D-01..D-13 de la phase 1 (format d'erreur, config, démarrage)
- `.planning/phases/01-fondations-testables/01-0*-SUMMARY.md` — ce qui existe (runtime, store, api, core)
- `tests/_support/winjob.py`, `tests/proc/test_spike_jobobject.py` — recette Job Object validée

### Recherche
- `.planning/research/PITFALLS.md` — P2, P5, P7, M1-M11, M18
- `.planning/research/ARCHITECTURE.md` — composants et ordre
- `.arthemis/reports/verifs-techniques-cycle-1.md` §6 — Job Object

### Exigences
- `.planning/REQUIREMENTS.md` — JOB-01..09
- `.planning/STATE.md` — décisions accumulées

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/deskgate/core/config.py` : `RunnerConfig`, `Capability` (kind, python, entry, timeout_max, resource) déjà validés.
- `src/deskgate/core/paths.py` : conversion et validation des chemins (artefacts).
- `src/deskgate/core/errors.py` + `api/handlers.py` : format d'erreur D-08.
- `src/deskgate/runtime.py` : ordre de démarrage (config → mutex → socket → base → Uvicorn) où brancher recovery et threads.
- `src/deskgate/store.py` : `open_db` (squelette) à étendre en migration 1.
- `tests/_support/winjob.py` : recette ctypes Job Object à promouvoir en `src/deskgate/jobobject.py`.
- `tests/conftest.py` : fixtures `instance_name`, `data_home`, `free_port`, `runner_process`.

### Established Patterns
- Noyau pur `core/` sans sqlite3/subprocess/ctypes (test AST) ; marqueurs `unit`/`fs`/`proc`/`e2e`.

### Integration Points
- `api/app.py` `create_app` : ajouter les routes `/jobs`.
- `runtime.serve` : recovery puis démarrage des threads `engine` (et emplacement du futur `sender`).

</code_context>

<specifics>
## Specific Ideas

- Test clé : `taskkill /F /T` du runner pendant une tâche à petit-enfant, redémarrage, tâche `interrupted`, aucun PID survivant.
- Test de course : délai atteint en même temps que la fin normale ; annulation pendant la grâce.

</specifics>

<deferred>
## Deferred Ideas

- Purge automatique des `work_dir` (après N jours) — idée pour une version ultérieure.

</deferred>

---

*Phase: 02-cœur-d'exécution*
*Context gathered: 2026-10-20*

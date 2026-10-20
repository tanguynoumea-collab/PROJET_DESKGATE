# Phase 3 : Rappel fiable - Research

**Researched:** 2026-10-20
**Domain:** rappel HTTP durable (outbox SQLite + thread sender + httpx2) vers la `resumeUrl` n8n 2.43.8, masquage de secret, audit
**Confidence:** HIGH (code n8n lu au tag `n8n@2.43.8`, comportements httpx2 mesurés localement) ; MEDIUM sur quelques cas limites n8n signalés plus bas

## Summary

Le code n8n 2.43.8 a été lu (`waiting-webhooks.ts`, `webhook-request-handler.ts`, `response-helper.ts`, `rest-error-*`). Les statuts et textes de reprise sont **exacts et figés ci-dessous** (section « Contrat n8n »). Trois faits changent la conception :
1. un doublon reçu **pendant** que l'exécution reprise tourne encore reçoit « is running already » (même 409 que « pas encore en attente ») ; seule la fin de l'exécution donne « has finished already ». Il faut donc **mémoriser qu'un envoi antérieur a pu aboutir** (colonne sticky, voir Migration 2) pour distinguer `delivered_duplicate` de `abandoned_stale` ;
2. `httpx2` **préserve octet pour octet** la query (`+ / = %2B %2b`), mais **journalise l'URL complète au niveau INFO** (logger `httpx2`, ligne `HTTP Request: POST <url avec signature> "200 OK"`) : le masquage est obligatoire dès que le logging racine est configuré ;
3. `result.json` est déjà plafonné à 1 Mio côté worker (`RESULT_MAX_BYTES`), donc le plafond de rappel de 1 Mio ne se déclenche en réel que dans une bande étroite : le plafond doit être un **paramètre injectable** (test avec une petite valeur) en plus de la constante de production.

Autres découvertes à intégrer : `localhost` coûte **+2 s par envoi sous Windows** quand le serveur n'écoute qu'en IPv4 (tests : utiliser `127.0.0.1`) ; `httpx2` dépend aujourd'hui seulement du groupe `dev` de `pyproject.toml` (à passer en dépendance d'exécution, `uv.lock` à régénérer pour le gate `uv sync --locked`) ; `ValueError`/exceptions httpx2 ne contiennent pas l'URL (vérifié), mais `exc.request.url` oui ; `JobRow` (dataclass) exposerait `callback_url` dans son `repr`.

**Primary recommendation:** un thread `sender` miroir de l'Engine (`tick()` testable avec horloge, transport et aléa injectés), état dans `callbacks` (écriture préalable `attempts+1` avant chaque envoi, résultat après), politique pure `core/callback_policy`, corps pur `core/payload`, masquage par un `Formatter` + `Filter` unique branché sur tous les handlers, et un faux n8n stdlib rejouant les réponses exactes listées ici.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Réessais
- **D-01:** Délai croissant exponentiel avec gigue : 2 s, 4 s, 8 s… plafonné à **5 min** entre deux
  essais ; **fenêtre totale 24 h** à partir de la fin de la tâche, puis abandon
  `abandoned_exhausted` tracé dans l'audit. Les réessais survivent au redémarrage (état dans la
  table `callbacks` : `attempts`, `next_attempt_at`). `not_before` = création + 2 s (délai
  d'amorçage, P1). Valeurs configurables dans `runner.toml` (`[callback] max_window_s`,
  `max_backoff_s`), défauts 86400 et 300.

### Hôtes autorisés (CB-05)
- **D-02:** Défaut `callback_allowed_hosts = ["localhost", "127.0.0.1"]` (avec n'importe quel port).
  Toute autre cible doit être ajoutée explicitement. Contrôle **dès `POST /jobs`** (422
  `callback_host_not_allowed`) et **revérifié à l'envoi**. Schéma `http` ou `https` seulement.
  `follow_redirects=False`, `trust_env=False` (pas de proxy système).

### Politique de réponse (CB-03)
- **D-03:** Fonction pure `core/callback_policy.classify(status, body)` :
  2xx → `delivered` ; 409 dont le texte indique que l'exécution est encore en cours / pas encore en
  attente → réessai court ; 409 « déjà terminée » → `delivered_duplicate` si un envoi antérieur a pu
  aboutir, sinon `abandoned_stale` ; 404 → `abandoned_stale` ; 401/403 → `abandoned_rejected`
  (signature refusée) ; 5xx, timeout, erreur réseau → réessai avec délai croissant. Les textes
  exacts des 409 de n8n 2.43.8 sont établis par la recherche (lecture du code source à la version
  épinglée) et figés en fixtures du faux n8n. Si le texte n'est pas reconnu : réessai court plafonné.

### Envoi
- **D-04:** Thread `sender` dédié (décision du conseil), `httpx2.Client` **synchrone** qui lui
  appartient, timeout explicite (connexion 5 s, lecture 30 s). Concurrence 1. Réveillé par
  `threading.Event` quand une ligne `callbacks` passe `pending`, et par sondage (1 s).
  Arrêt par le lifespan, comme l'engine.
- **D-05:** La `resumeUrl` est envoyée **telle quelle** (aucune réécriture d'hôte ni de query en
  v0.1). La recherche vérifie que `httpx2` ne réencode pas la query (signature avec `+`, `/`, `=`).
  Si `httpx2` la réencode, envoyer l'URL brute par un moyen qui préserve les octets.
- **D-06:** Corps construit à l'envoi depuis la ligne `jobs` (pas de `payload_json`) par
  `core/payload.build_callback(row)`. Plafond **1 Mio** : au-delà, `summary` est écrit dans
  `<work_dir>/summary.json` (avant la transaction terminale) et le rappel porte
  `summary: {"path": "/data/…/summary.json", "truncated": true}`. Artefacts en chemin conteneur.

### Secrets et audit
- **D-07:** Masquage unique par `core/redact` : filtre `logging` global (racine, Uvicorn, httpx2),
  sérialiseurs d'API, audit, `last_error_redacted`. Test : la signature d'une URL de rappel
  n'apparaît dans aucun fichier journal, aucune réponse d'API, aucune ligne d'audit ni de
  `callbacks`.
- **D-08:** Audit (SEC-06) : `job.submitted`, `job.refused` (avec code), `job.<statut terminal>`,
  `callback.attempt` (statut HTTP ou erreur, sans URL), `callback.delivered`,
  `callback.abandoned` (raison). Paramètres sans secrets. Ajout seul (déclencheurs existants).
  Consultation de l'audit par API : hors périmètre v0.1 (lecture SQLite suffit).

### Claude's Discretion
- Forme exacte des fixtures du faux n8n, découpage des plans, exposition éventuelle d'un compteur de
  rappels en attente et du battement de l'engine dans `/health`.

### Deferred Ideas (OUT OF SCOPE)
- Route d'API de consultation de l'audit — après v0.1.
- Réécriture d'hôte de la `resumeUrl` (Docker Engine dans WSL) — si le spike 01-D1 l'impose (phase 5).

Note de portée (CONTEXT, domaine) : le critère ROADMAP « une fois et une seule » est remplacé par **au moins une fois** ; n8n ne reprend qu'une fois ; un doublon reçoit 409 et est tracé `delivered_duplicate`.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CB-01 | À chaque état terminal, appel de la `resumeUrl` telle quelle avec `{job_id, capability, status, duration_s, summary, artifacts, error}` | « Payload » (pur, depuis la ligne `jobs`), « Envoi » : octets de query préservés par httpx2 (mesuré), `content=` + `Content-Type` explicite, succès n8n = 200 `{"message":"Workflow was started"}` (tout 2xx = livré) |
| CB-02 | Rappel non livré réessayé avec délai croissant, y compris après redémarrage | « Sender », « Backoff », écriture préalable `attempts+1`, état dans `callbacks`, test e2e `taskkill` pendant un réessai |
| CB-03 | Distinguer livré / pas encore en attente (réessai court) / terminée ou inconnue (abandon tracé) / signature refusée (abandon tracé) | « Contrat n8n » : statuts et textes exacts, `classify`, colonne `maybe_delivered` |
| CB-04 | Résumé > 1 Mio écrit dans `summary.json`, le rappel ne porte que le chemin | « Payload et plafond » : crochet côté engine avant `store.finish`, plafond injectable |
| CB-05 | Rappel envoyé seulement à un hôte autorisé | « Hôtes autorisés » : double analyse `urlsplit` + `httpx2.URL`, liste blanche de caractères, contrôle à la soumission ET à l'envoi |
| SEC-05 | Signature absente de tous journaux, réponses d'API, audit | « Masquage » : `Formatter`+`Filter` sur les handlers, logger `httpx2` INFO fuit l'URL (mesuré), `repr(JobRow)`, balayage de test |
| SEC-06 | Audit local de chaque soumission, refus, fin de tâche, rappel | « Audit » : événements, charges utiles sans secret, point d'accroche `JobsService.submit` / handlers / sender |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Français partout (documents, messages d'erreur, journaux, commits) ; identifiants de code et champs JSON en anglais.
- Cœur sans BIM ; **aucun `shell=True`** ; plugins jamais dans le processus du runner.
- **Règle 6 : la `resumeUrl` (paramètre `signature`) est un secret : appelée telle quelle, masquée partout ailleurs.**
- **Règle 7 : rappel petit (≤ 1 Mio)** ; gros résultats dans des fichiers artefacts.
- Écoute `127.0.0.1` seulement ; jeton sur toutes les routes sauf `/health`.
- Pile : Python ≥ 3.11 (dev 3.14.4 ici), FastAPI + Uvicorn, SQLite WAL, `httpx2`. n8n épinglé `2.43.8`.
- Tests obligatoires dont **masquage de la signature**. Marqueurs pytest : `unit`, `fs`, `proc`, `e2e` (`--strict-markers`).
- Commits ARTHEMIS : `type(scope): sujet` ≤ 72 caractères, en français ; `.arthemis/**` jamais mêlé au code ni à `.planning/`.
- Gate (profil `web_saas`) : `uv sync --locked`, `ruff check`, `ruff format --check`, `pyright`, `pytest -m "not e2e"`, `uv build --all-packages`, `pytest -m e2e`.
- Skill de projet `gsd-file-manuelle` : toute étape humaine est classée bloquante (B1/B2/B3) ou différable au moment du plan. **Cette phase n'a besoin d'aucune intervention humaine** (tout est automatisable en local : faux n8n, taskkill). Ne pas inventer de checkpoint.
- Test d'architecture existant : `core/` n'importe ni `sqlite3`, `subprocess`, `httpx2`, `httpx`, `fastapi`, `starlette`, `ctypes`, `uvicorn` ; seul `store.py` importe `sqlite3`. `core/callback_policy`, `core/payload`, `core/redact` doivent rester **purs** ; `httpx2` n'entre que dans `sender.py`.

## Contrat n8n 2.43.8 (reprise par waiting-webhook) — texte exact

Source : `packages/cli/src/webhooks/waiting-webhooks.ts` (l. 244-344), `response-helper.ts` `sendErrorResponse`, `@n8n/backend-services/.../rest-error-response.ts`, tag `n8n@2.43.8`. [code, HIGH]

Route : `POST /webhook-waiting/:executionId[/:suffix]?signature=<token>`. Ordre des contrôles dans `executeWebhook` :

| Ordre | Condition n8n | Statut | Corps (JSON) | Content-Type |
|-------|---------------|--------|--------------|--------------|
| 1 | exécution **absente** (l. 291) : le contrôle du jeton est **sauté** car `execution?.data.resumeToken` est vide | **404** | `{"code":404,"message":"The execution \"<id>\" does not exist."}` | `application/json` |
| 2 | jeton `signature` absent, de longueur différente ou différent de `resumeToken` (`validateToken`, l. 190-203, comparaison à temps constant) | **401** | `{"error":"Invalid token"}` (forme **différente** : clé `error`, pas de `code`) | `application/json; charset=utf-8` |
| 3 | `execution.status === 'running'` (l. 303) | **409** | `{"code":409,"message":"The execution \"<id>\" is running already."}` | `application/json` |
| 4 | `waitReason === 'suspended'` (l. 309) | **409** | `{"code":409,"message":"The execution \"<id>\" is about to resume."}` | `application/json` |
| 5 | `resultData.error` présent (l. 313) | **409** | `{"code":409,"message":"The execution \"<id>\" has finished with error."}` | `application/json` |
| 6 | `execution.finished` (l. 320) | **409** | `{"code":409,"message":"The execution \"<id> has finished already."}` — **le guillemet fermant manque dans la source, à reproduire à l'identique dans la fixture** | `application/json` |
| 7 | exécution en attente mais aucun webhook `restartWebhook` correspondant à (méthode, suffixe) (l. 413-424) | **404** | `{"code":404,"message":"The workflow for execution \"<id>\" does not contain a waiting webhook with a matching path/method."}` | `application/json` |
| 8 | succès | **200** (`responseCode` du nœud Wait, défaut 200) | `{"message":"Workflow was started"}` par défaut (`extractWebhookOnReceivedResponse`) ; l'utilisateur peut configurer autre chose | JSON |

Corps d'erreur de réponse : `{code, message[, hint, meta]}` via `serializeInternalRestError` ; `Content-Type` forcé `application/json` (`res.setHeader` avant `res.status(...).json`). Les erreurs 409 sur URL contenant `form-waiting` rendent du HTML : **hors périmètre** (le runner appelle `webhook-waiting`).

Conséquences :
- **« Pas encore en attente » (P1)** = ligne 3 (`is running already`). **Un doublon reçu pendant que l'exécution reprise tourne** = aussi ligne 3. Indiscernables par le seul texte → colonne `maybe_delivered` obligatoire (voir plus bas).
- Après la fin : ligne 5 ou 6. Si un envoi antérieur a pu aboutir → `delivered_duplicate` ; sinon (Wait expiré par « Limit Wait Time », exécution terminée seule, P6) → `abandoned_stale`.
- **Un Wait configuré en `responseMode = lastNode` / `responseNode` fait attendre la réponse HTTP jusqu'à la fin du workflow** (l. 1262 de `webhook-helpers.ts`, `waitForResponse`) : le délai de lecture de 30 s peut expirer alors que n8n a repris. Le réessai recevra alors 409 « running already » puis « finished » → `delivered_duplicate`. Comportement correct *si* l'ambiguïté est mémorisée. Le workflow d'exemple (phase 5) devra garder `responseMode = onReceived` (défaut).
- Corps trop gros : n8n lit le corps avec `getRawBody(limit = N8N_PAYLOAD_SIZE_MAX, défaut 16 Mio)` (`middlewares/body-parser.ts`). Le statut exact renvoyé au-delà n'est **pas établi** (erreur `raw-body` non classée par `classifyRestError` : probablement 500 ou 413). [LOW] Avec le plafond de 1 Mio il n'est pas atteignable en configuration par défaut ; traiter 413 comme « renvoyer une fois un corps minimal » (option, voir Open Questions).
- Le jeton est validé **avant** l'existence : pas de fuite d'existence par 401 ; une exécution inconnue donne 404 sans test de jeton.
- **Zone d'incertitude [LOW]** : on ne sait pas si, pendant la course P1 (le runner répond avant que n8n ait persisté l'état Wait), la ligne `executions` peut déjà exister avec un jeton valide (alors 409, cas nominal) ou si un 404/401 transitoire est possible. Non vérifié par exécution d'un vrai n8n. **Durcissement recommandé** : 401 et 404 ne causent l'abandon qu'à la **deuxième observation consécutive identique** (utiliser `last_status` de la tentative précédente) ; la première observation donne un réessai court. Coût : une requête de plus, jamais de perte.

### Table de décision à implémenter (`classify`)

| Entrée | Décision |
|--------|----------|
| 2xx | `delivered` |
| 409, texte contient `running already` ou `about to resume` | `retry_short` |
| 409, texte contient `finished` (couvre `has finished already` et `has finished with error`) | `delivered_duplicate` si `maybe_delivered` sinon `abandoned_stale` |
| 409, texte non reconnu / corps non JSON | `retry_short` (plafonné, D-03) |
| 404 | `abandoned_stale` (après confirmation, voir ci-dessus) |
| 401, 403 | `abandoned_rejected` (après confirmation) |
| 413 | `retry_minimal` (option) sinon `retry_backoff` |
| 5xx, 408, 429, autre 4xx, 3xx, timeout, erreur réseau | `retry_backoff` |

Tester le texte par **sous-chaîne insensible à la casse** sur le champ `message` du JSON (jamais sur l'égalité : le guillemet manquant et les identifiants varient). Ne lire que les 4 premiers Kio du corps. Un 3xx n'est jamais suivi (`follow_redirects=False`) : le traiter en `retry_backoff` sans journaliser `Location`.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx2 | `>=2.15,<3` (2.15.1 installé dans `.venv`, vérifié `httpx2.__version__`) | client HTTP synchrone du sender | choix STACK.md ; **à déplacer de `[dependency-groups].dev` vers `[project].dependencies`** ; régénérer `uv.lock` |
| sqlite3 (stdlib) via `store.py` | stdlib | outbox `callbacks`, audit | seul module autorisé à importer `sqlite3` |
| threading, logging, json, urllib.parse (stdlib) | stdlib | sender, masquage, analyse d'URL | aucune dépendance ajoutée |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx2.MockTransport` | 2.15.1 (existe, vérifié) | tests unitaires/fs du sender sans réseau | tests de `tick()` avec horloge fausse |
| `http.server.ThreadingHTTPServer` | stdlib | faux n8n (tests fs/e2e) | serveur réel, enregistre la ligne de requête brute |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx2 sync dans un thread | `AsyncClient` dans le lifespan (STACK.md) | **Écarté par D-04** (décision du conseil : un POST lent ne doit pas retarder un délai ; état durable en base). |
| `tenacity`, `httpx-retries` | table `callbacks` | écartés (STACK.md) : pas durables au redémarrage. |
| `pytest-httpx` | vrai serveur local | compatibilité `httpx2` non vérifiée ; un vrai serveur voit la ligne de requête brute. |

**Installation (dans le dépôt, par le plan, pas par la recherche) :**
```bash
uv add "httpx2>=2.15,<3"   # puis supprimer la ligne dev redondante ; uv lock ; uv sync --locked
```

**Version verification :** `httpx2 2.15.1` + `httpcore2 2.15.1` + `h11 0.16.0` lus dans `.venv` ; Python 3.14.4 ; uvicorn 0.54.0. [HIGH]

## Architecture Patterns

### Recommended Project Structure
```
src/deskgate/
├── sender.py                 # NOUVEAU : thread Sender (httpx2 ici seulement)
├── store.py                  # + MIGRATION_2, claim/record des callbacks, audit
├── engine.py                 # + écriture de summary.json avant store.finish
├── jobs.py                   # + contrôle d'hôte, audit job.refused/job.submitted enrichi
├── runtime.py                # + création/démarrage/arrêt du sender, handler de log redacté
├── api/handlers.py           # + audit du refus de validation de POST /jobs
└── core/
    ├── callback_policy.py    # NOUVEAU pur : classify, backoff, check_callback_url
    ├── payload.py            # NOUVEAU pur : build_callback(...)-> bytes, plafond
    ├── redact.py             # étendu : RedactingFormatter/Filter, redact_params
    ├── config.py             # + [callback], callback_allowed_hosts par défaut
    └── errors.py             # + CALLBACK_HOST_NOT_ALLOWED
tests/_support/fake_n8n.py    # NOUVEAU : faux n8n réutilisable (fs + e2e)
```

### Pattern 1 : Sender miroir de l'Engine
**What :** classe `Sender` avec `__init__(db_path, config, client=None, wall=_utcnow, rng=random.Random(), poll=1.0)`, `tick() -> bool` (a traité une ligne), `run()` (boucle `wake.wait(poll)`, `wake.clear()` **avant** la lecture), `start()`, `stop(timeout)`, `wake()`, `failed`, `on_fatal`. Connexion SQLite propre au thread (créée à la demande, fermée en `finally`). `httpx2.Client` créé dans `start()`/`run()` et fermé en `finally`.
**When :** toujours ; `tick()` seul dans les tests avec `httpx2.MockTransport` et `FakeClock`/wall injectés.
**Example :**
```python
# Source : modèle de src/deskgate/engine.py (Engine.run/tick/stop) + mesures httpx2 locales
def tick(self) -> bool:
    conn = self._connection()
    now = self._wall()
    claim = store.claim_due_callback(conn, now, max_window_s=self._cfg.callback.max_window_s)
    if claim is None:                       # rien d'échu (les échus hors fenêtre sont abandonnés ici)
        return False
    outcome = self._send(claim)             # (status|None, body_head|None, error_name|None)
    decision = classify(outcome.status, outcome.body, maybe_delivered=claim.maybe_delivered,
                        prev_status=claim.last_status)
    store.record_callback_result(conn, claim.job_id, decision=decision, attempts=claim.attempts,
                                 now=self._wall(), delay_s=next_delay(...), outcome=outcome)
    return True
```

### Pattern 2 : Réclamation et écriture préalable (au moins une fois, sans fenêtre aveugle)
Concurrence 1 et mutex d'instance → pas de verrou de bail nécessaire. `claim_due_callback` (une transaction `BEGIN IMMEDIATE`) :
```sql
SELECT c.job_id, c.attempts, c.last_status, c.maybe_delivered, j.*   -- jointure sur jobs
FROM callbacks c JOIN jobs j ON j.id = c.job_id
WHERE c.state='pending' AND c.next_attempt_at <= :now AND c.not_before <= :now
ORDER BY c.next_attempt_at, c.rowid LIMIT 1
```
Les horodatages `iso()` sont à largeur fixe (`...Z`, millisecondes) : la comparaison de chaînes est correcte. Dans la **même** transaction, avant l'envoi : `UPDATE callbacks SET attempts=attempts+1, maybe_delivered=1 WHERE job_id=?` (pessimiste : si le runner meurt pendant l'envoi, au redémarrage la ligne est échue, `attempts>=1`, `maybe_delivered=1`, donc un 409 « finished » donnera `delivered_duplicate`, ce qui est la bonne lecture d'un envoi interrompu). Après la réponse, `record_callback_result` (autre transaction) : si la réponse est une **réponse définitive de n8n** (401/403/404/409, c'est-à-dire n8n a répondu sans reprendre), restaurer `maybe_delivered` à sa valeur d'avant l'essai (lue dans `claim`) ; sinon (timeout, erreur réseau, 5xx) le laisser à 1. Une ligne = un essai en vol : aucun autre thread n'écrit `callbacks` hors la création (transaction terminale, thread engine/API) et le sender.
Fenêtre : `deadline = finished_at + max_window_s`. À la réclamation, si `now >= deadline` **et** `attempts >= 1` : état `abandoned_exhausted` + audit, sans envoi. Après un échec : si `now_apres >= deadline` → `abandoned_exhausted` ; sinon `next_attempt_at = min(now + delay, deadline)`.

### Pattern 3 : Migration 2 (colonne sticky)
`SCHEMA_VERSION = 2`, `MIGRATION_2 = ("ALTER TABLE callbacks ADD COLUMN maybe_delivered INTEGER NOT NULL DEFAULT 0 CHECK (maybe_delivered IN (0,1))",)` (valable en table `STRICT`). Les tests existants `test_store_schema.py` attendent la version 1 : à mettre à jour (message `SchemaTooNew`, `user_version`). Alternative écartée : encoder l'ambiguïté dans l'audit ou dans `last_error_redacted` (hacks fragiles). Le choix de la colonne appartient au planificateur (voir Open Questions) mais **la distinction `delivered_duplicate`/`abandoned_stale` impose un bit persistant** : `last_status` seul est écrasé à chaque essai.

### Pattern 4 : Backoff pur
```python
# core/callback_policy.py — pur, rng injecté
def next_delay(attempts: int, *, max_backoff_s: float, rng: random.Random, short: bool = False) -> float:
    base = 2.0 * (1.5 if short else 2.0) ** min(max(attempts - 1, 0), 30)   # 2, 4, 8, ... (court : 2, 3, 4.5, ...)
    cap = 30.0 if short else max_backoff_s            # réessai court plafonné à 30 s
    return min(cap, base * rng.uniform(0.75, 1.25))   # gigue ±25 %, plafond appliqué après
```
`attempts` = nombre d'essais déjà faits. Réessai court : `short=True` pour `retry_short`. La fenêtre de 24 h borne tout (pas de plafond de comptage séparé ; limiter à ~2 900 essais courts max par tâche, acceptable).

### Pattern 5 : Payload pur (`core/payload.py`)
Entrée : champs scalaires (pas `JobRow`, pour garder `core/` sans dépendance à `store`) :
`build_callback(job_id, capability, status, started_at, finished_at, result_json, error_code, error_message) -> dict`, `encode(body) -> bytes` = `json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")`.
Forme : `{"job_id","capability","status","duration_s","summary","artifacts","error"}` ; `summary` et `artifacts` lus dans `result_json` (`{}` / `[]` si NULL, cas `failed`/`timeout`/`cancelled`/`interrupted`) ; `error = {"code","message"}` ou `null` ; `duration_s` = `finished-started` arrondi 3 décimales, **`null` si jamais démarrée** (même règle que `jobs.job_view`, qui doit appeler la même fonction pour éviter la divergence). `data` du plugin n'est pas transmis.

### Pattern 6 : Plafond 1 Mio et `summary.json` (côté engine, avant la transaction terminale)
Point d'accroche : `Engine._evaluate` (après construction de `result_json`, avant `_conclude`), uniquement pour `SUCCEEDED` avec `ResultOk` (seul cas porteur d'un résumé). Algorithme :
1. construire le corps avec le même `core.payload` (durée provisoire, quelques octets d'écart sans conséquence) et mesurer `len(encode(body))` ;
2. si `> max_bytes` (défaut `CALLBACK_MAX_BYTES = 1_048_576`, **paramètre du constructeur d'`Engine`** pour les tests) : écrire `<work_dir>/summary.json` **de façon atomique** (`summary.json.tmp` puis `os.replace`, `fsync` du fichier) avec le résumé complet, puis remplacer dans `result_json` : `"summary": {"path": "<chemin conteneur>", "truncated": true}` ;
3. chemin conteneur : `host_to_container(host_path, mappings)` de `core.paths` (déjà utilisé pour les artefacts) ; si aucun mapping ne couvre `work_dir`, retomber sur le chemin hôte slashé et le journaliser en avertissement (cas de configuration atypique) ;
4. échec d'écriture (`OSError`) : ne **pas** perdre le résultat : remplacer par `{"truncated": true, "error": "summary_write_failed"}` et continuer.
`GET /jobs/{id}` renverra alors aussi le marqueur (la vue lit `result_json`) : souhaitable.
**Constat :** `RESULT_MAX_BYTES` (1 048 576) borne déjà `result.json` ; le dépassement réel n'arrive que si `summary` ≈ 1 Mio et que `artifacts` + enveloppe font franchir le seuil. D'où le test unitaire/fs avec `callback_max_bytes` petit **et** un test bord (résumé ≈ 1 047 000 caractères + artefacts) pour la borne réelle. Dans `build_callback`, une vérification défensive finale (> max) remplace en dernier recours `summary` par `{"truncated": true}` sans chemin plutôt que d'envoyer un corps trop gros.

### Pattern 7 : Hôtes autorisés (CB-05)
Fonction pure `check_callback_url(url, allowed_hosts) -> ParsedTarget | CallbackUrlError` :
1. refuser si l'URL ne respecte pas `re.fullmatch(r"[\x21-\x7e]+", url)` (espace, tabulation, saut de ligne, antislash : `\x5c` est dans la plage, donc exclure explicitement `\`, et tout non-ASCII) ;
2. `urlsplit` : schéma ∈ {`http`,`https`}, `hostname` non vide, **ni `username` ni `password`** (refuse `http://localhost@evil.com`), port valide (le `ValueError` de `.port` est une erreur de refus) ;
3. comparaison **exacte** du `hostname` (minuscules) à `callback_allowed_hosts` normalisés en minuscules (pas de suffixe, pas de joker, pas de normalisation d'adresse : `127.1` est refusé) ; n'importe quel port.
**À l'envoi** : refaire `check_callback_url` **et** vérifier que `httpx2.URL(url).host` (lu dans `sender.py`) vaut le même nom d'hôte ; sinon abandon `abandoned_rejected` (raison `host_not_allowed`), sans envoi. Mesuré : `urlsplit` supprime tab/LF et lit `localhost\t.evil.com` comme `localhost.evil.com` alors que `httpx2.URL` lève `InvalidURL` ; avec un espace en tête `urlsplit` voit `localhost` et `httpx2` un hôte vide. La liste blanche de caractères élimine ces divergences. Hôte avec point final (`localhost.`) : refusé (non listé).
Défaut de configuration : `callback_allowed_hosts` passe de `[]` à `["localhost", "127.0.0.1"]` ; `runner.example.toml` à mettre à jour (il contient `["localhost"]`). Rappel : une clé de premier niveau TOML doit précéder les tables (`[paths]`, `[callback]`).
Le 422 `callback_host_not_allowed` (`JobRequestError`, code stable dans `core/errors.py`) **ne doit pas contenir l'URL** ; il peut nommer l'hôte (non secret) et la clé `callback_allowed_hosts`.

### Pattern 8 : Configuration `[callback]`
```python
class CallbackConfig(Strict):
    max_window_s: int = Field(86400, ge=60, le=2_592_000)   # 24 h
    max_backoff_s: int = Field(300, ge=1, le=3600)
```
`RunnerConfig.callback: CallbackConfig = CallbackConfig()`. Dans `tests/e2e/conftest.write_config`, ajouter un paramètre pour écrire la table `[callback]` **après** `[paths]` (les surcharges actuelles ne gèrent que le premier niveau). Les e2e fixent `max_backoff_s = 2` pour des réessais courts. Messages d'erreur de configuration : réutiliser `_MESSAGES`/`_format_errors` existants.

### Anti-Patterns to Avoid
- **Reconstruire/réécrire la `resumeUrl`** (`httpx2.URL.copy_with`, `params=`) : D-05. Passer la chaîne brute stockée.
- **`client.post(url, json=payload)`** : empêche de mesurer le plafond sur les octets réellement envoyés. Utiliser `content=<bytes>` + `headers={"Content-Type": "application/json"}`.
- **Lire tout le corps de réponse n8n** : utiliser `client.stream("POST", ...)`, ne rien lire pour 2xx, lire ≤ 4 Kio sinon ; le corps d'un Wait en `lastNode` peut peser jusqu'à 16 Mio.
- **Keep-alive réutilisé** : callbacks rares, Express ferme les sockets inactifs → fausses erreurs « Server disconnected » qui marqueraient `maybe_delivered`. Créer le client avec `limits=httpx2.Limits(max_keepalive_connections=0)` (vérifié fonctionnel).
- **Utiliser `exc.request.url` ou `repr(request)`** dans les messages : contiennent la signature. Journaliser/stocker uniquement `type(exc).__name__`.
- **Un seul thread qui bloque tout après une exception SQLite** : `run()` doit attraper les erreurs d'une itération (journal + attente), ne s'arrêter fatalement (`on_fatal`) qu'en cas d'erreur d'infrastructure répétée.
- **Journaliser la `JobRow`** : le `repr` du dataclass contient `callback_url` ; déclarer `callback_url: str = field(repr=False)`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Transport HTTP, timeouts | sockets/`http.client` | `httpx2.Client(timeout=httpx2.Timeout(30.0, connect=5.0), follow_redirects=False, trust_env=False, limits=httpx2.Limits(max_keepalive_connections=0))` | gère connexion, TLS, encodage ; octets de query préservés (mesuré) |
| Réessai durable | décorateur en mémoire (`tenacity`) | table `callbacks` + `store.claim_due_callback` | survit au redémarrage (CB-02) |
| Mock HTTP unitaire | patch de `httpx2.post` | `httpx2.MockTransport` injecté dans le `Client` | pas de réseau ; le faux serveur réel couvre la ligne de requête brute |
| Analyse d'URL | regex maison pour l'hôte | `urllib.parse.urlsplit` + liste blanche de caractères + `httpx2.URL(url).host` en recoupement | `@`, `\`, tab, `#`, `?` : cas d'évasion mesurés ci-dessus |
| Masquage | un `sub` par site d'appel | `redact_signature` unique dans `Formatter`+`Filter` + sérialiseurs | D-07 ; un oubli = fuite |
| Écriture atomique de `summary.json` | `open(..., "w")` direct | fichier temporaire + `os.replace` | un lecteur n'observe jamais un JSON partiel |
| Faux n8n | mock par monkeypatch | `ThreadingHTTPServer` réel | voit la ligne de requête brute et les coupures TCP |

**Key insight :** tout le risque de cette phase est dans la *sémantique* (ordre des écritures, bit d'ambiguïté, signature qui fuit par un chemin inattendu), pas dans le HTTP lui-même ; chaque point ci-dessus se teste sans n8n réel parce que le contrat n8n est figé par le code source.

## Runtime State Inventory

Non applicable : phase d'ajout (pas de renommage ni de migration de données utilisateur), sauf **Migration 2 du schéma SQLite** (ajout de colonne, `user_version` 1 → 2) traitée au plan store. Aucune donnée externe, aucun service enregistré (la tâche planifiée est de la phase 5), aucun secret nommé, aucun artefact installé à rafraîchir hors `uv.lock` (httpx2 devient dépendance d'exécution).

## Common Pitfalls

### Pitfall 1 : `delivered_duplicate` confondu avec `abandoned_stale`
**What goes wrong :** sans bit persistant, la séquence timeout (n8n a repris) → 409 running → 409 finished est classée `abandoned_stale` (résultat marqué « perdu » alors qu'il a été livré), ou inversement.
**Why :** `last_status` est écrasé à chaque essai ; « running already » existe aussi pour un doublon.
**How to avoid :** colonne `maybe_delivered`, écriture préalable avant l'envoi (Pattern 2).
**Warning signs :** test e2e « coupure après réception » donne `abandoned_stale`.

### Pitfall 2 : la signature fuit par le logger `httpx2` (INFO)
**What goes wrong :** `httpx2` écrit `HTTP Request: POST http://…/webhook-waiting/42?signature=<jeton> "HTTP/1.1 200 OK"` (mesuré). Aujourd'hui rien ne sort car seul le logger `deskgate` a un handler ; dès qu'un handler racine existe, le jeton fuit.
**How to avoid :** `Formatter` redacté + `Filter` sur **chaque** handler ; en plus `logging.getLogger("httpx2").setLevel(logging.WARNING)` et `httpcore2` idem. Test : activer INFO racine, faire un envoi, balayer.
**Warning signs :** le jeton réapparaît quand on ajoute un handler racine ou en mode `--log-level debug`.

### Pitfall 3 : `localhost` coûte 2 s par envoi sous Windows
**What goes wrong :** mesuré : POST vers `http://localhost:<port>` avec un serveur lié à `127.0.0.1` → 2,04 s par requête (tentative `::1` refusée puis repli IPv4) ; `127.0.0.1` → 1-2 ms.
**How to avoid :** dans les tests, lier le faux n8n à `127.0.0.1` et utiliser `http://127.0.0.1:<port>/...` ; ne pas écrire de test de durée sensible avec `localhost` ; n8n réel sous Docker Desktop écoute en double pile (non mesuré ici).

### Pitfall 4 : réponse n8n lente à cause du `responseMode` du Wait
Voir « Contrat n8n » : timeout de lecture alors que n8n a repris → doublon ultérieur. Géré par `maybe_delivered`. Documenter dans le workflow d'exemple (phase 5).

### Pitfall 5 : plafond jamais exercé
`RESULT_MAX_BYTES` plafonne déjà `result.json` : sans paramètre injectable, CB-04 n'a aucun test réaliste. Prévoir `callback_max_bytes` (constructeur `Engine`) + test bord réel.

### Pitfall 6 : `callback_allowed_hosts` par défaut vide casserait tout
Le défaut actuel est `[]` : une fois CB-05 actif, **tous** les e2e existants (URL `localhost:5678`) seraient refusés en 422. Changer le défaut (D-02) dans le même plan que le contrôle.

### Pitfall 7 : exceptions SQLite après envoi
Si l'écriture du résultat échoue après un envoi réussi, la ligne reste échue → renvoi (doublon, n8n répondra 409 puis `delivered_duplicate`). Acceptable (au moins une fois) ; ne pas laisser le thread mourir : journaliser, attendre, réessayer.

### Pitfall 8 : arrêt pendant un envoi
`stop()` fait `join(timeout)` ; un POST en cours (jusqu'à 30 s) peut dépasser le délai du lifespan. Le thread est `daemon=True` ; à l'arrêt forcé l'envoi est interrompu, la ligne reste échue avec `maybe_delivered=1` : cas déjà couvert par l'écriture préalable. Ne pas fermer le client depuis un autre thread sans nécessité.

### Pitfall 9 : redémarrage après longue panne
Tous les rappels échus partent à la suite à 1 requête à la fois, ordre `next_attempt_at`. Connexion bloquée = 5 s par ligne (n8n injoignable, chemin silencieux) : le plafond de 24 h et la concurrence 1 bornent le risque ; pas de rafale parallèle. [M23 PITFALLS]

### Pitfall 10 : `test_store_schema` et migration
Passer à `SCHEMA_VERSION = 2` modifie les attentes de `tests/fs/test_store_schema.py` et le message `SchemaTooNew` : mettre à jour dans le même plan.

## Masquage (SEC-05, D-07)

Constats (mesurés / lus) :
- `runtime.configure_logging()` ne configure **que** le logger `deskgate` (`handlers[:] = [handler]`, INFO) ; la racine n'a pas de handler. Uvicorn est lancé avec `log_config=None` : ses loggers n'ont pas de handler et `Config.configure_logging` ne touche pas aux niveaux (`log_level=None`) → INFO d'`uvicorn.access` non émis aujourd'hui. Si un handler racine est ajouté, `uvicorn.access` loggue `%s - "%s %s HTTP/%s" %d` avec **le chemin + la query** ; la signature n'y figure que si n8n l'envoyait dans la query d'une route Deskgate (non). Le `POST /jobs` transporte l'URL dans le **corps**, jamais journalisé.
- Exceptions httpx2 (`ReadTimeout`, `ConnectError`, `RemoteProtocolError`, `UnsupportedProtocol`, `InvalidURL`) : `str(e)` et traceback **ne contiennent pas** l'URL (testé) ; `e.request.url` oui.
- Formatter redacté : le masquage appliqué à la chaîne **finale** formatée couvre `msg`, `args`, `exc_text` et la ligne de source du traceback (testé : `RuntimeError("…signature=SEC3")` masqué, y compris la ligne de code citée).

Conception :
```python
# core/redact.py — pur
class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact_signature(super().format(record))

class RedactingFilter(logging.Filter):          # pour caplog et handlers tiers
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_signature(record.getMessage())
        record.args = None
        return True
```
`configure_logging()` : un handler `StreamHandler(stderr)` avec `RedactingFormatter` **et** `RedactingFilter` ; l'attacher à `deskgate` (`propagate = False`) **et** à la racine (niveau WARNING) ; `httpx2`/`httpcore2` à WARNING. Un `Filter` posé sur un *logger* ne s'applique pas aux enregistrements propagés depuis un enfant : le placer sur le **handler**.
Extensions de `redact_signature` à tester : `signature%3D…` (URL encodée dans un autre paramètre) n'est pas couvert par l'expression actuelle ; ajouter `signature(?:=|%3[dD])` et `"signature":"…"` (JSON). Ajouter `redact_params(obj)` : masque récursivement les valeurs des clés `token|secret|password|authorization|api[_-]?key|signature` et applique `redact_signature` aux chaînes (pour les paramètres de l'audit).
Autres chemins à fermer : `last_error_redacted` (n'y mettre que le nom de classe d'exception et le statut HTTP, passés par `redact_signature` par principe) ; `job_view` n'expose déjà pas `callback_url` ; `JobRow.callback_url` avec `repr=False` ; `read_logs` masque déjà ; `jobs.callback_url` reste stockée en clair en base (nécessaire à l'envoi). **Option recommandée** (discrétion) : à l'état final de `callbacks` (livré/abandonné), exécuter `UPDATE jobs SET callback_url=''` dans la même transaction (colonne `NOT NULL`, chaîne vide acceptée) pour ne pas conserver un secret périmé ; vérifier qu'aucun test existant ne relit `callback_url` après la fin.

## Audit (SEC-06, D-08)

Table `audit` existante (ajout seul, déclencheurs `RAISE(ABORT)`), colonnes `ts, event, job_id, detail_json` ; `job_id` nullable. Événements et charge utile (JSON, sans secret) :

| Événement | Où | Détail |
|-----------|----|--------|
| `job.submitted` (existant : `{capability}`) | `store.insert_job` | enrichir : `client` (`"bearer"`, jeton unique v0.1), `capability`, `params` passés par `redact_params` et tronqués à ~4 Kio, `timeout_s`, `has_idempotency_key` |
| `job.refused` | `JobsService.submit` (capacité inconnue, délai trop grand, conflit d'idempotence, hôte non autorisé) + gestionnaire de validation pour `POST /jobs` | `{code, capability?}` ; `job_id` NULL (sauf conflit : id existant) |
| `job.started` (existant) | `claim_next` | inchangé |
| `job.<statut terminal>` (existant) | `_terminal` / recovery | enrichir : `duration_s`, `started_at`, `finished_at`, `status`, `error_code` (« début, fin, statut, durée » de SEC-06) |
| `callback.attempt` | `record_callback_result` | `{attempt, http_status|null, error|null (nom de classe), decision}` — **jamais l'URL** |
| `callback.delivered` | idem | `{attempts, state: "delivered"|"delivered_duplicate"}` |
| `callback.abandoned` | idem | `{reason: "stale"|"rejected"|"exhausted"|"host_not_allowed", attempts}` |

Le refus de validation Pydantic (corps invalide) passe par `RequestValidationError` : le gestionnaire (`api/handlers._validation`) dispose de la requête ; n'y auditer que `POST /jobs` (`request.method`, `request.url.path`) avec le code `invalid_request`, via un `JobsService.audit_refusal(code, capability=None)`. Les refus 401/Host (middlewares) ne sont **pas** des refus de soumission : hors périmètre (volumétrie d'attaque).
Volumétrie : ≤ ~290 `callback.attempt` par tâche bloquée pendant 24 h : acceptable.
Les tests existants lisent `detail_json` (`test_audit_sans_secret`, `job.interrupted`) : conserver les clés actuelles, n'**ajouter** que des clés.

## Sender : cycle complet

Câblage `runtime.serve()` (le commentaire `# phase 3 : thread sender` marque l'emplacement) :
```python
sender = Sender(db_path=db_path(home), config=cfg)
sender.on_fatal = lambda: setattr(server, "should_exit", True)
engine.start(); sender.start()
app = create_app(..., on_shutdown=lambda: (engine.stop(), sender.stop()))
...
finally:
    engine.stop(); sender.stop()      # idempotents
```
`create_app` accepte déjà un seul `on_shutdown` : passer une fonction composée (pas de changement de signature).
Réveil : `sender.wake()` n'avance rien en pratique (`not_before = création + 2 s`) ; garder `wake()` pour les tests et l'arrêt, sondage à 1 s (D-04). Câblage `Engine.on_finished` optionnel, sans bénéfice mesurable.
Compteur dans `/health` (discrétion) : si ajouté, ne jamais exposer d'URL ni d'identifiant ; un entier `callbacks_pending` et un booléen `sender_alive` suffisent ; `/health` est public.

États terminaux de `callbacks` (contrainte `CHECK` existante) : `delivered`, `delivered_duplicate`, `abandoned_stale`, `abandoned_rejected`, `abandoned_exhausted`. Raison `host_not_allowed` à l'envoi → `abandoned_rejected` + audit `reason`.
Cas particuliers : job `cancelled` depuis `queued` crée aussi une ligne `callbacks` (thread API) → traité comme les autres (`duration_s = null`).

## Faux n8n (tests)

`tests/_support/fake_n8n.py` : `ThreadingHTTPServer` lié à `127.0.0.1:0`, thread démon ; état protégé par un `threading.Lock` :
- `script: list[Step]` consommée par requête ; `Step(status, body, content_type, delay_s=0, hang=False, drop=False)` ; `default` répété quand le script est vide ;
- `requests: list[Recorded]` avec `requestline` **brute** (`self.requestline`), `headers`, `body: bytes`, `t`.
- `drop=True` : `self.connection.close()` sans réponse (vérifié : côté client `RemoteProtocolError: Server disconnected without sending a response`).
- fixtures de réponses exactes (voir « Contrat n8n ») : `RUNNING`, `ABOUT_TO_RESUME`, `FINISHED_ERROR`, `FINISHED` (avec le guillemet manquant), `NOT_FOUND`, `NO_WEBHOOK`, `INVALID_TOKEN` (`{"error":"Invalid token"}`), `OK` (`{"message":"Workflow was started"}`).
- `fake_n8n` fixture pytest (arrêt `shutdown()` + `server_close()`), `url(execution_id="42", signature="E2E-SECRET-SIG")` renvoie `http://127.0.0.1:<port>/webhook-waiting/42?signature=...` (utiliser une signature contenant `+ / = %2B`).
Utilisable en `fs` (sender piloté par `tick()`, wall fausse) et en `e2e` (runner réel dans un sous-processus, `callback.url` pointant le faux serveur). Dans le e2e, `start_runner` lance `stdout/stderr=PIPE` sans lecture continue : ne lire les flux qu'après l'arrêt (déjà le cas) et garder le volume de logs bas pour ne pas bloquer le tube.

## Code Examples

### classify (pur)
```python
# core/callback_policy.py — Source : textes n8n@2.43.8 waiting-webhooks.ts l. 304-328
import json
from dataclasses import dataclass

@dataclass(frozen=True)
class Decision:
    kind: str            # delivered | delivered_duplicate | abandoned_stale | abandoned_rejected
                         # | retry_short | retry_backoff | retry_minimal
    reason: str = ""

def _message(body: bytes | str | None) -> str:
    if not body:
        return ""
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
    try:
        data = json.loads(text[:4096])
        msg = data.get("message") if isinstance(data, dict) else None
    except ValueError:
        msg = None
    return (msg if isinstance(msg, str) else text[:200]).lower()

def classify(status: int | None, body, *, maybe_delivered: bool, prev_status: int | None = None) -> Decision:
    if status is None:
        return Decision("retry_backoff", "network")
    if 200 <= status < 300:
        return Decision("delivered")
    if status == 409:
        msg = _message(body)
        if "finished" in msg:
            return Decision("delivered_duplicate" if maybe_delivered else "abandoned_stale", "finished")
        return Decision("retry_short", "running" if ("running already" in msg or "about to resume" in msg) else "unknown_409")
    if status in (401, 403, 404):
        confirmed = prev_status == status        # deuxième observation consécutive
        if not confirmed:
            return Decision("retry_short", f"confirm_{status}")
        return Decision("abandoned_stale" if status == 404 else "abandoned_rejected", f"http_{status}")
    if status == 413:
        return Decision("retry_minimal", "too_large")
    return Decision("retry_backoff", f"http_{status}")
```

### Envoi (dans `sender.py`)
```python
# Source : mesures httpx2 2.15.1 locales (query préservée, pas de fuite d'URL dans str(exc))
client = httpx2.Client(
    timeout=httpx2.Timeout(30.0, connect=5.0),
    follow_redirects=False, trust_env=False,
    limits=httpx2.Limits(max_keepalive_connections=0),
)
def _send(self, url: str, body: bytes) -> tuple[int | None, bytes | None, str | None]:
    try:
        with self._client.stream("POST", url, content=body,
                                 headers={"Content-Type": "application/json"}) as r:
            head = None if 200 <= r.status_code < 300 else b"".join(_take(r.iter_bytes(), 4096))
            return r.status_code, head, None
    except httpx2.HTTPError as exc:                 # timeouts, réseau, protocole
        return None, None, type(exc).__name__       # JAMAIS str(exc.request.url)
    except httpx2.InvalidURL:
        return None, None, "InvalidURL"
```
(`httpx2.InvalidURL` n'est pas un `HTTPError` : l'attraper séparément ; vérifié : `InvalidURL`/`UnsupportedProtocol` levés avant tout envoi.)

### Test de préservation de query (fs, serveur réel)
```python
# le faux n8n enregistre self.requestline ; la signature contient + / = %2B
SIG = "a+b/c=d%2Bz%2Fq%3D"
... assert fake.requests[0].requestline == f"POST /webhook-waiting/42?signature={SIG} HTTP/1.1"
```
Mesuré : `POST /webhook-waiting/42?signature=a+b/c=d%2Bz%2Fq%3D&x=1 HTTP/1.1` ressort identique ; `%2b` minuscule aussi. Normalisés/encodés (non pertinents pour n8n) : segments `..` du **chemin** résolus, non-ASCII et espaces encodés en `%XX`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `httpx` 0.28 | `httpx2` 2.15 (loggers `httpx2`, `httpcore2`) | 2026 | filtrer les **nouveaux** noms de loggers ; `MockTransport` existe encore |
| `resumeUrl` sans jeton | `?signature=<resumeToken>` comparé à temps constant (2.43.8) ; HMAC seulement pour send-and-wait | n8n 2.x | URL opaque, jamais reconstruite ; 401 `{"error":"Invalid token"}` |
| ROADMAP « une fois et une seule » | « au moins une fois » + `delivered_duplicate` | décision utilisateur, phase 3 | duplication tolérée, tracée |

**Deprecated/outdated :** `$resumeWebhookUrl` (n8n) déprécié au profit de `$execution.resumeUrl`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (venv du dépôt) | tout | ✓ | 3.14.4 | — |
| httpx2 | sender, tests | ✓ (dev seulement) | 2.15.1 | — (à promouvoir en dépendance d'exécution) |
| `taskkill` Windows | e2e redémarrage | ✓ (déjà utilisé par `kill_tree`) | système | — |
| uv | gate `uv sync --locked` | ✓ (déjà utilisé) | — | — |
| n8n réel / Docker | non requis | n/a | — | faux n8n stdlib (la validation sur n8n réel est le parcours d'acceptation de la phase 5, ACC-01/02) |
| Accès réseau GitHub | lecture du code n8n | ✓ (fait) | — | — |

**Missing dependencies with no fallback :** aucune.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1 + pytest-timeout (config dans `pyproject.toml`, `--strict-markers`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (marqueurs `unit`, `fs`, `proc`, `e2e`) |
| Quick run command | `uv run pytest -m "unit or fs" -x -q` |
| Full suite command | `uv run pytest -m "not e2e" -q` puis `uv run pytest -m e2e -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CB-01 | corps `{job_id,capability,status,duration_s,summary,artifacts,error}` pour chacun des 5 statuts ; query brute préservée (`+ / = %2B`) ; Content-Type JSON | unit (`build_callback`) + fs (faux n8n, `tick()`) | `uv run pytest tests/unit/test_payload.py tests/fs/test_sender_send.py -x` | ❌ Wave 0 |
| CB-01 | tâche < 100 ms : le rappel attend `not_before` puis est livré | fs (wall fausse) | `uv run pytest tests/fs/test_sender_send.py::test_attend_amorcage -x` | ❌ Wave 0 |
| CB-02 | backoff 2/4/8… plafonné, gigue bornée, fenêtre 24 h → `abandoned_exhausted`, sans envoi après fenêtre | unit (`next_delay`) + fs (`tick()`, MockTransport) | `uv run pytest tests/unit/test_callback_policy.py tests/fs/test_sender_retry.py -x` | ❌ Wave 0 |
| CB-02 | survie au redémarrage : faux n8n en 500, `taskkill /F /T` du runner après la 1re tentative, redémarrage, livraison ; `attempts>=2`, état `delivered` | e2e | `uv run pytest tests/e2e/test_callback_restart.py -x` | ❌ Wave 0 |
| CB-02 | écriture préalable : envoi interrompu (faux n8n retient la réponse, kill) → renvoi après redémarrage | e2e | `uv run pytest tests/e2e/test_callback_restart.py::test_envoi_interrompu -x` | ❌ Wave 0 |
| CB-03 | `classify` : table complète (200, 409 running/about to resume/finished/finished with error/inconnu, 404, 401, 403, 413, 500, None) avec les textes exacts | unit | `uv run pytest tests/unit/test_callback_policy.py -x` | ❌ Wave 0 |
| CB-03 | `maybe_delivered` : timeout puis 409 running puis 409 finished → `delivered_duplicate` ; 409 running puis finished sans ambiguïté → `abandoned_stale` ; 401/404 confirmés | fs (script du faux n8n) | `uv run pytest tests/fs/test_sender_policy.py -x` | ❌ Wave 0 |
| CB-04 | résumé > plafond : `summary.json` écrit atomiquement avant la transaction terminale, rappel `{"path":"/data/...","truncated":true}` ; borne réelle ≈ 1 Mio ; échec d'écriture sans perte | fs (Engine avec `callback_max_bytes` petit, FakeLauncher) + unit | `uv run pytest tests/fs/test_engine_summary_cap.py tests/unit/test_payload.py -x` | ❌ Wave 0 |
| CB-05 | hôte non listé → 422 `callback_host_not_allowed` à `POST /jobs` ; évasions (`@`, `\`, tab, espace, `localhost.evil.com`, `127.1`, schéma `ftp`) ; revérification à l'envoi (ligne en base modifiée) → `abandoned_rejected` ; défaut `localhost`/`127.0.0.1` | unit (`check_callback_url`) + fs (routes, sender) | `uv run pytest tests/unit/test_callback_url.py tests/fs/test_routes_jobs.py -x` | ❌ Wave 0 (routes : fichier existant à étendre) |
| SEC-05 | balayage : signature absente de stderr/stdout du runner (INFO racine activé), réponses d'API (`POST/GET /jobs`, logs, erreurs 422/404/409), `audit.detail_json`, `callbacks.last_error_redacted`, `job.log` ; `repr(JobRow)` sans URL ; filtre sur `httpx2`/`uvicorn.access` | unit (formatter/filter, caplog) + e2e (balayage complet) | `uv run pytest tests/unit/test_redact.py tests/e2e/test_callback_secret.py -x` | ✅ `test_redact.py` à étendre ; e2e ❌ Wave 0 |
| SEC-06 | événements `job.submitted`, `job.refused` (+code), `job.<terminal>` (+durée), `callback.attempt`, `callback.delivered`, `callback.abandoned` ; aucune URL/secret dans `detail_json` ; params masqués | fs (store/sender/routes) | `uv run pytest tests/fs/test_audit_events.py -x` | ❌ Wave 0 |
| Archi | `httpx2` importé seulement par `sender.py` ; `core/` pur ; `sqlite3` seulement dans `store.py` | unit | `uv run pytest tests/architecture/test_import_boundaries.py -x` | ✅ existant (ajouter la règle `httpx2`) |

### Sampling Rate
- **Per task commit :** `uv run pytest -m "unit or fs" -x -q` (< 30 s ; sender et policy testés par `tick()` sans attente réelle)
- **Per wave merge :** `uv run pytest -m "not e2e" -q`
- **Phase gate :** gate complet du profil (`uv sync --locked`, ruff, pyright, `-m "not e2e"`, `uv build --all-packages`, `-m e2e`) vert avant `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/_support/fake_n8n.py` — faux n8n + fixtures de réponses exactes (CB-01..03, SEC-05)
- [ ] `tests/unit/test_callback_policy.py`, `test_payload.py`, `test_callback_url.py` (CB-01..03, CB-05)
- [ ] `tests/fs/test_sender_send.py`, `test_sender_retry.py`, `test_sender_policy.py`, `test_engine_summary_cap.py`, `test_audit_events.py`
- [ ] `tests/e2e/test_callback_restart.py`, `tests/e2e/test_callback_secret.py` ; extension de `tests/e2e/conftest.py` (`write_config` : section `[callback]`, fixture `fake_n8n`)
- [ ] Mise à jour de `tests/fs/test_store_schema.py` (version 2) et de la règle d'architecture `httpx2`
- [ ] `pyproject.toml` : `httpx2` en dépendance d'exécution ; `uv lock`
- Plafond de durée e2e : prévoir `@pytest.mark.timeout(90)` comme les e2e existants ; `max_backoff_s = 2` dans la configuration e2e.

## Open Questions

1. **Colonne `maybe_delivered` (Migration 2) ou autre mécanisme ?**
   - Known : `delivered_duplicate` vs `abandoned_stale` (D-03) exige de savoir si un envoi antérieur a pu aboutir ; `last_status` est écrasé ; « running already » couvre le doublon.
   - Unclear : l'utilisateur a figé le schéma en phase 2 (migration 1 « conçue une fois »).
   - Recommendation : Migration 2 (ALTER ADD COLUMN, bit sticky + écriture préalable). Si refusée, dégrader : traiter tout 409 « finished » avec `attempts>1` ou `last_status IS NULL OR last_status>=500` comme `delivered_duplicate` (heuristique moins exacte).
2. **Confirmation avant abandon sur 401/404 ?**
   - Known : D-03 abandonne immédiatement ; le cas P1 transitoire 404/401 n'est ni prouvé ni exclu (LOW).
   - Recommendation : exiger deux observations consécutives (coût : un essai court). À valider par l'utilisateur car cela nuance D-03.
3. **Dernier essai si `attempts == 0` après 24 h d'arrêt du runner ?**
   - D-01 : abandon à la fin de fenêtre. Un essai unique coûte peu et sert « au moins une fois ». Recommandation : suivre D-01 strictement sauf décision contraire.
4. **413 : corps minimal ou abandon ?**
   - Non atteignable à 1 Mio avec le défaut n8n 16 Mio, statut exact non vérifié. Recommandation : `retry_minimal` une fois (`summary` remplacé par le marqueur sans fichier), sinon `retry_backoff`.
5. **Purge de `jobs.callback_url` à l'état final** : recommandée (réduit le secret au repos) mais non décidée ; vérifier l'absence d'usage aval.

## Découpage suggéré (discrétion du planificateur)

1. **Noyau pur + config** : `core/callback_policy` (classify, `next_delay`, `check_callback_url`), `core/payload`, extension `core/redact`, `CallbackConfig`, défaut `callback_allowed_hosts`, code d'erreur, règle d'architecture `httpx2` ; dépendance httpx2.
2. **Store** : Migration 2, `claim_due_callback`, `record_callback_result`, audit enrichi, `JobRow.callback_url` `repr=False`, tests de schéma mis à jour.
3. **Sender + câblage** : `sender.py`, `runtime.serve`/`create_app`, `fake_n8n`, tests fs de politique et réessai.
4. **Engine plafond + soumission** : `summary.json` atomique, contrôle d'hôte et `job.refused` dans `JobsService`/handlers.
5. **Masquage** : `configure_logging` (handlers, `httpx2`/`httpcore2`), `redact_params`, tests unitaires.
6. **E2E** : redémarrage pendant réessai, envoi interrompu, balayage de la signature.
(Plans 1→2→3 séquentiels ; 4 et 5 parallélisables après 1 ; 6 en dernier.)

## Sources

### Primary (HIGH confidence)
- GitHub `n8n-io/n8n` tag `n8n@2.43.8` : `packages/cli/src/webhooks/waiting-webhooks.ts` (l. 160-344, 413-424), `webhook-request-handler.ts`, `response-helper.ts` (`sendErrorResponse`), `packages/@n8n/backend-services/src/errors/rest-error-classifier.ts` et `rest-error-response.ts`, `packages/@n8n/errors/src/response-errors/conflict.error.ts`, `middlewares/body-parser.ts`, `webhooks/webhook-helpers.ts` (l. 1262, 1334), `webhook-on-received-response-extractor.ts`, `nodes-base/nodes/Wait/Wait.node.ts` — lus et copiés dans le scratchpad.
- Mesures locales (`.venv` du dépôt, httpx2 2.15.1, Python 3.14.4, scripts `exp1`-`exp6` du scratchpad) : préservation de query, logs INFO `httpx2`, exceptions sans URL, `follow_redirects=False` (307 renvoyé), `Timeout`, `Limits`, `MockTransport`, coût `localhost`, divergences `urlsplit`/`httpx2.URL`, masquage par `Formatter`.
- Code du dépôt : `engine.py`, `store.py`, `runtime.py`, `jobs.py`, `api/*`, `core/*`, `tests/_support/jobs.py`, `tests/e2e/conftest.py`, `uvicorn.config.Config.configure_logging` (source inspectée).

### Secondary (MEDIUM confidence)
- `.arthemis/reports/verifs-techniques-cycle-1.md` §1 et §3 (comportement n8n, 16 Mio) ; `.planning/research/STACK.md`, `PITFALLS.md` (P1, P2, P6, M20-M23).

### Tertiary (LOW confidence)
- Statut exact renvoyé par n8n pour un corps > `N8N_PAYLOAD_SIZE_MAX` (erreur `raw-body` non classée) ; possibilité d'un 401/404 transitoire pendant la course P1 ; comportement double pile `localhost` de Docker Desktop. À confirmer sur un n8n réel en phase 5.

## Metadata

**Confidence breakdown :**
- Standard stack : HIGH — httpx2 déjà installé et exercé ; aucune nouvelle bibliothèque.
- Architecture : HIGH — miroir direct de l'Engine et du store existants ; points d'accroche lus dans le code.
- Contrat n8n : HIGH pour les 409/404/401 et textes (code source) ; MEDIUM/LOW pour 413 et la course P1.
- Pitfalls : HIGH (mesurés) sauf mention LOW.

**Research date :** 2026-10-20
**Valid until :** 2026-11-19 (n8n épinglé en 2.43.8 ; httpx2 jeune : revérifier si la version change)

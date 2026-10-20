# Phase 3: Rappel fiable - Context

**Gathered:** 2026-10-21
**Status:** Ready for planning

<domain>
## Phase Boundary

À chaque état terminal (`succeeded`, `failed`, `timeout`, `cancelled`, `interrupted`), le runner
appelle la `resumeUrl` n8n telle quelle avec `{ job_id, capability, status, duration_s, summary,
artifacts, error }`, réessaie de façon durable (y compris après redémarrage), distingue les
réponses de n8n, plafonne la taille, refuse les hôtes non autorisés, ne fuit jamais la `signature`,
et inscrit soumissions, refus, fins et rappels dans l'audit local.
Exigences : CB-01..05, SEC-05, SEC-06.

Le critère « une fois et une seule » de la ROADMAP est remplacé (décision utilisateur, STATE.md,
phase 3) par : **au moins une fois** ; n8n ne reprend qu'une fois ; un doublon reçoit 409 et est
tracé `delivered_duplicate`.

Hors phase : capacités réelles (phase 4), `deskgate init`, docker-compose, workflow d'exemple
(phase 5).

</domain>

<decisions>
## Implementation Decisions

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.arthemis/reports/llm-council-1.md` — sender, outbox sans payload, politique pure
- `.arthemis/reports/verifs-techniques-cycle-1.md` §1 (resumeUrl signée), §3 (taille)
- `.planning/research/PITFALLS.md` — P1, P2, P6, M20-M23
- `.planning/research/STACK.md` — httpx2
- `.planning/phases/02-c-ur-d-ex-cution/02-CONTEXT.md` et `02-0*-SUMMARY.md` — store, engine, lifespan, table callbacks
- `.planning/REQUIREMENTS.md` — CB-01..05, SEC-05, SEC-06 ; `.planning/STATE.md` — décision « au moins une fois »
- Code n8n 2.43.8 : `packages/cli/src/webhooks/waiting-webhooks.ts` (textes 409)

</canonical_refs>

<code_context>
## Existing Code Insights

- `src/deskgate/store.py` : table `callbacks` (pending insérée dans la transaction terminale), audit ajout seul.
- `src/deskgate/engine.py` : modèle de thread, `wake`, `stop`, horloge injectée — à reproduire pour le sender.
- `src/deskgate/runtime.py` : câblage lifespan (`on_shutdown`).
- `src/deskgate/core/redact.py`, `core/errors.py`, `core/config.py` (`callback_allowed_hosts` déjà lu).
- `tests/e2e/conftest.py` : `jobs_runner`, `FAKE_CAPS`, `write_config`.

</code_context>

<specifics>
## Specific Ideas

- Faux n8n (thread HTTP local) qui enregistre la query brute et rejoue 200, 409 « en cours », 409 « terminée », 404, 401, 500, coupure.
- Tâche de moins de 100 ms : le rappel doit attendre l'amorçage et finir livré.
- e2e : `taskkill /F /T` pendant un rappel en réessai, redémarrage, livraison.

</specifics>

<deferred>
## Deferred Ideas

- Route d'API de consultation de l'audit — après v0.1.
- Réécriture d'hôte de la `resumeUrl` (Docker Engine dans WSL) — si le spike 01-D1 l'impose (phase 5).

</deferred>

---

*Phase: 03-rappel-fiable*
*Context gathered: 2026-10-21*

---
phase: 03-rappel-fiable
verified: 2026-10-20T00:00:00Z
status: passed
score: 4/4 critères de succès vérifiés
---

# Phase 3 : Rappel fiable. Rapport de vérification

**Objectif :** n8n reprend toujours avec le bon statut, quel que soit l'état terminal ou l'arrêt du runner, sans fuite de la signature. Garantie au moins une fois ; un doublon reçoit 409 tracé `delivered_duplicate` (décision consignée dans STATE.md, non comptée comme écart).
**Statut :** passed. **Re-vérification :** non.

## Vérités observables

| # | Critère | Statut | Preuve |
|---|---------|--------|--------|
| 1 | Rappel `{job_id, capability, status, duration_s, summary, artifacts, error}` sur la resumeUrl telle quelle, 5 états, tâche < 100 ms | VERIFIED | `core/payload.py`, `sender.py` ; e2e `test_callback_flow.py` (succeeded < 100 ms, failed, timeout, cancelled, interrupted) ; faux n8n enregistre la ligne de requête brute |
| 2 | Réessai à délai croissant, reprise après redémarrage, réponses distinguées, abandon tracé | VERIFIED | `core/callback_policy.py` (2xx, 409, 401/403/404 sur 2e observation, 413, 5xx), états `delivered_duplicate`/`abandoned_stale`/`abandoned_exhausted` ; `store.py` (réclamation avec `maybe_delivered`, audit `callback.abandoned`) ; e2e `test_callback_restart.py` (taskkill /F /T) |
| 3 | Résumé > 1 Mio vers `summary.json` ; hôte non autorisé refusé | VERIFIED | `engine.py` l.378-416 (écriture atomique, repli `summary_write_failed`) ; `callback_host_not_allowed` (422 à la soumission, abandon sans envoi à l'envoi) ; tests `fs/test_engine_summary_cap.py`, `fs/test_sender_policy.py` |
| 4 | Signature absente des journaux, réponses, audit ; audit complet | VERIFIED | `core/redact.py` appliqué dans `store.py`, `jobs.py`, handlers de journal (`runtime.py`) ; e2e `test_callback_secret.py` ; audit `job.submitted`, `job.refused`, `job.<terminal>`, `callback.attempt`, `callback.delivered/abandoned` |

**Score :** 4/4.

## Artefacts et câblage

Tous présents et substantiels : `sender.py` (259 l.), `core/callback_policy.py`, `core/payload.py`, `core/redact.py`, `store.py`, `engine.py`. Le Sender est instancié, démarré après la recovery et arrêté par le lifespan (`runtime.py` l.107-138). Aucun TODO/FIXME/NotImplemented dans `src`. Flux de données réel : base SQLite vers Sender vers faux n8n par HTTP réel (e2e).

## Contrôles comportementaux (exécutés)

| Commande | Résultat |
|----------|----------|
| `uv run pytest -m "not e2e"` | 468 passed, 1 skipped (privilège de lien symbolique absent, sans rapport) |
| `uv run pytest -m e2e` | 26 passed |

Les phases 1 et 2 ne régressent pas (tests inclus dans ces deux passes).

## Couverture des exigences

| ID | Plans | Statut | Preuve |
|----|-------|--------|--------|
| CB-01 | 03-01, 03-03, 03-05, 03-06, 03-07, 03-08 | SATISFIED | payload + e2e 5 statuts |
| CB-02 | 03-01, 03-02, 03-04, 03-05, 03-08 | SATISFIED | backoff, réclamation durable, e2e redémarrage |
| CB-03 | 03-02, 03-04, 03-05, 03-07, 03-08 | SATISFIED | classification des réponses n8n 2.43.8 |
| CB-04 | 03-03, 03-05 | SATISFIED | summary.json, plafond |
| CB-05 | 03-01, 03-02, 03-05, 03-06 | SATISFIED | liste d'hôtes, 422 |
| SEC-05 | 03-03, 03-04, 03-05, 03-06, 03-07, 03-08 | SATISFIED | masquage + e2e secret |
| SEC-06 | 03-04, 03-05, 03-06, 03-08 | SATISFIED | audit |

Aucune exigence orpheline : les 7 ID mappés à la phase 3 dans REQUIREMENTS.md figurent dans au moins un plan.

## Anti-patterns

Aucun bloquant. Remarque d'information : la sémantique « une seule reprise » du ROADMAP est remplacée par « au moins une fois » (décision utilisateur), non comptée comme écart.

## Vérification humaine

Non requise : tous les comportements sont couverts par des tests e2e contre un faux n8n. Un essai contre un vrai n8n 2.43.8 reste un contrôle facultatif.

---
_Verified: 2026-10-20_
_Verifier: Claude (gsd-verifier)_

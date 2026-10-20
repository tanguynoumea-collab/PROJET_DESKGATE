---
phase: 02-c-ur-d-ex-cution
verified: 2026-10-20T00:00:00Z
status: passed
score: 5/5 critères de succès vérifiés
---

# Phase 2 : Coeur d'exécution, rapport de vérification

**Objectif :** n8n peut soumettre une tâche, la suivre, l'annuler, et le runner l'exécute une à la fois dans un Job Object avec délai maximum, sans jamais perdre l'état après un arrêt brutal.
**Re-vérification :** non, vérification initiale.

## Vérités observables

| # | Critère | Statut | Preuve |
|---|---------|--------|--------|
| 1 | POST /jobs renvoie 202 {job_id, status: queued} ; une tâche à la fois, ordre de soumission, survie au redémarrage | VERIFIE | `routes_jobs.py:28-31` (202), table SQLite `jobs` avec `seq`, index `jobs_status_seq`, `engine.py` ; tests fs/e2e `test_jobs_flow`, `test_jobs_restart` verts |
| 2 | GET /jobs/{id} et /logs : état, progression, résumé, artefacts, journaux ; work_dir et artefacts déclarés | VERIFIE | `routes_jobs.py:34-39`, `jobs.py`, `core/paths.py`, `deskgate_sdk/run.py` ; `test_routes_jobs`, `test_engine_results`, `test_sdk_worker` verts |
| 3 | Faux plugin hors délai : arbre entier arrêté (orphelin compris) puis timeout ; annulation idempotente (file ou en cours) | VERIFIE | `jobobject.py` (KILL_ON_JOB_CLOSE, jamais BREAKAWAY), `test_engine_timeout`, `test_engine_cancel`, `test_store_cancel`, `test_jobobject`, `test_spike_jobobject` verts |
| 4 | Après taskkill /F du runner en cours de tâche, le redémarrage passe la tâche en interrupted ; rappel = phase 3 | VERIFIE | `store.recover_interrupted` (store.py:394-405), insertion du rappel en outbox dans la même transaction ; décision consignée dans STATE.md ligne 77 ; `test_store_recovery`, e2e `test_jobs_restart`/`test_jobs_shutdown` verts |
| 5 | idempotency_key identique à une tâche non terminale refusée ; plugin en sous-processus sans shell, jamais dans le runner | VERIFIE | index unique partiel `jobs_idem` + contrôle store.py:256-295 (erreur 409 dédiée) ; `jobobject.py:170-175` Popen en liste, sans shell, lancé suspendu puis assigné au Job ; `test_store_queue`, `test_mutex` verts |

**Score :** 5/5

## Exécution des tests (lancés par le vérificateur)

| Commande | Résultat |
|----------|----------|
| `uv run pytest -m "not e2e"` | 313 passés, 1 ignoré (privilège de lien symbolique absent, sans lien avec la phase), 16 désélectionnés |
| `uv run pytest -m e2e` | 16 passés |

La régression de la phase 1 est couverte : tous les tests (unit, architecture, fs, proc, e2e) passent ensemble, y compris les frontières d'import (`tests/architecture`).

## Artefacts clés

Tous présents, substantiels et câblés : `engine.py` (450 lignes), `store.py` (406), `jobobject.py` (196), `jobs.py` (158), `runtime.py` (116), `api/routes_jobs.py`, `deskgate_sdk/run.py`, `core/states.py`, `core/outcome.py`, `core/worker_protocol.py`, faux plugins de test. Aucun TODO, FIXME ou NotImplemented dans `src/`.

## Couverture des exigences

Les IDs déclarés dans les frontmatter des 9 plans sont : JOB-01 à JOB-09, tous présents dans REQUIREMENTS.md (cochés, « Complete », mappés Phase 2). Aucune exigence orpheline.

| Exigence | Plans | Statut | Preuve |
|----------|-------|--------|--------|
| JOB-01 | 01, 07, 09 | SATISFAITE | POST /jobs 202 |
| JOB-02 | 03, 06, 09 | SATISFAITE | SQLite + moteur à tâche unique, tests queue/engine |
| JOB-03 | 07, 09 | SATISFAITE | GET /jobs/{id}, /logs |
| JOB-04 | 02, 03, 06, 07, 08, 09 | SATISFAITE | cancel idempotent, tests cancel |
| JOB-05 | 02, 04, 06, 08 | SATISFAITE | timeout avec arbre entier, tests timeout |
| JOB-06 | 03, 09 | SATISFAITE pour la phase 2 | passage interrupted vérifié ; l'envoi du rappel relève de la phase 3 (décision utilisateur dans STATE.md) |
| JOB-07 | 02, 04, 05, 06, 08 | SATISFAITE | Job Object, sans shell, hors processus runner |
| JOB-08 | 01, 03, 07, 09 | SATISFAITE | clé d'idempotence refusée |
| JOB-09 | 01, 05, 06, 08, 09 | SATISFAITE | work_dir et artefacts déclarés |

## Anti-patterns

Aucun bloquant. Un test ignoré pour cause d'environnement (lien symbolique, mode développeur désactivé) : information seulement.

## Vérification humaine

Aucune obligatoire. Les comportements critiques (arrêt brutal, arbre de processus, arrêt propre) sont couverts par des tests e2e réels avec de vrais processus.

## Synthèse

L'objectif de la phase est atteint : tous les critères de succès sont démontrés par le code et par des tests exécutés avec succès. Aucune lacune.

_Vérifié : 2026-10-20_
_Vérificateur : Claude (gsd-verifier)_

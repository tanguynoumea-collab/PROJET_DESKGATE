---
phase: 01-fondations-testables
verified: 2026-10-20T00:00:00Z
status: human_needed
score: 4/4 must-haves verified
human_verification:
  - test: "01-D1 : host.docker.internal joint un service lié à 127.0.0.1 (Docker Desktop)"
    expected: "Le conteneur reçoit la liste de répertoire (code 0) ; http.server journalise un GET 200 et l'IP source est notée"
    why_human: "Nécessite Docker Desktop sur la machine cible ; différé, bloque la phase 5 (pas un gap de la phase 1)"
---

# Phase 1 : Fondations testables — Rapport de vérification

**Objectif :** Un runner démarre localement avec une configuration valide, n'accepte que des requêtes authentifiées venant d'hôtes attendus et ne peut lire ou écrire que dans les racines autorisées.
**Statut :** human_needed (tous les contrôles automatiques passent ; seul 01-D1 reste différé)
**Re-vérification :** Non, vérification initiale

## Vérités observables (critères du ROADMAP)

| # | Vérité | Statut | Preuve |
|---|--------|--------|--------|
| 1 | `deskgate serve` n'écoute que sur 127.0.0.1 ; autre interface refusée sans option explicite | VERIFIED | `core/config.py` (l.105-122) refuse un host non loopback sans `allow_non_loopback` ; e2e `test_ecoute_loopback_seulement` et `test_config_non_loopback_refusee` passent |
| 2 | runner.toml invalide donne un échec clair en français ; second runner s'arrête sans toucher à la base | VERIFIED | `runtime.serve` : config, puis mutex, puis socket exclusif, puis `open_db` ; codes 2/3/4 avec messages français ; e2e `test_config_invalide_code_2`, `test_second_runner_code_3`, `test_second_runner_sans_base_existante`, `test_redemarrage_apres_kill` passent |
| 3 | /health sans jeton ni détail sensible ; autres routes 401 sans Bearer ; Host hors liste refusé en 4xx | VERIFIED | `api/middleware.py` (Host 400 externe, Bearer 401 sauf `/health`, y compris routes inconnues) ; `/health` renvoie seulement status, version, warnings ; `tests/unit/test_api_security.py` et e2e passent |
| 4 | /data <-> C:/BIM ; chemins hors racines refusés par tests d'attaque | VERIFIED | `core/paths.py` + `tests/unit/test_paths_mapping.py`, `test_paths_attacks.py`, `tests/fs/test_paths_real.py` passent (un test de lien symbolique ignoré : privilège absent sur ce poste) |

**Score :** 4/4

### Artefacts et câblage

Tous présents, substantiels et câblés : `cli.py` appelle `runtime.serve` ; `runtime.py` appelle `load_config`, `acquire_mutex`, `bind_exclusive`, `open_db`, `create_app` puis `uvicorn.Server.run(sockets=[sock])` ; `app.py` installe les middlewares Host puis Bearer ; jeton stocké haché (`token_sha256`, `verify_token`). Aucun TODO, FIXME ni placeholder dans `src/deskgate`.

Note : le module `paths` n'est pas encore consommé par une route (attendu : les routes de fichiers arrivent dans les phases suivantes) ; le périmètre de la phase 1 est le module et ses tests.

### Vérifications comportementales

| Comportement | Commande | Résultat | Statut |
|---|---|---|---|
| Tests hors e2e | `uv run pytest -m "not e2e"` | 159 réussis, 1 ignoré | PASS |
| Tests e2e (processus réels) | `uv run pytest -m e2e` | 8 réussis | PASS |
| Lint / types | `ruff check`, `pyright` | 0 erreur | PASS |

### Couverture des exigences

| Exigence | Plan | Statut | Preuve |
|---|---|---|---|
| RUN-01 | 01-01, 01-04, 01-05 | SATISFIED | Config loopback + e2e écoute |
| RUN-02 | 01-04, 01-05 | SATISFIED | Config typée stricte, messages français, code 2 |
| RUN-03 | 01-01, 01-05 | SATISFIED | Mutex + e2e second runner |
| RUN-04 | 01-03, 01-05 | SATISFIED | `/health` public minimal |
| SEC-01 | 01-03 | SATISFIED | Bearer 401, jeton haché |
| SEC-02 | 01-03 | SATISFIED | HostCheckMiddleware 400 |
| SEC-03 | 01-02 | SATISFIED | Mapping /data <-> C:/BIM testé |
| SEC-04 | 01-02 | SATISFIED | Tests d'attaque |

Les 8 IDs de la phase (RUN-01..04, SEC-01..04) sont couverts par les plans et cochés dans REQUIREMENTS.md ; aucune exigence orpheline (SEC-05/06 sont en phase 3).

### Anti-patterns

Aucun bloquant.

### Vérification humaine requise

1. **01-D1 : host.docker.internal vers un service sur 127.0.0.1** (différé, bloque la phase 5). Démarrer Docker Desktop, lancer `py -3.14 -m http.server 8799 --bind 127.0.0.1`, puis `docker run --rm alpine wget -qO- http://host.docker.internal:8799/`. Attendu : code 0, GET 200 journalisé, IP source notée. En cas d'échec : gap, repli D-02 (`allow_non_loopback` sur l'IP vEthernet) traité en phase 5.

Aussi à noter : le test de lien symbolique réel est ignoré sur ce poste (mode développeur désactivé) ; à rejouer avec privilège si souhaité.

## Synthèse

Aucun gap. L'objectif de la phase est atteint dans le code et confirmé par l'exécution des tests.

_Vérifié : 2026-10-20_
_Vérificateur : Claude (gsd-verifier)_

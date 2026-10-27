---
phase: 01-fondations-testables
plan: 03
subsystem: api
tags: [fastapi, asgi, bearer, host-check, sha256, errors, redaction]
requires:
  - phase: 01-01
    provides: outillage uv/ruff/pyright/pytest et tests AST de frontière
provides:
  - core/tokens (hash_token, verify_token, generate_token)
  - core/hostcheck (is_allowed_host, ALLOWED_HOSTS)
  - core/errors (codes stables, error_body, http_code, HTTP_MESSAGES_FR)
  - core/redact (redact_signature)
  - api/ (create_app, HostCheckMiddleware, BearerAuthMiddleware, handlers D-08, /health)
affects: [01-04, 01-05, phase-2]
tech-stack:
  added: []
  patterns: [middlewares ASGI purs (Host externe, Bearer interne), erreurs D-08 en français, logique de sécurité pure dans core/]
key-files:
  created:
    - src/deskgate/core/tokens.py
    - src/deskgate/core/hostcheck.py
    - src/deskgate/core/errors.py
    - src/deskgate/core/redact.py
    - src/deskgate/api/__init__.py
    - src/deskgate/api/app.py
    - src/deskgate/api/middleware.py
    - src/deskgate/api/handlers.py
    - src/deskgate/api/routes_health.py
    - tests/unit/test_tokens.py
    - tests/unit/test_hostcheck.py
    - tests/unit/test_redact.py
    - tests/unit/test_api_security.py
  modified: []
key-decisions:
  - "Les handlers n'utilisent pas assert (ruff S101 dans src) : cast() vers le type d'exception attendu"
patterns-established:
  - "Message 422 construit depuis loc + type seulement, jamais input ni msg"
requirements-completed: [RUN-04, SEC-02]
duration: 20min
completed: 2026-10-20
---

# Phase 1 Plan 03: Sécurité HTTP (jeton, Host, erreurs) Summary

Noyau pur jeton/Host/erreurs/masquage et coquille `api/` : deux middlewares ASGI (Host puis Bearer SHA-256 en temps constant), erreurs D-08 en français et `/health` public, prouvés par TestClient.

## Tâches

| Tâche | Commits | Contenu |
|---|---|---|
| 1 | 5ada05b (RED), 064d89f (GREEN) | tokens, hostcheck, errors, redact et leurs tests unitaires |
| 2 | a8510cf (RED), f87138f (GREEN) | api/ (app, middleware, handlers, routes_health) et test_api_security (16 cas + paramétrages) |

## Vérification

`ruff check`, `ruff format --check`, `pyright` (0 erreur), `pytest -m unit` (113 réussis), `pytest tests/architecture` (9 réussis, core toujours pur), `grep "_test/" src/` vide.

## Exigences

- RUN-04 : atteint (/health 200 sans jeton, sans chemin ni secret).
- SEC-02 : atteint (400 host_not_allowed avant l'authentification, host.docker.internal accepté).
- SEC-01 : partiel. Le 401 sur toute route sauf /health et la comparaison hachée sont livrés ; le stockage du jeton haché dans la configuration relève du plan 01-04. Laissé « Pending » dans REQUIREMENTS.md.

## Éléments différés

différé : 01-D1 (spike D-13(a) `host.docker.internal`, Docker Desktop requis), inscrit dans `01-HUMAN-UAT.md`, `blocks: 5`.

## Deviations from Plan

**1. [Rule 3 - Blocage] Règles ruff du dépôt**
- **Found during:** Tâche 2
- **Issue:** S101 (`assert` pour affiner le type d'exception dans les handlers), E501 (docstring de 101 caractères), S105 (constante `TOKEN` de test).
- **Fix:** `cast()` à la place de `assert`, docstring raccourcie, `# noqa: S105` sur le jeton de test.
- **Commit:** f87138f

**2. [Rule 2 - Robustesse] Test supplémentaire hors plan** : schéma `Basic` refusé, et non-fuite de la valeur fautive dans le message 422. Aucun changement de comportement.

Hors ces points : plan exécuté tel quel.

## Known Stubs

Aucun.

## Self-Check: PASSED

---
phase: 3
slug: rappel-fiable
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-10-21
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1 (infrastructure posée en phase 1) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (marqueurs `unit`, `fs`, `proc`, `e2e`) |
| **Quick run command** | `uv run pytest -m unit -q -x` |
| **Full suite command** | `uv run pytest -m "not e2e"` puis `uv run pytest -m e2e` |
| **Estimated runtime** | ~10 s (unit), ~120 s (suite complète) |

---

## Sampling Rate

- **After every task commit:** `uv run pytest -m unit -q -x` + `uv run ruff check`
- **After every plan wave:** `uv run pytest -m "not e2e"` + `uv run pyright`
- **Before `/gsd:verify-work`:** gate complet vert, e2e compris
- **Max feedback latency:** 120 secondes

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | CB-02, CB-05 | unit | `uv sync --locked && uv run pytest tests/unit/test_config.py tests/unit/test_locations.py tests/architecture/test_import_boundaries.py -q -x` | ✅ (à étendre) | ⬜ pending |
| 03-01-02 | 01 | 1 | CB-01 (D-05) | fs | `uv run pytest tests/fs/test_fake_n8n.py -q -x` | ❌ créé par la tâche | ⬜ pending |
| 03-02-01 | 02 | 1 | CB-02, CB-03, CB-05 | unit (TDD) | `uv run pytest tests/unit/test_callback_policy.py tests/unit/test_callback_url.py -q -x` | ❌ créé (RED d'abord) | ⬜ pending |
| 03-03-01 | 03 | 1 | CB-01, CB-04 | unit (TDD) | `uv run pytest tests/unit/test_payload.py -q -x` | ❌ créé (RED d'abord) | ⬜ pending |
| 03-03-02 | 03 | 1 | SEC-05 | unit (TDD) | `uv run pytest tests/unit/test_redact.py -q -x` | ✅ (à étendre) | ⬜ pending |
| 03-04-01 | 04 | 2 | SEC-05, SEC-06 | fs | `uv run pytest tests/fs/test_store_schema.py tests/fs/test_store_audit.py tests/fs/test_store_queue.py -q -x` | ✅ / ❌ test_store_audit créé | ⬜ pending |
| 03-04-02 | 04 | 2 | CB-02, CB-03 | fs (TDD) | `uv run pytest tests/fs/test_store_callbacks.py -q -x` | ❌ créé (RED d'abord) | ⬜ pending |
| 03-05-01 | 05 | 3 | CB-04 | fs (TDD) | `uv run pytest tests/fs/test_engine_summary_cap.py tests/fs/test_engine_tick.py -q -x` | ❌ créé (RED d'abord) | ⬜ pending |
| 03-05-02 | 05 | 3 | CB-05, SEC-05, SEC-06 | fs | `uv run pytest tests/fs/test_routes_jobs.py tests/fs/test_audit_events.py -q -x` | ✅ / ❌ test_audit_events créé | ⬜ pending |
| 03-06-01 | 06 | 3 | CB-01, CB-05 | fs (TDD, faux n8n) | `uv run pytest tests/fs/test_sender_send.py -q -x` | ❌ créé (RED d'abord) | ⬜ pending |
| 03-06-02 | 06 | 3 | CB-02, CB-03, SEC-05, SEC-06 | fs (faux n8n, MockTransport) | `uv run pytest tests/fs/test_sender_retry.py tests/fs/test_sender_policy.py -q -x` | ❌ créé | ⬜ pending |
| 03-07-01 | 07 | 4 | SEC-05 | unit + e2e | `uv run pytest tests/unit/test_logging.py -q -x && uv run pytest -m e2e tests/e2e/test_serve.py tests/e2e/test_jobs_shutdown.py -q -x` | ❌ test_logging créé | ⬜ pending |
| 03-07-02 | 07 | 4 | CB-01, CB-03 | e2e | `uv run pytest -m e2e tests/e2e/test_callback_flow.py -q -x` | ❌ créé | ⬜ pending |
| 03-08-01 | 08 | 5 | CB-01, CB-02, CB-03 | e2e (taskkill) | `uv run pytest -m e2e tests/e2e/test_callback_restart.py -q -x` | ❌ créé | ⬜ pending |
| 03-08-02 | 08 | 5 | SEC-05, SEC-06 | e2e + gate | `uv run pytest -m e2e tests/e2e/test_callback_secret.py -q -x` puis gate complet | ❌ créé | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Aucune tâche sans commande automatisée : la continuité d'échantillonnage est assurée (jamais 3 tâches consécutives sans vérification).

---

## Wave 0 Requirements

- [ ] Faux serveur n8n (thread HTTP sur 127.0.0.1) rejouant 200, 409 « running already », 409 « has finished already », 404, 401, 500, coupure, et enregistrant la ligne de requête brute — plan 03-01 tâche 2 (`tests/_support/fake_n8n.py`, fixture `fake_n8n`)
- [ ] `httpx2` en dépendance d'exécution, `uv.lock` régénéré — plan 03-01 tâche 1
- [ ] Tests unitaires purs créés en RED avant le code (03-02, 03-03, 03-04 tâche 2, 03-05 tâche 1, 03-06 tâche 1) : chaque plan TDD crée son fichier de test avant l'implémentation

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 120s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planificateur, 2026-10-21 (carte remplie depuis les plans 03-01 à 03-08)

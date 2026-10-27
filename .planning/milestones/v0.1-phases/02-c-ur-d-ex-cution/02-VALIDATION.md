---
phase: 2
slug: c-ur-d-ex-cution
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-10-20
---

# Phase 2 — Validation Strategy

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
| 02-01-01 | 01 | 1 | JOB-09 (work_root), D-01 | unit | `uv run pytest tests/unit/test_config.py -q -x` | ✅ à étendre | ⬜ pending |
| 02-01-02 | 01 | 1 | JOB-01, JOB-08 | unit | `uv run pytest tests/unit/test_jobspec.py tests/architecture -q -x` | ❌ créé par la tâche | ⬜ pending |
| 02-02-01 | 02 | 1 | JOB-04, JOB-05 | unit (TDD) | `uv run pytest tests/unit/test_states.py tests/unit/test_outcome.py -q -x` | ❌ créé par la tâche | ⬜ pending |
| 02-02-02 | 02 | 1 | JOB-07 | unit (TDD) | `uv run pytest tests/unit/test_worker_protocol.py -q -x` | ❌ créé par la tâche | ⬜ pending |
| 02-03-01 | 03 | 1 | JOB-02 | fs | `uv run pytest tests/fs/test_store_schema.py -q -x` | ❌ créé par la tâche | ⬜ pending |
| 02-03-02 | 03 | 1 | JOB-02, JOB-04, JOB-06, JOB-08 | fs | `uv run pytest tests/fs/test_store_queue.py tests/fs/test_store_cancel.py tests/fs/test_store_recovery.py -q -x` | ❌ créé par la tâche | ⬜ pending |
| 02-04-01 | 04 | 1 | JOB-05, JOB-07 | unit + proc | `uv run pytest tests/unit/test_env.py tests/proc/test_jobobject.py -q -x` | ❌ créé par la tâche | ⬜ pending |
| 02-04-02 | 04 | 1 | JOB-07 | unit (AST) + proc | `uv run pytest tests/architecture tests/proc/test_spike_jobobject.py -q -x` | ✅ à adapter | ⬜ pending |
| 02-05-01 | 05 | 2 | JOB-07 | unit (contrat, AST) | `uv run pytest tests/unit/test_sdk_contract.py tests/architecture -q -x` | ❌ créé par la tâche | ⬜ pending |
| 02-05-02 | 05 | 2 | JOB-07, JOB-09 | proc | `uv run pytest tests/proc/test_sdk_worker.py -q -x` | ❌ créé par la tâche | ⬜ pending |
| 02-06-01 | 06 | 2 | JOB-02, JOB-07, JOB-09 | fs (faux launcher) | `uv run pytest tests/fs/test_engine_tick.py -q -x` | ❌ créé par la tâche | ⬜ pending |
| 02-06-02 | 06 | 2 | JOB-04, JOB-05 | fs (faux launcher, thread) | `uv run pytest tests/fs/test_engine_tick.py -q -x` | ❌ créé par 02-06-01 | ⬜ pending |
| 02-07-01 | 07 | 2 | JOB-01, JOB-03, JOB-08 | fs | `uv run pytest tests/fs/test_routes_jobs.py -q -x` | ❌ créé par la tâche | ⬜ pending |
| 02-07-02 | 07 | 2 | JOB-01, JOB-03, JOB-04 | fs (TestClient) | `uv run pytest tests/fs/test_routes_jobs.py tests/unit/test_api_security.py -q -x` | ❌ créé par 02-07-01 | ⬜ pending |
| 02-08-01 | 08 | 3 | JOB-07, JOB-09 | proc | `uv run pytest tests/proc/test_engine_results.py -q -x` | ❌ créé par la tâche | ⬜ pending |
| 02-08-02 | 08 | 3 | JOB-04, JOB-05 | proc | `uv run pytest tests/proc/test_engine_timeout.py tests/proc/test_engine_cancel.py -q -x` | ❌ créé par la tâche | ⬜ pending |
| 02-09-01 | 09 | 4 | JOB-06 (câblage) | unit + e2e | `uv run pytest tests/unit/test_cli.py -q -x && uv run pytest -m e2e tests/e2e/test_serve.py -q -x` | ✅ | ⬜ pending |
| 02-09-02 | 09 | 4 | JOB-01, JOB-02, JOB-03, JOB-04, JOB-08, JOB-09 | e2e | `uv run pytest -m e2e tests/e2e/test_jobs_flow.py -q -x` | ❌ créé par la tâche | ⬜ pending |
| 02-09-03 | 09 | 4 | JOB-06 | e2e | `uv run pytest -m e2e tests/e2e/test_jobs_restart.py tests/e2e/test_jobs_shutdown.py -q -x` | ❌ créé par la tâche | ⬜ pending |

Chaque tâche crée son propre fichier de test (TDD ou test écrit dans la même tâche) : aucune référence
`MISSING`, pas de vague 0 séparée.

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Faux plugins de test (`sleep`, `spawn_orphan`, `bad_result`, `chatty`, `artifact_outside`, `artifact_ok`, `exit_code`, `fail`) — plan 02-05, tâche 2
- [ ] Déclaration `[capabilities."demo.*"]` : `tests/_support/jobs.py` (02-06) et `tests/e2e/conftest.py` (02-09)
- [ ] `src/deskgate/jobobject.py` remplaçant `tests/_support/winjob.py` — plan 02-04
- [ ] Aide `tests/_support/procs.py` (`is_alive`, `wait_dead`) — plan 02-04, tâche 2

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

**Approval:** planificateur, 2026-10-20 (carte remplie depuis les plans 02-01 à 02-09)

---
phase: 4
slug: capacit-s-v0-1
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-10-21
---

# Phase 4 — Validation Strategy

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
| 04-01-T1 | 01 | 1 | CAP-05 | unit + lock | `uv lock --check && uv sync --locked && uv run pytest -m unit -q -x` | ✅ (existant) | ⬜ pending |
| 04-01-T2 | 01 | 1 | CAP-05 | bim | `uv run pytest tests/plugins -q -x` | ❌ créé par la tâche | ⬜ pending |
| 04-01-T3 | 01 | 1 | CAP-05 | unit | `uv run pytest tests/architecture -q -x` | ⚠️ existant étendu | ⬜ pending |
| 04-02-T1 | 02 | 1 | CAP-01, CAP-04 | unit | `uv run pytest tests/unit/test_config_capabilities.py tests/unit/test_path_params.py tests/unit/test_worker_protocol.py tests/unit/test_sdk_contract.py -q -x` | ❌ créé par la tâche (TDD) | ⬜ pending |
| 04-02-T2 | 02 | 1 | CAP-01, CAP-04 | fs + proc | `uv run pytest tests/fs/test_engine_launch_params.py tests/fs/test_submit_path_params.py tests/proc/test_sdk_settings.py -q -x` | ❌ créé par la tâche (TDD) | ⬜ pending |
| 04-03-T1 | 03 | 2 | CAP-05 | bim (fumée CLI) | `uv run python -c "…deskgate-bcf write --input absent.json… code 2"` (voir plan) | n/a | ⬜ pending |
| 04-03-T2 | 03 | 2 | CAP-05, CAP-02 | bim | `uv run pytest plugins/bim/bcf/tests -q -x` | ❌ créé par la tâche (TDD) | ⬜ pending |
| 04-04-T1 | 04 | 2 | CAP-01 | unit | `uv run pytest plugins/bim/tests/test_grouping.py -q -x` | ❌ créé par la tâche (TDD) | ⬜ pending |
| 04-04-T2 | 04 | 2 | CAP-01, CAP-03 | bim + proc | `uv run pytest plugins/bim/tests/test_clash_hard.py plugins/bim/tests/test_clash_clearance.py plugins/bim/tests/test_clash_empty.py -q -x` | ❌ créé par la tâche (TDD) | ⬜ pending |
| 04-04-T3 | 04 | 2 | CAP-01 (D-06, D-07) | bim + proc | `uv run pytest plugins/bim/tests -q -x` | ❌ créé par la tâche (TDD) | ⬜ pending |
| 04-05-T1 | 05 | 2 | CAP-04 | unit + pyright | `uv run pytest tests/architecture -q -x && uv run pyright src/deskgate/workers tests/mcp_fake tests/_support/mcp_env.py` | ⚠️ existant | ⬜ pending |
| 04-05-T2 | 05 | 2 | CAP-04 | proc + mcp | `uv run pytest tests/proc/test_mcp_call.py tests/proc/test_mcp_errors.py -q -x` | ❌ créé par la tâche (TDD) | ⬜ pending |
| 04-05-T3 | 05 | 2 | CAP-04 | proc + mcp | `uv run pytest tests/proc/test_mcp_tree.py -q -x` | ❌ créé par la tâche (TDD) | ⬜ pending |
| 04-06-T1 | 06 | 2 | CAP-01 (D-07 mémoire) | unit + fs | `uv run pytest tests/unit/test_outcome.py tests/fs/test_engine_memory.py tests/fs/test_engine_tick.py -q -x` | ⚠️ existant étendu + ❌ nouveau | ⬜ pending |
| 04-06-T2 | 06 | 2 | CAP-01 (D-07 mémoire) | proc | `uv run pytest tests/proc/test_engine_memory.py tests/proc/test_jobobject.py -q -x` | ❌ créé par la tâche (TDD) | ⬜ pending |
| 04-07-T1 | 07 | 3 | CAP-02 | unit | `uv run pytest plugins/bim/tests/test_bcfdoc.py -q -x` | ❌ créé par la tâche (TDD) | ⬜ pending |
| 04-07-T2 | 07 | 3 | CAP-02, CAP-05 | bim + proc | `uv run pytest plugins/bim/tests -q -x` | ❌ créé par la tâche (TDD) | ⬜ pending |
| 04-07-T3 | 07 | 3 | CAP-01..05 (docs) | unit | `uv run pytest tests/unit/test_runner_example.py tests/unit/test_locations.py -q -x` | ❌ créé par la tâche | ⬜ pending |

Chaque tâche a une commande automatisée ; aucune suite de trois tâches sans vérification. Les tests `bim` exigent `uv` dans le PATH
(fixture `plugin_envs`, environnements dans `.cache/plugin-envs/pyXY/`) ; la matrice CI 3.11/3.13 tranche la compatibilité 3.13.

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Fixture `plugin_envs` (venvs uv des plugins deskgate-bim et deskgate-bcf) — 04-01-T2
- [ ] Générateur d'IFC synthétiques `plugins/bim/tests/envside/ifc_synth.py` — 04-04-T2
- [ ] Mini-serveur MCP de test (echo, add, sleep, erreur, spawn_orphan, env) — 04-05-T1
- [ ] Marqueurs `bim` et `mcp`, `.cache/` ignoré, `mcp` en dépendance du cœur — 04-01-T1

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| Rendu du BCF (deux vues, contexte gris transparent, couleurs) dans BIMcollab Zoom | CAP-02 | Rendu visuel d'un logiciel tiers | Item différable 04-D1 (04-07, `<manual-items>`, blocks 5) : ouvrir le .bcf produit sur une maquette réelle en phase 5 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 120s (par tâche ; la première construction des environnements de plugins peut dépasser à froid)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planificateur (2026-10-21)

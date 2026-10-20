---
phase: 4
slug: capacit-s-v0-1
status: draft
nyquist_compliant: false
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

À remplir par le planificateur depuis `04-RESEARCH.md` § Validation Architecture (CAP-01..05).

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Fixture `plugin_envs` (venvs uv des plugins deskgate-bim et deskgate-bcf) et générateur d'IFC synthétiques
- [ ] Mini-serveur MCP de test (echo, sleep, erreur, spawn_orphan)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| Rendu du BCF (deux vues, contexte gris transparent, couleurs) dans BIMcollab Zoom | CAP-02 | Rendu visuel d'un logiciel tiers | Ouvrir le .bcf produit sur une maquette réelle en phase 5 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: false` set in frontmatter

**Approval:** pending

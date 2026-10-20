---
phase: 3
slug: rappel-fiable
status: draft
nyquist_compliant: false
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

À remplir par le planificateur depuis `03-RESEARCH.md` § Validation Architecture.

---

## Wave 0 Requirements

- [ ] Faux serveur n8n (thread HTTP sur 127.0.0.1) rejouant 200, 409 « running already », 409 « has finished already », 404, 401, 500, coupure, et enregistrant la ligne de requête brute
- [ ] `httpx2` en dépendance d'exécution, `uv.lock` régénéré

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** planificateur, 2026-10-21 (carte remplie depuis les plans 02-01 à 02-09)

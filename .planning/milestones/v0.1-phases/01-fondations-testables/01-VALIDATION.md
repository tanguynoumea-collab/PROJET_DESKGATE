---
phase: 1
slug: fondations-testables
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-10-20
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1 (+ `starlette.testclient` via httpx2) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (marqueurs `unit`, `fs`, `proc`, `e2e`, `--strict-markers`) — installé en vague 0 |
| **Quick run command** | `uv run pytest -m unit -q -x` |
| **Full suite command** | `uv run pytest -m "not e2e"` puis `uv run pytest -m e2e` |
| **Estimated runtime** | ~5 s (unit), ~60 s (suite complète) |

---

## Sampling Rate

- **After every task commit:** `uv run pytest -m unit -q -x` + `uv run ruff check`
- **After every plan wave:** `uv run pytest -m "not e2e"` + `uv run pyright`
- **Before `/gsd:verify-work`:** gate complet D-12 vert, e2e compris
- **Max feedback latency:** 60 secondes

---

## Per-Task Verification Map

Rempli par le planificateur à partir de `01-RESEARCH.md` § Validation Architecture (table Exigences → tests).

| Req | Plan/Tâche | Comportement | Type | Commande automatisée |
|-----|------------|--------------|------|----------------------|
| D-12 | 01-01/T1 | Gate outillé, CI déclarée | CI | `uv sync --locked && uv run ruff check && uv run pyright && uv build --all-packages` |
| D-10 | 01-01/T1 | `core/` pur ; frontière GPL ; pas de BIM ; pas de `shell=True` | unit | `uv run pytest tests/architecture` |
| RUN-01 | 01-01/T2 | Socket exclusif (10048, 10013) | unit | `uv run pytest tests/unit/test_instance_socket.py` |
| RUN-03 | 01-01/T2 | Mutex ; libéré après `taskkill /F /T` | proc | `uv run pytest -m proc tests/proc/test_mutex.py` |
| D-13(c) | 01-01/T3 | Job Object tue le petit-enfant orphelin | proc | `uv run pytest -m proc tests/proc/test_spike_jobobject.py` |
| SEC-03 | 01-02/T1 | Correspondance `/data` ↔ `C:/BIM` par segments | unit | `uv run pytest tests/unit/test_paths_mapping.py` |
| SEC-04 | 01-02/T1 | Table d'attaques lexicales | unit | `uv run pytest tests/unit/test_paths_attacks.py` |
| SEC-04 | 01-02/T2 | Jonctions, ADS, réservés, préfixe frère, symlink (skipif) | fs | `uv run pytest -m fs tests/fs/test_paths_real.py` |
| SEC-01 | 01-03/T1 | SHA-256 + `compare_digest` | unit | `uv run pytest tests/unit/test_tokens.py` |
| SEC-02 | 01-03/T1 | Liste Host stricte | unit | `uv run pytest tests/unit/test_hostcheck.py` |
| SEC-01, SEC-02, RUN-04 | 01-03/T2 | 401/400/404/405/422/500 au format D-08 ; `/health` ; jeton absent des journaux | unit | `uv run pytest tests/unit/test_api_security.py` |
| RUN-01, RUN-02 | 01-04/T1 | Config stricte, loopback, messages FR sans fuite | unit | `uv run pytest tests/unit/test_config.py` |
| D-01 | 01-04/T2 | Dossier de données, gabarit valide | unit | `uv run pytest tests/unit/test_locations.py` |
| RUN-02 | 01-05/T1 | CLI, `dev-token`, config absente → 2 | unit | `uv run pytest tests/unit/test_cli.py` |
| RUN-01..04 | 01-05/T2 | `deskgate serve` de bout en bout (loopback, codes 2 et 3, redémarrage, /health) | e2e | `uv run pytest -m e2e tests/e2e/test_serve.py` |
| D-13(a) | 01-D1 (différé, 01-03) | `host.docker.internal` → 127.0.0.1 | manuel | voir Manual-Only |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml`, `uv.lock`, squelette `src/deskgate/`, `.github/workflows/ci.yml`
- [ ] `tests/conftest.py` : fixtures `instance_name`, `data_home`, `free_port`, `junction`, `symlink_ok`, `runner_process`
- [ ] Fichiers de test listés ci-dessus

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `host.docker.internal` joint un service sur 127.0.0.1 | D-13(a) / INS-05 | Docker Desktop non démarré, non scriptable en CI `windows-latest` | Procédure `01-RESEARCH.md` Open Questions §1 ; résultat consigné dans le SUMMARY |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

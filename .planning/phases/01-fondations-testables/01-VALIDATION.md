---
phase: 1
slug: fondations-testables
status: draft
nyquist_compliant: false
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

| Req | Comportement | Type | Commande automatisée |
|-----|--------------|------|----------------------|
| RUN-01 | Config refuse host non loopback sans `allow_non_loopback` ; défaut 127.0.0.1:8765 | unit | `pytest tests/unit/test_config.py -k loopback` |
| RUN-01 | `deskgate serve` n'écoute que sur 127.0.0.1 ; socket exclusif | e2e + unit | `pytest -m e2e tests/e2e/test_serve.py` ; `pytest tests/unit/test_instance_socket.py` |
| RUN-02 | Config invalide → échec, message FR citant la clé, sans fuite ; code de sortie 2 | unit + e2e | `pytest tests/unit/test_config.py` ; `pytest -m e2e -k config_invalide` |
| RUN-03 | Mutex ; second runner code 3 sans toucher la base ; redémarrage après `taskkill /F /T` | proc + e2e | `pytest -m proc tests/proc/test_mutex.py` ; `pytest -m e2e -k "second_runner or redemarrage"` |
| RUN-04 | `/health` 200 sans jeton, sans chemin ni secret | unit + e2e | `pytest tests/unit/test_api_security.py -k health` |
| SEC-01 | 401 sans/mauvais jeton, y compris route inconnue ; jeton clair jamais journalisé | unit | `pytest tests/unit/test_api_security.py tests/unit/test_tokens.py` |
| SEC-02 | 400 `host_not_allowed` ; Host vérifié avant l'auth | unit | `pytest tests/unit/test_hostcheck.py` |
| SEC-03 | Correspondance `/data` ↔ `C:/BIM` par segments | unit | `pytest tests/unit/test_paths_mapping.py` |
| SEC-04 | Attaques lexicales et réelles (jonctions, ADS, UNC, réservés, préfixe ; symlink en skipif explicite) | unit + fs | `pytest tests/unit/test_paths_attacks.py` ; `pytest -m fs tests/fs/test_paths_real.py` |
| D-10 | `core/` pur ; frontière GPL | unit | `pytest tests/architecture` |
| D-13 | Spikes bind exclusif et Job Object | proc | `pytest -m proc tests/proc/test_spike_jobobject.py` |

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

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

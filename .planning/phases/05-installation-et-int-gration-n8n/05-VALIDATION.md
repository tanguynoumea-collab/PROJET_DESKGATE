---
phase: 5
slug: installation-et-int-gration-n8n
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-10-21
---

# Phase 5 — Stratégie de validation

> Contrat de validation de la phase, pour l'échantillonnage pendant l'exécution.
> Source : `05-RESEARCH.md` § Architecture de validation.

---

## Infrastructure de tests

| Propriété | Valeur |
|----------|-------|
| **Framework** | pytest 9.1 (+ `pytest-timeout`), marqueurs `unit`, `fs`, `proc`, `e2e`, `bim`, `mcp` ; à déclarer : `scheduler`, `docker` |
| **Config** | `pyproject.toml` (`--strict-markers`) |
| **Commande rapide** | `uv run pytest -m unit -x -q tests/unit` |
| **Suite complète** | `uv run pytest -m "not e2e"` puis `uv run pytest -m e2e` |
| **Durée estimée** | ~30 s (rapide) ; suite complète de l'ordre de quelques minutes |

---

## Cadence d'échantillonnage

- **Après chaque commit de tâche :** `uv run pytest -m unit -x -q` plus le fichier de test touché
- **Après chaque vague :** `uv run pytest -m "not e2e"`
- **Avant `/gsd:verify-work` :** gate complet du profil vert (`ruff check`, `ruff format --check`, `pyright`, `pytest -m "not e2e"`, `uv build --all-packages`, `pytest -m e2e`)
- **Latence maximale de retour :** 30 s
- Les tests `scheduler` et `docker` s'exécutent sur cette machine ; sans Docker, ils échouent explicitement (`pytest.fail`, jamais de saut silencieux).

---

## Carte de vérification par tâche

| Plan (suggéré) | Vague | Exigence | Type | Commande automatique | Fichier existe | Statut |
|---------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01 | 1 | INS-02 | unit | `uv run pytest tests/unit/test_scheduler_xml.py -x` | ❌ W0 | ⬜ pending |
| 05-01 | 1 | INS-02 | scheduler | `uv run pytest -m scheduler tests/proc/test_scheduler_real.py -x` | ❌ W0 | ⬜ pending |
| 05-02 | 1 | INS-01 | unit | `uv run pytest tests/unit/test_cli_version.py -x` | ❌ W0 | ⬜ pending |
| 05-02 | 1 | runtime | e2e | `uv run pytest -m e2e tests/e2e/test_serve_logfile.py -x` | ❌ W0 | ⬜ pending |
| 05-03 | 2 | INS-01 | unit | `uv run pytest tests/unit/test_init.py -x` | ❌ W0 | ⬜ pending |
| 05-04 | 3 | INS-02 | unit | `uv run pytest tests/unit/test_doctor_task.py -x` | ❌ W0 | ⬜ pending |
| 05-04 | 3 | D-04 | unit | `uv run pytest tests/unit/test_doctor.py -x` | ❌ W0 | ⬜ pending |
| 05-05 | 1 | INS-03 | docker | `uv run pytest -m docker tests/unit/test_compose.py -x` | ❌ W0 | ⬜ pending |
| 05-05 | 1 | INS-04 | unit | `uv run pytest tests/unit/test_example_workflow.py -x` | ❌ W0 | ⬜ pending |
| 05-06 | 4 | INS-05 | acceptation | `docker compose exec -T n8n wget -qO- http://host.docker.internal:8765/health` | n/a | ⬜ pending |
| 05-07 | 5 | INS-04, ACC-01, ACC-02 | acceptation | script de `scripts/recette/` (Modèle 8 de la recherche) | ❌ W0 | ⬜ pending |

*Statut : ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Exigences de la vague 0

- [ ] `tests/unit/test_init.py`, `test_cli_version.py`, `test_scheduler_xml.py`, `test_doctor.py`, `test_doctor_task.py`, `test_compose.py`, `test_example_workflow.py`
- [ ] `tests/proc/test_scheduler_real.py` (marqueur `scheduler`, tâche jetable `DeskgateTest-<uuid>`, suppression en `finally`)
- [ ] `tests/e2e/test_serve_logfile.py`
- [ ] marqueurs `scheduler` et `docker` dans `pyproject.toml`
- [ ] `scripts/recette/` (déclenchement, sondage, arrêt brutal, relance) et `05-ACCEPTANCE.md` (preuves sans secrets)

*Aucune installation de framework : pytest est en place.*

---

## Vérifications manuelles seulement

| Comportement | Exigence | Pourquoi manuel | Instructions |
|----------|-------------|------------|-------------------|
| Le runner part seul à l'ouverture de session | INS-02 | fermer/rouvrir la session n'est pas automatisable | se déconnecter, se reconnecter, `deskgate doctor` ; différable (`blocks: none`) |
| Recette sur le n8n de l'utilisateur (2.42.5, port 5678) | INS-04 | second environnement, à ne pas modifier | import manuel du workflow, identifiant « Deskgate », exécution ; différable (`blocks: none`) |
| 04-D1 : rendu du BCF dans BIMcollab Zoom | CAP-02 | vérification visuelle | ouvrir le BCF du calcul ACC-01 : deux vues par sujet, contexte gris transparent, couleurs ; résultat dans `04-HUMAN-UAT.md` |

---

## Validation

- [ ] Chaque tâche a un `<automated>` ou une dépendance de vague 0
- [ ] Continuité : jamais 3 tâches consécutives sans vérification automatique
- [ ] La vague 0 couvre toutes les références manquantes
- [ ] Aucun mode watch
- [ ] Latence de retour < 30 s
- [ ] `nyquist_compliant: true` dans l'en-tête

**Approbation :** pending

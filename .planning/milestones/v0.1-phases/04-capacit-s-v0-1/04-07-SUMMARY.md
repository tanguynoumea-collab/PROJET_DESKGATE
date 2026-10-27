---
phase: 04-capacit-s-v0-1
plan: 07
subsystem: bim-plugin
tags: [bcf, ifc-clash, ifcopenshell, subprocess, docs]
requires:
  - phase: 04-03
    provides: deskgate-bcf write (contrat bcf-write-v1)
  - phase: 04-04
    provides: ifc.clash et groupes déterministes
  - phase: 04-05
    provides: exécuteur mcp et settings de capacité
  - phase: 04-06
    provides: classement memory_limit
provides:
  - "ifc.clash bcf:true : BCF 2.1 en artefact, via deskgate-bcf en sous-processus"
  - "bcfdoc.build_doc, context.context_guids, bcfjob.write_bcf"
  - "Documentation d'installation des plugins et exemples de configuration testés"
affects: [phase-5]
tech-stack:
  added: []
  patterns: ["contexte gris par arbre BREP natif + select_box", "sous-processus par chemin absolu de configuration"]
key-files:
  created:
    - plugins/bim/src/deskgate_bim/bcfdoc.py
    - plugins/bim/src/deskgate_bim/bcfjob.py
    - plugins/bim/src/deskgate_bim/context.py
    - plugins/bim/tests/test_bcfdoc.py
    - plugins/bim/tests/test_clash_bcf.py
    - plugins/bim/README.md
    - tests/unit/test_runner_example.py
  modified:
    - plugins/bim/src/deskgate_bim/clash.py
    - plugins/bim/src/deskgate_bim/params.py
    - src/deskgate/runner.example.toml
    - README.md
    - AGENTS.md
key-decisions:
  - "Contexte gris : voie A (select_box) retenue, pas de repli par étage"
  - "Les groupes sont lus avant l'omission des paires de data : le BCF couvre toutes les paires retenues"
patterns-established:
  - "Dégradation context_unavailable : exception du contexte = listes vides + avertissement, MemoryError relancée"
requirements-completed: [CAP-02, CAP-01, CAP-05]
duration: 50min
completed: 2026-10-20
---

# Phase 4 Plan 07: BCF d'ifc.clash et documentation Summary

**`ifc.clash` avec `bcf: true` écrit un BCF 2.1 (un sujet par groupe, deux points de vue, contexte gris `40B0B0B0`) en appelant `deskgate-bcf` par chemin absolu en sous-processus, prouvé de bout en bout par l'Engine réel et relu par `BcfXml.load`.**

## Spike du contexte gris (voie retenue : A, `select_box`)
Sur `contexte.ifc` (env bim, IfcOpenShell 0.9.0.post1, Python 3.14) :
- backend `opencascade.trianglebvh` : `select_box(entité)` lève « does not support select_box(entity) » ; une boîte tuple est refusée (TypeError).
- backend par défaut sans réglage : « requires native brep elements ».
- **backend `opencascade.brep` avec `settings.set("iterator-output", wrapper.NATIVE)`** : `tree.select_box(Mur1, extend=5.0)` renvoie {Dalle_proche, Gaine1, Mur1}, Poteau_loin (50 m) exclu. Construction de l'arbre 2,5 ms, requête 0,05 ms (maquette de 4 éléments ; coût réel à mesurer sur maquette réelle en phase 5).
- Décision : voie A. L'arbre n'est construit que si `bcf` et `max_context > 0`, indépendamment de l'arbre du calcul de conflits (trianglebvh). Toute exception donne des listes vides et l'avertissement `context_unavailable`.

## Accomplishments
- `bcfdoc.build_doc` (stdlib seule) : document conforme à `docs/contrats/bcf-write-v1.json`, validé par jsonschema ; titres `A x B (+N)`, caméra perspective, rayon `max(1, distance max + 0.5)`.
- `bcfjob.write_bcf` : `bcf_unavailable`, `bcf_contract_error` (code 2), `bcf_write_failed` ; aucun `shell=`, aucun import `bcf`.
- `clash.py` : artefact `bcf`, `summary.bcf` et `summary.bcf_topics`, avertissement `bcf_skipped_no_clash` sans conflit.
- Tests : 8 `test_bcfdoc`, 8 `test_clash_bcf` (mur_gaine, cinq_gaines rayons 1 et 10, contexte et `max_context=0`, déterminisme octet par octet, bcf_unavailable x2, zéro conflit, bcf faux par défaut), 1 `test_runner_example`.
- Docs : `plugins/bim/README.md`, AGENTS.md § 4 (v0.1, sans `--all-packages`), bloc d'exemples de `runner.example.toml`, section « Capacités v0.1 » du README.

## Task Commits
1. Tâche 1 : 33d5fd1 (feat) : document bcf-write-v1 et contexte gris
2. Tâche 2 : 0a908d0 (feat) : ifc.clash produit le BCF en sous-processus
3. Tâche 3 : 3fcf1cb (docs) : installation et exemples de configuration

## Deviations from Plan
None - plan exécuté comme écrit. Le test de bout en bout et les tests de contexte ont passé du premier coup. Note : `DeskgateClasher` expose `opened` (et non `_opened`) ; `context_guids` reçoit les fichiers via `clasher.opened.values()`.

## Différé
différé : 04-D1 (rendu du BCF dans BIMcollab Zoom, blocks 5) : consigné dans `04-HUMAN-UAT.md` (`result: pending`).

## Verification (porte D-12)
- `uv run pytest -m "not e2e" -q` : 615 passed, 1 skipped (privilège de lien symbolique absent), 26 deselected
- `uv run pytest -m e2e -q` : 26 passed
- `uv run ruff check` : All checks passed ; `uv run ruff format --check` : 147 files already formatted
- `uv run pyright` : 0 errors, 0 warnings
- `uv lock --check` : Resolved 68 packages
- `uv build --all-packages` : deskgate_bcf et deskgate_bim (sdist et wheel) construits

## Requirements
CAP-02 prouvé par `test_clash_bcf.py` (marqué Complete). CAP-01 et CAP-05 déjà Complete, confirmés (frontière GPL : aucun import `bcf` dans `plugins/bim/src`, tests d'architecture verts).

## Known Stubs
None.

## Self-Check: PASSED
Fichiers créés présents ; commits 33d5fd1, 0a908d0, 3fcf1cb présents.

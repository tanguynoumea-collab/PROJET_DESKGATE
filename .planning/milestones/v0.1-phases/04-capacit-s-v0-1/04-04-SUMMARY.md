---
phase: 04-capacit-s-v0-1
plan: 04
subsystem: bim-clash
tags: [ifcclash, ifcopenshell, clash, ifc.clash, determinisme]
requires: [04-01, 04-02]
provides:
  - ifc.clash (deskgate_bim.clash:run) : modes hard et clearance en mètres, groupes puis paires, GlobalId A/B
  - DeskgateClasher (sous-classe d'ifcclash.Clasher, check_all=True, sans export BCF)
  - grouping.py (stdlib seule) : normalise, prepare, group_clashes, build_groups, group_guid (UUID v5)
  - params.py : ClashParams (extra=forbid) et ClashError(error_code, message)
  - scènes IFC synthétiques (envside/ifc_synth.py) et banc Engine réel (_support/clash_env.py)
affects: [04-07]
tech-stack:
  added: []
  patterns: [pré-résolution des sélecteurs avant le moteur, progression bornée 1 % ou 0,5 s, artefact complet puis troncature de data]
key-files:
  created:
    - plugins/bim/src/deskgate_bim/clash.py
    - plugins/bim/src/deskgate_bim/grouping.py
    - plugins/bim/src/deskgate_bim/params.py
    - plugins/bim/tests/envside/ifc_synth.py
    - plugins/bim/tests/conftest.py
    - tests/_support/clash_env.py
    - plugins/bim/tests/test_grouping.py
    - plugins/bim/tests/test_clash_hard.py
    - plugins/bim/tests/test_clash_clearance.py
    - plugins/bim/tests/test_clash_empty.py
    - plugins/bim/tests/test_clash_errors.py
    - plugins/bim/tests/test_clash_limits.py
  modified: []
key-decisions:
  - "NS du GUID v5 de groupe figé à 6f1c2b7e-3b1e-5d0a-9a53-2f0f8e5d7a10 (ne plus jamais le changer)"
  - "Question ouverte 4 tranchée : après normalisation p1 est bien sur l'élément A et p2 sur B (test clearance), l'échange p1/p2 est conservé"
  - "Éléments communs à A et B : ajoutés une seule fois à l'arbre de collision (clé fichier + id)"
requirements-completed: [CAP-01, CAP-03]
duration: 40min
completed: 2026-10-20
---

# Phase 4 Plan 04 : ifc.clash (cœur) Summary

Capacité `ifc.clash` déterministe : sous-classe d'`ifcclash.Clasher` aux sélecteurs pré-résolus (syntaxe IfcOpenShell), modes `hard` (tolérance en m) et `clearance`, sélection vide en succès averti, groupes puis paires triés avec GUID v5, erreurs classées, plafonds et progression, prouvée par l'Engine réel sur des IFC synthétiques.

## Réalisé

- `grouping.py` : normalisation a/b (ids, classes, noms, p1/p2), filtre `a == b`, dédoublonnage, arrondi à 6 décimales, tri `(a, b)`, regroupement par rayon, GUID v5 indépendant de l'ordre. 11 tests unitaires, import limité à la stdlib (test AST).
- `params.py` : validation Pydantic (seuil obligatoire selon le mode, clé inconnue refusée), messages français sans valeurs.
- `clash.py` : `run(params, ctx)` : ouverture classée (`ifc_not_found`, `ifc_unreadable`, `memory`), `invalid_selector` (LarkError/re.error), avertissements `selection_a_empty` / `selection_b_empty` avec détails (sélecteur, trouvés, avec géométrie), `clashes.json` (artefact `kind=clashes`, `sort_keys`, octet-identique d'une exécution à l'autre), `data_max_bytes` (900 000 par défaut) vidant les paires de `data` (`pairs_omitted`, `truncated`).
- Scènes synthétiques : mur_gaine (m et mm), gaine_1mm, poutre_tuyau, cinq_gaines, murs + gaines, Maquette_é, contexte (pour 04-07), pas_un_ifc.
- 38 tests dans `plugins/bim/tests` (27 d'intégration via Engine réel) ; suite complète hors e2e : 570 verts, 1 sauté (lien symbolique, privilège absent), ruff et pyright verts.

## Valeurs observées

Conformes à la recherche : pierce 0,2 (±1e-3), protrusion 0,001, clearance 0,05 avec `p1 = [12, 0.1, 0.15]` et `p2 = [12, 0.1, 0.1]`, identiques sur la maquette en millimètres. Cinq gaines : rayon 1,0 et 0 donnent 5 groupes, rayon 10 un seul. Clash entre deux fichiers (question ouverte 6) : fonctionne.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] ClashEnv déplacé dans `tests/_support/clash_env.py`**
- **Found during :** Tâche 2
- **Issue :** `from conftest import ClashEnv` résout `tests/conftest.py` (mode d'import `importlib`, deux conftest homonymes).
- **Fix :** la classe vit dans `tests/_support/clash_env.py` (sur le `pythonpath`) ; `plugins/bim/tests/conftest.py` garde les fixtures `scenes` et `clash_env`.
- **Files modified :** tests/_support/clash_env.py, plugins/bim/tests/conftest.py, tests test_clash_*.py
- **Commit :** eefe2e6

**2. [Rule 2 - Missing critical] Dédoublonnage des éléments ajoutés à l'arbre**
- Un élément présent dans les sélections A et B aurait été ajouté deux fois à l'arbre ; `fresh` filtre par `(id(fichier), id élément)`.
- **Commit :** eefe2e6

## Known Stubs

Aucun. `bcf: true` (BCF) est livré par 04-07, comme prévu.

## Commits

- 2aab5c9 feat(04-04): paramètres ifc.clash et post-traitement déterministe
- eefe2e6 feat(04-04): ifc.clash hard et clearance sur IFC synthétiques
- 16cd2ab test(04-04): erreurs classées, plafonds, déterminisme, progression

## Self-Check: PASSED

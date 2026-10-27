---
phase: 04-capacit-s-v0-1
verified: 2026-10-20T00:00:00Z
status: human_needed
score: 4/4 must-haves verified (rendu BIMcollab différé, 04-D1)
---

# Phase 4 : Capacités v0.1 — rapport de vérification

**Objectif :** le runner réalise un vrai travail (conflits IFC avec export BCF 2.1, appel d'un outil MCP stdio) sans contaminer le code MIT avec du GPL.
**Statut :** human_needed (tout l'automatisable passe ; reste l'item humain différé 04-D1).
**Re-vérification :** non.

## Tests exécutés

- `uv run pytest -m "not e2e"` : 615 réussis, 1 ignoré (lien symbolique, privilège Windows absent), 26 désélectionnés.
- `uv run pytest -m e2e` : 26 réussis.
- Les deux suites couvrent aussi la non-régression des phases 1 à 3.

## Vérités observables

| # | Critère | Statut | Preuve |
|---|---------|--------|--------|
| 1 | `ifc.clash` : JSON groupé avec GlobalId par paire, modes hard et clearance avec tolérance explicite ; sélection vide = succès à 0 conflit avec avertissement (IFC synthétiques, décision D-09) | VÉRIFIÉ | `plugins/bim/src/deskgate_bim/clash.py` (304 lignes), `grouping.py`, `params.py` ; avertissement `selection_*_empty` ; tests `test_clash_hard/clearance/empty/errors/limits`, `test_grouping`, tous verts |
| 2 | BCF 2.1, deux points de vue par sujet, couleurs ARGB, sans sélection | VÉRIFIÉ (code et tests) ; rendu visuel à valider | `bcfdoc.py`, `bcfjob.py`, `context.py`, `deskgate_bcf/writer.py` ; tests `test_bcf_content`, `test_clash_bcf` verts ; rendu BIMcollab = 04-D1 |
| 3 | `mcp.call` : outil d'un serveur stdio déclaré, sans LLM, dans le Job Object ; l'arrêt tue le serveur | VÉRIFIÉ | `src/deskgate/workers/mcp_call.py` ; `tests/proc/test_mcp_call.py`, `test_mcp_errors.py`, `test_mcp_tree.py` (délai, annulation, sortie normale tuent l'arbre) |
| 4 | `deskgate-bcf` (GPL-3) écrit le BCF depuis un JSON versionné en sous-processus ; test CI contre les imports croisés | VÉRIFIÉ | `plugins/bim/bcf/` (LICENSE, NOTICE, cli, writer), contrat `bcf-write-v1.json` avec copies identiques (`tests/plugins/test_contract_equality.py`), `tests/architecture/test_import_boundaries.py`, `test_no_bcf_in_bim_env.py`, `test_licenses.py`, `test_sdist_exclusion.py` verts |

**Score :** 4/4.

## Artefacts et câblage

Tous les artefacts existent, sont substantiels (aucun TODO, FIXME ni NotImplemented dans `plugins/bim/src`, `plugins/bim/bcf/src`, `src/deskgate/workers`) et sont câblés. Le moteur lance `deskgate.workers.mcp_call:run` pour `kind = "mcp"`. `bcfjob` appelle `deskgate-bcf` en sous-processus. Les tests d'intégration de bout en bout (`tests/proc`, `tests/fs/test_engine_launch_params.py`, `tests/e2e`) passent.

## Couverture des exigences

| ID | Plan(s) | Statut | Preuve |
|----|---------|--------|--------|
| CAP-01 | 04-02, 04-04, 04-06, 04-07 | SATISFAIT | clash hard/clearance, groupes et paires, memory_limit |
| CAP-02 | 04-03, 04-07 | SATISFAIT (rendu visuel : 04-D1) | BCF à deux points de vue, ARGB, sans sélection |
| CAP-03 | 04-04 | SATISFAIT | sélection vide = succès, 0 conflit, avertissement |
| CAP-04 | 04-02, 04-05 | SATISFAIT | `mcp.call`, serveurs déclarés, kill de l'arbre |
| CAP-05 | 04-01, 04-03, 04-07 | SATISFAIT | `deskgate-bcf` GPL-3, JSON versionné, test d'isolation |

Les cinq identifiants de REQUIREMENTS.md (CAP-01 à CAP-05, marqués Complete) sont déclarés dans les plans. Aucune exigence orpheline.

## Anti-patterns

Aucun bloquant détecté.

## Vérification humaine requise

### 1. Rendu du BCF dans BIMcollab Zoom (04-D1, différé, voir 04-HUMAN-UAT.md)

**Test :** ouvrir l'IFC source puis `conflits.bcf` produit par `ifc.clash` sur une maquette réelle ; parcourir trois sujets, afficher les points de vue 1 et 2.
**Attendu :** vue 1 : seuls les deux objets du conflit visibles, rouge et bleu ; vue 2 : maquette visible, contexte gris transparent, objets du conflit colorés ; caméra cadrée sur le conflit.
**Pourquoi humain :** rendu visuel dans un logiciel tiers, non vérifiable par programme. Ce n'est pas un écart, mais un item différé (bloque la phase 5).

## Synthèse

Aucun écart trouvé. Le code, le contrat, l'isolation GPL/MIT et les 641 tests (615 + 26) valident l'objectif de la phase. Seul le rendu BIMcollab (04-D1) reste à confirmer par un humain.

_Vérifié : 2026-10-20 — Claude (gsd-verifier)_

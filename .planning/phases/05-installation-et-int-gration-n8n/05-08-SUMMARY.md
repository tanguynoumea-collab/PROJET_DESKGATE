---
phase: 05-installation-et-int-gration-n8n
plan: 08
subsystem: acceptation
tags: [acceptation, n8n, ifc-clash, recette]
requires: ["05-07"]
provides:
  - "05-ACCEPTANCE.md : preuves ACC-01 (partielles) et ACC-02"
affects: []
key-files:
  created:
    - .planning/phases/05-installation-et-int-gration-n8n/05-ACCEPTANCE.md
  modified: []
decisions:
  - "ACC-01 non marqué complet : durée maximale 281 s < 600 s après les trois paliers D-09, aucune attente artificielle"
metrics:
  duration: 25min
  completed: 2026-10-21
requirements-completed: [ACC-02]
---

# Phase 5 Plan 08 : acceptation sur la machine

ACC-02 est constaté (kill brutal, relance par la tâche, rappel `interrupted` reçu par n8n) ; ACC-01 reprend correctement avec résumé et BCF mais ne dépasse pas 600 s.

## Réalisé

- **ACC-01** : trois calculs réels CVC x ARC depuis n8n, runner lancé par la tâche (pythonw sous svchost). Palier 0 `d0d658690e26` 218,9 s ; palier 1 `f98099bfcce9` 281,4 s (2312 conflits tronqué, 359 sujets BCF, 1694464 octets) ; palier 2 `595286f5ba6e` 278,1 s (9522 conflits tronqué, 206 sujets). Tous : nœud « Succes », rappel delivered, artefacts `clashes.json` et `conflits.bcf`. Pic mémoire 3,7 à 5,1 Go.
- **ACC-02** : job `0cf1a5960612`, kill `/F /T` à 09:41:28Z après 90 s, `schtasks /Run`, job `interrupted` / `runner_restarted`, nœud « Echec ou delai » (`resultat: interrupted`), rappel delivered, aucun survivant. Runner relancé par la tâche, `/health` ok, `doctor` 7 lignes [ok].
- Preuves de recette sous `C:\BIM\recette\` (`--out` explicite, virtualisation MSIX). `05-ACCEPTANCE.md` sans secret (grep vide), commit 313657f.

## Deviations from Plan

### Écart de critère

**ACC-01 : durée > 600 s non atteinte.** Les trois paliers D-09 (sélections par défaut, élargies, élargies + clearance 0,05) donnent 219 à 281 s. Le plan interdit toute attente artificielle ; aucun changement de `runner.toml` n'a été nécessaire ni fait. Écart consigné pour le vérificateur ; `ACC-01` laissé non coché.
Pistes si une durée > 600 s reste exigée : autres IFC plus lourds, ou élargir les sélections au-delà des classes de MEP/structure (décision de l'utilisateur).

Aucun défaut de code, aucun correctif.

## Vérifications différées

- différé : 05-D1 — le runner démarre seul à l'ouverture de session Windows
- différé : 05-D2 — recette du workflow d'exemple sur le n8n de l'utilisateur (2.42.5, port 5678)
- différé : 04-D1 — C:\BIM\travail\f98099bfcce9\conflits.bcf (à ouvrir dans BIMcollab Zoom avec C:\BIM\depot\PIC-EXE-AW-CVC-MNQ-BaJ-SUP-30701-IFC4.ifc et C:\BIM\depot\PIC_REV_HRS_ARC_MNQ_BaJ_SUP_30400.ifc)

## Known Stubs

Aucun.

## Self-Check: PASSED

05-ACCEPTANCE.md présent, commit 313657f présent, runner en service.

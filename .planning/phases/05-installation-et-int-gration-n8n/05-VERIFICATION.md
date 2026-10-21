---
phase: 05-installation-et-integration-n8n
verified: 2026-10-21T15:00:00Z
status: human_needed
score: 7/7 exigences vérifiées (3 vérifications humaines différées, aucune bloquante)
re_verification: false
gaps: []
human_verification:
  - test: "05-D1 : fermer puis rouvrir la session Windows"
    expected: "Le runner démarre seul (pythonw sous la tâche « Deskgate », /health répond)"
    why_human: "Le déclencheur d'ouverture de session ne peut pas être exercé sans fermer la session ; la tâche a été lancée par schtasks /Run (même action) et son XML audité par doctor"
  - test: "05-D2 : recette du workflow d'exemple sur le n8n de l'utilisateur (2.42.5, port 5678)"
    expected: "Import manuel de n8n/examples/ifc-clash.json, déclenchement, reprise par « Succes »"
    why_human: "Ce n8n ne devait pas être modifié ; la recette a été faite sur 2.43.8 (compose du dépôt), sans écart constaté"
  - test: "04-D1 : ouvrir C:\\BIM\\travail\\1ec19b03b33d\\conflits.bcf dans BIMcollab Zoom"
    expected: "526 sujets, deux points de vue par sujet, couleurs conformes"
    why_human: "Rendu visuel dans un logiciel tiers"
---

# Phase 5 : Installation et intégration n8n, rapport de vérification

**Objectif :** Sur la machine cible, un utilisateur installe Deskgate, lance n8n épinglé et voit un calcul long déclenché depuis n8n reprendre avec son résultat, même après un arrêt brutal du runner.
**Vérifié :** 2026-10-21
**Statut :** human_needed (toutes les vérifications automatisables passent ; 3 vérifications différées sans effet bloquant)
**Re-vérification :** Non, vérification initiale

## Méthode

Les SUMMARY n'ont pas été crus sur parole. Contrôlés directement : code (`scheduler.py`, `installer.py`, `doctor.py`, `runtime.py`), `n8n/docker-compose.yml`, workflow d'exemple, preuves JSON `C:\BIM\recette\*.json`, sorties `C:\BIM\install\*` (`doctor.txt`), artefacts réels du job `1ec19b03b33d` et maquettes dans `C:\BIM\depot`. Le jeton n'a pas été lu.

## Vérités observables

| # | Vérité | Statut | Preuve |
|---|---|---|---|
| 1 | Installation : `init` crée config, dossiers, jeton ; tâche installée (INS-01, INS-02) | ✓ VÉRIFIÉ | `installer.py` (143 l.), `scheduler.py` : `ExecutionTimeLimit=PT0S`, `DisallowStartIfOnBatteries=false`, `RestartOnFailure`. `doctor.txt` : 7 lignes [ok], tâche « conforme (…\uv\tools\deskgate\Scripts\pythonw.exe -m deskgate serve) ». Maquettes présentes dans `C:\BIM\depot` (531 804 942 et 51 088 640 octets). Installation réelle faite depuis le terminal non virtualisé de l'application (contournement MSIX consigné dans STATE) |
| 2 | n8n 2.43.8 épinglé avec Postgres, `C:\BIM` monté sur `/data` (INS-03) | ✓ VÉRIFIÉ | Compose : image `2.43.8@sha256:a18edcf0…`, port `127.0.0.1:${N8N_HOST_PORT:-5679}:5678`, volume `${DESKGATE_SHARE:-C:/BIM}:/data`. Smoke `d6e17341c4b3` exécuté dessus (05-07) |
| 3 | Workflow d'exemple importable : HTTP, Wait, test du `status` (INS-04) | ✓ VÉRIFIÉ | `n8n/examples/ifc-clash.json` contient `$execution.resumeUrl` ; le smoke et les scénarios passent par le nœud « Succes » (`smoke.json`, `acc01-p4.json`) |
| 4 | Depuis le conteneur, `host.docker.internal:8765/health` répond (INS-05) | ✓ VÉRIFIÉ | Contrôle intégré à `n8n_setup.py`, constaté en 05-07 ; la soumission HTTP du workflow depuis n8n vers le runner aboutit (livraison du rappel 1 tentative) |
| 5 | ACC-01 : calcul de coordination réel et complet depuis n8n, runner démarré par la tâche, reprise avec résumé et chemin BCF | ✓ VÉRIFIÉ (critère revu) | Job `1ec19b03b33d` : succeeded, 485,8 s, branche « Succes », `callback_state=delivered` en 1 tentative, provenance pythonw sous svchost (tâche), artefacts `/data/travail/1ec19b03b33d/clashes.json` et `conflits.bcf`. Contrôle direct de `clashes.json` : `truncated=False`, `counts.clashes=3690`, `returned=3690`, 526 groupes, sélection A 34 628 éléments, B 8 070 ; `conflits.bcf` 2 518 670 octets |
| 6 | ACC-02 : arrêt brutal pendant une tâche, rappel `interrupted` reçu par n8n | ✓ VÉRIFIÉ | `acc02.json` : job `0cf1a5960612`, `interrupted`, `runner_restarted`, nœud « Echec ou delai », rappel delivered en 1 tentative, relance par `schtasks /Run` (provenance tâche), aucun survivant |

**Score :** 6/6 vérités, 7/7 exigences.

## Jugement d'ACC-01 (point explicite demandé)

Le critère écrit dans REQUIREMENTS.md reste « plus de 10 minutes ». Il n'est **pas atteint** : la durée maximale constatée est 485,8 s (460,7 s au palier 3). Je le juge donc contre la **décision utilisateur datée du 2026-10-21** (STATE.md, « peu importe le temps de calcul, la coordination la plus fiable »), qui remplace la durée par « calcul de coordination réel et complet, non tronqué (maquettes réelles, aucun conflit tronqué, réservations exclues, mode hard 1 cm) ». Contre ce critère revu, le palier 4 est satisfait : 3690 conflits retournés sur 3690 dans `clashes.json`, `IfcOpeningElement` exclu de la sélection A, `IfcCurtainWall`, `IfcStair`, `IfcFurnishingElement` exclus de B, mécanisme de reprise inchangé. Le script de recette conclut « faux » uniquement sur l'ancien critère de durée, ce que 05-ACCEPTANCE.md consigne.

Réserve non bloquante : REQUIREMENTS.md n'a pas été réécrit et affiche toujours « plus de 10 minutes » avec `[x]`. Il est recommandé d'y reporter le critère revu pour éviter une contradiction documentaire.

## Exigences (REQUIREMENTS.md contre les PLAN)

| ID | Plans | Statut | Évaluation sur la preuve finale |
|---|---|---|---|
| INS-01 | 05-02, 03, 04, 06, 09 | ✓ SATISFAIT | Coché tôt par 05-01/05-02, mais livré réellement par 05-03 (`init`) et constaté sur la machine en 05-06 (`runner.toml`, `C:\BIM`, jeton non affiché ; doctor [ok]) |
| INS-02 | 05-01 à 05-04, 05-06, 05-09 | ✓ SATISFAIT | Tâche réelle, XML audité (PT0S, batterie, IgnoreNew, RestartOnFailure). L'ouverture de session elle-même reste en 05-D1 (human_needed) |
| INS-03 | 05-05, 05-07 | ✓ SATISFAIT | Coché dès 05-05 (fichiers seuls) ; l'exécution réelle du compose 2.43.8 est prouvée par 05-07 |
| INS-04 | 05-05, 05-07 | ✓ SATISFAIT | Importé et exécuté de bout en bout sur 2.43.8 ; sur 2.42.5 de l'utilisateur : 05-D2 |
| INS-05 | 05-07 | ✓ SATISFAIT | Constaté sur la machine cible |
| ACC-01 | 05-08 | ✓ SATISFAIT (critère revu) | Voir section dédiée |
| ACC-02 | 05-08 | ✓ SATISFAIT | Voir vérité 6 |

Orphelines : aucune (les 7 ID de la phase apparaissent dans au moins un plan).

## Liens clés

| De | Vers | Statut |
|---|---|---|
| Tâche « Deskgate » | `pythonw.exe -m deskgate serve` de l'outil uv | ✓ CÂBLÉ (doctor, provenance des preuves) |
| `runner.toml` | plugins bim/bcf | ✓ CÂBLÉ (doctor « plugins présents », job produit un BCF) |
| workflow | `host.docker.internal:8765/jobs` | ✓ CÂBLÉ (rappels livrés) |
| compose | `/data` | ✓ CÂBLÉ (chemins `/data/travail/...` correspondant à `C:\BIM\travail\...` présents) |
| `recette.py acc02` | `schtasks /Run` | ✓ CÂBLÉ (provenance du runner relancé) |

## Anti-modèles et remarques

| Élément | Sévérité | Remarque |
|---|---|---|
| Message d'erreur de `acc02.json` : « RedÃ©marrÃ© pendant l'exÃ©cution » | ⚠️ Avertissement | Double encodage UTF-8 dans la sortie vue par n8n (ou par le script de recette) ; cosmétique, le code `runner_restarted` est correct. À examiner |
| `truncated: true` dans le résumé du rappel palier 4 | ℹ️ Info | Expliqué : omission des paires au-delà de 900 Ko (règle 7) ; l'artefact est complet (vérifié) |
| Findings `clash-troncature`, `clash-reservations` | ℹ️ Info | Constatés sur les paliers 1 à 3, traités par le palier 4 |
| RestartOnFailure ne relance pas après `taskkill` | ℹ️ Info | Documenté (AGENTS.md, ARCHITECTURE.md) ; relance explicite |
| Aucun jeton, clé ou signature détecté dans `scripts/`, `n8n/`, preuves examinées | ✓ | |

Aucun TODO bloquant ni stub relevé dans les modules vérifiés. Les tests unitaires n'ont pas été relancés (contrainte d'environnement).

## Vérifications humaines différées (aucune bloquante)

1. **05-D1** : ouverture de session Windows et démarrage seul du runner.
2. **05-D2** : recette sur le n8n de l'utilisateur 2.42.5 (port 5678), import manuel.
3. **04-D1** : BCF `C:\BIM\travail\1ec19b03b33d\conflits.bcf` à ouvrir dans BIMcollab Zoom.

## Synthèse

Aucun écart. L'objectif est atteint sur la machine cible : installation par `init`, tâche planifiée conforme, n8n 2.43.8 épinglé, reprise d'un calcul réel de 486 s avec résumé et BCF, et rappel `interrupted` après arrêt brutal. Seule la clause de durée d'ACC-01 n'est pas atteinte à la lettre ; elle est remplacée par une décision utilisateur datée, et satisfaite selon ce critère.

---

_Vérifié : 2026-10-21_
_Vérificateur : Claude (gsd-verifier)_

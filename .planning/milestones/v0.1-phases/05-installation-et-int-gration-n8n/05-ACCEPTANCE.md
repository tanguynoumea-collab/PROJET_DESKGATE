# Phase 5 : preuves d'acceptation

Date : 2026-10-21. Machine : Windows 11 Pro 10.0.26200. Versions : deskgate `0.1.0.dev0`, n8n `2.43.8`
(compose du dépôt, port 5679), Postgres 17, IfcOpenShell `0.9.0.post1` (plugin), Python 3.14 (outil uv).
Runner démarré par la tâche planifiée « Deskgate » (pythonw sous svchost.exe, vérifié avant chaque scénario).

## Verdicts

| Exigence | Verdict | Preuve |
|---|---|---|
| INS-01, INS-02 | Constaté | 05-06-SUMMARY |
| INS-03, INS-04, INS-05 | Constaté | 05-07-SUMMARY (smoke `d6e17341c4b3`) |
| ACC-01 | Constaté selon le critère revu le 2026-10-21 (palier 4 `1ec19b03b33d`, 486 s, complet) ; la durée de 600 s écrite n'est plus un objectif (décision STATE.md) | section ACC-01 |
| ACC-02 | Constaté | section ACC-02 |

## ACC-01

Trois exécutions réelles depuis n8n (webhook, Wait, reprise sur rappel), CVC x ARC, une par palier D-09.
Aucune attente artificielle. Aucune modification de `runner.toml`.

| Palier | job_id | Durée (s) | Pic mémoire (Mo) | Résumé | BCF (octets) |
|---|---|---|---|---|---|
| 0 : sélections par défaut, hard 0,01 | `d0d658690e26` | 218,9 | 3665 | 267 conflits, 51 groupes | 253025 |
| 1 : sélections élargies, hard 0,01 | `f98099bfcce9` | 281,4 | 3997 | 2312 conflits (tronqué), 359 groupes, 359 sujets BCF | 1694464 |
| 2 : sélections élargies, clearance 0,05 | `595286f5ba6e` | 278,1 | 5078 | 9522 conflits (tronqué), 206 groupes, 206 sujets BCF | 959966 |
| 3 : `IfcElement` x `IfcElement`, clearance 0,05 | `2befb1f418d5` | 460,7 | 4665 | 21227 conflits (tronqué), 138 groupes, 138 sujets BCF | 644960 |

| 4 : coordination fiable, hard 0,01, `max_clashes` 100000 | `1ec19b03b33d` | 485,8 | 5964 | 3690 conflits (complet), 526 groupes, 526 sujets BCF | 2518670 |

- Palier 4 (critère revu par l'utilisateur le 2026-10-21, STATE.md : durée indifférente, coordination la plus
  fiable) : sélection A = CVC `IfcElement` sans `IfcOpeningElement`, `IfcVirtualElement`, `IfcElementAssembly`
  (34628 éléments) ; sélection B = ARC idem sans `IfcCurtainWall`, `IfcStair`, `IfcFurnishingElement` (8070
  éléments). `clashes.json` complet (3690 retournés sur 3690, `truncated` faux) ; le `truncated` du résumé du
  rappel vient seulement de l'omission des paires au-delà de 900 Ko (règle 7, artefact complet). succeeded,
  « Succes », delivered en 1 tentative, provenance tâche planifiée. Preuve `C:\BIM\recette\acc01-p4.json` ;
  le verdict du script est faux sur le seul ancien critère de durée. **ACC-01 constaté selon le critère revu.**
- BCF retenu pour 04-D1 (remplace celui du palier 1) : `C:\BIM\travail\1ec19b03b33d\conflits.bcf`.
- Les paliers 1 à 3 étaient tronqués à 1000 paires (`max_clashes` par défaut) et le palier 3 incluait les
  réservations ARC : findings `clash-troncature` et `clash-reservations` ouverts dans l'état ARTHEMIS.
- Palier 3 (demandé par l'utilisateur le 2026-10-21) : mêmes constats (succeeded, « Succes », delivered, provenance
  tâche planifiée), preuve `C:\BIM\recette\acc01-p3.json`, verdict du script faux sur le seul critère de durée.

- Palier 0 : 2026-10-21T09:24:26Z à 09:28:33Z. Palier 1 : 09:28:44Z à 09:33:52Z. Palier 2 : 09:34:20Z à 09:39:27Z.
- Pour les trois : `job_status` succeeded, nœud n8n « Succes », `callback_state` delivered, 1 tentative, artefacts
  `/data/travail/<job_id>/clashes.json` et `/data/travail/<job_id>/conflits.bcf`.
- Provenance : `pythonw.exe, pythonw.exe, svchost.exe, services.exe, wininit.exe` (tâche planifiée).
- Preuves JSON : `C:\BIM\recette\acc01-p0.json`, `acc01-p1.json`, `acc01-p2.json`.
- BCF retenu pour 04-D1 : `C:\BIM\travail\f98099bfcce9\conflits.bcf`.

Écart : le critère « calcul de plus de 600 s » n'est pas atteint. Même avec tous les `IfcElement` des deux
maquettes (palier 3), la durée maximale est de 461 s. Les sélections ne contiennent plus de classe IFC utile à ajouter ;
la durée n'a pas été allongée artificiellement (D-09). Le mécanisme de reprise est constaté sur 3 calculs réels de
plus de 200 s, avec un fichier de 530 Mo et un de 51 Mo. Au vérificateur de décider.

## ACC-02

Palier 2, job `0cf1a5960612`. Début 2026-10-21T09:39:54Z, kill (`taskkill /F /T`) à 09:41:28Z (après 90 s de calcul),
fin du scénario 09:42:19Z. Relance par `schtasks /Run /TN Deskgate`.

- Job `interrupted`, erreur `runner_restarted` (« Runner redémarré pendant l'exécution. »).
- n8n : nœud « Echec ou delai », sortie `{"resultat": "interrupted", "erreur": {"code": "runner_restarted"}}`.
- `callback_state` delivered, 1 tentative. Survivants `deskgate_sdk` : aucun (`[]`).
- Provenance du runner relancé : pythonw sous svchost (tâche planifiée). `/health` : `ok`. `deskgate doctor` : 7 lignes [ok].
- Preuve : `C:\BIM\recette\acc02.json`.

## Écarts et limites

- Durée ACC-01 (voir ci-dessus).
- Version n8n : 2.43.8 du dépôt, aucun écart constaté avec 2.42.5 (05-07).
- La tâche planifiée ne relance pas le runner après `taskkill` (RestartOnFailure ne s'applique pas à un kill) :
  relance explicite par `schtasks /Run`.
- Veille : courant alternatif jamais, batterie 600 s ; non modifié.
- Préfixe de sortie des preuves : `C:\BIM\recette` (virtualisation MSIX de %LOCALAPPDATA%).

## Vérifications différées

- 05-D1 : le runner démarre seul à l'ouverture de session Windows.
- 05-D2 : recette du workflow d'exemple sur le n8n de l'utilisateur (2.42.5, port 5678).
- 04-D1 : BCF à ouvrir dans BIMcollab Zoom : `C:\BIM\travail\f98099bfcce9\conflits.bcf`.

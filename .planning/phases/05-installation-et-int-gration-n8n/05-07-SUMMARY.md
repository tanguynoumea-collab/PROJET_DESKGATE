---
phase: 05-installation-et-int-gration-n8n
plan: 07
subsystem: recette
tags: [n8n, docker-compose, recette, webhook, wait]
requires: ["05-05", "05-06"]
provides:
  - "scripts/recette/ : _commun.py, n8n_setup.py, recette.py (smoke, acc01, acc02), README.md"
  - "n8n 2.43.8 + Postgres 17 démarrés (projet deskgate-n8n, port 5679), exemple importé et publié"
  - "Preuve INS-04 et INS-05 sur la machine"
affects: [05-08]
tech-stack:
  added: []
  patterns: ["stdlib + psutil, SQLite en lecture seule (mode=ro)", "jeton par stdin du conteneur", "clé d'API n8n éphémère"]
key-files:
  created:
    - scripts/recette/_commun.py
    - scripts/recette/n8n_setup.py
    - scripts/recette/recette.py
    - scripts/recette/README.md
  modified: []
decisions:
  - "Paramètres et preuves du smoke écrits sous C:\\BIM\\recette (option --out), pas sous %LOCALAPPDATA% (virtualisation MSIX)"
metrics:
  duration: 25min
  completed: 2026-10-21
requirements-completed: [INS-04, INS-05]
---

# Phase 5 Plan 07 : n8n du dépôt et recette de bout en bout

n8n 2.43.8 tourne sur 127.0.0.1:5679, l'exemple `ifc.clash` est importé sans exposer le jeton, et un calcul court passe par Wait puis reprend sur le rappel avec un `conflits.bcf` ; les scripts de recette pour 05-08 sont prêts.

## Réalisé

- **Tâche 1** (f46cc21, 10145e8) : trois scripts + README, ruff, format et pyright verts, aucun `shell=True`, aucun import de `deskgate`, aucune mention du port ou des conteneurs de l'autre n8n.
- **Tâche 2** : `n8n/.env` généré (ignoré par git, vérifié par `git check-ignore`), `pull` puis `up -d`, Postgres et n8n `healthy`, `n8n --version` donne `2.43.8`. `n8n_setup.py` sort en 0 :
  propriétaire créé, identifiant importé (stdin), workflow importé, publié par la CLI `publish:workflow` (voie principale, pas de repli API) puis redémarrage de n8n.
  INS-05 : depuis le conteneur, `/health` renvoie `{"status":"ok","version":"0.1.0.dev0","warnings":[]}` et `/data` liste `depot install livrables travail`.
  n8n de l'utilisateur intact : les cinq conteneurs `pipelines-n8n-*` sont toujours `Up 2 hours`, `:5678/healthz` répond 200.
- **Tâche 3** : IFC synthétiques générés dans `C:\BIM\depot\exemple`. Smoke (murs.ifc / gaines.ifc, `IfcWall` / `IfcDuctSegment`, hard, 0,01) : code 0.

## Preuve du smoke (masquée, sans secret)

`C:\BIM\recette\smoke.json` : job `d6e17341c4b3`, `job_status` succeeded, `n8n_status` success, nœud « Succes », `duration_s` 1,575, résumé `clashes 1, groups 1, bcf_topics 1`, `callback_state` delivered, `callback_attempts` 1, `bcf_host_path` `C:/BIM/travail/d6e17341c4b3/conflits.bcf` (2684 octets), `verdict` true. Aucune occurrence de `signature=` non masquée. Un premier passage (job `03b3364b4d8a`) a réussi côté n8n et runner mais le script ne lisait pas encore les artefacts objets ; corrigé.

## Écart de version

Aucun comportement de 2.43.8 différent de 2.42.5 : webhook, Wait, `$json.body`, reprise sur `resumeUrl` fonctionnent sans modifier `n8n/examples/ifc-clash.json`.

## Deviations from Plan

**1. [Rule 1 - Bug] Artefacts du rappel** : les artefacts sont des objets `{kind, path}`, non des chaînes ; `recette.py` les lit désormais (10145e8).

**2. [Rule 1 - Bug] Provenance** : `provenance()` s'arrêtait sur `svchost.exe` (ligne de commande inaccessible hors administrateur) et `assert_started_by_task` échouait ; la chaîne conserve maintenant le processus avec une ligne vide (10145e8). Contrôle réel : `pythonw, pythonw, svchost, services, wininit`, vrai.

**3. [Rule 3 - Environnement MSIX]** : les paramètres et la preuve du smoke sont sous `C:\BIM\recette` au lieu de `%LOCALAPPDATA%\Deskgate\recette` (écriture interdite à l'exécuteur). Pour 05-08, lancer avec `--out C:/BIM/recette/<scénario>.json` depuis le même contexte.

## Known Stubs

Aucun.

## Exigences

INS-04 et INS-05 constatées sur la machine. INS-03 déjà livrée (05-05), maintenant démarrée.

## Self-Check: PASSED

Scripts présents, commits f46cc21 et 10145e8 présents, `ruff check`, `ruff format --check` verts, `pytest -m "not e2e"` : 690 passés, 1 ignoré.

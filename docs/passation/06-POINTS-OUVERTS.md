# 06 — Points ouverts, vérifications et risques

## §1 — Recherche de l'existant (à faire en premier)

Vérifier qu'aucun projet open source ne couvre déjà le besoin : **un service local Windows, à
plugins (Python / ligne de commande / MCP), qui reçoit des tâches longues d'un orchestrateur
(n8n en priorité), les exécute dans la session utilisateur et rappelle l'orchestrateur**.

Pistes connues, à évaluer comme concurrents ou briques réutilisables :
- files de tâches Python : Celery, RQ, Huey, Dramatiq ;
- workers d'orchestrateurs : Prefect workers, Windmill workers, Hatchet, Temporal ;
- agents installés sur une machine : exécuteurs GitHub Actions auto-hébergés, agents Jenkins,
  Rundeck ;
- ponts MCP : `supergateway`, `mcp-proxy` ;
- nœuds communautaires n8n existants autour des tâches distantes / longues ;
- mécanismes internes de n8n (*task runners*, mode *queue*) — non adaptés a priori, à confirmer.

Conclusion attendue : construire, contribuer à un projet existant, ou s'appuyer sur une brique
(ex. utiliser Huey/SQLite pour la file plutôt que l'écrire).

## §2 — Vérifications techniques avant la v0.1

1. **Attente dans un nœud n8n communautaire** : un nœud tiers peut-il mettre l'exécution en
   attente et être repris par webhook, comme le nœud *Wait* ? Conditionne la conception du nœud
   v0.3. Plan B : nœud « Soumettre » + nœud *Wait* préconfiguré.
2. **Joindre le runner depuis Docker Desktop / WSL2** : `host.docker.internal` + runner sur
   `127.0.0.1` fonctionne-t-il, ou faut-il écouter sur l'interface virtuelle WSL / vEthernet ?
   Trouver la configuration la plus restrictive qui marche, et la documenter.
3. **Taille du rappel** : limite de taille du corps accepté par l'URL de reprise n8n (d'où des
   résumés petits et des artefacts en fichiers).
4. **Version de n8n** à fixer (épingler l'image Docker) et nœuds disponibles : *MCP Server
   Trigger*, *MCP Client Tool*, *Wait* avec `resumeUrl`.
5. **Résultat de `uv`** pour créer des environnements isolés avec IfcOpenShell (roues
   disponibles pour la version Python ciblée sous Windows).
6. **Arrêt d'arbre de processus** sous Windows (Job Objects / `psutil`) pour les délais maximum.

## §3 — Questions à poser à l'utilisateur

- **ODM** : de quel outil s'agit-il exactement (logiciel de bureau, serveur MCP maison, service
  en ligne) ? A-t-il une ligne de commande ou une API ? Son MCP est-il en stdio ou en HTTP ?
- **Licence** du runner : MIT (cohérent avec `PROJET MCP`) ou Apache-2.0 (clause de brevets) ?
- ~~Nom définitif du produit~~ → tranché : **Deskgate** (voir D13).
- **Tableau de bord** : technologie et format de données attendus (pour le JSON de retour).
- **Hermes Agent** : version utilisée, comment il est hébergé sur le PC, et transport MCP
  supporté (HTTP / SSE).
- **Source des dépôts** : SharePoint synchronisé (OneDrive), client Dalux, client Kairnial ?
  Chemin exact du dossier.

## §4 — Risques et vigilances

| Risque | Mesure |
|---|---|
| **Périmètre trop large** (runner + 3 exécuteurs + UI + droits + nœud + MCP + installateur) | Respecter l'ordre v0.1 → v0.4 ; chaque version validée par un usage réel |
| **Sécurité** : un service qui exécute des actions sur le PC à la demande du réseau | Écoute locale, jetons, droits par plugin, pas de commande libre, chemins limités, audit |
| **PC éteint ou en veille** : n8n ne rattrape pas une exécution planifiée manquée | Désactiver la veille ; vérification au démarrage des exécutions manquées ; planifier aux heures d'usage |
| **Session Windows verrouillée** : le pilotage de logiciels échoue (souris, fenêtres) | `requires_session` + contrôle avant exécution ; préférer les modes sans interface (Nightshift, CLI) |
| **Mémoire partagée avec Revit** | Plafond WSL2 (`.wslconfig`), plafond des conteneurs, ressource `cpu-heavy` = 1 |
| **Fichiers synchronisés incomplets** | Attente de stabilité + hash avant traitement |
| **GlobalId instables entre versions** | Signature de secours pour la déduplication et la comparaison |
| **Licence Docker Desktop** : gratuite en usage personnel / petite structure, payante au-delà (> 250 salariés ou > 10 M$ de CA) | Si usage chez l'employeur : vérifier, ou Docker Engine directement dans WSL2 |
| **Licence n8n** (fair-code) | Le runner reste indépendant de n8n et réellement open source |
| **Confidentialité** : les JSON de synthèse partent chez le fournisseur du LLM | Envoyer des synthèses, jamais l'IFC ; modèle local (Ollama) possible pour les étapes sensibles |
| **Dépendances incompatibles entre plugins** | Environnement uv isolé par plugin |

## §5 — Licences de l'écosystème (rappel)

- IfcOpenShell : LGPL-3 (compatible avec un dépôt MIT si utilisé comme bibliothèque).
- That Open Engine / web-ifc : MIT / MPL-2 ; Speckle : Apache-2.0 ; Prefect : Apache-2.0.
- Bonsai : GPL ; xeokit, BIMserver : AGPL ; OpenProject : GPL-3 — à ne pas intégrer dans le
  code du runner (utilisation comme outils séparés sans problème).

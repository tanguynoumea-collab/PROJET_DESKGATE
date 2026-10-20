# 02 — Décisions actées

Chaque décision a été discutée et validée par l'utilisateur. Ne pas les rediscuter sans un
problème bloquant, explicitement signalé.

## D1 — IfcOpenShell est le moteur de traitement, Zoom devient optionnel

- Presque tout le traitement IFC (requêtes, quantités, conflits, IDS, BCF, comparaison de
  versions) se fait avec IfcOpenShell, sans logiciel.
- BIMcollab Zoom reste utile pour la **revue humaine**, le partage de standards et le circuit
  d'issues BIMcollab, mais **n'est pas requis dans les pipelines automatiques**.
- Conséquence : les pipelines sont majoritairement « sans interface graphique ».

## D2 — n8n est l'orchestrateur des pipelines

Alternatives étudiées : Prefect, Dagster, Windmill, Node-RED, Activepieces, Claude Agent SDK seul,
scripts + Planificateur Windows, Speckle Automate, CI avec exécuteur local.

n8n retenu parce que :
- l'utilisateur a besoin de **nombreux connecteurs** (Microsoft 365, SharePoint, Teams, webhooks) ;
- le nœud **MCP Server Trigger** expose un workflow comme outil MCP, ce que Hermes peut appeler ;
- l'éditeur visuel aide à suivre une chaîne multi-agents.

Limites connues et acceptées :
- n8n ne calcule pas, d'où le runner ;
- licence *Sustainable Use License* (fair-code, **pas** open source OSI) : auto-hébergement
  interne autorisé, redistribution ou revente restreintes. **Le runner, lui, doit être
  indépendant de n8n et réellement open source** : n8n est un client parmi d'autres.

## D3 — Configuration de référence

- n8n **auto-hébergé**, dans **Docker Compose**, sur le **PC personnel Windows** de l'utilisateur
  (avec Postgres).
- Le **runner tourne nativement sous Windows** (pas dans Docker), dans la **session utilisateur**,
  pour pouvoir piloter les logiciels installés. Lancement par le **Planificateur de tâches** à
  l'ouverture de session (un service Windows de type NSSM ne pourrait pas piloter d'interface).
- n8n joint le runner via `http://host.docker.internal:<port>`.
- Un dossier partagé (ex. `C:\BIM\`) est monté dans les conteneurs (ex. `/data`).

## D4 — Délégation asynchrone (soumission → attente → rappel)

1. n8n soumet la tâche (`POST /jobs`) avec l'URL de reprise de son nœud *Wait*
   (`$execution.resumeUrl`).
2. Le runner répond **immédiatement** avec un `job_id` et met la tâche en file.
3. n8n se met en pause (nœud *Wait*, « reprise sur webhook »).
4. Le runner exécute, écrit les artefacts dans le dossier partagé, puis appelle l'URL de reprise
   avec le résultat (succès ou erreur).

On transmet **des chemins de fichiers, jamais les fichiers eux-mêmes**.

## D5 — Quand passer par le runner

- MCP exposé en **HTTP** sur le réseau local **et** appel **court** (secondes) → n8n peut
  l'appeler **directement**.
- Calcul **lourd/long**, ou accès à un **logiciel installé** / à un MCP **stdio** → **runner**.
- Ce qui impose le runner, c'est **la durée ou l'accès à Windows**, pas le fait d'être local.

## D6 — Séparation déterministe / IA

- Les **calculs** (conflits, comparaisons, contrôles, quantités) sont **déterministes et
  reproductibles** : mêmes entrées → mêmes résultats.
- L'**IA** n'intervient que pour **juger et synthétiser** (pertinence d'un conflit, synthèse
  d'évolution, commentaire d'audit), sur des **JSON structurés**, jamais sur l'IFC brut. Chaque
  décision de l'IA est tracée avec sa justification.
- Les **agents décident** (quand, pourquoi, quoi en conclure) ; les **pipelines exécutent**.
  Hermes ne calcule jamais lui-même.

## D7 — Le produit : un runner générique à plugins

- **Un runner par PC.** Pas de serveur partagé multi-utilisateurs (prévoir sans construire).
- **Le cœur ne connaît rien au BIM.** Dépôt `deskgate` générique ; les plugins BIM
  (IfcOpenShell, ODM, Zoom) sont un paquet séparé qui s'appuie dessus.
- **Trois types de plugins** : fonction **Python**, **ligne de commande**, **outil MCP** (relayé
  avec file d'attente et délai maximum).
- **Chaque plugin est déclaré par un manifeste** (schémas d'entrée/sortie en JSON Schema, délai,
  ressource, prérequis).
- **Un environnement Python isolé par plugin** (créé avec `uv`) : les dépendances ne se mélangent
  pas.
- **Aucune exécution de commande libre** : seules les capacités déclarées sont appelables.

## D8 — Intégration n8n : un nœud = un plugin = une tâche

- Un **nœud n8n communautaire** : liste déroulante des plugins disponibles (chargée depuis le
  runner), champs générés à partir du schéma du plugin, soumission + attente du résultat.
- Plusieurs appels au runner dans un pipeline = plusieurs nœuds.
- Les nœuds s'enchaînent en se passant les chemins d'artefacts.

## D9 — Droits d'accès : modèle « un runner par PC »

- **Jetons par client** (n8n, Hermes, Claude…), chacun avec la **liste des plugins autorisés**.
- **Journal d'audit** : qui a appelé quoi, quand, avec quels paramètres, quel résultat, combien
  de temps.
- Quotas éventuels (nombre d'exécutions, concurrence).
- Pas de comptes utilisateurs, rôles ou authentification d'entreprise dans le périmètre.

## D10 — Interface visuelle

Servie par le runner lui-même sur `localhost` : catalogue des plugins **classés par type**
(Python / ligne de commande / MCP), statut (disponible / indisponible et pourquoi), schéma, bouton
de test, historique des tâches et journaux, gestion des jetons et des droits par plugin.

## D11 — Installation par un humain et par une IA

- Une commande d'installation, puis `deskgate init` (configuration, jeton, vérifications) et
  `deskgate doctor` (diagnostic complet).
- `AGENTS.md` / `CLAUDE.md` à la racine du dépôt : procédure d'installation pas à pas pour une IA.
- `deskgate plugin add <dépôt git | dossier>` pour installer un plugin.
- `pipeline.lock` : liste des plugins et versions requis par un pipeline, pour qu'un collègue le
  reproduise (`deskgate plugin install --from pipeline.lock`).

## D12 — Méthode de développement

- **Partir des vrais pipelines** : la v0.1 est validée par le pipeline de coordination réel de
  l'utilisateur, pas par une conception générique faite à l'avance.
- Ordre des versions fixé dans `04-FEUILLE-DE-ROUTE.md`.
- Licence du runner : **MIT ou Apache-2.0** (à trancher, voir points ouverts).

## D13 — Nom du produit : **Deskgate**

- « *desk* » (le poste de travail, les logiciels de bureau) + « *gate* » (la passerelle, qui
  filtre aussi les accès) : la porte d'entrée des orchestrateurs vers le PC.
- Noms dérivés :
  - dépôt et paquet PyPI du cœur : `deskgate` (module Python `deskgate`) ;
  - commande : `deskgate` (`deskgate init`, `deskgate doctor`, `deskgate plugin add`…) ;
  - nœud n8n communautaire : `n8n-nodes-deskgate` ;
  - dépôt des plugins BIM : `deskgate-bim`.
- Disponibilité vérifiée le 2026-10-20 : `deskgate` libre sur PyPI, `n8n-nodes-deskgate` libre
  sur npm, 3 dépôts GitHub seulement contiennent le mot. **Réserver les noms PyPI et npm tôt**
  (publication d'une version 0.0.1 vide) pour éviter qu'ils soient pris.
- Écartés : noms grecs (difficiles à prononcer), mots anglais simples déjà saturés, tout nom
  contenant « n8n » (marque déposée).
- Le terme générique « runner » reste utilisé dans les documents pour désigner le service.

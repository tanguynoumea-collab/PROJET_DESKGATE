# 01 — Vision et contexte

## L'utilisateur

- Coordinateur / BIM manager, travaille sur des projets de construction (coordination de maquettes
  IFC, audits de maquettes, extraction de quantités).
- Développe ses propres outils avec Claude Code : add-ins Revit (C#/WPF), serveur MCP Python
  `bim-assistant`, automatisation de BIMcollab Zoom.
- Environnement : **PC Windows 10 personnel**, avec ses logiciels installés (BIMcollab Zoom,
  Revit, et un outil nommé « ODM » — voir `06-POINTS-OUVERTS.md`).
- Langue de travail : **français** (documents, interface, messages).

## La vision d'ensemble

Construire un écosystème **open source et automatisable** pour la coordination BIM,
l'extraction de quantités et l'interrogation de maquettes, avec :

1. des **pipelines n8n** qui tournent automatiquement (à chaque dépôt d'IFC ou chaque semaine) ;
2. un **système d'agents** : un sous-agent **Hermes Agent** (Nous Research) dédié à la
   coordination, qui déclenche les pipelines, puis rend compte à un **agent superviseur**, lequel
   présente les résultats dans un **tableau de bord personnalisé** ;
3. un **moteur de calcul** IfcOpenShell (déjà existant dans `bim-assistant`) ;
4. des **logiciels de bureau** (Zoom, Revit, ODM) pilotés quand c'est nécessaire.

## Le problème que résout le nouveau projet

n8n tourne dans Docker (conteneurs Linux sous WSL2). Il ne peut pas :
- exécuter des calculs lourds (IfcOpenShell n'est pas installable dans le nœud Code ; une
  détection de conflits de 20–40 min dépasse les délais HTTP) ;
- lancer des logiciels Windows ni des serveurs MCP en mode stdio installés sur le PC.

Il faut donc une **passerelle** : un service local, sur le PC Windows, à qui n8n **délègue**
les tâches lourdes ou dépendantes d'un logiciel, de façon **asynchrone**.

L'utilisateur va construire **plusieurs pipelines** de ce type. Plutôt que de recoder la
passerelle à chaque fois, il veut la **formaliser en produit open source réutilisable** :

> Un service facile à installer (par un humain ou par une IA depuis le dépôt GitHub), qui
> permet à n'importe qui de créer des pipelines n8n avec de gros processus de calcul ou
> l'utilisation de logiciels délégués au PC.

## Ce que le produit doit offrir (expression de besoin de l'utilisateur)

- **Installation facile** chez les collègues, en local, et **installable par une IA** à partir
  du dépôt GitHub.
- Une **interface visuelle** qui montre les blocs (plugins) disponibles, **classés en trois
  types** : modules Python, lignes de commande, MCP.
- Pour chaque bloc : **gérer les droits d'accès** et **contrôler l'utilisation**.
- Pouvoir préparer ses propres plugins (ex. module Python IfcOpenShell, module ODM).
- Les plugins présents sont **exposés au nœud n8n** : dans n8n, on choisit facilement le module.
- **Un nœud n8n = un appel à un module du worker.** Si le pipeline utilise le worker plusieurs
  fois, chaque utilisation est un nœud distinct.
- **Un runner par PC** (chaque collègue installe le sien).

## Écosystème existant (projet `PROJET MCP`)

| Élément | Rôle | Emplacement |
|---|---|---|
| `bim-assistant` | Serveur MCP Python (stdio) : analyse IFC via IfcOpenShell, géométrie (volumes, distances, contacts, hauteurs libres), **détection de conflits** (modes hard / clearance / touch / duplicate), **écriture BCF 2.1** avec points de vue et images, pilotage de Zoom | `PROJET MCP\bim-assistant\` |
| `cli-anything-bczoom` | CLI qui génère les fichiers natifs Zoom (Smart Views `.bcsv`, règles de conflits `.bcr`, listes `.bcl`, Smart Properties `.bcsp`, projets `.bcp`) et lance Nightshift | `PROJET MCP\bimcollab-zoom\agent-harness\` |
| BIMcollab Zoom | Visionneuse / revue humaine, import des BCF | installé sur le PC |

Dépendances clés de `bim-assistant` (pyproject) : Python ≥ 3.11, `ifcopenshell>=0.8`, `mcp>=2`,
`numpy`, `shapely`, `manifold3d`, `python-fcl`, `rtree`, `psutil`, `pywinauto` / `pywin32`
(Windows). Licence du dépôt : MIT.

Fonctions de `bim_assistant/clash.py` utiles pour le premier plugin : `detect(...)`,
`clash(...)` (détection + regroupement), `write_bcf(...)` (BCF 2.1).

## Vocabulaire

| Terme | Sens dans ce projet |
|---|---|
| **Runner** | Le service local installé sur le PC (nom du produit : **Deskgate**) |
| **Plugin / capacité** | Un bloc exécutable déclaré par un manifeste (Python, ligne de commande ou outil MCP) |
| **Tâche (job)** | Une exécution d'un plugin, soumise par n8n, mise en file, suivie jusqu'au résultat |
| **Client** | Ce qui appelle le runner : une instance n8n, Hermes, Claude… identifié par un jeton |
| **Artefact** | Fichier produit par une tâche (JSON de résultat, BCF, rapport) |
| **Rappel (callback)** | Appel HTTP du runner vers l'URL de reprise du nœud *Wait* de n8n |
| **Hermes** | Hermes Agent (Nous Research), agent IA qui orchestre la coordination |

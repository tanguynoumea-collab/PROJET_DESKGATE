# Passation — projet « Deskgate »

Ce dossier contient la passation complète d'une conversation de cadrage menée le 2026-10-20
dans le projet `PROJET MCP` (serveur MCP `bim-assistant` + pilotage BIMcollab Zoom).
Il sert à démarrer **un nouveau projet Claude Code** sans perdre aucun contexte.

## Comment l'utiliser

1. Créer un dossier vide pour le nouveau projet (ex. `C:\Users\tanguy.delrieu\source\repos\deskgate`)
   et y initialiser un dépôt git.
2. Ouvrir une session Claude Code dans ce dossier.
3. Glisser-déposer **tous les fichiers de ce dossier** dans la conversation.
4. Coller le prompt de démarrage ci-dessous.

## Fichiers

| Fichier | Contenu |
|---|---|
| `00-LISEZ-MOI.md` | Ce fichier : mode d'emploi et prompt de démarrage |
| `01-VISION-ET-CONTEXTE.md` | Qui, pourquoi, écosystème existant, vocabulaire |
| `02-DECISIONS.md` | Décisions déjà prises, avec leur justification — à ne pas rediscuter sans raison |
| `03-ARCHITECTURE.md` | Conception technique : runner, plugins, manifeste, protocole, nœud n8n, sécurité |
| `04-FEUILLE-DE-ROUTE.md` | Versions v0.1 → v0.4, tâches et critères d'acceptation |
| `05-PIPELINES-CIBLES.md` | Les pipelines BIM qui vont consommer le runner (cas d'usage réels) |
| `06-POINTS-OUVERTS.md` | Questions non tranchées, risques, vérifications à faire en premier |

## Prompt de démarrage (à coller après le glisser-déposer)

> Voici la passation d'un nouveau projet. Lis les 7 fichiers dans l'ordre (00 à 06).
> Les décisions de `02-DECISIONS.md` sont actées : ne les rediscute que si tu trouves un
> problème bloquant, et dis-le explicitement.
>
> Commence par :
> 1. la **recherche de l'existant** décrite dans `06-POINTS-OUVERTS.md` (§1) — dis-moi si un
>    projet open source couvre déjà ce besoin, et si oui, s'il vaut mieux contribuer ;
> 2. les **vérifications techniques** du §2 (nœud n8n communautaire capable de mettre une
>    exécution en attente, etc.) ;
> 3. puis la rédaction dans le dépôt de `ARCHITECTURE.md`, `ROADMAP.md`, `AGENTS.md` et
>    `CLAUDE.md` à partir de cette passation.
>
> Ne commence pas à coder la v0.1 avant que j'aie validé ces documents.

## Projet d'origine (référence)

- Dépôt d'origine : `C:\Users\tanguy.delrieu\source\repos\PROJET MCP`
- Moteur IFC réutilisable : `PROJET MCP\bim-assistant\bim_assistant\`
  (`ifc_engine.py`, `geometry.py`, `clash.py`, `snapshot.py`, `zoom_bridge.py`, `server.py`)
- Harnais Zoom : `PROJET MCP\bimcollab-zoom\agent-harness\` (paquet `cli-anything-bczoom`)

# Note de cadrage — cycle 1 (v0.1.0)

Date : 2026-10-20. Sources : `docs/passation/` (00 à 06), `existant-cycle-1.md`,
`verifs-techniques-cycle-1.md`, échanges avec l'utilisateur du 2026-10-20.

## Zones générales

1. **Intention** : une passerelle locale pour que n8n (Docker) délègue des tâches lourdes ou
   dépendantes de Windows, de façon asynchrone. Usage immédiat : tests BIM de l'utilisateur.
2. **Périmètre IN** : runner, nœud n8n, interface locale, sécurité, plugins BIM (`ifc.clash`,
   `ifc.audit`, `ifc.diff`, `ifc.quantities`) écrits de zéro sur IfcOpenShell,
   développés dans ce dépôt en
   parallèle. **OUT** : workflows complets, ingestion, registre des maquettes, base et
   déduplication des conflits, tri IA, Hermes, superviseur, tableau de bord (projet
   d'intégration) ; exposition de Deskgate comme serveur MCP (sans usage dans ce périmètre) ;
   `odm.audit_loi` (backlog, après une version fonctionnelle).
3. **Limites** : tâche > délai → arbre tué, statut `timeout` ; runner redémarré → `interrupted` ;
   n8n injoignable → réessais puis abandon tracé ; chemin hors racine → refus ; rappel > 1 Mio →
   `summary.json`.
4. **Existant** : aucun (nouveau dépôt).
5. **Surface visible** : aucune en v0.1 (`impact_ui false`). L'interface arrive en v0.3, cycle
   distinct avec UX_DESIGN.
6. **Contraintes** : Windows 10/11 natif, session utilisateur, écoute `127.0.0.1`, MIT, aucun code
   GPL/AGPL, n8n épinglé en 2.43.8, Python ≥ 3.11.
7. **Critère de succès v0.1** : celui de `ROADMAP.md` (détection de conflits déclenchée depuis
   n8n, reprise après rappel, calcul > 10 min, `interrupted` au redémarrage, arbre tué au délai).
8. **Version dégradée acceptable** : `mcp.call` peut glisser en v0.2 si `ifc.clash` absorbe le cycle.

## Faits de contexte (zones 9 à 14)

- **Tenancy** : mono-tenant, un runner par PC.
- **Authentification** : jetons Bearer hachés ; un jeton en v0.1, par client avec droits en v0.2.
- **Données personnelles** : aucune collectée.
- **Facturation** : sans objet.
- **Stade** : nouveau projet, aucun utilisateur.
- **Environnements** : un seul, le PC local (runner natif + n8n Docker Desktop).

## Décisions prises pendant le cadrage

- Construire (pas de projet existant à reprendre) ; file de tâches écrite sur SQLite, Huey en plan B.
- Arrêt des tâches par Job Object Windows ; `resumeUrl` appelée telle quelle et masquée.
- Nœud n8n v0.3 en un seul nœud (soumission + attente).
- Licence MIT.
- Plugins BIM dans ce dépôt (`plugins/bim/`, paquet séparé du cœur).

## Hypothèses assumées / zones ouvertes

- **Moteur de conflits** : on repart de zéro. `ifc.clash` est écrit ici sur les outils IfcOpenShell
  existants (`ifcclash`, export BCF). Le projet d'origine `PROJET MCP` n'est pas réutilisé (décision
  utilisateur du 2026-10-20).
- **BIMcollab Zoom** : aucun plugin Zoom dans ce périmètre (`zoom.nightshift` retiré). La ressource
  `gui-session` reste dans le runner, générique.
- **Réseau** : `host.docker.internal` → `127.0.0.1` à tester sur la machine au début de la v0.1.
- **ODM** : non identifié, reporté.

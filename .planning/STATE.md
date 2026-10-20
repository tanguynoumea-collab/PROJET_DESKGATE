# État du projet

## Référence du projet

Voir : `.planning/PROJECT.md` (mis à jour le 2026-10-20)

**Valeur centrale :** n8n délègue une tâche longue au PC Windows et reprend fiablement quand elle se termine, quel que soit le résultat (succès, échec, délai dépassé, annulation, redémarrage du runner).
**Priorité actuelle :** Phase 1 : Fondations testables

## Position actuelle

Milestone : v0.1
Phase : 1 sur 5 (Fondations testables)
Plan : 0 sur 0 (non planifiée)
Statut : Prêt à planifier
Dernière activité : 2026-10-20 : feuille de route créée

Progression : [░░░░░░░░░░] 0 %

## Métriques de performance

**Vélocité :**
- Plans terminés : 0
- Durée moyenne : -
- Durée totale : -

**Par phase :**

| Phase | Plans | Total | Moy./plan |
|-------|-------|-------|-----------|

## Contexte accumulé

### Décisions

Les décisions sont consignées dans le tableau Key Decisions de PROJECT.md.
Décisions récentes affectant le travail en cours :

- Outbox de rappels écrite dans la même transaction que l'état terminal (schéma v0.1 dès la phase 2)
- Threads + Popen + Job Object (`ctypes`) ; asyncio pour le HTTP seulement
- `httpx2` pour le rappel ; `bcf-client` isolé dans `deskgate-bcf` (GPL-3)

### À faire

Aucun.

### Blocages / points d'attention

- Spikes de recherche : phase 3 (409 n8n, encodage signature), phase 4 (mcp dans Job Object, `bcf-client`, multiprocessing `ifcclash`), phase 5 (Planificateur sans élévation)
- Relecture juridique de la frontière GPL avant distribution d'un binaire

## Continuité de session

Dernière session : 2026-10-20
Arrêt à : feuille de route créée
Fichier de reprise : Aucun

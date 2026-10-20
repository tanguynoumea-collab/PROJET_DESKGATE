# 05 — Pipelines cibles (cas d'usage réels)

Ces pipelines ne font **pas** partie du runner (qui reste générique). Ils décrivent ce qui va le
consommer et servent à valider ses fonctionnalités.

## Architecture agents ↔ pipelines

```
┌ Agent superviseur ──────────── synthétise, présente → tableau de bord personnalisé
│   ▲ rapport consolidé
├ Hermes Agent (coordination) ── DÉCIDE : quand lancer, quoi en conclure (ne calcule jamais)
│   │ appelle le workflow n8n exposé par « MCP Server Trigger »
│   ▼                    ▲ JSON de résultat (schéma fixe) + chemins des livrables
├ Pipeline n8n ───────────────── EXÉCUTE de façon déterministe
│   │ un nœud = un plugin du runner
│   ▼
└ Deskgate (Windows) ─────────── calcul IfcOpenShell, logiciels (ODM, Zoom), base des conflits
```

## P1 — Coordination (le pipeline de validation de la v0.1)

Déclencheur : dépôt d'un IFC dans un dossier (SharePoint ou Dalux / Kairnial **synchronisé sur
le PC**), ou lancement par Hermes, ou chaque semaine.

1. **Ingestion** : attendre que le fichier soit **stable** (taille inchangée pendant N secondes ;
   les clients de synchronisation écrivent progressivement), calculer le **hash**, ignorer un
   fichier déjà traité, enregistrer la version dans le **registre des maquettes**.
2. **Association** des maquettes du même bâtiment / lot (comparaison des niveaux).
3. **Détection de conflits** (`ifc.clash`) selon une **matrice de règles** en YAML (lot A × lot B,
   mode, tolérance).
4. **Tri par l'IA** de la pertinence, avec les règles métier de l'utilisateur, par exemple :
   éléments `EVI` = évidements (réservations), plafond actif, murs `EI`, filtrage par
   localisation. Chaque conflit écarté est justifié.
5. **Déduplication** contre la **base des conflits existants** (voir ci-dessous).
6. **Livrables** : BCF 2.1 (nouveaux conflits, éventuellement persistants mis à jour) + rapport
   d'analyse, rangés dans un dossier défini.
7. **Retour à Hermes** : JSON au schéma fixe.

### Base des conflits et déduplication (partie la plus délicate)

En **base de données** (SQLite ou Postgres), pas en fichiers BCF :
- **signature stable** d'un conflit : `(GlobalId_A, GlobalId_B)` triés + identifiant de règle ;
  signature de secours si les GlobalId changent : position arrondie + types + niveau ;
- **statut** : `nouveau | persistant | résolu | écarté` (+ justification de l'IA, date de
  première et dernière détection) ;
- correspondance signature ↔ identifiant d'issue externe (BCF, Dalux, Kairnial, BIMcollab) si
  les issues vivent ailleurs ;
- un conflit absent d'une nouvelle exécution sur les mêmes maquettes passe en `résolu`.

### Schéma JSON de retour vers Hermes (à figer)

```json
{ "run_id": "...", "date": "...", "maquettes": [ { "nom": "...", "version": "...", "hash": "..." } ],
  "conflits": { "nouveaux": 12, "persistants": 30, "resolus": 8, "ecartes": 41 },
  "critiques": [ { "signature": "...", "lots": "CVC × STR", "niveau": "R+2", "resume": "..." } ],
  "livrables": { "bcf": "C:/BIM/livrables/...bcf", "rapport": "C:/BIM/livrables/...md" },
  "alertes": [ "..." ] }
```
Hermes et le superviseur ne dépendent **que de ce schéma**, jamais du contenu du rapport.

## P2 — Audit (à chaque dépôt)

1. Ingestion (comme P1) + contrôle de l'en-tête IFC (schéma, application d'export).
2. **Règles du gabarit d'audit** de l'utilisateur, **traduites en règles vérifiables** : IDS pour
   les exigences de propriétés (via `ifctester`), YAML pour le reste. L'IA ne réinterprète pas
   le gabarit à chaque exécution (sinon deux audits du même fichier divergent).
3. Commentaire et priorisation par l'IA.
4. Rapport d'audit + notification.

Variante **audit LOI via ODM** : un nœud appelle le plugin `odm.audit_loi` (type `mcp`, ou `cli`
si ODM a une ligne de commande — préférable pour une étape fixe), puis l'IA interprète.

## P3 — Évolution (chaque semaine)

1. Le registre fournit les versions N et N-1 d'une maquette.
2. **Comparaison déterministe** (`ifc.diff`, base `ifcdiff`) : éléments ajoutés / supprimés /
   modifiés par GlobalId, propriétés, géométrie, écarts de quantités.
3. **Agent spécialisé** de comparaison : synthèse par lot et par niveau, changements à risque.
4. Rapport d'évolution.

Attention : repose sur la **stabilité des GlobalId**. Avec Revit, paramètres d'export identiques
d'une semaine à l'autre. Prévoir un rapprochement de secours (type, position, nom).

## Briques communes (sous-workflows n8n)

Ingestion, génération de rapport, appel au jugement IA, notification.

## Plugins BIM à prévoir (dépôt `deskgate-bim`)

| Plugin | Type | Base |
|---|---|---|
| `ifc.clash` | python | `bim_assistant.clash` (`clash`, `write_bcf`) |
| `ifc.audit` | python | `bim_assistant.ifc_engine` + `ifctester` |
| `ifc.diff` | python | `ifcdiff` |
| `ifc.quantities` | python | `bim_assistant.ifc_engine` / `geometry` |
| `ifc.registry` | python | registre des maquettes (versions, hash, lots) |
| `clash.dedup` | python | base des conflits, signatures, statuts |
| `odm.audit_loi` | mcp ou cli | ODM |
| `zoom.nightshift` | cli | `cli-anything-bczoom` (requires_session) |

## Règles métier connues (projet CPR, maquette BaS, coordination P02)

À injecter dans le tri IA du pipeline de coordination :
- `EVI` dans un nom = évidement / réservation → un conflit avec un réseau qui le traverse est
  attendu, pas un problème ;
- plafond actif : à traiter à part des faux plafonds classiques ;
- murs `EI` (coupe-feu) : traversées à signaler avec priorité ;
- filtrer par localisation (`location=`) pour limiter le périmètre.

## Conventions BCF déjà établies dans le projet d'origine

Deux points de vue par issue : (1) objets du conflit seuls ; (2) contexte gris transparent. Pas
de sélection enregistrée. Zoom applique les couleurs ARGB.

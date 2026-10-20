# Paysage des fonctionnalités

**Domaine :** passerelle locale de tâches Windows (n8n -> outils lourds), plugins BIM IfcOpenShell
**Recherché le :** 2026-10-20
**Confiance globale :** MOYENNE à HAUTE (cœur runner : conception cohérente avec CI runners, Celery/RQ, Windmill, rapport d'existant ; `ifc.clash` : API IfcOpenShell vérifiée via Context7, mode `duplicate` non vérifié)

Légende versions : v0.1 à v0.4 = `ROADMAP.md`. Complexité : Faible / Moyenne / Élevée.

## 1. Runner : fonctionnalités indispensables (table stakes)

Un manque ici = la valeur centrale (« n8n reprend fiablement, quel que soit le résultat ») est fausse.

| Fonctionnalité | Pourquoi attendue | Complexité | Version | Notes |
|---|---|---|---|---|
| Soumission asynchrone `POST /jobs` -> 202 + `job_id` | Tâches de 20-40 min, HTTP synchrone impossible | Faible | v0.1 | Validation des paramètres avant mise en file (400 immédiat, pas d'échec tardif) |
| Cycle de vie complet `queued -> running -> succeeded/failed/timeout/cancelled/interrupted` | Tout runner (GitHub Actions, Rundeck) expose des états terminaux distincts | Moyenne | v0.1 | Transitions atomiques en SQLite ; un seul état terminal par tâche, jamais réécrit |
| File persistante SQLite (WAL), une tâche à la fois | Survie au redémarrage | Moyenne | v0.1 | Concurrence par ressource nommée = v0.2 |
| Lecture d'état `GET /jobs/{id}` (statut, progression, résumé, artefacts, erreur) | Repli par interrogation si le rappel est perdu | Faible | v0.1 | C'est le filet de sécurité du rappel |
| Annulation `POST /jobs/{id}/cancel` | Standard ; une tâche de 40 min doit être arrêtable | Moyenne | v0.1 | Annuler en `queued` = trivial ; en `running` = Job Object. Idempotente (annuler 2 fois = OK) ; état déjà terminal = 409 ou no-op documenté |
| Délai maximum par tâche + arrêt de l'arbre de processus | Sans cela, un processus zombie bloque la file | Moyenne | v0.1 | Job Object (`CREATE_SUSPENDED`, pas de breakaway). Défaut par capacité, surcharge plafonnée côté client |
| Journaux par tâche `GET /jobs/{id}/logs` | Diagnostic indispensable des échecs longs | Faible | v0.1 | Capture stdout/stderr + `ctx.log` ; borner la taille, tronquer avec marqueur explicite |
| Progression (`progress(pct, msg)`) | Attendue pour tâches longues ; utile à l'UI | Faible | v0.1 (champ) | Exposée en lecture ; pas de poussée vers n8n (voir anti-fonctionnalités) |
| Rappel HTTP vers `resumeUrl` avec réessais à délai croissant | Cœur de la valeur ; n8n peut être redémarré/indisponible | Moyenne | v0.1 | URL appelée telle quelle, masquée partout, plafond 1 Mio, abandon tracé. Rappel émis pour TOUS les états terminaux, y compris `interrupted` |
| Rappel « au moins une fois » + `job_id` stable dans la charge | n8n doit pouvoir dédupliquer ; la reprise d'un Wait déjà repris renvoie une erreur à tolérer | Faible | v0.1 | Traiter 404/410 du webhook Wait comme « déjà repris » = arrêt des réessais, pas une panne |
| Reprise au redémarrage : `running` -> `interrupted` + rappel | Exigence du critère d'acceptation v0.1 | Moyenne | v0.1 | Aussi : tâches `queued` conservées et rejouées ; rappels non livrés repris au démarrage (table d'envoi persistante) |
| Correspondance de chemins `/data` <-> `C:/BIM` + refus hors racines | Sans elle, Docker et Windows ne se parlent pas | Moyenne | v0.1 | Refus `..`, liens symboliques, jonctions ; conversion aussi pour les artefacts de sortie |
| Artefacts : déclaration `ctx.artifact(path, kind)`, chemins dans le résultat | Gros résultats hors rappel (BCF, JSON complet) | Faible | v0.1 | Dossier de travail par tâche. Téléchargement HTTP `/artifacts/{name}` = pas nécessaire en v0.1 (partage de dossier), v0.2 |
| Résumé volumineux déporté en `summary.json` | Plafond de rappel 1 Mio | Faible | v0.1 | Le rappel porte alors le chemin |
| Santé `GET /health` (sans détail sensible) | Sonde Docker/n8n, `deskgate doctor` | Faible | v0.1 | Version, état de la file, pas de chemins |
| Jeton Bearer obligatoire (haché), écoute 127.0.0.1 uniquement | Tout conteneur local atteint le runner | Faible | v0.1 | Un jeton dans `runner.toml` en v0.1 ; comparaison à temps constant ; refus de démarrer hors loopback |
| Aucune commande libre, pas de `shell=True` | Modèle de sécurité | Faible | v0.1 | Capacités codées en dur en v0.1 |
| Journal d'audit minimal (soumission, fin, refus) | Exigence « audit » ; en v0.1 au moins tracer les événements | Faible | v0.1 (minimal), v0.2 (complet) | Masquer `signature` et secrets ; stocker chemins/paramètres (donnée locale) |
| Démarrage à l'ouverture de session (`deskgate init`) | Session GUI, pas de service | Moyenne | v0.1 | Tâche planifiée « à l'ouverture de session » ; gérer l'instance unique (verrou) |
| Idempotence par `idempotency_key` | Rejeu n8n (reprise d'exécution, réessai de nœud) ne doit pas relancer 20 min de calcul | Moyenne | v0.2 | Précision utile : en v0.1, accepter et stocker la clé ; au minimum refuser/renvoyer le job existant si une tâche non terminale a la même clé (évite le double lancement) |
| Manifeste `plugin.yaml` + validation JSON Schema | Ajouter un plugin sans modifier le runner | Moyenne | v0.2 | Critère d'acceptation v0.2 |
| Concurrence par ressource (`gui-session`, `cpu-heavy`, `light`) | Un seul calcul lourd / une seule interface graphique à la fois | Moyenne | v0.2 | |
| Jetons multiples + droits par plugin + refus audités | Plusieurs conteneurs/clients locaux | Moyenne | v0.2 | `deskgate token create/revoke` |
| `deskgate doctor` | Diagnostic d'installation (pont Docker, chemins, uv, plugins) | Moyenne | v0.2 | Test `host.docker.internal` dès v0.1 en script |
| Découverte `/capabilities` (+ schémas) | Alimente le nœud n8n et l'UI | Faible | v0.2 | |
| Téléchargement d'artefacts HTTP | Cas où le dossier partagé n'existe pas | Faible | v0.2 | Optionnel tant que `C:\BIM` est monté |

## 2. Runner : différenciateurs

Ne sont pas attendus d'un runner générique, mais fondent le créneau (cf. rapport de l'existant).

| Fonctionnalité | Valeur | Complexité | Version | Notes |
|---|---|---|---|---|
| Exécution dans la session Windows de l'utilisateur (pilotage d'applications graphiques) | Aucun concurrent MIT/Apache ne le fait avec rappel + droits | Moyenne | v0.1 (base) | Ressource `gui-session` et `requires_session` en v0.2 ; vérifier session déverrouillée avant de lancer |
| Rappel direct vers la `resumeUrl` d'un nœud Wait n8n | Pas de scrutation côté n8n, reprise native | Faible | v0.1 | |
| Exécuteur MCP sans LLM (`mcp.call`) | Réutilise des serveurs MCP existants comme étapes déterministes | Moyenne | v0.1 (stdio, codé en dur), v0.2 (Streamable HTTP) | SDK `mcp` officiel ; gérer cycle de vie du serveur stdio (lancé par tâche, arrêt dans le Job Object) |
| Manifestes à trois exécuteurs (python / cli / mcp) avec schémas d'entrée-sortie | Un catalogue unique et typé | Élevée | v0.2 | Environnement uv isolé par plugin |
| Arrêt de l'arbre complet par Job Object (testé là où psutil échoue) | Fiabilité réelle des délais/annulations | Moyenne | v0.1 | |
| Nœud n8n unique soumission + attente, champs générés depuis le schéma | Réduit un pipeline à un nœud | Élevée | v0.3 | Vérifié faisable dans le code n8n 2.43.8 |
| Interface locale `/ui` (catalogue, bouton Tester, tâches, journaux, jetons, audit) | Utilisable par un collègue sans ligne de commande | Élevée | v0.3 | |
| `pipeline.lock` + installation reproductible | Reproductibilité d'un pipeline | Moyenne | v0.4 | |
| `AGENTS.md` éprouvé (installation par une IA) | Adoption | Faible | v0.4 | |
| Idempotence avec renvoi du résultat précédent (sans recalcul) | Économise des tâches de 20-40 min | Moyenne | v0.2 | Dépend d'une clé stable + empreinte des paramètres ; refuser si même clé mais paramètres différents (409) |
| Ressource `requires_session` avec contrôle d'état de session (verrouillée/déconnectée) -> échec explicite | Évite des tâches GUI bloquées sans message | Moyenne | v0.2 | MOYENNE confiance : détection de verrouillage fiable à vérifier (API Windows) |

## 3. Anti-fonctionnalités (à ne délibérément PAS construire)

| Anti-fonctionnalité | Pourquoi l'éviter | Alternative |
|---|---|---|
| DAG, enchaînement d'étapes, reprise d'étapes | Rôle de n8n ; devient un second orchestrateur (piège de Windmill/Kestra) | Un appel = un plugin ; n8n enchaîne |
| Planification (cron, déclencheurs, surveillance de dossier) | Idem ; l'ingestion et la stabilité de fichier sont dans le pipeline n8n | Nœuds n8n Schedule / déclencheur de fichier |
| Serveur MCP Deskgate | Aucun usage ; surface d'attaque en plus | Workflow n8n exposé par MCP Server Trigger ou API HTTP |
| Commande libre / `shell=True` / exécution arbitraire | Inverse du modèle de sécurité (cf. Desktop Commander) | Capacités déclarées uniquement |
| Réessai automatique des tâches échouées | Les calculs BIM sont déterministes ; relancer un échec masque un bug et double le coût ; risque d'effets de bord (COM) | Le rappel `failed` remonte à n8n qui décide (nœud de réessai n8n) ; seul le rappel HTTP est réessayé |
| Priorités, files multiples, équilibrage de charge | Un runner, un utilisateur | Concurrence par ressource suffit |
| Multi-utilisateurs, exécution distante, macOS/Linux | Hors périmètre (D7, D9) | Un runner par PC |
| Service Windows | Session 0 : pas de bureau | Planificateur de tâches à l'ouverture de session |
| Poussée de progression vers n8n (webhooks intermédiaires) | `resumeUrl` n'accepte qu'une reprise ; une deuxième appel casserait l'attente | Lecture `GET /jobs/{id}` ; progression visible en UI |
| Transfert de fichiers par HTTP en entrée (téléversement) | Fichiers IFC de centaines de Mo ; on transmet des chemins | Dossier partagé `C:\BIM` <-> `/data` |
| Déduplication / base des conflits / registre des maquettes dans Deskgate | Projet d'intégration (P1) ; plugins `ifc.registry`, `clash.dedup` écartés du dépôt | Base côté pipeline n8n ; Deskgate fournit des GlobalId stables et un résultat structuré |
| Tri IA, règles métier (EVI, EI, plafond actif) | Hors passerelle | Pipeline n8n filtre sur les champs du résultat |
| Rétention illimitée de journaux/artefacts | Disque local qui gonfle | Purge configurable simple (v0.2) |
| Chiffrement TLS / OAuth | Loopback seulement | Jeton Bearer haché |

## 4. Capacité `ifc.clash` : contenu pour un premier usage réel (v0.1)

Base vérifiée (Context7, IfcOpenShell v0.9.0, doc `ifcclash` et `geometry_tree`) :
- `ifcclash` : modes intersection, collision, clearance ; ensembles de conflits (un modèle ou plusieurs) ; groupement intelligent (`smart grouping`) ; sélecteurs ; export JSON et BCF-XML (HAUTE confiance).
- API arbre géométrique : `clash_intersection_many(a, b, tolerance, check_all)` (types protrusion/pierce/collision), `clash_collision_many(a, b, allow_touching)`, `clash_clearance_many(a, b, clearance, check_all)` ; retourne GlobalId, classe IFC, nom, points p1/p2, distance (HAUTE confiance).
- Le mode `duplicate` n'est PAS documenté comme mode natif d'`ifcclash` : il serait à écrire par Deskgate (BASSE confiance, à valider en phase de recherche).

### 4.1 Paramètres d'entrée

| Paramètre | Rôle | Priorité v0.1 | Notes |
|---|---|---|---|
| `ifc_a`, `ifc_b` (chemins `/data/...`) | Modèles comparés ; `ifc_b` absent = auto-conflit dans A | Indispensable | Chemins validés par le runner ; `ifc_b` omis = « within a single set » de l'API |
| `selector_a`, `selector_b` | Sélection d'éléments (syntaxe sélecteur IfcOpenShell : classe, `location=`, propriétés) | Indispensable | Premier cas : `IfcFlowSegment` contre `IfcWall`/`IfcSlab`/`IfcBeam`. Valider le sélecteur avant de calculer (échec rapide). Filtre par localisation pour limiter le périmètre (besoin P1) |
| `mode` | `hard` (intersection/collision), `clearance`, `touch`, `duplicate` | Indispensable : `hard` ; fortement souhaité : `clearance` ; `touch` et `duplicate` en v0.1 si le coût reste faible, sinon v0.2 | Correspondance : `hard` -> `clash_intersection_many` (protrusion/pierce/collision) ; `touch` -> `clash_collision_many(allow_touching=True)` ; `clearance` -> `clash_clearance_many` ; `duplicate` -> maison (éléments quasi identiques : même classe, boîtes englobantes et volumes proches, ou même position/géométrie) |
| `tolerance` (mm ou m, unité explicite) | Seuil d'ignorance pour `hard` | Indispensable | Documenter l'unité (API en mètres) ; défaut sûr (ex. 2 mm comme l'exemple IfcOpenShell) |
| `clearance` (distance) | Distance de dégagement pour `clearance` | Indispensable si mode clearance | Doit être >= 0 |
| `check_all` | Pire cas (profondeur max) vs premier trouvé | Souhaité | Coût CPU plus élevé ; défaut `true` pour fournir la profondeur de pénétration |
| `grouping` (`none` / par élément A / par élément B / `smart`) | Réduire des milliers de conflits en dizaines de sujets BCF | Indispensable (critère « regroupement » de la feuille de route) | Un conflit unique par couple (A,B) trié ; regroupement par élément d'un côté (ex. une gaine traverse 40 murs = 1 sujet ou 40 ?) à choisir : défaut `smart` d'`ifcclash` |
| `max_clashes` / plafond | Protection de la mémoire et du BCF | Souhaité | Marquer `truncated: true` dans le résumé |
| `output.bcf` (booléen, version `2.1`), `output.json` | Production des livrables | Indispensable | BCF via `deskgate-bcf` en sous-processus |
| `rule_id` / `label` (libre) | Étiquette recopiée dans le résultat | Souhaité | Permet à la base de conflits du pipeline (signature = GlobalId triés + identifiant de règle) |

### 4.2 Sortie

- `summary` (petit) : compteurs par mode, par couple de classes, par niveau si disponible ; nombre de conflits bruts et de groupes ; `truncated` ; durée ; chemins. Doit tenir sous 1 Mio, sinon `summary.json`.
- `data` ou fichier JSON complet (artefact `json`) : liste des conflits avec GlobalId A et B, classe IFC, nom, type de conflit, distance/profondeur, points p1/p2 (coordonnées en mètres), niveau (`IfcBuildingStorey`) et groupe. Les GlobalId sont la clé stable dont dépend la déduplication du pipeline P1 ; ne jamais les omettre.
- Artefact `bcf` : un `.bcf` BCF 2.1.

### 4.3 BCF 2.1 : exigences minimales

| Élément | Exigence | Notes |
|---|---|---|
| Un sujet (topic) par conflit ou par groupe | Indispensable | Titre lisible : « CVC x STR : <nom A> / <nom B> », statut initial, type, priorité optionnelle |
| GUID de sujet déterministe | Fortement souhaité | Dérivé de la signature (GlobalId A + B + règle) : permet à des exécutions successives de produire les mêmes identifiants et de mettre à jour des issues plutôt que d'en créer de nouvelles. À confirmer côté `bcf-client` (MOYENNE confiance) |
| Composants référencés (GlobalId `IfcGuid`) | Indispensable | Sans cela, le viewer ne sélectionne rien ; `AuthoringToolId` optionnel |
| Points de vue : (1) objets du conflit seuls ; (2) contexte gris transparent | Indispensable (convention déjà établie) | Caméra calculée depuis p1/p2 ou la boîte englobante des deux objets, couleurs ARGB, pas de sélection enregistrée |
| Captures d'écran (snapshot) | Non requis en v0.1 | Pas de rendu headless trivial ; les viewers (BIMcollab Zoom, Solibri, Dalux) n'en ont pas besoin pour ouvrir un viewpoint. Différé |
| Plafond de taille BCF | Souhaité | Au-delà d'un nombre de sujets, scinder en plusieurs `.bcf` (viewers lents) ; paramètre `bcf_max_topics` |
| Commentaire initial par sujet (distance, mode, règle) | Souhaité | Donne la raison du conflit sans ouvrir le modèle |
| Compatibilité BCF 3.0 | Différé (v0.2) | Déjà prévu pour `deskgate-bcf` |

### 4.4 Fiabilité d'exécution propres au clash

| Besoin | Raison | Version |
|---|---|---|
| Progression par paire de jeux (« chargement A », « géométrie », « conflits », « BCF ») | Tâche > 10 minutes, critère d'acceptation | v0.1 |
| Vérification coopérative de `ctx.cancelled()` entre phases | Annulation propre ; l'arrêt dur par Job Object reste le filet | v0.1 |
| Erreurs claires : IFC illisible, sélecteur sans résultat, schéma IFC non géré, mémoire | Un `failed` doit être exploitable par n8n (`error.code`) | v0.1 |
| Sélection vide = succès avec 0 conflit et avertissement, pas un échec | Sinon le pipeline se bloque sur un filtre trop strict | v0.1 |
| Unités et système de coordonnées : lire l'unité du projet, convertir en mètres | Source classique de tolérances fausses (mm vs m) | v0.1 (voir PITFALLS) |
| Multi-modèles : même coordonnées partagées (ou pas) | Modèles de lots différents avec points de base différents donnent zéro conflit ou du bruit | v0.1 : avertir ; v0.2 : option de recalage |
| Ensembles multiples en un appel (matrice lot A x lot B, comme P1 étape 3) | Une tâche par paire suffit pour la v0.1 ; la matrice reste dans n8n | Différé (n8n boucle) |

## 5. Dépendances entre fonctionnalités

```
Jeton + 127.0.0.1 ------------> toutes les routes
Chemins (/data <-> C:/BIM) ----> ifc.clash, artefacts, rappel (chemins renvoyés)
File SQLite + cycle de vie ----> annulation, délai, interrupted, rappel, idempotence
Job Object -------------------> délai, annulation dure, sous-processus deskgate-bcf
Rappel + réessais ------------> table d'envoi persistante -> reprise au démarrage (interrupted)
Résumé > 1 Mio ---------------> summary.json -> artefacts
ctx (log, progress, artifact, cancelled) -> ifc.clash (progression, annulation)
Manifeste plugin.yaml --------> exécuteurs python/cli/mcp, /capabilities, doctor, droits par plugin
/capabilities + input_schema -> nœud n8n (v0.3), formulaire Tester de l'UI (v0.3)
Droits par plugin ------------> jetons multiples -> audit des refus
deskgate-bcf (GPL-3, CLI) ----> ifc.clash BCF, puis plugins bcf.write/bcf.read (type cli, test de l'exécuteur cli)
Concurrence par ressource ----> manifeste (champ resource) ; en v0.1 : une seule tâche à la fois
Idempotence ------------------> clé stable + empreinte des paramètres (v0.2)
```

## 6. Recommandation pour la version 0.1

À prioriser (ordre de construction suggéré) :
1. Socle : jeton, chemins, SQLite et cycle de vie, `POST/GET /jobs`, `/health`.
2. Exécution fiable : exécuteur en sous-processus + Job Object, délai, annulation, `interrupted` au redémarrage.
3. Rappel : table d'envoi persistante, réessais, masquage de la `resumeUrl`, plafond 1 Mio.
4. `ifc.clash` mode `hard` + `clearance`, sélecteurs, tolérance, regroupement, JSON complet.
5. `deskgate-bcf` : BCF 2.1 avec deux points de vue par sujet.
6. `mcp.call` (stdio), `deskgate init`, docker-compose + workflow d'exemple.
7. Modes `touch` et `duplicate` : en v0.1 seulement si le cœur est stable, sinon v0.2 (le critère d'acceptation ne les exige pas ; `duplicate` n'est pas natif).

Reporter explicitement :
- v0.2 : idempotence complète, ressources, jetons multiples, audit complet, téléchargement d'artefacts, BCF 3.0, lecture de BCF, recalage de modèles.
- v0.3 : nœud n8n, interface.
- v0.4 : `pipeline.lock`, publication.

Point de vigilance sur la cohérence de la feuille de route : `ROADMAP.md` place l'idempotence en v0.2, mais le rejeu d'un nœud n8n en v0.1 peut déjà doubler un calcul de 20 minutes ; prévoir au minimum le champ `idempotency_key` accepté et le refus de doublon non terminal en v0.1 (faible coût).

## Sources

- `ROADMAP.md`, `ARCHITECTURE.md`, `.planning/PROJECT.md`, `docs/passation/05-PIPELINES-CIBLES.md`, `.arthemis/reports/existant-cycle-1.md` (HAUTE : documents du projet)
- IfcOpenShell v0.9.0, Context7 `/ifcopenshell/ifcopenshell` : `src/ifcclash/README.md`, `geometry_tree.md` (clash_intersection_many, clash_collision_many, clash_clearance_many), `ifcclash.md` (HAUTE)
- Mode `duplicate`, GUID déterministe BCF, détection de session verrouillée : BASSE/MOYENNE, issus de raisonnement, à valider en recherche de phase

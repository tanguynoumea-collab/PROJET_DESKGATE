---
gsd_state_version: 1.0
milestone: v0.1
milestone_name: Runner minimal
status: verifying
stopped_at: decision-ds-1 tranchée (exposer data) ; retour GSD de DS-ARCH-1 à insérer
last_updated: "2026-10-23T06:54:45.172Z"
last_activity: 2026-10-22
progress:
  total_phases: 15
  completed_phases: 8
  total_plans: 63
  completed_plans: 63
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-20)

**Core value:** n8n délègue une tâche longue au PC Windows et reprend fiablement quand elle se termine, quel que soit le résultat (succès, échec, délai dépassé, annulation, redémarrage du runner).
**Current focus:** Phase 5.3 — corrections-audit-council-1-passe-2-superviseur-refus-msix-de-task-install-messages-et-test-doctor

## Current Position

Phase: 999.1
Plan: Not started
Status: Phase complete — ready for verification
Last activity: 2026-10-22

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: -
- Total execution time: -

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

*Updated after each plan completion*
| Phase 01 P01 | 25min | 3 tasks | 13 files |
| Phase 01 P02 | 15min | 2 tasks | 4 files |
| Phase 01 P03 | 20min | 2 tasks | 13 files |
| Phase 01 P04 | 15min | 2 tasks | 5 files |
| Phase 01 P05 | 25min | 2 tasks | 7 files |
| Phase 02 P01 | 15min | 2 tasks | 6 files |
| Phase 02 P02 | 10min | 2 tasks | 6 files |
| Phase 02 P03 | 15min | 2 tasks | 6 files |
| Phase 02 P04 | 15min | 2 tasks | 8 files |
| Phase 02 P05 | 10min | 2 tasks | 7 files |
| Phase 02 P06 | 25min | 2 tasks | 4 files |
| Phase 02 P07 | 15min | 2 tasks | 5 files |
| Phase 02 P08 | 15min | 2 tasks | 4 files |
| Phase 02 P09 | 40min | 3 tasks | 7 files |
| Phase 03 P01 | 20min | 2 tasks | 11 files |
| Phase 03 P02 | 10min | 2 tasks | 3 files |
| Phase 03 P03 | 10min | 2 tasks | 4 files |
| Phase 03 P04 | 25min | 2 tasks | 5 files |
| Phase 03 P05 | 25min | 2 tasks | 7 files |
| Phase 03 P06 | 25min | 2 tasks | 5 files |
| Phase 03 P07 | 20min | 2 tasks | 4 files |
| Phase 03 P08 | 25min | 2 tasks | 2 files |
| Phase 04 P01 | 25min | 3 tasks | 25 files |
| Phase 04 P02 | 25min | 2 tasks | 15 files |
| Phase 04 P03 | 30min | 2 tasks | 6 files |
| Phase 04 P04 | 40min | 3 tasks | 12 files |
| Phase 04 P05 | 25min | 3 tasks | 7 files |
| Phase 04 P06 | 20min | 2 tasks | 8 files |
| Phase 04 P07 | 50min | 3 tasks | 12 files |
| Phase 05 P01 | 20min | 2 tasks | 5 files |
| Phase 05 P02 | 20min | 2 tasks | 6 files |
| Phase 05 P03 | 25min | 2 tasks | 4 files |
| Phase 05 P05 | 15min | 2 tasks | 7 files |
| Phase 05 P04 | 20min | 2 tasks | 4 files |
| Phase 05 P07 | 25min | 3 tasks | 4 files |
| Phase 05 P08 | 25min | 3 tasks | 1 files |
| Phase 05 P09 | 10min | 2 tasks | 3 files |
| Phase 05.1 P01 | 25min | 2 tasks | 8 files |
| Phase 05.1 P03 | 10min | 2 tasks | 2 files |
| Phase 05.1 P02 | 40min | 2 tasks | 6 files |
| Phase 05.1 P04 | 30min | 3 tasks | 7 files |
| Phase 05.1 P05 | 35min | 3 tasks | 8 files |
| Phase 05.1 P06 | 30min | 2 tasks | 7 files |
| Phase 05.1 P07 | 30min | 3 tasks | 7 files |
| Phase 05.1 P08 | 40min | 3 tasks | 5 files |
| Phase 05.1 P09 | 40min | 3 tasks | 7 files |
| Phase 05.1 P11 | 20min | 2 tasks | 0 files |
| Phase 05.1 P10 | 25min | 3 tasks | 8 files |
| Phase 05.1 P12 | 25min | 3 tasks | 6 files |
| Phase 05.1 P13 | 40min | 2 tasks | 1 files |
| Phase 05.2 P01 | 20min | 2 tasks | 5 files |
| Phase 05.2 P02 | 10min | 2 tasks | 8 files |
| Phase 05.2 P03 | 15min | 2 tasks | 4 files |
| Phase 05.2 P04 | 15min | 2 tasks | 8 files |
| Phase 05.2 P05 | 15min | 2 tasks | 8 files |
| Phase 05.2 P06 | 25min | 2 tasks | 9 files |
| Phase 05.2 P07 | 12min | 2 tasks | 7 files |
| Phase 05.2 P08 | 30min | 2 tasks | 13 files |
| Phase 05.2 P09 | 20min | 2 tasks | 6 files |
| Phase 05.2 P10 | 75min | 2 tasks | 10 files |
| Phase 05.3 P01 | 20min | 2 tasks | 4 files |
| Phase 05.3 P02 | 40min | 3 tasks | 9 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Init]: Outbox de rappels écrite dans la même transaction que l'état terminal
- [Init]: Threads + Popen + Job Object (`ctypes`) ; asyncio pour le HTTP seulement
- [Init]: `httpx2` pour le rappel ; `bcf-client` isolé dans `deskgate-bcf` (GPL-3)
- [Phase 1]: Architecture d'implémentation : .arthemis/reports/llm-council-1.md (noyau pur core/ + tests AST, thread engine + thread sender, mutex puis socket SO_EXCLUSIVEADDRUSE hors lifespan, fichiers = transport, outbox callbacks sans payload) — Conseil d'approche cycle 1
- [Phase 2]: Capacités v0.1 déclarées dans runner.toml [capabilities.<id>] (kind, python, entry, timeout_max, resource), validées par Pydantic ; aucun nom BIM dans src/deskgate — Règle 1 de CLAUDE.md ; validé par l'utilisateur
- [Phase 2]: Migration 1 complète en phase 2 (tables callbacks et audit) ; la phase 3 livre envoi, politique, plafond, masquage et contenu complet de l'audit — La recovery JOB-06 insère le rappel dans la transaction terminale ; validé par l'utilisateur
- [Phase 3]: Rappel garanti au moins une fois ; n8n ne reprend qu'une fois, un doublon reçoit 409 tracé delivered_duplicate (remplace « une fois et une seule ») — Exactement-une-fois impossible côté runner ; validé par l'utilisateur
- [Phase 01]: ruff exclut .planning/.arthemis/.claude/docs (ruff 0.17 formate le Markdown)
- [Phase 01]: validate_artifact_path convertit le chemin hôte lexical, pas le résolu
- [Phase 01]: Handlers API : cast() à la place de assert (ruff S101)
- [Phase 02]: stop() de l'engine ne conclut jamais la tâche : recovery au redémarrage
- [Phase 3]: Migration 2 additive : colonne callbacks.maybe_delivered (posée avant chaque envoi) pour distinguer delivered_duplicate d'abandoned_stale ; 401/404 exigent deux constats consécutifs avant abandon ; pas de dernier envoi après 24 h ; 413 : un renvoi minimal puis backoff ; jobs.callback_url purgée à l'état final du rappel — Recherche phase 3 (code n8n 2.43.8) ; questions ouvertes tranchées par ARTHEMIS, aucun utilisateur réel
- [Phase 03]: CB-04 complet ; CB-05, SEC-05, SEC-06 restent Pending (03-06, 03-07)
- [Phase 03]: 03-07 : compteur de rappels et battement du sender non exposés dans /health en v0.1
- [Phase 4]: Valeurs env des serveurs MCP transmises au worker par son environnement, jamais écrites dans input.json ; path_params déclarés par capacité, convertis et validés par le runner ; Capability.settings vers ctx.settings ; kind mcp ; rendu visuel BCF dans BIMcollab = vérification humaine différée (phase 5) — Recherche phase 4 ; input.json lisible par n8n via /data/travail
- [Phase 04]: Echec de uv sync d'un plugin = pytest.fail, pas de skip silencieux
- [Phase 04]: Chemins déclarés reconvertis et revalidés au lancement ; secrets MCP hors input.json
- [Phase 04]: deskgate-bcf : stderr forcé en UTF-8 (page de code Windows)
- [Phase 04]: 04-04 : NS du GUID v5 de groupe figé ; p1/p2 échangés avec a/b (p1 sur A vérifié)
- [Phase 04]: Contexte gris BCF : arbre BREP natif + select_box (voie A du spike)
- [Phase 5]: Accord utilisateur du 2026-10-21 : créer C:\BIM (depot, travail, livrables), %LOCALAPPDATA%\Deskgate, et installer la tâche du Planificateur ; recette sur le compose du dépôt (n8n 2.43.8, port 5679) ET sur le n8n de l'utilisateur (2.42.5, port 5678, non modifié) ; calcul long CVC (PIC-EXE-AW-CVC, 532 Mo) × ARC (PIC_REV_HRS_ARC) en mode hard, maquettes copiées depuis G:\Mon Drive\07_PROJETS\DESKGATE — Décisions de la discussion de la phase 5 ; 01-D1 (host.docker.internal) vérifié le 2026-10-21
- [Phase 5]: Recherche phase 5 : action de la tâche = pythonw.exe -m deskgate serve + journal fichier après le mutex ; RestartOnFailure ne relance pas après taskkill /F (relance ACC-02 par schtasks /Run) ; N8N_WEBHOOK_URL ; workflow avec déclencheur Webhook ; test If sur $json.body?.status ; import CLI n8n (id requis) ; n8n de l'utilisateur : import manuel sauf accord — Expériences de 05-RESEARCH.md (tâche jetable supprimée, n8n 2.42.5 jetable)
- [Phase 5]: Pythons gérés par uv (AppData\Roaming\uv\python 3.13/3.14) cassés depuis une recherche de la phase 1 ; en attendant réparation, UV_PYTHON=C:\Users\Tanguy\AppData\Local\Python\pythoncore-3.14-64\python.exe — Report de la passation 2026-10-21T09:41 ; réparation proposée, réponse utilisateur attendue
- [Phase 5]: Exécution des plans séquentielle dans l'arbre principal (pas de worktree), un gsd-executor à la fois ; n8n de l'utilisateur (pipelines-n8n, 2.42.5, port 5678) jamais modifié — Report de la passation 2026-10-21T09:41
- [Phase 5]: scheduler.py autorisé à importer ctypes et subprocess (tests d'architecture)
- [Phase 5]: 05-02 : journal fichier après le mutex, échec d'ouverture non bloquant ; --version ajouté
- [Phase 5]: 05-05 : fuseau par défaut du compose en UTC (GENERIC_TIMEZONE)
- [Phase 5]: 05-06 : Claude (app MSIX) virtualise %LOCALAPPDATA% et %APPDATA% ; l'installation (uv tool install, init, plugins, bloc ifc.clash) est faite par l'utilisateur dans un PowerShell hors Claude, après suppression des copies virtualisées. Les exécuteurs ne font que lire %LOCALAPPDATA%\Deskgate, jamais y écrire — Choix utilisateur (option A) du 2026-10-21, parcours d'installation réel
- [Phase 05]: Recette: paramètres et preuves sous C:\BIM\recette (MSIX), n8n 2.43.8 sans écart
- [Phase 05]: ACC-01 non marqué complet : durée max 281 s < 600 s après paliers D-09; ACC-02 constaté
- [Phase 5]: ACC-01 : la durée n'est pas un objectif ; le critère retenu est un calcul de coordination réel et complet (maquettes réelles, aucun conflit tronqué, réservations exclues, mode hard 1 cm) lancé depuis n8n, runner démarré par la tâche, repris avec résumé et chemin du BCF — Décision utilisateur du 2026-10-21 : « peu importe le temps de calcul, la coordination la plus fiable »
- [Phase 5]: Titre des sujets BCF : « <trigramme bâtiment>/<étage>/<techniques>/<sujet> », ex. « BaJ/P01/CVC-ARC/Gaine x Faux-plafond » ; trigramme et code étage tirés d'une charte passée en paramètre du job (bâtiment IFC → trigramme, ex. Jura → BaJ, Tour → BaT ; niveau → code court) ; sujet = types des deux objets principaux ; entrée absente de la charte → valeur IFC brute + avertissement dans le résumé — Décision utilisateur du 2026-10-21 (04-D1) : trier facilement les sujets
- [Phase 5]: Phase insérée 5.1 : BCF exploitable dans BIMcollab Zoom (points de vue absents, 04-D1), nommage des sujets, findings clash-troncature et clash-reservations — 04-D1 en échec le 2026-10-21 ; findings d'audit corrigés par phase insérée, jamais en quick
- [Phase 5.1]: Test BIMcollab Zoom V0..V5 : seules V4 (Header/File IFC) et V5 (viewpoint.bcfv/snapshot.png) affichent les deux points de vue ; V1 cadre bien en coordonnées monde. Retenu : coordonnées monde, snapshot.png par vue, Header/File, noms conventionnels, Comment et Index — Verdict utilisateur du 2026-10-21 sur C:\BIM\recherche-5.1\zoom-tests
- [Phase 05.1]: 07 : maj-5.1.ps1 réinstalle les paquets des plugins (--reinstall-package), non éditables ; Header/File par maquette, caméras monde
- [Phase 5.1]: Nommage générique : Deskgate reçoit du job un gabarit de titre (champs bâtiment, étage, techniques, types) et des tables de correspondance ; aucun libellé ni code métier en dur dans le plugin (table française et liste de techniques retirées). La charte PIC, les libellés et les codes vivent dans le pipeline n8n (exemple) — Décision utilisateur du 2026-10-22 : Deskgate est une passerelle, pas un pipeline
- [Phase 5.1]: Vue 2 du BCF : le contexte gris transparent doit couvrir tout ce qui est visible ; les éléments hors contexte ne doivent pas rester dans leurs couleurs d'origine — 04-D1 rejoué le 2026-10-22 : certains éléments non grisés
- [Phase 5.1]: Vue 2 : approche A retenue (DefaultVisibility false, exceptions = conflit + contexte à 5 m, contexte gris transparent, reste masqué) — Choix utilisateur du 2026-10-22 dans BIMcollab Zoom (zoom-tests-v2), B1 de 05.1-12 levé
- [Phase 05.1]: Vue 2 : approche A (isolé) retenue par l'utilisateur après essai dans Zoom
- [Phase 5.1]: AUDIT_COUNCIL cycle 1 : /saas-council complet ; outillage en exécution éphémère (uvx pip-audit 2.10.1, semgrep 1.182.1, radon 6.0.1, uv run --with pytest-cov, npx jscpd), gitleaks NON VÉRIFIÉ (recherche de secrets par rg, déclarée) ; roster Tier 1 + Tier 2 (tenancy, sécurité, fiabilité, données) + Tier 3 pertinence et livraison ; perfcout sauté (runner local, aucun coût d'exécution) ; billing, conformité, IA, SEO non activés (aucune dépendance de paiement, aucune donnée personnelle, aucun SDK de modèle, aucune page publique) — Choix utilisateur du 2026-10-22 au pré-vol du council ; audit pas encore lancé
- [Phase 5.2]: Triage du council 1 : phase 5.2 = ARC-001 (code de sortie et relance du runner), SEC-001 (path_params par outil MCP, règle 4), LIV-001 (détection MSIX) + Mineurs FIA-001, MNT-007, FIA-005, TST-004, SEC-005, PER-001, FIA-003 ; autres Mineurs en backlog 999.1-999.6 ; rapport audits/saas-council-2026-10-22.md — Choix utilisateur du 2026-10-22 au checkpoint triage
- [Phase 05.2]: Engine: verdict non écrit mémorisé (_unsettled) et rejoué ; Job jamais tué sur OperationalError ; fatal à 5 erreurs
- [Phase 05.2]: required_files (kind python) vérifié par doctor, interdit en mcp; existence non vérifiée au chargement
- [Phase 05.2]: Superviseur : recréation dans le processus, abandon code 6 après 3 recréations en 10 min
- [Phase 05.2]: path_arguments par outil, arguments non déclarés opaques, env MCP limité au serveur visé
- [Phase 05.2]: Détection MSIX par sonde d'écriture (E3) + identité de paquet ; init refuse sans contournement
- [Phase 05.2]: serve() supervisé : on_give_up par assignation directe server.should_exit (B010), startup.log sans rotation avant le mutex
- [Phase 05.2]: Dernier résultat de la tâche lu par Get-ScheduledTaskInfo (argv fixe, nom par environnement); 0x8007010B en échec
- [Phase 05.2]: Seuil stale = max(10 x sondage, plancher fixe 30 s engine / 60 s sender) (D-07)
- [Phase 05.2]: path_arguments du serveur mini limité aux outils de fichiers autorisés
- [Phase 05.2]: Fermeture des Engine, Sender, bases et journal de démarrage par fixtures autouse ; ResourceWarning en erreur
- [Phase 5.3]: Triage des findings N2 (certification du council 1) : phase 5.3 = ARC-N2-001 (budget du superviseur consommé par un recover qui échoue, sans back-off), ARC-N2-002 (stop pendant un recover lent laisse un engine vivant), MNT-N2-001 et LIVR-N2-002 (\r dans runtime.py et AGENTS.md), LIVR-N2-001 (task install sans refus MSIX), TST-N2-001 (chemin par défaut de last_task_result dans doctor non testé) ; Info LIVR-N2-003, FIAB-N2-001, PER-N2-001 en backlog 999.7 ; rapport audits/saas-council-certification-2026-10-22.md — Choix utilisateur du 2026-10-22 au checkpoint triage
- [Phase 05.3]: Budget du superviseur compté sur recréations effectives; back-off recover min(30s,2^n), abandon après 10 échecs
- [Phase 05.3]: P-06/P-07/P-08 : message d'abandon avec chemin réel, test d'octets CR, task install refuse en MSIX
- [Phase 5.3]: AUDIT_SENIOR cycle 1 : AUDIT_POINTS.md validé (5 points) ; dev-senior (.arthemis/reports/dev-senior-1-1.md) : DS-ARCH-1 critique (résultat de mcp.call jamais transmis à n8n, contrat data à trancher P-03/P-04), majeurs DS-ARCH-2 (sender non isolé par rappel), DS-ARCH-3 (NaN/Infinity), DS-SCAL-1 (data en base non purgeable), DS-MAINT-1 (ARCHITECTURE.md = cible) ; P2 et P3 tenus, P1 et P5 avec réserves, P4 non tenu sur la doc — Audit externe du 2026-10-23 ; décision produit sur le champ data attendue de l'utilisateur avant v0.1
- [Phase 5.3]: decision-ds-1 : exposer le champ data du résultat de plugin dans le rappel n8n et dans GET /jobs/{id}, dans la limite de 1 Mio ; au-delà, repli sur un fichier artefact (comme summary.json). Ferme le contrat de DS-ARCH-1 ; correction à faire en phase insérée — Décision utilisateur du 2026-10-23 (audit senior, P-03/P-04)

### Roadmap Evolution

- Phase 05.1 inserted after Phase 5: BCF exploitable dans BIMcollab et nommage des sujets (URGENT)
- Phase 05.2 inserted after Phase 5: corrections audit council 1 : reprise du runner, chemins MCP, installation MSIX (URGENT)
- Phase 05.3 inserted after Phase 5: corrections audit council 1 passe 2 : superviseur, refus MSIX de task install, messages et test doctor (URGENT)
- Phase 05.4 inserted after Phase 5: corrections audit senior 1 : contrat data exposé (DS-ARCH-1), sender isolé par rappel (DS-ARCH-2), NaN/Infinity refusés (DS-ARCH-3), rétention de data (DS-SCAL-1), ARCHITECTURE.md livré/cible (DS-MAINT-1) (URGENT)

### Pending Todos

None yet.

### Blockers/Concerns

- Spikes de recherche : phase 1 (Job Object, host.docker.internal, bind exclusif), phase 3 (409 n8n, encodage signature), phase 4 (mcp dans Job Object, `bcf-client`, multiprocessing `ifcclash`), phase 5 (Planificateur sans élévation)
- Relecture juridique de la frontière GPL avant distribution d'un binaire

### Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 261021-e6p | Épingler astral-sh/setup-uv@v10.3.0 dans la CI | 2026-10-21 | cbe3e56 | Verified | [261021-e6p-pingler-astral-sh-setup-uv-v10-3-0-dans-](./quick/261021-e6p-pingler-astral-sh-setup-uv-v10-3-0-dans-/) |
| 261022-iea | Attendre tout l'arbre dans kill_tree des tests e2e | 2026-10-22 | b233760 | Verified | [261022-iea-attendre-tout-l-arbre-dans-kill-tree-des](./quick/261022-iea-attendre-tout-l-arbre-dans-kill-tree-des/) |

## Session Continuity

Last session: 2026-10-23T06:54:45.165Z
Stopped at: decision-ds-1 tranchée (exposer data) ; retour GSD de DS-ARCH-1 à insérer
Resume file: .arthemis/PASSATION.md

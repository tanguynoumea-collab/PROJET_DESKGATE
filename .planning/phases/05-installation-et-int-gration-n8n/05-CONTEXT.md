# Phase 5: Installation et intégration n8n - Context

**Gathered:** 2026-10-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Sur la machine cible, l'utilisateur installe Deskgate (`deskgate init`), le runner démarre à
l'ouverture de session par une tâche du Planificateur, n8n (épinglé 2.43.8 par le compose du dépôt)
déclenche un calcul `ifc.clash` long sur des maquettes réelles et reprend sur le rappel, y compris
après un arrêt brutal du runner. Exigences : INS-01..05, ACC-01, ACC-02 (plus la vérification
humaine différée 04-D1 : rendu du BCF dans BIMcollab Zoom).

Hors phase : nœud n8n communautaire, interface web, manifeste de plugins (v0.2/v0.3).

</domain>

<decisions>
## Implementation Decisions

### Accords système (B2, donnés par l'utilisateur le 2026-10-21)
- **D-01:** Créer `C:\BIM` (`depot`, `travail`, `livrables`), `%LOCALAPPDATA%\Deskgate`
  (config, base, jeton haché, environnements de plugins), et installer la tâche du Planificateur.
  Ces actions sont autorisées pour la recette sur cette machine ; `deskgate init` doit malgré tout
  demander confirmation (ou exiger `--yes`) avant de créer la tâche, pour les autres utilisateurs.

### deskgate init (INS-01, INS-02)
- **D-02:** `deskgate init` : écrit `runner.toml` depuis le gabarit commenté (sans écraser un
  fichier existant sauf `--force`), crée les dossiers, génère le jeton (affiché une seule fois,
  hash SHA-256 dans la config), propose l'installation de la tâche. Idempotent.
- **D-03:** Tâche du Planificateur générée en XML (UTF-16) puis `schtasks /Create /XML`, sans
  élévation : `LogonTrigger` utilisateur courant, `InteractiveToken`, `LeastPrivilege`,
  `ExecutionTimeLimit=PT0S`, batterie autorisée, `MultipleInstancesPolicy=IgnoreNew`,
  `RestartOnFailure` (1 min, 3 essais). Action : exécutable absolu résolu à l'installation (lanceur
  sans console si fiable, sinon `deskgate serve` avec journal fichier). `deskgate uninstall-task`
  (ou équivalent) la retire. Spike à mener en tête de phase (compte standard, fermeture/réouverture
  de session non automatisable : à vérifier en démarrant la tâche par `schtasks /Run`).
- **D-04:** `deskgate doctor` minimal : config valide, dossiers, jeton présent, tâche installée et
  ses réglages relus, port libre ou runner joignable, environnements de plugins déclarés présents.

### n8n (INS-03, INS-04, INS-05)
- **D-05:** `n8n/docker-compose.yml` : n8n **2.43.8** épinglé (digest si possible) + Postgres,
  `C:\BIM` monté sur `/data`, port publié **127.0.0.1:5679** (le n8n de l'utilisateur occupe 5678),
  `WEBHOOK_URL=http://127.0.0.1:5679/` pour que la `resumeUrl` soit joignable depuis Windows (hôte
  autorisé `127.0.0.1`). Secrets (Postgres, clé de chiffrement) dans un `.env` non versionné, avec
  `.env.example`.
- **D-06:** Workflow d'exemple importable `n8n/examples/ifc-clash.json` : déclencheur manuel →
  HTTP Request `POST http://host.docker.internal:8765/jobs` (jeton en identifiant n8n, pas en dur)
  avec `callback.url = {{$execution.resumeUrl}}` → Wait « On Webhook Call » avec « Limit Wait
  Time » → If sur `status`. Un second exemple pour `mcp.call` facultatif.
- **D-07:** Recette sur **les deux** n8n : le compose du dépôt (2.43.8, recette officielle) et le
  n8n de l'utilisateur (`pipelines-n8n`, 2.42.5, port 5678, `WEBHOOK_URL=http://127.0.0.1:5678/`) **sans
  le modifier** (import du workflow par API ou à la main, rien d'autre). Écart de version consigné.
- **D-08:** `host.docker.internal` → runner sur 127.0.0.1 : **vérifié** le 2026-10-21 (01-D1).

### Acceptation (ACC-01, ACC-02)
- **D-09:** Calcul long : `ifc.clash` mode `hard`, `ifc_a` = `PIC-EXE-AW-CVC-MNQ-BaJ-SUP-30701-IFC4.ifc`
  (532 Mo) avec `selector_a` gaines, tuyaux et accessoires (`IfcFlowSegment, IfcFlowFitting`),
  `ifc_b` = `PIC_REV_HRS_ARC_MNQ_BaJ_SUP_30400.ifc` (51 Mo) avec `selector_b` murs, dalles, poutres,
  poteaux (`IfcWall, IfcSlab, IfcBeam, IfcColumn`), `bcf: true`. Maquettes copiées depuis
  `G:\Mon Drive\07_PROJETS\DESKGATE` vers `C:\BIM\depot\`. Si le calcul dure moins de 10 min, élargir
  les sélections ou la tolérance plutôt que d'ajouter une attente artificielle.
- **D-10:** ACC-01 depuis le runner **démarré par la tâche planifiée** (pas depuis un terminal).
  ACC-02 : arrêt brutal du runner (`taskkill /F /T`) pendant un calcul, relance par
  `schtasks /Run`, n8n reçoit `interrupted`.
- **D-11:** 04-D1 : l'utilisateur ouvre le BCF produit dans BIMcollab Zoom (deux vues par sujet,
  contexte gris transparent, couleurs) — vérification humaine différable, consignée dans
  `05-HUMAN-UAT.md` ou soldée dans `04-HUMAN-UAT.md`.

### Claude's Discretion
- Découpage des plans, lanceur sans console (`gui-scripts` sous `uv tool install` ou alternative),
  forme exacte de `deskgate doctor`, import du workflow (API n8n ou procédure manuelle documentée).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `AGENTS.md` (procédure d'installation cible, §4 plugins, §5 n8n) ; `README.md`
- `ARCHITECTURE.md` §2 (démarrage, Planificateur), §9 (intégration n8n)
- `.planning/research/STACK.md` § Planificateur de tâches, § Empaquetage ; `.planning/research/PITFALLS.md` P4, P5, P6
- `.arthemis/reports/verifs-techniques-cycle-1.md` §2, §4 (n8n 2.43.8, digest)
- `.planning/phases/01-fondations-testables/01-HUMAN-UAT.md` (01-D1 réussi)
- `.planning/phases/04-capacit-s-v0-1/04-HUMAN-UAT.md` (04-D1)
- `src/deskgate/runner.example.toml`, `src/deskgate/cli.py`, `src/deskgate/locations.py`
- `.planning/REQUIREMENTS.md` — INS-01..05, ACC-01, ACC-02

</canonical_refs>

<code_context>
## Existing Code Insights

- `src/deskgate/cli.py` : Typer (`serve`, `dev-token` caché) — y ajouter `init`, `doctor`, gestion de la tâche.
- `src/deskgate/locations.py` : `%LOCALAPPDATA%\Deskgate` via platformdirs (`appauthor=False`), `DESKGATE_HOME`.
- `src/deskgate/runner.example.toml` : gabarit commenté, bloc d'exemples de la phase 4.
- `tests/e2e/conftest.py` : lancement réel du runner, faux n8n.

</code_context>

<specifics>
## Specific Ideas

- Les maquettes réelles ne sont pas versionnées ; les tests automatiques restent sur IFC synthétiques.
- Le n8n de l'utilisateur ne doit subir aucune modification de configuration.

</specifics>

<deferred>
## Deferred Ideas

- Nœud communautaire `n8n-nodes-deskgate` (v0.3).

</deferred>

---

*Phase: 05-installation-et-int-gration-n8n*
*Context gathered: 2026-10-21*

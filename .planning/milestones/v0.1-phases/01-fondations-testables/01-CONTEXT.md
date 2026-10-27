# Phase 1: Fondations testables - Context

**Gathered:** 2026-10-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Un runner `deskgate` démarre localement avec une configuration typée et valide, n'écoute que sur
127.0.0.1, n'accepte que des requêtes authentifiées (jeton Bearer haché) venant d'hôtes attendus,
refuse tout chemin hors des racines autorisées, et ne tourne qu'en une seule instance. `/health`
répond sans jeton. Exigences : RUN-01, RUN-02, RUN-03, RUN-04, SEC-01, SEC-02, SEC-03, SEC-04.

Hors phase : file de tâches, exécution, Job Object en production, rappel, audit, capacités,
`deskgate init` (phases 2 à 5). Le schéma SQLite complet (migration 1) est livré en phase 2.

</domain>

<decisions>
## Implementation Decisions

### Emplacement des données
- **D-01:** `runner.toml`, la base `deskgate.db` et les journaux du runner vivent dans
  `%LOCALAPPDATA%\Deskgate` (via `platformdirs`), jamais sous OneDrive, `Documents` ni `C:\BIM`.
  Surcharge possible par `--config <chemin>` ou la variable `DESKGATE_HOME`.

### Écoute réseau
- **D-02:** Défaut `host = "127.0.0.1"`, port `8765`. Toute autre adresse n'est acceptée que si
  `allow_non_loopback = true` dans `runner.toml` ; dans ce cas, avertissement en français au
  démarrage et champ d'avertissement dans `/health`. `0.0.0.0` n'est jamais un défaut.
- **D-03:** Le socket est créé et lié à la main avec `SO_EXCLUSIVEADDRUSE`, puis passé à
  `uvicorn.Server(config).serve(sockets=[sock])`. Rien d'important dans le `lifespan` d'Uvicorn
  (il s'exécute avant le bind).

### Instance unique
- **D-04:** Ordre de démarrage strict : mutex nommé `Local\Deskgate` (`CreateMutexW`) → socket lié
  (`SO_EXCLUSIVEADDRUSE`) → ouverture de la base → (recovery et threads en phase 2) → Uvicorn. Un
  second runner sort à l'étape du mutex, avec un message clair, sans ouvrir la base (RUN-03).

### Configuration
- **D-05:** `tomllib` + `RunnerConfig.model_validate` (Pydantic 2) ; pas de pydantic-settings.
  Une configuration invalide arrête le démarrage avec un message en français qui cite la clé
  fautive. Clés connues dès la phase 1 : `host`, `port`, `allow_non_loopback`, `token_sha256`,
  `[paths] allowed_roots`, `[[paths.mapping]] container/host`, `callback_allowed_hosts` (lu, utilisé
  en phase 3), `[capabilities.<id>]` (lu, utilisé en phase 2 ; voir STATE.md, décision phase 2).
  Inconnu → erreur (pas de clé ignorée en silence).

### Jeton
- **D-06:** Un seul jeton en v0.1. `runner.toml` ne contient que `token_sha256` (SHA-256 hex) ;
  comparaison par `hmac.compare_digest`. Le jeton en clair n'est jamais écrit ni journalisé.
  Toute route sauf `/health` exige `Authorization: Bearer <jeton>` (401 sinon).

### Contrôle Host
- **D-07:** En-tête `Host` accepté : `127.0.0.1`, `localhost`, `host.docker.internal` (avec ou sans
  port). Sinon 400 avec erreur stable. Protège contre le DNS rebinding.

### Format d'erreur
- **D-08:** Toutes les erreurs de l'API ont la forme
  `{ "error": { "code": "<code_stable_anglais>", "message": "<message en français>" } }`. Codes
  stables (ex. `unauthorized`, `host_not_allowed`, `path_outside_roots`, `invalid_config`). Les
  erreurs de validation FastAPI sont réécrites dans ce format.

### Chemins
- **D-09:** `core/paths.py` pur : conversion `/data/...` ↔ `C:/BIM/...` selon `[[paths.mapping]]`,
  contrôles lexicaux (UNC, `\\?\`, noms réservés `CON`/`NUL`/…, flux alternatifs `:`, préfixe de
  segment `C:/BIM2`, `..`), résolution des liens et jonctions par un `resolver` injecté (le vrai :
  `Path.resolve(strict=…)`). Comparaison insensible à la casse, par segments.

### Architecture et tests (issus du conseil d'approche)
- **D-10:** Noyau pur `src/deskgate/core/` (`paths`, `config`, `tokens`, `redact`, `hostcheck`,
  `errors`) ; coquille `api`, `cli`, `store` (squelette), `instance` (mutex + socket). Test AST : `core/`
  n'importe jamais `sqlite3`, `subprocess`, `httpx2`, `fastapi`, `ctypes`. Test AST de frontière
  GPL : aucun paquet hors `plugins/bim/bcf/` n'importe `bcf` ni `deskgate_bcf` (vide mais actif dès
  la phase 1).
- **D-11:** Marqueurs pytest `unit`, `fs`, `proc`, `e2e`. Tests `fs` avec vraies jonctions
  (`mklink /J`, sans admin) ; liens symboliques en `skipif` explicite si le mode développeur manque.
  CI GitHub Actions `windows-latest`.
- **D-12:** Outillage de gate (`profil.gate[]` d'ARTHEMIS) à mettre en place dans cette phase :
  `uv sync --locked`, `uv run ruff check`, `uv run ruff format --check`, `uv run pyright`,
  `uv run pytest -m "not e2e"`, `uv build --all-packages`, `uv run pytest -m e2e`. Workspace uv
  (paquet `deskgate` ; `plugins/bim` et `plugins/bim/bcf` déclarés plus tard).

### Spikes en tête de phase (réduction des risques)
- **D-13:** Avant le code : (a) `host.docker.internal` → service sur 127.0.0.1 depuis un conteneur
  jetable (Docker 29.8.2 présent) ; (b) bind `SO_EXCLUSIVEADDRUSE` : un second bind échoue ;
  (c) Job Object ctypes avec petit-enfant orphelin porté en test pytest (le module `jobobject`
  définitif est livré en phase 2). Résultats consignés dans le RESEARCH ou le SUMMARY de la phase.

### Claude's Discretion
- Commande de développement pour générer un jeton et son hash avant `deskgate init` (phase 5).
- Contenu exact de `/health` (statut, version, avertissement d'écoute ; aucun chemin, aucun secret).
- Gabarit commenté de `runner.toml` et ses valeurs par défaut.
- Découpage des plans et vagues.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Conception
- `ARCHITECTURE.md` §2 (runner), §6 (protocole), §7 (chemins), §8 (sécurité), §12 (structure du dépôt)
- `CLAUDE.md` — règles non négociables du dépôt (langue, cœur générique, sécurité, licences)
- `.arthemis/reports/llm-council-1.md` — architecture d'implémentation retenue (noyau pur, démarrage, tests)

### Recherche
- `.planning/research/SUMMARY.md` — pile, contradictions tranchées
- `.planning/research/STACK.md` — versions épinglées (FastAPI, Uvicorn, Pydantic, uv)
- `.planning/research/PITFALLS.md` — M12 (chemins), M14, P3 (deux instances)
- `.arthemis/reports/verifs-techniques-cycle-1.md` §2 (host.docker.internal), §6 (Job Object)

### Exigences
- `.planning/REQUIREMENTS.md` — RUN-01..04, SEC-01..04
- `.planning/STATE.md` — décisions accumulées (capacités dans `runner.toml`)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Aucun code : dépôt neuf (documents seulement).

### Established Patterns
- Aucun ; cette phase pose la structure (`src/deskgate/`, `tests/`, workspace uv).

### Integration Points
- `pyproject.toml` racine (workspace uv), `src/deskgate/cli.py` (`deskgate serve`), CI
  `.github/workflows/`.

</code_context>

<specifics>
## Specific Ideas

- Messages d'erreur et journaux en français ; identifiants et codes d'erreur en anglais.
- Le runner ne doit jamais écouter sur `0.0.0.0` sans l'option explicite.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-fondations-testables*
*Context gathered: 2026-10-20*

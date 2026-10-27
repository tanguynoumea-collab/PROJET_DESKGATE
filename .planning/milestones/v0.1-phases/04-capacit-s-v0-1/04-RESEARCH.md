# Phase 4 : Capacités v0.1 - Research

**Researched:** 2026-10-20 (expériences locales, Windows 11, uv 0.12.17, CPython 3.11.9)
**Domain:** IfcOpenShell (`ifcclash`) en plugin Python isolé, écriture BCF 2.1 en paquet GPL-3 appelé en sous-processus, client MCP stdio dans un Job Object, packaging uv multi-environnements, contrôle des licences
**Confidence:** HIGH sur ifcclash, bcf-client, mcp, packaging (tout exécuté localement) ; MEDIUM sur le comportement des viewers BCF (alpha ARGB) et sur Python 3.13 (non exécuté)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Organisation des paquets (rappel des décisions de cadrage)**
- **D-01:** `plugins/bim/` = paquet `deskgate-bim` (MIT, pyproject propre), module `deskgate_bim.clash:run`. `plugins/bim/bcf/` = paquet `deskgate-bcf` (GPL-3, `LICENSE` propre), CLI `deskgate-bcf` (JSON vers `.bcf`). Le cœur `src/deskgate` ne contient aucun nom BIM : `ifc.clash` est déclaré dans `runner.toml` `[capabilities."ifc.clash"]` (`kind = "python"`, `python` = interpréteur du venv du plugin, `entry = "deskgate_bim.clash:run"`).
- **D-02:** Chaque plugin a son environnement isolé (uv). `ifc.clash` appelle `deskgate-bcf` en sous-processus (descendant du Job Object), avec des fichiers JSON comme seul échange ; le chemin de l'exécutable `deskgate-bcf` est fourni par la configuration de la capacité (mécanisme de réglages par capacité à définir par la recherche, sans nom BIM dans le cœur).
- **D-03:** Test CI : aucun paquet hors `plugins/bim/bcf/` n'importe `bcf` ni `deskgate_bcf` (test AST existant à étendre aux plugins) ; `ifc.clash` n'appelle jamais l'export BCF d'`ifcclash` ; contrôle des licences par environnement et fichier `NOTICE`.

**ifc.clash**
- **D-04:** Sélecteurs `selector_a` / `selector_b` en **syntaxe sélecteur IfcOpenShell** (`ifcopenshell.util.selector`), par exemple `IfcFlowSegment` ou `IfcWall, Name=/EI.*/`. `ifc_a` obligatoire, `ifc_b` optionnel (même maquette si absent). Chemins en forme conteneur `/data/...`, convertis et validés contre les racines avec les mêmes règles que le cœur.
- **D-05:** Modes v0.1 : `hard` (intersection, tolérance de pénétration) et `clearance` (distance minimale). **Tolérance explicite en mètres.** `touch` et `duplicate` en v0.2.
- **D-06:** **Un sujet BCF = un groupe de conflits** (regroupement spatial d'`ifcclash` ou équivalent), avec les GUID de toutes les paires du groupe. JSON de sortie : groupes puis paires (GlobalId A et B, types, noms, position, distance ou pénétration), tri déterministe, plafond `max_clashes` avec drapeau `truncated`.
- **D-07:** Sélection vide : succès à 0 conflit avec avertissement (CAP-03). Erreurs classées (fichier illisible, sélecteur invalide, mémoire).
- **D-08:** BCF sur demande (`bcf: true`) : BCF 2.1, deux points de vue par sujet — (1) objets du conflit seuls, (2) contexte gris transparent —, couleurs ARGB, pas de sélection enregistrée. GUID de sujet déterministes (UUID v5 sur la signature du groupe). BCF écrit dans le `work_dir` et déclaré comme artefact.
- **D-09:** Tests sur **IFC synthétiques** générés par les tests avec l'API IfcOpenShell (mur et gaine qui le traverse, poutre à 5 cm d'un tuyau, sélection vide…), résultats connus d'avance. Les maquettes réelles de l'utilisateur servent à l'acceptation (phase 5).

**deskgate-bcf**
- **D-10:** Contrat JSON d'entrée **versionné** (`schema_version`) dans `docs/contrats/` (par exemple `bcf-write-v1.json`), dupliqué (pas importé) côté `deskgate-bim` avec un test d'égalité. Sortie : fichier `.bcf` et code de sortie ; erreurs sur stderr.

**mcp.call**
- **D-11:** Serveurs MCP déclarés dans `runner.toml` (format proche de la configuration MCP de Claude : `command`, `args`, `env`, liste d'outils autorisés). `mcp.call` reçoit `{server, tool, arguments}` et refuse tout serveur ou outil non déclaré (aucune commande libre). Exécution par un worker Python dans le Job Object ; le serveur stdio est son descendant et meurt avec la tâche. SDK `mcp >=2.3,<3` (API 2.x). Résultat : contenu structuré ou texte de l'outil ; `is_error` donne une tâche `failed`.
- **D-12:** Tests avec un **mini-serveur MCP de test** dans `tests/` (outils `echo`, `sleep`, `erreur`, `spawn_orphan`) pour prouver l'appel, le délai et l'arrêt de l'arbre.

### Claude's Discretion
- Nom exact des clés de réglages par capacité, structure des dossiers des plugins, outillage de création des venv de plugins pour les tests, découpage des plans.

### Deferred Ideas (OUT OF SCOPE)
- Modes `touch` et `duplicate`, BCF 3.0, lecture BCF, plugins `bcf.write` / `bcf.read` — v0.2.
- Hors phase : manifeste `plugin.yaml`, `deskgate plugin add`, exécuteur `cli`, `deskgate init`, docker-compose, acceptation sur maquettes réelles (phase 5).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAP-01 | `ifc.clash` détecte les conflits en modes `hard` et `clearance` (tolérance explicite), regroupe, JSON avec GlobalId par paire | §ifc.clash : API ifcclash vérifiée (sémantique tolérance en mètres, types `protrusion`/`pierce`/`clearance`), sous-classe `Clasher`, regroupement maison déterministe, orientation a/b à normaliser, tri |
| CAP-02 | `ifc.clash` produit sur demande un BCF 2.1, deux points de vue par sujet, couleurs ARGB, sans sélection enregistrée | §deskgate-bcf : code complet vérifié (visibilité par défaut masquée + exceptions, coloring ARGB, caméra perspective/orthogonale, GUID v5), contrat JSON v1 |
| CAP-03 | Sélection vide = succès à 0 conflit avec avertissement | `Clasher` d'origine plante sur sélection vide (`TypeError` / `AssertionError`) : pré-résoudre les sélecteurs et court-circuiter |
| CAP-04 | `mcp.call` appelle un outil MCP stdio déclaré, sans LLM, dans le Job Object | §mcp.call : serveur mini + worker exécutés dans l'Engine réel ; arbre tué au délai, à l'annulation, en sortie normale ; forme du résultat ; `ExceptionGroup` à aplatir |
| CAP-05 | `deskgate-bcf` (GPL-3) écrit un BCF 2.1 depuis un JSON versionné, en sous-processus ; aucun autre paquet n'importe `bcf-client`/`deskgate-bcf` (test) | §Packaging (workspace uv, envs séparés), §Licences (sonde par environnement), sdist de `deskgate-bim` qui embarque `bcf/` par défaut : à exclure |
</phase_requirements>

## Summary

Tout ce qui est annoncé a été exécuté localement (venvs Python 3.11 dans le scratchpad, aucune écriture dans le dépôt). Le résultat tient en six faits qui changent le plan. (1) `ifcclash` 0.9.0 ne dépend **pas** de `bcf-client` (seule dépendance dure : `ifcopenshell` ; `scikit-learn` est dans l'extra `advanced`) et n'importe `bcf` que dans `export_bcfxml()` : l'environnement `deskgate-bim` ne contient donc aucun paquet GPL, et `import ifcclash` ne charge ni `bcf`, ni `sklearn`, ni `xsdata`. (2) Le `Clasher` d'origine est fragile pour notre usage : sélection vide = `TypeError` du C++, éléments sans géométrie = `AssertionError`, `num_threads` figé à `multiprocessing.cpu_count()`, aucun rappel de progression, ordre des résultats non déterministe d'une exécution à l'autre, et a/b non alignés sur les sélections A/B. Il faut une **sous-classe fine** (≈ 40 lignes) qui pré-résout les sélecteurs, règle les threads et alimente `ctx.progress`, puis normalise, trie et regroupe. (3) Le regroupement spatial d'ifcclash exige scikit-learn/scipy (+ ~60 Mo) et chaîne facilement : un regroupement « leader » par rayon, écrit en 15 lignes, est déterministe et suffisant. (4) `bcf-client` 0.9.0 (GPL-3, classifier encore GPLv3 sur PyPI) permet un BCF 2.1 complet avec les modèles xsdata ; le GUID de sujet déterministe exige de remplacer `topic.guid` **et** l'attribut privé `_topic_dir` ; les octets du zip varient (horodatages d'entrée) mais le contenu des membres est identique. (5) Le SDK `mcp` 2.3 fonctionne tel quel dans notre Job Object : le serveur est créé sans breakaway, puis le SDK l'assigne à son propre Job imbriqué ; l'arbre complet (serveur + petit-enfant) meurt au délai, à l'annulation et en sortie normale. (6) Piège majeur découvert : avec `memory_mb` posé, `import numpy` échoue (« OpenBLAS: Memory allocation still failed ») sur une machine à 24 cœurs tant que `OPENBLAS_NUM_THREADS=1` n'est pas posé **avant** l'import ; et un dépassement réel du plafond tue le processus par violation d'accès `0xC0000005` sans `result.json` : la classification « mémoire » doit se faire dans l'engine par `PeakJobMemoryUsed`, pas dans le plugin.

Côté cœur, deux manques génériques sont à combler, sans nom BIM : un mécanisme de **réglages par capacité** (`settings` → `input.json` → `ctx.settings`) et la **conversion des chemins** (le runner ne convertit aujourd'hui aucun paramètre : `validate_container_path` existe mais n'est appelé nulle part, alors que `ARCHITECTURE.md` §4 promet des chemins « déjà convertis »). Recommandation : `path_params` déclaré par capacité dans `runner.toml`, converti et validé par le runner (une seule source de vérité), jamais de fonction dupliquée dans le SDK.

**Primary recommendation:** Workspace uv (`plugins/bim`, `plugins/bim/bcf` membres) avec un environnement par paquet créé par `uv sync --locked --package X --no-dev` ; `ifc.clash` = sous-classe de `ifcclash.Clasher` + regroupement maison + appel de `deskgate-bcf.exe` ; `mcp.call` = nouveau `kind = "mcp"` générique dont le worker (`deskgate.workers.mcp_call`) tourne dans l'interpréteur du runner ; ajouter au cœur `settings`, `path_params`, `mcp_servers` et la classification `memory_limit` par pic mémoire du Job.

## Project Constraints (from CLAUDE.md)

- Français partout (documents, messages, journaux, commits) ; identifiants de code, routes, champs JSON en anglais.
- Règle 1 : `src/deskgate/` n'importe jamais `deskgate_bim` ni IfcOpenShell ; aucun nom BIM dans le cœur (les clés `selector_a`, `bcf_executable`, etc. n'existent que dans `plugins/` et `runner.toml`).
- Règle 2 : pas de `shell=True`, pas de commande construite par concaténation. Les commandes MCP viennent uniquement de `runner.toml` ; `mcp.call` refuse tout serveur/outil non déclaré.
- Règle 3 : un plugin ne tourne jamais dans le runner ; Job Object créé suspendu, assigné, repris ; breakaway interdit. Le sous-processus `deskgate-bcf` et le serveur MCP sont des descendants du Job.
- Règle 4 : tout chemin reçu converti puis validé contre `allowed_roots` (`..`, liens, jonctions).
- Règle 6 : secrets jamais dans manifestes, journaux, audit (voir pitfall `input.json` lisible par n8n via `/data`).
- Règle 7 : rappel ≤ 1 Mio ; gros résultats en fichiers artefacts. `result.json` est plafonné à 1 048 576 octets (`RESULT_MAX_BYTES`) : au-delà la tâche échoue `result_too_large`.
- Règle 8 : déterminisme (tri, GUID v5, horodatage injectable).
- Règles 9 et 10 : MIT partout, sauf `plugins/bim/bcf/` (GPL-3) ; seul ce paquet importe `bcf-client` ; l'export BCF d'`ifcclash` n'est jamais appelé depuis `deskgate-bim`.
- Tests : `pytest` ; vrais sous-processus Windows ; plugins BIM avec leurs propres tests dans `plugins/bim/tests/` sur petits IFC ; marqueurs existants `unit`, `fs`, `proc`, `e2e`.
- Commits `type(scope): sujet` ≤ 72 car. en français ; `.arthemis/**` jamais mêlé au code ni à `.planning/`.
- Skill `gsd-file-manuelle` : les interventions humaines sont classées au plan. Cette phase n'en a pas de nécessaire (tout est automatisable) ; la seule vérification subjective (rendu des couleurs/transparence dans un viewer BCF réel) est **différable** (verdict pass/issue sur un comportement déjà construit) et relève de la phase 5 avec les maquettes réelles.
- Règle utilisateur de session : jamais `uv python install`, jamais d'installation globale (les tests de plugin utilisent `UV_PYTHON_DOWNLOADS=never` et `--python <interpréteur courant>`).

## Standard Stack

Versions vérifiées sur PyPI le 2026-10-20 (`curl pypi.org/pypi/<nom>/json`) et installées dans les venvs d'essai.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| ifcopenshell | `==0.9.0.post1` | Lecture IFC, sélecteur, géométrie, arbre BVH de collision | Imposé ; wheels Windows 3.10 à 3.15 ; LGPL-3 utilisée comme bibliothèque |
| ifcclash | `==0.9.0` | `Clasher` (détection `intersection` / `clearance`) | Imposé par D-01 ; LGPL ; dépend seulement d'`ifcopenshell` (+ `numpy`, `shapely`, `lark` transitifs) ; **aucun `bcf-client`** |
| bcf-client | `==0.9.0` (GPL-3) | Écriture BCF 2.1 dans `deskgate-bcf` uniquement | Seule bibliothèque BCF de l'écosystème ; dépend de `xsdata`, `numpy`, `ifcopenshell`, `requests` |
| mcp | `>=2.3,<3` (2.3.0, 2026-10-02) | Client MCP stdio dans le worker `mcp.call` | Imposé ; résolution propre avec le lock du cœur (vérifié : ajoute `cryptography`, `pywin32`, `jsonschema`, `sse-starlette`… au lock du runner) |
| jsonschema | `>=4,<5` | Validation du contrat `bcf-write-v1` côté `deskgate-bcf` | MIT ; déjà tiré par `mcp` ; le JSON Schema est le contrat (pas un module Python partagé) |
| pydantic | `>=2.14,<3` | Validation des paramètres d'`ifc.clash` dans le venv du plugin | Déjà la pile du projet ; **non présent** dans le venv de plugin par défaut (vérifié) : à déclarer comme dépendance de `deskgate-bim` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| psutil | 7.2.2 | Vérifier la mort des PID dans les tests (déjà en dev) | Tests `proc` de `mcp.call` et du sous-processus bcf |
| uv | 0.12.17 locale (0.13.3 publié) | Création des venvs de plugins en tests/CI | Fixture de session `plugin_envs` |
| pytest | 9.1.x | Dans l'env `deskgate-bim` (groupe `dev` du plugin) pour `plugins/bim/tests/` | Tests du plugin dans son propre venv |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Regroupement maison (leader par rayon) | `Clasher.smart_group_clashes` (OPTICS) | Exige `scikit-learn` + `scipy` (+ ~60 Mo, 174 Mo de venv déjà), résultat dépendant de `min_samples`/`xi`, retire les clashes `-1` en groupes singletons. Rejeté : lourd et moins prévisible |
| Sous-classe de `Clasher` | Boucle maison sur `ifcopenshell.geom.tree` | Plus de liberté mais on perd la raison d'être d'`ifcclash` (D-01). La sous-classe ne réécrit que `add_collision_objects` et `process_clash_set` |
| Workspace uv | Deux projets uv indépendants (chacun son `uv.lock`) | Vérifié : les deux marchent. Le workspace garde un seul `uv.lock` et `uv build --all-packages` déjà en CI ; le risque (co-installation par `uv sync --all-packages`) est neutralisé par un test (voir Packaging) |
| `deskgate-bcf.exe` (D-02) | `<python du venv bcf> -m deskgate_bcf` | `.exe` = lanceur uv qui démarre `python.exe` en enfant (vérifié : fonctionne dans le Job avec l'environnement en liste blanche). `-m` évite un processus intermédiaire mais change la forme du réglage ; garder l'exécutable (D-02) |

**Installation (plugin, dans son environnement uv) :**
```bash
# environnements de plugins (jamais dans l'env de dev) :
UV_PROJECT_ENVIRONMENT=<cache>/bim uv sync --locked --package deskgate-bim --no-dev --python <interpréteur>
UV_PROJECT_ENVIRONMENT=<cache>/bcf uv sync --locked --package deskgate-bcf --no-dev --python <interpréteur>
# cœur : ajouter au pyproject racine
#   dependencies += ["mcp>=2.3,<3"]
```

**Version verification:** ifcclash 0.9.0, bcf-client 0.9.0 (dernier ; classifier PyPI toujours « GPLv3 », aucune version corrigée publiée au 2026-10-20 : le point « LGPL attendu » du STACK reste ouvert), ifcopenshell 0.9.0.post1, mcp 2.3.0.

## Architecture Patterns

### Recommended Project Structure
```
pyproject.toml                       # [tool.uv.workspace] members = ["plugins/bim", "plugins/bim/bcf"]
uv.lock                              # unique, couvre les trois paquets
docs/contrats/bcf-write-v1.json      # JSON Schema = source de vérité du contrat (D-10)
src/deskgate/
├── core/config.py                   # + Capability.settings/path_params/env ; kind "mcp" ; RunnerConfig.mcp_servers
├── core/worker_protocol.py          # + WorkerInput.settings ; CONTRACT.input_keys mis à jour
├── engine.py                        # conversion path_params ; settings ; kind mcp ; classification memory_limit
├── jobobject.py                     # + peak_memory() (PeakJobMemoryUsed)
└── workers/mcp_call.py              # run(params, ctx) : seul module (avec tests) qui importe `mcp`
src/deskgate_sdk/run.py              # + ctx.settings (stdlib seule)
plugins/bim/                         # deskgate-bim (MIT)
├── pyproject.toml                   # deps : ifcopenshell==0.9.0.post1, ifcclash==0.9.0, pydantic ; sdist exclude = ["bcf"]
├── src/deskgate_bim/{__init__,clash,grouping,params,bcfjob}.py
├── src/deskgate_bim/contracts/bcf-write-v1.json    # COPIE du contrat (test d'égalité)
└── tests/                           # tests du plugin, exécutés dans son venv (pytest en groupe dev)
plugins/bim/bcf/                     # deskgate-bcf (GPL-3-or-later)
├── LICENSE  NOTICE  pyproject.toml  # deps : bcf-client==0.9.0, ifcopenshell==0.9.0.post1, jsonschema
├── src/deskgate_bcf/{__init__,cli,writer}.py
├── src/deskgate_bcf/schemas/bcf-write-v1.json      # COPIE du contrat
└── tests/
tests/
├── plugins/conftest.py              # fixture de session plugin_envs (uv) ; marqueur `bim`
├── plugins/test_licenses.py  test_contract_equality.py  test_sdist_exclusion.py
├── mcp_fake/mini_server.py          # serveur MCP de test (D-12)
└── proc/test_mcp_call.py  test_ifc_clash_e2e.py
```

### Pattern 1 : réglages et chemins génériques par capacité (cœur sans nom BIM)
**What:** `runner.toml` déclare tout ce qui est propre à un plugin ; le cœur transporte sans interpréter.
```toml
[capabilities."ifc.clash"]
kind = "python"
python = 'C:/Users/me/AppData/Local/Deskgate/plugins/bim/Scripts/python.exe'
entry = "deskgate_bim.clash:run"
timeout_max = 14400
memory_mb = 8192
resource = "cpu-heavy"
path_params = ["ifc_a", "ifc_b"]            # clés de params à convertir /data/... -> C:/BIM/... (str ou list[str])
[capabilities."ifc.clash".settings]          # table libre, non secrète, lue par le plugin via ctx.settings
bcf_executable = 'C:/Users/me/AppData/Local/Deskgate/plugins/bcf/Scripts/deskgate-bcf.exe'
threads = 4

[mcp_servers.demo]                           # format proche de la config MCP de Claude
command = 'C:/Python311/python.exe'
args = ['C:/outils/serveur.py']
env = { LANG = "fr" }
allowed_tools = ["echo", "add"]              # liste vide ou absente = aucun outil autorisé

[capabilities."mcp.call"]
kind = "mcp"                                 # exécuteur intégré : pas de python/entry
timeout_max = 600
```
**Implémentation minimale :**
- `Capability` : `kind: Literal["python","mcp"]` ; `python`/`entry` obligatoires si `python`, interdits si `mcp` (`model_validator`) ; `settings: dict[str, str|int|float|bool|list[str|int|float|bool]] = {}` ; `path_params: list[str] = []`. `RunnerConfig.mcp_servers: dict[str, McpServer]` (`command`, `args`, `env`, `allowed_tools`, validations françaises de la même forme que le reste du fichier).
- `WorkerInput` gagne `settings: dict[str, Any]` ; **mettre à jour `CONTRACT["input_keys"]` des deux côtés** (`worker_protocol.py` et `deskgate_sdk/run.py`, le test `test_sdk_contract` l'exige). `Ctx.settings = inp.get("settings", {})`.
- Conversion des chemins : dans `Engine._launch_inner`, avant l'écriture d'`input.json`, pour chaque clé de `cap.path_params` présente dans `params` : `validate_container_path(valeur, config.mappings(), config.paths.allowed_roots, self._resolver)` (déjà écrit et testé en phase 1, SEC-03/SEC-04) ; `input.json` reçoit les chemins hôte (`C:/BIM/...`), la base garde les chemins d'origine. En complément, valider aussi à la soumission (`JobsService.submit`) pour un refus 422 immédiat `path_outside_roots` / `path_invalid` avec audit de refus ; revalider au lancement (la jonction a pu changer). Aucune fonction de conversion dupliquée dans le SDK ni les plugins : un seul code, une seule source de vérité.
- Artefacts : le plugin déclare des chemins hôte dans `work_dir` ; l'engine les revalide et les convertit déjà (`_artifact_host_path`, `host_to_container`).

### Pattern 2 : `ifc.clash` = sous-classe de `Clasher` + post-traitement pur
Flux : valider `params` (Pydantic) → pré-résoudre les sélecteurs (`ifcopenshell.util.selector.filter_elements`) → si l'un des deux ensembles est vide : succès à 0 conflit + avertissement → géométrie (threads réglés, progression 0-90 %) → `clash_*_many` → normaliser a/b, trier, regrouper → `data` + artefact `clashes.json` → si `bcf: true`, écrire le JSON de contrat, appeler `deskgate-bcf` → artefact `.bcf`.

Paramètres de la capacité (anglais, noms laissés à la discrétion de l'implémenteur, proposition) : `ifc_a` (obligatoire), `ifc_b`, `selector_a`, `selector_b`, `mode` (`hard`|`clearance`), `tolerance` (m, ≥ 0, `hard`), `clearance` (m, > 0, `clearance`), `group_radius` (m, défaut 2.0 ; 0 = pas de regroupement), `max_clashes` (défaut 1000), `threads` (défaut `min(4, cpu_count)`), `bcf` (bool), `bcf_author`, `created_at` (ISO UTC, injection pour déterminisme ; défaut maintenant), `context_radius` (m, défaut 5.0), `max_context` (défaut 500).

### Pattern 3 : `deskgate-bcf` = CLI minuscule, contrat JSON versionné
`deskgate-bcf write --input in.json --output out.bcf` ; codes de sortie : 0 ok, 2 entrée invalide (JSON illisible, `schema_version` inconnue, schéma non respecté), 3 échec d'écriture ; messages en français sur stderr, jamais sur stdout. Le CLI valide avec `jsonschema` contre sa copie du schéma. Le plugin MIT lit le code de sortie et stderr, rien d'autre.

### Pattern 4 : `mcp.call` = exécuteur intégré, worker dans l'interpréteur du runner
Pour `kind = "mcp"`, l'engine lance `[sys.executable, "-X", "utf8", "-P", "-m", "deskgate.workers.mcp_call", "--input", <input.json>]`, dans le Job Object comme tout worker, avec `settings = {"servers": {...}}` construit depuis `mcp_servers` **sans les valeurs d'`env`** (voir pitfall secrets) ; les valeurs d'`env` voyagent par l'environnement du worker (`DESKGATE_MCPENV__<serveur>__<NOM>`), jamais sur disque. Variante plus simple acceptable si le planificateur la préfère : `kind = "python"` avec `python = <interpréteur du runner>` et `entry = "deskgate.workers.mcp_call:run"` + `settings.servers` (le contrat « worker Python dans le Job » de D-11 est respecté dans les deux cas) ; elle expose en revanche les `env` dans `input.json`.

### Anti-Patterns to Avoid
- **Appeler `Clasher.clash()` tel quel** : plante sur sélection vide/sans géométrie, sature les cœurs, ordre non déterministe.
- **Appeler `Clasher.export()` / `export_bcfxml`** : importe `bcf-client` dans le processus MIT (D-03, règle 10).
- **`bcf-client` ou `deskgate-bcf` en dépendance de `deskgate-bim`** (M30.1) ou `uv sync --all-packages` dans l'environnement de dev.
- **Importer un modèle Pydantic partagé** entre `deskgate-bim` et `deskgate-bcf` : le contrat est un fichier JSON Schema, copié et comparé par test.
- **Lever une exception dans le corps de `async with Client(...)`** : le SDK l'enveloppe dans des `ExceptionGroup` imbriqués ; intercepter `MCPError` **dans** le corps.
- **Résoudre `deskgate-bcf` par le `PATH`** (STACK) : chemin absolu fourni par `settings.bcf_executable`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Détection de collisions IFC | Intersection de maillages | `ifcopenshell.geom.tree` via `ifcclash.Clasher` | BVH OpenCASCADE, tolérances, types `protrusion`/`pierce`/`clearance` |
| Syntaxe de sélection | Parseur de filtres | `ifcopenshell.util.selector.filter_elements` | `IfcWall, Name=/EI.*/`, unions `IfcWall, IfcBeam`, sous-types (`IfcFlowSegment` couvre gaines et tuyaux) |
| Écriture BCF 2.1 | ZIP + XML à la main | `bcf-client` (`BcfXml`, `bcf.v2.model`) dans `deskgate-bcf` | Sérialisation xsdata conforme au schéma, relecture par `BcfXml.load` |
| Conversion et validation de chemins | Fonction dans le SDK/plugin | `deskgate.core.paths.validate_container_path` appelée par le runner | Une source de vérité ; `..`, jonctions, UNC, noms réservés déjà testés |
| Client MCP stdio | Sous-processus + JSON-RPC à la main | `mcp.Client` + `StdioServerParameters` | Négociation de protocole (`mode="auto"` : serveurs 1.30 joignables, vérifié), arrêt du serveur |
| Arbre de processus | `psutil.children()` | Job Object du runner (déjà là) | Vérifié : tue serveur MCP et petit-enfant, y compris sous le Job imbriqué du SDK |
| Validation du contrat JSON | `if`/`in` éparpillés | `jsonschema` sur `bcf-write-v1.json` | Erreurs lisibles, version portée par le schéma |
| Licences des dépendances | Liste codée en dur | Sonde `importlib.metadata` exécutée dans l'env (`python -I`) | Reflète l'environnement réellement installé |

**Key insight:** la valeur du plugin est dans l'orchestration déterministe autour de bibliothèques existantes (normalisation, tri, regroupement, GUID v5) ; tout le reste est déjà écrit. Le piège inverse est d'écrire du code « malin » dans le cœur : chaque ajout du cœur doit rester une table de configuration générique.

## Runtime State Inventory

> Phase de création de capacités (pas de renommage ni de migration) : section omise. Seules créations : fichiers de plugins, tables de `runner.toml`, aucune donnée existante à migrer (aucun utilisateur, aucune capacité BIM existante).

## Common Pitfalls

### Pitfall 1 : `import numpy` échoue sous plafond mémoire (OpenBLAS) — vérifié
**What goes wrong:** avec `memory_mb` posé (Job `JOB_MEMORY`), le plugin sort en code 1 avec « OpenBLAS error: Memory allocation still failed after 10 retries » dès l'import de numpy (testé à 400, 200 et 140 Mo sur 24 cœurs).
**Why:** OpenBLAS réserve des tampons par thread au chargement ; ils comptent dans la mémoire engagée du Job.
**How to avoid:** `deskgate_bim/__init__.py` pose `os.environ.setdefault("OPENBLAS_NUM_THREADS","1")` et `OMP_NUM_THREADS`, `NUMEXPR_NUM_THREADS` **avant tout import** de numpy/ifcopenshell (le SDK importe `deskgate_bim.clash`, donc l'`__init__` passe d'abord). Avec cette protection : succès à 180 Mo sur 1800 éléments. Option générique (non indispensable) : table `env` par capacité fusionnée par `build_env(base, extra)` (le paramètre `extra` existe déjà).
**Warning signs:** `job.log` contenant « OpenBLAS error », sortie `nonzero_exit` code 1 sans `result.json`.

### Pitfall 2 : dépassement réel du plafond = violation d'accès, pas `MemoryError` — vérifié
**What goes wrong:** sur 9 800 éléments avec 100 ou 140 Mo, le processus meurt avec le code `3221225477` (0xC0000005) ; aucun `result.json`, `job.log` vide ; l'engine répond `nonzero_exit` sans cause.
**How to avoid:** classifier côté engine : avant de fermer le Job, lire `PeakJobMemoryUsed` (`QueryInformationJobObject` classe 9, structure `JOBOBJECT_EXTENDED_LIMIT_INFORMATION` déjà définie dans `jobobject.py`). Vérifié : limite 100 Mo -> pic 105,1 Mo et code 0xC0000005 ; limite 2000 Mo -> pic 168 Mo, code 0. Règle proposée : sortie non nulle, aucun résultat valide, `memory_mb` posé et `pic >= 0,95 × limite` -> `error_code = "memory_limit"`, message français (« plafond mémoire atteint (X Mo), augmentez memory_mb ou réduisez la sélection »). Ajouter `peak_memory()` à `JobHandle`/`JobLike` (les faux de test `FakeJob` en ont besoin). Le plugin gère en plus `MemoryError` Python (`error.type = "memory"`).
**Warning signs:** code de sortie `0xC0000005`/`0xC0000017` avec `memory_mb` configuré.

### Pitfall 3 : sélection vide ou sans géométrie plante ifcclash — vérifié
`TypeError: Attribute of type AGGREGATE OF STRING needs a python sequence` (sélection vide, `include=set()`), `AssertionError` (`iterator.initialize()` faux quand aucun élément sélectionné n'a de `Representation`). **Éviter :** pré-résoudre, filtrer `Representation is not None`, compter, avertir (`warnings: ["selection_a_empty"]`), ne jamais appeler le moteur. Une classe IFC inconnue (`IfcNotAClass`) ne lève pas : ensemble vide, donc même avertissement (le message doit citer le sélecteur et le nombre d'éléments trouvés).

### Pitfall 4 : orientation a/b et ordre non déterministes — vérifié
Les clashes sortent avec `a` = parfois l'élément de la sélection B (0 sur 900 alignés sur A dans notre test ; avec `check_all=False` l'orientation varie d'une paire à l'autre), et l'ordre du dictionnaire change d'une exécution à l'autre. **Éviter :** normaliser (si `b_global_id` ∈ sélection A et `a_global_id` ∉ A : échanger ids/classes/noms ; auto-clash sans `ifc_b` : ordre lexicographique des GlobalId), trier par `(a_global_id, b_global_id)`, **toujours `check_all=True`** (avec `False` ifcclash peut omettre des paires).

### Pitfall 5 : unités et sémantique des tolérances — vérifié
La géométrie est convertie en **mètres** quel que soit l'unité du fichier (modèle en millimètres testé : `tolerance=0.0005` détecte une pénétration de 1 mm, `0.002` non ; `clearance=0.10` détecte 5 cm, `0.03` non). En mode `hard`, `distance` = profondeur de pénétration (`protrusion` : 0,001 ; `pierce` : 0,2 = traversée de l'épaisseur du mur). En mode `clearance`, les éléments qui se touchent ou se chevauchent sortent aussi, avec `distance = 0.0` et `type = "clearance"`. **Documenter dans l'aide du paramètre** ; le JSON porte `unit: "m"`.

### Pitfall 6 : `result.json` > 1 Mio fait échouer la tâche
`RESULT_MAX_BYTES = 1_048_576` ; l'engine plafonne seulement le `summary` (renvoi dans `summary.json`), **pas** `data`. 4 900 clashes = plusieurs centaines de Ko. **Éviter :** `max_clashes` par défaut 1000, mesurer la taille sérialisée et tronquer (`truncated: true`) avant d'écrire ; écrire en plus l'artefact complet `clashes.json` (borné par `max_clashes`). `summary` : compteurs, avertissements, `truncated`, version d'IfcOpenShell, tolérance, mode.

### Pitfall 7 : GUID de sujet déterministe = deux attributs à remplacer — vérifié
`TopicHandler.create_new` tire un `uuid4` et fixe `_topic_dir = Path(guid)`. Changer seulement `topic.guid` écrit le sujet dans l'ancien dossier ZIP. **Faire :** retirer l'entrée de `bcf.topics`, poser `th.topic.guid`, `th._topic_dir = Path(guid)`, réinsérer. Les `Viewpoints.Guid` (uuid4 par défaut) sont fabriqués par nous (`uuid5(topic_guid, "viewpoint-1-only")`), et `creation_date` vient du JSON. Le zip lui-même n'est pas reproductible octet par octet (horodatages d'entrée via `ZipFile.writestr`) : tester l'égalité **membre par membre**, pas l'égalité du fichier.

### Pitfall 8 : `ExceptionGroup` imbriqués du client MCP — vérifié
Une `MCPError` levée dans `async with Client(...)` ressort en `ExceptionGroup(ExceptionGroup(MCPError))`. **Faire :** `try/except MCPError` **dans le corps** autour de `call_tool`, et pour l'échec de connexion un `except BaseException` qui aplatit (`_leaves`). Observé : commande absente = `FileNotFoundError` ; serveur qui sort immédiatement = `MCPError: Connection closed` ; stdout pollué = `MCPError: Request 'initialize' timed out` (donc **toujours** poser `read_timeout_seconds`, sinon attente jusqu'au délai de la tâche).

### Pitfall 9 : secrets MCP dans `input.json`
`input.json` est écrit dans `work_dir`, sous `C:/BIM/travail/` : dossier **monté dans n8n** (`/data`). Les valeurs d'`env` d'un serveur MCP (jetons d'API) y seraient lisibles par n'importe quel workflow. **Faire :** n'y mettre que `command`, `args`, `allowed_tools` ; passer les valeurs d'`env` par l'environnement du worker (mémoire uniquement). Le serveur ne reçoit que `get_default_environment() | env` : `DESKGATE_*` n'est jamais transmis (vérifié : `DESKGATE_SECRET` absent chez le serveur, `SYSTEMROOT` présent).

### Pitfall 10 : sdist de `deskgate-bim` embarque `bcf/` (GPL) — vérifié
`plugins/bim/bcf/` étant un sous-dossier du projet `plugins/bim`, `uv build --sdist` y a mis `bcf/pyproject.toml`, `bcf/src/deskgate_bcf/*.py`. **Faire :** `[tool.hatch.build.targets.sdist] exclude = ["bcf"]` dans `plugins/bim/pyproject.toml` + test qui ouvre le sdist construit et refuse tout membre contenant `bcf/`. Symétrique : `LICENSE` GPL-3 et `NOTICE` dans le sdist/wheel de `deskgate-bcf`, `license = "GPL-3.0-or-later"`, SPDX en tête de chaque fichier.

### Pitfall 11 : `uv sync --all-packages` en dev co-installe le GPL
En workspace, `uv sync` par défaut n'installe **que** le paquet racine (vérifié : ni `ifcopenshell` ni `bcf-client` dans l'env de dev). `--all-packages` les installerait ensemble. **Faire :** test de licences sur l'env de dev (aucun GPL/AGPL), consigne dans `AGENTS.md`/README, CI inchangée (`uv sync --locked`).

### Pitfall 12 : `uv` hors de l'environnement attendu
Le test qui construit les venvs ne doit jamais télécharger d'interpréteur : `UV_PYTHON_DOWNLOADS=never`, `--python <sys._base_executable ou l'interpréteur du venv de dev>` (vérifié : un `--python` pointant sur un venv est résolu vers sa base). Sans `uv` dans le `PATH` : `pytest.skip`/`pytest.fail` explicite (CI : `setup-uv` le fournit).

### Pitfall 13 : synthèse d'IFC coûteuse
Créer un élément avec l'API coûte ~7 ms : 9 800 éléments = 70 s. Les tests fonctionnels n'ont besoin que de 5 à 30 éléments (≤ 0,2 s). Une scène de perf (~1 800 éléments) reste hors CI (`slow`, optionnel).

### Pitfall 14 : coordonnées BCF
Les positions `p1/p2` d'ifcclash sont en mètres, repère monde IFC ; BCF attend des mètres. Une maquette géoréférencée (grandes coordonnées, `IfcMapConversion`) donnera des caméras très éloignées de l'origine mais cohérentes avec le modèle. À valider sur maquette réelle (phase 5), noté en question ouverte.

## Code Examples

Code exécuté dans les expériences (scratchpad `p4/`), à reprendre tel quel comme point de départ.

### IFC synthétique pour les tests (API ifcopenshell, `unit="MILLIMETRE"` inclus)
```python
# Source : scratchpad p4/synth.py (exécuté). L'API attend des METRES et convertit vers l'unité du projet :
# ne PAS pré-multiplier les coordonnées pour un modèle en millimètres (sinon scène x1000).
import ifcopenshell, ifcopenshell.api

def new_model(unit="METRE"):
    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    proj = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="P")
    if unit == "MILLIMETRE":
        u = ifcopenshell.api.run("unit.add_si_unit", f, unit_type="LENGTHUNIT", prefix="MILLI")
        ifcopenshell.api.run("unit.assign_unit", f, units=[u])
    else:
        ifcopenshell.api.run("unit.assign_unit", f)
    ctx = ifcopenshell.api.run("context.add_context", f, context_type="Model")
    body = ifcopenshell.api.run("context.add_context", f, context_type="Model",
        context_identifier="Body", target_view="MODEL_VIEW", parent=ctx)
    site = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcSite", name="S")
    bld = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuilding", name="B")
    st = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="L0")
    for child, parent in ((site, proj), (bld, site), (st, bld)):
        ifcopenshell.api.run("aggregate.assign_object", f, products=[child], relating_object=parent)
    return f, body, st

def box(f, body, st, cls, name, origin, size):          # origin = coin min, size = (dx, dy, dz) en mètres
    x, y, z = origin; dx, dy, dz = size
    v = [(x,y,z),(x+dx,y,z),(x+dx,y+dy,z),(x,y+dy,z),(x,y,z+dz),(x+dx,y,z+dz),(x+dx,y+dy,z+dz),(x,y+dy,z+dz)]
    faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    el = ifcopenshell.api.run("root.create_entity", f, ifc_class=cls, name=name)
    rep = ifcopenshell.api.run("geometry.add_mesh_representation", f, context=body, vertices=[v], faces=[faces])
    ifcopenshell.api.run("geometry.assign_representation", f, product=el, representation=rep)
    ifcopenshell.api.run("spatial.assign_container", f, products=[el], relating_structure=st)
    return el
```
**Scènes et résultats attendus (tous vérifiés) :**
| Scène | Sélecteurs / mode | Attendu |
|---|---|---|
| mur `(0,0,0)+(4,0.2,3)`, gaine `(1,-1,1)+(0.3,2,0.3)` | `IfcWall` / `IfcDuctSegment`, `hard`, tol 0.002 | 1 clash `pierce`, distance 0.2 |
| gaine enfoncée de 1 mm (`y=0.199`) | `hard`, tol 0.0005 / 0.002 | 1 clash `protrusion` 0.001 / 0 clash |
| poutre `(10,0,0.15)+(2,0.1,0.1)` et tuyau `(10,0,0)+(2,0.1,0.1)` (5 cm) | `IfcBeam` / `IfcPipeSegment`, `clearance` 0.10 / 0.03 | 1 clash `clearance` distance 0.05 / 0 clash ; position `p1=[12,0.1,0.15]`, `p2=[12,0.1,0.1]` |
| même poutre/tuyau, `hard` | tol 0.002 | 0 clash |
| objet disjoint `(30,30,30)` | quelconque | jamais dans les résultats |
| aucun `IfcSlab` | `IfcSlab` / `IfcPipeSegment` | 0 conflit + avertissement `selection_a_empty` |
| 5 gaines traversant un mur de 10 m (`x=i*2+0.5`) | `hard` | 5 clashes ; regroupement `group_radius=2.0` (> 2 m d'écart) donne plusieurs groupes, `10.0` un seul |
| sélecteur `IfcWall, Name=/[/` | | erreur classée `invalid_selector` (`lark.VisitError`) |
| fichier `pas un ifc` | | erreur `ifc_unreadable` (`ifcopenshell.Error: Unable to parse IFC SPF header`) ; absent = `FileNotFoundError` |
| `Maquette_é.ifc` | | s'ouvre normalement (M29 : accents OK en 0.9) |

### Cœur de `deskgate_bim.clash` : sous-classe de `Clasher`
```python
# Source : scratchpad p4/clash_proto.py (exécuté sur ifcclash 0.9.0). Aucun import de bcf.
import logging, ifcopenshell, ifcopenshell.geom, ifcopenshell.util.selector as sel
from ifcclash import ifcclash

class DeskgateClasher(ifcclash.Clasher):
    def __init__(self, num_threads, progress):
        s = ifcclash.ClashSettings(); s.logger = logging.getLogger("deskgate_bim.clash")
        super().__init__(s)
        self.num_threads, self.progress = num_threads, progress      # progress(pct, message), à limiter côté appelant
        self.selected: dict[str, set[str]] = {}                       # "a"/"b" -> GlobalId sélectionnés AVEC géométrie
        self.empty: set[str] = set()

    def add_collision_objects(self, name, ifc_file, source):
        found = set(sel.filter_elements(ifc_file, source["selector"]))   # lève LarkError/VisitError si sélecteur invalide
        with_geom = {e for e in found if getattr(e, "Representation", None) is not None}
        self.selected.setdefault(name, set()).update(e.GlobalId for e in with_geom)
        if not with_geom:
            return
        it = ifcopenshell.geom.iterator(self.geom_settings, ifc_file, self.num_threads, include=with_geom)
        if not it.initialize():
            return
        while True:
            self.tree.add_element(it.get())
            self.progress(it.progress(), f"géométrie {name}")           # it.progress() : 0..100, appelé à chaque élément
            if not it.next():
                break
        self.groups[name]["elements"].update({e.GlobalId: e for e in with_geom})

    def process_clash_set(self, clash_set):
        self.tree = ifcopenshell.geom.tree(backend="opencascade.trianglebvh")
        self.create_group("a")
        for src in clash_set["a"]:
            src["ifc"] = self.load_ifc(src["file"]); self.add_collision_objects("a", src["ifc"], src)
        b = "a"
        if clash_set.get("b"):
            self.create_group("b"); b = "b"
            for src in clash_set["b"]:
                src["ifc"] = self.load_ifc(src["file"]); self.add_collision_objects("b", src["ifc"], src)
        if not self.groups["a"]["elements"] or not self.groups[b]["elements"]:
            clash_set["clashes"] = {}; return                            # CAP-03 : aucun appel au moteur
        A, B = list(self.groups["a"]["elements"].values()), list(self.groups[b]["elements"].values())
        if clash_set["mode"] == "intersection":
            res = self.tree.clash_intersection_many(A, B, tolerance=clash_set["tolerance"], check_all=True)
        else:
            res = self.tree.clash_clearance_many(A, B, clearance=clash_set["clearance"], check_all=True)
        clash_set["clashes"] = {f"{r.a.get_argument(0)}-{r.b.get_argument(0)}": dict(
            a_global_id=r.a.get_argument(0), b_global_id=r.b.get_argument(0),
            a_ifc_class=r.a.is_a(), b_ifc_class=r.b.is_a(), a_name=r.a.get_argument(2), b_name=r.b.get_argument(2),
            type=ifcopenshell.geom.tree.get_clash_type(r.clash_type),
            p1=list(r.p1), p2=list(r.p2), distance=r.distance) for r in res}
```
Mapping des modes : `hard` -> `"intersection"` avec `tolerance` ; `clearance` -> `"clearance"` avec `clearance`. Les clés `ClashSet` sont `source = {"file": host_path, "mode": "i", "selector": ...}` (le `mode` de la source est ignoré par notre sous-classe). Performance mesurée (24 cœurs) : 1 800 éléments, 900 clashes : 2,8 s (1 thread) / 1,3 s (24 threads), RSS 104-128 Mo ; 9 800 éléments, 4 900 clashes : 16 s / 7 s, RSS 212-294 Mo. `it.progress()` est monotone par sélection : mapper A sur 0-45 %, B sur 45-90 %, post-traitement 90-100 %, et **limiter** les `ctx.progress` (1 % ou 0,5 s) : chaque appel écrit une ligne d'`events.jsonl` (1 800 lignes sans limitation).

### Normalisation, tri, regroupement, GUID (pur, sans scikit-learn)
```python
# Source : scratchpad p4/grouping.py (exécuté : 900 clashes, rayon 0/1 -> 900 groupes, 3.5 -> 338, 10 -> 56, 0,06 s)
import math, uuid

def normalise(c, sel_a, sel_b):                # a doit appartenir à la sélection A et b à la sélection B
    in_a_first, in_b_first = c["a_global_id"] in sel_a, c["a_global_id"] in sel_b
    swap = (not in_a_first and c["b_global_id"] in sel_a) or (        # a/b inversés par rapport aux sélections
        in_a_first == (c["b_global_id"] in sel_a) and c["a_global_id"] > c["b_global_id"])  # ambigu : ordre des GlobalId
    if swap:
        for k in ("global_id", "ifc_class", "name"):
            c["a_" + k], c["b_" + k] = c["b_" + k], c["a_" + k]
    return c

def group_clashes(clashes, radius):             # `clashes` triés par (a_global_id, b_global_id)
    if radius <= 0:
        return [[c] for c in clashes]
    groups = []                                  # (centre, membres) ; centre = milieu de p1/p2 du premier membre
    for c in clashes:
        m = [(a + b) / 2 for a, b in zip(c["p1"], c["p2"])]
        for centre, members in groups:
            if math.dist(centre, m) <= radius:
                members.append(c); break
        else:
            groups.append((m, [c]))
    return [members for _, members in groups]

NS = uuid.UUID("6f1c2b7e-3b1e-5d0a-9a53-2f0f8e5d7a10")   # constante du projet, à figer une fois
def group_guid(members, mode, tolerance):
    sig = "|".join(sorted(f"{c['a_global_id']}:{c['b_global_id']}" for c in members)) + f"#{mode}#{tolerance:.6f}"
    return str(uuid.uuid5(NS, sig))
```
(`normalise` est à couvrir par un test dédié : même entrée -> même sortie quel que soit l'ordre ou l'orientation renvoyés par ifcclash ; en auto-clash sans `ifc_b`, `sel_b == sel_a` et seul l'ordre des GlobalId tranche.)

### Contrat JSON `bcf-write-v1` (proposition, JSON Schema à écrire dans `docs/contrats/`)
```json
{
  "schema_version": 1,
  "project": "Clash CVC x STR",
  "author": "deskgate",
  "created_at": "2026-10-21T10:00:00Z",
  "colors": { "a": "FFE53935", "b": "FF1E88E5", "context": "40B0B0B0" },
  "topics": [{
    "guid": "<uuid v5 du groupe>",
    "title": "Gaine1 x Mur1 (+3)",
    "description": "hard, tolérance 0.002 m, 4 paires",
    "type": "Clash", "status": "Open",
    "guids_a": ["<GlobalId>", "..."], "guids_b": ["<GlobalId>", "..."],
    "context_guids": ["<GlobalId>", "..."],
    "camera": { "type": "perspective", "target": [1.1, 0.1, 1.0], "radius": 1.5 }
  }]
}
```
Couleurs : 8 hexadécimaux `AARRGGBB` (le XSD BCF 2.1 de `bcf-client` accepte 6 ou 8 caractères). Le fichier JSON ne porte ni chemin, ni nom BIM de plugin ; `context_guids` est calculé côté `deskgate-bim` (éléments dont la boîte englobante est à moins de `context_radius` du groupe, plafonné `max_context`, via `tree.select_box` ou une passe sur `ifcopenshell.util.shape` ; **à spiker** car non exécuté ici) ; vide = la vue 2 n'a que la coloration des objets du conflit.

### `deskgate-bcf` : écriture BCF 2.1 (vérifié, rechargé avec `BcfXml.load`)
```python
# Source : scratchpad p4/bcfproto/bcf_write.py (exécuté avec bcf-client 0.9.0). Seul fichier du dépôt autorisé à importer bcf.
import datetime, math, uuid
from pathlib import Path
from xsdata.models.datatype import XmlDateTime
import bcf.v2.model as mdl
from bcf.v2.bcfxml import BcfXml
from bcf.v2.visinfo import VisualizationInfoHandler

def _comps(guids): return [mdl.Component(ifc_guid=g) for g in guids]
def _cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]

def _camera(cam):                       # target, radius en mètres ; recul = 3 x rayon ; direction fixe (-1, 1, -0.8)
    d = cam.get("direction") or [-1.0, 1.0, -0.8]; n = math.sqrt(sum(c*c for c in d)); d = [c/n for c in d]
    r = max(float(cam["radius"]), 1.0); t = cam["target"]; pos = [t[i] - d[i] * 3 * r for i in range(3)]
    right = _cross([0, 0, 1], d); rn = math.sqrt(sum(c*c for c in right)) or 1.0; right = [c/rn for c in right]
    up = _cross(d, right)
    P, D, U = mdl.Point(x=pos[0], y=pos[1], z=pos[2]), mdl.Direction(x=d[0], y=d[1], z=d[2]), mdl.Direction(x=up[0], y=up[1], z=up[2])
    if cam.get("type") == "orthogonal":
        return {"orthogonal_camera": mdl.OrthogonalCamera(camera_view_point=P, camera_direction=D, camera_up_vector=U, view_to_world_scale=2.0 * r)}
    return {"perspective_camera": mdl.PerspectiveCamera(camera_view_point=P, camera_direction=D, camera_up_vector=U, field_of_view=60.0)}

def _only(t, c):       # vue 1 : tout masqué par défaut, exceptions = objets du conflit ; PAS de <Selection>
    return mdl.Components(
        visibility=mdl.ComponentVisibility(default_visibility=False,
            exceptions=mdl.ComponentVisibilityExceptions(component=_comps(t["guids_a"] + t["guids_b"]))),
        coloring=mdl.ComponentColoring(color=[
            mdl.ComponentColoringColor(color=c["a"], component=_comps(t["guids_a"])),
            mdl.ComponentColoringColor(color=c["b"], component=_comps(t["guids_b"]))]))

def _context(t, c):    # vue 2 : tout visible ; contexte gris alpha ; objets du conflit colorés
    skip = set(t["guids_a"]) | set(t["guids_b"]); ctx = [g for g in t.get("context_guids", []) if g not in skip]
    col = ([mdl.ComponentColoringColor(color=c["context"], component=_comps(ctx))] if ctx else []) + [
        mdl.ComponentColoringColor(color=c["a"], component=_comps(t["guids_a"])),
        mdl.ComponentColoringColor(color=c["b"], component=_comps(t["guids_b"]))]
    return mdl.Components(visibility=mdl.ComponentVisibility(default_visibility=True), coloring=mdl.ComponentColoring(color=col))

def write(doc, out: Path):
    created = XmlDateTime.from_datetime(datetime.datetime.fromisoformat(doc["created_at"]))   # "Z" accepté (3.11+)
    bcf = BcfXml.create_new(doc["project"])
    bcf.project_info.project.project_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "deskgate:" + doc["project"]))
    for t in doc["topics"]:
        th = bcf.add_topic(t["title"], t.get("description", ""), doc["author"], t.get("type", ""), t.get("status", ""))
        del bcf.topics[th.guid]                       # GUID déterministe : guid ET dossier du zip (attribut privé)
        th.topic.guid = t["guid"]; th.topic.creation_date = created; th._topic_dir = Path(t["guid"])
        bcf.topics[t["guid"]] = th
        for i, (make, label) in enumerate(((_only, "only"), (_context, "context")), 1):
            g = str(uuid.uuid5(uuid.UUID(t["guid"]), f"viewpoint-{i}-{label}"))
            th.add_visinfo_handler(VisualizationInfoHandler(
                mdl.VisualizationInfo(guid=g, components=make(t, doc["colors"]), **_camera(t["camera"]))))
    bcf.save(out)                                      # écrit en mémoire puis une seule fois sur disque
```
Sortie vérifiée : `bcf.version` = 2.1 ; par sujet `markup.bcf` + 2 `.bcfv` ; `Visibility DefaultVisibility="false"` + `Exceptions` (vue 1) ; `DefaultVisibility="true"` + `Coloring` `40B0B0B0` pour le contexte (vue 2) ; aucun `<Selection>` ; `BcfXml.load` relit 1 sujet, 2 points de vue, couleurs et caméra (perspective ou orthogonale). **Pas de snapshot** : `ViewPoint.snapshot` reste `None` et `bcf-client` n'imprime rien dans ce cas (il n'avertit que si un seul des deux côtés du snapshot est renseigné). Le test de validation du produit est la relecture : `BcfXml.load(...)` puis comparaison des GUID, couleurs, visibilité, type de caméra.

### Appel de `deskgate-bcf` depuis `ifc.clash` (MIT, sans import GPL)
```python
import json, subprocess
def write_bcf(settings, doc, work_dir):
    exe = settings["bcf_executable"]                               # chemin absolu, validé à l'entrée du plugin
    src, dst = f"{work_dir}/bcf-input.json", f"{work_dir}/conflits.bcf"
    with open(src, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    r = subprocess.run([exe, "write", "--input", src, "--output", dst],       # liste, pas de shell (règle 2)
                       capture_output=True, text=True, encoding="utf-8", timeout=600, check=False)
    if r.returncode != 0:
        raise BcfWriteError(r.returncode, r.stderr.strip()[:2000])            # le code de sortie classe l'erreur
    return dst
```
Vérifié : `deskgate-bcf.exe` lancé depuis un plugin dans le Job avec l'environnement en liste blanche renvoie 0 ; c'est un descendant du Job (mort avec lui). Le rendre indépendant du `PATH` : `settings.bcf_executable` obligatoire, absence = erreur classée `bcf_unavailable`.

### Worker `mcp.call` (exécuté dans l'Engine réel)
```python
# Source : scratchpad p4/mcp/mcp_worker.py (adapté : en production les serveurs viennent de ctx.settings["servers"])
import anyio
from mcp import Client, StdioServerParameters
from mcp.shared.exceptions import MCPError
from mcp.types import REQUEST_TIMEOUT

def _leaves(e):
    return [x for s in e.exceptions for x in _leaves(s)] if isinstance(e, BaseExceptionGroup) else [e]

async def _call(params, ctx, servers):
    name, tool, args = params["server"], params["tool"], params.get("arguments") or {}
    srv = servers.get(name)
    if srv is None: raise McpCallError("server_not_declared", name)
    if tool not in srv.get("allowed_tools", []): raise McpCallError("tool_not_allowed", f"{name}/{tool}")
    sp = StdioServerParameters(command=srv["command"], args=srv.get("args", []), env=srv_env(name), cwd=ctx.work_dir)
    box = {}
    async def watcher(scope):                         # annulation coopérative : ctx.cancelled() toutes les 0,25 s
        while True:
            await anyio.sleep(0.25)
            if ctx.cancelled(): box["cancelled"] = True; scope.cancel(); return
    async with anyio.create_task_group() as tg:
        tg.start_soon(watcher, tg.cancel_scope)
        try:
            async with Client(sp, read_timeout_seconds=params.get("call_timeout_s", 60)) as client:
                try:
                    box["r"] = await client.call_tool(tool, args)       # progress_callback= possible -> ctx.progress
                except MCPError as e:                                    # DANS le corps : sinon ExceptionGroup imbriqué
                    box["mcp_error"] = e
        except BaseException as eg:
            box["fatal"] = _leaves(eg)
        tg.cancel_scope.cancel()
    if box.get("cancelled") and "r" not in box: return {"summary": {"cancelled": True}}
    if "fatal" in box: raise McpCallError("server_unreachable", ", ".join(type(x).__name__ for x in box["fatal"]))
    if "mcp_error" in box:
        e = box["mcp_error"]
        raise McpCallError("call_timeout" if e.code == REQUEST_TIMEOUT else "mcp_error", str(e.code))
    r = box["r"]
    if r.is_error: raise McpCallError("tool_error", " ".join(getattr(c, "text", "") or "" for c in r.content)[:500])
    return {"summary": {"server": name, "tool": tool},
            "data": {"structured_content": r.structured_content,
                     "content": [{"type": c.type, "text": getattr(c, "text", None)} for c in r.content]}}

def run(params, ctx):
    return anyio.run(_call, params, ctx, ctx.settings["servers"])
```
Forme du résultat vérifiée : `CallToolResult` avec `is_error` (bool), `content` (liste de `TextContent` : `.type`, `.text`), `structured_content` (dict `{"result": ...}` si l'outil est annoté `-> str`, sinon `None` et le dict arrive en JSON dans `content[0].text`). Règle : `data.structured_content` si présent, sinon le texte ; contenus non texte (images) réduits à `{type, mime, bytes}` ; si `data` dépasserait ~900 Ko, écrire `mcp-result.json` en artefact et renvoyer `{"truncated": true}`.

Serveur de test (D-12), `MCPServer` de `mcp.server.mcpserver` :
```python
from mcp.server.mcpserver import MCPServer
mcp = MCPServer("deskgate-mini")
@mcp.tool()
def echo(text: str) -> str: return text
@mcp.tool()
def sleep(seconds: float) -> str: import time; time.sleep(seconds); return "reveille"
@mcp.tool()
def erreur(message: str = "boum") -> str: raise ValueError(message)          # -> is_error=True, content "Error executing tool erreur"
@mcp.tool()
def spawn_orphan(pid_file: str) -> str:                                      # petit-enfant qui dort 120 s ; PID écrits dans pid_file
    import os, subprocess, sys
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    open(pid_file, "w", encoding="utf-8").write(f"{os.getpid()} {p.pid}"); return "ok"
if __name__ == "__main__": mcp.run("stdio")
```
Lancement du serveur de test : `command = sys.executable`, `args = [chemin du fichier]` (pas de `uv run` : processus en plus).

### Contrôle de licence par environnement (CI)
```python
# Sonde exécutée DANS l'environnement contrôlé : <python de l'env> -I licenses_probe.py -> JSON sur stdout
import json
from importlib import metadata
def row(d):
    m = d.metadata
    return {"name": m["Name"], "version": d.version, "expr": m.get("License-Expression") or "",
            "license": (m.get("License") or "")[:200].replace("\n", " "),
            "classifiers": [c.split("::")[-1].strip() for c in m.get_all("Classifier", []) if c.startswith("License ::")]}
print(json.dumps(sorted((row(d) for d in metadata.distributions()), key=lambda r: r["name"].lower())))
```
```python
# Politique (tests/plugins/test_licenses.py) : copyleft fort = « GPL »/« AGPL » en mot entier ou classifier « GNU General Public License » / « GNU Affero »
import re
STRONG = re.compile(r"\b(A?GPL)\b|GNU (General|Affero) Public License", re.I)
def strong_copyleft(row):                       # \bGPL ne matche pas « LGPL » ; « GNU Lesser General Public License » ne matche pas
    text = " ".join([row["expr"], row["license"], *row["classifiers"]])
    return bool(STRONG.search(text)) and "Lesser" not in text and "LGPL" not in text
ALLOWED_GPL = {"env_bcf": {"bcf-client", "deskgate-bcf"}}     # ailleurs : ensemble vide
```
Inventaire réel observé (2026-10-20) : env `deskgate-bim` = ifcclash/ifcopenshell (LGPL), numpy, shapely, lark, pyparsing, isodate, six, python-dateutil, typing-extensions, tous permissifs ; env `deskgate-bcf` = idem + **bcf-client (classifier GPLv3, sans `License-Expression`)**, xsdata MIT, requests Apache-2.0, certifi MPL-2.0, urllib3 MIT, idna BSD ; env du runner + `mcp` = permissifs (pywin32 PSF, cryptography Apache/BSD). Le test vérifie, par environnement : aucun copyleft fort hors liste ; l'env de dev et l'env `deskgate-bim` n'ont ni `bcf-client` ni `deskgate-bcf` ; l'env `deskgate-bcf` contient `bcf-client` (sinon la sonde est cassée) ; `plugins/bim/bcf/NOTICE` mentionne `bcf-client` et la version installée.

### Fixture de session : environnements de plugins (uv)
```python
# tests/plugins/conftest.py
import os, shutil, subprocess, sys
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[2]

@pytest.fixture(scope="session")
def plugin_envs() -> dict[str, Path]:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv absent du PATH : environnements de plugins impossibles")
    cache = REPO / ".cache" / "plugin-envs"                      # dans .gitignore ; réutilisé d'une session à l'autre
    env = {**os.environ, "UV_PYTHON_DOWNLOADS": "never"}
    out = {}
    for pkg, key in (("deskgate-bim", "bim"), ("deskgate-bcf", "bcf")):
        target = cache / key
        subprocess.run([uv, "sync", "--locked", "--package", pkg, "--no-dev", "--python", sys._base_executable],
                       cwd=REPO, env={**env, "UV_PROJECT_ENVIRONMENT": str(target)}, check=True, timeout=600)
        out[key] = target / "Scripts" / "python.exe"
    out["bcf_exe"] = cache / "bcf" / "Scripts" / "deskgate-bcf.exe"
    return out
```
Coût mesuré (cache uv chaud, 1 Mo/s de téléchargement non limitant) : premier `sync` d'un env 1,6 s (bim) et 1,5 s (bcf), no-op 0,1 à 0,3 s ; premier téléchargement à froid : ifcopenshell 40 Mo + numpy 12 Mo (quelques secondes sur CI avec `enable-cache: true`). Les envs ne contiennent pas le groupe `dev` : les tests du plugin (`plugins/bim/tests/`) s'exécutent soit par pytest du dépôt via ces interpréteurs en sous-processus, soit dans l'env `deskgate-bim` synchronisé avec le groupe `dev` du plugin (pytest) : choisir une seule voie (recommandé : tests d'intégration dans `tests/` en sous-processus ; `plugins/bim/tests/` pour les tests unitaires exécutés dans l'env du plugin avec `uv sync --package deskgate-bim` + groupe `dev` dans un répertoire séparé).

### Extension du test AST (D-03)
```python
# tests/architecture/test_import_boundaries.py : étendre test_frontiere_gpl
# 1. déjà vrai : « bcf » / « deskgate_bcf » importés seulement sous plugins/bim/bcf/ (le test parcourt déjà tout le dépôt, plugins/ compris dès sa création)
# 2. à ajouter : « ifcclash.ifcclash.export_bcfxml », « .export(» et « export_bcfxml » ne doivent apparaître nulle part hors plugins/bim/bcf/ :
#    ast.walk sur plugins/bim/src : aucun Attribute dont attr in {"export", "export_bcfxml"} ; test_coeur_sans_bim couvre déjà src/deskgate.
# 3. mcp : seul src/deskgate/workers/mcp_call.py (et tests/mcp_fake) importe « mcp » ; `core/` interdit déjà httpx2/ctypes/subprocess.
# 4. deskgate_sdk reste stdlib-only (test existant) : ctx.settings n'y ajoute aucune dépendance.
# Dynamique : dans l'env bim, `python -I -c "import ifcclash.ifcclash, sys; assert 'bcf' not in sys.modules"`.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `McpError`, `timedelta` pour les délais, `HTTPStatusError` | `MCPError` (`.code`), `float` secondes, `REQUEST_TIMEOUT = -32001` importable de `mcp.types` | mcp 2.0 | Comparer `e.code == REQUEST_TIMEOUT`, jamais 408 |
| `FastMCP` | `MCPServer` (`mcp.server.mcpserver`) pour le serveur de test ; `mcp.server.fastmcp` reste en 1.x | mcp 2.x | Le serveur de test utilise la nouvelle API ; les serveurs 1.30 restent joignables par `Client(mode="auto")` (vérifié) |
| Export BCF d'ifcclash | `deskgate-bcf` | décision D-01..D-03 | L'export d'ifcclash (un point de vue, auteur « IfcClash », pas de couleurs) n'est jamais appelé |
| `smart_group_clashes` (sklearn) | regroupement par rayon maison | cette phase | Plus de scikit-learn dans le venv `deskgate-bim` |

**Deprecated/outdated :** le chemin `deskgate.workers.mcp_call` annoncé par `ARCHITECTURE.md` §4 est conservé tel quel ; `bcf-client` annonce un possible classifier LGPL (commits 2026-09-29) mais PyPI 0.9.0 reste GPLv3 : ne pas modifier la décision GPL du dépôt avant publication confirmée (décision de l'auteur).

## Open Questions

1. **Secrets d'`env` des serveurs MCP : disque ou mémoire ?**
   - Connu : `input.json` est lisible par n8n via `/data/travail/...` ; le serveur ne reçoit que la liste blanche + `env`.
   - Flou : coût réel de l'option « environnement du worker » (une clé `DESKGATE_MCPENV__...` par valeur).
   - Recommandation : option mémoire (§Pattern 4). Si le planificateur préfère la variante simple, documenter « aucun secret dans `env` en v0.1 » et ouvrir un item keyring v0.2 (déjà prévu, STACK/ARCHITECTURE §8).
2. **Calcul du contexte gris (`context_guids`)**
   - Connu : la vue 2 doit colorer le contexte ; BCF 2.1 n'a pas de « tout le reste » : il faut lister des GUID. `tree.select_box` existe dans l'arbre ifcopenshell (non exécuté ici).
   - Flou : coût sur une grosse maquette, rendu de l'alpha `40B0B0B0` dans BIMcollab/Solibri/Navisworks (certains viewers ignorent l'alpha).
   - Recommandation : spike court dans le plan `ifc.clash` (borne `max_context`, rayon `context_radius`) ; sans réponse, la vue 2 reste correcte avec le seul conflit coloré (dégradation acceptable) ; le rendu réel est une vérification différable (phase 5).
3. **Python 3.13 (matrice CI)** : wheels IfcOpenShell annoncées pour 3.13 mais non exécutées ici (3.11 seulement) ; `bcf-client`/`xsdata` non testés. La fixture utilise l'interpréteur courant : la CI le dira ; prévoir `skip` documenté plutôt qu'un échec si une roue manque.
4. **Orientation de `p1`/`p2` après échange a/b** : on laisse `p1/p2` inchangés (positions seulement, le milieu sert au regroupement et à la caméra) ; non vérifié que `p1` appartient toujours à l'élément `a` d'origine.
5. **Réglages avancés d'`ifcopenshell.geom.settings`** (`USE_WORLD_COORDS`, `DISABLE_OPENING_SUBTRACTIONS`) non explorés : les valeurs par défaut d'`ifcclash` sont conservées ; à inscrire dans `summary` pour M28.
6. **Clash entre deux fichiers (`ifc_a` ≠ `ifc_b`)** : la sous-classe passe par `load_ifc`, comme l'original ; non exécuté ici en deux fichiers, à couvrir par un test dédié (deux `file.write`).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 / 3.14 (launcher `py`) | plugins, runner | ✓ | 3.11.9, 3.14 | — (jamais `uv python install`) |
| uv | venvs de plugins en test/CI | ✓ | 0.12.17 (0.13.3 publié) | `skip` explicite si absent du PATH |
| Accès PyPI / cache uv | premières installations (ifcopenshell 40 Mo) | ✓ | — | cache `UV_CACHE_DIR` partagé |
| ifcopenshell, ifcclash, bcf-client, mcp | tests de la phase | ✓ (installés dans les venvs d'essai du scratchpad ; absents du dépôt) | 0.9.0.post1 / 0.9.0 / 0.9.0 / 2.3.0 | — |
| psutil | tests `proc` | ✓ | 7.2.2 | — |
| Docker / n8n | — | non requis | — | acceptation phase 5 |

**Missing dependencies with no fallback :** aucune.
**Missing dependencies with fallback :** `uv` absent en local de dev -> tests `bim`/`mcp` sautés avec message ; la CI (`setup-uv`) le fournit.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.x (`--strict-markers`, `--import-mode=importlib`) ; plugin `pytest-timeout` ; psutil |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (à étendre : marqueurs `bim`, `mcp`) |
| Quick run command | `uv run pytest -m "unit" -x -q` |
| Full suite command | `uv run pytest -m "not e2e"` puis `uv run pytest -m e2e` (CI existante) |

Marqueurs à déclarer (sinon `--strict-markers` échoue) : `bim` (exige les venvs de plugins construits par uv), `mcp` (serveur MCP réel en sous-processus). Les tests `bim`/`mcp` sont **aussi** marqués `proc` quand ils lancent le runner ; ils sont inclus dans `pytest -m "not e2e"` de la CI (coût ≈ 20 à 40 s en plus par cellule de matrice).

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CAP-01 | `hard` : mur + gaine = 1 clash `pierce`, GlobalId des deux côtés ; tolérance 0.0005 vs 0.002 sur 1 mm ; unités mm = m | bim (plugin dans son env) | `uv run pytest tests/plugins/test_clash_hard.py -x` | ❌ Wave 0 |
| CAP-01 | `clearance` : poutre/tuyau 5 cm : détecté à 0.10, absent à 0.03 ; touchant = distance 0 | bim | `uv run pytest tests/plugins/test_clash_clearance.py -x` | ❌ Wave 0 |
| CAP-01 | Regroupement par rayon, tri et GUID v5 déterministes (5 gaines, rayons 2 et 10 ; deux exécutions identiques ; ordre d'entrée permuté) | unit (pur) | `uv run pytest tests/unit/test_grouping.py` ou `plugins/bim/tests` | ❌ Wave 0 |
| CAP-01 | `max_clashes` : `truncated=true`, `result.json` < 1 Mio, artefact `clashes.json` | bim | `uv run pytest tests/plugins/test_clash_limits.py` | ❌ Wave 0 |
| CAP-01 | Progression alimentée (≥ 3 événements `progress` croissants, 0..100) via l'Engine réel | proc+bim | `uv run pytest tests/proc/test_ifc_clash_e2e.py::test_progress -x` | ❌ Wave 0 |
| CAP-01 | `ifc_a` en `/data/...` converti par le runner ; `..`, hors racine, jonction refusés (422 à la soumission, échec au lancement) | unit + fs + proc | `uv run pytest tests/unit/test_path_params.py tests/fs/test_path_params_real.py` | ❌ Wave 0 |
| CAP-02 | `bcf: true` : `.bcf` en artefact (chemin conteneur), 2 points de vue par sujet, vue 1 = masqué par défaut + exceptions, vue 2 = visible + contexte `40B0B0B0`, couleurs `AARRGGBB`, **aucun `<Selection>`**, `bcf.version` 2.1 ; relu par `BcfXml.load` dans l'env bcf | bim | `uv run pytest tests/plugins/test_bcf_output.py -x` | ❌ Wave 0 |
| CAP-02 | GUID déterministes : deux exécutions, mêmes GUID et mêmes membres XML (`created_at` injecté) | bim | `uv run pytest tests/plugins/test_bcf_deterministic.py` | ❌ Wave 0 |
| CAP-03 | Sélection vide / classe inconnue / sans géométrie : succès, 0 conflit, avertissement ; `bcf: true` avec 0 conflit n'écrit pas de BCF vide (ou BCF vide documenté) | bim | `uv run pytest tests/plugins/test_clash_empty.py -x` | ❌ Wave 0 |
| CAP-01 (D-07) | Erreurs classées : fichier illisible, sélecteur invalide, `bcf_unavailable` ; plafond mémoire : `memory_limit` via pic du Job | bim + proc | `uv run pytest tests/plugins/test_clash_errors.py tests/proc/test_engine_memory.py` | ❌ Wave 0 |
| CAP-04 | `mcp.call` echo : `succeeded`, `structured_content`/texte ; `erreur` -> `failed` ; serveur ou outil non déclaré -> `failed` (refus) | proc+mcp | `uv run pytest tests/proc/test_mcp_call.py -x` | ❌ Wave 0 |
| CAP-04 | Arbre arrêté : `spawn_orphan`, délai de tâche, annulation coopérative, sortie normale -> serveur et petit-enfant morts (`wait_dead`) | proc+mcp | `uv run pytest tests/proc/test_mcp_tree.py -x` | ❌ Wave 0 |
| CAP-04 | Délai d'appel (`call_timeout_s`) classé `call_timeout`, pas d'`ExceptionGroup` brut ; serveur absent / qui sort / stdout pollué | proc+mcp | `uv run pytest tests/proc/test_mcp_errors.py` | ❌ Wave 0 |
| CAP-04 | Config `[mcp_servers.*]` : validation, messages français, `kind="mcp"` sans `python`/`entry` ; env non écrit dans `input.json` | unit | `uv run pytest tests/unit/test_config_mcp.py tests/proc/test_mcp_no_secret_on_disk.py` | ❌ Wave 0 |
| CAP-05 | `deskgate-bcf write` : code 0, `.bcf` valide ; JSON invalide, `schema_version` inconnue = code 2 + stderr français ; écrit dans l'env bcf | bim | `uv run pytest tests/plugins/test_bcf_cli.py` | ❌ Wave 0 |
| CAP-05 | Contrat : `docs/contrats/bcf-write-v1.json` == copie `deskgate_bim/contracts` == copie `deskgate_bcf/schemas` (octet par octet) | unit | `uv run pytest tests/plugins/test_contract_equality.py` | ❌ Wave 0 |
| CAP-05 | Frontière : AST sans `bcf`/`deskgate_bcf` hors `plugins/bim/bcf/` ; pas d'appel à `export`/`export_bcfxml` ; `import ifcclash` dans l'env bim ne charge pas `bcf` | unit + bim | `uv run pytest tests/architecture/test_import_boundaries.py tests/plugins/test_no_bcf_in_bim_env.py` | ⚠️ existant à étendre |
| CAP-05 | Licences par environnement (dev, bim, bcf, runner+mcp) ; `NOTICE` ; sdist de `deskgate-bim` sans `bcf/` ; `deskgate-bcf` en GPL-3 avec `LICENSE` | bim | `uv run pytest tests/plugins/test_licenses.py tests/plugins/test_sdist_exclusion.py` | ❌ Wave 0 |
| D-02 | `settings` : transmis à `input.json` et `ctx.settings` ; contrat SDK/cœur identique (`CONTRACT.input_keys`) | unit | `uv run pytest tests/unit/test_sdk_contract.py tests/unit/test_settings.py` | ⚠️ existant à étendre |

### Sampling Rate
- **Per task commit:** `uv run pytest -m "unit" -x -q` (+ le fichier de test de la tâche)
- **Per wave merge:** `uv run pytest -m "not e2e"` (inclut `bim`, `mcp`, `proc`)
- **Phase gate:** suite complète verte (`-m "not e2e"` puis `-m e2e`), `ruff check`, `ruff format --check`, `pyright`, avant `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `tests/plugins/conftest.py` — fixture de session `plugin_envs`, helper `run_capability` (Engine réel + config avec `settings`/`path_params`), générateur IFC `tests/_support/ifc_synth.py` (copie du `synth.py`, importable seulement dans les envs de plugin : le générer par un petit script exécuté dans l'env bim, car `ifcopenshell` n'est pas dans l'env de dev)
- [ ] `tests/mcp_fake/mini_server.py` — serveur MCP de test (outils `echo`, `add`, `sleep`, `erreur`, `spawn_orphan`, `env`) ; il tourne avec l'interpréteur du runner (mcp installé comme dépendance cœur)
- [ ] `tests/plugins/licenses_probe.py` (sonde) et `tests/_support/` helpers de politique de licences
- [ ] Marqueurs `bim` et `mcp` dans `pyproject.toml` ; `.cache/` dans `.gitignore`
- [ ] `docs/contrats/bcf-write-v1.json` (schéma) avant tout code `deskgate-bcf` (llm-council : contrat d'abord)
- [ ] `mcp>=2.3,<3` dans `dependencies` du cœur + `uv lock` ; membres du workspace dans `[tool.uv.workspace]`
- [ ] Faux `FakeJob.peak_memory()` pour les tests de l'engine

## Plan suggéré (découpage et vagues)

Ordre issu du conseil (`llm-council-1.md` §7) : contrat d'abord, `mcp` en spike, puis `deskgate-bcf` et `ifc.clash` en parallèle sur le contrat. Fichiers modifiés indiqués pour éviter les conflits de vague.

| Plan | Vague | Contenu | Réqs | Fichiers principaux |
|------|-------|---------|------|---------------------|
| 04-01 | 1 | Contrat `docs/contrats/bcf-write-v1.json` (+ README du contrat) ; squelettes `plugins/bim` et `plugins/bim/bcf` (pyproject, `LICENSE` GPL-3, `NOTICE`, SPDX, `sdist exclude`) ; workspace uv + `uv lock` ; fixture `plugin_envs` ; sonde de licences et tests de licence/sdist/égalité de contrat ; extension AST ; marqueurs ; CI | CAP-05 | `pyproject.toml`, `uv.lock`, `docs/contrats/`, `plugins/**` (squelettes), `tests/architecture/`, `tests/plugins/`, `.github/workflows/ci.yml`, `.gitignore` |
| 04-02 | 1 | Cœur générique : `Capability.settings`/`path_params`, `kind="mcp"` + `mcp_servers`, `WorkerInput.settings` (+ `CONTRACT` des deux côtés), `ctx.settings`, conversion/validation des chemins (soumission 422 + lancement), classification `memory_limit` (pic du Job), `runner.example.toml` | CAP-01 (chemins), CAP-04 (config), D-02, D-07 | `src/deskgate/core/config.py`, `core/worker_protocol.py`, `deskgate_sdk/run.py`, `engine.py`, `jobs.py`, `jobobject.py`, `core/outcome.py`, tests unit/fs/proc |
| 04-03 | 2 | `deskgate-bcf` : `writer`, `cli write`, validation `jsonschema`, codes de sortie, tests dans l'env bcf (relecture `BcfXml.load`, vues, couleurs, absence de `<Selection>`, déterminisme) | CAP-05, CAP-02 (écriture) | `plugins/bim/bcf/**`, `tests/plugins/test_bcf_*.py` |
| 04-04 | 2 | `deskgate-bim` `ifc.clash` : params Pydantic, sous-classe `DeskgateClasher`, sélection vide, normalisation/tri/regroupement/GUID, JSON et plafonds, progression, erreurs classées, appel de `deskgate-bcf`, `OPENBLAS_NUM_THREADS` ; spike `context_guids` ; tests sur IFC synthétiques | CAP-01, CAP-02, CAP-03 | `plugins/bim/src/**`, `plugins/bim/tests/`, `tests/plugins/test_clash_*.py` |
| 04-05 | 2 | `mcp.call` : `deskgate/workers/mcp_call.py`, lancement `kind="mcp"` dans l'engine (déjà configuré en 04-02), serveur de test, tests (appel, erreur, refus, délai de tâche, annulation, arbre, secrets hors disque, serveur 1.x optionnel) | CAP-04 | `src/deskgate/workers/`, `tests/mcp_fake/`, `tests/proc/test_mcp_*.py` |
| 04-06 | 3 | Intégration : `ifc.clash` de bout en bout par l'Engine réel (conversion `/data`, artefacts `.bcf` et `clashes.json` en chemins conteneur, Job : arbre `deskgate-bcf` tué au délai) ; README/AGENTS (installation des venvs de plugins, consigne « pas de `--all-packages` »), `runner.example.toml` complet, clôture CAP-01..05 | CAP-01..05 | `tests/proc/test_ifc_clash_e2e.py`, docs |

04-03, 04-04 et 04-05 sont indépendants après 04-01 et 04-02 (04-04 ne dépend de 04-03 que pour l'étape `bcf: true`, qui n'a besoin que du contrat et de l'exécutable : les tests de 04-04 peuvent utiliser un faux exécutable jusqu'à ce que 04-03 le fournisse, ou 04-04 reste en vague 3 si le planificateur préfère l'ordre strict).

## Sources

### Primary (HIGH confidence)
- Exécution locale (scratchpad `p4/`, venvs 3.11.9) : `ifcclash` 0.9.0 (clash `hard`/`clearance`, unités mm/m, sélection vide, sans géométrie, orientation, déterminisme, perf 1 800 et 9 800 éléments, progression), `bcf-client` 0.9.0 (BCF 2.1 complet, relecture, GUID v5, caméra perspective/orthogonale), `mcp` 2.3.0 (Client/StdioServerParameters, mini-serveur, Engine réel du dépôt en copie : echo, erreur, refus, délai de tâche, délai d'appel, annulation, orphelin, serveur 1.30), packaging uv (workspace imbriqué, projets indépendants, sdist, `--package`, `--python <venv>`), mémoire Job (OpenBLAS, 0xC0000005, `PeakJobMemoryUsed`), `deskgate-bcf.exe` dans le Job, sondes de licences
- Code source lu : `ifcclash/ifcclash.py` (357 lignes), `bcf/v2/{bcfxml,topic,visinfo}.py`, `bcf/inmemory_zipfile.py`, `bcf/geometry.py`, `mcp/client/stdio.py`, `mcp/client/client.py`, `mcp/os/win32/utilities.py` (nid de Jobs, `CREATE_NO_WINDOW` sans breakaway)
- Context7 `/modelcontextprotocol/python-sdk/v2.3.0` : `Client.call_tool`, `MCPError` / `REQUEST_TIMEOUT = -32001`, forme d'une erreur d'outil (`is_error`, `content`, `structured_content`)
- PyPI JSON (2026-10-20) : bcf-client 0.9.0 (classifier GPLv3, seule version 0.9), ifcclash 0.9.0 (LGPLv3+), ifcopenshell 0.9.0.post1, mcp 2.3.0
- Dépôt : `CLAUDE.md`, `ARCHITECTURE.md` §4/§11, `.planning/research/{STACK,PITFALLS}.md` (M17, M26-M31), `.arthemis/reports/llm-council-1.md`, `src/**` (config, engine, jobobject, SDK, paths, jobs), `tests/**`

### Secondary (MEDIUM confidence)
- Convention BCF du projet d'origine (`docs/passation/05-PIPELINES-CIBLES.md` : deux points de vue, contexte gris transparent, pas de sélection, couleurs ARGB) ; le BCF 2.1 n'a pas de notion normative de transparence autre que le canal alpha du `Color` (lecture du XSD de `bcf-client` : motif 6 ou 8 hexadécimaux)

### Tertiary (LOW confidence)
- Rendu de l'alpha `40B0B0B0` dans BIMcollab/Solibri/Navisworks : non vérifié (viewers non disponibles) -> vérification différable phase 5
- Compatibilité Python 3.13 des roues IfcOpenShell/xsdata dans ce projet : annoncée, non exécutée

## Metadata

**Confidence breakdown:**
- Standard stack : HIGH — versions confirmées sur PyPI et installées ; dépendances (`ifcclash` sans `bcf-client`) lues dans les métadonnées
- Architecture : HIGH pour `ifc.clash`, `deskgate-bcf`, `mcp.call` (exécutés dans l'Engine réel) ; MEDIUM pour la conception `kind="mcp"`/`path_params` (cohérente avec le code existant mais non implémentée)
- Pitfalls : HIGH — chacun reproduit localement (OpenBLAS/mémoire, 0xC0000005, sélection vide, sdist, ExceptionGroup, orientation a/b)

**Research date:** 2026-10-20
**Valid until:** 30 jours pour ifcclash/bcf-client/IfcOpenShell (0.9.x stable) ; 7 jours pour `mcp` (2.x récent, API en mouvement) et pour une éventuelle publication `bcf-client` sous LGPL

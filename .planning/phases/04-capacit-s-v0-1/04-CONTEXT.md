# Phase 4: Capacités v0.1 - Context

**Gathered:** 2026-10-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Le runner réalise un vrai travail : `ifc.clash` détecte des conflits IFC (modes `hard` et
`clearance`), regroupe, renvoie un JSON avec les GlobalId et produit sur demande un BCF 2.1 via
`deskgate-bcf` (GPL-3, sous-processus) ; `mcp.call` appelle un outil d'un serveur MCP stdio déclaré,
sans LLM, dans le Job Object de la tâche. Le code MIT n'importe jamais `bcf-client`.
Exigences : CAP-01..05.

Hors phase : manifeste `plugin.yaml`, `deskgate plugin add`, exécuteur `cli`, modes `touch` et
`duplicate`, BCF 3.0, lecture de BCF (v0.2) ; `deskgate init`, docker-compose, acceptation sur
maquettes réelles (phase 5).

</domain>

<decisions>
## Implementation Decisions

### Organisation des paquets (rappel des décisions de cadrage)
- **D-01:** `plugins/bim/` = paquet `deskgate-bim` (MIT, pyproject propre), module
  `deskgate_bim.clash:run`. `plugins/bim/bcf/` = paquet `deskgate-bcf` (GPL-3, `LICENSE` propre),
  CLI `deskgate-bcf` (JSON vers `.bcf`). Le cœur `src/deskgate` ne contient aucun nom BIM :
  `ifc.clash` est déclaré dans `runner.toml` `[capabilities."ifc.clash"]` (`kind = "python"`,
  `python` = interpréteur du venv du plugin, `entry = "deskgate_bim.clash:run"`).
- **D-02:** Chaque plugin a son environnement isolé (uv). `ifc.clash` appelle `deskgate-bcf` en
  sous-processus (descendant du Job Object), avec des fichiers JSON comme seul échange ; le chemin
  de l'exécutable `deskgate-bcf` est fourni par la configuration de la capacité (mécanisme de
  réglages par capacité à définir par la recherche, sans nom BIM dans le cœur).
- **D-03:** Test CI : aucun paquet hors `plugins/bim/bcf/` n'importe `bcf` ni `deskgate_bcf` (test
  AST existant à étendre aux plugins) ; `ifc.clash` n'appelle jamais l'export BCF d'`ifcclash` ;
  contrôle des licences par environnement et fichier `NOTICE`.

### ifc.clash
- **D-04:** Sélecteurs `selector_a` / `selector_b` en **syntaxe sélecteur IfcOpenShell**
  (`ifcopenshell.util.selector`), par exemple `IfcFlowSegment` ou `IfcWall, Name=/EI.*/`. `ifc_a`
  obligatoire, `ifc_b` optionnel (même maquette si absent). Chemins en forme conteneur
  `/data/...`, convertis et validés contre les racines avec les mêmes règles que le cœur.
- **D-05:** Modes v0.1 : `hard` (intersection, tolérance de pénétration) et `clearance` (distance
  minimale). **Tolérance explicite en mètres.** `touch` et `duplicate` en v0.2.
- **D-06:** **Un sujet BCF = un groupe de conflits** (regroupement spatial d'`ifcclash` ou
  équivalent), avec les GUID de toutes les paires du groupe. JSON de sortie : groupes puis paires
  (GlobalId A et B, types, noms, position, distance ou pénétration), tri déterministe, plafond
  `max_clashes` avec drapeau `truncated`.
- **D-07:** Sélection vide : succès à 0 conflit avec avertissement (CAP-03). Erreurs classées
  (fichier illisible, sélecteur invalide, mémoire).
- **D-08:** BCF sur demande (`bcf: true`) : BCF 2.1, deux points de vue par sujet — (1) objets du
  conflit seuls, (2) contexte gris transparent —, couleurs ARGB, pas de sélection enregistrée.
  GUID de sujet déterministes (UUID v5 sur la signature du groupe). BCF écrit dans le `work_dir` et
  déclaré comme artefact.
- **D-09:** Tests sur **IFC synthétiques** générés par les tests avec l'API IfcOpenShell (mur et
  gaine qui le traverse, poutre à 5 cm d'un tuyau, sélection vide…), résultats connus d'avance.
  Les maquettes réelles de l'utilisateur servent à l'acceptation (phase 5).

### deskgate-bcf
- **D-10:** Contrat JSON d'entrée **versionné** (`schema_version`) dans `docs/contrats/`
  (par exemple `bcf-write-v1.json`), dupliqué (pas importé) côté `deskgate-bim` avec un test
  d'égalité. Sortie : fichier `.bcf` et code de sortie ; erreurs sur stderr.

### mcp.call
- **D-11:** Serveurs MCP déclarés dans `runner.toml` (format proche de la configuration MCP de
  Claude : `command`, `args`, `env`, liste d'outils autorisés). `mcp.call` reçoit
  `{server, tool, arguments}` et refuse tout serveur ou outil non déclaré (aucune commande libre).
  Exécution par un worker Python dans le Job Object ; le serveur stdio est son descendant et meurt
  avec la tâche. SDK `mcp >=2.3,<3` (API 2.x). Résultat : contenu structuré ou texte de l'outil ;
  `is_error` donne une tâche `failed`.
- **D-12:** Tests avec un **mini-serveur MCP de test** dans `tests/` (outils `echo`, `sleep`,
  `erreur`, `spawn_orphan`) pour prouver l'appel, le délai et l'arrêt de l'arbre.

### Claude's Discretion
- Nom exact des clés de réglages par capacité, structure des dossiers des plugins, outillage de
  création des venv de plugins pour les tests, découpage des plans.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `ARCHITECTURE.md` §4 (exécution), §11 (plugins BIM, module BCF GPL), §12 (structure)
- `CLAUDE.md` — règle 10 (frontière GPL), cœur générique
- `.arthemis/reports/llm-council-1.md` — mcp.call dans le Job, contrat JSON bcf d'abord
- `.planning/research/STACK.md` — mcp 2.x, ifcclash, bcf-client (API vérifiées)
- `.planning/research/PITFALLS.md` — M17, M26 à M31
- `docs/passation/05-PIPELINES-CIBLES.md` — conventions BCF du projet d'origine (contexte)
- `.planning/phases/02-c-ur-d-ex-cution/02-0*-SUMMARY.md` — engine, worker SDK, capacités dans runner.toml
- `.planning/phases/03-rappel-fiable/03-0*-SUMMARY.md` — rappel, payload
- `.planning/REQUIREMENTS.md` — CAP-01..05

</canonical_refs>

<code_context>
## Existing Code Insights

- `src/deskgate_sdk/run.py` : worker stdlib lancé par chemin (ctx.log, progress, artifact, cancelled, résultat atomique).
- `src/deskgate/core/config.py` : `Capability` (kind python, python, entry, pythonpath, memory_mb, timeout_max, resource).
- `src/deskgate/engine.py`, `jobobject.py` : lancement en Job Object, revalidation des artefacts.
- `tests/architecture/test_import_boundaries.py` : frontières AST (à étendre aux plugins).
- Faux plugins de test : modèle pour un plugin python.

</code_context>

<specifics>
## Specific Ideas

- Un calcul long (plus de 10 min) sur maquette réelle sera validé en phase 5 ; ici, la progression (`ctx.progress`) doit être alimentée pendant la détection.

</specifics>

<deferred>
## Deferred Ideas

- Modes `touch` et `duplicate`, BCF 3.0, lecture BCF, plugins `bcf.write` / `bcf.read` — v0.2.

</deferred>

---

*Phase: 04-capacit-s-v0-1*
*Context gathered: 2026-10-21*

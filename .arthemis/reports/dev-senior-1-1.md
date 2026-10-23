# Rapport dev-senior — Deskgate (cycle 1)

> Phases 2 (diagnostic) et 3 (plan de refactoring, proposition pure) de la skill dev-senior, sur la
> cartographie confirmée par l'utilisateur le 2026-10-23 (`dev-senior-1-1-architecture.md`).
> Commit analysé : `0006fa6` (code identique à `ce11da5`, seul le rapport de cartographie diffère).
> Lecture seule : ce fichier est le seul écrit dans le dépôt. Les rapports d'audit existants
> (`audits/saas-council-*.md`, `.planning/ROADMAP.md` phases 999.x) n'ont été lus **qu'après** le
> diagnostic, pour renseigner le champ « Statut » de chaque finding ; aucun finding n'en est recopié
> sans revérification.
>
> Vérité-terrain utilisée (commandes reproductibles, sorties citées dans les findings) :
> `uvx radon==6.0.1 cc -s -n C` et `mi -s` ; `npx --yes jscpd --min-lines 10` ; `rg` ; quatre sondes
> Python jetables dans le scratchpad, exécutées avec l'interpréteur `.venv` du dépôt en mode `-I`
> (`probe_nan.py`, `probe_poison.py`, `probe_growth.py`, `probe_mcpdata.py`) ; tests ciblés
> `pytest -p no:cacheprovider tests/fs/test_store_recovery.py tests/fs/test_sender_retry.py
> tests/fs/test_supervisor_restart.py tests/architecture` → `48 passed in 18.59s`.

## Synthèse

État général : un runner **solide et lisible** pour une v0.1. Le noyau pur, l'outbox SQLite en une
transaction et la discipline Job Object tiennent à la lecture comme à l'essai ; la dette se concentre
sur le **contrat du résultat** (champ `data`) et sur trois angles morts du thread `sender`.

Trois risques principaux :
1. **`mcp.call` ne rend pas son résultat à n8n** : la sortie de l'outil va dans `data`, que ni le rappel
   ni `GET /jobs/{id}` n'exposent (DS-ARCH-1, Critique, sonde `probe_mcpdata.py`).
2. **Une erreur déterministe sur un seul rappel bloque toute la boîte d'envoi** puis, par le
   superviseur, arrête le runner en code 6 (DS-ARCH-2, Majeur, sonde `probe_poison.py`).
3. **Un `NaN`/`Infinity` produit par un plugin traverse le contrat** : rappel en JSON invalide, `GET`
   en 500 (DS-ARCH-3, Majeur, sonde `probe_nan.py`).

Trois forces : noyau de décision pur et testé (`states.step`, `outcome.verdict`, `callback_policy`,
`supervisor.decide`) ; écriture terminale et ligne `callbacks` dans **une** transaction gardée par
`WHERE status=?` (`store.py:270-290`, `451-465`) avec écriture préalable de l'essai (`maybe_delivered`) ;
duplication 1,63 % et complexité du cœur plafonnée à C(20) (outils ci-dessous).

## Verdict par point d'audit (P1..P5)

| Point | Verdict | Preuve |
|---|---|---|
| **P1 Reprise fiable** | **Tenu avec réserves** | Tenu : toute transition terminale passe par `store._terminal` (`store.py:270-290`) ou `recover_interrupted` (`store.py:451-465`), qui insèrent la ligne `callbacks` dans la même transaction ; `callbacks.job_id UNIQUE` (`store.py:100`) ; recovery au démarrage (`runtime.py:189`) et par le superviseur (`supervisor.py:181-221`) ; verdict non écrit rejoué (`engine.py:256-281`) ; essai inscrit avant l'envoi puis classé `delivered_duplicate` sur 409 (`store.py:546-550`, `callback_policy.py:61-65`) ; abandon borné en code 6 (`supervisor.py:58-74`). Tests ciblés verts (48). Réserves : DS-ARCH-2 (une ligne empoisonnée bloque les autres rappels et arrête le runner), DS-ARCH-3 (`NaN` → rappel jamais accepté), DS-SCAL-3 (400/422 réessayés 24 h), DS-ARCH-1 (rappel livré mais vide pour `mcp.call`). Limite écrite par les auteurs : un thread bloqué (et non mort) n'est pas recréé (`engine.py:11-12`). |
| **P2 Frontières de sécurité** | **Tenu** | `rg "shell=\|BREAKAWAY\|os\.system"` : aucun `shell=`, `BREAKAWAY_OK` jamais posé (`jobobject.py:156-173`) ; `Popen` en liste, `argv[0]` et `cwd` absolus, création suspendue puis assignation (`jobobject.py:176-208`) ; chemins validés à la soumission **et** au lancement (`jobs.py:115-135`, `engine.py:301-322`) par segments puis après résolution (`core/paths.py:149-160`) ; arguments MCP déclarés convertis (`core/paths.py:206-228`) ; masquage `signature` sur handlers, audit, journaux de tâche (`core/redact.py:13-53`, `jobs.py:206`) ; erreur d'envoi réduite au nom de classe (`sender.py:221-224`). Notes (sans réserve sur le point lui-même) : les arguments MCP non déclarés dans `path_arguments` restent opaques par conception ; `allow_non_loopback` est une échappatoire explicite et signalée ; SEC-003 (filtre par nom d'hôte seul) reste au backlog 999.6. |
| **P3 Cœur générique et licences** | **Tenu** | `rg -i "ifc\|bcf\|clash" src/ --type py` → aucune occurrence ; `deskgate_bim` ne dépend que de `ifcclash`, `ifcopenshell`, `pillow`, `pydantic` (`uv.lock`) ; `ifcclash` 0.9.0 classé « LGPLv3+ » (METADATA de l'environnement `.cache/plugin-envs/py314`) et n'importe `bcf` que dans une fonction (`ifcclash/ifcclash.py:227`, import paresseux) ; seul `deskgate-bcf` déclare `bcf-client` ; frontière contrôlée par `tests/architecture/test_import_boundaries.py`, `tests/plugins/test_no_bcf_in_bim_env.py`, `test_licenses.py`, `test_sdist_exclusion.py`. |
| **P4 Reprenabilité** | **Non tenu (volet documentation) ; volet code tenu** | Code : radon `cc` ne remonte aucune fonction du cœur au-delà de C (max `mcp_call._call` C(20)), `mi` tout en A sauf `engine.py` B (16,14) ; jscpd 1,63 % dont 129 lignes de contrats JSON volontairement copiés. Documentation : `ARCHITECTURE.md` décrit en présent des éléments absents du code livré (routes `/capabilities`, `/artifacts`, `/ui`, exécuteur `cli`, concurrence par ressource, réutilisation idempotente, OpenAPI générée, `mcp_servers.toml`, arborescence `queue/ executors/ …`) — tableau d'écarts de la cartographie, revérifié sur `ARCHITECTURE.md:28-40` et `core/config.py:119`, `api/app.py:36`, `store.py:371`. Le critère P4 exige explicitement « le code livré, pas une cible future » (DS-MAINT-1). |
| **P5 Prêt à distribuer** | **Tenu avec réserves** | Tenu : `uv.lock` versionné, CI `uv sync --locked` sur 3.11 et 3.13, build `--all-packages` (`.github/workflows/ci.yml`) ; n8n `2.43.8` épinglé par digest (cartographie) ; trois paquets en `0.1.0.dev0` cohérents. Réserves : `AGENTS.md:38` contient encore `https://github.com/<organisation>/deskgate.git` (DS-MAINT-2) ; plugins installés en mode éditable, liés au clone (DS-MAINT-4) ; installation du runner sans contraintes du lock et bump des plugins hors liste (LIV-002, LIV-004, backlog 999.3, non revérifiés au-delà de `pyproject.toml`) ; capacité annoncée `mcp.call` inutilisable depuis n8n (DS-ARCH-1). `deskgate doctor` et la tâche planifiée n'ont pas été exécutés (consigne) : non vérifiés ici. |

## Findings par axe

### Axe 1 — Architecture

#### [DS-ARCH-1] Le résultat de `mcp.call` n'atteint jamais n8n : il vit dans `data`, que rien n'expose
- **Axe** : architecture
- **Point d'audit** : P1 (rappel livré mais vide), P5 (capacité annoncée)
- **Sévérité** : Critique (comportement incorrect latent : aucune exécution réelle depuis n8n ne l'a encore révélé, `n8n/README.md:51` « Aucun second exemple `mcp.call` »)
- **Preuve** :
  - `workers/mcp_call.py:118-128` : la sortie de l'outil (`structured_content`, `content`) est placée dans `data` ; `summary` ne contient que `{server, tool, is_error}`.
  - `core/payload.py:3` « Le champ `data` du plugin n'est jamais transmis » ; `core/payload.py:49-57` ; `jobs.py:50-72` (`job_view` sans `data`).
  - Sonde `probe_mcpdata.py` (fonctions réelles `build_callback` et `job_view`) :
    `rappel : {'job_id': 'j', 'capability': 'mcp.call', 'status': 'succeeded', 'duration_s': None, 'summary': {'server': 's', 'tool': 't', 'is_error': False}, 'artifacts': [], 'error': None}` ; même absence dans `GET`.
  - Le seul test qui lit la sortie MCP la lit **dans la base**, pas par l'API : `tests/proc/test_mcp_paths_real.py:166-168` (`json.loads(row.result_json)["data"]`).
- **Constat** : pour toute réponse d'outil inférieure à 900 000 octets, n8n reçoit `succeeded` sans le contenu ; au-delà, il reçoit un artefact `mcp-result.json`. Le résultat n'est consultable qu'en lisant SQLite.
- **Pourquoi c'est un problème** : une des deux capacités de la v0.1 (`README.md:29`) ne remplit pas sa fonction depuis n8n ; la décision D-06 (« `data` jamais transmis ») et le worker `mcp_call` se contredisent. La raison probable de D-06 (borner le rappel à 1 Mio, garder `data` pour un futur `output_schema`) tient pour `ifc.clash`, qui publie l'essentiel dans `summary` et des artefacts, pas pour `mcp.call`.
- **Refactoring proposé** : aucun refactoring iso-fonctionnel ne corrige ce point (il faut changer le contrat) → décision produit, voir « Suggestions produit » S1 et la proposition P-03 du plan.
- **Statut** : déjà connu **ARC-004** (backlog 999.5, « `data` stocké mais exposé nulle part »), classé Mineur par le council avec rayon « auteurs de plugins ». **Nouveau** : la conséquence sur `mcp.call` (capacité vidée) et la réévaluation en Critique.

#### [DS-ARCH-2] Thread `sender` sans isolement par ligne : une erreur déterministe bloque tous les rappels puis arrête le runner
- **Axe** : architecture
- **Point d'audit** : P1
- **Sévérité** : Majeur (mécanisme prouvé ; déclencheur réel non identifié)
- **Preuve** :
  - `store.py:546-550` : `attempts+1` et `maybe_delivered=1` sont validés **avant** l'envoi, sans avancer `next_attempt_at`.
  - `sender.py:123-202` : aucun `try` entre la réclamation et `record_callback_result` ; `sender.py:241-249` : 5 exceptions consécutives → `failed`, `on_fatal`.
  - `supervisor.py:69-74` : au-delà de 3 recréations en 600 s → `give_up` → code 6 (`runtime.py:219-221`), non relancé par le Planificateur (`supervisor.py:8-9`).
  - Sonde `probe_poison.py` (vrai `Sender.tick`, vraie base, client qui lève `RuntimeError`, deux rappels dus `j1` puis `j2`) :
    ```
    tick 0 RuntimeError
    [('j1', 1, 1, 'pending'), ('j2', 0, 0, 'pending')]
    tick 1 RuntimeError
    [('j1', 2, 1, 'pending'), ('j2', 0, 0, 'pending')]
    tick 2 RuntimeError
    [('j1', 3, 1, 'pending'), ('j2', 0, 0, 'pending')]
    ```
- **Constat** : la ligne fautive est réclamée en tête à chaque tour (`ORDER BY c.next_attempt_at`, `store.py:533`) ; `j2` n'est jamais tenté ; `maybe_delivered` passe à 1 sans qu'aucun octet ne soit parti. Avec le back-off du thread (2+4+8+16 s), le sender meurt en ≈ 30 s, quatre fois → runner arrêté en ≈ 2 min.
- **Pourquoi c'est un problème** : P1 exige « aucun rappel n'est perdu en silence » ; ici tous les rappels **des autres tâches** restent bloqués jusqu'à la prochaine ouverture de session. Le `maybe_delivered=1` fantôme peut ensuite transformer un 409 « finished » en `delivered_duplicate` alors que rien n'a été livré. L'engine, lui, isole chaque tâche (`engine.py:286-294`, `415-432`) : l'asymétrie est le vrai défaut de conception. Je n'ai pas trouvé d'exception non-HTTP atteignable aujourd'hui (`_send` capture `HTTPError` et `InvalidURL`, `build_callback` relit du JSON écrit par l'engine) : la sévérité reste Majeur et non Critique pour cette raison.
- **Refactoring proposé** : traiter toute exception levée après la réclamation comme un essai en échec de la ligne (réessai avec back-off, erreur = nom de classe), ne laisser remonter au thread que les erreurs de base. Proposition P-01.
- **Statut** : **nouveau** (DON-008 du council porte sur l'ordre essai/revérification d'hôte, pas sur ce blocage).

#### [DS-ARCH-3] Le contrat worker accepte `NaN`/`Infinity` : rappel en JSON invalide, `GET /jobs/{id}` en 500
- **Axe** : architecture
- **Point d'audit** : P1
- **Sévérité** : Majeur (comportement incorrect latent ; production réelle de `NaN` par un plugin non observée)
- **Preuve** :
  - `deskgate_sdk/run.py:56-62` : `json.dump` avec `allow_nan` par défaut (vrai) ; `core/worker_protocol.py:98` : `json.loads` accepte `NaN` ; `ResultOk.summary: dict[str, Any]` (`:54`) ne filtre pas.
  - `engine.py:547-550` et `core/payload.py:24-26` : `json.dumps` par défaut réécrit `NaN`.
  - Sonde `probe_nan.py` (fonctions réelles) :
    ```
    state: valid
    callback body: b'{"job_id":"j",...,"summary":{"d":NaN},"artifacts":[],"error":null}'
    strict JSON parse fails: NaN
    JSONResponse: Out of range float values are not JSON compliant: nan
    ```
- **Constat** : un résumé contenant un flottant non fini donne une tâche `succeeded` dont le rappel n'est pas du JSON standard et dont la lecture par l'API lève `ValueError` dans la sérialisation Starlette.
- **Pourquoi c'est un problème** : n8n (analyseur JSON strict, comportement exact de 2.43.8 non vérifié) refusera vraisemblablement le corps ; `classify` traite alors 400 comme transitoire (DS-SCAL-3) → ≈ 24 h de réessais puis `abandoned_exhausted`, et la voie de repli (`GET`) est en 500. Les calculs géométriques (`numpy`, `ifcclash`) et des serveurs MCP Python peuvent produire `NaN`.
- **Refactoring proposé** : refuser les constantes non finies à la frontière (`parse_result` → `invalid`, `run.py` → `allow_nan=False`). Change l'issue du cas `NaN` (aujourd'hui `succeeded` inutilisable → demain `failed/invalid_result` livré) : correction, pas iso-fonctionnelle sur ce seul cas. Proposition P-02.
- **Statut** : **nouveau**.

#### [DS-ARCH-4] L'engine construit lui-même la configuration de lancement MCP
- **Axe** : architecture
- **Point d'audit** : P4
- **Sévérité** : Mineur
- **Preuve** : radon `M 296:4 Engine._launch_inner - C (14)` ; `engine.py:328-359` (dictionnaire `servers`, sélection du serveur visé, nommage `mcp_env_var`) au milieu des effets de bord (`mkdir`, écriture d'`input.json`, lancement) ; `engine.py` seul module du cœur en MI B (`src\deskgate\engine.py - B (16.14)`), 715 lignes, 10 commits (cartographie).
- **Constat** : la décision « quel interpréteur, quelle entrée, quels réglages, quelles variables » est pure mais enfouie dans une méthode à effets.
- **Pourquoi c'est un problème** : c'est le point d'extension annoncé de la v0.2 (exécuteur `cli`, manifestes) ; chaque nouveau type ajoutera une branche ici, dans le fichier déjà le plus gros et le plus modifié. La raison probable (deux types seulement, éviter une abstraction prématurée) était juste en v0.1.
- **Refactoring proposé** : extraire une fonction pure `core/launch.py:build_launch(cap, row_params, config, runner_python) -> LaunchPlan`. Proposition P-06.
- **Statut** : **nouveau** (MNT-006 du council vise `mcp_call._call`, pas l'engine).

#### [DS-ARCH-5] File à un seul emplacement global, sans durée de vie en file
- **Axe** : architecture (conséquence en scalabilité)
- **Point d'audit** : P1
- **Sévérité** : Mineur
- **Preuve** : `store.py:369-371` (`NOT EXISTS (SELECT 1 FROM jobs WHERE status='running')`, `resource` non lu) ; l'échéance ne court qu'au lancement (`engine.py:409`) ; exemple n8n : Wait limité à 6 h, `timeout_max` 14 400 s (cartographie, « Réglages répartis »).
- **Constat** : deux tâches de 4 h en file suffisent à ce que la troisième démarre après l'expiration du Wait n8n ; elle calcule alors pour personne et son rappel finit en `abandoned_stale` (409 « finished » sans `maybe_delivered`).
- **Pourquoi c'est un problème** : coût CPU gaspillé et résultat perdu côté workflow, sans erreur explicite au moment de la soumission. Acceptable en mono-utilisateur v0.1, à trancher avant la concurrence par ressource de la v0.2.
- **Refactoring proposé** : aucun iso-fonctionnel ; suggestion produit S3 (délai maximal en file).
- **Statut** : déjà connu en partie **ARC-007** (concurrence 1 câblée, `resource` jamais lu) ; l'interaction avec le Wait n8n est **nouvelle**.

### Axe 2 — Logique dupliquée

Vérité-terrain : `npx --yes jscpd --min-lines 10` sur `src`, `plugins/bim/src`, `plugins/bim/bcf/src`,
`scripts` → `Found 4 exact clones with 142(1.63%) duplicated lines in 56 (5 formats) files`. Trois clones
sont les contrats JSON `bcf-write-v1/v2` copiés de part et d'autre de la frontière GPL : **duplication
voulue** (le côté MIT ne doit pas importer le paquet GPL), dont l'égalité est testée
(`tests/plugins/test_contract_equality.py`) — à ne pas fusionner. Le quatrième est DS-DUP-2.

#### [DS-DUP-1] Règle « quelle conversion de chemins pour quel type de capacité » écrite deux fois
- **Axe** : duplication
- **Point d'audit** : P2
- **Sévérité** : Mineur (duplication réelle d'une règle de sécurité ; la copie qui protège effectivement est celle du lancement)
- **Preuve** : `jobs.py:117-132` et `engine.py:304-319` : même `if cap.kind == "mcp": convert_mcp_arguments(... mcp_path_arguments(), mappings(), allowed_roots, resolver) else: convert_path_params(... cap.path_params ...)`.
- **Constat** : la soumission (refus précoce, 422) et le lancement (chemins réellement transmis) dupliquent l'aiguillage par `kind`.
- **Pourquoi c'est un problème** : l'exécuteur `cli` de la v0.2 devra être ajouté aux deux endroits ; un oubli côté soumission ferait passer en 202 une tâche refusée au lancement, un oubli côté lancement serait une faille de règle 4.
- **Refactoring proposé** : une fonction `convert_params(kind, path_params, params, config, resolver)` dans le noyau, appelée des deux côtés. Proposition P-05.
- **Statut** : **nouveau**.

#### [DS-DUP-2] Cycle de vie des threads `engine` et `sender` recopié
- **Axe** : duplication
- **Point d'audit** : P4
- **Sévérité** : Mineur
- **Preuve** : jscpd `deskgate\engine.py 613-625 <-> deskgate\sender.py 224-236 (13 lignes)` ; mêmes `_connection`/`_drop_connection` (`engine.py:213-222`, `sender.py:112-121`), `status` (`engine.py:662-670`, `sender.py:256-264`), `start`/`stop`.
- **Constat** : la mécanique (événements `_stop`/`_wake`, connexion paresseuse, état `/health`) est identique ; les **politiques d'erreur** de `run()` diffèrent volontairement (engine : `OperationalError` seule tolérée ; sender : toute exception).
- **Pourquoi c'est un problème** : coût faible aujourd'hui ; il augmenterait avec un troisième thread. **Similarité accidentelle pour `run()`** : ne pas fusionner les boucles.
- **Refactoring proposé** : au plus une petite base `_Loop` pour `start`/`stop`/`wake`/`status`/connexion, `run()` restant propre à chaque module. Effort S, bénéfice faible : à ne faire qu'avec un troisième thread.
- **Statut** : **nouveau** (MNT-007, fermé, documentait seulement les politiques).

#### [DS-DUP-3] Codes de sortie du runner déclarés à deux endroits
- **Axe** : duplication
- **Point d'audit** : P4, P5 (diagnostic `doctor`)
- **Sévérité** : Mineur
- **Preuve** : `runtime.py:48-52` et `supervisor.py:32` (valeurs 2 à 6) ; `scheduler.py:332-338` (`_RUNNER_EXIT`, mêmes valeurs, libellés lus par `doctor`).
- **Constat** : un nouveau code ou un renumérotage doit être reporté à la main dans le diagnostic.
- **Refactoring proposé** : module noyau `core/exit_codes.py` (constantes + libellés), importé par `runtime`, `supervisor`, `scheduler`. Iso-fonctionnel. Effort S.
- **Statut** : famille de **PER-007** (constantes réécrites ailleurs), cas précis **nouveau**.

#### [DS-DUP-4] Vocabulaire des états du rappel en trois copies
- **Axe** : duplication
- **Point d'audit** : P4
- **Sévérité** : Mineur
- **Preuve** : `store.py:30-43` (`CALLBACK_FINAL_STATES`, `ABANDON_REASONS`), `store.py:101-102` (`CHECK` SQL), `core/callback_policy.py:15-23` ; `rg -c "abandoned_|delivered"` → `store.py:23`, `callback_policy.py:7`, `sender.py:2`.
- **Statut** : déjà connu **MNT-002** (backlog 999.1) ; revérifié, inchangé. Pas de proposition supplémentaire.

### Axe 3 — Goulots de performance

Aucun goulot significatif à l'échelle d'un poste : sondage 0,5 s / 1 s, une tâche à la fois.

#### [DS-PERF-1] `result_json` complet désérialisé pour n'en lire que `summary` et `artifacts`
- **Axe** : performance
- **Point d'audit** : —
- **Sévérité** : Mineur (coût mécanique certain, impact non profilé et vraisemblablement faible)
- **Preuve** : `jobs.py:52` (`json.loads(row.result_json)` à chaque `GET`) ; `core/payload.py:47` (à chaque essai de rappel) ; `engine.py:556-567` (`_cap_summary` reconstruit et encode le corps) ; `data` peut approcher 900 000 octets (`clash.py` `data_max_bytes`, `mcp_call.py:22`).
- **Constat** : un `GET` de suivi relit jusqu'à ~1 Mio de JSON inutilisé.
- **Refactoring proposé** : se résout avec DS-SCAL-1 (ne plus stocker `data`, ou le stocker dans une colonne séparée) ; aucune action isolée recommandée.
- **Statut** : **nouveau** (conséquence d'ARC-004).

#### [DS-PERF-2] Réclamation des rappels sans index
- **Axe** : performance
- **Point d'audit** : P1 (indirect)
- **Sévérité** : Mineur — **abaissé par la mesure**
- **Preuve** : sonde `probe_growth.py`, base réelle de 20 000 tâches et 20 000 rappels livrés : `claim_due_callback 0.85 ms/appel`, `claim_next 0.02 ms/appel`.
- **Constat** : le balayage de `callbacks` existe (pas d'index sur `state`/`next_attempt_at`) mais coûte moins d'une milliseconde à 20 000 lignes ; il faudrait des millions de tâches pour qu'il compte.
- **Refactoring proposé** : index partiel du backlog 999.1, sans urgence.
- **Statut** : déjà connu **DON-002** (backlog 999.1) ; la mesure de coût est **nouvelle** et justifie de le laisser en bas de pile.

#### [DS-PERF-3] Une ligne d'`events.jsonl` de plus de 1 Mio fige la lecture de progression
- **Axe** : performance
- **Point d'audit** : —
- **Sévérité** : Mineur
- **Preuve** : `engine.py:489-499` (`if end < 0: return` sans avancer `events_off`) ; la même tranche de 1 Mio est relue toutes les 0,5 s.
- **Statut** : déjà connu **FIA-004** (backlog 999.5) ; revérifié, inchangé.

### Axe 4 — Risques de scalabilité (croissance des données)

#### [DS-SCAL-1] La base grossit jusqu'à ~0,8 Mio par tâche à cause de `data`, stocké et jamais lu ; aucune purge possible
- **Axe** : scalabilité
- **Point d'audit** : P1 (la base est le support de la reprise), P5
- **Sévérité** : Majeur
- **Preuve** :
  - `engine.py:547-550` : `data` écrit dans `jobs.result_json` ; aucun chemin d'exécution ne le relit (DS-ARCH-1).
  - Sonde `probe_growth.py` (cycle de vie réel `insert_job` → `claim_next` → `finish` → `claim_due_callback` → `record_callback_result`) :
    `N=20000` sans `data` → `db MiB 20.4 audit rows 100000` ; `N=500` avec ~800 Ko de `data` → `db MiB 398.7`.
  - `store.py:109-112` : triggers `audit_no_update`/`audit_no_delete` ; aucun `DELETE FROM` dans `src/` (`rg`).
- **Constat** : ≈ 1 Ko et 5 lignes d'audit par tâche sans `data` ; ≈ 0,8 Mio par tâche `ifc.clash` volumineuse. À 10 tâches lourdes par jour, ≈ 3 Gio par an, sans moyen de purger l'audit sans migration.
- **Pourquoi c'est un problème** : croissance non bornée de l'unique fichier critique (`synchronous=FULL`, WAL), sauvegardes et copies plus lentes, et aucun bénéfice puisque `data` n'est lu par personne. L'estimation du council (3,4 Ko d'audit par tâche) sous-évalue d'un facteur ~250 le cas `ifc.clash`.
- **Refactoring proposé** : d'abord trancher DS-ARCH-1 (exposer ou retirer `data`) ; ensuite, si `data` n'est pas exposé, ne plus le persister (iso-fonctionnel pour l'API et le rappel) ; rétention et purge (backlog 999.2). Proposition P-04.
- **Statut** : rétention déjà connue **DON-001** (backlog 999.2, abaissé Mineur par le council) et `data` connu **ARC-004** ; la **mesure de croissance par `data`** et la réévaluation en Majeur sont **nouvelles**.

#### [DS-SCAL-2] Dossiers de tâche jamais purgés
- **Axe** : scalabilité
- **Point d'audit** : P5
- **Sévérité** : Mineur
- **Preuve** : `runner.example.toml:30-31` (purge laissée à l'utilisateur, dit par les auteurs) ; `clash.py:349-351` (`clashes.json` complet, non tronqué) ; images `snapshots/`, `conflits.bcf`, `job.log` sans plafond (`jobobject.py:187`).
- **Constat** : `<racine>/travail/<job_id>/` s'accumule sur le disque partagé avec Docker.
- **Refactoring proposé** : hors iso-fonctionnel ; à couvrir par la commande de purge du backlog 999.2 (même politique de rétention que la base).
- **Statut** : documenté par les auteurs ; couvert par l'intitulé de **999.2** (« rétention et purge ») sans y être nommé → **à préciser dans 999.2**.

#### [DS-SCAL-3] Les réponses 400 et 422 sont réessayées pendant toute la fenêtre de 24 h
- **Axe** : scalabilité (et fiabilité du rappel)
- **Point d'audit** : P1
- **Sévérité** : Mineur
- **Preuve** : `core/callback_policy.py:76` (`return Decision(RETRY_BACKOFF, f"http_{status}")` pour tout statut non traité) ; `next_delay` plafonné à `max_backoff_s` = 300 s (`callback_policy.py:79-85`) ; fenêtre 86 400 s ; chaque essai écrit une ligne d'audit non purgeable (`store.py:605-616`).
- **Constat** : une erreur client permanente (corps refusé, par exemple DS-ARCH-3) donne ≈ 290 essais et autant de lignes d'audit avant `abandoned_exhausted`, et n'est visible comme abandon qu'au bout de 24 h.
- **Refactoring proposé** : traiter 400/422 comme 401/403 (deux constats consécutifs puis `abandoned_rejected`). Changement de politique, non iso-fonctionnel → proposition P-07 soumise à décision.
- **Statut** : **nouveau**.

### Axe 5 — Maintenabilité

Mesures : radon `cc -n C` → 19 blocs en C ou D, dont 12 dans `src/deskgate` (max `mcp_call._call`
C(20), `paths._check_segments` C(17)) et 2 D dans le plugin (`clash._run` D(29), `_write_bcf` D(21),
déjà connues MNT-001) ; `mi` : tout le cœur en A sauf `engine.py` B (16,14). Le cœur se lit bien : les
docstrings de module énoncent la politique d'erreur réelle (`engine.py:1-13`, `sender.py:1-12`,
`supervisor.py:1-17`).

#### [DS-MAINT-1] `ARCHITECTURE.md` décrit la cible v0.2–v0.3 comme l'existant
- **Axe** : maintenabilité
- **Point d'audit** : **P4**
- **Sévérité** : Majeur (critère de publication explicite)
- **Preuve** : `ARCHITECTURE.md:28-40` (schéma : `/capabilities`, `/artifacts`, `/ui`, exécuteurs `python │ cli │ mcp`, « ordonnanceur par ressource », manifestes `plugin.yaml`, jetons et droits par plugin) vs `core/config.py:119` (`kind: Literal["python","mcp"]`), routes `api/routes_*.py` (5 routes), `api/app.py:36` (`openapi_url=None`), `store.py:371` (une tâche globale) ; tableau complet des 12 écarts dans `dev-senior-1-1-architecture.md` § « Écarts ». `README.md:8` annonce des plugins « ligne de commande ».
- **Constat** : le document de référence mêle sans marquage systématique ce qui existe et ce qui viendra ; certaines sections sont marquées « (v0.2) », pas le schéma d'ensemble ni §3, §4, §6.
- **Pourquoi c'est un problème** : un nouveau développeur cherchera `/capabilities`, l'exécuteur `cli` ou la concurrence par ressource ; P4 est non tenu tant que ce document n'est pas aligné.
- **Refactoring proposé** : documentaire — scinder « État v0.1 (livré) » / « Cible » ou marquer chaque élément. Proposition P-08.
- **Statut** : déjà connu **PER-003 (+ARC-010)** et **PER-004** (backlog 999.6) ; revérifié, toujours ouvert.

#### [DS-MAINT-2] Lien de clonage générique dans le guide d'installation
- **Axe** : maintenabilité
- **Point d'audit** : P5
- **Sévérité** : Mineur
- **Preuve** : `AGENTS.md:38` `git clone https://github.com/<organisation>/deskgate.git`.
- **Constat** : la première commande du guide exécutable par une IA (critère v0.4) échoue telle quelle.
- **Refactoring proposé** : renseigner l'URL au moment de la publication (décision de dépôt). Effort S.
- **Statut** : **nouveau** (PER-004 vise `README.md` et `ROADMAP.md`).

#### [DS-MAINT-3] `store.tx` ne fait pas de `ROLLBACK` si le `COMMIT` échoue
- **Axe** : maintenabilité
- **Point d'audit** : P1 (indirect)
- **Sévérité** : Mineur (sans effet aujourd'hui)
- **Preuve** : `store.py:142-152` : le `COMMIT` est dans `else:`, hors du `except BaseException` ; un `COMMIT` en `SQLITE_BUSY` laisse la transaction ouverte sur la connexion.
- **Constat** : sans conséquence actuelle, car chaque appelant jette sa connexion sur erreur (`engine.py:633`, `sender.py:244`, `closing(...)` dans `jobs.py`, `runtime.py:194-213`). C'est un invariant implicite : un futur appelant qui réutiliserait sa connexion après l'erreur hériterait d'une transaction ouverte.
- **Refactoring proposé** : `try: COMMIT except BaseException: ROLLBACK (supprimé si déjà fermée); raise`. Proposition P-09.
- **Statut** : **nouveau**.

#### [DS-MAINT-4] Plugins installés en mode éditable : le code exécuté suit l'arbre de travail du clone
- **Axe** : maintenabilité
- **Point d'audit** : P5
- **Sévérité** : Mineur (choix documenté)
- **Preuve** : `uv.lock` `source = { editable = "plugins/bim" }` et `"plugins/bim/bcf"` ; `AGENTS.md:131-134` (fichiers `_editable_impl_*.pth` vers le dépôt, « pris au prochain job ») ; le runner, lui, est copié par `uv tool install .` (`AGENTS.md:39`).
- **Constat** : un `git checkout` ou une modification en cours dans le dépôt change le plugin exécuté en production, alors que `deskgate_sdk/run.py` reste celui de l'installation du runner ; supprimer le clone casse les plugins.
- **Pourquoi c'est un problème** : pour l'auteur, c'est un confort assumé ; pour une distribution (P5) et pour la règle 8 (déterminisme), la version du plugin n'est plus attachée à une installation.
- **Refactoring proposé** : documenter `uv sync --no-editable` comme voie « utilisateur » et garder l'éditable pour le développement. Non iso-fonctionnel (mode d'installation) → suggestion S4.
- **Statut** : **nouveau** comme finding (comportement documenté par les auteurs ; LIV-002/LIV-004 portent sur le lock et les versions).

#### [DS-MAINT-5] Commentaires contredits par le code sur les imports `ctypes`/`subprocess`
- **Axe** : maintenabilité
- **Point d'audit** : P4
- **Sévérité** : Mineur
- **Preuve** : `jobobject.py:3-4` « Seul module … (avec `instance`) qui importe `ctypes`, et seul à importer `subprocess` » ; `instance.py:3` « Seul module … autorisé à importer `ctypes` » ; `scheduler.py:12,16` importe `ctypes` et `subprocess` (admis par `tests/architecture/test_import_boundaries.py`).
- **Refactoring proposé** : réécrire les deux docstrings en renvoyant au test qui fait foi. Effort S.
- **Statut** : **nouveau**.

## Plan de refactoring priorisé

Ordre : Critique → Majeur → Mineur, regroupé par zone. P-03 et P-04 dépendent d'une même décision
produit sur `data` : la prendre avant de toucher l'engine.

### P-01 — `sender.py` : isoler l'échec d'un rappel (DS-ARCH-2) — effort S
Test de caractérisation à écrire **d'abord** (`tests/fs/test_sender_retry.py`) : reprendre
`probe_poison.py` — deux rappels dus, client qui lève `RuntimeError` ; attendu après la correction :
`j1` en `pending` avec `next_attempt_at` dans le futur et `last_error_redacted == "RuntimeError"`, puis
`j2` tenté au tour suivant ; le thread ne passe pas `failed`.

Pseudo-diff :
```diff
 def tick(self) -> bool:
     now = self._wall()
     self.last_tick_at = now
     conn = self._connection()
     claim = store.claim_due_callback(conn, now, max_window_s=...)
     if claim is None:
         return False
+    try:
+        return self._process(conn, claim)
+    except store.OperationalError:
+        raise                       # base : politique du thread inchangée
+    except Exception as exc:        # erreur propre à cette ligne : elle ne bloque pas les autres
+        logger.exception("Rappel de la tâche %s : erreur interne.", claim.job_id)
+        after = self._wall()
+        delay = next_delay(claim.attempt, max_backoff_s=..., rng=self._rng)
+        state = ABANDONED_EXHAUSTED if after + timedelta(seconds=delay) >= claim.deadline else "pending"
+        store.record_callback_result(conn, claim, state=state, decision="internal_error",
+            http_status=None, error=type(exc).__name__,
+            next_attempt_at=None if state != "pending" else after + timedelta(seconds=delay), now=after)
+        return True
+
+def _process(self, conn, claim) -> bool:
-    if not self._host_allowed(...):   # corps actuel de tick() à partir d'ici, inchangé
+    if not self._host_allowed(...):
```
Iso-fonctionnalité attendue : tous les chemins nominaux (2xx, 4xx, 5xx, réseau, hôte refusé) passent
par `_process` sans changement ; `tests/fs/test_sender_policy.py`, `test_sender_retry.py`,
`test_sender_send.py`, `tests/e2e/test_callback_*.py` restent verts. Seul le chemin « exception
inattendue » change (réessai de la ligne au lieu de la mort du thread).
Risque résiduel : une erreur de programmation répétée devient silencieuse côté supervision ; elle reste
visible par `logger.exception` et l'audit `callback.attempt` (`decision: internal_error`). `maybe_delivered`
reste à 1 (prudent : on ignore si l'envoi a eu lieu).

### P-02 — Frontière worker : refuser `NaN`/`Infinity` (DS-ARCH-3) — effort S
Test de caractérisation d'abord (`tests/unit/`) : `parse_result(b'{"protocol":1,"ok":true,"summary":{"d":NaN}}')`
renvoie aujourd'hui `"valid"` (sonde `probe_nan.py`) ; le figer, puis le basculer en `"invalid"`.
```diff
 # core/worker_protocol.py
+def _no_constant(name: str) -> object:
+    raise ValueError(f"constante JSON non standard : {name}")
 ...
-        data = json.loads(raw)
+        data = json.loads(raw, parse_constant=_no_constant)
 # deskgate_sdk/run.py (_write_atomic)
-        json.dump(obj, f, ensure_ascii=False)
+        json.dump(obj, f, ensure_ascii=False, allow_nan=False)
```
Côté SDK, `ValueError` est déjà capturée par le `except BaseException` de `main` (`run.py:119`) et produit
un `result.json` d'erreur. Appliquer le même `parse_constant` à `parse_event` (`worker_protocol.py:73`).
Preuve attendue : `tests/unit/test_sdk_contract.py` et les tests `test_engine_*` verts ; nouveau test :
tâche à résumé `NaN` → `failed/invalid_result`, rappel JSON strict.
Risque résiduel : un plugin tiers qui renvoyait `NaN` « avec succès » passe en échec — c'est
l'intention ; le signaler dans le changelog. **Non iso-fonctionnel sur ce seul cas** (correction).

### P-03 — Résultat de `mcp.call` (DS-ARCH-1) — décision produit requise, effort S à M
Aucune option n'est iso-fonctionnelle ; deux directions, à trancher par l'auteur (voir S1) :
- **Option A (la plus petite)** : le worker MCP place la sortie de l'outil dans `summary` quand elle
  tient sous le plafond, sinon l'artefact actuel.
  ```diff
  # workers/mcp_call.py
  -    return {"summary": {"server": name, "tool": tool, "is_error": False}, "data": data}
  +    return {"summary": {"server": name, "tool": tool, "is_error": False, "result": data}}
  ```
  Le plafond du rappel (`engine._cap_summary`) déporte déjà un `summary` trop gros dans `summary.json`.
- **Option B (contrat)** : exposer `data` dans `GET /jobs/{id}` (et éventuellement le rappel) sous la même
  règle de 1 Mio ; ferme aussi ARC-004 pour tous les plugins.
Test à écrire d'abord : variante API de `tests/proc/test_mcp_paths_real.py` qui lit la valeur par
`GET /jobs/{id}` (ou par le corps reçu par `tests/_support/fake_n8n.py`) au lieu de `row.result_json`.
Risque résiduel : option A change la forme de `summary` pour les workflows existants (aucun aujourd'hui,
`n8n/README.md:51`).

### P-04 — Ne plus persister `data` s'il n'est pas exposé (DS-SCAL-1, DS-PERF-1) — effort S
Conditionnel à P-03 option A (ou à la décision « `data` hors contrat »).
```diff
 # engine.py:_evaluate
-            result_json = json.dumps({"summary": parsed.summary, "data": parsed.data, "artifacts": artifacts}, ...)
+            result_json = json.dumps({"summary": parsed.summary, "artifacts": artifacts}, ...)
```
Iso-fonctionnalité : `build_callback` et `job_view` ne lisent que `summary`/`artifacts`
(`core/payload.py:54-55`, `jobs.py:65-66`) → rappel et API identiques octet pour octet. Test à adapter :
`tests/proc/test_mcp_paths_real.py:166` (lit `data` en base) ; ajouter un test « `result_json` sans
`data` ». Risque résiduel : les lignes déjà écrites gardent leur `data` (purge 999.2). La rétention
(migration 3, `deskgate purge`) reste le chantier du backlog 999.2 ; y ajouter les dossiers de tâche
(DS-SCAL-2).

### P-05 — Une seule fonction d'aiguillage des chemins (DS-DUP-1) — effort S
```diff
 # core/paths.py
+def convert_params(kind, params, path_params, mcp_path_arguments, mappings, roots, resolver):
+    if kind == "mcp":
+        return convert_mcp_arguments(params, mcp_path_arguments, mappings, roots, resolver)
+    return convert_path_params(params, path_params, mappings, roots, resolver)
 # jobs.py:117-132 et engine.py:304-319
-            if cap.kind == "mcp": convert_mcp_arguments(...) else: convert_path_params(...)
+            convert_params(cap.kind, raw, cap.path_params, cfg.mcp_path_arguments(), cfg.mappings(), cfg.paths.allowed_roots, resolver)
```
Iso-fonctionnel (même appel, même ordre). Tests à garder verts : `tests/fs/test_submit_path_params.py`,
`test_engine_launch_params.py`, `test_paths_real.py`, `tests/proc/test_mcp_paths_real.py`. `core/paths.py`
reste pur (aucun import interdit par `test_import_boundaries.py`). Risque résiduel : nul.

### P-06 — Extraire la construction du lancement (DS-ARCH-4) — effort M
`core/launch.py` : `@dataclass(frozen=True) class LaunchPlan(python, entry, sys_path, settings, extra_env)`
et `build_launch(cap, params, config, runner_python) -> LaunchPlan` reprenant `engine.py:323-359` à
l'identique ; `_launch_inner` n'appelle plus que `build_launch`, puis fait les effets (`mkdir`,
`input.json`, `launcher`). Test de caractérisation d'abord : pour une capacité `python` et une `mcp`
à deux serveurs, figer le contenu d'`input.json` et de `LaunchSpec.env` produits aujourd'hui (le test
SEC-005 `AUTRE_SECRET` absent existe déjà côté processus réel). Iso-fonctionnel ; `radon` attendu :
`_launch_inner` ≤ B. Risque résiduel : faible, zone couverte par `tests/fs/test_engine_*`.

### P-07 — 400/422 traités comme refus confirmés (DS-SCAL-3) — décision requise, effort S
```diff
 # core/callback_policy.py
-    if status in (401, 403, 404):
+    if status in (400, 401, 403, 404, 422):
         if prev_status != status:
             return Decision(RETRY_SHORT, f"confirm_{status}")
         kind = ABANDONED_STALE if status == 404 else ABANDONED_REJECTED
```
**Non iso-fonctionnel** (politique de réessai). Test : deux 400 consécutifs → `abandoned_rejected`.
Risque résiduel : un proxy intermédiaire qui renverrait un 400 transitoire ferait abandonner trop tôt
(aucun proxy dans la topologie actuelle, `trust_env=False`).

### P-08 — `ARCHITECTURE.md` : séparer livré et cible (DS-MAINT-1) — effort M (documentation)
Ajouter en tête une section « État livré en v0.1 » (5 routes, exécuteurs `python` et `mcp`, une tâche à la
fois, `[mcp_servers]` dans `runner.toml`, `deskgate-bcf write` seul, annulation coopérative puis
`TerminateJobObject`) et marquer « cible vX » sur chaque élément absent, en reprenant le tableau d'écarts
de la cartographie ; corriger `README.md:8` (« ligne de commande ») et `AGENTS.md:38` (DS-MAINT-2).
Preuve attendue : chaque affirmation de la section « livré » pointe un `fichier:ligne`.

### P-09 — Petites corrections iso-fonctionnelles (DS-MAINT-3, DS-MAINT-5, DS-DUP-3) — effort S
- `store.tx` : `COMMIT` dans un `try` avec `ROLLBACK` (supprimé par `contextlib.suppress`) avant de relancer.
  Test : connexion factice dont le `COMMIT` lève → `in_transaction` faux ensuite.
- Docstrings de `jobobject.py` et `instance.py` alignées sur `test_import_boundaries.py`.
- `core/exit_codes.py` pour les codes 2 à 6 et leurs libellés, importé par `runtime`, `supervisor`,
  `scheduler` ; tests `doctor` et `test_serve_supervision.py` verts.

## Suggestions produit hors périmètre

- **S1 — Contrat du résultat** : décider le sort de `data` (exposé dans `GET` et/ou le rappel, ou retiré
  du protocole) ; en l'état, `mcp.call` est inutilisable depuis n8n (DS-ARCH-1). C'est le seul point que
  je recommande de trancher avant la publication v0.1.
- **S2 — Validation des sorties** : refuser les flottants non finis à la frontière (P-02) et l'écrire
  dans le contrat `docs/contrats/` et le README des plugins.
- **S3 — Délai maximal en file** : un `queue_timeout` (ou une échéance absolue transmise par n8n) qui
  conclut `cancelled`/`expired` une tâche restée trop longtemps `queued`, cohérent avec la durée du Wait
  n8n (DS-ARCH-5).
- **S4 — Installation « utilisateur » des plugins** non éditable (`uv sync --no-editable`), l'éditable
  restant la voie développeur (DS-MAINT-4).
- **S5 — Purge des dossiers de tâche** dans la même commande que la rétention de la base (DS-SCAL-2).

## Ce qui n'a pas pu être vérifié

- **Réponse réelle de n8n 2.43.8** à un corps contenant `NaN` (400 supposé) : non testé contre n8n
  (aucun serveur lancé, consigne). La dégradation `GET` en 500 est, elle, prouvée (sonde).
- **Déclencheur réel de DS-ARCH-2** : aucune exception non-HTTP atteignable n'a été trouvée dans
  `Sender.tick` ; seul le mécanisme d'amplification est prouvé.
- **Production de `NaN` par `ifc.clash`** (`grouping.py`, `context.py`, `render.py` lus par signatures
  seulement en Phase 1) et par des serveurs MCP tiers : non observée.
- **`deskgate doctor`, tâche planifiée, contexte MSIX** : non exécutés (aucune tâche planifiée, jamais
  `%LOCALAPPDATA%\Deskgate`) ; je m'en remets à la certification LIV-001 du council pour P5.
- **Suite de tests complète et couverture** : non exécutées (consigne) ; 48 tests ciblés verts
  (`test_store_recovery`, `test_sender_retry`, `test_supervisor_restart`, architecture).
- **Déterminisme du plugin** (règle 8) sous plusieurs threads `ifcopenshell.geom` : non éprouvé.
- **SDK `mcp` 2.3** : liste blanche d'environnement propre au SDK et imbrication de son Job Object avec
  celui du runner non relues dans le code du SDK (zones non élucidées de la cartographie).
- **Licence des dépendances transitives** des environnements de plugins au-delà d'`ifcclash` : non
  listées par outil ici (`tests/plugins/test_licenses.py` existe, non exécuté).

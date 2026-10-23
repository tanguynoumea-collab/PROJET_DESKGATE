# Certification dev-senior — Deskgate, findings de l'audit 1-1 après la phase 5.4

> **Mode** : re-vérification ciblée (certification post-correction), pas un audit complet. Posture
> dev-senior : lecture seule sur le code du dépôt (ce fichier est le seul écrit), preuves `fichier:ligne`.
> **Commit vérifié** : `8c48f9b` (arbre propre ; fins de ligne CRLF en copie de travail sur
> `sender.py`, `store.py`, `cli.py`, LF dans l'index, `core.autocrlf=true`, sans effet sur le contenu).
> **Référence** : `.arthemis/reports/dev-senior-1-1.md` (DS-ARCH-1, DS-ARCH-2, DS-ARCH-3, DS-SCAL-1,
> DS-MAINT-1 ; plan P-01 à P-04, P-08).
>
> Vérité-terrain :
> - sondes réécrites dans le scratchpad de la session
>   (`C:\Users\Tanguy\AppData\Local\Temp\claude\C--Users-Tanguy-Documents-PROGRAMMES-DEV-PROJET-DESKGATE\55069796-9b7f-4c99-9454-c9f37460a42e\scratchpad\probes\`) :
>   `probe_poison.py`, `probe_nan.py`, `probe_nan_submit.py`, `probe_mcpdata.py`, `probe_growth.py`,
>   `probe_purge_pending.py`. Elles passent par les vraies fonctions (`Sender.tick`/`run`, `Engine`,
>   `parse_result`, `build_callback`, `job_view` via `TestClient`, `store.purge_data`, CLI Typer réelle).
>   Lancées par `uv run python` depuis la racine (Python 3.14.4, SQLite 3.50.4), bases dans `probes\dbs\`
>   uniquement ;
> - tests ciblés : `uv run pytest -p no:cacheprovider` sur les 11 fichiers de preuve des SUMMARY
>   + `test_sender_retry`, `test_store_recovery`, `test_supervisor_restart`, `tests/architecture`
>   → **200 passés, 1 ignoré** (lien symbolique, mode développeur désactivé), 61 s ;
>   `pytest -m e2e tests/e2e/test_callback_flow.py tests/e2e/test_callback_restart.py` → **8 passés**.

## Verdicts

| Finding | Verdict | Preuve principale |
|---|---|---|
| **DS-ARCH-1** `mcp.call` : résultat jamais transmis à n8n | **FERMÉ** | `core/payload.py:35-38` (`result_parts`, source unique), `:61-70` (`data` dans le corps) ; `jobs.py:51,67` (`data` dans `GET`). Sonde `probe_mcpdata` (Engine réel, Sender réel, faux n8n, `TestClient`) : rappel `data={'structured_content': {'answer': 42}, 'content': [...]}`, même `data` dans `GET 200`. Cas `result.json` de 1 048 541 o : rappel de 244 o, `data={'path': '/data/travail/<id>/data.json', 'truncated': True}`, `data.json` de 1 048 447 o égal au `data` d'origine, même marqueur dans `GET` (`engine.py:555-583`). |
| **DS-ARCH-2** Sender : une ligne en erreur bloque tous les rappels, runner arrêté | **FERMÉ** | `sender.py:133-139` (exception de ligne → `_record_internal_error`, seules `DatabaseError`/`StoreError` remontent), `:155-175`. Sonde `probe_poison` : `result_json` corrompu sur `j1` → `tick 0` : `j1` `(1, 1, 'pending', 'JSONDecodeError')`, `tick 1` : `j2` `delivered`, n8n reçoit `/webhook-waiting/2` ; client qui lève partout → `j1` puis `j2` tentés (`RuntimeError` chacun) ; boucle `run()` réelle 4 s avec ligne empoisonnée permanente → `failed = False`, `status = ok`. Signature absente de l'audit ; journal formaté par `RedactingFormatter` : `signature=***`, valeur brute absente. |
| **DS-ARCH-3** `NaN`/`Infinity` traversent le contrat worker | **FERMÉ** (sortie du plugin) | `core/worker_protocol.py:71-84` (`parse_constant` + `parse_float` finis), `:90,115` ; écritures en `allow_nan=False` : `deskgate_sdk/run.py:58,82`, `core/payload.py:30`, `engine.py:550,580,586,605`, `workers/mcp_call.py:122,125`. Sonde `probe_nan` : `NaN`, `Infinity`, `-Infinity`, `1e999`, `-1e999` imbriqué dans `data`, `NaN` dans une erreur plugin → `invalid` ; `1e308` → `valid` ; `parse_event` `NaN`/`1e999` → `None` ; `encode`, `build_callback` et `_write_atomic` du SDK lèvent `ValueError` (pas de `.tmp` résiduel). Le côté **entrée** (`POST /jobs`) n'est pas couvert : nouveau candidat DS2-1. |
| **DS-SCAL-1** Croissance de la base par `data`, aucune purge | **FERMÉ** (avec réserve, candidat DS2-4) | `store.py:643-674` (`purge_data`, un `UPDATE json_set` gardé par `json_valid`) ; `cli.py:88-124` (`deskgate purge`). Sonde `probe_growth` (cycle de vie réel) : 2 000 tâches sans `data` → 2,1 Mio ; +300 tâches à ~800 Ko → 232,8 Mio ; `purge_data` → 301 tâches en 0,56 s (300 lourdes + 1 dont le rappel a été clos en `abandoned_exhausted` par la sonde), 58 691 pages libres ; +300 tâches lourdes ensuite → 234,2 Mio (espace réutilisé). Ignorées sans erreur : JSON invalide, `NaN` hérité, `data` liste, marqueur `truncated`, tâche récente ; rappel `pending` jamais purgé (`probe_purge_pending` : 0). Rejeu → 0 (idempotent). CLI : code 0 et message ; base absente → code 1 ; `-1` → code 2. |
| **DS-MAINT-1** `ARCHITECTURE.md` décrit la cible comme livrée | **PARTIEL** | Tenu : la section « État livré en v0.1 » (`ARCHITECTURE.md:12-77`) dit vrai ; ses 36 références tombent sur le bon code (10 relues à la main, ex. `engine.py:451` `cancel.flag`, `store.py:96-97` `jobs_idem`, `deskgate_bcf/cli.py:50` `write`) ; les 12 écarts du cycle 1 sont marqués « cible vX » ; `README.md:8` corrigé (« ligne de commande en v0.2 »). **Reste** : trois phrases du corps présentent comme livré ce qui ne l'est pas (DS2-3). P4 n'est donc pas encore tenu sans réserve. |

## Nouveaux findings (candidats)

### DS2-1 — `POST /jobs` accepte `NaN`/`Infinity`/`1e999` dans `params` ; le plugin reçoit `null` — **Mineur**
- **Preuve** : sonde `probe_nan_submit` (`TestClient`, corps brut) : `NaN`, `Infinity`, `1e999` → **202** ;
  `jobs.params_json` stocké `{"x": NaN}` / `{"x": Infinity}` (`jobs.py:144`, `json.dumps` sans
  `allow_nan=False`) ; audit `job.queued` avec `"params": {"x": NaN}` (`store.py:233,240`) ;
  `input.json` produit par l'engine : `{'x': None}` (`engine.py:374`, `model_dump_json` de Pydantic
  sérialise un non-fini en `null`).
- **Constat** : la frontière stricte de DS-ARCH-3 n'existe qu'en sortie. En entrée, la valeur est altérée
  sans erreur (règle 8 : mêmes entrées, mêmes sorties) et la base et l'audit contiennent du JSON non
  standard.
- **Pourquoi Mineur** : n8n (`JSON.stringify`) ne produit jamais `NaN` ; seul un client écrit à la main
  y arrive. Défaut antérieur à la phase 5.4, pas une régression.
- **Proposition** : refuser en 422 à la soumission (analyse stricte du corps, ou validateur de
  `SubmitRequest.params` qui rejette les flottants non finis) ; `allow_nan=False` sur `jobs.py:144` et `_audit`.

### DS2-2 — Le renvoi minimal après un 413 efface aussi les marqueurs `{path, truncated}` — **Mineur**
- **Preuve** : `core/payload.py:41-43` (`minimal` remplace `summary` et `data` par `{"truncated": true}`) ;
  sonde `probe_mcpdata`, cas « 413 puis 200 » : rappel 1 `data={'truncated': True}`,
  `summary={'truncated': True}`.
- **Constat** : si `data` avait déjà été déporté (`{"path": ".../data.json", "truncated": true}`, une
  centaine d'octets), le renvoi minimal supprime le chemin : n8n ne sait plus où lire le résultat sans
  appeler `GET`. Comportement documenté (`ARCHITECTURE.md:47-49`, `:270-271`), mais étendu à `data` par 5.4.
  Sur le même sujet, `mcp.call` produit un troisième marqueur, `{"truncated": true}` sans chemin, avec
  l'artefact `mcp_result` (`workers/mcp_call.py:122-127`) : trois formes de « tronqué » pour n8n.
- **Proposition** : dans `minimal`, conserver une valeur déjà réduite à un marqueur `{path, truncated}` ;
  à terme, une seule forme de marqueur (chemin compris) pour `mcp.call`.

### DS2-3 — Trois phrases d'`ARCHITECTURE.md` décrivent encore une cible comme livrée — **Mineur** (rend DS-MAINT-1 partiel)
- `ARCHITECTURE.md:157` « Plafond de mémoire et de threads transmis aux plugins par variables
  d'environnement » : faux en v0.1. La mémoire passe par le Job Object (`memory_mb`, `engine.py:389`),
  les threads par `settings.threads` du plugin (`plugins/bim/src/deskgate_bim/clash.py:280`) ; aucune
  variable de ce type n'est posée (`core/env.py:7-42`, liste blanche plus `PYTHONUTF8`).
- `ARCHITECTURE.md:250-255` : l'exemple `POST /jobs` contient `"callback": { "url": ..., "headers": {} }` ;
  `CallbackSpec` est `extra="forbid"` avec `url` seul (`core/jobspec.py:33-36`). Vérifié :
  `ValidationError callback.headers — Extra inputs are not permitted`, donc 422 si on copie l'exemple.
- `ARCHITECTURE.md:306-307` : « Secrets des plugins dans le gestionnaire d'identifiants Windows » :
  aucun `keyring` dans `src/` (la pile le reporte à la v0.2) ; non marqué « cible ».
- Hors du périmètre de DS-MAINT-1, mais dans le critère P4 et le plan P-08 : `AGENTS.md:38`
  `git clone https://github.com/<organisation>/deskgate.git` toujours générique (DS-MAINT-2, ouvert).
- Le verrou `tests/unit/test_architecture_doc.py` ne couvre que la section livrée : ces phrases du
  corps lui échappent.

### DS2-4 — La rétention dépend d'une commande manuelle que rien ne rappelle — **Mineur**
- **Preuve** : purge manuelle par décision (SUMMARY 05.4-04 : « pas au démarrage, sans clé de config ») ;
  seule mention côté utilisateur : `AGENTS.md:202` (dépannage) ; `doctor.py` ne lit ni la taille de
  `deskgate.db` ni l'ancienneté des `data`.
- **Constat** : sans action de l'utilisateur, la croissance mesurée au cycle 1 (≈ 0,8 Mio par tâche
  lourde) reste la même ; le fichier ne rétrécit jamais (pas de `VACUUM`, documenté). Les dossiers de
  tâche, désormais aussi `data.json`, restent non purgés (DS-SCAL-2, ouvert).
- **Proposition** : un avertissement de `deskgate doctor` au-delà d'un seuil de taille, ou l'appel
  périodique de `purge_data` par le runner. Choix produit, à trancher par l'auteur.

### Observations sans finding
- Une ligne écrite avant 5.4 avec `NaN` dans `result_json` ferait encore un `GET` en 500 et des réessais
  `internal_error` pendant 24 h. Sans objet : aucun utilisateur, rien à migrer (CLAUDE.md, « Stade »).
- Un entier JSON de plus de 308 chiffres passe la frontière (`valid`) et devient `Infinity` côté
  JavaScript. Négligeable.
- `plugins/bim/src/deskgate_bim/clash.py:350` et `bcfjob.py:31` écrivent leurs artefacts JSON sans
  `allow_nan=False`. Si un `NaN` apparaît, le résultat est déjà refusé par le SDK (la tâche finit
  `failed`), mais `clashes.json` reste sur le disque avec du JSON non standard.
- Une ligne en `internal_error` garde `maybe_delivered=1` alors que rien n'est parti (corps illisible).
  C'est le risque résiduel accepté au cycle 1 (P-01).
- Le traceback de `logger.exception` (`sender.py:159`) contient l'URL complète si l'exception la cite ;
  elle est masquée par `RedactingFormatter` sur tous les handlers du runner (`runtime.py:69,94,116`).
  `RedactingFilter` ne masque pas `exc_text` : la protection repose sur le formateur seul.

## Non vérifié
- Réception réelle par n8n 2.43.8 de `data` d'un `mcp.call` (05.4-D2) : aucun n8n lancé.
- `tests/proc/test_mcp_paths_real.py:97` (lien symbolique) ignoré : privilège absent sur ce poste.
- Suite complète (1032 + 33 e2e) et `uv build --all-packages` : non rejoués, je reprends le gate de
  l'exécuteur ; seuls les 200 tests ciblés et 8 e2e de rappel ont été rejoués.
- `purge_data` sous SQLite 3.45 (Python 3.11, plancher de la CI) : sondé seulement sous 3.50.4.
- Purge concurrente d'un runner actif (verrou `BEGIN IMMEDIATE`, `busy_timeout` 5 s) : non éprouvée sous charge.

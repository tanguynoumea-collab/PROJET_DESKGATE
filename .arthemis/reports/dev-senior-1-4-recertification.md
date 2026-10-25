# Dev senior, cycle 1 : re-certification ciblée 05.4-D5 (DS3-1, DS3-2, DS2-2)

> Mode : re-certification ciblée, en lecture seule sur le code du dépôt. Seul fichier écrit : ce rapport.
> Commit : `8ee2d50` (HEAD, `main`, arbre propre avant l'écriture du rapport). Plans contrôlés : 05.4-08 (`0e1eb6d`,
> `fd01ea9`, `9fa9d2e`) et 05.4-09 (`8f67527`, `c7ff968`, `8bec4b1`). Base : `dev-senior-1-3-recertification.md`,
> `05.4-08-SUMMARY.md`, `05.4-09-SUMMARY.md`, diffs des commits `fix`.
>
> Vérité-terrain :
> - sondes dans le scratchpad
>   (`C:\Users\Tanguy\AppData\Local\Temp\claude\C--Users-Tanguy-Documents-PROGRAMMES-DEV-PROJET-DESKGATE\55069796-9b7f-4c99-9454-c9f37460a42e\scratchpad\probes3\`) :
>   `probe_mcp_big.py` (Engine, worker `deskgate_sdk/run.py` et mini serveur MCP réels, rappel par `build_callback`,
>   `GET` par `TestClient`), `probe_doc_refs.py`, `probe_purge.py`, `probe_purge_perf.py`,
>   `probe_purge_perf_timing.py`, `probe_413_marker.py` et `probe_marker_edges.py` (rejoués de `probes2`).
>   Lancées par `uv run python` depuis la racine (Python 3.14.4, SQLite 3.50.4), bases dans `probes3\dbs\` seulement ;
> - tests ciblés : `uv run pytest -p no:cacheprovider tests/proc/test_mcp_call.py tests/unit/test_architecture_doc.py
>   tests/unit/test_text_bytes.py tests/fs/test_store_purge.py tests/unit/test_payload.py tests/fs/test_sender_send.py`
>   → **90 passés** (32 s) ; `tests/architecture/test_import_boundaries.py` → **29 passés**.

## Verdicts

| Point | Verdict | Preuve principale |
|---|---|---|
| **DS3-1** — seuil `mcp.call` en caractères | **FERMÉ** | `workers/mcp_call.py:123-124` mesure `len(json.dumps(..., ensure_ascii=False).encode("utf-8"))`, cohérent avec l'écriture UTF-8 non échappée de `result.json` (`deskgate_sdk/run.py:58`). Sonde `probe_mcp_big` : `echo` 200 000 « € » (1 200 081 o) → **`succeeded`**, `data == {"truncated": true, "artifact": "mcp_result"}`, `artifacts=['mcp_result']`, `mcp-result.json` 1 200 081 o, rappel 297 o, `GET` identique ; bornes exactes (texte « € » + « x » calé à l'octet) : **899 999 o → en ligne** (`result_json` 900 092 o, rappel 900 176 o, aucun artefact), **900 001 o → déporté** (marqueur, `mcp-result.json` 900 001 o). Doc : « octets » à `ARCHITECTURE.md:50` et `:201` ; les 37 références `fichier:ligne` (`symbole`) du document tombent **à la ligne exacte** (aucune dans la tolérance ±2, aucune fausse), dont `mcp_call.py:130` et `store.py:643`. |
| **DS3-2** — purge plus large qu'`is_marker` | **FERMÉ** (réserve doc n8n, DS4-3) | `store.py:662-682` : candidats en SQL, filtre `is_marker` (`store.py:18`, `:677`) importé de `core/payload.py:44` ; même fonction que le renvoi minimal (`payload.py:58-64`, appelé par `sender.py:198-199`). Sonde `probe_purge` (`purge_data` réelle) : `ifc.clash` à `truncated` métier vrai **purgé** ; les quatre marqueurs `{path,truncated}`, `{truncated,artifact}`, `{truncated,error}`, `{truncated}` **conservés** ; faux marqueurs (`truncated: 1`, `path` de 4 097 car., `path` entier) purgés ; `{}` et liste conservés ; JSON invalide, `NaN` hérité (avec et sans `truncated`), `Infinity` hérité **ignorés sans erreur** ; rejeu → **0** ; `callbacks` identiques ; audit : préfixe identique, une seule ligne ajoutée `data.purged {"count": 7, …}` ; `summary`/`artifacts` des purgées intacts ; tâche au rappel non final intacte. Cœur sans BIM : `store.py` n'importe que `core.payload` et `core.redact`, aucun `deskgate_bim`/`ifcopenshell`/`bcf` dans `src/` ; `test_import_boundaries` vert. |
| **DS2-2** — renvoi minimal après 413 | **FERMÉ** (inchangé) | Rejeu `probe_413_marker` : `data` déporté → rappel 1 (220 o) `data={'path': '/data/travail/<id>/data.json', 'truncated': True}`, `data.json` 1 048 507 o égal au `data` d'origine, `GET` même marqueur ; `summary` déporté → marqueur `summary.json` gardé ; 413, 413, 200 → marqueur gardé aux deux renvois, `delivered` en 3 essais. (La ligne « summary.json égal à data d'origine : False » est un artefact de la sonde, qui compare `summary.json` au `data` vide.) |
| **DS2-2** — marqueur `mcp.call` | **FERMÉ** | Voir DS3-1 : ASCII et non ASCII, sous et au-dessus du seuil, rappel et `GET` identiques (`data` et `artifacts`). Le marqueur `{truncated, artifact}` est reconnu par `is_marker` (rejeu `probe_marker_edges`) et donc conservé au renvoi minimal comme à la purge. |
| **DS2-2 dans son ensemble** | **FERMÉ** | Les deux moitiés tiennent par la même règle (`payload.is_marker`), pour les trois consommateurs : renvoi minimal, purge, et (par construction) `GET`. |

## Régressions cherchées (05.4-08, 05.4-09)

- **05.4-08** : diff de deux lignes (`mcp_call.py:122-124`) ; pour l'ASCII, octets = caractères : comportement
  identique. Le seuil compte un `json.dumps` de plus en `.encode` (≈ 1 Mo de copie, une fois par appel) : négligeable.
  Le mini serveur (`tests/mcp_fake/mini_server.py:27`) gagne un paramètre `char` à défaut `"x"` : tests existants
  inchangés.
- **05.4-09, transaction** : SELECT et `executemany` par `id` dans le même `BEGIN IMMEDIATE` (`store.py:659`) :
  pas de fenêtre entre lecture et écriture. Une exception Python (y compris dans `json.loads`) fait `ROLLBACK`
  (`store.py:148-150`) ; sondé : imbrication de 900 et 990 niveaux avec `truncated: true` → purge normale, pas de
  `RecursionError`.
- **05.4-09, durée sous verrou** (`probe_purge_perf_timing`, sans `tracemalloc`) : 20 000 `data` de 2 Ko + 2 000
  marqueurs → nouveau 2,75 s, ancien SQL (reconstitué depuis `c7ff968^`) 4,04 s ; 40 000 → 7,17 s contre 10,09 s.
  Mesures bruitées (disque), mais **aucune régression de durée** : l'`UPDATE` par clé est aussi rapide que l'`UPDATE`
  filtré. La durée absolue du verrou est un défaut antérieur (DS4-2).
- **05.4-09, mémoire** : **régression** (DS4-1). `fetchall()` (`store.py:673`) charge le texte complet de `data` de
  chaque candidat dont `truncated` vaut `true` ; l'ancien code ne lisait rien en Python.

## Nouveaux findings (candidats)

### DS4-1 — `purge_data` charge en mémoire tous les gros `data` à `truncated` métier — **Mineur**
- **Preuve** : `store.py:663-664` (`CASE WHEN json_type(...,'$.data.truncated') = 'true' THEN json_extract(...,'$.data')`)
  puis `.fetchall()` (`:673`) : tous les textes restent en mémoire jusqu'à la fin du filtre (`:674-678`). Sonde
  `probe_purge_perf` : 300 `data` `ifc.clash` plafonnés de 880 Ko → **pic Python 260 Mo**, 3,0 s ; soit ≈ 0,87 Mo par
  ligne, linéaire. Le cas visé par DS3-2 est justement celui-ci : un `ifc.clash` plafonné peut atteindre ≈ 1 Mio de
  `data` en ligne (plafond de rappel, `payload.py:18`). 1 000 résultats de ce type ≈ 0,9 Go pour une commande CLI.
- **Constat** : le commentaire `store.py:660-661` (« le texte de data n'est lu que si truncated vaut true ») est exact,
  mais cette condition ne filtre rien pour `ifc.clash`. Un marqueur a au plus 4 clés de ≤ 4 096 caractères
  (`payload.py:19-20`), donc ≤ ≈ 16,5 Ko : tout texte plus long n'est pas un marqueur.
- **Proposition iso-fonctionnelle** : ne lire le texte que s'il peut être un marqueur, par exemple
  `CASE WHEN json_type(…,'$.data.truncated')='true' AND length(json_extract(…,'$.data')) <= 20000 THEN json_extract(…) ELSE '{}' END`
  (`'{}'` → `is_marker` faux → purgé), ou `(SELECT count(*) FROM json_each(result_json,'$.data')) <= 4`. Test : pic
  mémoire borné avec quelques centaines de `data` de 1 Mo. `is_marker` reste le seul juge.

### DS4-2 — La purge tient le verrou d'écriture plusieurs secondes ; le runner attend au plus 5 s — **Info** (antérieur)
- **Preuve** : un seul `BEGIN IMMEDIATE` pour toute la purge (`store.py:659`) ; connexions du runner à
  `busy_timeout=5000` (`store.py:134`, `:137`). Sonde : 40 000 lignes → 7 à 10 s de verrou (ancien et nouveau code) ;
  un écrivain concurrent a attendu 5,03 s, à la limite de `SQLITE_BUSY`.
- **Constat** : non introduit par 05.4-09 (l'ancien `UPDATE` unique tenait le verrou aussi longtemps), mais
  `AGENTS.md:202` présente la purge comme un geste courant sans dire d'arrêter le runner. Avec un runner actif et une
  grosse base, l'engine ou le sender peuvent prendre une erreur de base pendant la purge.
- **Proposition** : purger par lots (par exemple 1 000 `id` par transaction), ou documenter « runner arrêté ». Rien
  d'obligatoire en v0.1 mono-utilisateur.

### DS4-3 — `data.truncated` d'`ifc.clash` reste ambigu côté n8n — **Info** (reste de DS3-2, point 2)
- **Preuve** : `plugins/bim/src/deskgate_bim/clash.py:344` (`"truncated": truncated` dans `data`) ;
  `ARCHITECTURE.md:289-291` le mentionne désormais, mais seulement à propos de la rétention ; `n8n/README.md:59-62`
  décrit les marqueurs sans prévenir qu'un `data` `ifc.clash` peut porter `truncated: true` avec d'autres clés.
- **Constat** : un workflow qui teste `$json.body.data.truncated` croira à un repli sur un résultat `ifc.clash`
  plafonné. La règle juste (forme exacte du marqueur) est écrite, mais pas ce piège.
- **Proposition** : une phrase dans `n8n/README.md` (« tester la forme complète, pas la seule clé `truncated` ;
  `ifc.clash` porte un champ métier de ce nom ») ; le renommage `clashes_truncated` reste une suggestion produit.

### Observations sans finding
- Un `data` dont le texte fait exactement 900 000 o n'est pas atteignable avec la forme `mcp.call` du mini serveur
  (surcoût fixe impair de 81 o, texte doublé) ; les bornes 899 999 et 900 001 encadrent la comparaison stricte
  `> DATA_MAX_BYTES` (`mcp_call.py:124`).
- Un `data` hérité `{"truncated": true, "path": "\ud800"}` (surrogate isolé, JSON valide) est un marqueur pour
  `is_marker` et reste conservé : cohérent avec le renvoi minimal.
- `1e999` dans un `result_json` hérité est du JSON valide pour SQLite : la ligne est purgée sans erreur.

## Non vérifié
- Suite complète et `pytest -m e2e` non relancés (le SUMMARY 05.4-09 annonce 1053 passés, 2 ignorés, 33 e2e verts).
- n8n 2.43.8 réel : le 413 vient du faux n8n (`tests/_support/fake_n8n.py`).
- Comportement réel de l'engine et du sender pendant une purge longue (DS4-2) : seul un écrivain SQLite nu a été
  mesuré.

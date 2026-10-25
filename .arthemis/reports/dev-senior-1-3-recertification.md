# Dev senior, cycle 1 : re-certification ciblée (05.4-D3, 05.4-D4)

> Mode : re-certification ciblée, en lecture seule sur le code du dépôt. Seul fichier écrit : ce rapport.
> Commit : `3d5814f` (HEAD, `main`, arbre propre). Plans contrôlés : 05.4-06 (DS2-2), 05.4-07 (DS2-3, partie doc,
> DS-MAINT-1). Base : `dev-senior-1-2-certification.md` (DS2-2, DS2-3, DS-MAINT-1 PARTIEL), `AUDIT_POINTS.md` (P4),
> `05.4-06-SUMMARY.md`, `05.4-07-SUMMARY.md`, `05.4-VERIFICATION.md`, `CLAUDE.md`.
>
> Vérité-terrain :
> - sondes dans le scratchpad
>   (`C:\Users\Tanguy\AppData\Local\Temp\claude\C--Users-Tanguy-Documents-PROGRAMMES-DEV-PROJET-DESKGATE\55069796-9b7f-4c99-9454-c9f37460a42e\scratchpad\probes2\`) :
>   `probe_413_marker.py`, `probe_marker_edges.py`, `probe_mcp_big.py`, `probe_doc_mutation.py`. Elles passent par
>   les vraies fonctions : `Engine` (lanceur factice pour `result.json`, ou worker et mini serveur MCP réels),
>   `Sender.tick`, `tests/_support/fake_n8n.py`, `payload.build_callback` / `minimal` / `is_marker`,
>   `store.purge_data`, `GET /jobs/{id}` par `TestClient`. Lancées par `uv run python` depuis la racine
>   (Python 3.14.4, SQLite 3.50.4), bases dans `probes2\dbs\` seulement ;
> - tests ciblés des deux SUMMARY : `uv run pytest -p no:cacheprovider tests/unit/test_payload.py
>   tests/fs/test_sender_send.py tests/proc/test_mcp_call.py tests/unit/test_architecture_doc.py
>   tests/**/test_text_bytes.py` → **68 passés**, 40 s ;
> - `ARCHITECTURE.md` du dépôt jamais modifié : la mutation porte sur une copie (`probes2\dbs\ARCHITECTURE.copy.md`),
>   le test lit la copie par remplacement de `_texte` ; contrôle octet pour octet en fin de sonde ;
>   `git status --porcelain` vide avant l'écriture de ce rapport.

## Verdicts

| Point | Verdict | Preuve principale |
|---|---|---|
| **05.4-D3 — DS2-2**, renvoi minimal après 413 | **FERMÉ** | `core/payload.py:44-64` (`is_marker`, `_reduce`, `minimal`), `sender.py:198-199`. Sonde `probe_413_marker` (Engine, Sender et faux n8n réels, 413 puis 200) : `data` déporté → rappel 1 (renvoi minimal, 219 o) `data={'path': '/data/travail/<id>/data.json', 'truncated': True}`, `data.json` de 1 048 507 o égal au `data` d'origine, `GET` porte le même marqueur ; `summary` déporté → rappel 1 `summary={'path': '…/summary.json', 'truncated': True}` ; 413, 413, 200 → marqueur gardé aux deux renvois, rappel `delivered` en 3 essais. |
| **05.4-D3 — DS2-2**, marqueur `mcp.call` | **PARTIEL** | Tenu en ASCII : sonde `probe_mcp_big` (worker et mini serveur MCP réels), `big` 950 000 → `data == {"truncated": true, "artifact": "mcp_result"}`, `artifacts=[{'kind': 'mcp_result', 'path': '/data/travail/<id>/mcp-result.json'}]`, rappel 298 o, `GET` identique (`data` et `artifacts`). **Non tenu** pour une réponse non ASCII : `echo` de 200 000 « € » (≈ 1,2 Mo d'octets, ≈ 400 000 caractères) → tâche **`failed/result_too_large`**. Le seuil se compte en caractères : `workers/mcp_call.py:122` `len(json.dumps(..., ensure_ascii=False))`, alors que `DATA_MAX_BYTES` (`:22`) et la doc (`ARCHITECTURE.md:50`, `:201`) disent « 900 000 octets ». Candidat DS3-1. |
| **05.4-D4 — DS-MAINT-1** (`ARCHITECTURE.md` décrit la cible comme livrée) | **FERMÉ** | Relecture P4 des 420 lignes : plus aucune cible présentée comme livrée. Les trois phrases sont corrigées et justes : `:160-163` (mémoire par `memory_mb` du Job Object, `engine.py:389,410` ; threads par `settings.threads`, `plugins/bim/src/deskgate_bim/clash.py:280` ; variable d'environnement posée par le runner : marquée cible), `:256-266` (exemple validé par `SubmitRequest`, `core/jobspec.py:33-36` `extra="forbid"`, `url` seul ; `headers` marqué cible), `:321-323` (`DESKGATE_MCPENV__<SERVEUR>__<CLÉ>` : `core/env.py:50`, posée par `engine.py:349`, relue par `workers/mcp_call.py:73-75` ; `keyring` marqué cible v0.2, aucun `keyring` dans `src/`). Verrou par mutation (`probe_doc_mutation`) : témoin vert ; chacune des trois phrases d'origine réintroduite → **échec** (`test_fonctionnalites_absentes_marquees_cible`, et `test_exemple_post_jobs_valide` pour `headers`, y compris avec une URL valide). Réserve sans effet sur P4 : le mot « octets » de `:50` et `:201` est faux (DS3-1). |

## Contournements cherchés (DS2-2)

- **Faux marqueur d'un plugin** (`probe_marker_edges`, `is_marker` réel) : clé en plus → `False` ; `truncated` à `1`,
  `"true"` ou `false` → `False` ; `path` entier ou `None` → `False` ; chemin de 4 096 caractères → `True`, de 4 097
  → `False` ; liste → `False`. Un plugin peut produire un marqueur valide pointant n'importe où
  (`{"truncated": true, "path": "C:/Windows/System32/config/SAM"}` → `True`) : il passe tel quel au renvoi minimal.
  Sans effet : c'est déjà la sortie du plugin, la même que dans le premier rappel et dans `GET`, et Deskgate ne lit
  jamais ce chemin. Pire cas du renvoi minimal avec deux marqueurs maximaux conservés : 24 730 o, sous le plafond.
- **Purge** : `store.purge_data` saute bien le marqueur `mcp.call` (`store.py:667`,
  `json_type($.data.truncated) IS NOT 'true'`) : `{"truncated": true, "artifact": "mcp_result"}` conservé. Mais ce
  filtre est plus large que `is_marker` : un `data` de 200 000 o qui contient `"truncated": true` parmi d'autres
  clés n'est **jamais purgé** ; avec `"truncated": 1` il l'est. Candidat DS3-2 (le cas existe dans le dépôt :
  `ifc.clash`).
- **Rappel et GET** : même forme hors 413 (`data` et `artifacts` identiques dans les trois cas sondés). Après un 413,
  le rappel diffère de `GET` par construction (`summary`/`data` non déportés réduits à `{"truncated": true}`,
  `ARCHITECTURE.md:280-286`) : conforme au contrat.

## Nouveaux findings (candidats)

### DS3-1 — `mcp.call` : seuil de 900 000 compté en caractères ; réponse non ASCII en échec `result_too_large` — **Mineur**
- **Preuve** : `workers/mcp_call.py:122` `len(json.dumps(data, ensure_ascii=False, allow_nan=False)) > DATA_MAX_BYTES`
  mesure des caractères ; le résultat est ensuite écrit en UTF-8 et plafonné à 1 Mio d'octets
  (`core/worker_protocol.py:15`, `engine.py:513`). Sonde `probe_mcp_big` : `echo` de 200 000 « € » → `failed`,
  `result_too_large`, « result.json dépasse la taille maximale ». Le SDK `mcp` double le texte (`content` et
  `structured_content`) : une réponse en français accentué de ~260 000 caractères suffit à dépasser.
- **Constat** : la réponse n'est ni livrée ni déportée dans `mcp-result.json`, alors que la doc promet un repli
  « > 900 000 octets » (`ARCHITECTURE.md:50`, `:201`). Défaut antérieur à 05.4-06 (même ligne), mais dans le contrat
  que 05.4-06 a documenté.
- **Pourquoi Mineur** : échec franc et tracé (pas de perte silencieuse), réponses MCP de cette taille rares.
- **Proposition** (iso-fonctionnelle pour l'ASCII) : mesurer `len(json.dumps(...).encode("utf-8"))` ; test
  `proc` avec un texte multi-octets.

### DS3-2 — Le contrat des marqueurs entre en collision avec le champ métier `truncated` d'`ifc.clash` — **Mineur**
- **Preuve** : `plugins/bim/src/deskgate_bim/clash.py:344` met `"truncated": truncated` dans `data` (vrai quand
  `max_clashes` coupe la liste), à côté de `counts`, `groups`… ; `store.py:667` exclut de la purge tout `data` où
  `$.data.truncated` vaut `true` ; sonde `probe_marker_edges` : `{"truncated": true, "rows": <200 000 o>}` → conservé,
  `{"truncated": 1, …}` et `data` ordinaire → purgés.
- **Constat** : (1) un résultat `ifc.clash` plafonné (jusqu'à 900 000 o de `data`, `clash.py:31`) n'est jamais purgé,
  ce qui contredit `ARCHITECTURE.md:61-62` et `:289-290` ; (2) pour n8n, `data.truncated == true` ne signifie plus
  « marqueur de repli » : la liste de `ARCHITECTURE.md:283-286` et `n8n/README.md:59-62` ne prévient pas de ce cas.
- **Proposition** : dans `purge_data`, reprendre le critère de `is_marker` (clés ⊆ `path`, `truncated`, `error`,
  `artifact`), par exemple en sélectionnant en Python ou par `json_each` ; à terme, renommer le champ d'`ifc.clash`
  (`clashes_truncated`), ce qui est un changement de contrat du plugin (suggestion produit, à trancher par l'auteur).

### DS3-3 — Verrou documentaire lexical, contournable par paraphrase ou par voisinage du mot « cible » — **Info**
- **Preuve** : `tests/unit/test_architecture_doc.py:30-38` et `:255-261` ; `probe_doc_mutation` : restent verts
  (C1) une phrase fausse sur les threads ajoutée dans la puce qui contient déjà « cible (non planifiée) » ;
  (C2) « Le runner pose `OMP_NUM_THREADS` dans les variables d'environnement » (`\bthreads?\b` ne trouve pas
  `THREADS` après `_`) ; (C3) « Credential Manager » ; (C4) des en-têtes de rappel décrits en prose.
- **Constat** : le verrou attrape les trois phrases d'origine, ce qu'on lui demandait. C1 est le cas le plus
  plausible en relecture : l'unité de contrôle est la puce entière.
- **Proposition** : rien d'obligatoire. Si l'on veut durcir : exiger « cible » dans la même phrase que le motif, et
  ajouter `OMP_NUM_THREADS` et `Credential Manager` aux motifs.

### Observations sans finding
- Après un 413, un `data` vide (`{}`) devient `{"truncated": true}` (`payload.py:58-59`) : n8n croit à une troncature
  alors qu'il n'y a rien ; `GET` rend `{}`. Conforme à la lettre de `ARCHITECTURE.md:286` (« lire `GET` »).
- `deskgate_bim/__init__.py:8-9` pose lui-même `OMP_NUM_THREADS=1` (et trois autres) par `setdefault` : la phrase
  `ARCHITECTURE.md:162-163` (« transmis aux plugins par variables d'environnement : cible ») reste juste, puisque
  le runner ne transmet rien (`core/env.py:7-42`), mais elle ne dit pas que le plugin BIM se plafonne à 1.
- `ctx.settings` (`deskgate_sdk/run.py:73`) n'est pas listé dans « Contexte passé au plugin »
  (`ARCHITECTURE.md:187`), alors que `:161` y renvoie. Omission, pas une cible présentée comme livrée.
- Le marqueur `mcp.call` ne porte pas de chemin (choix de 05.4-06) : deux lectures pour n8n (chercher dans
  `artifacts` le `kind` `mcp_result`). Documenté, cohérent dans le rappel et `GET`.

## Non vérifié
- n8n 2.43.8 réel : le 413 vient du faux n8n (`fake_n8n.py`), pas d'un vrai dépassement de `N8N_PAYLOAD_SIZE_MAX`.
- Écriture impossible de `data.json` (marqueur `{"truncated": true, "error": "data_write_failed"}`) au renvoi
  minimal : couvert par `is_marker` en sonde unitaire seulement, pas de bout en bout.
- Suite complète et `pytest -m e2e` non relancés : seuls les 68 tests ciblés l'ont été (le SUMMARY 05.4-07 annonce
  1048 + 33 e2e verts).
- `AGENTS.md:38` (`<organisation>`, DS-MAINT-2), DS2-1 et DS2-4 : hors périmètre de cette re-certification, non relus.

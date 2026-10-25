# Journal des changements

Format : sections par version, la plus récente en tête. Les changements de comportement visibles par un plugin ou
par n8n sont signalés « Changement de comportement ».

## Non publié

### Ajouté

- **`data` exposé à n8n** (DS-ARCH-1, decision-ds-1) : le corps du rappel et `GET /jobs/{id}` portent `data`, entre
  `summary` et `artifacts` (`{}` si vide). Au-delà de 1 Mio, `data` est écrit dans `data.json` du dossier de la tâche et
  la clé vaut `{"path": "…/data.json", "truncated": true}` ; si le corps dépasse encore, `summary` suit le même chemin
  (`summary.json`). Après un 413, le renvoi minimal réduit `summary` et `data` à `{"truncated": true}`, sauf un marqueur de repli déjà
  posé, transmis avec son chemin (DS2-2).
- **`deskgate purge [--older-than-days N]`** (DS-SCAL-1) : retire `data` des tâches terminées depuis plus de N
  jours (défaut 30) dont le rappel est final ; `GET /jobs/{id}` renvoie alors `data: {"purged": true}`. `summary`,
  artefacts, audit et rappels sont conservés. Purge manuelle, sans migration ; le fichier de base ne rétrécit pas.

### Changement de comportement

- **Marqueur `mcp.call`** (DS2-2) : une réponse `mcp.call` de plus de 900 000 octets donne `data` =
  `{"truncated": true, "artifact": "mcp_result"}` (au lieu de `{"truncated": true}`) ; le chemin de `mcp-result.json`
  est celui de l'entrée `artifacts` de type `mcp_result`.
- **NaN et Infinity refusés** (DS-ARCH-3) : un `result.json` ou un événement de `events.jsonl` contenant `NaN`,
  `Infinity`, `-Infinity` ou un flottant hors limites (`1e999`) est refusé ; la tâche finit `failed` avec le code
  `invalid_result`. Le SDK n'écrit plus de flottant non fini : un plugin qui renvoie `float("nan")` finit en erreur
  `ValueError`, et `ctx.progress(float("nan"))` lève `ValueError`. Remplacer ces valeurs par `null` ou une chaîne.

### Corrigé

- **Rappel empoisonné isolé** (DS-ARCH-2) : une erreur propre à un rappel est un essai en échec `internal_error` de
  cette ligne ; les autres rappels partent et le runner ne s'arrête plus en code 6 pour cette cause.
- **Seuil de déport de `mcp.call` en octets** (DS3-1) : le seuil de 900 000 se mesure en octets UTF-8, comme le
  plafond de `result.json`. Une réponse non ASCII (texte accentué, « € »…) au-delà est déportée dans
  `mcp-result.json` (`data` = `{"truncated": true, "artifact": "mcp_result"}`) au lieu de finir
  `failed/result_too_large`.
- **Purge et champ métier `truncated`** (DS3-2) : `deskgate purge` ne conserve que les vrais marqueurs de repli,
  reconnus par la même règle que le renvoi minimal ; un `data` d'`ifc.clash` plafonné par `max_clashes`
  (`"truncated": true` parmi ses champs) est désormais purgé.

### Documentation

- `ARCHITECTURE.md` : section « État livré en v0.1 » (références au code vérifiées par test) et marquage
  « cible vX » (DS-MAINT-1).

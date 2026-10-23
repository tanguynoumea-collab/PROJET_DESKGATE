# Journal des changements

Format : sections par version, la plus récente en tête. Les changements de comportement visibles par un plugin ou
par n8n sont signalés « Changement de comportement ».

## Non publié

### Ajouté

- **`data` exposé à n8n** (DS-ARCH-1, decision-ds-1) : le corps du rappel et `GET /jobs/{id}` portent `data`, entre
  `summary` et `artifacts` (`{}` si vide). Au-delà de 1 Mio, `data` est écrit dans `data.json` du dossier de la tâche et
  la clé vaut `{"path": "…/data.json", "truncated": true}` ; si le corps dépasse encore, `summary` suit le même chemin
  (`summary.json`). Après un 413, le renvoi minimal marque `summary` et `data` `{"truncated": true}`.
- **`deskgate purge [--older-than-days N]`** (DS-SCAL-1) : retire `data` des tâches terminées depuis plus de N
  jours (défaut 30) dont le rappel est final ; `GET /jobs/{id}` renvoie alors `data: {"purged": true}`. `summary`,
  artefacts, audit et rappels sont conservés. Purge manuelle, sans migration ; le fichier de base ne rétrécit pas.

### Changement de comportement

- **NaN et Infinity refusés** (DS-ARCH-3) : un `result.json` ou un événement de `events.jsonl` contenant `NaN`,
  `Infinity`, `-Infinity` ou un flottant hors limites (`1e999`) est refusé ; la tâche finit `failed` avec le code
  `invalid_result`. Le SDK n'écrit plus de flottant non fini : un plugin qui renvoie `float("nan")` finit en erreur
  `ValueError`, et `ctx.progress(float("nan"))` lève `ValueError`. Remplacer ces valeurs par `null` ou une chaîne.

### Corrigé

- **Rappel empoisonné isolé** (DS-ARCH-2) : une erreur propre à un rappel est un essai en échec `internal_error` de
  cette ligne ; les autres rappels partent et le runner ne s'arrête plus en code 6 pour cette cause.

### Documentation

- `ARCHITECTURE.md` : section « État livré en v0.1 » (références au code vérifiées par test) et marquage
  « cible vX » (DS-MAINT-1).

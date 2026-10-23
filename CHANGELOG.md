# Journal des changements

Format : sections par version, la plus récente en tête. Les changements de comportement visibles par un plugin ou
par n8n sont signalés « Changement de comportement ».

## Non publié

### Changement de comportement

- **NaN et Infinity refusés** (DS-ARCH-3) : un `result.json` ou un événement de `events.jsonl` contenant `NaN`,
  `Infinity`, `-Infinity` ou un flottant hors limites (`1e999`) est refusé ; la tâche finit `failed` avec le code
  `invalid_result`. Le SDK n'écrit plus de flottant non fini : un plugin qui renvoie `float("nan")` finit en erreur
  `ValueError`, et `ctx.progress(float("nan"))` lève `ValueError`. Remplacer ces valeurs par `null` ou une chaîne.

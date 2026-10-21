# Scripts de recette

Bibliothèque standard et `psutil` (environnement de développement). Aucun import de `deskgate`.
À lancer depuis la racine du dépôt, avec `UV_PYTHON` positionné :

```
uv run python scripts/recette/n8n_setup.py
uv run python scripts/recette/recette.py smoke --params-file <params.json>
uv run python scripts/recette/recette.py acc01 --params-file <params.json>
uv run python scripts/recette/recette.py acc02 --params-file <params.json> --kill-after-s 90
```

- `_commun.py` : lecture de `n8n/.env`, HTTP, docker compose du dépôt (projet `deskgate-n8n`, port 5679),
  lecture SQLite en lecture seule (jamais `callback_url`), provenance du runner, masquage de la signature.
- `n8n_setup.py` : propriétaire, identifiant `DeskgateToken0001` (jeton par stdin du conteneur), import et
  publication du workflow, contrôle INS-05 depuis le conteneur.
- `recette.py` : scénarios `smoke` (calcul court), `acc01` (calcul long, durée > 600 s) et `acc02`
  (arrêt brutal du runner pendant un calcul). Preuve JSON dans `%LOCALAPPDATA%\Deskgate\recette\`.

## Règles de secret

Les scripts n'écrivent ni jeton, ni clé d'API, ni mot de passe, ni signature (`signature=***`). La clé d'API
n8n est éphémère, créée en mémoire et supprimée en fin de scénario.

## Relance du runner

La tâche planifiée ne relance pas le runner après `taskkill` : `acc02` relance explicitement par
`schtasks /Run /TN Deskgate`.

# Deskgate — règles du dépôt pour Claude Code

Lire aussi [`AGENTS.md`](AGENTS.md) (installation) et [`ARCHITECTURE.md`](ARCHITECTURE.md) (référence
technique). Le cycle de développement est piloté par ARTHEMIS (profil `web_saas`, état dans
`.arthemis/state.json`) et GSD (`.planning/`, écrit uniquement par les commandes GSD).

## Langue

Français partout : documents, interface, messages d'erreur, journaux, commits (sujet en français).
Identifiants de code, noms de routes et de champs JSON : anglais.

## Ce que Deskgate est, et n'est pas

- Une **passerelle** : n8n soumet une tâche, Deskgate exécute un plugin dans la session Windows,
  puis rappelle n8n. Une tâche = un appel d'un plugin.
- **Pas** un orchestrateur : aucun DAG, aucune planification, aucun enchaînement d'étapes.
- **Pas** un serveur MCP : Deskgate *appelle* des outils MCP (exécuteur `mcp`), il n'en expose pas.
- Workflows complets, Hermes, tableau de bord : hors de ce dépôt.

## Règles non négociables

1. **Le cœur ne connaît rien au BIM.** `src/deskgate/` n'importe jamais `deskgate_bim` ni
   IfcOpenShell. Les plugins BIM vivent dans `plugins/bim/`, paquet séparé.
2. **Aucune exécution de commande libre.** Pas de `shell=True`, pas de chaîne de commande construite
   par concaténation. L'exécuteur `cli` n'utilise que l'exécutable et le gabarit du manifeste.
3. **Un plugin ne tourne jamais dans le processus du runner** : sous-processus, dans un Job Object
   (créé suspendu, assigné, repris ; breakaway interdit).
4. **Chemins** : tout chemin reçu est converti puis validé contre `allowed_roots` (résolution des
   `..`, liens et jonctions) avant usage. On transmet des chemins, jamais les fichiers.
5. **Écoute sur `127.0.0.1` uniquement** ; jeton obligatoire sur toutes les routes sauf `/health`.
6. **Secrets** : jamais dans les manifestes, les journaux ni l'audit. La `resumeUrl` n8n est un
   secret (paramètre `signature`) : appelée telle quelle, masquée partout ailleurs.
7. **Rappel** : petit (≤ 1 Mio) ; les gros résultats vont dans des fichiers artefacts.
8. **Déterminisme** : un plugin de calcul donne les mêmes sorties pour les mêmes entrées.
9. **Licences** : le code du dépôt est MIT. Ne jamais intégrer de code GPL ou AGPL (Bonsai, xeokit,
   BIMserver, Windmill…) ; IfcOpenShell (LGPL-3) s'utilise comme bibliothèque.
10. **Frontière GPL** : seul `plugins/bim/bcf/` (`deskgate-bcf`, GPL-3) importe `bcf-client`.
    Aucun autre paquet ne l'importe ni n'importe `deskgate-bcf` : on l'appelle en sous-processus,
    avec des fichiers JSON. N'appeler l'export BCF d'`ifcclash` et le rapporteur BCF d'`ifctester`
    que depuis `deskgate-bcf`.

## Pile

- Python ≥ 3.11, `uv` pour les environnements, FastAPI + Uvicorn, SQLite (WAL), SDK `mcp` officiel,
  `pywin32` ou `ctypes` pour les Job Objects.
- n8n épinglé en `2.43.8` dans `n8n/docker-compose.yml`. Ne pas passer sur `latest`.
- Nœud n8n : TypeScript, paquet `n8n-nodes-deskgate`.

## Tests

- `pytest` pour le runner ; chaque exécuteur a des tests avec de vrais sous-processus Windows.
- Tests obligatoires sur : refus de chemin hors racine (`..`, lien, jonction), arrêt de l'arbre de
  processus au délai, passage `running` → `interrupted` au redémarrage, masquage de la signature,
  refus d'un jeton sans droit.
- Les plugins BIM ont leurs propres tests sur de petits fichiers IFC d'exemple dans `plugins/bim/tests/`.

## Commits

Format ARTHEMIS : `type(scope): sujet` ≤ 72 caractères, sujet en français. `.arthemis/**` jamais
mêlé au code ni à `.planning/`.

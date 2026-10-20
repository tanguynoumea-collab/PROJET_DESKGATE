# AGENTS.md — installer Deskgate (procédure pour une IA)

> **Statut : procédure cible.** Les commandes ci-dessous décrivent l'installation visée ; elles
> deviennent exécutables au fil des versions (v0.1 pour le runner, v0.3 pour le nœud n8n) et la
> procédure sera éprouvée sur un PC vierge en v0.4. Ne pas inventer de commande absente du dépôt :
> si une étape échoue parce qu'elle n'existe pas encore, s'arrêter et le signaler.

Règles de dépôt pour le développement : voir [`CLAUDE.md`](CLAUDE.md).

## Ce que tu installes

Deskgate est un service local Windows qui exécute, pour n8n, des tâches lourdes (calculs,
logiciels installés, serveurs MCP stdio). Il tourne **dans la session de l'utilisateur**, écoute
sur `127.0.0.1:8765` et exige un jeton.

## Règles pour l'agent

- Demande l'accord de l'utilisateur avant : d'installer un logiciel global, de créer la tâche du
  Planificateur, de modifier un fichier hors du dossier du dépôt et de `C:\BIM`.
- N'écris jamais un jeton dans le chat, un commit ou un journal. Il est affiché une seule fois par
  `deskgate init` : dis à l'utilisateur où le copier (identifiants n8n), sans le répéter.
- N'écoute jamais sur `0.0.0.0`.
- Si une vérification échoue, arrête-toi et rapporte la sortie exacte.

## 1. Prérequis (vérifier, ne pas supposer)

```powershell
winver                      # Windows 10 ou 11
uv --version                # sinon : winget install --id=astral-sh.uv -e   (avec accord)
docker --version            # Docker Desktop, backend WSL2 (pour n8n)
git --version
```

Python n'a pas besoin d'être installé globalement : `uv` fournit l'interpréteur (≥ 3.11).

## 2. Récupérer et installer le runner

```powershell
git clone https://github.com/<organisation>/deskgate.git
cd deskgate
uv tool install .           # installe la commande `deskgate`
deskgate --version
```

## 3. Initialiser

```powershell
deskgate init
```

`deskgate init` crée `runner.toml`, le dossier partagé (`C:\BIM` par défaut) et ses sous-dossiers
`depot`, `travail`, `livrables`, génère le jeton et propose de créer la tâche du Planificateur
(démarrage à l'ouverture de session). Puis :

```powershell
deskgate doctor             # tout doit être vert ; sinon rapporter la sortie
deskgate serve              # premier lancement manuel, pour vérifier
```

Vérifier : `curl http://127.0.0.1:8765/health` répond.

## 4. Installer les plugins (v0.1)

Chaque plugin a son propre environnement `uv`, séparé de celui du runner. `deskgate plugin add`
arrive en v0.2 : en v0.1 la procédure est manuelle.

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$env:LOCALAPPDATA\Deskgate\plugins\bim"
uv sync --locked --package deskgate-bim --no-dev
$env:UV_PROJECT_ENVIRONMENT = "$env:LOCALAPPDATA\Deskgate\plugins\bcf"
uv sync --locked --package deskgate-bcf --no-dev
Remove-Item Env:UV_PROJECT_ENVIRONMENT
```

Puis, dans `runner.toml`, copier le bloc d'exemples de `src/deskgate/runner.example.toml` (entre
`# >>> exemples phase 4` et `# <<< exemples phase 4`), retirer les `# ` et remplacer les chemins par
ceux des environnements créés ci-dessus (`...\bim\Scripts\python.exe` et
`...\bcf\Scripts\deskgate-bcf.exe`). Les exemples couvrent `ifc.clash`, `mcp.call` et `mcp_servers`.
Redémarrer le runner.

Consignes :

- ne jamais lancer `uv sync --all-packages` : cela mélange les dépendances de tous les plugins
  dans un seul environnement ;
- ne jamais lancer `uv python install` : utiliser l'interpréteur déjà installé (`UV_PYTHON`) ;
- toujours définir `UV_PROJECT_ENVIRONMENT` avant `uv sync --package ...`, sinon l'environnement du
  dépôt est modifié ; le restaurer avec `uv sync --locked`.

## 5. Brancher n8n

```powershell
cd n8n
docker compose up -d        # n8n 2.43.8 épinglé + Postgres, C:\BIM monté sur /data
```

Vérifier depuis le conteneur :

```powershell
docker compose exec n8n wget -qO- http://host.docker.internal:8765/health
```

Puis, dans n8n : installer le nœud communautaire `n8n-nodes-deskgate` (v0.3) ou importer
`n8n/examples/*.json` (v0.1), et créer l'identifiant « Deskgate » avec l'URL
`http://host.docker.internal:8765` et le jeton.

## 6. Test de bout en bout

Importer `n8n/examples/ifc-clash.json`, déposer un IFC d'exemple dans `C:\BIM\depot\`, lancer le
workflow : il doit se mettre en attente puis reprendre avec un résumé et le chemin d'un BCF.

## Dépannage

| Symptôme | Cause probable |
|---|---|
| n8n ne joint pas le runner | Runner arrêté ; Docker Engine dans WSL (pas Docker Desktop) : voir `ARCHITECTURE.md` §2 |
| Rappel refusé en 401 | `resumeUrl` modifiée : elle doit être transmise telle quelle |
| Plugin `requires_session` en échec | Session Windows verrouillée ou fermée |

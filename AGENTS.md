# AGENTS.md — installer Deskgate (procédure pour une IA)

> **Statut : procédure éprouvée en v0.1 sur Windows 11 (phase 5).** Elle sera rejouée sur un PC
> vierge en v0.4. Ne pas inventer de commande absente du dépôt : si une étape échoue parce qu'elle
> n'existe pas, s'arrêter et le signaler.

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

Si `deskgate` n'est pas dans le `PATH` : `uv tool update-shell` (puis rouvrir le terminal), ou appeler
l'exécutable dans le dossier donné par `uv tool dir --bin`. Si l'interpréteur géré par `uv` est
indisponible, définir `UV_PYTHON` sur un Python ≥ 3.11 déjà installé.

> **Terminal normal obligatoire.** Une application empaquetée en MSIX (par exemple les outils isolés
> de l'application de bureau Claude) virtualise `%LOCALAPPDATA%` et `%APPDATA%`. Lancer `uv tool install`
> et `deskgate init` depuis un terminal ordinaire (PowerShell ouvert depuis le menu Démarrer, pas
> depuis une application empaquetée). Symptômes d'une installation virtualisée : tâche planifiée avec le
> dernier résultat `0x8007010B`, fichiers sous `%LOCALAPPDATA%\Packages\<application>\LocalCache`.

## 3. Initialiser

```powershell
deskgate init
```

`deskgate init` crée `runner.toml`, le dossier partagé (`C:\BIM` par défaut) et ses sous-dossiers
`depot`, `travail`, `livrables`, génère le jeton et propose de créer la tâche du Planificateur
(démarrage à l'ouverture de session). Le **jeton est seul sur la sortie standard** (une ligne) ; le
guidage va sur la sortie d'erreur.

Options : `--root <dossier>` (racine partagée), `--force` (sauvegarde `runner.toml` en `.bak-*` puis le
réécrit), `--no-task` (pas de tâche), `--yes` (crée la tâche sans question). La tâche est refusée si
`DESKGATE_HOME` est défini.

Pour une IA : rediriger le jeton vers un fichier hors du dépôt, sans jamais le lire dans la
conversation. Dans Windows PowerShell 5.1, `>` écrit en UTF-16 et le jeton devient inutilisable : passer
par `cmd` (ou `Out-File -Encoding ascii`).

```powershell
cmd /c "deskgate init --yes > <fichier-hors-depot>"
```

Puis démarrer le runner par la tâche et vérifier :

```powershell
deskgate task run
deskgate doctor > <fichier>   # tout doit être [ok] ; rapporter la sortie sinon
curl http://127.0.0.1:8765/health
```

Ne pas relier `deskgate doctor` à un tube sur la console Windows (plantage de Rich) : le rediriger vers un
fichier. Le journal est `%LOCALAPPDATA%\Deskgate\logs\runner.log`. `deskgate serve` en console ne sert
qu'à voir une erreur de configuration.

### Tâche du Planificateur

```powershell
deskgate task install | status | run | end | remove
```

`install` crée la tâche (sans élévation), `status` la compare à l'attendu, `run` la lance, `end` l'arrête,
`remove` la supprime. Un runner tué brutalement **n'est pas relancé automatiquement** : relancer par
`deskgate task run` ou à la prochaine ouverture de session. Les tâches `running` deviennent `interrupted`
au redémarrage et n8n reçoit le rappel.

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
La clé `required_files = ["bcf_executable"]` du bloc `ifc.clash` demande à `deskgate doctor` de vérifier que
`deskgate-bcf.exe` existe ; une capacité d'un autre plugin peut déclarer ses propres fichiers requis de la même façon.
Adapter `memory_mb` de `[capabilities."ifc.clash"]` à la machine (24576 sur le PC de recette). Vérifier
les chemins par `deskgate doctor`, puis `deskgate task end` et `deskgate task run`.

Consignes :

- ne jamais lancer `uv sync --all-packages` : cela mélange les dépendances de tous les plugins
  dans un seul environnement ;
- ne jamais lancer `uv python install` : utiliser l'interpréteur déjà installé (`UV_PYTHON`) ;
- toujours définir `UV_PROJECT_ENVIRONMENT` avant `uv sync --package ...`, sinon l'environnement du
  dépôt est modifié ; le restaurer avec `uv sync --locked`.

### Mettre à jour les plugins

Les paquets des plugins (`deskgate-bim`, `deskgate-bcf`) sont installés **en mode éditable** : les fichiers
`_editable_impl_deskgate_bim.pth` et `_editable_impl_deskgate_bcf.pth` pointent vers le dépôt. Un changement de
code d'un plugin est donc pris au prochain job, sans redémarrage du runner (le plugin est lancé à chaque
tâche). Seule une dépendance modifiée (`pyproject.toml` ou `uv.lock`, par exemple Pillow en phase 5.1) exige de
relancer les deux `uv sync --locked --package ... --no-dev` de la section précédente, avec
`UV_PROJECT_ENVIRONMENT` et `UV_PYTHON` définis, depuis un terminal hors application MSIX (qui
virtualise `%LOCALAPPDATA%`).

## 5. Brancher n8n

Le compose du dépôt publie n8n 2.43.8 (et Postgres) sur `127.0.0.1:5679`, `C:\BIM` monté sur `/data`.

```powershell
cp n8n/.env.example n8n/.env          # puis remplacer chaque valeur a-remplacer par un secret généré
docker compose -f n8n/docker-compose.yml pull
docker compose -f n8n/docker-compose.yml up -d
```

`n8n/.env` est ignoré par git ; `N8N_ENCRYPTION_KEY` doit rester stable ; `N8N_WEBHOOK_URL` désigne
`127.0.0.1` ou `localhost` (sinon le runner refuse la `resumeUrl`). Vérifier depuis le conteneur :

```powershell
docker compose -f n8n/docker-compose.yml exec -T n8n wget -qO- http://host.docker.internal:8765/health
docker compose -f n8n/docker-compose.yml exec -T n8n ls /data
```

Importer l'exemple et créer l'identifiant « Deskgate » (le jeton passe par l'entrée standard du
conteneur, jamais par un fichier du dépôt) : `uv run python scripts/recette/n8n_setup.py`, ou les étapes
de [`n8n/README.md`](n8n/README.md). Voir aussi [`scripts/recette/README.md`](scripts/recette/README.md).

Avec un **n8n déjà installé** : importer à la main `n8n/examples/ifc-clash.json`, ne pas modifier sa
configuration, et vérifier que sa `WEBHOOK_URL`/`N8N_WEBHOOK_URL` désigne `127.0.0.1` ou `localhost`.
Le nœud communautaire `n8n-nodes-deskgate` n'arrive qu'en v0.3.

## 6. Test de bout en bout

Déposer un IFC d'exemple dans `C:\BIM\depot\`, puis `POST http://127.0.0.1:5679/webhook/deskgate-ifc-clash`
(corps `{"params": {...}, "timeout": 14400}` ; un 404 juste après la publication : réessayer), ou lancer
`uv run python scripts/recette/recette.py smoke`. Exemple de corps avec gabarit de titre et tables (détails : [`plugins/bim/README.md`](plugins/bim/README.md)) :
`{"params": {"ifc_a": "...", "selector_a": "IfcWall", "mode": "hard", "tolerance": 0.01, "bcf": true,
"title_template": "{building}/{storey}/{trade_a}-{trade_b}/{type_a} x {type_b}",
"mappings": {"building": {"Jura": "BaJ"}, "storey": {"J_11_P01": "P01"},
"trade": {"PIC-EXE-AW-CVC-MNQ-BaJ-SUP-30701-IFC4": "CVC", "PIC_REV_HRS_ARC_MNQ_BaJ_SUP_30400": "ARC"}}}}`.
Les paramètres complets du projet pilote sont dans `n8n/examples/ifc-clash-params.json`.
Le workflow se met en attente puis reprend avec un
résumé et le chemin d'un BCF. Si `recette.py` tourne dans un contexte virtualisé, donner `--out`
explicitement (dossier hors `%LOCALAPPDATA%`, par exemple sous `C:\BIM\recette`).

## Mettre à jour

```powershell
deskgate task end
uv tool upgrade deskgate        # ou : uv tool install --force .
deskgate task run
deskgate doctor > <fichier>
```

## Dépannage

| Symptôme | Cause probable |
|---|---|
| n8n ne joint pas le runner | Runner arrêté ; Docker Engine dans WSL (pas Docker Desktop) : voir `ARCHITECTURE.md` §2 |
| Runner arrêté après un arrêt brutal | Pas de relance automatique : `deskgate task run` |
| Aucun journal | Vérifier `logs\runner.log` ; sinon erreur de configuration : `deskgate doctor` |
| Tâche planifiée en `0x8007010B` | Installation faite depuis une application MSIX : refaire depuis un terminal normal |
| Jeton refusé après `init` | Fichier écrit en UTF-16 par `>` de PowerShell 5.1 : utiliser `cmd /c` |
| Webhook 404 juste après la publication | Enregistrement en cours : réessayer après quelques secondes |
| Wait expiré | Branche « Echec ou delai » : rappel absent ; voir `n8n/README.md` |
| Rappel refusé en 401 | `resumeUrl` modifiée : elle doit être transmise telle quelle |
| Plugin `requires_session` en échec | Session Windows verrouillée ou fermée |

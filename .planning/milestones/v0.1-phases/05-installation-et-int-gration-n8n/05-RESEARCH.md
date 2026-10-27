# Phase 5 : Installation et intégration n8n - Recherche

**Recherché :** 2026-10-21
**Domaine :** installation Windows (Planificateur de tâches, lanceur sans console), `deskgate init` / `doctor`, n8n épinglé en Docker Desktop (compose + Postgres), import de workflow, recette de bout en bout (ACC-01, ACC-02)
**Confiance globale :** HAUTE sur ce qui a été exécuté sur cette machine (marqué [test]), MOYENNE sur les points lus dans la doc n8n seulement, un point reste à reconfirmer sur 2.43.8 (voir « Questions ouvertes »).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Accords système (B2, donnés par l'utilisateur le 2026-10-21)**
- **D-01:** Créer `C:\BIM` (`depot`, `travail`, `livrables`), `%LOCALAPPDATA%\Deskgate`
  (config, base, jeton haché, environnements de plugins), et installer la tâche du Planificateur.
  Ces actions sont autorisées pour la recette sur cette machine ; `deskgate init` doit malgré tout
  demander confirmation (ou exiger `--yes`) avant de créer la tâche, pour les autres utilisateurs.

**deskgate init (INS-01, INS-02)**
- **D-02:** `deskgate init` : écrit `runner.toml` depuis le gabarit commenté (sans écraser un
  fichier existant sauf `--force`), crée les dossiers, génère le jeton (affiché une seule fois,
  hash SHA-256 dans la config), propose l'installation de la tâche. Idempotent.
- **D-03:** Tâche du Planificateur générée en XML (UTF-16) puis `schtasks /Create /XML`, sans
  élévation : `LogonTrigger` utilisateur courant, `InteractiveToken`, `LeastPrivilege`,
  `ExecutionTimeLimit=PT0S`, batterie autorisée, `MultipleInstancesPolicy=IgnoreNew`,
  `RestartOnFailure` (1 min, 3 essais). Action : exécutable absolu résolu à l'installation (lanceur
  sans console si fiable, sinon `deskgate serve` avec journal fichier). `deskgate uninstall-task`
  (ou équivalent) la retire. Spike à mener en tête de phase (compte standard, fermeture/réouverture
  de session non automatisable : à vérifier en démarrant la tâche par `schtasks /Run`).
- **D-04:** `deskgate doctor` minimal : config valide, dossiers, jeton présent, tâche installée et
  ses réglages relus, port libre ou runner joignable, environnements de plugins déclarés présents.

**n8n (INS-03, INS-04, INS-05)**
- **D-05:** `n8n/docker-compose.yml` : n8n **2.43.8** épinglé (digest si possible) + Postgres,
  `C:\BIM` monté sur `/data`, port publié **127.0.0.1:5679** (le n8n de l'utilisateur occupe 5678),
  `WEBHOOK_URL=http://127.0.0.1:5679/` pour que la `resumeUrl` soit joignable depuis Windows (hôte
  autorisé `127.0.0.1`). Secrets (Postgres, clé de chiffrement) dans un `.env` non versionné, avec
  `.env.example`.
- **D-06:** Workflow d'exemple importable `n8n/examples/ifc-clash.json` : déclencheur manuel →
  HTTP Request `POST http://host.docker.internal:8765/jobs` (jeton en identifiant n8n, pas en dur)
  avec `callback.url = {{$execution.resumeUrl}}` → Wait « On Webhook Call » avec « Limit Wait
  Time » → If sur `status`. Un second exemple pour `mcp.call` facultatif.
- **D-07:** Recette sur **les deux** n8n : le compose du dépôt (2.43.8, recette officielle) et le
  n8n de l'utilisateur (`pipelines-n8n`, 2.42.5, port 5678, `WEBHOOK_URL=http://127.0.0.1:5678/`) **sans
  le modifier** (import du workflow par API ou à la main, rien d'autre). Écart de version consigné.
- **D-08:** `host.docker.internal` → runner sur 127.0.0.1 : **vérifié** le 2026-10-21 (01-D1).

**Acceptation (ACC-01, ACC-02)**
- **D-09:** Calcul long : `ifc.clash` mode `hard`, `ifc_a` = `PIC-EXE-AW-CVC-MNQ-BaJ-SUP-30701-IFC4.ifc`
  (532 Mo) avec `selector_a` gaines, tuyaux et accessoires (`IfcFlowSegment, IfcFlowFitting`),
  `ifc_b` = `PIC_REV_HRS_ARC_MNQ_BaJ_SUP_30400.ifc` (51 Mo) avec `selector_b` murs, dalles, poutres,
  poteaux (`IfcWall, IfcSlab, IfcBeam, IfcColumn`), `bcf: true`. Maquettes copiées depuis
  `G:\Mon Drive\07_PROJETS\DESKGATE` vers `C:\BIM\depot\`. Si le calcul dure moins de 10 min, élargir
  les sélections ou la tolérance plutôt que d'ajouter une attente artificielle.
- **D-10:** ACC-01 depuis le runner **démarré par la tâche planifiée** (pas depuis un terminal).
  ACC-02 : arrêt brutal du runner (`taskkill /F /T`) pendant un calcul, relance par
  `schtasks /Run`, n8n reçoit `interrupted`.
- **D-11:** 04-D1 : l'utilisateur ouvre le BCF produit dans BIMcollab Zoom (deux vues par sujet,
  contexte gris transparent, couleurs) — vérification humaine différable, consignée dans
  `05-HUMAN-UAT.md` ou soldée dans `04-HUMAN-UAT.md`.

### Claude's Discretion
- Découpage des plans, lanceur sans console (`gui-scripts` sous `uv tool install` ou alternative),
  forme exacte de `deskgate doctor`, import du workflow (API n8n ou procédure manuelle documentée).

### Deferred Ideas (OUT OF SCOPE)
- Nœud communautaire `n8n-nodes-deskgate` (v0.3).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Support de la recherche |
|----|-------------|-------------------------|
| INS-01 | `deskgate init` crée `runner.toml`, `C:\BIM` (`depot`, `travail`, `livrables`) et le jeton affiché une fois | § Conception de `init` : gabarit via `importlib.resources` (le `runner.example.toml` est bien dans la roue [test]), remplacement de la ligne `token_sha256`, jeton seul sur stdout, messages sur stderr |
| INS-02 | `init` installe, avec accord, la tâche du Planificateur (ouverture de session, sans limite, sur batterie) | § Spike Planificateur [test] : XML exact qui passe sans élévation, relecture en XML, `/Run`, `/Delete`; lanceur = `pythonw.exe -m deskgate serve` |
| INS-03 | `n8n/docker-compose.yml` : n8n 2.43.8 épinglé + Postgres + `C:\BIM` sur `/data` | § Compose : digest vérifié, `docker compose config` valide [test], montage `C:/BIM` vérifié par conteneur jetable [test] |
| INS-04 | Workflow d'exemple importable (HTTP Request, Wait, test du `status`) | § Workflow : JSON complet, exécuté de bout en bout sur n8n 2.42.5 avec le vrai runner [test] ; import par CLI avec `id` fixes |
| INS-05 | Depuis le conteneur n8n, `http://host.docker.internal:8765/health` répond | § Recette : commande `docker compose exec -T n8n wget`; `wget` présent dans l'image [test]; 01-D1 déjà réussi |
| ACC-01 | Calcul de plus de 10 min depuis n8n, runner démarré par la tâche, reprise avec résumé et chemin du BCF | § Procédure de recette programmatique (déclenchement par webhook, sondage de l'API n8n) |
| ACC-02 | Arrêt brutal du runner pendant une tâche : rappel `interrupted` reçu par n8n | § Recette : `taskkill /F /T` puis `schtasks /Run` explicite (pas de relance automatique, [test]) ; répétition à blanc réussie avec un faux plugin [test] |
</phase_requirements>

## Résumé

Toute la mécanique de la phase a été éprouvée sur cette machine avant d'écrire ce document, sans toucher au dépôt, à `C:\BIM`, à `%LOCALAPPDATA%\Deskgate` ni au n8n de l'utilisateur. Le Planificateur accepte, **sans élévation**, une tâche créée par `schtasks /Create /XML` avec tous les réglages de D-03, démarre le programme dans la session interactive (session 1), se relit en XML et se supprime proprement. Le vrai runner (`python -m deskgate serve`) tourne sous `pythonw.exe` (stdout/stderr valent `None`) et exécute des tâches normalement, mais **n'écrit alors aucun journal** : un journal fichier est à ajouter. Un n8n jetable (image locale 2.42.5, port 5699, supprimé après) a servi à rejouer le parcours complet avec le vrai runner : soumission HTTP Request, Wait, reprise, `If`, et le cas `interrupted` après `taskkill /F /T` puis relance.

Trois constats changent le plan par rapport au CONTEXT. (1) `RestartOnFailure` **ne relance pas** un runner tué par `taskkill /F` [test, 140 s d'observation] : la relance de l'ACC-02 est un `schtasks /Run` explicite, et la tâche ne sert pas de superviseur. (2) Le déclenchement « manuel » du CONTEXT n'est pas pilotable par programme (l'API publique n'a pas de route d'exécution, et le scope `workflow:execute` n'existe pas) : l'exemple doit offrir **aussi** un déclencheur Webhook, que la recette appelle par `curl`. (3) Un webhook de production n'existe qu'après publication du workflow et **quelques secondes de latence** : il faut sonder jusqu'à ne plus recevoir 404.

Côté n8n, deux voies d'import sont validées : l'API publique (clé d'API créée via la session du propriétaire) et surtout la **CLI** `n8n import:credentials` / `import:workflow` dans le conteneur, sans clé d'API et sans écrire le jeton sur disque (stdin). La CLI exige un `id` dans le JSON du workflow et des `id` fixes pour l'identifiant n8n.

**Recommandation principale :** `deskgate init` génère la tâche avec `pythonw.exe -m deskgate serve` (pythonw voisin de `sys.executable`, pas de `gui-scripts`), le runner journalise dans `%LOCALAPPDATA%\Deskgate\logs\runner.log` après l'acquisition du mutex, le workflow d'exemple porte deux déclencheurs (manuel + webhook) et des `id` fixes, et la recette est un script Python en bibliothèque standard qui pilote n8n (webhook + API) et le runner (`schtasks`, `taskkill`).

## Pile standard

### Cœur (déjà dans le dépôt, rien à ajouter)
| Bibliothèque | Version | Rôle | Pourquoi |
|---|---|---|---|
| Typer | `>=0.27,<0.28` | commandes `init`, `doctor`, `task install/remove` | déjà la CLI ; `typer.confirm`, `--yes`, `typer.testing.CliRunner` pour les tests |
| `importlib.resources` (stdlib) | 3.11+ | lire `runner.example.toml` livré dans la roue | la roue contient bien `deskgate/runner.example.toml` [test] |
| `xml.etree.ElementTree` (stdlib) | 3.11+ | générer et relire le XML de la tâche | pas de dépendance ; échapper les chemins par l'API ET (jamais de f-string non échappée en production) |
| `subprocess` + `schtasks.exe` | Windows | créer, lancer, relire, supprimer la tâche | seul moyen sans élévation ni dépendance (COM/pywin32 écartés par STACK.md) |
| `tomllib` (stdlib) | 3.11+ | valider le `runner.toml` écrit par `init` | `load_config` existe déjà : `init` doit finir par `load_config(path)` pour prouver que le fichier produit est valide |

### Infrastructure n8n
| Élément | Version / référence | Rôle | Vérifié |
|---|---|---|---|
| `docker.n8n.io/n8nio/n8n` | `2.43.8@sha256:a18edcf018198b33b5488fb47ededafe11e0b10d28f65b9535b7c447c9ce3b2c` | n8n épinglé | digest de l'index multi-architecture confirmé par `docker buildx imagetools inspect` le 2026-10-21 [test] |
| `postgres` | `17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24` | base de n8n | digest relevé le 2026-10-21 [test] ; le choix de la majeure 17 est le nôtre (MOYENNE) |
| Docker Compose | v5.5.1 (machine) | orchestration | `docker compose config` valide le fichier [test] |

### Alternatives écartées
| Au lieu de | Option | Pourquoi pas |
|---|---|---|
| `pythonw -m deskgate serve` | `[project.gui-scripts] deskgatew` | Fonctionne aussi [test] mais ajoute un processus intermédiaire (voir § Lanceur) ; la commande `-m` ne dépend ni du PATH ni de l'empaquetage |
| Import par API publique | Import par CLI dans le conteneur | L'API exige une clé d'API (création via session du propriétaire) ; la CLI n'a besoin de rien et accepte le jeton sur stdin. L'API reste la voie du sondage des exécutions |
| `schtasks /Create /SC ONLOGON` en ligne | XML | Le XML porte `RestartOnFailure`, `ExecutionTimeLimit`, batterie, `InteractiveToken` ; la ligne de commande ne les expose pas |

**Installation :** rien de nouveau dans `pyproject.toml`. Nouveaux marqueurs pytest à déclarer (`--strict-markers`) : `scheduler` (vraie tâche du Planificateur) et `docker` (exige `docker compose`).

## Modèles d'architecture

### Structure recommandée
```
src/deskgate/
├── cli.py              # + init, doctor, task (install | remove | status), --version
├── scheduler.py        # NOUVEAU : XML de la tâche (pur) + enveloppe schtasks
├── installer.py        # NOUVEAU : logique de init (gabarit, dossiers, jeton) sans Typer
├── doctor.py           # NOUVEAU : vérifications, chacune renvoie (état, message)
├── runtime.py          # + journal fichier après le mutex
n8n/
├── docker-compose.yml
├── .env.example        # .env ignoré par git (ajouter n8n/.gitignore)
├── README.md           # procédure d'import et de recette
└── examples/ifc-clash.json
scripts/recette/        # NOUVEAU : script de recette ACC-01/ACC-02 (stdlib seulement)
```
Règle 1 de CLAUDE.md respectée : rien de BIM dans `src/deskgate`. Le bloc d'exemples de `runner.example.toml` cite `ifc.clash` en commentaire (déjà le cas, test existant `test_runner_example.py`).

### Modèle 1 : XML de tâche, vérifié sans élévation [test]

Création par `schtasks /Create /XML <fichier> /TN <nom> [/F]`, fichier encodé UTF-16 **avec BOM** (`xml.encode("utf-16")`, ou `write_text(..., encoding="utf-16")`). Ce XML exact a été créé, lancé (`/Run`), relu (`/Query /XML`) et supprimé (`/Delete /F`) sur un compte standard, sans invite UAC :

```xml
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Runner Deskgate</Description></RegistrationInfo>
  <Triggers>
    <LogonTrigger><Enabled>true</Enabled><UserId>DOMAINE\nom</UserId></LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>DOMAINE\nom</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure><Interval>PT1M</Interval><Count>3</Count></RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>C:\...\Scripts\pythonw.exe</Command>
      <Arguments>-m deskgate serve</Arguments>
      <WorkingDirectory>C:\Users\moi\AppData\Local\Deskgate</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
```

Faits relevés [test] :
- **Aucune erreur** d'accès refusé, y compris pour `RestartOnFailure`, `ExecutionTimeLimit` et le déclencheur de session.
- Le processus démarré par `/Run` vit en **session 1** (interactive, `ProcessIdToSessionId`) avec `sys.stdout is None` sous `pythonw`.
- Résultat `Dernier résultat: 267009` (0x41301, `SCHED_S_TASK_RUNNING`) pendant l'exécution.
- La **relecture** `schtasks /Query /TN x /XML` renvoie un XML **normalisé** : `UserId` converti en SID, `RunLevel` **absent** quand il vaut `LeastPrivilege` (valeur par défaut), éléments par défaut supprimés (`Hidden`, `Priority`, `Enabled`…), `<UseUnifiedSchedulingEngine>` ajouté. `doctor` doit donc traiter « `RunLevel` absent » comme `LeastPrivilege` et ne tester `AllowStartOnDemand`, `Enabled`, etc. que si présents.
- La sortie de `schtasks` est **localisée** (français ici, cp850) : ne jamais analyser le texte. Seul le **code de retour** (0 = ok, 1 = absente) et le **XML** sont fiables. La déclaration `encoding="UTF-16"` du XML relu ne correspond pas aux octets reçus (texte déjà décodé) : retirer la déclaration par expression régulière avant `ET.fromstring` (vérifié).
- `/Create ... /F` écrase une tâche existante : c'est l'idempotence de `init`.
- `/Delete /F` supprime ; `/Query /TN absent` renvoie 1.
- **P4 de PITFALLS résolu** : `RestartOnFailure` ne relance **pas** un processus tué par `taskkill /F /T` (140 s d'observation, une seule ligne de démarrage). Ne pas le présenter comme un superviseur ; il reste dans le XML (D-03) pour les échecs de démarrage.
- Un second runner lancé en parallèle (relance explicite après un arrêt, ou `IgnoreNew`) sort proprement avec le code 3 (mutex) : sans risque de doublon.

L'utilisateur du XML s'obtient par `USERDOMAIN` + `\` + `USERNAME` (ou `getpass.getuser()`). Utiliser ElementTree pour construire le document (échappement correct des chemins contenant `&`).

### Modèle 2 : lanceur sans console

**Mesures [test]** avec un paquet jouet installé par `uv tool install` dans un dossier jetable (`UV_TOOL_DIR`, `UV_TOOL_BIN_DIR`) :
- `[project.gui-scripts]` **produit bien** un `.exe` de sous-système GUI (2) à côté du `.exe` console (3) : `toyw.exe` à côté de `toy.exe`. Lancé, il exécute `...\Scripts\pythonw.exe` du venv de l'outil.
- Chaîne de processus pour `toyw.exe` : trampoline `toyw.exe` → `pythonw.exe` du venv → `pythonw.exe` de base : **trois processus**. Un `-m` direct sous la tâche en donne deux (redirecteur du venv + interpréteur).
- Sous `pythonw`, `sys.stdout` et `sys.stderr` valent `None`.
- Le **vrai runner** (`.venv\Scripts\pythonw.exe -m deskgate serve`, lancé détaché, stdio vers `DEVNULL`) répond à `/health`, accepte une tâche, la termine `succeeded` : l'absence de flux ne casse ni Uvicorn (`log_config=None`), ni le moteur, ni le sous-processus du plugin [test].
- Mais : **aucun journal n'est écrit nulle part** (le dossier de données ne contient que la base et `runner.toml`). `runtime.configure_logging()` écrit sur `sys.stderr`, qui vaut `None`.

**Recommandation (prescriptive) :**
1. Action de la tâche : `Command` = `Path(sys.executable).with_name("pythonw.exe")` résolu **au moment de `init`** (depuis `deskgate.exe` installé par `uv tool install`, `sys.executable` est le `python.exe` du venv de l'outil, `pythonw.exe` est à côté [test]) ; `Arguments` = `-m deskgate serve` ; `WorkingDirectory` = dossier de données. Pas de `gui-scripts` (un processus de moins, aucun PATH, `python -m deskgate` est l'entrée prévue par `__main__.py`).
2. Ajouter à `runtime.py` un `RotatingFileHandler` (`%LOCALAPPDATA%\Deskgate\logs\runner.log`, par exemple 5 × 2 Mio), avec le même `RedactingFilter`/`RedactingFormatter`, installé **après** `acquire_mutex` (RUN-03 : un second runner ne doit rien écrire) et avant `bind_exclusive`. Le garder en plus du flux stderr quand celui-ci existe (le terminal reste utile). Les erreurs de configuration invalide, qui surviennent **avant** le mutex, ne sont alors visibles que par `deskgate doctor` ou `deskgate serve` en console : le dire dans `doctor`.
3. `cli.py` gère déjà `sys.stdout is None` (test `isinstance(TextIOWrapper)`). Vérifier que `_err()` de `runtime.py` (qui teste `sys.stderr is not None`) reste le seul point d'écriture direct.
4. Chemin de mise à jour : `uv tool upgrade deskgate` échoue si `pythonw.exe` du venv tourne (fichiers verrouillés). `deskgate task end` (ou `schtasks /End`) avant la mise à jour : à documenter dans `AGENTS.md`.
5. Si `DESKGATE_HOME` est défini à l'installation, la tâche ne peut pas le reproduire (le Planificateur ne pose pas de variable d'environnement). `init` doit refuser d'installer la tâche dans ce cas, avec un message, plutôt que d'installer une tâche qui lirait un autre dossier.

### Modèle 3 : conception de `deskgate init` (D-02), idempotent

Ordre et comportement (chaque étape indépendante, relançable, résumé final par étape) :

| Étape | Premier passage | Relance |
|---|---|---|
| `runner.toml` | écrit depuis `importlib.resources` : remplace la ligne `token_sha256 = "0…0"` par le hash, et (si `--root` différent de `C:/BIM`) les deux lignes `allowed_roots`/`host` ; puis `load_config(path)` pour prouver la validité | **existe : intact**, aucun nouveau jeton, message « déjà initialisé » ; `--force` : sauvegarde `runner.toml.bak-<horodatage>` (qui conserve les blocs de capacités) puis réécrit |
| Dossiers | `depot`, `travail`, `livrables` sous la racine, `logs`, `plugins` sous le dossier de données (`mkdir(parents=True, exist_ok=True)`) | rien à faire |
| Jeton | `generate_token()` + `hash_token()` existants ; **jeton seul sur stdout** (une ligne), tout le reste (guidage, consigne « copiez-le dans l'identifiant n8n ») sur stderr via `typer.echo(err=True)`, comme `dev-token` | aucun jeton affiché (impossible de le retrouver : le dire) |
| Tâche | `typer.confirm("Installer la tâche…")` ; `--yes` supprime la question ; `--no-task` la saute ; `/Create /XML /F` | tâche déjà conforme : message, sinon recréée avec `/F` après confirmation |

Pourquoi le jeton seul sur stdout : l'exécuteur automatique (Claude) peut rediriger stdout vers un fichier hors dépôt (`deskgate init --yes > fichier`) et lire le jeton **sans l'écrire dans le chat ni dans un journal** (règle de AGENTS.md), tandis que l'humain voit tout dans sa console. Même schéma que `dev-token` existant.

Autres points :
- `deskgate --version` n'existe pas alors que `AGENTS.md` le prescrit [test : « No such option: --version »] : ajouter un callback `--version` (Typer `is_eager`).
- Valider le chemin racine saisi avec `normalize_host_path` (existant) ; refuser UNC.
- `deskgate task install | remove | status` (ou `uninstall-task`) : `remove` fait `/End` (ignorer l'échec si non lancée) puis `/Delete /F`. Ne supprime ni `C:\BIM` ni la base (plan de retour arrière PUB-05).
- Tests : `typer.testing.CliRunner` avec `DESKGATE_HOME` et `--root` dans `tmp_path`, `--no-task` ; la partie Planificateur testée séparément (§ Validation).

### Modèle 4 : conception de `deskgate doctor` (D-04)

Chaque vérification renvoie `ok | avertissement | échec` + message français ; code de sortie 1 s'il existe au moins un échec. Vérifications minimales :
1. **Configuration** : `load_config` (message d'erreur existant relayé).
2. **Dossiers** : racines autorisées, `depot`, `travail`, `livrables`, `work_root` ; dossier de données.
3. **Jeton** : `token_sha256` différent de la valeur « tout à zéro » du gabarit.
4. **Tâche** : `/Query /XML` ; échec si absente ; contrôle `ExecutionTimeLimit == PT0S`, `DisallowStartIfOnBatteries == false`, `StopIfGoingOnBatteries == false`, `MultipleInstancesPolicy == IgnoreNew`, `LogonType == InteractiveToken`, `RunLevel` absent ou `LeastPrivilege`, présence d'un `LogonTrigger`, `Command` existant sur disque et pointant `pythonw.exe` ; avertissement (pas échec) si `RestartOnFailure` absent.
5. **Port** : `GET /health` sur `host:port` : répond = « runner joignable (version) » ; sinon tenter l'ouverture (`socket.bind`) pour distinguer « libre » (ok) de « occupé par autre chose » (échec).
6. **Plugins** : pour chaque capacité `kind = "python"`, `python` existe ; `settings.bcf_executable` s'il est déclaré ; `command` de chaque `mcp_servers`.
7. **Veille** (avertissement) : lire `powercfg` est localisé et fragile ; se contenter d'un avertissement générique si une tâche longue est attendue (P5).
8. Option `--n8n` (facultative, hors D-04) : `docker compose -f n8n/docker-compose.yml exec -T n8n wget -qO- http://host.docker.internal:<port>/health`.

### Modèle 5 : compose n8n (INS-03, D-05)

`docker compose config` accepte ce fichier [test] ; non démarré (n8n de l'utilisateur sur 5678 intact). Le montage `C:/BIM:/data` est accepté par Docker Desktop et le répertoire est **inscriptible par l'utilisateur `node`** du conteneur [test, conteneur jetable de l'image locale 2.42.5].

```yaml
name: deskgate-n8n
services:
  postgres:
    image: postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-n8n}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?définir POSTGRES_PASSWORD dans .env}
      POSTGRES_DB: ${POSTGRES_DB:-n8n}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10
  n8n:
    image: docker.n8n.io/n8nio/n8n:2.43.8@sha256:a18edcf018198b33b5488fb47ededafe11e0b10d28f65b9535b7c447c9ce3b2c
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "127.0.0.1:${N8N_HOST_PORT:-5679}:5678"
    environment:
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: postgres
      DB_POSTGRESDB_PORT: "5432"
      DB_POSTGRESDB_DATABASE: ${POSTGRES_DB:-n8n}
      DB_POSTGRESDB_USER: ${POSTGRES_USER:-n8n}
      DB_POSTGRESDB_PASSWORD: ${POSTGRES_PASSWORD}
      N8N_ENCRYPTION_KEY: ${N8N_ENCRYPTION_KEY:?définir N8N_ENCRYPTION_KEY dans .env}
      N8N_WEBHOOK_URL: http://127.0.0.1:${N8N_HOST_PORT:-5679}/
      N8N_EDITOR_BASE_URL: http://127.0.0.1:${N8N_HOST_PORT:-5679}/
      N8N_SECURE_COOKIE: "false"          # interface en http local
      GENERIC_TIMEZONE: ${GENERIC_TIMEZONE:-Europe/Zurich}
      TZ: ${GENERIC_TIMEZONE:-Europe/Zurich}
      N8N_DIAGNOSTICS_ENABLED: "false"
      N8N_VERSION_NOTIFICATIONS_ENABLED: "false"
    volumes:
      - n8n_data:/home/node/.n8n
      - ${DESKGATE_SHARE:-C:/BIM}:/data
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1:5678/healthz >/dev/null || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 12
      start_period: 30s
volumes:
  postgres_data:
  n8n_data:
```

Notes de vérification :
- **`WEBHOOK_URL` vs `N8N_WEBHOOK_URL`** : `N8N_WEBHOOK_URL` existe depuis n8n 2.30.0 ; `WEBHOOK_URL` en est un alias **déprécié depuis 2.35.0** (fonctionne, journalise un avertissement) [doc]. Le compose du dépôt (2.43.8) utilise `N8N_WEBHOOK_URL` ; le n8n de l'utilisateur (2.42.5) a `WEBHOOK_URL`, ce qui fonctionne aussi. Le CONTEXT D-05 écrit `WEBHOOK_URL` : l'intention (URL joignable depuis Windows) est identique, la variable moderne est préférable.
- **Pas de `N8N_RUNNERS_ENABLED`** : absent de la config de 2.43.8 ; seul `N8N_RUNNERS_MODE` (`internal` par défaut) existe [code]. Ne rien mettre.
- **Pas de `extra_hosts: host-gateway`** : Docker Desktop fournit déjà `host.docker.internal` (01-D1 réussi sans). Le déclarer pourrait changer l'adresse résolue ; le réserver à une variante Linux documentée.
- **Santé** : l'image n8n **n'a pas de `HEALTHCHECK`** [Dockerfile] ; la nôtre interroge `/healthz` (chemin par défaut de `N8N_ENDPOINT_HEALTH`) avec le `wget` présent dans l'image [test].
- Les secrets viennent de `.env` (non versionné) ; fournir `.env.example` avec des valeurs factices et la commande de génération (`python -c "import secrets; print(secrets.token_hex(32))"`). Ajouter `n8n/.gitignore` avec `.env`. `N8N_ENCRYPTION_KEY` doit rester **stable** (chiffre les identifiants en base).
- `restart: unless-stopped` : comportement voulu pour un poste ; ne pas utiliser `latest`.
- Premier `up` : téléchargement des images (n8n, Postgres) ; prévoir `docker compose pull` explicite et un délai.

### Modèle 6 : workflow d'exemple (INS-04, D-06)

**Exécuté de bout en bout sur n8n 2.42.5** [test] avec le vrai runner (capacité factice `demo.sleep`) : exécution créée par webhook, HTTP Request `202 {job_id, status: queued}`, exécution `waiting`, reprise par le rappel du runner, `If` vrai → « Succès » (sortie `{resultat: 'succes', job_id, duree_s, resume, artefacts}`).

Points de forme confirmés :
- Wait **v1.1** : paramètres `resume: "webhook"`, `httpMethod: "POST"`, `limitWaitTime: true`, `limitType: "afterTimeInterval"`, `resumeAmount`, `resumeUnit` (`seconds | minutes | hours | days`), `options: {}` [code du nœud lu dans l'image].
- `{{ $execution.resumeUrl }}` est évalué dans le corps du HTTP Request (nœud antérieur au Wait) : l'URL contient `?signature=…` et le runner l'appelle telle quelle.
- Le corps du rappel arrive dans `$json.body` après le Wait : `$json.body.status`, `.job_id`, `.duration_s`, `.summary`, `.artifacts`, `.error`.
- **Échéance du Wait (P6) confirmée sur 2.42.5** [test, échéance 90 s, tâche de 130 s] : à l'échéance le workflow **continue sans erreur** et la sortie du Wait est l'**item d'entrée** (ici la réponse du HTTP Request `{job_id, status: "queued"}`), **sans clé `body`**. Donc le test doit viser `$json.body?.status` et **non** `$json.status` (qui vaudrait `queued` et tromperait un test naïf). Le rappel tardif est ensuite abandonné par le runner (`abandoned_stale`, 409 traité, CB-03).
- Fuite côté n8n à connaître : en cas d'erreur du HTTP Request, n8n inscrit la requête (donc la `resumeUrl` avec sa signature) dans l'erreur d'exécution et dans les journaux du conteneur. Cela reste dans le périmètre de n8n (même secret que celui qu'il détient) ; ne pas le recopier dans les rapports de recette.

JSON complet recommandé (à placer dans `n8n/examples/ifc-clash.json`). Il porte un `id` de workflow et un `id` d'identifiant **fixes** (voir § Import) et deux déclencheurs : manuel (interactif) et webhook (programmable) :

```json
{
  "id": "DeskgateClash0001",
  "name": "Deskgate - ifc.clash (soumettre puis attendre le rappel)",
  "nodes": [
    {
      "parameters": {},
      "id": "11111111-1111-4111-8111-111111111101",
      "name": "Lancement manuel",
      "type": "n8n-nodes-base.manualTrigger",
      "typeVersion": 1,
      "position": [0, 160]
    },
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "deskgate-ifc-clash",
        "responseMode": "onReceived",
        "options": {}
      },
      "id": "11111111-1111-4111-8111-111111111102",
      "name": "Lancement par webhook",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2,
      "position": [0, 400],
      "webhookId": "5b1c0f0e-8a52-4c3a-9d55-2f0f6b6a0a01"
    },
    {
      "parameters": {
        "mode": "raw",
        "jsonOutput": "={{ { capability: $json.body?.capability ?? 'ifc.clash', params: $json.body?.params ?? { ifc_a: '/data/depot/PIC-EXE-AW-CVC-MNQ-BaJ-SUP-30701-IFC4.ifc', selector_a: 'IfcFlowSegment, IfcFlowFitting', ifc_b: '/data/depot/PIC_REV_HRS_ARC_MNQ_BaJ_SUP_30400.ifc', selector_b: 'IfcWall, IfcSlab, IfcBeam, IfcColumn', mode: 'hard', tolerance: 0.01, bcf: true }, timeout: $json.body?.timeout ?? 14400 } }}",
        "options": {}
      },
      "id": "11111111-1111-4111-8111-111111111103",
      "name": "Parametres",
      "type": "n8n-nodes-base.set",
      "typeVersion": 3.4,
      "position": [260, 280]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "http://host.docker.internal:8765/jobs",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({ capability: $json.capability, params: $json.params, timeout: $json.timeout, callback: { url: $execution.resumeUrl } }) }}",
        "options": { "timeout": 30000 }
      },
      "id": "11111111-1111-4111-8111-111111111104",
      "name": "Soumettre a Deskgate",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [520, 280],
      "credentials": {
        "httpHeaderAuth": { "id": "DeskgateToken0001", "name": "Deskgate" }
      }
    },
    {
      "parameters": {
        "resume": "webhook",
        "httpMethod": "POST",
        "limitWaitTime": true,
        "limitType": "afterTimeInterval",
        "resumeAmount": 6,
        "resumeUnit": "hours",
        "options": {}
      },
      "id": "11111111-1111-4111-8111-111111111105",
      "name": "Attendre le rappel",
      "type": "n8n-nodes-base.wait",
      "typeVersion": 1.1,
      "position": [780, 280],
      "webhookId": "5b1c0f0e-8a52-4c3a-9d55-2f0f6b6a0a02"
    },
    {
      "parameters": {
        "conditions": {
          "options": { "caseSensitive": true, "leftValue": "", "typeValidation": "strict", "version": 2 },
          "conditions": [
            {
              "id": "c1",
              "leftValue": "={{ $json.body?.status }}",
              "rightValue": "succeeded",
              "operator": { "type": "string", "operation": "equals" }
            }
          ],
          "combinator": "and"
        },
        "options": {}
      },
      "id": "11111111-1111-4111-8111-111111111106",
      "name": "Succes ?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2.2,
      "position": [1040, 280]
    },
    {
      "parameters": {
        "mode": "raw",
        "jsonOutput": "={{ { resultat: 'succes', job_id: $json.body.job_id, duree_s: $json.body.duration_s, resume: $json.body.summary, artefacts: $json.body.artifacts } }}",
        "options": {}
      },
      "id": "11111111-1111-4111-8111-111111111107",
      "name": "Succes",
      "type": "n8n-nodes-base.set",
      "typeVersion": 3.4,
      "position": [1300, 180]
    },
    {
      "parameters": {
        "mode": "raw",
        "jsonOutput": "={{ { resultat: $json.body?.status ?? 'delai_depasse_sans_rappel', job_id: $json.body?.job_id ?? null, erreur: $json.body?.error ?? null } }}",
        "options": {}
      },
      "id": "11111111-1111-4111-8111-111111111108",
      "name": "Echec ou delai",
      "type": "n8n-nodes-base.set",
      "typeVersion": 3.4,
      "position": [1300, 400]
    }
  ],
  "connections": {
    "Lancement manuel": { "main": [[{ "node": "Parametres", "type": "main", "index": 0 }]] },
    "Lancement par webhook": { "main": [[{ "node": "Parametres", "type": "main", "index": 0 }]] },
    "Parametres": { "main": [[{ "node": "Soumettre a Deskgate", "type": "main", "index": 0 }]] },
    "Soumettre a Deskgate": { "main": [[{ "node": "Attendre le rappel", "type": "main", "index": 0 }]] },
    "Attendre le rappel": { "main": [[{ "node": "Succes ?", "type": "main", "index": 0 }]] },
    "Succes ?": { "main": [[{ "node": "Succes", "type": "main", "index": 0 }], [{ "node": "Echec ou delai", "type": "main", "index": 0 }]] }
  },
  "settings": { "executionOrder": "v1" }
}
```

Remarques :
- Le workflow importé avec `"id"` par la CLI est **inactif**. L'`If` a deux sorties : `true` (succès) et `false` (tout le reste, y compris `failed`, `timeout`, `cancelled`, `interrupted` et l'échéance sans rappel).
- `limitWaitTime` à 6 h doit **dépasser** le `timeout` de la tâche (14 400 s = 4 h dans l'exemple) plus une marge.
- Différence 2.42.5 / 2.43.8 : **aucune identifiée**, mais ce JSON n'a été exécuté que sur 2.42.5 (l'image 2.43.8 n'a pas été téléchargée : consigne). À reconfirmer à la première exécution sur le compose (voir Questions ouvertes). Pas de `typeVersion` récent hasardeux : les versions utilisées (Webhook 2, HTTP Request 4.2, Set 3.4, If 2.2, Wait 1.1) sont celles acceptées par 2.42.5 et dans la fourchette que 2.43.8 déclare pour Wait (`[1, 1.1]`) [code].
- Un second exemple `mcp.call` (facultatif, D-06) : même squelette, `capability: "mcp.call"`, paramètres du serveur et de l'outil ; à écrire d'après le schéma de la capacité (phase 4) sans nouvelle recherche.

### Modèle 7 : import dans n8n sans coder le jeton en dur [test]

**Voie recommandée : CLI dans le conteneur** (aucune clé d'API, aucun jeton sur disque) :
```powershell
# 1. Propriétaire (une seule fois) : le premier appel crée le compte, route non authentifiée de n8n
#    POST /rest/owner/setup  {"email","firstName","lastName","password"}   (mot de passe >= 8 car., majuscule, chiffre)
# 2. Identifiant « Deskgate » avec id fixe ; le jeton passe par stdin (jamais dans un fichier ni un journal)
'[{"id":"DeskgateToken0001","name":"Deskgate","type":"httpHeaderAuth","data":{"name":"Authorization","value":"Bearer <JETON>"}}]' |
  docker compose -f n8n/docker-compose.yml exec -T -u node n8n n8n import:credentials --input=/dev/stdin
# 3. Workflow (id fixe obligatoire dans le JSON)
docker compose -f n8n/docker-compose.yml cp n8n/examples/ifc-clash.json n8n:/tmp/ifc-clash.json
docker compose -f n8n/docker-compose.yml exec -T -u node n8n n8n import:workflow --input=/tmp/ifc-clash.json
# 4. Publication, puis redémarrage pour que le webhook de production soit enregistré (doc n8n)
docker compose -f n8n/docker-compose.yml exec -T -u node n8n n8n publish:workflow --id=DeskgateClash0001
docker compose -f n8n/docker-compose.yml restart n8n
```
Résultats vérifiés [test, n8n 2.42.5] :
- `import:credentials --input=/dev/stdin` fonctionne : « Successfully imported 1 credential. », partagé automatiquement avec le propriétaire ; les identifiants à `id` arbitraire (16 caractères alphanumériques) sont acceptés.
- `import:workflow` **sans** `id` échoue : `SQLITE_CONSTRAINT: NOT NULL constraint failed: workflow_entity.id` (Postgres aura l'équivalent) ; **avec** `id` il réussit, le workflow est importé inactif, et la référence d'identifiant `DeskgateToken0001` n'est pas vérifiée à l'import (d'où l'ordre : identifiant d'abord).
- `publish:workflow` + redémarrage : décrit par la doc officielle (« ne prennent effet qu'au redémarrage si n8n tourne »), **non exécuté** ici (le PUT + activate par API l'a été) : MOYENNE.
- Le propriétaire se crée par `POST /rest/owner/setup` [test] (n8n 2.42.5) ; sinon par l'interface au premier accès. Mot de passe du propriétaire : à poser dans `n8n/.env` (non versionné) pour que l'utilisateur puisse se connecter ensuite.

**Voie API publique (alternative, utile au sondage)** [test] : session `POST /rest/login {"emailOrLdapLoginId","password"}` (cookie), `GET /rest/api-keys/scopes` pour lister les scopes valides du rôle, `POST /rest/api-keys {label, scopes, expiresAt:null}` → `rawApiKey` (affichée une seule fois). Scopes utiles : `workflow:create|read|update|list|activate|deactivate`, `credential:create|list`, `execution:read|list`. **`workflow:execute` n'existe pas** (400 « Invalid scopes for user role ») : aucune route publique ne lance une exécution. Ensuite `POST /api/v1/credentials`, `POST /api/v1/workflows`, `POST /api/v1/workflows/{id}/activate` (réponse `active: true`), `GET /api/v1/executions?workflowId=…&limit=1` et `GET /api/v1/executions/{id}?includeData=true`.

**Pour le n8n de l'utilisateur (5678, 2.42.5), à ne pas modifier** : la voie par défaut est **manuelle** (Import from file dans l'interface, création de l'identifiant « Deskgate » avec le jeton, puis « Execute workflow » avec le déclencheur manuel, qui n'exige aucune publication ni redémarrage). L'import par CLI `docker exec` dans `pipelines-n8n-n8n-1` est techniquement le même que ci-dessus, **sans** `publish:workflow` ni redémarrage, mais il écrit dans la base de cette instance : à ne faire qu'avec l'accord explicite de l'utilisateur.

### Modèle 8 : procédure de recette programmatique (ACC-01, ACC-02)

Un script Python en bibliothèque standard (`scripts/recette/…`), non exécuté par `pytest`, pilote tout. Répété à blanc [test] avec le vrai runner et un faux plugin sur un n8n jetable : trigger → exécution `waiting` → kill → relance → `interrupted` reçu.

1. **Pré-vol** : `GET http://127.0.0.1:8765/health` (runner lancé **par la tâche**, voir 2) ; `GET http://127.0.0.1:5679/healthz` = 200 ; `docker compose exec -T n8n wget -qO- http://host.docker.internal:8765/health` (INS-05) ; maquettes présentes sous `C:\BIM\depot` ; capacité `ifc.clash` déclarée.
2. **Démarrage par la tâche** : `schtasks /Run /TN Deskgate` puis sondage de `/health`. Prouver que le processus vient de la tâche : `Get-NetTCPConnection -LocalPort 8765 -State Listen` → PID ; `Get-CimInstance Win32_Process -Filter "ProcessId=<pid>"` doit montrer `pythonw.exe -m deskgate serve` (et non un terminal), parent `svchost`/Planificateur.
3. **ACC-01 : déclenchement** : `POST http://127.0.0.1:5679/webhook/deskgate-ifc-clash` avec `{"params": {...}, "timeout": 14400}` (réponse `{"message":"Workflow was started"}`, sans identifiant d'exécution) ; **si 404** juste après une publication, attendre et recommencer (enregistrement du webhook : 3 à 6 s observées [test]). Récupérer l'exécution : `GET /api/v1/executions?workflowId=<id>&limit=1` (le script mémorise l'id le plus haut avant le déclenchement pour ne pas lire la précédente).
4. **Attente et sondage** (toutes les 30 s) : statut n8n `waiting` (avec `waitTill`), et en parallèle `GET http://127.0.0.1:8765/jobs/<id>` (jeton) pour la progression. Fin attendue : statut n8n `success`, nœud « Succes » avec `resume` et `artefacts` contenant `conflits.bcf` ; durée du job > 600 s (sinon voir D-09 : élargir sélections/tolérance).
5. **ACC-02** : redéclencher ; quand `GET /jobs/<id>` vaut `running`, tuer le runner : PID du processus qui écoute le port (étape 2) puis `taskkill /F /T /PID <pid>` ; vérifier qu'il n'y a plus de worker (`Get-CimInstance` sur `deskgate_sdk`) ; **relancer explicitement** `schtasks /Run /TN Deskgate` (la tâche ne relance pas seule, [test]) ; attendre `/health` ; la récupération marque le job `interrupted` et envoie le rappel ; l'exécution n8n passe `success` par la sortie « Echec ou delai » avec `resultat: "interrupted"` et `erreur.code: "runner_restarted"` [test à blanc].
6. **Preuves** (dans un fichier de recette, sans jeton ni `signature`) : horodatages, `job_id`, durée, statut n8n, ligne `callbacks` de SQLite (`state = 'delivered'`), chemin et taille du BCF.
7. **Veille (P5)** : la machine a `STANDBYIDLE` à 0 sur secteur (jamais) et pas de batterie [test] ; rien à faire, mais consigner l'état. Aucun code `SetThreadExecutionState` n'existe dans `src/` : à proposer comme tâche facultative (PITFALLS P5 le prévoit « v0.1 ou v0.2 »).

Calcul long : le temps de `ifc.clash` sur ces maquettes est **inconnu** (non mesuré : les environnements de plugins n'existent pas encore). Prévoir une mesure préalable de la durée et de la mémoire dès la première exécution réelle.

### Anti-modèles à éviter
- **Analyser la sortie texte de `schtasks`** : localisée (français sur cette machine). Utiliser codes de retour et XML.
- **Compter sur `RestartOnFailure` ou sur le Planificateur comme superviseur** : démenti [test].
- **Écrire le jeton dans un fichier, un argument de commande ou un journal** : le passer par stdin/stdout redirigé.
- **Reconstruire la `resumeUrl`** : toujours `{{ $execution.resumeUrl }}` tel quel.
- **Tester `$json.status` après le Wait** : l'item d'échéance porte `status: "queued"` à la racine.
- **Lancer `uv python install`** ; **modifier la configuration du n8n de l'utilisateur** ; **`latest`** pour n8n.
- **Créer des fichiers dans `src/deskgate` avant le mutex** (RUN-03) : le journal fichier vient après.

## Ne pas écrire soi-même

| Problème | Ne pas construire | Utiliser | Pourquoi |
|---|---|---|---|
| Planificateur de tâches | COM `Schedule.Service`, pywin32, service Windows | `schtasks /Create /XML` | Sans dépendance ni élévation ; un service est en session 0 (pas de bureau) |
| XML de tâche | concaténation de chaînes | `xml.etree.ElementTree` | échappement des chemins, encodage UTF-16 correct |
| Jeton | générateur maison | `deskgate.core.tokens.generate_token` / `hash_token` | existent, testés |
| Validation de `runner.toml` | contrôle à la main | `load_config` | messages français déjà standardisés |
| Lecture du gabarit | chemin relatif au fichier | `importlib.resources.files("deskgate")` | marche dans la roue installée par `uv tool install` |
| Santé de n8n | boucle maison à l'aveugle | `/healthz` n8n + `healthcheck` compose | l'image n'en a pas |
| Import de workflow | script SQL dans Postgres | `n8n import:workflow` / API publique | schémas internes de n8n |
| Arrêt d'arbre de processus | énumération `psutil` | `taskkill /F /T` (recette) ; Job Object (déjà en place) | orphelins invisibles (vérifs §6) |

**Idée directrice :** tout ce qui touche le Planificateur ou n8n passe par leurs interfaces officielles ; Deskgate n'ajoute que de la glue testable (XML pur, gabarit, vérifications).

## Pièges courants

### Piège 1 : journal absent sous `pythonw`
**Ce qui casse :** le runner démarré par la tâche fonctionne mais aucun journal n'existe ; un échec après le mutex est invisible. **Cause :** `configure_logging` écrit sur `sys.stderr = None`. **Éviter :** journal fichier après le mutex. **Signe :** `deskgate doctor` voit un runner qui ne répond pas, sans trace.

### Piège 2 : webhook de production pas encore enregistré
**Ce qui casse :** `curl` renvoie 404 « not registered » quelques secondes après l'activation [test]. **Éviter :** boucle de sondage jusqu'à autre chose que 404 ; ne jamais conclure à un échec sur un premier 404.

### Piège 3 : expiration du Wait lue comme un succès
Voir Modèle 6. **Éviter :** `If` sur `$json.body?.status`, branche `false` = « échec ou délai ».

### Piège 4 : import CLI sans `id`
`NOT NULL constraint failed: workflow_entity.id`. **Éviter :** `id` fixes dans le JSON d'exemple, et créer l'identifiant `DeskgateToken0001` avant d'activer.

### Piège 5 : `RestartOnFailure` pris pour un superviseur
Voir Modèle 1. **Éviter :** `schtasks /Run` explicite ; documenter qu'un runner tué reste arrêté jusqu'à la prochaine ouverture de session ou à `schtasks /Run`.

### Piège 6 : `DESKGATE_HOME` perdu par la tâche
La tâche ne transmet pas l'environnement. **Éviter :** `init` refuse d'installer la tâche si `DESKGATE_HOME` est défini ; `doctor` signale la divergence.

### Piège 7 : mémoire du Job Object sur la grosse maquette
Le bloc d'exemples met `memory_mb = 8192` ; l'ouverture d'un IFC de 532 Mo avec géométrie peut dépasser (issue `memory_limit`). **Éviter :** pour la recette, `memory_mb` généreux (la machine a 32 Gio, 24 processeurs) et `threads` réglé ; si le job sort `memory_limit`, le consigner plutôt que de baisser les sélections à l'aveugle.

### Piège 8 : copie des maquettes depuis Google Drive
`G:\Mon Drive\...` est un lecteur de flux : la copie de 532 Mo peut déclencher un téléchargement lent. **Éviter :** copier d'abord (`robocopy`/`Copy-Item`) et vérifier tailles (532 804 942 et 51 088 640 octets observés) avant le calcul.

### Piège 9 : mise à jour de l'outil pendant que le runner tourne
`uv tool upgrade deskgate` échoue sur les fichiers verrouillés. **Éviter :** `schtasks /End` avant, `schtasks /Run` après.

### Piège 10 : droits d'écriture de la liaison `C:/BIM`
Vérifié inscriptible par `node` [test]. Si Docker Desktop partage mal le lecteur (autre machine), le symptôme est un `ls /data` vide depuis le conteneur : l'inclure dans la recette INS-05.

## Exemples de code

### Génération du XML (modèle, à adapter)
```python
# Source : XML éprouvé sans élévation (spike du 2026-10-21) ; construction par ElementTree
import xml.etree.ElementTree as ET

NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"

def build_task_xml(*, user: str, command: str, arguments: str, working_dir: str) -> bytes:
    ET.register_namespace("", NS)
    q = lambda tag: f"{{{NS}}}{tag}"
    root = ET.Element(q("Task"), version="1.4")
    ET.SubElement(ET.SubElement(root, q("RegistrationInfo")), q("Description")).text = "Runner Deskgate"
    logon = ET.SubElement(ET.SubElement(root, q("Triggers")), q("LogonTrigger"))
    ET.SubElement(logon, q("Enabled")).text = "true"
    ET.SubElement(logon, q("UserId")).text = user
    p = ET.SubElement(ET.SubElement(root, q("Principals")), q("Principal"), id="Author")
    ET.SubElement(p, q("UserId")).text = user
    ET.SubElement(p, q("LogonType")).text = "InteractiveToken"
    ET.SubElement(p, q("RunLevel")).text = "LeastPrivilege"
    s = ET.SubElement(root, q("Settings"))
    for tag, val in (("MultipleInstancesPolicy", "IgnoreNew"), ("DisallowStartIfOnBatteries", "false"),
                     ("StopIfGoingOnBatteries", "false"), ("AllowHardTerminate", "true"),
                     ("StartWhenAvailable", "true"), ("ExecutionTimeLimit", "PT0S")):
        ET.SubElement(s, q(tag)).text = val
    r = ET.SubElement(s, q("RestartOnFailure"))
    ET.SubElement(r, q("Interval")).text = "PT1M"
    ET.SubElement(r, q("Count")).text = "3"
    a = ET.SubElement(root, q("Actions"), Context="Author")
    e = ET.SubElement(a, q("Exec"))
    ET.SubElement(e, q("Command")).text = command
    ET.SubElement(e, q("Arguments")).text = arguments
    ET.SubElement(e, q("WorkingDirectory")).text = working_dir
    # Le BOM UTF-16 est écrit par l'encodeur « utf-16 » ; la déclaration annonce UTF-16.
    return ('<?xml version="1.0" encoding="UTF-16"?>\n' + ET.tostring(root, encoding="unicode")).encode("utf-16")
```
Remarque : l'ordre des éléments de `Settings` n'a pas d'importance pour le Planificateur (les deux XML testés, l'un à la main, l'autre normalisé par Windows, sont acceptés). Le test unitaire doit relire le résultat avec ET et vérifier chaque réglage de D-03.

### Enveloppe schtasks (sans shell, chemin absolu)
```python
import os, subprocess
SCHTASKS = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "schtasks.exe")

def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([SCHTASKS, *args], capture_output=True, text=True,  # noqa: S603
                          encoding="cp850", errors="replace", check=False)  # sortie localisée : ne lire que returncode
# create : _run("/Create", "/XML", str(fichier_tmp), "/TN", nom, "/F")
# query  : _run("/Query", "/TN", nom, "/XML") ; returncode 1 = absente
# run    : _run("/Run", "/TN", nom)  ;  end : _run("/End", "/TN", nom)  ;  delete : _run("/Delete", "/TN", nom, "/F")
```
Écrire le fichier XML dans un dossier temporaire du dossier de données (supprimé ensuite) ; jamais de jeton dedans.

### Relecture du XML pour `doctor`
```python
import re, xml.etree.ElementTree as ET
def parse_task(xml_text: str) -> ET.Element:
    return ET.fromstring(re.sub(r"^<\?xml[^>]*\?>", "", xml_text.strip()))   # déclaration UTF-16 inexacte après décodage
# RunLevel absent == LeastPrivilege ; UserId relu = SID
```

### Déclenchement et sondage (recette)
```python
# POST webhook (réponse 200 {"message":"Workflow was started"} ; 404 = pas encore enregistré, réessayer)
# GET  /api/v1/executions?workflowId=<id>&limit=1          -> status: waiting | success | error ; waitTill
# GET  /api/v1/executions/<id>?includeData=true            -> data.resultData.runData["Succes"|"Echec ou delai"]
# En-tête : X-N8N-API-KEY (clé lue dans l'environnement, jamais affichée)
```

## État de l'art

| Ancien | Actuel | Depuis | Impact |
|---|---|---|---|
| `WEBHOOK_URL` | `N8N_WEBHOOK_URL` | déprécié 2.35.0, nouveau nom dès 2.30.0 | compose du dépôt : nouveau nom ; le n8n de l'utilisateur garde l'ancien, fonctionnel |
| `N8N_RUNNERS_ENABLED` | `N8N_RUNNERS_MODE` (`internal` par défaut) | 2.x | ne pas poser de variable |
| `n8n update:workflow --active` | `n8n publish:workflow --id` | `--active` déprécié depuis 2.0 | publication en CLI, effet après redémarrage |
| `$resumeWebhookUrl` | `$execution.resumeUrl` | 2.x | utiliser le second |

**Obsolète :** `extra_hosts: host-gateway` sur Docker Desktop (inutile) ; exécution manuelle par l'API publique (n'existe pas).

## Questions ouvertes

1. **Le workflow et la publication se comportent-ils à l'identique sur 2.43.8 ?**
   - Ce qui est établi : tout le parcours a été exécuté sur 2.42.5 (image locale) ; le code de 2.43.8 est celui analysé en cycle 1 et le nœud Wait y déclare `[1, 1.1]`.
   - Ce qui manque : une exécution réelle sur l'image 2.43.8 (non téléchargée).
   - Recommandation : la première tâche de recette sur le compose rejoue exactement le JSON ci-dessus ; en cas d'écart, le consigner (écart de version, D-07).
2. **Import dans le n8n de l'utilisateur par CLI `docker exec` ou à la main ?**
   - Établi : les deux sont techniquement possibles ; D-07 interdit de modifier sa configuration, pas d'y importer un workflow.
   - Recommandation : manuel par défaut (item différable) ; CLI seulement si l'utilisateur l'accepte explicitement.
3. **Durée et mémoire réelles du calcul CVC × ARC** : inconnues avant exécution ; ajuster `memory_mb`, `threads`, `tolerance` et les sélecteurs selon D-09.
4. **`publish:workflow` + `restart` en CLI** : lu dans la doc, non exécuté ; si le redémarrage pose problème, l'API (`POST /rest/api-keys` puis `/api/v1/workflows/{id}/activate`) est la voie vérifiée.
5. **Inhibition de veille** : non implémentée ; inutile sur cette machine (veille jamais sur secteur), à décider (tâche facultative ou report v0.2).
6. **Déclenchement réel à l'ouverture de session** : non automatisable (fermer/rouvrir la session) ; seul `schtasks /Run` est testé. Voir item différable.

## Disponibilité de l'environnement

| Dépendance | Requise par | Dispo | Version | Repli |
|---|---|---|---|---|
| Windows 11 Pro (compte standard) | Planificateur sans élévation | oui | 10.0.26200 | — |
| `schtasks.exe` | INS-02 | oui | système | — |
| `uv` | installation (`uv tool install .`, plugins) | oui | 0.12.17 | — |
| Python (via `UV_PYTHON`) | outil et plugins | oui | 3.14.4 (aussi 3.11.9) | ne jamais `uv python install` |
| Docker Desktop / Compose | INS-03..05, ACC | oui | Docker 29.8.2, Compose v5.5.1 | — |
| Ports 8765 et 5679 | runner, n8n du dépôt | libres | — | `port` / `N8N_HOST_PORT` |
| n8n de l'utilisateur | recette D-07 | en cours (5678, 2.42.5) | 2.42.5 | ne pas le modifier |
| Maquettes `G:\Mon Drive\07_PROJETS\DESKGATE` | ACC-01 | oui | CVC 531 804 942 o ; ARC 51 088 640 o | — |
| Espace disque `C:` | copie, bases | oui | ≈ 830 Go libres | — |
| Mémoire / CPU | calcul | oui | 32 Gio / 24 processeurs | — |
| `%LOCALAPPDATA%\Deskgate`, `C:\BIM` | installation | absents | — | créés par `init` (accord D-01) |
| Environnements de plugins (`bim`, `bcf`) | `ifc.clash` | à créer | — | `uv sync --locked --package … --no-dev` avec `UV_PROJECT_ENVIRONMENT` (AGENTS.md § 4) |
| Images n8n 2.43.8 et Postgres 17 | compose | non téléchargées | — | `docker compose pull` (consenti par INS-03) |
| Batterie | tâche sur batterie | aucune (poste fixe) | — | réglages XML posés quand même |

**Bloquant sans repli :** aucun.

## Architecture de validation

### Infrastructure de tests
| Propriété | Valeur |
|---|---|
| Framework | pytest 9.1 (+ `pytest-timeout`), marqueurs `unit`, `fs`, `proc`, `e2e`, `bim`, `mcp` |
| Config | `pyproject.toml` (`--strict-markers`) : déclarer `scheduler` et `docker` |
| Commande rapide | `uv run pytest -m "unit" -x -q tests/unit` (quelques secondes) |
| Suite complète | `uv run pytest -m "not e2e"` puis `uv run pytest -m e2e` (gate du profil, `.arthemis`) |

### Exigences vers tests
| Exigence | Comportement | Type | Commande automatique | Fichier existe ? |
|---|---|---|---|---|
| INS-01 | `init` crée `runner.toml` valide (`load_config`), dossiers, jeton sur stdout seul, hash cohérent ; relance idempotente ; `--force` sauvegarde | unit (CliRunner, `tmp_path`) | `uv run pytest tests/unit/test_init.py -x` | Wave 0 |
| INS-01 | `--version` répond | unit | `uv run pytest tests/unit/test_cli_version.py -x` | Wave 0 |
| INS-02 | XML conforme à D-03 (relu par ET) ; parseur de relecture tolère `RunLevel` absent | unit | `uv run pytest tests/unit/test_scheduler_xml.py -x` | Wave 0 |
| INS-02 | création/lecture/exécution/suppression d'une vraie tâche `DeskgateTest-<uuid>` sans élévation, supprimée en `finally` | scheduler (Windows) | `uv run pytest -m scheduler tests/proc/test_scheduler_real.py -x` | Wave 0 |
| INS-02 | `doctor` signale chaque réglage dangereux (XML falsifié) | unit | `uv run pytest tests/unit/test_doctor_task.py -x` | Wave 0 |
| D-04 | `doctor` : config invalide, dossier absent, jeton gabarit, port occupé/joignable, plugin absent | unit + e2e léger | `uv run pytest tests/unit/test_doctor.py -x` | Wave 0 |
| runtime | journal fichier créé après le mutex, signature masquée, un second runner n'écrit rien | e2e | `uv run pytest -m e2e tests/e2e/test_serve_logfile.py -x` | Wave 0 |
| INS-03 | compose : images épinglées par digest, `127.0.0.1:5679`, montage sur `/data`, secrets sans valeur par défaut | docker | `uv run pytest -m docker tests/unit/test_compose.py -x` (utilise `docker compose config --format json`, aucun PyYAML) | Wave 0 |
| INS-04 | JSON d'exemple : valide, `$execution.resumeUrl` présent, Wait 1.1 avec `limitWaitTime`, `If` sur `body?.status`, aucun jeton littéral, `id` fixes | unit | `uv run pytest tests/unit/test_example_workflow.py -x` | Wave 0 |
| INS-04 | exécution réelle workflow ↔ runner | acceptation (hors gate) | script de recette, § Modèle 8 | Wave 0 |
| INS-05 | `docker compose exec -T n8n wget -qO- http://host.docker.internal:8765/health` répond | acceptation (machine cible) | commande du Modèle 8, étape 1 | manuel/auto exécuteur |
| ACC-01 | calcul > 10 min, runner lancé par la tâche, résumé + chemin BCF dans n8n | acceptation (long) | script de recette | Wave 0 |
| ACC-02 | `taskkill /F /T` pendant le calcul, `schtasks /Run`, rappel `interrupted` reçu | acceptation (long) | script de recette | Wave 0 |

### Cadence d'échantillonnage
- **Par commit de tâche :** `uv run pytest -m unit -x -q` plus le fichier de test touché (< 30 s).
- **Par fusion de vague :** `uv run pytest -m "not e2e"`.
- **Gate de phase :** gate complet du profil vert (`ruff`, `pyright`, `pytest -m "not e2e"`, `uv build --all-packages`, `pytest -m e2e`) avant `/gsd:verify-work`. Les tests `scheduler` et `docker` s'exécutent sur cette machine ; les marquer pour qu'un environnement sans Docker échoue explicitement (pas de saut silencieux, cohérent avec la décision 04 « pytest.fail, pas de skip »).

### Lacunes de la vague 0
- [ ] `tests/unit/test_init.py`, `test_cli_version.py`, `test_scheduler_xml.py`, `test_doctor.py`, `test_doctor_task.py`, `test_compose.py`, `test_example_workflow.py`
- [ ] `tests/proc/test_scheduler_real.py` (marqueur `scheduler`, nom de tâche jetable, suppression en `finally`)
- [ ] `tests/e2e/test_serve_logfile.py`
- [ ] marqueurs `scheduler` et `docker` dans `pyproject.toml`
- [ ] `scripts/recette/` (déclenchement, sondage, kill, relance) et `.planning/phases/05-…/05-ACCEPTANCE.md` (preuves sans secrets)
- Installation de framework : aucune (pytest en place).

## Classement des interventions humaines (gsd-file-manuelle)

| Élément | Classe | Justification |
|---|---|---|
| Créer `C:\BIM`, `%LOCALAPPDATA%\Deskgate`, installer la tâche | **Aucune intervention** | accord B2 déjà donné (D-01, STATE.md) ; `init --yes` côté exécuteur |
| `docker compose pull/up`, création du propriétaire n8n (REST), import CLI | **Aucune** | couvert par INS-03/04 ; réversible (`down -v`) ; mot de passe du propriétaire dans `n8n/.env` non versionné |
| Création de la clé d'API n8n (si voie API retenue) | évitée | la voie CLI n'en a pas besoin |
| Copie des maquettes depuis G: | **Aucune** (tâche auto) | simple copie |
| Fermer/rouvrir la session pour voir le runner partir seul | **Différable** (`kind: verify`, `blocks: none`) | autostart et reboot sont différables par défaut ; la recette officielle utilise `schtasks /Run` (D-10) |
| Recette sur le n8n de l'utilisateur (import manuel, identifiant « Deskgate », « Execute workflow ») | **Différable** (`kind: verify`, `blocks: none`) | second environnement, constat pass/issue, aucune tâche auto n'en consomme la valeur |
| 04-D1 : rendu du BCF dans BIMcollab Zoom | **Différable** (consigné dans `05-HUMAN-UAT.md` ou soldé dans `04-HUMAN-UAT.md`) | vérification visuelle ; garder son `blocks` d'origine |
| Confirmation d'une montée de `memory_mb`/sélections si le calcul dure < 10 min | **Aucune** | choix réversible à la charge du planificateur/exécuteur (D-09) |

Aucun B1, B2 ni B3 identifié pour cette phase : tous les plans peuvent être `autonomous: true`. Si l'exécuteur choisit un jour de lire le jeton affiché pour le recopier, ce serait une faute (AGENTS.md) : rediriger stdout vers un fichier hors dépôt et ne jamais l'afficher. Les exigences SOC/AUD/PUB du ROADMAP (phase 5) sont portées par le pipeline ARTHEMIS, pas par ce plan de recherche.

## Découpage de plans suggéré

| Plan | Vague | Contenu | Exigences |
|---|---|---|---|
| 05-01 Planificateur | 1 | `scheduler.py` (XML pur + enveloppe), tests unit + test `scheduler` réel, marqueurs | INS-02 |
| 05-02 Journal fichier et `--version` | 1 | `runtime.py` (handler après mutex), `--version`, test e2e du journal | prérequis INS-02/ACC |
| 05-03 `deskgate init` | 2 (dépend 01, 02) | `installer.py`, commandes `init`, `task install|remove|status`, tests | INS-01, INS-02 |
| 05-04 `deskgate doctor` | 3 (dépend 01, 03) | `doctor.py`, tests | D-04 |
| 05-05 Compose et exemples n8n | 1 (indépendant) | `n8n/docker-compose.yml`, `.env.example`, `.gitignore`, `examples/ifc-clash.json`, README n8n, tests statiques | INS-03, INS-04 |
| 05-06 Installation machine et INS-05 | 4 (dépend 03, 04, 05) | `uv tool install .`, `init --yes`, environnements de plugins, bloc de capacités dans `runner.toml`, copie des maquettes, `compose up`, propriétaire, import, publication, vérif INS-05, script de recette | INS-01..05 |
| 05-07 Recette ACC-01/ACC-02 | 5 | exécution du script, mesure durée/mémoire, ajustement D-09, `05-ACCEPTANCE.md`, `<manual-items>` (session, n8n 5678, 04-D1) | ACC-01, ACC-02 |
| (clôture) | — | `AGENTS.md` corrigé d'après l'expérience (`--version`, `task`, `doctor`), `ARCHITECTURE.md` §2 | doc |

Les plans 05-01, 05-02 et 05-05 sont parallélisables. Les modifications de `runner.example.toml` doivent rester compatibles avec `tests/unit/test_runner_example.py` et `test_locations.py` (qui le lisent).

## Contraintes du projet (CLAUDE.md)

- Français partout (documents, messages, journaux, commits) ; identifiants de code, routes et champs JSON en anglais.
- Règle 1 : `src/deskgate` n'importe jamais `deskgate_bim` ni IfcOpenShell (le test d'architecture AST l'impose).
- Règle 2 : pas de `shell=True`, aucune commande construite par concaténation : `schtasks`/`docker` appelés avec une liste d'arguments et un exécutable absolu ; l'exécuteur `cli` n'est pas concerné.
- Règle 5 : écoute `127.0.0.1` seulement, jeton sur toutes les routes sauf `/health` ; n8n publié en `127.0.0.1`.
- Règle 6 : jamais de secret dans manifestes, journaux, audit ; la `resumeUrl` est masquée partout ailleurs que dans l'appel.
- Pile : Python ≥ 3.11, `uv`, FastAPI + Uvicorn, n8n **épinglé 2.43.8** (jamais `latest`).
- Tests : `pytest` ; vrais sous-processus Windows ; les tests obligatoires existants (refus de chemin, arbre de processus, `interrupted`, masquage de la signature, refus de jeton) ne doivent pas être retirés ni ignorés.
- Commits ARTHEMIS : `type(scope): sujet` ≤ 72 caractères, sujet en français ; `.arthemis/**` jamais mêlé au code ni à `.planning/`.
- GSD : `.planning/` n'est écrit que par les commandes GSD ; ne jamais lancer `uv sync --all-packages` ni `uv python install` ; `UV_PROJECT_ENVIRONMENT` avant `uv sync --package`.
- AGENTS.md : demander l'accord avant toute installation globale, création de tâche, écriture hors dépôt et `C:\BIM` (accord déjà donné pour cette recette, D-01) ; ne jamais écrire un jeton dans le chat, un commit ou un journal.

## Sources

### Primaire (HAUTE)
- Expériences exécutées le 2026-10-21 sur cette machine (marquées [test]) : tâche jetable `DeskgateSpike-*` (créée, lancée, relue, supprimée ; vérifiée absente), paquet jouet `uv tool install` avec `gui-scripts` (dossiers jetables du scratchpad), vrai runner sous `pythonw`, n8n jetable 2.42.5 (conteneur `dgspike-n8n`, port 5699, arrêté et supprimé), `docker compose config`, `docker buildx imagetools inspect` (digests), conteneur jetable pour le montage `C:/`.
- Context7 `/n8n-io/n8n-docs` : variables PostgreSQL, CLI `import:workflow` / `import:credentials` / `publish:workflow`, API publique et en-tête `X-N8N-API-KEY`.
- Code de n8n 2.43.8 (GitHub, tag `n8n@2.43.8`) : `endpoints.config.ts` (`N8N_ENDPOINT_REST`, payload 16 Mio), `runners.config.ts` (`N8N_RUNNERS_MODE` par défaut `internal`, pas d'`enabled`), `Dockerfile` (pas de `HEALTHCHECK`, utilisateur `node`, port 5678), `owner.controller.ts` (`POST /owner/setup`, sans authentification), `api-keys.controller.ts` (`POST /api-keys`, `rawApiKey`).
- Image n8n 2.42.5 locale : source compilée du nœud Wait (`limitWaitTime`, `limitType`, `resumeAmount`, `resumeUnit`, versions `[1, 1.1]`).
- `.arthemis/reports/verifs-techniques-cycle-1.md` §1..§4, `.planning/research/STACK.md`, `PITFALLS.md` P4..P6.

### Secondaire (MOYENNE)
- https://docs.n8n.io/hosting/configuration/configuration-examples/webhook-url/ et https://docs.n8n.io/hosting/configuration/environment-variables/endpoints/ : `N8N_WEBHOOK_URL` remplace `WEBHOOK_URL` (déprécié dès 2.35.0), disponible dès 2.30.0.
- https://docs.n8n.io/hosting/cli-commands/ : indicateurs de `import:workflow`, `publish:workflow` (effet après redémarrage), `update:workflow --active` déprécié.

### Tertiaire (BASSE)
- Aucun élément retenu ne repose sur une source unique non vérifiée. Le choix de Postgres 17 relève du jugement (compatible n8n, non spécifié par la doc consultée).

## Métadonnées

**Confiance :**
- Pile standard : HAUTE (outils du dépôt, digests relevés, compose validé par `docker compose config`).
- Planificateur et lanceur : HAUTE (exécuté, y compris l'absence de relance automatique).
- Workflow et import : HAUTE sur 2.42.5, MOYENNE pour 2.43.8 (non exécuté) et pour `publish:workflow` + redémarrage.
- Recette : HAUTE pour la mécanique (répétition à blanc réussie), BASSE pour la durée et la mémoire réelles du calcul CVC × ARC (jamais mesurées).
- Pièges : HAUTE (la plupart observés).

**Date de la recherche :** 2026-10-21
**Valide jusqu'au :** 2026-11-20 (n8n publie des correctifs quasi quotidiens ; la montée de version reste un acte explicite)

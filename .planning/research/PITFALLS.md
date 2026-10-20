# Pièges du domaine

**Domaine :** passerelle locale Windows (runner Python) entre n8n (Docker Desktop) et des outils lourds (IfcOpenShell, CLI, MCP stdio)
**Recherché le :** 2026-10-20
**Confiance globale :** MOYENNE (voir niveau par piège ; les points [code n8n] sont HAUTE, le reste vient surtout de l'expérience du domaine et doit être confirmé par un test sur la machine)

Ce document ne reprend pas `.arthemis/reports/verifs-techniques-cycle-1.md` (Job Object, psutil, 16 Mio, `host.docker.internal`, signature `resumeUrl`, roues IfcOpenShell). Il traite ce qui n'y figure pas. Les phases visées suivent `ROADMAP.md` : v0.1 (noyau), v0.2 (manifestes, plugins BIM), v0.3 (nœud n8n, interface), v0.4.

Légende : [code] lu dans le code ; [doc] documentation officielle ; [exp] connaissance du domaine, à tester ; [web] source unique.

---

## Pièges critiques

Ceux qui provoquent une réécriture du noyau ou une perte de la promesse « n8n reprend toujours ».

### P1 — Le rappel arrive avant que n8n soit en attente (course HTTP Request → Wait)
**Ce qui casse :** `POST /jobs` rend 202, puis le nœud *Wait* n'est mis en attente qu'après. Une tâche courte (ou `interrupted` immédiat, ou idempotence qui rend un résultat en cache) rappelle la `resumeUrl` alors que l'exécution est encore `running`. Lu dans `waiting-webhooks.ts` (n8n 2.43.8) [code] : exécution en cours → `ConflictError "The execution X is running already."` ; exécution terminée → `ConflictError "... has finished already."` ; terminée en erreur → `ConflictError "... has finished with error."` ; inconnue → `NotFoundError`. Le code HTTP 409 est donc **ambigu** : il signifie soit « réessaie dans une seconde », soit « abandonne ».
**Cause :** un schéma « on rappelle une fois et on abandonne sur 4xx » traite la course comme un échec définitif ; à l'inverse « on réessaie sur tout 4xx » boucle sur une exécution terminée.
**Conséquences :** exécution n8n suspendue jusqu'à son délai, alors que la tâche a réussi. Bug intermittent, visible surtout sur les tâches rapides (donc en test, pas en production).
**Prévention :**
- Politique de réessai par réponse : 2xx = livré ; 401 = abandon (jeton invalide, pas de réessai) ; 409 dont le corps contient « running already » ou « about to resume » = réessai court (0,5 s, 1 s, 2 s…) ; 409 « finished » ou 404 = terminal, tracé `callback_stale` (n8n n'attend plus) ; 5xx, timeout, connexion refusée = réessai à délai croissant et plafonné.
- Délai d'amorçage : ne jamais rappeler dans les premières ~2 s après l'acceptation (`max(0, 2 s - âge)`), en plus de la règle ci-dessus.
- Test d'intégration obligatoire avec une tâche qui se termine en moins de 100 ms.
**Détection :** exécutions n8n « Waiting » à vie pour des tâches `succeeded` ; lignes d'audit avec rappel 409 puis abandon.
**Phase :** v0.1 (rappel) ; revérifier en v0.3 avec le nœud unique (là, le webhook est enregistré à la mise en attente, la fenêtre se réduit sans disparaître).

### P2 — Le résultat est perdu entre « tâche terminée » et « rappel livré » (pas d'outbox)
**Ce qui casse :** le statut passe `succeeded`, le runner plante ou redémarre avant l'envoi, ou n8n est indisponible plus longtemps que les réessais en mémoire.
**Cause :** réessais portés par une tâche asyncio (`asyncio.sleep` en boucle) au lieu de l'état en base.
**Prévention :**
- Table de rappels (outbox) : `callback_status` (`pending | delivered | abandoned_stale | abandoned_exhausted`), `attempts`, `next_attempt_at`, **écrite dans la même transaction que le changement de statut final** de la tâche. Un seul « travailleur de rappel » lit cette table, y compris au démarrage.
- Un redémarrage rejoue tous les `pending` ; c'est aussi ce qui envoie le rappel `interrupted` (§2 ARCHITECTURE). Ne pas coder `interrupted` comme un cas spécial.
- Le corps du rappel est reconstruit depuis la base, pas gardé en mémoire ; l'`attempt` et un `Idempotency-Key`/`job_id` dans le corps permettent au nœud v0.3 de dédupliquer (n8n répond 409 au deuxième appel, ce qui est déjà une idempotence de fait).
- Durée de vie des réessais ≥ le `waitTill` posé côté n8n ; au-delà, abandon tracé.
**Détection :** tâches `succeeded` avec `callback_status = pending` depuis plus de N minutes (à exposer dans `/health` et `deskgate doctor`).
**Phase :** v0.1 (conception de la table dès le premier schéma ; migration coûteuse après).

### P3 — Deux instances du runner en même temps
**Ce qui casse :** Planificateur de tâches + lancement manuel (`deskgate serve`), ou deux sessions (changement rapide d'utilisateur). La deuxième instance démarre, voit des tâches `running`, les passe `interrupted`, envoie des rappels, et peut relancer des tâches en double ; ou échoue sur le port après avoir touché la base.
**Prévention :** verrou d'instance **avant** toute écriture : lier le port d'abord (échec = on sort sans toucher à la base), plus un verrou de fichier exclusif (`msvcrt.locking`/`portalocker` sur `runner.lock`) ou un mutex Windows nommé. La récupération « running → interrupted » ne s'exécute qu'après obtention du verrou. Stocker dans la base le `runner_instance_id` et le PID + heure de création du propriétaire de chaque tâche `running`.
**Détection :** deux lignes `runner_started` sans `runner_stopped` ; rappels en double.
**Phase :** v0.1.

### P4 — La tâche du Planificateur tue ou n'ouvre pas le runner (paramètres par défaut) [exp, à vérifier avec `schtasks /query /xml`]
**Ce qui casse :**
- **Limite d'exécution par défaut de 72 h** : le runner est arrêté sans erreur au bout de 3 jours. Mettre `ExecutionTimeLimit = PT0S`.
- **Batterie** : `DisallowStartIfOnBatteries` et `StopIfGoingOnBatteries` sont vrais par défaut ; sur portable, le runner ne démarre pas ou s'arrête au débranchement.
- **`MultipleInstancesPolicy`** : à `IgnoreNew` (déclenchement répété = pas de deuxième instance, bon) ; ne pas mettre `StopExisting`.
- **Type d'ouverture de session** : « Exécuter même si l'utilisateur n'est pas connecté » = session 0, sans bureau, annule tout l'intérêt (plugins `gui-session`). Il faut `LogonType = Interactive` / « seulement si l'utilisateur est connecté », `RunLevel = Limited` (pas d'élévation : les fichiers créés et les jetons de sécurité diffèrent, et la boîte UAC ne s'affiche pas).
- **`schtasks /create /sc onlogon`** exige souvent l'administrateur ; `Register-ScheduledTask` pour son propre compte peut passer, pas toujours selon la stratégie. Prévoir un repli sans droits (raccourci du dossier Démarrage ou clé `HKCU\...\Run`) et le dire dans `deskgate init`.
- **Redémarrage en cas d'échec** (`RestartCount`/`RestartInterval`) : comportement peu fiable quand le processus se termine par un code d'erreur [exp, LOW] ; ne pas s'en servir comme seul superviseur.
**Prévention :** `deskgate init` génère le **XML de tâche** (ou PowerShell `New-ScheduledTaskSettingsSet`) et non une ligne `schtasks` ; `deskgate doctor` relit la tâche et signale chaque paramètre à risque. Superviseur léger : le lanceur de la tâche est `deskgate serve --supervise` (boucle de relance avec temporisation et compteur), ou un déclencheur supplémentaire « toutes les 5 min, IgnoreNew ».
**Détection :** runner absent le 4e jour ; plus de démarrage après débranchement.
**Phase :** v0.1 (`deskgate init`) ; test de recette sur portable en v0.1.

### P5 — Mise en veille / hibernation : tâches et attentes n8n qui se désynchronisent
**Ce qui casse :** à la veille, le runner, Docker Desktop (VM WSL) et les minuteurs sont gelés. Au réveil : délais maximum mal mesurés (selon l'horloge murale, un sommeil de 8 h = « délai dépassé » et une tâche saine est tuée ; selon l'horloge monotone, peut ne pas compter la veille, selon la source [exp, à mesurer sous Windows 11 : `time.monotonic` repose sur `QueryPerformanceCounter`/`GetTickCount64`]) ; `waitTill` n8n échu pendant la veille (le *Wait* reprend sans résultat, voir P6) ; rappels réessayés sur le réseau Docker pas encore remonté.
**Prévention :**
- Mesurer la durée de tâche en temps actif : échantillonner l'écart horloge murale / horloge monotone toutes les secondes ; si l'écart dépasse 30 s, c'est une veille : décaler l'échéance de la durée constatée et tracer `slept_s` dans la tâche.
- Empêcher la veille pendant les tâches : `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)` par le runner tant qu'une tâche `running` existe (ne couvre pas la fermeture du capot ni la veille forcée). Documenter `powercfg`.
- Au réveil : drapeau « réseau instable » ; réessais de rappel immédiats (pas de rattrapage différé de 30 minutes).
- Fixer `waitTill` côté n8n avec marge large (ARCHITECTURE v0.3 déjà prévu) et indiquer dans l'exemple que « Limit Wait Time » est obligatoire.
**Détection :** tâches `timeout` à durée réelle supérieure à `timeout` de plusieurs heures ; trous dans le journal du runner.
**Phase :** v0.1 (mesure du délai) ; l'inhibition de veille en v0.1 ou v0.2.

### P6 — Le *Wait* n8n expiré reprend « normalement » sans résultat
**Ce qui casse :** avec « Limit Wait Time », à l'échéance, n8n **continue le workflow** par la sortie du nœud, pas par une erreur [doc/exp, à confirmer sur 2.43.8]. Le workflow aval croit avoir un résultat. Un rappel tardif reçoit ensuite 409 « finished already » (P1).
**Prévention :** workflow d'exemple qui teste explicitement la présence de `status` après le *Wait* (nœud `If` : `{{ $json.body.status }}` existe) et traite l'absence comme `timeout`. Documenter. Nœud v0.3 : lever une erreur de nœud à l'échéance au lieu de sortir vide, et brancher « erreur » vers la sortie standard de `continueOnFail`.
**Détection :** résultats vides qui se propagent dans les workflows de coordination.
**Phase :** v0.1 (exemple), v0.3 (nœud).

### P7 — Étiquettes « annulation » et « délai » sans arrêt coopératif ni `CTRL_BREAK` fiable
**Ce qui casse :** le plan §Arrêt poli de la vérification 6 (`CTRL_BREAK_EVENT` puis grâce puis `TerminateJobObject`) suppose une console partagée. [exp]
- `GenerateConsoleCtrlEvent`/`os.kill(pid, CTRL_BREAK_EVENT)` n'atteint que les processus **attachés à la console de l'appelant**. Un runner lancé par le Planificateur n'a pas de console (ou une console cachée) ; avec `CREATE_NO_WINDOW` l'enfant n'a pas de console utilisable, le signal est perdu en silence.
- Avec `CREATE_NEW_PROCESS_GROUP`, `CTRL_C_EVENT` est désactivé pour cet enfant : seul `CTRL_BREAK` passe.
- Envoyer l'événement avec `dwProcessGroupId = 0` frappe **tous les processus de la console, runner compris**.
- Python reçoit `CTRL_BREAK` comme `KeyboardInterrupt` seulement si aucun gestionnaire ne l'a remplacé ; IfcOpenShell (code C++ dans `ifcopenshell_wrapper`) ne vérifie pas les signaux pendant un long calcul natif : le Python ne reprend la main qu'à la fin.
**Prévention :** l'annulation fiable est **coopérative** : `ctx.cancelled()` lit un fichier sentinelle `work_dir/.cancel` (ou un événement Windows nommé) ; pour les plugins `python`, le point d'entrée enveloppe appelle `ctx.cancelled()` entre étapes. `CTRL_BREAK` n'est qu'un bonus facultatif, testé sur un enfant avec son propre groupe, jamais `0`. Le vrai garde-fou reste `TerminateJobObject`. Documenter que les calculs natifs longs ne s'arrêtent qu'à la grâce, donc que la grâce par défaut (10 s) est courte pour ne pas retarder `timeout`.
**Détection :** `cancel` qui dure toujours la totalité de la grâce ; runner qui se ferme avec un `KeyboardInterrupt` lors d'une annulation (signal envoyé à lui-même).
**Phase :** v0.1.

---

## Pièges modérés

### SQLite comme file de tâches

**M1 — `SQLITE_BUSY` immédiat sur promotion de transaction (lecture puis écriture).**
Une transaction `DEFERRED` qui lit puis écrit échoue tout de suite avec `database is locked`, sans attendre `busy_timeout`, si un autre écrivain est passé entre-temps [exp, comportement documenté de SQLite]. Pour la file : `BEGIN IMMEDIATE` pour toute transaction qui écrit ; réclamation atomique en une instruction `UPDATE jobs SET status='running' ... WHERE id = (SELECT id ... LIMIT 1) RETURNING *` (SQLite ≥ 3.35, présent dans le CPython 3.11+ de python.org). Régler `PRAGMA busy_timeout=5000`, `journal_mode=WAL`, `foreign_keys=ON` **à chaque connexion**. Attention au module `sqlite3` : le mode transactionnel hérité (`isolation_level`) ouvre des transactions implicitement ; sous 3.12+, utiliser `autocommit=True` + `BEGIN IMMEDIATE` explicites. Phase : v0.1.

**M2 — Bloquer la boucle asyncio avec `sqlite3` synchrone, ou partager une connexion entre threads.**
Un `fsync` lent (antivirus) fige l'API et le rappel. Prévention : **un seul thread écrivain** (file interne d'ordres d'écriture) et des connexions de lecture par thread, ou `aiosqlite` (qui fait déjà un thread dédié) ; jamais une connexion partagée (`check_same_thread=False` sans verrou). L'écrivain unique supprime aussi la plupart des `BUSY`. Phase : v0.1.

**M3 — Base placée dans un dossier synchronisé, réseau ou monté dans Docker.**
WAL exige un mémoire partagée locale (`-shm`) : OneDrive (le dépôt est sous `Documents`, redirigé vers OneDrive sur beaucoup de PC), SMB, ou le montage `C:\BIM` dans le conteneur provoquent verrous, corruption ou fichiers `-wal` verrouillés par le synchroniseur. Prévention : base et audit dans `%LOCALAPPDATA%\Deskgate\` (jamais sous `C:\BIM`, ni sous un dossier OneDrive) ; `deskgate doctor` refuse un chemin sur un lecteur réseau ou un point d'analyse OneDrive/ cloud (`FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS`). Les artefacts, eux, vivent dans `C:\BIM` (voir M12). Phase : v0.1.

**M4 — Croissance du WAL et sauvegardes incomplètes.**
Une lecture longue (itération de `/jobs` en cours, interface web) empêche les points de contrôle : `-wal` grossit. Prévention : transactions de lecture courtes ; `PRAGMA wal_autocheckpoint` par défaut + `wal_checkpoint(TRUNCATE)` à l'arrêt propre et périodique. Copier seulement `deskgate.db` perd les écritures du `-wal` : sauvegarde par `VACUUM INTO` ou l'API de sauvegarde. Phase : v0.1 (réglages), v0.3 (sauvegarde si l'interface l'expose).

**M5 — `synchronous=NORMAL` et coupure de courant.**
En WAL, `NORMAL` protège de la panne du processus mais pas d'une coupure : les derniers commits peuvent disparaître (le rappel « delivered » peut revenir à « pending », bénin grâce à l'idempotence côté n8n, mais le statut `running → succeeded` peut être perdu). Prévention : `synchronous=FULL` pour une file à faible débit (le coût est négligeable ici) ; choix à écrire dans le code, pas par défaut implicite. Phase : v0.1.

**M6 — Récupération au démarrage incomplète.**
Passer `running → interrupted` ne règle pas : (a) les enfants survivants si le runner a été tué sans fermer le handle du job (`KILL_ON_JOB_CLOSE` couvre la mort du runner, mais pas un handle hérité par un processus étranger), (b) les PID réutilisés, (c) les `work_dir` à moitié écrits, (d) les tâches `queued` avec `idempotency_key` d'une tâche `interrupted` (le client réessaie : politique à fixer, une tâche `interrupted` ne compte pas comme « réussie » pour l'idempotence). Prévention : stocker PID + `create_time` à chaque lancement ; au démarrage, tuer tout processus correspondant à une ligne `running` orpheline (jamais par seul PID) ; nommer le job (`Deskgate-<job_id>`) et ouvrir/terminer par nom ; test « tuer le runner pendant une tâche à petits-enfants » (déjà listé en vérification 6) à relier au test SQLite. Phase : v0.1.

**M7 — Course sur l'idempotence.**
Deux POST simultanés avec la même clé créent deux tâches si le contrôle est « lire puis insérer ». Prévention : index unique partiel `(capability, idempotency_key)` pour les statuts `queued|running|succeeded` ; en cas de conflit, renvoyer la tâche existante (202, même `job_id`). Définir la portée (par jeton ? globale ?) et l'empreinte des `params` : même clé avec params différents = 422, pas un résultat silencieusement faux. Phase : v0.1.

**M8 — Migrations de schéma non prévues.**
Greenfield, mais `interrupted`, `callback_status`, droits par plugin (v0.2) imposent des évolutions. `PRAGMA user_version` + migrations numérotées dès le premier commit ; un test qui ouvre une base d'une version antérieure. Phase : v0.1.

### Sous-processus Windows

**M9 — Fenêtres console qui clignotent.**
Runner lancé par `pythonw.exe` ou sans console : chaque `python.exe`, `uv.exe`, `IfcConvert.exe` enfant crée sa fenêtre. Prévention : `CREATE_NO_WINDOW` (+ `STARTUPINFO.wShowWindow = SW_HIDE`) par défaut pour `python`, `cli` sans interface et pour `uv` ; **ne pas** l'appliquer aux plugins `gui-session` (la fenêtre de l'application doit apparaître). À déclarer dans le manifeste (`window: hidden|normal`). Attention : `CREATE_NO_WINDOW` et `DETACHED_PROCESS` sont exclusifs ; la combinaison avec `CREATE_SUSPENDED | CREATE_NEW_PROCESS_GROUP` est valide. Test : lancement par le Planificateur, observer visuellement. Phase : v0.1.

**M10 — Encodage de la sortie (cp1252/cp850/UTF-8).**
Sous Windows, un enfant Python écrit stdout selon la page de code (cp1252 si fichier/pipe sur beaucoup de PC français, cp850 pour des outils console) ; `subprocess` en `text=True` décode avec la locale → `UnicodeDecodeError` sur « é », « ² » dans un nom de maquette, ou mojibake. Prévention : lire en **octets**, décoder en UTF-8 avec `errors="replace"` ; imposer à nos enfants Python `PYTHONUTF8=1` et `PYTHONIOENCODING=utf-8` ; pour des `cli` tiers, déclarer `encoding: cp850|cp1252|utf-8` dans le manifeste ; le contrat plugin ↔ runner passe par des **fichiers JSON UTF-8** (`result.json`), pas par la sortie standard, qui ne sert qu'au journal. Les journaux sont lus ligne à ligne en octets (une ligne sans fin de ligne et très longue = tampon plein : limiter). Phase : v0.1 (`python`), v0.2 (`cli`).

**M11 — Interblocage des tubes (stdout/stderr pleins).**
Lire stdout puis stderr séquentiellement, ou `communicate()` sans fin sur une sortie volumineuse (IfcOpenShell est bavard), fige l'enfant quand le tampon de tube (≈ 4–64 Kio) est plein : « timeout » inexpliqué. Prévention : lire les deux flux en continu (deux tâches asyncio ou deux threads), écrire dans un fichier de journal plafonné (taille et rotation), ne jamais garder toute la sortie en mémoire. Rediriger vers `NUL` ce qui n'est pas lu. Phase : v0.1.

**M12 — Chemins longs, jonctions, UNC, noms réservés.**
- Limite de 260 caractères (`MAX_PATH`) : `C:\BIM\travail\<job_id>\...` plus des noms de maquettes BIM très longs dépassent vite. Le préfixe `\\?\` est requis pour beaucoup d'API Win32 et **désactive la normalisation** (`..`, `/`) : normaliser avant, puis préfixer ; l'activation `LongPathsEnabled` du registre n'aide pas les outils non déclarés « long path aware » (IfcConvert, anciens CLI). Garder `job_id` court (8 caractères, déjà le cas) et nommer les fichiers de travail par motif court.
- Validation « sous la racine » : `startswith` sur chaînes est faux (`C:/BIM2` passe sous `C:/BIM`, casse, `/` vs `\`, noms courts 8.3 `BIMTRA~1`, flux de données alternatifs `fichier.ifc:flux`, noms réservés `CON`, `NUL`, espaces/points finaux). Résoudre avec `os.path.realpath`/`Path.resolve(strict=False)` **puis** comparer par `Path.is_relative_to` insensible à la casse (`os.path.normcase`), refuser tout chemin UNC (`\\serveur\...`, `\\?\UNC\...`), les chemins d'appareil (`\\.\`, `\\?\GLOBALROOT`), les lecteurs relatifs (`C:fichier`) et les flux alternatifs. Limites connues : `realpath` suit les jonctions et liens symboliques mais il y a toujours une **course contrôle/usage** (TOCTOU) : une jonction substituée entre la validation et l'ouverture. Pour les écritures, créer le fichier dans `work_dir` (créé par le runner, sans droit d'écriture pour d'autres) ; pour les lectures, ré-valider le chemin résolu juste avant de passer l'argument et enregistrer le `realpath` dans l'audit.
- Correspondance `/data` ↔ `C:/BIM` : traiter la conversion comme **préfixe de segment**, pas comme remplacement de sous-chaîne (`/data2/x` ne doit pas devenir `C:/BIM2/x` ; un `/data/../etc` doit être refusé avant conversion).
- Fichiers synchronisés : verrous OneDrive/« Files On-Demand » (fichier cloud non téléchargé = lecture lente ou erreur) ; le point de contrôle de stabilité + hash du §4 de 06-POINTS-OUVERTS s'applique avant tout calcul.
Phase : v0.1 (validation + tests de traversée dès le premier commit : `..`, jonction, lien symbolique créé par le test, UNC, `C:/BIM2`, `CON`, flux alternatif). Le TOCTOU est un risque accepté et documenté.

**M13 — Arguments `cli` : le piège du `CommandLineToArgvW`.**
`subprocess` assemble la ligne de commande par `list2cmdline`, mais chaque programme l'analyse à sa façon : guillemets, barre oblique inverse finale (`"C:\dossier\"`), espaces, `%VAR%`, caractères `^&|` si l'outil est un `.bat`/`.cmd` (appel `cmd.exe /c` implicite → injection même sans `shell=True`). Prévention : refuser les exécutables `.bat`/`.cmd` dans le type `cli` (ou exiger un exécutable `.exe` résolu en chemin absolu), valider chaque paramètre contre son schéma (pas de valeur commençant par `-` quand un chemin est attendu : injection d'option), chemins en barres obliques ou doublées. Phase : v0.2 (exécuteur `cli`).

**M14 — Hérédité de handles et variables d'environnement.**
Un enfant hérite les handles du runner (`close_fds` est vrai par défaut sous Windows sauf si l'on redirige les trois flux standard, subtilité de `Popen` : hérité alors via `STARTUPINFO`/`handle_list`), dont le handle d'écoute du port 8765 : après la mort du runner, un petit-enfant **retient le port** et le redémarrage échoue (`address already in use`). Prévention : `inheritable=False` sur les sockets (Python le fait par défaut depuis 3.4, vérifier pour Uvicorn avec un test : tuer le runner, relancer, port libre) ; environnement des plugins **construit explicitement** (liste blanche : `PATH`, `SystemRoot`, `TEMP`, `PYTHONUTF8`, variables Deskgate), pas hérité en bloc (sinon fuite du jeton Bearer et du secret de rappel dans l'environnement des plugins). Phase : v0.1.

**M15 — Console runner et `Ctrl+C`/fermeture de la fenêtre.**
Lancé à la main dans un terminal, le runner reçoit `CTRL_C`/`CTRL_CLOSE` : prévoir un arrêt propre (`SetConsoleCtrlHandler` ou capture de `KeyboardInterrupt`) qui passe les tâches en `interrupted` et ferme les jobs ; au lancement par le Planificateur il n'y a pas de console : l'arrêt vient de l'arrêt de session/`taskkill` (`WM_ENDSESSION`, non traité par un processus sans fenêtre) : de ce fait, déconnexion/arrêt de Windows = mort brutale, donc récupération au démarrage (M6) indispensable et non une exception. Phase : v0.1.

### asyncio sous Windows

**M16 — Boucle d'événements et sous-processus.**
Depuis Python 3.8, `ProactorEventLoop` est la boucle par défaut sous Windows et gère `asyncio.create_subprocess_exec` ; la `SelectorEventLoop` ne le gère pas (`NotImplementedError`) [doc Python]. Le piège vient du **serveur** : certains modes de démarrage d'Uvicorn (`--reload`, plusieurs workers) ou une politique de boucle posée par une bibliothèque (ou `nest_asyncio`, certains drivers) peuvent imposer la `SelectorEventLoop` [web, source unique : à vérifier dans la doc/le code d'Uvicorn de la version épinglée]. Prévention : lancer Uvicorn **par programme** (`uvicorn.Server(Config(...)).serve()`) depuis `deskgate serve`, un seul worker, sans `--reload` en production ; test de démarrage qui échoue explicitement si `type(asyncio.get_running_loop())` n'est pas `ProactorEventLoop`. Pour limiter la dépendance à la boucle : lancer les enfants avec `subprocess.Popen` dans un thread (plutôt que `asyncio.create_subprocess_*`) : on garde la main sur `CREATE_SUSPENDED`/Job Object (que `asyncio` n'expose pas bien : `creationflags` passe, mais l'assignation au job et `NtResumeProcess` se font de toute façon hors asyncio). Phase : v0.1.

**M17 — Limites du Proactor.**
Descripteurs de fichiers / sockets : `ProactorEventLoop` ne supporte pas `add_reader`/`add_writer` (certaines bibliothèques, par ex. des clients Postgres/ZMQ, en dépendent). Les tubes anonymes de Windows ne supportent pas les lectures asynchrones recouvertes pour `stdin` des enfants dans toutes les situations ; le SDK `mcp` en stdio lance son propre sous-processus via `anyio` : l'insérer dans un Job Object impose de passer par son API de lancement ou de **lancer le serveur MCP nous-mêmes** et de le raccorder. À vérifier tôt : le SDK `mcp` accepte-t-il un lancement personnalisé (paramètres de `StdioServerParameters`) compatible avec `CREATE_SUSPENDED` ? Sinon, assigner au job **après** création et accepter la fenêtre de course, ou envelopper dans un petit lanceur (`deskgate-launch.exe` qui entre dans le job puis lance le serveur). Phase : v0.1 (spike de 1 jour avant l'exécuteur `mcp` ; le plan « création suspendue » ne s'applique pas tel quel).

**M18 — Annulation asyncio qui laisse des enfants vivants.**
`asyncio.wait_for` annule la coroutine, pas le processus. Chaque exécution doit passer par un bloc `try/finally` qui `TerminateJobObject` + ferme le handle, y compris sur `CancelledError`. Ne pas confondre « tâche asyncio annulée » et « job tué » : le registre des jobs actifs vit en base et en mémoire. Phase : v0.1.

**M19 — Uvicorn : arrêt avec des requêtes ouvertes.**
Téléchargement d'artefact ou polling ouvert retarde l'arrêt (`timeout_graceful_shutdown`). Fixer-le (5–10 s) pour que le redémarrage par le Planificateur ne traîne pas. Phase : v0.1.

### Rappels vers n8n

**M20 — Jeton `signature` fuité dans les journaux d'accès et les traces d'erreur.**
Masquer dans l'audit (déjà prévu) ne suffit pas : les journaux d'Uvicorn, `httpx` (niveau INFO affiche l'URL complète), les exceptions (`str(exc)` contient l'URL), les tableaux de bord. Prévention : filtre de journalisation global qui remplace `signature=[^&\s"']+`, désactiver le journal d'URL de `httpx`/`httpcore`, ne jamais mettre `callback.url` brute dans `/jobs/{id}` ni dans `/jobs/{id}/logs` (la rendre masquée en lecture), la stocker chiffrée ou au moins dans une colonne exclue des exports. Test : chercher la signature dans tous les fichiers de journaux après un scénario complet. Phase : v0.1.

**M21 — `callback.url` en SSRF.**
Le runner appelle une URL fournie par le client. Un conteneur local avec un jeton valide peut viser `http://127.0.0.1:8765/...`, un service local Windows, un site interne. Prévention : liste d'hôtes autorisés dans `runner.toml` (par défaut `localhost`, `host.docker.internal`, `127.0.0.1` + le port n8n configuré), schéma `http`/`https` seulement, **pas de redirections suivies** (`follow_redirects=False`), délai court de connexion. À noter : l'URL `resumeUrl` côté n8n est celle que n8n publie : `N8N_WEBHOOK_URL=http://localhost:5678/` (vérif. 2) : **le runner (Windows) joint `localhost:5678`, mais si le workflow transmet l'adresse interne du conteneur (`http://n8n:5678`) le rappel échoue** : valider l'URL à la soumission (résolution, test de connexion à blanc non idempotent interdit) et réécrire le nom d'hôte via une table de correspondance déclarée (pas la reconstruction de la signature : seule la partie hôte change, la query reste intacte : à cadrer avec la règle « appeler telle quelle », à trancher en v0.1). Phase : v0.1.

**M22 — Corps de rappel et limites.**
`status` d'erreur (413 de n8n, vérif. 3) : pas de boucle ; au-delà de 1 Mio, `summary.json`. Autre piège : le corps est écrit dans la base d'exécutions n8n (Postgres) : des champs comme `data` volumineux gonflent la base et ralentissent l'interface n8n bien en dessous de 1 Mio si la file est active. Prévoir un plafond plus bas par défaut (par exemple 256 Kio) et un champ `summary` borné en profondeur. Phase : v0.1.

**M23 — Taille de la file de réessais et tempête au réveil.**
Au redémarrage de n8n ou du PC, des dizaines de rappels `pending` se déclenchent ensemble : limiter la concurrence du travailleur de rappel (≈ 4) et appliquer du *jitter* au délai. Phase : v0.1.

### uv et environnements par plugin

**M24 — Création d'environnement à chaud, hors ligne et concurrente.**
- Premier lancement d'un plugin = `uv venv` + téléchargement de roues (IfcOpenShell ≈ plusieurs dizaines de Mo, numpy, shapely) : minutes, voire échec hors ligne ou derrière un proxy d'entreprise. Si cela se fait dans la tâche, le `timeout` est consommé par l'installation. Prévention : séparer **installation** (`deskgate plugin add`/`sync`, avec progression et erreurs claires) et **exécution** (jamais d'installation implicite) ; l'exécution refuse un plugin dont l'environnement n'est pas prêt (`unavailable`, visible dans `/capabilities`) ; `uv sync --frozen` / `--locked` avec `uv.lock` par plugin ; `UV_OFFLINE=1` en exécution pour interdire tout accès réseau (et détecter les installations accidentelles). Mode « hors ligne » documenté : pré-télécharger dans un dossier de roues (`uv pip install --no-index --find-links`).
- Deux installations en parallèle du même plugin (deux `plugin add`, ou un doctor + une tâche) : verrou par plugin (fichier `.lock` dans le dossier de l'environnement) ; uv a son propre verrou de cache mais pas de l'environnement cible.
- **Cache et disque** : le cache uv (`UV_CACHE_DIR`) et les environnements doivent être sur le **même volume** pour que l'édition de liens (`hardlink`) fonctionne ; sinon uv **copie** (avertissement `Failed to hardlink`) : plusieurs Go par plugin ; avec `C:\BIM` ou un environnement sur un autre disque/OneDrive, c'est le cas. Régler `UV_LINK_MODE` explicitement et le noter dans `doctor`. Les hardlinks partagent les fichiers : une mise à jour ou `uv cache clean` ne casse pas un environnement existant, mais **un environnement dont les roues viennent d'un cache purgé** reste valide (fichiers liés) ; un environnement **copié depuis un autre PC** ne l'est pas.
- Antivirus (Defender) : analyse de milliers de petits fichiers à la création : minutes ; prévoir une exclusion documentée pour le dossier des environnements (recommandation, jamais appliquée automatiquement).
- Python géré par uv : `uv python install` télécharge un CPython (hors ligne = échec) ; si les versions installées du système changent (désinstallation de 3.11), les venvs pointant vers celles-ci cassent : épingler `--python-preference only-managed` pour les environnements de plugins, et un contrôle `doctor` qui lance `python -c "import sys"` dans chaque environnement.
- `requirements.txt` non verrouillé : `ifcopenshell>=0.8` dérive vers 0.9 puis 0.10 (API changeante). `==` par défaut + `uv.lock` + test de fumée par plugin.
- Chemin de l'environnement > 260 caractères (M12) : `C:\Users\<nom>\AppData\Local\Deskgate\envs\<plugin>\Lib\site-packages\...` : garder des identifiants de plugin courts (hachés) dans le chemin ; vérifier avec `LongPathsEnabled`.
Phase : v0.1 pour un environnement fixe de `ifc.clash` (script de préparation + `doctor`), v0.2 pour le cycle de vie générique.

**M25 — Le runner lui-même et `uv`.**
Si `deskgate` est installé par `uv tool install`, une mise à jour remplace l'environnement du runner en cours d'exécution (fichiers `.pyd`/`.exe` verrouillés sous Windows : « Accès refusé »). Mise à jour = arrêt du runner d'abord ; `deskgate update` ou documentation explicite. Phase : v0.2.

### IfcOpenShell : calculs lourds

**M26 — Mémoire.**
Un IFC de plusieurs centaines de Mo se charge en mémoire à raison de plusieurs fois sa taille ; `ifcclash` construit un arbre BVH/maillages pour deux sélections ; le multiplicateur grimpe avec des maquettes CVC. Un `MemoryError` ou un « killed » silencieux (Windows ne tue pas par OOM : il swappe jusqu'à figer la machine, y compris Revit et Docker). Prévention : `JobMemoryLimit`/`JOB_OBJECT_LIMIT_PROCESS_MEMORY` déjà prévus : l'échec doit être **classé** (`failed` avec cause `memory_limit`, détectée par le code de sortie `STATUS_NO_MEMORY` / `MemoryError` ou par `JobObjectNotificationLimitInformation`) et non un `timeout` après 3 h ; plafond par défaut proportionnel à la RAM (par exemple 50 %), partagé avec le plafond WSL2 (`.wslconfig`, 06-POINTS-OUVERTS §4). `cpu-heavy = 1` n'empêche pas Docker/n8n de consommer : tester le scénario complet. Fermer et rouvrir : un `ifcopenshell.file` n'est pas toujours libéré (références croisées) ; un processus par tâche (déjà prévu) est la bonne parade : ne **jamais** réutiliser un processus ouvrier entre tâches. Phase : v0.1 (`ifc.clash`).

**M27 — `ifcopenshell.geom.iterator` multiprocessus sous Windows.**
Windows n'a pas `fork` : `multiprocessing` démarre en `spawn`, réimporte le module principal. Conséquences : (1) script de plugin **sans** protection `if __name__ == "__main__":` → chaque ouvrier ré-exécute le script (explosion récursive de processus ou erreur `RuntimeError: An attempt has been made to start a new process before the current process has finished its bootstrapping phase`) ; (2) le paramètre `num_threads` de `iterator(settings, file, num_threads)` utilise des threads C++ dans le processus, pas `multiprocessing` : choisir `num_threads` explicitement (le défaut ou `os.cpu_count()` peut saturer l'hôte et affamer n8n/Docker : passer `DESKGATE_THREADS` du plafond de §3 et le lire dans le plugin) ; (3) les objets `ifcopenshell.file` et de géométrie **ne se transmettent pas** entre processus (non sérialisables par `pickle`, ou très coûteux) : paralléliser par fichiers (un processus par IFC) ou par tranches d'éléments en ré-ouvrant le fichier ; (4) les ouvriers `multiprocessing` lancés par le plugin **restent dans le Job Object** (ils en héritent), bon, mais leur mémoire s'additionne contre le plafond du job ; (5) `ifcclash` a son propre `multiprocessing` selon la version : à lire et à tester sur 0.9.0.post1. Prévention : le plugin lance son code dans `__main__` protégé, `multiprocessing.freeze_support()` si le plugin est jamais gelé, test avec ≥ 2 ouvriers. Phase : v0.1 (spike de 0,5 jour sur `ifcclash` avant le plugin) ; confiance : [exp], à confirmer par lecture du code d'`ifcclash` 0.9.

**M28 — Déterminisme (résultats différents d'une exécution à l'autre).**
Pour que l'idempotence (« même clé → même résultat ») et la comparaison de conflits entre exécutions aient un sens : l'ordre des conflits dépend de l'ordre d'itération du threadpool (`num_threads > 1` : ordre non déterministe de sortie de l'itérateur), des itérations sur des `set`/`dict` Python, de tolérances flottantes différentes selon le nombre de threads/versions d'OpenCASCADE, et de l'ordre des entités du fichier. Les `GlobalId` sont instables entre versions de maquette (06-POINTS-OUVERTS). Prévention : trier les résultats (par couple de `GlobalId`, puis géométrie) avant écriture ; écrire dans le résumé la version d'IfcOpenShell, la tolérance et les réglages géométriques (`USE_WORLD_COORDS`, etc.) ; hacher l'entrée (empreinte SHA-256 du fichier) dans l'audit ; GUID BCF dérivés (UUID v5 d'une paire de `GlobalId` + tolérance) plutôt qu'aléatoires, sinon le BCF d'une même détection change à chaque exécution et pollue le suivi dans BIMcollab/Solibri ; horodatages du BCF mis à part. Test de non-régression : deux exécutions, même sortie octet par octet (hors horodatage). Phase : v0.1 (`ifc.clash`).

**M29 — Chemin et encodage des IFC.**
Chemins non ASCII (accents) passés au C++ d'IfcOpenShell : OK en 0.9 en général, mais les versions anciennes d'IfcConvert et des CLI tiers utilisent la page de code ANSI ; tester `Maquette_é.ifc` dans le dossier. Les fichiers `.ifczip` : extraction temporaire dans `work_dir`, nettoyage. Fichiers IFC encore en cours d'écriture par la synchronisation : voir M12 (stabilité + hash). Phase : v0.1.

### Frontière GPL (`deskgate-bcf`)

**M30 — Frontière de licence rendue poreuse par le packaging.**
Appeler un programme séparé par JSON est une frontière défendable, mais elle se casse sans bruit : (1) `deskgate-bim` (MIT) déclare `deskgate-bcf` en **dépendance** installée dans le même environnement uv et l'importe « pour gagner du temps » ; (2) un `pyproject.toml` racine d'espace de travail uv qui publie un seul paquet contenant les deux ; (3) un utilitaire commun (`deskgate_common`) importé des deux côtés mais copié dans le GPL ; (4) les schémas/typages du JSON partagés comme module Python importé par les deux : c'est du code lié, pas un format. (5) `ifcclash` importe `bcf-client` lui-même quand on active son export BCF : dans l'environnement du plugin `ifc.clash`, `bcf-client` (GPL-3) est installé et importé **dans le même processus** que le code MIT : c'est exactement ce que l'architecture veut éviter (« l'export BCF intégré d'`ifcclash` n'est utilisé que depuis `deskgate-bcf` »). Il faut donc vérifier si `ifcclash` importe `bcf-client` à l'import du module (alors le simple `import ifcclash` charge du GPL dans le processus MIT) ou seulement à l'appel de l'export [à lire dans le code d'`ifcclash` 0.9 : non vérifié ici]. Prévention : `bcf-client` **uniquement** dans l'environnement uv de `deskgate-bcf` ; environnement séparé de celui d'`ifc.clash` ; si `ifcclash` l'exige en dépendance dure, l'environnement d'`ifc.clash` le contient mais le code MIT ne l'appelle jamais, et la question juridique (agrégation de dépendances installées vs. combinaison) est notée comme risque accepté, à faire relire (je n'ai pas de source juridique : [LOW], ne pas présenter comme tranché) ; test d'architecture automatisé : un contrôle de CI qui échoue si `import bcf` (ou `bcf_client`) apparaît hors de `plugins/bim/bcf/`, et un second qui liste les licences de toutes les dépendances de chaque environnement (`pip-licenses`/`uv pip` + liste de refus pour GPL/AGPL hors `deskgate-bcf`). Le contrat JSON est un **schéma de données** (JSON Schema) décrit dans la documentation, pas un module Python partagé.
**Autres éléments :** fichier `LICENSE` et en-têtes SPDX par fichier dans `plugins/bim/bcf/` ; `pyproject.toml` du paquet avec `license = "GPL-3.0-or-later"` ; l'obligation de fournir le **code source** de `deskgate-bcf` à ceux qui reçoivent un binaire (si un jour livré par installateur : joindre les sources) ; le mot « distribué sous MIT » du README ne doit pas couvrir le répertoire. Vérifier la licence exacte de `bcf-client` (GPL-3 seule ou « ou ultérieure ») et de ses propres dépendances. Phase : v0.1 (dès que `deskgate-bcf` existe) ; contrôle CI dès le premier commit du paquet.

**M31 — `bcf.write`/`bcf.read` comme plugin `cli` : mêmes pièges que M10/M13.**
Le BCF contient des noms, commentaires et captures (PNG) : encodage UTF-8 dans le JSON (`ensure_ascii=False`, fichier ouvert en `utf-8`, **pas** `open()` sans encodage, qui prend cp1252 sous Windows), chemins en entrée de fichiers (les validations de M12), taille des captures (images base64 dans le JSON : mettre les captures en fichiers référencés, pas inline). Lecture d'un `.bcf` inconnu = archive ZIP non fiable : zip-bomb et chemins `..` dans l'archive (« Zip Slip ») : plafonner la taille décompressée et le nombre d'entrées. Phase : v0.1/v0.2.

---

## Pièges mineurs

**m1 — Port 8765 déjà pris ou réservé** (plages réservées par Hyper-V/WSL, `netsh interface ipv4 show excludedportrange protocol=tcp`) : `doctor` le détecte ; message clair plutôt que trace Python. Phase : v0.1.

**m2 — Vérification `Host`** (anti-DNS-rebinding, déjà notée en vérif. 2) : accepter `127.0.0.1`, `localhost`, `host.docker.internal` ; sinon l'appel de n8n est refusé (421/400) : **`host.docker.internal` doit être dans la liste**, point d'oubli classique, à couvrir par le test de bout en bout. Phase : v0.1.

**m3 — Hachage des jetons** : jeton aléatoire de ≥ 32 octets stocké en SHA-256 (pas besoin de bcrypt pour un jeton à haute entropie) ; comparaison en temps constant ; affichage une seule fois à la création. Ne pas logguer l'en-tête `Authorization`. Phase : v0.1.

**m4 — Fuseau et horodatages** : stocker en UTC ISO 8601 avec `Z` ; l'interface convertit. Phase : v0.1.

**m5 — Identifiant de tâche court (8 caractères)** : collisions rares mais réelles sur de longues périodes ; contrainte d'unicité + régénération, ou 12 caractères. Phase : v0.1.

**m6 — Journaux de tâche sans limite** : disque plein par une tâche bavarde (M11) ; plafond par tâche et rotation ; nettoyage des `work_dir` (politique de rétention : 7 jours par défaut) sinon `C:\BIM\travail\` grossit sans fin. Phase : v0.2.

**m7 — Antivirus/Defender et `deskgate.exe`** : un exécutable non signé produit par un lanceur peut être mis en quarantaine ; privilégier `python -m deskgate`/`uv run`. Phase : v0.1.

**m8 — Docker Desktop non démarré à l'ouverture de session** : la tâche du Planificateur démarre avant ; les rappels échouent et le runner doit réessayer sans bruit ; le doctor distingue « runner OK / n8n injoignable ». Phase : v0.1.

**m9 — Tests CI sous Linux seulement** : tout ce qui précède est Windows-spécifique ; la CI doit tourner sur `windows-latest` (GitHub Actions) pour les tests de Job Object, de chemins, de console. Les tests d'intégration lourds (IfcOpenShell réel) sur un petit IFC de fixture. Phase : v0.1.

---

## Avertissements par phase

| Phase / sujet | Piège probable | Mitigation |
|---|---|---|
| v0.1 schéma SQLite | Outbox absente (P2), `user_version` absent (M8), idempotence sans index unique (M7), `synchronous` par défaut (M5) | Schéma conçu une fois : `jobs`, `callbacks`, `audit`, index unique partiel, migrations numérotées |
| v0.1 file et ordonnanceur | `BUSY` sur promotion (M1), boucle bloquée (M2), deux instances (P3) | Écrivain unique, `BEGIN IMMEDIATE`, verrou d'instance avant tout accès à la base |
| v0.1 exécuteur (Job Object) | Annulation sans coopération (P7), tubes pleins (M11), encodage (M10), fenêtres console (M9), handles hérités (M14), spike MCP/anyio (M17) | `ctx.cancelled()` par sentinelle, lecture d'octets en continu, `CREATE_NO_WINDOW`, environnement en liste blanche, spike d'un jour sur `mcp` stdio dans un job |
| v0.1 rappel n8n | Course avant le *Wait* (P1), 409 ambigu, SSRF (M21), fuite de signature (M20), *Wait* vide (P6) | Politique de réessai par réponse, liste d'hôtes, filtre de journalisation, `If` dans l'exemple, test avec tâche < 100 ms |
| v0.1 `deskgate init` | Paramètres du Planificateur (P4), veille (P5) | XML de tâche, `doctor` relit la tâche, `ES_SYSTEM_REQUIRED`, mesure du délai en temps actif |
| v0.1 chemins | Traversée, UNC, jonctions, 260 caractères, préfixe de segment (M12) | Suite de tests d'attaque dès le premier commit, `is_relative_to` insensible à la casse |
| v0.1 `ifc.clash` | Mémoire (M26), multiprocessus `spawn` (M27), non-déterminisme (M28), GPL via `ifcclash` (M30) | Spike `ifcclash` 0,5 jour, plafond mémoire classé, tri des résultats, contrôle d'imports/licences en CI |
| v0.2 manifestes et `cli` | Injection d'arguments, `.bat` (M13), encodages tiers (M10), cycle de vie des environnements uv (M24) | Gabarits validés, `.exe` seulement, `encoding` déclaré, `plugin add`/`sync` séparés de l'exécution, `UV_OFFLINE` en exécution |
| v0.3 nœud n8n | Course à l'enregistrement du webhook (P1), échéance à vide (P6), version du nœud et n8n épinglé | Nœud qui lève une erreur à l'échéance, test sur 2.43.8 puis sur la version suivante avant toute montée |
| v0.3 interface | WAL croissant par lectures longues (M4), `Host` (m2) | Lectures courtes, test de bout en bout depuis le conteneur |

## Pièges à vérifier par un test avant de s'y fier (niveau de confiance faible)

1. Comptabilisation de la veille par `time.monotonic` sous Windows 11 (P5).
2. Comportement du redémarrage en cas d'échec du Planificateur et droits exigés par `/sc onlogon` (P4).
3. Boucle d'événements imposée par Uvicorn selon les options de démarrage (M16) : source unique.
4. `ifcclash` : import de `bcf-client` à l'import ou à l'appel, et `multiprocessing` interne (M27, M30).
5. Sortie du *Wait* à l'échéance sur n8n 2.43.8 : continuation sans erreur (P6).
6. Compatibilité du SDK `mcp` (lancement stdio) avec la création suspendue + Job Object (M17).
7. Analyse juridique de la frontière GPL : à faire relire hors du projet (M30).

## Sources

- `waiting-webhooks.ts` du tag n8n@2.43.8 (erreurs 409 « running already », « about to resume », « finished already », « finished with error » ; 404 « does not exist » ; 401 « Invalid token ») : https://github.com/n8n-io/n8n/blob/n8n@2.43.8/packages/cli/src/webhooks/waiting-webhooks.ts : HAUTE (lu pour cette recherche).
- Documentation Python asyncio, boucles et sous-processus sous Windows (Proactor par défaut depuis 3.8, Selector sans sous-processus) : https://docs.python.org/3/library/asyncio-platforms.html : MOYENNE (connaissance, relue par la recherche web, pas rouverte).
- Note sur Uvicorn `--reload` et la boucle Selector : source unique, tierce : LOW.
- Rapports du dépôt : `.arthemis/reports/verifs-techniques-cycle-1.md`, `ARCHITECTURE.md`, `docs/passation/06-POINTS-OUVERTS.md`.
- Tout le reste (SQLite WAL/BUSY, Planificateur de tâches, console et signaux Windows, `uv`, `multiprocessing` spawn, IfcOpenShell, GPL) : connaissance du domaine [exp], à confirmer par les tests listés ci-dessus ; aucune de ces affirmations n'a été vérifiée dans la documentation officielle pendant cette session.

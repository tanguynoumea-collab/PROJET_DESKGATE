# Deskgate — Vérifications techniques préalables (cycle 1)

Date : 2026-10-20. Portée : les six points de `docs/passation/06-POINTS-OUVERTS.md` §2, en lien avec
`03-ARCHITECTURE.md` §1, §4, §6, §7 et §8.
Le code n8n cité est celui du tag **`n8n@2.43.8`**, l'actuelle version `stable`.

Légende des niveaux de preuve :
- **[code]** : lu dans le code source ;
- **[doc]** : documentation officielle ;
- **[test]** : exécuté sur cette machine ;
- **[communauté]** : forum, issue ou tiers, à considérer comme indicatif.

---

## 1. Un nœud communautaire peut-il mettre l'exécution en attente et être repris par webhook ?

### Constat

Le mécanisme du nœud *Wait* est **générique**. Il ne dépend pas du type de nœud et n'est pas réservé aux nœuds core.

1. **La mise en attente.** `Wait` (qui hérite de `Webhook`) appelle depuis `execute()` la méthode
   `context.putExecutionToWait(waitTill, { acceptsResumeRequest: true })`. Cette méthode fait partie de
   l'interface publique `IExecuteFunctions` de `n8n-workflow` (`interfaces.ts`, l. 1363-1367). Sa signature
   est `putExecutionToWait(waitTill: Date, options?: { acceptsResumeRequest?: boolean })`. Pour une attente
   sans échéance, on passe `WAIT_INDEFINITELY`, une valeur exportée par `n8n-workflow`. [code]
2. **La reprise.** La description du nœud déclare `webhooks: [{ name: 'default', httpMethod: 'POST', path, restartWebhook: true, ... }]`.
   Le nœud implémente `async webhook(context: IWebhookFunctions)`, qui renvoie
   `{ workflowData: [[...]] }`. [code]
3. **Le routage, côté serveur.** `packages/cli/src/webhooks/waiting-webhooks.ts` suit ces étapes :
   - il charge l'exécution en attente ;
   - il vérifie le jeton `signature` ;
   - il retrouve le dernier nœud exécuté ;
   - il cherche dans **ses** webhooks celui qui a la bonne méthode et le bon chemin, avec
     `restartWebhook === true` (l. 404-411).

   **Aucune liste blanche de types de nœuds n'intervient.** Seuls les nœuds *send-and-wait* et *HITL*
   reçoivent un traitement particulier (HMAC). [code]
4. **Environ quinze nœuds core** utilisent ce même mécanisme : Wait, Form, et les opérations
   *sendAndWait* de Slack, Gmail, Teams, Telegram, Discord, WhatsApp, etc. (recherche de code GitHub). L'ADR
   moteur v2 (`ADR-20260902-steps-declare-waits.md`) confirme que le futur moteur traduira
   **tout** appel à `putExecutionToWait` en « déclaration d'attente », quel que soit le nœud. La voie reste
   donc pérenne. [code]
5. **Un nœud communautaire publié le fait déjà : `n8n-nodes-wayza` 0.1.5** (npm). Son code compilé
   `dist/nodes/Wayza/Wayza.node.js` contient :
   - `webhooks: [{ httpMethod: 'POST', path: '={{ $nodeId }}', restartWebhook: true, isFullPath: true }]` ;
   - l'évaluation de `{{ $execution.resumeUrl }}` (avec ajout du suffixe `nodeId` après `?signature=`) ;
   - l'appel `await this.putExecutionToWait(waitTill)` ;
   - un `async webhook()` qui renvoie `workflowData`.

   `n8n-nodes-formstep` exploite aussi `$execution.resumeUrl`. [test : inspection des archives npm]
6. **Changement récent à connaître.** L'URL de reprise contient désormais un jeton
   (`?signature=<token>`), comparé à `execution.data.resumeToken` en temps constant
   (`validateToken`, `waiting-webhooks.ts` l. 186-202). Une URL reconstruite à la main ou sans sa
   query string reçoit une **401 « Invalid token »**. [code]
7. **Restriction de distribution.** Les nœuds communautaires non vérifiés ne sont pas disponibles sur n8n Cloud.
   Ils exigent un n8n auto-hébergé, ce qui est notre cas. [doc]

### Preuves

- Nœud *Wait* : https://github.com/n8n-io/n8n/blob/n8n@2.43.8/packages/nodes-base/nodes/Wait/Wait.node.ts
  (`webhooks` l. 285-310, `webhook()` l. 501, `putExecutionToWait` l. 635)
- Interface : https://github.com/n8n-io/n8n/blob/n8n@2.43.8/packages/workflow/src/interfaces.ts (l. 1363-1367, `IWebhookFunctions` l. 1603, `IWebhookDescription.restartWebhook` l. 3266)
- Routage de reprise : https://github.com/n8n-io/n8n/blob/n8n@2.43.8/packages/cli/src/webhooks/waiting-webhooks.ts
- ADR moteur v2 : https://github.com/n8n-io/n8n/blob/master/packages/@n8n/engine/docs/adr/ADR-20260902-steps-declare-waits.md
- Nœud communautaire existant : https://www.npmjs.com/package/n8n-nodes-wayza (https://github.com/wayza-protocol/n8n-nodes-wayza)
- Doc du nœud Wait : https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.wait/
- Installation des nœuds communautaires : https://docs.n8n.io/integrations/community-nodes/installation/
- Forum (comportement des attentes courtes, `$resumeWebhookUrl` déprécié au profit de `$execution.resumeUrl`) :
  https://community.n8n.io/t/wait-for-webhook-call-for-under-65-seconds/46303

### Conclusion

**FAISABLE.** Un nœud `n8n-nodes-deskgate` peut, en un seul nœud, faire trois choses :
- soumettre la tâche, avec `callback.url = $execution.resumeUrl` évalué dans `execute()` ;
- appeler `putExecutionToWait` ;
- recevoir le rappel dans `webhook()` et le sortir comme données du nœud.

Le plan B (« Soumettre » + *Wait*) reste utile pour la v0.1. L'attente active est inutile.

### Impact sur l'architecture

- §7 v0.3 : retenir le **nœud unique** avec `webhooks[].restartWebhook = true`. S'inspirer du *Wait* et de Wayza :
  - suffixe `$nodeId` pour distinguer plusieurs nœuds Deskgate dans un même workflow ;
  - échéance maximale (`waitTill`) = délai max de la tâche + marge, pour qu'une exécution ne reste jamais
    suspendue indéfiniment si le PC est éteint.
- **Règle runner :** traiter `callback.url` comme **opaque**, l'appeler **telle quelle** (query string comprise)
  et ne jamais la reconstruire. Le jeton qu'elle contient est un secret : le **masquer dans les journaux
  d'audit** (§6).
- v0.1 : le *Wait* « On Webhook Call » avec **« Limit Wait Time »** activé (même raison que l'échéance ci-dessus).
- Le nœud v0.3 devra accepter un rappel authentifié. Pistes : en-tête signé par le runner, vérifié dans `webhook()`,
  en plus du jeton n8n.
- À tester en v0.3 : reprise en mode *queue* (main + webhook process) si on l'adopte un jour. Le mécanisme est
  le même, mais rien n'a été vérifié ici.

---

## 2. Joindre le runner Windows depuis un conteneur Docker Desktop (WSL2) via `host.docker.internal`

### Constat

État de la machine [test] :
- `docker --version` renvoie `Docker version 29.8.2, build 7fc2dff` ;
- WSL : distribution par défaut `docker-desktop`, version 2 ;
- il n'existe **aucun** `%USERPROFILE%\.wslconfig`, donc WSL est en mode réseau **NAT** par défaut.

Aucun conteneur n'a été lancé, conformément à la consigne.

1. **Docker Desktop (backend WSL2).** Dans le conteneur, `host.docker.internal` pointe vers une adresse
   interne (192.168.65.254 dans les versions récentes). Le trafic vers cette adresse ne traverse **pas** le
   réseau Windows. Il est intercepté par la pile réseau en espace utilisateur de Docker Desktop
   (`com.docker.backend`, lignée vpnkit / gVisor), qui **rouvre la connexion côté Windows vers
   `127.0.0.1`**. Un service qui écoute uniquement sur `127.0.0.1` est donc **joignable**.
   - La doc officielle se contente de dire que le nom « résout vers l'adresse IP interne de l'hôte », sans préciser
     l'interface d'écoute. [doc]
   - Le même mécanisme est explicite dans `gvisor-tap-vsock` (pile équivalente utilisée par Podman et Lima) :
     `config.Stack.NAT = { HostIP: "127.0.0.1" }`, l'adresse hôte étant la dernière adresse utilisable du
     sous-réseau. [code]
   - Les retours communautaires concordent. Le serveur voit la connexion arriver **depuis 127.0.0.1**
     (issue de sécurité « loopback unauthenticated bypass »). [communauté]
2. **Conséquence de sécurité.** Pour le runner, une requête venue d'un conteneur est indiscernable d'un
   processus local. **N'importe quel conteneur** de Docker Desktop peut l'atteindre, et pas seulement n8n.
   Le jeton par client (§6) est donc **indispensable** : il ne s'agit pas d'une défense en profondeur.
3. **Mode « mirrored » de WSL2** (`[wsl2] networkingMode=mirrored`). Il permet aux **distributions WSL**
   (Ubuntu…) de joindre les services Windows via `127.0.0.1`. Il concerne la pile réseau WSL elle-même,
   pas le relais de Docker Desktop. Il n'est donc **pas nécessaire** pour Docker Desktop. Il implique en outre le
   pare-feu Hyper-V pour l'entrant. [doc]
4. **Docker Engine installé directement dans une distribution WSL2** (sans Docker Desktop) :
   - `host.docker.internal` n'existe pas par défaut. Avec `--add-host=host.docker.internal:host-gateway`, il
     pointe vers la passerelle du bridge **dans la VM Linux** (172.17.0.1), pas vers Windows. [communauté]
   - En mode **NAT** : il faut viser l'IP Windows vue depuis WSL (`ip route show default`, par exemple 172.x.x.1,
     interface vEthernet (WSL)). Le runner doit alors **écouter sur cette interface**, avec une règle de pare-feu.
     Microsoft recommande `0.0.0.0` dans ce cas, ce qui est à proscrire pour Deskgate. [doc]
   - En mode **mirrored** : 127.0.0.1 depuis WSL atteint Windows, mais **pas** depuis un conteneur en bridge, où
     127.0.0.1 désigne le conteneur. Il faudrait `network_mode: host` pour le conteneur n8n. [doc + déduction]

### Preuves

- Docker, connexion à un service de l'hôte : https://docs.docker.com/desktop/features/networking/networking-how-tos/
- Réseau Docker Desktop : https://docs.docker.com/desktop/features/networking/
- gvisor-tap-vsock, NAT HostIP vers 127.0.0.1 : https://github.com/containers/gvisor-tap-vsock/blob/main/cmd/gvproxy/config.go (l. 234-258)
- Forum Docker (redirection vers le loopback de l'hôte par la VM Docker Desktop) : https://forums.docker.com/t/connection-refused-on-host-docker-internal/136925
- Issue de sécurité (connexion vue comme 127.0.0.1) : https://github.com/jaekanglee/RavenCode/issues/67
- Linux / host-gateway ne joint pas un service sur 127.0.0.1 : https://dev.to/mjnaderi/accessing-host-services-from-docker-containers-1a97
- Microsoft, réseau WSL (NAT vs mirrored, 0.0.0.0, pare-feu Hyper-V) : https://learn.microsoft.com/en-us/windows/wsl/networking
- Issue for-win #10856 (résolution de `host.docker.internal` côté hôte) : https://github.com/docker/for-win/issues/10856

### Conclusion

**Avec Docker Desktop, la configuration la plus restrictive qui marche est la suivante :**
- le runner écoute **uniquement sur `127.0.0.1`** ;
- n8n appelle `http://host.docker.internal:<port>` ;
- aucune règle de pare-feu, aucune écoute sur vEthernet, aucun `.wslconfig`.

**Niveau de confiance : élevé, mais pas encore prouvé sur cette machine.** La doc officielle ne le dit pas noir
sur blanc, et le test n'a pas été lancé, faute d'autorisation de démarrer un conteneur.

**Test de validation à exécuter (2 min) :**
1. `py -3.11 -m http.server 8765 --bind 127.0.0.1` ;
2. `docker run --rm curlimages/curl -s -o /dev/null -w "%{http_code}" http://host.docker.internal:8765/`, qui doit renvoyer `200` ;
3. dans le journal du serveur, constater que l'IP source est `127.0.0.1`.

### Impact sur l'architecture

- §1 : remplacer « écouter aussi sur l'interface utilisée par `host.docker.internal` » par **« écoute sur
  127.0.0.1 uniquement (cible Docker Desktop) »**. Ne prévoir l'écoute sur l'IP vEthernet (WSL) que pour le cas
  « Docker Engine dans WSL en NAT », en option explicite, avec règle de pare-feu limitée au sous-réseau WSL.
- §6 : documenter que **127.0.0.1 ≠ confiance**. Tout conteneur local peut joindre le runner, d'où les points suivants :
  - jeton obligatoire, y compris en local ;
  - aucune route sans authentification, sauf éventuellement `/health` ;
  - vérification de l'en-tête `Host` (anti-DNS-rebinding depuis un navigateur).
- Sens inverse (rappel runner → n8n) : publier n8n en `127.0.0.1:5678:5678` et fixer
  `N8N_WEBHOOK_URL=http://localhost:5678/`. `WEBHOOK_URL` est déprécié depuis 2.35.0. Ainsi
  `$execution.resumeUrl` sera joignable depuis Windows.
- `deskgate doctor` : intégrer le test ci-dessus (depuis le conteneur n8n : `wget host.docker.internal:<port>/health`).

---

## 3. Taille maximale du corps accepté par un webhook / la `resumeUrl`

### Constat

- `N8N_PAYLOAD_SIZE_MAX` : **16 Mio par défaut** (`endpoints.config.ts` : `payloadSizeMax: number = 16`,
  « Maximum request payload size in MiB »). [code + doc]
- `rawBodyReader` est monté globalement (`abstract-server.ts` l. 130), **avant** les routes
  `/webhook-waiting/:path{/:suffix}` (l. 262). Il applique `getRawBody(..., { limit: '16mb' })`. La limite
  vaut donc aussi pour la `resumeUrl`. Le corps décompressé (gzip / deflate) est limité de la même façon. [code]
- `N8N_FORMDATA_FILE_SIZE_MAX` : **200 Mio** par fichier en multipart (webhooks). [code + doc]
- Au-delà de la limite HTTP, le JSON de rappel devient la sortie du nœud. Il est **sérialisé dans les données
  d'exécution en Postgres** et rechargé dans les nœuds suivants : un gros JSON coûte en mémoire et en base.

### Preuves

- https://github.com/n8n-io/n8n/blob/n8n@2.43.8/packages/@n8n/config/src/configs/endpoints.config.ts (l. 150-156)
- https://github.com/n8n-io/n8n/blob/n8n@2.43.8/packages/cli/src/middlewares/body-parser.ts
- https://github.com/n8n-io/n8n/blob/n8n@2.43.8/packages/cli/src/abstract-server.ts (l. 130, 262)
- https://docs.n8n.io/hosting/configuration/environment-variables/endpoints/

### Conclusion

Le plafond dur est de **16 Mio par défaut**, ajustable. Le choix « résumé petit + artefacts en fichiers » est confirmé.

### Impact sur l'architecture

- §3 / §2 : le runner **refuse ou tronque** un rappel au-delà d'un seuil interne prudent, par exemple **1 Mio**,
  configurable dans `runner.toml`. Au-delà, il écrit le résumé complet dans `work_dir/summary.json` et
  le référence dans `artifacts`.
- En cas de 413 au rappel : renvoyer un rappel d'erreur minimal (statut + chemin du résumé), sans boucle de réessai.
- Ne jamais transporter de binaire (IFC, PDF) dans le rappel. Passer par le dossier partagé (§5).

---

## 4. Version de n8n à épingler et nœuds disponibles

### Constat

- **Version stable actuelle : `n8n@2.43.8`**, publiée le 2026-10-19. Les tags Docker `stable`, `latest` et
  `2.43.8` ont le même digest :
  `sha256:a18edcf018198b33b5488fb47ededafe11e0b10d28f65b9535b7c447c9ce3b2c`.
- Branche beta : `2.45.0` (2026-10-20, prerelease). Une ligne de maintenance 1.x existe encore (`1.123.85`).
  [test : API GitHub releases + Docker Hub]
- Nœuds présents dans le tag `n8n@2.43.8` [code] :
  - **Wait** avec reprise par webhook et `$execution.resumeUrl` (cf. point 1) ;
  - **MCP Server Trigger** (`McpTrigger`, versions 1 à 2.1) ;
  - **MCP Client Tool** (`McpClientTool`, versions 1 à 1.4, sous-nœud d'outil pour agent IA) ;
  - **MCP Client** (`McpClient`, « Standalone MCP Client », v1 à 1.1) : appel d'outils MCP **hors agent**, dans
    un workflow classique ;
  - (MCP Registry Client Tool.)
- **Transports des clients MCP n8n : `httpStreamable` et `sse` (déprécié). Pas de stdio.**
  (`nodes/mcp/shared/descriptions.ts`) [code]

### Preuves

- Releases : https://github.com/n8n-io/n8n/releases/tag/n8n%402.43.8
- Docker Hub : https://hub.docker.com/r/n8nio/n8n/tags (tags `2.43.8`, `stable`, `latest`)
- Nœuds MCP : https://github.com/n8n-io/n8n/tree/n8n@2.43.8/packages/@n8n/nodes-langchain/nodes/mcp
- Transports : https://github.com/n8n-io/n8n/blob/n8n@2.43.8/packages/@n8n/nodes-langchain/nodes/mcp/shared/descriptions.ts

### Conclusion

Épingler **`docker.n8n.io/n8nio/n8n:2.43.8`**, idéalement avec son digest. Les trois nœuds requis sont disponibles.
n8n publie des correctifs quasi quotidiens : la montée de version doit être un acte explicite, avec une recette
des workflows d'exemple.

### Impact sur l'architecture

- §7 v0.1 : `docker-compose.yml` d'exemple avec l'image épinglée, plus Postgres, `N8N_WEBHOOK_URL` et le port
  publié en `127.0.0.1`.
- §8 (v0.4, exposition MCP) : le runner doit exposer son serveur MCP en **Streamable HTTP**, car n8n ne sait pas
  lancer de stdio. Le stdio reste réservé aux serveurs MCP *consommés* par les plugins `mcp` du runner.
- Le nœud **MCP Client** (standalone) offre une voie alternative à `HTTP Request` pour des appels courts une
  fois le serveur MCP Deskgate en place. Les tâches longues restent sur le protocole `/jobs` + rappel.

---

## 5. IfcOpenShell via `uv` sous Windows (Python 3.11 / 3.12 / 3.13)

### Constat

- `uv --version` renvoie `uv 0.12.17 (635500036 2026-09-18 x86_64-pc-windows-msvc)`. [test]
- Python présents (`py -0`) : 3.14.4 (par défaut) et 3.11.9. 3.12 et 3.13 sont absents de la machine. [test]
- PyPI : `ifcopenshell` **0.9.0.post1**, publié le 2026-10-15, `requires_python >=3.10,<3.16`.

  Roues **`win_amd64`** (et `win_arm64`) publiées pour **py310, py311, py312, py313, py314, py315**. Les tags
  sont de la forme `pyXY-none-win_amd64` : une roue par version mineure, sans abi3. La version précédente,
  0.8.3.post2, couvrait py310 à py313. [test : API JSON PyPI]
- Test dans des venv jetables du scratchpad. Cache uv local au scratchpad, `UV_PYTHON_DOWNLOADS=never`,
  rien d'installé globalement :

```text
=== Python 3.11
Using CPython 3.11.9 interpreter at: C:\Users\Tanguy\AppData\Local\Python\pythoncore-3.11-64\python.exe
Creating virtual environment at: venv3.11
 + isodate==0.7.2  + lark==1.3.1  + numpy==2.4.6  + pyparsing==3.3.3
 + python-dateutil==2.9.0.post0  + shapely==2.2.0  + six==1.17.0  + typing-extensions==4.16.0
3.11.9 (tags/v3.11.9:de54cf5, Apr  2 2024, 10:12:12) [MSC v.1938 64 bit (AMD64)]
ifcopenshell 0.9.0.post1
IFC4
=== Python 3.14
Using CPython 3.14.4 interpreter at: C:\Users\Tanguy\AppData\Local\Python\pythoncore-3.14-64\python.exe
 + ... numpy==2.5.4, shapely==2.2.0 ...
3.14.4 (tags/v3.14.4:23116f9, Apr  7 2026, 14:10:54) [MSC v.1944 64 bit (AMD64)]
ifcopenshell 0.9.0.post1
IFC4
```

  Commandes utilisées : `uv venv --python 3.11 venv3.11` puis `uv pip install --python venv3.11/Scripts/python.exe ifcopenshell`,
  puis `python -I -c "import ifcopenshell; print(ifcopenshell.version); ifcopenshell.file(schema='IFC4')"`.
  3.12 et 3.13 n'ont **pas** été testés en local, faute d'interpréteur. Les roues existent néanmoins.

### Preuves

- https://pypi.org/project/ifcopenshell/0.9.0.post1/#files (liste via https://pypi.org/pypi/ifcopenshell/0.9.0.post1/json)
- Sortie de commande ci-dessus.

### Conclusion

**OK.** `uv venv` + `uv pip install ifcopenshell` fonctionne nativement sous Windows, sans compilation, de 3.10 à 3.15.

### Impact sur l'architecture

- §2 *Registre et environnements* : le manifeste déclare la version Python. Le runner fait
  `uv venv --python X.Y` et, si l'interpréteur manque, laisse uv le télécharger (`uv python install`, Pythons
  gérés par uv). Il n'y a donc pas de dépendance aux Pythons installés sur le PC.
- **Épingler** `ifcopenshell==0.9.0.post1` (version publiée il y a 5 jours ; l'API 0.8 → 0.9 peut casser des
  scripts). Utiliser un `uv.lock` / `requirements.txt` verrouillé par plugin.
- Partager un cache uv (`UV_CACHE_DIR` sous le dossier Deskgate) : uv lie les fichiers depuis son cache, ce qui
  rend les venvs par plugin peu coûteux.
- Python cible du runner : 3.12 ou 3.13 conseillé (3.11 OK, mais support de sécurité seulement jusqu'à fin 2027).

---

## 6. Arrêt d'un arbre de processus sous Windows (délai maximum)

### Constat

Démonstration exécutée localement : Python 3.11, ctypes, psutil 7.2.2 dans le venv jetable. Script
`scratchpad/jobtest/jobtest.py` et `breakaway.py`. [test]

```text
intermédiaire terminé, petit-enfant pid 92988 vivant: True
psutil children(recursive=True) du runner : [] => petit-enfant trouvé ? False
après TerminateJobObject, petit-enfant vivant : False

le processus de test est-il déjà dans un job (environnement) ? False
job SANS BREAKAWAY_OK -> enfant 47748 dans le job: True ; vivant après TerminateJobObject: False
job AVEC BREAKAWAY_OK -> enfant 123524 dans le job: False ; vivant après TerminateJobObject: True
```

1. **psutil `children(recursive=True)`** reconstruit l'arbre à partir du PPID. Sous Windows, le PPID n'est
   pas maintenu : quand un intermédiaire se termine, ses enfants deviennent **orphelins et invisibles**. Le PID
   parent peut en outre être réutilisé, au risque de tuer un processus étranger. Il existe aussi une course :
   des enfants peuvent naître pendant l'énumération. **psutil ne suffit pas comme mécanisme principal** (prouvé
   ci-dessus). [test]
2. **Job Object** (`CreateJobObjectW` + `SetInformationJobObject(JobObjectExtendedLimitInformation, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)`
   + `AssignProcessToJobObject`) :
   - tous les descendants héritent du job, y compris les orphelins ;
   - `TerminateJobObject` les tue tous ;
   - `KILL_ON_JOB_CLOSE` les tue aussi si le **runner meurt**, puisque le handle se ferme. [test + doc]
3. **Piège de la course au démarrage.** Le processus doit être assigné **avant** de créer ses enfants. `subprocess`
   ne prend pas en charge `PROC_THREAD_ATTRIBUTE_JOB_LIST`. Méthode validée : `creationflags=CREATE_SUSPENDED`,
   puis `AssignProcessToJobObject(p._handle)`, puis `NtResumeProcess` (ntdll, ctypes). Le handle de thread
   n'est pas exposé par `Popen`. [test]
4. **`CREATE_BREAKAWAY_FROM_JOB`.**
   - Si le job **n'a pas** `JOB_OBJECT_LIMIT_BREAKAWAY_OK`, l'enfant reste dans le job, sans erreur sur ce
     Windows 11 26200.
   - S'il l'a, l'enfant **s'échappe** et survit à `TerminateJobObject`.
   - **Ne jamais poser `BREAKAWAY_OK` ni `SILENT_BREAKAWAY_OK`.** [test + doc]
5. **Évasions qu'aucun job n'attrape.** Ces processus ne sont pas des descendants du processus lancé :
   - processus créés **par un tiers** pour le compte du plugin : serveur COM / DCOM hors processus (Revit, Excel
     ou Word pilotés par COM), WMI `Win32_Process.Create`, Planificateur de tâches, services ;
   - `ShellExecute` vers une application **mono-instance déjà ouverte** (la requête est transmise à l'instance
     existante).

   C'est précisément le profil des plugins `gui-session`. [doc + déduction]
6. **Bonus.** Le même job peut plafonner la mémoire (`JobMemoryLimit`) et le nombre de processus. Cela répond
   au « plafond mémoire » de §4, appliqué par le noyau et non plus seulement indicatif.

### Preuves

- Job Objects : https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
- `JOBOBJECT_BASIC_LIMIT_INFORMATION` (KILL_ON_JOB_CLOSE, BREAKAWAY_OK, SILENT_BREAKAWAY_OK) :
  https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information
- Process Creation Flags (CREATE_BREAKAWAY_FROM_JOB, CREATE_SUSPENDED) :
  https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags
- psutil `children()` : https://psutil.readthedocs.io/en/latest/#psutil.Process.children
- Sorties de commande ci-dessus.

### Conclusion et recommandation

Mécanisme principal : **un Job Object par tâche** (ctypes, sans dépendance à pywin32), avec :
- `KILL_ON_JOB_CLOSE` ;
- création suspendue, assignation, puis reprise ;
- pas de breakaway ;
- `JobMemoryLimit` optionnel.

Séquence au délai maximum :
1. arrêt poli : `CTRL_BREAK_EVENT` si lancé avec `CREATE_NEW_PROCESS_GROUP`, ou `WM_CLOSE` pour les GUI ;
2. délai de grâce, par exemple 10 s ;
3. `TerminateJobObject` ;
4. contrôle par `JobObjectBasicAccountingInformation.ActiveProcesses == 0`.

psutil ne sert **qu'en complément** : diagnostic, et nettoyage ciblé des processus COM connus d'un plugin
`gui-session`, par nom d'exécutable + heure de création postérieure au début de la tâche. Ce nettoyage doit
être déclaré dans le manifeste.

### Impact sur l'architecture

- §2 / §4 : ajouter au manifeste `cleanup.extra_process_names` (optionnel, pour les `gui-session`), et une
  limite `memory_mb` appliquée via le job.
- Les serveurs MCP stdio longue durée (plugins `mcp`) vont aussi dans un job propre à chaque serveur, pour
  qu'ils meurent avec le runner.
- Le runner lui-même ne doit pas être lancé dans un job qui interdit les jobs imbriqués. C'est sans objet depuis
  Windows 8, qui gère les jobs imbriqués ; noter le cas si le runner tourne sous un superviseur.
- Tests d'intégration à prévoir : orphelin, fork bomb bornée, dépassement mémoire, mort brutale du runner.

---

## Synthèse

| # | Question | Verdict | Changement d'architecture |
|---|----------|---------|---------------------------|
| 1 | Attente dans un nœud communautaire | **Faisable** (mécanisme générique ; `n8n-nodes-wayza` le fait déjà) | Nœud unique en v0.3 ; `callback.url` opaque, utilisée telle quelle et masquée dans les journaux |
| 2 | `host.docker.internal` → 127.0.0.1 | **Oui avec Docker Desktop** (relais vers le loopback de l'hôte) ; test de 2 min à exécuter | Écoute sur 127.0.0.1 seulement ; jeton obligatoire même en local ; n8n publié en 127.0.0.1 |
| 3 | Taille du rappel | **16 Mio** par défaut (`N8N_PAYLOAD_SIZE_MAX`) | Seuil runner ~1 Mio ; débordement dans `summary.json` |
| 4 | Version n8n | **2.43.8** (stable) ; Wait, MCP Server Trigger, MCP Client Tool et MCP Client présents | Exposition MCP v0.4 en Streamable HTTP (pas de stdio côté n8n) |
| 5 | IfcOpenShell + uv | **OK** : 0.9.0.post1, roues win_amd64 py310 à py315 ; testé en 3.11 et 3.14 | Version Python par plugin, Pythons gérés par uv, épinglage |
| 6 | Arbre de processus | **Job Object** (testé) ; psutil insuffisant (orphelins) | Job par tâche + limite mémoire ; nettoyage COM déclaré |

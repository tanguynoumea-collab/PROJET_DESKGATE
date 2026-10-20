# Recherche de l'existant — Deskgate, cycle 1

Date : 2026-10-20. Périmètre : `docs/passation/06-POINTS-OUVERTS.md` §1, en regard de
`03-ARCHITECTURE.md`. Recherches web réelles (WebSearch / WebFetch). Les affirmations non
confirmées par une source sont marquées **(non vérifié)**.

## Rappel du besoin (grille d'évaluation)

Un service **Windows natif, dans la session utilisateur**, qui :
1. reçoit des tâches longues (20-40 min) d'un orchestrateur (n8n en Docker/WSL2, agents IA via MCP) ;
2. les exécute via des **plugins déclarés par manifeste** (python en venv uv isolé / CLI à gabarit sans shell / outil MCP appelé sans LLM) ;
3. file **SQLite persistante**, concurrence **par ressource** (`gui-session=1`, `cpu-heavy=1`) ;
4. **jetons par client** avec droits par plugin, **journal d'audit**, correspondance `/data ⇄ C:/BIM` ;
5. **rappel asynchrone** (POST sur `resumeUrl` du nœud Wait) ;
6. interface web locale de catalogue ; MIT/Apache ; indépendant de n8n ; installation simple.

Colonnes du tableau : **Win** = fonctionne nativement sous Windows ; **GUI** = peut exécuter dans la
session interactive de l'utilisateur ; **Callback** = rappel HTTP asynchrone vers l'appelant à la
fin d'une tâche ; **Manifeste** = capacités déclarées / typées et découvrables ; **Auth client** =
jetons par client avec droits par capacité.

## Tableau des candidats

| Nom | Licence | Win natif | Session GUI | Callback async | Plugins / manifeste | Auth par client | Verdict | URL |
|---|---|---|---|---|---|---|---|---|
| **Huey** (SqliteHuey) | MIT | Oui en pratique avec workers *thread* ; problèmes connus en mode *process* (pickling sous spawn) | Oui (s'exécute où on le lance) | Non (pas de webhook) | Non (décorateurs Python) | Non | **Brique possible**, mais peu de valeur ajoutée (voir conclusion) | https://github.com/coleifer/huey · https://huey.readthedocs.io/en/stable/api.html |
| **Celery** | BSD-3 | Non supporté officiellement depuis 4.x ; pool *prefork* cassé, seuls *solo/threads* | — | Non | Non | Non | **Écarté** (broker requis, Windows de seconde zone) | https://docs.celeryq.dev/en/stable/userguide/concurrency/index.html · https://www.simplethread.com/running-celery-5-on-windows/ |
| **RQ** | BSD-2 | Partiel : `fork()` absent, `SimpleWorker`/`rq-win` « dev only » | — | Non | Non | Non | **Écarté** (Redis + Windows non cible) | https://pypi.org/project/rq-win/ · https://python-rq.org/docs/testing |
| **Dramatiq** | LGPL-3 | Fonctionne selon retours, broker Redis/RabbitMQ requis | — | Non | Non | Non | **Écarté** (broker externe, LGPL) | https://www.simplethread.com/queue-the-dramatiq-title/ |
| **persist-queue** | BSD-3 **(non vérifié)** | Oui (pur Python + sqlite3) | — | Non | Non | Non | **Brique possible** (file brute), faible apport | https://pypi.org/project/persist-queue |
| **litequeue** | MIT **(non vérifié)** | Oui (pur Python) | — | Non | Non | Non | **Écarté** (trop minimal, peu actif) | https://www.pypi.org/project/litequeue |
| **Procrastinate** | MIT **(non vérifié)** | — | — | Non | Non | Non | **Écarté** (PostgreSQL obligatoire) **(non vérifié en ligne)** | https://github.com/procrastinate-org/procrastinate |
| **Prefect** (process worker) | Apache-2.0 | Oui (worker *process* documenté sous Windows) | Oui si lancé dans la session | Non natif vers n8n (automations / webhooks Prefect) | Déploiements / flows Python, pas de manifeste CLI/MCP | Non en self-hosted (RBAC = Cloud) | **Écarté comme socle** (serveur + Postgres, modèle « flows ») | https://docs.prefect.io/v3/how-to-guides/self-hosted/server-windows · https://docs.prefect.io/v3/api-ref/python/prefect-workers-process |
| **Windmill** workers | AGPLv3 + propriétaire (EE) | **Workers Windows natifs = Enterprise uniquement** (`windmill-ee.exe`) | Non documenté (service recommandé) | Webhooks oui | Scripts typés (schéma auto) — très proche du « catalogue » | Oui (EE / workspaces) | **Concurrent le plus proche fonctionnellement, mais disqualifié** (licence, Windows payant, serveur lourd) | https://www.windmill.dev/docs/misc/windows_workers.md · https://raw.githubusercontent.com/windmill-labs/windmill/HEAD/LICENSE · https://isitreallyfoss.com/projects/windmill/ |
| **Hatchet** | MIT | Engine en conteneur ; worker Python Windows **non confirmé** | Si worker lancé en session | Non (SDK pull) | Non (code Python) | Jetons de tenant | **Écarté** (Postgres + engine, pas de manifeste) | https://pypi.org/project/hatchet-sdk · https://pkg.go.dev/github.com/hatchet-dev/hatchet |
| **Temporal** | MIT (SDK + serveur) | SDK Python : Windows x64 **non confirmé explicitement** | Si worker en session | Non (modèle workflow durable) | Non | mTLS / namespaces | **Écarté** (surdimensionné, impose un cluster) | https://simple-repository.app.cern.ch/project/temporalio · https://community.temporal.io/t/license-and-support-for-temporal/16250 |
| **Kestra** | Apache-2.0 (cœur) | Oui : JAR standalone + *Process task runner* OS-indépendant ; worker distant Windows | Si lancé en session | Webhooks / triggers oui | Plugins Java + flows YAML | RBAC = Enterprise | **Écarté** (JVM, orchestrateur concurrent de n8n, pas un agent léger) | https://kestra.io/docs/installation/windows · https://kestra.io/docs/task-runners/types |
| **GitHub Actions self-hosted runner** | MIT **(non vérifié)** | Oui | Oui via `run.cmd` (pas en service) | Non (lié à GitHub) | Non (workflows YAML) | Via GitHub | **Écarté** (dépend de GitHub, mais confirme le pattern « run.cmd en session ») | https://www.red-gate.com/simple-talk/devops/introduction-to-github-actions-part-3-self-hosted-runners/ |
| **Jenkins agent** | MIT | Oui (JAR) | **Uniquement hors service** (Session 0 casse les GUI) | Non | Non | Via contrôleur Jenkins | **Écarté** (contrôleur Java requis) — enseignement utile sur la session 0 | https://docs.cloudbees.com/d/kb-360029047492 · https://community.jenkins.io/t/jenkins-windows-node-agent-for-gui-testing/1031 |
| **Rundeck / PagerDuty Runbook Automation** | Apache-2.0 (Community) **(non vérifié)** | Nœuds Windows via **WinRM** (pas d'agent en session) | Non (WinRM = session non interactive) | Webhooks de notification | Jobs + plugins Java | ACL Rundeck | **Écarté** (serveur Java, exécution distante WinRM ≠ session GUI) | https://docs.rundeck.com/docs/learning/howto/configuring-windows-nodes.html |
| **Salt minion** | Apache-2.0 | Oui (service) | Non (service) | Event bus Salt | Modules Salt | PKI master/minion | **Écarté** (gestion de config, master requis) | https://docs.saltproject.io/salt/install-guide/en/latest/_sources/topics/install-by-operating-system/windows.rst.txt |
| **Ansible pull** | GPL-3 | Non (contrôleur Ansible non supporté sous Windows) **(non vérifié en ligne)** | — | Non | — | — | **Écarté** | — |
| **Cronicle** (→ xyOps) | MIT | Non documenté (Node.js, Unix-first) | — | Webhooks de notification | Plugins exécutables, JSON stdin/stdout — idée proche | Clés API | **Écarté** (ordonnanceur cron, en maintenance, successeur xyOps) | https://github.com/jhuckaby/Cronicle |
| **Dagu** | **GPL-3.0** | Oui (binaire Go, installeur PowerShell) | Si lancé en session | Non (DAG locaux) | DAG YAML | Basique | **Écarté** (GPL, modèle DAG/cron, pas d'API job+callback) | https://pkg.go.dev/github.com/dagucloud/dagu · https://github.com/dagucloud/dagu |
| **adnanh/webhook**, **HookRun** | MIT | Oui (Go) — HookRun annoncé Linux/Windows/macOS | Si lancé en session | **Non** (synchrone) | Règles YAML commande ← endpoint (proche du `cli` à gabarit) | Secret/signature par hook | **Écarté comme socle**, inspiration pour l'exécuteur `cli` | https://awesome.ecosyste.ms/projects/github.com%2Fadnanh%2Fwebhook · https://pkg.go.dev/github.com/bluvenr/hookrun |
| **supergateway** | MIT **(non vérifié)** | Oui (Node) | — | Non | Non (pont transport stdio⇄SSE/HTTP/WS) | Non | **Brique optionnelle** (pas nécessaire si le runner parle MCP stdio lui-même) | https://mcpservers.org/servers/supercorp-ai/supergateway |
| **mcp-proxy** (sparfenyuk) | MIT | Oui (Python, `uv tool install`) | — | Non | Non | Non | **Brique optionnelle** (même rôle) | https://glama.ai/mcp/servers/sparfenyuk/mcp-proxy |
| **mcpo** (Open WebUI) | MIT | Oui (Python) | — | Non (synchrone) | **Expose les outils MCP en OpenAPI** — génère un catalogue typé | Une clé API unique (ou OAuth 2.1) | **Inspiration / brique** pour l'exécuteur `mcp` ; ne gère ni file ni callback | https://github.com/open-webui/mcpo · https://pypi.org/project/mcpo/ |
| **IBM ContextForge** | Apache-2.0 | Python ; Windows **non confirmé** | — | Non | Registre MCP/REST/gRPC | JWT/OAuth, RBAC, équipes | **Écarté** (gateway d'entreprise, pas d'exécution locale longue) | https://www.everydev.ai/tools/contextforge-ai-gateway |
| **Bifrost**, **Docker MCP Gateway**, **mcp-audit** | Apache-2.0 / MIT / ? | Docker MCP Gateway exige Docker | Non | Non | Non | Bifrost : allow-list par clé virtuelle ; mcp-audit : politiques + audit signé | **Écarté** (passerelles de trafic MCP, pas runners) ; mcp-audit = idée pour l'audit | https://www.getmaxim.ai/articles/best-open-source-mcp-gateway-for-secure-ai-agent-access-2026/ · https://glama.ai/mcp/servers/P4ST4S/mcp-audit |
| **Desktop Commander MCP** | MIT | Oui (Node) | Oui (lancé par le client) | Non (sortie en arrière-plan + `read_output`) | Non (commande libre) | Non | **Écarté** (commande libre = l'inverse du modèle de sécurité visé) | https://archestra.ai/mcp-catalog/wonderwhy-er__desktopcommandermcp |
| **Hermes Agent** (Nous Research) | MIT | — | — | Webhook entrant (HMAC) | — | — | **Hors périmètre** (agent LLM, client de Deskgate, pas runner) | https://fast.io/resources/hermes-agent-n8n-integration/ |
| **NyxID** | Apache-2.0 | — | — | — | — | — | **Hors périmètre** (tunnel sortant agent→services) | https://community.n8n.io/t/open-source-connectivity-gateway-for-ai-agents-turn-localhost-into-an-mcp-server/287391 |
| **Stonebranch × n8n** | Propriétaire | Agent Windows x64 | — | **Polling** de l'exécution n8n | — | — | **Écarté** (commercial, sens inverse : déclenche n8n) | https://docs.stonebranch.com/integrations/n8n |
| **n8n — nœuds communautaires** (A2A, AgentHub…) | divers | — | — | A2A : nœud de callback | Non | — | **Aucun équivalent trouvé** d'un agent Windows d'exécution distante | https://classic.yarnpkg.com/en/package/n8n-nodes-a2a-protocol · https://unpkg.com/n8n-nodes-agenthub@1.0.1/README.md |
| **n8n — Execute Command / SSH** | fair-code | Execute Command s'exécute **dans le conteneur**, et est **désactivé par défaut depuis n8n 2.0** ; SSH vers OpenSSH Windows : fonctionne avec contournements, session non interactive | Non | Non (synchrone, timeouts) | Non | Clé SSH (accès shell complet) | **Écarté** (ni session GUI, ni droits fins, ni tâches de 40 min fiables) | https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executecommand · https://docs.n8n.io/2-0-breaking-changes |
| **n8n — task runners** | fair-code | Sidecar `n8nio/runners` (conteneur) | Non | — | — | Jeton runner↔n8n | **Écarté, confirmé** : n'isole que l'exécution du nœud Code (JS/Python) | https://docs.n8n.io/deploy/host-n8n/configure-n8n/set-up-task-runners/ |
| **n8n — queue mode** | fair-code | Workers = instances n8n + Redis | Non | — | — | — | **Écarté, confirmé** : répartit des exécutions de workflows entières entre instances n8n, pas des tâches sur un hôte Windows | https://railway.com/deploy/n8n-scalable-queue-mode-workers-webhooks |

### Points de mécanique confirmés au passage

- **Wait + `resumeUrl`** : le nœud Wait décharge l'exécution en base et la reprend à l'appel de
  `$execution.resumeUrl` (unique par exécution) ; attention, une exécution partielle change l'URL.
  Le pattern v0.1 « HTTP Request → Wait » est donc le bon. Aucune doc publique trouvée sur
  `putExecutionToWait` pour un nœud communautaire : à vérifier dans le code source de
  `Wait.node.ts` (§2.1 des points ouverts reste ouvert).
  https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.wait · https://community.n8n.io/t/wait-for-webhook-call-for-under-65-seconds/46303
- **Session 0** : tout agent installé comme **service Windows** perd l'accès au bureau
  (Jenkins, GitHub runner). Confirme le choix « Planificateur de tâches à l'ouverture de
  session » de l'architecture.
- **MCP Tasks** : la spec 2025-11-25 a introduit un primitif expérimental *Tasks*
  (« call-now, fetch-later ») ; les sources divergent sur son devenir dans la spec 2026-07-28
  (extension). Pertinent pour la v0.4 (`submit`/`status` vs Tasks MCP) — à vérifier dans le dépôt
  officiel de la spec avant conception.
  https://workos.com/blog/mcp-2025-11-25-spec-update · https://aaif.io/blog/handle-long-running-mcp-tool-calls-with-the-mcp-tasks-extension

## Conclusion argumentée

### 1. Rien ne couvre 80 % du besoin

Aucun projet trouvé ne combine les éléments différenciants de Deskgate : **exécution dans la
session interactive Windows** + **rappel vers une URL fournie par l'appelant** (`resumeUrl`) +
**catalogue de capacités par manifeste couvrant python/CLI/MCP** + **jetons par client avec droits
par capacité** + **léger, sans serveur ni broker**.

Le plus proche fonctionnellement est **Windmill** (scripts typés avec schéma auto-généré,
webhooks, workers, UI) : il couvrirait peut-être 60-70 % *fonctionnellement*, mais il est
disqualifié par trois contraintes dures du projet : les **workers Windows natifs sont réservés à
l'Enterprise Edition**, la licence est **AGPLv3 + code propriétaire** dans les binaires
Community, et il impose un serveur + PostgreSQL, ce qui en fait un **second orchestrateur** à
côté de n8n plutôt qu'un agent local. Kestra et Prefect sont dans la même situation (orchestrateurs
complets, qui doublonnent n8n). Les agents CI (GitHub, Jenkins) et d'administration (Rundeck,
Salt) sont liés à leur contrôleur et, en service, ne voient pas le bureau.

Côté n8n : **task runners** (sandbox du nœud Code) et **queue mode** (répartition d'exécutions
entre instances n8n) sont **confirmés non adaptés**. Execute Command est désactivé par défaut
depuis n8n 2.0 et tourne dans le conteneur ; SSH vers Windows donne un shell complet non
interactif, sans droits fins ni audit. **Aucun nœud communautaire** équivalent trouvé.

**Recommandation : construire Deskgate.** Le créneau est réel et non occupé par un projet MIT/Apache.

### 2. Contribuer ? Non

Les seuls projets dont Deskgate pourrait être une extension (Windmill, Kestra, Prefect) sont des
orchestrateurs dont le modèle (serveur central, flows) est à l'opposé du besoin « agent local
indépendant de n8n », et Windmill n'est pas acceptable côté licence.

### 3. S'appuyer sur des briques : avec mesure

- **File de tâches : ne PAS adopter Huey (ni persist-queue) — écrire la file SQLite.**
  Argument honnête : ce que Deskgate demande à sa file (concurrence **par ressource** nommée,
  états `queued/running/succeeded/failed/timeout/cancelled/interrupted`, reprise au redémarrage
  avec passage en `interrupted`, idempotence par clé, annulation, progression, lien avec le
  rappel webhook et l'audit) n'est **pas** fourni par Huey : Huey offre une file + un consumer
  à N workers homogènes, sans notion de ressource, avec un consumer en mode *process* fragile sous
  Windows (spawn/pickling) et ses propres conventions de stockage qu'il faudrait contourner pour
  l'UI et l'API `/jobs`. Les tâches s'exécutent de toute façon **en sous-processus** (venv uv
  isolé), donc la file ne fait que de l'ordonnancement d'états : une table `jobs` SQLite (WAL) +
  un ordonnanceur asyncio de ~200-400 lignes est plus simple, plus testable et sans dépendance
  que d'adapter Huey. Huey reste un **plan B** si l'ordonnanceur maison s'avère fragile.
- **Exécuteur MCP : utiliser le SDK officiel `mcp` (Python)** pour parler stdio/HTTP aux serveurs
  déclarés ; `supergateway` / `mcp-proxy` sont inutiles côté exécution (le runner lance lui-même
  le serveur stdio). `mcpo` est une **bonne référence de conception** (outils MCP → schémas
  OpenAPI/JSON Schema, ce que fait le catalogue Deskgate).
- **Exécuteur CLI** : s'inspirer de `adnanh/webhook` / HookRun (règles déclaratives
  commande ← paramètres), mais l'implémenter en Python (`subprocess` sans shell + Job Objects /
  `psutil` pour l'arrêt d'arbre).
- **Audit / politiques** : `mcp-audit` (allow/deny, journal signé) est une idée à regarder pour la
  v0.4, pas une dépendance.
- **Exposition MCP v0.4** : suivre l'état du primitif *Tasks* de MCP avant de figer `submit`/`status`.

### Risque à surveiller

Le danger n'est pas un concurrent existant mais le **périmètre** : la valeur de Deskgate est
précisément l'assemblage léger (session GUI + callback + manifeste + droits). Rester sur l'ordre
v0.1 → v0.4 et ne pas reconstruire un orchestrateur (pas de DAG, pas de planification : c'est le
rôle de n8n).

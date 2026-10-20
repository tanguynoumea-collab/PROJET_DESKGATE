# Feuille de route de Deskgate

Principe : chaque version est **validée par un usage réel**, pas seulement par des tests.
Deux pistes avancent en parallèle : le **runner** (cœur générique) et les **plugins BIM**
(`plugins/bim/`), qui servent de cas de test réels au runner.

## v0.0 — Cadrage ✅ (2026-10-20)

- [x] Recherche de l'existant : rien ne couvre le besoin, **on construit**
      (`.arthemis/reports/existant-cycle-1.md`).
- [x] Vérifications techniques : attente dans un nœud communautaire faisable, `host.docker.internal`
      vers `127.0.0.1` via Docker Desktop, IfcOpenShell + uv OK, arrêt par Job Object
      (`.arthemis/reports/verifs-techniques-cycle-1.md`).
- [x] Périmètre recadré : passerelle seule ; Hermes, tableau de bord et workflows complets hors dépôt ;
      pas d'exposition MCP de Deskgate.
- [x] Licence : MIT.
- [ ] Validation de ces documents par l'utilisateur avant tout code.

## v0.1 — Runner minimal, prouvé sur une détection de conflits

Runner :
- [ ] Test `host.docker.internal` → runner sur `127.0.0.1` sur la machine cible.
- [ ] Runner FastAPI sur `127.0.0.1`, un jeton unique dans `runner.toml`.
- [ ] File SQLite persistante, une seule tâche à la fois.
- [ ] `POST /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/logs`, `POST /jobs/{id}/cancel`.
- [ ] Rappel vers la `resumeUrl` telle quelle, masquée dans les journaux, plafonné à 1 Mio, réessais.
- [ ] Délai maximum + arrêt de l'arbre de processus par Job Object.
- [ ] Correspondance des chemins `/data` ↔ `C:/BIM`, refus hors racines.
- [ ] Au redémarrage : `running` → `interrupted` + rappel.
- [ ] Capacités codées en dur : `ifc.clash` et `mcp.call` (outil d'un serveur MCP stdio déclaré).
- [ ] `deskgate init` : configuration, jeton, tâche du Planificateur à l'ouverture de session.
- [ ] `n8n/docker-compose.yml` (n8n 2.43.8 épinglé, Postgres, montage `C:\BIM`) et workflow
      d'exemple HTTP Request + Wait.

Plugins BIM (en parallèle) :
- [ ] `ifc.clash` écrit de zéro sur IfcOpenShell (`ifcclash`) : détection hard / clearance /
      touch / duplicate, regroupement, BCF 2.1.

Critère d'acceptation :
> Un IFC déposé dans `C:\BIM\depot\` déclenche dans n8n une détection de conflits exécutée par le
> runner ; n8n reprend après le rappel et récupère le résumé et le chemin du BCF. Un calcul de plus
> de 10 minutes fonctionne. Un redémarrage du runner pendant une tâche produit un rappel
> `interrupted`. Un délai dépassé tue tout l'arbre de processus.

## v0.2 — Plugins génériques, droits et diagnostic

Runner :
- [ ] Manifeste `plugin.yaml` + validation.
- [ ] Exécuteurs `python` (sous-processus, environnement uv isolé), `cli` (gabarit sans shell),
      `mcp` (stdio et Streamable HTTP, SDK `mcp`).
- [ ] `deskgate plugin add | remove | list`, `deskgate doctor`.
- [ ] Ressources et concurrence (`gui-session`, `cpu-heavy`, `light`).
- [ ] Jetons multiples, droits par plugin, audit, `deskgate token create | revoke`.
- [ ] Idempotence.

Plugins BIM :
- [ ] `ifc.clash` migré en plugin à manifeste.
- [ ] `ifc.audit` (IDS via `ifctester`), `ifc.diff` (`ifcdiff`), `ifc.quantities`.

Critère d'acceptation :
> `ifc.audit` est ajouté par `deskgate plugin add` **sans modifier le code du runner**. Un jeton
> limité à `ifc.clash` se voit refuser `ifc.audit`, et le refus apparaît dans l'audit.

## v0.3 — Nœud n8n et interface locale

- [ ] Nœud communautaire `n8n-nodes-deskgate` : identifiants, liste dynamique des capacités, champs
      générés depuis le schéma, **soumission et attente dans un seul nœud**.
- [ ] Interface web : catalogue par type, test d'un plugin, tâches, journaux, jetons et droits,
      audit, diagnostic.

Critère d'acceptation :
> Un collègue installe le runner et le nœud, puis construit et lance seul un workflow à deux nœuds
> Deskgate (`ifc.clash` puis un second plugin qui consomme le BCF).

## v0.4 — Reproductibilité et publication

- [ ] `pipeline.lock` + `deskgate plugin install --from pipeline.lock`.
- [ ] `AGENTS.md` éprouvé : une IA installe le runner depuis GitHub sur un PC vierge.
- [ ] Documentation complète, exemples, publication GitHub, réservation des noms PyPI et npm.

Critère d'acceptation :
> Une session Claude Code installe le runner et un plugin BIM sur un PC vierge en suivant
> uniquement `AGENTS.md`.

## Backlog

- `odm.audit_loi` : plugin ODM, après une version fonctionnelle (interface d'ODM à identifier).

## Hors périmètre

- Exposition de Deskgate comme serveur MCP (un agent passe par un workflow n8n exposé par
  *MCP Server Trigger*, ou par l'API HTTP).
- Workflows complets, ingestion, registre des maquettes, base et déduplication des conflits,
  tri par IA, Hermes, superviseur, tableau de bord : projet d'intégration.
- Runner partagé multi-utilisateurs, exécution sur une machine distante, macOS / Linux natif.

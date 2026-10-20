# 04 — Feuille de route

Principe : chaque version est **validée par un usage réel**, pas seulement par des tests.

## v0.0 — Cadrage (avant tout code)

- [ ] Recherche de l'existant (voir `06-POINTS-OUVERTS.md` §1) et conclusion : construire,
      contribuer ou adapter.
- [ ] Vérifications techniques (§2 des points ouverts), en particulier l'attente dans un nœud
      n8n communautaire et l'accès `host.docker.internal` → runner.
- [ ] Rédaction dans le dépôt : `ARCHITECTURE.md`, `ROADMAP.md`, `AGENTS.md`, `CLAUDE.md`,
      `README.md` (squelette), choix de la licence.
- [ ] **Validation par l'utilisateur** avant de coder.

## v0.1 — Le runner minimal, prouvé sur le pipeline de coordination

Contenu :
- [ ] Runner FastAPI sur `127.0.0.1`, un jeton unique dans `runner.toml`.
- [ ] File de tâches SQLite persistante, un exécuteur, une seule tâche à la fois.
- [ ] `POST /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/logs`, rappel vers `resumeUrl` avec
      réessais.
- [ ] Délai maximum + arrêt de l'arbre de processus.
- [ ] Correspondance des chemins `/data` ↔ `C:/BIM` et refus hors racines.
- [ ] Deux capacités codées « en dur » (le format de manifeste viendra en v0.2) :
  - `ifc.clash` : appelle le moteur `bim-assistant` (`clash.clash`, `clash.write_bcf`) ;
  - `mcp.call` : appelle un outil d'un serveur MCP stdio déclaré.
- [ ] Lancement au démarrage de session (Planificateur de tâches).
- [ ] Workflow n8n d'exemple : HTTP Request + Wait.

Critère d'acceptation :
> Un IFC déposé dans `C:\BIM\depot\` déclenche dans n8n une détection de conflits exécutée par le
> runner ; n8n reprend après le rappel et récupère le résumé et le chemin du BCF. Un calcul de
> plus de 10 minutes fonctionne. Un redémarrage du runner pendant une tâche produit un rappel
> `interrupted`.

## v0.2 — Plugins génériques, droits et diagnostic

- [ ] Format de manifeste `plugin.yaml` + validation.
- [ ] Les trois exécuteurs : `python` (sous-processus, environnement uv isolé), `cli`
      (gabarit d'arguments, sans shell), `mcp` (stdio et HTTP).
- [ ] `deskgate plugin add | remove | list`, `deskgate doctor` (prérequis, disponibilité).
- [ ] Ressources et concurrence (`gui-session`, `cpu-heavy`, `light`).
- [ ] Jetons multiples, droits par plugin, journal d'audit, `deskgate token create | revoke`.
- [ ] Idempotence.
- [ ] Les deux capacités de la v0.1 migrées en plugins (dépôt `deskgate-bim`).

Critère d'acceptation :
> Le plugin ODM (`odm.audit_loi`) est ajouté **sans modifier le code du runner**. Un jeton
> limité à `ifc.*` se voit refuser `odm.audit_loi`, et le refus apparaît dans l'audit.

## v0.3 — Nœud n8n et interface visuelle

- [ ] Nœud communautaire `n8n-nodes-deskgate` : identifiants, liste dynamique des
      capacités, champs générés depuis le schéma, soumission + attente.
- [ ] Interface web : catalogue par type, test d'un plugin, tâches, journaux, jetons et droits,
      audit, diagnostic.

Critère d'acceptation :
> Un collègue installe le runner et le nœud, puis construit et lance seul un pipeline à deux
> nœuds (`ifc.clash` puis un second plugin qui consomme le BCF).

## v0.4 — Exposition MCP, reproductibilité, publication

- [ ] Capacités exposées en outils MCP (HTTP), mêmes droits et audit.
- [ ] `pipeline.lock` + `deskgate plugin install --from pipeline.lock`.
- [ ] `AGENTS.md` éprouvé : une IA installe le runner depuis le dépôt GitHub sur un PC vierge.
- [ ] Documentation complète, exemples, plugins BIM d'exemple, publication GitHub.

Critère d'acceptation :
> Hermes Agent appelle `ifc.clash` en MCP directement. Une session Claude Code installe le
> runner et un plugin sur un PC vierge en suivant uniquement `AGENTS.md`.

## Hors périmètre (prévu, pas construit)

- Runner partagé multi-utilisateurs (comptes, rôles, SSO, exposition réseau).
- Exécution de plugins sur une machine distante.
- Support macOS / Linux natif (le runner devrait le permettre, mais Windows est la cible).

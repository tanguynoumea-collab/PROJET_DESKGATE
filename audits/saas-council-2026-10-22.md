# Audit saas-team-council — Deskgate — 2026-10-22

Audit complet (`/saas-council`), cycle ARTHEMIS 1, milestone GSD v0.1, commit audité `ca2afd3`
(code identique à `d689cbe`, dernier gate vert). Arbre propre pendant tout l'audit, aucun agent en
écriture : les portes outillées citées sont valides. Aucun auditeur n'a écrit dans le dépôt
(`git status --short` vide vérifié par chaque agent).

---

## 1. Carte d'identité de l'audit

**Écosystème détecté** : Python ≥ 3.11, workspace uv (`deskgate`, `plugins/bim` = `deskgate-bim`,
`plugins/bim/bcf` = `deskgate-bcf` GPL-3), FastAPI 0.151 + Uvicorn, SQLite WAL (sqlite3, migrations
`PRAGMA user_version`), httpx2, SDK `mcp` 2.3, Typer, pytest, pyright, ruff. CI GitHub Actions
`windows-latest` (Python 3.11 et 3.13). n8n épinglé 2.43.8 (tag + digest). Pas de front web.

**Six faits de contexte** (source : `.arthemis/state.json` › `extension.web_saas.contexte_saas`) :

| Fait | Valeur |
|---|---|
| Tenancy | Mono-tenant : un runner par PC, pas de multi-utilisateurs (D7, D9) |
| Authentification | Un jeton Bearer haché (SHA-256, comparaison en temps constant), écoute 127.0.0.1, contrôle Host ; droits par plugin en v0.2 |
| Données personnelles | Aucune collectée ; l'audit local contient chemins et paramètres |
| Facturation | Sans objet (open source MIT) |
| Environnements | Un seul : le PC local (runner natif + n8n Docker Desktop) |
| Stade | Nouveau projet, aucun utilisateur → catégories 6 et 7 plafonnées à Majeur |

**Roster exécuté** : Tier 1 `saas-architecte`, `saas-mainteneur`, `saas-tests` · Tier 2
`saas-tenancy`, `saas-securite`, `saas-fiabilite`, `saas-donnees` · Tier 3 `saas-livraison`,
`saas-pertinence` · transversal `saas-sceptique` · arbitrage : 3 juges indépendants (SEC-001).

**Non activés, avec raison** :
- `saas-perfcout` : sauté (choix du pré-vol) — runner local, aucun coût d'exécution.
- `saas-billing` : aucune dépendance de paiement.
- `saas-conformite` : aucune donnée personnelle dans le schéma (tables `jobs`, `callbacks`, `audit`).
- `saas-ia` : aucun SDK de modèle.
- `saas-seo` : aucune page publique (seule route non authentifiée : `GET /health`).

**Outillage Phase 1** (exécution éphémère, rien d'installé) : `uv run ruff check|format --check`,
`uv run pyright`, `uv run --with pytest-cov pytest -m "not e2e"` (sortie hors projet),
`uvx pip-audit==2.10.1`, `uvx semgrep==1.182.1` (p/security-audit, p/python), `uvx radon==6.0.1`,
`npx --yes jscpd`, sondes Python dans le répertoire temporaire de session (base SQLite neuve,
`TestClient` en mémoire, vraie jonction NTFS, vrai `Engine` sous verrou). gitleaks absent.

---

## 2. Verdict et résumé exécutif

| Sévérité | Nombre (après sceptique, cross-challenge, arbitrage, dédoublonnage) |
|---|---|
| Bloquant | **0** |
| Majeur | **3** |
| Mineur | **28** |
| Info | **29** |

70 findings bruts → 60 uniques (10 doublons fusionnés). Sceptique : 0 invalidé, 10 abaissés,
8 doublons ; 26 % des findings ont bougé (sous le seuil de 60 %), mais **6 Majeurs bruts sur 9 ont
bougé** — voir la question d'auto-surveillance ci-dessous.

**Verdict : aucun Bloquant → rien n'interdit la publication v0.1.0 ; trois Majeurs à trier**, dont
deux touchent directement la valeur centrale (« reprend fiablement ») et un la règle non négociable 4.

1. **ARC-001** — un thread de fond qui meurt arrête le runner avec le code 0 ; le Planificateur ne le
   relance pas ; les rappels restent bloqués jusqu'à la prochaine ouverture de session.
2. **SEC-001** — l'exécuteur `mcp` transmet les arguments de l'appelant sans conversion ni validation
   contre `allowed_roots` (règle 4) ; arbitrage council unanime 3/3 : Majeur.
3. **LIV-001** — `init` / `doctor` lancés depuis une application MSIX valident une installation
   virtualisée qui échouera (item ARTHEMIS `05-06-msix`, confirmé toujours ouvert).

**Certifications demandées par ARTHEMIS** (rôle Tests) :
- `clash-troncature` : **CERTIFIÉ** — `plugins/bim/tests/test_clash_limits.py:84-95` (1024 conflits,
  défaut sans plafond, `truncated is False`, aucun avertissement) ; `params.py:58` `max_clashes = None`.
- `clash-reservations` : **CERTIFIÉ avec réserve** — `plugins/bim/tests/test_clash_openings.py:27-53` ;
  filtre `clash.py:85` indépendant du sélecteur ; le cas d'origine (sélecteur `IfcElement` littéral)
  n'a pas de test → TST-002.

**Question d'auto-surveillance du sceptique** (portée : les Majeurs) : « le council a-t-il gonflé
ses Majeurs, ou est-ce moi qui abaisse trop ? » Ses arguments sont vérifiables : MNT-001 sans impact
de comportement ; MNT-002 compare deux ensembles de sémantiques différentes (décisions du classifieur
vs états stockés, avec `CHECK` en base) ; DON-001 à l'échelle d'un poste mono-utilisateur. FIA-001
a été abaissé **par son propre auditeur** au cross-challenge (gravité portée par ARC-001).

### Où l'audit est aveugle (NON VÉRIFIÉ)

- **Secrets dans l'historique** : gitleaks absent ; recherche par `rg` + `git log -p -G` (sans
  entropie) — couverture partielle, aucun résultat.
- **Typage des plugins** : pyright ne couvre pas `plugins/**/src` (ARC-003) ; dans leurs venvs, non mesuré.
- **Couverture des sous-processus** : `workers/mcp_call.py` (0 %) et `deskgate_bim` non mesurés
  (exercés par 11 tests MCP et les tests BIM) — TST-003.
- **E2E** : non relancés par l'audit ; état repris du gate (`gate-1-05.1.log`, 30 passed) et de la CI
  (run 39774727051 : 804 passed, 0 skipped, 30 e2e passed).
- **Planificateur Windows réel** : effet d'un code de sortie non nul sur `RestartOnFailure` non observé
  (aucune tâche créée) — conditionne le correctif d'ARC-001.
- **Lien symbolique** : test obligatoire sauté en local (privilège absent), vert en CI — TST-001.
- **Code mort** : vulture non exécuté ; sondes AST maison sur les symboles de premier niveau.
- **Base réelle** `%LOCALAPPDATA%\Deskgate` : jamais ouverte (interdit) ; sondes sur base neuve.
- **n8n réel 2.43.8**, **MSIX réel**, **conteneur Docker créant des liens dans `C:/BIM`** : non rejoués.
- **Domaines sans vérité-terrain possible** (`outils.md` §6) : cohérence architecturale, nommage,
  qualité des assertions, justesse d'une règle d'autorisation, pertinence produit.

### Angles morts signalés par le sceptique (remontée obligatoire)

| # | Localisation | Catégorie §5.2 atteignable | Re-vérification ciblée | Traitement |
|---|---|---|---|---|
| AM-1 | `runtime.py:168`, `ARCHITECTURE.md:64-65` | hors liste (fiabilité), plafond Majeur | `/saas-council-role fiabilite` puis `livraison` sur `runtime.py` | Le correctif « code non nul » d'ARC-001 peut ne pas déclencher `RestartOnFailure`. Intégré à la recommandation d'ARC-001 : prouver la relance par une tâche réelle (ou relance par `schtasks /Run`). |
| AM-2 | `workers/mcp_call.py:46-54`, `core/config.py:135-146` | hors liste (fonctionnel) ; 2 si la règle 4 est étendue — elle l'est (arbitrage) | `/saas-council-role securite` | Un chemin `/data/...` n8n arrive non converti au serveur MCP Windows : rupture fonctionnelle en plus de la sécurité. Intégré à SEC-001. |
| AM-3 | CLAUDE.md « Tests », exécuteur `mcp` | 2, sous condition de l'arbitrage (réalisée) | `/saas-council-role tests` | Aucun test obligatoire de refus hors racine pour `mcp.call`. Intégré à la recommandation de SEC-001. |

Aucun angle mort ne désigne une perte de données. Aucun ne contredit un rôle ayant tourné sans être
déjà tranché : AM-2 et AM-3 sont absorbés par l'arbitrage unanime de SEC-001.

---

## 3. Plan de remédiation priorisé

Ordre : sévérité × tier × rayon d'impact, regroupé par module. Les corrections d'audit passent par une
phase GSD insérée (règle ARTHEMIS), jamais en quick.

| Rang | Module | IDs | Action | Classe (§11.3) |
|---|---|---|---|---|
| 1 | `runtime.py`, `engine.py`, `sender.py`, `api/routes_health.py` | **ARC-001** (+FIA-002), FIA-001 (+DON-004), MNT-007, FIA-005, TST-004 | Code de sortie non nul après `on_fatal` + relance prouvée sur tâche réelle ; tolérer les `OperationalError` transitoires dans l'engine (N erreurs avec back-off, comme le sender) ; documenter les deux politiques ; exposer l'état des threads dans `/health` ; fermer `_conn` dans `stop()`. Test e2e qui force l'échec fatal. | conception |
| 2 | `workers/mcp_call.py`, `core/config.py`, `runner.example.toml`, ARCHITECTURE.md | **SEC-001**, AM-2, AM-3, SEC-005 (+LIV-003) | `path_params` par outil MCP (ex. `[mcp_servers.X.tool_paths] read_file = ["path"]`) passés à `convert_path_params` à la soumission (422) et au lancement ; tests obligatoires `..` / lien / jonction pour `mcp.call` ; documenter que les autres arguments sont opaques ; n'injecter que l'`env` du serveur visé. | sensible (contrat de config) |
| 3 | `doctor.py`, `installer.py`, `locations.py` | **LIV-001** (= `05-06-msix`), PER-001, FIA-003 | Détecter l'exécution empaquetée (`GetCurrentPackageFullName`) ou un home sous `\Packages\…\LocalCache` : `init` refuse, `doctor` en échec ; `doctor` lit le dernier résultat de la tâche (0x8007010B) ; journal de démarrage avant la config ; vérification générique des exécutables déclarés plutôt que `bcf_executable` en dur. | mécanique + conception (PER-001) |
| 4 | `core/callback_policy.py`, `store.py`, `sender.py`, `engine.py`, `core/payload.py` | MNT-002, ARC-005, DON-002, DON-008 | Source unique des états du rappel ; une seule décision « tient dans 1 Mio » ; index partiel `callbacks(next_attempt_at) WHERE state='pending'` ; compter l'essai après la revérification d'hôte. | mécanique (index : sensible, migration 3 additive) |
| 5 | `store.py` (rétention), AGENTS.md | DON-001, DON-003, SEC-002 (+DON-007), LIV-007 | Politique de rétention + `deskgate purge` (migration 3) ; copie `VACUUM INTO` avant migration ; procédures retour arrière / désinstallation ; plafond de taille de `POST /jobs`. | sensible (schéma) |
| 6 | Installation et CI | LIV-002, LIV-004, LIV-005, TST-001 | Installer depuis l'export du lock (contraintes) ; versionner les trois `pyproject.toml` ensemble ; `permissions: contents: read`, épinglage SHA, `timeout-minutes` ; le gate local échoue si un test obligatoire est sauté. | mécanique |
| 7 | `plugins/bim` | MNT-001, MNT-003, MNT-005, MNT-009, ARC-003 (+MNT-004), TST-002 | Découper `clash._run` (`_detect`, `_trim_data`, `_summary`), accumulateur d'avertissements, constantes de progression, `TypedDict` locaux ; pyright par environnement de plugin ; test paramétré avec `IfcElement`. | mécanique / conception |
| 8 | Tests d'architecture et noyau | ARC-002, ARC-006, ARC-004, MNT-006, MNT-008, FIA-004 | Test AST qui interdit `deskgate.*` hors `core` et les imports relatifs ; trancher le champ `data` ; `_Outcome` dans `mcp_call` ; typer `audit_settings` ; saut de ligne d'`events.jsonl` > 1 Mio. | mécanique |
| 9 | Documentation et périmètre | PER-003 (+ARC-010), PER-004, PER-005, SEC-003 | Marquer v0.1 / cible dans ARCHITECTURE.md et corriger l'exemple `POST /jobs` (422) ; mettre à jour ROADMAP.md et README ; décider du retrait du contrat `bcf-write-v1` avant publication ; `callback_allowed_hosts` en `hôte:port`. | décision produit |

Infos : aucune action requise ; à relire au triage pour les décisions produit (PER-009 vignettes,
ARC-007 concurrence N en v0.2, TEN-002 IDOR à prévoir avec les droits par plugin).

---

## 4. Findings détaillés

### 4.1 Majeurs

```
ID            : ARC-001  (fusionne FIA-002)
Sévérité      : Majeur
Rôle émetteur : saas-architecte (Tier 1) ; saas-fiabilite (Tier 2)
Localisation  : src/deskgate/runtime.py:157-168 ; src/deskgate/engine.py:546-550 ; src/deskgate/sender.py:234-238
Preuve        : CITATION:runtime.py:158-159 « # Le Planificateur relancera le runner ; la recovery rend l'arrêt sûr. »
                « engine.on_fatal = lambda: setattr(server, "should_exit", True) » ; runtime.py:168 « return 0 » ;
                ARCHITECTURE.md:64-65 « RestartOnFailure ne couvre que les échecs de démarrage » ;
                OUTIL:rg « \.failed\b|last_tick_at » → jamais lus hors tests ; sonde probe_busy (FIA) : thread engine mort sur verrou maintenu
Constat       : La mort du thread engine ou sender arrête proprement le serveur et serve() renvoie 0. Le Planificateur
                ne relance pas. Aucune tâche ni aucun rappel n'avance jusqu'à la prochaine ouverture de session ;
                au-delà de max_window_s (24 h) le rappel est abandonné sans envoi (store.py:535-542).
Rayon d'impact: un utilisateur (toutes les tâches en file et tous les rappels dus du PC)
Impact        : n8n attend jusqu'à l'échéance de son Wait ; contredit la valeur centrale « reprend fiablement ».
Recommandation: Code de sortie dédié non nul si engine.failed ou sender.failed ; prouver la relance sur une tâche
                réelle (sinon relance par schtasks /Run après sortie) ; corriger le commentaire runtime.py:158 ;
                test e2e qui force l'échec fatal (aucun test aujourd'hui : cross-challenge Tests, runtime.py 59 %).
Applicabilité : Runner de session supervisé par le Planificateur, seul mécanisme de reprise prévu (D-03/D-04).
Statut challenge : validé par sceptique ; confirmé au cross-challenge Architecte ↔ Tests ; angle mort AM-1 joint
```

```
ID            : SEC-001
Sévérité      : Majeur
Rôle émetteur : saas-securite (Tier 2)
Localisation  : src/deskgate/workers/mcp_call.py:46-54, :96 ; src/deskgate/core/config.py:135-146
Preuve        : CITATION:mcp_call.py:96 « box["r"] = await client.call_tool(tool, arguments) » ;
                config.py:140-145 « kind = "mcp" n'accepte ni python, ni entry, ni pythonpath, ni settings, ni path_params » ;
                ARCHITECTURE.md:108 promet des chemins « déjà convertis » et validés
Constat       : Les arguments d'un appel mcp.call partent bruts vers l'outil MCP : ni conversion /data → hôte, ni
                validation contre allowed_roots. La configuration interdit explicitement le mécanisme qui le
                permettrait. Chemin : POST /jobs (jeton) {capability: mcp.call, params: {server, tool,
                arguments: {path: "C:/Users/…"}}} → call_tool. Exemption ni documentée ni justifiée (04-02-PLAN.md:151).
Rayon d'impact: un utilisateur (tout porteur du jeton, dont tout conteneur local qui l'obtient)
Impact        : Si l'opérateur autorise un outil de fichiers, lecture/écriture hors des racines ; et un chemin
                /data/... de n8n n'aboutit pas côté Windows (AM-2). Règle non négociable 4 non tenue.
Recommandation: path_params par outil MCP, convertis et validés à la soumission (422) et au lancement ; tests
                obligatoires (.., lien, jonction) pour mcp.call ; documenter que les autres arguments sont opaques.
Applicabilité : Règle 4 du dépôt, exécuteur livré en v0.1. Plafonné à Majeur : jeton + configuration opérateur requis.
Statut challenge : en arbitrage council → Majeur à l'unanimité (3/3) ; citation corrigée par le sceptique (:336-386 → :46-54, :96)
```

```
ID            : LIV-001  (= item ARTHEMIS 05-06-msix)
Sévérité      : Majeur
Rôle émetteur : saas-livraison (Tier 3)
Localisation  : src/deskgate/doctor.py:142-171 ; src/deskgate/installer.py:118-127 ; src/deskgate/locations.py:16
Preuve        : OUTIL:rg -i "msix|virtualis|WindowsApps|Packages" src → aucune occurrence ;
                CITATION:AGENTS.md:51-52 « tâche planifiée avec le dernier résultat 0x8007010B, fichiers sous
                %LOCALAPPDATA%\Packages\<application>\LocalCache »
Constat       : init et doctor lancés depuis une application MSIX écrivent dans le stockage virtualisé et le jugent
                conforme ; la tâche planifiée, exécutée hors paquet, échoue. Seule la documentation prévient.
Rayon d'impact: un utilisateur (le poste qui installe)
Impact        : Le runner ne démarre pas à l'ouverture de session pendant que doctor affiche « conforme ».
Recommandation: Détecter l'exécution empaquetée (GetCurrentPackageFullName) ou un home sous \Packages\…\LocalCache :
                init refuse, doctor en échec ; doctor lit le dernier résultat de la tâche et signale 0x8007010B.
Applicabilité : Chemin d'installation réel décrit dans AGENTS.md ; l'auteur l'a déjà rencontré (STATE.md, phase 5).
Statut challenge : validé par sceptique
```

### 4.2 Mineurs

| ID | Émetteur(s) | Localisation | Preuve | Constat → recommandation | Rayon | Statut |
|---|---|---|---|---|---|---|
| FIA-001 (+DON-004) | Fiabilité T2, Données T2 | engine.py:328-339, 538-550 ; store.py:131-134 | OUTIL sonde probe_busy : verrou externe > 5 s → `failed/engine_error`, ou tâche `running` sans rappel + thread mort | Erreur SQLite transitoire traitée comme erreur fatale → tolérer N erreurs, rouvrir la connexion, ne pas tuer le Job | un utilisateur | abaissé (Majeur → Mineur) par l'auditeur au cross-challenge et par le sceptique : déclencheur externe, rappel différé seulement, gravité portée par ARC-001 |
| MNT-001 | Mainteneur T1 | deskgate_bim/clash.py:277-414, 184-274 | OUTIL radon `_run` D(29), `_write_bcf` D(21) ; 7 commits | Fonction à six responsabilités → extraire `_detect`, `_trim_data`, `_summary` | mainteneur | abaissé (Majeur → Mineur) : aucun impact de comportement |
| MNT-002 | Mainteneur T1 | store.py:27-40, 508, 540 ; callback_policy.py:15-23 ; sender.py:164-181 | CITATION `FINAL` vs `CALLBACK_FINAL_STATES` + littéraux | Vocabulaire du rappel dispersé → source unique, docstring décision ≠ état | mainteneur | abaissé (Majeur → Mineur) : sémantiques distinctes, `CHECK` store.py:99 |
| DON-001 | Données T2 | store.py:96-109 | OUTIL sonde : `DELETE` refusés (FK, trigger) ; 3,4 Ko d'audit par tâche ; aucun `DELETE FROM` | Croissance non bornée, audit non purgeable → politique de rétention + `deskgate purge` (migration 3) | un utilisateur | abaissé (Majeur → Mineur) : choix assumé, échelle mono-poste ; cross-challenge : effet fiabilité négligeable |
| ARC-003 (+MNT-004) | Architecte T1, Mainteneur T1 | pyproject.toml `[tool.pyright] include` ; ci.yml | OUTIL pyright plugins → 19 `reportMissingImports` | Plugins BIM non typés en CI → pyright par environnement de plugin | mainteneur | validé (MNT-004 Majeur fusionné et aligné) |
| ARC-002 | Architecte T1 | tests/architecture/test_import_boundaries.py:15-39 | OUTIL sonde probe_purity : `from deskgate.store import …` ACCEPTÉ | Garde-fou « noyau pur » aveugle aux imports internes et relatifs → interdire `deskgate.*` hors `core` | mainteneur | validé ; confirmé au cross-challenge |
| ARC-004 | Architecte T1 | engine.py:454-456 ; payload.py:3 ; jobs.py:44-66 | CITATION payload.py:3 « data … jamais transmis » | `data` stocké mais exposé nulle part → exposer ou retirer du contrat | auteurs de plugins | validé |
| ARC-005 | Architecte T1 | engine.py:461-475 ; sender.py:130-141 | CITATION corps mesuré sans horodatages vs envoyé avec | Règle 7 évaluée deux fois → une seule fonction de décision + test du cas limite | une tâche | validé ; aucun test (cross-challenge) |
| MNT-003 | Mainteneur T1 | clash.py:195-198, 304-369 | CITATION `warn` / `note` | Triplet d'avertissement écrit 5 fois → accumulateur | mainteneur | validé |
| MNT-005 | Mainteneur T1 | grouping.py, bcfdoc.py, clash.py | CITATION `dict[str, Any]`, `ctx: Any` | Structures non typées → `TypedDict` + `Protocol` locaux | mainteneur | validé |
| MNT-006 | Mainteneur T1 | workers/mcp_call.py:81-117 | OUTIL radon `_call` C(20) | Dictionnaire boîte à lettres → dataclass `_Outcome` | mainteneur | validé |
| MNT-007 | Mainteneur T1 | engine.py:538-555 ; sender.py:220-243 | CITATION politiques d'erreur opposées | Non documentées → une phrase par module (à traiter avec ARC-001) | mainteneur | validé |
| MNT-008 | Mainteneur T1 | doctor.py:149 ; scheduler.py:157 | CITATION `# type: ignore[arg-type]` | Type `Level` contourné → typer `audit_settings` | mainteneur | validé |
| MNT-009 | Mainteneur T1 | clash.py (10 littéraux) | CITATION `progress(90, …)` ×2 | Échelle de progression magique → constantes nommées | mainteneur | validé |
| TST-001 | Tests T1 | tests/fs/test_paths_real.py:116 ; tests/conftest.py:64-77 | OUTIL pytest « SKIPPED … Privilège de lien symbolique absent » | Test obligatoire sauté dans le gate local déclaré vert → échec si sauté dans le gate | mainteneur | validé |
| TST-002 | Tests T1 | plugins/bim/tests/test_clash_openings.py:14-20 | OUTIL rg `IfcElement\b` tests → aucun | Cas d'origine non testé → paramétrer avec `IfcElement` | utilisateur BIM | validé (réserve de certification) |
| TST-004 | Tests T1 | engine.py:562-578 | OUTIL pytest 187 `ResourceWarning: unclosed database` | `stop()` ne ferme pas `_conn` → fermer, puis warnings en erreur | mainteneur | validé |
| SEC-003 | Sécurité T2 | callback_policy.py:107-128 | CITATION filtre par nom d'hôte seul | SSRF aveugle POST vers un port local → `hôte:port` (+ préfixe de chemin) | porteur du jeton | validé |
| FIA-003 | Fiabilité T2 | runtime.py:82-125 | CITATION `if sys.stderr is not None` ; pas d'excepthook | Échecs de démarrage muets sous pythonw → journal de démarrage | un utilisateur | validé |
| FIA-004 | Fiabilité T2 | engine.py:396-406 | CITATION `if end < 0: return` | Ligne > 1 Mio fige la progression → sauter au prochain saut de ligne | une tâche | validé |
| DON-002 | Données T2 | store.py:524-532 | OUTIL EXPLAIN « SCAN c … USE TEMP B-TREE » | Scan de `callbacks` chaque seconde → index partiel | un utilisateur | validé |
| DON-003 (+LIV-006) | Données T2, Livraison T3 | store.py:152-162 ; AGENTS.md:178-185 | OUTIL sonde migration atomique ; rg `backup` → rien | Pas de sauvegarde avant migration ni de retour arrière documenté → `VACUUM INTO` + procédure | un utilisateur | validé |
| LIV-002 | Livraison T3 | AGENTS.md:40, 182 ; pyproject.toml:6 | OUTIL `uv tool install --help` sans `--locked` | Runner installé ≠ testé, versions non auditées (angle supply-chain, cross-challenge Sécurité) → contraintes exportées du lock | un utilisateur | validé |
| LIV-004 | Livraison T3 | state.json `fichiers_version` ; plugins/*/pyproject.toml | CITATION `0.1.0.dev0` ×3 | Plugins hors du bump → ajouter à `fichiers_version` | un utilisateur | validé |
| PER-001 | Pertinence T3 | doctor.py:112-114 | CITATION `cap.settings.get("bcf_executable")` | Le cœur connaît une clé de plugin BIM (esprit règle 1) → vérification générique | un utilisateur | validé |
| PER-003 (+ARC-010) | Pertinence T3, Architecte T1 | ARCHITECTURE.md:35-36, 141, 155-174 | CITATION exemple `callback.headers` vs `extra="forbid"` | Doc de référence = cible v0.2-0.3 ; exemple → 422 → marquer les versions, corriger l'exemple | un utilisateur | validé |
| PER-004 | Pertinence T3 | ROADMAP.md:21-41 ; README.md:7, 34 | CITATION cases v0.1 vides ; exécuteur `cli`, modes touch/duplicate | Page d'accueil publique fausse → mettre à jour | surface publique | validé |
| PER-005 | Pertinence T3 | deskgate_bcf/cli.py:17 | CITATION `SUPPORTED = {1: …, 2: …}` | Contrat v1 sans producteur → retirer avant publication (à confirmer) | un utilisateur | validé |

### 4.3 Info

| ID | Émetteur(s) | Localisation | Constat (preuve) | Statut |
|---|---|---|---|---|
| ARC-006 | Architecte | core/config.py:278-290 ; core/paths.py:47-48 | E/S fichier dans le noyau « pur », résolveur injectable | abaissé (Mineur → Info) |
| ARC-007 (+DON-006, PER-002) | Architecte, Données, Pertinence | store.py:361-376 ; config.py:124 | Concurrence 1 câblée en SQL ; `resource` jamais lu ; CLAUDE.md « Motifs SQLite » en écart avec D-10 | validé ; PER-002 abaissé |
| ARC-008 | Architecte | core/jobspec.py:22-30 | Erreur du noyau porteuse d'un statut HTTP | validé |
| ARC-009 (+PER-006) | Architecte, Pertinence | plugins/bim/src/deskgate_bim/contracts/ | Règles 1 et 10 tenues ; copie MIT du contrat jamais lue | validé |
| MNT-010 | Mainteneur | src/deskgate | Cœur très lisible (radon mi A, ruff 0, 0 clone) — observation positive | validé |
| TST-003 | Tests | workers/mcp_call.py ; deskgate_bim | Sous-processus non mesurés par la couverture | validé |
| TST-005 | Tests | tests/proc/* | Bornes de temps réel | validé |
| TST-006 | Tests | tests/unit/test_api_security.py | « Jeton sans droit » au sens v0.1 ; test 403 à prévoir en v0.2 | validé |
| TEN-001 | Tenancy | api/middleware.py:22, 52 | Scopes non-`http` non gardés ; aucune route WebSocket (latent) | abaissé (Mineur → Info) |
| TEN-002 | Tenancy | jobs.py:146-196 | Pas de propriétaire de tâche : IDOR à prévenir avec les droits par plugin (v0.2) | validé |
| TEN-003 | Tenancy | runtime.py:143 | Rotation du jeton = `init --force` + redémarrage, non documentée | validé |
| TEN-004 | Tenancy | config.py:191-203 ; hostcheck.py:7 | `allow_non_loopback` à moitié fonctionnel, jeton en clair | validé |
| SEC-002 (+DON-007) | Sécurité, Données | jobspec.py:43 ; api/ | Aucune limite de taille du corps `POST /jobs` (l'audit, lui, est tronqué à 4 Ko) | abaissé (Mineur → Info) |
| SEC-004 | Sécurité | config.py:188-189 ; n8n/docker-compose.yml | Dossier de travail sous la racine partagée RW : choix documenté (fichiers = transport) | abaissé (Mineur → Info) |
| SEC-005 (+LIV-003) | Sécurité, Livraison | engine.py:257-261 ; core/env.py:50 | `env` de tous les serveurs MCP injecté dans chaque worker ; `DESKGATE_MCPENV__*` est un canal interne construit depuis runner.toml | validé ; LIV-003 requalifié (Mineur → Info) au cross-challenge : prémisse fausse |
| SEC-006 | Sécurité | bcfjob.py:47 ; core/redact.py:141 | Messages d'exception (chemins hôte) renvoyés ; double encodage non masqué | validé |
| FIA-005 | Fiabilité | api/routes_health.py:139-142 | `/health` sans état des threads | abaissé (Mineur → Info) |
| FIA-006 | Fiabilité | ARCHITECTURE.md:81 ; n8n/examples/ifc-clash.json:47 | Réutilisation (PLG-05) documentée avant l'heure ; exemple sans `idempotency_key` | validé |
| FIA-007 | Fiabilité | engine.py:349-350 | Annulation après la sortie du plugin écarte un résultat valide | validé |
| FIA-008 | Fiabilité | jobobject.py:188-208 | Worker suspendu hors Job si crash entre Popen et Assign | validé |
| FIA-009 | Fiabilité | engine.py:570-578 | Course théorique sur `JobHandle` à l'arrêt | validé |
| DON-005 | Données | store.py:135 | FK appliquée seulement via `store.connect` | validé |
| DON-008 | Données | store.py:543-547 | Essai compté avant la revérification d'hôte : audit inexact, sans autre effet (cross-challenge) | validé |
| LIV-005 | Livraison | .github/workflows/ci.yml | Pas de `permissions:`, actions par tag, pas de `timeout-minutes` (vecteur réel mais limité, cross-challenge) | abaissé (Mineur → Info) |
| LIV-007 | Livraison | AGENTS.md:178-185 | La mise à jour coupe les tâches en cours sans vérification | validé |
| PER-007 | Pertinence | core/errors.py ; outcome.py ; jobspec.py | Constantes déclarées, littéraux réécrits ailleurs | validé |
| PER-008 | Pertinence | pyproject.toml (×3) | Transitives importées directement (numpy, lark, xsdata) | validé |
| PER-009 | Pertinence | deskgate_bim/render.py ; pillow | Rendu 3D logiciel : coût/valeur à décider | validé |
| PER-010 | Pertinence | docs/passation/ | Dossier d'amorçage figé, lié depuis le README | validé |

---

## Annexe A — Cross-challenge (§7.2)

| Paire | Résultat |
|---|---|
| Architecte ↔ Tests | ARC-001, ARC-002, ARC-005 sans test, confirmé ; `serve()` sans couture d'injection (runtime.py 59 %). |
| Fiabilité ↔ Données | FIA-001 abaissé à Mineur par son auteur et fusionné avec DON-004 (aucune incohérence en base, retard seulement) ; DON-001 sans effet fiabilité notable ; DON-008 limité à l'audit. |
| Sécurité ↔ Livraison | LIV-003 requalifié Info (canal interne) et fusionné dans SEC-005 ; LIV-005 vecteur réel limité (jeton en écriture sur `push: main`) ; LIV-002 angle supply-chain confirmé. |
| Architecte ↔ Tenancy | Sans objet (pas de navigateur) ; le seul recoupement (scopes WebSocket) est TEN-001. |
| Tenancy ↔ Données | Sans objet (mono-tenant) ; TEN-002 note la colonne de propriétaire à prévoir en v0.2. |
| Performance ↔ Données, Billing ↔ Fiabilité | Non activées (rôles non exécutés). |

## Annexe B — Arbitrage council (§7.3)

Un seul finding encore débattu après sceptique et cross-challenge : **SEC-001**. Trois juges
indépendants, en aveugle : Majeur / Majeur / Majeur. Tous jugent que la règle 4 s'applique (lettre
« tout chemin reçu », ARCHITECTURE.md:108) et que l'exemption de `config.py:140-145` n'est ni
documentée ni justifiée ; tous écartent Bloquant (jeton et configuration opérateur requis) ; tous
recommandent `path_params` par outil MCP plutôt que la seule documentation.

## Annexe C — Écartés

Aucun finding invalidé par le sceptique. Doublons fusionnés (le porteur garde l'ID) : FIA-002 → ARC-001 ·
MNT-004 → ARC-003 · DON-004 → FIA-001 · DON-006, PER-002 → ARC-007 · DON-007 → SEC-002 · ARC-010 → PER-003 ·
LIV-006 → DON-003 · PER-006 → ARC-009 · LIV-003 → SEC-005. Résultats d'outil écartés comme faux positifs :
semgrep `doctor.py:88` (URL issue de runner.toml), `scheduler.py:18` (ElementTree sur la sortie de
`schtasks`, expat sans entités externes), `scheduler.py:196` (`SYSTEMROOT` local, sans shell) ; sondes
de code mort : routes FastAPI et commandes Typer (enregistrées par décorateur).

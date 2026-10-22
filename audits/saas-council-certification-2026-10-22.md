# Certification post-correction — saas-team-council — Deskgate — 2026-10-22

Mode re-vérification (`/saas-council-role`), un agent par rôle d'origine, lecture seule, en parallèle, sur le commit
`2f25c11` (code identique à `23f0617`, gate vert : `.arthemis/reports/gate-1-05.2.log`). Arbre immobile pendant la passe
(aucun agent en écriture). Findings d'origine : `audits/saas-council-2026-10-22.md`. Corrections : phase GSD 5.2.

> Mode isolé : pas de sceptique, pas de cross-challenge, pas d'arbitrage. Les nouveaux findings sont des **candidats** ;
> les deux contrôles mécaniques ont été appliqués (aucun Bloquant, toutes les preuves renseignées).

## 1. Verdicts

| ID | Rôle certificateur | Verdict | Preuve principale |
|---|---|---|---|
| ARC-001 (+FIA-002) | saas-architecte | **FERMÉ** | `supervisor.py:113-142` (recréation), `:49-55` (budget 3/600 s, code 6) ; `runtime.py:210-264` (Holder, `wake` tardif) ; commentaire faux supprimé ; 47 tests ciblés verts ; e2e `test_serve_supervision.py` vert au gate |
| FIA-001 | saas-fiabilite | **FERMÉ** | Sonde d'origine rejouée (vrai `Engine.run()`, WAL, `BEGIN IMMEDIATE`) : verrou 6,5 s → Job non tué, `succeeded` ; verrou maintenu → `on_fatal` à +30,8 s sans tuer le Job ; rejeu idempotent `store.py:282-289` |
| FIA-003 | saas-fiabilite | **FERMÉ** | `runtime.py:101-143` (`startup.log` avant `load_config`, plafond 256 Kio) ; sonde `stderr=None` : trace journalisée, signature masquée ; e2e pythonw vert au gate |
| FIA-005 | saas-fiabilite | **FERMÉ** | `core/health.py:20-32`, `/health` `engine`/`sender`, `degraded` ; pire cas sender ≈ 41 s < 60 s, engine ≈ 21,5 s < 30 s : pas de faux `stale` |
| MNT-007 | saas-mainteneur | **FERMÉ** | Docstrings `engine.py:7-12`, `sender.py:9-11` conformes au code réel ; radon : aucune fonction ajoutée au-delà de B |
| TST-004 | saas-tests | **FERMÉ** | `pyproject.toml:54` `error::ResourceWarning` ; gate 936 passed avec le filtre ; sonde de fuite → le filtre fait échouer le test |
| SEC-001 | saas-securite | **FERMÉ** | Sonde `JobsService` : `..`, jonction, hôte absolu, UNC, ADS, dict, liste, entier, null → 422 ; revalidation au lancement testée sur serveur MCP réel ; 20 tests verts (1 lien symbolique sauté) |
| SEC-005 | saas-securite | **FERMÉ** | `engine.py:346-352` : seules les variables du serveur visé ; test réel deux serveurs (`AUTRE_SECRET` absent) ; semgrep : aucun nouveau résultat |
| LIV-001 (= 05-06-msix) | saas-livraison | **FERMÉ** | Détection constatée dans cette session MSIX réelle (sonde d'écriture ; l'identité de paquet est absente, ce qui valide le double mécanisme) ; `init` refuse (code 2, sans `--force`) ; `doctor` en échec ; 61 tests verts ; 0x8007010B reproduit au gate |
| PER-001 | saas-pertinence | **FERMÉ** | `rg "bcf_executable\|bcf" src/deskgate --glob '*.py'` → aucun ; `doctor.py:120-124` générique ; 40 tests verts |

**10 / 10 fermés.**

## 2. Nouveaux findings introduits par la correction (§11.2)

Dédoublonnés (le porteur garde l'ID ; les co-émetteurs sont cités).

| ID | Sév. | Émetteur(s) | Localisation | Constat (preuve) | Recommandation |
|---|---|---|---|---|---|
| ARC-N2-001 (+FIAB-N2-002) | Mineur | architecte, fiabilité | `supervisor.py:137-156` ; `runtime.py:203-208` | Le budget est consommé avant `recover()` ; un recover qui échoue compte comme une recréation, sans back-off. Sonde : `gave_up = True`, 0 recréation. Un verrou externe d'environ 50 à 75 s fait sortir le runner en code 6, non relancé. En outre, un verdict différé en mémoire au moment du fatal est conclu `interrupted` | Ne compter la place qu'après un recover réussi, back-off borné ; documenter le verdict différé perdu |
| ARC-N2-002 | Mineur | architecte | `supervisor.py:144-160, 206-212` ; `runtime.py:226-263` | `stop()` sans `_lock` et pas de nouvelle vérification de `_stop` après `_recover()`. Sonde : un nouvel engine reste vivant après l'arrêt | Revérifier `_stop` avant `make_*()`/`start()` |
| MNT-N2-001 (+ARC-N2-003) | Mineur | mainteneur, architecte | `runtime.py:267-268` | `"Voir logs\runner.log."` non brute : `\r` = retour chariot (AST : CR présent). Le message d'abandon en code 6 affiche « logs⏎unner.log » | `logs\\runner.log` ou `log_path(home)` ; assertion sur le texte |
| LIVR-N2-002 | Mineur | livraison | `AGENTS.md:197` | Octet CR littéral dans la ligne de dépannage « code 6 » (`od -c`) | Remplacer par `logs\runner.log` |
| LIVR-N2-001 | Mineur | livraison | `cli.py:171-185` | `deskgate task install` n'appelle pas `refuse_if_packaged()` : contournement du garde-fou de LIV-001 | Appel en tête de `task_install` + test jumeau |
| TST-N2-001 | Mineur | tests | `tests/conftest.py:106` ; `doctor.py:180, 211` | La fixture fixe `last_task_result` à 0 ; aucun test n'exerce `run_all(with_task=True)` → `check_task()` → `last_task_result` par défaut. Un câblage cassé passerait | Test unitaire qui remplace `last_task_result` par 0x8007010B et vérifie la ligne « Tâche » en échec |
| LIVR-N2-003 | Info | livraison | `AGENTS.md:48-67` ; `scheduler.py:73-74` | Refus d'`init` non documenté ; sonde impossible → « processus non empaqueté » au lieu de « indéterminé » | Une phrase dans AGENTS.md ; niveau avertissement |
| FIAB-N2-001 | Info | fiabilité | `engine.py:499, 506` | `events_off` avance avant `update_progress` : un événement lu pendant un verrou est perdu (progression seulement) | Avancer l'offset après l'écriture |
| PER-N2-001 | Info | pertinence | `installer.py:34` ; `cli.py:201` | Antérieur à la 5.2 : message de désinstallation « C:\BIM » en dur quelle que soit la racine | Afficher la racine configurée |

Aucun Bloquant, aucun Majeur. Les deux défauts `\r` (MNT-N2-001, LIVR-N2-002) ont une seule cause, une séquence `\r` dans une chaîne non brute.

## 3. Non vérifié

- E2E non rejoués par les certificateurs (verts au gate : 33 passed).
- Tâche planifiée réelle (`tests/proc/test_scheduler_real.py`) non rejouée, verte au gate.
- Tests de lien symbolique : sautés localement (privilège absent), verts en CI.
- Processus doté d'une identité de paquet MSIX : seul le test unitaire avec identité injectée le couvre.

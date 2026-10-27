# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v0.1 — Runner minimal

**Shipped:** 2026-10-27 (version produit 0.1.0, tag `v0.1.0`)
**Phases:** 9 (1 à 5, 5.1 à 5.4) | **Plans:** 72 | **Commits:** 471 depuis 016a497 (175 de code, test et correctif)

### What Was Built
- Runner local sécurisé (127.0.0.1, jeton haché, Host, chemins validés), file SQLite durable, exécution en Job Object.
- Rappel garanti vers la `resumeUrl` avec outbox, politique n8n 2.43.8, `data` exposé et marqueurs de repli.
- Capacités `ifc.clash` (BCF 2.1 lisible dans BIMcollab Zoom) et `mcp.call`, frontière GPL tenue par `deskgate-bcf`.
- Installation réelle : `init`, tâche planifiée, `doctor`, `purge`, compose n8n 2.43.8 et workflow d'exemple.

### What Worked
- Les vrais sous-processus Windows dans les tests (Job Object, MCP stdio, SDK) ont attrapé des défauts qu'un mock aurait masqués.
- La boucle audit → phase insérée → certification par le rôle d'origine : chaque recertification a trouvé quelque chose
  (DS-MAINT-1 partiel, DS3-1 en octets, DS3-2 purge), rien n'a été déclaré fermé sans sonde rejouée.
- Les tests RED écrits avant chaque correctif (phases 5.4-01 à 09) ont tous échoué pour la bonne raison.
- La recette sur la machine réelle (ACC-01 sur maquettes de 532 Mo, 05.4-D2 sur les deux n8n) a validé le contrat de bout en bout.

### What Was Inefficient
- Les SUMMARY n'ont presque jamais de `one-liner` dans leur frontmatter : CHANGELOG et MILESTONES ont dû être rédigés depuis
  REQUIREMENTS et ROADMAP, et `milestone complete` a produit des accomplissements inutilisables (corrigés à la main).
- Trois tours de gaps sur la phase 5.4 pour des défauts que la première passe aurait pu voir (seuil en caractères, champ
  métier `truncated`).
- Pièges d'environnement répétés : fins de ligne CRLF, antislashs interprétés par `sed`, sortie cp1252, virtualisation
  MSIX de `%LOCALAPPDATA%`, Pythons de uv cassés.
- Une exécution du planner coupée par une erreur d'API ; reprise sans perte grâce aux plans déjà écrits.

### Patterns Established
- Scope de commit `type(NN-PP)` pour tout commit de code, y compris les corrections de style.
- Exécution séquentielle dans l'arbre principal, un exécuteur à la fois, gate complet journalisé dans `.arthemis/reports/`.
- Toute vérification humaine passe par `NN-HUMAN-UAT.md` avec `blocks`, et les reports par une décision consignée.
- Les contrats documentaires sont verrouillés par test (`test_architecture_doc.py`, références `fichier:ligne`).

### Key Lessons
1. Exiger un `one-liner` dans le frontmatter de chaque SUMMARY : c'est la source du CHANGELOG.
2. Mesurer les tailles en octets UTF-8 partout où un plafond est en octets ; tester avec du texte non ASCII.
3. Un marqueur de contrat ne doit pas pouvoir être confondu avec un champ métier : une seule fonction de reconnaissance (`is_marker`).
4. Vérifier le démarrage réel après redémarrage du PC, Docker Desktop compris, avant de déclarer une installation prête.
5. Surveiller `runner.log` au repos : des verrous SQLite sont apparus sans charge (999.11).

### Cost Observations
- Model mix : orchestration et planification sur opus, exécution, vérification et recherche sur sonnet ; proportions non mesurées.
- Sessions : plusieurs passations ARTHEMIS entre le 2026-10-20 et le 2026-10-27 ; nombre exact non mesuré.
- Notable : les certifications par sonde rejouée coûtent cher mais ont trouvé trois défauts réels.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v0.1 | non mesuré | 9 | Pipeline ARTHEMIS complet (cadrage, council, audit senior, certifications, publication) |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v0.1 | 1053 + 33 e2e (gate du 2026-10-26) | non mesurée | non mesuré |

### Top Lessons (Verified Across Milestones)

1. À établir au prochain milestone.

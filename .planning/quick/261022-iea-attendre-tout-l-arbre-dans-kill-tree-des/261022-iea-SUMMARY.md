# Quick 261022-iea : kill_tree attend tout l'arbre

`kill_tree` (tests/e2e/conftest.py) collecte les descendants via `psutil` avant `taskkill`, attend le lanceur puis chaque descendant (10 s), tue les survivants et échoue en français en listant les PID. Signature inchangée, aucun fichier de `src/deskgate` modifié.

- Nouveau test : tests/e2e/test_kill_tree.py (arbre mort, `deskgate.db` relisible, `integrity_check` ok).
- Vérification : ruff, pyright propres ; `pytest -m e2e tests/e2e` : 30 passés.
- Commit : voir `git log` (test(quick-261022-iea): attendre tout l'arbre dans kill_tree).

## Deviations
Ajout de `contextlib.suppress` (règle ruff SIM105). Les deux tâches sont dans un seul commit, comme le prévoit le critère de succès.

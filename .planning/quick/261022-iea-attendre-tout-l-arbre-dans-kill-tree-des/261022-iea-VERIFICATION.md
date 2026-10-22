---
phase: quick-261022-iea
verified: 2026-10-22T00:00:00Z
status: passed
score: 5/5 must-haves verified
---

# Quick 261022-iea : vérification

**Objectif :** `kill_tree` attend la mort de tout l'arbre du runner avant que le test relise la base SQLite ; test de non-régression ; aucun changement de `src/deskgate`.
**Commit vérifié :** b233760

## Vérités observables

| # | Vérité | Statut | Preuve |
|---|--------|--------|--------|
| 1 | Après `kill_tree`, plus aucun processus de l'arbre vivant | VERIFIE | `conftest.py` collecte `children(recursive=True)` avant `taskkill`, puis `p.wait(10)` et `psutil.wait_procs(enfants, timeout=10)` |
| 2 | La base se relit sans `OperationalError` | VERIFIE | `test_kill_tree` relit `deskgate.db` (integrity_check, count) : vert ; `test_callback_secret` vert |
| 3 | Un survivant fait échouer le test en français avec les PID | VERIFIE | `proc.kill()` puis `pytest.fail("Processus du runner encore vivants après taskkill : {pids}")` |
| 4 | Signature `kill_tree(p: subprocess.Popen[bytes]) -> None` inchangée | VERIFIE | Diff : seule la docstring et le corps changent ; appelants intacts |
| 5 | Aucun fichier de `src/deskgate` modifié | VERIFIE | `git show --stat` : uniquement `tests/e2e/conftest.py` et `tests/e2e/test_kill_tree.py` |

**Score :** 5/5

## Artefacts et liens

- `tests/e2e/conftest.py` : substantiel, contient `psutil.wait_procs` et `children(recursive=True)` ; taskkill en liste, sans `shell=True` (grep vide).
- `tests/e2e/test_kill_tree.py` : démarre un vrai runner, relève les PID de l'arbre, appelle `kill_tree`, vérifie l'absence de PID vivants et la lecture de la base. Les écritures restent sous `tmp_path` (fixture `data_home`).
- Liens : collecte de l'arbre avant taskkill : câblé ; taskkill `/F /T` en liste : câblé.

## Contrôles comportementaux

| Commande | Résultat |
|----------|----------|
| `uv run pytest -m e2e tests/e2e/test_kill_tree.py tests/e2e/test_callback_secret.py -q` (UV_PYTHON 3.14) | 3 passed en 20 s |
| `ruff check` sur les deux fichiers | All checks passed |

## Anti-motifs

Aucun (pas de TODO, pas de stub, pas de `shell=True`).

## Réserves

- Le test de non-régression ne reproduit pas déterministement la course d'origine (CI Python 3.13) ; il vérifie le résultat (arbre mort, base lisible). Non bloquant.
- La suite e2e complète et pyright n'ont pas été rejoués ici (seuls les tests demandés et ruff).

## Conclusion

Objectif atteint. Aucun écart.

_Vérifié : 2026-10-22 — Claude (gsd-verifier)_

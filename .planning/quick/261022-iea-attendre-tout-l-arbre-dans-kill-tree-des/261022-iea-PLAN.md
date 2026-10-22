---
phase: quick-261022-iea
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/e2e/conftest.py
  - tests/e2e/test_kill_tree.py
autonomous: true
requirements: [QUICK-261022-iea]

must_haves:
  truths:
    - "Après kill_tree(p), aucun processus de l'arbre du runner (lanceur de venv, runner Python enfant, éventuels plugins) n'est encore vivant"
    - "Après kill_tree(p), la base deskgate.db du DESKGATE_HOME de test se relit sans sqlite3.OperationalError"
    - "Si un processus de l'arbre survit au délai, le test échoue explicitement avec un message en français listant les PID"
    - "La signature kill_tree(p: subprocess.Popen[bytes]) -> None est inchangée ; les ~23 appels de tests/e2e marchent sans modification"
    - "Aucun fichier de src/deskgate n'est modifié"
  artifacts:
    - path: "tests/e2e/conftest.py"
      provides: "kill_tree qui attend tout l'arbre via psutil"
      contains: "psutil.wait_procs"
    - path: "tests/e2e/test_kill_tree.py"
      provides: "Test de non-régression : arbre du runner entièrement mort après kill_tree"
      contains: "kill_tree"
  key_links:
    - from: "tests/e2e/conftest.py::kill_tree"
      to: "psutil.Process(p.pid).children(recursive=True)"
      via: "collecte de l'arbre AVANT taskkill"
      pattern: "children\\(recursive=True\\)"
    - from: "tests/e2e/conftest.py::kill_tree"
      to: "taskkill /F /T /PID"
      via: "subprocess.run en liste, sans shell=True"
      pattern: "\"taskkill\", \"/F\", \"/T\""
---

<objective>
Corriger `kill_tree` dans `tests/e2e/conftest.py` pour qu'il attende la mort de TOUT l'arbre de
processus du runner, pas seulement du lanceur de venv.

Purpose : `sys.executable -m deskgate serve` passe par le lanceur `python.exe` du venv, qui crée un
processus Python enfant (le vrai runner). Aujourd'hui `p.wait(10)` n'attend que le lanceur ; le
runner enfant peut encore tenir `deskgate.db` (WAL) quand le test relit la base, d'où
`sqlite3.OperationalError: disk I/O error` dans
`tests/e2e/test_callback_secret.py::test_audit_parcours` (CI windows-latest, Python 3.13,
run 39568004313).
Output : `kill_tree` corrigé + test de non-régression. Aucun changement du code produit.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md
@tests/e2e/conftest.py
@tests/e2e/test_callback_secret.py

<interfaces>
Actuel (tests/e2e/conftest.py, l. 109-112) :
```python
def kill_tree(p: subprocess.Popen[bytes]) -> None:
    """Tue l'arbre entier (le lanceur de venv crée un processus enfant)."""
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
    p.wait(10)
```
Aides disponibles dans le même fichier : `write_config(home, port, *, capabilities=None, callback=None)`,
`runner_env(data_home, instance_name)`, `start_runner(env, log_path=None)`,
`wait_health(port, proc, timeout=15.0)`, `TOKEN`, `api(...)`.
Fixtures (tests/conftest.py) : `data_home` (= `tmp_path/home`, pose `DESKGATE_HOME` : aucune
écriture sous %LOCALAPPDATA%/%APPDATA%), `instance_name` (mutex unique), `free_port`.
Marquage des fichiers e2e :
```python
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows seul"),
]
```
psutil est déjà en dépendance dev (`psutil>=7.2`) et utilisé dans `tests/_support/procs.py`.
Ruff : `tests/**` ignore S101, S603, S607 (taskkill en liste OK).
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: kill_tree attend tout l'arbre (psutil) et échoue si un processus survit</name>
  <files>tests/e2e/conftest.py</files>
  <action>
Ajouter `import psutil` (bloc tiers, ordre isort : avant `import pytest`). Réécrire le corps de
`kill_tree` en gardant exactement la signature `kill_tree(p: subprocess.Popen[bytes]) -> None` :

1. Collecter l'arbre AVANT de tuer : `try: enfants = psutil.Process(p.pid).children(recursive=True)`
   `except psutil.NoSuchProcess: enfants = []` (le lanceur peut déjà être mort, p. ex. appel depuis
   `wait_health` ou runner sorti tout seul ; `taskkill` échoue alors sans conséquence).
2. `subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, check=False)`
   — liste d'arguments, jamais `shell=True` (règle 2 du dépôt).
3. `p.wait(10)` (inchangé ; lève `TimeoutExpired` comme avant si le lanceur ne meurt pas).
4. `_, vivants = psutil.wait_procs(enfants, timeout=10)`.
5. Si `vivants` n'est pas vide : tenter `proc.kill()` sur chacun (en ignorant `psutil.NoSuchProcess`)
   pour ne pas laisser fuir de processus sur la CI, puis
   `pytest.fail(f"Processus du runner encore vivants après taskkill : {pids}")` avec la liste triée
   des PID. Message en français.

Mettre à jour la docstring en français : explique que le lanceur de venv crée un runner Python
enfant qui tient `deskgate.db` (WAL), et qu'on attend donc tout l'arbre collecté avant `taskkill`.
Ne modifier aucun autre helper ni aucun appelant. Aucune modification sous `src/deskgate`.
  </action>
  <verify>
    <automated>UV_PYTHON="C:\Users\Tanguy\AppData\Local\Python\pythoncore-3.14-64\python.exe" uv run ruff check tests/e2e/conftest.py &amp;&amp; UV_PYTHON="C:\Users\Tanguy\AppData\Local\Python\pythoncore-3.14-64\python.exe" uv run ruff format --check tests/e2e/conftest.py &amp;&amp; UV_PYTHON="C:\Users\Tanguy\AppData\Local\Python\pythoncore-3.14-64\python.exe" uv run pyright tests/e2e/conftest.py</automated>
  </verify>
  <done>kill_tree collecte les descendants via psutil avant taskkill, attend lanceur + descendants
  (10 s chacun), échoue en français si l'un survit ; signature inchangée ; ruff et pyright propres.</done>
</task>

<task type="auto">
  <name>Task 2: Test de non-régression de kill_tree et suite e2e complète</name>
  <files>tests/e2e/test_kill_tree.py</files>
  <action>
Créer `tests/e2e/test_kill_tree.py` (docstring de module en français, même `pytestmark` e2e +
skipif Windows que les autres fichiers e2e, `@pytest.mark.timeout(60)`).

Test `test_kill_tree_attend_tout_l_arbre(data_home, instance_name, free_port)` :
- `write_config(data_home, free_port)`, `env = runner_env(data_home, instance_name)`,
  `proc = start_runner(env)`, `wait_health(free_port, proc)`.
- Collecter les PID de l'arbre : `pids = [proc.pid] + [c.pid for c in
  psutil.Process(proc.pid).children(recursive=True)]`.
- `kill_tree(proc)` dans un `try/finally` qui ferme `proc.stdout`/`proc.stderr`.
- Assert : `[pid for pid in pids if psutil.pid_exists(pid)] == []` (un PID réutilisé est
  improbable dans l'intervalle ; si besoin, comparer aussi `create_time` relevé avant).
- Assert : la base se relit immédiatement : `sqlite3.connect(data_home / "deskgate.db", timeout=5)`,
  `PRAGMA integrity_check` renvoie `"ok"` et `SELECT count(*) FROM jobs` passe ; fermer la connexion.
  (Si le nom de table diffère, utiliser `SELECT count(*) FROM sqlite_master`.)

Importer depuis `tests.e2e.conftest` comme les autres fichiers (`kill_tree`, `runner_env`,
`start_runner`, `wait_health`, `write_config`). Toutes les écritures restent sous `tmp_path`.

Puis lancer toute la suite e2e (les ~23 appels existants doivent passer sans modification) et
ruff/pyright sur les deux fichiers.
  </action>
  <verify>
    <automated>UV_PYTHON="C:\Users\Tanguy\AppData\Local\Python\pythoncore-3.14-64\python.exe" uv run ruff check tests/e2e/conftest.py tests/e2e/test_kill_tree.py &amp;&amp; UV_PYTHON="C:\Users\Tanguy\AppData\Local\Python\pythoncore-3.14-64\python.exe" uv run pyright tests/e2e/conftest.py tests/e2e/test_kill_tree.py &amp;&amp; UV_PYTHON="C:\Users\Tanguy\AppData\Local\Python\pythoncore-3.14-64\python.exe" uv run pytest -m e2e tests/e2e -q</automated>
  </verify>
  <done>Nouveau test vert ; suite `pytest -m e2e tests/e2e` entièrement verte (dont
  test_callback_secret.py::test_audit_parcours) ; ruff/pyright propres.</done>
</task>

</tasks>

<verification>
- `git diff --stat` ne touche que `tests/e2e/conftest.py` et `tests/e2e/test_kill_tree.py` (aucun
  fichier sous `src/deskgate`).
- `grep -n "shell=True" tests/e2e/conftest.py` ne renvoie rien.
- Suite e2e complète verte avec UV_PYTHON 3.14.
</verification>

<success_criteria>
- kill_tree attend lanceur + tous les descendants collectés avant taskkill ; échec explicite en
  français si un processus survit.
- La relecture de `deskgate.db` juste après kill_tree ne lève plus `disk I/O error`.
- Commit : `test(quick-261022-iea): attendre tout l'arbre dans kill_tree` (≤ 72 caractères, sujet
  en français), sans `.arthemis/**` ni `.planning/` mêlés. Ne pas pousser.
</success_criteria>

<output>
After completion, create `.planning/quick/261022-iea-attendre-tout-l-arbre-dans-kill-tree-des/261022-iea-SUMMARY.md`
</output>

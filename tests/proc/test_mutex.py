"""RUN-03 : le mutex nommé bloque une seconde instance et se libère à la mort du détenteur."""

from __future__ import annotations

import subprocess
import sys

import pytest

from deskgate.instance import acquire_mutex

pytestmark = [
    pytest.mark.proc,
    pytest.mark.skipif(sys.platform != "win32", reason="Mutex Windows"),
]


@pytest.mark.timeout(60)
def test_meme_processus(instance_name: str) -> None:
    assert acquire_mutex(instance_name)
    assert acquire_mutex(instance_name) is None


@pytest.mark.timeout(60)
def test_detenteur_externe_puis_mort(instance_name: str) -> None:
    nom = instance_name + "-b"
    code = (
        "import sys,time; from deskgate.instance import acquire_mutex; "
        "h=acquire_mutex(sys.argv[1]); print('ACQUIRED' if h else 'BUSY', flush=True); "
        "time.sleep(120)"
    )
    p = subprocess.Popen([sys.executable, "-c", code, nom], stdout=subprocess.PIPE, text=True)
    try:
        assert p.stdout is not None
        assert p.stdout.readline().strip() == "ACQUIRED"
        assert acquire_mutex(nom) is None
    finally:
        # Le lanceur de venv double le processus : tuer l'arbre entier (/T).
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        p.wait(10)
        if p.stdout is not None:
            p.stdout.close()
    assert acquire_mutex(nom)

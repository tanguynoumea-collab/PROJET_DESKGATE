"""Tests de `deskgate doctor` : configuration, dossiers, jeton, port, plugins."""

from __future__ import annotations

import json
import shutil
import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from deskgate import doctor, installer, scheduler
from deskgate.core.config import RunnerConfig, load_config
from deskgate.locations import config_path

pytestmark = pytest.mark.unit


def _setup(tmp_path: Path, port: int | None = None) -> tuple[Path, Path]:
    home = tmp_path / "home"
    root = (tmp_path / "bim").as_posix()
    installer.init_config(home, root, force=False, now=datetime(2026, 10, 21))
    if port is not None:
        cfg = config_path(home)
        text = cfg.read_text(encoding="utf-8")
        assert "port = 8765" in text
        cfg.write_text(text.replace("port = 8765", f"port = {port}"), encoding="utf-8")
    return home, Path(root)


def _levels(checks: list[doctor.Check]) -> set[str]:
    return {c.level for c in checks}


def test_configuration_absente_est_un_echec(tmp_path: Path) -> None:
    checks = doctor.run_all(tmp_path / "vide", with_task=False)
    assert [c.name for c in checks if c.level == "echec"] == ["Configuration"]
    assert doctor.exit_code(checks) == 1
    assert all(c.name in ("Contexte d'exécution", "Configuration", "Environnement") for c in checks)


def test_configuration_invalide(tmp_path: Path) -> None:
    home, _ = _setup(tmp_path)
    config_path(home).write_text("n'importe quoi = [", encoding="utf-8")
    check, cfg = doctor.check_config(config_path(home))
    assert cfg is None
    assert check.level == "echec"
    assert "deskgate serve" in check.message


def test_installation_saine(tmp_path: Path, free_port: int) -> None:
    home, _ = _setup(tmp_path, free_port)
    checks = doctor.run_all(home, with_task=False)
    by_name = {c.name: c for c in checks}
    assert by_name["Configuration"].level == "ok"
    assert by_name["Dossiers"].level == "ok"
    assert by_name["Jeton"].level == "ok"
    assert by_name["Port"].level == "ok"
    assert "libre" in by_name["Port"].message


def test_dossier_livrables_manquant(tmp_path: Path) -> None:
    home, root = _setup(tmp_path)
    shutil.rmtree(root / "livrables")
    cfg = load_config(config_path(home))
    checks = doctor.check_dirs(cfg, home)
    assert any(c.level == "echec" and "livrables" in c.message for c in checks)


def test_jeton_du_gabarit(tmp_path: Path) -> None:
    home, _ = _setup(tmp_path)
    cfg = load_config(config_path(home))
    zero = cfg.model_copy(update={"token_sha256": installer.ZERO_HASH})
    assert doctor.check_token(zero).level == "echec"
    assert doctor.check_token(cfg).level == "ok"


def test_port_runner_joignable(tmp_path: Path) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = json.dumps({"status": "ok", "version": "9.9"}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        home, _ = _setup(tmp_path, server.server_address[1])
        cfg = load_config(config_path(home))
        check = doctor.check_port(cfg)
    finally:
        server.shutdown()
        server.server_close()
    assert check.level == "ok"
    assert "9.9" in check.message


@contextmanager
def _listening() -> Iterator[int]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(5)
        yield int(s.getsockname()[1])


def test_port_occupe_par_un_autre_programme(tmp_path: Path) -> None:
    with _listening() as port:
        home, _ = _setup(tmp_path, port)
        cfg = load_config(config_path(home))
        check = doctor.check_port(cfg, timeout=0.5)
    assert check.level == "echec"
    assert "occupé" in check.message


def _with_capabilities(tmp_path: Path, extra: str) -> tuple[Path, Path]:
    home, _root = _setup(tmp_path)
    cfg = config_path(home)
    text = cfg.read_text(encoding="utf-8")
    cfg.write_text(text + "\n" + extra, encoding="utf-8")
    return home, cfg


def test_plugins_interpreteur_absent(tmp_path: Path) -> None:
    missing = (tmp_path / "nope" / "python.exe").as_posix()
    _home, cfg_file = _with_capabilities(
        tmp_path,
        f'[capabilities."ifc.test"]\nkind = "python"\npython = \'{missing}\'\n'
        'entry = "mod:fn"\ntimeout_max = 60\n',
    )
    cfg = load_config(cfg_file)
    checks = doctor.check_plugins(cfg)
    assert any(c.level == "echec" and "ifc.test" in c.message for c in checks)


def _cap_requise(tmp_path: Path, exe: str, declare: bool) -> RunnerConfig:
    python = Path(shutil.which("python") or __import__("sys").executable).as_posix()
    req = 'required_files = ["bcf_executable"]\n' if declare else ""
    _, cfg_file = _with_capabilities(
        tmp_path,
        f'[capabilities."ifc.clash"]\nkind = "python"\npython = \'{python}\'\n'
        f'entry = "mod:fn"\ntimeout_max = 60\n{req}'
        f"[capabilities.\"ifc.clash\".settings]\nbcf_executable = '{exe}'\n",
    )
    return load_config(cfg_file)


def test_plugins_fichier_requis_absent(tmp_path: Path) -> None:
    absent = (tmp_path / "bcf.exe").as_posix()
    checks = doctor.check_plugins(_cap_requise(tmp_path, absent, True))
    assert any(
        c.level == "echec" and "ifc.clash : bcf_executable absent" in c.message for c in checks
    )


def test_plugins_fichier_requis_present(tmp_path: Path) -> None:
    present = tmp_path / "bcf.exe"
    present.write_bytes(b"")
    checks = doctor.check_plugins(_cap_requise(tmp_path, present.as_posix(), True))
    assert not any(c.level == "echec" for c in checks)


def test_plugins_settings_non_declare_ignore(tmp_path: Path) -> None:
    absent = (tmp_path / "bcf.exe").as_posix()
    checks = doctor.check_plugins(_cap_requise(tmp_path, absent, False))
    assert not any(c.level == "echec" for c in checks)


def test_plugins_serveur_mcp_absent(tmp_path: Path) -> None:
    absent = (tmp_path / "mcp.exe").as_posix()
    _, cfg_file = _with_capabilities(tmp_path, f"[mcp_servers.srv]\ncommand = '{absent}'\n")
    checks = doctor.check_plugins(load_config(cfg_file))
    assert any(c.level == "echec" and "srv" in c.message for c in checks)


def test_aucune_capacite_est_un_avertissement(tmp_path: Path) -> None:
    home, _ = _setup(tmp_path)
    cfg = load_config(config_path(home)).model_copy(update={"capabilities": {}, "mcp_servers": {}})
    assert _levels(doctor.check_plugins(cfg)) == {"avertissement"}


def test_deskgate_home_defini_avertit() -> None:
    assert doctor.check_home_env({"DESKGATE_HOME": "x"}).level == "avertissement"
    assert doctor.check_home_env({}).level == "ok"


def test_exit_code() -> None:
    ok = doctor.Check("a", "ok", "")
    warn = doctor.Check("b", "avertissement", "")
    bad = doctor.Check("c", "echec", "")
    assert doctor.exit_code([ok, warn]) == 0
    assert doctor.exit_code([ok, bad]) == 1


def test_doctor_contexte_empaquete() -> None:
    check = doctor.check_context(detect=lambda: "processus empaqueté (paquet P)")
    assert check.name == "Contexte d'exécution"
    assert check.level == "echec"
    assert "terminal normal" in check.message


def test_doctor_contexte_normal() -> None:
    assert doctor.check_context(detect=lambda: None).level == "ok"


def test_run_all_contexte_en_tete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler, "packaged_context", lambda: "processus empaqueté (paquet P)")
    home = tmp_path / "home"
    home.mkdir()
    checks = doctor.run_all(home, with_task=False)
    assert checks[0].name == "Contexte d'exécution"
    assert checks[0].level == "echec"
    assert doctor.exit_code(checks) == 1

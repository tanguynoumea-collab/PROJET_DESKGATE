"""Tests de `deskgate init` (INS-01) : aucun accès à la vraie machine."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from deskgate import installer, scheduler
from deskgate.cli import app
from deskgate.core.config import load_config
from deskgate.core.tokens import hash_token

pytestmark = pytest.mark.unit

runner = CliRunner()


@pytest.fixture
def pythonw(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    fake = tmp_path / "pythonw.exe"
    fake.write_bytes(b"")
    monkeypatch.setattr(installer, "launcher_command", lambda: str(fake))
    monkeypatch.setattr(installer, "query_task_xml", lambda name: None)
    return fake


@pytest.fixture
def created_tasks(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, bytes]]:
    calls: list[tuple[str, bytes]] = []
    monkeypatch.setattr(installer, "create_task", lambda name, xml, tmp: calls.append((name, xml)))
    return calls


def _root(tmp_path: Path) -> str:
    return (tmp_path / "bim").as_posix()


def test_premier_passage(data_home: Path, tmp_path: Path) -> None:
    root = _root(tmp_path)
    res = runner.invoke(app, ["init", "--root", root, "--no-task"])
    assert res.exit_code == 0
    lines = res.stdout.strip().splitlines()
    assert len(lines) == 1
    token = lines[0]
    assert len(token) >= 43
    cfg_path = data_home / "runner.toml"
    cfg = load_config(cfg_path)
    assert cfg.token_sha256 == hash_token(token)
    assert token not in cfg_path.read_text(encoding="utf-8")
    assert [str(r).replace("\\", "/") for r in cfg.paths.allowed_roots] == [root]
    for name in ("depot", "travail", "livrables"):
        assert (tmp_path / "bim" / name).is_dir()
    assert (data_home / "logs").is_dir()
    assert (data_home / "plugins").is_dir()
    assert ">>> exemples phase 4" in cfg_path.read_text(encoding="utf-8")
    assert token not in res.stderr


def test_relance_ne_touche_rien(data_home: Path, tmp_path: Path) -> None:
    args = ["init", "--root", _root(tmp_path), "--no-task"]
    runner.invoke(app, args)
    before = (data_home / "runner.toml").read_bytes()
    res = runner.invoke(app, args)
    assert res.exit_code == 0
    assert res.stdout.strip() == ""
    assert (data_home / "runner.toml").read_bytes() == before
    assert "déjà" in res.stderr


def test_force_sauvegarde_et_regenere(data_home: Path, tmp_path: Path) -> None:
    args = ["init", "--root", _root(tmp_path), "--no-task"]
    first = runner.invoke(app, args).stdout.strip()
    old = (data_home / "runner.toml").read_text(encoding="utf-8")
    res = runner.invoke(app, [*args, "--force"])
    assert res.exit_code == 0
    second = res.stdout.strip()
    assert second
    assert second != first
    backups = list(data_home.glob("runner.toml.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == old
    assert load_config(data_home / "runner.toml").token_sha256 == hash_token(second)


@pytest.mark.parametrize("root", ["//serveur/partage", "\\\\serveur\\partage"])
def test_unc_refuse(data_home: Path, root: str) -> None:
    res = runner.invoke(app, ["init", "--root", root, "--no-task"])
    assert res.exit_code == 2
    assert not (data_home / "runner.toml").exists()


def test_deskgate_home_refuse_la_tache(
    data_home: Path, tmp_path: Path, pythonw: Path, created_tasks: list
) -> None:
    res = runner.invoke(app, ["init", "--root", _root(tmp_path), "--yes"])
    assert res.exit_code == 1
    assert "DESKGATE_HOME" in res.stderr
    assert created_tasks == []


def test_yes_installe_la_tache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pythonw: Path,
    created_tasks: list[tuple[str, bytes]],
) -> None:
    monkeypatch.delenv("DESKGATE_HOME", raising=False)
    monkeypatch.setattr("deskgate.locations.default_home", lambda: tmp_path / "home2")
    res = runner.invoke(app, ["init", "--root", _root(tmp_path), "--yes"])
    assert res.exit_code == 0, res.stderr
    assert len(created_tasks) == 1
    name, xml = created_tasks[0]
    assert name == "Deskgate"
    text = xml.decode("utf-16")
    assert "-m deskgate serve" in text
    assert "pythonw.exe" in text


def test_refus_interactif(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pythonw: Path,
    created_tasks: list[tuple[str, bytes]],
) -> None:
    monkeypatch.delenv("DESKGATE_HOME", raising=False)
    monkeypatch.setattr("deskgate.locations.default_home", lambda: tmp_path / "home2")
    res = runner.invoke(app, ["init", "--root", _root(tmp_path)], input="n\n")
    assert res.exit_code == 0
    assert created_tasks == []
    # CliRunner recopie la saisie simulée dans stdout ; la question, elle, est sur stderr.
    assert len(res.stdout.splitlines()[0]) >= 43
    assert "Installer la tâche" in res.stderr


_RAISON = "écritures sous %LOCALAPPDATA% redirigées vers le paquet Claude_x"


def test_init_refuse_en_contexte_empaquete(
    data_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scheduler, "packaged_context", lambda: _RAISON)
    res = runner.invoke(app, ["init", "--root", _root(tmp_path), "--no-task"])
    assert res.exit_code == 2
    assert "Terminal normal obligatoire" in res.stderr
    assert "AGENTS.md" in res.stderr
    assert list(data_home.iterdir()) == []
    assert not (tmp_path / "bim").exists()


def test_init_refuse_meme_avec_force(
    data_home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pythonw: Path,
    created_tasks: list[tuple[str, bytes]],
) -> None:
    monkeypatch.setattr(scheduler, "packaged_context", lambda: _RAISON)
    res = runner.invoke(app, ["init", "--root", _root(tmp_path), "--force", "--yes"])
    assert res.exit_code == 2
    assert "Terminal normal obligatoire" in res.stderr
    assert list(data_home.iterdir()) == []
    assert not (tmp_path / "bim").exists()
    assert created_tasks == []


def _prepare_task_install_msix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    lues: list[str] = []
    monkeypatch.delenv("DESKGATE_HOME", raising=False)
    monkeypatch.setattr("deskgate.locations.default_home", lambda: tmp_path / "home2")
    monkeypatch.setattr(scheduler, "packaged_context", lambda: _RAISON)
    monkeypatch.setattr(installer, "query_task_xml", lambda name: lues.append(name))
    return lues


def test_task_install_refuse_en_contexte_empaquete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pythonw: Path,
    created_tasks: list[tuple[str, bytes]],
) -> None:
    lues = _prepare_task_install_msix(tmp_path, monkeypatch)
    res = runner.invoke(app, ["task", "install", "--yes"])
    assert res.exit_code == 2
    assert "Terminal normal obligatoire" in res.stderr
    assert "deskgate task install" in res.stderr
    assert created_tasks == []
    assert lues == []
    assert not (tmp_path / "home2").exists()


def test_task_install_refuse_sans_poser_la_question(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pythonw: Path,
    created_tasks: list[tuple[str, bytes]],
) -> None:
    lues = _prepare_task_install_msix(tmp_path, monkeypatch)
    res = runner.invoke(app, ["task", "install"], input="o\n")
    assert res.exit_code == 2
    assert "Installer la tâche" not in res.stderr
    assert created_tasks == []
    assert lues == []

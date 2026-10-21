"""Tests de `deskgate task …` (INS-02) : le Planificateur est remplacé par des fakes."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from deskgate import installer, scheduler
from deskgate.cli import app
from deskgate.scheduler import TaskSpec, build_task_xml

pytestmark = pytest.mark.unit

runner = CliRunner()


def _xml(tmp_path: Path, *, limit: str = "PT0S") -> str:
    fake = tmp_path / "pythonw.exe"
    fake.write_bytes(b"")
    spec = TaskSpec(
        user="PC\\moi", command=str(fake), arguments="-m deskgate serve", working_dir=str(tmp_path)
    )
    return build_task_xml(spec).decode("utf-16").replace("PT0S", limit)


def test_status_absente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler, "query_task_xml", lambda name: None)
    res = runner.invoke(app, ["task", "status"])
    assert res.exit_code == 1
    assert "absente" in res.stdout


def test_status_conforme(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    xml = _xml(tmp_path)
    monkeypatch.setattr(scheduler, "query_task_xml", lambda name: xml)
    res = runner.invoke(app, ["task", "status"])
    assert res.exit_code == 0
    assert "conforme" in res.stdout
    assert "pythonw.exe" in res.stdout
    assert "-m deskgate serve" in res.stdout


def test_status_limite_de_duree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    xml = _xml(tmp_path, limit="PT72H")
    monkeypatch.setattr(scheduler, "query_task_xml", lambda name: xml)
    res = runner.invoke(app, ["task", "status"])
    assert res.exit_code == 1
    assert "[echec]" in res.stdout
    assert "limite de durée" in res.stdout


def test_remove_ordre_et_donnees_conservees(
    monkeypatch: pytest.MonkeyPatch, data_home: Path
) -> None:
    (data_home / "deskgate.db").write_bytes(b"x")
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(scheduler, "end_task", lambda n: calls.append(("end", n)) or True)
    monkeypatch.setattr(scheduler, "delete_task", lambda n: calls.append(("delete", n)) or True)
    res = runner.invoke(app, ["task", "remove"])
    assert res.exit_code == 0
    assert calls == [("end", "Deskgate"), ("delete", "Deskgate")]
    assert (data_home / "deskgate.db").exists()


def test_remove_echec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler, "end_task", lambda n: False)
    monkeypatch.setattr(scheduler, "delete_task", lambda n: False)
    res = runner.invoke(app, ["task", "remove"])
    assert res.exit_code == 1
    assert "Impossible" in res.stderr


@pytest.mark.parametrize(("cmd", "attr"), [("run", "run_task"), ("end", "end_task")])
def test_run_end(monkeypatch: pytest.MonkeyPatch, cmd: str, attr: str) -> None:
    seen: list[str] = []
    monkeypatch.setattr(scheduler, attr, lambda n: seen.append(n) or True)
    assert runner.invoke(app, ["task", cmd]).exit_code == 0
    assert seen == ["Deskgate"]
    monkeypatch.setattr(scheduler, attr, lambda n: False)
    res = runner.invoke(app, ["task", cmd])
    assert res.exit_code == 1
    assert "Planificateur" in res.stderr


def test_install_refuse_sous_deskgate_home(
    monkeypatch: pytest.MonkeyPatch, data_home: Path
) -> None:
    created: list[str] = []
    monkeypatch.setattr(installer, "create_task", lambda *a: created.append("x"))
    res = runner.invoke(app, ["task", "install", "--yes"])
    assert res.exit_code == 1
    assert "DESKGATE_HOME" in res.stderr
    assert created == []


def test_install_refus_interactif(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DESKGATE_HOME", raising=False)
    created: list[str] = []
    monkeypatch.setattr(installer, "create_task", lambda *a: created.append("x"))
    res = runner.invoke(app, ["task", "install"], input="n\n")
    assert res.exit_code == 0
    assert created == []
    assert "Installer la tâche" in res.stderr

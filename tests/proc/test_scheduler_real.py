"""Tâche réelle jetable du Planificateur : créée, lancée, relue puis supprimée."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest

from deskgate.scheduler import (
    SchedulerError,
    TaskSpec,
    build_task_xml,
    create_task,
    current_user,
    delete_task,
    launcher_command,
    parse_task_xml,
    query_task_xml,
    read_settings,
    run_task,
)

pytestmark = [pytest.mark.scheduler]


@pytest.mark.timeout(60)
def test_cycle_complet_tache_jetable(tmp_path: Path) -> None:
    nom = f"DeskgateTest-{uuid.uuid4().hex}"
    command = launcher_command()
    if not Path(command).exists():
        pytest.fail(f"pythonw.exe introuvable : {command}")
    marque = tmp_path / "marque.txt"
    spec = TaskSpec(
        user=current_user(),
        command=command,
        arguments=f"-c \"import pathlib; pathlib.Path(r'{marque}').write_text('ok')\"",
        working_dir=str(tmp_path),
    )
    try:
        create_task(nom, build_task_xml(spec), tmp_path)
        xml = query_task_xml(nom)
        assert xml is not None
        s = read_settings(parse_task_xml(xml))
        assert s.execution_time_limit == "PT0S"
        assert s.multiple_instances == "IgnoreNew"
        assert s.logon_type == "InteractiveToken"
        assert s.run_level == "LeastPrivilege"
        assert s.command == command
        assert run_task(nom) is True
        fin = time.monotonic() + 20
        while time.monotonic() < fin:
            if marque.exists() and marque.read_text() == "ok":
                break
            time.sleep(0.2)
        assert marque.read_text() == "ok"
    finally:
        delete_task(nom)
    assert query_task_xml(nom) is None


@pytest.mark.timeout(60)
def test_nom_inexistant() -> None:
    nom = f"DeskgateTest-{uuid.uuid4().hex}"
    assert query_task_xml(nom) is None
    assert delete_task(nom) is False


@pytest.mark.timeout(60)
def test_xml_invalide_leve_scheduler_error(tmp_path: Path) -> None:
    nom = f"DeskgateTest-{uuid.uuid4().hex}"
    try:
        with pytest.raises(SchedulerError) as exc:
            create_task(nom, b"pas du xml", tmp_path)
        assert "refusée" in exc.value.message
    finally:
        delete_task(nom)

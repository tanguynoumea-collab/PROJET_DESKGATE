"""Tests purs du XML de tâche du Planificateur et de sa relecture."""

from __future__ import annotations

import pytest

from deskgate.scheduler import (
    SERVE_ARGUMENTS,
    TaskSpec,
    audit_settings,
    build_task_xml,
    current_user,
    launcher_command,
    parse_task_xml,
    read_settings,
)

pytestmark = pytest.mark.unit

NORMALISE = (
    '<?xml version="1.0" encoding="UTF-16"?><Task version="1.4" '
    'xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
    r"<RegistrationInfo><URI>\Deskgate</URI></RegistrationInfo>"
    "<Triggers><LogonTrigger><UserId>S-1-5-21-1-2-3-1001</UserId></LogonTrigger></Triggers>"
    '<Principals><Principal id="Author"><UserId>S-1-5-21-1-2-3-1001</UserId>'
    "<LogonType>InteractiveToken</LogonType></Principal></Principals>"
    "<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>"
    "<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>"
    "<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>"
    "<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>"
    "<RestartOnFailure><Interval>PT1M</Interval><Count>3</Count></RestartOnFailure>"
    "<UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine></Settings>"
    '<Actions Context="Author"><Exec><Command>C:\\venv\\Scripts\\pythonw.exe</Command>'
    "<Arguments>-m deskgate serve</Arguments>"
    "<WorkingDirectory>C:\\Users\\moi\\AppData\\Local\\Deskgate</WorkingDirectory>"
    "</Exec></Actions></Task>"
)


def _spec(command: str = r"C:\venv\Scripts\pythonw.exe") -> TaskSpec:
    return TaskSpec(
        user="PC\\moi",
        command=command,
        arguments=SERVE_ARGUMENTS,
        working_dir=r"C:\Users\moi\AppData\Local\Deskgate",
    )


def _niveaux(xml: str) -> list[tuple[str, str]]:
    return audit_settings(read_settings(parse_task_xml(xml)))


def test_xml_commence_par_le_bom_utf16() -> None:
    data = build_task_xml(_spec())
    assert data.startswith(b"\xff\xfe")
    assert "LogonTrigger" in data.decode("utf-16")


def test_aller_retour_des_reglages() -> None:
    spec = _spec()
    s = read_settings(parse_task_xml(build_task_xml(spec).decode("utf-16")))
    assert s.logon_trigger is True
    assert s.user == spec.user
    assert s.logon_type == "InteractiveToken"
    assert s.run_level == "LeastPrivilege"
    assert s.execution_time_limit == "PT0S"
    assert s.disallow_on_batteries == "false"
    assert s.stop_on_batteries == "false"
    assert s.multiple_instances == "IgnoreNew"
    assert s.restart_interval == "PT1M"
    assert s.restart_count == "3"
    assert (s.command, s.arguments, s.working_dir) == (
        spec.command,
        spec.arguments,
        spec.working_dir,
    )
    assert audit_settings(s) == []


def test_chemin_avec_esperluette_et_accent() -> None:
    spec = _spec("C:/Dossier & é/pythonw.exe")
    s = read_settings(parse_task_xml(build_task_xml(spec).decode("utf-16")))
    assert s.command == "C:/Dossier & é/pythonw.exe"


def test_xml_normalise_est_conforme() -> None:
    s = read_settings(parse_task_xml(NORMALISE))
    assert s.run_level == "LeastPrivilege"
    assert [n for n, _ in audit_settings(s) if n == "echec"] == []


@pytest.mark.parametrize(
    ("ancien", "nouveau"),
    [
        ("<ExecutionTimeLimit>PT0S<", "<ExecutionTimeLimit>PT72H<"),
        ("<DisallowStartIfOnBatteries>false<", "<DisallowStartIfOnBatteries>true<"),
        ("<StopIfGoingOnBatteries>false<", "<StopIfGoingOnBatteries>true<"),
        ("<MultipleInstancesPolicy>IgnoreNew<", "<MultipleInstancesPolicy>Parallel<"),
        ("<LogonType>InteractiveToken<", "<LogonType>Password<"),
        ("</LogonType>", "</LogonType><RunLevel>HighestAvailable</RunLevel>"),
        ("LogonTrigger>", "TimeTrigger>"),
    ],
)
def test_audit_signale_les_ecarts(ancien: str, nouveau: str) -> None:
    modifie = NORMALISE.replace(ancien, nouveau)
    assert modifie != NORMALISE
    assert any(n == "echec" for n, _ in _niveaux(modifie))


def test_audit_sans_action_exec() -> None:
    modifie = NORMALISE.replace("Exec>", "Autre>")
    assert any(n == "echec" for n, _ in _niveaux(modifie))


def test_audit_avertit_sans_restart() -> None:
    modifie = NORMALISE.replace(
        "<RestartOnFailure><Interval>PT1M</Interval><Count>3</Count></RestartOnFailure>", ""
    )
    assert [n for n, _ in _niveaux(modifie)] == ["avertissement"]


def test_launcher_et_utilisateur() -> None:
    assert launcher_command(r"C:\venv\Scripts\python.exe") == r"C:\venv\Scripts\pythonw.exe"
    assert current_user({"USERDOMAIN": "PC", "USERNAME": "moi"}) == "PC\\moi"

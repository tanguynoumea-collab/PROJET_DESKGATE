"""Tâche du Planificateur Windows : XML, relecture tolérante et audit des réglages.

La tâche lance le runner à l'ouverture de session de l'utilisateur, sans élévation, sans limite de
durée et sur batterie (D-03). Le XML est construit par ElementTree, jamais par concaténation.
Aucune sortie texte de ``schtasks`` n'est analysée (elle est localisée) : seuls le code de retour
et le XML relu comptent.
"""

from __future__ import annotations

import getpass
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

TASK_NAME = "Deskgate"
TASK_NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"
SERVE_ARGUMENTS = "-m deskgate serve"
DESCRIPTION = "Runner Deskgate (passerelle n8n)"


class SchedulerError(Exception):
    """Échec d'une opération du Planificateur ; ``message`` est en français."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class TaskSpec:
    """Paramètres variables de la tâche."""

    user: str
    command: str
    arguments: str
    working_dir: str


def current_user(environ: Mapping[str, str] | None = None) -> str:
    """Utilisateur courant au format ``DOMAINE\\nom``."""
    env = os.environ if environ is None else environ
    domain = env.get("USERDOMAIN")
    name = env.get("USERNAME")
    if domain and name:
        return f"{domain}\\{name}"
    return getpass.getuser()


def launcher_command(executable: str | None = None) -> str:
    """``pythonw.exe`` voisin de l'interpréteur (pas de console)."""
    return str(Path(executable or sys.executable).with_name("pythonw.exe"))


def _q(tag: str) -> str:
    return f"{{{TASK_NS}}}{tag}"


def build_task_xml(spec: TaskSpec) -> bytes:
    """XML UTF-16 avec BOM de la tâche, conforme à D-03."""
    ET.register_namespace("", TASK_NS)
    root = ET.Element(_q("Task"), version="1.4")
    reg = ET.SubElement(root, _q("RegistrationInfo"))
    ET.SubElement(reg, _q("Description")).text = DESCRIPTION
    logon = ET.SubElement(ET.SubElement(root, _q("Triggers")), _q("LogonTrigger"))
    ET.SubElement(logon, _q("Enabled")).text = "true"
    ET.SubElement(logon, _q("UserId")).text = spec.user
    principal = ET.SubElement(ET.SubElement(root, _q("Principals")), _q("Principal"), id="Author")
    ET.SubElement(principal, _q("UserId")).text = spec.user
    ET.SubElement(principal, _q("LogonType")).text = "InteractiveToken"
    ET.SubElement(principal, _q("RunLevel")).text = "LeastPrivilege"
    settings = ET.SubElement(root, _q("Settings"))
    for tag, value in (
        ("MultipleInstancesPolicy", "IgnoreNew"),
        ("DisallowStartIfOnBatteries", "false"),
        ("StopIfGoingOnBatteries", "false"),
        ("AllowHardTerminate", "true"),
        ("StartWhenAvailable", "true"),
        ("RunOnlyIfNetworkAvailable", "false"),
        ("AllowStartOnDemand", "true"),
        ("Enabled", "true"),
        ("Hidden", "false"),
        ("ExecutionTimeLimit", "PT0S"),
        ("Priority", "7"),
    ):
        ET.SubElement(settings, _q(tag)).text = value
    restart = ET.SubElement(settings, _q("RestartOnFailure"))
    ET.SubElement(restart, _q("Interval")).text = "PT1M"
    ET.SubElement(restart, _q("Count")).text = "3"
    actions = ET.SubElement(root, _q("Actions"), Context="Author")
    exe = ET.SubElement(actions, _q("Exec"))
    ET.SubElement(exe, _q("Command")).text = spec.command
    ET.SubElement(exe, _q("Arguments")).text = spec.arguments
    ET.SubElement(exe, _q("WorkingDirectory")).text = spec.working_dir
    text = '<?xml version="1.0" encoding="UTF-16"?>\n' + ET.tostring(root, encoding="unicode")
    return text.encode("utf-16")


def parse_task_xml(xml_text: str) -> ET.Element:
    """Analyse le XML relu (la déclaration UTF-16 est fausse après décodage : retirée)."""
    cleaned = re.sub(r"^\s*<\?xml[^>]*\?>", "", xml_text.lstrip("﻿"))
    # XML produit par schtasks en local, pas d'entrée réseau.
    return ET.fromstring(cleaned)  # noqa: S314


@dataclass(frozen=True)
class TaskSettings:
    """Réglages relus d'une tâche, tolérants au XML normalisé par Windows."""

    logon_trigger: bool
    user: str | None
    logon_type: str | None
    run_level: str
    execution_time_limit: str | None
    disallow_on_batteries: str | None
    stop_on_batteries: str | None
    multiple_instances: str | None
    restart_interval: str | None
    restart_count: str | None
    command: str | None
    arguments: str | None
    working_dir: str | None


def _text(root: ET.Element, path: str) -> str | None:
    parts = "/".join(_q(p) for p in path.split("/"))
    node = root.find(f".//{parts}")
    return node.text if node is not None else None


def read_settings(root: ET.Element) -> TaskSettings:
    """Extrait les réglages utiles ; ``RunLevel`` absent vaut ``LeastPrivilege``."""
    return TaskSettings(
        logon_trigger=root.find(f".//{_q('LogonTrigger')}") is not None,
        user=_text(root, "Principal/UserId"),
        logon_type=_text(root, "Principal/LogonType"),
        run_level=_text(root, "Principal/RunLevel") or "LeastPrivilege",
        execution_time_limit=_text(root, "Settings/ExecutionTimeLimit"),
        disallow_on_batteries=_text(root, "Settings/DisallowStartIfOnBatteries"),
        stop_on_batteries=_text(root, "Settings/StopIfGoingOnBatteries"),
        multiple_instances=_text(root, "Settings/MultipleInstancesPolicy"),
        restart_interval=_text(root, "RestartOnFailure/Interval"),
        restart_count=_text(root, "RestartOnFailure/Count"),
        command=_text(root, "Exec/Command"),
        arguments=_text(root, "Exec/Arguments"),
        working_dir=_text(root, "Exec/WorkingDirectory"),
    )


def audit_settings(s: TaskSettings) -> list[tuple[str, str]]:
    """Écarts avec D-03 : liste de (niveau, message) ; vide si conforme."""
    out: list[tuple[str, str]] = []
    if not s.logon_trigger:
        out.append(("echec", "La tâche n'a pas de déclencheur à l'ouverture de session."))
    if s.logon_type != "InteractiveToken":
        out.append(
            ("echec", "La tâche ne s'exécute pas dans la session interactive de l'utilisateur.")
        )
    if s.run_level != "LeastPrivilege":
        out.append(("echec", "La tâche demande une élévation de privilèges."))
    if s.execution_time_limit != "PT0S":
        out.append(("echec", "La tâche a une limite de durée (attendu : aucune, PT0S)."))
    if s.disallow_on_batteries != "false":
        out.append(("echec", "La tâche ne démarre pas sur batterie."))
    if s.stop_on_batteries != "false":
        out.append(("echec", "La tâche s'arrête en passant sur batterie."))
    if s.multiple_instances not in (None, "IgnoreNew"):
        out.append(("echec", "La politique d'instances multiples n'est pas « IgnoreNew »."))
    if s.command is None:
        out.append(("echec", "La tâche n'a aucune action d'exécution."))
    if s.restart_interval is None:
        out.append(("avertissement", "Aucun redémarrage automatique sur échec n'est configuré."))
    return out

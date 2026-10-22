"""Tâche du Planificateur Windows : XML, relecture tolérante et audit des réglages.

La tâche lance le runner à l'ouverture de session de l'utilisateur, sans élévation, sans limite de
durée et sur batterie (D-03). Le XML est construit par ElementTree, jamais par concaténation.
Aucune sortie texte de ``schtasks`` n'est analysée (elle est localisée) : seuls le code de retour
et le XML relu comptent.
"""

from __future__ import annotations

import contextlib
import ctypes
import getpass
import os
import re
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

TASK_NAME = "Deskgate"
TASK_NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"
SERVE_ARGUMENTS = "-m deskgate serve"
DESCRIPTION = "Runner Deskgate (passerelle n8n)"

# --- Contexte empaqueté (MSIX) -------------------------------------------------------------
APPMODEL_ERROR_NO_PACKAGE = 15700
ERROR_INSUFFICIENT_BUFFER = 122


def package_full_name() -> str | None:
    """Nom complet du paquet du processus courant, ou ``None`` (pas d'identité, ou inconnu)."""
    try:
        from ctypes import wintypes

        func = ctypes.WinDLL("kernel32", use_last_error=True).GetCurrentPackageFullName  # type: ignore[attr-defined]
        func.argtypes = [ctypes.POINTER(wintypes.UINT), wintypes.LPWSTR]
        func.restype = wintypes.LONG
        length = wintypes.UINT(0)
        rc = func(ctypes.byref(length), None)
        if rc == APPMODEL_ERROR_NO_PACKAGE or rc != ERROR_INSUFFICIENT_BUFFER:
            return None
        buf = ctypes.create_unicode_buffer(length.value)
        if func(ctypes.byref(length), buf) != 0:
            return None
        return buf.value or None
    except (OSError, AttributeError):
        return None


def _write_bytes(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def probe_virtualized(
    local_appdata: Path, *, write: Callable[[Path, bytes], None] | None = None
) -> Path | None:
    """Sonde d'écriture : renvoie la copie redirigée sous Packages/*/LocalCache/Local, ou ``None``.

    Le marqueur et son éventuelle copie physique sont toujours supprimés.
    """
    name = f"deskgate-probe-{uuid.uuid4().hex}.tmp"
    marker = local_appdata / name
    found: list[Path] = []
    try:
        (write or _write_bytes)(marker, b"deskgate")
        found = list((local_appdata / "Packages").glob(f"*/LocalCache/Local/{name}"))
        return found[0] if found else None
    except OSError:
        return None
    finally:
        with contextlib.suppress(OSError):
            marker.unlink(missing_ok=True)
        for copy in found:
            with contextlib.suppress(OSError):
                copy.unlink(missing_ok=True)


def detect_packaged_context(
    environ: Mapping[str, str],
    *,
    identity: Callable[[], str | None] = package_full_name,
    probe: Callable[[Path], Path | None] = probe_virtualized,
) -> str | None:
    """Raison (français) de l'exécution dans un contexte empaqueté, ou ``None`` (D-14)."""
    name = identity()
    if name:
        return f"processus empaqueté (paquet {name})"
    local = environ.get("LOCALAPPDATA")
    if local:
        copy = probe(Path(local))
        if copy is not None:
            return f"écritures sous %LOCALAPPDATA% redirigées vers le paquet {copy.parents[2].name}"
    home = environ.get("DESKGATE_HOME", "").lower().replace("/", "\\")
    if "\\packages\\" in home and "\\localcache\\" in home:
        return "DESKGATE_HOME pointe dans le stockage d'une application empaquetée"
    return None


def packaged_context() -> str | None:
    """Détection sur le poste réel (``os.environ``)."""
    return detect_packaged_context(os.environ)


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


SCHTASKS = os.path.join(os.environ.get("SYSTEMROOT", r"C:\Windows"), "System32", "schtasks.exe")


def _oem_encoding() -> str:
    try:
        return f"cp{ctypes.windll.kernel32.GetOEMCP()}"  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return "cp850"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Appelle schtasks (liste d'arguments, exécutable absolu, sans shell)."""
    return subprocess.run(  # noqa: S603
        [SCHTASKS, *args],
        capture_output=True,
        text=True,
        encoding=_oem_encoding(),
        errors="replace",
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def create_task(name: str, xml: bytes, tmp_dir: Path) -> None:
    """Crée ou remplace la tâche ``name`` à partir du XML."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fichier = tmp_dir / f"tache-{uuid.uuid4().hex}.xml"
    fichier.write_bytes(xml)
    try:
        res = _run("/Create", "/XML", str(fichier), "/TN", name, "/F")
    finally:
        fichier.unlink(missing_ok=True)
    if res.returncode != 0:
        raise SchedulerError(
            f"Création de la tâche « {name} » refusée par le Planificateur (code {res.returncode})."
        )


def query_task_xml(name: str) -> str | None:
    """XML relu de la tâche, ou ``None`` si elle n'existe pas."""
    res = _run("/Query", "/TN", name, "/XML")
    return res.stdout if res.returncode == 0 else None


def run_task(name: str) -> bool:
    return _run("/Run", "/TN", name).returncode == 0


def end_task(name: str) -> bool:
    return _run("/End", "/TN", name).returncode == 0


def delete_task(name: str) -> bool:
    return _run("/Delete", "/TN", name, "/F").returncode == 0


# --- Dernier résultat de la tâche -----------------------------------------------------------

SCHED_S_TASK_RUNNING = 0x00041301
SCHED_S_TASK_HAS_NOT_RUN = 0x00041303
RESULT_VIRTUALIZED = 0x8007010B
POWERSHELL = os.path.join(
    os.environ.get("SYSTEMROOT", r"C:\Windows"),
    "System32",
    "WindowsPowerShell",
    "v1.0",
    "powershell.exe",
)
_TASK_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_RUNNER_EXIT = {
    2: "configuration invalide",
    3: "runner déjà en cours",
    4: "port indisponible",
    5: "base de données inaccessible",
    6: "thread engine ou sender en échec répété",
}


@dataclass(frozen=True)
class TaskResult:
    kind: Literal["ok", "running", "never", "virtualized", "runner_exit", "failure", "unreadable"]
    level: Literal["ok", "avertissement", "echec"]
    message: str


def last_task_result(name: str = TASK_NAME, *, timeout: float = 20.0) -> int | None:
    """Dernier résultat numérique de la tâche (Get-ScheduledTaskInfo, indépendant de la langue).

    Commande fixe : le nom passe par l'environnement de l'enfant, jamais par la ligne de commande.
    """
    if not _TASK_NAME_RE.fullmatch(name):
        return None
    argv = [
        POWERSHELL,
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "(Get-ScheduledTaskInfo -TaskName $env:DESKGATE_TASK_NAME).LastTaskResult",
    ]
    env = {**os.environ, "DESKGATE_TASK_NAME": name}
    try:
        res = subprocess.run(  # noqa: S603
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return int(res.stdout.strip()) & 0xFFFFFFFF
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None


def classify_task_result(code: int | None) -> TaskResult:
    """Classe un dernier résultat : « en cours », « jamais exécutée » et 0 ne sont pas des échecs."""
    if code is None:
        return TaskResult(
            "unreadable",
            "avertissement",
            "dernier résultat de la tâche illisible (PowerShell indisponible ou tâche absente)",
        )
    if code == 0:
        return TaskResult("ok", "ok", "dernière exécution réussie")
    if code == SCHED_S_TASK_RUNNING:
        return TaskResult("running", "ok", "tâche en cours")
    if code == SCHED_S_TASK_HAS_NOT_RUN:
        return TaskResult("never", "ok", "tâche jamais exécutée")
    if code == RESULT_VIRTUALIZED:
        return TaskResult(
            "virtualized",
            "echec",
            "dernier résultat 0x8007010B : dossier de travail introuvable pour le Planificateur, "
            "cause probable une installation virtualisée par une application MSIX ; refaire "
            "`deskgate init` depuis un terminal normal (AGENTS.md, « Terminal normal obligatoire »)",
        )
    if code in _RUNNER_EXIT:
        return TaskResult(
            "runner_exit",
            "avertissement",
            f"le runner est sorti avec le code {code} ({_RUNNER_EXIT[code]}) ; "
            "voir logs\startup.log et logs\runner.log",
        )
    return TaskResult("failure", "avertissement", f"dernier résultat 0x{code:08X}")

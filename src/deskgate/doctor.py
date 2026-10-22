"""Diagnostic de l'installation : `deskgate doctor` (D-04).

Chaque vérification renvoie un niveau et un message français ; aucune ne modifie le poste.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from deskgate import scheduler
from deskgate.core.config import ConfigError, RunnerConfig, load_config
from deskgate.installer import SHARE_DIRS, ZERO_HASH
from deskgate.locations import config_path
from deskgate.scheduler import (
    SERVE_ARGUMENTS,
    TASK_NAME,
    audit_settings,
    parse_task_xml,
    read_settings,
)

Level = Literal["ok", "avertissement", "echec"]


@dataclass(frozen=True)
class Check:
    name: str
    level: Level
    message: str


_CONSOLE_HINT = (
    " (un runner lancé par la tâche n'affiche pas cette erreur : "
    "lancez `deskgate serve` en console pour la voir)"
)


def check_config(path: Path) -> tuple[Check, RunnerConfig | None]:
    try:
        cfg = load_config(path)
    except ConfigError as exc:
        return Check("Configuration", "echec", f"{exc.message}{_CONSOLE_HINT}"), None
    return Check("Configuration", "ok", f"{path} valide"), cfg


def check_dirs(cfg: RunnerConfig, home: Path) -> list[Check]:
    wanted: list[Path] = [Path(r) for r in cfg.paths.allowed_roots]
    if cfg.paths.allowed_roots:
        first = Path(cfg.paths.allowed_roots[0])
        wanted += [first / name for name in SHARE_DIRS if name != "travail"]
    wanted += [Path(cfg.effective_work_root()), home]
    seen: set[str] = set()
    missing: list[Check] = []
    for directory in wanted:
        key = str(directory)
        if key in seen:
            continue
        seen.add(key)
        if not directory.is_dir():
            missing.append(
                Check(
                    "Dossiers", "echec", f"dossier manquant : {directory} (lancez `deskgate init`)"
                )
            )
    return missing or [Check("Dossiers", "ok", "tous les dossiers existent")]


def check_token(cfg: RunnerConfig) -> Check:
    if cfg.token_sha256 == ZERO_HASH:
        return Check(
            "Jeton",
            "echec",
            "l'empreinte du jeton est celle du gabarit : lancez `deskgate init --force`",
        )
    return Check("Jeton", "ok", "empreinte de jeton définie")


def check_port(cfg: RunnerConfig, *, timeout: float = 2.0) -> Check:
    url = f"http://{cfg.host}:{cfg.port}/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = json.loads(resp.read(65536))
            if resp.status == 200 and body.get("status") == "ok":
                return Check("Port", "ok", f"runner joignable (version {body.get('version', '?')})")
    except (OSError, TimeoutError, ValueError, AttributeError):
        pass
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)  # type: ignore[attr-defined]
        sock.bind((cfg.host, cfg.port))
    except OSError:
        return Check("Port", "echec", f"port {cfg.port} occupé par un autre programme")
    finally:
        sock.close()
    return Check("Port", "ok", f"port {cfg.port} libre (runner arrêté)")


def check_plugins(cfg: RunnerConfig) -> list[Check]:
    checks: list[Check] = []
    for ident, cap in cfg.capabilities.items():
        if cap.kind == "python" and cap.python and not Path(cap.python).is_file():
            checks.append(
                Check("Plugins", "echec", f"{ident} : interpréteur absent ({cap.python})")
            )
        if cap.kind == "python":
            for key in cap.required_files:
                value = str(cap.settings[key])
                if not Path(value).is_file():
                    checks.append(Check("Plugins", "echec", f"{ident} : {key} absent ({value})"))
    for ident, server in cfg.mcp_servers.items():
        if not Path(server.command).is_file():
            checks.append(
                Check(
                    "Plugins",
                    "echec",
                    f"serveur MCP {ident} : exécutable absent ({server.command})",
                )
            )
    if checks:
        return checks
    if not cfg.capabilities:
        return [Check("Plugins", "avertissement", "aucune capacité déclarée")]
    return [Check("Plugins", "ok", "environnements de plugins présents")]


def check_home_env(environ: Mapping[str, str] | None = None) -> Check:
    env = os.environ if environ is None else environ
    if "DESKGATE_HOME" in env:
        return Check(
            "Environnement",
            "avertissement",
            "DESKGATE_HOME est défini : la tâche planifiée ne le transmet pas au runner",
        )
    return Check("Environnement", "ok", "DESKGATE_HOME non défini")


def check_task(
    query: Callable[[str], str | None] | None = None,
    result: Callable[[str], int | None] | None = None,
) -> list[Check]:
    xml = (query or scheduler.query_task_xml)(TASK_NAME)
    if xml is None:
        return [Check("Tâche", "echec", "absente (deskgate task install)")]
    s = read_settings(parse_task_xml(xml))
    checks = [Check("Tâche", level, msg) for level, msg in audit_settings(s)]  # type: ignore[arg-type]
    if s.command is not None:
        if not Path(s.command).is_file():
            checks.append(
                Check("Tâche", "echec", f"commande introuvable sur le disque : {s.command}")
            )
        elif Path(s.command).name.lower() != "pythonw.exe":
            checks.append(
                Check(
                    "Tâche", "avertissement", "la commande n'est pas pythonw.exe : console visible"
                )
            )
    if s.arguments != SERVE_ARGUMENTS:
        checks.append(
            Check(
                "Tâche",
                "echec",
                f"arguments inattendus : {s.arguments!r} (attendu {SERVE_ARGUMENTS!r})",
            )
        )
    outcome = scheduler.classify_task_result((result or scheduler.last_task_result)(TASK_NAME))
    if outcome.level != "ok":
        checks.append(Check("Tâche", outcome.level, outcome.message))
    if not checks:
        return [Check("Tâche", "ok", f"conforme ({s.command} {s.arguments})")]
    return checks


def check_context(detect: Callable[[], str | None] | None = None) -> Check:
    reason = (detect or scheduler.packaged_context)()
    if reason:
        return Check(
            "Contexte d'exécution",
            "echec",
            f"{reason} : installation et diagnostic faussés ; relancez depuis un terminal normal "
            "(AGENTS.md, « Terminal normal obligatoire »)",
        )
    return Check("Contexte d'exécution", "ok", "processus non empaqueté")


def run_all(
    home: Path, config_override: Path | None = None, *, with_task: bool = True
) -> list[Check]:
    checks = [check_context(), check_home_env()]
    cfg_check, cfg = check_config(config_path(home, config_override))
    checks.append(cfg_check)
    if cfg is None:
        return checks
    checks += check_dirs(cfg, home)
    checks.append(check_token(cfg))
    if with_task:
        checks += check_task()
    checks.append(check_port(cfg))
    checks += check_plugins(cfg)
    return checks


def exit_code(checks: list[Check]) -> int:
    return 1 if any(c.level == "echec" for c in checks) else 0

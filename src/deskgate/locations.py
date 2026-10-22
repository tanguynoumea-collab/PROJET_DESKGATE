"""Emplacements des données (D-01). Aucune création de dossier ici.

Seul le journal de démarrage (`logs/startup.log`) est écrit avant le mutex, par
`runtime.attach_startup_log`.

Priorité du fichier de configuration : `--config` > `DESKGATE_HOME` > dossier par défaut.
La base suit toujours `resolve_home()`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

import platformdirs


def default_home() -> Path:
    # appauthor=False : sinon platformdirs ajoute un second niveau « Deskgate\Deskgate ».
    return Path(platformdirs.user_data_dir("Deskgate", appauthor=False, roaming=False))


def resolve_home(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    override = env.get("DESKGATE_HOME")
    return Path(override) if override else default_home()


def config_path(home: Path, override: Path | None = None) -> Path:
    return override if override is not None else home / "runner.toml"


def db_path(home: Path) -> Path:
    return home / "deskgate.db"


def logs_dir(home: Path) -> Path:
    return home / "logs"


def log_path(home: Path) -> Path:
    return logs_dir(home) / "runner.log"


def startup_log_path(home: Path) -> Path:
    return logs_dir(home) / "startup.log"

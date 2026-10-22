"""Installation de Deskgate : configuration initiale et tâche du Planificateur (D-02, D-03).

Aucune dépendance à Typer : la logique reste testable, la CLI ne fait que l'afficher.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from importlib import resources
from pathlib import Path

from deskgate import scheduler
from deskgate.core.config import ConfigError, load_config
from deskgate.core.paths import PathDenied, normalize_host_path
from deskgate.core.tokens import generate_token, hash_token
from deskgate.locations import config_path, logs_dir
from deskgate.scheduler import (
    SERVE_ARGUMENTS,
    TASK_NAME,
    TaskSpec,
    audit_settings,
    build_task_xml,
    create_task,
    current_user,
    launcher_command,
    parse_task_xml,
    query_task_xml,
    read_settings,
)

DEFAULT_ROOT = "C:/BIM"
SHARE_DIRS = ("depot", "travail", "livrables")
ZERO_HASH = "0" * 64


PACKAGED_MESSAGE = (
    "Contexte empaqueté détecté ({reason}) : {command} écrirait dans un stockage virtualisé "
    "que la tâche planifiée ne voit pas. Relancez-le depuis un terminal normal (PowerShell ou "
    "Terminal Windows ouvert hors de toute application MSIX) : voir "
    "« Terminal normal obligatoire » dans AGENTS.md. Rien n'a été écrit."
)


class InitError(Exception):
    """Échec de l'installation ; ``message`` est en français."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def load_template() -> str:
    return (resources.files("deskgate") / "runner.example.toml").read_text(encoding="utf-8")


def refuse_if_packaged(
    detect: Callable[[], str | None] | None = None, *, command: str = "deskgate init"
) -> None:
    """D-15 : refus avant toute écriture ; aucun contournement (--force ne change rien).

    Utilisé par init et task install.
    """
    reason = (detect or scheduler.packaged_context)()
    if reason:
        raise InitError(PACKAGED_MESSAGE.format(reason=reason, command=command))


def normalize_root(raw: str) -> str:
    if raw.startswith(("//", "\\\\")):
        raise InitError(
            "Racine réseau (UNC) refusée : utilisez un dossier local, par exemple C:/BIM."
        )
    try:
        return normalize_host_path(raw)
    except PathDenied as exc:
        raise InitError(exc.message) from exc


def _replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise InitError(f"Gabarit inattendu : la ligne {old!r} doit apparaître une seule fois.")
    return text.replace(old, new)


def render_config(template: str, *, token_sha256: str, root: str) -> str:
    text = _replace_once(
        template, f'token_sha256 = "{ZERO_HASH}"', f'token_sha256 = "{token_sha256}"'
    )
    if root != DEFAULT_ROOT:
        text = _replace_once(
            text, f"allowed_roots = ['{DEFAULT_ROOT}']", f"allowed_roots = ['{root}']"
        )
        text = _replace_once(text, f"host = '{DEFAULT_ROOT}'", f"host = '{root}'")
    return text


@dataclass
class InitResult:
    config_path: Path
    written: bool
    backup: Path | None = None
    token: str | None = None
    created: list[Path] = field(default_factory=list)


def ensure_dirs(home: Path, root: str) -> list[Path]:
    wanted = [Path(root) / name for name in SHARE_DIRS] + [logs_dir(home), home / "plugins"]
    created: list[Path] = []
    for directory in wanted:
        if not directory.exists():
            created.append(directory)
        directory.mkdir(parents=True, exist_ok=True)
    return created


def init_config(home: Path, root: str, *, force: bool, now: datetime) -> InitResult:
    path = config_path(home)
    home.mkdir(parents=True, exist_ok=True)
    created = ensure_dirs(home, root)
    if path.exists() and not force:
        return InitResult(config_path=path, written=False, created=created)
    backup: Path | None = None
    if path.exists():
        backup = path.with_name(f"{path.name}.bak-{now:%Y%m%d-%H%M%S}")
        shutil.copy2(path, backup)
    token = generate_token()
    text = render_config(load_template(), token_sha256=hash_token(token), root=root)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    try:
        load_config(path)
    except ConfigError as exc:
        raise InitError(f"Configuration écrite invalide : {exc.message}") from exc
    return InitResult(config_path=path, written=True, backup=backup, token=token, created=created)


def task_spec(home: Path) -> TaskSpec:
    command = launcher_command()
    if not Path(command).exists():
        raise InitError(f"pythonw.exe introuvable à côté de l'interpréteur : {command}")
    return TaskSpec(
        user=current_user(),
        command=command,
        arguments=SERVE_ARGUMENTS,
        working_dir=str(home),
    )


def install_task(home: Path) -> str:
    spec = task_spec(home)
    existing = query_task_xml(TASK_NAME)
    if existing is not None:
        settings = read_settings(parse_task_xml(existing))
        failures = [m for level, m in audit_settings(settings) if level == "echec"]
        if (
            not failures
            and settings.command == spec.command
            and settings.arguments == spec.arguments
        ):
            return "conforme"
    create_task(TASK_NAME, build_task_xml(spec), home)
    return "installee"

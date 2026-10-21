"""Ligne de commande `deskgate` (Typer)."""

from __future__ import annotations

import io
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from deskgate import __version__, installer, runtime
from deskgate.core.tokens import generate_token, hash_token
from deskgate.locations import resolve_home
from deskgate.scheduler import SchedulerError

# cp1252 par défaut sous Windows ; sous pythonw le flux vaut None (isinstance l'écarte).
for _stream in (sys.stdout, sys.stderr):
    if isinstance(_stream, io.TextIOWrapper):
        _stream.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Deskgate : passerelle locale entre n8n et le poste Windows.",
)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"deskgate {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version,
            is_eager=True,
            help="Affiche la version et quitte.",
        ),
    ] = False,
) -> None:
    """Deskgate : passerelle locale entre n8n et le poste Windows."""


@app.command()
def serve(
    config: Annotated[Path | None, typer.Option("--config", help="Chemin de runner.toml")] = None,
) -> None:
    """Démarre le runner."""
    runtime.configure_logging()
    raise typer.Exit(code=runtime.serve(config))


@app.command("dev-token", hidden=True)
def dev_token() -> None:
    """Génère un jeton de développement et son empreinte."""
    token = generate_token()
    typer.echo(token)
    typer.echo(f'token_sha256 = "{hash_token(token)}"')
    typer.echo(
        "Copiez la seconde ligne dans runner.toml ; le jeton n'est affiché qu'une fois "
        "et n'est écrit nulle part.",
        err=True,
    )


def _err(message: str) -> None:
    typer.echo(message, err=True)


def _confirm_task(yes: bool) -> bool:
    """Garde DESKGATE_HOME puis accord de l'utilisateur pour installer la tâche."""
    if "DESKGATE_HOME" in os.environ:
        _err(
            "DESKGATE_HOME est défini : la tâche planifiée ne le transmettrait pas au runner. "
            "Tâche non installée."
        )
        raise typer.Exit(1)
    return yes or typer.confirm(
        "Installer la tâche du Planificateur « Deskgate » (démarrage à l'ouverture de session) ?",
        default=False,
        err=True,
    )


@app.command()
def init(
    root: Annotated[
        str, typer.Option("--root", help="Racine locale des dossiers de travail.")
    ] = installer.DEFAULT_ROOT,
    force: Annotated[
        bool, typer.Option("--force", help="Sauvegarde runner.toml puis le réécrit.")
    ] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Installe la tâche sans poser la question.")
    ] = False,
    no_task: Annotated[
        bool, typer.Option("--no-task", help="N'installe pas la tâche du Planificateur.")
    ] = False,
) -> None:
    """Crée la configuration, les dossiers, le jeton et (avec accord) la tâche planifiée."""
    home = resolve_home()
    try:
        normalized = installer.normalize_root(root)
        result = installer.init_config(home, normalized, force=force, now=datetime.now())
    except installer.InitError as exc:
        _err(exc.message)
        raise typer.Exit(2) from exc
    if result.token:
        typer.echo(result.token)
        _err(
            "Jeton affiché une seule fois : copiez-le dans l'identifiant n8n « Deskgate » "
            "(en-tête Authorization: Bearer <jeton>). Il n'est écrit nulle part."
        )
        if result.backup:
            _err(f"Ancienne configuration sauvegardée : {result.backup}")
    else:
        _err(
            "runner.toml existe déjà : configuration conservée, aucun nouveau jeton "
            "(l'ancien ne peut pas être réaffiché ; --force pour régénérer)."
        )
    _err(f"Fichier de configuration : {result.config_path}")
    for directory in result.created:
        _err(f"Dossier créé : {directory}")
    if no_task:
        _err("Tâche du Planificateur ignorée (--no-task).")
        return
    try:
        if not _confirm_task(yes):
            _err("Tâche non installée (deskgate task install pour l'ajouter plus tard).")
            return
        outcome = installer.install_task(home)
    except (installer.InitError, SchedulerError) as exc:
        _err(exc.message)
        raise typer.Exit(2) from exc
    _err(
        "Tâche « Deskgate » déjà conforme."
        if outcome == "conforme"
        else "Tâche « Deskgate » installée."
    )

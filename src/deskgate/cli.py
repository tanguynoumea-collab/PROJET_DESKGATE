"""Ligne de commande `deskgate` (Typer)."""

from __future__ import annotations

import io
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

from deskgate import __version__, installer, runtime, scheduler, store
from deskgate import doctor as doctor_mod
from deskgate.core.tokens import generate_token, hash_token
from deskgate.locations import db_path, resolve_home
from deskgate.scheduler import TASK_NAME, SchedulerError

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


@app.command()
def doctor(
    config: Annotated[Path | None, typer.Option("--config", help="Chemin de runner.toml")] = None,
) -> None:
    """Vérifie l'installation (configuration, dossiers, jeton, tâche, port, plugins)."""
    checks = doctor_mod.run_all(resolve_home(), config)
    for check in checks:
        label = "échec" if check.level == "echec" else check.level
        typer.echo(f"[{label}] {check.name} : {check.message}")
    raise typer.Exit(doctor_mod.exit_code(checks))


@app.command()
def purge(
    older_than_days: Annotated[
        int,
        typer.Option(
            "--older-than-days",
            min=0,
            help="Purge data des tâches terminées depuis plus de N jours (rappel final).",
        ),
    ] = 30,
) -> None:
    """Retire `data` des tâches terminées dont le rappel est final (summary conservé)."""
    path = db_path(resolve_home())
    if not path.is_file():
        _err(f"Base introuvable : {path}. Rien à purger.")
        raise typer.Exit(1)
    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
    conn = store.connect(path)
    try:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if version > store.SCHEMA_VERSION:
            _err(str(store.SchemaTooNew(version)))
            raise typer.Exit(2)
        if version == 0:
            _err("Base non initialisée : lancez une fois `deskgate serve`. Rien à purger.")
            raise typer.Exit(2)
        count = store.purge_data(conn, older_than=cutoff)
    except store.OperationalError as exc:
        _err(
            f"Base occupée ou illisible ({type(exc).__name__}) : réessayez dans quelques secondes."
        )
        raise typer.Exit(1) from exc
    finally:
        conn.close()
    typer.echo(
        f"{count} tâche(s) purgée(s) : data des tâches terminées avant le "
        f"{cutoff:%Y-%m-%d %H:%M} UTC, rappel final. Le fichier de base ne rétrécit pas."
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
        installer.refuse_if_packaged()
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
        installer.refuse_if_packaged(command="deskgate task install")
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


task_app = typer.Typer(
    no_args_is_help=True,
    help="Tâche du Planificateur « Deskgate » (démarrage à l'ouverture de session).",
)
app.add_typer(task_app, name="task")


@task_app.command("install")
def task_install(
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Installe sans poser la question.")
    ] = False,
) -> None:
    """Installe (ou vérifie) la tâche du Planificateur."""
    try:
        installer.refuse_if_packaged(command="deskgate task install")
        if not _confirm_task(yes):
            _err("Tâche non installée.")
            return
        outcome = installer.install_task(resolve_home())
    except (installer.InitError, SchedulerError) as exc:
        _err(exc.message)
        raise typer.Exit(2) from exc
    typer.echo("Tâche déjà conforme." if outcome == "conforme" else "Tâche installée.")


@task_app.command("remove")
def task_remove() -> None:
    """Arrête puis supprime la tâche ; les données sont conservées."""
    try:
        scheduler.end_task(TASK_NAME)
        deleted = scheduler.delete_task(TASK_NAME)
    except SchedulerError as exc:
        _err(exc.message)
        raise typer.Exit(2) from exc
    if not deleted:
        _err("Impossible de supprimer la tâche « Deskgate » (absente ou refusée).")
        raise typer.Exit(1)
    typer.echo("Tâche supprimée. C:\\BIM, la configuration et la base sont conservés.")


@task_app.command("status")
def task_status() -> None:
    """Relit la tâche et vérifie ses réglages."""
    try:
        xml = scheduler.query_task_xml(TASK_NAME)
    except SchedulerError as exc:
        _err(exc.message)
        raise typer.Exit(2) from exc
    if xml is None:
        typer.echo("Tâche « Deskgate » absente (deskgate task install).")
        raise typer.Exit(1)
    settings = scheduler.read_settings(scheduler.parse_task_xml(xml))
    findings = scheduler.audit_settings(settings)
    for level, message in findings:
        label = "echec" if level == "echec" else "avertissement"
        typer.echo(f"[{label}] {message}")
    typer.echo(f"Commande : {settings.command} {settings.arguments}")
    failed = any(level == "echec" for level, _ in findings)
    if failed:
        raise typer.Exit(1)
    typer.echo("Tâche conforme.")


@task_app.command("run")
def task_run() -> None:
    """Démarre le runner par le Planificateur."""
    if not scheduler.run_task(TASK_NAME):
        _err("Le Planificateur n'a pas pu démarrer la tâche « Deskgate ».")
        raise typer.Exit(1)
    typer.echo("Runner démarré par le Planificateur.")


@task_app.command("end")
def task_end() -> None:
    """Arrête la tâche en cours."""
    if not scheduler.end_task(TASK_NAME):
        _err("Le Planificateur n'a pas pu arrêter la tâche « Deskgate » (déjà arrêtée ?).")
        raise typer.Exit(1)
    typer.echo("Tâche arrêtée.")

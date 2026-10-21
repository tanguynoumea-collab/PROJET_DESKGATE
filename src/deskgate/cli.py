"""Ligne de commande `deskgate` (Typer)."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Annotated

import typer

from deskgate import __version__, runtime
from deskgate.core.tokens import generate_token, hash_token

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

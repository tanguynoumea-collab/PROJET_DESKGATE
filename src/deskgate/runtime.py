"""Démarrage du runner dans l'ordre strict D-04, hors `lifespan` (D-03).

Configuration, puis mutex, puis socket exclusif, puis base, puis Uvicorn.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import uvicorn

from deskgate import __version__
from deskgate.api import create_app
from deskgate.core.config import ConfigError, load_config
from deskgate.instance import (
    acquire_mutex,
    bind_exclusive,
    describe_bind_error,
    instance_name_from_env,
)
from deskgate.locations import config_path, db_path, resolve_home
from deskgate.store import open_db

EXIT_INVALID_CONFIG = 2
EXIT_ALREADY_RUNNING = 3
EXIT_BIND_FAILED = 4

logger = logging.getLogger("deskgate")


def configure_logging() -> None:
    """Journal sur stderr ; ne journalise jamais d'en-tête ni de jeton."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s : %(message)s"))
    logger.handlers[:] = [handler]
    logger.setLevel(logging.INFO)


def _err(message: str) -> None:
    if sys.stderr is not None:
        print(message, file=sys.stderr)


def serve(config_override: Path | None = None) -> int:
    """Lance le runner ; renvoie le code de sortie du processus."""
    home = resolve_home()
    try:
        cfg = load_config(config_path(home, config_override))
    except ConfigError as exc:
        _err(exc.message)
        return EXIT_INVALID_CONFIG

    name = instance_name_from_env()
    if acquire_mutex(name) is None:
        _err(
            f"Un runner Deskgate est déjà en cours d'exécution ({name}) : "
            "arrêt sans toucher à la base."
        )
        return EXIT_ALREADY_RUNNING

    try:
        sock = bind_exclusive(cfg.host, cfg.port)
    except OSError as exc:
        _err(describe_bind_error(exc, cfg.host, cfg.port))
        return EXIT_BIND_FAILED

    conn = open_db(db_path(home))
    # phase 2 : recovery, engine, sender
    try:
        warnings = cfg.listen_warnings()
        app = create_app(token_sha256=cfg.token_sha256, version=__version__, warnings=warnings)
        if warnings:
            logger.warning(
                "Attention : écoute sur une interface non locale (%s:%s), "
                "activée par allow_non_loopback.",
                cfg.host,
                cfg.port,
            )
        logger.info("Écoute sur http://%s:%s", cfg.host, sock.getsockname()[1])
        server = uvicorn.Server(uvicorn.Config(app, log_config=None, lifespan="on"))
        server.run(sockets=[sock])
    finally:
        conn.close()
    return 0

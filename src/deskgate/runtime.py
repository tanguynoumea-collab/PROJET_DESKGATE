"""Démarrage du runner dans l'ordre strict D-04, hors `lifespan` (D-03).

Configuration, puis mutex, puis socket exclusif, puis base, puis Uvicorn.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

import uvicorn

import deskgate_sdk.run
from deskgate import __version__
from deskgate.api import create_app
from deskgate.core.config import ConfigError, load_config
from deskgate.core.redact import RedactingFilter, RedactingFormatter
from deskgate.engine import Engine
from deskgate.instance import (
    acquire_mutex,
    bind_exclusive,
    describe_bind_error,
    instance_name_from_env,
)
from deskgate.jobs import JobsService
from deskgate.locations import config_path, db_path, log_path, logs_dir, resolve_home
from deskgate.sender import Sender
from deskgate.store import SchemaTooNew, open_db, recover_interrupted

EXIT_INVALID_CONFIG = 2
EXIT_ALREADY_RUNNING = 3
EXIT_BIND_FAILED = 4
EXIT_DB_ERROR = 5

LOG_MAX_BYTES = 2 * 1024 * 1024
LOG_BACKUPS = 5
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s : %(message)s"

logger = logging.getLogger("deskgate")


def configure_logging() -> None:
    """Journal sur stderr, signature masquée sur tous les handlers (D-07, SEC-05)."""
    handlers: list[logging.Handler] = []
    if sys.stderr is not None:  # pythonw : pas de flux, le journal fichier prend le relais
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(RedactingFormatter(LOG_FORMAT))
        handler.addFilter(RedactingFilter())
        handlers.append(handler)
    logger.handlers[:] = handlers
    logger.setLevel(logging.INFO)
    logger.propagate = False
    root = logging.getLogger()
    root.handlers[:] = handlers
    root.setLevel(logging.WARNING)
    third = logging.WARNING
    level = os.environ.get("DESKGATE_LOG_LEVEL", "").upper()
    if level in ("DEBUG", "INFO", "WARNING"):
        root.setLevel(level)
        third = getattr(logging, level)
    for name in ("httpx2", "httpcore2"):
        logging.getLogger(name).setLevel(third)


def attach_file_log(home: Path) -> Path:
    """Ajoute le journal fichier rotatif (appelé après le mutex), signature masquée."""
    logs_dir(home).mkdir(parents=True, exist_ok=True)
    path = log_path(home)
    handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUPS, encoding="utf-8"
    )
    handler.setFormatter(RedactingFormatter(LOG_FORMAT))
    handler.addFilter(RedactingFilter())
    logger.addHandler(handler)
    logging.getLogger().addHandler(handler)
    return path


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
        path = attach_file_log(home)
    except OSError as exc:
        path = None
        _err(f"Journal fichier indisponible : {exc}")
    logger.info("Runner Deskgate %s démarré (pid %d), journal : %s", __version__, os.getpid(), path)

    try:
        sock = bind_exclusive(cfg.host, cfg.port)
    except OSError as exc:
        _err(describe_bind_error(exc, cfg.host, cfg.port))
        return EXIT_BIND_FAILED

    try:
        conn = open_db(db_path(home))  # migration
    except SchemaTooNew as exc:
        _err(str(exc))
        return EXIT_DB_ERROR
    try:
        ids = recover_interrupted(conn)  # running -> interrupted + rappels pending + audit
    finally:
        conn.close()
    if ids:
        logger.warning("%d tâche(s) interrompue(s) par l'arrêt précédent du runner.", len(ids))

    warnings = cfg.listen_warnings()
    engine = Engine(
        db_path=db_path(home),
        config=cfg,
        worker_script=Path(deskgate_sdk.run.__file__).resolve(),
    )
    jobs = JobsService(db_path=db_path(home), config=cfg, wake=engine.wake)
    sender = Sender(db_path=db_path(home), config=cfg)

    def _shutdown() -> None:
        engine.stop()
        sender.stop()

    app = create_app(
        token_sha256=cfg.token_sha256,
        version=__version__,
        warnings=warnings,
        jobs=jobs,
        on_shutdown=_shutdown,
    )
    if warnings:
        logger.warning(
            "Attention : écoute sur une interface non locale (%s:%s), "
            "activée par allow_non_loopback.",
            cfg.host,
            cfg.port,
        )
    logger.info("Écoute sur http://%s:%s", cfg.host, sock.getsockname()[1])
    server = uvicorn.Server(uvicorn.Config(app, log_config=None, lifespan="on"))
    # Le Planificateur relancera le runner ; la recovery rend l'arrêt sûr.
    engine.on_fatal = lambda: setattr(server, "should_exit", True)
    sender.on_fatal = lambda: setattr(server, "should_exit", True)
    engine.start()
    sender.start()
    try:
        server.run(sockets=[sock])
    finally:
        engine.stop()
        sender.stop()  # KeyboardInterrupt ; la voie CTRL_BREAK passe par le lifespan
    return 0

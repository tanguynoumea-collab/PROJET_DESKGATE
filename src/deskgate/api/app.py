"""Fabrique de l'application FastAPI (sans dépendance à la configuration)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI

from deskgate.api.handlers import install_handlers
from deskgate.api.middleware import BearerAuthMiddleware, HostCheckMiddleware
from deskgate.api.routes_health import router as health_router
from deskgate.api.routes_jobs import router as jobs_router
from deskgate.jobs import JobsService


def create_app(
    *,
    token_sha256: str,
    version: str,
    warnings: Sequence[str] = (),
    jobs: JobsService | None = None,
    on_shutdown: Callable[[], None] | None = None,
) -> FastAPI:
    """Construit l'application : Host contrôlé, puis jeton, puis routage."""

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        # Seule voie exécutée à l'arrêt propre (CTRL_BREAK) : arrêt de l'engine.
        if on_shutdown is not None:
            on_shutdown()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.version = version
    app.state.warnings = tuple(warnings)
    install_handlers(app)
    app.include_router(health_router)
    if jobs is not None:
        app.state.jobs = jobs
        app.include_router(jobs_router)
    # Le dernier middleware ajouté est le plus externe : Host s'exécute avant l'authentification.
    app.add_middleware(BearerAuthMiddleware, token_sha256=token_sha256)
    app.add_middleware(HostCheckMiddleware)
    return app

"""Fabrique de l'application FastAPI (sans dépendance à la configuration)."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import FastAPI

from deskgate.api.handlers import install_handlers
from deskgate.api.middleware import BearerAuthMiddleware, HostCheckMiddleware
from deskgate.api.routes_health import router as health_router


def create_app(*, token_sha256: str, version: str, warnings: Sequence[str] = ()) -> FastAPI:
    """Construit l'application : Host contrôlé, puis jeton, puis routage."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.version = version
    app.state.warnings = tuple(warnings)
    install_handlers(app)
    app.include_router(health_router)
    # Le dernier middleware ajouté est le plus externe : Host s'exécute avant l'authentification.
    app.add_middleware(BearerAuthMiddleware, token_sha256=token_sha256)
    app.add_middleware(HostCheckMiddleware)
    return app

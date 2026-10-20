"""Middlewares ASGI purs : contrôle du Host puis jeton Bearer.

Pas de `BaseHTTPMiddleware` ni de `TrustedHostMiddleware` (réponse texte brut, hors D-08),
pas de dépendance FastAPI (elle ne protégerait pas les routes inconnues).
L'en-tête Authorization et le jeton ne sont jamais journalisés.
"""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from deskgate.core.errors import HOST_NOT_ALLOWED, HTTP_MESSAGES_FR, UNAUTHORIZED, error_body
from deskgate.core.hostcheck import is_allowed_host
from deskgate.core.tokens import verify_token


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope["headers"]:
        if key.lower() == name:
            return value.decode("latin-1")
    return None


class HostCheckMiddleware:
    """Refuse (400) toute requête dont l'en-tête Host n'est pas autorisé."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if not is_allowed_host(_header(scope, b"host")):
            response = JSONResponse(
                error_body(HOST_NOT_ALLOWED, "En-tête Host non autorisé."), status_code=400
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class BearerAuthMiddleware:
    """Exige un jeton Bearer valide sur toute route sauf `/health`."""

    def __init__(self, app: ASGIApp, token_sha256: str) -> None:
        self.app = app
        self.token_sha256 = token_sha256

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] == "/health":
            await self.app(scope, receive, send)
            return
        parts = (_header(scope, b"authorization") or "").split(" ", 1)
        if (
            len(parts) == 2
            and parts[0].lower() == "bearer"
            and verify_token(parts[1], self.token_sha256)
        ):
            await self.app(scope, receive, send)
            return
        response = JSONResponse(
            error_body(UNAUTHORIZED, HTTP_MESSAGES_FR[401]),
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
        await response(scope, receive, send)

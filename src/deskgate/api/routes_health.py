"""Route `/health` : seule route publique. Aucun chemin, aucune capacité, aucun secret."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    state = request.app.state
    return {"status": "ok", "version": state.version, "warnings": list(state.warnings)}

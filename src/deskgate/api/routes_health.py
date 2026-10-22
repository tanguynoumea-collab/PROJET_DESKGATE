"""Route `/health` : seule route publique. Aucun chemin, aucune capacité, aucun secret."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from deskgate.core.health import overall

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    state = request.app.state
    threads = state.threads() if state.threads is not None else {}
    engine = threads.get("engine", "ok")
    sender = threads.get("sender", "ok")
    return {
        "status": overall({"engine": engine, "sender": sender}),
        "version": state.version,
        "warnings": list(state.warnings),
        "engine": engine,
        "sender": sender,
    }

"""Worker `mcp.call` : appelle un outil d'un serveur MCP stdio déclaré, sans LLM (D-11).

Seul module de `src/deskgate` qui importe le SDK `mcp`. Aucune commande libre : le serveur et
l'outil doivent figurer dans `runner.toml` (transmis par l'engine dans `ctx.settings`).
"""

from __future__ import annotations

import json
import os
from typing import Any

import anyio
from mcp import Client, StdioServerParameters
from mcp.shared.exceptions import MCPError
from mcp.types import REQUEST_TIMEOUT

from deskgate.core.env import mcp_env_var

DEFAULT_CALL_TIMEOUT_S = 60.0
MAX_CALL_TIMEOUT_S = 3600.0
DATA_MAX_BYTES = 900_000
WATCH_PERIOD_S = 0.25


class McpCallError(Exception):
    """Erreur classée : `error_code` devient `error.type` (lu par le SDK)."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(f"{error_code} : {message}")
        self.error_code = error_code


def _leaves(e: BaseException) -> list[BaseException]:
    if isinstance(e, BaseExceptionGroup):
        return [x for s in e.exceptions for x in _leaves(s)]
    return [e]


def _validate(params: dict[str, Any]) -> tuple[str, str, dict[str, Any], float]:
    server, tool = params.get("server"), params.get("tool")
    if not isinstance(server, str) or not server:
        raise McpCallError("invalid_params", "« server » doit être une chaîne non vide.")
    if not isinstance(tool, str) or not tool:
        raise McpCallError("invalid_params", "« tool » doit être une chaîne non vide.")
    arguments = params.get("arguments", {})
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise McpCallError("invalid_params", "« arguments » doit être un objet.")
    timeout = params.get("call_timeout_s", DEFAULT_CALL_TIMEOUT_S)
    if isinstance(timeout, bool) or not isinstance(timeout, int | float) or timeout <= 0:
        raise McpCallError("invalid_params", "« call_timeout_s » doit être un nombre > 0.")
    return server, tool, arguments, min(float(timeout), MAX_CALL_TIMEOUT_S)


def _content(c: Any) -> dict[str, Any]:
    if getattr(c, "type", None) == "text":
        return {"type": "text", "text": c.text}
    mime = getattr(c, "mimeType", None) or getattr(c, "mime_type", None)
    return {"type": str(getattr(c, "type", "unknown")), "mime": mime}


async def _call(params: dict[str, Any], ctx: Any) -> dict[str, Any]:
    name, tool, arguments, call_timeout = _validate(params)
    servers: dict[str, Any] = (ctx.settings or {}).get("servers", {})
    srv = servers.get(name)
    if srv is None:
        raise McpCallError("server_not_declared", f"serveur MCP « {name} » non déclaré.")
    if tool not in srv.get("allowed_tools", []):
        raise McpCallError("tool_not_allowed", f"outil « {tool} » non autorisé sur « {name} ».")
    env = {
        k: os.environ[mcp_env_var(name, k)]
        for k in srv.get("env_keys", [])
        if mcp_env_var(name, k) in os.environ
    }
    sp = StdioServerParameters(
        command=srv["command"], args=list(srv.get("args", [])), env=env, cwd=ctx.work_dir
    )
    ctx.log(f"Appel de l'outil « {tool} » sur le serveur MCP « {name} ».")
    box: dict[str, Any] = {}

    async def watcher(scope: anyio.CancelScope) -> None:
        while True:
            await anyio.sleep(WATCH_PERIOD_S)
            if ctx.cancelled():
                box["cancelled"] = True
                scope.cancel()
                return

    async with anyio.create_task_group() as tg:
        tg.start_soon(watcher, tg.cancel_scope)
        try:
            async with Client(sp, read_timeout_seconds=call_timeout) as client:
                try:
                    box["r"] = await client.call_tool(tool, arguments)
                except MCPError as e:  # dans le corps : sinon ExceptionGroup imbriqué
                    box["mcp_error"] = e
        except BaseException as eg:
            if not box.get("cancelled"):
                box["fatal"] = _leaves(eg)
        tg.cancel_scope.cancel()

    if box.get("cancelled") and "r" not in box:
        return {"summary": {"cancelled": True}}
    if "fatal" in box:
        kinds = ", ".join(sorted({type(x).__name__ for x in box["fatal"]}))
        raise McpCallError("server_unreachable", f"serveur « {name} » injoignable ({kinds}).")
    if "mcp_error" in box:
        e = box["mcp_error"]
        if e.code == REQUEST_TIMEOUT:
            raise McpCallError("call_timeout", f"délai de {call_timeout:g} s dépassé.")
        raise McpCallError("mcp_error", f"erreur MCP (code {e.code}).")
    r = box["r"]
    if r.is_error:
        text = " ".join(getattr(c, "text", "") or "" for c in r.content)
        raise McpCallError("tool_error", text[:500])
    data: dict[str, Any] = {
        "structured_content": r.structured_content,
        "content": [_content(c) for c in r.content],
    }
    # Octets UTF-8, comme le plafond de result.json (DS3-1) : « € » compte 3, pas 1.
    size = len(json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    if size > DATA_MAX_BYTES:
        path = os.path.join(ctx.work_dir, "mcp-result.json")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, allow_nan=False)
        ctx.artifact(path, "mcp_result")
        # Le worker ignore les chemins conteneur : n8n lit le chemin dans artifacts (mcp_result).
        data = {"truncated": True, "artifact": "mcp_result"}
    return {"summary": {"server": name, "tool": tool, "is_error": False}, "data": data}


def run(params: dict[str, Any], ctx: Any) -> dict[str, Any]:
    return anyio.run(_call, params, ctx)

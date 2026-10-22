"""Serveur MCP de test (D-12) : echo, add, sleep, erreur, spawn_orphan, env, fichiers."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Any

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("deskgate-mini")


@mcp.tool()
def echo(text: str) -> str:
    return text


@mcp.tool()
def add(a: int, b: int) -> int:
    return a + b


@mcp.tool()
def sleep(seconds: float) -> str:
    time.sleep(seconds)
    return "reveille"


@mcp.tool()
def erreur(message: str = "boum") -> str:
    raise ValueError(message)


@mcp.tool()
def spawn_orphan(pid_file: str, sleep: float = 0) -> str:
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    with open(pid_file, "w", encoding="utf-8") as f:
        f.write(f"{os.getpid()} {p.pid}")
    if sleep:
        time.sleep(sleep)
    return "ok"


@mcp.tool()
def env(names: list[str]) -> dict[str, Any]:
    return {
        "values": {n: os.environ.get(n) for n in names},
        "deskgate": sorted(k for k in os.environ if k.upper().startswith("DESKGATE")),
    }


@mcp.tool()
def read_file(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


@mcp.tool()
def write_file(path: str, text: str = "ecrit") -> str:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


if __name__ == "__main__":
    mcp.run("stdio")

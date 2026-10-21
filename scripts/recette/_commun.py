"""Briques communes des scripts de recette (n8n, runner, SQLite en lecture seule, masquage).

Bibliothèque standard + psutil. N'importe jamais `deskgate`. Aucun secret n'est écrit ni affiché.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

import psutil

REPO = Path(__file__).resolve().parents[2]
DOCKER = shutil.which("docker") or "docker"
COMPOSE = [DOCKER, "compose", "-f", str(REPO / "n8n" / "docker-compose.yml")]
N8N = "http://127.0.0.1:5679"
RUNNER = "http://127.0.0.1:8765"
WORKFLOW_ID = "DeskgateClash0001"
WEBHOOK = f"{N8N}/webhook/deskgate-ifc-clash"
DATA = Path(os.environ.get("LOCALAPPDATA", ".")) / "Deskgate"
DB = DATA / "deskgate.db"
TASK_NAME = "Deskgate"
SYSTEM32 = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32"
SCHTASKS = str(SYSTEM32 / "schtasks.exe")
TASKKILL = str(SYSTEM32 / "taskkill.exe")

_SIGNATURE = re.compile(r"(signature(?:=|%3[dD]))[^&\s\"']+", re.IGNORECASE)
_FINAL_CALLBACK = ("delivered", "delivered_duplicate", "abandoned")


def mask(text: str) -> str:
    """Masque la valeur du paramètre `signature` (resumeUrl n8n)."""
    return _SIGNATURE.sub(r"\1***", text)


def read_env(path: Path | None = None) -> dict[str, str]:
    """Lit `n8n/.env` (lignes CLE=valeur, commentaires ignorés)."""
    env: dict[str, str] = {}
    for line in (path or REPO / "n8n" / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def http(
    method: str,
    url: str,
    body: Any = None,
    headers: dict[str, str] | None = None,
    opener: urllib.request.OpenerDirector | None = None,
    timeout: float = 30,
) -> tuple[int, Any]:
    """Appel HTTP JSON ; une erreur HTTP renvoie (code, corps)."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    all_headers = {"Accept": "application/json", **(headers or {})}
    if data is not None:
        all_headers["Content-Type"] = "application/json"
    # URL locale fixe (127.0.0.1), schéma http : pas d'entrée externe.
    request = urllib.request.Request(url, data=data, method=method, headers=all_headers)  # noqa: S310
    open_fn = opener.open if opener else urllib.request.urlopen
    try:
        with open_fn(request, timeout=timeout) as response:
            raw = response.read()
            code = response.status
    except urllib.error.HTTPError as error:
        raw = error.read()
        code = error.code
    except (urllib.error.URLError, OSError) as error:
        return 0, str(error)
    try:
        return code, json.loads(raw) if raw else None
    except ValueError:
        return code, raw.decode("utf-8", "replace")


def wait_health(url: str, timeout_s: float) -> bool:
    """Attend qu'une URL de santé réponde 200."""
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        code, _ = http("GET", url, timeout=5)
        if code == 200:
            return True
        time.sleep(2)
    return False


class N8nSession:
    """Session n8n (cookie) et clé d'API éphémère."""

    def __init__(self) -> None:
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        return http(method, N8N + path, body, opener=self.opener)

    def login(self, email: str, password: str) -> bool:
        code, _ = self.call(
            "POST", "/rest/login", {"emailOrLdapLoginId": email, "password": password}
        )
        return code == 200

    def create_api_key(self, label: str) -> tuple[str, str]:
        wanted = [
            "execution:read",
            "execution:list",
            "workflow:read",
            "workflow:list",
            "workflow:activate",
        ]
        code, scopes = self.call("GET", "/rest/api-keys/scopes")
        if code == 200 and isinstance(scopes, dict) and isinstance(scopes.get("data"), list):
            valid = set(scopes["data"])
            wanted = [s for s in wanted if s in valid]
        code, reply = self.call(
            "POST", "/rest/api-keys", {"label": label, "scopes": wanted, "expiresAt": None}
        )
        if code != 200:
            raise RuntimeError(f"création de la clé d'API refusée (HTTP {code})")
        data = reply["data"]
        return str(data["id"]), str(data["rawApiKey"])

    def delete_api_key(self, key_id: str) -> None:
        code, _ = self.call("DELETE", f"/rest/api-keys/{key_id}")
        if code not in (200, 204):
            print(f"suppression de la clé d'API: HTTP {code} (best effort)")


def api_get(api_key: str, path: str) -> tuple[int, Any]:
    """GET sur l'API publique n8n avec la clé éphémère."""
    return http("GET", N8N + "/api/v1" + path, headers={"X-N8N-API-KEY": api_key})


def compose(
    *args: str, input_bytes: bytes | None = None, check: bool = True
) -> subprocess.CompletedProcess[bytes]:
    """docker compose sur le compose du dépôt (projet deskgate-n8n)."""
    return subprocess.run(  # noqa: S603 - liste d'arguments, exécutable résolu, pas de shell
        [*COMPOSE, *args], input=input_bytes, capture_output=True, check=check, cwd=REPO
    )


def db_rows(sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    """Lecture seule de la base du runner. Ne jamais sélectionner `jobs.callback_url`."""
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True, timeout=10)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def listener_pid(port: int = 8765) -> int | None:
    for conn in psutil.net_connections(kind="tcp"):
        if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port:
            return conn.pid
    return None


def provenance(pid: int | None) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    try:
        proc = psutil.Process(pid) if pid else None
    except psutil.Error:
        proc = None
    while proc is not None:
        try:
            chain.append(
                {"pid": proc.pid, "name": proc.name(), "cmdline": " ".join(proc.cmdline())}
            )
            proc = proc.parent()
        except psutil.Error:
            break
    return chain


def assert_started_by_task(chain: list[dict[str, Any]]) -> bool:
    forbidden = {
        "bash.exe",
        "cmd.exe",
        "powershell.exe",
        "pwsh.exe",
        "windowsterminal.exe",
        "code.exe",
    }
    names = [str(p["name"]).lower() for p in chain]
    if any(n in forbidden for n in names):
        return False
    runner = any(
        str(p["name"]).lower() == "pythonw.exe" and "-m deskgate serve" in str(p["cmdline"])
        for p in chain
    )
    return runner and "svchost.exe" in names


def deskgate_processes() -> list[psutil.Process]:
    """Processus runner (`-m deskgate serve`) ou plugin (`deskgate_sdk`) vivants."""
    found = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        line = " ".join(proc.info.get("cmdline") or [])
        if "-m deskgate serve" in line or "deskgate_sdk" in line:
            found.append(proc)
    return found


def plugin_rss_mb() -> float:
    """Somme des RSS des processus `deskgate_sdk` et de leurs enfants."""
    seen: dict[int, psutil.Process] = {}
    for proc in psutil.process_iter(["pid", "cmdline"]):
        if "deskgate_sdk" in " ".join(proc.info.get("cmdline") or []):
            seen[proc.pid] = proc
            try:
                for child in proc.children(recursive=True):
                    seen[child.pid] = child
            except psutil.Error:
                continue
    total = 0
    for proc in seen.values():
        try:
            total += proc.memory_info().rss
        except psutil.Error:
            continue
    return total / (1024 * 1024)


def is_final_callback(state: str | None) -> bool:
    return bool(state) and str(state).startswith(_FINAL_CALLBACK)

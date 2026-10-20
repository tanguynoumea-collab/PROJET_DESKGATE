"""Instance unique : mutex nommé Windows et socket d'écoute exclusif.

Seul module de `src/deskgate` autorisé à importer `ctypes` en phase 1.
Ordre de démarrage (D-04) : mutex, puis socket lié, puis base.
"""

from __future__ import annotations

import ctypes
import os
import socket
from ctypes import wintypes

DEFAULT_INSTANCE_NAME = "Local\\Deskgate"

ERROR_ALREADY_EXISTS = 183
ERROR_ACCESS_DENIED = 5

WSAEADDRINUSE = 10048
WSAEACCES = 10013

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
# argtypes/restype explicites indispensables : sinon les poignées 64 bits sont tronquées.
_k32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
_k32.CreateMutexW.restype = wintypes.HANDLE
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
_k32.CloseHandle.restype = wintypes.BOOL

# Poignées gardées jusqu'à la sortie du processus : la mort du processus libère le mutex.
_HELD: list[int] = []


def instance_name_from_env() -> str:
    """Nom du mutex : variable `DESKGATE_INSTANCE_NAME`, sinon le nom par défaut."""
    return os.environ.get("DESKGATE_INSTANCE_NAME", DEFAULT_INSTANCE_NAME)


def acquire_mutex(name: str | None = None) -> int | None:
    """Prend le mutex nommé. Renvoie la poignée, ou `None` si une autre instance le détient."""
    if name is None:
        name = instance_name_from_env()
    ctypes.set_last_error(0)
    handle = _k32.CreateMutexW(None, True, name)
    err = ctypes.get_last_error()  # à lire immédiatement
    if not handle or err in (ERROR_ALREADY_EXISTS, ERROR_ACCESS_DENIED):
        if handle:
            _k32.CloseHandle(handle)
        return None
    _HELD.append(int(handle))
    return int(handle)


def bind_exclusive(host: str, port: int) -> socket.socket:
    """Crée un socket TCP lié en exclusivité (SO_EXCLUSIVEADDRUSE).

    Ne jamais poser SO_REUSEADDR en plus (WinError 10022).
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        s.bind((host, port))
    except OSError:
        s.close()
        raise
    return s


def describe_bind_error(exc: OSError, host: str, port: int) -> str:
    """Message français selon `winerror` (jamais `strerror`, qui est localisé)."""
    code = getattr(exc, "winerror", None)
    if code == WSAEADDRINUSE:
        return f"Le port {port} est déjà utilisé sur {host}."
    if code == WSAEACCES:
        return (
            f"Accès refusé au port {port} sur {host} (port réservé ? voir "
            "netsh interface ipv4 show excludedportrange protocol=tcp)."
        )
    return f"Impossible d'écouter sur {host}:{port} (code Windows {code})."

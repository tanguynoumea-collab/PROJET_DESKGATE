"""Accès à la base SQLite : seul module qui importe `sqlite3`.

Phase 1 : squelette minimal. Le schéma et les migrations arrivent en phase 2.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def open_db(path: Path) -> sqlite3.Connection:
    """Ouvre (et crée au besoin) la base en WAL, durabilité complète."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

"""Contrat de fichiers runner <-> worker (complété par la tâche suivante)."""

from __future__ import annotations

from typing import Literal

ResultState = Literal["valid", "plugin_error", "missing", "invalid", "too_large"]

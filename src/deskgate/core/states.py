"""Statuts d'une tâche et décision pure d'un tour d'engine.

Choix déterministes (recherche, Pattern 4) :
- l'ordre d'évaluation est : sortie du processus, puis annulation, puis échéance ;
- un processus déjà sorti à l'instant du ``poll()`` est évalué par ``outcome`` même si
  l'échéance est dépassée dans le même tour (fin normale et délai simultanés : pas de timeout) ;
- une annulation demandée avant la sortie donne ``cancelled`` (même si le résultat est valide) ;
- l'échéance est ignorée pendant la grâce d'annulation : l'annulation, demandée avant, l'emporte ;
- la grâce écoulée sans sortie, le job est tué et la tâche est ``cancelled``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

QUEUED, RUNNING, SUCCEEDED, FAILED, TIMEOUT, CANCELLED, INTERRUPTED = (
    "queued",
    "running",
    "succeeded",
    "failed",
    "timeout",
    "cancelled",
    "interrupted",
)
STATUSES = (QUEUED, RUNNING, SUCCEEDED, FAILED, TIMEOUT, CANCELLED, INTERRUPTED)
TERMINAL = frozenset({SUCCEEDED, FAILED, TIMEOUT, CANCELLED, INTERRUPTED})

Action = Literal["wait", "write_cancel_flag", "kill", "exited"]


@dataclass(frozen=True)
class Observation:
    exit_code: int | None  # None = processus vivant (lu par Popen.poll() AVANT l'échéance)
    cancel_requested: bool
    cancel_sent_at: float | None  # horloge monotone ; None si cancel.flag pas encore écrit
    deadline: float  # horloge monotone


@dataclass(frozen=True)
class Decision:
    action: Action
    status: str | None = None  # "kill" : CANCELLED ou TIMEOUT ; "exited" : CANCELLED ou None


def step(obs: Observation, now: float, grace: float) -> Decision:
    """Décide de l'action d'un tour d'engine ; fonction pure."""
    if obs.exit_code is not None:
        return Decision("exited", CANCELLED if obs.cancel_requested else None)
    if obs.cancel_requested or obs.cancel_sent_at is not None:
        if obs.cancel_sent_at is None:
            return Decision("write_cancel_flag")
        if now - obs.cancel_sent_at >= grace:
            return Decision("kill", CANCELLED)
        return Decision("wait")
    if now >= obs.deadline:
        return Decision("kill", TIMEOUT)
    return Decision("wait")

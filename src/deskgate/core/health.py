"""État des threads pour /health (D-07) : fonctions pures.

`stale` signale un thread vivant mais qui ne fait plus de tour : le superviseur ne recrée que
les threads morts. Le seuil est `max(10 x période de sondage, plancher)` : le plancher évite un
faux `stale` pendant un POST lent (sender) ou un suivi de Job long (engine).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

ThreadState = Literal["ok", "failed", "stale"]

ENGINE_STALE_FLOOR_S = 30.0
SENDER_STALE_FLOOR_S = 60.0
STALE_FACTOR = 10.0


def stale_threshold(poll_s: float, floor_s: float, factor: float = STALE_FACTOR) -> float:
    return max(factor * poll_s, floor_s)


def thread_state(*, failed: bool, age_s: float | None, threshold_s: float) -> ThreadState:
    if failed:
        return "failed"
    if age_s is None or age_s <= threshold_s:
        return "ok"
    return "stale"


def overall(states: Mapping[str, ThreadState]) -> Literal["ok", "degraded"]:
    return "ok" if all(s == "ok" for s in states.values()) else "degraded"

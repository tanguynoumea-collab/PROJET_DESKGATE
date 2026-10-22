"""Pilote de test : serve() avec une panne injectée dans Engine.tick (DESKGATE_TEST_FAULT)."""

from __future__ import annotations

import os
import sys
import threading

from deskgate import runtime
from deskgate.engine import Engine

MODE = os.environ.get("DESKGATE_TEST_FAULT", "")
_lock = threading.Lock()
_left = [int(MODE.split(":", 1)[1])] if MODE.startswith("running:") else [0]
_original = Engine.tick


def _tick(self: Engine) -> None:
    _original(self)
    if MODE == "always":
        raise RuntimeError("panne injectée (test)")
    if self.running_job_id is not None:
        with _lock:
            if _left[0] > 0:
                _left[0] -= 1
                raise RuntimeError("panne injectée (test)")


setattr(Engine, "tick", _tick)  # noqa: B010

if __name__ == "__main__":
    runtime.configure_logging()
    sys.exit(runtime.serve())

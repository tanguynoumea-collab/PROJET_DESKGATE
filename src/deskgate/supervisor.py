"""Superviseur des threads engine et sender (D-03 cas 2).

Recrée un thread mort après avoir conclu la tâche courante en interrupted. Le budget (MAX_RESTARTS
recréations dans WINDOW_S secondes) ne compte que les recréations effectives : recover réussi,
thread neuf démarré et installé dans le Holder. Un recover qui échoue (base verrouillée) n'en
consomme aucune ; il est retenté après min(RECOVER_BACKOFF_CAP_S, 2^n) secondes, n étant le nombre
d'échecs consécutifs, et le superviseur abandonne après MAX_RECOVER_FAILURES échecs consécutifs.
Abandon = code EXIT_THREAD_FAILED : RestartOnFailure du Planificateur ne relance pas une sortie
non nulle (expérience E1, phase 5.2), le code ne sert qu'à signaler l'abandon.

stop() ne prend pas le verrou (un recover peut durer plusieurs secondes) ; une recréation en cours
revérifie _stop après le recover et après le démarrage du thread neuf, qui est alors arrêté.

Limite assumée : un verdict différé (`Engine._unsettled`) encore en mémoire quand le thread meurt
est perdu ; la tâche est conclue `interrupted` (`runner_restarted`) par la recovery, jamais avec le
verdict calculé.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from deskgate.core.health import ThreadState

logger = logging.getLogger(__name__)

EXIT_THREAD_FAILED = 6
MAX_RESTARTS = 3
WINDOW_S = 600.0
MAX_RECOVER_FAILURES = 10
RECOVER_BACKOFF_CAP_S = 30.0


@dataclass(frozen=True)
class Decision:
    restart_engine: bool
    restart_sender: bool
    give_up: bool


def recent(times: Sequence[float], now: float, window: float = WINDOW_S) -> list[float]:
    """Horodatages encore dans la fenêtre glissante (borne basse exclusive)."""
    return [t for t in times if now - t < window]


def recover_delay(failures: int, cap: float = RECOVER_BACKOFF_CAP_S) -> float:
    """Délai avant le prochain recover après `failures` échecs consécutifs (P-02)."""
    if failures <= 0:
        return 0.0
    return min(cap, 2.0**failures)


def decide(
    *,
    engine_failed: bool,
    sender_failed: bool,
    recent_restarts: int,
    max_restarts: int = MAX_RESTARTS,
    recover_failures: int = 0,
    max_recover_failures: int = MAX_RECOVER_FAILURES,
) -> Decision:
    if not (engine_failed or sender_failed):
        return Decision(False, False, False)
    if engine_failed and recover_failures >= max_recover_failures:
        return Decision(False, False, True)
    needed = int(engine_failed) + int(sender_failed)
    if recent_restarts + needed > max_restarts:
        return Decision(False, False, True)
    return Decision(engine_failed, sender_failed, False)


def exit_code(*, gave_up: bool) -> int:
    return EXIT_THREAD_FAILED if gave_up else 0


class Restartable(Protocol):
    failed: bool
    on_fatal: Callable[[], None] | None

    def start(self) -> None: ...
    def stop(self, timeout: float = 5.0) -> None: ...
    def wake(self) -> None: ...
    def status(self) -> ThreadState: ...


@dataclass
class Holder:
    engine: Restartable
    sender: Restartable


class Supervisor:
    def __init__(
        self,
        *,
        holder: Holder,
        make_engine: Callable[[], Restartable],
        make_sender: Callable[[], Restartable],
        recover: Callable[[], list[str]],
        on_give_up: Callable[[], None],
        clock: Callable[[], float] = time.monotonic,
        period: float = 1.0,
        max_restarts: int = MAX_RESTARTS,
        window_s: float = WINDOW_S,
    ) -> None:
        self._holder = holder
        self._make_engine = make_engine
        self._make_sender = make_sender
        self._recover = recover
        self._on_give_up = on_give_up
        self._clock = clock
        self._period = period
        self._max_restarts = max_restarts
        self._window_s = window_s
        self._times: list[float] = []
        self._event = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.gave_up = False
        self.last_cause: str | None = None

    def notify(self) -> None:
        """Appelé depuis le thread mourant : pose seulement l'événement (jamais de join)."""
        self._event.set()

    def attach(self) -> None:
        self._holder.engine.on_fatal = self.notify
        self._holder.sender.on_fatal = self.notify

    def check(self) -> None:
        with self._lock:
            if self._stop.is_set() or self.gave_up:
                return
            now = self._clock()
            self._times = recent(self._times, now, self._window_s)
            d = decide(
                engine_failed=self._holder.engine.failed,
                sender_failed=self._holder.sender.failed,
                recent_restarts=len(self._times),
                max_restarts=self._max_restarts,
            )
            if d.give_up:
                self.gave_up = True
                logger.error(
                    "Superviseur : abandon après %d recréation(s) en %.0f s "
                    "(dernière cause : %s) ; arrêt du runner (code %d).",
                    len(self._times),
                    self._window_s,
                    self.last_cause,
                    EXIT_THREAD_FAILED,
                )
                self._on_give_up()
                return
            if d.restart_engine:
                self._times.append(now)
                self._restart_engine()
            if d.restart_sender:
                self._times.append(now)
                self._restart_sender()

    def _restart_engine(self) -> None:
        old = self._holder.engine
        self.last_cause = "engine"
        old.stop()
        try:
            ids = self._recover()
        except Exception:
            logger.exception(
                "Superviseur : conclusion des tâches interrompues impossible ; "
                "nouvel essai au prochain passage."
            )
            self.last_cause = "engine (recovery impossible)"
            return
        new = self._make_engine()
        new.on_fatal = self.notify
        new.start()
        self._holder.engine = new
        self._holder.sender.wake()
        logger.warning(
            "Thread engine recréé (%d/%d en %.0f s) ; %d tâche(s) conclue(s) en interrupted.",
            len(self._times),
            self._max_restarts,
            self._window_s,
            len(ids),
        )

    def _restart_sender(self) -> None:
        old = self._holder.sender
        self.last_cause = "sender"
        old.stop()
        new = self._make_sender()
        new.on_fatal = self.notify
        new.start()
        self._holder.sender = new
        logger.warning(
            "Thread sender recréé (%d/%d en %.0f s).",
            len(self._times),
            self._max_restarts,
            self._window_s,
        )

    def run(self) -> None:
        while not self._stop.is_set():
            self._event.wait(self._period)
            self._event.clear()
            if self._stop.is_set():
                break
            try:
                self.check()
            except Exception:
                logger.exception("Superviseur arrêté sur erreur.")
                self.gave_up = True
                self._on_give_up()
                return
            if self.gave_up:
                return

    def start(self) -> None:
        thread = threading.Thread(target=self.run, name="deskgate-supervisor", daemon=True)
        self._thread = thread
        thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Arrête le superviseur ; l'appelant arrête ensuite engine et sender courants."""
        self._stop.set()
        self._event.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)

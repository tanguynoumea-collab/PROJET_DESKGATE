"""Thread `sender` : rappelle la `resumeUrl` n8n, une ligne `callbacks` à la fois.

Concurrence 1. L'état vit en base (table `callbacks`) : un redémarrage reprend les lignes dues.
`tick()` fait un tour complet et se teste sans thread, avec une horloge murale injectée ;
`run()` n'est que la boucle de réveil autour de `tick()`. Ce module est le seul de `src/` qui
importe `httpx2`. La `resumeUrl` est un secret : elle est passée telle quelle au client et
n'apparaît jamais dans les journaux, les erreurs enregistrées ni l'audit.

Politique d'erreur : toute exception d'un tour est journalisée, la connexion rouverte et le tour
rejoué avec back-off ; l'état de chaque rappel vit en base, donc rien n'est perdu ; au-delà de
`MAX_CONSECUTIVE_ERRORS` erreurs consécutives le thread meurt et le superviseur le recrée.
"""

from __future__ import annotations

import contextlib
import logging
import random
import threading
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

import httpx2

from deskgate import store
from deskgate.core.callback_policy import (
    ABANDONED_EXHAUSTED,
    ABANDONED_REJECTED,
    BODY_READ_MAX,
    FINAL,
    RETRY_MINIMAL,
    RETRY_SHORT,
    CallbackUrlError,
    check_callback_url,
    classify,
    next_delay,
)
from deskgate.core.config import RunnerConfig
from deskgate.core.payload import build_callback, encode, minimal

logger = logging.getLogger("deskgate.sender")

MAX_CONSECUTIVE_ERRORS = 5


class SendOutcome(NamedTuple):
    status: int | None
    body: bytes | None
    error: str | None


def make_client() -> httpx2.Client:
    """Client synchrone : pas de redirection, pas de proxy d'environnement, pas de keep-alive."""
    return httpx2.Client(
        timeout=httpx2.Timeout(30.0, connect=5.0),
        follow_redirects=False,
        trust_env=False,
        limits=httpx2.Limits(max_keepalive_connections=0),
    )


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _head(chunks: Iterator[bytes], limit: int) -> bytes:
    """Lit au plus `limit` octets du corps de la réponse."""
    out = bytearray()
    for chunk in chunks:
        out += chunk
        if len(out) >= limit:
            break
    return bytes(out[:limit])


class Sender:
    def __init__(
        self,
        *,
        db_path: Path,
        config: RunnerConfig,
        client: httpx2.Client | None = None,
        wall: Callable[[], datetime] = _utcnow,
        rng: random.Random | None = None,
        poll: float = 1.0,
    ) -> None:
        self._db_path = db_path
        self._config = config
        self._client = client if client is not None else make_client()
        self._wall = wall
        self._rng = rng if rng is not None else random.Random()  # noqa: S311 - gigue, non cryptographique
        self._poll = poll
        self._conn: store.Connection | None = None
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self.on_fatal: Callable[[], None] | None = None
        self.failed = False
        self.last_tick_at: datetime | None = None

    # ------------------------------------------------------------------ tour

    def _connection(self) -> store.Connection:
        if self._conn is None:
            self._conn = store.connect(self._db_path)
        return self._conn

    def _drop_connection(self) -> None:
        if self._conn is not None:
            with contextlib.suppress(Exception):
                self._conn.close()
            self._conn = None

    def tick(self) -> bool:
        """Traite un rappel échu ; True si une ligne a été envoyée ou abandonnée."""
        now = self._wall()
        self.last_tick_at = now
        conn = self._connection()
        claim = store.claim_due_callback(conn, now, max_window_s=self._config.callback.max_window_s)
        if claim is None:
            return False
        if not self._host_allowed(claim.callback_url):
            store.abandon_callback(
                conn,
                claim.job_id,
                state=ABANDONED_REJECTED,
                reason="host_not_allowed",
                now=self._wall(),
            )
            logger.warning("Rappel de la tâche %s abandonné : hôte non autorisé.", claim.job_id)
            return True
        body = build_callback(
            job_id=claim.job_id,
            capability=claim.capability,
            status=claim.status,
            started_at=claim.started_at,
            finished_at=claim.finished_at,
            result_json=claim.result_json,
            error_code=claim.error_code,
            error_message=claim.error_message,
        )
        if claim.last_status == 413:  # un renvoi minimal
            body = minimal(body)
        outcome = self._send(claim.callback_url, encode(body))
        decision = classify(
            outcome.status,
            outcome.body,
            maybe_delivered=claim.maybe_delivered_before,
            prev_status=claim.last_status,
        )
        after = self._wall()
        delay = 0.0
        next_at: datetime | None = None
        if decision.kind in FINAL:
            state = decision.kind
        else:
            delay = next_delay(
                claim.attempt,
                max_backoff_s=self._config.callback.max_backoff_s,
                rng=self._rng,
                short=decision.kind in (RETRY_SHORT, RETRY_MINIMAL),
            )
            if after + timedelta(seconds=delay) >= claim.deadline:
                state = ABANDONED_EXHAUSTED  # pas de dernier envoi hors fenêtre
            else:
                state = "pending"
                next_at = after + timedelta(seconds=delay)
        store.record_callback_result(
            conn,
            claim,
            state=state,
            decision=decision.kind,
            http_status=outcome.status,
            error=outcome.error,
            next_attempt_at=next_at,
            now=after,
        )
        reason = decision.reason or decision.kind
        if state.startswith("delivered"):
            logger.info(
                "Rappel de la tâche %s livré (essai %d, %s).", claim.job_id, claim.attempt, state
            )
        elif state == "pending":
            logger.info(
                "Rappel de la tâche %s : essai %d sans succès (%s), nouvel essai dans %.0f s.",
                claim.job_id,
                claim.attempt,
                reason,
                delay,
            )
        else:
            logger.warning("Rappel de la tâche %s abandonné (%s).", claim.job_id, state)
        return True

    def _host_allowed(self, url: str) -> bool:
        """Revérifie l'hôte à l'envoi (D-02) : la liste a pu changer depuis la soumission."""
        try:
            host = check_callback_url(url, self._config.callback_allowed_hosts)
            parsed = httpx2.URL(url).host.lower()
        except (CallbackUrlError, httpx2.InvalidURL):
            return False
        return parsed == host

    def _send(self, url: str, data: bytes) -> SendOutcome:
        """POST de la `resumeUrl` telle quelle ; jamais l'URL ni le texte d'une erreur en retour."""
        try:
            with self._client.stream(
                "POST", url, content=data, headers={"Content-Type": "application/json"}
            ) as r:
                head = None if 200 <= r.status_code < 300 else _head(r.iter_bytes(), BODY_READ_MAX)
                return SendOutcome(r.status_code, head, None)
        except httpx2.HTTPError as exc:  # délais, réseau, protocole
            return SendOutcome(None, None, type(exc).__name__)
        except httpx2.InvalidURL:
            return SendOutcome(None, None, "InvalidURL")

    # ------------------------------------------------- boucle, réveil, arrêt

    def wake(self) -> None:
        self._wake.set()

    def run(self) -> None:
        errors = 0
        try:
            while not self._stop.is_set():
                self._wake.wait(self._poll)
                self._wake.clear()  # avant la lecture de la base : aucun réveil perdu
                try:
                    while not self._stop.is_set() and self.tick():
                        errors = 0
                    errors = 0
                except Exception:
                    errors += 1
                    logger.exception("Erreur du thread sender.")
                    self._drop_connection()
                    if errors >= MAX_CONSECUTIVE_ERRORS:
                        self.failed = True
                        if self.on_fatal is not None:
                            self.on_fatal()
                        return
                    self._stop.wait(min(30, 2**errors))
        finally:
            self._drop_connection()
            with contextlib.suppress(Exception):
                self._client.close()

    def start(self) -> None:
        thread = threading.Thread(target=self.run, name="deskgate-sender", daemon=True)
        self._thread = thread
        thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Arrête la boucle. Un POST en vol peut dépasser le délai : la ligne reste due."""
        already = self._stop.is_set()
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
        if not already:
            logger.info("Sender arrêté.")

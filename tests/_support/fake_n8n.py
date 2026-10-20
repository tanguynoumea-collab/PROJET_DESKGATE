"""Faux n8n 2.43.8 : serveur HTTP local rejouant les réponses exactes de `webhook-waiting`.

Stdlib seulement. Écoute sur 127.0.0.1 (jamais `localhost` : +2 s par requête sous Windows).
Enregistre la ligne de requête brute pour prouver que la query est transmise octet pour octet.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, cast

SIG = "a+b/c=d%2Bz%2Fq%3D"


@dataclass(frozen=True)
class Step:
    status: int
    body: bytes = b""
    content_type: str = "application/json"
    delay_s: float = 0.0
    drop: bool = False


@dataclass(frozen=True)
class Recorded:
    requestline: str
    path: str
    headers: dict[str, str]
    body: bytes
    t: float


OK = Step(200, b'{"message":"Workflow was started"}')
RUNNING = Step(409, b'{"code":409,"message":"The execution \\"42\\" is running already."}')
ABOUT_TO_RESUME = Step(409, b'{"code":409,"message":"The execution \\"42\\" is about to resume."}')
FINISHED_ERROR = Step(
    409, b'{"code":409,"message":"The execution \\"42\\" has finished with error."}'
)
# Guillemet fermant absent après l'identifiant : reproduit tel quel depuis n8n 2.43.8
# (waiting-webhooks.ts l. 320).
FINISHED = Step(409, b'{"code":409,"message":"The execution \\"42 has finished already."}')
NOT_FOUND = Step(404, b'{"code":404,"message":"The execution \\"42\\" does not exist."}')
NO_WEBHOOK = Step(
    404,
    b'{"code":404,"message":"The workflow for execution \\"42\\" does not contain a waiting '
    b'webhook with a matching path/method."}',
)
INVALID_TOKEN = Step(401, b'{"error":"Invalid token"}', "application/json; charset=utf-8")
SERVER_ERROR = Step(500, b'{"code":500,"message":"Internal Server Error"}')
DROP = Step(0, drop=True)


def hang(seconds: float) -> Step:
    return Step(200, OK.body, delay_s=seconds)


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    owner: FakeN8n

    def handle_error(self, request: Any, client_address: Any) -> None:
        return None


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return None

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        owner = cast(_Server, self.server).owner
        step = owner._record(
            Recorded(
                requestline=self.requestline,
                path=self.path,
                headers={k.lower(): v for k, v in self.headers.items()},
                body=body,
                t=time.monotonic(),
            )
        )
        if step.drop:
            self.close_connection = True
            self.connection.close()
            return
        if step.delay_s > 0:
            time.sleep(step.delay_s)
        self.send_response(step.status)
        self.send_header("Content-Type", step.content_type)
        self.send_header("Content-Length", str(len(step.body)))
        self.end_headers()
        self.wfile.write(step.body)


class FakeN8n:
    def __init__(self) -> None:
        self.default: Step = OK
        self.requests: list[Recorded] = []
        self._script: list[Step] = []
        self._lock = threading.Lock()
        self._server = _Server(("127.0.0.1", 0), _Handler)
        self._server.owner = self
        self._thread: threading.Thread | None = None
        self._stopped = False
        self.port: int = int(self._server.server_address[1])

    def _record(self, rec: Recorded) -> Step:
        with self._lock:
            self.requests.append(rec)
            return self._script.pop(0) if self._script else self.default

    def start(self) -> FakeN8n:
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="fake-n8n", daemon=True
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        if self._thread is not None:
            self._server.shutdown()
            self._thread.join(timeout=5)
        self._server.server_close()

    def script(self, *steps: Step) -> None:
        with self._lock:
            self._script = list(steps)

    def url(self, execution_id: str = "42", signature: str = SIG) -> str:
        return f"http://127.0.0.1:{self.port}/webhook-waiting/{execution_id}?signature={signature}"

    def wait_requests(self, n: int, timeout: float = 10.0) -> list[Recorded]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if len(self.requests) >= n:
                    return list(self.requests)
            time.sleep(0.02)
        with self._lock:
            vues = len(self.requests)
        raise AssertionError(f"{n} requête(s) attendue(s) en {timeout} s, {vues} reçue(s)")

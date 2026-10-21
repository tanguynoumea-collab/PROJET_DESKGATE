"""Journal du runner : la signature n'apparaît sur aucun handler (SEC-05, D-07)."""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from deskgate.runtime import attach_file_log, configure_logging

pytestmark = pytest.mark.unit

_NOMS = ("", "deskgate", "httpx2", "httpcore2")


@pytest.fixture
def logging_isole(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("DESKGATE_LOG_LEVEL", raising=False)
    sauve = [
        (n, list(lg.handlers), lg.level, lg.propagate)
        for n in _NOMS
        for lg in (logging.getLogger(n),)
    ]
    try:
        yield
    finally:
        for n, handlers, level, propagate in sauve:
            lg = logging.getLogger(n)
            lg.handlers[:] = handlers
            lg.setLevel(level)
            lg.propagate = propagate


@pytest.mark.usefixtures("logging_isole")
def test_signature_masquee_partout(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    logging.getLogger("deskgate.sender").info("appel http://127.0.0.1/w?signature=SEC123")
    logging.getLogger("httpx2").warning(
        'HTTP Request: POST http://127.0.0.1/webhook-waiting/1?signature=SEC123 "HTTP/1.1 500"'
    )
    logging.getLogger("uvicorn.error").error("x", exc_info=RuntimeError("signature=SEC123"))
    logging.getLogger("httpx2").info("deja signature=SEC9")
    err = capsys.readouterr().err
    assert "SEC123" not in err
    assert "SEC9" not in err
    assert "signature=***" in err
    assert "deja" not in err


@pytest.mark.usefixtures("logging_isole")
def test_niveau_info_sur_demande(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DESKGATE_LOG_LEVEL", "INFO")
    configure_logging()
    logging.getLogger("httpx2").info("ligne signature=SEC9")
    err = capsys.readouterr().err
    assert "ligne signature=***" in err
    assert "SEC9" not in err


@pytest.mark.usefixtures("logging_isole")
def test_stderr_none_sans_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stderr", None)
    configure_logging()
    assert logging.getLogger("deskgate").handlers == []
    assert logging.getLogger().handlers == []


@pytest.mark.usefixtures("logging_isole")
def test_journal_fichier_masque_et_additif(tmp_path: Path) -> None:
    configure_logging()
    avant = len(logging.getLogger("deskgate").handlers)
    path = attach_file_log(tmp_path)
    lg = logging.getLogger("deskgate")
    try:
        assert len(lg.handlers) == avant + 1
        lg.info("rappel vers http://h/w?signature=SECRET123")
        for h in lg.handlers:
            h.flush()
        texte = path.read_text(encoding="utf-8")
        assert path == tmp_path / "logs" / "runner.log"
        assert "rappel vers" in texte
        assert "SECRET123" not in texte
    finally:
        for h in list(lg.handlers) + list(logging.getLogger().handlers):
            if isinstance(h, logging.FileHandler):
                h.close()

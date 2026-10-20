"""Signature absente partout (SEC-05) et audit complet du parcours de rappel (SEC-06)."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from tests.e2e.conftest import (
    FAKE_CAPS,
    TOKEN,
    kill_tree,
    runner_env,
    start_runner,
    wait_callback_state,
    wait_health,
    write_config,
)

from _support.fake_n8n import DROP, OK, SERVER_ERROR, FakeN8n

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows seul"),
]

SWEEP = "SWEEPq7"
SIG = f"{SWEEP}a+b/c=d%2Bz"


def _raw(
    port: int, method: str, path: str, body: object | None = None, token: str | None = TOKEN
) -> tuple[int, str]:
    """Appel brut : renvoie le statut et le texte de la réponse, sans l'interpréter."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310 (http local)
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


@contextmanager
def _journee(
    data_home: Path, instance_name: str, port: int, log_path: Path
) -> Iterator[subprocess.Popen[bytes]]:
    write_config(data_home, port, capabilities=FAKE_CAPS, callback={"max_backoff_s": 2})
    env = runner_env(data_home, instance_name)
    env["DESKGATE_LOG_LEVEL"] = "INFO"
    proc = start_runner(env, log_path=log_path)
    try:
        wait_health(port, proc)
        yield proc
    finally:
        if proc.poll() is None:
            kill_tree(proc)


def _parcours(
    data_home: Path, instance_name: str, port: int, fake: FakeN8n, log_path: Path
) -> tuple[str, list[str]]:
    """Joue le parcours complet, arrête le runner, renvoie (job_id, réponses brutes)."""
    fake.script(SERVER_ERROR, DROP)
    fake.default = OK
    reponses: list[str] = []
    with _journee(data_home, instance_name, port, log_path) as proc:
        status, texte = _raw(
            port,
            "POST",
            "/jobs",
            {
                "capability": "demo.sleep",
                "params": {"n": 0.05, "api_key": "PARAM-SECRET"},
                "callback": {"url": fake.url(signature=SIG)},
            },
        )
        assert status == 202, texte
        reponses.append(texte)
        job_id = str(json.loads(texte)["job_id"])
        wait_callback_state(data_home, job_id, {"delivered"}, timeout=40)
        for methode, chemin in (
            ("GET", f"/jobs/{job_id}"),
            ("GET", f"/jobs/{job_id}/logs"),
            ("POST", f"/jobs/{job_id}/cancel"),
        ):
            _, texte = _raw(port, methode, chemin)
            reponses.append(texte)
        status, texte = _raw(
            port,
            "POST",
            "/jobs",
            {
                "capability": "demo.sleep",
                "params": {},
                "callback": {"url": f"http://evil.example/webhook-waiting/1?signature={SIG}"},
            },
        )
        assert status == 422, texte
        reponses.append(texte)
        status, texte = _raw(
            port,
            "POST",
            "/jobs",
            {
                "capability": "demo.sleep",
                "params": {},
                "champ_inconnu": 1,
                "callback": {"url": fake.url(signature=SIG)},
            },
        )
        assert status == 422, texte
        reponses.append(texte)
        status, texte = _raw(
            port,
            "POST",
            "/jobs",
            {
                "capability": "demo.sleep",
                "params": {},
                "callback": {"url": fake.url(signature=SIG)},
            },
            token=None,
        )
        assert status == 401, texte
        reponses.append(texte)
        kill_tree(proc)
        for stream in (proc.stdout, proc.stderr):
            if stream is not None:
                stream.close()
    return job_id, reponses


def _lignes(home: Path, sql: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(home / "deskgate.db", timeout=5)
    try:
        conn.row_factory = sqlite3.Row
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


@pytest.mark.timeout(90)
def test_signature_absente_partout(
    data_home: Path, instance_name: str, free_port: int, fake_n8n: FakeN8n, tmp_path: Path
) -> None:
    journal = tmp_path / "runner.log"
    _, reponses = _parcours(data_home, instance_name, free_port, fake_n8n, journal)
    for texte in reponses:
        assert SWEEP not in texte
    texte_journal = journal.read_text(encoding="utf-8", errors="replace")
    assert SWEEP not in texte_journal
    assert "signature=***" in texte_journal  # la ligne INFO httpx2 a été émise puis masquée
    travail = tmp_path / "bim" / "travail"
    for fichier in travail.rglob("*"):
        if fichier.is_file():
            assert SWEEP not in fichier.read_text(encoding="utf-8", errors="replace"), fichier
    for ligne in _lignes(data_home, "SELECT detail_json FROM audit"):
        assert SWEEP not in (ligne["detail_json"] or "")
        assert "PARAM-SECRET" not in (ligne["detail_json"] or "")
    for ligne in _lignes(data_home, "SELECT last_error_redacted FROM callbacks"):
        assert SWEEP not in (ligne["last_error_redacted"] or "")
    for ligne in _lignes(data_home, "SELECT callback_url, params_json FROM jobs"):
        assert SWEEP not in (ligne["callback_url"] or "")
        assert SWEEP not in (ligne["params_json"] or "")


@pytest.mark.timeout(90)
def test_audit_parcours(
    data_home: Path, instance_name: str, free_port: int, fake_n8n: FakeN8n, tmp_path: Path
) -> None:
    _parcours(data_home, instance_name, free_port, fake_n8n, tmp_path / "runner.log")
    lignes = _lignes(data_home, "SELECT event, detail_json FROM audit ORDER BY id")
    par_evenement: dict[str, list[dict[str, object]]] = {}
    for ligne in lignes:
        par_evenement.setdefault(ligne["event"], []).append(json.loads(ligne["detail_json"]))
    soumis = par_evenement["job.submitted"][0]
    assert {"client", "capability", "params", "timeout_s"} <= set(soumis)
    assert any(d.get("code") == "callback_host_not_allowed" for d in par_evenement["job.refused"])
    reussi = par_evenement["job.succeeded"][0]
    assert {"duration_s", "started_at", "finished_at"} <= set(reussi)
    tentatives = par_evenement["callback.attempt"]
    assert len(tentatives) >= 3
    for detail in tentatives:
        assert {"attempt", "http_status", "error", "decision"} <= set(detail)
    assert "callback.delivered" in par_evenement

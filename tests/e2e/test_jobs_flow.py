"""Flux nominal des tâches par HTTP réel (JOB-01, 02, 04, 08, 09)."""

from __future__ import annotations

import json
import re
import sys
import time

import pytest
from tests.e2e.conftest import CALLBACK_URL, Runner, api, wait_status

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows seul"),
]


def _submit(r: Runner, capability: str, params: dict[str, object], **extra: object) -> str:
    body: dict[str, object] = {
        "capability": capability,
        "params": params,
        "callback": {"url": CALLBACK_URL},
        **extra,
    }
    status, resp = api(r.port, "POST", "/jobs", body)
    assert status == 202, resp
    return str(resp["job_id"])


@pytest.mark.timeout(90)
def test_soumission_suivi_et_journaux(jobs_runner: Runner) -> None:
    debut = time.monotonic()
    status, resp = api(
        jobs_runner.port,
        "POST",
        "/jobs",
        {"capability": "demo.sleep", "params": {"n": 0.3}, "callback": {"url": CALLBACK_URL}},
    )
    assert time.monotonic() - debut < 1.0
    assert status == 202
    assert re.fullmatch(r"[0-9a-f]{12}", resp["job_id"])
    assert resp["status"] == "queued"
    job = wait_status(jobs_runner.port, resp["job_id"], {"succeeded"})
    texte = json.dumps(job)
    assert "E2E-SECRET-SIG" not in texte
    assert "webhook-waiting" not in texte
    status, logs = api(jobs_runner.port, "GET", f"/jobs/{resp['job_id']}/logs")
    assert status == 200
    assert logs["complete"] is True
    assert json.dumps(logs)
    assert "E2E-SECRET-SIG" not in json.dumps(logs)
    assert "début du sommeil" in json.dumps(logs, ensure_ascii=False)


@pytest.mark.timeout(90)
def test_artefact_sous_work_dir(jobs_runner: Runner) -> None:
    job_id = _submit(jobs_runner, "demo.artifact_ok", {})
    job = wait_status(jobs_runner.port, job_id, {"succeeded"})
    assert job["artifacts"][0]["path"] == f"/data/travail/{job_id}/sortie.txt"
    fichier = jobs_runner.home.parent / "bim" / "travail" / job_id / "sortie.txt"
    assert fichier.is_file()


@pytest.mark.timeout(90)
def test_ordre_de_soumission(jobs_runner: Runner) -> None:
    a = _submit(jobs_runner, "demo.sleep", {"n": 1})
    b = _submit(jobs_runner, "demo.sleep", {"n": 0.1})
    ja = wait_status(jobs_runner.port, a, {"succeeded"})
    jb = wait_status(jobs_runner.port, b, {"succeeded"})
    assert jb["started_at"] >= ja["finished_at"]


@pytest.mark.timeout(90)
def test_idempotence_et_annulation(jobs_runner: Runner) -> None:
    premier = _submit(jobs_runner, "demo.sleep", {"n": 5}, idempotency_key="wf1-exec1")
    status, resp = api(
        jobs_runner.port,
        "POST",
        "/jobs",
        {
            "capability": "demo.sleep",
            "params": {"n": 5},
            "callback": {"url": CALLBACK_URL},
            "idempotency_key": "wf1-exec1",
        },
    )
    assert status == 409
    assert resp["error"]["job_id"] == premier
    api(jobs_runner.port, "POST", f"/jobs/{premier}/cancel")
    wait_status(jobs_runner.port, premier, {"cancelled"}, timeout=15)


@pytest.mark.timeout(90)
def test_annulation_idempotente(jobs_runner: Runner) -> None:
    premier = _submit(jobs_runner, "demo.sleep", {"n": 5})
    wait_status(jobs_runner.port, premier, {"running"})
    status, resp = api(jobs_runner.port, "POST", f"/jobs/{premier}/cancel")
    assert status == 200
    wait_status(jobs_runner.port, premier, {"cancelled"}, timeout=15)
    status, resp = api(jobs_runner.port, "POST", f"/jobs/{premier}/cancel")
    assert status == 200
    assert resp["status"] == "cancelled"


@pytest.mark.timeout(90)
def test_erreurs_http(jobs_runner: Runner) -> None:
    status, resp = api(
        jobs_runner.port,
        "POST",
        "/jobs",
        {"capability": "demo.inconnue", "params": {}, "callback": {"url": CALLBACK_URL}},
    )
    assert status == 404
    assert resp["error"]["code"] == "capability_not_found"
    status, _ = api(jobs_runner.port, "GET", "/jobs/000000000000", token=None)
    assert status == 401
    status, resp = api(jobs_runner.port, "GET", "/jobs/000000000000")
    assert status == 404
    assert resp["error"]["code"] == "job_not_found"

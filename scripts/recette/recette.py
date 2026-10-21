"""Scénarios de recette : smoke, acc01, acc02. Preuve JSON sans secret.

Déroulé : webhook n8n -> Deskgate -> Wait -> rappel -> nœud final. Aucun secret en sortie.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from _commun import (
    DATA,
    RUNNER,
    SCHTASKS,
    TASK_NAME,
    TASKKILL,
    WEBHOOK,
    WORKFLOW_ID,
    N8nSession,
    api_get,
    assert_started_by_task,
    db_rows,
    deskgate_processes,
    http,
    listener_pid,
    mask,
    plugin_rss_mb,
    provenance,
    read_env,
    wait_health,
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _max_seq() -> int:
    rows = db_rows("SELECT MAX(seq) FROM jobs")
    return int(rows[0][0] or 0)


def _exec_ids(key: str) -> list[int]:
    code, reply = api_get(key, f"/executions?workflowId={WORKFLOW_ID}&limit=20")
    if code != 200 or not isinstance(reply, dict):
        return []
    return [int(e["id"]) for e in reply.get("data", [])]


def _exec_status(key: str, exec_id: int) -> str:
    code, reply = api_get(key, f"/executions/{exec_id}")
    return str(reply.get("status")) if code == 200 and isinstance(reply, dict) else "?"


def _exec_node(key: str, exec_id: int) -> tuple[str | None, Any]:
    code, reply = api_get(key, f"/executions/{exec_id}?includeData=true")
    if code != 200 or not isinstance(reply, dict):
        return None, None
    run_data = reply.get("data", {}).get("resultData", {}).get("runData", {})
    for name in ("Succes", "Echec ou delai"):
        if name in run_data:
            try:
                return name, run_data[name][0]["data"]["main"][0][0]["json"]
            except (KeyError, IndexError, TypeError):
                return name, None
    return None, None


def run(scenario: str, args: argparse.Namespace) -> int:
    started = _now()
    proof: dict[str, Any] = {
        "scenario": scenario,
        "started_at": started,
        "ended_at": None,
        "job_id": None,
        "job_status": None,
        "error_code": None,
        "duration_s": None,
        "n8n_status": None,
        "node": None,
        "node_output": None,
        "callback_state": None,
        "callback_attempts": None,
        "provenance": [],
        "peak_rss_mb": 0.0,
        "bcf_host_path": None,
        "bcf_size": None,
        "kill_at": None,
        "survivors": None,
        "relaunch_provenance": None,
        "verdict": False,
    }
    if not wait_health(RUNNER + "/health", 30):
        print("runner injoignable")
        return 2
    chain = provenance(listener_pid())
    proof["provenance"] = chain
    if scenario != "smoke" and not assert_started_by_task(chain):
        print("runner non démarré par le Planificateur : " + mask(json.dumps(chain)))
        return 2

    params = (
        json.loads(Path(args.params_file).read_text(encoding="utf-8")) if args.params_file else {}
    )
    env = read_env()
    session = N8nSession()
    if not session.login(env["N8N_OWNER_EMAIL"], env["N8N_OWNER_PASSWORD"]):
        print("connexion n8n impossible")
        return 2
    key_id, key = session.create_api_key("recette-" + scenario)
    password = env["N8N_OWNER_PASSWORD"]
    step = 5 if scenario == "smoke" else 30
    try:
        seq0 = _max_seq()
        exec0 = max(_exec_ids(key), default=0)
        end = time.monotonic() + 90
        while True:
            code, _ = http("POST", WEBHOOK, {"params": params, "timeout": args.timeout})
            if code != 404 or time.monotonic() > end:
                break
            time.sleep(3)
        print(f"webhook : HTTP {code}")
        if code != 200:
            return 1

        job_id = None
        end = time.monotonic() + 120
        while job_id is None and time.monotonic() < end:
            rows = db_rows("SELECT id FROM jobs WHERE seq > ? ORDER BY seq ASC LIMIT 1", (seq0,))
            if rows:
                job_id = rows[0][0]
            else:
                time.sleep(2)
        if job_id is None:
            print("aucun job créé")
            return 1
        proof["job_id"] = job_id
        exec_id = None
        end = time.monotonic() + 60
        while exec_id is None and time.monotonic() < end:
            new = [i for i in _exec_ids(key) if i > exec0]
            if new:
                exec_id = min(new)
            else:
                time.sleep(2)
        if exec_id is None:
            print("aucune exécution n8n")
            return 1

        running_since: float | None = None
        killed = False
        limit = time.monotonic() + args.timeout + 900
        while time.monotonic() < limit:
            proof["peak_rss_mb"] = max(proof["peak_rss_mb"], round(plugin_rss_mb(), 1))
            status = db_rows("SELECT status FROM jobs WHERE id = ?", (job_id,))[0][0]
            n8n_status = _exec_status(key, exec_id)
            print(
                mask(f"{_now()} job={status} n8n={n8n_status} rss_max={proof['peak_rss_mb']} Mo"),
                flush=True,
            )
            if scenario == "acc02" and not killed and status == "running":
                running_since = running_since or time.monotonic()
                if time.monotonic() - running_since >= args.kill_after_s:
                    pid = listener_pid()
                    proof["kill_at"] = _now()
                    subprocess.run(  # noqa: S603 - chemin absolu System32, arguments fixes
                        [TASKKILL, "/F", "/T", "/PID", str(pid)],
                        capture_output=True,
                        check=False,
                    )
                    time.sleep(10)
                    proof["survivors"] = [
                        {"pid": p.pid, "cmdline": mask(" ".join(p.cmdline()))}
                        for p in deskgate_processes()
                    ]
                    subprocess.run(  # noqa: S603 - chemin absolu System32, arguments fixes
                        [SCHTASKS, "/Run", "/TN", TASK_NAME], capture_output=True, check=False
                    )
                    if not wait_health(RUNNER + "/health", 60):
                        print("runner non relancé")
                        return 1
                    proof["relaunch_provenance"] = provenance(listener_pid())
                    killed = True
                    continue
            if n8n_status in ("success", "error"):
                break
            time.sleep(step)

        proof["n8n_status"] = _exec_status(key, exec_id)
        node, output = _exec_node(key, exec_id)
        proof["node"] = node
        proof["node_output"] = output
        job = db_rows(
            "SELECT status, error_code, started_at, finished_at FROM jobs WHERE id = ?", (job_id,)
        )[0]
        proof["job_status"], proof["error_code"] = job[0], job[1]
        end = time.monotonic() + 60
        while time.monotonic() < end:
            rows = db_rows("SELECT state, attempts FROM callbacks WHERE job_id = ?", (job_id,))
            if rows:
                proof["callback_state"], proof["callback_attempts"] = rows[0]
                if str(rows[0][0]).startswith(("delivered", "abandoned")):
                    break
            time.sleep(2)

        if isinstance(output, dict) and isinstance(output.get("duree_s"), (int, float)):
            proof["duration_s"] = output["duree_s"]
        else:
            try:
                proof["duration_s"] = round(
                    (
                        datetime.fromisoformat(str(job[3])) - datetime.fromisoformat(str(job[2]))
                    ).total_seconds(),
                    1,
                )
            except (TypeError, ValueError):
                proof["duration_s"] = None
        artefacts = output.get("artefacts") if isinstance(output, dict) else None
        chemins = [str(a.get("path") if isinstance(a, dict) else a) for a in (artefacts or [])]
        bcf = next((c for c in chemins if c.endswith("conflits.bcf")), None)
        if bcf:
            host = Path("C:/BIM") / str(bcf).removeprefix("/data/")
            proof["bcf_host_path"] = host.as_posix()
            proof["bcf_size"] = host.stat().st_size if host.exists() else None

        succes = node == "Succes" and bcf is not None
        if scenario == "smoke":
            proof["verdict"] = succes
        elif scenario == "acc01":
            proof["min_duration_s"] = args.min_duration_s
            proof["verdict"] = succes and (proof["duration_s"] or 0) > args.min_duration_s
        else:
            proof["verdict"] = bool(
                node == "Echec ou delai"
                and isinstance(output, dict)
                and output.get("resultat") == "interrupted"
                and proof["job_status"] == "interrupted"
                and proof["callback_state"] == "delivered"
            )
    finally:
        session.delete_api_key(key_id)
        proof["ended_at"] = _now()
        text = mask(json.dumps(proof, ensure_ascii=False, indent=2, default=str))
        if key in text or password in text:
            raise RuntimeError("secret détecté dans la preuve : écriture refusée")
        out = args.out or DATA / "recette" / f"{scenario}-{datetime.now(UTC):%Y%m%dT%H%M%S}.json"
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
        print(text)
        print(f"preuve : {out}")
    return 0 if proof["verdict"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="scenario", required=True)
    for name in ("smoke", "acc01", "acc02"):
        p = sub.add_parser(name)
        p.add_argument("--params-file")
        p.add_argument("--timeout", type=int, default=600 if name == "smoke" else 14400)
        p.add_argument("--out")
        if name == "acc01":
            p.add_argument("--min-duration-s", type=int, default=600)
        if name == "acc02":
            p.add_argument("--kill-after-s", type=int, default=90)
    return run(*(lambda a: (a.scenario, a))(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())

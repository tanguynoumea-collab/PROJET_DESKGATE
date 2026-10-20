"""Faux plugins de test (stdlib seule) : signature ``fn(params, ctx) -> dict``."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Any


def sleep(params: dict[str, Any], ctx: Any) -> dict[str, Any]:
    n = float(params.get("n", 1.0))
    ignore_cancel = bool(params.get("ignore_cancel", False))
    ctx.log("début du sommeil")
    fin = time.monotonic() + n
    pas = 0
    while time.monotonic() < fin:
        if ctx.cancelled() and not ignore_cancel:
            return {"summary": {"cancelled": True}}
        if pas < 10:
            pas += 1
            ctx.progress(min(100.0, pas * 10.0))
        time.sleep(0.05)
    summary: dict[str, Any] = {"slept": n}
    if params.get("report_env"):
        summary["deskgate_env"] = sorted(k for k in os.environ if k.startswith("DESKGATE"))
        summary["pythonutf8"] = os.environ.get("PYTHONUTF8")
    return {"summary": summary}


def spawn_orphan(params: dict[str, Any], ctx: Any) -> dict[str, Any]:
    orphan = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    with open(os.path.join(ctx.work_dir, "orphan.pid"), "w", encoding="utf-8") as f:
        f.write(str(orphan.pid))
    with open(os.path.join(ctx.work_dir, "plugin.pid"), "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    time.sleep(float(params.get("sleep", 60)))
    return {"summary": {}}


def bad_result(params: dict[str, Any], ctx: Any) -> Any:
    mode = params.get("mode", "not_dict")
    path = os.path.join(ctx.work_dir, "result.json")
    if mode == "not_dict":
        return [1]
    if mode == "garbage":
        with open(path, "w", encoding="utf-8") as f:
            f.write("{")
    elif mode == "huge":
        import json

        doc = {
            "protocol": 1,
            "ok": True,
            "summary": {"x": "a" * 1_100_000},
            "data": {},
            "artifacts": [],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f)
    os._exit(0)


def chatty(params: dict[str, Any], ctx: Any) -> dict[str, Any]:
    mb = int(params.get("mb", 4))
    bloc = "x" * 65535 + "\n"
    for _ in range(mb * 16):
        sys.stdout.write(bloc)
    sys.stdout.flush()
    for _ in range(mb * 16):
        sys.stderr.write(bloc)
    sys.stderr.flush()
    return {"summary": {"mb": mb}}


def artifact_outside(params: dict[str, Any], ctx: Any) -> dict[str, Any]:
    ctx.artifact(params.get("path", "C:/Windows/win.ini"), "txt")
    return {"summary": {}}


def artifact_ok(params: dict[str, Any], ctx: Any) -> dict[str, Any]:
    chemin = os.path.join(ctx.work_dir, "sortie.txt")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("contenu")
    ctx.artifact(chemin, "txt")
    return {"summary": {"ok": True}}


def exit_code(params: dict[str, Any], ctx: Any) -> dict[str, Any]:
    os._exit(int(params.get("code", 3)))


def fail(params: dict[str, Any], ctx: Any) -> dict[str, Any]:
    raise ValueError("échec volontaire")

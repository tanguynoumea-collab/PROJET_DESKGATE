"""Worker Deskgate : exécuté par chemin, bibliothèque standard seule (D-09).

Lancé par ``<python du plugin> <chemin>/run.py --input <work_dir>/input.json``. Le contrat de
fichiers est dupliqué en littéral : ce module ne doit rien importer du cœur.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import time
import traceback
from typing import Any

PROTOCOL = 1

CONTRACT: dict[str, Any] = {
    "protocol": 1,
    "files": {
        "input": "input.json",
        "events": "events.jsonl",
        "result": "result.json",
        "cancel": "cancel.flag",
        "log": "job.log",
    },
    "input_keys": [
        "capability",
        "entry",
        "job_id",
        "params",
        "protocol",
        "settings",
        "sys_path",
        "work_dir",
    ],
    "event_types": ["artifact", "progress"],
    "result_ok_keys": ["artifacts", "data", "ok", "protocol", "summary"],
    "result_error_keys": ["error", "ok", "protocol"],
}


def _replace(src: str, dst: str) -> None:
    """``os.replace`` avec réessais (PermissionError : antivirus, lecteur concurrent)."""
    for i in range(10):
        try:
            os.replace(src, dst)
        except PermissionError:
            time.sleep(0.05 * (i + 1))
        else:
            return
    os.replace(src, dst)


def _write_atomic(path: str, obj: dict[str, Any]) -> None:
    tmp = path + ".tmp"
    text = json.dumps(obj, ensure_ascii=False, allow_nan=False)
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    _replace(tmp, path)


class Ctx:
    """Contexte du plugin : journal sur stderr, événements dans events.jsonl."""

    def __init__(self, inp: dict[str, Any]) -> None:
        self.job_id: str = inp["job_id"]
        self.work_dir: str = inp["work_dir"]
        self.params: dict[str, Any] = inp["params"]
        self.settings: dict[str, Any] = inp.get("settings") or {}
        self.artifacts: list[dict[str, str]] = []
        self._events = open(  # noqa: SIM115  fermé à la fin du processus
            os.path.join(self.work_dir, "events.jsonl"), "ab", buffering=0
        )
        self._flag = os.path.join(self.work_dir, "cancel.flag")

    def _emit(self, **ev: Any) -> None:
        self._events.write((json.dumps(ev, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))

    def log(self, msg: str) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)

    def progress(self, pct: float, message: str = "") -> None:
        self._emit(type="progress", pct=float(pct), message=str(message))

    def artifact(self, path: str, kind: str) -> None:
        self.artifacts.append({"kind": kind, "path": str(path)})
        self._emit(type="artifact", kind=kind, path=str(path))

    def cancelled(self) -> bool:
        return os.path.exists(self._flag)


def main(argv: list[str]) -> int:
    sys.path.pop(0)  # dossier du script : évite de masquer des modules (sans option -P)
    with open(argv[argv.index("--input") + 1], encoding="utf-8") as f:
        inp = json.load(f)
    ctx = Ctx(inp)
    res = os.path.join(inp["work_dir"], "result.json")
    try:
        for p in reversed(inp.get("sys_path", [])):
            sys.path.insert(0, p)
        mod, _, fn = inp["entry"].partition(":")
        out = getattr(importlib.import_module(mod), fn)(inp["params"], ctx)
        if not isinstance(out, dict):
            raise TypeError("le plugin doit renvoyer un dict")
        _write_atomic(
            res,
            {
                "protocol": PROTOCOL,
                "ok": True,
                "summary": out.get("summary", {}),
                "data": out.get("data", {}),
                "artifacts": out.get("artifacts") or ctx.artifacts,
            },
        )
    except BaseException as exc:
        traceback.print_exc()
        # Un plugin classe ses erreurs par l'attribut `error_code` (str).
        code = getattr(exc, "error_code", None)
        etype = code if isinstance(code, str) and code else type(exc).__name__
        _write_atomic(
            res,
            {
                "protocol": PROTOCOL,
                "ok": False,
                "error": {"type": etype, "message": str(exc)[:2000]},
            },
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

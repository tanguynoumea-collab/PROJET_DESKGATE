# SPDX-License-Identifier: MIT
"""Écriture du BCF par appel de deskgate-bcf en sous-processus (frontière GPL, CAP-05)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .params import ClashError

NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW ; jamais de breakaway : le processus reste dans le Job


def write_bcf(
    settings: dict[str, Any], doc: dict[str, Any], work_dir: str | Path, *, timeout: float = 600
) -> str:
    exe = settings.get("bcf_executable")
    if not isinstance(exe, str) or not os.path.isabs(exe) or not os.path.isfile(exe):
        raise ClashError(
            "bcf_unavailable",
            "deskgate-bcf introuvable : renseignez settings.bcf_executable "
            "de la capacité ifc.clash.",
        )
    work = Path(work_dir)
    src = work / "bcf-input.json"
    dst = work / "conflits.bcf"
    with src.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    try:
        r = subprocess.run(  # noqa: S603 - liste, sans shell, exécutable issu de la configuration
            [exe, "write", "--input", str(src), "--output", str(dst)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        raise ClashError("bcf_write_failed", "Écriture du BCF : délai dépassé.") from None
    except OSError as exc:
        raise ClashError("bcf_write_failed", f"Écriture du BCF impossible : {exc}") from exc
    if r.returncode == 2:
        raise ClashError("bcf_contract_error", (r.stderr or "document refusé")[:2000])
    if r.returncode != 0:
        raise ClashError(
            "bcf_write_failed",
            f"Écriture du BCF échouée (code {r.returncode}) : {(r.stderr or '')[:2000]}",
        )
    return str(dst)
